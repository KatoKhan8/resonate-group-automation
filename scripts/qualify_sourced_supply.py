#!/usr/bin/env python3
"""Sourced supply -> S3 -> MX -> collision -> the QUALIFIED-only export list.

    py scripts/qualify_sourced_supply.py --run
    py scripts/qualify_sourced_supply.py --sample 50

Reads `work/agency-sourcing.jsonl` and writes `work/qualified-supply.jsonl`.
Provider-facing reads only; it enrolls nobody and sends nothing.

FOUR RULES THIS FILE EXISTS TO HOLD:

**QUALIFIED ONLY.** Operator ruling after ISSUE-019: REVIEW means we could not
decide, and an undecided account written into a client export reads to the
client as one we chose. REVIEW is routed to enrichment and counted, never
exported.

**THE 20 FLOOR IS APPLIED TO `employees`, NEVER TO THE BAND.** `size` is
LinkedIn's self-reported bucket and `employees` is a different estimate - a
row in the `51_200` bucket came back reading 392. The sourcing run already
applied this; it is applied again here because this script must be correct
about the file it is handed rather than about the one that produced it.

**EVERY CUT IS COUNTED SEPARATELY.** Operator instruction: the collision cut
is shown apart from the ICP cut. A funnel that reports only its output cannot
tell "the ICP was strict" from "suppression ate it", and those call for
opposite responses.

**SUPPRESSION UNREADABLE MEANS REFUSE.** Not "continue without it".
"""
import argparse
import collections
import json
import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import (clients, icp, ingest, nightlysourcing,          # noqa: E402
                 singlewalker, store)
from src.providers import load_env                                   # noqa: E402

IN = os.path.join(ROOT, "work", "agency-sourcing.jsonl")
OUT = os.path.join(ROOT, "work", "qualified-supply.jsonl")
REVIEW_OUT = os.path.join(ROOT, "work", "review-to-enrichment.jsonl")
LOCK = os.path.join(ROOT, "work", "qualify-supply.lock")
MIN_EMPLOYEES = 20


def rows():
    with open(IN, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def as_record(row):
    return {"domain": row["domain"], "company": row.get("name") or "",
            "company_facts": {
                "name": row.get("name") or "",
                "employees": row.get("employees"),
                "industry": row.get("industry") or "",
                "description": row.get("overview") or "",
                "offices": [row["country"]] if row.get("country") else [],
                "country": row.get("country") or "",
                "services": [], "specialties": row.get("specialties") or []}}


def run():
    load_env()
    config = clients.load("productive")
    try:
        suppressed = {str(d).strip().lower() for d in ingest.load_suppress()}
    except Exception as exc:                       # noqa: BLE001
        print(f"REFUSING: suppression unreadable ({exc}). An export built "
              "without it can carry a domain the client told us to drop.")
        return 2
    held = {str(r.get("domain") or "").strip().lower()
            for r in store.load() if r.get("domain")}

    cut = collections.Counter()
    qualified, review = [], []
    seen = set()

    for row in rows():
        domain = row["domain"]
        if domain in seen:
            cut["duplicate_in_file"] += 1
            continue
        seen.add(domain)

        employees = row.get("employees")
        if not isinstance(employees, int) or employees < MIN_EMPLOYEES:
            cut["under_20_floor"] += 1
            continue
        if domain in suppressed:
            cut["client_suppression"] += 1
            continue
        if domain in held:
            cut["already_in_estate"] += 1
            continue

        verdict = icp.score(as_record(row), config=config)
        status = verdict.get("icp_status")
        if status == icp.REVIEW:
            cut["icp_review_to_enrichment"] += 1
            row["_icp_status"] = status
            row["_icp_score"] = verdict.get("icp_score")
            review.append(row)
            continue
        if status != icp.QUALIFIED:
            cut["icp_rejected"] += 1
            continue

        # MX through the pipeline's OWN stage, not a hand-rolled copy.
        # `mx.classify` takes resolved HOSTS, not a domain, and a second
        # implementation of this is how the two come to disagree about which
        # statuses survive. dns_failure is HELD: we could not ask, which is
        # not the same fact as no mail.
        staged = nightlysourcing._mx_classify([row], config=config)
        if not staged:
            cut[f"mx_{row.get('_drop_reason') or row.get('_mx_status')}"] += 1
            continue

        # COLLISION IS THE PIPELINE'S LOCAL STAGE, and deliberately not
        # `collision.check_account`. That one is a PROVIDER read - it refused
        # outright here because the credential is bound to workspace
        # 'PRODUCTIVE' and not 'productive' - and running it per domain would
        # be 48,000 provider calls to answer a question the estate can answer
        # about itself. The provider-side check belongs before a PUSH, on the
        # few hundred leads actually being enrolled, not on the supply list.
        cleared = nightlysourcing._local_collision([row], config=config)
        if not cleared:
            cut["collision"] += 1
            continue

        row["_icp_status"] = status
        row["_icp_score"] = verdict.get("icp_score")
        row["_icp_why"] = icp.evidence_text(verdict)
        qualified.append(row)

    for path, data in ((OUT, qualified), (REVIEW_OUT, review)):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            for item in data:
                handle.write(json.dumps(item) + "\n")

    print(f"  input            {len(seen):,} distinct domains")
    print("\n  CUTS, each counted separately:")
    for reason, n in cut.most_common():
        print(f"    {n:>8,}  {reason}")
    print(f"\n  QUALIFIED (export) {len(qualified):,}  -> {OUT}")
    print(f"  REVIEW (enrichment) {len(review):,}  -> {REVIEW_OUT}")
    return 0


def sample(n):
    data = [json.loads(l) for l in open(OUT, encoding="utf-8") if l.strip()]
    if not data:
        print("  nothing qualified; no sample")
        return 1
    random.seed(20260923)
    for row in random.sample(data, min(n, len(data))):
        print(f"  {row.get('employees'):>6}  {str(row.get('industry'))[:34]:<34} "
              f"{str(row.get('country'))[:16]:<16} {row['domain']}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--sample", type=int)
    args = parser.parse_args(argv)
    if args.sample:
        return sample(args.sample)
    if not args.run:
        parser.error("one of --run or --sample")
    with singlewalker.held(LOCK):
        return run()


if __name__ == "__main__":
    raise SystemExit(main())
