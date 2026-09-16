#!/usr/bin/env python3
"""Approve and ACTIVATE HeyReach campaign 604869. Authorized 2026-09-16.

    py -3 scripts/activate_linkedin_canary.py            # dry run
    py -3 scripts/activate_linkedin_canary.py --live      # approve + ACTIVATE

THIS SENDS. `heyreach.start_campaign` starts the campaign, and the campaign's
audience is the leads in its bound `linkedInUserListId` (TASK-220, from the
vendor documentation). There is no recalling a LinkedIn message.

THE GRANT: "APPROVE HEYREACH ACTIVATION: campaign 604869, maximum send
exposure 1 person / up to 4 messages." Recorded in
OPERATOR-AUTHORIZATION-2026-09-16.md.

WHY THERE ARE THREE STEPS AND NOT ONE. `providerwrites.perform` refuses a
prospect-facing verb without an `executionguard.Authorization`, and
`authorize()` refuses without (a) a provider readback it did not fetch itself
and (b) a CURRENT campaign-level approval. That campaign approval is a
different thing from the per-step copy approvals: it binds the senders, the
limits, the provider binding, the tenant and the LEAD SET, by fingerprint. A
campaign whose lead set changed after approval is not approved.

So: record the operator's approval through `orchestrator.decide` (never by
hand-setting `campaign["approval"]` - the fingerprint binding is the point),
take a fresh `compare_heyreach` readback, mint the Authorization, then write.

WHAT IS SCOPED WHERE:
  providerwrites.CONDITIONAL   refuses any campaign but 604869
  start_campaign expect_leads  refuses if the provider disagrees with the
                               audience count this script read
  executionguard.authorize     every prospect-facing gate, per contact
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (campaigns, clients, configdiff, executionguard,      # noqa
                 liststaging, orchestrator, providerwrites, store)
from src.providers import heyreach                                    # noqa

CANONICAL = "productive-linkedin-canary-v1"
PROVIDER_ID = 604869
LIST_ID = 940797
SEAT_ID = 174892
STEP_KEY = "li1"
CANARY_PROFILE_HASH = "1b294aaaa2a2"
MAX_AUDIENCE = 1


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def approver():
    who = subprocess.run(["git", "config", "user.email"],
                         capture_output=True, text=True).stdout.strip()
    if not who:
        raise SystemExit("REFUSED: git config user.email is unset, so the "
                         "approval would be attributed to nobody.")
    return who


def find_canary(campaign, recs):
    for rec in recs:
        if rec["id"] not in (campaign.get("record_ids") or []):
            continue
        for contact in rec.get("contacts") or []:
            url = liststaging.canonical_profile_url(contact.get("linkedin"))
            if url and h12(url.lower()) == CANARY_PROFILE_HASH:
                return rec, contact
    return None, None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="approve and ACTIVATE; omit for a dry run")
    args = parser.parse_args(argv)

    config = clients.load("productive")
    recs = store.load()
    campaign = campaigns.require(CANONICAL)

    problems = []
    row = heyreach.campaign_by_id(PROVIDER_ID) or {}
    status = str(row.get("status") or "").upper()
    _members, audience = heyreach.list_leads(LIST_ID)
    graph = heyreach.campaign_sequence(PROVIDER_ID)
    nodes, words = heyreach.validate_sequence_for_write(
        heyreach.sequence_for_write(graph))

    print("=== PRE-ACTIVATION, PROVIDER TRUTH ===")
    print(f"  provider campaign : {row.get('id')}")
    print(f"  status            : {status}")
    print(f"  bound list        : {row.get('linkedInUserListId')}")
    print(f"  seats             : {row.get('campaignAccountIds')}")
    print(f"  sequence          : {nodes} nodes, {words} word-bearing")
    print(f"  audience (list)   : {audience}")

    if str(row.get("linkedInUserListId")) != str(LIST_ID):
        problems.append(f"bound list is {row.get('linkedInUserListId')}, "
                        f"not {LIST_ID}")
    if SEAT_ID not in (row.get("campaignAccountIds") or []):
        problems.append(f"seat {SEAT_ID} is not attached")
    if status != "DRAFT":
        problems.append(f"status is {status!r}; expected DRAFT")
    if audience != MAX_AUDIENCE:
        problems.append(f"audience is {audience}, and this authorization "
                        f"covers {MAX_AUDIENCE}")

    rec, contact = find_canary(campaign, recs)
    if rec is None:
        problems.append("the approved canary contact is not on the campaign row")

    if problems:
        print("\nREFUSED. Nothing was activated:")
        for p in problems:
            print(f"  - {p}")
        return 2
    print("  preflight         : PASS")
    print(f"  max send exposure : {audience} person, up to 4 messages")

    if not args.live:
        print("\nDRY RUN: nothing was activated.")
        print("Re-run with --live to approve and ACTIVATE.")
        return 0

    # 1. THE CAMPAIGN APPROVAL, through the sanctioned path.
    print("\n=== 1. RECORD THE CAMPAIGN APPROVAL ===")
    who = approver()
    with campaigns.transaction() as rows:
        target = campaigns.get(CANONICAL, rows)
        fingerprint = campaigns.fingerprint(target, recs, config)
        result = orchestrator.decide(
            target, who, "approve", fingerprint=fingerprint,
            interaction_id="operator-authz-2026-09-16-heyreach",
            config=config, recs=recs, role="admin")
    campaign = campaigns.require(CANONICAL)
    print(f"  decide            : {result.get('status', 'approved')}")
    print(f"  fingerprint       : {fingerprint}")
    if not campaigns.is_approved(campaign, recs, config):
        print("  REFUSED: the campaign approval is not current after writing "
              "it. Not activating.")
        return 3
    print("  campaign approved : current")

    # 2. THE READBACK AND THE AUTHORIZATION.
    print("\n=== 2. MINT THE AUTHORIZATION ===")
    readback = configdiff.compare_heyreach(campaign, recs=recs, config=config,
                                           staging=True)
    print(f"  readback verdict  : {(readback.diff or {}).get('verdict')}")
    try:
        auth = executionguard.authorize(
            operation=providerwrites.LINKEDIN_ACTIVATE, channel="linkedin",
            campaign=campaign, rec=rec, contact=contact, step_key=STEP_KEY,
            workspace="productive", config=config, recs=recs,
            readback=readback, by="operator")
    except Exception as exc:
        print(f"  REFUSED: {type(exc).__name__}: {exc}")
        print("  Nothing was activated.")
        return 3
    print(f"  authorization     : minted for {auth.operation}")

    # 3. ACTIVATION.
    print("\n=== 3. ACTIVATE ===")
    try:
        providerwrites.perform(
            providerwrites.LINKEDIN_ACTIVATE,
            authorization=auth,
            provider_campaign_id=str(PROVIDER_ID),
            campaign=CANONICAL, tenant="productive",
            payload={"campaign_id": PROVIDER_ID, "expect_leads": audience},
            transport=lambda p: heyreach.start_campaign(
                p["campaign_id"], expect_leads=p["expect_leads"]),
            readback=lambda: {"status": str(
                heyreach.campaign_read(PROVIDER_ID).get("status") or "").upper()},
            expected=None, by="operator")
    except Exception as exc:
        print(f"  REFUSED / FAILED: {type(exc).__name__}: {exc}")
        print("\n  READ PROVIDER TRUTH before anything else - the campaign may "
              "have started:")
        print(f"    py -3 -c \"from src.providers import heyreach; "
              f"print(heyreach.campaign_read({PROVIDER_ID}))\"")
        return 3

    print("\n=== 4. PROVIDER TRUTH AFTER ACTIVATION ===")
    after = heyreach.campaign_by_id(PROVIDER_ID) or {}
    print(json.dumps({k: after.get(k) for k in (
        "id", "name", "status", "linkedInUserListId",
        "campaignAccountIds")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
