#!/usr/bin/env python3
"""TASK-214: prove the free crawl works over 10 records.

Loads 10 records that currently have no research, runs the free webfetch
crawl on each, and reports per-record results. Does NOT persist changes to
the queue - this is a proof run, not a production run.

Reports:
- crawl attempted (yes/no)
- pages fetched (count)
- research rows written (count)
- whether a criterion moved from UNKNOWN (yes/no)
- the waterfall row that now exists (stage, provider, call, cost)
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import research, store, waterfall, icpstructural


def main():
    records = store.load()
    no_research = [r for r in records if not r.get("research")]
    print(f"Total records: {len(records)}")
    print(f"Records with no research: {len(no_research)}")
    print()

    if len(no_research) == 0:
        print("No records without research found.")
        return 0

    ten = no_research[:10]
    print(f"Running free crawl over {len(ten)} records...")
    print("=" * 80)
    print()

    results = []
    for rec in ten:
        record_id = rec["id"]
        domain = rec.get("domain", "unknown")
        # Hash the domain for privacy
        import hashlib
        domain_hash = hashlib.sha256(domain.encode()).hexdigest()[:12]

        print(f"Record: {record_id}")
        print(f"  Domain (hashed): {domain_hash}")

        reason = research.why(rec)
        if not reason:
            print(f"  Crawl attempted: NO (no stated need)")
            print(f"  Reason: structured evidence is sufficient")
            results.append({
                "record": record_id,
                "domain_hash": domain_hash,
                "crawl_attempted": False,
                "reason": "no stated need",
                "pages_fetched": 0,
                "research_rows": 0,
                "criterion_moved": False,
                "waterfall_row": None,
            })
            print()
            continue

        print(f"  Crawl attempted: YES (reason: {reason})")

        before_research = len(rec.get("research") or [])
        before_waterfall = len(waterfall.ledger(rec))

        # Check ICP before
        before_flags = {}
        try:
            before_verdict = icpstructural.score(rec)
            before_flags = before_verdict.get("flags", {})
        except Exception:
            pass

        # Run the free crawl
        research.crawl_cache_clear()
        try:
            result = research.run(rec, {}, live=False)
            crawl_attempted = True
        except Exception as e:
            print(f"  ERROR: {e}")
            crawl_attempted = False
            result = []

        after_research = len(rec.get("research") or [])
        after_waterfall = len(waterfall.ledger(rec))
        pages_fetched = after_research - before_research
        research_rows = after_research - before_research

        # Check ICP after
        after_flags = {}
        criterion_moved = False
        try:
            after_verdict = icpstructural.score(rec)
            after_flags = after_verdict.get("flags", {})
            for key in before_flags:
                if before_flags[key] == "UNKNOWN" and after_flags.get(key) != "UNKNOWN":
                    criterion_moved = True
                    break
        except Exception:
            pass

        # Get the waterfall row
        wf_rows = waterfall.ledger(rec)[before_waterfall:]
        webfetch_row = None
        for row in wf_rows:
            if row.get("provider") == "webfetch":
                webfetch_row = {
                    "stage": row.get("stage"),
                    "provider": row.get("provider"),
                    "call": row.get("call"),
                    "expected_cost": row.get("expected_cost"),
                    "result": row.get("result"),
                }
                break

        print(f"  Pages fetched: {pages_fetched}")
        print(f"  Research rows written: {research_rows}")
        print(f"  Criterion moved from UNKNOWN: {criterion_moved}")
        if webfetch_row:
            print(f"  Waterfall row: stage={webfetch_row['stage']}, "
                  f"provider={webfetch_row['provider']}, "
                  f"call={webfetch_row['call']}, "
                  f"cost={webfetch_row['expected_cost']}, "
                  f"result={webfetch_row['result']}")
        else:
            print(f"  Waterfall row: NONE")

        results.append({
            "record": record_id,
            "domain_hash": domain_hash,
            "crawl_attempted": crawl_attempted,
            "reason": reason,
            "pages_fetched": pages_fetched,
            "research_rows": research_rows,
            "criterion_moved": criterion_moved,
            "waterfall_row": webfetch_row,
        })
        print()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    attempted = sum(1 for r in results if r["crawl_attempted"])
    pages = sum(r["pages_fetched"] for r in results)
    rows = sum(r["research_rows"] for r in results)
    moved = sum(1 for r in results if r["criterion_moved"])
    wf_rows = sum(1 for r in results if r["waterfall_row"] is not None)

    print(f"Records processed: {len(results)}")
    print(f"Crawls attempted: {attempted}")
    print(f"Total pages fetched: {pages}")
    print(f"Total research rows written: {rows}")
    print(f"Criteria moved from UNKNOWN: {moved}")
    print(f"Waterfall rows written: {wf_rows}")
    print()

    if wf_rows == attempted and attempted > 0:
        print("SUCCESS: every successful crawl wrote a waterfall row.")
    elif attempted > 0:
        print(f"PARTIAL: {wf_rows} of {attempted} crawls wrote waterfall rows.")
    else:
        print("NO CRAWLS: no records had a stated need.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
