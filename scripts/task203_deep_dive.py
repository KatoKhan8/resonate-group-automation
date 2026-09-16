#!/usr/bin/env python3
"""TASK-203: Deep dive into verification status.

The task description mentions 240 contacts with email and 159 without verification.
Live state shows only 87 contacts with email. This script investigates:
1. Are we counting contacts correctly?
2. Is the task measuring something different?
3. What does the snapshot show vs live state?
"""
import json
from pathlib import Path
from datetime import datetime

def load_jsonl(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def count_contacts(records, label):
    """Count contacts in various ways."""
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"{'='*60}")
    print(f"Total records: {len(records)}")

    # Count all contacts
    all_contacts = []
    for rec in records:
        for contact in rec.get("contacts", []):
            all_contacts.append((rec, contact))

    print(f"Total contacts (all): {len(all_contacts)}")

    # Contacts with email
    with_email = [(r, c) for r, c in all_contacts if c.get("email")]
    print(f"Contacts with email: {len(with_email)}")

    # Contacts with email but no verification block
    no_verification_block = [(r, c) for r, c in with_email if not c.get("verification")]
    print(f"Contacts with email, NO verification block: {len(no_verification_block)}")

    # Contacts with verification block
    has_verification_block = [(r, c) for r, c in with_email if c.get("verification")]
    print(f"Contacts with verification block: {len(has_verification_block)}")

    # Now check: does verification.evidence exist and is it empty?
    no_evidence = []
    has_evidence = []
    for r, c in has_verification_block:
        v = c.get("verification", {})
        evidence = v.get("evidence", [])
        if not evidence:
            no_evidence.append((r, c))
        else:
            has_evidence.append((r, c))

    print(f"\nOf contacts with verification block:")
    print(f"  Have evidence entries: {len(has_evidence)}")
    print(f"  Have EMPTY evidence list: {len(no_evidence)}")

    # Contacts with NO verification evidence at all (no block OR empty evidence)
    total_no_evidence = len(no_verification_block) + len(no_evidence)
    print(f"\n*** TOTAL with NO verification evidence: {total_no_evidence} ***")
    print(f"    (no block: {len(no_verification_block)}, empty evidence: {len(no_evidence)})")

    # Check for legacy evidence (verdict/reoon fields)
    with_legacy = []
    for r, c in no_verification_block:
        if c.get("verdict") or c.get("reoon"):
            with_legacy.append((r, c))
    print(f"\nOf contacts without verification block:")
    print(f"  Have legacy verdict/reoon fields: {len(with_legacy)}")

    # Breakdown by record state
    print(f"\n--- Record states of contacts with NO verification evidence ---")
    by_state = {}
    for r, c in no_verification_block + no_evidence:
        state = r.get("state") or "NO_STATE"
        by_state[state] = by_state.get(state, 0) + 1
    for state, count in sorted(by_state.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")

    # Breakdown by enrich stage
    print(f"\n--- Enrich stage status of contacts with NO verification evidence ---")
    by_enrich = {}
    for r, c in no_verification_block + no_evidence:
        enrich_status = r.get("stages", {}).get("enrich", {}).get("status", "NOT_RUN")
        by_enrich[enrich_status] = by_enrich.get(enrich_status, 0) + 1
    for status, count in sorted(by_enrich.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")

    return {
        "total_records": len(records),
        "total_contacts": len(all_contacts),
        "with_email": len(with_email),
        "no_verification_block": len(no_verification_block),
        "has_verification_block": len(has_verification_block),
        "no_evidence": len(no_evidence),
        "total_no_evidence": total_no_evidence,
    }

def main():
    # Live state
    live_records = load_jsonl("work/queue.jsonl")
    live_stats = count_contacts(live_records, "LIVE STATE (work/queue.jsonl)")

    # Snapshot
    print("\n\n")
    snapshot_records = load_jsonl("work/queue.snapshot.jsonl")
    snapshot_stats = count_contacts(snapshot_records, "SNAPSHOT STATE (work/queue.snapshot.jsonl)")

    # Comparison
    print("\n\n")
    print("="*60)
    print("COMPARISON")
    print("="*60)
    print(f"{'Metric':<40} {'Live':>10} {'Snapshot':>10}")
    print("-"*60)
    for key in ["total_records", "total_contacts", "with_email", "no_verification_block",
                "has_verification_block", "no_evidence", "total_no_evidence"]:
        print(f"{key:<40} {live_stats[key]:>10} {snapshot_stats[key]:>10}")

if __name__ == "__main__":
    main()
