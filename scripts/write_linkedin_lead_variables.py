#!/usr/bin/env python3
"""Put each lead's APPROVED words on the list, and prove they arrived.

    py -3 scripts/write_linkedin_lead_variables.py            # dry run
    py -3 scripts/write_linkedin_lead_variables.py --live      # write them

WHY THIS IS NOT OPTIONAL. The sequence graph holds VARIABLES, never words -
`{connection_note}`, `{connected_1}`..`{connected_4}`. HeyReach does not error
on a variable it cannot fill; the vendor's own help centre says "if the value
is null, the fallback message will be used". List 944355's three leads were
staged with names and URLs only, every one `customFields: []`. So starting the
campaign in that state would reach three real people with generic fallback
copy, under authorizations whose fingerprints cover their PERSONALISED li1-li5
copy. That is the same defect on the LinkedIn side that TASK-215 caught on the
email side, and `providerwrites._require_approved_words` refused the activation
because of it.

THE ROUTE. `/list/AddLeadsToListV2` carries `customUserFields` and UPDATES a
lead already in the list - `updatedLeadsCount` is the upsert counter. This
module previously documented the list route as three fields only; that was an
over-read of the 2026-09-15 probes, none of which ever sent the key.

WHY NOT THE CAMPAIGN ROUTE. `/campaign/AddLeadsToCampaignV2` also carries the
fields, and is sealed - correctly. The vendor documents that only ongoing,
paused and finished campaigns accept added leads, and that adding to a FINISHED
campaign activates it. 605732 is DRAFT, so that call would simply fail.

SEND EXPOSURE IS ZERO. Adding or updating leads on a list reaches nobody; list
944355's campaign 605732 is DRAFT and a DRAFT sends nothing. The words are
staged here so that the activation, when it happens, sends the approved ones.

WHAT IT REFUSES. A contact whose approved copy is incomplete is not written and
not silently defaulted - `custom_fields_for` returns `missing` and this stops.
Writing a partial set would be choosing which sentences a prospect reads.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import (campaigns, clients, heyreachfactory, liststaging,   # noqa
                 providerwrites, store)
from src.providers import heyreach, load_env                          # noqa

CANONICAL = "productive-linkedin-cohort-v2"
LIST_ID = 944355
PROVIDER_ID = 605732
COHORT_PROFILE_HASHES = {"4684b25b0372", "c01f0c88111c", "4258f756357d"}


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def planned():
    """(rows, problems) - one row per cohort contact with its approved words."""
    config = clients.load("productive")
    recs = store.load()
    campaign = campaigns.require(CANONICAL)
    cadence_steps = campaign.get("cadence_steps")
    rows, problems = [], []
    for rec in recs:
        if rec["id"] not in (campaign.get("record_ids") or []):
            continue
        for contact in rec.get("contacts") or []:
            url = liststaging.canonical_profile_url(contact.get("linkedin"))
            if not url or h12(url.lower()) not in COHORT_PROFILE_HASHES:
                continue
            fields, missing = heyreachfactory.custom_fields_for(
                rec, contact.get("key"), cadence_steps=cadence_steps,
                campaign=campaign, config=config)
            if missing:
                problems.append(
                    f"{h12(url.lower())} has no approved copy for "
                    f"{sorted({m if isinstance(m, str) else str(m) for m in missing})}")
                continue
            parts = str(contact.get("name") or "").strip().split()
            rows.append({
                "hash": h12(url.lower()),
                "linkedin_url": url,
                "first_name": parts[0] if parts else "",
                "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
                "custom_fields": fields,
            })
    found = {row["hash"] for row in rows}
    for missing_hash in sorted(COHORT_PROFILE_HASHES - found):
        problems.append(f"{missing_hash} produced no row")
    return rows, problems


def provider_fields():
    """What the provider holds per lead, right now."""
    members, _total = heyreach.list_leads(LIST_ID)
    out = {}
    for member in members:
        url = liststaging.canonical_profile_url(member.get("profile_url"))
        out[h12((url or "").lower())] = member.get("custom_fields") or {}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="write the variables; omit for a dry run")
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    row = heyreach.campaign_read(PROVIDER_ID) or {}
    status = str(row.get("status") or "").upper()
    rows, problems = planned()

    print("=== BEFORE, PROVIDER TRUTH ===")
    print(f"  campaign {PROVIDER_ID}   : {status}")
    before = provider_fields()
    for phash, fields in sorted(before.items()):
        print(f"  {phash}      : {sorted(fields)}")

    if status != "DRAFT":
        problems.append(f"campaign {PROVIDER_ID} is {status!r}, not DRAFT; "
                        f"staging words into a running campaign is not what "
                        f"this script is for")

    print("\n=== PLANNED ===")
    for plan in rows:
        print(f"  {plan['hash']}      : {sorted(plan['custom_fields'])}")
    if problems:
        print("\nREFUSED. Nothing was written:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print(f"  contacts          : {len(rows)}")
    print("  send exposure     : ZERO (list write; the campaign is DRAFT)")

    if not args.live:
        print("\nDRY RUN: nothing was written.")
        return 0

    print("\n=== WRITE ===")
    written, refused = [], []
    for plan in rows:
        payload_row = {k: plan[k] for k in (
            "linkedin_url", "first_name", "last_name", "custom_fields")}
        try:
            liststaging.stage_lead(
                LIST_ID, payload_row,
                lambda p, _row=payload_row: heyreach.add_leads_to_list(
                    p["listId"], [_row]),
                allow_restage=True)
            written.append(plan["hash"])
            print(f"  WROTE    {plan['hash']}")
        except TypeError:
            # `stage_lead` may not take `allow_restage`; these leads already
            # exist, so go through the transport directly rather than pretend
            # this is a first staging.
            heyreach.add_leads_to_list(LIST_ID, [payload_row])
            written.append(plan["hash"])
            print(f"  WROTE    {plan['hash']} (direct upsert)")
        except Exception as exc:
            refused.append(plan["hash"])
            print(f"  REFUSED  {plan['hash']}  {type(exc).__name__}: "
                  f"{str(exc)[:90]}")

    # THE READBACK IS THE POINT. A write that reports success proves nothing
    # about what the provider holds; this reads it back and compares the words.
    print("\n=== AFTER, PROVIDER TRUTH ===")
    after = provider_fields()
    by_hash = {plan["hash"]: plan for plan in rows}
    exact, wrong = [], []
    for phash, plan in sorted(by_hash.items()):
        held = after.get(phash) or {}
        want = {str(k): str(v) for k, v in plan["custom_fields"].items()}
        got = {str(k): str(v) for k, v in held.items() if str(k) in want}
        print(f"  {phash}      : provider holds {sorted(held)}")
        if got == want:
            exact.append(phash)
        else:
            differing = sorted(k for k in want if want[k] != got.get(k))
            wrong.append((phash, differing))
            print(f"     MISMATCH on {differing}")

    print(f"\n  written  : {len(written)}   refused : {len(refused)}")
    print(f"  EXACT    : {len(exact)}/{len(rows)}")
    if wrong:
        print("\n  THE PROVIDER DOES NOT HOLD THE APPROVED WORDS. Do not "
              "activate: the graph would fall back to generic copy.")
        return 4
    print("\n  Every cohort lead holds exactly its approved words.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
