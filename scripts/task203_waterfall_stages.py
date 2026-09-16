#!/usr/bin/env python3
"""TASK-203: Check what stages are in the waterfall."""
import json
from pathlib import Path

def load_jsonl(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def main():
    records = load_jsonl("work/queue.snapshot.jsonl")

    print("="*70)
    print("WATERFALL STAGES")
    print("="*70)

    stage_counts = {}
    for rec in records:
        waterfall = rec.get("waterfall", [])
        for row in waterfall:
            stage = row.get("stage", "NO_STAGE")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

    print("Stage counts:")
    for stage, count in sorted(stage_counts.items(), key=lambda x: -x[1]):
        print(f"  {stage}: {count}")

    # Check a record that has contacts with verification evidence
    print("\n\n--- Sample record with verification evidence ---")
    for rec in records:
        has_evidence = False
        for contact in rec.get("contacts", []):
            v = contact.get("verification")
            if v and v.get("evidence"):
                has_evidence = True
                break
        if has_evidence:
            print(f"\nRecord {rec['id']}:")
            print(f"  State: {rec.get('state')}")
            print(f"  Waterfall rows: {len(rec.get('waterfall', []))}")
            for i, row in enumerate(rec.get("waterfall", [])[:5]):
                print(f"    [{i}] stage={row.get('stage')}, provider={row.get('provider')}, call={row.get('call')}")
            print(f"  Contacts:")
            for contact in rec.get("contacts", []):
                if contact.get("email"):
                    v = contact.get("verification", {})
                    evidence = v.get("evidence", [])
                    print(f"    {contact.get('key')}: email={contact.get('email')}, state={v.get('state')}, evidence_count={len(evidence)}")
            break

if __name__ == "__main__":
    main()
