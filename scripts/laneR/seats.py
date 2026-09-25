"""Lane R step 2: READ the seats. Never assume a capacity.

Rule 3 of the brief and the 2026-09-22 operator rule together:

  * a seat's daily connection limit is whatever `/li_account/GetAll` says it
    is today - lane P measured 7 of 33 under 25 and one seat that read 0 on
    2026-09-17 and 25 today;
  * where a seat is SHARED and the client's usage on it is unknown, the
    licensed rate is 10, because unknown is not room.

One provider request (two if the estate has grown past a page).
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot      # noqa: E402
import readonly  # noqa: E402

OUT = os.path.join(boot.WORKTREE, "work", "laneR")
SHARED_SEAT_RATE = 10     # operator, 2026-09-22: unknown is not room
TARGET_PER_SEAT = 25      # the figure the 825 target assumed


def main():
    os.makedirs(OUT, exist_ok=True)
    readonly.install(os.path.join(boot.PROD, "config", ".env"))
    readonly.selftest()
    print("seal: a write to StopLeadInCampaign and AddLeadsToCampaignV2 was "
          "refused before the first read.\n")

    from src.providers import heyreach
    from src import senderinventory

    seats, total = heyreach.all_li_accounts()
    print("seats returned :", len(seats), " provider totalCount:", total)

    rows = []
    for s in seats:
        state = senderinventory.li_seat_state(s)
        rows.append({
            "seat_id": s.get("id"),
            "auth_is_valid": state["auth_is_valid"],
            "is_active": state["is_active"],
            "active_campaigns": state["active_campaigns"],
            "connection_limit": state["connection_limit"],
            "connection_max": state["connection_max"],
            "message_limit": state["message_limit"],
            "health": senderinventory.li_health_of(s),
            # A TIMEZONE FIELD, IF THE PROVIDER HAS ONE. It does not, as far
            # as this repository has ever read - recorded here so the claim
            # is measured rather than remembered.
            "timezone_keys": sorted(
                k for k in s.keys() if "time" in k.lower()
                or "zone" in k.lower()),
        })

    live = [r for r in rows
            if r["auth_is_valid"] is True and r["is_active"] is True]
    print("active with valid auth :", len(live))
    print()

    limits = Counter(r["connection_limit"] for r in live)
    print("configured daily connection limit across the live seats:")
    for lim, n in sorted(limits.items(),
                         key=lambda kv: (kv[0] is None, kv[0]), reverse=True):
        print("   %-8s %d seats" % (lim, n))
    print()

    under = [r for r in live
             if isinstance(r["connection_limit"], int)
             and r["connection_limit"] < TARGET_PER_SEAT]
    unknown_limit = [r for r in live
                     if not isinstance(r["connection_limit"], int)]
    seat_arith = sum(min(TARGET_PER_SEAT, r["connection_limit"])
                     for r in live if isinstance(r["connection_limit"], int))
    rule_figure = sum(min(SHARED_SEAT_RATE, r["connection_limit"])
                      for r in live if isinstance(r["connection_limit"], int))

    print("seats that CANNOT take %d/day      : %d %s"
          % (TARGET_PER_SEAT, len(under),
             sorted(r["connection_limit"] for r in under)))
    print("seats whose limit the provider will not name: %d"
          % len(unknown_limit))
    print("sum of min(%d, seat limit)          : %d"
          % (TARGET_PER_SEAT, seat_arith))
    print("sum of min(%d, seat limit)  <- the rule : %d"
          % (SHARED_SEAT_RATE, rule_figure))
    print()

    tz = sorted({k for r in rows for k in r["timezone_keys"]})
    print("seat-row keys that mention time or zone :", tz or "NONE")
    print("  -> 'seat-local' is not resolvable from the seat row."
          if not tz else "  -> candidate timezone source found, verify it")
    print()
    print(readonly.report())

    path = os.path.join(OUT, "seats-2026-09-25.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"read_at": "2026-09-25",
                   "n_seats": len(rows), "n_live": len(live),
                   "seat_arithmetic_at_%d" % TARGET_PER_SEAT: seat_arith,
                   "rule_respecting_at_%d" % SHARED_SEAT_RATE: rule_figure,
                   "seats": rows}, fh, indent=1)
    print("\nwrote", path)


if __name__ == "__main__":
    main()
