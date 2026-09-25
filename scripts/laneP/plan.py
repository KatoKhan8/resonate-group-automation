#!/usr/bin/env python3
"""LANE P: turn verified LinkedIn-only candidates into an enrollment plan the
FOREGROUND can execute. This process writes to no provider.

WHAT THE PLAN CONTAINS, per cohort and per seat
-----------------------------------------------
  * the campaign name, <=50 chars, unique, carrying all five cohort tags
  * the list name (HeyReach lists are permanent - no delete verb)
  * the lead rows in `heyreach.build_lead_pairs` shape, first/last name
    present, profile url canonical - a lead missing either is dropped by the
    provider with a 200 and no error
  * the schedule, which can ONLY be set at create: `set_schedule` is refused
    by this repo because no route reads a schedule back, so the window is a
    creation-time decision or it is the provider's Mon-Fri 09:00-17:00 UTC
    default that nobody chose
  * the expected readback, so the foreground can prove the write landed

THE RATE. Measured, not assumed:
  - 33 seats are active with valid auth (41 exist, 34 active, 33 auth-valid)
  - their CONFIGURED `connectioRequestLimit` is 40 on 20 seats, 25 on 6, and
    15/15/17/18/19/22/23 on the remaining 7. So 25-per-seat is NOT uniformly
    available: min(25, limit) over the 33 sums to 779, not 825.
  - every one of the 33 also carries 8-14 of the CLIENT's IN_PROGRESS
    campaigns. Zero seats are exclusively ours. The standing operator rule of
    2026-09-22 is explicit about that case: "where the client's usage on a
    shared seat is UNKNOWN, the rate is 10 - unknown is not room."
So this plan is built at 10 per seat per day and reports what 25 would need.
"""
import argparse
import collections
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402
import cohort  # noqa: E402

DAY_FLAGS = ("enabledMonday", "enabledTuesday", "enabledWednesday",
             "enabledThursday", "enabledFriday", "enabledSaturday",
             "enabledSunday")
# 07:00-23:00, seven days. The timezone is named per cohort below.
WINDOW = {"dailyStartTime": "07:00", "dailyEndTime": "23:00"}
SEQUENCE_SOURCE = "config/linkedin/productive-standard.json"

# Seat 174810 is inside the 33 live campaigns but the 2026-09-17 capacity
# audit excludes it as UNATTESTED - its address is on the client's own
# corporate domain. An attestation conflict is not a seat to start a new
# cohort on, so it is held back and named rather than silently used.
ATTESTATION_HELD = {"174810"}


def ref(value):
    return hashlib.sha1(str(value).encode()).hexdigest()[:6].upper()


def split_name(row):
    first = str(row.get("first_name") or "").strip()
    last = str(row.get("last_name") or "").strip()
    if first and last:
        return first, last
    parts = str(row.get("name") or "").split()
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return first or (parts[0] if parts else ""), last


def seats_available():
    seats = json.load(open(os.path.join(boot.OUT, "heyreach_seats.json"),
                           encoding="utf-8"))["seats"]
    usable = []
    for s in seats:
        if not (s["active"] and s["auth_valid"]):
            continue
        limit = (s["limits"] or {}).get("connectioRequestLimit") or 0
        usable.append({"seat_id": str(s["id"]), "configured_limit": limit,
                       "held": str(s["id"]) in ATTESTATION_HELD})
    usable.sort(key=lambda s: (s["held"], -s["configured_limit"],
                               s["seat_id"]))
    return usable


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--verified", nargs="+",
                    default=["verified_top3.json", "verified_all.json"])
    ap.add_argument("--rate", type=int, default=10,
                    help="leads per seat per day. 10 is what a SHARED seat "
                         "licenses; 25 is what the operator asked for")
    ap.add_argument("--day", default="D1")
    args = ap.parse_args(argv)

    rows, seen = [], set()
    for name in args.verified:
        path = os.path.join(boot.OUT, name)
        if not os.path.exists(path):
            continue
        for row in json.load(open(path, encoding="utf-8"))["rows"]:
            key = (row["record_id"], row["contact_key"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    passed = [r for r in rows if r.get("verdict") == "linkedin_only"]
    by_cell = collections.defaultdict(list)
    for r in passed:
        by_cell[tuple(r["cell"])].append(r)

    seats = seats_available()
    free = [s for s in seats if not s["held"]]
    cohorts, seat_at = [], 0
    for cell, members in sorted(by_cell.items(), key=lambda kv: -len(kv[1])):
        if str(cell[0]) == "untagged":
            continue
        staged, dropped = [], []
        for m in members:
            first, last = split_name(m)
            if not (first and last and m.get("profile_url")):
                dropped.append({"contact_ref": ref(m["contact_key"]),
                                "why": "firstName/lastName required - the "
                                       "provider drops the lead with a 200"})
                continue
            staged.append({
                "record_id": m["record_id"],
                "contact_key": m["contact_key"],
                "first_name": first, "last_name": last,
                "company": m.get("company"), "title": m.get("title"),
                "linkedin_url": m["profile_url"],
                "client": "productive",
            })
        if not staged:
            continue
        timezone = (members[0].get("timezone") or "Europe/London")
        chunks = [staged[i:i + args.rate]
                  for i in range(0, len(staged), args.rate)]
        campaigns = []
        for chunk in chunks:
            if seat_at >= len(free):
                break
            seat = free[seat_at]
            seat_at += 1
            name = cohort.cohort_name(cell, seat["seat_id"], args.day)
            campaigns.append({
                "campaign_name": name,
                "list_name": name,
                "seat_id": seat["seat_id"],
                "seat_configured_connection_limit": seat["configured_limit"],
                "leads": chunk,
                "lead_count": len(chunk),
                "schedule": dict(WINDOW, timeZoneId=timezone,
                                 **{d: True for d in DAY_FLAGS}),
                "sequence_source": SEQUENCE_SOURCE,
                "expected_readback": {
                    "campaign_read.status": "DRAFT after create",
                    "campaign_read.campaignAccountIds": [int(seat["seat_id"])],
                    "list_leads count": len(chunk),
                    "campaigns_for_lead(profile) after enroll":
                        "1 campaign, this one, leadStatus Pending",
                    "store write-back": "contacts[].campaign_id_linkedin, "
                                        "linkedin_list_id AND heyreach_lead_id "
                                        "- ISSUE-041: the cross-channel stop "
                                        "is gated on the last one and zero "
                                        "contacts carry it",
                },
            })
        cohorts.append({
            "cohort_tags": {"geo": cell[0], "industry_group": cell[1],
                            "headcount_band": cell[2], "persona": cell[3],
                            "signal_state": cell[4]},
            "timezone": timezone,
            "members_passed": len(members),
            "members_stageable": len(staged),
            "dropped_before_staging": dropped,
            "campaigns": campaigns,
        })

    plan = {
        "lane": "P",
        "reads_only": True,
        "rate_per_seat_per_day": args.rate,
        "seats_total_active_auth_valid": len(seats),
        "seats_held_for_attestation": [s["seat_id"] for s in seats
                                       if s["held"]],
        "cohorts": cohorts,
        "enrolled_if_executed": sum(c["lead_count"] for co in cohorts
                                    for c in co["campaigns"]),
    }
    with open(os.path.join(boot.OUT, "ENROLLMENT-PLAN.json"), "w",
              encoding="utf-8") as f:
        json.dump(plan, f, indent=1)

    print(json.dumps({
        "candidates_verified": len(rows),
        "passed_linkedin_only": len(passed),
        "cohorts": [{"tags": c["cohort_tags"], "stageable":
                     c["members_stageable"],
                     "campaigns": [{"name": x["campaign_name"],
                                    "seat": x["seat_id"],
                                    "leads": x["lead_count"]}
                                   for x in c["campaigns"]]}
                    for c in cohorts],
        "enrolled_if_executed": plan["enrolled_if_executed"],
    }, indent=1))


if __name__ == "__main__":
    main()
