#!/usr/bin/env python3
"""TASK-139: Measure relationship states in the estate snapshot.

Reads work/queue.snapshot.jsonl (read-only) and reports:
1. How many contacts are in each relationship state, with the evidence field
2. Which states are computed somewhere in src/
3. Which states change a decision today (traced to a named caller)
4. LinkedIn connection state specifically
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SNAPSHOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "work", "queue.snapshot.jsonl")


def load_records():
    records = []
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def all_contacts(records):
    """Yield (rec, contact) pairs for every contact on every record."""
    for rec in records:
        for contact in rec.get("contacts") or []:
            yield rec, contact


def has_bison_lead_id(contact):
    return bool(contact.get("bison_lead_id"))


def has_reply_event(rec, contact_key):
    """Check if this contact has a REPLY_RECEIVED event."""
    for entry in rec.get("events") or []:
        if entry.get("step") == "reply_received" or entry.get("type") == "reply_received":
            if entry.get("contact") == contact_key:
                return True
    return False


def get_reply_events(rec, contact_key):
    """Get all reply events for a contact."""
    results = []
    for entry in rec.get("events") or []:
        if entry.get("type") == "reply_received" and entry.get("contact") == contact_key:
            results.append(entry)
    return results


def has_linkedin_connected(rec, contact_key):
    """Check if this contact has a linkedin_connected event."""
    for entry in rec.get("events") or []:
        if entry.get("type") == "linkedin_connected" and entry.get("contact") == contact_key:
            return True
    return False


def has_linkedin_acceptance(rec, contact_key):
    """Check for connection_accepted events."""
    for entry in rec.get("events") or []:
        if entry.get("type") == "connection_accepted" and entry.get("contact") == contact_key:
            return True
    return False


def is_suppressed_contact(contact):
    return bool(contact.get("suppressed") or contact.get("unsubscribed"))


def is_stopped_contact(contact):
    return bool(contact.get("stopped"))


def has_push_marked(rec, contact_key):
    """Has a push_marked event (handed to provider)."""
    for entry in rec.get("events") or []:
        if entry.get("type") == "push_marked" and entry.get("contact") == contact_key:
            return True
    return False


def has_email_delivered(rec, contact_key):
    """Has an email_delivered event."""
    for entry in rec.get("events") or []:
        if entry.get("type") == "email_delivered" and entry.get("contact") == contact_key:
            return True
    return False


def has_any_confirmed_touch(rec, contact_key):
    """Has push_marked, email_delivered, or linkedin_connected."""
    return (has_push_marked(rec, contact_key) or
            has_email_delivered(rec, contact_key) or
            has_linkedin_connected(rec, contact_key))


def get_event_types(rec, contact_key):
    """Get all event types for this contact."""
    types = []
    for entry in rec.get("events") or []:
        if entry.get("contact") == contact_key:
            types.append(entry.get("type") or entry.get("step"))
    return types


def get_reply_classification(rec, contact_key):
    """Look for reply classification in events."""
    for entry in rec.get("events") or []:
        if (entry.get("type") == "reply_classified" and
                entry.get("contact") == contact_key):
            return entry.get("classification") or entry.get("category")
    return None


def check_record_suppression(rec):
    """Check if the record itself is suppressed."""
    supp = rec.get("suppression") or {}
    return bool(supp.get("unsubscribed") or supp.get("suppressed"))


def check_drop_reason(rec):
    """Check if the record was dropped for suppression."""
    dr = rec.get("drop_reason") or ""
    return dr.startswith("suppress")


def has_linkedin_note_events(rec, contact_key):
    """Check if LinkedIn note events exist for this contact."""
    for entry in rec.get("events") or []:
        step = entry.get("step") or entry.get("type")
        if step == "linkedin_note" and entry.get("contact") == contact_key:
            return True
    return False


def has_approved_steps(rec, contact_key):
    """Check if any steps are approved for this contact."""
    for entry in rec.get("events") or []:
        if entry.get("step") == "approved" and entry.get("contact") == contact_key:
            return True
    return False


def main():
    records = load_records()
    print(f"=== TASK-139 MEASUREMENT ===")
    print(f"Snapshot: {SNAPSHOT}")
    stamp_file = os.path.join(os.path.dirname(SNAPSHOT), "queue.snapshot.STAMP")
    if os.path.exists(stamp_file):
        with open(stamp_file) as f:
            print(f"Stamp: {f.read().strip()}")
    print(f"Records: {len(records)}")

    total_contacts = 0
    excluded_contacts = 0
    contacts_with_bison = 0
    contacts_with_reply = 0
    contacts_with_positive_reply = 0
    contacts_with_negative_reply = 0
    contacts_with_unknown_reply = 0
    contacts_with_neutral_reply = 0
    contacts_with_unsubscribe_reply = 0
    contacts_linkedin_connected = 0
    contacts_linkedin_acceptance = 0
    contacts_suppressed = 0
    contacts_stopped = 0
    contacts_with_push_marked = 0
    contacts_with_email_delivered = 0
    contacts_with_any_touch = 0
    contacts_no_history = 0
    contacts_with_linkedin_notes = 0
    contacts_with_approved = 0
    contacts_record_suppressed = 0
    contacts_record_dropped_suppress = 0

    reply_classifications = {}
    event_type_counts = {}

    # Per-contact state classification
    states = {
        "bison_lead_id": [],
        "reply_no_classification": [],
        "reply_positive": [],
        "reply_negative": [],
        "reply_neutral": [],
        "reply_unsubscribe": [],
        "reply_unknown": [],
        "linkedin_connected": [],
        "suppressed_contact": [],
        "stopped_contact": [],
        "record_suppressed": [],
        "no_history": [],
        "has_confirmed_touch_no_reply": [],
    }

    for rec in records:
        # Check record-level suppression
        if check_record_suppression(rec):
            contacts_record_suppressed += 1
        if check_drop_reason(rec):
            contacts_record_dropped_suppress += 1

        # Count excluded contacts too
        for exc in rec.get("excluded") or []:
            excluded_contacts += 1

        for contact in rec.get("contacts") or []:
            total_contacts += 1
            key = contact.get("key")
            rec_id = rec.get("id")
            label = f"{rec_id}/{key}"

            # Track event types
            etypes = get_event_types(rec, key)
            for et in etypes:
                event_type_counts[et] = event_type_counts.get(et, 0) + 1

            # 1. bison_lead_id
            if has_bison_lead_id(contact):
                contacts_with_bison += 1
                states["bison_lead_id"].append(label)

            # 2. Reply events
            reply_events = get_reply_events(rec, key)
            if reply_events:
                contacts_with_reply += 1
                classification = get_reply_classification(rec, key)
                if classification:
                    reply_classifications[classification] = reply_classifications.get(classification, 0) + 1
                    if classification == "positive":
                        contacts_with_positive_reply += 1
                        states["reply_positive"].append(label)
                    elif classification == "negative":
                        contacts_with_negative_reply += 1
                        states["reply_negative"].append(label)
                    elif classification == "neutral":
                        contacts_with_neutral_reply += 1
                        states["reply_neutral"].append(label)
                    elif classification in ("unsubscribe", "account_do_not_contact"):
                        contacts_with_unsubscribe_reply += 1
                        states["reply_unsubscribe"].append(label)
                    else:
                        contacts_with_unknown_reply += 1
                        states["reply_unknown"].append(label)
                else:
                    states["reply_no_classification"].append(label)

            # 3. LinkedIn connection
            if has_linkedin_connected(rec, key):
                contacts_linkedin_connected += 1
                states["linkedin_connected"].append(label)
            if has_linkedin_acceptance(rec, key):
                contacts_linkedin_acceptance += 1

            # 4. Suppression
            if is_suppressed_contact(contact):
                contacts_suppressed += 1
                states["suppressed_contact"].append(label)
            if is_stopped_contact(contact):
                contacts_stopped += 1
                states["stopped_contact"].append(label)

            # 5. Confirmed touches
            if has_push_marked(rec, key):
                contacts_with_push_marked += 1
            if has_email_delivered(rec, key):
                contacts_with_email_delivered += 1
            if has_any_confirmed_touch(rec, key):
                contacts_with_any_touch += 1
                if not reply_events:
                    states["has_confirmed_touch_no_reply"].append(label)

            # 6. LinkedIn notes
            if has_linkedin_note_events(rec, key):
                contacts_with_linkedin_notes += 1

            # 7. Approved steps
            if has_approved_steps(rec, key):
                contacts_with_approved += 1

            # 8. No history at all (no events for this contact)
            if not etypes:
                contacts_no_history += 1
                states["no_history"].append(label)

    print(f"\n=== CONTACT COUNTS (primary contacts only) ===")
    print(f"Total contacts (on active records): {total_contacts}")
    print(f"Excluded contacts: {excluded_contacts}")
    print()

    print(f"--- STATE: bison_lead_id present ---")
    print(f"Count: {contacts_with_bison}")
    print(f"Field: contact['bison_lead_id']")
    print(f"Examples: {states['bison_lead_id'][:5]}")
    print()

    print(f"--- STATE: reply received (any) ---")
    print(f"Count: {contacts_with_reply}")
    print(f"  Positive: {contacts_with_positive_reply}")
    print(f"  Negative: {contacts_with_negative_reply}")
    print(f"  Neutral:  {contacts_with_neutral_reply}")
    print(f"  Unsubscribe/DNC: {contacts_with_unsubscribe_reply}")
    print(f"  Unknown/other: {contacts_with_unknown_reply}")
    print(f"  No classification event: {len(states['reply_no_classification'])}")
    print(f"Field: events with type='reply_received'")
    print()

    print(f"--- Reply classifications found ---")
    for k, v in sorted(reply_classifications.items()):
        print(f"  {k}: {v}")
    print()

    print(f"--- STATE: LinkedIn connected ---")
    print(f"Count (linkedin_connected event): {contacts_linkedin_connected}")
    print(f"Count (connection_accepted event): {contacts_linkedin_acceptance}")
    print(f"Field: events with type='linkedin_connected' or 'connection_accepted'")
    print()

    print(f"--- STATE: Contact suppressed/unsubscribed ---")
    print(f"Count (contact-level): {contacts_suppressed}")
    print(f"Count (contact stopped): {contacts_stopped}")
    print(f"Count (record-level suppressed): {contacts_record_suppressed}")
    print(f"Count (record dropped/suppress): {contacts_record_dropped_suppress}")
    print(f"Field: contact['suppressed'], contact['unsubscribed'], contact['stopped']")
    print(f"       rec['suppression']['unsubscribed'], rec['drop_reason']")
    print()

    print(f"--- STATE: Confirmed touches ---")
    print(f"push_marked: {contacts_with_push_marked}")
    print(f"email_delivered: {contacts_with_email_delivered}")
    print(f"any confirmed touch: {contacts_with_any_touch}")
    print(f"confirmed touch, no reply: {len(states['has_confirmed_touch_no_reply'])}")
    print(f"Field: events with type in (push_marked, email_delivered, linkedin_connected)")
    print()

    print(f"--- STATE: LinkedIn notes sent ---")
    print(f"Count: {contacts_with_linkedin_notes}")
    print()

    print(f"--- STATE: Approved steps ---")
    print(f"Count: {contacts_with_approved}")
    print()

    print(f"--- STATE: No event history at all ---")
    print(f"Count: {contacts_no_history}")
    print(f"Examples: {states['no_history'][:5]}")
    print()

    print(f"=== EVENT TYPE DISTRIBUTION (across all contacts) ===")
    for et, count in sorted(event_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {et}: {count}")
    print()

    # Now check what the snapshot contacts look like in terms of fields
    print(f"=== SAMPLE CONTACT FIELDS ===")
    for rec in records[:1]:
        for contact in rec.get("contacts") or []:
            print(f"Contact: {contact.get('key')}")
            print(f"  Fields: {list(contact.keys())}")
            print(f"  bison_lead_id: {contact.get('bison_lead_id')}")
            print(f"  suppressed: {contact.get('suppressed')}")
            print(f"  unsubscribed: {contact.get('unsubscribed')}")
            print(f"  stopped: {contact.get('stopped')}")
            print(f"  paused: {contact.get('paused')}")
            break

    # Check for linkedin_state or connection_state on contacts
    print(f"\n=== LINKEDIN STATE FIELDS ON CONTACTS ===")
    li_state_fields = set()
    for rec in records:
        for contact in rec.get("contacts") or []:
            for k in contact.keys():
                if "linkedin" in k.lower() or "connection" in k.lower():
                    li_state_fields.add(k)
    print(f"LinkedIn/connection-related fields found on contacts: {li_state_fields}")

    # Check for reply classification in contact objects
    print(f"\n=== REPLY-RELATED FIELDS ON CONTACTS ===")
    reply_fields = set()
    for rec in records:
        for contact in rec.get("contacts") or []:
            for k in contact.keys():
                if "reply" in k.lower() or "sentiment" in k.lower() or "classification" in k.lower():
                    reply_fields.add(k)
    print(f"Reply-related fields found on contacts: {reply_fields}")

    # Check what events exist per contact that has bison_lead_id
    print(f"\n=== BOISON_LEAD_ID CONTACTS: EVENT PROFILES ===")
    for rec in records:
        for contact in rec.get("contacts") or []:
            if has_bison_lead_id(contact):
                key = contact.get("key")
                etypes = get_event_types(rec, key)
                rec_id = rec.get("id")
                unique_types = sorted(set(etypes))
                print(f"  {rec_id}/{key}: bison_lead_id={contact['bison_lead_id']}, events={unique_types}")


if __name__ == "__main__":
    main()
