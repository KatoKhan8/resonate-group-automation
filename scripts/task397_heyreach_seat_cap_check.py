#!/usr/bin/env python3
"""TASK-397: is any HeyReach seat over its own daily connection cap?

Read-only provider check. Every attested seat's configured cap vs what the
provider reports as actually sent this period.

## What the provider exposes

`/li_account/GetAll` returns `accountLimits.connectioRequestLimit` (the
configured daily cap) and `accountLimits.connectioRequestMax` (the plan
ceiling, 40 everywhere). NEITHER is a "sent today" counter - confirmed in
`senderinventory.py` and `test_a_configured_limit_is_not_a_remaining_count`.

`/stats/GetOverallStats` accepts `accountIds: []` and returns
`overallStats.connectionsSent` - but this is an ALL-TIME aggregate over the
named accounts, not a daily figure. With `accountIds: []` (empty) it returns
the estate-wide total.

## The gap

The provider publishes NO per-seat daily usage counter. `senderinventory`
records this as `REMAINING_UNKNOWN = "unknown"` deliberately. This script
therefore reports:

1. Every seat's configured cap (from `/li_account/GetAll`).
2. Every seat's cooldown state (the closest thing to "near cap" the provider
   offers - a seat on cooldown has exhausted its allowance for that action).
3. The estate-wide all-time connections sent (from `/stats/GetOverallStats`),
   as a cross-check, not a per-seat figure.
4. An explicit finding that per-seat daily usage is UNKNOWN and cannot be
   compared to cap.

READ-ONLY. No campaign, seat or cap modification. Nothing sent, nothing
activated.
"""
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import heyreach, load_env, request  # noqa: E402

OUT = os.path.join(ROOT, "docs", "state", "TASK397-SEAT-CAP-CHECK.json")

ENTRY_ACTION = "connectioRequestLimit"
MESSAGE_ACTION = "messageLimit"
COOLDOWN_KEYS = ("connectionRequestCooldown", "connectionNoteCooldown",
                 "inMailCooldown", "searchCooldown")


def main():
    load_env()
    base, hdr = heyreach.BASE, heyreach.headers()

    # 1. All seats with their caps
    st, data = request("POST", base + "/li_account/GetAll", hdr,
                       {"offset": 0, "limit": 100})
    if st != 200:
        print("li_account/GetAll failed: HTTP %s" % st)
        return 2
    seats = data.get("items") or []
    total = data.get("totalCount")

    # 2. Estate-wide stats (all-time, not per-seat daily)
    st2, stats_data = request("POST", base + "/stats/GetOverallStats", hdr,
                              {"campaignIds": [], "accountIds": [],
                               "timeFrom": None, "timeTo": None})
    overall = {}
    if st2 == 200:
        overall = stats_data.get("overallStats") or {}

    # 3. Per-seat analysis
    findings = []
    per_seat = []
    for s in seats:
        ident = s.get("id")
        limits = s.get("accountLimits") or {}
        cap = limits.get(ENTRY_ACTION)
        msg_cap = limits.get(MESSAGE_ACTION)
        is_active = s.get("isActive")
        auth_valid = s.get("authIsValid")
        cooldowns = {k: s.get(k) for k in COOLDOWN_KEYS}
        on_cooldown = any(cooldowns.values())
        active_campaigns = s.get("activeCampaigns") or 0

        if not is_active:
            state = "INACTIVE"
        elif not auth_valid:
            state = "AUTH_INVALID"
        else:
            state = "HEALTHY"

        # The provider exposes no per-seat daily usage figure.
        # Cooldown is the closest signal: a seat on connectionRequestCooldown
        # has hit its daily limit for that action.
        if on_cooldown and cooldowns.get("connectionRequestCooldown"):
            usage_signal = "AT_OR_OVER_CAP"
            findings.append({
                "sender_id": ident,
                "finding": "connectionRequestCooldown is active",
                "cap": cap,
                "state": state,
            })
        elif on_cooldown:
            usage_signal = "COOLDOWN_OTHER"
        else:
            usage_signal = "UNKNOWN_NO_USAGE_COUNTER"

        per_seat.append({
            "sender_id": ident,
            "state": state,
            "connection_cap": cap,
            "message_cap": msg_cap,
            "connection_max": limits.get("connectioRequestMax"),
            "active_campaigns": active_campaigns,
            "cooldowns": cooldowns,
            "on_cooldown": on_cooldown,
            "usage_signal": usage_signal,
            "daily_sent": "UNKNOWN - provider exposes no per-seat daily counter",
        })

    # 4. Summary
    healthy = [s for s in per_seat if s["state"] == "HEALTHY"]
    on_cr_cooldown = [s for s in per_seat
                      if s["cooldowns"].get("connectionRequestCooldown")]
    caps = sorted(set(s["connection_cap"] for s in per_seat
                      if s["connection_cap"] is not None))

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "source": ("HeyRead /li_account/GetAll + /stats/GetOverallStats, "
                   "read-only. Credential env var: HEYREACH_KEY."),
        "seats_total": len(seats),
        "provider_totalCount": total,
        "cap_distribution": {
            "distinct_connection_caps": caps,
            "note": ("connectioRequestLimit varies per seat; "
                     "connectioRequestMax is 40 everywhere (plan ceiling)"),
        },
        "estate_wide_stats": {
            "connectionsSent_all_time": overall.get("connectionsSent"),
            "connectionsAccepted_all_time": overall.get("connectionsAccepted"),
            "totalMessageReplies_all_time": overall.get("totalMessageReplies"),
            "uniqueLeadsContacted_all_time": overall.get(
                "uniqueLeadsContacted"),
            "note": ("All-time aggregates from /stats/GetOverallStats with "
                     "empty accountIds. NOT per-seat daily usage."),
        },
        "key_finding": {
            "per_seat_daily_usage": (
                "UNKNOWN. The HeyReach provider exposes NO per-seat daily "
                "usage counter. accountLimits.connectioRequestLimit is the "
                "CONFIGURED daily cap, not a remaining-today or sent-today "
                "figure. This was established on 2026-09-17 against 41 seats "
                "and is recorded in senderinventory.py as REMAINING_UNKNOWN."),
            "cooldown_as_signal": (
                "connectionRequestCooldown is the ONLY provider signal that "
                "a seat has reached its daily limit. It is a boolean, not a "
                "count - it says 'at or over cap' without saying how many "
                "were sent."),
            "seats_on_connection_cooldown": len(on_cr_cooldown),
            "seats_at_or_over_90_percent": (
                "CANNOT BE DETERMINED. No per-seat sent-today counter exists "
                "at the provider. The 90% threshold requires a numerator "
                "(sent) and a denominator (cap). The denominator is available; "
                "the numerator is not."),
        },
        "findings": findings,
        "per_seat": per_seat,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")

    print("TASK-397 HeyReach Seat Cap Check")
    print("=" * 50)
    print("Seats: %d total (provider says %s)" % (len(seats), total))
    print("Healthy: %d" % len(healthy))
    print("On connection cooldown (AT_OR_OVER_CAP): %d" % len(on_cr_cooldown))
    print("Distinct caps: %s" % caps)
    print()
    print("KEY FINDING:")
    print("  The provider exposes NO per-seat daily usage counter.")
    print("  Cap vs actual % CANNOT be computed.")
    print("  Cooldown is the only 'at cap' signal (boolean, not count).")
    print()
    if findings:
        print("FINDINGS (%d seats on connection cooldown):" % len(findings))
        for f in findings:
            print("  seat %s: cap=%s state=%s" % (
                f["sender_id"], f["cap"], f["state"]))
    else:
        print("No seats on connection cooldown at time of read.")
    print()
    print("written: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
