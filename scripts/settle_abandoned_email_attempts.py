#!/usr/bin/env python3
"""Settle the ledger reservations left by the refused 489 activation.

    py -3 scripts/settle_abandoned_email_attempts.py            # dry run
    py -3 scripts/settle_abandoned_email_attempts.py --live      # settle

WHAT HAPPENED, and it is a defect worth reading before it is settled.

Activating EmailBison campaign 489 minted authorizations for all five of its
contacts - each of which RESERVES a ledger key - and was then refused at gate
7, the killswitch, because `executionguard.LIVE_ACTIVATION_GRANTS` did not yet
name the canonical row. `providerwrites.perform` was never reached and the
campaign was never started.

THE FIVE KEYS WERE LEFT `attempted`, AND THAT POISONED THE CAMPAIGN AGAINST
ITSELF. `collision.staging_artifact_evidence` proves a campaign is our own
silent staging on four arms, and the fourth is "this repository's action ledger
records no unrefuted prospect-facing action against the canonical campaign".
Five unrefuted attempts is not silence. So on the NEXT attempt, campaign 489
stopped qualifying as our own staging, its five leads stopped being excluded
from the collision history, and all five contacts read TOUCHED - "loaded as a
lead, nothing sent yet" - against the very campaign that had just loaded them.

Measured 2026-09-18, in this order:

    run 1   5 authorized, refused at gate 7 (killswitch), 0 emails sent
    run 2   0 authorized, refused at gate 3 (collision), on run 1's own rows

`executionguard` puts the killswitch last and says why: "last so that a
killswitch refusal does not leave a reservation behind". It is last, and a
reservation is left behind anyway, because the reservation is taken while the
gates run rather than after all of them pass. A refused activation therefore
blocks its own retry. That is recorded in PRODUCT-GAPS.md; this script is the
settlement, not the fix.

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

WHY = (f"activation of EmailBison campaign {REFUSED_CAMPAIGN} was refused at "
       f"gate 7 (killswitch) before any provider write; the campaign is "
       f"paused, has sent nothing, and nothing was sent under these keys")


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
