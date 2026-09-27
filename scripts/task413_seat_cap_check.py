#!/usr/bin/env python3
"""TASK-413: Per-seat HeyReach cap check — actual usage vs. configured cap.

Read-only. Two provider reads per seat:
  1. /li_account/GetAll  — configured caps (accountLimits)
  2. /stats/GetOverallStats (one call per seat, accountIds=[seat_id])
     — actual daily usage (connectionsSent, messagesSent, profileViews)

Reports any seat at or over 90% of its connection-request cap.

No provider write route is called. No campaign, seat or cap is modified.
"""
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import heyreach, load_env, request  # noqa: E402

THRESHOLD = 0.90


def main():
    load_env()
    base, hdr = heyreach.BASE, heyreach.headers()

    # Step 1: read all seats with their caps
    st, data = request("POST", base + "/li_account/GetAll", hdr,
                       {"offset": 0, "limit": 100})
    if st != 200:
        print("li_account/GetAll failed: HTTP %s" % st)
        return 2
    seats = data.get("items") or []
    total = data.get("totalCount", len(seats))
    if len(seats) != total:
        print("SHORT READ: got %d of %d seats" % (len(seats), total))
        return 2

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_key = today + "T00:00:00Z"

    rows = []
    for s in seats:
        seat_id = s.get("id")
        limits = s.get("accountLimits") or {}
        conn_max = limits.get("connectioRequestMax") or 0
        msg_max = limits.get("messageLimitMax") or 0
        pv_max = limits.get("profileViewLimitMax") or 0
        is_active = s.get("isActive")
        auth_valid = s.get("authIsValid")

        # Step 2: read this seat's actual usage today
        conn_sent = msg_sent = pv_used = None
        stats_error = None
        if is_active and auth_valid:
            try:
                st2, d2 = request("POST", base + "/stats/GetOverallStats", hdr,
                                  {"campaignIds": [], "accountIds": [seat_id],
                                   "timeFrom": None, "timeTo": None})
                if st2 == 200 and isinstance(d2, dict):
                    by_day = d2.get("byDayStats") or {}
                    today_stats = by_day.get(today_key)
                    if today_stats:
                        conn_sent = today_stats.get("connectionsSent", 0)
                        msg_sent = today_stats.get("messagesSent", 0)
                        pv_used = today_stats.get("profileViews", 0)
                    else:
                        # No data for today — seat hasn't acted yet
                        conn_sent = msg_sent = pv_used = 0
                else:
                    stats_error = "HTTP %d" % st2
            except Exception as e:
                stats_error = str(e)

        # Compute percentages
        conn_pct = (conn_sent / conn_max * 100) if (conn_max and conn_sent is not None) else None
        msg_pct = (msg_sent / msg_max * 100) if (msg_max and msg_sent is not None) else None
        pv_pct = (pv_used / pv_max * 100) if (pv_max and pv_used is not None) else None

        state = "HEALTHY"
        if not is_active:
            state = "INACTIVE"
        elif not auth_valid:
            state = "AUTH_INVALID"

        rows.append({
            "seat_id": seat_id,
            "state": state,
            "active_campaigns": s.get("activeCampaigns"),
            "conn_cap": conn_max,
            "conn_actual": conn_sent,
            "conn_pct": conn_pct,
            "msg_cap": msg_max,
            "msg_actual": msg_sent,
            "msg_pct": msg_pct,
            "pv_cap": pv_max,
            "pv_actual": pv_used,
            "pv_pct": pv_pct,
            "stats_error": stats_error,
            "cooldown_conn": s.get("connectionRequestCooldown"),
            "cooldown_msg": s.get("connectionNoteCooldown"),
        })

    # Report
    print("=" * 90)
    print("TASK-413: HeyReach Seat Cap Check — %s" % today)
    print("READ-ONLY. No campaign, seat or cap modified.")
    print("=" * 90)
    print()
    print("Seats: %d total, %d healthy, %d auth_invalid, %d inactive" % (
        len(seats),
        sum(1 for r in rows if r["state"] == "HEALTHY"),
        sum(1 for r in rows if r["state"] == "AUTH_INVALID"),
        sum(1 for r in rows if r["state"] == "INACTIVE"),
    ))
    print()

    # Per-seat table
    print("%-8s %-12s %-5s %-6s %-6s %-6s %-6s %-6s %-6s %-6s" % (
        "seat_id", "state", "camp", "c_cap", "c_act", "c_%",
        "m_cap", "m_act", "m_%", "err"))
    print("-" * 90)
    for r in rows:
        c_pct = "%d%%" % r["conn_pct"] if r["conn_pct"] is not None else "n/a"
        m_pct = "%d%%" % r["msg_pct"] if r["msg_pct"] is not None else "n/a"
        c_act = str(r["conn_actual"]) if r["conn_actual"] is not None else "-"
        m_act = str(r["msg_actual"]) if r["msg_actual"] is not None else "-"
        err = r["stats_error"] or ""
        print("%-8s %-12s %-5s %-6s %-6s %-6s %-6s %-6s %-6s %-6s" % (
            r["seat_id"], r["state"], r["active_campaigns"],
            r["conn_cap"], c_act, c_pct,
            r["msg_cap"], m_act, m_pct,
            err))

    # Findings: seats at or over 90%
    print()
    print("=" * 90)
    print("FINDINGS: Seats at or over 90%% of connection-request cap")
    print("=" * 90)
    flagged = [r for r in rows
               if r["conn_pct"] is not None and r["conn_pct"] >= THRESHOLD * 100]
    if flagged:
        for r in flagged:
            print("  SEAT %s: %d/%d connection requests (%.1f%%) — state=%s, campaigns=%d" % (
                r["seat_id"], r["conn_actual"], r["conn_cap"],
                r["conn_pct"], r["state"], r["active_campaigns"]))
    else:
        print("  NONE — no seat is at or over 90%% of its connection-request cap today.")

    # Also flag message cap
    print()
    print("=" * 90)
    print("FINDINGS: Seats at or over 90%% of message cap")
    print("=" * 90)
    msg_flagged = [r for r in rows
                   if r["msg_pct"] is not None and r["msg_pct"] >= THRESHOLD * 100]
    if msg_flagged:
        for r in msg_flagged:
            print("  SEAT %s: %d/%d messages (%.1f%%) — state=%s, campaigns=%d" % (
                r["seat_id"], r["msg_actual"], r["msg_cap"],
                r["msg_pct"], r["state"], r["active_campaigns"]))
    else:
        print("  NONE — no seat is at or over 90%% of its message cap today.")

    # Write JSON for the record
    out_path = os.path.join(ROOT, "docs", "state", "TASK-413-SEAT-CAP-CHECK.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "date": today,
        "source": "HeyReach /li_account/GetAll + /stats/GetOverallStats (per-seat), read-only",
        "threshold_pct": THRESHOLD * 100,
        "seats_total": len(seats),
        "seats_flagged_connection": len(flagged),
        "seats_flagged_message": len(msg_flagged),
        "seats": rows,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    print()
    print("Written: %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
