"""Deliver PLANNED notifications to Slack, on a loop. Nothing else does.

THE GAP THIS CLOSES. `notify.notify()` only PLANS: it resolves the routing,
writes the row and stops. `notify.deliver()` is what reaches Slack, and on
2026-09-21 the only two callers were `src/digestwatch.py` - which delivers a
daily DIGEST row and nothing else - and `scripts/slack_replay_today.py`, which
is deliberately unrun. So Slack was live and proven by a smoke test while 244
notifications sat undelivered, and the first confirmed send on 489 reached
nobody.

WHAT IT WILL NOT DO, and each of these is a decision rather than an omission:

  - It never touches `unconfigured`. Those rows carry no channel because none
    was configured when they were built; re-resolving them is the replay
    script's job and that stays an operator action.
  - It never touches `suppressed`. HELD IS HELD. Eleven rows were suppressed
    by operator decision - nine stale August rows pointing at channel names
    that may not exist, two pre-TASK-238 unmatched replies - and a loop that
    quietly un-holds them would defeat the point of holding them.
  - It never re-sends a `sent` row. `notify.deliver` already returns early on
    SENT, and the loop also skips it, so an id can be delivered once.
  - It does not retry a FAILED row on its own. A failure is left visible with
    its error; `notify.retry` exists and is a deliberate act.

IDEMPOTENT PER ROW ID because delivery is the irreversible direction. Two
guards: `deliver` refuses a row already SENT, and this loop only ever selects
PLANNED. A row seen twice in one pass is delivered once.

    py -3 scripts/notify_deliver_loop.py --once
    py -3 scripts/notify_deliver_loop.py --interval 60

Bare. Never under `timeout` - a monitor killed by a wrapper is a monitor that
lies about being up.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import notify                                          # noqa: E402
from src.providers import load_env, slack                       # noqa: E402

HEARTBEAT = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "work", "heartbeat", "notify-deliver.json")


def due(rows):
    """PLANNED rows with a channel, that their workspace still allows."""
    out = []
    for row in rows:
        if row.get("status") != notify.PLANNED or not row.get("channel"):
            continue
        slug = row.get("workspace")
        if slug:
            allowed, why = notify.workspace_allows(slug, row.get("type"))
            if not allowed:
                notify._update(row["id"], status=notify.SUPPRESSED,
                               why=f"workspace toggle: {why}")
                continue
        out.append(row)
    return out


def sweep(quiet=False):
    """One pass. Returns (delivered, failed, skipped)."""
    delivered = failed = 0
    rows = due(notify.load())
    for row in rows:
        result = notify.deliver(row["id"]) or {}
        if result.get("status") == notify.SENT:
            delivered += 1
            if not quiet:
                print(f"SENT {row['id'][:12]} {row.get('type')} -> "
                      f"{row.get('channel')}", flush=True)
        else:
            failed += 1
            if not quiet:
                print(f"FAILED {row['id'][:12]} {row.get('type')}: "
                      f"{str(result.get('last_error'))[:120]}", flush=True)
    return delivered, failed, len(rows)


def beat(delivered, failed, considered):
    import datetime
    import json
    os.makedirs(os.path.dirname(HEARTBEAT), exist_ok=True)
    with open(HEARTBEAT, "w", encoding="utf-8") as handle:
        json.dump({"source": "notify", "watcher": "notify-deliver",
                   "at": datetime.datetime.now(
                       datetime.timezone.utc).isoformat(),
                   "pid": os.getpid(), "live": slack.live(),
                   "delivered": delivered, "failed": failed,
                   "considered": considered}, handle)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args(argv)

    load_env()
    if not slack.live():
        print(f"REFUSED: {slack.LIVE_VAR} and {slack.KEY_VAR} must both be "
              f"set. Delivering nothing.")
        return 2

    print(f"DELIVERING planned notifications, every {args.interval}s. "
          f"suppressed and unconfigured are left alone.", flush=True)
    total = 0
    while True:
        delivered, failed, considered = sweep()
        total += delivered
        beat(delivered, failed, considered)
        if args.once:
            print(f"once: delivered {delivered}, failed {failed}")
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
