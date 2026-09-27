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

from . import (clients as client_config, columns, events, identity, linkedin,
               store)

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
    """Yield rows preserving original headers for column mapping.

    The keys are stripped of surrounding whitespace but NOT lowercased:
    `columns.resolve` needs the original header text to map "Work Email"
    onto the canonical `email` field and "LinkedIn URL" onto `linkedin`.
    Lowercasing here destroyed that mapping and silently dropped every
    contact column the file carried.
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


# Operational columns from the Software Agencies universe that the pack needs
# but `columns.py` deliberately has no opinion about. They are company-level
# facts, not contact identity, so they travel as provenance on company_facts.
#
# The keys are the normalised forms `columns.normalise` produces: all
# non-alphanumeric stripped, lowercased. The `source` dict from
# `columns.apply` uses the original header text as keys, so we match by
# normalising at lookup time.
OPERATIONAL_COLUMN_KEYS = {
    "companytotalheadcountgrowth12months": "headcount_growth_12m",
    "companyproductandservices": "products_and_services",
    "companyemployeecount": "employee_count",
    "companysize": "company_size",
    "companyindustrytags": "industry_tags",
}


def _canonical_row(row, resolution):
    """Apply column mapping if available; pass through if not.

    Returns `(canonical, source_extra)`. For CSV sources with a resolution,
    this is `columns.apply`. For JSONL/dir sources (no resolution), the row
    is already canonical and there is no source extra.

    Internal columns (`lane`, `client`, `id`, `context`, `signal`) are read
    from the raw row regardless of mapping: they are estate internals, not
    foreign headers, and `columns.py` deliberately has no alias for them.
    """
    if resolution is None:
        lowered = {k.strip().lower(): (v or "").strip()
                   for k, v in row.items() if k}
        return lowered, {}
    canonical, source_extra = columns.apply(row, resolution)
    # Internal columns the alias table does not know about. Read them from
    # the raw row by case-insensitive match so "Lane", "LANE" and "lane"
    # all work.
    raw_lower = {k.strip().lower(): (v or "").strip()
                 for k, v in row.items() if k}
    for internal in ("lane", "client", "id", "context", "signal"):
        if internal not in canonical and raw_lower.get(internal):
            canonical[internal] = raw_lower[internal]
    return canonical, source_extra


def _contact_from_row(canonical):
    """A contact dict from canonical fields, or None if the row carries nobody.

    A row with neither a strong identity (email, linkedin) nor a name is a
    company-level row, not a person. Returning None here is the signal to
    skip contact attachment for this row.
    """
    email = (canonical.get("email") or "").strip()
    raw_linkedin = (canonical.get("linkedin") or "").strip()
    first = (canonical.get("first_name") or "").strip()
    last = (canonical.get("last_name") or "").strip()
    name = (canonical.get("name") or "").strip()
    title = (canonical.get("title") or "").strip()

    linkedin_url = linkedin.canonical(raw_linkedin) if raw_linkedin else None

    if not name and first and last:
        name = f"{first} {last}".strip()

    if not any([email, linkedin_url, name]):
        return None

    return {
        "name": name or None,
        "title": title or None,
        "linkedin": linkedin_url,
        "email": email or None,
        "email_source": "ingest",
        "persona": None,
        "angle": None,
        "verdict": None,
        "reoon": None,
        "sendable": False,
        "primary": False,
    }


def _operational_facts(source_extra):
    """Company-level facts from unmapped columns, keyed by short name.

    The `source_extra` dict from `columns.apply` uses original header text
    as keys, so we normalise at lookup time to match the OPERATIONAL map.
    """
    facts = {}
    for header, value in source_extra.items():
        norm = columns.normalise(header)
        short_name = OPERATIONAL_COLUMN_KEYS.get(norm)
        if short_name and value and str(value).strip():
            facts[short_name] = str(value).strip()
    return facts


def _contact_identity_key(contact):
    """The strong identity for deduplication, matching upload.contact_identity."""
    email = (contact.get("email") or "").strip().lower()
    if email:
        return f"email:{email}"
    profile = linkedin.canonical(contact.get("linkedin") or "")
    if profile:
        return f"linkedin:{profile}"
    return None


def run(source, client, lane, suppress_path=None):
    """Build records from `source` and hand them to the store. Returns a summary."""
    raw_rows = read_rows(source)
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

    # Resolve column headers for CSV sources. JSONL and dir sources already
    # carry canonical keys, so no resolution is needed.
    resolution = None
    if source.endswith(".csv") and raw_rows:
        resolution = columns.resolve(list(raw_rows[0].keys()))

    # domain -> the record being built, so later rows at the same domain
    # attach their contacts rather than being discarded as duplicates.
    # Five rows at acme.test are five contacts on one account, not one
    # account and four thrown away.
    domain_records = {}

    def add(row_client, row_lane, company, domain, context, signal, raw_id,
            reason, contacts=None, company_facts_extra=None):
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
        if company_facts_extra:
            rec["company_facts"].update(company_facts_extra)
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

    for raw_row in raw_rows:
        canonical, source_extra = _canonical_row(raw_row, resolution)
        row_client = canonical.get("client") or client
        row_lane = canonical.get("lane") or lane
        domain = norm_domain(canonical.get("domain", ""))
        company = canonical.get("company") or domain
        context = canonical.get("context", "")
        signal = canonical.get("signal", "")
        raw_id = canonical.get("id")

        if row_client not in checked_clients:
            if not client_config_exists(row_client):
                sys.exit(
                    f"no config/clients/{row_client}.yaml, "
                    "refusing to ingest")
            checked_clients.add(row_client)

        key = key_of(row_client, domain, company)
        if key in existing_keys:
            skipped.append((company, "already in queue"))
            continue

        contact = _contact_from_row(canonical)
        ops_facts = _operational_facts(source_extra)

        # A domain we have already seen in THIS batch: attach the contact
        # to the existing record rather than creating a duplicate.
        # A row with NO contact and NO operational facts at an already-seen
        # domain is a duplicate company row, not another person.
        if domain in domain_records:
            entry = domain_records[domain]
            if contact is not None:
                person_id = _contact_identity_key(contact)
                if person_id is None or person_id not in entry["identities"]:
                    if person_id is not None:
                        entry["identities"].add(person_id)
                    entry["contacts"].append(contact)
                    # Assign a key to the newly added contact. The record
                    # already holds this list, so the key is visible on it.
                    identity.assign_keys(entry["contacts"])
                # else: duplicate contact in this file, silently skip
            elif not ops_facts:
                # Nothing distinguishes this row from the one already taken.
                add(row_client, row_lane, company, domain, context, signal,
                    raw_id, "duplicate domain")
                continue
            if ops_facts:
                entry["company_facts_extra"].update(ops_facts)
                # Update the record itself, not just the accumulator.
                entry["record"]["company_facts"].update(ops_facts)
            continue

        if row_lane not in store.LANES:
            add(row_client, lane, company, domain, context, signal, raw_id,
                f"unknown lane: {row_lane}",
                contacts=[contact] if contact else None,
                company_facts_extra=ops_facts or None)
            continue
        if not domain:
            add(row_client, row_lane, company, domain, context, signal,
                raw_id, "no domain",
                contacts=[contact] if contact else None,
                company_facts_extra=ops_facts or None)
            continue
        if not is_hostname(domain):
            add(row_client, row_lane, company, domain, context, signal,
                raw_id,
                "not a usable domain: this is not the shape of a hostname",
                contacts=[contact] if contact else None,
                company_facts_extra=ops_facts or None)
            continue
        if domain in suppress:
            add(row_client, row_lane, company, domain, context, signal,
                raw_id, "suppressed (live account)",
                contacts=[contact] if contact else None,
                company_facts_extra=ops_facts or None)
            continue
        if key in run_keys:
            add(row_client, row_lane, company, domain, context, signal,
                raw_id, "duplicate domain",
                contacts=[contact] if contact else None,
                company_facts_extra=ops_facts or None)
            continue

        run_keys.add(key)
        contacts_list = [contact] if contact else []
        identities = set()
        person_id = _contact_identity_key(contact) if contact else None
        if person_id is not None:
            identities.add(person_id)
        rec = add(row_client, row_lane, company, domain, context, signal,
                  raw_id, None, contacts=contacts_list or None,
                  company_facts_extra=ops_facts or None)
        domain_records[domain] = {
            "record": rec,
            "contacts": contacts_list,
            "identities": identities,
            "company_facts_extra": dict(ops_facts),
        }

    if records:
        store.append(records, note=f"ingested from {origin}")

    contacts_total = sum(len(r.get("contacts") or []) for r in records)
    linkedin_total = sum(
        1 for r in records
        for c in (r.get("contacts") or [])
        if linkedin.canonical(c.get("linkedin") or "")
    )

    return {
        "queued": [r["id"] for r in records if r["state"] == "queued"],
        "dropped": [(r["id"], r["drop_reason"]) for r in records
                    if r["state"] == "dropped"],
        "skipped": skipped,
        "contacts": contacts_total,
        "contacts_with_linkedin": linkedin_total,
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.ingest")
    p.add_argument("source")
    p.add_argument("--client", required=True)
    p.add_argument("--lane", required=True, choices=list(store.LANES))
    a = p.parse_args(argv)

    result = run(a.source, a.client, a.lane)
    print(f"queued {len(result['queued'])} record(s) -> {store.queue_path()}")
    print(f"  contacts: {result.get('contacts', 0)}"
          f" ({result.get('contacts_with_linkedin', 0)} with LinkedIn)")
    for rid, reason in result["dropped"]:
        print(f"  dropped {rid}: {reason}")
    for company, reason in result["skipped"]:
        print(f"  skipped {company}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
