#!/usr/bin/env python3
"""Find a record where the crawl succeeded and check impact."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import research, store, qualify


def main():
    records = store.load()
    # Find records that would benefit
    beneficiaries = [r for r in records if research.why(r)]

    found = 0
    for rec in beneficiaries[:20]:  # Check first 20
        before_research = len(rec.get("research") or [])

        # Run the free crawl
        research.crawl_cache_clear()
        result = research.run(rec, {}, live=False)

        after_research = len(rec.get("research") or [])

        if after_research > before_research:
            found += 1
            print(f"Record: {rec['id']}")
            print(f"  Domain: {rec.get('domain')}")
            print(f"  Reason: {research.why(rec)}")
            print(f"  Rows added: {after_research - before_research}")

            # Check verdict before (need to reload to get clean state)
            # Actually, we already modified rec, so let's just show after
            after = qualify.company(rec, {}, store_result=False)
            after_verdict = (after.get("verdict") or {}).get("icp_status")
            print(f"  After ICP status: {after_verdict}")

            if rec.get("research"):
                print(f"  Sample evidence:")
                for row in rec["research"][:2]:
                    fact = row.get("fact", "")[:80]
                    print(f"    - {row.get('field')}: {fact}...")
            print()

            if found >= 3:
                break

    if found == 0:
        print("No records found where crawl succeeded in first 20 beneficiaries")

    return 0


if __name__ == "__main__":
    sys.exit(main())
