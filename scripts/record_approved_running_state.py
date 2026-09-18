#!/usr/bin/env python3
"""Canonical state still says these campaigns are drafts. They are running.

    py -3 scripts/record_approved_running_state.py            # dry run
    py -3 scripts/record_approved_running_state.py --live      # write + approve

ZERO SEND EXPOSURE. It writes `work/campaigns.jsonl` and takes an approval. No
provider write of any kind; the only provider calls are the read-only ones that
establish what each campaign is actually doing.

THE DEFECT. `configdiff` builds the approved side's `status` from the row's
`provider_status_expected`, defaulting to `paused` when absent. Both rows were
written while their campaigns were drafts and neither was updated when the
operator activated them:

    productive-email-control-v3     row None -> "paused"   provider "active"
    productive-linkedin-cohort-v2   row "DRAFT"            provider "IN_PROGRESS"

So `compare_bison` and `compare_heyreach` FAIL on `status` for both live
campaigns, and that readback is what `executionguard.authorize` requires. Every
future authorization on either channel would be refused - not because anything
is wrong, but because canonical state never recorded a decision the operator
had already made.

WHY THIS IS NOT "MAKE THE GATE AGREE WITH THE PROVIDER". Writing whatever the
provider currently reports would make the comparison tautological: the approved
side would be defined by the thing it is supposed to check, and a campaign
somebody else started would read as approved. What is written here is the state
the operator APPROVED each campaign to be in - running - which happens to match
the provider today and would NOT match a campaign that had been paused,
finished or archived behind our backs. That difference is the whole value of
the field.

So the expected value is a constant per channel, not a copy of the read, and
the script REFUSES if the provider is in any state other than the one being
recorded. A campaign that has stopped is a thing to look at, not a value to
write down.

AND THE APPROVAL MOVES WITH IT. `campaigns.fingerprint` covers the row, so
changing this field stales the approval that authorized activation. It is
retaken through `orchestrator.decide` in the same pass - never by hand, because
the fingerprint binding is the point.
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import campaigns, clients, configdiff, orchestrator, store  # noqa
from src.providers import bison, heyreach, load_env                  # noqa

# The state each channel's campaign was APPROVED to be in, and the provider
# word for it. Constants, not reads - see the docstring.
TARGETS = [
    {"canonical": "productive-email-control-v3", "channel": "email",
     "provider_id": 487, "expected": "active"},
    {"canonical": "productive-linkedin-cohort-v2", "channel": "linkedin",
     "provider_id": 605732, "expected": "IN_PROGRESS"},
    # ADDED 2026-09-18. Campaign 489, the five-contact US cohort, activated
    # under the operator's 2026-09-18 authorization and confirmed `active` by
    # provider read-back.
    #
    # ITS ROW WAS WRITTEN `paused` DELIBERATELY AND THIS IS THE FLIP. The
    # read-back that `executionguard.authorize` requires is taken BEFORE
    # activation, when the campaign is legitimately still paused, so a row
    # that said `active` at that moment made `configdiff` FAIL on `status`
    # alone - 14 checks, one failure, and that one failure refuses the
    # activation it was written to permit. Recording the running state is
    # therefore a step that happens AFTER the provider confirms, which is what
    # this script is for.
    {"canonical": "productive-email-us-cohort-v1", "channel": "email",
     "provider_id": 489, "expected": "active"},
]


def approver():
    who = subprocess.run(["git", "config", "user.email"],
                         capture_output=True, text=True).stdout.strip()
    if not who:
        raise SystemExit("REFUSED: git config user.email is unset, so the "
                         "approval would be attributed to nobody.")
    return who


def provider_status(target):
    if target["channel"] == "email":
        return str((bison.campaign(target["provider_id"]) or {}).get("status")
                   or "")
    return str((heyreach.campaign_read(target["provider_id"]) or {}).get(
        "status") or "")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="write the rows and retake the approvals")
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))
    config = clients.load("productive")
    recs = store.load()

    problems, plan = [], []
    print("=== WHAT THE ROW SAYS vs WHAT THE CAMPAIGN IS DOING ===")
    for target in TARGETS:
        row = campaigns.get(target["canonical"])
        if row is None:
            problems.append(f"no canonical row {target['canonical']!r}")
            continue
        stored = row.get("provider_status_expected")
        live = provider_status(target)
        print(f"  {target['canonical']:32s} row={stored!r:10s} "
              f"provider={live!r}")
        if live != target["expected"]:
            problems.append(
                f"{target['canonical']}: provider reads {live!r} and this "
                f"script only records {target['expected']!r}. A campaign that "
                f"has stopped is a thing to look at, not a value to write down")
            continue
        if stored == target["expected"]:
            print(f"      already recorded; nothing to write")
            continue
        plan.append(target)

    if problems:
        print("\nREFUSED. Nothing was written:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    if not plan:
        print("\nNothing to do.")
        return 0
    print(f"\n  to record : {[t['canonical'] for t in plan]}")
    print("  exposure  : ZERO (canonical state and one approval each)")

    if not args.live:
        print("\nDRY RUN: no row was written and no approval taken.")
        return 0

    who = approver()
    failed = []
    for target in plan:
        name = target["canonical"]
        print(f"\n=== {name} ===")
        with campaigns.transaction() as rows:
            row = campaigns.get(name, rows)
            row["provider_status_expected"] = target["expected"]
        campaign = campaigns.require(name)
        print(f"  recorded              : {target['expected']!r}")

        fingerprint = campaigns.fingerprint(campaign, recs, config)
        if campaigns.is_approved(campaign, recs, config):
            print("  approval              : still current, unchanged")
        else:
            with campaigns.transaction() as rows:
                orchestrator.decide(
                    campaigns.get(name, rows), who, "approve",
                    fingerprint=fingerprint,
                    interaction_id="operator-authz-2026-09-17-running-state",
                    config=config, recs=recs, role="admin")
            campaign = campaigns.require(name)
            print(f"  approval              : retaken, {fingerprint}")
        if not campaigns.is_approved(campaign, recs, config):
            print("  REFUSED: approval not current after retaking it")
            failed.append(name)
            continue

        compare = (configdiff.compare_bison if target["channel"] == "email"
                   else configdiff.compare_heyreach)
        readback = compare(campaign, recs=recs, config=config)
        diff = readback.diff or {}
        print(f"  readback verdict      : {diff.get('verdict')}")
        for failure in (diff.get("failures") or [])[:6]:
            print(f"    {failure[:130]}")
        if diff.get("verdict") != configdiff.PASS:
            failed.append(name)
    return 0 if not failed else 4


if __name__ == "__main__":
    raise SystemExit(main())
