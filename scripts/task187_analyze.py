#!/usr/bin/env python3
"""TASK-187: is icp_pass reachable at all?

Reads the queue snapshot and re-runs the structural verdict logic to answer:
1. What does verdict_of actually require?
2. How did the 32+ qualified records get there?
3. How many of 550 can reach icp_pass if every purchasable fact were bought?
4. What actually gates person-credit spend?
"""
import json
import sys
from collections import Counter

SNAPSHOT = "work/queue.snapshot.jsonl"


def load():
    with open(SNAPSHOT, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main():
    recs = load()
    print(f"Records: {len(recs)}")
    print()

    # --- 1. Current icp_status distribution ---
    statuses = Counter()
    for r in recs:
        q = r.get("qualification") or {}
        v = (q.get("verdict") or {}).get("icp_status", "NONE")
        statuses[v] += 1
    print("=== CURRENT ICP STATUS (stored on record) ===")
    for k, v in statuses.most_common():
        print(f"  {k}: {v}")
    print()

    # --- 2. Current structural verdict distribution ---
    struct_statuses = Counter()
    for r in recs:
        q = r.get("qualification") or {}
        v = (q.get("verdict") or {}).get("structural", {}).get("verdict", "NONE")
        struct_statuses[v] += 1
    print("=== STORED STRUCTURAL VERDICT ===")
    for k, v in struct_statuses.most_common():
        print(f"  {k}: {v}")
    print()

    # --- 3. Qualified records: trace their structural criteria ---
    qualified = [r for r in recs if (r.get("qualification") or {}).get(
        "verdict", {}).get("icp_status") == "qualified"]
    print(f"=== QUALIFIED RECORDS: {len(qualified)} ===")
    for i, r in enumerate(qualified[:10]):
        q = r.get("qualification") or {}
        v = q.get("verdict") or {}
        s = v.get("structural") or {}
        print(f"\n  [{i+1}] {r.get('domain')}: status={v.get('icp_status')}, "
              f"tier={v.get('icp_tier')}, score={v.get('icp_score')}")
        print(f"    structural verdict: {s.get('verdict')}")
        print(f"    eligible: {s.get('eligible')}")
        criteria = s.get("criteria") or {}
        for name in ("geography", "company_type", "services_business",
                      "employees", "tracks_time"):
            ans = criteria.get(name) or {}
            why = (ans.get("why") or "")[:100]
            print(f"      {name:20s}: {ans.get('status', 'MISSING'):20s} {why}")
        unknowns = s.get("unknown_criteria") or []
        print(f"    unknown_criteria: {unknowns}")

    # --- 4. tracks_time distribution across all records ---
    print("\n=== TRACKS_TIME CRITERION (stored) ===")
    tt_dist = Counter()
    for r in recs:
        q = r.get("qualification") or {}
        s = (q.get("verdict") or {}).get("structural") or {}
        criteria = s.get("criteria") or {}
        tt = (criteria.get("tracks_time") or {}).get("status", "MISSING")
        tt_dist[tt] += 1
    for k, v in tt_dist.most_common():
        print(f"  {k}: {v}")

    # --- 5. How many records have NO fail on any criterion except tracks_time? ---
    # If tracks_time were the ONLY unknown, how many would pass?
    print("\n=== REACHABILITY ANALYSIS ===")
    no_fail_except_tt = 0
    would_pass_if_tt_pass = 0
    would_pass_uncertain_if_tt_unknown = 0
    still_review = 0

    for r in recs:
        q = r.get("qualification") or {}
        s = (q.get("verdict") or {}).get("structural") or {}
        criteria = s.get("criteria") or {}

        if not criteria:
            continue

        # Check each criterion
        has_fail = False
        has_non_tt_unknown = False
        tt_status = (criteria.get("tracks_time") or {}).get("status", "MISSING")
        defining_pass = True

        for name in ("geography", "company_type", "services_business",
                      "employees", "tracks_time"):
            ans = criteria.get(name) or {}
            status = ans.get("status", "MISSING")
            if status == "fail":
                has_fail = True
            if status == "unknown" and name != "tracks_time":
                has_non_tt_unknown = True
            if name in ("geography", "company_type"):
                if status not in ("pass", "pass_with_tolerance", "not_required"):
                    defining_pass = False

        if has_fail:
            continue

        # No fails at all
        no_fail_except_tt += 1

        # If tracks_time were PASS, would this record reach icp_pass?
        # All others must be PASSING
        all_others_pass = True
        for name in ("geography", "company_type", "services_business",
                      "employees"):
            ans = criteria.get(name) or {}
            status = ans.get("status", "MISSING")
            if status not in ("pass", "pass_with_tolerance", "not_required"):
                all_others_pass = False
                break

        if all_others_pass:
            would_pass_if_tt_pass += 1

        # With tracks_time UNKNOWN, would it reach icp_pass_with_uncertainty?
        if defining_pass and not has_non_tt_unknown:
            # Only tracks_time is unknown (or nothing is)
            would_pass_uncertain_if_tt_unknown += 1
        elif defining_pass:
            # Defining pass but other unknowns exist
            still_review += 1

    print(f"  Records with no FAIL on any criterion: {no_fail_except_tt}")
    print(f"  Would reach icp_pass if tracks_time were PASS: "
          f"{would_pass_if_tt_pass}")
    print(f"  Would reach icp_pass_with_uncertainty with tracks_time UNKNOWN "
          f"(only TT unknown): {would_pass_uncertain_if_tt_unknown}")
    print(f"  Still review even with TT resolved (other unknowns): "
          f"{still_review}")

    # --- 6. What is the FULL set of criterion combinations for qualified records? ---
    print("\n=== QUALIFIED RECORDS: CRITERIA COMBINATIONS ===")
    combos = Counter()
    for r in qualified:
        q = r.get("qualification") or {}
        s = (q.get("verdict") or {}).get("structural") or {}
        criteria = s.get("criteria") or {}
        combo = tuple(
            (criteria.get(name) or {}).get("status", "MISSING")
            for name in ("geography", "company_type", "services_business",
                         "employees", "tracks_time")
        )
        combos[combo] += 1
    for combo, count in combos.most_common():
        labels = ("geo", "type", "svc", "emp", "tt")
        parts = [f"{l}={s}" for l, s in zip(labels, combo)]
        print(f"  {count:3d}x  {', '.join(parts)}")

    # --- 7. Records with NO qualification verdict at all ---
    no_verdict = [r for r in recs if not (r.get("qualification") or {}).get("verdict")]
    print(f"\n=== RECORDS WITH NO STORED VERDICT: {len(no_verdict)} ===")

    # --- 8. What do the review/unknown records look like? ---
    review_recs = [r for r in recs if (r.get("qualification") or {}).get(
        "verdict", {}).get("icp_status") == "review"]
    print(f"\n=== REVIEW RECORDS: {len(review_recs)} ===")
    review_unknowns = Counter()
    for r in review_recs:
        q = r.get("qualification") or {}
        s = (q.get("verdict") or {}).get("structural") or {}
        for name in (s.get("unknown_criteria") or []):
            review_unknowns[name] += 1
    print("  Unknown criteria in review records:")
    for k, v in review_unknowns.most_common():
        print(f"    {k}: {v}")

    # --- 9. Per-criterion status distribution across ALL records ---
    print("\n=== PER-CRITERION STATUS DISTRIBUTION (stored) ===")
    for criterion in ("geography", "company_type", "services_business",
                       "employees", "tracks_time"):
        dist = Counter()
        for r in recs:
            q = r.get("qualification") or {}
            s = (q.get("verdict") or {}).get("structural") or {}
            criteria = s.get("criteria") or {}
            status = (criteria.get(criterion) or {}).get("status", "MISSING")
            dist[status] += 1
        print(f"  {criterion}:")
        for k, v in dist.most_common():
            print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
