#!/usr/bin/env python3
"""Poll both providers for replies on a timer. One line per EVENT.

    py -3 scripts/reply_watch_loop.py [--interval 300]

WHY THIS EXISTS WHILE CAMPAIGNS ARE LIVE. `ACCOUNT-OUTREACH.md` guarantees that
a confirmed reply stops that lead on BOTH channels. `src/replywatch` implements
it as a supervised daemon thread inside the deployed Railway service - but this
is a workstation, that service is not what is driving these two campaigns, and
`--status` said "no poll has ever run". A guarantee nothing is polling is a
guarantee only as timely as the last time somebody remembered. A cadence step
can fire in that gap.

So this is the same poll on a timer, in the process that is already watching
these campaigns.

IT READS, AND THEN IT PROTECTS. `poller.run` ingests: it records the reply,
pauses the record and may enqueue a tag-sync intent. Nothing on this path
sends, drafts or replies - `push` and `tagsync.send` refuse by construction.
`REPLY_POLL_ENABLED` is set here deliberately and in one place, because a
default that reaches a provider is a default that surprises somebody.

WHAT IT EMITS. Silence means "inspected, nothing new", which is the normal
case and not worth a notification. A line means something happened:

    REPLY        a reply was ingested, followed by WHAT THE STOP DID on each
                 channel - stopped / already stopped / REFUSED with the
                 reason / no lead on that channel. This line used to be the
                 constant "the lead is stopped on both channels", printed on
                 any non-zero count and consulting nothing, and it said that
                 twice about leads that were never stopped.
    STOP-REFUSED a reply arrived and the stop was refused. The person may
                 still receive the next step. Also raised as a CRITICAL
                 notification to the ops channel.
    POLL-ERROR   a provider could not be polled, after it repeats
    SKIPPED      the cross-process lock was held, twice running

A watcher that only reported replies would be indistinguishable from one whose
credentials expired an hour ago, so failures get their own lines.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import watchsink                                       # noqa: E402
from src.providers import load_env                              # noqa: E402

PROVIDERS = ("emailbison", "heyreach")


def emit(line):
    """Stdout only. The DURABLE emitter is built in `main` - see
    `src/watchsink.py` for why printing alone was not a monitor."""
    print(line, flush=True)


def _alert_refusals(provider, refusals, emit):
    """A refused stop goes to #resonate-notifications. OPERATOR DECISION.

    `REPLY_PROTECTION_FAILED` is the existing event for this and it routes
    GLOBAL at CRITICAL, which is exactly right: a stop that was refused means
    somebody may still be written to after they answered. It is the same verb
    `replywatch._alert` raises when polling itself dies, and the two failures
    have the same consequence.

    Only REFUSALS. "no lead on that channel" is the ordinary state of a
    single-channel contact and alerting on it would bury this one.

    `notify.notify` cannot raise, which is what makes it safe to call from
    the watcher: a notification that cannot be built must not stop the next
    poll.
    """
    if not refusals:
        return
    from src import notify
    for refusal in refusals:
        notify.notify(
            notify.REPLY_PROTECTION_FAILED, None,
            fields={"provider": provider,
                    "channel": refusal.get("channel"),
                    "record": refusal.get("record"),
                    "why": refusal.get("why"),
                    "action": "this person replied and the stop was REFUSED - "
                              "they may still receive the next step. Stop "
                              "them by hand and read provider truth"},
            ids={"record_id": refusal.get("record"),
                 "channel": refusal.get("channel"),
                 "provider": provider})
        emit(f"STOP-REFUSED {provider} {refusal.get('channel')} "
             f"record={refusal.get('record')}: {refusal.get('why')}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interval", type=float, default=300.0)
    args = parser.parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_env(os.path.join(root, "config", ".env"))
    os.environ["REPLY_POLL_ENABLED"] = "1"

    # `replywatch.poll_once`, NOT `poller.run`. This loop called the lower
    # level directly and silently lost four things the wrapper does:
    #
    #   the TENANCY PIN   `poll_once` passes expect=expected_workspace(provider)
    #                     and `poller.run` skips the check entirely when
    #                     `expect` is None. A credential pointed at another
    #                     estate would have had its replies ingested and
    #                     applied to OUR records.
    #   the per-provider lock, so two pollers could not overlap
    #   the status file, which is how anybody knows polling is alive - it read
    #                     "last succeeded 2026-09-17T08:21Z" after this loop
    #                     had been polling happily for three hours
    #   `_alert`, which says once that reply protection has stopped
    #
    # `poll_once` also never raises: a failure is a status, not a crash.
    from src import replywatch

    # Durable from here down. This loop already wrote `replywatch.json` and
    # `notifications.jsonl`, so it was the one watcher that was not blind -
    # but its own event lines still went to the dead pipe, so a REPLY line
    # and a POLL-ERROR line were both unreadable after the shell exited.
    emit = watchsink.emitter("replies")

    emit(f"WATCHING replies on {', '.join(PROVIDERS)}")
    errors = {p: 0 for p in PROVIDERS}
    skips = {p: 0 for p in PROVIDERS}
    while True:
        for provider in PROVIDERS:
            try:
                report = replywatch.poll_once(provider, live=True)
            except Exception as exc:                # should not happen
                errors[provider] += 1
                if errors[provider] in (3, 12):
                    emit(f"POLL-ERROR {provider} unreadable "
                         f"{errors[provider]}x: {type(exc).__name__}")
                continue

            if not isinstance(report, dict):
                continue

            # `poll_once` reports failure rather than raising, so the error
            # path is read off the status it returns.
            if report.get("last_error"):
                errors[provider] = int(report.get("consecutive_failures") or 0)
                if errors[provider] in (3, 12):
                    emit(f"POLL-ERROR {provider} unreadable "
                         f"{errors[provider]}x: {report['last_error'][:90]}")
                continue
            errors[provider] = 0

            if report.get("skipped_reason"):
                skips[provider] += 1
                if skips[provider] == 2:
                    emit(f"SKIPPED {provider} lock held twice running")
                continue
            skips[provider] = 0

            count = int(report.get("new_replies_ingested") or 0)
            if count:
                # WHAT HAPPENED, NOT WHAT WAS SUPPOSED TO HAPPEN.
                #
                # This line read "the lead is stopped on both channels" and
                # was a constant - printed on any non-zero ingest, consulting
                # nothing. It said that twice about leads that were never
                # stopped, on the safety path, and both times the failure
                # looked exactly like the success. It is now built from
                # `inbound.summarise_stops`, so it can only say what the
                # provider actually confirmed.
                emit(f"REPLY {provider} ingested={count} - "
                     f"{report.get('stops') or 'no stop outcome recorded'}")
                _alert_refusals(provider, report.get("stop_refusals") or [], emit)
        # EVERY sweep, after both providers. Reply protection going quiet and
        # reply protection dying look identical from the outside.
        watchsink.beat("replies",
                       state={"errors": dict(errors), "skips": dict(skips)})
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
