"""TASK-196: Analyse the queue snapshot for contacts held by insufficient confirmations.

Reads work/queue.snapshot.jsonl and reports:
1. Total contacts with email addresses
2. Contacts in each verification state
3. Contacts held for insufficient confirmations - broken down by what evidence exists
4. What Deliverable evidence looks like (or doesn't)
5. What ContactOut says about the held contacts
"""
import json
import sys
from collections import Counter, defaultdict

SNAPSHOT = "work/queue.snapshot.jsonl"


def load():
    records = []
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def evidence_of(contact):
    return list((contact.get("verification") or {}).get("evidence") or [])


def main():
    records = load()
    print(f"Records: {len(records)}")

    total_contacts = 0
    contacts_with_email = 0
    contacts_with_verification = 0
    state_counts = Counter()
    held_insufficient = []
    held_other = []
    deliverable_evidence = Counter()
    contactout_verdicts_for_held = Counter()
    evidence_patterns = Counter()

    for rec in records:
        for contact in rec.get("contacts") or []:
            total_contacts += 1
            if not contact.get("email"):
                continue
            contacts_with_email += 1

            v = contact.get("verification") or {}
            state = v.get("state")
            if state:
                contacts_with_verification += 1
                state_counts[state] += 1

            evidence = evidence_of(contact)
            if not evidence:
                continue

            by_provider = {}
            for entry in evidence:
                by_provider[entry["provider"]] = entry

            # Check for held + insufficient confirmations
            reason = v.get("reason", "")
            is_insufficient = v.get("insufficient_confirmations") or \
                "insufficient" in reason.lower() or \
                ("only" in reason.lower() and "confirmation" in reason.lower())

            if state == "held" and is_insufficient:
                held_insufficient.append((rec, contact, by_provider, reason))

                # What does ContactOut say?
                co = by_provider.get("contactout")
                if co:
                    contactout_verdicts_for_held[co.get("status", "none")] += 1
                else:
                    contactout_verdicts_for_held["no_contactout"] += 1

                # What does Deliverable say?
                dv = by_provider.get("deliverable")
                if dv:
                    deliverable_evidence[dv.get("status", "none")] += 1
                else:
                    deliverable_evidence["no_deliverable"] += 1

                # Evidence pattern
                providers_present = sorted(by_provider.keys())
                statuses = {p: e.get("status") for p, e in by_provider.items()}
                pattern = ", ".join(f"{p}={s}" for p, s in sorted(statuses.items()))
                evidence_patterns[pattern] += 1
            elif state == "held":
                held_other.append((rec, contact, by_provider, reason))

    print(f"Total contacts: {total_contacts}")
    print(f"Contacts with email: {contacts_with_email}")
    print(f"Contacts with verification block: {contacts_with_verification}")
    print(f"\nVerification state counts:")
    for state, count in state_counts.most_common():
        print(f"  {state}: {count}")

    print(f"\n=== HELD for insufficient confirmations: {len(held_insufficient)} ===")
    print(f"\nContactOut verdicts for held-insufficient contacts:")
    for verdict, count in contactout_verdicts_for_held.most_common():
        print(f"  {verdict}: {count}")

    print(f"\nDeliverable evidence for held-insufficient contacts:")
    for status, count in deliverable_evidence.most_common():
        print(f"  {status}: {count}")

    print(f"\nEvidence patterns (top 20):")
    for pattern, count in evidence_patterns.most_common(20):
        print(f"  [{count}] {pattern}")

    print(f"\n=== HELD for other reasons: {len(held_other)} ===")
    other_reasons = Counter()
    for rec, contact, by_provider, reason in held_other:
        other_reasons[reason[:100]] += 1
    for reason, count in other_reasons.most_common(10):
        print(f"  [{count}] {reason}")

    # Sample some held-insufficient contacts
    print(f"\n=== SAMPLE held-insufficient contacts (first 5) ===")
    for rec, contact, by_provider, reason in held_insufficient[:5]:
        email_hash = hash(contact.get("email", "")) % 10000
        print(f"\n  Record {rec['id']}, contact {contact.get('key')}, "
              f"email hash #{email_hash}")
        print(f"  Reason: {reason}")
        print(f"  Confirmation count: "
              f"{(contact.get('verification') or {}).get('confirmation_count')}")
        print(f"  Required: "
              f"{(contact.get('verification') or {}).get('required_confirmations')}")
        print(f"  Confirmed by: "
              f"{(contact.get('verification') or {}).get('confirmed_by')}")
        for provider, entry in sorted(by_provider.items()):
            print(f"  {provider}: status={entry.get('status')}, "
                  f"deliverable={entry.get('deliverable')}, "
                  f"safe_to_send={entry.get('safe_to_send')}, "
                  f"reason={(entry.get('reason') or '')[:80]}")


if __name__ == "__main__":
    main()
