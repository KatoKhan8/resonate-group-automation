#!/usr/bin/env python3
"""Slack agent phase 1: polls for @mentions, answers in a thread, never acts.

Read-only by construction. This script imports nothing that can write to a
provider, a store, or a campaign. The import graph is asserted by
``tests.test_slack_agent.TheLoopImportsNothingThatCanWrite``.

Polls #resonate-os (and DMs to the bot) every 20-30 seconds for messages
that mention the bot. Each mention is answered exactly once, in a thread,
using the same LLM adapter as the rest of the system. The answer is built
from live readback data assembled by ``src.slackagentreadback``.

Idempotent by message ts: a restart does not re-answer the backlog.

    py -3 scripts/slack_agent_loop.py              # refuses unless configured
    py -3 scripts/slack_agent_loop.py --dry-run    # show what it would do
    py -3 scripts/slack_agent_loop.py --once       # one poll, then exit

SLACK SCOPES REQUIRED (bot token):
    channels:history   read messages in public channels
    channels:read      read public channel metadata
    groups:history     read messages in private channels
    groups:read        read private channel metadata
    im:history         read DMs to the bot
    im:read            read DM channel metadata
    app_mentions:read  receive app_mention events
    chat:write         post reply threads (already held)

After adding scopes the app MUST BE REINSTALLED for the token to carry them.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import llm, slackagentreadback                          # noqa: E402
from src.providers import load_env                               # noqa: E402

SLACK_BASE = "https://slack.com/api"
POLL_MIN = 20
POLL_MAX = 30
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "prompts")


# ----------------------------------------------------------- idempotency

class AnsweredTracker:
    """Remember which message ts values have been answered.

    Persisted to a JSON file so a restart does not re-answer the backlog.
    The file is a flat set of ts strings, small and append-only.
    """

    def __init__(self, path=None):
        self._path = path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "work", "slack_agent_answered.json")
        self._seen = set()
        self._load()

    def _load(self):
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._seen = set(data)
        except Exception:
            pass

    def _save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(sorted(self._seen), f)
        os.replace(tmp, self._path)

    def has(self, ts):
        return ts in self._seen

    def mark(self, ts):
        self._seen.add(ts)
        self._save()

    def count(self):
        return len(self._seen)


# ----------------------------------------------------------- Slack reads

def _slack_headers(token):
    return {"Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"}


def _slack_get(url, params, token):
    """GET from Slack API. Returns (ok: bool, data: dict)."""
    qs = "&".join(f"{k}={urllib.request.quote(str(v))}"
                  for k, v in params.items())
    full = f"{url}?{qs}"
    req = urllib.request.Request(full, headers=_slack_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return False, {"error": str(exc)}
    return data.get("ok", False), data


def _slack_post(url, body, token):
    """POST to Slack API. Returns (ok: bool, data: dict)."""
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=payload,
                                 headers=_slack_headers(token),
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return False, {"error": str(exc)}
    return data.get("ok", False), data


def fetch_mentions(token, channel, since_ts=None):
    """Read recent messages from a channel that mention the bot.

    Uses ``conversations.history`` which needs ``channels:history`` or
    ``groups:history`` depending on channel type.  Returns a list of
    message dicts, oldest first.
    """
    params = {"channel": channel, "limit": "50"}
    if since_ts:
        params["oldest"] = since_ts
    ok, data = _slack_get(f"{SLACK_BASE}/conversations.history",
                          params, token)
    if not ok:
        return []
    messages = data.get("messages") or []
    return list(reversed(messages))


def fetch_dm_channels(token):
    """List DM channels the bot is in. Needs ``im:read``."""
    ok, data = _slack_get(f"{SLACK_BASE}/conversations.list",
                          {"types": "im"}, token)
    if not ok:
        return []
    return [ch for ch in (data.get("channels") or [])
            if ch.get("is_im") and not ch.get("is_user_deleted")]


def fetch_dm_messages(token, dm_channel_id, since_ts=None):
    """Read recent DMs. Needs ``im:history``."""
    params = {"channel": dm_channel_id, "limit": "20"}
    if since_ts:
        params["oldest"] = since_ts
    ok, data = _slack_get(f"{SLACK_BASE}/conversations.history",
                          params, token)
    if not ok:
        return []
    messages = data.get("messages") or []
    return list(reversed(messages))


def post_reply(token, channel, thread_ts, text):
    """Post a threaded reply. Needs ``chat:write``."""
    body = {"channel": channel, "text": text, "thread_ts": thread_ts}
    return _slack_post(f"{SLACK_BASE}/chat.postMessage", body, token)


def bot_user_id(token):
    """The bot's own user id. Uses ``auth.test`` (no extra scope)."""
    ok, data = _slack_post(f"{SLACK_BASE}/auth.test", {}, token)
    if not ok:
        return None
    return data.get("user_id")


# ----------------------------------------------------------- the answer

def _load_system_prompt():
    path = os.path.join(PROMPTS_DIR, "slack_agent.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


def build_answer(user_text, model=None):
    """Assemble readback data, prompt the LLM, return the answer text.

    The LLM receives the system prompt and the readback data as a single
    user prompt. The model formats and explains; it does not choose what
    to read.
    """
    readback = slackagentreadback.gather()
    readback_text = slackagentreadback.format_for_prompt(readback)
    system_prompt = _load_system_prompt()

    full_prompt = (
        f"{system_prompt}\n\n"
        f"{readback_text}\n\n"
        f"## User message\n\n"
        f"{user_text}\n"
    )

    if model is None:
        model = llm.from_env()
    raw = model.complete(full_prompt)
    return raw.strip()


# ----------------------------------------------------------- the loop

def _extract_question(message_text):
    """Pull the text of the message, stripping the @mention prefix.

    Slack delivers mentions as ``<@U12345> rest of message``. The bot
    id prefix is removed so the LLM sees a clean question.
    """
    import re
    text = re.sub(r"<@[A-Z0-9]+>\s*", "", message_text or "").strip()
    return text or message_text or ""


def _extract_campaign_id(text):
    """If the message asks about a specific campaign, extract its id."""
    import re
    m = re.search(r"campaign\s+(\d{3,7})", text, re.IGNORECASE)
    return m.group(1) if m else None


def poll_once(token, channel, tracker, bot_id=None, dm_channels=None,
              model=None):
    """One poll cycle. Returns the list of (ts, answer) pairs produced."""
    answers = []
    campaign_id = None

    messages = fetch_mentions(token, channel)
    for msg in messages:
        ts = msg.get("ts")
        if not ts or tracker.has(ts):
            continue
        text = msg.get("text") or ""
        if bot_id and f"<@{bot_id}>" not in text:
            continue
        thread_ts = msg.get("thread_ts") or ts
        question = _extract_question(text)
        campaign_id = _extract_campaign_id(question)
        try:
            answer = build_answer(question, model=model)
        except Exception as exc:
            answer = f"Readback failed: {type(exc).__name__}: {exc}"
        ok, _resp = post_reply(token, channel, thread_ts, answer)
        if ok:
            tracker.mark(ts)
            answers.append((ts, answer))

    for dm_ch in (dm_channels or []):
        dm_id = dm_ch.get("id") if isinstance(dm_ch, dict) else dm_ch
        dm_msgs = fetch_dm_messages(token, dm_id)
        for msg in dm_msgs:
            ts = msg.get("ts")
            if not ts or tracker.has(ts):
                continue
            text = msg.get("text") or ""
            if bot_id and f"<@{bot_id}>" not in text and text.strip():
                pass
            thread_ts = msg.get("thread_ts") or ts
            question = _extract_question(text)
            try:
                answer = build_answer(question, model=model)
            except Exception as exc:
                answer = f"Readback failed: {type(exc).__name__}: {exc}"
            ok, _resp = post_reply(token, dm_id, thread_ts, answer)
            if ok:
                tracker.mark(ts)
                answers.append((ts, answer))

    return answers


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Slack agent phase 1: read-only, answers @mentions.")
    parser.add_argument("--dry-run", action="store_true",
                        help="build one answer and print it, send nothing")
    parser.add_argument("--once", action="store_true",
                        help="one poll cycle, then exit")
    parser.add_argument("--channel", default=None,
                        help="override the channel to poll")
    parser.add_argument("--question", default=None,
                        help="for --dry-run: the question to answer")
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    token = (os.environ.get("SLACK_BOT_TOKEN") or "").strip()
    channel = args.channel or os.environ.get("SLACK_OPS_CHANNEL", "").strip()

    if args.dry_run:
        question = args.question or "What is the current pipeline status?"
        answer = build_answer(question)
        print("DRY RUN - nothing sent to Slack.")
        print(f"  question: {question}")
        print(f"  answer:\n{answer}")
        return 0

    if not token:
        print("REFUSED: SLACK_BOT_TOKEN is not set.")
        return 2
    if not channel:
        print("REFUSED: SLACK_OPS_CHANNEL is not set and no --channel given.")
        return 2

    tracker = AnsweredTracker()
    bid = bot_user_id(token)
    dm_channels = fetch_dm_channels(token)

    if args.once:
        answers = poll_once(token, channel, tracker, bot_id=bid,
                            dm_channels=dm_channels)
        print(f"Polled once. {len(answers)} answer(s) posted.")
        return 0

    print(f"Slack agent phase 1 started. Polling {channel} every "
          f"{POLL_MIN}-{POLL_MAX}s. Read-only; no writes.")
    while True:
        try:
            answers = poll_once(token, channel, tracker, bot_id=bid,
                                dm_channels=dm_channels)
            if answers:
                for ts, ans in answers:
                    print(f"  answered {ts}: {ans[:80]}...")
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"  poll error: {type(exc).__name__}: {exc}")
        import random
        time.sleep(random.randint(POLL_MIN, POLL_MAX))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
