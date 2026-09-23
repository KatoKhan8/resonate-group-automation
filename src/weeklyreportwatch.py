"""When the weekly report is due, and the half-hour in which it can be stopped.

OPERATOR, 2026-09-23, the second increment: "Monday 08:00 local schedule,
07:30 preview in `#resonate-os` with a stop, PDF via `clientreport` from the
report's data dict under the new vocabulary, '@Resonate OS send me the weekly
report' in thread."

## THE PREVIEW IS THE FEATURE, NOT A COURTESY

Thirty minutes before a document goes to a client, the same document goes to
`#resonate-os` where a person can stop it. That window is the whole design:
this system has posted a wrong number to a client channel once - the
2026-09-22 14:42 report that marked all 69 domains "no sends in the last 7
days" on a day those mailboxes sent 494 - and the correction still has to be
sent by hand, in Croatian, by a person, because the channel is Slack Connect
and the app is the only thing that can post there.

A preview nobody can act on is a notification. **The stop is what makes it a
preview**, so the stop is a stored decision with a name against it, not a
flag somebody sets in their head.

## THE STOP IS RECORDED, THE SEND IS NOT ASSUMED

Three states for one Monday, and the absence of a record is not one of them:

    (nothing)   not previewed yet
    previewed   the 07:30 post went out; the window is open
    stopped     a person stopped it, with a name and a reason
    delivered   the 08:00 post went out

**Nothing here posts if the preview did not.** A run that starts at 07:45 -
a restart, a machine that was asleep, a loop somebody started late - has
missed the window in which the report could have been stopped, and posting
anyway would be posting an unreviewed client document. It waits for next
week and says so. `MISSED_PREVIEW` is a first-class outcome for exactly
that, because the alternative is a silent send that nobody chose.

## LOCAL MEANS ZAGREB, AND THE HOUR MOVES WITH DST

The operator said "local". `digestwatch` learned this the hard way with a
UTC hour that has to be hand-moved on 2026-10-25; this module stores the
zone and converts, so DST is arithmetic rather than a diary entry. The
readback always reports the local time it actually fired at, so a wrong hour
is visible rather than inferred from a late message.

## IDEMPOTENT BY THE MONDAY, NOT BY THE CLOCK

`report_id` keys on the workspace and the Monday's date. A restart, a second
process or a clock that steps backwards cannot produce two previews or two
posts, and cannot reopen a window a person already closed.
"""
import datetime
import json
import os

try:                                                            # 3.9+
    from zoneinfo import ZoneInfo
except ImportError:                                             # pragma: no cover
    ZoneInfo = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: "Local" is the operator's local, which is where this business is.
TIMEZONE = "Europe/Zagreb"

#: Monday. `datetime.weekday()` is 0-based from Monday.
WEEKDAY = 0

#: The client post, local.
POST_HOUR = 8
POST_MINUTE = 0

#: The preview into `#resonate-os`, local. Thirty minutes of window.
PREVIEW_HOUR = 7
PREVIEW_MINUTE = 30

#: Where the preview goes. Never a client channel.
PREVIEW_CHANNEL = "#resonate-os"

JOURNAL_NAME = "slack-weekly-report.jsonl"
JOURNAL_VAR = "SLACK_WEEKLY_REPORT"

#: Outcomes of one tick, per workspace.
PREVIEWED = "previewed"
DELIVERED = "delivered"
STOPPED = "stopped"
ALREADY = "already_done"
WAITING = "not_due"
MISSED_PREVIEW = "missed_preview"
FAILED = "failed"

OUTCOMES = (PREVIEWED, DELIVERED, STOPPED, ALREADY, WAITING,
            MISSED_PREVIEW, FAILED)


def zone():
    """The local zone, or UTC when `zoneinfo` has no database.

    Returning UTC silently would move every post by an hour or two, so the
    caller is told which it got - `settings()` carries it into the readback.
    """
    if ZoneInfo is None:
        return datetime.timezone.utc
    try:
        return ZoneInfo(TIMEZONE)
    except Exception:                                           # noqa: BLE001
        return datetime.timezone.utc


def zone_is_real():
    """False when we fell back to UTC. The readback prints this."""
    return zone() is not datetime.timezone.utc


def _now(now=None):
    if now is None:
        return datetime.datetime.now(tz=zone())
    if now.tzinfo is None:
        return now.replace(tzinfo=datetime.timezone.utc).astimezone(zone())
    return now.astimezone(zone())


def monday_of(now=None):
    """The date of the Monday of `now`'s local week."""
    moment = _now(now)
    return (moment - datetime.timedelta(days=moment.weekday())).date()


def _at(monday, hour, minute):
    return datetime.datetime(monday.year, monday.month, monday.day,
                             hour, minute, tzinfo=zone())


def preview_at(now=None):
    """The local moment this week's preview is due."""
    return _at(monday_of(now), PREVIEW_HOUR, PREVIEW_MINUTE)


def post_at(now=None):
    """The local moment this week's client post is due."""
    return _at(monday_of(now), POST_HOUR, POST_MINUTE)


def report_id(workspace, monday):
    """One key per workspace per Monday. The whole of the idempotency."""
    return "weekly:%s:%s" % (workspace, monday)


# ------------------------------------------------------------- the journal

def path():
    override = os.environ.get(JOURNAL_VAR)
    if override:
        return os.path.abspath(override)
    return os.path.join(ROOT, "work", JOURNAL_NAME)


def _append(row):
    target = path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def load():
    target = path()
    if not os.path.exists(target):
        return []
    rows = []
    with open(target, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                # A half-written line from a killed process is skipped, not
                # raised on. One corrupt row must not stop this week's post.
                continue
    return rows


def rows_for(workspace, monday, rows=None):
    key = report_id(workspace, monday)
    return [r for r in (load() if rows is None else rows)
            if r.get("report_id") == key]


def state_of(workspace, monday, rows=None):
    """`None`, `previewed`, `stopped` or `delivered`.

    LAST WRITE WINS WITHIN A PRECEDENCE, not by position: `stopped` outranks
    `previewed` however they are ordered on disk, because a stop that arrived
    in the same second as a preview is still a stop. `delivered` outranks
    both - once a client has it, the state is what happened, not what
    somebody intended.
    """
    mine = rows_for(workspace, monday, rows)
    if not mine:
        return None
    kinds = {r.get("kind") for r in mine}
    for kind in (DELIVERED, STOPPED, PREVIEWED):
        if kind in kinds:
            return kind
    return None


def record_preview(workspace, monday, detail=None, at=None):
    return _append({"report_id": report_id(workspace, monday),
                    "kind": PREVIEWED, "workspace": workspace,
                    "monday": str(monday),
                    "at": _now(at).isoformat(), "detail": detail})


def record_delivery(workspace, monday, detail=None, at=None):
    return _append({"report_id": report_id(workspace, monday),
                    "kind": DELIVERED, "workspace": workspace,
                    "monday": str(monday),
                    "at": _now(at).isoformat(), "detail": detail})


def stop(workspace, monday, by, reason=None, at=None):
    """A person stops this week's client post.

    `by` IS REQUIRED AND IS NOT DEFAULTED. A stop with nobody's name on it
    is indistinguishable from a bug that suppressed a report, and the first
    question on the Monday a client does not get their document is who
    stopped it.
    """
    if not str(by or "").strip():
        raise ValueError("a stop must carry who stopped it")
    return _append({"report_id": report_id(workspace, monday),
                    "kind": STOPPED, "workspace": workspace,
                    "monday": str(monday), "by": str(by).strip(),
                    "at": _now(at).isoformat(), "reason": reason})


def stopped(workspace, monday, rows=None):
    return state_of(workspace, monday, rows) == STOPPED


# ------------------------------------------------------------- the decision

def decide(workspace, now=None, rows=None):
    """What should happen for one workspace, right now. Decides, never acts.

    Kept separate from the loop so the decision is testable without a Slack
    token, which is the property `slackfollowup` was missing when `due()`
    shipped read by nothing.
    """
    moment = _now(now)
    monday = monday_of(moment)
    state = state_of(workspace, monday, rows)
    out = {"workspace": workspace, "monday": str(monday),
           "local_now": moment.isoformat(),
           "preview_at": preview_at(moment).isoformat(),
           "post_at": post_at(moment).isoformat(),
           "state": state, "zone": TIMEZONE,
           "zone_resolved": zone_is_real()}

    if moment.weekday() != WEEKDAY:
        out["outcome"] = WAITING
        out["why"] = "not Monday"
        return out

    if state == DELIVERED:
        out["outcome"] = ALREADY
        out["why"] = "this Monday's report has already gone to the client"
        return out
    if state == STOPPED:
        out["outcome"] = STOPPED
        out["why"] = "a person stopped this Monday's report"
        return out

    if moment < preview_at(moment):
        out["outcome"] = WAITING
        out["why"] = "before the preview"
        return out

    if state is None:
        if moment >= post_at(moment):
            # THE WINDOW HAS PASSED AND NOBODY COULD HAVE USED IT. Posting
            # now would put an unreviewed client document in a client
            # channel, which is the one thing the preview exists to prevent.
            out["outcome"] = MISSED_PREVIEW
            out["why"] = ("the 07:30 preview never ran, so nobody had the "
                          "window in which to stop this; refusing to post "
                          "an unreviewed client document")
            return out
        out["outcome"] = PREVIEWED
        out["why"] = "the preview is due"
        return out

    # Previewed, not stopped.
    if moment < post_at(moment):
        out["outcome"] = WAITING
        out["why"] = "previewed; the stop window is open"
        out["window_closes_at"] = post_at(moment).isoformat()
        return out
    out["outcome"] = DELIVERED
    out["why"] = "previewed, not stopped, and the hour has come"
    return out


def status(workspaces, now=None, rows=None):
    """Every workspace's decision in one readback, for `monitors`."""
    rows = load() if rows is None else rows
    return {"read_at": _now(now).isoformat(),
            "zone": TIMEZONE, "zone_resolved": zone_is_real(),
            "workspaces": [decide(slug, now=now, rows=rows)
                           for slug in workspaces]}
