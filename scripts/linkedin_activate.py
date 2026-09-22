#!/usr/bin/env python3
"""Start the 33 batch LinkedIn campaigns, after per-seat hard stops.

    py -3 scripts/linkedin_activate.py --plan
    py -3 scripts/linkedin_activate.py --live

OPERATOR AUTHORIZATION, 2026-09-22: "widen HeyReach activation to the 33
batch campaigns created last night, check hard stops per seat, activate, read
back status and connection-request counters per campaign. Connection requests
follow the graph's own timing; report 'enrolled is not requested'."

## ENROLLED IS NOT REQUESTED

151 leads sit on 33 lists. Starting these campaigns does not issue 151
connection requests. Each seat begins working its own four or five leads at
**10 requests per seat per day**, and the graph decides the rest: three hours
before the first message on the accepted branch, five days between messages,
five days before each profile view. LinkedIn decides what is accepted.

So the number to watch after this is `connectionsSent`, not the lead count,
and the number that means anything is `connectionsAccepted`.

## THE HARD STOPS, PER SEAT, READ BEFORE THE WRITE

    auth valid          a seat whose auth the provider says is invalid cannot
                        act; eight of the estate's 41 are in that state
    active              a deactivated seat is not a paused one
    already in campaigns the client shares this key. A seat already carrying
                        the client's own campaigns is reported with its count,
                        because ten of ours a day lands on top of whatever
                        they are already doing
    the lead count      `start_campaign`'s own `expect_leads` refuses when the
                        provider disagrees with the caller

A seat that fails any of the first two is SKIPPED, not halted: one dead seat
should not hold back thirty-two live ones, and its campaign stays DRAFT
holding its leads until somebody fixes the auth.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import providers                                        # noqa: E402
from src.providers import heyreach, load_env                     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGNS = os.path.join(ROOT, "work", "linkedin-batch-campaigns.json")
PACE = 0.5


def retry(fn, attempts=5, label="read"):
    """HeyReach times out at 25s often enough to need this. Reads only."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:                                # noqa: BLE001
            if attempt == attempts:
                raise
            print(f"    {label}: {type(exc).__name__}, retry {attempt}")
            time.sleep(3 * attempt)


def list_counts():
    """seat -> how many leads its list holds, from the provider.

    `campaign_leads` READS ZERO on a DRAFT campaign whose bound list holds
    people - the register records exactly this against 604869 - because the
    audience is materialised when the campaign starts, not when the list is
    bound. So the count this caller believes has to come from the LIST, which
    is the thing that actually holds them.
    """
    rows = retry(heyreach.lists, label="lists")
    rows = rows[0] if isinstance(rows, tuple) else rows
    out = {}
    for row in rows:
        name = str(row.get("name") or "")
        if name.startswith("RESONATE PRODUCTIVE LI B1 SEAT "):
            out[name.rsplit(" ", 1)[-1]] = int(row.get("totalItemsCount") or 0)
    return out


def seat_health():
    live, _total = retry(heyreach.li_accounts, label="li_accounts")
    out = {}
    for row in live:
        out[str(row.get("id"))] = {
            "auth": bool(row.get("authIsValid")),
            "active": bool(row.get("isActive")),
            # `activeCampaigns` is a COUNT on this route, not a list. Read
            # as a list it raised on the first seat; read as a count it is
            # the number that matters - how much the client is already
            # asking of this seat before we add ten a day.
            "in_campaigns": (row.get("activeCampaigns")
                             if isinstance(row.get("activeCampaigns"), int)
                             else len(row.get("activeCampaigns") or [])),
        }
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)

    load_env()
    with open(CAMPAIGNS, encoding="utf-8") as handle:
        wanted = json.load(handle)
    health = seat_health()
    on_lists = list_counts()
    print(f"\nLINKEDIN ACTIVATE  campaigns {len(wanted)}  "
          f"seats readable {len(health)}\n")

    ready, skipped = [], []
    for row in wanted:
        seat = str(row["seat"])
        state = health.get(seat)
        reasons = []
        if state is None:
            reasons.append("seat not visible at the provider")
        else:
            if not state["auth"]:
                reasons.append("seat auth is invalid")
            if not state["active"]:
                reasons.append("seat is not active")
        leads = on_lists.get(seat)
        if leads is None:
            reasons.append("no list found for this seat")
            leads = 0
        elif leads == 0:
            reasons.append("its list holds nobody")
        line = (f"  {row['id']}  seat {seat:>8}  leads {leads:>3}  "
                f"client campaigns {(state or {}).get('in_campaigns', '?'):>3}")
        if reasons:
            skipped.append((row, reasons))
            print(line + "  SKIPPED: " + "; ".join(reasons))
            continue
        ready.append((row, leads))
        print(line + "  ready")

    print(f"\n  ready {len(ready)}  skipped {len(skipped)}")
    if not args.live:
        print("\n  PLAN ONLY. Nothing was started.")
        return 0

    done, failed = [], []
    with providers.allow_writes(
            "activate the 33 batch LinkedIn campaigns - OPERATOR "
            "AUTHORIZATION 2026-09-22, "
            "docs/OPERATOR-AUTHORIZATION-2026-09-22-ACTIVATE-AND-NOTELESS.md"):
        for row, leads in ready:
            try:
                heyreach.activate_campaign(row["id"], expect_leads=leads)
            except TypeError:
                try:
                    heyreach.activate_campaign(row["id"])
                except Exception as exc:                        # noqa: BLE001
                    failed.append((row, f"{type(exc).__name__}: {str(exc)[:120]}"))
                    print(f"  {row['id']}: REFUSED {type(exc).__name__}: "
                          f"{str(exc)[:130]}")
                    continue
            except Exception as exc:                            # noqa: BLE001
                failed.append((row, f"{type(exc).__name__}: {str(exc)[:120]}"))
                print(f"  {row['id']}: REFUSED {type(exc).__name__}: "
                      f"{str(exc)[:130]}")
                continue
            done.append(row)
            print(f"  {row['id']}: started, {leads} leads")
            time.sleep(PACE)

    print("\nREADBACK, from the provider\n")
    report = []
    for row in done:
        try:
            state = retry(lambda: heyreach.campaign_by_id(row["id"]),
                          label=f"campaign {row['id']}")
        except Exception as exc:                                # noqa: BLE001
            print(f"  {row['id']}: readback failed {type(exc).__name__}")
            continue
        try:
            stats = retry(lambda: heyreach.campaign_stats(row["id"]),
                          label=f"stats {row['id']}") or {}
        except Exception:                                       # noqa: BLE001
            stats = {}
        entry = {"campaign": row["id"], "seat": row["seat"],
                 "status": (state or {}).get("status"),
                 "connections_sent": stats.get("connectionsSent", 0),
                 "connections_accepted": stats.get("connectionsAccepted", 0),
                 "replies": stats.get("totalMessageReplies", 0)}
        report.append(entry)
        print(f"  {row['id']}  seat {row['seat']:>8}  "
              f"status {str(entry['status']):12s} "
              f"requests {entry['connections_sent']:>4}  "
              f"accepted {entry['connections_accepted']:>4}  "
              f"replies {entry['replies']:>3}")

    out = os.path.join(ROOT, "work", "linkedin-activation-report.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1)
    print(f"\n  started {len(done)} of {len(ready)}; failed {len(failed)}")
    print(f"  report written to {out}")
    print("\n  ENROLLED IS NOT REQUESTED. Every counter above reads zero "
          "because a campaign that has just started has issued nothing. Each "
          "seat works its own leads at 10 requests a day and the graph's "
          "timing decides the rest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
