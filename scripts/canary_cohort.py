#!/usr/bin/env python3
"""The canary cohort: derive it, pin it, fingerprint it, classify it.

READ-ONLY. Every provider call reached from here is a GET and nothing is written
to `work/`. Prints counts, buckets and a digest. NEVER an address, a name, a
company or a contact key.

WHY THIS EXISTS. The 43-contact canary shortlist of 2026-10-01 lived in ONE TEXT
FILE OUTSIDE THE REPOSITORY and no committed script reproduced it, so the number
could not be re-measured after a rule changed - which is exactly what the
operator's rule of 2026-10-01 then required.

AND IT IS NOT DERIVABLE. Measured 2026-10-01, before writing this: no
conjunction of up to four of fifteen plausible record and contact predicates
reproduces those 43 members. `sendable` covers all 43 but selects 873.
`sendable AND mx AND not_dropped` selects 872. The record marker `canary` exists
on exactly ONE record and is an email-sequence hash, not a cohort tag. The
shortlist's own campaign labels span `local/approved`, `local/held`, `FRESH` and
seven provider campaigns, and its members straddle four record states
(`verified` 37, `drafted` 3, `held` 2, `approved` 1). It was hand-picked, or
picked by a process whose inputs are no longer in the store.

THE NEAR MISS IS THE WHOLE LESSON. `bison_lead_id AND has_research` selects
EXACTLY 43 rows - and 52 of them are the wrong people. A count is not a cohort,
which is why `--derive` prints a digest of the member SET and never a size on
its own, and why `--pin` exists at all.

    py -3 scripts/canary_cohort.py --derive
    py -3 scripts/canary_cohort.py --pin <path-outside-the-repo>
    py -3 scripts/canary_cohort.py --pin <path> --classify

WHAT HAS TO BE RECORDED FOR A COHORT TO BE REPRODUCIBLE, and none of it was:

  1. COHORT MEMBERSHIP IS CANONICAL STATE, not a text file. Write the cohort id
     onto the record at selection time - `rec["cohorts"]` through `src/store.py`
     - so membership is in the one place that holds record state and travels
     with it. A list in `~/Desktop` fails the durable-state test in CLAUDE.md:
     a fresh session on another machine with a clone and the secrets cannot read
     it.
  2. THE CRITERIA, AS CODE, committed with the cohort - a function, not prose,
     because prose cannot be re-run.
  3. THE INPUTS' OWN VERSIONS: master SHA, the store fingerprint, and the
     `generated_at` of every provider read the selection consulted. A cohort is
     a function of state that moves.
  4. A SET DIGEST, so two runs can be proven to have selected the same PEOPLE
     rather than the same NUMBER of people.

Until (1) exists, `--pin` is the honest route: it takes the identities from
wherever they are recorded, resolves them against the store, and reports what is
missing. It never copies them into the repository - the shortlist flags its own
contact keys as PII, because they are derived from people's names.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import store                                          # noqa: E402

#: Lines in a pinned shortlist: an ordinal, a record id, and `key=<contact>`.
PINNED_ROW = re.compile(r"^\s*(\d+)\s+(\S+)\s+key=(\S+)")

#: A pinned shortlist in its other shape: ordinal, record id, contact key, then
#: an address in angle brackets. Matched so a file in either layout resolves.
PINNED_ROW_ADDR = re.compile(r"^\s*(\d+)\s+(\S+)\s+(\S+)\s+<[^>]+>")


def records():
    """Every record in the store, by id. Read through `store`, never the file."""
    return {r.get("id"): r for r in store.load()}


def digest(pairs):
    """A one-way digest of the member SET, safe to print and to commit.

    Over the SET rather than per member, so nothing here is a lookup table for
    an identity: one value, and two runs that selected the same people produce
    it while two runs that merely selected the same NUMBER do not. Domain
    separated so a digest cannot be confused with one taken over anything else.
    """
    joined = "\n".join(f"{rid}::{key}" for rid, key in sorted(pairs))
    return hashlib.sha256(
        b"resonate-cohort-v1\x00" + joined.encode("utf-8")).hexdigest()[:16]


def derive(recs):
    """A cohort by STATED CRITERIA, re-runnable, and NOT the 2026-10-01 43.

    Every clause is here because it is a precondition for an email going out at
    all, so this answers "who could a canary be drawn from today" rather than
    "who was drawn on 2026-10-01". It is deliberately not tuned to reproduce
    that list: a filter reverse-engineered until its output matched 43 known
    people would be a lookup table wearing a predicate's clothes.
    """
    chosen, why = set(), collections.Counter()
    for rid, rec in recs.items():
        if rec.get("drop_reason"):
            why["record dropped"] += 1
            continue
        excluded = {(e.get("email") or "").strip().lower()
                    for e in (rec.get("excluded") or []) if isinstance(e, dict)}
        for contact in rec.get("contacts") or []:
            address = (contact.get("email") or "").strip().lower()
            if not address:
                why["no address"] += 1
            elif address in excluded:
                why["set aside on the record"] += 1
            elif contact.get("excluded"):
                why["contact flagged excluded"] += 1
            elif not contact.get("sendable"):
                why["not sendable"] += 1
            elif not contact.get("mx"):
                why["no MX verdict"] += 1
            else:
                chosen.add((rid, contact.get("key")))
    return chosen, why


def pinned(path):
    """Member identities from a file OUTSIDE the repository. Never copied in."""
    found = {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = PINNED_ROW.match(line)
            if match:
                found[int(match.group(1))] = (match.group(2), match.group(3))
                continue
            match = PINNED_ROW_ADDR.match(line)
            if match and int(match.group(1)) not in found:
                found[int(match.group(1))] = (match.group(2), match.group(3))
    return found


def classify(recs, pairs):
    """The five buckets of LEAD KLASIFIKACIJA over a cohort. Live, read-only."""
    from src import clients, collision

    config = clients.load("productive")
    workspace = clients.provider_workspace(config, "emailbison")
    os_campaigns, readable = collision.os_campaign_ids()
    if not readable:
        print("  the campaign ledger could not be read, so every lead is "
              "UNKNOWN by construction. Refusing to print buckets that would "
              "all say the same thing for the wrong reason.")
        return
    print(f"  workspace {workspace!r}  Resonate OS campaigns {len(os_campaigns)}"
          f"  settings {collision.settings(config)}")
    buckets = collections.Counter()
    for rid, key in sorted(pairs):
        rec = recs.get(rid) or {}
        contact = next((c for c in (rec.get("contacts") or [])
                        if c.get("key") == key), None)
        if contact is None:
            buckets["gone from the store"] += 1
            continue
        try:
            _d, klass, _why, _dossier = collision.recontact_check(
                contact.get("email"), profile_url=contact.get("linkedin"),
                name=contact.get("name"), expect_workspace=workspace,
                client="productive",
                heyreach_campaign_id=contact.get("heyreach_campaign_id"),
                config=config)
        except Exception as exc:                               # noqa: BLE001
            klass = collision.CLASS_UNKNOWN
            buckets[f"read failed: {type(exc).__name__}"] += 1
        buckets[klass] += 1
    for name in (collision.CLASS_BLOCKED, collision.CLASS_ON_HOLD,
                 collision.CLASS_REVIVAL, collision.CLASS_COLD,
                 collision.CLASS_COLD_WAITING, collision.CLASS_UNKNOWN):
        print(f"    {name.upper():<16}{buckets.get(name, 0)}")
    print(f"    {'SENDABLE NOW':<16}{buckets.get(collision.CLASS_COLD, 0)}")
    for name, count in buckets.items():
        if name not in collision.CLASSES:
            print(f"    note: {name}: {count}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m scripts.canary_cohort",
        description="Derive, pin, fingerprint and classify a canary cohort. "
                    "Read-only. Prints no prospect identity.")
    parser.add_argument("--derive", action="store_true",
                        help="select by stated criteria from the store")
    parser.add_argument("--pin", metavar="PATH",
                        help="read member identities from a file outside the "
                             "repository; they are never copied into it")
    parser.add_argument("--classify", action="store_true",
                        help="run LEAD KLASIFIKACIJA over the cohort (live GETs)")
    args = parser.parse_args(argv)
    if not (args.derive or args.pin):
        parser.error("name --derive or --pin")

    recs = records()
    print(f"store: {len(recs)} records, "
          f"{sum(len(r.get('contacts') or []) for r in recs.values())} contacts")

    if args.derive:
        chosen, why = derive(recs)
        print(f"\nDERIVED BY STATED CRITERIA: {len(chosen)} contacts")
        print(f"  set digest {digest(chosen)}")
        for reason, count in why.most_common():
            print(f"  excluded, {reason}: {count}")
        print("  NOTE: this is not the 2026-10-01 cohort of 43 and does not "
              "try to be. See this file's header.")
        if args.classify:
            print("\n  LEAD KLASIFIKACIJA over the derived cohort:")
            classify(recs, chosen)

    if args.pin:
        found = pinned(args.pin)
        pairs = set(found.values())
        print(f"\nPINNED FROM {os.path.basename(args.pin)}: "
              f"{len(found)} rows, {len(pairs)} distinct contacts")
        print(f"  set digest {digest(pairs)}")
        missing = [(rid, key) for rid, key in pairs
                   if rid not in recs
                   or not any(c.get("key") == key
                              for c in (recs[rid].get("contacts") or []))]
        print(f"  resolved against the store: {len(pairs) - len(missing)} "
              f"present, {len(missing)} MISSING")
        if missing:
            print("  a cohort whose members have left the store cannot be "
                  "re-measured as the same cohort; the digest above is of what "
                  "the FILE says, not of what is still there")
        if args.classify:
            print("\n  LEAD KLASIFIKACIJA over the pinned cohort:")
            classify(recs, pairs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
