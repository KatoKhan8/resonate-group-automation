#!/usr/bin/env python3
"""Read the workspace's own Slack history, so the agent learns what is asked.

    py -3 scripts/slack_history.py --scopes      # prove each scope by using it
    py -3 scripts/slack_history.py --survey      # list channels, join nothing
    py -3 scripts/slack_history.py --join        # join the public ones
    py -3 scripts/slack_history.py --read        # pull history into work/
    py -3 scripts/slack_history.py --loop --interval 3600

OPERATOR, 2026-09-22: "Read the workspace's Slack history to learn what
people actually ask and how... Join every PUBLIC channel that is not shared
with an external organization (skip Slack Connect / shared channels; list
them for me instead). For private channels, list them and I will invite the
bot."

## JOINING NEVER WIDENS SCOPE

This is the rule that makes the rest safe, and it is enforced somewhere
else: `slackscope.resolve` decides what a channel may hear from the
workspace policy and the internal list, and knows nothing about which
channels the bot happens to be in. Joining a channel lets the agent READ
it. It does not make it internal, and it does not make it a client's.
A joined channel nobody has bound is `unbound` - generic answers, no client
data - exactly as it was before the bot walked in.

## A SHARED CHANNEL IS NOT JOINED, IT IS REPORTED

`is_ext_shared` or `is_org_shared` means somebody outside Resonate is in
the room. Reading one is a decision about another organisation's messages,
and it is the operator's to make rather than a loop's. They are listed.

## RAW HISTORY STAYS IN `work/`

Gitignored, per the operator. What reaches `docs/` is the SHAPE of the
questions and role-labelled style examples - never a prospect, an address,
or a client-internal detail. `work/` is also where a re-read picks up:
each channel records the newest timestamp it has, and an incremental pass
asks only for what is newer.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import slackscope                                      # noqa: E402
from src.providers import load_env                              # noqa: E402

BASE = "https://slack.com/api"
TOKEN_VAR = "SLACK_BOT_TOKEN"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def history_dir():
    """Raw history lives beside the queue, with the rest of the state."""
    try:
        from src import store
        return os.path.join(os.path.dirname(store.queue_path()),
                            "slack-history")
    except Exception:                                           # noqa: BLE001
        return os.path.join(ROOT, "work", "slack-history")


def _emit(line=""):
    print(line, flush=True)


def call(method, **params):
    """One Slack API call with the BOT token. Read-only unless named.

    Returns `(ok, payload)`. A `missing_scope` comes back as a payload
    rather than an exception, because "which scope is missing" is the
    question this script exists to answer.
    """
    token = (os.environ.get(TOKEN_VAR) or "").strip()
    if not token:
        return False, {"error": "no_token", "needed": TOKEN_VAR}
    query = urllib.parse.urlencode({k: v for k, v in params.items()
                                    if v is not None})
    url = "%s/%s%s" % (BASE, method, ("?" + query) if query else "")
    request = urllib.request.Request(
        url, headers={"Authorization": "Bearer %s" % token})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:                                    # noqa: BLE001
        return False, {"error": "transport", "detail": type(exc).__name__}
    return bool(body.get("ok")), body


def paged(method, key, **params):
    """Every page of a cursor-paginated read. Refuses nothing, yields all."""
    cursor = None
    while True:
        ok, body = call(method, cursor=cursor, **params)
        if not ok:
            return body.get("error") or "unknown", []
        for row in body.get(key) or []:
            yield None, row
        cursor = ((body.get("response_metadata") or {})
                  .get("next_cursor") or "").strip()
        if not cursor:
            return


# ------------------------------------------------------------- the scopes

#: Each scope, and one READ that proves it. `channels:join` is the only one
#: that cannot be proved read-only, so it is proved by the join itself and
#: reported separately.
SCOPE_PROBES = (
    ("channels:read", "conversations.list",
     {"types": "public_channel", "limit": 1}),
    ("groups:read", "conversations.list",
     {"types": "private_channel", "limit": 1}),
    ("users:read", "users.list", {"limit": 1}),
    ("channels:history", "conversations.history", {"limit": 1}),
    ("groups:history", "conversations.history", {"limit": 1}),
    ("im:history", "conversations.list", {"types": "im", "limit": 1}),
    ("mpim:history", "conversations.list", {"types": "mpim", "limit": 1}),
)


def check_scopes(sample_channel=None):
    """Prove each scope by using it. Reports what actually failed."""
    load_env()
    _emit("SCOPE CHECK - each one proved by a read, not by reading the "
          "app config")
    _emit()
    results = {}
    for scope, method, params in SCOPE_PROBES:
        if "history" in method and sample_channel:
            params = dict(params, channel=sample_channel)
        elif "history" in method:
            results[scope] = "SKIPPED (no channel to read; pass --channel)"
            _emit("  %-18s %s" % (scope, results[scope]))
            continue
        ok, body = call(method, **params)
        if ok:
            results[scope] = "ok"
        else:
            results[scope] = body.get("error") or "failed"
        _emit("  %-18s %s" % (scope, results[scope]))
    _emit()
    missing = sorted(s for s, r in results.items()
                     if r not in ("ok",) and not r.startswith("SKIPPED"))
    if missing:
        _emit("MISSING OR FAILING: %s" % ", ".join(missing))
        _emit("`missing_scope` means the app needs it added and "
              "reinstalled; anything else is a different fault.")
    else:
        _emit("Every scope probed answered. `channels:join` is proved by "
              "--join, because there is no read-only way to prove it.")
    return results


# ------------------------------------------------------------- the survey

def survey():
    """Every conversation, classified. Joins nothing."""
    load_env()
    public, private, shared, dms = [], [], [], []
    error = None
    for err, row in paged("conversations.list",
                          "channels",
                          types="public_channel,private_channel,mpim,im",
                          exclude_archived="true", limit=200):
        if err:
            error = err
            break
        if row.get("is_im") or row.get("is_mpim"):
            dms.append(row)
            continue
        if row.get("is_ext_shared") or row.get("is_org_shared") \
                or row.get("is_pending_ext_shared"):
            shared.append(row)
            continue
        (private if row.get("is_private") else public).append(row)
    return {"public": public, "private": private, "shared": shared,
            "dms": dms, "error": error}


def _row(channel):
    return {"id": channel.get("id"), "name": channel.get("name"),
            "member": bool(channel.get("is_member")),
            "members": channel.get("num_members"),
            "private": bool(channel.get("is_private")),
            "shared": bool(channel.get("is_ext_shared")
                           or channel.get("is_org_shared"))}


def print_survey(found):
    bound = slackscope.client_channels()
    internal = slackscope.internal_channels()

    def label(channel):
        cid = channel.get("id")
        if cid in bound:
            return "CLIENT:%s" % bound[cid]
        if cid in internal:
            return "internal"
        return "unbound"

    for title, rows in (("PUBLIC, joinable", found["public"]),
                        ("PRIVATE - need your invite", found["private"]),
                        ("SHARED with an external org - NOT joined",
                         found["shared"])):
        _emit()
        _emit("%s (%d)" % (title, len(rows)))
        for channel in sorted(rows, key=lambda c: c.get("name") or ""):
            _emit("  %-12s %-34s %-9s members=%-5s %s"
                  % (channel.get("id"), "#" + str(channel.get("name")),
                     "JOINED" if channel.get("is_member") else "-",
                     channel.get("num_members"), label(channel)))
    _emit()
    _emit("DMs and group DMs visible: %d (not joined, not read here)"
          % len(found["dms"]))
    if found.get("error"):
        _emit("LIST FAILED PARTWAY: %s" % found["error"])


# --------------------------------------------------------------- joining

def join(dry_run=True):
    """Join every public, non-shared channel. Reports every decision."""
    load_env()
    found = survey()
    joined, already, failed = [], [], []
    for channel in found["public"]:
        if channel.get("is_member"):
            already.append(_row(channel))
            continue
        if dry_run:
            joined.append(_row(channel))
            continue
        ok, body = call("conversations.join", channel=channel.get("id"))
        if ok:
            joined.append(_row(channel))
        else:
            failed.append(dict(_row(channel),
                               why=body.get("error") or "failed"))
        time.sleep(0.4)
    return {"joined": joined, "already_in": already, "failed": failed,
            "skipped_shared": [_row(c) for c in found["shared"]],
            "private_awaiting_invite": [_row(c) for c in found["private"]]}


# --------------------------------------------------------------- reading

def _state_path():
    return os.path.join(history_dir(), "_cursors.json")


def _cursors():
    path = _state_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:                                           # noqa: BLE001
        return {}


def _save_cursors(cursors):
    path = _state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(cursors, handle, indent=1)
    os.replace(tmp, path)


def read_channel(channel_id, name, oldest=None, include_threads=True):
    """Every message in one channel, newest cursor returned.

    Threads are followed because that is where the answers are: the real
    question this whole phase came from is a parent with eleven replies,
    and the parent alone says nothing about how it was handled.
    """
    rows, newest, error = [], oldest, None
    for err, message in paged("conversations.history", "messages",
                              channel=channel_id, oldest=oldest, limit=200):
        if err:
            error = err
            break
        rows.append(message)
        ts = message.get("ts")
        if ts and (newest is None or float(ts) > float(newest)):
            newest = ts
    if include_threads and not error:
        parents = [m for m in rows if m.get("reply_count")]
        for parent in parents:
            for err, reply in paged("conversations.replies", "messages",
                                    channel=channel_id, ts=parent.get("ts"),
                                    limit=200):
                if err:
                    error = err
                    break
                if reply.get("ts") != parent.get("ts"):
                    rows.append(reply)
            time.sleep(0.2)
    return rows, newest, error


#: Rooms this monitor never pulls, by NAME or by PURPOSE/TOPIC. Operator
#: decision, 2026-09-22. These hold payroll, banking, personnel and credential
#: material, and none of it is the agent's business: the catalogue exists to
#: answer questions about outreach, and nothing it could learn in a payroll
#: channel is worth having that material in `work/` at all.
#:
#: MATCHED ON PURPOSE AND TOPIC, NOT ONLY ON NAME. A room called `#leadership`
#: whose purpose says "comp planning" is exactly the room this is for, and a
#: name-only rule would read it. Substring matching is deliberate so
#: `#hr-updates`, `#finance-ops` and `#admin-internal` are all caught.
#: THE LIST IS BILINGUAL BECAUSE THE ESTATE IS. An English-only rule read
#: `#racuni` - Croatian for invoices - straight past, in a workspace whose
#: people write Croatian daily. A safety list in one language is a safety list
#: with a hole in it, and the hole is exactly where the local team files the
#: invoices.
SENSITIVE_TERMS = (
    # English
    "finance", "financial", "payroll", "salary", "salaries", "comp-plan",
    "compensation", "invoice", "invoicing", "billing", "banking",
    "accounts-payable", "bookkeeping", "tax",
    "hr", "human-resources", "people-ops", "peopleops", "recruit", "hiring",
    "personnel", "performance-review",
    "admin", "credential", "credentials", "secret", "secrets", "password",
    "passwords", "token", "tokens", "apikey", "api-key", "vault",
    # Croatian. Folded to ASCII before matching, so `racuni` catches `računi`
    # and `place` catches `plaće`.
    "racun", "racuni", "faktura", "fakture", "knjigovodstvo", "knjigovoda",
    "placa", "place", "placu", "porez", "porezi", "banka", "bankovni",
    "kadrovska", "kadrovi", "zaposlenici", "ugovori", "lozinka", "lozinke",
)

#: Diacritics the fold has to remove before a Croatian term can match.
_FOLD = str.maketrans({
    "č": "c", "ć": "c", "ž": "z", "š": "s", "đ": "d",
    "Č": "c", "Ć": "c", "Ž": "z", "Š": "s", "Đ": "d",
})


def _fold(text):
    """Lowercased and stripped of Croatian diacritics, for matching only."""
    return (text or "").translate(_FOLD).lower()


#: Channels excluded by TERM that are not actually sensitive, allow-listed by
#: exact name. Operator decision, 2026-09-22.
#:
#: A NAME-LEVEL ALLOWLIST, NOT A WEAKER TERM. `#finance-weekend-team` is a
#: campaign channel - "Finance Weekend" is a Resonate campaign, not a finance
#: function - and it matched `finance`. Dropping or narrowing the `finance`
#: term to let it through would stop excluding real finance rooms, which is
#: the whole point of the list. Naming the one exception keeps the term intact
#: and makes every future exception a decision somebody has to write down.
ALLOWED_BY_NAME = ("finance-weekend-team",)


def _sensitive_hit(channel):
    """The term that excludes this channel, or None.

    Name is matched on word-ish boundaries for the SHORT terms so `hr` does
    not swallow `#thread-watch` or `#chruby`; the longer terms are plain
    substrings because a false positive there costs nothing but a channel we
    did not need.
    """
    name = _fold(channel.get("name"))
    if name in ALLOWED_BY_NAME:
        return None
    prose = _fold(" ".join(str((channel.get(k) or {}).get("value", "")
                               if isinstance(channel.get(k), dict)
                               else channel.get(k) or "")
                           for k in ("purpose", "topic")))
    parts = set(re.split(r"[^a-z0-9]+", name))
    for term in SENSITIVE_TERMS:
        if len(term) <= 3:
            if term in parts:
                return term
            continue
        if term in name or term in prose:
            return term
    for term in SENSITIVE_TERMS:
        if len(term) <= 3 and term in re.split(r"[^a-z0-9]+", prose):
            return term
    return None


def is_sensitive(channel):
    """True when this room may never be pulled. Fails CLOSED on a bad shape."""
    if not isinstance(channel, dict):
        return True
    return _sensitive_hit(channel) is not None


def read_all(incremental=True):
    """Pull history for every channel the bot is in. Writes only `work/`."""
    load_env()
    found = survey()
    cursors = _cursors() if incremental else {}
    directory = history_dir()
    os.makedirs(directory, exist_ok=True)

    # WHICH CHANNELS ARE READ, AND WHY THE SHARED ONES MOSTLY ARE NOT.
    #
    # Resonate's own rooms - public and private - are Resonate's to read.
    # An externally-shared channel is a different thing: it holds another
    # organisation's messages, and eight of the nine here are other
    # clients' outbound channels.
    #
    # A shared channel is read only when it is BOUND to a workspace. Then
    # what is read is attributable to one client and stays theirs, which is
    # the scoping rule applied to history exactly as to answers. An UNBOUND
    # shared channel is attributable to nobody, so anything learnt there
    # could only feed the general catalogue - and a general catalogue built
    # out of one client's room is how one client's questions end up shaping
    # another's answers. Those are listed for the operator instead.
    bound = slackscope.client_channels()
    readable = list(found["public"]) + list(found["private"])
    for channel in found["shared"]:
        if channel.get("id") in bound:
            readable.append(channel)
    skipped_shared = [_row(c) for c in found["shared"]
                      if c.get("id") not in bound]

    # SENSITIVE ROOMS ARE NEVER PULLED. Operator decision, 2026-09-22.
    excluded = [_row(c) for c in readable if is_sensitive(c)]
    readable = [c for c in readable if not is_sensitive(c)]

    report = {"channels": [], "messages": 0, "errors": [],
              "skipped_shared_unbound": skipped_shared,
              "skipped_sensitive": excluded}
    for channel in readable:
        if not channel.get("is_member"):
            continue
        cid, name = channel.get("id"), channel.get("name")
        rows, newest, error = read_channel(
            cid, name, oldest=cursors.get(cid) if incremental else None)
        if error:
            report["errors"].append({"channel": name, "error": error})
            if error == "missing_scope":
                continue
        if rows:
            path = os.path.join(directory, "%s.jsonl" % cid)
            with open(path, "a", encoding="utf-8") as handle:
                for message in rows:
                    handle.write(json.dumps(
                        dict(message, _channel=cid, _channel_name=name),
                        default=str) + "\n")
        if newest:
            cursors[cid] = newest
        report["channels"].append({"channel": name, "id": cid,
                                   "messages": len(rows)})
        report["messages"] += len(rows)
        time.sleep(0.3)
    _save_cursors(cursors)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--scopes", action="store_true")
    parser.add_argument("--channel", help="a channel id for the history probe")
    parser.add_argument("--survey", action="store_true")
    parser.add_argument("--join", action="store_true")
    parser.add_argument("--read", action="store_true")
    parser.add_argument("--full", action="store_true",
                        help="ignore the saved cursors and re-read all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=3600)
    args = parser.parse_args(argv)
    load_env()

    if args.scopes:
        check_scopes(args.channel)
        return 0
    if args.survey:
        print_survey(survey())
        return 0
    if args.join:
        result = join(dry_run=args.dry_run)
        _emit("JOINED (%d)%s" % (len(result["joined"]),
                                 "  [DRY RUN]" if args.dry_run else ""))
        for row in result["joined"]:
            _emit("  #%s" % row["name"])
        _emit("ALREADY IN (%d)" % len(result["already_in"]))
        for row in result["already_in"]:
            _emit("  #%s" % row["name"])
        if result["failed"]:
            _emit("FAILED (%d)" % len(result["failed"]))
            for row in result["failed"]:
                _emit("  #%s  %s" % (row["name"], row["why"]))
        _emit("SKIPPED, shared with an external org (%d) - yours to decide"
              % len(result["skipped_shared"]))
        for row in result["skipped_shared"]:
            _emit("  #%s" % row["name"])
        _emit("PRIVATE, awaiting your invite (%d)"
              % len(result["private_awaiting_invite"]))
        for row in result["private_awaiting_invite"]:
            _emit("  #%s" % row["name"])
        return 0
    if args.read or args.loop:
        while True:
            report = read_all(incremental=not args.full)
            _emit("READ %d message(s) across %d channel(s) at %s"
                  % (report["messages"], len(report["channels"]),
                     time.strftime("%H:%M:%SZ", time.gmtime())))
            for row in sorted(report["channels"],
                              key=lambda r: -r["messages"])[:15]:
                if row["messages"]:
                    _emit("  %-34s %d" % ("#" + str(row["channel"]),
                                          row["messages"]))
            for row in report["errors"]:
                _emit("  ERROR #%s: %s" % (row["channel"], row["error"]))
            if not args.loop:
                return 0
            time.sleep(args.interval)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
