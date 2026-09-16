#!/usr/bin/env python3
"""TASK-213: Locate the 42 records TASK-211 grouped as fail-closed.

Reads live queue state and reports:
1. Where each of the 42 sits (state, icp_status, criterion)
2. Whether the verdict is recorded or only derivable
3. The TASK-193 check on geo_excluded
4. Corrected review count

This script is READ-ONLY. It does not modify any record.
"""
import hashlib
import json
import os
import sys
from collections import Counter

# Live state is in Claude's worktree.
CLAUDE_QUEUE = (
    r"C:\Users\Zvonimir\Desktop\resonate-group-automation\work\queue.jsonl"
)
LOCAL_QUEUE = os.path.join(
    os.path.dirname(__file__), "..", "work", "queue.jsonl"
)


def load_queue(path):
    recs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def hash_id(rec):
    return hashlib.sha256(rec.get("id", "").encode()).hexdigest()[:12]


def hash_domain(rec):
    return hashlib.sha256(rec.get("domain", "").encode()).hexdigest()[:12]


def get_verdict(rec):
    return (rec.get("qualification") or {}).get("verdict") or {}


def get_structural(rec):
    return get_verdict(rec).get("structural") or {}


def get_criteria(rec):
    return get_structural(rec).get("criteria") or {}


def classify_record(rec):
    """Determine which TASK-211 group a record belongs to.

    TASK-211 grouped by icp_flags text matching. We check BOTH:
    - The actual criterion status (PASS/FAIL/UNKNOWN)
    - The icp_flags text (what TASK-211 used)

    Returns (group, criterion_status, details) or None.
    """
    criteria = get_criteria(rec)
    structural = get_structural(rec)
    verdict = get_verdict(rec)
    cf = rec.get("company_facts") or {}
    icp_flags = cf.get("icp_flags") or []

    emp = criteria.get("employees") or {}
    geo = criteria.get("geography") or {}

    emp_status = (emp.get("status") or "UNKNOWN").lower()
    geo_status = (geo.get("status") or "UNKNOWN").lower()

    # Check icp_flags for TASK-211-style grouping
    has_too_small_flag = any(
        "employee" in f.lower() and "under" in f.lower()
        for f in icp_flags
    )
    has_geo_flag = any(
        "geo" in f.lower() or "country" in f.lower()
        for f in icp_flags
    )

    # Group by actual criterion status
    if emp_status == "fail":
        return ("too_small_criterion_fail", emp_status, emp.get("why", ""),
                has_too_small_flag)

    if geo_status == "fail":
        return ("geo_excluded_exclude_list_fail", geo_status,
                geo.get("why", ""), has_geo_flag)

    # TASK-193: geography UNKNOWN because country not on include list
    if geo_status == "unknown":
        why = geo.get("why", "")
        if "neither list" in why or "unestablished" in why:
            return ("geo_not_on_include_list_unknown", geo_status, why,
                    has_geo_flag)

    # Records with too_small flag but employees is not FAIL
    if has_too_small_flag and emp_status != "fail":
        return ("too_small_flag_but_not_fail", emp_status,
                emp.get("why", ""), True)

    return None


def main():
    queue_path = None
    if os.path.exists(CLAUDE_QUEUE):
        queue_path = CLAUDE_QUEUE
        source = "Claude worktree (LIVE)"
    elif os.path.exists(LOCAL_QUEUE):
        queue_path = LOCAL_QUEUE
        source = "local worktree (may be stale)"
    else:
        print("ERROR: No queue.jsonl found")
        return 1

    print(f"Reading queue from: {queue_path}")
    print(f"Source: {source}")
    recs = load_queue(queue_path)
    print(f"Total records: {len(recs)}")
    print()

    # State distribution
    states = Counter(r.get("state") for r in recs)
    print("=== State distribution ===")
    for s, c in states.most_common():
        print(f"  {s}: {c}")
    print()

    # icp_status distribution
    statuses = Counter()
    for r in recs:
        statuses[get_verdict(r).get("icp_status", "ABSENT")] += 1
    print("=== ICP status distribution ===")
    for s, c in statuses.most_common():
        print(f"  {s}: {c}")
    print()

    # Structural verdict distribution
    struct_verdicts = Counter()
    for r in recs:
        struct_verdicts[get_structural(r).get("verdict", "ABSENT")] += 1
    print("=== Structural verdict distribution ===")
    for s, c in struct_verdicts.most_common():
        print(f"  {s}: {c}")
    print()

    # Locate all groups
    groups = {}
    unclassified_flags = []

    for r in recs:
        result = classify_record(r)
        cf = r.get("company_facts") or {}
        icp_flags = cf.get("icp_flags") or []

        if result:
            group = result[0]
            groups.setdefault(group, []).append({
                "id_hash": hash_id(r),
                "domain_hash": hash_domain(r),
                "state": r.get("state"),
                "icp_status": get_verdict(r).get("icp_status", "ABSENT"),
                "structural_verdict": get_structural(r).get("verdict", "ABSENT"),
                "primary_reason": get_structural(r).get("primary_reason"),
                "criterion_status": result[1],
                "why": result[2],
                "had_flag": result[3] if len(result) > 3 else None,
            })
        elif icp_flags:
            unclassified_flags.append({
                "id_hash": hash_id(r),
                "state": r.get("state"),
                "icp_status": get_verdict(r).get("icp_status", "ABSENT"),
                "flags": icp_flags,
            })

    print("=" * 70)
    print("TASK-211 GROUPS - LOCATED")
    print("=" * 70)

    for group_name in sorted(groups.keys()):
        records = groups[group_name]
        print(f"\n--- {group_name}: {len(records)} records ---")
        by_state = Counter(r["state"] for r in records)
        print(f"  By state: {dict(by_state)}")
        by_status = Counter(r["icp_status"] for r in records)
        print(f"  By icp_status: {dict(by_status)}")
        by_struct = Counter(r["structural_verdict"] for r in records)
        print(f"  By structural verdict: {dict(by_struct)}")

        # Show all records for small groups, first 10 for large
        show = records if len(records) <= 15 else records[:10]
        for r in show:
            print(f"    id={r['id_hash']} state={r['state']} "
                  f"icp={r['icp_status']} struct={r['structural_verdict']} "
                  f"criterion={r['criterion_status']}")
            print(f"      why={r['why'][:90]}")
        if len(records) > 15:
            print(f"    ... and {len(records) - 10} more")

    # Records with icp_flags but not classified
    if unclassified_flags:
        print(f"\n--- Records with icp_flags but not in any group: "
              f"{len(unclassified_flags)} ---")
        for r in unclassified_flags[:10]:
            print(f"    id={r['id_hash']} state={r['state']} "
                  f"icp={r['icp_status']} flags={r['flags']}")
        if len(unclassified_flags) > 10:
            print(f"    ... and {len(unclassified_flags) - 10} more")

    # TASK-193 check
    print()
    print("=" * 70)
    print("TASK-193 CHECK: geo_excluded")
    print("=" * 70)
    print()

    geo_fail = groups.get("geo_excluded_exclude_list_fail", [])
    geo_unknown = groups.get("geo_not_on_include_list_unknown", [])

    print(f"Records with geography FAIL (on exclude list): {len(geo_fail)}")
    print(f"Records with geography UNKNOWN (not on include list): "
          f"{len(geo_unknown)}")
    print()
    print("TASK-193 established: 'country not on include list' -> UNKNOWN,")
    print("not FAIL. This is DELIBERATE: a company headquartered outside the")
    print("target geography may still deliver inside it.")
    print()

    if geo_unknown:
        by_state = Counter(r["state"] for r in geo_unknown)
        by_status = Counter(r["icp_status"] for r in geo_unknown)
        print(f"geo_not_on_include_list by state: {dict(by_state)}")
        print(f"geo_not_on_include_list by icp_status: {dict(by_status)}")
        print()
        print("VERDICT: These records are NOT fail-closed. They are correctly")
        print("held as UNKNOWN/review per TASK-193's design finding.")

    if geo_fail:
        by_state = Counter(r["state"] for r in geo_fail)
        by_status = Counter(r["icp_status"] for r in geo_fail)
        print(f"\ngeo_excluded_exclude_list by state: {dict(by_state)}")
        print(f"geo_excluded_exclude_list by icp_status: {dict(by_status)}")
        print()
        print("These ARE fail-closed: the country is on the EXCLUDE list,")
        print("which produces a FAIL verdict.")

    # Corrected review count
    print()
    print("=" * 70)
    print("CORRECTED REVIEW COUNT")
    print("=" * 70)
    print()

    review_count = sum(1 for r in recs
                       if get_verdict(r).get("icp_status") == "review")
    print(f"Records with icp_status='review': {review_count}")

    # How many of each group are in review?
    for group_name in sorted(groups.keys()):
        records = groups[group_name]
        in_review = sum(1 for r in records if r["icp_status"] == "review")
        if in_review > 0:
            print(f"  {group_name} in review: {in_review}")

    # The 42 question
    too_small = groups.get("too_small_criterion_fail", [])
    too_small_flag_not_fail = groups.get("too_small_flag_but_not_fail", [])
    print()
    print("TASK-211 said 32 too_small + 10 geo_excluded = 42 fail-closed.")
    print(f"Actual too_small (employees FAIL): {len(too_small)}")
    print(f"Actual too_small (flag but NOT FAIL): "
          f"{len(too_small_flag_not_fail)}")
    print(f"Actual geo FAIL (exclude list): {len(geo_fail)}")
    print(f"Actual geo UNKNOWN (not on include list): {len(geo_unknown)}")
    print()

    # How many of too_small are already terminal?
    too_small_rejected = sum(1 for r in too_small
                             if r["icp_status"] == "rejected")
    too_small_review = sum(1 for r in too_small
                           if r["icp_status"] == "review")
    too_small_other = len(too_small) - too_small_rejected - too_small_review
    print(f"too_small (employees FAIL) breakdown:")
    print(f"  rejected (terminal): {too_small_rejected}")
    print(f"  review (should be terminal?): {too_small_review}")
    print(f"  other: {too_small_other}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
