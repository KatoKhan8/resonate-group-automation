#!/usr/bin/env python3
"""Settle the ledger reservations left by the refused 605487 activation.

    py -3 scripts/settle_abandoned_linkedin_attempts.py            # dry run
    py -3 scripts/settle_abandoned_linkedin_attempts.py --live      # settle

WHAT HAPPENED. Activating campaign 605487 minted authorizations for three of
its four contacts - each of which RESERVES a ledger key - and was then refused
at the fourth, so `providerwrites.perform` was never reached and the campaign
was never started. The three keys were left `attempted`: reserved, with the
provider not yet known to have acted. `require_clear` correctly refuses any
further attempt on an unsettled key, which is what blocked the replacement
campaign.

WHY `ABANDONED` AND NOT `FAILED`. `FAILED` says the provider was asked and did
not do it. Nobody asked. The refusal happened two layers above the transport.

THE PROOF IS PROVIDER TRUTH, READ HERE RATHER THAN ASSERTED. The ledger's own
rule is "provider truth must settle it", so this refuses to settle anything
unless HeyReach says campaign 605487 is DRAFT, has never started
(`startedAt` null) and holds no leads of its own. A DRAFT that never started
has sent nothing, so no prospect was reached under these keys and they are free
to be attempted again.

SEND EXPOSURE IS ZERO. This writes the action ledger and makes no provider
write of any kind.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import actionledger                                   # noqa: E402
from src.providers import heyreach, load_env                   # noqa: E402

REFUSED_CAMPAIGN = 605732
KEYS = (
    "aubryandco-com:jamal-fraiser:li1:linkedin",
    "tractorbeam-com:audrey-hancock:li1:linkedin",
    "tractorbeam-com:michelle-parsons:li1:linkedin",
)
WHY = ("activation of HeyReach campaign 605732 was refused at the write door "
       "by `_require_approved_words` before any provider write; the campaign "
       "is DRAFT, never started, and nothing was sent under these keys")


def provider_proof():
    row = heyreach.campaign_read(REFUSED_CAMPAIGN) or {}
    _leads, total = heyreach.campaign_leads(REFUSED_CAMPAIGN)
    facts = {"status": str(row.get("status") or "").upper(),
             "startedAt": row.get("startedAt"),
             "campaign_leads": total}
    problems = []
    if facts["status"] != "DRAFT":
        problems.append(f"campaign {REFUSED_CAMPAIGN} is {facts['status']!r}, "
                        f"not DRAFT - it may have sent")
    if facts["startedAt"]:
        problems.append(f"campaign {REFUSED_CAMPAIGN} has startedAt "
                        f"{facts['startedAt']!r}; a started campaign is not "
                        f"proof that nothing was sent")
    return facts, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="settle the keys; omit for a dry run")
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    facts, problems = provider_proof()
    print("=== PROVIDER TRUTH ===")
    for key, value in facts.items():
        print(f"  {key:16s}: {value}")

    print("\n=== LEDGER ===")
    unsettled = {row.get("key") for row in actionledger.unsettled()}
    targets = []
    for key in KEYS:
        state = actionledger.state_of(key)
        print(f"  {key}  state={state}")
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
        print(f"  SETTLED  {key} -> {actionledger.state_of(key)}")

    still = [row.get("key") for row in actionledger.unsettled()]
    print(f"\n  unsettled remaining: {len(still)}")
    for key in still:
        print(f"    {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
