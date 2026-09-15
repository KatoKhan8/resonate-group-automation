#!/usr/bin/env python3
"""Turn the purchased contact list into a batch `src.ingest` can read.

## Why an adapter and not a column rename

`src.ingest` expects `company, domain`. The purchased list is a PEOPLE file -
52 columns of `First_Name`, `Title`, `Organization`, `Email_Business` - with no
domain column at all. 51,741 rows, every one carrying a business email, across
**20,944 unique domains at 2.5 contacts per domain**.

So the mapping is not cosmetic: a record in this system is a COMPANY, and the
source is one row per PERSON. Collapsing 51,741 people into 20,944 accounts is
the actual work, and doing it wrong would either create 51,741 records - one
per person, which is exactly the shape the cohort policy forbids - or silently
drop the extra contacts.

This writes the ACCOUNT batch. Contacts are discovered per account later by the
existing enrichment path, which is the only path that verifies an address
before anybody is contacted.

## What it refuses to do

**It does not verify anything.** Every email in the source is unverified - it
is a purchased list, and `Email_Business` being populated says somebody sold us
a string, not that a person reads it. Nothing here marks a contact sendable.

**It does not re-queue what is already queued.** `src.ingest` reports and skips
duplicates, but doing it here too keeps the batch file honest about its own
size.

**It writes to `batches/productive-*.csv`, which is gitignored.** The file is
20,944 real companies somebody paid for. The pattern is ignored deliberately -
see `.gitignore`, which records that a `git add` meant for a report nearly
caught these on 2026-09-10.
"""

import argparse
import csv
import json
import os
import sys

csv.field_size_limit(10 ** 7)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "work",
                      "Software_Agencies_All_Geo_cleaned - Sheet1.csv")
QUEUE = os.path.join(ROOT, "work", "queue.jsonl")

# Free and consumer mailboxes are not a company domain. A row whose business
# email is on one of these tells us nothing about an account, and ingesting it
# would create a "company" called gmail.com with several hundred contacts.
NOT_A_COMPANY = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "hotmail.com",
    "hotmail.co.uk", "outlook.com", "live.com", "aol.com", "icloud.com",
    "me.com", "mac.com", "msn.com", "protonmail.com", "proton.me",
    "gmx.de", "gmx.net", "web.de", "yandex.ru", "mail.ru", "qq.com",
}


def queued_domains():
    if not os.path.exists(QUEUE):
        return set()
    out = set()
    with open(QUEUE, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.add((json.loads(line).get("domain") or "").lower())
            except Exception:
                continue
    return out


def domain_of(email):
    e = (email or "").strip().lower()
    if "@" not in e:
        return ""
    d = e.rsplit("@", 1)[-1].strip().strip(".")
    return d if "." in d else ""


def build(limit, offset, country, out_path):
    already = queued_domains()
    seen, rows, skipped = {}, [], {"no_domain": 0, "free_mailbox": 0,
                                   "already_queued": 0, "country": 0}
    with open(SOURCE, encoding="utf-8", errors="replace", newline="") as fh:
        for r in csv.DictReader(fh):
            if country and (r.get("Country") or "").strip().lower() != country.lower():
                skipped["country"] += 1
                continue
            d = domain_of(r.get("Email_Business"))
            if not d:
                skipped["no_domain"] += 1
                continue
            if d in NOT_A_COMPANY:
                skipped["free_mailbox"] += 1
                continue
            if d in already:
                skipped["already_queued"] += 1
                continue
            if d in seen:
                seen[d]["contacts"] += 1      # count only; contacts are found later
                continue
            seen[d] = {"company": (r.get("Organization") or "").strip() or d,
                       "domain": d,
                       "contacts": 1,
                       "country": (r.get("Country") or "").strip()}
    ordered = list(seen.values())
    window = ordered[offset:offset + limit] if limit else ordered[offset:]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["company", "domain"])
        for row in window:
            w.writerow([row["company"], row["domain"]])
    return ordered, window, skipped


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m scripts.build_intake_batch")
    p.add_argument("--limit", type=int, default=0,
                   help="accounts to write; 0 writes all remaining")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--country", default=None,
                   help="restrict to one Country value, e.g. 'United States'")
    p.add_argument("--out", default=None)
    a = p.parse_args(argv)

    out = a.out or os.path.join(
        ROOT, "batches", "productive-intake-%05d-%05d.csv"
        % (a.offset, a.offset + (a.limit or 0)))
    ordered, window, skipped = build(a.limit, a.offset, a.country, out)

    print("source rows read      : %s" % SOURCE.rsplit(os.sep, 1)[-1])
    print("unique NEW accounts   : %d" % len(ordered))
    print("written to batch      : %d" % len(window))
    print("skipped:")
    for k, v in sorted(skipped.items()):
        print("   %-16s %d" % (k, v))
    multi = sum(1 for r in ordered if r["contacts"] > 1)
    print("accounts with >1 contact in source: %d" % multi)
    print("batch file            : %s" % os.path.relpath(out, ROOT))
    print()
    print("NOTHING IS VERIFIED. Every source email is unverified and no contact")
    print("is marked sendable here. Ingest creates ACCOUNTS; contacts are")
    print("discovered and verified later, by the path that charges for it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
