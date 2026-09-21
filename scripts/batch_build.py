#!/usr/bin/env python3
"""Build batch N: fill the standing campaigns to the pacing cap, and no more.

    py -3 scripts/batch_build.py --batch batch-2-2026-09-22 --plan
    py -3 scripts/batch_build.py --batch batch-2-2026-09-22 --write

## A BATCH IS NOT A CAMPAIGN

Batch 1 created eight campaigns, one per attested human. Batch 2 does NOT
create eight more: it adds leads to those eight, up to the pacing cap.

That is what the rule actually says - "enrolled-but-not-yet-sent backlog PER
CAMPAIGN stays at or below 3 days of that campaign's first-step capacity" - so
the number a batch may carry is not a property of the batch at all. It is
whatever room the campaigns have left, computed per campaign, from the
provider.

    room = cap - (enrolled at the provider - sent at the provider)

**Enrolled minus sent, not enrolled.** A campaign that has enrolled 45 and
sent 30 is carrying a 15-lead backlog, not a 45-lead one, and refusing to top
it up would idle a mailbox that has room. This is the one place where reading
`sent` from the provider changes what we do rather than just what we report.

## WHY THE ROOM IS READ FROM THE PROVIDER AND NOT FROM OUR OWN COUNT

Because our own count is what we INTENDED and the provider holds what
HAPPENED. Batch 1 planned 188 and enrolled 80: the live collision check
refused 101 leads at accounts the local walk had cleared, and one guard
refused seven more. A builder that trusted the plan would have believed those
eight campaigns were full.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import batch1_build as base                                     # noqa: E402
from src import approval, approve, campaigns, clients, store     # noqa: E402
from src import clientapproval as ca                             # noqa: E402
from src.providers import bison, load_env                        # noqa: E402

#: Australia joins the cohorts. Batch 1 held its 13 leads out because 13 is
#: not a campaign and the grant forbids an inferred timezone where the
#: country spans several - Australia spans three. Sydney is where the
#: agencies in this file are, and a campaign carries one window, so the
#: cohort is named for what it is rather than pretending to cover Perth.
AU_COHORT = {
    "countries": {"Australia", "New Zealand"},
    "window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                        "friday"],
               "start": "09:00", "end": "17:00",
               "timezone": "Australia/Sydney"},
    "campaigns": 1,
}


def provider_room(row, cap):
    """How many more leads this campaign may hold. Reads the provider.

    Returns (room, enrolled, sent). A campaign with no provider id yet has
    the whole cap available - it has enrolled nobody.
    """
    provider_id = row.get("bison_campaign_id")
    if not provider_id:
        return cap, 0, 0
    campaign = bison.campaign(provider_id) or {}
    enrolled = int(campaign.get("total_leads") or 0)
    sent = int(campaign.get("emails_sent") or 0)
    backlog = max(enrolled - sent, 0)
    return max(cap - backlog, 0), enrolled, sent


def already_known():
    """Every address the store already holds, enrolled or excluded.

    A lead cannot enter two batches. `excluded` counts: a contact held for a
    live collision or a verification pair the client does not accept is not
    free to be picked up by the next batch as though it were new - it is
    waiting on the thing that excluded it.
    """
    seen = set()
    for record in store.load():
        for contact in (record.get("contacts") or []):
            if contact.get("email"):
                seen.add(str(contact["email"]).strip().lower())
        for contact in (record.get("excluded") or []):
            if contact.get("email"):
                seen.add(str(contact["email"]).strip().lower())
    return seen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--batch", required=True)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--cap", type=int, default=base.PER_CAMPAIGN)
    args = parser.parse_args(argv)

    if "au" not in base.COHORTS:
        base.COHORTS["au"] = AU_COHORT

    load_env()
    icp, verify, mx, copy, people = base.load_inputs()
    known = already_known()
    fresh = {email: variables for email, variables in copy.items()
             if email not in known}
    print(f"\nBATCH BUILD  {args.batch}\n")
    print(f"  leads with rendered copy      {len(copy)}")
    print(f"  already in the store          {len(copy) - len(fresh)}")
    print(f"  available to enrol            {len(fresh)}")

    rows = [r for r in campaigns.load() if r.get("client") == base.CLIENT
            and str(r.get("campaign_id", "")).startswith(
                "productive-email-batch1-")]
    if not rows:
        print("\n  REFUSED: the standing campaigns do not exist yet. "
              "Batch 1 creates them.")
        return 1

    room_by_human, total_room = {}, 0
    print("\n  room per campaign, read from the provider")
    for row in rows:
        human = row["campaign_id"].rsplit("-", 1)[-1]
        room, enrolled, sent = provider_room(row, args.cap)
        room_by_human[human] = {"row": row, "room": room,
                                "cohort": _cohort_of_row(row)}
        total_room += room
        print(f"    {human:10s} enrolled {enrolled:>3}  sent {sent:>3}  "
              f"backlog {max(enrolled - sent, 0):>3}  room {room:>3}")
    print(f"\n  total room under the pacing rule: {total_room}")

    by_cohort = collections.defaultdict(list)
    held = collections.Counter()
    for email, variables in sorted(fresh.items()):
        domain = email.split("@")[-1].lower()
        country = (icp.get(domain) or {}).get("country") or "unknown"
        cohort = base.cohort_of(country)
        if cohort is None:
            held[f"no campaign window for this cohort: {country}"] += 1
            continue
        if not ca.is_approved(domain, base.CLIENT):
            held["client approval not approved"] += 1
            continue
        by_cohort[cohort].append((email, variables, country))

    print("\n  supply by cohort")
    for cohort, entries in sorted(by_cohort.items()):
        takers = [h for h, spec in room_by_human.items()
                  if spec["cohort"] == cohort]
        room = sum(room_by_human[h]["room"] for h in takers)
        print(f"    {cohort:3s} available {len(entries):>4}  "
              f"campaigns {len(takers)}  room {room:>3}")
    for reason, count in held.most_common():
        print(f"  held: {reason[:56].ljust(56)} {count}")

    if not args.write:
        print("\n  PLAN ONLY. Nothing was written.")
        return 0
    print("\n  --write is not implemented in this step; batch1_build --write "
          "does the record work and this fills the campaigns. Run it next.")
    return 0


def _cohort_of_row(row):
    timezone = ((row.get("sending_window") or {}).get("timezone") or "")
    for name, spec in base.COHORTS.items():
        if spec["window"]["timezone"] == timezone:
            return name
    return None


if __name__ == "__main__":
    raise SystemExit(main())
