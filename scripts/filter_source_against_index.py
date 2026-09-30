#!/usr/bin/env python3
"""Filter the whole approved source against the collision index.

Operator, 2026-09-30. Two questions, and the second is the one that decides
whether a canary exists:

  1. how much of the approved source has already been contacted
  2. the same counts restricted to rows that pass the DETERMINISTIC ICP
     classifier (`qualify.company` - "Spends nothing")

CANARY ELIGIBILITY, the operator's rule until one is agreed with the client:

    the person has never been contacted by anyone
    AND their company domain has no active sequence in any campaign
    AND no contact at that domain in the last 90 days

Read-only. Reads `work/collision-index.json`, which is gitignored.
"""
import argparse
import collections
import csv
import datetime
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, qualify, store

SOURCE = os.path.join("work", "Productive",
                      "productive_ICP_safe_to_send (1).csv")
RECENT_DAYS = 90


def _domain_of(email):
    return (email or "").split("@")[-1].strip().lower()


def _parse(ts):
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(
            str(ts).replace("Z", "+00:00"))
    except Exception:                                         # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    path = os.path.abspath(os.path.join(os.path.dirname(store.queue_path()),
                                        "collision-index.json"))
    with io.open(path, encoding="utf-8") as f:
        index = json.load(f)
    by_email = index.get("by_email") or {}
    by_domain = index.get("by_domain") or {}
    incomplete = index.get("incomplete") or []
    hr = index.get("heyreach") or {}
    now = datetime.datetime.now(datetime.timezone.utc)

    cfg = clients.load("productive")
    recs = {(r.get("domain") or "").strip().lower(): r for r in store.load()
            if r.get("domain")}

    tally = collections.Counter()
    eligible = []
    seen_domains = set()
    qualified_cache = {}

    with io.open(SOURCE, encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), 1):
            if args.limit and i > args.limit:
                break
            email = (row.get("Work Email") or "").strip().lower()
            domain = _domain_of(email)
            if not email or not domain:
                tally["no email"] += 1
                continue
            tally["rows"] += 1
            seen_domains.add(domain)

            person_touched = email in by_email
            dom = by_domain.get(domain)
            dom_touched = dom is not None
            dom_active = bool(dom and dom.get("active"))
            last = _parse(dom and dom.get("last_touch"))
            dom_recent = bool(last and (now - last).days <= RECENT_DAYS)

            tally["person contacted"] += person_touched
            tally["person never contacted"] += (not person_touched)
            tally["domain any contact"] += dom_touched
            tally["domain ACTIVE sequence"] += dom_active
            tally["domain touched <90d"] += dom_recent

            # The deterministic ICP verdict. Zero cost, no model.
            rec = recs.get(domain)
            if domain not in qualified_cache:
                verdict = None
                if rec is not None:
                    try:
                        out = qualify.company(rec, cfg, store_result=False)
                        verdict = str((out.get("verdict") or {}).get(
                            "icp_status") or "").lower()
                    except Exception:                         # noqa: BLE001
                        verdict = "raised"
                qualified_cache[domain] = verdict
            verdict = qualified_cache[domain]
            is_q = verdict == "qualified"
            tally["icp qualified"] += is_q
            if rec is None:
                tally["no canonical record"] += 1

            if not is_q:
                continue
            tally["qualified rows"] += 1
            tally["qualified + person contacted"] += person_touched
            tally["qualified + domain any contact"] += dom_touched
            tally["qualified + domain ACTIVE"] += dom_active

            if (not person_touched) and (not dom_active) and (not dom_recent):
                tally["ELIGIBLE under the rule"] += 1
                if len(eligible) < 25:
                    eligible.append({
                        "row": i, "email": email, "domain": domain,
                        "company": row.get("Company"),
                        "title": row.get("Job Title"),
                        "domain_touched_ever": dom_touched})

    print("SOURCE: %s" % SOURCE)
    print("index generated_at: %s" % index.get("generated_at"))
    print("index campaigns walked: %d, INCOMPLETE: %d"
          % (len(index.get("campaigns") or {}), len(incomplete)))
    print("HeyReach in index: %s (%s)"
          % (hr.get("read"), str(hr.get("why"))[:70]))
    print("people in index: %d | domains in index: %d"
          % (len(by_email), len(by_domain)))
    print()
    for k in ("rows", "person never contacted", "person contacted",
              "domain any contact", "domain ACTIVE sequence",
              "domain touched <90d", "no canonical record",
              "icp qualified", "qualified rows",
              "qualified + person contacted", "qualified + domain any contact",
              "qualified + domain ACTIVE", "ELIGIBLE under the rule"):
        print("  %-34s %d" % (k, tally[k]))
    print()
    print("FIRST ELIGIBLE CANDIDATES (deterministic source order):")
    for e in eligible[:15]:
        print("  row %-7d %-34s %-28s %s"
              % (e["row"], e["email"][:32], (e["company"] or "")[:26],
                 "domain touched before" if e["domain_touched_ever"] else ""))
    if not eligible:
        print("  NONE. The eligible pool is EMPTY under the operator's rule.")
    if incomplete:
        print()
        print("UNKNOWN, NOT CLEAR: %d campaign walk(s) incomplete, so any "
              "'never contacted' above is a floor, not a fact." % len(incomplete))


if __name__ == "__main__":
    main()
