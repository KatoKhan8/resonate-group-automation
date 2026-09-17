#!/usr/bin/env python3
"""Approve and ACTIVATE HeyReach campaign 605487 - the 4-contact cohort.

    py -3 scripts/activate_linkedin_cohort.py            # dry run
    py -3 scripts/activate_linkedin_cohort.py --live      # approve + ACTIVATE

THIS SENDS. `heyreach.start_campaign` starts the campaign, and the campaign's
audience is the leads in its bound `linkedInUserListId` (TASK-220, from the
vendor documentation). There is no recalling a LinkedIn message.

EXACT MAXIMUM EXPOSURE, measured by walking the installed graph rather than
asserted: 10 distinct paths, and the longest carries 4 prospect-facing
messages. Already-connected takes CHECK_IS_CONNECTION > MESSAGE x2 >
VIEW_PROFILE > MESSAGE x2; cold takes VIEW_PROFILE > FOLLOW >
CONNECTION_REQUEST > MESSAGE > VIEW_PROFILE > MESSAGE x2. So per person: at
most 4 messages, and on the cold path at most 1 connection request. Across the
4-person audience: AT MOST 16 MESSAGES AND 4 CONNECTION REQUESTS.

WHY FOUR AND NOT SIX. Six contacts carry full li1-li5 `operator-control-arm`
approval. `collision.account_policy` is re-read at run time and HOLDS account
c0ef6483d378 - nine emails across two campaigns, one `stopped` for a reason
the provider does not record. The hold is correct and is not worked around;
those two contacts are simply not in this cohort. The cohort is what the gates
allow, not a number chosen here.

WHY THERE ARE THREE STEPS AND NOT ONE. `providerwrites.perform` refuses a
prospect-facing verb without an `executionguard.Authorization`, and
`authorize()` refuses without (a) a provider readback it did not fetch itself
and (b) a CURRENT campaign-level approval binding senders, limits, provider
binding, tenant and LEAD SET by fingerprint. EVERY contact in the cohort is
authorized separately - one Authorization for the campaign would prove nothing
about the other three people it reaches.

WHAT IS SCOPED WHERE:
  providerwrites.CONDITIONAL   refuses any campaign but the authorized one
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import (campaigns, clients, configdiff, executionguard,      # noqa
                 liststaging, orchestrator, providerwrites, store)
from src.providers import heyreach                                    # noqa
from provider_truth import heyreach_sequence_hash                     # noqa

CANONICAL = "productive-linkedin-cohort-v1"
PROVIDER_ID = 605487
SOURCE_ID = 599020
LIST_ID = 943957
SEAT_ID = 174892
STEP_KEY = "li1"
MAX_AUDIENCE = 4
MAX_MESSAGES_PER_PERSON = 4
COHORT_PROFILE_HASHES = {"6acd6d9f031b", "4684b25b0372",
                         "c01f0c88111c", "4258f756357d"}


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def approver():
    who = subprocess.run(["git", "config", "user.email"],
                         capture_output=True, text=True).stdout.strip()
    if not who:
        raise SystemExit("REFUSED: git config user.email is unset, so the "
                         "approval would be attributed to nobody.")
    return who


def cohort_contacts(campaign, recs):
    """Every (rec, contact) on the row whose profile is in the cohort."""
    found = {}
    for rec in recs:
        if rec["id"] not in (campaign.get("record_ids") or []):
            continue
        for contact in rec.get("contacts") or []:
            url = liststaging.canonical_profile_url(contact.get("linkedin"))
            if url and h12(url.lower()) in COHORT_PROFILE_HASHES:
                found[h12(url.lower())] = (rec, contact)
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="approve and ACTIVATE; omit for a dry run")
    args = parser.parse_args(argv)

    config = clients.load("productive")
    recs = store.load()
    campaign = campaigns.require(CANONICAL)

    problems = []
    row = heyreach.campaign_read(PROVIDER_ID) or {}
    status = str(row.get("status") or "").upper()
    members, audience = heyreach.list_leads(LIST_ID)
    graph = heyreach.campaign_sequence(PROVIDER_ID)
    graph_hash = heyreach_sequence_hash(graph)
    source_hash = heyreach_sequence_hash(heyreach.campaign_sequence(SOURCE_ID))
    nodes, words = heyreach.validate_sequence_for_write(
        heyreach.sequence_for_write(graph))

    print("=== PRE-ACTIVATION, PROVIDER TRUTH ===")
    print(f"  provider campaign : {row.get('id')}")
    print(f"  status            : {status}")
    print(f"  bound list        : {row.get('linkedInUserListId')}")
    print(f"  seats             : {row.get('campaignAccountIds')}")
    print(f"  sequence          : {nodes} nodes, {words} word-bearing")
    print(f"  sequence hash     : {graph_hash}")
    print(f"  audited 599020    : {source_hash}")
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
    if graph_hash != source_hash:
        problems.append(f"the installed graph {graph_hash} is not the audited "
                        f"599020 graph {source_hash}")

    # The provider's people must be exactly the cohort, by profile hash.
    staged = {h12((liststaging.canonical_profile_url(m.get("profile_url"))
                   or "").lower()) for m in members}
    if staged != COHORT_PROFILE_HASHES:
        problems.append(f"the bound list holds {sorted(staged)} and the "
                        f"approved cohort is {sorted(COHORT_PROFILE_HASHES)}")

    found = cohort_contacts(campaign, recs)
    missing = COHORT_PROFILE_HASHES - set(found)
    if missing:
        problems.append(f"cohort contact(s) not on the campaign row: "
                        f"{sorted(missing)}")

    if problems:
        print("\nREFUSED. Nothing was activated:")
        for p in problems:
            print(f"  - {p}")
        return 2
    print("  preflight         : PASS")
    print(f"  max send exposure : {audience} people, up to "
          f"{MAX_MESSAGES_PER_PERSON} messages each = "
          f"{audience * MAX_MESSAGES_PER_PERSON} messages, plus at most "
          f"{audience} connection requests")

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
            interaction_id="operator-authz-2026-09-16-heyreach-cohort",
            config=config, recs=recs, role="admin")
    campaign = campaigns.require(CANONICAL)
    print(f"  decide            : {result.get('status', 'approved')}")
    print(f"  fingerprint       : {fingerprint}")
    if not campaigns.is_approved(campaign, recs, config):
        print("  REFUSED: the campaign approval is not current after writing "
              "it. Not activating.")
        return 3
    print("  campaign approved : current")

    # 2. THE READBACK AND ONE AUTHORIZATION PER CONTACT.
    print("\n=== 2. MINT THE AUTHORIZATIONS ===")
    readback = configdiff.compare_heyreach(campaign, recs=recs, config=config,
                                           staging=True)
    print(f"  readback verdict  : {(readback.diff or {}).get('verdict')}")
    auths = {}
    for phash in sorted(COHORT_PROFILE_HASHES):
        rec, contact = found[phash]
        try:
            auths[phash] = executionguard.authorize(
                operation=providerwrites.LINKEDIN_ACTIVATE, channel="linkedin",
                campaign=campaign, rec=rec, contact=contact, step_key=STEP_KEY,
                workspace="productive", config=config, recs=recs,
                readback=readback, by="operator")
            print(f"  {phash}      : authorized")
        except Exception as exc:
            print(f"  {phash}      : REFUSED {type(exc).__name__}: {exc}")
    if len(auths) != len(COHORT_PROFILE_HASHES):
        print("\n  REFUSED: not every contact in the audience is authorized, "
              "and the audience is the whole bound list. Nothing was "
              "activated.")
        return 3
    print(f"  authorizations    : {len(auths)}/{len(COHORT_PROFILE_HASHES)}")

    # 3. ACTIVATION.
    print("\n=== 3. ACTIVATE ===")
    try:
        providerwrites.perform(
            providerwrites.LINKEDIN_ACTIVATE,
            authorization=auths[sorted(auths)[0]],
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
              "have started. Read campaign_read(605487).")
        return 3

    print("\n=== 4. PROVIDER TRUTH AFTER ACTIVATION ===")
    after = heyreach.campaign_read(PROVIDER_ID) or {}
    print(json.dumps({k: after.get(k) for k in (
        "id", "name", "status", "linkedInUserListId",
        "campaignAccountIds", "startedAt")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
