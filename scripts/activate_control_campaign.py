#!/usr/bin/env python3
"""Assign sender 2736 to EmailBison 485 and activate it. Authorized 2026-09-16.

    py -3 scripts/activate_control_campaign.py            # dry run
    py -3 scripts/activate_control_campaign.py --live      # assign + ACTIVATE

THIS IS THE FIRST VERB IN THIS SYSTEM THAT MAKES A CAMPAIGN SEND. Everything
before it staged or stopped. `bison.resume_campaign` starts a campaign sending
to EVERY lead it holds, and there is no recalling an email.

THE GRANT, VERBATIM IN SCOPE. The operator authorized, on 2026-09-16:

    workspace    productive
    channel      EmailBison
    campaign_id  485
    cohort       the existing 10 approved contacts
    sequence     the existing approved 3-step CONTROL
    daily_cap    20
    sender_id    2736

    exactly two actions: bison.assign_sender (2736 to 485 only) and
    bison.activate (485 only)

and stated it is NOT authorization to disable or weaken any global safety
mechanism, activate other campaigns, change copy, add unapproved contacts, or
increase caps. `providerwrites.CONDITIONAL` enforces the campaign scope on both
verbs: 481 is refused, and so is a canonical row that does not match.

WHAT THIS CHECKS BEFORE IT SENDS. Everything it can, from the provider rather
than from local state, and it refuses on any surprise:

    the campaign is 485 and its name is the one we derived
    it holds EXACTLY 10 leads - `expect_leads` refuses if the provider
      disagrees, because a canary meant for ten that finds ninety is stopped
      here rather than discovered afterwards
    the sequence is EXACTLY the 3 approved steps
    the cap is 20/day
    sender 2736 resolves and is attached after the assign
    all 30 approval fingerprints still match the copy on the records

`resume_campaign` then classifies the provider's own answer rather than
trusting a 200: `queued` is polled out, and `failed` is not "started". A resume
whose outcome is still unknown when polling runs out raises.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import approval, campaigns, providerwrites, store      # noqa: E402
from src.providers import bison                                 # noqa: E402

CAMPAIGN_ID = "productive-email-control-v2"
PROVIDER_ID = 485
SENDER_ID = 2736
EXPECT_LEADS = 10
EXPECT_STEPS = 3
EXPECT_CAP = 20
APPROVAL_MARK = "operator authorisation 2026-09-16"

# THE ONLY STATUS THIS MAY ACTIVATE FROM.
#
# The preflight checked the cap, the lead count, the step count and the
# approval fingerprints - and NOT the status. It therefore passed on a
# campaign reading `archived`, and would have gone on to resume it. Found
# 2026-09-16: campaigns 484 and 485 were both `paused` when written and both
# read `archived` twenty minutes later, while 481 from 2026-09-13 stayed
# `paused`.
#
# `archived` is in none of bison's known state tuples - not STARTED_STATES,
# not STARTING_STATES, not FAILED_STATES - so what `resume` does to an
# archived campaign is unmeasured. An unrecognised status is not proven safe,
# which is the same rule `heyreach.campaign_cannot_send` applies, and the
# same shape of bug that made FINISHED fall through there.
ACTIVATABLE_STATES = ("paused", "draft")


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def approval_still_matches():
    """Every approved step's fingerprint against the copy that is there now.

    An approval is a fingerprint of the words it was taken against. If the copy
    moved after approval, the approval is for a message that no longer exists -
    and this is the last moment anyone can notice before it is sent.
    """
    ok = bad = 0
    for rec in store.load():
        for contact_key, steps in (rec.get("cadence") or {}).items():
            if not isinstance(steps, dict):
                continue
            for step_key in ("em1", "em2", "em3"):
                step = steps.get(step_key) or {}
                by = str(((step.get("approval") or {}).get("by")) or "")
                if APPROVAL_MARK not in by:
                    continue
                if approval.is_approved(rec, contact_key, step_key):
                    ok += 1
                else:
                    bad += 1
    return ok, bad


def preflight():
    """Provider truth plus the approval check. Returns (facts, problems)."""
    problems = []
    facts = {}

    row = campaigns.require(CAMPAIGN_ID)
    facts["canonical"] = CAMPAIGN_ID
    facts["bound"] = row.get("bison_campaign_id")
    if str(facts["bound"]) != str(PROVIDER_ID):
        problems.append(f"row is bound to {facts['bound']!r}, not {PROVIDER_ID}")

    ws = bison.bound_workspace()
    facts["workspace"] = f"{ws.get('id')} {ws.get('name')}"

    campaign = bison.campaign(PROVIDER_ID)
    facts["status"] = campaign.get("status")
    facts["cap"] = campaign.get("max_emails_per_day")
    facts["leads"] = campaign.get("leads_count") or campaign.get("total_leads")
    facts["sent"] = campaign.get("emails_sent") or campaign.get("sent") or 0
    if str(facts["status"] or "").lower() not in ACTIVATABLE_STATES:
        problems.append(
            f"status is {facts['status']!r}; this may only activate from "
            f"{ACTIVATABLE_STATES}. What `resume` does from "
            f"{facts['status']!r} is unmeasured, and an unrecognised status "
            f"is not proven safe")
    if facts["cap"] != EXPECT_CAP:
        problems.append(f"cap is {facts['cap']}, not {EXPECT_CAP}")
    if facts["leads"] != EXPECT_LEADS:
        problems.append(f"provider holds {facts['leads']} leads, not "
                        f"{EXPECT_LEADS} - the cohort has changed")

    steps = bison.sequence_steps(PROVIDER_ID)
    facts["steps"] = len(steps)
    if len(steps) != EXPECT_STEPS:
        problems.append(f"sequence has {len(steps)} steps, not {EXPECT_STEPS}")

    facts["senders_before"] = bison.campaign_senders(PROVIDER_ID)

    ok, bad = approval_still_matches()
    facts["approvals_matching"] = ok
    facts["approvals_stale"] = bad
    if ok != EXPECT_LEADS * EXPECT_STEPS:
        problems.append(f"{ok} approved steps match their copy, expected "
                        f"{EXPECT_LEADS * EXPECT_STEPS}")
    if bad:
        problems.append(f"{bad} approval(s) no longer match their copy")
    return facts, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="assign the sender and ACTIVATE; omit for a dry run")
    args = parser.parse_args(argv)

    facts, problems = preflight()
    print("=== PRE-ACTIVATION, PROVIDER TRUTH ===")
    for key in ("workspace", "canonical", "bound", "status", "leads", "steps",
                "cap", "sent", "senders_before", "approvals_matching",
                "approvals_stale"):
        print(f"  {key:19s}: {facts.get(key)}")
    if problems:
        print("\nREFUSED. Nothing was sent:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print("  preflight          : PASS")

    if not args.live:
        print("\nDRY RUN: every check passed and nothing was sent.")
        print("Re-run with --live to assign sender 2736 and ACTIVATE 485.")
        return 0

    # 1. THE SENDER. Through `perform`, so the campaign scope condition, the
    #    ledger and the readback all apply.
    print("\n=== 1. ASSIGN SENDER 2736 ===")
    try:
        providerwrites.perform(
            providerwrites.EMAIL_ASSIGN_SENDER,
            provider_campaign_id=str(PROVIDER_ID),
            campaign=CAMPAIGN_ID,
            tenant="productive",
            payload={"campaign_id": PROVIDER_ID, "sender_ids": [SENDER_ID]},
            transport=lambda p: bison.attach_senders(p["campaign_id"],
                                                     p["sender_ids"]),
            readback=lambda: {"senders": sorted(
                bison.campaign_senders(PROVIDER_ID))},
            expected={"senders": [SENDER_ID]},
            by="operator")
    except Exception as exc:
        print(f"  REFUSED / FAILED: {type(exc).__name__}: {exc}")
        print("  The campaign was NOT activated.")
        return 3
    attached = bison.campaign_senders(PROVIDER_ID)
    print(f"  senders now       : {attached}")
    if SENDER_ID not in (attached or []):
        print("  REFUSED: sender is not attached after the write. Not "
              "activating.")
        return 3

    # 2. ACTIVATION. `expect_leads` is the containment: resume sends to EVERY
    #    lead the campaign holds, and this refuses if the provider disagrees
    #    with the number we believe.
    print("\n=== 2. ACTIVATE CAMPAIGN 485 ===")
    try:
        providerwrites.perform(
            providerwrites.EMAIL_ACTIVATE,
            provider_campaign_id=str(PROVIDER_ID),
            campaign=CAMPAIGN_ID,
            tenant="productive",
            payload={"campaign_id": PROVIDER_ID, "expect_leads": EXPECT_LEADS},
            transport=lambda p: bison.resume_campaign(
                p["campaign_id"], expect_leads=p["expect_leads"]),
            readback=lambda: {"status": bison.campaign(PROVIDER_ID).get("status")},
            expected=None,
            by="operator")
    except Exception as exc:
        print(f"  REFUSED / FAILED: {type(exc).__name__}: {exc}")
        print("\n  READ PROVIDER TRUTH before anything else. The campaign may "
              "have started:")
        print(f"    py -3 -c \"from src.providers import bison; "
              f"print(bison.campaign({PROVIDER_ID}))\"")
        return 3

    print("\n=== 3. PROVIDER TRUTH AFTER ACTIVATION ===")
    after = bison.campaign(PROVIDER_ID)
    print(json.dumps({k: after.get(k) for k in (
        "id", "name", "status", "max_emails_per_day", "leads_count",
        "total_leads", "emails_sent", "sent")}, indent=1))
    print(f"  senders           : {bison.campaign_senders(PROVIDER_ID)}")
    print(f"  sequence steps    : {len(bison.sequence_steps(PROVIDER_ID))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
