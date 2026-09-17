#!/usr/bin/env python3
"""Reproduce 599020's audited sequence into HeyReach campaign 605732.

    py -3 scripts/install_linkedin_cohort_b_sequence.py            # dry run
    py -3 scripts/install_linkedin_cohort_b_sequence.py --live      # write it

REPRODUCED, NOT REBUILT. The graph is read off campaign 599020 - the audited
production sequence - put through `heyreach.sequence_for_write` and written
verbatim. Nothing here composes copy. This is the same path that gave 604869 a
graph identical to 599020, and the proof is the same: after the write, 605487's
sequence must hash equal to 599020's, read the same way.

SEND EXPOSURE IS ZERO. 605487 is DRAFT. A DRAFT SENDS NOTHING; a sequence is
what it WOULD send. Activation is /campaign/StartCampaign, a separate gate with
its own campaign-scoped operator authorization.

`heyreach.set_sequence` is SUPPORTED without condition. `providerwrites.perform`
still demands a readback that agrees, and this one compares the written graph to
the source with `heyreach.sequence_matches` and refuses on any difference.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import campaigns, providerwrites                      # noqa: E402
from src.providers import heyreach                             # noqa: E402
from provider_truth import heyreach_sequence_hash              # noqa: E402

CANONICAL = "productive-linkedin-cohort-v2"
SOURCE_ID = 599020          # the audited production graph
TARGET_ID = 605732
LIST_ID = 944355


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="write the sequence; omit for a dry run")
    args = parser.parse_args(argv)

    problems = []
    campaign = campaigns.require(CANONICAL)
    if int(campaign.get("heyreach_campaign_id") or 0) != TARGET_ID:
        problems.append(f"canonical row points at "
                        f"{campaign.get('heyreach_campaign_id')}, not {TARGET_ID}")

    target = heyreach.campaign_read(TARGET_ID) or {}
    status = str(target.get("status") or "").upper()
    if status != "DRAFT":
        problems.append(f"target campaign is {status!r}, not DRAFT")
    if str(target.get("linkedInUserListId")) != str(LIST_ID):
        problems.append(f"target is bound to list "
                        f"{target.get('linkedInUserListId')}, not {LIST_ID}")

    source = heyreach.campaign_sequence(SOURCE_ID)
    source_hash = heyreach_sequence_hash(source)
    write_shape = heyreach.sequence_for_write(source)
    nodes, words = heyreach.validate_sequence_for_write(write_shape)

    print("=== SOURCE, PROVIDER TRUTH ===")
    print(f"  source campaign   : {SOURCE_ID}")
    print(f"  source hash       : {source_hash}")
    print(f"  write shape       : {nodes} nodes, {words} word-bearing")
    print("=== TARGET, PROVIDER TRUTH ===")
    print(f"  target campaign   : {target.get('id')}")
    print(f"  status            : {status}")
    print(f"  bound list        : {target.get('linkedInUserListId')}")
    print(f"  seats             : {target.get('campaignAccountIds')}")

    if problems:
        print("\nREFUSED. Nothing was written:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print("  preflight         : PASS")
    print("  send exposure     : ZERO (target is DRAFT)")

    if not args.live:
        print("\nDRY RUN: nothing was written.")
        return 0

    def _transport(payload):
        return heyreach.set_sequence(payload["campaign_id"],
                                     payload["sequence"])

    def _readback():
        found = heyreach.campaign_sequence(TARGET_ID)
        same, _why = heyreach.sequence_matches(found, write_shape)
        return {"matches": same, "hash": heyreach_sequence_hash(found)}

    try:
        providerwrites.perform(
            providerwrites.LINKEDIN_SET_SEQUENCE,
            provider_campaign_id=str(TARGET_ID),
            campaign=CANONICAL, tenant="productive",
            payload={"campaign_id": TARGET_ID, "sequence": write_shape},
            transport=_transport, readback=_readback,
            expected={"matches": True, "hash": source_hash}, by="operator")
    except Exception as exc:
        print(f"\nREFUSED / FAILED: {type(exc).__name__}: {exc}")
        print("\n  READ PROVIDER TRUTH before any retry - HeyReach may have "
              "written the sequence:")
        print(f"    py -3 -c \"from src.providers import heyreach; "
              f"print(heyreach.campaign_sequence({TARGET_ID}))\"")
        return 3

    after = _readback()
    print("\n=== AFTER THE WRITE ===")
    print(f"  target hash       : {after['hash']}")
    print(f"  source hash       : {source_hash}")
    print(f"  identical graph   : {after['hash'] == source_hash}")
    print(f"  matches source    : {after['matches']}")
    return 0 if after["hash"] == source_hash and after["matches"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
