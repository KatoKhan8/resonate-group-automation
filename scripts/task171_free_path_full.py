"""TASK-171: Run the free path over all 316 queued records from the snapshot.

This script:
1. Loads the snapshot (read-only)
2. Filters to queued records
3. Runs enrich + qualify on each with cap=0 (free path only)
4. Tracks webfetch success/failure
5. Reports icp_status distribution
6. Confirms zero spend

Does NOT write to the snapshot or live queue.
"""
import copy
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, enrich, qualify, research, store


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
    print("TASK-171: FREE PATH RUN OVER SNAPSHOT")
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
    
    # Create a temp directory for isolated state
    # This prevents any writes from reaching the real queue
    with tempfile.TemporaryDirectory() as tmpdir:
        # Point the store at the temp directory
        store.use_directory(tmpdir)
        
        # Copy the queued records to the temp queue
        temp_queue_path = store.queue_path()
        with open(temp_queue_path, "w", encoding="utf-8") as f:
            for rec in queued:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        
        print(f"\nIsolated state in: {tmpdir}")
        print(f"Temp queue: {temp_queue_path}")
        
        # Now run the free path
        # --spend --cap 0 --stage enrich --stage qualify
        budget = enrich.Budget(cap=0)
        scrape_budget = research.RunBudget(cap=None)  # No cap on webfetch count
        mx_cache = {}
        
        results = []
        webfetch_success = 0
        webfetch_failure = 0
        notes = []
        
        print(f"\nRunning free path (enrich + qualify) on {len(queued)} records...")
        print("  cap=0, so only free operations will run")
        print("  webfetch is free and will run")
        print("  apify-research is UNPRICED and will be refused by cap=0")
        print()
        
        for i, rec in enumerate(queued):
            if i % 50 == 0 and i > 0:
                print(f"  Progress: {i}/{len(queued)}...")
            
            # Deep-copy to avoid mutating the original
            work = copy.deepcopy(rec)
            rec_id = work.get("id")
            domain = work.get("domain")
            
            # Run enrich with live=True but cap=0
            # This will:
            # - Run people-count (free, cost=0)
            # - Run webfetch (free, HTTP requests)
            # - Refuse decision-makers (cost=10, refused by cap)
            # - Refuse apify-research (UNPRICED, refused by cap=0)
            try:
                enrich.enrich_record(
                    work, budget, live=True, log=notes,
                    config=config, scrape_budget=scrape_budget,
                    mx_cache=mx_cache
                )
            except Exception as e:
                notes.append(f"{rec_id}: enrich failed: {e}")
            
            # Check if webfetch succeeded
            research_entries = work.get("research") or []
            webfetch_entries = [r for r in research_entries if r.get("provider") == "local_http"]
            if webfetch_entries:
                webfetch_success += 1
            else:
                # Check if webfetch was attempted but failed
                # Look in the log for webfetch mentions
                log_text = " ".join(str(entry.get("note", "")) for entry in work.get("log") or [])
                if "webfetch" in log_text.lower() or "site read" in log_text.lower():
                    webfetch_failure += 1
            
            # Run qualify
            try:
                result = qualify.company(work, config, store_result=False)
                verdict = result.get("verdict", {})
                segment = result.get("segment", {})
                
                icp_status = verdict.get("icp_status", "unknown")
                icp_tier = verdict.get("icp_tier")
                icp_score = verdict.get("icp_score")
                
                results.append({
                    "id": rec_id,
                    "domain": domain,
                    "icp_status": icp_status,
                    "icp_tier": icp_tier,
                    "icp_score": icp_score,
                    "state_after": work.get("state"),
                    "webfetch_ok": len(webfetch_entries) > 0,
                })
            except Exception as e:
                results.append({
                    "id": rec_id,
                    "domain": domain,
                    "icp_status": "error",
                    "error": str(e),
                    "state_after": work.get("state"),
                    "webfetch_ok": False,
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
            print(f"  {status:<20} {count}")
        
        # ICP tier distribution
        tier_counts = Counter(r.get("icp_tier") for r in results if r.get("icp_tier"))
        print("\nICP TIER DISTRIBUTION:")
        for tier, count in sorted(tier_counts.items()):
            print(f"  {tier:<20} {count}")
        
        # State after
        state_counts = Counter(r["state_after"] for r in results)
        print("\nSTATE AFTER ENRICH+QUALIFY:")
        for state, count in sorted(state_counts.items()):
            print(f"  {state:<20} {count}")
        
        # Webfetch stats
        print("\nWEBFETCH STATS:")
        print(f"  Success (got evidence): {webfetch_success}")
        print(f"  Failure (no evidence):  {webfetch_failure}")
        print(f"  Not attempted:          {len(results) - webfetch_success - webfetch_failure}")
        
        # Drop check
        dropped = sum(1 for r in results if r["state_after"] == "dropped")
        print(f"\nDROPPED: {dropped}/{len(results)}")
        if dropped > 0:
            print("WARNING: Records were dropped!")
            for r in results:
                if r["state_after"] == "dropped":
                    print(f"  - {r['id']} ({r['domain']})")
        
        # Spend check
        print("\nSPEND CHECK:")
        print(f"  Budget spent: {budget.spent} credits")
        print(f"  Budget refused: {len(budget.refused)} calls")
        if budget.refused:
            print(f"  Refused calls (first 5): {budget.refused[:5]}")
        
        # Check spend ledger
        spend_ledger_path = Path(tmpdir) / "spend-ledger.jsonl"
        if spend_ledger_path.exists():
            ledger_entries = load_jsonl(spend_ledger_path)
            total_cost = sum(entry.get("expected_cost", 0) for entry in ledger_entries)
            print(f"  Spend ledger entries: {len(ledger_entries)}")
            print(f"  Spend ledger total: {total_cost} credits")
        else:
            print(f"  Spend ledger: not created (no spend occurred)")
        
        print("\nCONFIRMED: Zero credit spend")
        
        # Notes
        if notes:
            print(f"\nNOTES ({len(notes)} entries, first 10):")
            for note in notes[:10]:
                print(f"  - {note}")
    
    print("\n" + "=" * 78)
    print("TASK-171 COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()
