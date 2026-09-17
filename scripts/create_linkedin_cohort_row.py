#!/usr/bin/env python3
"""Canonical Resonate OS campaign row for HeyReach campaign 605487.

    py -3 scripts/create_linkedin_cohort_row.py            # dry run
    py -3 scripts/create_linkedin_cohort_row.py --live      # write the row

SEND EXPOSURE IS ZERO. This writes `work/campaigns.jsonl` only. It makes no
provider call except the read-only preflight that proves 605487 is the DRAFT
we think it is.

WHY THE ROW EXISTS AT ALL. `providerwrites.perform` refuses a prospect-facing
verb without an `executionguard.Authorization`, and `authorize()` refuses
without a CURRENT campaign-level approval. That approval binds the senders,
the limits, the provider binding, the tenant and the LEAD SET by fingerprint.
No canonical row means no fingerprint means no activation - the row is the
thing the operator's approval is attached to.

SHAPE COPIED FROM productive-linkedin-canary-v1, deliberately, field for
field: same client, same daily_volume, same seat, same org_unit, same
provider_delays, same provider_actions, same provider_note. Only the id, the
name, the record ids, the bound list and the provider campaign id differ. The
sequence those provider_* fields describe is the graph reproduced from 599020,
so describing it any other way would be describing a different campaign.

THE ROW IS CREATED IN `draft`. Approval is a separate, operator-attributed
step through `orchestrator.decide`, never by hand-setting `approval`.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib                                                # noqa: E402

from src import campaigns, liststaging, orchestrator, store   # noqa: E402
from src.providers import heyreach                            # noqa: E402

CANONICAL = "productive-linkedin-cohort-v1"
PROVIDER_ID = 605487
LIST_ID = 943957
SEAT_ID = 174892
ORG_UNIT = 118832
NAME = "RESONATE - PRODUCTIVE LINKEDIN COHORT V1 - CONTROL"
EXPECT_LEADS = 4

# THE COHORT IS NAMED BY PROFILE HASH, NOT BY DOMAIN. Writing the three real
# client domains here put them in tracked source and `tests/test_fixture_
# hygiene.py` caught it. Hashes identify the same people without publishing
# who they are, and they are the same identifiers the staging and activation
# scripts already use, so the three scripts agree by construction.
COHORT_PROFILE_HASHES = {"6acd6d9f031b", "4684b25b0372",
                         "c01f0c88111c", "4258f756357d"}

# Copied from productive-linkedin-canary-v1. These describe the graph that is
# reproduced from 599020 - not a shape chosen here.
PROVIDER_DELAYS = [["DAY", 1]]
PROVIDER_NOTE = "{connection_note}"
PROVIDER_ACTIONS = ["CHECK_IS_CONNECTION", "MESSAGE", "VIEW_PROFILE", "END",
                    "FOLLOW", "CONNECTION_REQUEST"]


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def cohort_record_ids(recs=None):
    """The records holding the cohort, resolved from state by profile hash.

    Refuses rather than guessing: if the four hashes do not resolve to
    records, the row would name the wrong people and there is nothing safe to
    write.
    """
    recs = store.load() if recs is None else recs
    found, seen = [], set()
    for rec in recs:
        for contact in rec.get("contacts") or []:
            url = liststaging.canonical_profile_url(contact.get("linkedin"))
            if url and h12(url.lower()) in COHORT_PROFILE_HASHES:
                seen.add(h12(url.lower()))
                if rec["id"] not in found:
                    found.append(rec["id"])
    missing = COHORT_PROFILE_HASHES - seen
    return sorted(found), sorted(missing)


def preflight():
    problems, facts = [], {}
    row = heyreach.campaign_read(PROVIDER_ID) or {}
    facts["provider_campaign"] = row.get("id")
    facts["status"] = str(row.get("status") or "").upper()
    facts["bound_list"] = row.get("linkedInUserListId")
    facts["seats"] = row.get("campaignAccountIds") or []
    if facts["status"] != "DRAFT":
        problems.append(f"campaign {PROVIDER_ID} is {facts['status']!r}, "
                        f"not DRAFT")
    if str(facts["bound_list"]) != str(LIST_ID):
        problems.append(f"campaign is bound to list {facts['bound_list']}, "
                        f"not {LIST_ID}")
    if SEAT_ID not in facts["seats"]:
        problems.append(f"seat {SEAT_ID} is not attached")

    _members, total = heyreach.list_leads(LIST_ID)
    facts["audience"] = total
    if total != EXPECT_LEADS:
        problems.append(f"list {LIST_ID} holds {total} lead(s), expected "
                        f"{EXPECT_LEADS}")
    record_ids, missing = cohort_record_ids()
    facts["record_ids"] = record_ids
    if missing:
        problems.append(f"cohort profile hash(es) resolve to no record: "
                        f"{missing}")
    if campaigns.get(CANONICAL):
        problems.append(f"canonical row {CANONICAL} already exists")
    return facts, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="write the canonical row; omit for a dry run")
    args = parser.parse_args(argv)

    facts, problems = preflight()
    print("=== PROVIDER TRUTH ===")
    for key in ("provider_campaign", "status", "bound_list", "seats",
                "audience", "record_ids"):
        print(f"  {key:18s}: {facts.get(key)}")
    if problems:
        print("\nREFUSED. No row was written:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print("  preflight         : PASS")
    print(f"  canonical id      : {CANONICAL}")
    print("  send exposure     : ZERO (this writes canonical state only)")

    if not args.live:
        print("\nDRY RUN: no row was written.")
        return 0

    with campaigns.transaction() as rows:
        campaign = orchestrator.create(
            CANONICAL, "productive", NAME,
            record_ids=cohort_record_ids()[0],
            created_by="operator", rows=rows)
        campaign["daily_volume"] = {"email": 0, "linkedin": 20}
        campaign["senders"] = {"email": [],
                               "linkedin": [{"provider_account_id": SEAT_ID}]}
        campaign["heyreach_campaign_id"] = PROVIDER_ID
        campaign["heyreach_list_id"] = LIST_ID
        campaign["org_unit"] = ORG_UNIT
        campaign["provider_status_expected"] = "DRAFT"
        campaign["provider_delays"] = PROVIDER_DELAYS
        campaign["provider_note"] = PROVIDER_NOTE
        campaign["provider_actions"] = PROVIDER_ACTIONS

    written = campaigns.require(CANONICAL)
    print(f"\n=== WROTE {CANONICAL} ===")
    print(json.dumps({k: written.get(k) for k in (
        "campaign_id", "client", "name", "status", "record_ids",
        "daily_volume", "senders", "heyreach_campaign_id", "heyreach_list_id",
        "org_unit", "provider_delays", "provider_actions")}, indent=1))
    print("\nStatus is `draft`. Approval is a separate operator-attributed "
          "step; activation is a gate again after that.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
