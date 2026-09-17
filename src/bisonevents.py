"""Normalise one EmailBison webhook payload into a trimmed event dict.

EmailBison retries every webhook five times over 24 hours and
`/api/events` replays the last ten days.  Duplicate delivery is documented
and normal.  This module makes two deliveries of one event produce one
`event_key`, and two genuinely different events produce different keys.

SCOPE: a pure function and a dedupe predicate.  No server, no endpoint,
no provider call.  Wiring to a real HTTP route is Claude's, after review.

Payload shape (documented at docs.emailbison.com and the OpenAPI spec)::

    {"event": {"type": "EMAIL_SENT", "name": "Email Sent",
               "instance_url": "https://dedi.emailbison.com",
               "workspace_id": 10, "workspace_name": "Productive",
               "id": "evt-abc-123"},
     "data": {"lead_id": 4001, "campaign_id": 487,
              "email": "champ@example.test",
              "occurred_at": "2026-09-17T10:00:00Z"}}

ASSUMED payload fields - every one must be checked against a real webhook
before this module is wired to a live endpoint:

=========================  ======  ==========================================
Field                      Status  Notes
=========================  ======  ==========================================
event.type                 ASSUMED  UPPER_SNAKE values: EMAIL_SENT,
                                   EMAIL_OPENED, CONTACT_REPLIED,
                                   EMAIL_BOUNCED, CONTACT_UNSUBSCRIBED,
                                   CONTACT_INTERESTED, TAG_ATTACHED,
                                   TAG_REMOVED, UNTRACKED_REPLY_RECEIVED.
                                   The docs use English names ("Email Sent");
                                   the example payload uses UPPER_SNAKE.
                                   Both are handled by normalising to upper
                                   and stripping spaces, but the real values
                                   must be confirmed.
event.id                   ASSUMED  Present in every payload.  The OpenAPI
                                   spec shows `id` on webhook event objects
                                   but the research doc does not reproduce a
                                   full payload.  If absent, event_key falls
                                   back to a derived composite.
event.workspace_id         ASSUMED  Integer.  The poller already reads this
                                   from reply payloads; webhooks are expected
                                   to carry it at the same path.
data.lead_id               ASSUMED  Integer.  Every event-specific data shape
                                   is expected to carry this.
data.campaign_id           ASSUMED  Integer.  Same assumption as lead_id.
data.email                 ASSUMED  String.  The contact's email address.
data.occurred_at           ASSUMED  ISO-8601 string with timezone.  The poller
                                   already reads `occurred_at` / `createdAt`
                                   from reply payloads.
data.message_id            ASSUMED  Present on EMAIL_SENT, EMAIL_OPENED,
                                   CONTACT_REPLIED, EMAIL_BOUNCED.  Absent on
                                   TAG_ATTACHED, CONTACT_INTERESTED.  Used in
                                   the derived event_key when event.id is
                                   missing.
=========================  ======  ==========================================
"""
import os

TYPE_TO_KIND = {
    "EMAIL_SENT": "sent",
    "EMAIL_OPENED": "opened",
    "CONTACT_REPLIED": "replied",
    "EMAIL_BOUNCED": "bounced",
    "CONTACT_UNSUBSCRIBED": "unsubscribed",
    "CONTACT_INTERESTED": "interested",
}

ALLOWED_KINDS = frozenset(TYPE_TO_KIND.values()) | {"unknown"}


class TenancyRefused(Exception):
    """A payload whose workspace_id is not ours."""


class MalformedPayload(Exception):
    """A payload missing a required field."""


def _expected_workspace(env=None):
    """Which workspace this deployment believes it owns, or None.

    Follows `replywatch.expected_workspace`: reads BISON_WORKSPACE_ID from
    the environment without loading config/.env.  None means unpinned, and
    unpinned refuses every payload rather than silently accepting one.
    """
    source = env if env is not None else os.environ
    raw = (source.get("BISON_WORKSPACE_ID") or "").strip()
    return int(raw) if raw else None


def _normalise_type(raw_type):
    """Map a provider event type string to a kind.

    Unknown types map to "unknown" and are never folded into a neighbouring
    kind.  This follows `heyreach.lead_state`, which returns LIFECYCLE_UNKNOWN
    for any value not in its allowlist.
    """
    key = raw_type.strip().upper().replace(" ", "_")
    return TYPE_TO_KIND.get(key, "unknown")


def normalise(payload):
    """One decoded webhook payload -> a trimmed event dict.

    Raises TenancyRefused if the workspace_id is not ours.
    Raises MalformedPayload if data or a required field is missing.
    """
    event_block = payload.get("event")
    if not isinstance(event_block, dict):
        raise MalformedPayload("payload has no 'event' block")

    raw_type = event_block.get("type")
    if not raw_type:
        raise MalformedPayload("event.type is missing")

    raw_ws = event_block.get("workspace_id")
    if raw_ws is None:
        raise MalformedPayload("event.workspace_id is missing")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise MalformedPayload("payload has no 'data' block")

    pin = _expected_workspace()
    if pin is None:
        raise TenancyRefused(
            "BISON_WORKSPACE_ID is not set; refusing every payload rather "
            "than accepting one for an unverified workspace")
    payload_ws = int(raw_ws)
    if payload_ws != pin:
        raise TenancyRefused(
            f"workspace_id {payload_ws} does not match pin {pin}; "
            f"refusing to let another tenant's event reach our state")

    kind = _normalise_type(raw_type)

    occurred_at = data.get("occurred_at")
    if not occurred_at:
        raise MalformedPayload("data.occurred_at is missing")

    lead_id = data.get("lead_id")
    if lead_id is None:
        raise MalformedPayload("data.lead_id is missing")

    campaign_id = data.get("campaign_id")
    if campaign_id is None:
        raise MalformedPayload("data.campaign_id is missing")

    email = data.get("email")
    if not email:
        raise MalformedPayload("data.email is missing")

    return {
        "provider_event_type": raw_type,
        "provider_event_id": event_block.get("id"),
        "workspace_id": payload_ws,
        "campaign_id": campaign_id,
        "lead_id": lead_id,
        "email": email,
        "occurred_at": occurred_at,
        "kind": kind,
        "raw_keys": sorted(data.keys()),
    }


def event_key(event):
    """Idempotency key for a normalised event.

    Prefer the provider's own event id when present: it is the vendor's
    statement that this is one occurrence, and it is stable across retries.

    When event.id is absent (ASSUMED to be rare but not impossible), derive
    a key from the fields that together identify the occurrence:
    (kind, workspace_id, campaign_id, lead_id, occurred_at).  This set is
    sufficient because:

    - kind + lead_id + occurred_at distinguishes two events at the same
      lead at different times, or different kinds at the same time.
    - campaign_id + workspace_id prevents cross-campaign or cross-workspace
      collision for leads that appear in more than one estate.

    A key that changes between two deliveries of the same event is a bug;
    so is one that collides across two genuinely different events.
    """
    eid = event.get("provider_event_id")
    if eid:
        return f"bison:{eid}"
    parts = (event["kind"], event["workspace_id"], event["campaign_id"],
             event["lead_id"], event["occurred_at"])
    return "bison:" + ":".join(str(p) for p in parts)
