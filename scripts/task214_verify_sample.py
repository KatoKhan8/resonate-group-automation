#!/usr/bin/env python3
"""Verify the free crawl impact by checking before/after for a sample."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import research, store, qualify


def main():
    records = store.load()
    # Find a record that would benefit and has no research
    beneficiaries = [r for r in records if research.why(r) and not r.get("research")]

    if not beneficiaries:
        print("No beneficiaries found")
        return 0

    rec = beneficiaries[0]
    print(f"Record: {rec['id']}")
    print(f"Domain: {rec.get('domain')}")
    print(f"Reason: {research.why(rec)}")
    print()

    # Check verdict before
    before = qualify.company(rec, {}, store_result=False)
    before_verdict = (before.get("verdict") or {}).get("icp_status")
    before_flags = (before.get("verdict") or {}).get("flags", {})
    print(f"Before crawl:")
    print(f"  ICP status: {before_verdict}")
    print(f"  Flags: {before_flags}")
    print(f"  Research rows: {len(rec.get('research') or [])}")
    print()

    # Run the free crawl
    research.crawl_cache_clear()
    result = research.run(rec, {}, live=False)
    print(f"Crawl result: {len(result) if result else 0} rows")
    print()

    # Check verdict after
    after = qualify.company(rec, {}, store_result=False)
    after_verdict = (after.get("verdict") or {}).get("icp_status")
    after_flags = (after.get("verdict") or {}).get("flags", {})
    print(f"After crawl:")
    print(f"  ICP status: {after_verdict}")
    print(f"  Flags: {after_flags}")
    print(f"  Research rows: {len(rec.get('research') or [])}")
    print()

    if before_verdict != after_verdict:
        print(f"STATUS CHANGED: {before_verdict} -> {after_verdict}")
    else:
        print(f"Status unchanged: {after_verdict}")

    # Check what the research evidence says
    if rec.get("research"):
        print()
        print("Research evidence added:")
        for row in rec["research"][:3]:
            print(f"  - {row.get('field')}: {row.get('fact', '')[:100]}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
