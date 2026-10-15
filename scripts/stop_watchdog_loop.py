#!/usr/bin/env python3
"""The one process that runs the standing stops and records every attempt.

    py -3 -u scripts/stop_watchdog_loop.py --interval 300 --every 3600
    py -3 scripts/stop_watchdog_loop.py --status        # read the record only
    py -3 scripts/stop_watchdog_loop.py --once          # one pass, then exit
    py -3 scripts/stop_watchdog_loop.py --controls-only # no provider call

THE OPERATOR STARTS THIS, NOT A TASK. The one command is at the bottom of
this docstring.

## WHY A LOOP, AND WHY THIS LOOP

`scripts/bounce_stop_7day.py` and `scripts/hard_stop_check.py` were both added
on 2026-09-22 and, measured at `495fb3206` on 2026-10-16, **nothing has ever
invoked either of them** - no service, timer, monitor, unit or module.
`scripts/queue_wall_check.py` was added at 01:10 the same morning and was born
the same way. 24 days of a standing hard stop that was never asked.

`weekly_report_loop.py`'s own docstring records this happening three times
before - `digestwatch`, `digest.announce`, `slackfollowup.due()` - and its
answer is the precedent followed here: **a loop in `scripts/`, registered in
`src/supervisor.py`'s one monitor table, started by
`scripts/start_monitors.py`, with its heartbeat declared rather than guessed.**
The Monday report is the closest shape and this is written after it: tick
often, beat every tick, act on a cadence.

Nothing new is invented. The supervisor already restarts a dead monitor with
backoff, `start_monitors.py --status` already reports one that is not up on two
independent witnesses, and `scripts/server/generate_units.py` already derives
the systemd unit from the same table - so this loop inherits all of it by
being one row in one list.

## TWO CLOCKS, AND THEY ARE NOT THE SAME NUMBER

    --interval  300s   how often this process wakes and BEATS
    --every    3600s   the minimum gap between full check passes

They are separate because the checks are expensive - a bounce pass walks the
queue rows of ten campaigns, and 491 alone is 45 pages - while
`start_monitors.STALE_SECONDS` is 1200s, so a process that only woke hourly
would read DOWN for forty minutes of every hour and `--live` would be free to
start a second one beside it. Beating every 300s and checking every 3600s
keeps both true.

## WHAT IS LOUD, AND WHERE

    the attempt journal   work/stop-watchdog.jsonl, one row per PASS, append
                          only. A pass that did not happen is a HOLE in this
                          file, which a heartbeat can never show: a heartbeat
                          is rewritten every poll and carries no history.
    the heartbeat         work/heartbeat/stop-watchdog.json, so the supervisor
                          and `start_monitors.py --status` can see the process
                          is alive even on a tick that ran no checks.
    stdout                this loop's log, `work/w-stop_watchdog.out` when
                          started by `start_monitors.py`. The check's OWN
                          sentence, verbatim.
    a notification        on STOP, `notify.STATUS_HARD_STOP` - CRITICAL, and
                          already in the routing table since 2026-09-21 with
                          NOTHING in the repository raising it until now.

## AND THE HONEST PART ABOUT THAT LAST ONE

**A STOP DOES NOT REACH THE OPERATOR TODAY AND THIS LOOP CANNOT MAKE IT.**
`notify.plan` stores a row and posts nothing; `notify.deliver` asks
`slack.post`, which refuses unless `SLACK_LIVE` is set, and it is not set in
this build. So the notification is a durable local record - findable, audited,
and read by nobody who is not already looking.

What would actually reach him, in the order they would cost least to arrange:

  1. `SLACK_LIVE` set and `SLACK_STATUS_CHANNEL` naming `#resonate-os`, which
     is the transport this product already has and the channel the operator
     already reads. `notify_deliver_loop` is in the monitor table and would
     post it.
  2. Failing that, the digest: `digest_loop` already posts a daily summary,
     and a STOP in it is one line in something a person opens anyway.
  3. Failing both, nothing in this repository reaches a human unprompted, and
     the record above is the whole story. Said out loud here rather than left
     for somebody to discover on the day a mailbox trips.

That is the operator's decision, not this file's. It is written down in
`LANE-suppression.md` with the measurement behind it.

## THE THREE CONTROLS PRINT ON EVERY PASS

A planted over-threshold mailbox must produce STOP; a planted unreadable
campaign must produce BLIND and a non-zero exit; a record with a missing pass
must show a gap. They cost nothing, touch no provider, and if one of them
disagrees the whole pass is BLIND - because an instrument that cannot be seen
to fail is not evidence that nothing is wrong. See
`src/stopwatchdog.controls`.

## THE ONE COMMAND THAT STARTS IT

    py -3 scripts/start_monitors.py --live --only stop_watchdog

and `py -3 scripts/start_monitors.py --status` to confirm it came up.
"""
import argparse
import datetime
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import notify, stopwatchdog, watchsink                  # noqa: E402

WATCHER = "stop-watchdog"

#: The pass cadence. Hourly: the stop it serves is a 7-day rate, so hourly is
#: far finer than the rule needs, and the cost is the ceiling - a pass walks
#: every campaign's queue, so this is the number that decides how much
#: provider traffic the gate costs a day. An operator who wants it cheaper
#: raises this; nothing else has to change.
DEFAULT_EVERY = 3600

#: The beat cadence. Must stay under `start_monitors.STALE_SECONDS` (1200) or
#: this monitor reads DOWN between passes and `--live` starts a second one.
DEFAULT_INTERVAL = 300


def emit(text):
    sys.stdout.write("%s %s\n" % (datetime.datetime.now(
        tz=datetime.timezone.utc).strftime("%H:%M:%S"), text))
    sys.stdout.flush()


def due(rows, every, now=None):
    """Is a pass due? `(due, seconds_since_last)`.

    DUE WHEN THE RECORD IS EMPTY. A loop that has never run must run at once
    rather than waiting out a cadence it has no start point for.
    """
    now = time.time() if now is None else now
    dated = [r["epoch"] for r in rows or []
             if isinstance(r.get("epoch"), (int, float))]
    if not dated:
        return True, None
    since = now - max(dated)
    return since >= every, since


def _notification_fields(assessment):
    """COUNTS AND WORDS ONLY. No address, no mailbox, no campaign body.

    `notify._status_payload` refuses a string shaped like an address, and that
    refusal is swallowed by `notify.notify` into a FAILED row - so a payload
    carrying one would not raise here, it would silently stop being a
    notification. It also does not look inside a LIST, so a list of check
    summaries would pass its guard while carrying every stopped mailbox's
    address into the channel the whole team reads.

    Both are why this builds counts by hand instead of forwarding the check
    rows. `hard_stop_check` reports mailboxes BY EMAIL ADDRESS; the detail
    belongs in the journal and the log, which are local, and the channel gets
    the numbers and the names of the checks.
    """
    stopped = [r["name"] for r in assessment["checks"]
               if r.get("verdict") == stopwatchdog.STOP]
    blind = [r["name"] for r in assessment["checks"]
             if r.get("verdict") == stopwatchdog.BLIND]
    return {
        "verdict": assessment["verdict"],
        "checks_total": len(assessment["checks"]),
        "checks_stopped": len(stopped),
        "checks_blind": len(blind),
        "stopped_checks": stopped,
        "blind_checks": blind,
        "gaps": len(assessment["gaps"]),
        "controls_held": sum(1 for c in assessment["controls"] if c.get("ok")),
        "controls_total": len(assessment["controls"]),
        "detail_is_local": "work/%s and this loop's own log"
                           % stopwatchdog.JOURNAL_NAME,
    }


def announce(assessment, at=None):
    """Plan the notification for a STOP. Returns the row, or None.

    ONLY ON STOP. A BLIND is reported in the journal, in the log and in the
    supervisor's view of this monitor, and raising a CRITICAL for every
    unreadable campaign would make the critical channel unreadable - which is
    the argument `notify.CAMPAIGN_STOPPED_EXTERNALLY`'s own comment makes
    about not reusing a louder event.

    THE ID CARRIES THE PASS. `notification_id` is deterministic, so without a
    per-pass discriminator the second STOP of the week would be a no-op
    against the first and the operator would be told once and never again.
    """
    if assessment["verdict"] != stopwatchdog.STOP:
        return None
    stamp = (at or datetime.datetime.now(datetime.timezone.utc))
    return notify.notify(
        notify.STATUS_HARD_STOP,
        fields=_notification_fields(assessment),
        ids={"check": "stop_watchdog",
             "pass": stamp.strftime("%Y-%m-%dT%H:00Z")})


def print_pass(assessment, out=emit):
    """Everything, in the order an operator needs it. No tick, ever."""
    for row in assessment["controls"]:
        out("  CONTROL %-4s %s" % ("OK" if row["ok"] else "FAIL",
                                   row["control"]))
        if not row["ok"]:
            out("           planted  %s" % row["planted"])
            out("           expected %r" % (row["expected"],))
            out("           observed %r" % (row["observed"],))
    for row in assessment["checks"]:
        out("  %-5s %-18s exit %s  %.1fs"
            % (row["verdict"], row["name"], row["exit_code"],
               row.get("seconds", 0.0)))
        # VERBATIM. The check's own sentence, unchanged - carrying 0140's
        # "every rate is UNDEFINED and UNDEFINED is not a pass" through
        # rather than folding it into a count.
        out("        %s" % row["summary"])
    for gap in assessment["gaps"]:
        out("  GAP   %-8s %s" % (gap["kind"], gap["why"]))
    out("  %s" % assessment["summary"])


def tick(every=DEFAULT_EVERY, now=None, force=False, checks=None,
         per_check=None, journal=None, with_controls=True, announce_stop=True,
         out=emit):
    """One wake-up. Runs a pass if one is due, beats either way.

    Returns the assessment when a pass ran, and `None` when it did not. A
    tick that runs no pass writes NO journal row - the journal is a record of
    attempts at the schedule, and padding it with wake-ups would make a gap
    unfindable, which is the one thing it exists to show.
    """
    now = time.time() if now is None else now
    rows = stopwatchdog.attempts(path=journal)
    is_due, since = due(rows, every, now=now)
    if not (is_due or force):
        watchsink.beat(WATCHER, state={
            "pass_due_in": round(every - (since or 0), 1),
            "attempts_recorded": len(rows)},
            note="waiting; last pass %.0fs ago" % (since or 0))
        return None

    control_rows = stopwatchdog.controls() if with_controls else []
    results = stopwatchdog.run_checks(checks=checks, per_check=per_check)
    assessment = stopwatchdog.assess(results, rows, every, now=now,
                                     control_rows=control_rows)

    stamp = datetime.datetime.fromtimestamp(
        now, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {
        "at": stamp,
        "epoch": int(now),
        "pid": os.getpid(),
        "verdict": assessment["verdict"],
        "exit_code": assessment["exit_code"],
        "every": every,
        "controls_ok": assessment["controls_ok"],
        "gaps": [{"kind": g["kind"], "why": g["why"]}
                 for g in assessment["gaps"]],
        "checks": [{"name": r["name"], "verdict": r["verdict"],
                    "exit_code": r["exit_code"], "summary": r["summary"],
                    "error": r.get("error")}
                   for r in assessment["checks"]],
        "summary": assessment["summary"],
    }
    # RECORDED BEFORE ANYTHING ELSE CAN FAIL. A notification that raises, a
    # Slack transport that is down, a print into a closed pipe - none of them
    # may cost the record of the attempt, because the record is what makes the
    # next missing pass visible.
    stopwatchdog.record_attempt(row, path=journal)
    assessment["recorded"] = row

    print_pass(assessment, out=out)
    if announce_stop:
        planned = announce(assessment)
        if planned is not None:
            out("  NOTIFIED %s status=%s channel=%s"
                % (notify.STATUS_HARD_STOP, planned.get("status"),
                   planned.get("channel")))
            if planned.get("status") != notify.SENT:
                out("        and that is NOT a message anybody received - "
                    "see this file's docstring")
    watchsink.beat(WATCHER, state={
        "verdict": assessment["verdict"],
        "exit_code": assessment["exit_code"],
        "controls_ok": assessment["controls_ok"],
        "gaps": len(assessment["gaps"]),
        "attempts_recorded": len(rows) + 1},
        note=assessment["summary"])
    return assessment


def status(every=DEFAULT_EVERY, now=None, journal=None, out=print):
    """Read the record. Runs no check and makes no provider call.

    Its exit code is the record's own verdict: the last pass's code, or 2 when
    the schedule has a gap. A reader who only wants to know whether the gate
    is being asked at all should ask this, not a pass.
    """
    rows = stopwatchdog.attempts(path=journal)
    found = stopwatchdog.gaps(rows, every=every, now=now)
    last = rows[-1] if rows else None
    out("")
    out("STOP WATCHDOG RECORD  %s" % (journal or stopwatchdog.journal_path()))
    out("  attempts recorded: %d   cadence %ds   tolerance %gx"
        % (len(rows), every, stopwatchdog.GAP_FACTOR))
    if last and last.get("epoch"):
        out("  last attempt: %s  verdict %s  exit %s"
            % (last.get("at"), last.get("verdict"), last.get("exit_code")))
        out("        %s" % last.get("summary"))
    else:
        out("  NO ATTEMPT HAS EVER BEEN RECORDED. Nothing has been checked.")
    for gap in found:
        out("  GAP %-8s %s" % (gap["kind"], gap["why"]))
    if not found:
        out("  no gap: every scheduled pass in this record ran")
    code = (stopwatchdog.EXIT_BLIND if found
            else (last.get("exit_code") if last else stopwatchdog.EXIT_BLIND))
    out("  exit %s" % code)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                        help="seconds between wake-ups and heartbeats")
    parser.add_argument("--every", type=int, default=DEFAULT_EVERY,
                        help="minimum seconds between full check passes")
    parser.add_argument("--once", action="store_true",
                        help="run one pass, print it, exit with its code")
    parser.add_argument("--status", action="store_true",
                        help="read the record only; no check, no provider")
    parser.add_argument("--controls-only", action="store_true",
                        help="run the three controls and nothing else")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.status:
        return status(every=args.every)

    if args.controls_only:
        rows = stopwatchdog.controls()
        if args.json:
            print(json.dumps(rows, indent=1, default=str))
        else:
            for row in rows:
                print("  CONTROL %-4s %s"
                      % ("OK" if row["ok"] else "FAIL", row["control"]))
                print("           expected %r" % (row["expected"],))
                print("           observed %r" % (row["observed"],))
        return 0 if all(r["ok"] for r in rows) else stopwatchdog.EXIT_BLIND

    if args.once:
        assessment = tick(every=args.every, force=True, out=emit)
        if args.json:
            print(json.dumps(assessment, indent=1, default=str))
        return assessment["exit_code"]

    emit("stop watchdog up: beating every %ds, checking every %ds"
         % (args.interval, args.every))
    while True:
        try:
            tick(every=args.every)
        except Exception:                                       # noqa: BLE001
            # The loop survives, LOUDLY. A traceback on stdout lands in this
            # monitor's own log, and the next tick records its attempt - so a
            # crash in one pass does not become a gap, and a crash in every
            # pass does.
            traceback.print_exc()
            try:
                watchsink.beat(WATCHER, note="tick raised; see the log")
            except Exception:                                   # noqa: BLE001
                pass
        time.sleep(max(30, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
