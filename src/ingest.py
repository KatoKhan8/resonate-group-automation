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

from . import clients as client_config, columns, events, identity, linkedin, store

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
    """Yield rows with original header names preserved.

    The `columns` module maps foreign headers onto canonical fields by their
    original spelling; lowercasing them here would break that mapping. Values
    are still stripped of surrounding whitespace.
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            yield {k.strip(): (v or "").strip() for k, v in row.items() if k}


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


def client_config_exists(client):
    return os.path.exists(client_config.path_for(client))


def run(source, client, lane, suppress_path=None):
    """Build records from `source` and hand them to the store. Returns a summary.

    For CSV sources, the `columns` module maps foreign headers onto canonical
    fields. Contact columns (email, linkedin, name, first_name, last_name,
    title) become contacts on the record. Operational columns (headcount
    growth, products and services, employee count) are attached to
    `company_facts`. A LinkedIn URL that is not a profile URL (company page,
    search result, truncated share link) is refused, not stored.
    """
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

    def add(row_client, row_lane, company, domain, context, signal, raw_id,
            reason, contacts=None, company_facts=None):
        rid = slug(raw_id or company or domain)
        base, n = rid, 2
        while rid in taken_ids:
            rid = f"{base}-{n}"
            n += 1
        taken_ids.add(rid)
        rec = store.new_record(rid, row_lane, row_client, company, domain,
                               context, signal)
        rec["batch"] = batch
        if contacts:
            rec["contacts"] = identity.assign_keys(contacts)
        if company_facts:
            rec["company_facts"].update(company_facts)
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

    # For CSV sources, resolve foreign headers onto canonical fields.
    # JSONL and dir sources already use canonical names.
    is_csv = source.lower().endswith(".csv")
    resolution = None
    op_cols = {}
    if is_csv and rows:
        headers = list(rows[0].keys())
        resolution = columns.resolve(headers)
        # Operational columns: unmapped headers that match known patterns.
        # These are company-level facts, not contact fields.
        for header in resolution.get("unmapped", []):
            norm = columns.normalise(header)
            if "headcountgrowth" in norm or "growth12" in norm:
                op_cols[header] = "headcount_growth_12m"
            elif "product" in norm and "service" in norm:
                op_cols[header] = "products_and_services"
            elif "employee" in norm and "count" in norm:
                op_cols[header] = "employee_count"
            elif norm in ("companysize",):
                op_cols[header] = "company_size"
            elif norm in ("companyindustrytags", "industry"):
                op_cols[header] = "industry_tags"

    for row in rows:
        if resolution is not None:
            canonical, source_extra = columns.apply(row, resolution)
            row_client = (canonical.get("client")
                          or row.get("client") or client)
            row_lane = canonical.get("lane") or row.get("lane") or lane
            domain = norm_domain(canonical.get("domain", ""))
            company = canonical.get("company") or domain
            context = source_extra.get("context", "")
            signal = source_extra.get("signal", "")
            raw_id = source_extra.get("id") or source_extra.get("Id")

            # Contact columns
            email_val = (canonical.get("email") or "").strip()
            li_val = (canonical.get("linkedin") or "").strip()
            fn_val = (canonical.get("first_name") or "").strip()
            ln_val = (canonical.get("last_name") or "").strip()
            name_val = (canonical.get("name") or "").strip()
            title_val = (canonical.get("title") or "").strip()

            # Validate LinkedIn URL from mapped column: must be a profile.
            if li_val and not linkedin.canonical(li_val):
                li_val = ""

            # Value-based promotion: a column called "Url" that was not
            # mapped by `columns` (too vague) may still hold a LinkedIn
            # profile. Check the value, not the header.
            if not li_val:
                for url_key in ("Url", "URL", "url"):
                    candidate = (source_extra.get(url_key) or "").strip()
                    if candidate and linkedin.canonical(candidate):
                        li_val = linkedin.canonical(candidate)
                        source_extra.pop(url_key, None)
                        break

            # Build contact dict
            contact = {}
            if email_val:
                contact["email"] = email_val
            if li_val:
                contact["linkedin"] = li_val
            if name_val:
                contact["name"] = name_val
            elif fn_val or ln_val:
                contact["name"] = f"{fn_val} {ln_val}".strip()
            if title_val:
                contact["title"] = title_val
            # Source provenance: unmapped columns, never read for eligibility.
            src = {k: v.strip()[:200]
                   for k, v in source_extra.items()
                   if v and v.strip()
                   and k not in ("context", "signal", "id", "Id")}
            if src:
                contact["source"] = src

            # Only create a contact if it has actual person data.
            # Source provenance alone is not a person.
            if not (email_val or li_val or name_val or fn_val or ln_val
                    or title_val):
                contact = {}

            # Operational columns -> company_facts
            facts = {}
            for orig_header, fact_key in op_cols.items():
                val = row.get(orig_header, "").strip()
                if val:
                    if fact_key == "headcount_growth_12m":
                        cleaned = re.sub(r"[^\d.+-]", "", val)
                        try:
                            facts[fact_key] = float(cleaned)
                        except (ValueError, TypeError):
                            facts[fact_key] = val
                    elif fact_key == "employee_count":
                        cleaned = re.sub(r"[^\d]", "", val)
                        try:
                            facts[fact_key] = int(cleaned)
                        except (ValueError, TypeError):
                            facts[fact_key] = val
                    else:
                        facts[fact_key] = val[:500]
        else:
            # JSONL or dir source: canonical keys already present
            row_client = row.get("client") or client
            row_lane = row.get("lane") or lane
            domain = norm_domain(row.get("domain"))
            company = row.get("company") or domain
            context = row.get("context", "")
            signal = row.get("signal", "")
            raw_id = row.get("id")
            contact = {}
            facts = {}

        contacts = [contact] if contact else None
        cf = facts if facts else None

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
                f"unknown lane: {row_lane}", contacts, cf)
            continue
        if not domain:
            add(row_client, row_lane, company, domain, context, signal, raw_id,
                "no domain", contacts, cf)
            continue
        if not is_hostname(domain):
            add(row_client, row_lane, company, domain, context, signal, raw_id,
                "not a usable domain: this is not the shape of a hostname",
                contacts, cf)
            continue
        if domain in suppress:
            add(row_client, row_lane, company, domain, context, signal, raw_id,
                "suppressed (live account)", contacts, cf)
            continue
        if key in run_keys:
            add(row_client, row_lane, company, domain, context, signal, raw_id,
                "duplicate domain", contacts, cf)
            continue

        run_keys.add(key)
        add(row_client, row_lane, company, domain, context, signal, raw_id,
            None, contacts, cf)

    if records:
        store.append(records, note=f"ingested from {origin}")

    result = {
        "queued": [r["id"] for r in records if r["state"] == "queued"],
        "dropped": [(r["id"], r["drop_reason"])
                    for r in records if r["state"] == "dropped"],
        "skipped": skipped,
    }
    if resolution is not None:
        result["column_mapping"] = columns.describe(resolution)
        result["contacts_found"] = sum(
            len(r.get("contacts") or []) for r in records)
        result["linkedin_found"] = sum(
            1 for r in records
            for c in (r.get("contacts") or [])
            if c.get("linkedin"))
    return result


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
