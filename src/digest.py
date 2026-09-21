#!/usr/bin/env python3
"""A day in one workspace: what happened, and what is still waiting.

## Why this exists

`notify` routes an ordinary reply to `NOWHERE` on purpose. A neutral or
negative reply belongs in the Reply Center where somebody is already
looking, and an unsubscribe is a suppression to process rather than an
interruption to send. That decision is right, and it leaves a gap: if
nothing ever summarises those replies, the quiet ones are invisible unless
an operator goes looking.

This is the other half of that trade. One message a day carrying the shape
of the day - twelve replies, four of them positive, three out of office -
instead of nineteen interruptions carrying one fact each.

## Every number is counted, never estimated

Replies come from `account.replies`, confirmed sends from
`account.touches(confirmed_only=True)`, outstanding work from
`tasks.collect`. Nothing here derives a figure from a plan: a prepared
payload is not a send, and an approved campaign has contacted nobody.

Where a thing cannot be counted it is absent rather than zero. "We did not
measure this" and "this did not happen" are different sentences and a
digest that prints 0 for both is lying about one of them.

## Two halves, and they are different questions

*What happened* is bounded by a window and looks backwards. *What is
waiting* is true right now and comes from `tasks`, which holds no state of
its own - so the digest and the work queue cannot disagree about how much
is outstanding.

## It does not post

Building a digest records a notification. Whether anything reaches Slack is
`SLACK_LIVE`'s business and nothing here changes that.
"""
import argparse
import collections
import datetime
import json

from . import account, clientapproval, clients, notify, store, tasks

WINDOW_HOURS = 24

# Reply classifications worth naming separately in a summary. Anything else
# is counted in the total and not broken out - a digest with twenty rows is
# a digest nobody reads to the end.
NAMED = ("positive", "out_of_office", "not_relevant", "negative",
         "unsubscribe", "neutral")

LABEL = {
    "positive": "Positive",
    "out_of_office": "Out of office",
    "not_relevant": "Wrong person or not a fit",
    "negative": "Negative",
    "unsubscribe": "Unsubscribed",
    "neutral": "Neutral",
    "unknown": "Needs a person to classify",
}


def _moment(value):
    """An aware datetime, or None. Never a guess."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # Naive and aware do not compare, and assuming UTC would silently
        # move an event by hours. Unreadable is unknown.
        return None
    return parsed


def window(since=None, until=None, hours=WINDOW_HOURS, now=None):
    """The period this digest covers, stated rather than implied."""
    end = _moment(until) or _moment(now) or _moment(store.now())
    if end is None:
        return None
    start = _moment(since) or (end - datetime.timedelta(hours=hours))
    return {"since": start.isoformat(), "until": end.isoformat(),
            "hours": round((end - start).total_seconds() / 3600, 1)}


def _within(stamp, period):
    at = _moment(stamp)
    if at is None:
        return False
    return (_moment(period["since"]) <= at <= _moment(period["until"]))


def activity(recs, period):
    """What actually happened in the window, counted from the event log."""
    replies = collections.Counter()
    unclassified = 0
    people_replied = set()
    touches = 0
    people_touched = set()

    for rec in recs:
        for reply in account.replies(rec):
            if not _within(reply.get("at"), period):
                continue
            classification = reply.get("classification")
            if reply.get("type") != "reply_classified":
                # `reply_received` and the positive marker are the same
                # message seen twice. Counting them would triple a day.
                continue
            if not classification:
                unclassified += 1
            else:
                replies[classification] += 1
            key = (rec.get("id"), reply.get("contact_key"))
            people_replied.add(key)

        for touch in account.touches(rec, confirmed_only=True):
            if not _within(touch.get("at"), period):
                continue
            touches += 1
            people_touched.add((rec.get("id"), touch.get("contact_key")))

    named = {kind: replies.get(kind, 0) for kind in NAMED if replies.get(kind)}
    other = sum(count for kind, count in replies.items() if kind not in NAMED)
    return {
        "confirmed_touches": touches,
        "people_contacted": len(people_touched),
        "replies": sum(replies.values()) + unclassified,
        "people_replied": len(people_replied),
        "by_classification": named,
        "other_classifications": other,
        "unclassified": unclassified,
    }


def build(workspace, recs=None, config=None, since=None, until=None,
          hours=WINDOW_HOURS, now=None, today=None):
    """One workspace's day. Reads; writes nothing; posts nothing."""
    recs = store.load() if recs is None else recs
    recs = [r for r in recs if not workspace or r.get("client") == workspace]
    if config is None and workspace:
        try:
            config = clients.load(workspace)
        except Exception:                                 # noqa: BLE001
            config = None

    period = window(since=since, until=until, hours=hours, now=now)
    happened = activity(recs, period) if period else None
    outstanding = tasks.collect(workspace, recs=recs, config=config,
                                today=today)
    # CLIENT APPROVAL SUPPLY CONSTRAINT: how many accounts are waiting for
    # the client to approve them. This is the bucket that makes the supply
    # constraint visible in the daily digest.
    approval_counts = clientapproval.counts(workspace or "productive")
    return {
        "workspace": workspace,
        "window": period,
        "activity": happened,
        "outstanding": tasks.summarise(outstanding),
        "outstanding_total": sum(row["count"] for row in outstanding),
        "counts": tasks.counts(outstanding),
        "awaiting_client_approval": approval_counts.get("pending", 0),
        "client_approval": approval_counts,
    }


def lines(digest):
    """The digest as sentences, for a Slack body or a terminal.

    Written so the first line is the one worth reading if somebody reads
    only one.
    """
    out = []
    workspace = digest.get("workspace") or "workspace"
    period = digest.get("window") or {}
    happened = digest.get("activity") or {}

    replies = happened.get("replies", 0)
    positive = (happened.get("by_classification") or {}).get("positive", 0)
    waiting = digest.get("outstanding_total", 0)

    out.append(f"{workspace} - last {period.get('hours', WINDOW_HOURS)}h")
    out.append("")
    if replies:
        out.append(f"Replies: {replies} from {happened['people_replied']} "
                   f"people, {positive} positive")
    else:
        out.append("Replies: none")
    if happened.get("confirmed_touches"):
        out.append(f"Confirmed sends: {happened['confirmed_touches']} to "
                   f"{happened['people_contacted']} people")
    else:
        # Not "0 sent". Nothing in this build sends, and a zero would read
        # as a bad day rather than as a system that cannot do it yet.
        out.append("Confirmed sends: none recorded")

    for kind, count in (happened.get("by_classification") or {}).items():
        out.append(f"  {LABEL.get(kind, kind)}: {count}")
    if happened.get("unclassified"):
        out.append(f"  {LABEL['unknown']}: {happened['unclassified']}")

    out.append("")
    if waiting:
        out.append(f"Waiting for somebody: {waiting}")
        for row in digest.get("outstanding") or []:
            out.append(f"  {row['label']}: {row['count']}")
    else:
        out.append("Waiting for somebody: nothing")

    awaiting = digest.get("awaiting_client_approval", 0)
    approval = digest.get("client_approval") or {}
    out.append("")
    out.append(f"Awaiting client approval: {awaiting}"
               f"  (approved {approval.get('approved', 0)}"
               f"  suppressed {approval.get('suppressed', 0)}"
               f"  rejected {approval.get('rejected', 0)})")
    return out


def announce(digest):
    """Record the digest as a notification. Posting is `SLACK_LIVE`'s call.

    Routed to the operations channel at INFO: it is the thing that makes
    routing ordinary replies to NOWHERE reasonable, and it is by
    construction never urgent - anything urgent has its own kind and has
    already been sent.
    """
    period = digest.get("window") or {}
    return notify.notify(
        notify.OPERATIONS_DIGEST, digest.get("workspace"),
        fields={"window": f"{period.get('hours', WINDOW_HOURS)}h",
                "summary": "\n".join(lines(digest))},
        ids={"workspace": digest.get("workspace"),
             "until": period.get("until")})


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m src.digest",
        description="What happened in one workspace, and what is waiting.")
    parser.add_argument("--client", required=True)
    parser.add_argument("--hours", type=int, default=WINDOW_HOURS)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--announce", action="store_true",
                        help="record it as a notification. Posting to Slack "
                             "still needs SLACK_LIVE")
    args = parser.parse_args(argv)

    digest = build(args.client, hours=args.hours)
    if args.json:
        print(json.dumps(digest, indent=2))
    else:
        for line in lines(digest):
            print("  " + line if line else "")
    if args.announce:
        recorded = announce(digest)
        print()
        print("  recorded as " + str((recorded or {}).get("status")))
        print("  Nothing was posted. Slack posting needs SLACK_LIVE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
