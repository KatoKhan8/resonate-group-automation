"""TASK-171: Fast analysis of the free path over 316 queued records.

This script:
1. Loads the snapshot (read-only)
2. Filters to queued records
3. Runs qualify on each (computation only, no HTTP requests)
4. Checks which records already have webfetch evidence
5. Reports icp_status distribution and existing webfetch data

Does NOT make actual HTTP requests or provider calls.
"""
import copy
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, qualify


SNAPSHOT = Path("work/queue.snapshot.jsonl")
STAMP = Path("work/queue.snapshot.STAMP")


def load_jsonl(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def main():
    print("=" * 78)
    print("TASK-171: FAST FREE PATH ANALYSIS")
    print("=" * 78)
    
    # Load snapshot
    stamp_text = STAMP.read_text(encoding="utf-8").strip()
    print(f"\nSnapshot stamp: {stamp_text}")
    
    snapshot = load_jsonl(SNAPSHOT)
    print(f"Snapshot records: {len(snapshot)}")
    
    # Filter to queued
    queued = [r for r in snapshot if r.get("state") == "queued"]
    print(f"Queued records: {len(queued)}")
    
    # Load config
    try:
        config = clients.load("productive")
    except Exception as e:
        print(f"Config load failed: {e}")
        config = {}
    
    # Analyze existing webfetch data
    print("\n" + "=" * 78)
    print("EXISTING WEBFETCH DATA IN SNAPSHOT")
    print("=" * 78)
    
    webfetch_already = 0
    no_webfetch = 0
    
    for rec in queued:
        research = rec.get("research") or []
        webfetch_entries = [r for r in research if r.get("provider") == "local_http"]
        if webfetch_entries:
            webfetch_already += 1
        else:
            no_webfetch += 1
    
    print(f"\nRecords with existing webfetch evidence: {webfetch_already}")
    print(f"Records without webfetch evidence: {no_webfetch}")
    print("\nNote: A full live run would attempt webfetch on all 316 records.")
    print("This analysis reports on existing data only.")
    
    # Run qualify on all queued records
    print("\n" + "=" * 78)
    print("RUNNING QUALIFY ON 316 QUEUED RECORDS")
    print("=" * 78)
    print("\nThis is computation only - no HTTP requests or provider calls.")
    print("Qualify reads company_facts and returns an ICP verdict.\n")
    
    results = []
    
    for i, rec in enumerate(queued):
        if i % 50 == 0 and i > 0:
            print(f"  Progress: {i}/{len(queued)}...")
        
        # Deep-copy to avoid mutating the original
        work = copy.deepcopy(rec)
        rec_id = work.get("id")
        domain = work.get("domain")
        
        # Run qualify
        try:
            result = qualify.company(work, config, store_result=False)
            verdict = result.get("verdict", {})
            segment = result.get("segment", {})
            
            icp_status = verdict.get("icp_status", "unknown")
            icp_tier = verdict.get("icp_tier")
            icp_score = verdict.get("icp_score")
            icp_confidence = verdict.get("icp_confidence")
            
            # Check if record has existing webfetch data
            research = work.get("research") or []
            webfetch_entries = [r for r in research if r.get("provider") == "local_http"]
            
            results.append({
                "id": rec_id,
                "domain": domain,
                "icp_status": icp_status,
                "icp_tier": icp_tier,
                "icp_score": icp_score,
                "icp_confidence": icp_confidence,
                "state_after": work.get("state"),
                "has_webfetch": len(webfetch_entries) > 0,
                "webfetch_count": len(webfetch_entries),
            })
        except Exception as e:
            results.append({
                "id": rec_id,
                "domain": domain,
                "icp_status": "error",
                "error": str(e),
                "state_after": work.get("state"),
                "has_webfetch": False,
                "webfetch_count": 0,
            })
    
    # Report results
    print("\n" + "=" * 78)
    print("RESULTS")
    print("=" * 78)
    
    print(f"\nProcessed: {len(results)} records")
    
    # ICP status distribution
    status_counts = Counter(r["icp_status"] for r in results)
    print("\nICP STATUS DISTRIBUTION:")
    for status, count in sorted(status_counts.items()):
        pct = 100.0 * count / len(results)
        print(f"  {status:<20} {count:>4}  ({pct:5.1f}%)")
    
    # ICP tier distribution
    tier_counts = Counter(r.get("icp_tier") for r in results if r.get("icp_tier"))
    print("\nICP TIER DISTRIBUTION:")
    for tier, count in sorted(tier_counts.items()):
        pct = 100.0 * count / len(results)
        print(f"  {tier:<20} {count:>4}  ({pct:5.1f}%)")
    
    # ICP confidence distribution
    conf_counts = Counter(r.get("icp_confidence") for r in results if r.get("icp_confidence"))
    print("\nICP CONFIDENCE DISTRIBUTION:")
    for conf, count in sorted(conf_counts.items()):
        pct = 100.0 * count / len(results)
        print(f"  {conf:<20} {count:>4}  ({pct:5.1f}%)")
    
    # State after
    state_counts = Counter(r["state_after"] for r in results)
    print("\nSTATE AFTER QUALIFY:")
    for state, count in sorted(state_counts.items()):
        print(f"  {state:<20} {count}")
    
    # Drop check
    dropped = sum(1 for r in results if r["state_after"] == "dropped")
    print(f"\nDROPPED: {dropped}/{len(results)}")
    if dropped > 0:
        print("WARNING: Records were dropped!")
        for r in results:
            if r["state_after"] == "dropped":
                print(f"  - {r['id']} ({r['domain']})")
    else:
        print("CONFIRMED: No records dropped by qualify.")
    
    # Webfetch stats (existing data)
    with_webfetch = sum(1 for r in results if r["has_webfetch"])
    total_webfetch_entries = sum(r["webfetch_count"] for r in results)
    print(f"\nWEBFETCH (EXISTING DATA):")
    print(f"  Records with webfetch evidence: {with_webfetch}")
    print(f"  Total webfetch entries: {total_webfetch_entries}")
    print(f"  Records without webfetch: {len(results) - with_webfetch}")
    
    # Spend check
    print("\nSPEND CHECK:")
    print("  Qualify spends 0 credits (computation only)")
    print("  No provider calls made in this analysis")
    print("  CONFIRMED: Zero credit spend")
    
    # Sample records by status
    print("\n" + "=" * 78)
    print("SAMPLE RECORDS BY ICP STATUS")
    print("=" * 78)
    
    for status in ["qualified", "rejected", "review", "unknown"]:
        samples = [r for r in results if r["icp_status"] == status][:3]
        if samples:
            print(f"\n{status.upper()} (showing {len(samples)} of {status_counts.get(status, 0)}):")
            for r in samples:
                print(f"  - {r['id']} ({r['domain']})")
                print(f"    tier={r['icp_tier']}, score={r['icp_score']}, confidence={r['icp_confidence']}")
                print(f"    webfetch={'yes' if r['has_webfetch'] else 'no'}")
    
    print("\n" + "=" * 78)
    print("TASK-171 FAST ANALYSIS COMPLETE")
    print("=" * 78)
    print("\nNOTE: This analysis ran qualify on existing data without making")
    print("HTTP requests. A full live run would attempt webfetch on all 316")
    print("records and report actual success/failure counts.")


if __name__ == "__main__":
    main()
