#!/usr/bin/env python3
"""The daily digest on a schedule, so it does not depend on somebody asking.

## The gap this closes

`digest.build` assembles a day and `digest.announce` records it, and both
worked from the first commit - as a command an operator types. Which means
the digest existed exactly as often as somebody remembered it, and the whole
argument for routing ordinary replies to `NOWHERE` is that a digest catches
them. A summary nobody schedules is a summary nobody reads.

## No new state, and that is the design

Whether a period has already been delivered is *derived*, not stored.
`notify.plan` is idempotent on a notification id built from the event type,
the workspace and the identifiers - and `digest.announce` already passes the
period's end as one. So the same period announced twice is one row, and "has
this gone out?" is answered by looking for that id rather than by a second
file that could disagree with the notification log.

That is also why the window is anchored to a scheduled boundary rather than
to `now()`: a digest built at 08:00:03 and again at 08:05 would otherwise be
two different periods and two different ids, and the idempotency would be
real but useless.

## Catching up, honestly

If the process was down, the window starts at the last digest this workspace
actually received rather than at the previous boundary - so the days in
between are reported once instead of vanishing. Bounded by `MAX_CATCH_UP`:
beyond that the gap is too large to summarise usefully and the window falls
back to one period, which the result says out loud rather than implying that
a fortnight fitted into it.

## The hour is UTC and says so

There is no per-workspace timezone anywhere in this build, and inventing one
here would be a guessed timezone presented as a decision - worse than a
missing one. `DIGEST_HOUR` is UTC. An operator who wants 09:00 in Zagreb
sets 7 or 8 and knows which.

## What it will not do

It reads and it records. `notify.deliver` refuses without `SLACK_LIVE` and
writes that refusal down, which is deliberately still called: a scheduler
that stops at "planned" proves the plan and nothing about the delivery. It
sends no outreach, drafts nothing and touches no record.

  python -m src.digestwatch --once
  python -m src.digestwatch --status
"""
import argparse
import datetime
import os
import sys

from . import digest, notify, store, workspaces as ws

OFF = "off"
DAILY = "daily"
WEEKDAYS = "weekdays"

SCHEDULES = (OFF, DAILY, WEEKDAYS)

SCHEDULE_LABEL = {
    OFF: "no digest is scheduled",
    DAILY: "every day",
    WEEKDAYS: "Monday to Friday",
}

DEFAULT_HOUR = 8

# A gap longer than this is not a digest, it is a report. The window falls
# back to one period and the result says so.
MAX_CATCH_UP_DAYS = 7

# Long enough for one build, short enough that a tick never queues behind
# the previous tick. Same reasoning as `replywatch.LOCK_WAIT`.
LOCK_WAIT = 1.0


class NotConfigured(RuntimeError):
    """The schedule was asked for in a way this cannot honour."""


def settings(env=None):
    """What the environment asks for. Unreadable is refused, never defaulted.

    A misread hour is a digest that arrives at the wrong time every day and
    looks like a working schedule, which is the failure this build keeps
    finding: something that reports healthy because nothing checked it.
    """
    env = os.environ if env is None else env
    schedule = str(env.get("DIGEST_SCHEDULE") or OFF).strip().lower()
    if schedule not in SCHEDULES:
        raise NotConfigured(
            f"DIGEST_SCHEDULE must be one of {', '.join(SCHEDULES)}, "
            f"not {schedule!r}")

    raw = str(env.get("DIGEST_HOUR") or "").strip()
    if raw == "":
        hour = DEFAULT_HOUR
    else:
        try:
            hour = int(raw)
        except ValueError:
            raise NotConfigured(
                f"DIGEST_HOUR must be a whole hour 0-23, not {raw!r}") from None
        if not 0 <= hour <= 23:
            raise NotConfigured(
                f"DIGEST_HOUR must be a whole hour 0-23, not {raw!r}")

    return {"schedule": schedule, "hour": hour,
            "enabled": schedule != OFF,
            "label": (f"{SCHEDULE_LABEL[schedule]} at {hour:02d}:00 UTC"
                      if schedule != OFF else SCHEDULE_LABEL[OFF])}


# ------------------------------------------------------------- the schedule

def _utc(value):
    """An aware UTC datetime, or None. Never a guess about a naive one."""
    try:
        parsed = datetime.datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(datetime.timezone.utc)


def _is_working_day(moment, schedule):
    return schedule != WEEKDAYS or moment.weekday() < 5


def boundary(now=None, schedule=DAILY, hour=DEFAULT_HOUR):
    """The most recent scheduled moment at or before `now`, or None.

    The anchor for everything else here: two ticks inside the same period
    resolve to the same boundary, which is what makes one digest per period
    fall out of `notify`'s idempotency rather than needing to be enforced.
    """
    if schedule == OFF:
        return None
    current = _utc(now or store.now())
    if current is None:
        return None
    candidate = current.replace(hour=hour, minute=0, second=0, microsecond=0)
    if candidate > current:
        candidate -= datetime.timedelta(days=1)
    # At most a week back: a schedule with no working day in seven does not
    # exist, so a loop that cannot end is a bug rather than a configuration.
    for _ in range(7):
        if _is_working_day(candidate, schedule):
            return candidate
        candidate -= datetime.timedelta(days=1)
    return None


def previous(moment, schedule=DAILY):
    """The scheduled moment before this one."""
    candidate = moment - datetime.timedelta(days=1)
    for _ in range(7):
        if _is_working_day(candidate, schedule):
            return candidate
        candidate -= datetime.timedelta(days=1)
    return moment - datetime.timedelta(days=1)


def digest_id(workspace, until):
    """The id `digest.announce` will produce for this workspace and period."""
    return notify.notification_id(notify.OPERATIONS_DIGEST, workspace,
                                  workspace=workspace, until=until)


def delivered(workspace, until, rows=None):
    """Has this exact period already been announced? Read from the log."""
    return notify.get(digest_id(workspace, until), rows=rows)


def _last_until(workspace, until, rows=None):
    """When this workspace's last digest ended, if there was one.

    Read from the notification log's identifiers rather than from its
    timestamp: `at` is when the row was written, and the window is what the
    row was about.
    """
    best = None
    for row in notify.history(workspace, notify.OPERATIONS_DIGEST,
                              limit=100000, rows=rows):
        stamp = _utc((row.get("ids") or {}).get("until"))
        if stamp is None or stamp >= until:
            continue
        if best is None or stamp > best:
            best = stamp
    return best


def period_for(workspace, until, schedule=DAILY, rows=None):
    """The window this workspace's next digest should cover.

    Starts where its last one ended, so a process that was down for two days
    reports those two days rather than dropping them. Beyond
    `MAX_CATCH_UP_DAYS` that stops being a digest, and the fallback is
    reported rather than silently applied.
    """
    step = previous(until, schedule)
    last = _last_until(workspace, until, rows=rows)
    if last is None:
        return {"since": step.isoformat(), "until": until.isoformat(),
                "basis": "first digest for this workspace"}
    if (until - last).days > MAX_CATCH_UP_DAYS:
        return {"since": step.isoformat(), "until": until.isoformat(),
                "basis": f"the last digest was more than "
                         f"{MAX_CATCH_UP_DAYS} days ago, so this covers one "
                         f"period rather than the whole gap"}
    if last >= step:
        return {"since": last.isoformat(), "until": until.isoformat(),
                "basis": "since the last digest"}
    return {"since": last.isoformat(), "until": until.isoformat(),
            "basis": "since the last digest, catching up a missed period"}


# ------------------------------------------------------------------ the tick

SKIPPED = "already_delivered"
BUILT = "delivered"
FAILED = "failed"


def _one(workspace, until, schedule, config=None):
    """One workspace's digest for one period. Never raises.

    Isolated the way `replywatch.poll_once` is: one workspace whose config
    cannot be read must not stop the rest of the estate getting a digest.
    """
    already = delivered(workspace, until.isoformat())
    if already is not None:
        return {"workspace": workspace, "outcome": SKIPPED,
                "notification": already.get("id"),
                "status": already.get("status")}
    try:
        period = period_for(workspace, until, schedule)
        built = digest.build(workspace, since=period["since"],
                             until=period["until"], config=config)
        row = digest.announce(built)
        if row is None:
            return {"workspace": workspace, "outcome": FAILED,
                    "error": "the notification could not be built"}
        attempted = notify.deliver(row["id"])
        return {"workspace": workspace, "outcome": BUILT,
                "notification": row["id"],
                "status": (attempted or row).get("status"),
                "why": (attempted or row).get("why"),
                "basis": period["basis"],
                "window": built.get("window")}
    except Exception as exc:                                  # noqa: BLE001
        # Broad, and deliberately not silent. A digest that cannot be built
        # is reported as a failure for that workspace; the others carry on.
        return {"workspace": workspace, "outcome": FAILED,
                "error": f"{type(exc).__name__}: {exc}"[:300]}


def lock_file():
    return os.path.join(os.path.dirname(store.queue_path()), "digestwatch")


def tick(now=None, env=None, rows=None):
    """Deliver whatever is due, once. Safe to call as often as you like.

    Called every few minutes by the reply watcher's loop, and doing nothing
    is the ordinary outcome: the period's digest already exists, so the
    idempotent id finds it and this returns without building anything.
    """
    config = settings(env)
    if not config["enabled"]:
        # Distinct from the boundary refusal below, and it has to be: "no
        # digest is scheduled" and "the clock could not be read" are
        # different answers to an operator asking why nothing arrived.
        return {"schedule": OFF, "ran": False, "why": SCHEDULE_LABEL[OFF],
                "workspaces": []}

    until = boundary(now, config["schedule"], config["hour"])
    if until is None:
        return {"schedule": config["schedule"], "ran": False,
                "why": "no scheduled moment could be resolved from the clock",
                "workspaces": []}

    slugs = [w.get("slug") for w in ws.workspaces(rows) if w.get("slug")]
    try:
        with store.lock(for_path=lock_file(), timeout=LOCK_WAIT):
            done = [_one(slug, until, config["schedule"]) for slug in slugs]
    except store.QueueLocked:
        # Another process is doing exactly this. Skipping loses nothing:
        # the work is not queued, it is already happening.
        return {"schedule": config["schedule"], "ran": False,
                "period": until.isoformat(),
                "why": "another process is delivering this period",
                "workspaces": []}
    return {"schedule": config["schedule"], "ran": True,
            "period": until.isoformat(), "hour": config["hour"],
            "why": config["label"], "workspaces": done}


def hook(env=None):
    """The callable the reply watcher runs each tick, or None if off.

    Returned rather than always-on so the watcher's loop carries no
    knowledge of digests, and so an operator reading the boot output is
    told which of the two background jobs is running.
    """
    try:
        config = settings(env)
    except NotConfigured:
        raise
    if not config["enabled"]:
        return None
    return tick


# ----------------------------------------------------------------- reporting

def status(now=None, env=None, rows=None):
    """What the schedule is and what the last period actually did.

    Derived from the notification log, which is where a digest's fate is
    already recorded. Silence is reported as silence rather than as health:
    a workspace with no digest for the current period says so.
    """
    config = settings(env)
    until = boundary(now, config["schedule"], config["hour"])
    out = []
    for workspace in ws.workspaces(rows):
        slug = workspace.get("slug")
        if not slug:
            continue
        current = (delivered(slug, until.isoformat())
                   if until is not None else None)
        history = notify.history(slug, notify.OPERATIONS_DIGEST, limit=1)
        out.append({
            "workspace": slug,
            "this_period": (current or {}).get("status"),
            "last_at": (history[0].get("at") if history else None),
            "last_status": (history[0].get("status") if history else None),
            "last_covered_until": ((history[0].get("ids") or {}).get("until")
                                   if history else None),
        })
    return {"schedule": config["schedule"], "hour": config["hour"],
            "enabled": config["enabled"], "label": config["label"],
            "period": until.isoformat() if until is not None else None,
            "workspaces": out}


# The watcher ticks on `replywatch`'s interval, so a digest is never
# instant. An hour is long enough that a slow tick is not a fault and short
# enough that a schedule which stopped working is noticed the same morning.
GRACE_SECONDS = 3600


def problems(workspace=None, now=None, env=None, rows=None):
    """Only what somebody has to do something about. Usually nothing.

    Being off is not a problem here, and that is the difference between
    this and `replywatch.problems`. Reply polling off means outreach can go
    to somebody who already answered; a digest off means nobody chose to
    have one. Reporting a deliberate configuration as a fault is how a
    health page stops meaning anything.

    A digest that *failed to post* is not here either - it is already a row
    in the notification outbox, and the same failure in two places is two
    numbers that can disagree.
    """
    try:
        config = settings(env)
    except NotConfigured as exc:
        return [{"workspace": workspace, "state": "misconfigured",
                 "detail": str(exc),
                 "label": "the digest schedule is not usable"}]
    # No `enabled` check. `boundary` already answers OFF with None, and a
    # second guard reaching the same answer is one a mutation can remove
    # without any test noticing - which is how a guard becomes decorative.
    until = boundary(now, config["schedule"], config["hour"])
    current = _utc(now or store.now())
    if until is None or current is None:
        return []
    if (current - until).total_seconds() < GRACE_SECONDS:
        return []                      # too soon to call it late

    out = []
    for entry in ws.workspaces(rows):
        slug = entry.get("slug")
        if not slug or (workspace and slug != workspace):
            continue
        if delivered(slug, until.isoformat()) is not None:
            continue
        out.append({
            "workspace": slug,
            "state": "missing",
            "period": until.isoformat(),
            "detail": f"no digest for the period ending {until.isoformat()}",
            "label": "the scheduled digest did not run"})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m src.digestwatch",
        description="The daily digest on a schedule. Sends no outreach.")
    parser.add_argument("--once", action="store_true",
                        help="deliver whatever is due and exit")
    parser.add_argument("--status", action="store_true",
                        help="the schedule and what the last period did")
    args = parser.parse_args(argv)

    try:
        report = status() if (args.status or not args.once) else None
    except NotConfigured as exc:
        print(f"  refused: {exc}")
        return 2

    if report is not None:
        print(f"  schedule: {report['label']}")
        if report["period"]:
            print(f"  current period ends {report['period']}")
        for row in report["workspaces"]:
            state = row["this_period"] or "not delivered"
            print(f"    {row['workspace']:20} {state:12} "
                  f"last: {row['last_at'] or 'never'}")
        return 0

    try:
        result = tick()
    except NotConfigured as exc:
        print(f"  refused: {exc}")
        return 2
    if not result["ran"]:
        print(f"  nothing ran: {result['why']}")
        return 0
    print(f"  period ending {result['period']} - {result['why']}")
    for row in result["workspaces"]:
        detail = row.get("error") or row.get("status") or ""
        print(f"    {row['workspace']:20} {row['outcome']:18} {detail}")
    print("\n  A digest is a summary. Nothing was sent to a prospect, and")
    print("  posting to Slack still needs SLACK_LIVE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
