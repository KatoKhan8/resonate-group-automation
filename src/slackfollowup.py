#!/usr/bin/env python3
"""An offer the agent can actually keep: tell me when the first send lands.

OPERATOR, 2026-09-22: "No promises the agent cannot keep. Remove 'I'll
check with the team' and 'want me to send you an update' unless a real
mechanism exists. If you want the offer, build it: a client can say 'yes'
and the agent posts once in that thread when the first provider-confirmed
send of the batch lands."

## THE FAULT THIS REPLACES

The first live client answer ended "Želite li da vam pošaljem kratki update
nakon što prvi batch-1 mailovi danas izađu?" - would you like a short
update once the first batch-1 mails go out today. Nothing anywhere could
have produced that update. The client says yes and waits.

A promise with no mechanism is worse than no offer, because the client
stops asking.

## WHAT THIS IS

A registered WATCH. A client says yes; a row is written; a loop asks the
provider whether any campaign in the batch has a non-zero `emails_sent`;
the first time one does, the agent posts once into the same thread, in the
language the conversation was in, and the watch is closed.

    registered -> fired      the send happened, one message posted
    registered -> expired    nothing sent inside the window; says so once
    registered -> cancelled  somebody withdrew it

## PROVIDER-CONFIRMED MEANS THE COUNTER MOVED

Not "scheduled", not "active", not a queue row with a date on it. The whole
register of this project exists because those three were each read as a
send at some point. The watch fires on `emails_sent` moving above the value
recorded when it was registered - a baseline, so a campaign that had
already sent does not fire it instantly.

## IT POSTS NOTHING ITSELF

Like every other part of this agent: it decides, and the loop posts. There
is no `slack.post` in this module.
"""
import json
import os
import time

REGISTERED = "registered"
FIRED = "fired"
EXPIRED = "expired"
CANCELLED = "cancelled"

#: How long an unfired watch stays open. A day: past that, "the first send
#: of the batch" is no longer the thing anybody asked about, and a message
#: arriving three days later reads as a system that lost track.
TTL_SECONDS = 24 * 3600

JOURNAL_NAME = "slack-followups.jsonl"
JOURNAL_VAR = "SLACK_FOLLOWUPS"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The deliverer's heartbeat, under the same name every other monitor here
#: beats under. `scripts/slack_followup_loop.py` writes it.
WATCHER = "slack-followup"

#: How stale that beat may be before the OFFER STOPS BEING MADE.
#:
#: THIS IS THIS MODULE'S OWN FAULT, ONE LEVEL DOWN. This file was written
#: because the agent offered an update nothing could deliver. It then
#: shipped with `register()` wired into the conversation and NOTHING
#: reading `due()` - so a client says yes, a row is written, and the same
#: silence follows. A registered watch is not a mechanism; a process that
#: fires it is. So the agent asks whether that process is beating before it
#: opens its mouth, and stays quiet when it is not.
#:
#: Three minutes over a 60-second interval: long enough for one missed tick
#: and a reconnect, short enough that a deliverer killed an hour ago cannot
#: license an offer.
MAX_BEAT_AGE_SECONDS = 180

#: A test, or an operator proving the gate, points this at its own file.
HEARTBEAT_VAR = "SLACK_FOLLOWUP_HEARTBEAT"


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def path():
    override = (os.environ.get(JOURNAL_VAR) or "").strip()
    if override:
        return os.path.abspath(override)
    try:
        from . import store
        return os.path.join(os.path.dirname(store.queue_path()),
                            JOURNAL_NAME)
    except Exception:                                           # noqa: BLE001
        return os.path.join(ROOT, "work", JOURNAL_NAME)


def _append(row):
    from . import store
    target = path()
    store.refuse_production_write(target)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row, at=_now()), default=str) + "\n")
    return row


def load():
    """Every watch, latest state per id."""
    target = path()
    if not os.path.isfile(target):
        return []
    latest = {}
    with open(target, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("id"):
                latest[row["id"]] = row
    return sorted(latest.values(), key=lambda r: str(r.get("registered_at")))


def open_watches():
    return [r for r in load() if r.get("status") == REGISTERED]


def for_thread(channel, thread_ts):
    for row in open_watches():
        if row.get("channel") == channel and row.get("thread_ts") == thread_ts:
            return row
    return None


def register(channel, thread_ts, workspace, campaign_ids, baseline,
             language=None, asked_by=None):
    """Open one watch. Refuses a second on the same thread."""
    import secrets

    existing = for_thread(channel, thread_ts)
    if existing:
        return existing
    row = {
        "id": "fu-%s" % secrets.token_hex(3),
        "status": REGISTERED,
        "channel": channel,
        "thread_ts": thread_ts,
        "workspace": workspace,
        "campaign_ids": [str(i) for i in (campaign_ids or [])],
        # THE COUNTER WHEN THE WATCH OPENED. Without it a campaign that has
        # already sent fires the watch on the first check, and the client
        # gets "the first mail has gone out" about mail that went out
        # before they asked.
        "baseline": {str(k): int(v) for k, v in (baseline or {}).items()},
        "language": language,
        "asked_by": asked_by,
        "registered_at": _now(),
        "expires_epoch": int(time.time()) + TTL_SECONDS,
    }
    return _append(row)


def close(watch, status, detail=None):
    return _append(dict(watch, status=status, closed_at=_now(),
                        detail=detail))


def heartbeat_path():
    override = (os.environ.get(HEARTBEAT_VAR) or "").strip()
    if override:
        return os.path.abspath(override)
    from . import watchsink
    return watchsink.heartbeat_path(WATCHER)


def deliverer_is_running(now=None):
    """Is anything actually firing these watches right now?

    Read from the heartbeat file rather than from a flag somebody sets,
    because a flag records an intention and a beat records a process. The
    deliverer being configured, installed, committed and not started is the
    exact state this returns False for, and it is the state the feature
    shipped in.

    An unreadable or absent beat is False. There is no benefit of the doubt
    available here: the cost of a wrong True is a client told they will be
    updated and never updated, which is the one outcome the module exists
    to prevent.
    """
    target = heartbeat_path()
    try:
        with open(target, encoding="utf-8") as handle:
            row = json.load(handle)
    except Exception:                                           # noqa: BLE001
        return False
    epoch = row.get("epoch")
    if not isinstance(epoch, (int, float)):
        stamp = str(row.get("at") or "").replace("Z", "+00:00")
        try:
            import datetime
            epoch = datetime.datetime.fromisoformat(stamp).timestamp()
        except Exception:                                       # noqa: BLE001
            return False
    return (float(now if now is not None else time.time()) - float(epoch))         <= MAX_BEAT_AGE_SECONDS


def due(read_counts):
    """`[(watch, fired campaigns)]` for watches whose counter has moved.

    `read_counts(campaign_ids) -> {id: emails_sent}` is passed in rather
    than called from here, so this module reaches no provider and the loop
    owns the read.
    """
    out = []
    now = int(time.time())
    for watch in open_watches():
        if now > int(watch.get("expires_epoch") or 0):
            out.append((watch, None))
            continue
        counts = read_counts(watch.get("campaign_ids") or [])
        moved = {}
        for campaign_id, count in (counts or {}).items():
            before = int((watch.get("baseline") or {}).get(campaign_id, 0))
            if isinstance(count, int) and count > before:
                moved[campaign_id] = count - before
        if moved:
            out.append((watch, moved))
    return out


#: What gets posted. Facts only, in the language the thread was in, and it
#: says WHICH campaigns moved rather than "it has started".
MESSAGE = {
    "hr": "Javljam kako smo se dogovorili: prvi mailovi iz ovog batcha su "
          "upravo poslani — %s. Ovo je potvrda od providera (brojač "
          "poslanih se pomaknuo), ne raspored.",
    "en": "As promised: the first emails from this batch have now been "
          "sent — %s. This is the provider's own confirmation (its sent "
          "counter moved), not a schedule.",
}

EXPIRED_MESSAGE = {
    "hr": "Javljam kako smo se dogovorili: u zadnjih 24 sata nijedan mail "
          "iz ovog batcha još nije potvrđen kao poslan. Ne zatvaram temu, "
          "samo da ne čekate bez informacije.",
    "en": "As promised, an update: no email from this batch has been "
          "confirmed as sent in the last 24 hours. Nothing is wrong on "
          "your side - telling you rather than leaving you waiting.",
}


def message_for(watch, moved):
    code = (watch.get("language") or "en")
    if moved is None:
        template = EXPIRED_MESSAGE.get(code) or EXPIRED_MESSAGE["en"]
        return template
    template = MESSAGE.get(code) or MESSAGE["en"]
    detail = ", ".join("%s: %d" % (cid, count)
                       for cid, count in sorted(moved.items()))
    return template % detail
