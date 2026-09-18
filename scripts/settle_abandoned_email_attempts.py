#!/usr/bin/env python3
"""Settle a ledger reservation that was minted and never used.

    py -3 scripts/settle_abandoned_email_attempts.py            # dry run
    py -3 scripts/settle_abandoned_email_attempts.py --live      # settle

WHAT HAPPENED, and the first account of it here was WRONG.

Activating EmailBison campaign 489 took three runs on 2026-09-18:

    run A   5 contacts REFUSED at gate 7 (killswitch) - the canonical row was
            not yet in `executionguard.LIVE_ACTIVATION_GRANTS`
    run B   5 contacts AUTHORIZED, then `providerwrites.perform` raised
            `no transport supplied` - a caller bug, before the transport
    run C   0 contacts authorized, REFUSED at gate 3 (collision)

The first version of this docstring blamed run A: it said a killswitch refusal
leaves a reservation behind. **That is false.** `actionledger.reserve` runs
AFTER `gates.append("killswitch")`, so a killswitch refusal raises before any
ledger write. The record above proves it without reading the code: if run A
had left reservations, run B could not have authorized anybody, because gate 6
refuses an unsettled retry - which is exactly what run C then hit.

**The five rows came from run B, where authorize SUCCEEDED.** Each
authorization correctly reserved its key. Then `perform` raised before
reaching the provider, so nothing was sent and nothing settled the keys.

THE POISONING IS REAL AND THE MECHANISM IS THIS ONE.
`collision.staging_artifact_evidence` proves a campaign is our own silent
staging on four arms, and the fourth is "the action ledger records no
unrefuted prospect-facing action against the canonical campaign". Five
unrefuted attempts is not silence. So on run C campaign 489 stopped
qualifying, its five leads stopped being excluded from their own collision
history, and every contact read TOUCHED - "loaded as a lead, nothing sent
yet" - against the campaign that had just loaded them.

AND THE ALL-OR-NOTHING SHAPE MAKES IT ROUTINE. An activation mints one
authorization per contact and aborts if any refuses, because the campaign
emails everybody it holds or nobody. Every authorization minted before the
refusal has already reserved. `settle_abandoned_linkedin_attempts.py` exists
because HeyReach campaign 605487 hit precisely that - three of four
authorized, the fourth refused. Two channels, one defect, and it is this one
rather than the killswitch. PRODUCT-GAPS.md 44.

WHY `ABANDONED` AND NOT `FAILED`. `FAILED` says the provider was asked and did
not do it. Nobody asked. The refusal happened two layers above the transport.

THE PROOF IS PROVIDER TRUTH, READ HERE RATHER THAN ASSERTED. The ledger's own
rule is "provider truth must settle it", so this refuses to settle anything
unless EmailBison says campaign 489 is PAUSED, reports `emails_sent` 0 with
every other prospect-facing counter at zero, and holds no scheduled row that
has ever gone out. A campaign that has sent nothing reached nobody under these
keys, so they are free to be attempted again.

SEND EXPOSURE IS ZERO. This writes the action ledger and makes no provider
write of any kind.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import actionledger, campaigns                        # noqa: E402
from src.providers import bison, load_env                      # noqa: E402

CANONICAL = "productive-email-us-cohort-v1"
REFUSED_CAMPAIGN = 489
# THE KEYS ARE DERIVED, NOT LISTED, for the reason the LinkedIn version of
# this script records: a hardcoded list would put real prospect identifiers
# into tracked source, and it would settle what somebody typed rather than
# what is actually outstanding.
KEY_SUFFIX = ":em1:email"

# WHAT THE SETTLEMENT RECORDS, and it names the caller rather than a gate.
# The first version of this said "refused at gate 7 (killswitch)", which
# was wrong: the killswitch refusal never reserved anything. These keys
# come from an authorization that SUCCEEDED and was then not used, because
# `providerwrites.perform` raised before the transport.
WHY = (f"an authorization for EmailBison campaign {REFUSED_CAMPAIGN} was "
       f"minted and never used - `perform` raised before the transport - "
       f"and provider truth confirms the campaign is not sending and has "
       f"sent nothing under these keys")


def outstanding_keys():
    """Email keys still sitting at `attempted`, read from the ledger.

    ONLY `attempted`. `unresolved` means a provider was asked and the answer is
    not known, which is the opposite of abandoned, and blanket-settling it
    would destroy the one record saying the question is open. Campaign 487's
    own keys must not be touched by this: it is a live campaign with ten
    openers queued for the 23rd.
    """
    return sorted({row.get("key") for row in actionledger.unsettled()
                   if str(row.get("key") or "").endswith(KEY_SUFFIX)
                   and actionledger.state_of(row.get("key"))
                   == actionledger.ATTEMPTED})


def provider_proof():
    row = bison.campaign(REFUSED_CAMPAIGN) or {}
    facts = {"status": str(row.get("status") or "").lower(),
             "emails_sent": row.get("emails_sent"),
             "total_leads_contacted": row.get("total_leads_contacted"),
             "replied": row.get("replied"),
             "bounced": row.get("bounced"),
             "total_leads": row.get("total_leads")}
    problems = []
    if facts["status"] not in ("paused", "draft"):
        problems.append(f"campaign {REFUSED_CAMPAIGN} is {facts['status']!r}, "
                        f"not paused or draft - it may have sent")
    for field in ("emails_sent", "total_leads_contacted", "replied",
                  "bounced"):
        value = facts.get(field)
        if value is None:
            problems.append(f"the provider reports no {field}; an absent "
                            f"counter is not a zero one")
        elif int(value) != 0:
            problems.append(f"campaign {REFUSED_CAMPAIGN} reports {field}="
                            f"{value}, so something reached somebody")

    # THE QUEUE, NOT ONLY THE COUNTERS. A scheduled row carrying `sent_at`
    # is a send the campaign-level counter could in principle lag behind.
    scheduled = bison.scheduled_emails(REFUSED_CAMPAIGN)
    went_out = [r for r in scheduled if r.get("sent_at")
                or str(r.get("status") or "").lower() == "sent"]
    facts["scheduled_rows"] = len(scheduled)
    facts["rows_that_went_out"] = len(went_out)
    if went_out:
        problems.append(f"{len(went_out)} scheduled row(s) on campaign "
                        f"{REFUSED_CAMPAIGN} have already gone out")
    return facts, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="settle the keys; omit for a dry run")
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    row = campaigns.get(CANONICAL) or {}
    if str(row.get("bison_campaign_id")) != str(REFUSED_CAMPAIGN):
        raise SystemExit(
            f"REFUSED: {CANONICAL} is bound to "
            f"{row.get('bison_campaign_id')!r}, not {REFUSED_CAMPAIGN}. This "
            f"script proves its safety from ONE campaign's provider truth and "
            f"cannot vouch for another.")

    facts, problems = provider_proof()
    print("=== PROVIDER TRUTH ===")
    for key, value in facts.items():
        print(f"  {key:24s}: {value}")

    print("\n=== LEDGER ===")
    unsettled = {r.get("key") for r in actionledger.unsettled()}
    targets = []
    for key in outstanding_keys():
        state = actionledger.state_of(key)
        print(f"  ...{str(key)[-26:]}  state={state}")
        if key in unsettled:
            targets.append(key)
    if not targets:
        print("\nNothing to settle.")
        return 0
    if problems:
        print("\nREFUSED. Nothing was settled:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print(f"\n  to settle        : {len(targets)} as "
          f"{actionledger.ABANDONED}")
    print("  send exposure    : ZERO (ledger write only)")

    if not args.live:
        print("\nDRY RUN: nothing was settled.")
        return 0

    for key in targets:
        actionledger.settle(key, actionledger.ABANDONED, why=WHY,
                            provider_response=facts)
        print(f"  SETTLED  ...{str(key)[-26:]} -> "
              f"{actionledger.state_of(key)}")

    still = [r.get("key") for r in actionledger.unsettled()]
    print(f"\n  unsettled remaining: {len(still)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
