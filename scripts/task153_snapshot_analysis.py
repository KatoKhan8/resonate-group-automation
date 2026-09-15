#!/usr/bin/env python3
"""TASK-153: Snapshot analysis of the historical estate.

Reads work/queue.snapshot.jsonl (550 records) and reports:
1. Every contact carrying a bison_lead_id - confirm the 29 count at 550
2. Prior reply inventory from events and log
3. Cold/warm/never split with evidence fields
4. LinkedIn conversation history indicators in canonical state

No provider calls. No writes.
"""
import json
import os
import sys
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SNAPSHOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "work", "queue.snapshot.jsonl")
STAMP_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "work", "queue.snapshot.STAMP")


def load_stamp():
    if os.path.exists(STAMP_FILE):
        with open(STAMP_FILE, encoding="utf-8") as f:
            return f.read().strip()
    return "unknown"


def load_records():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def hash_id(rec_id, contact_key):
    """Hash a prospect identifier for the document."""
    raw = f"{rec_id}/{contact_key}"
    return "h:" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def hash_domain(domain):
    return "h:" + hashlib.sha256(domain.encode()).hexdigest()[:12]


def contact_verified(contact):
    v = contact.get("verification") or {}
    return v.get("state") == "verified"


def get_all_contacts(records):
    """Yield (rec, contact) for every contact on non-dropped records."""
    for rec in records:
        if rec.get("state") == "dropped" or rec.get("drop_reason"):
            continue
        for contact in rec.get("contacts") or []:
            yield rec, contact


def get_reply_events(rec, contact_key):
    results = []
    for entry in rec.get("events") or []:
        if entry.get("type") == "reply_received" and entry.get("contact") == contact_key:
            results.append(entry)
    return results


def get_push_events(rec, contact_key):
    results = []
    for entry in rec.get("events") or []:
        if entry.get("type") == "push_marked" and entry.get("contact") == contact_key:
            results.append(entry)
    return results


def has_linkedin_note_in_log(rec, contact_key=None):
    """Check log array for linkedin_note entries."""
    count = 0
    for entry in rec.get("log") or []:
        if entry.get("step") == "linkedin_note":
            count += 1
    return count


def check_reply_in_log(rec):
    """Check if the log has any reply evidence."""
    for entry in rec.get("log") or []:
        step = (entry.get("step") or "").lower()
        note = (entry.get("note") or "").lower()
        if "reply" in step or "replied" in note:
            return True
    return False


def get_log_reply_details(rec):
    """Get details of reply entries in the log."""
    results = []
    for entry in rec.get("log") or []:
        step = (entry.get("step") or "").lower()
        note = (entry.get("note") or "").lower()
        if "reply" in step or "replied" in note:
            results.append({
                "step": entry.get("step"),
                "note": (entry.get("note") or "")[:120],
                "at": entry.get("at"),
            })
    return results


def is_suppressed(rec, contact):
    """Check all suppression signals."""
    if contact.get("suppressed") or contact.get("unsubscribed"):
        return True
    if contact.get("stopped"):
        return True
    supp = rec.get("suppression") or {}
    if supp.get("unsubscribed") or supp.get("suppressed"):
        return True
    dr = rec.get("drop_reason") or ""
    if dr.startswith("suppress"):
        return True
    return False


def is_paused(rec, contact):
    """Check if the account or contact is paused."""
    if contact.get("paused"):
        return True
    if (rec.get("cadence") or {}).get("paused"):
        return True
    return False


def main():
    records = load_records()
    stamp = load_stamp()

    print(f"=== TASK-153 SNAPSHOT ANALYSIS ===")
    print(f"Snapshot stamp: {stamp}")
    print(f"Total records: {len(records)}")
    print()

    # --- Partition records ---
    active_records = [r for r in records
                      if r.get("state") != "dropped" and not r.get("drop_reason")]
    dropped_records = [r for r in records
                       if r.get("state") == "dropped" or r.get("drop_reason")]

    print(f"Active records: {len(active_records)}")
    print(f"Dropped records: {len(dropped_records)}")
    print()

    # --- Collect all contacts ---
    all_contacts = list(get_all_contacts(records))
    print(f"Total contacts (on active records): {len(all_contacts)}")

    # --- 1. bison_lead_id contacts ---
    bison_contacts = [(rec, c) for rec, c in all_contacts if c.get("bison_lead_id")]
    non_bison_contacts = [(rec, c) for rec, c in all_contacts if not c.get("bison_lead_id")]

    print(f"\n{'='*60}")
    print(f"1. BOISON_LEAD_ID CONTACTS")
    print(f"{'='*60}")
    print(f"Total with bison_lead_id: {len(bison_contacts)}")
    print(f"Total without bison_lead_id: {len(non_bison_contacts)}")

    # Verified email breakdown
    bison_verified = [(r, c) for r, c in bison_contacts if contact_verified(c)]
    bison_unverified = [(r, c) for r, c in bison_contacts if not contact_verified(c)]
    print(f"  Verified email: {len(bison_verified)}")
    print(f"  Unverified email: {len(bison_unverified)}")

    print(f"\nAll bison_lead_id contacts:")
    for rec, c in bison_contacts:
        hid = hash_id(rec.get("id"), c.get("key"))
        domain = hash_domain(rec.get("domain", ""))
        lead_id = c.get("bison_lead_id")
        verified = contact_verified(c)
        print(f"  {hid} | lead={lead_id} | domain={domain} | "
              f"verified={verified} | email={c.get('email', 'N/A')[:5]}...")

    # --- 2. Reply inventory ---
    print(f"\n{'='*60}")
    print(f"2. PRIOR REPLY INVENTORY")
    print(f"{'='*60}")

    # From events array
    contacts_with_reply_events = 0
    reply_classifications = {}
    for rec, c in all_contacts:
        replies = get_reply_events(rec, c.get("key"))
        if replies:
            contacts_with_reply_events += 1
            for r in replies:
                cls = r.get("classification") or r.get("category") or "unknown"
                reply_classifications[cls] = reply_classifications.get(cls, 0) + 1

    print(f"Contacts with reply_received events: {contacts_with_reply_events}")
    print(f"Reply classifications: {reply_classifications}")

    # From log array - look for reply evidence
    records_with_log_reply = 0
    log_reply_details = {}
    for rec in active_records:
        details = get_log_reply_details(rec)
        if details:
            records_with_log_reply += 1
            hid = hash_id(rec.get("id"), "record")
            log_reply_details[hid] = details

    print(f"Records with reply evidence in log: {records_with_log_reply}")
    for hid, details in list(log_reply_details.items())[:10]:
        for d in details:
            print(f"  {hid}: step={d['step']} note={d['note'][:80]}")

    # Check events array for ALL event types
    event_type_counts = {}
    for rec, c in all_contacts:
        for entry in rec.get("events") or []:
            if entry.get("contact") == c.get("key"):
                et = entry.get("type") or entry.get("step")
                event_type_counts[et] = event_type_counts.get(et, 0) + 1

    print(f"\nEvent type distribution across all contacts:")
    for et, count in sorted(event_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {et}: {count}")

    # --- 3. Suppression / must-not-contact ---
    print(f"\n{'='*60}")
    print(f"3. SUPPRESSION / MUST-NOT-CONTACT")
    print(f"{'='*60}")

    suppressed_contacts = [(r, c) for r, c in all_contacts if is_suppressed(r, c)]
    paused_contacts = [(r, c) for r, c in all_contacts if is_paused(r, c)]
    print(f"Suppressed contacts: {len(suppressed_contacts)}")
    print(f"Paused contacts: {len(paused_contacts)}")

    # Check agency DNC
    dnc_count = 0
    try:
        from src import agencydnc
        agency_index = agencydnc.build_index()
        for rec, c in all_contacts:
            if agencydnc.lookup(c, index=agency_index):
                dnc_count += 1
    except Exception as e:
        print(f"Agency DNC check error: {e}")
    print(f"Agency DNC matches: {dnc_count}")

    # --- 4. Cold/warm/never split ---
    print(f"\n{'='*60}")
    print(f"4. COLD / WARM / NEVER SPLIT")
    print(f"{'='*60}")

    cold = []          # no history at all, no bison_lead_id
    warm_bison = []    # bison_lead_id but never emailed (effectively cold)
    warm_emailed = []  # bison_lead_id and actually emailed
    warm_reply = []    # has reply evidence
    warm_linkedin = [] # has LinkedIn conversation in log
    never = []         # truly nobody home

    for rec, c in all_contacts:
        key = c.get("key")
        has_bison = bool(c.get("bison_lead_id"))
        has_push = bool(get_push_events(rec, key))
        has_reply = bool(get_reply_events(rec, key))
        has_log_reply = check_reply_in_log(rec)
        li_notes = has_linkedin_note_in_log(rec, key)
        suppressed = is_suppressed(rec, c)

        if suppressed:
            continue  # counted separately

        if has_reply or has_log_reply:
            warm_reply.append((rec, c))
        elif has_bison:
            # Will be split by provider read; for now, group as warm_bison
            warm_bison.append((rec, c))
        elif has_push:
            warm_emailed.append((rec, c))
        elif li_notes > 0:
            warm_linkedin.append((rec, c))
        else:
            cold.append((rec, c))

    print(f"Cold (no history, no bison_lead_id): {len(cold)}")
    print(f"Warm - bison_lead_id (needs provider read to split): {len(warm_bison)}")
    print(f"Warm - actually emailed (push_marked): {len(warm_emailed)}")
    print(f"Warm - reply evidence: {len(warm_reply)}")
    print(f"Warm - LinkedIn notes in log: {len(warm_linkedin)}")
    print(f"Suppressed (excluded from above): {len(suppressed_contacts)}")
    print(f"TOTAL: {len(cold) + len(warm_bison) + len(warm_emailed) + len(warm_reply) + len(warm_linkedin) + len(suppressed_contacts)}")

    # --- 5. LinkedIn indicators in canonical state ---
    print(f"\n{'='*60}")
    print(f"5. LINKEDIN INDICATORS IN CANONICAL STATE")
    print(f"{'='*60}")

    # Count linkedin_note entries per contact
    contacts_with_li_notes = 0
    total_li_notes = 0
    for rec, c in all_contacts:
        count = 0
        for entry in rec.get("log") or []:
            if entry.get("step") == "linkedin_note":
                count += 1
        if count > 0:
            contacts_with_li_notes += 1
            total_li_notes += count

    print(f"Contacts with linkedin_note in log: {contacts_with_li_notes}")
    print(f"Total linkedin_note entries: {total_li_notes}")

    # Check for linkedin_connected, connection_accepted events
    li_connected = 0
    li_accepted = 0
    for rec, c in all_contacts:
        for entry in rec.get("events") or []:
            if entry.get("contact") != c.get("key"):
                continue
            if entry.get("type") == "linkedin_connected":
                li_connected += 1
            if entry.get("type") == "connection_accepted":
                li_accepted += 1

    print(f"linkedin_connected events: {li_connected}")
    print(f"connection_accepted events: {li_accepted}")

    # Check for approved LinkedIn steps
    li_approved = 0
    for rec, c in all_contacts:
        for entry in rec.get("events") or []:
            if entry.get("contact") != c.get("key"):
                continue
            note = entry.get("note") or ""
            if entry.get("step") == "approved" and ":li" in note:
                li_approved += 1
                break

    print(f"Contacts with approved LinkedIn steps: {li_approved}")

    # --- 6. Verification state summary ---
    print(f"\n{'='*60}")
    print(f"6. VERIFICATION STATE SUMMARY")
    print(f"{'='*60}")

    verified_count = sum(1 for _, c in all_contacts if contact_verified(c))
    unverified_count = len(all_contacts) - verified_count
    sendable_count = sum(1 for _, c in all_contacts if c.get("sendable"))

    print(f"Verified contacts: {verified_count}")
    print(f"Unverified contacts: {unverified_count}")
    print(f"Sendable contacts: {sendable_count}")

    # Cross-tabulate: verified + bison vs verified + no bison
    verified_bison = sum(1 for _, c in all_contacts
                         if contact_verified(c) and c.get("bison_lead_id"))
    verified_no_bison = sum(1 for _, c in all_contacts
                            if contact_verified(c) and not c.get("bison_lead_id"))
    print(f"Verified + bison_lead_id: {verified_bison}")
    print(f"Verified + no bison_lead_id: {verified_no_bison}")

    # --- 7. Record states ---
    print(f"\n{'='*60}")
    print(f"7. RECORD STATE DISTRIBUTION")
    print(f"{'='*60}")

    state_counts = {}
    for rec in records:
        s = rec.get("state") or "none"
        state_counts[s] = state_counts.get(s, 0) + 1
    for s, count in sorted(state_counts.items(), key=lambda x: -x[1]):
        print(f"  {s}: {count}")

    print(f"\n=== END SNAPSHOT ANALYSIS ===")


if __name__ == "__main__":
    main()
