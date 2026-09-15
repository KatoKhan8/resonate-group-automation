#!/usr/bin/env python3
"""TASK-139: measure what the estate already knows about its contacts.

Reads the queue snapshot (read-only) and answers:
1. For each relationship state, how many contacts are in it and what proves it.
2. Which states are already computed in src/ and by whom.
3. Which states change a production decision today (named consumer).
4. LinkedIn connection state: what a local model adds over the provider branch.
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SNAPSHOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "work", "queue.snapshot.jsonl")

def load_records():
    recs = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            recs.append(json.loads(line))
    return recs

def measure():
    recs = load_records()
    print(f"=== SNAPSHOT: {len(recs)} records ===\n")

    # --- Collect all contacts and their relationship evidence ---
    all_contacts = []  # (rec, contact)
    for rec in recs:
        for contact in rec.get("contacts") or []:
            all_contacts.append((rec, contact))

    print(f"Total contacts across all records: {len(all_contacts)}\n")

    # --- STATE 1: previously emailed, no reply ---
    # Evidence: push_marked events on email channel, no reply event for that contact
    emailed_no_reply = 0
    emailed_no_reply_evidence = []
    for rec, contact in all_contacts:
        key = contact.get("key")
        has_email_send = False
        has_reply = False
        for e in rec.get("events") or []:
            if e.get("contact") != key:
                continue
            if e.get("type") == "push_marked" and e.get("channel") == "email":
                has_email_send = True
            if e.get("type") in ("reply_received", "reply_classified",
                                  "positive_reply_detected"):
                has_reply = True
        if has_email_send and not has_reply:
            emailed_no_reply += 1
            emailed_no_reply_evidence.append("push_marked(email)")
    print(f"1a. Previously emailed, no reply: {emailed_no_reply}")
    print(f"    Evidence field: events[type=push_marked, channel=email]")
    print(f"    No reply event for that contact\n")

    # --- STATE 1b: previously emailed, replied NEGATIVE ---
    emailed_replied_negative = 0
    for rec, contact in all_contacts:
        key = contact.get("key")
        has_email_send = False
        has_negative_reply = False
        for e in rec.get("events") or []:
            if e.get("contact") != key:
                continue
            if e.get("type") == "push_marked" and e.get("channel") == "email":
                has_email_send = True
            if e.get("type") == "reply_classified":
                cls = (e.get("classification") or "").lower()
                if cls in ("negative", "unsubscribed", "not_interested",
                           "remove", "removal"):
                    has_negative_reply = True
        if has_email_send and has_negative_reply:
            emailed_replied_negative += 1
    print(f"1b. Previously emailed, replied NEGATIVE: {emailed_replied_negative}")
    print(f"    Evidence: events[type=reply_classified, classification=negative*]")
    print()

    # --- STATE 1c: previously emailed, replied POSITIVE ---
    emailed_replied_positive = 0
    for rec, contact in all_contacts:
        key = contact.get("key")
        has_email_send = False
        has_positive_reply = False
        for e in rec.get("events") or []:
            if e.get("contact") != key:
                continue
            if e.get("type") == "push_marked" and e.get("channel") == "email":
                has_email_send = True
            if e.get("type") in ("positive_reply_detected",):
                has_positive_reply = True
            if e.get("type") == "reply_classified":
                cls = (e.get("classification") or "").lower()
                if cls in ("positive", "interested", "meeting_accepted"):
                    has_positive_reply = True
        if has_email_send and has_positive_reply:
            emailed_replied_positive += 1
    print(f"1c. Previously emailed, replied POSITIVE: {emailed_replied_positive}")
    print(f"    Evidence: events[type=positive_reply_detected | reply_classified=positive*]")
    print()

    # --- STATE 1d: previously emailed, reply UNKNOWN ---
    emailed_reply_unknown = 0
    for rec, contact in all_contacts:
        key = contact.get("key")
        has_email_send = False
        has_reply = False
        has_classified_reply = False
        for e in rec.get("events") or []:
            if e.get("contact") != key:
                continue
            if e.get("type") == "push_marked" and e.get("channel") == "email":
                has_email_send = True
            if e.get("type") in ("reply_received", "reply_classified",
                                  "positive_reply_detected"):
                has_reply = True
            if e.get("type") in ("reply_classified", "positive_reply_detected"):
                has_classified_reply = True
        if has_email_send and has_reply and not has_classified_reply:
            emailed_reply_unknown += 1
    print(f"1d. Previously emailed, reply UNKNOWN (received but unclassified): {emailed_reply_unknown}")
    print(f"    Evidence: reply_received without reply_classified")
    print()

    # --- STATE 2: already a LinkedIn connection ---
    li_connected = 0
    for rec, contact in all_contacts:
        key = contact.get("key")
        for e in rec.get("events") or []:
            if e.get("contact") != key:
                continue
            if e.get("type") in ("linkedin_connected", "connection_accepted"):
                li_connected += 1
                break
    print(f"2. Already a LinkedIn connection: {li_connected}")
    print(f"    Evidence: events[type=linkedin_connected|connection_accepted]")
    print()

    # --- STATE 3: previous LinkedIn outreach, no reply ---
    li_outreach_no_reply = 0
    for rec, contact in all_contacts:
        key = contact.get("key")
        has_li_send = False
        has_reply = False
        for e in rec.get("events") or []:
            if e.get("contact") != key:
                continue
            if e.get("type") == "push_marked" and e.get("channel") == "linkedin":
                has_li_send = True
            if e.get("type") in ("reply_received", "reply_classified",
                                  "positive_reply_detected"):
                has_reply = True
        if has_li_send and not has_reply:
            li_outreach_no_reply += 1
    print(f"3. Previous LinkedIn outreach, no reply: {li_outreach_no_reply}")
    print(f"    Evidence: events[type=push_marked, channel=linkedin] without reply")
    print()

    # --- STATE 4: suppressed / DNC ---
    suppressed_count = 0
    agency_dnc = 0
    unsubscribed = 0
    stopped = 0
    for rec, contact in all_contacts:
        key = contact.get("key")
        domain = (rec.get("domain") or "").lower()
        drop = (rec.get("drop_reason") or "")
        if drop.startswith("suppress") or rec.get("state") == "dropped":
            suppressed_count += 1
        if contact.get("unsubscribed") or contact.get("suppressed"):
            unsubscribed += 1
        if contact.get("stopped"):
            stopped += 1
    print(f"4. Suppressed / DNC:")
    print(f"   4a. Record-level suppression (domain on suppress list or dropped): {suppressed_count}")
    print(f"       Evidence: rec.drop_reason starts with 'suppress' or rec.state='dropped'")
    print(f"   4b. Contact unsubscribed/suppressed: {unsubscribed}")
    print(f"       Evidence: contact.unsubscribed or contact.suppressed")
    print(f"   4c. Contact stopped: {stopped}")
    print(f"       Evidence: contact.stopped")
    print(f"   4d. Agency DNC (src/agencydnc.py): CANNOT MEASURE WITHOUT CALLING lookup()")
    print(f"       Evidence needed: agencydnc.lookup(contact) - hash-based, no provider call")
    print()

    # --- STATE 5: nobody has ever contacted them ---
    never_contacted = 0
    for rec, contact in all_contacts:
        key = contact.get("key")
        has_any_send = False
        for e in rec.get("events") or []:
            if e.get("contact") != key:
                continue
            if e.get("type") == "push_marked":
                has_any_send = True
                break
        if not has_any_send:
            never_contacted += 1
    print(f"5. Nobody has ever contacted them: {never_contacted}")
    print(f"    Evidence: ABSENCE of events[type=push_marked] for this contact")
    print(f"    NOTE: absence of evidence is not evidence of absence - the snapshot")
    print(f"    may not carry events for contacts not yet in a campaign")
    print()

    # --- STATE 6: bison_lead_id (the one bit that reaches production) ---
    has_bison = 0
    for rec, contact in all_contacts:
        if contact.get("bison_lead_id"):
            has_bison += 1
    print(f"6. Has bison_lead_id (prior EmailBison outreach): {has_bison}")
    print(f"    Evidence: contact.bison_lead_id (integer)")
    print(f"    Consumer: scripts/build_control_cohort.py eligible_contacts()")
    print(f"    skips these as 'prior EmailBison outreach; not a cold prospect'")
    print()

    # --- Cross-tabulation ---
    print("=== CROSS-TABULATION ===\n")
    # How many contacts have bison_lead_id AND also have push_marked events?
    bison_with_sends = 0
    bison_without_sends = 0
    for rec, contact in all_contacts:
        if not contact.get("bison_lead_id"):
            continue
        key = contact.get("key")
        has_send = any(e.get("type") == "push_marked" and e.get("contact") == key
                       for e in rec.get("events") or [])
        if has_send:
            bison_with_sends += 1
        else:
            bison_without_sends += 1
    print(f"bison_lead_id holders:")
    print(f"  with push_marked sends: {bison_with_sends}")
    print(f"  without push_marked sends: {bison_without_sends}")
    print(f"  (bison_lead_id may mean they were emailed in EmailBison but")
    print(f"   the send event was not recorded in this estate's event log)")
    print()

    # --- Event type breakdown for all contacts ---
    print("=== EVENT TYPES ACROSS ALL CONTACTS ===\n")
    push_by_channel = Counter()
    reply_events = Counter()
    li_events = Counter()
    for rec, contact in all_contacts:
        key = contact.get("key")
        for e in rec.get("events") or []:
            if e.get("contact") != key:
                continue
            t = e.get("type")
            if t == "push_marked":
                push_by_channel[e.get("channel", "unknown")] += 1
            if t in ("reply_received", "reply_classified", "positive_reply_detected"):
                reply_events[t] += 1
            if t in ("linkedin_connected", "connection_accepted"):
                li_events[t] += 1
    print(f"push_marked by channel: {dict(push_by_channel)}")
    print(f"reply events: {dict(reply_events)}")
    print(f"LinkedIn connection events: {dict(li_events)}")
    print()

    # --- Records with no contacts at all ---
    no_contacts = sum(1 for rec in recs if not rec.get("contacts"))
    print(f"Records with no contacts: {no_contacts} of {len(recs)}")
    print()

    # --- Contact verdicts ---
    verdicts = Counter()
    for rec, contact in all_contacts:
        verdicts[contact.get("verdict") or "NONE"] += 1
    print(f"Contact verdicts: {dict(verdicts)}")
    print()

    # --- Sendable contacts ---
    sendable = sum(1 for _, c in all_contacts if c.get("sendable"))
    print(f"Contacts with sendable=True: {sendable}")
    print()

    # --- Records by state ---
    rec_states = Counter()
    for rec in recs:
        rec_states[rec.get("state") or "NONE"] += 1
    print(f"Record states: {dict(rec_states)}")
    print()

    # --- Check what reply classifications exist ---
    print("=== REPLY CLASSIFICATIONS IN ESTATE ===\n")
    classifications = Counter()
    for rec in recs:
        for e in rec.get("events") or []:
            if e.get("type") == "reply_classified":
                classifications[e.get("classification") or "NONE"] += 1
    print(f"reply_classified classifications: {dict(classifications)}")
    print()

    # --- Check what the 29 bison_lead_id contacts look like ---
    print("=== BISON_LEAD_ID CONTACTS DETAIL ===\n")
    for rec, contact in all_contacts:
        if not contact.get("bison_lead_id"):
            continue
        key = contact.get("key")
        sends = [e for e in rec.get("events") or []
                 if e.get("type") == "push_marked" and e.get("contact") == key]
        replies = [e for e in rec.get("events") or []
                   if e.get("type") in ("reply_received", "reply_classified",
                                         "positive_reply_detected")
                   and e.get("contact") == key]
        print(f"  {rec.get('id')}/{key}: bison_lead_id={contact['bison_lead_id']}, "
              f"sends={len(sends)}, replies={len(replies)}, "
              f"email={contact.get('email', 'NONE')[:30]}")
    print()

if __name__ == "__main__":
    measure()
