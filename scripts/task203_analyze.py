#!/usr/bin/env python3
"""TASK-203: Analyze why 159 contacts never entered the verification waterfall.

Reads live state from work/queue.jsonl and reports:
1. Total contacts with email addresses
2. How many have no verification block at all
3. How many have verification evidence
4. The record states of contacts without verification
5. Whether enrich stage was run on their records
"""
import json
from pathlib import Path

QUEUE_PATH = Path("work/queue.jsonl")

def load_records():
    """Load all records from the queue."""
    records = []
    with open(QUEUE_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def analyze():
    records = load_records()
    print(f"Total records: {len(records)}")

    # Count contacts
    all_contacts = []
    for rec in records:
        for contact in rec.get("contacts", []):
            all_contacts.append({
                "record_id": rec["id"],
                "record_state": rec.get("state"),
                "record_stages": rec.get("stages", {}),
                "record_lane": rec.get("lane"),
                "contact_key": contact.get("key"),
                "contact_email": contact.get("email"),
                "contact_verification": contact.get("verification"),
                "contact_verdict": contact.get("verdict"),
                "contact_reoon": contact.get("reoon"),
            })

    print(f"Total contacts: {len(all_contacts)}")

    contacts_with_email = [c for c in all_contacts if c["contact_email"]]
    print(f"Contacts with email: {len(contacts_with_email)}")

    # Contacts with no verification block at all
    no_verification = [c for c in contacts_with_email if not c["contact_verification"]]
    print(f"\nContacts with email but NO verification block: {len(no_verification)}")

    # Contacts with verification block
    has_verification = [c for c in contacts_with_email if c["contact_verification"]]
    print(f"Contacts with verification block: {len(has_verification)}")

    # Break down the no_verification group by record state
    print("\n--- Breakdown of contacts WITHOUT verification by record state ---")
    by_state = {}
    for c in no_verification:
        state = c["record_state"] or "NO_STATE"
        by_state[state] = by_state.get(state, 0) + 1
    for state, count in sorted(by_state.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")

    # Break down by enrich stage status
    print("\n--- Breakdown by enrich stage status ---")
    by_enrich = {}
    for c in no_verification:
        enrich_status = c["record_stages"].get("enrich", {}).get("status", "NOT_RUN")
        by_enrich[enrich_status] = by_enrich.get(enrich_status, 0) + 1
    for status, count in sorted(by_enrich.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")

    # Break down by record lane
    print("\n--- Breakdown by record lane ---")
    by_lane = {}
    for c in no_verification:
        lane = c["record_lane"] or "NO_LANE"
        by_lane[lane] = by_lane.get(lane, 0) + 1
    for lane, count in sorted(by_lane.items(), key=lambda x: -x[1]):
        print(f"  {lane}: {count}")

    # Check if any have legacy verdict or reoon fields (which count as evidence)
    print("\n--- Legacy evidence check (contacts without verification block) ---")
    with_legacy_verdict = [c for c in no_verification if c["contact_verdict"]]
    with_legacy_reoon = [c for c in no_verification if c["contact_reoon"]]
    print(f"  Have legacy 'verdict' field: {len(with_legacy_verdict)}")
    print(f"  Have legacy 'reoon' field: {len(with_legacy_reoon)}")

    # Now analyze contacts WITH verification
    print("\n--- Contacts WITH verification block ---")
    verification_states = {}
    for c in has_verification:
        v = c["contact_verification"]
        state = v.get("state", "NO_STATE")
        verification_states[state] = verification_states.get(state, 0) + 1
    for state, count in sorted(verification_states.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")

    # Check verification evidence
    print("\n--- Verification evidence breakdown ---")
    evidence_counts = {}
    for c in has_verification:
        v = c["contact_verification"]
        evidence = v.get("evidence", [])
        n = len(evidence)
        evidence_counts[n] = evidence_counts.get(n, 0) + 1
    for n, count in sorted(evidence_counts.items()):
        print(f"  {n} evidence entries: {count} contacts")

    # Check which providers appear in evidence
    print("\n--- Providers in verification evidence ---")
    provider_counts = {}
    for c in has_verification:
        v = c["contact_verification"]
        evidence = v.get("evidence", [])
        for e in evidence:
            provider = e.get("provider", "unknown")
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
    for provider, count in sorted(provider_counts.items(), key=lambda x: -x[1]):
        print(f"  {provider}: {count} contacts")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total contacts with email: {len(contacts_with_email)}")
    print(f"Never entered verification (no block): {len(no_verification)}")
    print(f"Entered verification (have block): {len(has_verification)}")

    # The two populations the task asks about
    # Population 1: records that never reached the enrich stage (which runs verification)
    pop1_enrich_not_done = [c for c in no_verification
                            if c["record_stages"].get("enrich", {}).get("status") not in ("done", "partial")]
    print(f"\nPopulation 1 - Record never completed enrich stage: {len(pop1_enrich_not_done)}")

    # Population 2: records that completed enrich but contact still has no verification
    pop2_enrich_done = [c for c in no_verification
                        if c["record_stages"].get("enrich", {}).get("status") in ("done", "partial")]
    print(f"Population 2 - Record completed enrich but contact not verified: {len(pop2_enrich_done)}")

if __name__ == "__main__":
    analyze()
