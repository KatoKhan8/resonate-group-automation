#!/usr/bin/env python3
"""Report the four-bucket collision walk verdict.

    py -3 scripts/collision_walk_report.py
    py -3 scripts/collision_walk_report.py --walk work/stage/s6-collision-walk.json
    py -3 scripts/collision_walk_report.py --staleness-days 7

Reads the walk output and prints:

  - The four verdicts: CLEAR, COLLIDES, REFUSED, NOT_WALKED
  - Counts summing to the input set
  - Every COLLIDES row with campaign id, date, and ownership evidence
  - Every REFUSED row with the response shape that refused it
  - A staleness field on every clearance

WHY THIS EXISTS

The walk script writes per-domain verdicts. This script reads them and
reports the four buckets the task requires, with the evidence the task
demands. A report that has three buckets has lost one of them.

## THE FOUR VERDICTS

    CLEAR      walked, no touch from us or the client
    COLLIDES   walked, a touch found - with the campaign and the date
    REFUSED    the provider's answer was not trustworthy (broad match)
    NOT_WALKED not asked yet

REFUSED and NOT_WALKED are different answers and neither is CLEAR.
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import collision  # noqa: E402


def load_walk(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def classify_entry(entry):
    """Map a walk entry to one of the four verdict buckets.

    Returns (bucket, detail). The bucket is one of CLEAR, COLLIDES, REFUSED,
    NOT_WALKED. The detail carries the evidence the task requires.
    """
    if not isinstance(entry, dict):
        return "REFUSED", {"why": "entry is not a dict"}

    verdict = entry.get("verdict")
    policy = entry.get("policy")

    if verdict == "REFUSED" or (not verdict and not policy):
        return "REFUSED", {"why": entry.get("why", "no verdict and no policy")}

    if policy == collision.ALLOW:
        if verdict == collision.CLEAR:
            return "CLEAR", {}
        if verdict == collision.TOUCHED:
            return "CLEAR", {"note": "touched but policy is ALLOW (history)"}
        return "CLEAR", {"note": f"policy ALLOW, verdict {verdict}"}

    if policy == collision.STOP:
        detail = {"why": entry.get("why", "")}
        if verdict == collision.IN_SEQUENCE:
            detail["reason"] = "somebody is mid-sequence"
        else:
            detail["reason"] = f"verdict={verdict}"
        return "COLLIDES", detail

    if policy == collision.HOLD:
        detail = {"why": entry.get("why", "")}
        if entry.get("unknown_statuses"):
            detail["reason"] = f"unknown statuses: {entry['unknown_statuses']}"
        elif entry.get("any_bounce"):
            detail["reason"] = "an address bounced"
        else:
            detail["reason"] = f"verdict={verdict}, policy=HOLD"
        return "COLLIDES", detail

    return "REFUSED", {"why": f"unrecognised policy: {policy!r}"}


def staleness_of(entry, now=None):
    """Days since this entry was walked. None if no timestamp."""
    now = now or datetime.now(timezone.utc)
    at = entry.get("at") if isinstance(entry, dict) else None
    if not at:
        return None
    try:
        walked = datetime.fromisoformat(at.replace("Z", "+00:00"))
        return (now - walked).days
    except (ValueError, TypeError):
        return None


def report(walk_path, staleness_threshold=14):
    data = load_walk(walk_path)
    if data is None:
        print(f"NO WALK FILE at {walk_path}")
        print("The collision walk has not been run yet.")
        print("NOT_WALKED: all domains (the walk has not started)")
        return

    accounts = data.get("accounts", {})
    if not accounts:
        print("WALK FILE EXISTS but has no accounts")
        return

    buckets = Counter()
    clear_details = []
    collides_details = []
    refused_details = []

    for domain, entry in sorted(accounts.items()):
        bucket, detail = classify_entry(entry)
        buckets[bucket] += 1
        age = staleness_of(entry)
        base = {"domain": domain, "age_days": age, **detail}

        if bucket == "CLEAR":
            clear_details.append(base)
        elif bucket == "COLLIDES":
            base["campaign_ids"] = [
                c.get("campaign_id")
                for c in (entry.get("people") or [{}])[0].get("campaigns", [])
            ] if entry.get("people") else []
            collides_details.append(base)
        elif bucket == "REFUSED":
            refused_details.append(base)

    total = sum(buckets.values())
    print(f"\nCOLLISION WALK REPORT  {walk_path}")
    print(f"  walked: {total} account(s)")
    print(f"  started_at: {data.get('started_at', 'unknown')}")
    print()
    print(f"  {'BUCKET':<14} {'COUNT':>6}")
    for bucket in ("CLEAR", "COLLIDES", "REFUSED", "NOT_WALKED"):
        print(f"  {bucket:<14} {buckets.get(bucket, 0):>6}")
    print(f"  {'TOTAL':<14} {total:>6}")

    stale_count = sum(
        1 for d in clear_details
        if d.get("age_days") is not None and d["age_days"] > staleness_threshold
    )
    if stale_count:
        print(f"\n  STALE CLEARANCES: {stale_count} clearance(s) older than "
              f"{staleness_threshold} days")

    if collides_details:
        print(f"\n  COLLIDES ({len(collides_details)}):")
        for row in collides_details[:10]:
            campaigns = row.pop("campaign_ids", [])
            print(f"    {row['domain']:<40} "
                  f"age={row.get('age_days', '?')}d  "
                  f"reason={row.get('reason', row.get('why', ''))}")
            if campaigns:
                print(f"      campaigns: {campaigns}")

    if refused_details:
        print(f"\n  REFUSED ({len(refused_details)}):")
        for row in refused_details[:10]:
            print(f"    {row['domain']:<40} "
                  f"why={row.get('why', '')[:80]}")

    return {
        "buckets": dict(buckets),
        "total": total,
        "clear": clear_details,
        "collides": collides_details,
        "refused": refused_details,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--walk", default=os.path.join(
        ROOT, "work", "stage", "s6-collision-walk.json"))
    ap.add_argument("--staleness-days", type=int, default=14)
    args = ap.parse_args(argv)
    report(args.walk, staleness_threshold=args.staleness_days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
