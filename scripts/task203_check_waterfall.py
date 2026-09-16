#!/usr/bin/env python3
"""TASK-203: Check the waterfall ledger for verification calls.

The task mentions that verification.verify wrote to the per-record waterfall
before the spend ledger existed. Let's check what the waterfall shows.
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

def main():
    records = load_jsonl("work/queue.snapshot.jsonl")

    print("="*70)
    print("WATERFALL LEDGER ANALYSIS")
    print("="*70)

    # Count records with waterfall entries
    records_with_waterfall = 0
    total_waterfall_rows = 0
    verification_rows = 0
    verification_by_provider = {}

    for rec in records:
        waterfall = rec.get("waterfall", [])
        if waterfall:
            records_with_waterfall += 1
            total_waterfall_rows += len(waterfall)
            for row in waterfall:
                stage = row.get("stage", "")
                if stage == "EMAIL_VERIFICATION":
                    verification_rows += 1
                    provider = row.get("provider", "unknown")
                    verification_by_provider[provider] = verification_by_provider.get(provider, 0) + 1

    print(f"Records with waterfall entries: {records_with_waterfall}")
    print(f"Total waterfall rows: {total_waterfall_rows}")
    print(f"EMAIL_VERIFICATION rows: {verification_rows}")

    if verification_by_provider:
        print("\n--- Verification calls by provider ---")
        for provider, count in sorted(verification_by_provider.items(), key=lambda x: -x[1]):
            print(f"  {provider}: {count}")

    # Now check: how many contacts have verification blocks with evidence?
    contacts_with_evidence = 0
    for rec in records:
        for contact in rec.get("contacts", []):
            if not contact.get("email"):
                continue
            v = contact.get("verification")
            if not v:
                continue
            evidence = v.get("evidence", [])
            if evidence:
                contacts_with_evidence += 1

    print(f"\nContacts with verification evidence: {contacts_with_evidence}")

    # Sample some waterfall entries
    print("\n--- Sample EMAIL_VERIFICATION waterfall entries (first 10) ---")
    count = 0
    for rec in records:
        waterfall = rec.get("waterfall", [])
        for row in waterfall:
            if row.get("stage") == "EMAIL_VERIFICATION":
                print(f"\nRecord {rec['id']}:")
                print(f"  Provider: {row.get('provider')}")
                print(f"  Call: {row.get('call')}")
                print(f"  Result: {row.get('result')}")
                print(f"  Expected cost: {row.get('expected_cost')}")
                print(f"  Actual cost: {row.get('actual_cost')}")
                print(f"  Reason: {row.get('reason')}")
                count += 1
                if count >= 10:
                    break
        if count >= 10:
            break

if __name__ == "__main__":
    main()
