"""TASK-196: Deep analysis of the verification gap.

TASK-194 found 207 contacts enriched but never verified:
  143  held by "insufficient confirmations" - ContactOut says VALID,
       Deliverable returns errors nobody can parse
   15  MX-blocked
   11  catch-all uncleared
   37  no email address

This script analyses the queue snapshot to understand the real shape.
"""
import json
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
    state_counts = Counter()

    # Breakdown of unknown-state contacts
    unknown_contacts = []
    verified_contacts = []

    # For all contacts with email, what evidence do they have?
    provider_presence = Counter()  # which providers have evidence
    contactout_status_for_unknown = Counter()
    deliverable_status_for_unknown = Counter()
    reoon_status_for_unknown = Counter()

    # The key question: ContactOut=valid but no Deliverable confirmation
    co_valid_no_dv = []
    co_valid_dv_error = []
    co_valid_dv_valid = []
    co_valid_dv_unknown = []
    no_co_no_dv = []

    for rec in records:
        for contact in rec.get("contacts") or []:
            total_contacts += 1
            if not contact.get("email"):
                continue
            contacts_with_email += 1

            v = contact.get("verification") or {}
            state = v.get("state", "none")
            state_counts[state] += 1

            evidence = evidence_of(contact)
            by_provider = {}
            for entry in evidence:
                by_provider[entry["provider"]] = entry

            # Track which providers have evidence
            providers_present = sorted(by_provider.keys())
            provider_presence[tuple(providers_present)] += 1

            co = by_provider.get("contactout")
            dv = by_provider.get("deliverable")
            re = by_provider.get("reoon")

            if state == "unknown":
                unknown_contacts.append((rec, contact, by_provider, v))
                if co:
                    contactout_status_for_unknown[co.get("status", "none")] += 1
                else:
                    contactout_status_for_unknown["no_contactout_evidence"] += 1
                if dv:
                    deliverable_status_for_unknown[dv.get("status", "none")] += 1
                else:
                    deliverable_status_for_unknown["no_deliverable_evidence"] += 1
                if re:
                    reoon_status_for_unknown[re.get("status", "none")] += 1
                else:
                    reoon_status_for_unknown["no_reoon_evidence"] += 1

                # Key breakdown
                co_status = co.get("status") if co else None
                dv_status = dv.get("status") if dv else None

                if co_status == "valid":
                    if dv is None:
                        co_valid_no_dv.append((rec, contact, by_provider))
                    elif dv_status == "error":
                        co_valid_dv_error.append((rec, contact, by_provider))
                    elif dv_status == "valid":
                        co_valid_dv_valid.append((rec, contact, by_provider))
                    else:
                        co_valid_dv_unknown.append((rec, contact, by_provider))
                elif co is None and dv is None:
                    no_co_no_dv.append((rec, contact, by_provider))

            elif state == "verified":
                verified_contacts.append((rec, contact, by_provider, v))

    print(f"\nTotal contacts: {total_contacts}")
    print(f"Contacts with email: {contacts_with_email}")
    print(f"\nVerification state counts:")
    for state, count in state_counts.most_common():
        print(f"  {state}: {count}")

    print(f"\n=== UNKNOWN STATE: {len(unknown_contacts)} contacts ===")
    print(f"\nContactOut status for unknown contacts:")
    for s, c in contactout_status_for_unknown.most_common():
        print(f"  {s}: {c}")
    print(f"\nDeliverable status for unknown contacts:")
    for s, c in deliverable_status_for_unknown.most_common():
        print(f"  {s}: {c}")
    print(f"\nReoon status for unknown contacts:")
    for s, c in reoon_status_for_unknown.most_common():
        print(f"  {s}: {c}")

    print(f"\n=== KEY BREAKDOWN of unknown contacts ===")
    print(f"ContactOut=valid, NO Deliverable evidence: {len(co_valid_no_dv)}")
    print(f"ContactOut=valid, Deliverable=error:       {len(co_valid_dv_error)}")
    print(f"ContactOut=valid, Deliverable=valid:       {len(co_valid_dv_valid)}")
    print(f"ContactOut=valid, Deliverable=other:       {len(co_valid_dv_unknown)}")
    print(f"No ContactOut, No Deliverable:             {len(no_co_no_dv)}")

    print(f"\n=== Provider presence patterns (all contacts) ===")
    for pattern, count in provider_presence.most_common(15):
        print(f"  [{count}] {', '.join(pattern) if pattern else '(none)'}")

    # Look at Deliverable error reasons
    print(f"\n=== Deliverable error reasons (all contacts) ===")
    dv_error_reasons = Counter()
    dv_all_statuses = Counter()
    for rec in records:
        for contact in rec.get("contacts") or []:
            for entry in evidence_of(contact):
                if entry.get("provider") == "deliverable":
                    dv_all_statuses[entry.get("status", "none")] += 1
                    if entry.get("status") == "error":
                        reason = (entry.get("reason") or "")[:120]
                        dv_error_reasons[reason] += 1
    print(f"All Deliverable statuses:")
    for s, c in dv_all_statuses.most_common():
        print(f"  {s}: {c}")
    print(f"\nDeliverable error reasons:")
    for reason, count in dv_error_reasons.most_common():
        print(f"  [{count}] {reason}")

    # Sample some CO=valid, no DV contacts
    print(f"\n=== SAMPLE: ContactOut=valid, NO Deliverable evidence (first 5) ===")
    for rec, contact, by_provider in co_valid_no_dv[:5]:
        email_hash = hash(contact.get("email", "")) % 10000
        v = contact.get("verification") or {}
        print(f"\n  Record {rec['id']}, contact {contact.get('key')}, "
              f"email hash #{email_hash}")
        print(f"  State: {v.get('state')}, Reason: {(v.get('reason') or '')[:120]}")
        print(f"  Confirmations: {v.get('confirmation_count')}/{v.get('required_confirmations')}")
        for p, entry in sorted(by_provider.items()):
            print(f"  {p}: status={entry.get('status')}, "
                  f"charged={entry.get('charged')}, "
                  f"reason={(entry.get('reason') or '')[:80]}")

    # Sample some CO=valid, DV=error contacts
    print(f"\n=== SAMPLE: ContactOut=valid, Deliverable=error (first 5) ===")
    for rec, contact, by_provider in co_valid_dv_error[:5]:
        email_hash = hash(contact.get("email", "")) % 10000
        v = contact.get("verification") or {}
        print(f"\n  Record {rec['id']}, contact {contact.get('key')}, "
              f"email hash #{email_hash}")
        print(f"  State: {v.get('state')}, Reason: {(v.get('reason') or '')[:120]}")
        print(f"  Confirmations: {v.get('confirmation_count')}/{v.get('required_confirmations')}")
        for p, entry in sorted(by_provider.items()):
            print(f"  {p}: status={entry.get('status')}, "
                  f"charged={entry.get('charged')}, "
                  f"reason={(entry.get('reason') or '')[:80]}")


if __name__ == "__main__":
    main()
