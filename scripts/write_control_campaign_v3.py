#!/usr/bin/env python3
"""Create the EmailBison CONTROL campaign and write its sequence. Authorized.

    py -3 scripts/write_control_campaign_v3.py            # dry run, sends nothing
    py -3 scripts/write_control_campaign_v3.py --live     # perform the write

WHY THIS FILE EXISTS. Claude Code's auto-mode classifier denies every write
from Claude's session - provider calls and local state alike. It is a harness
control, not a Resonate OS gate, and not something to work around. The operator
authorized this write in writing (OPERATOR-AUTHORIZATION-2026-09-16.md), so it
is packaged as one reviewed command.

ORDER MATTERS. Run this AFTER the approval:

    1  py -3 scripts/apply_control_approval.py --live   10 contacts, 30 steps
    2  py -3 scripts/write_control_campaign_v3.py --live   this file
    3  read the provider back (this file does it, and prints it)

Step 1 first because `bisonfactory._ensure_leads` refuses a campaign whose
steps are not approved, and because an approval taken AFTER a sequence write
is an approval against copy the provider already has.

WHAT THIS DOES, AND WHERE IT STOPS. `bisonfactory.stage` creates the campaign
through `providerwrites.perform` with `EMAIL_CREATE_CAMPAIGN`, caps it, writes
the schedule, writes the CONTROL sequence with `EMAIL_SET_SEQUENCE`, stops it,
and then adds leads. Both write verbs are in `SUPPORTED`. It stops before
ACTIVATION, because `bison.activate` is not in `SUPPORTED` and enabling it is
the narrow operator decision in `docs/ACTIVATION-DECISION-2026-09-16.md`.

THE FACT THAT GOVERNS RETRIES. `bison.set_sequence` APPENDS rather than
replaces - proven against a fake in TASK-184, measured against the provider on
2026-09-13. A second write leaves the campaign carrying CONTROL twice, which
once leads are added is a prospect receiving six messages instead of three. The
brake is `_ensure_sequence`, which reads the provider's current steps first and
refuses on a mismatch. **If this script fails partway, do NOT re-run it.**
Read `bison.sequence_steps(provider_id)`: empty means safe to write, three
correct steps means it is already done, six means the append trap fired and the
campaign must be rebuilt.

CAMPAIGN 481 IS NOT THE DESTINATION. It holds 23 people with 6 to 40
historical touches each under a five-step non-CONTROL sequence (TASK-174).
`bison.set_sequence` is authorized on the stated grounds that a sequence
written onto a campaign holding nobody reaches nobody, and 481 holds somebody.
This creates a new campaign.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import bisonfactory, campaigns, store                 # noqa: E402

CAMPAIGN_ID = "productive-email-control-v3"
HUMAN_NAME = "RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - CONTROL V3"
CLIENT = "productive"
DAILY_EMAILS = 20
SENDER_ID = 2736


# THE CAMPAIGN CARRIES ITS OWN CADENCE, and v1 is abandoned rather than fixed.
#
# 484 was created from a client cadence with FIVE email steps, so it holds five
# provider steps. `bison.set_sequence` APPENDS - no replace, no per-step delete
# - so a three-step sequence can never be written onto it: `_ensure_sequence`
# reads the five held steps, sees they are not the three wanted, and refuses.
# Correctly. 484 is draft, holds nobody and has sent nothing, so it is
# harmless; it is simply unusable for CONTROL.
#
# `cadence.steps_for` resolves a campaign's own `cadence_steps` BEFORE the
# client's named cadence, so declaring it here scopes CONTROL to this campaign
# instead of changing what any other campaign runs.
CONTROL_CADENCE = [
    {"key": "em1", "day": 1, "channel": "email", "template": "persona_pain"},
    {"key": "em2", "day": 4, "channel": "email", "template": "comparable_proof"},
    {"key": "em3", "day": 8, "channel": "email", "template": "breakup"},
]


def ensure_row():
    """The local campaign row `stage` needs. Local state only, no provider."""
    with campaigns.transaction() as rows:
        existing = campaigns.get(CAMPAIGN_ID, rows)
        if existing:
            return existing, False
        row = campaigns.new_campaign(CAMPAIGN_ID, CLIENT, HUMAN_NAME,
                                     created_by="operator")
        row["daily_volume"] = {"email": DAILY_EMAILS, "linkedin": 0}
        row["cadence_steps"] = [dict(s) for s in CONTROL_CADENCE]
        # THE SENDER IS NAMED BEFORE `stage()` RUNS, AND THAT IS THE WHOLE
        # REASON THIS FILE EXISTS SEPARATELY FROM v2.
        #
        # EmailBison ARCHIVES a campaign that has no sending account attached.
        # Four for four across this workspace: 451 (sender 3948) completed, 481
        # (2736, 2737) paused, 484 (none) archived ~6 minutes after creation,
        # 485 (none) archived ~10 minutes after creation. Nothing in this
        # repository archives anything - there is no archive route and no
        # campaign DELETE in `bison.WRITE_ROUTES` - and 481 received the same
        # call sequence and survived. The difference is the ABSENCE of
        # attach-sender-emails.
        #
        # `_ensure_senders` deliberately no-ops on an empty row, because
        # "choosing an inbox would be choosing who a prospect hears from". That
        # is the right default and it is also a window this provider measures
        # in minutes, so the operator's choice is recorded here rather than
        # left for someone to make later.
        row["senders"] = {"email": [{"provider_account_id": str(SENDER_ID),
                                     "account_id": f"eb-{SENDER_ID}"}],
                          "linkedin": []}
        rows.append(row)
    return campaigns.require(CAMPAIGN_ID), True


def approved_cohort():
    """Record ids whose em1-em3 carry the 2026-09-16 operator approval.

    Read from live state rather than from a list in this file, so a cohort
    that moved is visible instead of assumed.
    """
    marker = "operator authorisation 2026-09-16"
    out = []
    for rec in store.load():
        cadence = rec.get("cadence") or {}
        for contact_key, steps in cadence.items():
            if not isinstance(steps, dict):
                continue
            approved = 0
            for step_key in ("em1", "em2", "em3"):
                by = ((steps.get(step_key) or {}).get("approval") or {}).get("by")
                if by and marker in str(by):
                    approved += 1
            if approved == 3:
                out.append((rec["id"], contact_key))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="perform the write; omit for a dry run")
    parser.add_argument("--with-leads", action="store_true",
                        help="put the approved cohort on the campaign row "
                             "before staging, so stage() attaches them")
    args = parser.parse_args(argv)

    cohort = approved_cohort()
    print(f"approved cohort   {len(cohort)} contacts with all three CONTROL "
          f"steps approved 2026-09-16")
    if not cohort:
        print("\nREFUSED: no contact carries the 2026-09-16 operator "
              "approval on em1, em2 and em3.")
        print("Run this first:  py -3 scripts/apply_control_approval.py --live")
        return 2
    if len(cohort) != 10:
        print(f"\nWARNING: expected 10, found {len(cohort)}. The cohort has "
              f"moved since it was approved - check before continuing.")

    row, created = ensure_row()
    print(f"campaign row      {CAMPAIGN_ID} "
          f"({'created' if created else 'already present'})")
    print(f"derived name      {bisonfactory.provider_campaign_name(row)}")
    print(f"daily cap         {DAILY_EMAILS} emails")
    print(f"bison_campaign_id {row.get('bison_campaign_id')}")

    if args.with_leads:
        with campaigns.transaction() as rows:
            target = campaigns.get(CAMPAIGN_ID, rows)
            target["record_ids"] = sorted({rid for rid, _ck in cohort})
        row = campaigns.require(CAMPAIGN_ID)
        print(f"record_ids        {len(row['record_ids'])} set on the row")
    else:
        print("record_ids        [] - campaign will be created EMPTY. Re-run "
              "with --with-leads to attach the cohort.")

    try:
        report = bisonfactory.stage(CAMPAIGN_ID, live=bool(args.live),
                                    by="operator")
    except Exception as exc:
        print(f"\nREFUSED / FAILED: {type(exc).__name__}: {exc}")
        print("\nIf a campaign WAS created before this failed, do NOT re-run. "
              "Read the provider first:")
        print("  py -3 -c \"from src.providers import bison; "
              "print(bison.sequence_steps(<provider_id>))\"")
        return 3

    print("\n--- what stage() did ---")
    for line in report.get("did") or []:
        print(f"  {line}")
    provider = report.get("provider") or {}
    if provider:
        print(f"\nprovider campaign id  {provider.get('campaign_id')}")
        print(f"provider name         {provider.get('name')}")
        readback = provider.get("readback")
        if readback:
            print("\n--- PROVIDER READBACK ---")
            print(json.dumps(readback, indent=1)[:1800])
    if not args.live:
        print("\nDRY RUN: nothing was sent.")
        print("Re-run with --live (and --with-leads when you want the cohort "
              "attached) to perform the authorized write.")
    else:
        print("\nWritten. The campaign is STOPPED and cannot send: "
              "bison.activate is not in SUPPORTED. See "
              "docs/ACTIVATION-DECISION-2026-09-16.md for the narrow "
              "activation decision.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
