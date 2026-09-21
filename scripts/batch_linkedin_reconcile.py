#!/usr/bin/env python3
"""Finish the LinkedIn side from provider truth, not from what we meant to do.

    py -3 scripts/batch_linkedin_reconcile.py --plan
    py -3 scripts/batch_linkedin_reconcile.py --live

## WHY A RECONCILER AND NOT A RE-RUN

The build ran three times and each attempt got further before a provider
contract stopped it:

    1  list name over 50 characters      nothing created
    2  rows pre-formatted in provider
       shape, which the adapter refuses  33 lists created
    3  campaign names already taken,
       which the duplicate guard caught  33 campaigns created, leads landed

So the estate now holds 33 lists carrying 151 leads and 33 DRAFT campaigns
with one seat each - and no sequence on any of them. A fourth `--live` run
would refuse at the first create and change nothing, because every creating
verb here is correctly idempotent-by-refusal.

**What is missing is the step the third run never reached.** This script
reads what exists, does only that step, and writes back. It creates nothing.

## WHAT IT DOES

    set_sequence      the standard graph cloned from 565765, per campaign,
                      read back and compared on node shape by the adapter
    write-back        campaign_id_linkedin and linkedin_list_id per contact,
                      matched by the same deterministic round-robin the
                      build used

It does NOT activate. `heyreach.activate` names campaign 604869 and nothing
else, so these 33 stay DRAFT and no connection request can be issued.
"""
import argparse
import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import batch_linkedin_push as build                              # noqa: E402
from src import providers, store                                 # noqa: E402
from src.providers import heyreach, load_env                     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = "RESONATE PRODUCTIVE LI B1 SEAT "
PACE = 0.4


def provider_state():
    """(seat -> campaign row, seat -> list row), from the provider."""
    campaigns, _total = heyreach.campaigns()
    lists = heyreach.lists()
    lists = lists[0] if isinstance(lists, tuple) else lists
    by_campaign, by_list = {}, {}
    for row in campaigns:
        name = str(row.get("name") or "")
        if name.startswith(PREFIX):
            by_campaign[name[len(PREFIX):].strip()] = row
    for row in lists:
        name = str(row.get("name") or "")
        if name.startswith(PREFIX):
            by_list[name[len(PREFIX):].strip()] = row
    return by_campaign, by_list


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)

    load_env()
    by_campaign, by_list = provider_state()
    print(f"\nLINKEDIN RECONCILE  campaigns {len(by_campaign)}  "
          f"lists {len(by_list)}\n")

    leads_on_lists = sum(int(r.get("totalItemsCount") or 0)
                         for r in by_list.values())
    need_sequence = []
    for seat, campaign in sorted(by_campaign.items()):
        try:
            sequence = heyreach.campaign_sequence(campaign["id"])
            has = bool(sequence and sequence.get("nodeType"))
        except Exception:                                       # noqa: BLE001
            has = False
        if not has:
            need_sequence.append((seat, campaign))
    print(f"  leads sitting on the lists   {leads_on_lists}")
    print(f"  campaigns without a sequence {len(need_sequence)} "
          f"of {len(by_campaign)}")
    print(f"  every campaign is DRAFT and heyreach.activate names 604869 "
          f"only, so none of them can send")

    if not args.live:
        print("\n  PLAN ONLY.")
        return 0

    graph = build.standard_graph()
    done = []
    with providers.allow_writes(
            "LinkedIn side reconcile - set the cloned standard sequence on "
            "campaigns the build created; no creates, no activation"):
        for seat, campaign in need_sequence:
            try:
                time.sleep(PACE)
                heyreach.set_sequence(campaign["id"], graph)
            except Exception as exc:                            # noqa: BLE001
                print(f"  seat {seat}: sequence REFUSED "
                      f"{type(exc).__name__}: {str(exc)[:130]}")
                continue
            done.append(seat)
            print(f"  seat {seat}: sequence set on campaign {campaign['id']}")

    # WRITE-BACK, from the same deterministic allocation the build used, so
    # a contact's `campaign_id_linkedin` names the campaign its LinkedIn URL
    # actually went to rather than one we hope it did.
    seats = build.attested_seats()
    leads = build.enrolled_leads()
    plan = build.allocate(leads, seats) if leads else {}
    written = 0
    if plan:
        assignment = {}
        for seat_id, rows in plan.items():
            campaign = by_campaign.get(str(seat_id))
            listing = by_list.get(str(seat_id))
            if not campaign:
                continue
            for row in rows:
                assignment[(row["record_id"], row["contact_key"])] = (
                    campaign["id"], (listing or {}).get("id"))
        with store.transaction() as current:
            for index, record in enumerate(current):
                touched = False
                for contact in record.get("contacts") or []:
                    key = (record.get("id"), contact.get("key"))
                    if key in assignment and not contact.get(
                            "campaign_id_linkedin"):
                        campaign_id, list_id = assignment[key]
                        contact["campaign_id_linkedin"] = campaign_id
                        contact["linkedin_list_id"] = list_id
                        touched = True
                        written += 1
                if touched:
                    current[index] = record
    print(f"\n  sequences set {len(done)}")
    print(f"  contacts written back {written}")
    print("\n  ENROLLED IS NOT SENT. A DRAFT campaign has issued no "
          "connection request and sent no message.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
