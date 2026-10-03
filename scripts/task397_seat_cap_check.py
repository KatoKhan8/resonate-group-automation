#!/usr/bin/env python3
"""TASK-397 — HeyReach seat cap check.

READ-ONLY. Calls POST /li_account/GetAll and reports each seat's configured
daily cap (connectioRequestLimit) against what the provider exposes about
actual usage today.

The provider exposes NO used-today or remaining-today counter. This was
established on 2026-09-17 across 41 seats and is recorded in
src/senderinventory.py:170-200. The seat row has 15 keys and accountLimits
12 numbers; none is a used-today figure.

So this script reports:
- Each seat's configured cap (connectioRequestLimit)
- Each seat's plan ceiling (connectioRequestMax)
- Cooldown flags (the only volatile provider-side signal)
- Active campaign count (shared capacity indicator)
- Health classification

Any seat at connectioRequestLimit == 0 is flagged: it cannot send connection
requests at all. Any seat on cooldown is flagged as degraded.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import heyreach, load_env, request  # noqa: E402


def classify(seat):
    if not seat.get("isActive"):
        return "INACTIVE"
    if not seat.get("authIsValid"):
        return "AUTH_INVALID"
    return "HEALTHY"


def main():
    load_env()
    base, hdr = heyreach.BASE, heyreach.headers()

    # Page through all seats
    all_seats = []
    offset = 0
    page_size = 100
    while True:
        st, data = request("POST", base + "/li_account/GetAll", hdr,
                           {"offset": offset, "limit": page_size})
        if st != 200:
            print("ERROR: li_account/GetAll returned HTTP %s" % st)
            return 2
        items = data.get("items") or []
        all_seats.extend(items)
        total = data.get("totalCount", 0)
        if len(all_seats) >= total or not items:
            break
        offset += len(items)

    print("=" * 80)
    print("TASK-397: HeyReach Seat Cap Check")
    print("READ-ONLY: POST /li_account/GetAll, %d seats returned, totalCount %d"
          % (len(all_seats), total))
    print("=" * 80)
    print()

    # Per-seat table
    print("%-8s %-12s %-6s %-6s %-6s %-6s %-10s %-12s %s" % (
        "seat_id", "health", "limit", "max", "msg_lim", "active", "cooldown", "at_cap?", "notes"))
    print("-" * 100)

    findings = []
    summary = {"total": len(all_seats), "healthy": 0, "auth_invalid": 0,
               "inactive": 0, "zero_limit": 0, "on_cooldown": 0,
               "at_or_over_90pct": 0}

    for s in all_seats:
        state = classify(s)
        limits = s.get("accountLimits") or {}
        cr_limit = limits.get("connectioRequestLimit")
        cr_max = limits.get("connectioRequestMax")
        msg_limit = limits.get("messageLimit")
        active_camps = s.get("activeCampaigns") or 0

        cooldowns = {
            "cr": s.get("connectionRequestCooldown"),
            "note": s.get("connectionNoteCooldown"),
            "inmail": s.get("inMailCooldown"),
            "search": s.get("searchCooldown"),
        }
        on_cooldown = any(v for v in cooldowns.values())
        cooldown_str = ",".join(k for k, v in cooldowns.items() if v) or "-"

        if state == "HEALTHY":
            summary["healthy"] += 1
        elif state == "AUTH_INVALID":
            summary["auth_invalid"] += 1
        else:
            summary["inactive"] += 1

        # Flag zero-limit seats
        notes = []
        if cr_limit == 0:
            summary["zero_limit"] += 1
            notes.append("ZERO_LIMIT: cannot send connection requests")
            findings.append("Seat %d: connectioRequestLimit=0, cannot send ANY "
                            "connection requests" % s.get("id"))

        if on_cooldown:
            summary["on_cooldown"] += 1
            notes.append("ON_COOLDOWN: %s" % cooldown_str)

        if state == "AUTH_INVALID":
            notes.append("DEAD_CREDENTIAL: authIsValid=false")
            findings.append("Seat %d: AUTH_INVALID - isActive=%s but credential "
                            "is dead" % (s.get("id"), s.get("isActive")))

        # The provider exposes NO used-today counter.
        # We cannot compute actual/% from provider data.
        # What we CAN say about approaching limits:
        # - connectioRequestLimit == connectioRequestMax means no throttle applied
        # - connectioRequestLimit < connectioRequestMax means the operator has
        #   throttled this seat below the plan ceiling
        # - cooldown flags are the only provider-side signal of recent activity
        at_cap = "-"
        if isinstance(cr_limit, int) and isinstance(cr_max, int) and cr_max > 0:
            pct = (cr_limit / cr_max) * 100
            at_cap = "%d%%" % pct
            if pct >= 90:
                summary["at_or_over_90pct"] += 1

        print("%-8s %-12s %-6s %-6s %-6s %-6s %-10s %-12s %s" % (
            s.get("id"), state,
            cr_limit if cr_limit is not None else "?",
            cr_max if cr_max is not None else "?",
            msg_limit if msg_limit is not None else "?",
            active_camps,
            cooldown_str,
            at_cap,
            "; ".join(notes) if notes else "-"))

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("Total seats:        %d" % summary["total"])
    print("  HEALTHY:          %d" % summary["healthy"])
    print("  AUTH_INVALID:     %d" % summary["auth_invalid"])
    print("  INACTIVE:         %d" % summary["inactive"])
    print("Zero limit (can't send CR): %d" % summary["zero_limit"])
    print("On cooldown:        %d" % summary["on_cooldown"])
    print("Limit >= 90%% of max: %d" % summary["at_or_over_90pct"])
    print()

    # The central finding about actual usage
    print("=" * 80)
    print("CRITICAL: PROVIDER EXPOSES NO USED-TODAY COUNTER")
    print("=" * 80)
    print("The HeyReach API does not expose a 'sent today' or 'remaining today'")
    print("counter for any seat. The seat row has 15 keys and accountLimits has")
    print("12 numbers; none is a used-today or remaining-today figure.")
    print()
    print("This was established on 2026-09-17 across 41 seats and is recorded in")
    print("src/senderinventory.py:170-200 (CONNECTION_LIMIT / CONNECTION_MAX /")
    print("REMAINING_UNKNOWN).")
    print()
    print("connectioRequestLimit is a CONFIGURED SETTING, not a remaining counter.")
    print("It was byte-identical across 32 seats over 4 days (2026-09-13 to")
    print("2026-09-17) while cooldown flags moved - which is what a setting looks")
    print("like beside something genuinely volatile.")
    print()
    print("Therefore a per-seat 'cap vs actual vs %' table CANNOT be produced")
    print("from provider data. The 'actual' column does not exist at the API.")
    print()

    if findings:
        print("=" * 80)
        print("FINDINGS (%d)" % len(findings))
        print("=" * 80)
        for i, f in enumerate(findings, 1):
            print("  %d. %s" % (i, f))
    else:
        print("No material findings beyond the structural limitation above.")

    print()
    print("=" * 80)
    print("COOLDOWN SEATS (the only volatile provider-side activity signal)")
    print("=" * 80)
    cooldown_seats = [s for s in all_seats
                      if any(s.get(k) for k in ("connectionRequestCooldown",
                                                "connectionNoteCooldown",
                                                "inMailCooldown",
                                                "searchCooldown"))]
    if cooldown_seats:
        for s in cooldown_seats:
            flags = [k for k in ("connectionRequestCooldown",
                                 "connectionNoteCooldown",
                                 "inMailCooldown", "searchCooldown")
                     if s.get(k)]
            limits = s.get("accountLimits") or {}
            print("  Seat %d: health=%s, limit=%s/%s, cooldowns: %s" % (
                s.get("id"), classify(s),
                limits.get("connectioRequestLimit"),
                limits.get("connectioRequestMax"),
                ", ".join(flags)))
    else:
        print("  No seats on cooldown at this read.")

    # Write machine-readable output
    out_path = os.path.join(ROOT, "docs", "state", "TASK397-SEAT-CAP-CHECK.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    seat_rows = []
    for s in all_seats:
        limits = s.get("accountLimits") or {}
        cooldowns = {k: bool(s.get(k)) for k in
                     ("connectionRequestCooldown", "connectionNoteCooldown",
                      "inMailCooldown", "searchCooldown")}
        seat_rows.append({
            "sender_id": s.get("id"),
            "health": classify(s),
            "is_active": s.get("isActive"),
            "auth_is_valid": s.get("authIsValid"),
            "connection_limit": limits.get("connectioRequestLimit"),
            "connection_max": limits.get("connectioRequestMax"),
            "message_limit": limits.get("messageLimit"),
            "active_campaigns": s.get("activeCampaigns"),
            "cooldowns": cooldowns,
            "on_cooldown": any(cooldowns.values()),
        })

    doc = {
        "task": "TASK-397",
        "source": "POST /li_account/GetAll, read-only",
        "seats_total": len(all_seats),
        "summary": summary,
        "provider_exposes_used_today": False,
        "provider_exposes_remaining_today": False,
        "finding": ("The HeyReach API exposes no used-today or remaining-today "
                    "counter. connectioRequestLimit is a configured setting, not "
                    "a remaining counter. A cap-vs-actual-vs-% table cannot be "
                    "produced from provider data."),
        "findings_text": findings,
        "seats": seat_rows,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    print()
    print("Written: %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
