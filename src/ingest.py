#!/usr/bin/env python3
"""Turn a batch file into queue records: normalise, dedupe, suppress, slug.

Writes nothing itself. Every record goes in through src/store.py.

Sources:
  .csv    columns: company, domain, and optionally lane, client, context, signal, id
  .jsonl  rows already in record shape
  a dir   of .md/.txt/.eml dumps; filename is the company, contents are the context

Rows that cannot be queued are still written, as records in state `dropped`
with a drop_reason, so a batch is auditable and re-runnable. A row already
present in the queue from an earlier run is reported and not written again.

  python -m src.ingest batches/phase1-sample.csv --client productive --lane domains
"""
import argparse
import csv
import glob
import json
import os
import re
import sys

from . import clients as client_config, events, store

ROOT = store.ROOT
# The tracked template. It carries the mechanism and no real customer, because
# the roster of who is paying us is confidential and a tracked file is a file
# that reaches every clone.
SUPPRESS = os.path.join(ROOT, "config", "suppress.txt")
# The real roster, gitignored. `load_suppress()` merges it over the template,
# so the operational list lives on the machine that does the outreach and
# nowhere else. See ENGAGEMENT-HYGIENE.md.
SUPPRESS_LOCAL = os.path.join(ROOT, "config", "suppress.local.txt")


# Prefixes that are the same site rather than a different company, and the
# one list of them. It lives in `dedupe` because that is where "are these
# the same company" is decided, and importing it here rather than keeping a
# second copy is the whole point of this function's shape: the two used to
# disagree, so `mail.acme.test` imported as a company of its own while the
# hygiene check matched it against `acme.test`'s history. The preview said
# "we have contacted this company" about a record that had never been
# contacted, and outreach to both would have been the same account twice.


def norm_domain(d):
    """The domain a row is about. Normalises; does not judge.

    "Not a domain" survives this unchanged - `HOSTNAME` below is what
    refuses. A trailing dot is stripped rather than refused: `acme.test.`
    is a fully qualified name, not a typo, and it was being excluded as
    "not the shape of a hostname" while matching `acme.test` everywhere
    else.
    """
    from . import dedupe

    if not d:
        return ""
    d = d.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0].split("?")[0].strip()
    return dedupe.normalise_domain(d) or ""


# What a hostname can actually look like. `norm_domain` *normalises* - it
# lowercases, strips a scheme and a path - and does not judge, so
# "not a domain" survives it unchanged. Validation is this, and it lives
# here so the import path and the discovery path cannot drift into two
# different opinions about what a domain is.
HOSTNAME = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def is_hostname(value):
    """Is this the shape of a hostname? Normalises first."""
    return bool(HOSTNAME.match(norm_domain(value) or ""))


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:40] or "record"


def _read_suppress(path):
    """One domain per line, # comments stripped, normalised the same way input is."""
    if not os.path.exists(path):
        return set()
    out = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line:
                out.add(norm_domain(line))
    return out


def suppress_sources():
    """Which suppression files actually exist, in merge order.

    Exposed so a caller can tell "the roster is empty" from "the roster is
    missing". Those are different states and reading one as the other is how a
    live customer gets cold-sequenced by a system reporting itself healthy.
    """
    return [p for p in (SUPPRESS, SUPPRESS_LOCAL) if os.path.exists(p)]


def load_suppress(path=None):
    """The domains never to sequence.

    An explicit `path` reads exactly that file and nothing else, which is what
    every fixture-driven test wants. The default merges the tracked template
    with the gitignored local roster, so the real customer list can exist on
    this machine without existing in git.
    """
    if path is not None:
        return _read_suppress(path)
    out = set()
    for source in (SUPPRESS, SUPPRESS_LOCAL):
        out |= _read_suppress(source)
    return out


def from_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            yield {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}


def from_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def from_dir(path):
    for fp in sorted(glob.glob(os.path.join(path, "*"))):
        if os.path.isdir(fp) or not fp.lower().endswith((".md", ".txt", ".eml")):
            continue
        name = os.path.splitext(os.path.basename(fp))[0]
        with open(fp, encoding="utf-8", errors="replace") as f:
            text = f.read()
        m = re.search(r"(?:^|\s)((?:[a-z0-9-]+\.)+[a-z]{2,})(?:\s|/|$)", text, re.I)
        yield {"company": name.replace("-", " ").title(),
               "domain": m.group(1) if m else "",
               "context": text}


def read_rows(source):
    if os.path.isdir(source):
        return list(from_dir(source))
    if source.endswith(".jsonl"):
        return list(from_jsonl(source))
    if source.endswith(".csv"):
        return list(from_csv(source))
    sys.exit("source must be .csv, .jsonl or a directory")


def key_of(client, domain, company):
    """Dedupe key. Domain when there is one, company slug when there is not."""
    return (client, domain or slug(company))


# Columns a CSV may carry that belong on company_facts rather than being
# dropped.  Keys are the lowered CSV header, values are the company_facts key.
# The Productive export names its positioning columns `headline` and
# `industry`; the Software Agencies sheet names its headcount columns
# `company_employee_count`, `company_size`,
# `company_total_headcount_growth_12_months` and
# `company_product_and_services`.  A column absent from a particular file is
# simply not present in the row dict and is silently skipped.
INGEST_TO_FACTS = {
    "headline": "headline",
    "industry": "industry",
    "company_employee_count": "headcount",
    "company_size": "employee_range",
    "company_total_headcount_growth_12_months": "headcount_growth_12m",
    "company_product_and_services": "products",
}


def client_config_exists(client):
    return os.path.exists(client_config.path_for(client))


def run(source, client, lane, suppress_path=None):
    """Build records from `source` and hand them to the store. Returns a summary."""
    rows = read_rows(source)
    suppress = load_suppress(suppress_path)
    existing = store.load()
    existing_keys = {key_of(r.get("client"), r.get("domain"), r.get("company"))
                     for r in existing}
    taken_ids = {r.get("id") for r in existing}

    origin = os.path.basename(os.path.normpath(source))
    batch = {"id": f"{origin}-{store.now()[:19]}", "source": origin,
             "at": store.now(), "client": client, "lane": lane}
    checked_clients = set()
    run_keys = set()
    records, skipped = [], []

    def add(row_client, row_lane, company, domain, context, signal, raw_id, reason,
            row=None):
        rid = slug(raw_id or company or domain)
        base, n = rid, 2
        while rid in taken_ids:
            rid = f"{base}-{n}"
            n += 1
        taken_ids.add(rid)
        rec = store.new_record(rid, row_lane, row_client, company, domain, context, signal)
        rec["batch"] = batch
        if row:
            for csv_col, fact_key in INGEST_TO_FACTS.items():
                val = (row.get(csv_col) or "").strip()
                if val:
                    rec["company_facts"][fact_key] = val
        if reason:
            rec["state"] = "dropped"
            rec["drop_reason"] = reason
        store.log(rec, rec["state"], reason or f"ingested from {origin}")
        events.record(rec, events.BATCH_INGESTED, batch=batch["id"])
        if reason and "suppressed" in reason:
            events.record(rec, events.RECORD_SUPPRESSED, reason=reason)
        elif reason:
            events.record(rec, events.RECORD_DROPPED, reason=reason)
        records.append(rec)
        return rec

    for row in rows:
        row_client = row.get("client") or client
        row_lane = row.get("lane") or lane
        domain = norm_domain(row.get("domain"))
        company = row.get("company") or domain
        context = row.get("context", "")
        signal = row.get("signal", "")
        raw_id = row.get("id")

        if row_client not in checked_clients:
            if not client_config_exists(row_client):
                sys.exit(f"no config/clients/{row_client}.yaml, refusing to ingest")
            checked_clients.add(row_client)

        key = key_of(row_client, domain, company)
        if key in existing_keys:
            skipped.append((company, "already in queue"))
            continue

        if row_lane not in store.LANES:
            add(row_client, lane, company, domain, context, signal, raw_id,
                f"unknown lane: {row_lane}", row=row)
            continue
        if not domain:
            add(row_client, row_lane, company, domain, context, signal, raw_id,
                "no domain", row=row)
            continue
        if not is_hostname(domain):
            # The rule this module defines, applied by this module.
            #
            # `HOSTNAME` and `is_hostname` had exactly two consumers -
            # `discovery` and the web upload - and `run` was not one of them,
            # so the CLI import path queued whatever survived `norm_domain`
            # non-empty. Measured: `not a domain`, `=importxml(1)` and the
            # residue of a spreadsheet injection all became records with that
            # string as their domain, and then carried it into MX lookups,
            # provider payloads and client exports. The comment above
            # `HOSTNAME` says it lives here "so the import path and the
            # discovery path cannot drift into two different opinions about
            # what a domain is"; the two import paths had drifted into
            # exactly that.
            add(row_client, row_lane, company, domain, context, signal, raw_id,
                "not a usable domain: this is not the shape of a hostname",
                row=row)
            continue
        if domain in suppress:
            add(row_client, row_lane, company, domain, context, signal, raw_id,
                "suppressed (live account)", row=row)
            continue
        if key in run_keys:
            add(row_client, row_lane, company, domain, context, signal, raw_id,
                "duplicate domain", row=row)
            continue

        run_keys.add(key)
        add(row_client, row_lane, company, domain, context, signal, raw_id,
            None, row=row)

    if records:
        store.append(records, note=f"ingested from {origin}")

    return {
        "queued": [r["id"] for r in records if r["state"] == "queued"],
        "dropped": [(r["id"], r["drop_reason"]) for r in records if r["state"] == "dropped"],
        "skipped": skipped,
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.ingest")
    p.add_argument("source")
    p.add_argument("--client", required=True)
    p.add_argument("--lane", required=True, choices=list(store.LANES))
    a = p.parse_args(argv)

    result = run(a.source, a.client, a.lane)
    print(f"queued {len(result['queued'])} record(s) -> {store.queue_path()}")
    for rid, reason in result["dropped"]:
        print(f"  dropped {rid}: {reason}")
    for company, reason in result["skipped"]:
        print(f"  skipped {company}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
