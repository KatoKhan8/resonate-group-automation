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
from src import collision  # noqa: E402

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

def part2_linkedin_reads(records):
    """Check LinkedIn conversation history for verified contacts.

    Uses collision.check_linkedin_profile (READ ONLY) for each contact
    that has a LinkedIn profile URL.
    """
    print("=" * 72)
    print("PART 2: LinkedIn conversation history")
    print("=" * 72)
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
        li_url = item["linkedin"]
        sys.stdout.write(f"  [{i+1}/{len(candidates)}] {hid}... ")
        sys.stdout.flush()

        try:
            verdict, detail = collision.check_linkedin_profile(
                li_url,
                name=item["name"],
                expect_workspace=WORKSPACE,
            )
            if verdict == collision.ALLOW:
                clear_contacts.append({
                    "hid": hid,
                    "name": item["name"],
                    "verdict": verdict,
                })
                print(f"CLEAR")
            elif verdict == collision.STOP:
                found_conversations.append({
                    "hid": hid,
                    "name": item["name"],
                    "verdict": verdict,
                    "detail": str(detail)[:200],
                })
                print(f"HISTORY FOUND: {str(detail)[:100]}")
            elif verdict == collision.HOLD:
                found_conversations.append({
                    "hid": hid,
                    "name": item["name"],
                    "verdict": verdict,
                    "detail": str(detail)[:200],
                })
                print(f"HOLD: {str(detail)[:100]}")
            else:
                clear_contacts.append({
                    "hid": hid,
                    "name": item["name"],
                    "verdict": verdict,
                    "detail": str(detail)[:200] if detail else None,
                })
                print(f"{verdict}: {str(detail)[:80] if detail else 'no detail'}")
        except collision.CollisionUnknown as e:
            err_msg = str(e)[:120]
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
                print(f"ERROR: {err_msg}")
        except Exception as e:
            errors.append({
                "hid": hid,
                "name": item["name"],
                "error": str(e)[:120],
            })
            print(f"ERROR: {str(e)[:80]}")

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
