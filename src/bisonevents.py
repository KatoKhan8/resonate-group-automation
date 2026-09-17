"""Normalise one EmailBison webhook payload into a trimmed event dict.

EmailBison retries every webhook five times over 24 hours and
`/api/events` replays the last ten days.  Duplicate delivery is documented
and normal.  This module makes two deliveries of one event produce one
`event_key`, and two genuinely different events produce different keys.

SCOPE: a pure function and a dedupe predicate.  No server, no endpoint,
no provider call.  Wiring to a real HTTP route is Claude's, after review.

MEASURED AGAINST REAL PROVIDER EVENTS ON 2026-09-17.  1,200 rows were walked
from `/api/events` by cursor.  **Every assumed field path below was wrong, and
`normalise` rejected 100% of real events** - all of them on the first check,
`data.occurred_at is missing`.  The table now records what was OBSERVED.

THE REAL ENVELOPE, from `/api/events`::

    {"id": 12345, "uuid": "....", "created_at": "...", "updated_at": "...",
     "webhook_deliveries": [],
     "payload": {
        "event": {"type": "EMAIL_SENT", "name": "Email Sent",
                  "instance_url": "...", "workspace_id": 10,
                  "workspace_name": "PRODUCTIVE"},
        "data": {"campaign":        {"id": ..., "name": ...},
                 "campaign_event":  {"id": ..., "type": ...,
                                     "created_at": ..., "created_at_local": ...,
                                     "local_timezone": ...},
                 "lead":            {"id": ..., "email": ..., "first_name": ...,
                                     "company": ..., "status": ..., ...},
                 "scheduled_email": {"id": ..., "lead_id": ..., "sent_at": ...,
                                     "raw_message_id": ..., "status": ...,
                                     "sequence_step_id": ..., ...},
                 "sender_email":    {"id": ..., "email": ..., "daily_limit": ...},
                 "reply":           {...}   # ONLY on LEAD_REPLIED / EMAIL_BOUNCED
        }}}

**WHETHER A WEBHOOK POSTS THE ENVELOPE OR THE `payload` OBJECT IS
HYPOTHESIS.**  `webhook_deliveries` sits BESIDE `payload` rather than inside
it, which reads as "this payload is what gets delivered" - but no real webhook
delivery has been captured, and that inference is not a contract.  So
`normalise` accepts EITHER: given an envelope it unwraps `payload` and keeps
the envelope's `uuid`/`id` as the provider event id; given a bare payload it
proceeds without one.

=========================  ========  ========================================
Field                      Status    Notes
=========================  ========  ========================================
event.type                 OBSERVED  UPPER_SNAKE confirmed.  Values actually
                                     seen in 1,200 rows: EMAIL_SENT (1121),
                                     LEAD_FIRST_CONTACTED (48),
                                     EMAIL_BOUNCED (15),
                                     EMAIL_SEND_FAILED (15),
                                     LEAD_REPLIED (1).
                                     **THE REPLY TYPE IS `LEAD_REPLIED`, NOT
                                     `CONTACT_REPLIED`.**  The assumed name
                                     mapped to "unknown", so a real reply
                                     would not have suppressed anything.
                                     EMAIL_OPENED, CONTACT_UNSUBSCRIBED,
                                     CONTACT_INTERESTED, TAG_ATTACHED,
                                     TAG_REMOVED and
                                     UNTRACKED_REPLY_RECEIVED were NOT seen;
                                     they remain UNCONFIRMED rather than
                                     disproven - this estate has sent little
                                     and opens are not tracked on it.
event.id                   REFUTED   ABSENT in 1,200 of 1,200.  The provider's
                                     event identity is on the ENVELOPE:
                                     `uuid` (36 chars) and `id` (int).
                                     `event_key` would have fallen back to its
                                     composite every single time.
event.workspace_id         OBSERVED  Integer, present in all 1,200.  This
                                     estate reads 10.
data.lead_id               REFUTED   Real path is `data.lead.id`.
                                     (`data.scheduled_email.lead_id` also
                                     exists and agrees.)
data.campaign_id           REFUTED   Real path is `data.campaign.id`.
data.email                 REFUTED   Real path is `data.lead.email`.
data.occurred_at           REFUTED   No such field.  Three real timestamps,
                                     all present in all 1,200:
                                     `data.campaign_event.created_at` - when
                                     the event itself happened, and the one
                                     used here;
                                     `data.scheduled_email.sent_at`;
                                     and the envelope's own `created_at`.
data.message_id            REFUTED   Real path is
                                     `data.scheduled_email.raw_message_id`.
                                     NOT used by `event_key`.
data.reply                 OBSERVED  Present ONLY on LEAD_REPLIED and
                                     EMAIL_BOUNCED, absent on the other three.
                                     So the reply body has a home, and a
                                     normaliser must not require it.
=========================  ========  ========================================

STILL UNKNOWN, and not answerable from `/api/events`: whether a real webhook
delivery carries the envelope or the payload, and whether a RETRY of one
delivery repeats the envelope `uuid`.  The second decides whether the dedupe
key survives a retry, which is the whole point of the module.
"""
import os

TYPE_TO_KIND = {
    # OBSERVED in 1,200 real events, 2026-09-17.
    "EMAIL_SENT": "sent",
    "LEAD_REPLIED": "replied",            # NOT "CONTACT_REPLIED". See below.
    "EMAIL_BOUNCED": "bounced",
    "EMAIL_SEND_FAILED": "send_failed",
    "LEAD_FIRST_CONTACTED": "first_contacted",
    # NOT OBSERVED on this estate and kept rather than removed: the docs name
    # them and absence here is explained - nothing has been opened because
    # open tracking is off, and nobody has unsubscribed from ten queued
    # emails. Removing them would turn a real future event into "unknown".
    "EMAIL_OPENED": "opened",
    "CONTACT_UNSUBSCRIBED": "unsubscribed",
    "CONTACT_INTERESTED": "interested",
    # THE ASSUMED REPLY NAME, KEPT AS AN ALIAS AND NOT AS THE TRUTH.
    # `CONTACT_REPLIED` was this module's assumed reply type and it never
    # existed: the provider sends `LEAD_REPLIED`. The assumption mapped a real
    # reply to "unknown", which is a reply that suppresses nothing. It stays
    # mapped because a provider that adds the name later must not produce that
    # same silence - but `LEAD_REPLIED` above is the observed one.
    "CONTACT_REPLIED": "replied",
    "UNTRACKED_REPLY_RECEIVED": "replied",
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


def _workspace_id(raw):
    """A workspace id, strictly, or a CLASSIFIED refusal.

    `int(raw)` was called directly and GLM's review of this file - run before
    it had a caller - found two holes in that one expression.

    **`int("bison")` raises a bare `ValueError`.** The caller of a webhook
    handler catches the two exceptions this module documents; an undocumented
    third becomes a 500, and a provider that retries 5xx five times over 24
    hours turns one malformed payload into fifteen requests. Worse, the crash
    happened BEFORE the tenancy comparison, so a cross-tenant probe got a 500
    where a legitimate-but-foreign payload got a clean refusal - two
    distinguishable answers, which is a probe signal.

    **`int(True) == 1`, and `bool` is a subclass of `int`.** So a JSON `true`
    or a `1.0` both coerce to 1 and would PASS tenancy on a workspace pinned
    to 1. This estate is pinned to 10, so it was not exploitable here - which
    is exactly the kind of "safe by accident" that stops being true when
    somebody adds a second tenant.

    Accepted: an `int` that is not a `bool`, or a string of digits. Everything
    else is MalformedPayload, which the handler already has to handle.
    """
    if isinstance(raw, bool):
        raise MalformedPayload(
            f"event.workspace_id is the boolean {raw!r}; bool is a subclass "
            f"of int and would coerce to {int(raw)}")
    if isinstance(raw, int):
        return raw
    text = str(raw).strip()
    if not text.isdigit():
        raise MalformedPayload(
            f"event.workspace_id {raw!r} is not an id. Refused as malformed "
            f"rather than raised as a ValueError: an undocumented exception "
            f"here becomes a 5xx, and this provider retries those")
    return int(text)


def _unwrap(payload):
    """`(payload, envelope)` - accepts an /api/events row or a bare payload.

    A row from `/api/events` carries the event under `payload`, with the
    provider's own identity (`uuid`, `id`) and `created_at` on the OUTSIDE.
    Whether a webhook POSTs that envelope or just the inner object is not
    documented and no real delivery has been captured, so both are accepted
    rather than one being guessed.

    The envelope is not discarded: it is where the provider event id actually
    lives, `event.id` having been measured absent in 1,200 of 1,200 rows.
    """
    if isinstance(payload.get("payload"), dict) and "event" not in payload:
        return payload["payload"], payload
    return payload, None


def normalise(payload):
    """One decoded webhook payload -> a trimmed event dict.

    Accepts an `/api/events` envelope or a bare payload object.

    Raises TenancyRefused if the workspace_id is not ours.
    Raises MalformedPayload if data or a required field is missing.
    """
    if not isinstance(payload, dict):
        raise MalformedPayload(
            f"payload is {type(payload).__name__}, not an object")
    payload, envelope = _unwrap(payload)
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
    payload_ws = _workspace_id(raw_ws)
    if payload_ws != pin:
        raise TenancyRefused(
            f"workspace_id {payload_ws} does not match pin {pin}; "
            f"refusing to let another tenant's event reach our state")

    kind = _normalise_type(raw_type)

    # EVERY PATH BELOW IS THE MEASURED ONE. The four this module originally
    # read - data.occurred_at, data.lead_id, data.campaign_id, data.email -
    # do not exist in a real event, and the first of them rejected 100% of
    # them before any of the others was reached.
    lead = data.get("lead") if isinstance(data.get("lead"), dict) else {}
    campaign = (data.get("campaign")
                if isinstance(data.get("campaign"), dict) else {})
    scheduled = (data.get("scheduled_email")
                 if isinstance(data.get("scheduled_email"), dict) else {})
    campaign_event = (data.get("campaign_event")
                      if isinstance(data.get("campaign_event"), dict) else {})

    # WHEN THE EVENT HAPPENED, most specific first. `campaign_event.created_at`
    # is the event's own time; `scheduled_email.sent_at` is the send's; the
    # envelope's `created_at` is when the provider recorded it. They are not
    # the same question, so the source is reported rather than flattened.
    occurred_at, occurred_from = None, None
    for value, source in ((campaign_event.get("created_at"), "campaign_event"),
                          (scheduled.get("sent_at"), "scheduled_email"),
                          ((envelope or {}).get("created_at"), "envelope")):
        if value:
            occurred_at, occurred_from = value, source
            break
    if not occurred_at:
        raise MalformedPayload(
            "no timestamp: campaign_event.created_at, scheduled_email.sent_at "
            "and the envelope's created_at are all absent")

    lead_id = lead.get("id", scheduled.get("lead_id"))
    if lead_id is None:
        raise MalformedPayload("data.lead.id is missing")

    campaign_id = campaign.get("id")
    if campaign_id is None:
        raise MalformedPayload("data.campaign.id is missing")

    email = lead.get("email")
    if not email:
        raise MalformedPayload("data.lead.email is missing")

    return {
        "provider_event_type": raw_type,
        # The provider's identity lives on the envelope. `uuid` is preferred
        # over `id` because it is the value most likely to be stable across a
        # redelivery - which is UNKNOWN and is the open question for dedupe.
        "provider_event_id": (envelope or {}).get("uuid")
                             or (envelope or {}).get("id"),
        "workspace_id": payload_ws,
        "campaign_id": campaign_id,
        "lead_id": lead_id,
        "email": email,
        "occurred_at": occurred_at,
        "occurred_at_source": occurred_from,
        "message_id": scheduled.get("raw_message_id"),
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

    **THE RESIDUAL RISK IS `occurred_at`, AND IT IS NOT GUARDED HERE.** This
    fallback is stable only if that field is the time the event HAPPENED. If
    the provider stamps the time it was DELIVERED, then a retry twenty-three
    hours later carries a different value, the key changes, and dedupe fails
    silently - which is precisely the failure this module exists to prevent,
    arriving through the one path that has no provider evidence behind it.
    Marked ASSUMED in the table above; check it against a real retry, not a
    real first delivery, before this is wired to anything.
    """
    eid = event.get("provider_event_id")
    if eid:
        return f"bison:{eid}"
    # LOUD, CLASSIFIED, AND NEVER SUBSTITUTED. These five were indexed
    # directly, so an id-less event missing any of them raised a bare
    # `KeyError` - and GLM's review named both the failure and the wrong fix.
    #
    # The wrong fix is `.get(k, "")`. That turns a loud failure into a silent
    # mass collision: a provider sending `"lead_id": null` renders as the
    # literal `None`, and a batch sharing one `occurred_at` collapses N
    # distinct leads onto one key. First write wins and N-1 events are
    # silently deduped. **If the kind is `unsubscribed`, those people keep
    # getting mail.**
    #
    # So it fails loudly - but as MalformedPayload, which a handler already
    # has to catch and can route to a dead letter without taking the rest of
    # a batch down with it.
    missing = [f for f in ("kind", "workspace_id", "campaign_id", "lead_id",
                           "occurred_at")
               if event.get(f) in (None, "")]
    if missing:
        raise MalformedPayload(
            f"cannot derive an event key without {', '.join(missing)}, and "
            f"substituting a blank would collapse distinct leads onto one key")
    parts = (event["kind"], event["workspace_id"], event["campaign_id"],
             event["lead_id"], event["occurred_at"])
    return "bison:" + ":".join(str(p) for p in parts)
