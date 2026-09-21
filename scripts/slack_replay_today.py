"""Deliver TODAY's queued notifications, and only today's.

WHY THIS IS NOT `notify.retry` IN A LOOP. There are 236 rows in the
notification store and 221 of them are historical - accumulated over weeks
while no Slack channel was configured, every one sitting at `unconfigured`.
Arming Slack and replaying the store would post all 221 at once into the ops
channel. A channel that receives 221 messages in one burst gets muted, and a
muted ops channel is worse than none - which is the same argument
`notify.route` makes for its NOWHERE default.

So the cut is by DATE and it is explicit: `--since`, defaulting to today at
00:00Z. Everything older is left exactly as it is, still readable in the web
app, and reported as skipped rather than silently ignored.

WHY THE CHANNEL HAS TO BE RE-RESOLVED. The rows are `unconfigured` because
they were built when `SLACK_OPS_CHANNEL` was unset, so each carries
`channel: None` - and `notify.deliver` returns early on `unconfigured`
without ever reaching the transport. Replaying therefore has to ask
`notify.destination_for` for the routing decision AGAIN, now that the
variable exists, and write the answer back before delivering. That is a
re-resolution, not an override: if the event type still routes NOWHERE, or
the workspace still has no channel, the row stays undelivered and says so.

    py -3 scripts/slack_replay_today.py            # dry run, sends nothing
    py -3 scripts/slack_replay_today.py --live     # actually posts
    py -3 scripts/slack_replay_today.py --since 2026-09-20T00:00Z

DRY RUN IS THE DEFAULT and `--live` is the only way to send.
"""

import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import notify                                          # noqa: E402
from src.providers import load_env, slack                       # noqa: E402


def _today_utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00Z")


def _at(row):
    return str(row.get("at") or "")


def _on_or_after(row, since):
    """Lexicographic compare on ISO-8601, which is only valid because both
    sides are UTC and zero-padded. `at` is written by `store.now()` as
    `+00:00` and `since` may end in `Z`, so compare the date-and-hour prefix
    rather than the whole string."""
    return _at(row)[:13] >= since[:13]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default=None,
                        help="ISO-8601 UTC cutoff; default today 00:00Z")
    parser.add_argument("--live", action="store_true",
                        help="actually post; without it nothing is sent")
    args = parser.parse_args(argv)

    load_env()
    since = args.since or _today_utc()
    rows = notify.load()

    due = [r for r in rows if _on_or_after(r, since)]
    older = len(rows) - len(due)

    print(f"notification store: {len(rows)} rows")
    print(f"  cutoff            {since}")
    print(f"  on or after       {len(due)}")
    print(f"  older, untouched  {older}")
    if not due:
        print("\nNothing to replay.")
        return 0

    by_type = collections.Counter(r.get("type") for r in due)
    by_status = collections.Counter(r.get("status") for r in due)
    print(f"  by type           {dict(by_type)}")
    print(f"  by status         {dict(by_status)}")

    # Re-resolve each row's routing with the variables as they are NOW.
    plan = []
    for row in due:
        decision = notify.destination_for(row.get("type"),
                                          row.get("workspace"))
        plan.append((row, decision))

    deliverable = [(r, d) for r, d in plan if d.get("channel")]
    blocked = [(r, d) for r, d in plan if not d.get("channel")]

    print(f"\nWOULD DELIVER      {len(deliverable)}")
    for row, decision in deliverable[:20]:
        print(f"  {row['id'][:12]}  {_at(row)[:19]}  {row.get('type')}"
              f"  -> {decision['channel']}")
    if len(deliverable) > 20:
        print(f"  ... and {len(deliverable) - 20} more")

    if blocked:
        print(f"\nSTILL UNDELIVERABLE {len(blocked)}")
        seen = set()
        for row, decision in blocked:
            why = decision.get("why")
            if why in seen:
                continue
            seen.add(why)
            print(f"  {row.get('type')}: {why}")

    if not args.live:
        print("\nDRY RUN - nothing was sent. Re-run with --live to post.")
        return 0

    if not slack.live():
        print(f"\nREFUSED: {slack.LIVE_VAR} and {slack.KEY_VAR} must both be "
              f"set before --live can post. Nothing was sent.")
        return 2

    sent = failed = 0
    for row, decision in deliverable:
        # Write the re-resolved routing back, then deliver. `_update` is the
        # module's own single writer, so the store stays consistent with what
        # the web app reads.
        notify._update(row["id"], channel=decision["channel"],
                       destination=decision["destination"],
                       severity=decision["severity"],
                       status=notify.PLANNED,
                       why="re-resolved on replay; channel now configured")
        result = notify.deliver(row["id"])
        if (result or {}).get("status") == notify.SENT:
            sent += 1
        else:
            failed += 1
            print(f"  FAILED {row['id'][:12]} "
                  f"{(result or {}).get('last_error', '')[:120]}")

    print(f"\nSENT {sent}   FAILED {failed}   "
          f"UNTOUCHED (older than cutoff) {older}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
