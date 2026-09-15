#!/usr/bin/env python3
"""What the LinkedIn sender estate can safely carry, read from the provider.

## The question this answers

"Given the currently healthy sender estate, how quickly can a cohort move
through its cadence?" - and its inverse, which is the one that actually
decides whether to build another campaign: **is throughput limited by
senders, or by something else?**

On 2026-09-15 the answer was "something else". Campaign 599020 had ONE sender
attached and ZERO leads while 33 healthy seats sat idle. Capacity was never
the constraint; approval and copy quality were.

## What is and is not a limit

`accountLimits` is what the PROVIDER is configured to allow per seat per day.
It is not a measurement of what was sent, and it is not a promise LinkedIn
will tolerate it. Two rules follow and neither may be traded for volume:

- **Never raise a limit to increase throughput.** Add senders or add days.
  A raised limit is a change to the risk taken with a client's real LinkedIn
  account, and it is not an engineering decision.
- **A seat that is `isActive` but whose `authIsValid` is false is NOT
  capacity.** It will accept an assignment and then fail, which is worse than
  being absent because the leads sit queued behind it looking scheduled.

READ-ONLY. Writes nothing to any provider.

## PII

A seat is a real person. Names, emails and profile URLs are hashed; the id,
the health flags and the numeric limits are what planning needs and are all
that is persisted.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import heyreach, load_env, request  # noqa: E402

OUT = os.path.join(ROOT, "docs", "state", "SENDER-CAPACITY.json")

# The action that opens a LinkedIn cadence. Connection-request throughput is
# what decides how fast a cold cohort can START, so it is the headline number;
# message limit governs how fast an ACCEPTED cohort can be worked.
ENTRY_ACTION = "connectioRequestLimit"      # provider's spelling, kept verbatim
MESSAGE_ACTION = "messageLimit"


def h(value):
    v = " ".join(str(value or "").split()).lower()
    return hashlib.sha256(v.encode("utf-8")).hexdigest()[:12] if v else None


def classify(seat):
    """Three states, deliberately not two. 'Cannot be used' and 'is not
    configured' are different problems with different owners."""
    if not seat.get("isActive"):
        return "INACTIVE"
    if not seat.get("authIsValid"):
        # Looks available, fails on use. The dangerous middle state.
        return "AUTH_INVALID"
    return "HEALTHY"


def main():
    load_env()
    base, hdr = heyreach.BASE, heyreach.headers()
    st, data = request("POST", base + "/li_account/GetAll", hdr,
                       {"offset": 0, "limit": 100})
    if st != 200:
        print("li_account/GetAll failed: HTTP %s (env var HEYREACH_KEY)" % st)
        return 2
    seats = data.get("items") or []

    rows, totals = [], {"HEALTHY": 0, "AUTH_INVALID": 0, "INACTIVE": 0}
    entry_cap = msg_cap = 0
    for s in seats:
        state = classify(s)
        totals[state] += 1
        limits = s.get("accountLimits") or {}
        entry = limits.get(ENTRY_ACTION) or 0
        msg = limits.get(MESSAGE_ACTION) or 0
        if state == "HEALTHY":
            entry_cap += entry
            msg_cap += msg
        rows.append({
            "sender_id": s.get("id"),
            "provider": "heyreach",
            "identity_hash": h("%s %s|%s" % (s.get("firstName"), s.get("lastName"),
                                             s.get("emailAddress"))),
            "state": state,
            "is_active": s.get("isActive"),
            "auth_is_valid": s.get("authIsValid"),
            "active_campaigns": s.get("activeCampaigns"),
            "daily_connection_requests": entry,
            "daily_messages": msg,
            "daily_profile_views": limits.get("profileViewLimit"),
            "sales_navigator": s.get("isValidNavigator"),
            # Cooldowns are the provider's own throttle. Present here so a
            # planner cannot quietly assume a seat is instantly reusable.
            "cooldowns": {
                "connection_request": s.get("connectionRequestCooldown"),
                "connection_note": s.get("connectionNoteCooldown"),
                "inmail": s.get("inMailCooldown"),
                "search": s.get("searchCooldown"),
            },
        })

    unassigned = [r for r in rows
                  if r["state"] == "HEALTHY" and not r["active_campaigns"]]

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "HeyReach li_account/GetAll, read-only. Credential env var: HEYREACH_KEY.",
        "seats_total": len(seats),
        "seats_by_state": totals,
        "healthy_seats": totals["HEALTHY"],
        "healthy_seats_with_no_active_campaign": len(unassigned),
        "daily_capacity_healthy_only": {
            "connection_requests": entry_cap,
            "messages": msg_cap,
            "note": ("Provider-configured ceilings summed over HEALTHY seats. "
                     "This is what is ALLOWED, not what was sent, and not a "
                     "promise LinkedIn tolerates it. Never raise a per-seat "
                     "limit to gain throughput - add senders or add days."),
        },
        "senders": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")

    print("seats: %s  healthy=%s auth_invalid=%s inactive=%s"
          % (len(seats), totals["HEALTHY"], totals["AUTH_INVALID"], totals["INACTIVE"]))
    print("healthy seats with no active campaign: %s" % len(unassigned))
    print("daily ceiling over healthy seats: %s connection requests, %s messages"
          % (entry_cap, msg_cap))
    print("written: docs/state/SENDER-CAPACITY.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
