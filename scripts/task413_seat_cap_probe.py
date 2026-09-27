#!/usr/bin/env python3
"""TASK-413 probe: does HeyReach expose per-seat actual usage vs. cap?

Read-only. Two questions:
1. What fields does accountLimits actually carry? (Is there a usage field?)
2. Does /stats/GetOverallStats return per-seat breakdowns when accountIds
   are passed?

Writes nothing to any provider.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import heyreach, load_env, request  # noqa: E402


def main():
    load_env()
    base, hdr = heyreach.BASE, heyreach.headers()

    # Question 1: raw accountLimits structure for the first 3 seats
    st, data = request("POST", base + "/li_account/GetAll", hdr,
                       {"offset": 0, "limit": 100})
    if st != 200:
        print("li_account/GetAll failed: HTTP %s" % st)
        return 2
    seats = data.get("items") or []
    print("=== Q1: accountLimits fields (first 3 seats) ===")
    for s in seats[:3]:
        print(f"\nSeat {s.get('id')}:")
        print(f"  All keys: {sorted(s.keys())}")
        limits = s.get("accountLimits") or {}
        print(f"  accountLimits keys: {sorted(limits.keys())}")
        print(f"  accountLimits values: {json.dumps(limits, indent=4)}")

    # Question 2: does /stats/GetOverallStats accept accountIds for per-seat?
    # Try with one specific seat
    if seats:
        seat_id = seats[0].get("id")
        print(f"\n=== Q2: /stats/GetOverallStats for seat {seat_id} ===")
        st2, data2 = request("POST", base + "/stats/GetOverallStats", hdr,
                             {"campaignIds": [], "accountIds": [seat_id],
                              "timeFrom": None, "timeTo": None})
        print(f"  HTTP {st2}")
        if st2 == 200:
            print(f"  Response keys: {sorted(data2.keys()) if isinstance(data2, dict) else type(data2)}")
            print(f"  Full response: {json.dumps(data2, indent=2)[:2000]}")

    # Question 3: try with ALL account ids to see if it returns per-seat breakdown
    all_ids = [s.get("id") for s in seats[:5]]
    print(f"\n=== Q3: /stats/GetOverallStats for seats {all_ids} ===")
    st3, data3 = request("POST", base + "/stats/GetOverallStats", hdr,
                         {"campaignIds": [], "accountIds": all_ids,
                          "timeFrom": None, "timeTo": None})
    print(f"  HTTP {st3}")
    if st3 == 200:
        print(f"  Response: {json.dumps(data3, indent=2)[:2000]}")

    # Question 4: try with a campaign we know is live (605732) + accountIds
    print(f"\n=== Q4: /stats/GetOverallStats for campaign 605732, seat {seat_id} ===")
    st4, data4 = request("POST", base + "/stats/GetOverallStats", hdr,
                         {"campaignIds": [605732], "accountIds": [seat_id],
                          "timeFrom": None, "timeTo": None})
    print(f"  HTTP {st4}")
    if st4 == 200:
        print(f"  Response: {json.dumps(data4, indent=2)[:2000]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
