#!/usr/bin/env python3
"""The process that makes the agent's one offer real.

    py -3 -u scripts/slack_followup_loop.py --interval 60
    py -3 scripts/slack_followup_loop.py --once --dry-run   # decide only

OPERATOR, 2026-09-22: "No promises the agent cannot keep. If you want the
offer, build it: a client can say 'yes' and the agent posts once in that
thread when the first provider-confirmed send of the batch lands."

## WHY THIS IS A SEPARATE PROCESS

`src/slackfollowup.py` was written for exactly that, and it shipped with
`register()` wired into the conversation and `due()` READ BY NOTHING. A
client could say yes, a row was written, and then the same silence the
module exists to prevent - a promise with no mechanism, one level down and
harder to see, because a journal full of registered watches looks like a
working feature.

The agent loop cannot do this work itself. It blocks in
`socketmode.envelopes` waiting for a mention, and on a quiet afternoon that
is a blocking read returning nothing for an hour. A watch that fires only
when somebody happens to speak is not a watch. So this beats on its own
interval, like `reply_watch_loop` and every other monitor here.

## AND THE AGENT ASKS WHETHER IT IS RUNNING BEFORE IT OFFERS

`slackfollowup.deliverer_is_running()` reads this loop's heartbeat, and
`slackconversation.offer_is_available` returns None when it is cold. Not
started means not offered. That is the property that keeps "build the
mechanism" from degrading back into "write the sentence": the sentence is
unavailable unless the mechanism is beating.

## IT CONFIRMS THE CHANNEL BEFORE IT POSTS

A watch carries the channel and the workspace it was registered for.
Between registration and firing an operator can rebind that channel, and
posting the stored campaign ids into a channel that now belongs to somebody
else is a cross-client leak arriving a day late. So the binding is resolved
AGAIN at fire time, and a watch whose channel no longer resolves to its own
workspace is cancelled unposted, loudly.

## PROVIDER-CONFIRMED MEANS THE COUNTER MOVED

`slackagentreadback.campaign_by_id` and nothing else - the same reader the
agent answers from, whose import contract forbids the write path. Not
`active`, not `scheduled`, not a queue row with a date on it.
"""
import argparse
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (replies, slackagentreadback as readback,       # noqa: E402
                 slackfollowup as followup, slackscope, watchsink)
from src.providers import bison, load_env, slack                # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Read at call time, not at import, so a test run on the production
#: machine appends to its own temp file rather than to the journal an
#: operator reads to find out what was said to a client.
LOG_VAR = "SLACK_FOLLOWUP_LOG"
LOG = os.path.join(ROOT, "work", "slack-followups-delivered.jsonl")


def log_path():
    override = (os.environ.get(LOG_VAR) or "").strip()
    return os.path.abspath(override) if override else LOG


DEFAULT_INTERVAL = 60


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def emit(line):
    sys.stdout.write("%s %s\n" % (_now(), line))
    sys.stdout.flush()


def log(row):
    target = log_path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row, at=_now()), default=str) + "\n")


def read_counts(campaign_ids):
    """`{campaign_id: emails_sent}` for the ids a watch names.

    A campaign that cannot be read is ABSENT from the result rather than
    present as zero. `followup.due` compares against a baseline, and a zero
    standing in for an unreadable campaign is a send that never gets
    announced - a failure that is silent and in the quiet direction.
    """
    out = {}
    for campaign_id in campaign_ids or []:
        detail = readback.campaign_by_id(campaign_id) or {}
        value = detail.get("emails_sent")
        if isinstance(value, int):
            out[str(campaign_id)] = value
    return out


#: Pages of the reply feed one tick will walk. The walk is newest-first and
#: STOPS at the watch's own marker, so in steady state it reads one page;
#: this bounds the pathological case - a watch opened a week ago against an
#: estate that has since taken thousands of replies - rather than the normal
#: one. Past it the read is UNREADABLE, never "no replies".
REPLY_PAGE_CAP = 40


def _campaign_of(row):
    value = row.get("campaign_id")
    return str(value) if value is not None else None


def _is_human(row):
    """Did a PERSON write this? Two witnesses, and they must agree.

    OPERATOR, 2026-09-22: automated is never positive, and an out-of-office,
    a ticketing acknowledgement and an assistant writing on somebody else's
    behalf are all things nobody chose to say to us. `replies.is_automated`
    is the one definition of that - the 18:00 summary, the client-facing
    counts and the never-positive guarantee all read it.

    The provider offers a second witness on the row itself,
    `automated_reply`, and this trusts NEITHER alone. A reply is human only
    when our classifier says it is and the provider does not contradict it.
    FAIL-CLOSED ON DISAGREEMENT, because the two errors are not symmetrical:
    a missed human reply delays one message by a tick, and a false one tells
    a client an autoresponder was their first real answer - in a thread they
    opted into, in the direction that sounds like good news.
    """
    if row.get("automated_reply"):
        return False
    text = row.get("text_body") or row.get("subject") or ""
    try:
        verdict = replies.classify(str(text))
    except Exception:                                           # noqa: BLE001
        # A classifier that cannot answer is not a licence to call it human.
        return False
    classification = (verdict.get("classification")
                      if isinstance(verdict, dict) else verdict)
    return not replies.is_automated(classification)


def read_human_replies(watch):
    """How many replies a PERSON wrote to this watch's campaigns since it
    opened. `None` means the feed could not be read.

    Walks newest-first and stops at the watch's marker, so it reads what has
    arrived since the client opted in and nothing older. A row for another
    campaign is skipped rather than stopping the walk - the feed is the
    whole workspace's.
    """
    marker = watch.get("reply_marker")
    if not isinstance(marker, int):
        return None
    wanted = {str(i) for i in (watch.get("campaign_ids") or [])}
    if not wanted:
        return None
    seen, cursor, pages = 0, None, 0
    while True:
        try:
            rows, cursor = bison.fetch_replies(cursor=cursor)
        except Exception as exc:                                # noqa: BLE001
            emit("REPLY-FEED-UNREADABLE %s %s: %s"
                 % (watch.get("id"), type(exc).__name__, str(exc)[:160]))
            return None
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            ident = row.get("id")
            if isinstance(ident, int) and ident <= marker:
                # EVERYTHING FROM HERE IS OLDER THAN THE WATCH. The feed is
                # ordered, so this is the end of the walk and not a skip.
                return seen
            if bison.classify_reply_row(row) != "reply":
                continue
            if _campaign_of(row) not in wanted:
                continue
            if _is_human(row):
                seen += 1
        pages += 1
        if not cursor:
            return seen
        if pages >= REPLY_PAGE_CAP:
            # A PREFIX IS NOT AN ANSWER, and the same rule the queue read
            # follows: refuse rather than return part of it as the whole.
            emit("REPLY-FEED-TOO-LONG %s: stopped at %d pages without "
                 "reaching the watch's marker" % (watch.get("id"), pages))
            return None


def still_bound(watch):
    """Does this watch's channel still belong to the workspace it was for?"""
    scope = slackscope.resolve(channel=watch.get("channel"))
    return bool(scope.is_client
                and scope.workspace == watch.get("workspace"))


def deliver(watch, moved, dry_run=False, stage=None):
    """One watch, one post, then move it on. The write FOLLOWS the post.

    The order matters. Writing first and posting second loses the message
    when the post fails, and leaves the client on a watch that says it
    fired. Posting first and writing second can at worst repeat, and the
    thread is the one place a repeat is visible and harmless.

    TWO POSTS PER THREAD AND NEVER THREE. The send post ADVANCES the watch
    to the reply half rather than closing it; the reply post closes it. An
    expiry at either stage closes it, having said so once.
    """
    stage = stage or followup.stage_of(watch)
    if stage == followup.AWAITING_REPLY:
        text = followup.reply_message_for(watch, moved)
    else:
        text = followup.message_for(watch, moved)
    status = followup.FIRED if moved is not None else followup.EXPIRED
    if not still_bound(watch):
        followup.close(watch, followup.CANCELLED,
                       "the channel is no longer bound to %s"
                       % watch.get("workspace"))
        emit("REBOUND %s: %s is no longer %s's channel. Cancelled unposted."
             % (watch["id"], watch.get("channel"), watch.get("workspace")))
        log({"kind": "followup_cancelled_rebound", "watch": watch["id"],
             "channel": watch.get("channel")})
        return False
    if dry_run:
        emit("DRY-RUN %s -> %s: %s" % (watch["id"], status, text))
        return False
    try:
        slack.post({"kind": "slack_agent_followup",
                    "channel": watch["channel"], "text": text,
                    "thread_ts": watch.get("thread_ts")})
    except Exception as exc:                                    # noqa: BLE001
        # LOUD AND STILL OPEN. The watch is not closed, so the next tick
        # tries again - and if the failure is permanent the TTL closes it
        # as expired, which the client is told about rather than left in.
        emit("FOLLOWUP-POST-FAILED %s %s: %s"
             % (watch["id"], type(exc).__name__, str(exc)[:200]))
        log({"kind": "followup_post_failed", "watch": watch["id"],
             "error": type(exc).__name__, "detail": str(exc)[:300]})
        return False
    detail = "posted to %s" % watch.get("channel")
    if stage == followup.AWAITING_SEND and moved is not None:
        # THE SEND IS ANNOUNCED AND THE THREAD IS NOT FINISHED. Advancing
        # rather than closing is what makes the second half a promise the
        # client was actually given; `advance_to_reply` closes it instead
        # when no marker could be established, because then there is no
        # honest second post to make.
        after = followup.advance_to_reply(watch, detail)
        moved_to = followup.stage_of(after)
        emit("POSTED %s -> %s in %s" % (watch["id"], moved_to, watch["channel"]))
        log({"kind": "followup_posted", "watch": watch["id"],
             "stage": followup.AWAITING_SEND, "now": moved_to,
             "channel": watch["channel"], "moved": moved})
        return True
    followup.close(watch, status, detail)
    emit("POSTED %s -> %s in %s (%s)"
         % (watch["id"], status, watch["channel"], stage))
    log({"kind": "followup_posted", "watch": watch["id"], "status": status,
         "stage": stage, "channel": watch["channel"], "moved": moved})
    return True


def tick(dry_run=False):
    """One pass. Returns how many watches were delivered."""
    open_now = followup.open_watches()
    try:
        pending = followup.due(read_counts)
    except Exception as exc:                                    # noqa: BLE001
        emit("DUE-FAILED %s: %s" % (type(exc).__name__, str(exc)[:200]))
        log({"kind": "followup_due_failed", "error": type(exc).__name__,
             "detail": traceback.format_exc()[:1000]})
        pending = []
    try:
        pending_replies = followup.due_replies(read_human_replies)
    except Exception as exc:                                    # noqa: BLE001
        # SEPARATE FROM `due`'s FAILURE, deliberately. The two halves read
        # different feeds and one being down is not the other being down;
        # collapsing them would let a reply-feed outage stop a send from
        # ever being announced.
        emit("DUE-REPLIES-FAILED %s: %s" % (type(exc).__name__, str(exc)[:200]))
        log({"kind": "followup_due_replies_failed",
             "error": type(exc).__name__,
             "detail": traceback.format_exc()[:1000]})
        pending_replies = []
    delivered = 0
    for watch, moved in pending:
        if deliver(watch, moved, dry_run=dry_run,
                   stage=followup.AWAITING_SEND):
            delivered += 1
    for watch, count in pending_replies:
        if deliver(watch, count, dry_run=dry_run,
                   stage=followup.AWAITING_REPLY):
            delivered += 1
    # THE BEAT IS WRITTEN LAST AND UNCONDITIONALLY. It is what licenses the
    # agent to make the offer at all, so it has to mean "a pass completed",
    # not "a pass started".
    watchsink.beat(followup.WATCHER,
                   state={"open": len(open_now), "due": len(pending),
                          "delivered": delivered})
    return delivered


def serve(interval=DEFAULT_INTERVAL, once=False, dry_run=False):
    load_env()
    emit("SLACK FOLLOWUP DELIVERER starting. interval=%ds journal=%s"
         % (interval, followup.path()))
    emit("heartbeat: %s" % followup.heartbeat_path())
    while True:
        try:
            tick(dry_run=dry_run)
        except Exception as exc:                                # noqa: BLE001
            emit("TICK-ERROR %s: %s" % (type(exc).__name__, str(exc)[:200]))
            log({"kind": "error", "error": type(exc).__name__,
                 "detail": traceback.format_exc()[:1000]})
        if once:
            return 0
        time.sleep(max(5, int(interval)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="decide and print; post nothing, close nothing")
    args = parser.parse_args(argv)
    return serve(interval=args.interval, once=args.once,
                 dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
