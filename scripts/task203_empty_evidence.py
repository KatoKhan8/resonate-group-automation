#!/usr/bin/env python3
"""TASK-203: Investigate the 154 contacts with verification blocks but empty evidence.

The snapshot shows 159 contacts with no verification evidence:
- 5 have no verification block at all
- 154 have a verification block but with empty evidence lists

This script investigates why the waterfall created verification blocks
but never called any providers.
"""
import json
from pathlib import Path

def load_jsonl(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def analyze_empty_evidence():
    records = load_jsonl("work/queue.snapshot.jsonl")

    print("="*70)
    print("CONTACTS WITH VERIFICATION BLOCKS BUT EMPTY EVIDENCE")
    print("="*70)

    empty_evidence_contacts = []
    for rec in records:
        for contact in rec.get("contacts", []):
            if not contact.get("email"):
                continue
            v = contact.get("verification")
            if not v:
                continue
            evidence = v.get("evidence", [])
            if not evidence:
                empty_evidence_contacts.append({
                    "record_id": rec["id"],
                    "record_state": rec.get("state"),
                    "record_lane": rec.get("lane"),
                    "enrich_status": rec.get("stages", {}).get("enrich", {}).get("status"),
                    "enrich_note": rec.get("stages", {}).get("enrich", {}).get("note"),
                    "contact_key": contact.get("key"),
                    "contact_email": contact.get("email"),
                    "verification_state": v.get("state"),
                    "verification_reason": v.get("reason"),
                    "verification_stopped": v.get("stopped"),
                    "verification_cost": v.get("cost"),
                    "verification_at": v.get("at"),
                })

    print(f"Total contacts with empty evidence: {len(empty_evidence_contacts)}")

    # Breakdown by verification state
    print("\n--- Verification state ---")
    by_state = {}
    for c in empty_evidence_contacts:
        state = c["verification_state"] or "NO_STATE"
        by_state[state] = by_state.get(state, 0) + 1
    for state, count in sorted(by_state.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")

    # Breakdown by verification reason
    print("\n--- Verification reason ---")
    by_reason = {}
    for c in empty_evidence_contacts:
        reason = c["verification_reason"] or "NO_REASON"
        # Truncate long reasons
        if len(reason) > 80:
            reason = reason[:77] + "..."
        by_reason[reason] = by_reason.get(reason, 0) + 1
    for reason, count in sorted(by_reason.items(), key=lambda x: -x[1])[:20]:
        print(f"  {reason}: {count}")

    # Breakdown by verification stopped
    print("\n--- Verification stopped ---")
    by_stopped = {}
    for c in empty_evidence_contacts:
        stopped = c["verification_stopped"] or "NOT_STOPPED"
        by_stopped[stopped] = by_stopped.get(stopped, 0) + 1
    for stopped, count in sorted(by_stopped.items(), key=lambda x: -x[1]):
        print(f"  {stopped}: {count}")

    # Breakdown by verification cost
    print("\n--- Verification cost ---")
    by_cost = {}
    for c in empty_evidence_contacts:
        cost = c["verification_cost"]
        by_cost[cost] = by_cost.get(cost, 0) + 1
    for cost, count in sorted(by_cost.items()):
        print(f"  {cost}: {count}")

    # Breakdown by enrich status
    print("\n--- Enrich stage status ---")
    by_enrich = {}
    for c in empty_evidence_contacts:
        status = c["enrich_status"] or "NOT_RUN"
        by_enrich[status] = by_enrich.get(status, 0) + 1
    for status, count in sorted(by_enrich.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")

    # Breakdown by record state
    print("\n--- Record state ---")
    by_record_state = {}
    for c in empty_evidence_contacts:
        state = c["record_state"] or "NO_STATE"
        by_record_state[state] = by_record_state.get(state, 0) + 1
    for state, count in sorted(by_record_state.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")

    # Breakdown by record lane
    print("\n--- Record lane ---")
    by_lane = {}
    for c in empty_evidence_contacts:
        lane = c["record_lane"] or "NO_LANE"
        by_lane[lane] = by_lane.get(lane, 0) + 1
    for lane, count in sorted(by_lane.items(), key=lambda x: -x[1]):
        print(f"  {lane}: {count}")

    # Sample some records to see the pattern
    print("\n--- Sample records (first 5) ---")
    for i, c in enumerate(empty_evidence_contacts[:5]):
        print(f"\n[{i+1}] Record {c['record_id']}, contact {c['contact_key']}")
        print(f"    Email: {c['contact_email']}")
        print(f"    Record state: {c['record_state']}, lane: {c['record_lane']}")
        print(f"    Enrich: {c['enrich_status']} - {c['enrich_note']}")
        print(f"    Verification state: {c['verification_state']}")
        print(f"    Verification reason: {c['verification_reason']}")
        print(f"    Verification stopped: {c['verification_stopped']}")
        print(f"    Verification cost: {c['verification_cost']}")
        print(f"    Verification at: {c['verification_at']}")

    return empty_evidence_contacts

def analyze_no_block():
    records = load_jsonl("work/queue.snapshot.jsonl")

    print("\n\n")
    print("="*70)
    print("CONTACTS WITH NO VERIFICATION BLOCK AT ALL")
    print("="*70)

    no_block_contacts = []
    for rec in records:
        for contact in rec.get("contacts", []):
            if not contact.get("email"):
                continue
            if not contact.get("verification"):
                no_block_contacts.append({
                    "record_id": rec["id"],
                    "record_state": rec.get("state"),
                    "record_lane": rec.get("lane"),
                    "enrich_status": rec.get("stages", {}).get("enrich", {}).get("status"),
                    "enrich_note": rec.get("stages", {}).get("enrich", {}).get("note"),
                    "contact_key": contact.get("key"),
                    "contact_email": contact.get("email"),
                })

    print(f"Total contacts with no verification block: {len(no_block_contacts)}")

    # Breakdown by enrich status
    print("\n--- Enrich stage status ---")
    by_enrich = {}
    for c in no_block_contacts:
        status = c["enrich_status"] or "NOT_RUN"
        by_enrich[status] = by_enrich.get(status, 0) + 1
    for status, count in sorted(by_enrich.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")

    # Breakdown by record state
    print("\n--- Record state ---")
    by_record_state = {}
    for c in no_block_contacts:
        state = c["record_state"] or "NO_STATE"
        by_record_state[state] = by_record_state.get(state, 0) + 1
    for state, count in sorted(by_record_state.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")

    # Sample
    print("\n--- Sample records (all 5) ---")
    for i, c in enumerate(no_block_contacts):
        print(f"\n[{i+1}] Record {c['record_id']}, contact {c['contact_key']}")
        print(f"    Email: {c['contact_email']}")
        print(f"    Record state: {c['record_state']}, lane: {c['record_lane']}")
        print(f"    Enrich: {c['enrich_status']} - {c['enrich_note']}")

    return no_block_contacts

if __name__ == "__main__":
    empty = analyze_empty_evidence()
    no_block = analyze_no_block()

    print("\n\n")
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Contacts with empty evidence list: {len(empty)}")
    print(f"Contacts with no verification block: {len(no_block)}")
    print(f"Total with no verification evidence: {len(empty) + len(no_block)}")
