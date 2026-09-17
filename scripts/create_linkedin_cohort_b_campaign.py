#!/usr/bin/env python3
"""Create the LinkedIn DRAFT production campaign bound to list 944355.

    py -3 scripts/create_linkedin_cohort_b_campaign.py            # dry run
    py -3 scripts/create_linkedin_cohort_b_campaign.py --live      # create it

Sibling of create_linkedin_canary_campaign.py. Same preflight, same write, same
zero-send property; only the target list and the expected lead count differ.

WHY A NEW SCRIPT RATHER THAN A FLAG. The canary script's constants are what its
preflight refuses against - LIST_ID 940797, EXPECT_LEADS 1. 940797 is now bound
to campaign 604869 and the single contact it holds is HELD by account_collision.
That campaign is a dead end for sending and is left alone. This cohort is
list 944355: unbound, holding exactly the 3 contacts that BOTH collision
gates clear - account_policy AND the profile check executionguard itself makes.
List 943957 held four; gate 4 refused one of them at activation for four prior
LinkedIn messages from our own seat, and that contact is dropped.

AUTHORIZED: `heyreach.create_campaign` is SUPPORTED/CONDITIONAL on the LIST -
ours, in our tenant, unbound, holding only approved leads. 943957 satisfies
every clause; the condition is not scoped to a campaign id, so no new grant is
needed to create a DRAFT.

MAXIMUM SEND EXPOSURE OF THIS SCRIPT IS ZERO. `heyreach.create_campaign`
creates in DRAFT. A DRAFT SENDS NOTHING. Activation is /campaign/StartCampaign,
a separate gate that needs its own campaign-scoped operator authorization.

THE BIND IS ONE-WAY. `linkedInUserListId` is supplied at creation and there is
no detach route, so the moment this succeeds 943957 stops being unbound and
`liststaging.assert_list_safe` will correctly refuse every later add to it. A
future cohort needs a different unbound list. That is expected, not a bug.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import liststaging, providerwrites, store          # noqa: E402
from src.providers import heyreach                          # noqa: E402

LIST_ID = 944355
SEAT_ID = 174892
NAME = "RESONATE - PRODUCTIVE LINKEDIN COHORT V2 - CONTROL"
EXPECT_LEADS = 3
REQUIRED_APPROVER = "operator-control-arm"
REQUIRED_STEPS = ("li1", "li2", "li3", "li4", "li5")


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def approved_profiles():
    """Canonical profile URLs whose li1-li5 carry operator approval."""
    out = {}
    for rec in store.load():
        cadence = rec.get("cadence") or {}
        for contact in rec.get("contacts") or []:
            steps = cadence.get(contact.get("key")) or {}
            ok = all(
                ((steps.get(s) or {}).get("approval") or {}).get("by")
                == REQUIRED_APPROVER for s in REQUIRED_STEPS)
            url = liststaging.canonical_profile_url(contact.get("linkedin"))
            if ok and url:
                out[url.lower()] = (rec["id"], contact.get("key"))
    return out


def preflight():
    problems, facts = [], {}

    row = heyreach.list_by_id(LIST_ID)
    facts["list_id"] = row.get("id")
    facts["campaignIds"] = row.get("campaignIds") or []
    if facts["campaignIds"]:
        problems.append(
            f"list {LIST_ID} is already attached to {facts['campaignIds']}; "
            f"it is no longer an unbound staging list")

    members, total = heyreach.list_leads(LIST_ID)
    facts["lead_count"] = total
    if total != EXPECT_LEADS:
        problems.append(f"list holds {total} lead(s), expected {EXPECT_LEADS}")

    approved = approved_profiles()
    facts["approved_available"] = len(approved)
    held, unapproved = [], []
    for m in members:
        url = liststaging.canonical_profile_url(m.get("profile_url"))
        key = (url or "").lower()
        held.append(h12(key))
        if key not in approved:
            unapproved.append(h12(key))
    facts["held"] = held
    if unapproved:
        problems.append(
            f"list holds lead(s) with no operator-control-arm approval on "
            f"li1-li5: {unapproved}")

    try:
        seat = heyreach.sender_by_id(SEAT_ID) if hasattr(
            heyreach, "sender_by_id") else None
        facts["seat"] = SEAT_ID if seat is None else (
            seat.get("id") or SEAT_ID)
    except Exception as exc:
        problems.append(f"seat {SEAT_ID} could not be read "
                        f"({type(exc).__name__})")
    return facts, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="create the DRAFT campaign; omit for a dry run")
    args = parser.parse_args(argv)

    facts, problems = preflight()
    print("=== PRE-CREATION, PROVIDER TRUTH ===")
    for key in ("list_id", "campaignIds", "lead_count", "held",
                "approved_available", "seat"):
        print(f"  {key:19s}: {facts.get(key)}")
    if problems:
        print("\nREFUSED. Nothing was created:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print("  preflight          : PASS")
    print(f"  name               : {NAME}")
    print("  max send exposure  : ZERO (created in DRAFT; activate is not "
          "in SUPPORTED)")

    if not args.live:
        print("\nDRY RUN: nothing was created.")
        print("Re-run with --live to create the DRAFT campaign.")
        return 0

    created = {}

    def transport(payload):
        created.update(heyreach.create_campaign(
            payload["name"], payload["list_id"], payload["account_ids"]) or {})
        return created

    def readback():
        if not created.get("id"):
            return {}
        row = heyreach.campaign_by_id(created["id"]) or {}
        return {"status": str(row.get("status") or "").upper(),
                "list": row.get("linkedInUserListId")}

    try:
        providerwrites.perform(
            providerwrites.LINKEDIN_CREATE_CAMPAIGN,
            provider_campaign_id=str(LIST_ID),   # the condition takes a LIST id
            campaign=None,
            tenant="productive",
            payload={"name": NAME, "list_id": LIST_ID,
                     "account_ids": [SEAT_ID]},
            transport=transport,
            readback=readback,
            expected={"status": "DRAFT", "list": LIST_ID},
            by="operator")
    except Exception as exc:
        print(f"\nREFUSED / FAILED: {type(exc).__name__}: {exc}")
        if created.get("id"):
            print(f"\n  A CAMPAIGN WAS CREATED: {created['id']}. Read provider "
                  f"truth before doing anything else:")
            print(f"    py -3 -c \"from src.providers import heyreach; "
                  f"print(heyreach.campaign_by_id({created['id']}))\"")
        return 3

    cid = created.get("id")
    print(f"\n=== CREATED. provider campaign id {cid} ===")
    row = heyreach.campaign_by_id(cid) or {}
    print(json.dumps({k: row.get(k) for k in (
        "id", "name", "status", "linkedInUserListId",
        "campaignAccountIds")}, indent=1))
    leads, total = heyreach.campaign_leads(cid)
    print(f"  campaign leads     : {total}")
    after = heyreach.list_by_id(LIST_ID)
    print(f"  list campaignIds   : {after.get('campaignIds')}")
    print("\nThe campaign is DRAFT and cannot send. Activation needs "
          "heyreach.activate, which is not in SUPPORTED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
