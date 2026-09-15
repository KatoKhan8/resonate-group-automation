#!/usr/bin/env python3
"""TASK-153: Provider reads for the historical estate.

READ ONLY. No writes. No mutations.

Two questions:
1. Re-confirm the 13/16 split among 29 bison_lead_id contacts at 550 records
   by calling GET /leads/{id} for each one.
2. For every verified contact, check LinkedIn conversation history on the
   client's seats by searching the HeyReach inbox.

Quotes the snapshot stamp. Hashes all prospect identifiers.
"""
import json
import os
import sys
import time
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import bison  # noqa: E402
from src.providers import heyreach  # noqa: E402
from src import collision  # noqa: E402
from src import clients  # noqa: E402

SNAPSHOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "work", "queue.snapshot.jsonl")
STAMP_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "work", "queue.snapshot.STAMP")
RESULTS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "task153_results.json")

WORKSPACE = "PRODUCTIVE"


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


def hash_id(raw):
    return "h:" + hashlib.sha256(str(raw).encode()).hexdigest()[:12]


def contact_verified(contact):
    v = contact.get("verification") or {}
    return v.get("state") == "verified"


def get_active_contacts(records):
    """Yield (rec, contact) for every contact on non-dropped records."""
    for rec in records:
        if rec.get("state") == "dropped" or rec.get("drop_reason"):
            continue
        for contact in rec.get("contacts") or []:
            yield rec, contact


# ============================================================
# PART 1: Re-confirm the 13/16 split via provider reads
# ============================================================

def check_lead_send_status(lead_id):
    """READ ONLY: GET /leads/{id} -> did this lead receive emails?"""
    try:
        data = bison.lead(lead_id)
    except Exception as e:
        return {"lead_id": lead_id, "error": str(e)}

    overall = data.get("overall_stats") or {}
    emails_sent = int(overall.get("emails_sent") or 0)

    campaigns = []
    for lcd in data.get("lead_campaign_data") or []:
        campaigns.append({
            "campaign_id": lcd.get("campaign_id"),
            "status": lcd.get("status"),
            "emails_sent": int(lcd.get("emails_sent") or 0),
            "replies": int(lcd.get("replies") or 0),
        })

    return {
        "lead_id": lead_id,
        "overall_emails_sent": emails_sent,
        "overall_replies": int(overall.get("replies") or 0),
        "overall_opens": int(overall.get("opens") or 0),
        "campaigns": campaigns,
        "lead_status": data.get("status"),
    }


def part1_bison_reads(records):
    """Re-confirm the 13/16 split for all 29 bison_lead_id contacts."""
    print("=" * 72)
    print("PART 1: Re-confirm 13/16 split via provider reads")
    print("=" * 72)
    print()

    bison_contacts = []
    for rec, c in get_active_contacts(records):
        if c.get("bison_lead_id"):
            bison_contacts.append({
                "rec_id": rec.get("id"),
                "domain": rec.get("domain"),
                "contact_key": c.get("key"),
                "name": c.get("name"),
                "email": c.get("email"),
                "bison_lead_id": c["bison_lead_id"],
            })

    print(f"Contacts with bison_lead_id: {len(bison_contacts)}")
    print()

    never_emailed = []
    actually_emailed = []
    errors = []

    for i, item in enumerate(bison_contacts):
        bid = item["bison_lead_id"]
        hid = hash_id(f"{item['rec_id']}/{item['contact_key']}")
        sys.stdout.write(f"  [{i+1}/{len(bison_contacts)}] lead={bid} ({hid})... ")
        sys.stdout.flush()

        result = check_lead_send_status(bid)
        result["hid"] = hid
        result["domain_hid"] = hash_id(item["domain"])
        result["name"] = item["name"]

        if "error" in result:
            errors.append(result)
            print(f"ERROR: {result['error']}")
        elif result["overall_emails_sent"] == 0:
            never_emailed.append(result)
            print(f"NEVER EMAILED (emails_sent=0, status={result.get('lead_status')})")
        else:
            actually_emailed.append(result)
            print(f"EMAILED: {result['overall_emails_sent']} email(s), "
                  f"{result['overall_replies']} replies")

        time.sleep(0.5)

    print()
    print(f"RESULT: {len(never_emailed)} never emailed, "
          f"{len(actually_emailed)} actually emailed, "
          f"{len(errors)} errors")
    print()

    return {
        "never_emailed": never_emailed,
        "actually_emailed": actually_emailed,
        "errors": errors,
    }


# ============================================================
# PART 2: LinkedIn conversation history
# ============================================================

def establish_tenant_scope():
    """Derive the tenant scope from campaigns + all LI accounts.

    Bypasses our_linkedin_seats (needs sender inventory, absent here) and
    uses only the provider-side tenant boundary from campaigns.
    """
    config = {}
    try:
        config = clients.load(WORKSPACE)
    except Exception:
        pass

    expected = str(((config or {}).get("providers") or {}).get(
        "heyreach", {}).get("org_unit") or "")

    campaigns, _meta = heyreach.campaigns()
    units = {str(c.get("organizationUnitId")) for c in campaigns
             if c.get("organizationUnitId") is not None}

    if not units:
        raise RuntimeError("no campaign states an organisation unit")
    if expected and units != {expected}:
        raise RuntimeError(
            f"multi-tenant: campaigns in {sorted(units)}, "
            f"expected {expected}")

    seats, _ = heyreach.all_li_accounts()
    everybody = {str(a.get("id")) for a in seats if a.get("id") is not None}

    print(f"  Tenant scope: org_unit={units}, "
          f"{len(everybody)} seats from provider, "
          f"{len(campaigns)} campaigns visible")
    return everybody


def check_li_profile_direct(name, linkedin_slug, tenant_seats):
    """Check one LinkedIn profile against the HeyReach inbox.

    Bypasses collision.check_linkedin_profile (needs sender inventory).
    Uses the same algorithm: search by first name, match locally on slug,
    scope to tenant seats.
    """
    slug = collision.profile_slug(linkedin_slug) if "/" in str(linkedin_slug) else (linkedin_slug or "")
    if not slug:
        return "error", {"why": "no usable LinkedIn slug"}

    term = str(name or "").strip().split()[0] if str(name or "").strip() else slug.replace("-", " ")

    try:
        everything = collision.conversations_named(term)
    except collision.CollisionUnknown as e:
        return "error", {"why": str(e)[:200]}

    rows = []
    foreign = 0
    for row in everything:
        touches = collision.linkedin_touches_of(row)
        if str(touches.get("our_seat")) in tenant_seats:
            rows.append(row)
        else:
            foreign += 1

    for row in rows:
        found = collision.linkedin_touches_of(row)
        if found["slug"] != slug:
            continue
        if found["they_replied"]:
            return "replied", found
        if found["total_messages"] > 0:
            return "touched", found
        return "touched", dict(found, note="conversation exists, 0 messages counted")

    return "clear", {
        "slug": slug,
        "searched_as": term,
        "conversations_for_name": len(rows),
        "foreign_ignored": foreign,
        "seats_searched": len(tenant_seats),
    }


def part2_linkedin_reads(records):
    """Check LinkedIn conversation history for verified contacts.

    Establishes tenant scope from campaigns + all LI accounts (provider reads),
    then searches the HeyReach inbox for each verified contact by name,
    matching locally on profile slug.
    """
    print("=" * 72)
    print("PART 2: LinkedIn conversation history")
    print("=" * 72)
    print()

    # Establish tenant scope first (2 provider reads)
    print("  Establishing tenant scope...")
    try:
        tenant_seats = establish_tenant_scope()
    except Exception as e:
        print(f"  FATAL: cannot establish tenant scope: {e}")
        return {
            "found_conversations": [],
            "clear_contacts": [],
            "broad_match": [],
            "errors": [{"error": f"tenant scope failed: {e}"}],
            "total_checked": 0,
        }
    print()

    # Collect verified contacts with LinkedIn profiles
    candidates = []
    for rec, c in get_active_contacts(records):
        if not contact_verified(c):
            continue
        li = c.get("linkedin") or ""
        if not li:
            continue
        candidates.append({
            "rec_id": rec.get("id"),
            "domain": rec.get("domain"),
            "contact_key": c.get("key"),
            "name": c.get("name"),
            "linkedin": li,
            "has_bison": bool(c.get("bison_lead_id")),
        })

    print(f"Verified contacts with LinkedIn profiles: {len(candidates)}")
    print()

    found_conversations = []
    clear_contacts = []
    errors = []
    broad_match = []

    for i, item in enumerate(candidates):
        hid = hash_id(f"{item['rec_id']}/{item['contact_key']}")
        sys.stdout.write(f"  [{i+1}/{len(candidates)}] {hid}... ")
        sys.stdout.flush()

        verdict, detail = check_li_profile_direct(
            item["name"], item["linkedin"], tenant_seats)

        if verdict == "clear":
            clear_contacts.append({
                "hid": hid,
                "name": item["name"],
                "conversations_for_name": detail.get("conversations_for_name", 0),
            })
            print(f"CLEAR ({detail.get('conversations_for_name', 0)} convos for name)")
        elif verdict == "replied":
            found_conversations.append({
                "hid": hid,
                "name": item["name"],
                "verdict": "replied",
                "detail": {k: v for k, v in detail.items()
                           if k in ("total_messages", "they_replied",
                                    "last_message_at", "our_seat",
                                    "seat_name", "conversation_id")},
            })
            print(f"REPLIED (msgs={detail.get('total_messages')}, "
                  f"seat={detail.get('seat_name', '?')})")
        elif verdict == "touched":
            found_conversations.append({
                "hid": hid,
                "name": item["name"],
                "verdict": "touched",
                "detail": {k: v for k, v in detail.items()
                           if k in ("total_messages", "they_replied",
                                    "last_message_at", "our_seat",
                                    "seat_name", "conversation_id", "note")},
            })
            print(f"TOUCHED (msgs={detail.get('total_messages')}, "
                  f"seat={detail.get('seat_name', '?')})")
        elif verdict == "error":
            err_msg = detail.get("why", "unknown")
            if "broad" in err_msg.lower() or "too many" in err_msg.lower():
                broad_match.append({
                    "hid": hid,
                    "name": item["name"],
                    "error": err_msg,
                })
                print(f"BROAD MATCH")
            else:
                errors.append({
                    "hid": hid,
                    "name": item["name"],
                    "error": err_msg,
                })
                print(f"ERROR: {err_msg[:80]}")

        time.sleep(0.75)

    print()
    print(f"RESULT: {len(found_conversations)} with history, "
          f"{len(clear_contacts)} clear, "
          f"{len(broad_match)} broad match, "
          f"{len(errors)} errors")
    print()

    return {
        "found_conversations": found_conversations,
        "clear_contacts": clear_contacts,
        "broad_match": broad_match,
        "errors": errors,
        "total_checked": len(candidates),
        "tenant_seats": len(tenant_seats),
    }


# ============================================================
# MAIN
# ============================================================

def main():
    records = load_records()
    stamp = load_stamp()

    print(f"=== TASK-153 PROVIDER READS ===")
    print(f"Snapshot stamp: {stamp}")
    print(f"Total records: {len(records)}")
    print(f"Workspace: {WORKSPACE}")
    print(f"READS ONLY. No writes.")
    print()

    # Part 1: bison reads
    p1 = part1_bison_reads(records)

    print()

    # Part 2: LinkedIn reads
    p2 = part2_linkedin_reads(records)

    # Save results
    results = {
        "stamp": stamp,
        "part1_bison": p1,
        "part2_linkedin": p2,
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"Results saved to {RESULTS_FILE}")
    print()

    # Summary
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print()
    print(f"Part 1 - Bison lead re-check:")
    print(f"  Never emailed: {len(p1['never_emailed'])}")
    print(f"  Actually emailed: {len(p1['actually_emailed'])}")
    print(f"  Errors: {len(p1['errors'])}")
    print()
    print(f"Part 2 - LinkedIn conversation history:")
    print(f"  Total checked: {p2['total_checked']}")
    print(f"  With history (STOP/HOLD): {len(p2['found_conversations'])}")
    print(f"  Clear (ALLOW): {len(p2['clear_contacts'])}")
    print(f"  Broad match: {len(p2['broad_match'])}")
    print(f"  Errors: {len(p2['errors'])}")


if __name__ == "__main__":
    main()
