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

EXACTLY THREE SENTENCES, in this order and in prose - no bullets, no
headings, no preamble:

  1. What happened. The most recent real state of the system.
  2. What is next.
  3. What needs the operator, naming the items rather than counting them.

Rules:
  - NEVER state a number that is not in the material below.
  - Enrolled is not sent. If you give an enrolled figure, give the sent
    figure beside it.
  - A colleague's voice: direct, specific, no corporate register.
  - If nothing needs the operator, say so plainly in the third sentence.

MATERIAL:
{material}
"""


def gather(scope=None):
    """Everything the briefing is built from. Internal scope, by definition."""
    scope = scope or slackscope.Scope(slackscope.INTERNAL,
                                      source="briefing")
    results = tools.run_all(scope, [
        {"name": "next_actions"},
        {"name": "sends_today"},
        {"name": "batch_state"},
        {"name": "monitors"},
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
    """The briefing with no model. The same three things, plainly."""
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
