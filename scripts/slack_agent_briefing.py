#!/usr/bin/env python3
"""The morning briefing: three sentences in `#resonate-os`, after the digest.

    py -3 scripts/slack_agent_briefing.py --loop --interval 300
    py -3 scripts/slack_agent_briefing.py --once     # post if one is due
    py -3 scripts/slack_agent_briefing.py --preview  # print it, post nothing
    py -3 scripts/slack_agent_briefing.py --force    # post now, for testing

OPERATOR, 2026-09-21: "a morning message in #resonate-os at 07:15 after the
digest, in prose, three sentences: what happened, what is next, what needs
the operator."

## 07:15 LOCAL, AND THE HOUR MOVES WITH DST

`DIGEST_HOUR` is 5 UTC, which is 07:00 in Zagreb during CEST. This posts
fifteen minutes after it, so the briefing follows the digest rather than
racing it. **The handoff's standing note applies here too: DIGEST_HOUR moves
5 -> 6 on 2026-10-25 when CEST ends**, and this reads that variable rather
than hard-coding an hour, so it moves with it instead of drifting an hour
away from the thing it is supposed to follow.

The briefing reports the local time it actually fired at, so a wrong hour is
visible in the log rather than inferred from a late message.

## THREE SENTENCES, AND THE THIRD ONE IS THE POINT

What happened, what is next, what needs the operator. The third is read
first by the only person who can unblock anything, so it names the items
rather than summarising them - "151 leads are enrolled behind one activation
decision" is actionable and "several items await review" is not.

## IDEMPOTENT BY THE DAY

One briefing per calendar day per destination, recorded in the same log the
agent writes everything else to. A restart, a second process or a clock that
steps backwards cannot produce two.
"""
import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (llm, slackagenttools as tools,                 # noqa: E402
                 slackconversation as conversation,
                 slackknowledge as knowledge, slackrequests as requests,
                 slackscope)
from src import notify                                           # noqa: E402
from src.providers import load_env, slack                        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "work", "slack-agent.jsonl")
HEARTBEAT = os.path.join(ROOT, "work", "heartbeat", "slack-agent-briefing.json")

#: The digest's hour, in UTC. Read rather than assumed: it moves with DST.
DIGEST_HOUR_VAR = "DIGEST_HOUR"
DEFAULT_DIGEST_HOUR = 5

#: Minutes after the digest. The operator asked for 07:15 against an 07:00
#: digest, so this is the gap rather than a second absolute hour to keep in
#: step with the first.
MINUTES_AFTER_DIGEST = 15

#: How late is too late. A loop that starts at 09:00 should not fire a
#: 07:15 briefing as though it were on time; it records that it missed one.
LATE_CUTOFF_MINUTES = 180

#: OPERATOR, `docs/SLACK-AGENT-EXPECTATIONS.md` section 4 item 2: flag a
#: sender at 1.5%, "early enough to matter, not at 2%".
#:
#: A PERCENTAGE, not a fraction, because `sender_roster` reports
#: `bounce_rate_percent` that way and a threshold in the other unit would
#: compare 0.015 against 1.5 and flag every sender or none.
BOUNCE_ALERT_PERCENT = 1.5

#: How quiet a watcher may be before the briefing names it. Half an hour:
#: the fastest monitor here beats on a 60s interval and the slowest on 300s,
#: so this is several missed beats rather than one slow one.
QUIET_AFTER_SECONDS = 1800


def _emit(line):
    print(line, flush=True)


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def digest_hour():
    try:
        return int(os.environ.get(DIGEST_HOUR_VAR, DEFAULT_DIGEST_HOUR))
    except ValueError:
        return DEFAULT_DIGEST_HOUR


def due_at(day):
    """The UTC moment the briefing is due on `day`."""
    return datetime.datetime(day.year, day.month, day.day, digest_hour(),
                             tzinfo=datetime.timezone.utc) + \
        datetime.timedelta(minutes=MINUTES_AFTER_DIGEST)


def log(row):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row, at=_now().strftime(
            "%Y-%m-%dT%H:%M:%SZ")), default=str) + "\n")


def already_posted(day):
    """Has a briefing gone out for this calendar day?"""
    if not os.path.isfile(LOG):
        return False
    stamp = day.strftime("%Y-%m-%d")
    with open(LOG, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or stamp not in line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("kind") == "briefing_posted" and \
                    row.get("day") == stamp:
                return True
    return False


def heartbeat(state):
    os.makedirs(os.path.dirname(HEARTBEAT), exist_ok=True)
    payload = {"source": "slack-agent-briefing",
               "watcher": "slack-agent-briefing",
               "at": _now().strftime("%Y-%m-%dT%H:%M:%SZ"),
               "epoch": int(time.time()), "pid": os.getpid(), "state": state}
    tmp = HEARTBEAT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    os.replace(tmp, HEARTBEAT)


# ------------------------------------------------------------- the content

BRIEFING_PROMPT = """Write the morning briefing for the Resonate team, in
their internal Slack channel.

ONE SENTENCE EACH for the items below, in this order, in prose - no
bullets, no headings, no preamble. Say "nothing" for an item with nothing
in it rather than dropping it; a briefing that silently omits an empty
section is indistinguishable from one whose readback failed.

  1. What happened. The most recent real state of the system.
  2. What is next.
  3. What needs the operator, naming the items rather than counting them.
  4. Anything we PROMISED somebody and have not delivered, from the
     `promises` readback. Only rows whose status is `open`. `undated` is
     not late and is never reported as such.
  5. Any WATCHER that is not beating, from the `monitors` readback, and how
     long it has been quiet.
  6. Any SENDER at or above 1.5% bounce, from the `sender_roster` readback,
     named. The operator's threshold, chosen to be early enough to matter
     rather than at 2% when it already does.

Rules:
  - NEVER state a number that is not in the material below.
  - Enrolled is not sent. If you give an enrolled figure, give the sent
    figure beside it.
  - A colleague's voice: direct, specific, no corporate register.
  - If nothing needs the operator, say so plainly in the third sentence.
  - A readback carrying `_error` is a FAILED READ, not an empty result.
    Say that it could not be read. Never report it as "nothing to report".

MATERIAL:
{material}
"""


def gather(scope=None):
    """Everything the briefing is built from. Internal scope, by definition."""
    scope = scope or slackscope.Scope(slackscope.INTERNAL,
                                      source="briefing")
    # `run_scheduled`, NOT `run_all`. This list is a literal; no message
    # chooses it, so the turn budget protects nothing here and was silently
    # truncating the report - `monitors` sat at index 5 against a budget of
    # 5 and came back as `{"_error": "dropped: over the 5-call budget"}`
    # EVERY MORNING. See `slackagenttools.run_scheduled`.
    results = tools.run_scheduled(scope, [
        {"name": "next_actions"},
        {"name": "sends_today"},
        {"name": "batch_state"},
        {"name": "meetings_booked", "argument": "week"},
        {"name": "promises", "argument": "open"},
        {"name": "monitors"},
        # OPERATOR, `docs/SLACK-AGENT-EXPECTATIONS.md` section 4 item 2:
        # lead with "any sender over 1.5% bounce - early enough to matter,
        # not at 2%". `sender_roster` carries the per-sender bounce rate and
        # has been a registered tool the whole time; the briefing simply
        # never asked for it. Adding a SEVENTH call is only possible because
        # the budget above is gone.
        {"name": "sender_roster"},
        # `weekly_plan`'s own docstring cites this briefing by name - "the
        # 07:15 briefing is supposed to already hold it when somebody asks".
        # It did not.
        {"name": "weekly_plan"},
    ])
    pending = requests.pending()
    approved = requests.approved_unexecuted()
    extra = {"read_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "change_requests_awaiting_operator": [
                 {"id": r["id"], "kind": r["kind"],
                  "workspace": r["workspace"]} for r in pending],
             "change_requests_approved_not_executed": [
                 {"id": r["id"], "kind": r["kind"]} for r in approved]}
    results.append(("change_requests", None, extra))
    return scope, results


def compose(model=None):
    """`(text, how)`. Never invents a number; falls back to a plain list."""
    scope, results = gather()
    material = conversation.material_for(scope, "morning briefing", results)
    plain = _plain(results)

    model = conversation.model_for_agent() if model is None else model
    if isinstance(model, llm.NoModel):
        return plain, "deterministic (no model configured)"
    try:
        text = model.complete(BRIEFING_PROMPT.format(material=material))
    except Exception as exc:                                    # noqa: BLE001
        return plain, "deterministic (model %s)" % type(exc).__name__

    checked, why = conversation.guard(text, material, scope)
    if checked is None:
        return plain, "deterministic (guard: %s)" % why
    return checked, "model"


def _plain(results):
    """The briefing with no model. EVERYTHING GATHERED, not a subset.

    This used to read `next_actions`, `sends_today` and `change_requests`
    and nothing else - so `meetings_booked`, `promises` and `monitors` were
    fetched every morning and silently discarded whenever no model was
    configured. The operator's promises requirement, which is the reason
    `promises` exists at all, simply vanished on that path.

    A fallback that quietly answers a smaller question than the one it was
    asked is worse than one that fails, because the output still looks like
    a briefing.
    """
    by_name = {name: value for name, _argument, value in results}
    state = by_name.get("next_actions") or {}
    waiting = state.get("waiting_on_operator") or []
    tickets = (by_name.get("change_requests") or {}).get(
        "change_requests_awaiting_operator") or []

    lines = []
    headline = state.get("headline")
    if headline:
        lines.append("Where we are: %s." % headline.rstrip("."))
    sends = by_name.get("sends_today") or {}
    rows = [r for r in (sends.get("campaigns") or []) if r.get("emails_sent")]
    if rows:
        lines.append("Sent so far: " + "; ".join(
            "%s %s" % (r.get("campaign_id"), r.get("emails_sent"))
            for r in rows) + " (provider counters; enrolled is not sent).")
    if waiting:
        lines.append("Waiting on you: " + " ".join(
            "%d) %s" % (index + 1, item)
            for index, item in enumerate(waiting[:5])))
    else:
        lines.append("Nothing in the handoff is waiting on you.")
    if tickets:
        lines.append("Change requests to decide: " + ", ".join(
            "%s (%s, %s)" % (t["id"], t["kind"], t["workspace"])
            for t in tickets))

    # THE THREE THAT WERE GATHERED AND THROWN AWAY.
    promised = by_name.get("promises") or {}
    open_rows = promised.get("open") or []
    if open_rows:
        lines.append("Promised and not delivered: " + ", ".join(
            str(r.get("what") or r.get("text") or r.get("id") or "?")
            for r in open_rows[:5]))

    # THE SHAPES ARE THE READBACKS' OWN, taken off the real returns rather
    # than guessed. `monitors` returns {"monitors": [...]} - not
    # "watchers" - and each row carries `watcher` and `age_seconds`, with
    # no `beating` flag. An UNDATED beat counts as quiet, which is
    # `watchsink.stale`'s rule and its reasoning: the question is "may I
    # read silence as unchanged", and for a beat that cannot be read the
    # only safe answer is no.
    watchers = by_name.get("monitors") or {}
    quiet = []
    for row in watchers.get("monitors") or []:
        age = row.get("age_seconds")
        if not isinstance(age, (int, float)):
            quiet.append((row.get("watcher"), "no readable beat"))
        elif age > QUIET_AFTER_SECONDS:
            quiet.append((row.get("watcher"), "%d min" % (age // 60)))
    if quiet:
        lines.append("Not beating: " + ", ".join(
            "%s (%s)" % (name, why) for name, why in quiet[:6]))

    # `bounce_rate_percent` is ALREADY A PERCENTAGE (1.5 means 1.5%), and
    # the sender's key is `name`. Multiplying it again would have reported
    # 150% and named nobody.
    roster = by_name.get("sender_roster") or {}
    hot = [x for x in (roster.get("senders") or [])
           if isinstance(x.get("bounce_rate_percent"), (int, float))
           and x["bounce_rate_percent"] >= BOUNCE_ALERT_PERCENT]
    if hot:
        lines.append("Bounce at or over %.1f%%: " % BOUNCE_ALERT_PERCENT
                     + ", ".join("%s %.2f%%" % (x.get("name"),
                                                x["bounce_rate_percent"])
                                 for x in hot))

    # A FAILED READ IS NOT AN ABSENCE. Named, so a morning with a broken
    # readback does not read as a quiet morning.
    broken = sorted(n for n, _a, v in results
                    if isinstance(v, dict) and v.get("_error"))
    if broken:
        lines.append("Could not be read: " + ", ".join(broken) + ".")

    return "\n".join(lines) if lines else "No briefing material was readable."


def destination():
    return (notify.status_channel() or notify.ops_channel()
            or (sorted(slackscope.internal_channels())[0]
                if slackscope.internal_channels() else None))


def post(force=False, preview=False, model=None):
    """Post one briefing, or say why it did not."""
    now = _now()
    day = now.date()
    if not force and not preview:
        if already_posted(day):
            return "already posted for %s" % day
        due = due_at(day)
        if now < due:
            return "not due until %s" % due.strftime("%H:%MZ")
        late = (now - due).total_seconds() / 60.0
        if late > LATE_CUTOFF_MINUTES:
            log({"kind": "briefing_missed", "day": day.strftime("%Y-%m-%d"),
                 "minutes_late": round(late)})
            return ("MISSED %s by %d minutes - not posting a stale briefing"
                    % (day, late))

    text, how = compose(model)
    body = "*Morning briefing* — %s\n\n%s" % (
        day.strftime("%A %d %B %Y"), text)
    if preview:
        return body + "\n\n[%s, not posted]" % how

    channel = destination()
    if not channel:
        log({"kind": "briefing_undelivered",
             "why": "no internal channel configured"})
        return "REFUSED: no internal channel is configured"
    slack.post({"kind": "slack_agent_briefing", "channel": channel,
                "text": body})
    log({"kind": "briefing_posted", "day": day.strftime("%Y-%m-%d"),
         "channel": channel, "how": how, "text": text[:1500],
         "fired_at_local": time.strftime("%Y-%m-%d %H:%M %Z")})
    return "posted to %s (%s)" % (channel, how)


def loop(interval=300):
    load_env()
    _emit("BRIEFING LOOP starting. Due %d minutes after DIGEST_HOUR=%d UTC."
          % (MINUTES_AFTER_DIGEST, digest_hour()))
    while True:
        try:
            result = post()
            heartbeat({"last": result})
            if not result.startswith("not due"):
                _emit(result)
        except Exception as exc:                                # noqa: BLE001
            _emit("BRIEFING-ERROR %s: %s" % (type(exc).__name__,
                                             str(exc)[:200]))
            heartbeat({"error": type(exc).__name__})
        time.sleep(interval)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-model", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args(argv)
    load_env()
    model = llm.NoModel() if args.no_model else None

    if args.loop:
        loop(args.interval)
        return 0
    if args.preview:
        print(post(preview=True, model=model))
        return 0
    print(post(force=args.force, model=model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
