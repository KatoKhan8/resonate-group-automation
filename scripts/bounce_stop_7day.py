#!/usr/bin/env python3
"""The 7-day bounce hard stop, measured from OUR OWN sends and nothing else.

    py -3 scripts/bounce_stop_7day.py
    py -3 scripts/bounce_stop_7day.py --days 7 --json

READ-ONLY. Writes nothing.

## THE QUESTION, AND WHY THE USUAL ANSWER IS THE WRONG ONE

The standing hard stop is **bounce > 2% on any mailbox over 7 days**. Every
stop checked in this project so far has been LIFETIME, which is what
`bison.sender_emails()` returns: 3437 reads 2.14% over 8,947 sends, and those
8,947 sends are overwhelmingly the client's, made before this system existed.

Lifetime and 7-day are different questions. A mailbox with a bad decade and a
clean week passes the stated rule; a mailbox with a clean decade and a bad
week fails it. Only sends WE caused can answer the rule as written.

## WHERE OUR OWN SENDS ACTUALLY LIVE, AND WHERE THEY DO NOT

**Not in `work/action-ledger.jsonl`.** That ledger holds 136 rows of
`bison.activate`, `heyreach.activate` and `heyreach.add_lead`, it stops on
2026-09-18, and it carries no send and no bounce event of any kind. It records
what was ATTEMPTED against a provider, not what a provider then did. A 7-day
bounce rate cannot be derived from it, and a script that appeared to do so
would be reading activations as sends.

So this reads the per-message queue rows of the campaigns THIS SYSTEM owns.
Each row is one message, carries its own `status`, `sent_at` and sender, and
goes `scheduled` -> `sent` | `bounced` | `stopped`. That is the same witness
`production_status` uses, and it is the only record of what our own sends did.

## UNDEFINED IS NOT ZERO

A mailbox this system has never sent from has NO 7-day bounce rate. It is not
0%, it is unanswerable, and the two must not print the same way: a 0% that
means "we never asked" is exactly the reading that would clear a hold nobody
had evidence to clear. Mailboxes with no sends are reported as UNDEFINED and
are never counted as passing.
"""
import argparse
import collections
import datetime
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.providers import bison, load_env                        # noqa: E402

#: Every campaign this system has ever pointed at a prospect. The client's own
#: 327/328/352 are deliberately absent: their sends are not our actions and
#: folding them in would rebuild the lifetime number this script exists to
#: replace.
OURS = (487, 489, 491, 492, 493, 494, 495, 496, 497, 498)

THRESHOLD = 2.0


def window_start(days):
    return (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=days))


def measure(days=7, campaigns=OURS):
    since = window_start(days)
    per = collections.defaultdict(lambda: {"sent": 0, "bounced": 0,
                                           "campaigns": set()})
    for cid in campaigns:
        for row in bison.scheduled_emails(cid):
            status = str(row.get("status") or "").lower()
            if status not in ("sent", "bounced"):
                continue
            stamp = row.get("sent_at") or row.get("scheduled_date")
            if not stamp:
                continue
            when = datetime.datetime.fromisoformat(
                str(stamp).replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=datetime.timezone.utc)
            if when < since:
                continue
            sid = (row.get("sender_email") or {}).get("id")
            if sid is None:
                continue
            entry = per[int(sid)]
            entry[status] += 1
            entry["campaigns"].add(cid)
    return since, per


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    load_env()
    since, per = measure(args.days)
    tripped = []
    out = {}
    for sid, e in sorted(per.items()):
        total = e["sent"] + e["bounced"]
        rate = (100.0 * e["bounced"] / total) if total else None
        out[sid] = {"sent": e["sent"], "bounced": e["bounced"],
                    "rate": rate, "campaigns": sorted(e["campaigns"])}
        if rate is not None and rate > THRESHOLD:
            tripped.append(sid)

    if args.json:
        print(json.dumps({"since": since.isoformat(), "days": args.days,
                          "mailboxes": out, "tripped": tripped}, indent=1))
        return 1 if tripped else 0

    print(f"\n7-DAY BOUNCE STOP  since {since.strftime('%Y-%m-%dT%H:%M:%SZ')}"
          f"  threshold {THRESHOLD}%")
    print(f"  source: per-message queue rows of campaigns "
          f"{', '.join(str(c) for c in OURS)}\n")
    if not out:
        print("  NO SENDS IN THE WINDOW from any campaign this system owns.")
        print("  Every mailbox's 7-day rate is UNDEFINED - not 0%.")
    for sid, e in out.items():
        rate = "UNDEFINED" if e["rate"] is None else f"{e['rate']:.2f}%"
        print(f"  mailbox {sid:<6} sent {e['sent']:>4}  bounced "
              f"{e['bounced']:>3}  rate {rate:>9}  "
              f"campaigns {e['campaigns']}")
    print(f"\n  TRIPPED: {tripped or 'none'}")
    print("  Any mailbox not listed has sent nothing for us in the window and "
          "has NO 7-day rate. Undefined is not a pass.")
    return 1 if tripped else 0


if __name__ == "__main__":
    raise SystemExit(main())
