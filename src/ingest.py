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

    def add(row_client, row_lane, company, domain, context, signal, raw_id, reason):
        rid = slug(raw_id or company or domain)
        base, n = rid, 2
        while rid in taken_ids:
            rid = f"{base}-{n}"
            n += 1
        taken_ids.add(rid)
        rec = store.new_record(rid, row_lane, row_client, company, domain, context, signal)
        rec["batch"] = batch
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
                f"unknown lane: {row_lane}")
            continue
        if not domain:
            add(row_client, row_lane, company, domain, context, signal, raw_id, "no domain")
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
                "not a usable domain: this is not the shape of a hostname")
            continue
        if domain in suppress:
            add(row_client, row_lane, company, domain, context, signal, raw_id,
                "suppressed (live account)")
            continue
        if key in run_keys:
            add(row_client, row_lane, company, domain, context, signal, raw_id,
                "duplicate domain")
            continue

        run_keys.add(key)
        add(row_client, row_lane, company, domain, context, signal, raw_id, None)

    if records:
        store.append(records, note=f"ingested from {origin}")

    return {
        "queued": [r["id"] for r in records if r["state"] == "queued"],
        "dropped": [(r["id"], r["drop_reason"]) for r in records if r["state"] == "dropped"],
        "skipped": skipped,
    }


def _extract_domain_from_email(email):
    """The domain part of a work email, normalised. Empty if unusable."""
    if not email or "@" not in email:
        return ""
    return norm_domain(email.split("@", 1)[1])


def _contact_from_person_row(row):
    """One person row to a contact dict. No paid call, no verification."""
    first = row.get("first name", "").strip()
    last = row.get("last name", "").strip()
    name = f"{first} {last}".strip()
    email = row.get("work email", "").strip().lower()
    return {
        "name": name or None,
        "title": row.get("job title", "").strip() or None,
        "headline": row.get("headline", "").strip() or None,
        "linkedin": row.get("url", "").strip() or None,
        "email": email or None,
        "email_status": row.get("work email status", "").strip() or None,
        "email_source": "client_file",
    }


def run_person_centric(source, client, lane, suppress_path=None):
    """Import a person-centric CSV: group by email domain, one record per company.

    The source CSV has one row per person with columns: Url, First Name,
    Last Name, Job Title, Headline, Company, Industry, Location, Work Email,
    Work Email Status. Rows are grouped by the domain extracted from the
    work email. Each person becomes a contact on that company's record.

    Returns a summary dict with counts and skip reasons.
    """
    from . import identity

    rows = read_rows(source)
    suppress = load_suppress(suppress_path)
    existing = store.load()
    existing_by_domain = {}
    for r in existing:
        d = r.get("domain")
        if d:
            existing_by_domain.setdefault(d, r)

    existing_emails = set()
    for r in existing:
        for c in (r.get("contacts") or []):
            e = (c.get("email") or "").strip().lower()
            if e:
                existing_emails.add(e)

    origin = os.path.basename(os.path.normpath(source))
    batch = {"id": f"{origin}-{store.now()[:19]}", "source": origin,
             "at": store.now(), "client": client, "lane": lane}

    groups = {}
    skipped_rows = []
    for row in rows:
        email = row.get("work email", "").strip().lower()
        domain = _extract_domain_from_email(email)
        name = ((row.get("first name", "") + " " + row.get("last name", "")).strip()
                or "unnamed")
        if not domain:
            skipped_rows.append((name, "no usable domain in work email"))
            continue
        if not is_hostname(domain):
            skipped_rows.append((name,
                                "not a usable domain: this is not the shape of a hostname"))
            continue
        if domain in suppress:
            skipped_rows.append((email or "unknown", "suppressed (live account)"))
            continue
        if email and email in existing_emails:
            skipped_rows.append((email, "contact already in queue"))
            continue
        groups.setdefault(domain, []).append(row)

    new_records = []
    updated_records = []
    contact_counts = []

    for domain, person_rows in groups.items():
        company_name = ""
        industry = ""
        location = ""
        contacts_to_add = []
        for row in person_rows:
            contact = _contact_from_person_row(row)
            if not contact["email"]:
                skipped_rows.append((contact.get("name") or "unnamed",
                                    "no work email"))
                continue
            contacts_to_add.append(contact)
            if not company_name:
                company_name = row.get("company", "").strip() or domain
            if not industry:
                industry = row.get("industry", "").strip()
            if not location:
                location = row.get("location", "").strip()

        if not contacts_to_add:
            continue

        if domain in existing_by_domain:
            rec = existing_by_domain[domain]
            existing_contact_emails = {
                (c.get("email") or "").strip().lower()
                for c in (rec.get("contacts") or [])
            }
            added = 0
            for contact in contacts_to_add:
                if contact["email"] in existing_contact_emails:
                    skipped_rows.append((contact["email"],
                                        "contact already on this record"))
                    continue
                rec["contacts"].append(contact)
                existing_contact_emails.add(contact["email"])
                added += 1
            if added:
                identity.assign_keys(rec["contacts"])
                if industry and not rec.get("company_facts", {}).get("industry"):
                    rec.setdefault("company_facts", {})["industry"] = industry
                if location and not rec.get("company_facts", {}).get("location"):
                    rec.setdefault("company_facts", {})["location"] = location
                store.log(rec, rec.get("state", "queued"),
                          f"added {added} contact(s) from {origin}")
                events.record(rec, events.BATCH_INGESTED, batch=batch["id"])
                updated_records.append(rec)
            contact_counts.append(len(rec["contacts"]))
        else:
            rid = slug(company_name or domain)
            rec = store.new_record(rid, lane, client, company_name or domain,
                                   domain)
            rec["batch"] = batch
            if industry:
                rec.setdefault("company_facts", {})["industry"] = industry
            if location:
                rec.setdefault("company_facts", {})["location"] = location
            for contact in contacts_to_add:
                rec["contacts"].append(contact)
            identity.assign_keys(rec["contacts"])
            store.log(rec, rec["state"], f"ingested from {origin}")
            events.record(rec, events.BATCH_INGESTED, batch=batch["id"])
            new_records.append(rec)
            contact_counts.append(len(rec["contacts"]))

    if new_records:
        store.append(new_records, note=f"ingested from {origin}")

    if updated_records:
        all_recs = store.load()
        updated_ids = {r["id"] for r in updated_records}
        merged = []
        for r in all_recs:
            if r["id"] in updated_ids:
                for u in updated_records:
                    if u["id"] == r["id"]:
                        merged.append(u)
                        break
            else:
                merged.append(r)
        store.save(merged)

    total_contacts = sum(contact_counts) if contact_counts else 0
    total_skipped = len(skipped_rows)
    total_rows = len(rows)

    distribution = {}
    for c in contact_counts:
        bucket = "1" if c == 1 else "2" if c == 2 else "3" if c == 3 else "4+"
        distribution[bucket] = distribution.get(bucket, 0) + 1

    return {
        "rows_in": total_rows,
        "records_created": len(new_records),
        "records_updated": len(updated_records),
        "contacts_attached": total_contacts,
        "max_contacts_on_one_record": max(contact_counts) if contact_counts else 0,
        "distribution": distribution,
        "skipped": skipped_rows,
        "skipped_count": total_skipped,
        "arithmetic_ok": total_rows == total_contacts + total_skipped,
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.ingest")
    p.add_argument("source")
    p.add_argument("--client", required=True)
    p.add_argument("--lane", required=True, choices=list(store.LANES))
    p.add_argument("--person-centric", action="store_true",
                   help="Import a person-centric CSV (one row per person, "
                        "grouped by email domain into company records)")
    a = p.parse_args(argv)

    if a.person_centric:
        result = run_person_centric(a.source, a.client, a.lane)
        print(f"rows in: {result['rows_in']}")
        print(f"records created: {result['records_created']}")
        print(f"records updated: {result['records_updated']}")
        print(f"contacts attached: {result['contacts_attached']}")
        print(f"max contacts on one record: {result['max_contacts_on_one_record']}")
        print(f"distribution: {result['distribution']}")
        print(f"skipped: {result['skipped_count']}")
        print(f"arithmetic balanced: {result['arithmetic_ok']}")
        for who, reason in result["skipped"]:
            print(f"  skipped {who}: {reason}")
        return 0

    result = run(a.source, a.client, a.lane)
    print(f"queued {len(result['queued'])} record(s) -> {store.queue_path()}")
    for rid, reason in result["dropped"]:
        print(f"  dropped {rid}: {reason}")
    for company, reason in result["skipped"]:
        print(f"  skipped {company}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
