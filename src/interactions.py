#!/usr/bin/env python3
"""Inbound Slack interactions: verify, then decide, in that order.

This is the module a forged payload has to get past, so it is written to be
read by someone looking for a hole. The order is deliberate and every step is
a refusal, not a warning:

    1. verify the signature      - is this from Slack at all?
    2. check the timestamp       - is it fresh, or a replay of a real one?
    3. check the interaction id  - have we already acted on it?
    4. parse the payload         - only now is anything read
    5. check the actor           - is this person a configured approver?
    6. check the fingerprint     - is this still the campaign they saw?
    7. apply the decision        - through the orchestrator, like any other

Steps 1 and 2 happen before the body is parsed, so a forged payload never
reaches code that trusts its contents. Step 6 is what makes "Approve" mean
"approve *this*": the button carries the fingerprint the message was built
with, and a campaign that changed since is refused even for the right person
with a perfect signature.

None of these failures is retried. A bad signature does not become good, and
retrying an unauthorised approval is how a retry storm turns into an audit
finding.

The HTTP layer is not here. Whatever eventually terminates the request should
read the raw body and three headers, call `handle()`, and return its status -
nothing else. Business logic in an HTTP handler is how a webhook ends up with
two behaviours.
"""
import json
import os
import urllib.parse

from . import campaigns, clients, events, orchestrator, store
from .providers import slack

# Slack's header names, so the HTTP layer does not have to know them either.
SIGNATURE_HEADER = "X-Slack-Signature"
TIMESTAMP_HEADER = "X-Slack-Request-Timestamp"

# How many interaction ids to remember. Slack retries within seconds, so this
# only has to outlive a retry burst; the durable defence is that the campaign
# itself records the interaction id it acted on.
SEEN_LIMIT = 512
_seen = []


class Rejected(RuntimeError):
    """The interaction was refused. Nothing changed, and it is not retryable."""


def reset_seen():
    """Tests and long-lived runners forget the replay cache."""
    _seen.clear()


def _remember(interaction_id):
    """True if this is new. False if we have already seen it in this process."""
    if not interaction_id:
        return True
    if interaction_id in _seen:
        return False
    _seen.append(interaction_id)
    if len(_seen) > SEEN_LIMIT:
        del _seen[:len(_seen) - SEEN_LIMIT]
    return True


def parse(body):
    """Slack posts `payload=<url-encoded json>`. Returns the decoded dict."""
    if not isinstance(body, str):
        raise Rejected("the request body is not text")
    raw = body
    if body.startswith("payload="):
        pairs = urllib.parse.parse_qs(body)
        values = pairs.get("payload") or []
        if not values:
            raise Rejected("no payload field in the request body")
        raw = values[0]
    try:
        payload = json.loads(raw)
    except ValueError:
        raise Rejected("the payload is not valid JSON")
    if not isinstance(payload, dict):
        raise Rejected("the payload is not an object")
    return payload


def interaction_id(payload):
    """A stable id for one click.

    Slack's `trigger_id` changes per delivery, so it cannot be the idempotency
    key: a retry of the same click would look like a second click. The message
    and the action together identify the click itself.
    """
    container = payload.get("container") or {}
    message = payload.get("message") or {}
    actions = payload.get("actions") or [{}]
    action = actions[0] if actions else {}
    parts = [
        str(payload.get("callback_id") or ""),
        str(container.get("message_ts") or message.get("ts") or ""),
        str(action.get("action_id") or action.get("value") or ""),
        str((payload.get("user") or {}).get("id") or ""),
    ]
    return "slack:" + ":".join(p for p in parts if p)


def metadata_of(payload):
    """The ids the message was built with. Never read from the visible text."""
    actions = payload.get("actions") or [{}]
    action = actions[0] if actions else {}
    raw = action.get("value")
    if isinstance(raw, str) and raw.strip():
        try:
            decoded = json.loads(raw)
            if isinstance(decoded, dict):
                return decoded
        except ValueError:
            pass
    for name in ("metadata", "private_metadata"):
        blob = payload.get(name)
        if isinstance(blob, dict):
            return blob
        if isinstance(blob, str) and blob.strip():
            try:
                decoded = json.loads(blob)
                if isinstance(decoded, dict):
                    return decoded
            except ValueError:
                continue
    return {}


ACTION_TO_DECISION = {slack.APPROVE: "approve", slack.REJECT: "reject"}


def handle(body, timestamp, signature, secret=None, now=None, rows=None,
           config=None, recs=None):
    """One Slack interaction, verified and applied. Returns what happened.

    Every early return is a refusal with a reason. Nothing here is retryable:
    the caller should answer Slack and move on.
    """
    # 1 and 2: is this from Slack, and is it fresh? Before anything is parsed.
    try:
        slack.verify(body, timestamp, signature, secret=secret, now=now)
    except slack.BadSignature as e:
        _note_rejection("signature", str(e))
        raise Rejected(f"signature: {e}")

    payload = parse(body)
    actions = payload.get("actions") or []
    action_id = (actions[0] if actions else {}).get("action_id")
    decision = ACTION_TO_DECISION.get(action_id)
    if decision is None:
        return {"status": "ignored", "why": f"no decision maps to {action_id!r}"}

    # 3: the same click delivered twice must change state once.
    click = interaction_id(payload)
    if not _remember(click):
        return {"status": "duplicate", "interaction_id": click,
                "why": "this interaction was already handled"}

    meta = metadata_of(payload)
    campaign_id = meta.get("campaign_id")
    if not campaign_id:
        raise Rejected("the payload names no campaign")

    actor = (payload.get("user") or {}).get("id")

    own = rows is None
    rows = campaigns.load() if own else rows
    campaign = campaigns.get(campaign_id, rows)
    if campaign is None:
        raise Rejected(f"no such campaign: {campaign_id}")

    if config is None:
        config = clients.load(campaign.get("client"))

    # A payload for one client must never decide another client's campaign.
    if meta.get("client") and meta["client"] != campaign.get("client"):
        raise Rejected("the payload's client does not match the campaign's")

    # 5, 6 and 7 all live in the orchestrator, which already refuses an
    # unauthorised actor and a stale fingerprint. Nothing is re-implemented
    # here: a second copy of that logic is a second thing to get wrong.
    result = orchestrator.decide(
        campaign, actor, decision, fingerprint=meta.get("fingerprint"),
        interaction_id=click, config=config, recs=recs)
    if own and result.get("status") in ("approved", "rejected"):
        campaigns.save(rows)
    return {**result, "interaction_id": click, "campaign_id": campaign_id,
            "actor": actor}


def _note_rejection(reason, detail):
    """Rejections are counted, not stored: a forged payload is not a record."""
    from . import observability
    observability.count(events.WEBHOOK_REJECTED, provider="slack",
                        reason=reason, detail=detail[:120])


def headers_from(mapping):
    """Pull Slack's two headers out of whatever the HTTP layer provides."""
    lowered = {str(k).lower(): v for k, v in (mapping or {}).items()}
    return (lowered.get(TIMESTAMP_HEADER.lower()),
            lowered.get(SIGNATURE_HEADER.lower()))
