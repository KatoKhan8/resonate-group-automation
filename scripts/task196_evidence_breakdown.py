"""TASK-196: Breakdown of the 81 contacts with verification evidence.

All 81 have Deliverable=error (ContractNotVerified).
What are their states, and what do ContactOut and Reoon say?
"""
import json
from collections import Counter

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

    # Contacts with evidence
    with_evidence = []
    for rec in records:
        for contact in rec.get("contacts") or []:
            if not contact.get("email"):
                continue
            evidence = evidence_of(contact)
            if evidence:
                by_provider = {}
                for entry in evidence:
                    by_provider[entry["provider"]] = entry
                v = contact.get("verification") or {}
                with_evidence.append((rec, contact, by_provider, v))

    print(f"Contacts with evidence: {len(with_evidence)}")

    # State breakdown
    state_counts = Counter()
    co_statuses = Counter()
    dv_statuses = Counter()
    re_statuses = Counter()

    # Detailed patterns
    patterns = Counter()

    # Confirmation counts
    confirmation_counts = Counter()

    for rec, contact, by_provider, v in with_evidence:
        state = v.get("state", "none")
        state_counts[state] += 1

        co = by_provider.get("contactout", {})
        dv = by_provider.get("deliverable", {})
        re = by_provider.get("reoon", {})

        co_s = co.get("status", "none")
        dv_s = dv.get("status", "none")
        re_s = re.get("status", "none")

        co_statuses[co_s] += 1
        dv_statuses[dv_s] += 1
        re_statuses[re_s] += 1

        pattern = f"co={co_s}, dv={dv_s}, re={re_s}"
        patterns[pattern] += 1

        cc = v.get("confirmation_count", 0)
        confirmation_counts[cc] += 1

    print(f"\nState breakdown:")
    for s, c in state_counts.most_common():
        print(f"  {s}: {c}")

    print(f"\nContactOut statuses:")
    for s, c in co_statuses.most_common():
        print(f"  {s}: {c}")

    print(f"\nDeliverable statuses:")
    for s, c in dv_statuses.most_common():
        print(f"  {s}: {c}")

    print(f"\nReoon statuses:")
    for s, c in re_statuses.most_common():
        print(f"  {s}: {c}")

    print(f"\nEvidence patterns:")
    for p, c in patterns.most_common():
        print(f"  [{c}] {p}")

    print(f"\nConfirmation counts:")
    for cc, count in sorted(confirmation_counts.items()):
        print(f"  {cc}: {count}")

    # What would change if Deliverable worked?
    print(f"\n=== WHAT IF DELIVERABLE WORKED? ===")
    print(f"Contacts where ContactOut=valid and Deliverable=error:")
    co_valid_dv_error = 0
    co_valid_dv_error_states = Counter()
    for rec, contact, by_provider, v in with_evidence:
        co = by_provider.get("contactout", {})
        dv = by_provider.get("deliverable", {})
        if co.get("status") == "valid" and dv.get("status") == "error":
            co_valid_dv_error += 1
            co_valid_dv_error_states[v.get("state", "none")] += 1
    print(f"  Count: {co_valid_dv_error}")
    print(f"  States: {dict(co_valid_dv_error_states)}")

    # Contacts where adding Deliverable=valid would change the state
    print(f"\nContacts that would benefit from a working Deliverable:")
    would_benefit = 0
    for rec, contact, by_provider, v in with_evidence:
        state = v.get("state", "none")
        cc = v.get("confirmation_count", 0)
        req = v.get("required_confirmations", 2)
        co = by_provider.get("contactout", {})
        if state in ("held", "unknown") and cc < req:
            if co.get("status") == "valid":
                would_benefit += 1
    print(f"  Count: {would_benefit}")

    # The 154 with no evidence at all
    no_evidence_count = 0
    for rec in records:
        for contact in rec.get("contacts") or []:
            if not contact.get("email"):
                continue
            evidence = evidence_of(contact)
            if not evidence:
                no_evidence_count += 1
    print(f"\nContacts with email but NO evidence: {no_evidence_count}")
    print(f"These were never put through the verification waterfall.")


if __name__ == "__main__":
    main()
