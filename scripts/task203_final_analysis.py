#!/usr/bin/env python3
"""TASK-203: Final analysis - why do 154 contacts have empty verification evidence?"""
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
    print("FINAL ANALYSIS: WHY 154 CONTACTS HAVE EMPTY VERIFICATION")
    print("="*70)

    # Collect all contacts with empty verification evidence
    empty_verification_contacts = []
    for rec in records:
        for contact in rec.get("contacts", []):
            if not contact.get("email"):
                continue
            v = contact.get("verification")
            if not v:
                continue
            evidence = v.get("evidence", [])
            if not evidence:
                empty_verification_contacts.append({
                    "record_id": rec["id"],
                    "record": rec,
                    "contact": contact,
                })

    print(f"Total contacts with empty verification: {len(empty_verification_contacts)}")

    # Check if their records have ANY email_verification waterfall entries
    records_with_email_verification = 0
    records_without_email_verification = 0

    for item in empty_verification_contacts:
        rec = item["record"]
        waterfall = rec.get("waterfall", [])
        has_email_verification = any(row.get("stage") == "email_verification" for row in waterfall)
        if has_email_verification:
            records_with_email_verification += 1
        else:
            records_without_email_verification += 1

    print(f"\nRecords with email_verification in waterfall: {records_with_email_verification}")
    print(f"Records WITHOUT email_verification in waterfall: {records_without_email_verification}")

    # Check the enrich stage status
    print("\n--- Enrich stage status of contacts with empty verification ---")
    enrich_status_counts = {}
    for item in empty_verification_contacts:
        rec = item["record"]
        status = rec.get("stages", {}).get("enrich", {}).get("status", "NOT_RUN")
        enrich_status_counts[status] = enrich_status_counts.get(status, 0) + 1
    for status, count in sorted(enrich_status_counts.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")

    # Check if the record has ANY waterfall entries
    print("\n--- Waterfall presence for contacts with empty verification ---")
    waterfall_presence = {}
    for item in empty_verification_contacts:
        rec = item["record"]
        waterfall = rec.get("waterfall", [])
        n = len(waterfall)
        waterfall_presence[n] = waterfall_presence.get(n, 0) + 1
    for n, count in sorted(waterfall_presence.items()):
        print(f"  {n} waterfall rows: {count} contacts")

    # Sample some records without email_verification in waterfall
    print("\n--- Sample records WITHOUT email_verification in waterfall (first 5) ---")
    count = 0
    for item in empty_verification_contacts:
        rec = item["record"]
        waterfall = rec.get("waterfall", [])
        has_email_verification = any(row.get("stage") == "email_verification" for row in waterfall)
        if not has_email_verification:
            print(f"\n[{count+1}] Record {rec['id']}")
            print(f"    State: {rec.get('state')}")
            print(f"    Enrich: {rec.get('stages', {}).get('enrich', {}).get('status')}")
            print(f"    Waterfall rows: {len(waterfall)}")
            for i, row in enumerate(waterfall[:3]):
                print(f"      [{i}] {row.get('stage')}: {row.get('provider')}/{row.get('call')}")
            contact = item["contact"]
            v = contact.get("verification", {})
            print(f"    Contact: {contact.get('key')}")
            print(f"    Verification state: {v.get('state')}")
            print(f"    Verification reason: {v.get('reason')}")
            print(f"    Verification cost: {v.get('cost')}")
            print(f"    Verification stopped: {v.get('stopped')}")
            print(f"    Verification at: {v.get('at')}")
            count += 1
            if count >= 5:
                break

    # Sample some records WITH email_verification in waterfall but contact still has empty evidence
    print("\n\n--- Sample records WITH email_verification but empty contact evidence (first 5) ---")
    count = 0
    for item in empty_verification_contacts:
        rec = item["record"]
        waterfall = rec.get("waterfall", [])
        has_email_verification = any(row.get("stage") == "email_verification" for row in waterfall)
        if has_email_verification:
            print(f"\n[{count+1}] Record {rec['id']}")
            print(f"    State: {rec.get('state')}")
            print(f"    Enrich: {rec.get('stages', {}).get('enrich', {}).get('status')}")
            print(f"    Waterfall rows: {len(waterfall)}")
            email_ver_rows = [r for r in waterfall if r.get("stage") == "email_verification"]
            print(f"    email_verification rows: {len(email_ver_rows)}")
            for i, row in enumerate(email_ver_rows[:3]):
                print(f"      [{i}] {row.get('provider')}/{row.get('call')}: result={row.get('result')}")
            contact = item["contact"]
            v = contact.get("verification", {})
            print(f"    Contact: {contact.get('key')}")
            print(f"    Verification state: {v.get('state')}")
            print(f"    Verification reason: {v.get('reason')}")
            print(f"    Verification cost: {v.get('cost')}")
            print(f"    Verification stopped: {v.get('stopped')}")
            count += 1
            if count >= 5:
                break

if __name__ == "__main__":
    main()
