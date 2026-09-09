#!/usr/bin/env python3
"""Slack: the control surface, behind the same seam as every other provider.

## Nothing here posts

There is no Slack connection in this build. `post()` refuses exactly the way
push.run(live=True) refuses, and for the same reason: a notification layer that
can reach a real workspace is a thing that can wake a client at 3am because of
a fixture. What this module does instead is build the *payload* - the complete,
final message body, with its ids and its actions - and hand it back so it can
be inspected, tested and stored. When a workspace is connected, the transport
below is the only thing that changes.

## Two rules that are not about Slack at all

  1. **Slack can never be the reason something is safe.** A campaign is not
     approved because a message said so; it is approved because a permitted
     actor's decision matched the campaign's current fingerprint. The message
     carries ids, never trusted text - a button labelled "Approve" that posts a
     stale fingerprint is refused like any other stale approval.
  2. **Slack failing can never change what the engine does.** A reply pauses
     the company before anyone is notified. If the notification then fails, the
     pause stands, the failure is recorded, and the alert stays retryable.
     Outbound never resumes because a message did not get through.

## Configuration

Off unless a client turns it on. An existing client that has never heard of
Slack posts nothing, which is why `enabled` defaults to False and every channel
lookup returns None rather than a default channel.

  python -m src.providers.slack --check
"""
import argparse
import hashlib
import hmac
import json
import os
import time

from . import (ProviderError, failed, key, mapping, ok, redact,
               request, result)

BASE = "https://slack.com/api"
KEY_VAR = "SLACK_BOT_TOKEN"

# Message kinds. Each maps to a configured channel and a notify toggle.
CAMPAIGN_READY = "campaign_ready"
POSITIVE_REPLY = "positive_reply"
CREDIT_CAP_REACHED = "credit_cap_reached"
BATCH_COMPLETE = "batch_complete"
PROVIDER_FAILURE = "provider_failure"
CAMPAIGN_PAUSED = "campaign_paused"
CAMPAIGN_REJECTED = "campaign_rejected"
CAMPAIGN_APPROVED = "campaign_approved"
CAMPAIGN_LAUNCH_READY = "campaign_launch_ready"
LARGE_HELD_COUNT = "large_held_count"
DAILY_SUMMARY = "daily_summary"

KINDS = (CAMPAIGN_READY, POSITIVE_REPLY, CREDIT_CAP_REACHED, BATCH_COMPLETE,
         PROVIDER_FAILURE, CAMPAIGN_PAUSED, CAMPAIGN_REJECTED,
         CAMPAIGN_APPROVED, CAMPAIGN_LAUNCH_READY, LARGE_HELD_COUNT,
         DAILY_SUMMARY)

# Which configured channel each kind belongs in.
CHANNEL_OF = {
    CAMPAIGN_READY: "approvals_channel",
    CAMPAIGN_APPROVED: "approvals_channel",
    CAMPAIGN_REJECTED: "approvals_channel",
    CAMPAIGN_LAUNCH_READY: "approvals_channel",
    POSITIVE_REPLY: "positive_replies_channel",
    CREDIT_CAP_REACHED: "operational_alerts_channel",
    PROVIDER_FAILURE: "operational_alerts_channel",
    BATCH_COMPLETE: "operational_alerts_channel",
    CAMPAIGN_PAUSED: "operational_alerts_channel",
    LARGE_HELD_COUNT: "operational_alerts_channel",
    DAILY_SUMMARY: "operational_alerts_channel",
}

# Alert thresholds. A notification layer that cries wolf gets muted, and a
# muted layer is worse than none, so the noisy kinds are gated.
DEFAULT_THRESHOLDS = {
    "held_count_threshold": 10,
    "provider_failure_threshold": 3,
}

APPROVE = "approve_campaign"
REJECT = "reject_campaign"
OPEN_REVIEW = "open_review"
OPEN_CONVERSATION = "open_conversation"
ASSIGN_OWNER = "assign_owner"
MARK_MEETING = "mark_meeting"
MARK_NOT_POSITIVE = "mark_not_positive"


class SlackNotEnabled(RuntimeError):
    """Slack is off for this client. Nothing was built and nothing was sent."""


class SlackPostingNotEnabled(RuntimeError):
    """No workspace is connected in this build. The payload exists; the post
    does not."""


class NotPermitted(RuntimeError):
    """This Slack user may not take this action. Nothing changed."""


# ------------------------------------------------------------------ config

def settings(config):
    return ((config or {}).get("slack") or {})


def enabled(config):
    return settings(config).get("enabled", False) is True


# A caller that already knows where a message goes passes `channel=`, and it
# is used verbatim - including when it is None. That is what the sentinel is
# for: `channel=None` has to be able to mean "this workspace has no channel,
# so nothing is posted", which is a different statement from "nobody told me,
# look it up". Without the distinction, a workspace with no mapping would
# silently fall back to whatever the client config happens to name, and a
# fallback is the one thing this router must not have.
UNSET = object()


def channel_for(config, kind, channel=UNSET):
    """The channel a kind posts to, or None. There is no default channel:
    guessing one is how a client's private alert lands in a shared room.

    `channel` is the workspace mapping, when the caller resolved one. It wins
    outright: where a workspace's alerts go is a workspace setting, and a
    client config that named a different room would otherwise be a second
    router with a different answer.
    """
    if channel is not UNSET:
        return channel or None
    name = CHANNEL_OF.get(kind)
    if not name:
        return None
    return settings(config).get(name) or None


def notifies(config, kind):
    """Is this kind switched on? Unlisted kinds are off."""
    notify = settings(config).get("notify") or {}
    return notify.get(kind, False) is True


def threshold(config, name):
    thresholds = settings(config).get("thresholds") or {}
    value = thresholds.get(name, DEFAULT_THRESHOLDS.get(name))
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLDS.get(name)


def approvers(config):
    return list(settings(config).get("allowed_approvers") or [])


def reviewer_groups(config):
    return list(settings(config).get("allowed_reviewer_groups") or [])


def should_notify(config, kind, channel=UNSET):
    """Every condition, in one place, so no caller has to remember them."""
    if not enabled(config):
        return False, "slack is not enabled for this client"
    if not notifies(config, kind):
        return False, f"notify.{kind} is off"
    if not channel_for(config, kind, channel):
        return False, (
            "this workspace has no Slack channel mapped"
            if channel is not UNSET else
            f"no channel configured for {kind}")
    return True, "ok"


# ---------------------------------------------------------------- payloads
#
# Every payload carries ids in `metadata`. The rendered text is for humans and
# is never read back: an interaction is trusted for what its metadata says, not
# for what its message displayed.

def _metadata(**ids):
    return {k: v for k, v in ids.items() if v not in (None, "", [], {})}


def action(action_id, label, style=None, value=None):
    button = {"action_id": action_id, "text": label}
    if style:
        button["style"] = style
    if value is not None:
        button["value"] = value
    return button


def message(kind, config, text, blocks=None, actions=(), channel=UNSET,
            **ids):
    """The envelope every payload shares."""
    return {
        "kind": kind,
        "channel": channel_for(config, kind, channel),
        "text": text,
        "blocks": list(blocks or []),
        "actions": list(actions),
        "metadata": _metadata(**ids),
    }


def campaign_approval_request(campaign, summary, config):
    """"This campaign is ready. May it go?" - with the numbers behind it."""
    lines = [
        f"*{summary.get('client')}* · {summary.get('name') or campaign.get('name')}",
        f"domains {summary.get('domains', 0)} · "
        f"contacts {summary.get('contacts', 0)} selected, "
        f"{summary.get('sendable', 0)} sendable",
        f"held {summary.get('held', 0)} · dropped {summary.get('dropped', 0)} · "
        f"suppressed {summary.get('suppressed', 0)}",
        f"email senders {', '.join(summary.get('email_senders') or []) or 'none'}",
        f"linkedin senders {', '.join(summary.get('linkedin_senders') or []) or 'none'}",
        f"daily volume {json.dumps(summary.get('daily_volume') or {}, sort_keys=True)}",
        f"cadence {summary.get('cadence') or 'default'}",
        f"estimated spend {json.dumps(summary.get('estimate') or {}, sort_keys=True)}",
    ]
    return message(
        CAMPAIGN_READY, config,
        text=f"Campaign ready for approval: {campaign.get('campaign_id')}",
        blocks=lines,
        actions=(action(APPROVE, "Approve Campaign", "primary"),
                 action(REJECT, "Reject Campaign", "danger"),
                 action(OPEN_REVIEW, "Open Review")),
        campaign_id=campaign.get("campaign_id"),
        client=campaign.get("client"),
        fingerprint=summary.get("fingerprint"))


def positive_reply_alert(detail, config, channel=UNSET):
    """Someone answered and meant it. The one alert worth interrupting for."""
    lines = [
        f"*{detail.get('company')}* · {detail.get('contact')}"
        f"{' · ' + detail['title'] if detail.get('title') else ''}",
        f"{detail.get('channel')} reply on step {detail.get('step') or '?'}"
        f" · persona {detail.get('persona') or '?'}"
        f" · angle {detail.get('angle') or '?'}",
        f"> {detail.get('excerpt') or ''}",
    ]
    return message(
        POSITIVE_REPLY, config, channel=channel,
        text=f"Positive reply: {detail.get('company')}",
        blocks=lines,
        actions=(action(OPEN_CONVERSATION, "Open conversation"),
                 action(ASSIGN_OWNER, "Assign owner"),
                 action(MARK_MEETING, "Mark meeting booked", "primary"),
                 action(MARK_NOT_POSITIVE, "Mark not positive")),
        campaign_id=detail.get("campaign_id"),
        client=detail.get("client"),
        record_id=detail.get("record_id"),
        contact_key=detail.get("contact_key"),
        source=detail.get("source"))


def operational_alert(kind, config, text, detail=None, **ids):
    return message(kind, config, text=text,
                   blocks=[f"{k}: {v}" for k, v in sorted((detail or {}).items())],
                   **ids)


def batch_summary(summary, config):
    return operational_alert(
        BATCH_COMPLETE, config,
        text=f"Batch complete: {summary.get('batch_id') or 'batch'}",
        detail=summary, client=summary.get("client"),
        batch_id=summary.get("batch_id"))


def daily_summary(summary, config):
    """Only what is actually known. A metric this system cannot observe yet is
    absent, not zero: reporting zero meetings when nothing tracks meetings is a
    lie that looks like data."""
    known = {k: v for k, v in (summary or {}).items() if v is not None}
    return operational_alert(DAILY_SUMMARY, config,
                             text=f"Daily summary: {known.get('date') or 'today'}",
                             detail=known, client=known.get("client"))


# ------------------------------------------------------------- permissions

def may_approve(config, slack_user_id):
    """Only a configured approver. An empty list permits nobody, on purpose."""
    return bool(slack_user_id) and slack_user_id in approvers(config)


def require_approver(config, slack_user_id):
    if not may_approve(config, slack_user_id):
        raise NotPermitted(
            f"{slack_user_id or 'an unidentified user'} is not in "
            "slack.allowed_approvers for this client")
    return True


def interaction(campaign_id, slack_user_id, action_id, fingerprint=None,
                interaction_id=None, at=None):
    """The neutral shape an inbound Slack action is translated into.

    Everything the decision depends on is here, and all of it comes from the
    payload metadata rather than the message text.
    """
    from .. import store
    return {
        "campaign_id": campaign_id,
        "slack_user_id": slack_user_id,
        "action": action_id,
        "fingerprint": fingerprint,
        "interaction_id": interaction_id,
        "at": at or store.now(),
    }


# --------------------------------------------------------------- transport
#
# Posting is off unless SLACK_LIVE is explicitly set. Two switches, not one:
# a token being present must never be enough, because a token gets configured
# for a health check and then a fixture wakes a client at 3am.

LIVE_VAR = "SLACK_LIVE"
SIGNING_SECRET_VAR = "SLACK_SIGNING_SECRET"
WEBHOOK_VAR = "SLACK_WEBHOOK_URL"

POST_MESSAGE = "/chat.postMessage"
AUTH_TEST = "/auth.test"


def live():
    """Is posting switched on? Requires the flag AND a token."""
    flag = (os.environ.get(LIVE_VAR) or "").strip().lower()
    return flag in ("1", "true", "yes", "on") and bool(
        (os.environ.get(KEY_VAR) or "").strip())


def render(payload):
    """The message body Slack receives. Blocks become one text field.

    Deliberately plain text rather than Block Kit: the actions are carried in
    metadata and acted on by id, so rich blocks would add a rendering surface
    without adding a capability.
    """
    lines = [payload.get("text") or ""]
    lines.extend(payload.get("blocks") or [])
    actions = payload.get("actions") or []
    if actions:
        lines.append("actions: " + ", ".join(a.get("text", "") for a in actions))
    return "\n".join(line for line in lines if line)


def post(payload, config=None):
    """Send one message, or refuse. Never raises a secret.

    Refuses unless SLACK_LIVE is on, a token exists and the payload names a
    channel. A missing channel is a configuration error, not a reason to pick
    one.
    """
    if not live():
        raise SlackPostingNotEnabled(
            f"Slack posting is off. Set {LIVE_VAR}=1 and {KEY_VAR} to enable "
            f"it. The payload was built and is testable; intended channel: "
            f"{payload.get('channel')!r}")
    channel = payload.get("channel")
    if not channel:
        raise SlackPostingNotEnabled(
            "this payload names no channel, and there is no default to fall "
            "back on")

    body = {"channel": channel, "text": render(payload)}
    status, data = request("POST", f"{BASE}{POST_MESSAGE}",
                           {"Authorization": f"Bearer {key(KEY_VAR)}",
                            "Content-Type": "application/json; charset=utf-8"},
                           body)
    if not ok(status):
        raise ProviderError(f"slack postMessage: {status}")
    if isinstance(data, dict) and not data.get("ok", False):
        # Slack answers 200 with ok:false and an error name. Carry the name,
        # never the payload, which would echo the message back into a log.
        raise ProviderError(f"slack postMessage: {data.get('error', 'unknown')}")
    return {"ok": True, "ts": mapping(data, "slack").get("ts"),
            "channel": channel}


# ------------------------------------------------- interaction verification
#
# Slack signs every interactive payload. Verifying that signature is the only
# thing standing between a campaign approval and anyone who can guess a URL, so
# it is done here, before the payload is parsed, and a failure is never
# retried: a bad signature does not become good.

MAX_SIGNATURE_AGE = 300          # five minutes, Slack's own recommendation
SIGNATURE_VERSION = "v0"


class BadSignature(RuntimeError):
    """The payload did not come from Slack, or is too old. Nothing happened."""


def signing_secret():
    return (os.environ.get(SIGNING_SECRET_VAR) or "").strip()


def sign(body, timestamp, secret=None):
    """The signature Slack would send for this body. Used to verify and to test."""
    secret = secret or signing_secret()
    if not secret:
        raise BadSignature(
            f"{SIGNING_SECRET_VAR} is not configured, so no interaction can be "
            "verified. Refusing rather than trusting an unsigned payload.")
    base = f"{SIGNATURE_VERSION}:{timestamp}:{body}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_VERSION}={digest}"


def verify(body, timestamp, signature, secret=None, now=None,
           max_age=MAX_SIGNATURE_AGE):
    """Is this really from Slack, and recent? Raises BadSignature if not.

    Three checks, in the order that fails cheapest first: the timestamp is a
    number, it is fresh, and the signature matches. The comparison is constant
    time, because a leaky comparison is how a signature gets guessed.
    """
    try:
        sent_at = int(str(timestamp).strip())
    except (TypeError, ValueError):
        raise BadSignature("the timestamp is missing or not a number")

    current = int(now if now is not None else time.time())
    age = abs(current - sent_at)
    if age > max_age:
        raise BadSignature(
            f"the payload is {age}s old, over the {max_age}s limit. A replayed "
            "payload is refused even when its signature is valid")

    expected = sign(body, sent_at, secret)
    if not hmac.compare_digest(expected, str(signature or "")):
        raise BadSignature("the signature does not match")
    return True


def check():
    """Readiness only. Nothing is posted to find out."""
    token = (os.environ.get(KEY_VAR) or "").strip()
    if not token:
        return {"provider": "Slack", "ok": None, "status": None, "skipped": True,
                "note": f"{KEY_VAR} is not set: no workspace is connected"}
    # Deliberately not gated on `live()`.
    #
    # `auth.test` is free and read-only and this function's whole job is
    # readiness, but it used to return SKIP whenever `SLACK_LIVE` was off -
    # and `SLACK_LIVE` is the switch that arms `post()`. So the only way to
    # find out whether the token worked was to turn on sending, which is
    # exactly backwards for a health check, and it made a read-only Slack
    # proof a code change rather than a setting.
    #
    # Whether posting is armed is a separate fact and is reported as one.
    try:
        # auth.test is free and read-only: it identifies the token and posts
        # nothing. It is the only live call this module makes on a health check.
        status, data = request("POST", f"{BASE}{AUTH_TEST}",
                               {"Authorization": f"Bearer {key(KEY_VAR)}"})
        if isinstance(data, dict) and data.get("ok"):
            return result("Slack", status,
                          f"team {data.get('team')} as {data.get('user')}")
        return {"provider": "Slack", "ok": False, "status": status,
                # Not `mapping` here: this is already the failure branch,
                # and raising while reporting a failure would replace the
                # status with a traceback.
                "note": ("auth.test: "
                         + str((data.get("error", "unknown")
                                if isinstance(data, dict)
                                else f"unreadable {type(data).__name__}")))}
    except ProviderError as e:
        return failed("Slack", e)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.providers.slack")
    p.add_argument("--check", action="store_true")
    p.parse_args(argv)
    r = check()
    mark = "SKIP" if r.get("skipped") else ("ok  " if r["ok"] else "FAIL")
    print(f"{mark} {r['provider']:<12} {r['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
