#!/usr/bin/env python3
"""Where a notification goes, and why it is never the other client's channel.

## Two levels, and the reason they must not touch

There are exactly two kinds of Slack destination in this product, and mixing
them is the failure this module exists to prevent:

    GLOBAL      one channel: Resonate's own operations feed. Approvals to
                make, jobs that failed, providers that are degraded, replies
                nobody could match. Internal, operational, and about every
                workspace at once.

    WORKSPACE   one channel per client. A positive reply, and very little
                else. Written so it could one day be a channel the *client*
                is sitting in.

A message that belongs in one and lands in the other is not a formatting
mistake. Putting internal QA diagnostics in a client's channel is a bad day;
putting ContactOut's prospect in Productive's channel is the kind that ends an
account.

So the destination is decided by a table keyed on the event type, the
workspace channel is an explicit mapping, and **there is no fallback**. A
workspace with no channel configured produces a notification in state
`unconfigured` - a durable record of something that did not happen - rather
than a message somebody else receives. `route_to_workspace` cannot return
another workspace's channel because it never looks at another workspace.

## The router is a pure function

    event -> event type -> destination + severity     ROUTES, a table
          -> workspace policy                         is this kind on here?
          -> channel                                  explicit mapping only
          -> sanitised payload                        per destination
          -> a stored notification                    nothing is posted here

Nothing in that chain reads message text and nothing guesses. An event type
absent from `ROUTES` routes to `NOWHERE`, not to the global channel: a
notification layer whose default is "tell everybody" becomes noise, and noise
gets muted, and a muted channel is worse than no channel.

## Idempotency is an id, not a search

Every notification carries a deterministic id built from the facts that make
it *the same notification*: the event type, the workspace, and whichever of
the record, contact, campaign and provider event identify the occurrence. A
poller replaying the same EmailBison reply produces the same id and the second
write is a no-op. Same construction `events.record` uses for provider events,
and for the same reason.

## Slack failing changes nothing

A notification is planned *after* the business state is already correct. The
reply pauses the company, the classification is stored, and only then is
anything routed. If the transport fails the record moves to `failed` and stays
retryable; the pause, the suppression and the campaign state do not move.
`notify()` is written so that it cannot raise into a caller - a notification
layer that can break the engine is not a notification layer.

## Nothing here posts

`plan()` builds and stores. `deliver()` asks `slack.post`, which refuses
unless `SLACK_LIVE` is set, and it is not set in this build. The statuses
reachable here are `planned`, `unconfigured` and `suppressed`; `sent` requires
a transport this build does not have.

  python -m src.notify --list
  python -m src.notify --workspace productive
"""
import argparse
import hashlib
import json
import re
import os

from . import store, testidentity, workspaces as ws
from .providers import slack

# ------------------------------------------------------------ destinations

GLOBAL = "global"
WORKSPACE = "workspace"
#: The team-facing status feed. OPERATOR DECISION, 2026-09-21: a THIRD
#: destination rather than a second use of the ops channel. Ops is where
#: something needs doing; status is where the team reads what the machine is
#: doing. Mixing them makes the loud one unreadable and the quiet one ignored,
#: which is the same argument that separated GLOBAL from WORKSPACE.
#:
#: NOTHING HERE CARRIES A PROSPECT. Names, addresses and client-internal
#: detail beyond counts are refused by `_status_payload`, not by convention -
#: this channel has the widest human audience in the product.
STATUS = "status"
NOWHERE = "nowhere"
DESTINATIONS = (GLOBAL, WORKSPACE, STATUS, NOWHERE)

# --------------------------------------------------------------- severity

INFO = "info"
ACTION_REQUIRED = "action_required"
WARNING = "warning"
CRITICAL = "critical"
SEVERITIES = (INFO, ACTION_REQUIRED, WARNING, CRITICAL)

# ----------------------------------------------------------------- status

PLANNED = "planned"
SENT = "sent"
FAILED = "failed"
RETRYING = "retrying"
SUPPRESSED = "suppressed"
UNCONFIGURED = "unconfigured"
STATUSES = (PLANNED, SENT, FAILED, RETRYING, SUPPRESSED, UNCONFIGURED)

# ------------------------------------------------------------ event types
#
# Stable names. Reporting and the notification history are keyed on these, so
# renaming one loses history - they are vocabulary, and nothing invents a
# variant.

# Global operations feed.
CAMPAIGN_APPROVAL_REQUIRED = "campaign_approval_required"
CAMPAIGN_READY_FOR_APPROVAL = "campaign_ready_for_approval"
CAMPAIGN_APPROVED = "campaign_approved"
CAMPAIGN_REJECTED = "campaign_rejected"
CAMPAIGN_HELD = "campaign_held"
CAMPAIGN_QA_FAILED = "campaign_qa_failed"
CAMPAIGN_PAUSED = "campaign_paused"
#: A campaign stopped and THIS SYSTEM CANNOT SHOW IT DID IT.
#:
#: Its own type rather than a louder CAMPAIGN_PAUSED, because that one also
#: covers our own deliberate pauses and raising its severity would make every
#: routine pause critical - which is how a critical channel stops being read.
#:
#: MEASURED 2026-09-23: campaign 495 went active -> archived at 15:57:22Z
#: with 59 of 60 leads stopped, nothing in this system did it, and nobody was
#: told. A campaign stopping is the difference between sending and not
#: sending, and it was the one state change with no alert on it.
CAMPAIGN_STOPPED_EXTERNALLY = "campaign_stopped_externally"
CAMPAIGN_COMPLETED = "campaign_completed"
WORKSPACE_CREATED = "workspace_created"
WORKSPACE_CONFIG_ISSUE = "workspace_configuration_issue"
SENDER_CAPACITY_WARNING = "sender_capacity_warning"
EMAIL_INFRASTRUCTURE_WARNING = "email_infrastructure_warning"
LINKEDIN_INFRASTRUCTURE_WARNING = "linkedin_infrastructure_warning"
VERIFICATION_DEGRADED = "verification_degraded"
MX_ANOMALY = "mx_security_anomaly"
UNMATCHED_REPLY = "unmatched_reply_needs_review"
FAILED_JOB = "failed_job_needs_attention"
PROVIDER_HEALTH_ISSUE = "provider_health_issue"
# Reply ingestion has stopped. Critical because it is the only failure
# here that means outreach may still be going out to somebody who has
# already answered.
REPLY_PROTECTION_FAILED = "reply_protection_failed"
PROVIDER_CREDIT_WARNING = "provider_credit_warning"
REPORT_GENERATED = "report_generated"
REPORT_GENERATION_FAILED = "report_generation_failed"

# Workspace feed.
POSITIVE_REPLY = "positive_reply"
NEUTRAL_REPLY = "neutral_reply"
NEGATIVE_REPLY = "negative_reply"
UNSUBSCRIBE = "unsubscribe"
CAMPAIGN_MILESTONE = "campaign_milestone"
REPORT_AVAILABLE = "report_available"
# One message a day instead of nineteen carrying one fact each. It is what
# makes routing an ordinary reply to NOWHERE reasonable: the quiet ones are
# summarised rather than lost.
OPERATIONS_DIGEST = "operations_digest"

# Status feed. Human-readable, counts only, no raw ids.
STATUS_NOW_RUNNING = "status_now_running"
STATUS_CHECKPOINT = "status_checkpoint"
STATUS_BATCH_STATS = "status_batch_stats"
STATUS_MILESTONE = "status_milestone"
#: A hard stop goes to ops AND here, which is the one deliberate double
#: route in this table. It is raised as its own type rather than by routing
#: one event twice, so each has its own id and neither can suppress the
#: other.
STATUS_HARD_STOP = "status_hard_stop"

# (destination, severity). An event type not in here routes NOWHERE.
#
# The workspace side is deliberately three lines long. Every extra kind that
# reaches a client's channel is a reason for them to stop reading it, and the
# one message worth interrupting somebody for is "a prospect said yes".
ROUTES = {
    CAMPAIGN_APPROVAL_REQUIRED: (GLOBAL, ACTION_REQUIRED),
    CAMPAIGN_READY_FOR_APPROVAL: (GLOBAL, ACTION_REQUIRED),
    CAMPAIGN_APPROVED: (GLOBAL, INFO),
    CAMPAIGN_REJECTED: (GLOBAL, INFO),
    CAMPAIGN_HELD: (GLOBAL, WARNING),
    CAMPAIGN_QA_FAILED: (GLOBAL, WARNING),
    CAMPAIGN_PAUSED: (GLOBAL, WARNING),
    CAMPAIGN_STOPPED_EXTERNALLY: (GLOBAL, CRITICAL),
    CAMPAIGN_COMPLETED: (GLOBAL, INFO),
    WORKSPACE_CREATED: (GLOBAL, INFO),
    WORKSPACE_CONFIG_ISSUE: (GLOBAL, WARNING),
    SENDER_CAPACITY_WARNING: (GLOBAL, WARNING),
    EMAIL_INFRASTRUCTURE_WARNING: (GLOBAL, WARNING),
    LINKEDIN_INFRASTRUCTURE_WARNING: (GLOBAL, WARNING),
    VERIFICATION_DEGRADED: (GLOBAL, WARNING),
    MX_ANOMALY: (GLOBAL, WARNING),
    UNMATCHED_REPLY: (GLOBAL, ACTION_REQUIRED),
    FAILED_JOB: (GLOBAL, ACTION_REQUIRED),
    PROVIDER_HEALTH_ISSUE: (GLOBAL, CRITICAL),
    REPLY_PROTECTION_FAILED: (GLOBAL, CRITICAL),
    PROVIDER_CREDIT_WARNING: (GLOBAL, WARNING),
    REPORT_GENERATED: (GLOBAL, INFO),
    REPORT_GENERATION_FAILED: (GLOBAL, WARNING),
    # INFO by construction: anything urgent has its own kind and has
    # already been sent by the time this is built.
    STATUS_NOW_RUNNING: (STATUS, INFO),
    STATUS_CHECKPOINT: (STATUS, INFO),
    STATUS_BATCH_STATS: (STATUS, ACTION_REQUIRED),
    STATUS_MILESTONE: (STATUS, INFO),
    STATUS_HARD_STOP: (STATUS, CRITICAL),
    # The 07:00 digest is a status message, and the operator moved it here on
    # 2026-09-21. Ops keeps everything that needs doing.
    OPERATIONS_DIGEST: (STATUS, INFO),

    POSITIVE_REPLY: (WORKSPACE, INFO),
    CAMPAIGN_MILESTONE: (WORKSPACE, INFO),
    REPORT_AVAILABLE: (WORKSPACE, INFO),

    # Recorded, routed nowhere. A neutral or negative reply belongs in the
    # Reply Center where somebody is already looking, and an unsubscribe is a
    # suppression to process rather than an interruption to send. Making them
    # explicit `NOWHERE` entries rather than omissions is the point: somebody
    # reading this table can see the decision was made.
    NEUTRAL_REPLY: (NOWHERE, INFO),
    NEGATIVE_REPLY: (NOWHERE, INFO),
    UNSUBSCRIBE: (NOWHERE, INFO),
}

EVENT_TYPES = tuple(sorted(ROUTES))

# Which workspace policy switch gates each workspace-bound kind, and what it
# defaults to. Positive replies are the only one on by default: it is the
# reason the channel exists.
WORKSPACE_TOGGLES = {
    POSITIVE_REPLY: ("slack.notify_positive_replies", True),
    NEUTRAL_REPLY: ("slack.notify_neutral_replies", False),
    NEGATIVE_REPLY: ("slack.notify_negative_replies", False),
    CAMPAIGN_MILESTONE: ("slack.notify_campaign_milestones", False),
    REPORT_AVAILABLE: ("slack.notify_reports", False),
}

# Where the global operations channel is configured. An environment variable
# rather than a client config, because it belongs to no client - putting it in
# one would make it look like a client's channel and invite exactly the
# mistake this module is about.
OPS_CHANNEL_VAR = "SLACK_OPS_CHANNEL"

#: The team status channel, and the switch that silences it. Same shape as
#: the ops channel and for the same reason: it belongs to no client.
STATUS_CHANNEL_VAR = "SLACK_STATUS_CHANNEL"
STATUS_ENABLED_VAR = "SLACK_STATUS"

WORKSPACE_CHANNEL_KEY = "slack.workspace_channel"


class NotifyError(RuntimeError):
    """The notification could not be built. Nothing was stored."""


# ---------------------------------------------------------------- the store

def path():
    return os.path.abspath(os.environ.get("NOTIFICATIONS")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "notifications.jsonl"))


def load():
    return store.read_jsonl(path())


def save(rows, timeout=None):
    with store.lock(timeout, for_path=path()):
        store.write_jsonl(path(), rows)


def transaction(timeout=None):
    return store.file_transaction(path(), timeout)


# --------------------------------------------------------------- the router

def route(event_type):
    """Where this kind of event goes, and how loud it is.

    An unknown type routes NOWHERE. That is the important default: a
    notification layer whose fallback is "tell everybody" becomes noise,
    noise gets muted, and a muted channel is worse than none.
    """
    return ROUTES.get(event_type, (NOWHERE, INFO))


def ops_channel():
    """The global operations channel, or None if nobody configured one."""
    return (os.environ.get(OPS_CHANNEL_VAR) or "").strip() or None


def status_channel():
    """The team status channel, or None if nobody configured one."""
    return (os.environ.get(STATUS_CHANNEL_VAR) or "").strip() or None


def status_enabled():
    """The status feed is ON unless it is explicitly switched off.

    Default-on, unlike every per-workspace toggle here, because this channel
    carries no prospect and no client detail - the cost of an unwanted
    message in it is noise, and the cost of a missing one is a team that
    does not know a wave changed.
    """
    value = (os.environ.get(STATUS_ENABLED_VAR) or "").strip().lower()
    if value in ("off", "false", "no", "0"):
        return False
    return True


def workspace_channel(slug, rows=None):
    """This workspace's channel, or None. Never another workspace's.

    Reads one workspace's own policy and nothing else, so there is no code
    path here that could return a different client's channel - not a fallback
    that is disabled, an absence of one.
    """
    if not slug:
        return None
    policy = ws.policy(slug, rows)
    return (policy.get(WORKSPACE_CHANNEL_KEY) or "").strip() or None


def workspace_for_client(client, rows=None):
    """The workspace a client's records belong to, or None. Never a guess.

    A record carries a client, not a workspace, and the two are usually the
    same string - but `ws.ensure` allows them to differ, and one client can be
    served by more than one workspace. So this returns a slug only when
    exactly one workspace claims that client.

    Zero matches is None. **Two matches is also None**, and that is the point:
    picking either would route one client's positive reply into a room the
    other client's team reads. An alert with nowhere to go is a configuration
    problem somebody fixes; an alert in the wrong room is a disclosure nobody
    can take back.
    """
    if not client:
        return None
    matches = [w["slug"] for w in ws.workspaces(rows)
               if (w.get("client") or w.get("slug")) == client]
    return matches[0] if len(matches) == 1 else None


def workspace_allows(slug, event_type, rows=None):
    """Is this kind switched on for this workspace? Returns (bool, why)."""
    toggle = WORKSPACE_TOGGLES.get(event_type)
    if toggle is None:
        return True, "this kind has no per-workspace switch"
    key, default = toggle
    value = ws.policy(slug, rows).get(key)
    if value is None:
        return bool(default), (
            f"{key} is not configured; the default is "
            f"{'on' if default else 'off'}")
    on = str(value).strip().lower() in ("on", "true", "yes", "1")
    return on, f"{key} is {'on' if on else 'off'}"


def destination_for(event_type, workspace=None, rows=None):
    """The full routing decision, with the reason attached.

    Returns a dict rather than a channel string, because every caller needs
    the *why* as much as the where: the notification history exists to answer
    "why did this not go out", and a function that returned only a channel
    would make that unanswerable.
    """
    where, severity = route(event_type)
    if where == NOWHERE:
        return {"destination": NOWHERE, "severity": severity, "channel": None,
                "status": SUPPRESSED,
                "why": (f"{event_type} is not routed to Slack; it is recorded "
                        "and visible in the web app")}

    if where == STATUS:
        if not status_enabled():
            return {"destination": STATUS, "severity": severity,
                    "channel": None, "status": SUPPRESSED,
                    "why": f"the status feed is switched off ({STATUS_ENABLED_VAR})"}
        channel = status_channel()
        if not channel:
            return {"destination": STATUS, "severity": severity,
                    "channel": None, "status": UNCONFIGURED,
                    "why": (f"no team status channel is configured; set "
                            f"{STATUS_CHANNEL_VAR}")}
        return {"destination": STATUS, "severity": severity,
                "channel": channel, "status": PLANNED,
                "why": "routed to the team status channel"}

    if where == GLOBAL:
        channel = ops_channel()
        if not channel:
            return {"destination": GLOBAL, "severity": severity,
                    "channel": None, "status": UNCONFIGURED,
                    "why": (f"no global operations channel is configured; set "
                            f"{OPS_CHANNEL_VAR}")}
        return {"destination": GLOBAL, "severity": severity,
                "channel": channel, "status": PLANNED,
                "why": "routed to the global operations channel"}

    # WORKSPACE
    if not workspace:
        return {"destination": WORKSPACE, "severity": severity,
                "channel": None, "status": UNCONFIGURED,
                "why": ("this kind is workspace-bound and the event names no "
                        "workspace, so there is nowhere it may go")}
    allowed, why = workspace_allows(workspace, event_type, rows)
    if not allowed:
        return {"destination": WORKSPACE, "severity": severity,
                "channel": None, "status": SUPPRESSED, "why": why}
    channel = workspace_channel(workspace, rows)
    if not channel:
        return {"destination": WORKSPACE, "severity": severity,
                "channel": None, "status": UNCONFIGURED,
                "why": (f"{workspace} has no Slack channel configured. It is "
                        "recorded here and sent nowhere: another workspace's "
                        "channel is never a fallback")}
    return {"destination": WORKSPACE, "severity": severity, "channel": channel,
            "status": PLANNED, "why": f"routed to {workspace}'s own channel"}


# ------------------------------------------------------------- idempotency

def notification_id(event_type, workspace=None, /, **ids):
    """The same occurrence produces the same id, on any machine, any order.

    Built from the facts that make two notifications *the same one*. A poller
    replaying an EmailBison page hands us the same provider event id, which
    lands on the same notification, and the second write does nothing.

    The two parameters are positional-only and the identifiers are nested
    under their own key. Both are for the same reason: an identifier legibly
    named `workspace` or `type` is a completely reasonable thing for a caller
    to pass, and before this it either raised a TypeError or - worse - quietly
    overwrote the workspace in the material and made two different
    workspaces' notifications collide on one id.
    """
    material = {
        "type": event_type,
        "workspace": workspace,
        "ids": {k: v for k, v in sorted(ids.items())
                if v not in (None, "", [], {})},
    }
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"),
                      default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


# ---------------------------------------------------------------- payloads
#
# Two builders, and the difference between them is the whole client-safety
# story. `_workspace_payload` is an allowlist: it copies named fields and
# nothing else, so a field added to an event upstream cannot appear in a
# client's channel by accident. `_global_payload` may carry operational
# detail - but never a credential, which `_scrub` enforces on both.

WORKSPACE_SAFE_FIELDS = (
    "campaign_name", "company", "contact_name", "contact_role", "channel",
    "email_sender", "linkedin_sender", "reply_excerpt", "previous_touches",
    "paused", "report_name", "period", "milestone",
    # Account context. Under account-based outreach the client's next
    # question after "somebody replied" is always "and what about the other
    # people we are talking to there" - so the answer travels with the alert.
    #
    # Names and roles only, and only of people at the *same company*, whom
    # the recipient already knows. No sender internals, no provider account,
    # no counts of anybody else's campaigns.
    "account_contacts", "account_note",
    # What the policy did about the reply, and what a person
    # has to do next. Client-safe by construction: these are
    # words about the client's own account - "held", "review
    # this reply" - with no sender internals, no provider
    # account and nothing about another workspace.
    "contact_state", "account_state", "next_action",
)

# Never in any payload, either level. Checked rather than trusted.
FORBIDDEN = ("token", "secret", "password", "api_key", "apikey", "bearer",
             "authorization", "signing_secret", "webhook_url")


def _scrub(fields):
    """Refuse a field *named* like a credential. Checked before anything else.

    Two decisions here, and the second is the one worth explaining.

    **Raises rather than stripping.** A silently dropped secret means somebody
    wrote code that put one in a notification and nobody ever found out. The
    exception is how they find out.

    **Names are checked; values are not.** The obvious implementation greps
    the whole serialised payload, and it is wrong: `reply_excerpt` is text a
    *prospect* wrote, and a prospect who writes "we would need to sort out
    authorization first" would have their positive reply silently refused. A
    keyword scan over attacker-or-customer-controlled free text is a filter
    that fails on exactly the message you most wanted.

    So this catches the real programming error - a field called `api_key`
    being passed in - and the workspace allowlist below independently
    guarantees that only named fields reach a client at all. Two different
    guards, neither relying on the other.
    """
    for key in _keys(fields):
        lowered = str(key).lower()
        for word in FORBIDDEN:
            if word in lowered:
                raise NotifyError(
                    f"refusing to build a notification with a field called "
                    f"{key!r}: no credential belongs in a Slack payload")
    return fields


def _keys(value, depth=0):
    """Every key in a nested structure. Bounded, so a cycle cannot hang."""
    if depth > 6:
        return
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from _keys(inner, depth + 1)
    elif isinstance(value, (list, tuple)):
        for inner in value:
            yield from _keys(inner, depth + 1)


def _workspace_payload(fields):
    """An allowlist. Anything not named here does not reach a client.

    Scrubbed first, then filtered. The other order would mean a credential
    passed in for a workspace notification was quietly dropped by the
    allowlist and never reported - safe, and silent, which is half of what is
    wanted.
    """
    _scrub(fields)
    return {k: v for k, v in (fields or {}).items()
            if k in WORKSPACE_SAFE_FIELDS and v not in (None, "", [], {})}


def _global_payload(fields):
    """Operational detail. No allowlist here - the global channel is ours -
    but the same refusal on a credential-shaped field name."""
    _scrub(fields)
    return {k: v for k, v in (fields or {}).items()
            if v not in (None, "", [], {})}


#: Field names that carry a person or a client's private detail. Refused in
#: the status feed by NAME, before any value is looked at, because the
#: audience is the whole team and the cheapest guarantee is the one that does
#: not depend on what a caller happened to put in the string.
#: Field names that carry a PERSON. Matched as substrings, because
#: `contact_name`, `prospect_note` and `reply_excerpt_1` are all the same
#: mistake.
STATUS_FORBIDDEN_FIELDS = (
    "recipient", "prospect", "contact_name", "first_name", "last_name",
    "full_name", "person", "lead_email", "reply_excerpt", "subject", "body",
    "copy", "linkedin_url", "profile_url", "phone",
)

#: Names that ARE an address field rather than merely mentioning the channel.
#:
#: `email` and `address` were substring-matched here until 2026-09-21, and the
#: first dual-channel batch report could not be posted: `enrolled_email` is a
#: CHANNEL COUNT - 80 leads on the email side - and the guard read it as a
#: mailbox. Now that the operator wants both channels counted separately in
#: every report, half the legitimate field names in this product mention a
#: channel.
#:
#: So the name rule went back to what it can actually decide - a field that
#: holds an address - and the VALUE rule below does the real work. That was
#: always the stronger of the two: it catches an address embedded in an
#: otherwise innocent summary string, which no name check can.
STATUS_ADDRESS_FIELDS = ("email", "address", "email_address", "mailbox",
                         "to", "from")

_EMAIL_SHAPE = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")


def _status_payload(fields):
    """Counts and words about the machine. Never a person.

    OPERATOR, 2026-09-21: "Nothing in this channel contains prospect names,
    emails or client-internal data beyond counts."

    RAISES rather than stripping, on both the name check and the value check.
    A silently dropped prospect name means the caller believes it sent
    something it did not, and the next person to add a field learns nothing.
    The value check catches the case the name check cannot: an address
    embedded in an otherwise innocent summary string.
    """
    _scrub(fields)
    clean = {}
    for key, value in (fields or {}).items():
        if value in (None, "", [], {}):
            continue
        lowered = str(key).strip().lower()
        if any(bad in lowered for bad in STATUS_FORBIDDEN_FIELDS):
            raise NotifyError(
                f"{key!r} may not appear in the status feed: it names a "
                f"person or a prospect, and that channel carries counts only")
        if lowered in STATUS_ADDRESS_FIELDS:
            raise NotifyError(
                f"{key!r} is an address field, not a count. The status feed "
                f"carries counts and domains; a mailbox belongs nowhere near "
                f"a channel the whole team reads")
        if isinstance(value, str) and _EMAIL_SHAPE.search(value):
            raise NotifyError(
                f"{key!r} carries something shaped like an email address; "
                f"the status feed carries counts, not prospects")
        clean[key] = value
    return clean


# ------------------------------------------------------------------ planning

def plan(event_type, workspace=None, fields=None, ids=None, actions=(),
         rows=None, at=None):
    """Decide, build and store one notification. Posts nothing.

    Idempotent: a notification whose id already exists is returned unchanged
    rather than duplicated. Never raises for a routing or configuration
    problem - those are *statuses*, because "we could not send this" is
    information somebody needs rather than an error that should unwind a
    caller who has already paused a company.
    """
    ids = dict(ids or {})
    decision = destination_for(event_type, workspace, rows)
    identifier = notification_id(event_type, workspace, **ids)

    # THE OPERATOR'S TEST IDENTITY NEVER REACHES A CLIENT CHANNEL.
    #
    # 2026-09-23: a `positive_reply` for `/in/zbeslic` was routed to
    # C0BFUF4JRK9, Productive's own channel. It was suppressed by hand, and a
    # hand-edit is not a mechanism - the next reply from that profile would
    # have planned another one. Suppressed rather than dropped: the row is
    # still written, so an audit can see the decision was made deliberately.
    # See `src/testidentity.py` for why the match is on any binding.
    if testidentity.matches(ids):
        decision = dict(decision, destination=NOWHERE, channel=None,
                        status=SUPPRESSED, why=testidentity.WHY)

    # The duplicate check is inside the transaction below, and only there.
    # A second check up here would be free to write but impossible to test:
    # either one alone keeps the behaviour identical, so neither can be
    # removed by a mutation and caught by a test.
    if decision["destination"] == WORKSPACE:
        payload = _workspace_payload(fields)
    elif decision["destination"] == STATUS:
        payload = _status_payload(fields)
    else:
        payload = _global_payload(fields)

    row = {
        "id": identifier,
        "at": at or store.now(),
        "type": event_type,
        "workspace": workspace,
        "destination": decision["destination"],
        "severity": decision["severity"],
        "channel": decision["channel"],
        "status": decision["status"],
        "why": decision["why"],
        "ids": ids,
        "payload": payload,
        "actions": list(actions),
        "attempts": 0,
        "last_error": None,
    }
    with transaction() as current:
        if any(r.get("id") == identifier for r in current):
            return get(identifier)
        current.append(row)
    return row


def notify(event_type, workspace=None, fields=None, ids=None, actions=(),
           rows=None, at=None):
    """`plan`, but it cannot raise into the caller.

    The contract this function exists for: a notification layer must never be
    able to break the engine. Everything upstream of it - the pause, the
    suppression, the classification, the campaign state - has already
    happened and is already correct. If building a notification fails, the
    failure is recorded where it can be seen and the caller carries on.
    """
    try:
        return plan(event_type, workspace, fields, ids, actions, rows, at)
    except Exception as e:                                  # noqa: BLE001
        try:
            return _record_failure(event_type, workspace, ids, e)
        except Exception:                                   # noqa: BLE001
            return None


def _record_failure(event_type, workspace, ids, error):
    identifier = notification_id(event_type, workspace, **(ids or {}))
    row = {
        "id": identifier, "at": store.now(), "type": event_type,
        "workspace": workspace, "destination": NOWHERE, "severity": WARNING,
        "channel": None, "status": FAILED,
        "why": "the notification could not be built",
        "ids": dict(ids or {}), "payload": {}, "actions": [],
        "attempts": 0, "last_error": f"{type(error).__name__}: {error}"[:300],
    }
    with transaction() as current:
        if any(r.get("id") == identifier for r in current):
            return get(identifier)
        current.append(row)
    return row


# ------------------------------------------------------ the builders
#
# One function per notification worth building from real state. Each assembles
# its fields from the record and the roster rather than from anything a caller
# passed in, so a caller cannot describe an outreach history that did not
# happen by handing over a nicely formatted string.


def positive_reply(rec, contact_key, workspace, campaign=None, excerpt=None,
                   channel=None, provider=None, provider_event_id=None,
                   config=None, rows=None, effect=None):
    """The one message a client's channel is for.

    Everything in it is read from stored state:

      * the two humans come from the contact's stored sender assignment
      * the previous outreach comes from `touch.confirmed_touches`, which is
        the same gate that decides whether a message may *say* a touch
        happened. A planned step is not in this list, an approved one is not,
        and a built payload is not.

    So the "Previous outreach" block is the real timeline or it is absent.
    There is no path here that formats a step the engine has not confirmed,
    which is the difference between telling somebody their multichannel
    sequence converted and telling them a story about it.
    """
    from . import assignment, touch

    contact = next((c for c in rec.get("contacts") or []
                    if c.get("key") == contact_key), None)
    if contact is None:
        return None

    senders = assignment.describe(contact)
    email_sender = (senders.get("email") or {}).get("display_name")
    linkedin_sender = (senders.get("linkedin") or {}).get("display_name")

    confirmed = touch.confirmed_touches(rec, contact_key, config=config)
    previous = [
        f"Day {t['day']} - {t['channel']} - {_sender_name(senders, t)}"
        for t in confirmed]

    others, note = _account_context(rec, contact_key, workspace, rows)

    return notify(
        POSITIVE_REPLY, workspace,
        fields={
            "campaign_name": (campaign or {}).get("name"),
            "company": rec.get("company"),
            "contact_name": contact.get("name"),
            "contact_role": contact.get("title"),
            "channel": channel,
            "email_sender": email_sender,
            "linkedin_sender": linkedin_sender,
            "reply_excerpt": _excerpt(excerpt),
            "previous_touches": previous,
            "account_contacts": others or None,
            "account_note": note,
            "paused": ("company and contact paused from further outreach"
                       if rec.get("paused") else None),
            # What the policy did, and what a person has to do next. Read
            # from the effect the caller already applied - never
            # recomputed here, because an alert that derives its own
            # answer can disagree with the state it is announcing.
            "contact_state": _state_words(
                (effect or {}).get("contact")),
            "account_state": _state_words((effect or {}).get("account")),
            "next_action": _next_action(effect),
        },
        ids={"record_id": rec.get("id"), "contact_key": contact_key,
             "provider_event_id": provider_event_id,
             "campaign_id": (campaign or {}).get("campaign_id")},
        actions=[
            {"action_id": "open_reply", "text": "Open Reply"},
            {"action_id": "open_contact", "text": "Open Contact"},
            {"action_id": "open_campaign", "text": "Open Campaign"},
        ],
        rows=rows)



def _state_words(action):
    """One policy action, in words a client would use.

    `None` when the policy did not say - absent rather than guessed, so a
    reader cannot mistake "we did not record this" for "nothing
    happened".
    """
    from . import accountpolicy

    if not action:
        return None
    return accountpolicy.ACTION_LABEL.get(action, action)


def _next_action(effect):
    """What a person has to do, or None when nothing is required.

    Only three answers, and each is a thing somebody does rather than a
    status: look at it, decide about the account, or nothing. A "next
    action" that restates the state is noise on an alert somebody reads
    in a hurry.
    """
    from . import accountpolicy

    if not effect:
        return None
    if effect.get("review"):
        return "Review this reply before anything else goes out"
    if effect.get("account") == accountpolicy.SUPPRESS:
        return "The company is suppressed: nothing further will be sent"
    if effect.get("account") == accountpolicy.HOLD:
        return "Other people at this company are on hold pending review"
    return None


def _account_context(rec, contact_key, workspace, rows=None):
    """Who else at this company we are talking to, and what a reply does.

    Client-safe by construction: names and roles of people at the recipient's
    own company, which they already know, plus whether the reply paused
    anybody. Nothing about senders, providers, credits or other clients.

    Returns (lines, note). Both may be empty, and an empty one is omitted
    rather than rendered as "none" - a client channel does not need to be
    told there is nothing to tell.
    """
    from . import account, accountpolicy

    try:
        graph = account.graph(rec, workspace, rows)
    except Exception:                                       # noqa: BLE001
        return [], None

    lines = []
    for entry in graph["contacts"]:
        if entry["key"] == contact_key:
            continue
        if not entry["confirmed_touches"] and not entry["replies"]:
            continue                    # nobody has actually contacted them
        state = ("replied" if entry["replies"] else "in sequence")
        lines.append(f"{entry['name']} - {entry['title'] or 'role unknown'}"
                     f" - {state}")

    note = None
    if lines:
        decision = accountpolicy.resolve(accountpolicy.POSITIVE)
        if decision["action"] in (accountpolicy.HOLD, accountpolicy.REVIEW):
            note = ("Outreach to the others above is held while this "
                    "conversation is live.")
        elif decision["action"] == accountpolicy.STOP:
            note = "Outreach to the others above has stopped."
    return lines, note


def _sender_name(senders, step):
    """Who made this touch, by name where the touch recorded one.

    Falls back to the channel's currently assigned human only when the touch
    carries no sender at all - and says so, rather than presenting the current
    assignment as though it were history.
    """
    if step.get("sender_id"):
        for channel in ("email", "linkedin"):
            row = senders.get(channel) or {}
            if row.get("sender_id") == step["sender_id"]:
                return row.get("display_name") or step["sender_id"]
        return step["sender_id"]
    return "sender not recorded"


# How much of a prospect's reply travels into Slack. Enough to judge whether
# it is worth acting on, and not the whole thread: a Slack channel is a poor
# place to keep somebody's correspondence, and a long paste is how a client
# channel becomes an archive nobody meant to create.
EXCERPT_LIMIT = 300


def _excerpt(text):
    text = " ".join(str(text or "").split())
    if len(text) <= EXCERPT_LIMIT:
        return text or None
    return text[:EXCERPT_LIMIT].rstrip() + "..."


def campaign_approval_required(campaign, summary, workspace, review_url=None,
                               rows=None):
    """"This campaign is ready. May it go?" - with the numbers behind it.

    Global channel only. The context here is operational - QA verdicts, held
    counts, credit exposure - and none of it belongs in a client's room.

    The fingerprint travels because that is what makes an approval mean
    "approve *this*". A button that posts a stale one is refused by
    `orchestrator.decide` exactly as any other stale approval is; nothing
    about arriving from Slack makes it trusted.
    """
    return notify(
        CAMPAIGN_APPROVAL_REQUIRED, workspace,
        fields={
            "campaign": campaign.get("name") or campaign.get("campaign_id"),
            "segment": campaign.get("segment_key"),
            "personas": ", ".join(campaign.get("personas") or []) or None,
            "geographies": ", ".join(campaign.get("geos") or []) or None,
            "companies": summary.get("companies"),
            "contacts": summary.get("contacts"),
            "email_eligible": summary.get("email_eligible"),
            "linkedin_eligible": summary.get("linkedin_eligible"),
            "held": summary.get("held"),
            "qa": summary.get("qa"),
            "double_verified": summary.get("double_verified"),
            "mx_summary": summary.get("mx_summary"),
            "sender_strategy": summary.get("sender_strategy"),
            "estimated_credits": summary.get("estimated_credits"),
            "fingerprint": campaign.get("fingerprint"),
            "review_url": review_url,
        },
        ids={"campaign_id": campaign.get("campaign_id"),
             "fingerprint": campaign.get("fingerprint")},
        actions=[
            {"action_id": "approve_campaign", "text": "Approve",
             "style": "primary"},
            {"action_id": "reject_campaign", "text": "Reject",
             "style": "danger"},
            {"action_id": "hold_campaign", "text": "Hold"},
            {"action_id": "open_review", "text": "Open in Web App"},
        ],
        rows=rows)


def operational(event_type, workspace=None, rows=None, **fields):
    """Anything else that belongs in the Resonate operations feed.

    A thin wrapper, but a deliberate one: it keeps every operational
    notification going through the same routing and the same scrub, so a new
    kind of warning cannot quietly acquire its own path to a channel.
    """
    where, _ = route(event_type)
    if where != GLOBAL:
        raise NotifyError(
            f"{event_type} is not a global operations event; it routes to "
            f"{where}")
    ids = fields.pop("ids", None) or {k: v for k, v in fields.items()
                                      if k.endswith("_id")}
    return notify(event_type, workspace, fields=fields, ids=ids, rows=rows)


# ------------------------------------------------------------------ reading

def get(identifier, rows=None):
    for row in (load() if rows is None else rows):
        if row.get("id") == identifier:
            return row
    return None


def history(workspace=None, event_type=None, status=None, limit=200,
            rows=None):
    """The notification log, newest first.

    `workspace=None` is every workspace and is only ever reached from the
    admin console; the web layer passes a slug for anything workspace-scoped.
    """
    found = load() if rows is None else rows
    if workspace:
        found = [r for r in found if r.get("workspace") == workspace]
    if event_type:
        found = [r for r in found if r.get("type") == event_type]
    if status:
        found = [r for r in found if r.get("status") == status]
    return sorted(found, key=lambda r: str(r.get("at")), reverse=True)[:limit]


def summarise(workspace=None, rows=None):
    found = history(workspace, limit=100000, rows=rows)
    by_status, by_destination, by_severity = {}, {}, {}
    for row in found:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        by_destination[row["destination"]] = by_destination.get(
            row["destination"], 0) + 1
        by_severity[row["severity"]] = by_severity.get(row["severity"], 0) + 1
    return {
        "total": len(found),
        "by_status": dict(sorted(by_status.items())),
        "by_destination": dict(sorted(by_destination.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "last": found[0] if found else None,
    }


def last_for(workspace, event_type=POSITIVE_REPLY, rows=None):
    found = history(workspace, event_type, limit=1, rows=rows)
    return found[0] if found else None


# ----------------------------------------------------------------- delivery

def deliver(identifier, config=None):
    """Attempt one notification. Refuses in this build, and records that.

    `slack.post` raises `SlackPostingNotEnabled` unless `SLACK_LIVE` is set,
    and it is not set here - so this function's job in this build is to prove
    the failure path: the status moves, the attempt is counted, the error is
    kept, and nothing about the record, the pause or the campaign changes.
    """
    row = get(identifier)
    if row is None:
        raise NotifyError(f"no notification {identifier!r}")
    if row["status"] in (SENT, SUPPRESSED, UNCONFIGURED):
        return row
    if not row.get("channel"):
        return _update(identifier, status=UNCONFIGURED,
                       why="no channel to post to")

    payload = {"kind": row["type"], "channel": row["channel"],
               "text": render(row), "blocks": [], "actions": row["actions"],
               "metadata": dict(row["ids"], notification_id=row["id"])}
    try:
        slack.post(payload, config)
    except Exception as e:                                  # noqa: BLE001
        return _update(identifier, status=FAILED,
                       attempts=(row.get("attempts") or 0) + 1,
                       last_error=f"{type(e).__name__}: {e}"[:300],
                       why="the transport refused; this stays retryable")
    return _update(identifier, status=SENT,
                   attempts=(row.get("attempts") or 0) + 1,
                   why="posted")


def retry(identifier, config=None):
    """Try a failed notification again. Idempotent on the same id."""
    row = get(identifier)
    if row is None:
        raise NotifyError(f"no notification {identifier!r}")
    if row["status"] == SENT:
        return row
    _update(identifier, status=RETRYING)
    return deliver(identifier, config)


def _update(identifier, **changes):
    updated = None
    with transaction() as current:
        for i, row in enumerate(current):
            if row.get("id") == identifier:
                updated = {**row, **changes}
                current[i] = updated
                break
    return updated


def render(row):
    """The message text. Plain, and built only from the stored payload.

    Never reads anything back from Slack and never interpolates a provider's
    text into an instruction - the reply excerpt is quoted as data.
    """
    lines = [f"{_icon(row)} {row['type'].replace('_', ' ').upper()}"]
    if row.get("workspace"):
        lines.append(f"Workspace: {row['workspace']}")
    for key, value in (row.get("payload") or {}).items():
        # Any list renders as an indented block, not as a Python repr.
        # Special-casing one field meant the next list field added - account
        # context - printed as ['Sarah Jones - ...'] in a client's channel.
        if isinstance(value, list):
            lines.append(_LIST_HEADING.get(key,
                                           key.replace("_", " ").capitalize())
                         + ":")
            lines += [f"  {item}" for item in value]
            continue
        if key == "reply_excerpt":
            lines.append(f"Reply: \"{value}\"")
            continue
        lines.append(f"{key.replace('_', ' ').capitalize()}: {value}")
    return "\n".join(lines)


# What a list field is called when it is printed. Anything not here falls
# back to its own key, humanised.
_LIST_HEADING = {
    "previous_touches": "Previous outreach",
    "account_contacts": "Others at this company",
}


def _icon(row):
    if row.get("type") == POSITIVE_REPLY:
        return "[POSITIVE REPLY]"
    return {INFO: "[INFO]", ACTION_REQUIRED: "[ACTION REQUIRED]",
            WARNING: "[WARNING]", CRITICAL: "[CRITICAL]"}.get(
                row.get("severity"), "[INFO]")


def status_for(slug, rows=None):
    """What the workspace dashboard shows about Slack."""
    channel = workspace_channel(slug, rows)
    positive, why = workspace_allows(slug, POSITIVE_REPLY, rows)
    last = last_for(slug)
    return {
        "workspace": slug,
        "channel": channel,
        "configured": bool(channel),
        "positive_replies": positive,
        "positive_replies_why": why,
        "last_alert": last,
        "ops_channel": ops_channel(),
        "live": slack.live(),
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.notify", description=__doc__)
    p.add_argument("--workspace")
    p.add_argument("--type")
    p.add_argument("--status")
    p.add_argument("--list", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    rows = history(args.workspace, args.type, args.status)
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return 0
    print(f"global operations channel: {ops_channel() or 'NOT CONFIGURED'}")
    print(f"slack posting: {'LIVE' if slack.live() else 'disabled'}\n")
    for row in rows:
        print(f"  {row['at']}  {row['status']:<13} {row['destination']:<10} "
              f"{row.get('channel') or '-':<32} {row['type']}")
        if row["status"] not in (PLANNED, SENT):
            print(f"      {row['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
