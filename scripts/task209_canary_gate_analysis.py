#!/usr/bin/env python3
"""TASK-209: Find the 6 contacts with full li1-li5 operator approval and
analyse their record states. Read-only. Hashes all PII.

Reads work/queue.snapshot.jsonl (the only queue data available in this
worktree - the live queue is in Claude's worktree only).
"""
import hashlib
import json
import os
import sys

QUEUE_PATH = os.path.join(os.path.dirname(__file__), "..", "work",
                          "queue.snapshot.jsonl")


def h12(value):
    """SHA-256 hash, first 12 hex chars."""
    return hashlib.sha256(str(value or "").encode()).hexdigest()[:12]


def load_records():
    records = []
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def find_operator_approved_contacts(records):
    """Find contacts with full li1-li5 operator approval.

    A contact has full li1-li5 operator approval when every step li1..li5
    in their cadence carries an approval with by == 'operator-control-arm'
    (or another human operator identifier, NOT 'claude').
    """
    LI_STEPS = ["li1", "li2", "li3", "li4", "li5"]
    OPERATOR_APPROVERS = {"operator-control-arm", "operator", "zb"}

    results = []
    for rec in records:
        cadence = rec.get("cadence") or {}
        for contact_key, steps in cadence.items():
            approved_count = 0
            approvers = set()
            step_details = []
            for step_key in LI_STEPS:
                step_data = steps.get(step_key, {})
                approval = step_data.get("approval")
                if approval:
                    by = approval.get("by", "")
                    fp = approval.get("fingerprint", "")
                    if by in OPERATOR_APPROVERS or (
                        by not in ("claude", "system", "")
                        and "operator" in by.lower()
                    ):
                        approved_count += 1
                        approvers.add(by)
                    step_details.append({
                        "step": step_key,
                        "approved": True,
                        "by": by,
                        "fingerprint": fp[:12] if fp else "",
                        "channel": step_data.get("channel", ""),
                    })
                else:
                    step_details.append({
                        "step": step_key,
                        "approved": False,
                        "by": None,
                        "fingerprint": "",
                        "channel": step_data.get("channel", ""),
                    })

            if approved_count == 5:
                contact_obj = None
                for c in (rec.get("contacts") or []):
                    if c.get("key") == contact_key:
                        contact_obj = c
                        break

                results.append({
                    "record_id": rec.get("id"),
                    "record_id_hash": h12(rec.get("id")),
                    "domain": rec.get("domain"),
                    "domain_hash": h12(rec.get("domain")),
                    "company": rec.get("company"),
                    "company_hash": h12(rec.get("company")),
                    "state": rec.get("state"),
                    "hold_reason": rec.get("hold_reason"),
                    "hold_class": rec.get("hold_class"),
                    "client": rec.get("client"),
                    "contact_key": contact_key,
                    "contact_hash": h12(contact_key),
                    "contact_name": (contact_obj or {}).get("name"),
                    "name_hash": h12((contact_obj or {}).get("name")),
                    "linkedin": (contact_obj or {}).get("linkedin"),
                    "profile_hash": h12((contact_obj or {}).get("linkedin")),
                    "sendable": (contact_obj or {}).get("sendable", False),
                    "email": (contact_obj or {}).get("email"),
                    "email_hash": h12((contact_obj or {}).get("email")),
                    "persona": (contact_obj or {}).get("persona"),
                    "angle": (contact_obj or {}).get("angle"),
                    "approvers": approvers,
                    "step_details": step_details,
                    "icp_status": rec.get("icp_status"),
                    "bison_lead_id": (contact_obj or {}).get("bison_lead_id"),
                })
    return results


def main():
    if not os.path.exists(QUEUE_PATH):
        print(f"ERROR: {QUEUE_PATH} not found")
        print("The live queue is in Claude's worktree only.")
        print("This script reads the snapshot, which is the only queue data")
        print("available in this worktree.")
        sys.exit(1)

    records = load_records()
    print(f"Loaded {len(records)} records from snapshot")

    approved = find_operator_approved_contacts(records)
    print(f"\nFound {len(approved)} contacts with full li1-li5 operator approval")
    print("=" * 80)

    for i, contact in enumerate(approved, 1):
        print(f"\n--- Contact #{i} ---")
        print(f"  Record ID hash:    {contact['record_id_hash']}")
        print(f"  Record state:      {contact['state']}")
        print(f"  Hold reason:       {contact['hold_reason']}")
        print(f"  Hold class:        {contact['hold_class']}")
        print(f"  Domain hash:       {contact['domain_hash']}")
        print(f"  Company hash:      {contact['company_hash']}")
        print(f"  Contact key hash:  {contact['contact_hash']}")
        print(f"  Name hash:         {contact['name_hash']}")
        print(f"  Profile hash:      {contact['profile_hash']}")
        print(f"  Email hash:        {contact['email_hash']}")
        print(f"  Sendable:          {contact['sendable']}")
        print(f"  Persona:           {contact['persona']}")
        print(f"  Angle:             {contact['angle']}")
        print(f"  Approvers:         {contact['approvers']}")
        print(f"  ICP status:        {contact['icp_status']}")
        print(f"  Bison lead ID:     {contact['bison_lead_id']}")
        print(f"  Client:            {contact['client']}")
        print(f"  LinkedIn present:  {bool(contact['linkedin'])}")
        for sd in contact["step_details"]:
            print(f"    {sd['step']}: approved={sd['approved']} by={sd['by']} "
                  f"fp={sd['fingerprint']} channel={sd['channel']}")

    # Summary by record state
    print("\n" + "=" * 80)
    print("SUMMARY BY RECORD STATE")
    states = {}
    for c in approved:
        s = c["state"]
        states.setdefault(s, []).append(c)
    for state, contacts in sorted(states.items()):
        print(f"\n  {state}: {len(contacts)} contact(s)")
        for c in contacts:
            print(f"    record={c['record_id_hash']} contact={c['contact_hash']} "
                  f"hold_reason={c['hold_reason']} sendable={c['sendable']} "
                  f"linkedin={bool(c['linkedin'])}")


if __name__ == "__main__":
    main()
