#!/usr/bin/env python3
"""Fire the daily digest when its hour comes round. A bare monitor.

    py -3 scripts/digest_loop.py --interval 300
    py -3 scripts/digest_loop.py --once          # announce if one is due
    py -3 scripts/digest_loop.py --force         # announce now, for testing

## WHY THIS EXISTS

`src/digestwatch.py` computes when a digest is due and `digest.announce`
records one. **Nothing called either of them.** Measured 2026-09-21: no
process, no cron, no script - the whole mechanism was written, tested and
never wired, which is the recurring defect CLAUDE.md names as "a thing
computed correctly that nothing downstream reads".

The operator asked for the 07:00 digest in `#resonate-os`. Without a caller
it would simply not have appeared, and the absence would have looked like a
quiet night rather than a missing loop.

## THE HOUR IS UTC AND IT MOVES WITH DST

`DIGEST_HOUR` is UTC. 05:00 UTC is 07:00 in Zagreb during CEST and 06:00
during CET, so the handoff's standing note is exact: **DIGEST_HOUR moves
5 -> 6 on 2026-10-25.** This loop does not paper over that - it reports the
local time it is actually firing at, so a wrong hour is visible in the log
rather than inferred from a late message.

## IDEMPOTENT BY THE DIGEST'S OWN ID

`digestwatch.delivered` checks whether this workspace already has a digest
for this boundary, and `notify` de-duplicates on the same id anyway. So a
restart, a second process or a clock that steps backwards cannot produce two.
"""
import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import digest, digestwatch, workspaces as ws            # noqa: E402
from src.providers import load_env                               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEARTBEAT = os.path.join(ROOT, "work", "heartbeat", "digest.json")


def emit(line):
    print(line, flush=True)


def heartbeat(state):
    os.makedirs(os.path.dirname(HEARTBEAT), exist_ok=True)
    payload = {"source": "digest", "watcher": "digest",
               "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "epoch": int(time.time()), "pid": os.getpid(), "state": state}
    tmp = HEARTBEAT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    os.replace(tmp, HEARTBEAT)


#: ONE DIGEST, NOT THREE. The first run announced one per workspace -
#: productive, contactout and demo-client - into a channel the whole team
#: reads. `demo-client` is a demo and `contactout` has no live outreach, so
#: two of the three would have been noise in a feed whose value is that
#: everything in it matters. Named explicitly rather than filtered by a
#: heuristic, so adding a real second client is a deliberate edit.
DIGEST_WORKSPACES = ("productive",)


def workspaces(only=None):
    if only:
        return [only]
    known = set()
    try:
        known = {w.get("slug") for w in ws.workspaces() if w.get("slug")}
    except Exception:                                           # noqa: BLE001
        pass
    return [slug for slug in DIGEST_WORKSPACES if not known or slug in known]


def sweep(force=False, only=None):
    """Announce a digest for every workspace that is due one."""
    settings = digestwatch.settings()
    hour = settings.get("hour") if isinstance(settings, dict) else None
    now = datetime.datetime.now(datetime.timezone.utc)
    announced = 0
    for slug in workspaces(only):
        try:
            until = digestwatch.boundary(now=now)
        except Exception as exc:                                # noqa: BLE001
            emit(f"BOUNDARY-FAILED {slug}: {type(exc).__name__}: {exc}")
            continue
        if not force and until > now:
            continue
        # BUILD FIRST, THEN ASK THE BUILT WINDOW WHETHER IT WAS ANNOUNCED.
        #
        # Four digests went to #resonate-os in twenty minutes because the
        # check and the write were keyed differently, twice over. First
        # `digest.build(slug)` with no `until` windows on NOW, so every
        # sweep wrote a new id. Passing the boundary in fixed that and it
        # STILL repeated, because `boundary()` returns a datetime and the
        # window carries an ISO STRING - and `notification_id` hashes its
        # identifiers, so a datetime and the string spelling of the same
        # instant are two different rows.
        #
        # Asking the built window is the only version that cannot drift:
        # the value checked is the value written.
        built = digest.build(slug, until=until)
        window_until = (built.get("window") or {}).get("until")
        if not force and digestwatch.delivered(slug, window_until):
            continue
        row = digest.announce(built) or {}
        announced += 1
        emit(f"DIGEST {slug} until={until} -> {row.get('status')} "
             f"{row.get('channel')}")
    return announced


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workspace")
    args = parser.parse_args(argv)

    load_env()
    local = datetime.datetime.now().astimezone()
    emit(f"DIGEST LOOP starting. DIGEST_HOUR="
         f"{os.environ.get('DIGEST_HOUR', '(unset)')} UTC. "
         f"This machine is {local.tzname()} ({local.utcoffset()}), so that "
         f"hour is {local.tzname()} local. DIGEST_HOUR moves 5 -> 6 on "
         f"2026-10-25 when Zagreb leaves DST.")
    if args.once or args.force:
        count = sweep(force=args.force, only=args.workspace)
        emit(f"{count} digest(s) announced")
        return 0
    while True:
        try:
            count = sweep(only=args.workspace)
            heartbeat({"announced_last_sweep": count})
            if count:
                emit(f"{count} digest(s) announced")
        except Exception as exc:                                # noqa: BLE001
            emit(f"SWEEP-FAILED {type(exc).__name__}: {str(exc)[:160]}")
            heartbeat({"error": type(exc).__name__})
        time.sleep(max(args.interval, 30))


if __name__ == "__main__":
    raise SystemExit(main())
