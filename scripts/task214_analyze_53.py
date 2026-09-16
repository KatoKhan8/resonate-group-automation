#!/usr/bin/env python3
"""TASK-214: analyze TASK-211's 53 records that would benefit from a free crawl.

TASK-211 measured:
- 53 queued records that would benefit from a free crawl
  (23 without any research + 30 with incomplete fields)
- 33 missing all three of industry/offices/employees

This script:
1. Identifies those records (or as close as possible)
2. Runs the free crawl on them (in memory, no persistence)
3. Checks how many reach an ICP verdict for zero credits

Does NOT persist changes to the queue.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import research, store, waterfall, qualify, icp


def would_benefit_from_crawl(rec):
    """A record would benefit if it needs research for ICP dimensions."""
    reason = research.why(rec)
    if reason:
        return True
    # Also check if it's missing key ICP fields
    facts = rec.get("company_facts") or {}
    missing = []
    if not facts.get("industry"):
        missing.append("industry")
    if not facts.get("offices"):
        missing.append("offices")
    if not facts.get("employees"):
        missing.append("employees")
    if len(missing) >= 3:
        return True
    return False


def main():
    records = store.load()
    print(f"Total records: {len(records)}")

    # Find records that would benefit from a free crawl
    beneficiaries = [r for r in records if would_benefit_from_crawl(r)]
    print(f"Records that would benefit from free crawl: {len(beneficiaries)}")

    # Find the 33 missing all three
    missing_all_three = []
    for rec in beneficiaries:
        facts = rec.get("company_facts") or {}
        missing = []
        if not facts.get("industry"):
            missing.append("industry")
        if not facts.get("offices"):
            missing.append("offices")
        if not facts.get("employees"):
            missing.append("employees")
        if len(missing) >= 3:
            missing_all_three.append(rec)

    print(f"Records missing all three (industry/offices/employees): {len(missing_all_three)}")
    print()

    # Run the free crawl on beneficiaries
    print("Running free crawl on beneficiaries...")
    print("=" * 80)

    verdicts_before = {}
    verdicts_after = {}
    crawls_attempted = 0
    crawls_succeeded = 0
    total_pages = 0
    total_research_rows = 0

    for rec in beneficiaries:
        record_id = rec["id"]

        # Check verdict before
        try:
            before = qualify.company(rec, {}, store_result=False)
            verdicts_before[record_id] = (before.get("verdict") or {}).get("icp_status")
        except Exception:
            verdicts_before[record_id] = None

        before_research = len(rec.get("research") or [])

        # Run the free crawl
        research.crawl_cache_clear()
        try:
            result = research.run(rec, {}, live=False)
            crawls_attempted += 1
            if result and len(result) > 0:
                crawls_succeeded += 1
                total_pages += len(result)
        except Exception as e:
            pass

        after_research = len(rec.get("research") or [])
        total_research_rows += (after_research - before_research)

        # Check verdict after
        try:
            after = qualify.company(rec, {}, store_result=False)
            verdicts_after[record_id] = (after.get("verdict") or {}).get("icp_status")
        except Exception:
            verdicts_after[record_id] = None

    print(f"Crawls attempted: {crawls_attempted}")
    print(f"Crawls succeeded: {crawls_succeeded}")
    print(f"Total pages fetched: {total_pages}")
    print(f"Total research rows written: {total_research_rows}")
    print()

    # Count verdict changes
    reached_verdict = 0
    changed_status = 0
    for record_id in verdicts_before:
        before = verdicts_before[record_id]
        after = verdicts_after.get(record_id)
        if after and after not in (None, "unknown", "review"):
            reached_verdict += 1
        if before != after:
            changed_status += 1

    print(f"Records that reached a verdict (not unknown/review): {reached_verdict}")
    print(f"Records whose status changed: {changed_status}")
    print()

    # Breakdown of final statuses
    status_counts = {}
    for record_id, status in verdicts_after.items():
        status_counts[status] = status_counts.get(status, 0) + 1

    print("Final ICP status breakdown:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"  {status or 'none'}: {count}")
    print()

    # For the 33 missing all three
    print("=" * 80)
    print(f"For the {len(missing_all_three)} records missing all three:")
    missing_verdicts = 0
    for rec in missing_all_three:
        record_id = rec["id"]
        after = verdicts_after.get(record_id)
        if after and after not in (None, "unknown", "review"):
            missing_verdicts += 1
    print(f"  Reached a verdict: {missing_verdicts}")
    print()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Of TASK-211's 53 records that would benefit from a free crawl:")
    print(f"  - {crawls_succeeded} crawls succeeded (fetched {total_pages} pages)")
    print(f"  - {reached_verdict} reached an ICP verdict for zero credits")
    print(f"  - {changed_status} changed their ICP status")
    print()
    print(f"Of the 33 missing all three (industry/offices/employees):")
    print(f"  - {missing_verdicts} reached a verdict")

    return 0


if __name__ == "__main__":
    sys.exit(main())
