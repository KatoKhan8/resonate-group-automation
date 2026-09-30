#!/usr/bin/env python3
"""TASK-397 — per-seat HeyReach seat cap check.

Read-only. Calls `/li_account/GetAll` for the configured cap per seat,
reads the action ledger for our own actions today, and uses `seatledger`
for the per-seat verdict.

THE KEY FINDING this script is built around:

    HeyReach exposes NO used-today or remaining-today counter.
    `connectioRequestLimit` is the CONFIGURED daily cap, not remaining.
    `connectioRequestMax` is always 40 and is the plan ceiling.
    Neither is a "sent this period" figure.

So the "actual" column in the table below is our own action count from
the action ledger — a LOWER BOUND. The provider's own total usage per
seat per day is UNOBSERVABLE from any read route.
"""

import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import heyreach, load_env, request  # noqa: E402
from src import seatledger, actionledger  # noqa: E402


def main():
    load_env()
    base, hdr = heyreach.BASE, heyreach.headers()

    # --- Real provider read: /li_account/GetAll ---
    st, data = request("POST", base + "/li_account/GetAll", hdr,
                       {"offset": 0, "limit": 100})
    if st != 200:
        print(f"FAIL: /li_account/GetAll returned HTTP {st}")
        return 2
    seats = data.get("items") or []
    total_count = data.get("totalCount", len(seats))
    if len(seats) < total_count:
        print(f"WARNING: got {len(seats)} of {total_count} seats (paging)")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # --- Action ledger: our own actions today ---
    try:
        ledger_rows = actionledger.load()
    except (FileNotFoundError, OSError):
        ledger_rows = []

    # --- Provider truth for exclusivity check ---
    provider_truth = seatledger._load_provider_truth()
    exclusive = seatledger._is_exclusive(provider_truth)
    attested = seatledger._attested_seats(provider_truth)

    # --- Build the per-seat table ---
    findings = []
    table = []
    for s in seats:
        sid = str(s.get("id"))
        limits = s.get("accountLimits") or {}
        cap = limits.get("connectioRequestLimit")
        ceiling = limits.get("connectioRequestMax")
        is_active = s.get("isActive")
        auth_valid = s.get("authIsValid")
        active_campaigns = s.get("activeCampaigns", 0)

        # Our actions today from the action ledger
        ours = actionledger.count_on(
            today, channel="linkedin", sender_id=sid, rows=ledger_rows)

        # seatledger verdict
        sl = seatledger.daily(sid, today, rows=ledger_rows,
                              provider_truth=provider_truth)

        # Cooldown flags
        cooldowns = {k: s.get(k) for k in
                     ("connectionRequestCooldown", "connectionNoteCooldown",
                      "inMailCooldown", "searchCooldown")}
        any_cooldown = any(cooldowns.values())

        # Percentage: ours / cap. Cap of 0 means cannot send at all.
        if cap and isinstance(cap, (int, float)) and cap > 0:
            pct = round(100.0 * ours / cap, 1)
        elif cap == 0:
            pct = None  # configured at 0, cannot send
        else:
            pct = None

        row = {
            "seat_id": sid,
            "is_active": is_active,
            "auth_valid": auth_valid,
            "active_campaigns": active_campaigns,
            "configured_cap": cap,
            "plan_ceiling": ceiling,
            "our_actions_today": ours,
            "pct_of_cap": pct,
            "seatledger_verdict": sl["verdict"],
            "seatledger_reason": sl["reason"],
            "cooldown_active": any_cooldown,
            "in_roster": sid in attested,
        }
        table.append(row)

        # Flag seats at or over 90% of cap
        if pct is not None and pct >= 90:
            findings.append(
                f"SEAT {sid}: {ours}/{cap} ({pct}%) of daily connection cap "
                f"(our actions from ledger)")

    # --- Report ---
    print(f"TASK-397 — HeyReach seat cap check, {today}")
    print(f"Provider read: /li_account/GetAll, {len(seats)} of {total_count} seats")
    print(f"Workspace exclusive: {exclusive}")
    print(f"Attested seats in provider truth: {len(attested)}")
    print()

    # Summary
    healthy = [r for r in table if r["is_active"] and r["auth_valid"]]
    blocked = [r for r in table if not r["auth_valid"]]
    inactive = [r for r in table if not r["is_active"] and r["auth_valid"]]
    at_cap = [r for r in table if r["pct_of_cap"] is not None and r["pct_of_cap"] >= 90]
    zero_cap = [r for r in table if r["configured_cap"] == 0]

    print(f"Total seats: {len(table)}")
    print(f"  Healthy (active + auth valid): {len(healthy)}")
    print(f"  Blocked (auth invalid): {len(blocked)}")
    print(f"  Inactive: {len(inactive)}")
    print(f"  At or over 90% of cap (our actions): {len(at_cap)}")
    print(f"  Configured cap = 0: {len(zero_cap)}")
    print()

    # Full per-seat table
    print(f"{'seat_id':>10} {'active':>6} {'auth':>5} {'camps':>5} "
          f"{'cap':>4} {'ceil':>4} {'ours':>5} {'pct':>6} {'verdict':>8} "
          f"{'cool':>5} {'roster':>6}")
    print("-" * 95)
    for r in sorted(table, key=lambda x: (not x["is_active"],
                                          not x["auth_valid"],
                                          x["seat_id"])):
        pct_str = f"{r['pct_of_cap']}%" if r['pct_of_cap'] is not None else "n/a"
        cool_str = "YES" if r["cooldown_active"] else "-"
        roster_str = "yes" if r["in_roster"] else "no"
        print(f"{r['seat_id']:>10} {str(r['is_active']):>6} "
              f"{str(r['auth_valid']):>5} {r['active_campaigns']:>5} "
              f"{r['configured_cap']:>4} {r['plan_ceiling']:>4} "
              f"{r['our_actions_today']:>5} {pct_str:>6} "
              f"{r['seatledger_verdict']:>8} {cool_str:>5} {roster_str:>6}")

    print()

    # Findings
    if findings:
        print("FINDINGS — seats at or over 90% of configured cap:")
        for f in findings:
            print(f"  ** {f}")
    else:
        print("FINDINGS — none: no seat is at or over 90% of its configured "
              "cap based on our action ledger.")

    print()
    print("IMPORTANT CAVEAT:")
    print("  HeyReach exposes NO used-today or remaining-today counter.")
    print("  `connectioRequestLimit` is the CONFIGURED daily cap, not remaining.")
    print("  `connectioRequestMax` is always 40 (plan ceiling).")
    print("  The 'ours' column is our action ledger count — a LOWER BOUND.")
    print("  The client's usage on shared seats is UNOBSERVABLE.")
    print("  seatledger reports REFUSED on shared seats for this reason.")

    # Write JSON output
    out_path = os.path.join(ROOT, "docs", "state",
                            "TASK-397-SEAT-CAP-CHECK.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "task": "TASK-397",
        "source": ("HeyReach /li_account/GetAll (read-only) + action ledger "
                   "+ seatledger"),
        "date": today,
        "total_seats": len(table),
        "healthy": len(healthy),
        "blocked": len(blocked),
        "at_or_over_90_pct": len(at_cap),
        "findings": findings,
        "provider_exposes_sent_today": False,
        "seats": table,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    print(f"\nWritten: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
