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
  - It never posts to a channel outside `NOTIFY_DELIVER_CHANNELS`, when that
    variable is set. 2026-10-03, the runtime lane: the operator's standing
    limit for the canary night is "no Slack post outside the OUTPUT channel
    without the operator's GO", and the ledger held ELEVEN undelivered
    PLANNED rows aimed at other rooms. A promise not to post is not a
    mechanism; this is. Unset, the loop behaves exactly as before, so the
    narrowing is an operator act - visible in the banner and in the
    heartbeat - and never a silent default. A row outside the allowlist is
    LEFT PLANNED and untouched, so widening the list delivers it with
    nobody having to un-hold anything by hand.

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

from src import notify, singlewalker, supervisor                # noqa: E402
from src.providers import load_env, slack                       # noqa: E402

#: The name this monitor is declared under in `supervisor.MONITORS`. The
#: lock and the state file are keyed on it, so it must match exactly or the
#: repository's own supervisor would start a SECOND copy of this loop.
MONITOR = "notify_deliver"

#: An ADDITIONAL absolute heartbeat path, set by whoever supervises this
#: loop. Operator, 2026-10-03: the GO checklist's liveness test is "the
#: heartbeat is younger than five minutes", not "a process is listed" - a
#: process census can see a hung interpreter and call it up, and the one
#: thing a hung loop cannot do is keep rewriting a file. It is a SECOND
#: file rather than a replacement for `heartbeat_path()`, because that one
#: lives beside the ledger and is what `supervisor.witnesses` reads; this
#: one lives where the operator looks, outside every worktree, and survives
#: the tree being deleted.
LIVENESS_VAR = "NOTIFY_DELIVER_HEARTBEAT"


def liveness_path():
    return (os.environ.get(LIVENESS_VAR) or "").strip() or None


def heartbeat_path():
    """Beside the LEDGER being drained, resolved per call.

    It was `<this file>/../work/heartbeat/`, which is this TREE's work/ and
    not necessarily the one being drained. Run from a worktree with QUEUE
    pointed at production - which is how the loop was finally started on
    2026-10-03 - the loop drained production and wrote its heartbeat into a
    temporary directory nothing reads, so production's health file stayed
    absent while the loop was up. A heartbeat in the wrong directory is a
    heartbeat for a machine nobody is asking about.
    """
    return os.path.join(os.path.dirname(notify.path()), "heartbeat",
                        "notify-deliver.json")


#: Operator-set allowlist of channel ids this loop may post to, comma
#: separated. UNSET MEANS EVERY CHANNEL, which is what every caller before
#: 2026-10-03 relied on, so setting nothing changes nothing.
CHANNELS_VAR = "NOTIFY_DELIVER_CHANNELS"


def allowed_channels():
    """Channel ids this loop may post to, or None meaning "all of them"."""
    raw = (os.environ.get(CHANNELS_VAR) or "").strip()
    if not raw:
        return None
    return tuple(c.strip() for c in raw.split(",") if c.strip())


def due(rows, channels=None):
    """PLANNED rows with a channel, that their workspace still allows.

    `channels`, when given, is an allowlist. A row outside it is skipped and
    LEFT PLANNED - not suppressed and not failed. The narrowing is a limit on
    this loop, never a decision about the row.
    """
    out = []
    for row in rows:
        if row.get("status") != notify.PLANNED or not row.get("channel"):
            continue
        if channels is not None and row.get("channel") not in channels:
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


def sweep(quiet=False, channels=None):
    """One pass. Returns (delivered, failed, considered)."""
    delivered = failed = 0
    rows = due(notify.load(), channels)
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


def beat(delivered, failed, considered, channels=None):
    import datetime
    import json
    target = heartbeat_path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump({"source": "notify", "watcher": "notify-deliver",
                   "at": datetime.datetime.now(
                       datetime.timezone.utc).isoformat(),
                   "pid": os.getpid(), "live": slack.live(),
                   "delivered": delivered, "failed": failed,
                   "considered": considered,
                   # The ledger and the allowlist, so a reader of the
                   # heartbeat can tell WHICH ledger is being drained and
                   # WHERE it may post. A heartbeat that proves a loop is
                   # alive without saying what it is draining is how a
                   # worktree's empty `work/` reads as a quiet estate.
                   "ledger": notify.path(),
                   "channels": list(channels) if channels else None},
                  handle)

    # The operator's liveness file. Written LAST and written WHOLE, so its
    # mtime means "a sweep completed", never "a sweep was attempted".
    live_at = liveness_path()
    if live_at:
        os.makedirs(os.path.dirname(live_at), exist_ok=True)
        tmp = f"{live_at}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({
                "watcher": "notify-deliver",
                "at": datetime.datetime.now(
                    datetime.timezone.utc).isoformat(),
                "pid": os.getpid(), "live": slack.live(),
                "delivered": delivered, "failed": failed,
                "considered": considered, "ledger": notify.path(),
                "channels": list(channels) if channels else None}) + "\n")
        os.replace(tmp, live_at)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--channel", action="append", default=None,
                        help=("only post to this channel id; repeatable. "
                              "Overrides " + CHANNELS_VAR + ". Unset means "
                              "every channel, the historic behaviour."))
    args = parser.parse_args(argv)

    load_env()
    if not slack.live():
        print(f"REFUSED: {slack.LIVE_VAR} and {slack.KEY_VAR} must both be "
              f"set. Delivering nothing.")
        return 2

    channels = tuple(args.channel) if args.channel else allowed_channels()
    print(f"DELIVERING planned notifications, every {args.interval}s. "
          f"suppressed and unconfigured are left alone.", flush=True)
    print(f"LEDGER {notify.path()}", flush=True)
    if channels:
        print(f"NARROWED to {', '.join(channels)}. Every other channel is "
              f"left PLANNED and untouched.", flush=True)
    else:
        print("EVERY channel. No allowlist is set.", flush=True)

    if args.once:
        delivered, failed, considered = sweep(channels=channels)
        beat(delivered, failed, considered, channels)
        print(f"once: delivered {delivered}, failed {failed}")
        return 0

    # ONE LOOP AT A TIME, AND THE REPOSITORY'S OWN STATUS VIEW KNOWS IT IS UP.
    #
    # Two separate problems, one seam. `scripts/supervise.py` takes this same
    # `singlewalker` lock before spawning `notify_deliver`, so a loop started
    # any other way - by hand, or by the shell supervisor that finally
    # started this one on 2026-10-03 - was invisible to it and a second copy
    # would have been spawned on top. Taking the lock HERE means the loop
    # defends itself whoever starts it, and `record_started` is public for
    # exactly this case: witness 1 is "a live pid from a state file", and
    # until this call that file was only ever written by `supervise.py`.
    #
    # Fail CLOSED on the lock. A refusal here means another deliver loop is
    # already draining this ledger, and two is worse than one.
    try:
        lock = singlewalker.held(
            supervisor._lock_path(MONITOR))  # noqa: SLF001
    except Exception as e:                                  # noqa: BLE001
        print(f"REFUSED: cannot resolve the {MONITOR} lock: "
              f"{type(e).__name__}: {e}")
        return 3
    try:
        with lock:
            supervisor.record_started(MONITOR, os.getpid())
            print(f"HOLDING the {MONITOR} lock, pid {os.getpid()}.",
                  flush=True)
            while True:
                delivered, failed, considered = sweep(channels=channels)
                beat(delivered, failed, considered, channels)
                time.sleep(args.interval)
    except singlewalker.AlreadyWalking as e:
        print(f"REFUSED: another {MONITOR} is already running: {e}")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
