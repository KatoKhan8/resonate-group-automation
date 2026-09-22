#!/usr/bin/env python3
"""What we said we would do, and whether we did it.

`docs/SLACK-AGENT-EXPECTATIONS.md` ends on this and calls it the
highest-value thing the history suggests building:

    Fifty-three promise-shaped messages in ten days, and NO SYSTEM ANYWHERE
    TRACKS WHETHER ANY OF THEM WAS KEPT. The domain-list promise on Monday
    was kept in 119 minutes with the wrong artefact, and the only reason
    anybody knows is that the client replied.

It was not on the tool list because it needed a decision about what counts
as delivery. That decision now exists.

OPERATOR, 2026-09-22: "a promise is delivered when, in the same thread and
after it, an internal user posts a file, a link, a list (3+ lines) or an
explicit delivery word (sent / poslano / evo / done / here you go), or when
the system posts a matching artifact. Otherwise it is open once its stated
time has passed, and appears in the 07:15 briefing internally only. Clients
never see the promise scan."

## FOUR STATES, AND ONLY ONE OF THEM IS A REPROACH

    delivered   something arrived in the thread after it
    open        the stated time has passed and nothing did
    due         a stated time that has not arrived yet
    undated     a promise with no time in it

`open` is the only one the briefing leads with. The distinction between
`open` and `undated` is the whole difference between a scan people read and
a scan people turn off: calling a promise late when nobody said when is how
a monitor teaches its readers to ignore it.

## "DANAS ILI SUTRA" IS JUDGED ON SUTRA

A promise with two times in it is measured against the LATER one. The
alternative cries wolf at lunchtime on a promise that was kept, and one
false alarm costs more attention than one missed promise.

## THE SAME THREAD, EXACTLY AS SPECIFIED

Delivery counts in the promise's own thread. A promise made at channel
level with no replies can therefore only be delivered inside its own
thread - a separate later message in the channel does not close it, and it
will read as `open`. That is the operator's definition taken literally
rather than widened, because widening it to "anything the same person said
later in the channel" would mark a promise delivered on the strength of an
unrelated message.

## IT IS INTERNAL, AND STRUCTURALLY SO

The scan reads Resonate's own rooms and reports on Resonate's own
commitments. `slackagenttools` registers it INTERNAL-only, so there is no
scope in which a client channel can call it, and no argument that changes
that. A client never sees which of our promises we missed.
"""
import json
import os
import re
import time

DELIVERED = "delivered"
OPEN = "open"
DUE = "due"
UNDATED = "undated"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: How far back a scan looks, in days. Ten, because that is the window the
#: expectations document measured and the one the briefing is about. A
#: promise from last month is history, not a worklist.
WINDOW_DAYS = 10


# ------------------------------------------------------- what is a promise

#: Commitments that imply an ARTEFACT will arrive. Deliberately narrower
#: than "anything forward-looking": "momenat, gledam" and "on it" are
#: acknowledgements, and a scan that calls them promises fills the briefing
#: with things nobody owes anybody. A false promise costs more attention
#: than a missed one, because it is the one that trains people to skip the
#: section.
_PROMISE = re.compile(
    r"("
    r"posl(?:at|a[tć])\s*[čc]u|posljemo|po[sš]aljemo|po[sš]aljem|"
    r"[sš]aljem(?:o)?|javit\s*[čc]u|javim(?:o)?|javljam\s+(?:ti|vam)|"
    r"pripremit\s*[čc]u|pripremam|napravit\s*[čc]u|dostavljam|"
    r"provjerit\s*[čc]u|slo[zž]it\s*[čc]u|sredit\s*[čc]u|"
    r"i\s*(?:'|’)?ll\s+(?:send|share|put\s+together|get\s+you|"
    r"have|prepare|pull|write\s+up|forward|come\s+back)|"
    r"i\s+will\s+(?:send|share|get\s+back|prepare|forward)|"
    r"we\s*(?:'|’)?ll\s+(?:send|share|get\s+you|have|prepare|"
    r"put\s+together)|we\s+will\s+(?:send|share|prepare)|"
    r"sending\s+(?:it|you|over|through)|will\s+get\s+(?:it|you|this)\s+to"
    r")", re.I)

#: A question is never a promise, however it is worded. "možeš poslati
#: popis?" contains the verb and asks for the thing.
_ASKS = re.compile(r"\?\s*$|^\s*(?:mo[zž]e[sš]|can\s+you|could\s+you|"
                   r"would\s+you|please)\b", re.I)


# ------------------------------------------------------- when it was for

#: `(pattern, days from the promise)`. Matched in order and the LATEST
#: match wins, so "danas ili sutra" is judged on tomorrow.
_WHEN = (
    (re.compile(r"\b(?:odmah|right\s+away|now|within\s+the\s+hour)\b",
                re.I), 0),
    (re.compile(r"\b(?:danas|today|do\s+kraja\s+dana|"
                r"by\s+end\s+of\s+day|eod)\b", re.I), 0),
    (re.compile(r"\b(?:sutra|tomorrow)\b", re.I), 1),
    (re.compile(r"\b(?:prekosutra|day\s+after\s+tomorrow)\b", re.I), 2),
    (re.compile(r"\b(?:ovaj\s+tjedan|this\s+week|do\s+kraja\s+tjedna|"
                r"by\s+(?:the\s+)?end\s+of\s+(?:the\s+)?week|"
                r"do\s+petka|by\s+friday)\b", re.I), 5),
    (re.compile(r"\b(?:idu[cć]i\s+tjedan|next\s+week|"
                r"u\s+ponedjeljak|on\s+monday)\b", re.I), 7),
)


def deadline_days(text):
    """Days from the promise to when it was due, or None if unstated.

    The LATEST stated time wins. "pošaljemo najnoviju listu danas ili
    sutra" is a promise about tomorrow; treating it as a promise about
    today makes the scan wrong at 17:00 on a day nobody broke anything.
    """
    body = str(text or "")
    found = [days for pattern, days in _WHEN if pattern.search(body)]
    return max(found) if found else None


# ------------------------------------------------------ what is delivery

#: Slack wraps links as `<http...|label>`; a bare URL also counts.
_LINK = re.compile(r"<https?://[^>\s]+|https?://\S+", re.I)

#: The operator's list, plus the inflections the same words arrive in.
_DELIVERY_WORD = re.compile(
    r"\b(?:sent|poslano|poslala|poslao|poslali|evo(?:\s+ga|\s+ti|\s+vam)?|"
    r"done|here\s+you\s+go|here\s+it\s+is|attached|u\s+privitku|"
    r"gotovo|napravljeno)\b", re.I)


def _lines(text):
    return [line for line in str(text or "").splitlines() if line.strip()]


def delivery_evidence(message):
    """Why this message counts as a delivery, or None.

    The operator's four shapes, each named in the answer rather than
    collapsed into a boolean - so a person reading the briefing can see
    WHY the system thinks a promise was kept, and disagree with it. The
    domain-list promise was "kept" with the wrong artefact, and a scan that
    only says `delivered` would have said delivered about that too.
    """
    if message.get("files"):
        return "a file"
    text = str(message.get("text") or "")
    if _LINK.search(text):
        return "a link"
    if len(_lines(text)) >= 3:
        return "a list"
    if _DELIVERY_WORD.search(text):
        return "an explicit delivery word"
    return None


def _is_system(message):
    return bool(message.get("bot_id")
                or message.get("subtype") == "bot_message")


# ------------------------------------------------------------- the reading

def history_dir():
    try:
        from . import store
        return os.path.join(os.path.dirname(store.queue_path()),
                            "slack-history")
    except Exception:                                           # noqa: BLE001
        return os.path.join(ROOT, "work", "slack-history")


def messages(directory=None):
    """Every message the history holds, or an empty list.

    An empty list here means NOTHING HAS BEEN PULLED, which is a different
    claim from "nobody promised anything" - and the caller says which, so a
    scan that has never been fed does not read as a clean week.
    """
    directory = directory or history_dir()
    if not os.path.isdir(directory):
        return []
    out = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".jsonl") or name.startswith("_"):
            continue
        with open(os.path.join(directory, name), encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


def _thread_key(message):
    return (message.get("_channel"),
            message.get("thread_ts") or message.get("ts"))


def scan(rows=None, internal_users=None, now=None, window_days=WINDOW_DAYS):
    """Every promise in the window, with its state and its evidence.

    `internal_users` is passed in rather than read here so the caller owns
    the scoping decision, and so a test does not need a workspace store.
    """
    rows = messages() if rows is None else rows
    people = set(internal_users or ())
    now = float(now if now is not None else time.time())
    floor = now - window_days * 86400

    by_thread = {}
    for message in rows:
        by_thread.setdefault(_thread_key(message), []).append(message)
    for thread in by_thread.values():
        thread.sort(key=lambda m: float(m.get("ts") or 0))

    out = []
    for key, thread in sorted(by_thread.items(), key=lambda kv: str(kv[0])):
        for index, message in enumerate(thread):
            stamp = float(message.get("ts") or 0)
            if stamp < floor:
                continue
            user = message.get("user")
            if people and user not in people:
                continue
            if _is_system(message):
                continue
            text = str(message.get("text") or "")
            if _ASKS.search(text.strip()) or not _PROMISE.search(text):
                continue
            out.append(_judge(message, thread[index + 1:], people, now, key))
    return sorted(out, key=lambda p: p["at"])


def _judge(promise, after, people, now, key):
    """One promise against everything that followed it in its thread."""
    stamp = float(promise.get("ts") or 0)
    row = {"channel": key[0], "channel_name": promise.get("_channel_name"),
           "thread_ts": key[1], "ts": promise.get("ts"),
           "at": _iso(stamp), "by": promise.get("user"),
           "text": str(promise.get("text") or "")[:300]}

    for message in after:
        # A DELIVERY IS OURS OR THE SYSTEM'S, never the other party's. A
        # client posting a link in the thread is not us keeping a promise.
        if _is_system(message):
            pass
        elif people and message.get("user") not in people:
            continue
        evidence = delivery_evidence(message)
        if not evidence:
            continue
        row.update({"status": DELIVERED,
                    "delivered_at": _iso(float(message.get("ts") or 0)),
                    "delivered_by": ("the system" if _is_system(message)
                                     else message.get("user")),
                    "evidence": evidence,
                    "minutes_taken": int(
                        (float(message.get("ts") or 0) - stamp) / 60)})
        return row

    days = deadline_days(promise.get("text"))
    if days is None:
        row.update({"status": UNDATED,
                    "note": "no time was stated, so this is not late - it "
                            "is untracked"})
        return row
    due_at = stamp + days * 86400 + 86400 if days else stamp + 86400
    row["due_by"] = _iso(due_at)
    row["stated_time_days"] = days
    row["status"] = OPEN if now > due_at else DUE
    return row


def _iso(epoch):
    if not epoch:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def summary(promises, history_found=True):
    """Counts, the open ones in full, and the honest empty case."""
    by_status = {}
    for row in promises or []:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    out = {"promises": len(promises or []), "by_status": by_status,
           "open": [p for p in (promises or []) if p["status"] == OPEN],
           "due": [p for p in (promises or []) if p["status"] == DUE]}
    if not history_found:
        # THE DIFFERENCE THAT MATTERS. A scan nobody has fed and a week
        # nobody broke a promise in look identical unless this is said.
        out["note"] = ("no Slack history has been pulled, so this is not a "
                       "clean week - it is an empty file. Run "
                       "`py -3 scripts/slack_history.py --read`.")
    elif not promises:
        out["note"] = ("no promise-shaped message was found in the last "
                       "%d days" % WINDOW_DAYS)
    else:
        out["note"] = ("`open` means a stated time has passed with nothing "
                       "posted in that thread. `undated` is not late. "
                       "Delivery is judged on the thread only, so a promise "
                       "answered in a separate message reads as open.")
    return out
