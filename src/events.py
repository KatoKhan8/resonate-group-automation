#!/usr/bin/env python3
"""The event model, and the neutral interface external events arrive through.

Two jobs, one append-only log per record:

  1. the pipeline records what it did, in stable names, so reporting is derived
     rather than counted by hand
  2. an outside system (an EmailBison webhook, a HeyReach poll, a human pasting
     a reply into a CLI) hands us an event in one neutral shape, and it is
     applied once, whatever happens to arrive twice

Nothing here calls a provider. The adapters map a payload that a provider would
send into the neutral shape, so wiring a real webhook later is a transport
change and not a behaviour change.

  python -m src.events list --id meridian
  python -m src.events ingest --file work/webhook.json
"""
import argparse
import hashlib
import json

from . import store

# ------------------------------------------------------------ event names
#
# Stable. Renaming one breaks longitudinal reporting, so these are the
# vocabulary and nothing invents a variant.

BATCH_INGESTED = "batch_ingested"
RECORD_SUPPRESSED = "record_suppressed"
RECORD_DROPPED = "record_dropped"
ENRICHMENT_STARTED = "enrichment_started"
ENRICHMENT_COMPLETED = "enrichment_completed"
CONTACT_FOUND = "contact_found"
VERIFICATION_RESULT = "verification_result"
# A provider answer restored from this record's own event log rather than
# bought again. Deliberately not VERIFICATION_RESULT: nothing was asked of
# any provider, and a repair that reads as a fresh verification is how a
# reconstruction becomes indistinguishable from evidence.
EVIDENCE_RECONSTRUCTED = "evidence_reconstructed"
PERSONA_SELECTED = "persona_selected"
DRAFT_GENERATED = "draft_generated"
LINT_FAILED = "lint_failed"
DRAFT_APPROVED = "draft_approved"
CADENCE_PREPARED = "cadence_prepared"
PUSH_PREPARED = "push_prepared"
PUSH_MARKED = "push_marked"
EMAIL_DELIVERED = "email_delivered"
EMAIL_BOUNCED = "email_bounced"
REPLY_RECEIVED = "reply_received"
LINKEDIN_CONNECTED = "linkedin_connected"
COMPANY_PAUSED = "company_paused"

# What a reply did to the people it reached. One event per state transition,
# because "the company was paused" and "this person was suppressed" are
# different facts and a report that cannot tell them apart cannot answer
# "why did we stop writing to Sarah".
#
# These are recorded by `accountpolicy.apply_reply`, which is the only place
# that moves this state. A transition with no event here is a transition
# nobody can audit.
CONTACT_HELD = "contact_held"
CONTACT_STOPPED = "contact_stopped"
CONTACT_SUPPRESSED = "contact_suppressed"
ACCOUNT_SUPPRESSED = "account_suppressed"
REVIEW_REQUIRED = "review_required"
REFERRED_CONTACT_ACTIVATED = "referred_contact_activated"

REPLY_EFFECT_EVENTS = (COMPANY_PAUSED, CONTACT_HELD, CONTACT_STOPPED,
                       CONTACT_SUPPRESSED, ACCOUNT_SUPPRESSED,
                       REVIEW_REQUIRED, REFERRED_CONTACT_ACTIVATED)

# Provider, cost, verification and research events.
# Campaign lifecycle. A campaign is approved, invalidated, launched, paused
# and finished; every one of those is a thing someone will later ask about.
CAMPAIGN_CREATED = "campaign_created"
CAMPAIGN_READY_FOR_REVIEW = "campaign_ready_for_review"
CAMPAIGN_APPROVAL_REQUESTED = "campaign_approval_requested"
CAMPAIGN_APPROVED = "campaign_approved"
CAMPAIGN_REJECTED = "campaign_rejected"
CAMPAIGN_APPROVAL_INVALIDATED = "campaign_approval_invalidated"
CAMPAIGN_LAUNCH_READY = "campaign_launch_ready"
CAMPAIGN_PAUSED = "campaign_paused"
CAMPAIGN_RESUMED = "campaign_resumed"
DUPLICATE_COPY_DETECTED = "duplicate_copy_detected"
CAMPAIGN_FROZEN = "campaign_frozen"
CAMPAIGN_UNFROZEN = "campaign_unfrozen"
CAMPAIGN_COMPLETED = "campaign_completed"

CAMPAIGN_EVENTS = (CAMPAIGN_CREATED, CAMPAIGN_READY_FOR_REVIEW,
                   CAMPAIGN_APPROVAL_REQUESTED, CAMPAIGN_APPROVED,
                   CAMPAIGN_REJECTED, CAMPAIGN_APPROVAL_INVALIDATED,
                   CAMPAIGN_LAUNCH_READY, CAMPAIGN_PAUSED, CAMPAIGN_RESUMED,
                   CAMPAIGN_FROZEN, CAMPAIGN_UNFROZEN,
                   DUPLICATE_COPY_DETECTED,
                   CAMPAIGN_COMPLETED)

# What a reply turned out to mean, and what we did about it.
REPLY_CLASSIFIED = "reply_classified"
POSITIVE_REPLY_DETECTED = "positive_reply_detected"
# What an out-of-office said, kept apart from what it was classified as.
# The category cannot carry "a person wrote this" or "they said the 8th",
# and both are needed before anything can be scheduled for their return.
OUT_OF_OFFICE_RECORDED = "out_of_office_recorded"
# The same shape for "try me in November": a date somebody gave for when to
# come back, kept apart from the category so a follow-up can be judged
# against it later.
NOT_NOW_RECORDED = "not_now_recorded"
MEETING_MARKED = "meeting_marked"
OWNER_ASSIGNED = "owner_assigned"

# One person telling us to talk to another. Recorded, never inferred.
#
# The edge exists because a reply was classified as a referral *and* somebody
# named the target - a classifier reading "Sarah handles this" out of free
# text and writing an edge would manufacture an introduction that never
# happened, and the next message would open by claiming it did. The target
# contact key travels on `referred_to`, and `src/account.py` refuses an edge
# missing either end.
REFERRAL_RECORDED = "referral_recorded"

# The step before an edge. A reply pointed at somebody, and what could be
# proved about who that is - which is often nothing more than a name. Kept
# apart from REFERRAL_RECORDED on purpose: that edge is an introduction
# between two contacts we hold, and this is a mention that may name nobody
# we know.
REFERRAL_MENTIONED = "referral_mentioned"

# Notification is planned, then sent or not. Three events, because "we meant
# to tell someone" and "someone was told" are different facts.
SLACK_NOTIFICATION_PLANNED = "slack_notification_planned"
SLACK_NOTIFICATION_SENT = "slack_notification_sent"
SLACK_NOTIFICATION_FAILED = "slack_notification_failed"

SLACK_EVENTS = (SLACK_NOTIFICATION_PLANNED, SLACK_NOTIFICATION_SENT,
                SLACK_NOTIFICATION_FAILED)

# MX, the cheap gate in front of paid verification. Domain-level, so these
# fire once per email domain rather than once per contact.
MX_LOOKUP_STARTED = "mx_lookup_started"
MX_LOOKUP_COMPLETED = "mx_lookup_completed"
MX_LOOKUP_FAILED = "mx_lookup_failed"
MX_SECURITY_PROVIDER_DETECTED = "mx_security_provider_detected"
EMAIL_CHANNEL_BLOCKED_MX = "email_channel_blocked_mx"

MX_EVENTS = (MX_LOOKUP_STARTED, MX_LOOKUP_COMPLETED, MX_LOOKUP_FAILED,
             MX_SECURITY_PROVIDER_DETECTED, EMAIL_CHANNEL_BLOCKED_MX)

SENDER_ASSIGNED = "sender_assigned"
EXTERNAL_CAMPAIGN_MAPPED = "external_campaign_mapped"
CAMPAIGN_MAPPING_VALIDATED = "campaign_mapping_validated"
CAMPAIGN_MAPPING_FAILED = "campaign_mapping_failed"

# Transport-level facts that belong to no record. A rejected webhook names a
# record it has no right to write to, so these are counted in
# src/observability.py rather than appended to anything.
WEBHOOK_RECEIVED = "webhook_received"
WEBHOOK_REJECTED = "webhook_rejected"
EVENT_INGESTED = "event_ingested"
EVENT_DUPLICATE = "event_duplicate"
EVENT_UNKNOWN = "event_unknown"
EVENT_RETRY_SCHEDULED = "event_retry_scheduled"
SLACK_POST_PLANNED = "slack_post_planned"
SLACK_POST_SENT = "slack_post_sent"
SLACK_POST_FAILED = "slack_post_failed"

OBSERVED = (WEBHOOK_RECEIVED, WEBHOOK_REJECTED, EVENT_INGESTED,
            EVENT_DUPLICATE, EVENT_UNKNOWN, EVENT_RETRY_SCHEDULED,
            SLACK_POST_PLANNED, SLACK_POST_SENT, SLACK_POST_FAILED,
            CAMPAIGN_MAPPING_VALIDATED, CAMPAIGN_MAPPING_FAILED)

PROVIDER_CALL_PLANNED = "provider_call_planned"
PROVIDER_CALL_STARTED = "provider_call_started"
PROVIDER_CALL_COMPLETED = "provider_call_completed"
PROVIDER_CALL_FAILED = "provider_call_failed"
PROVIDER_CALL_SKIPPED = "provider_call_skipped"
PROVIDER_CREDIT_ESTIMATED = "provider_credit_estimated"
PROVIDER_CREDIT_SPENT = "provider_credit_spent"

VERIFICATION_STARTED = "verification_started"
VERIFICATION_DISAGREEMENT = "verification_disagreement"

SCRAPE_PLANNED = "scrape_planned"
SCRAPE_STARTED = "scrape_started"
SCRAPE_COMPLETED = "scrape_completed"
SCRAPE_FAILED = "scrape_failed"

EVIDENCE_ADDED = "evidence_added"

# Retrieved, and refused before it could influence anything. Recorded because
# the alternative is evidence that was paid for and then silently vanished,
# which is indistinguishable from a scrape that returned nothing.
EVIDENCE_REFUSED = "evidence_refused"

PROVIDER_EVENTS = (PROVIDER_CALL_PLANNED, PROVIDER_CALL_STARTED,
                   PROVIDER_CALL_COMPLETED, PROVIDER_CALL_FAILED,
                   PROVIDER_CALL_SKIPPED, PROVIDER_CREDIT_ESTIMATED,
                   PROVIDER_CREDIT_SPENT)
RESEARCH_EVENTS = (SCRAPE_PLANNED, SCRAPE_STARTED, SCRAPE_COMPLETED,
                   SCRAPE_FAILED, EVIDENCE_ADDED, EVIDENCE_REFUSED)

INTERNAL = (CAMPAIGN_EVENTS + SLACK_EVENTS + MX_EVENTS +
            (REPLY_CLASSIFIED, POSITIVE_REPLY_DETECTED, MEETING_MARKED,
             OUT_OF_OFFICE_RECORDED, NOT_NOW_RECORDED,
             REFERRAL_RECORDED, REFERRAL_MENTIONED,
             OWNER_ASSIGNED, SENDER_ASSIGNED, EXTERNAL_CAMPAIGN_MAPPED,
             CAMPAIGN_MAPPING_VALIDATED, CAMPAIGN_MAPPING_FAILED) +
            (VERIFICATION_STARTED, VERIFICATION_DISAGREEMENT,
             EVIDENCE_RECONSTRUCTED,
             BATCH_INGESTED, RECORD_SUPPRESSED, RECORD_DROPPED,
             ENRICHMENT_STARTED, ENRICHMENT_COMPLETED, CONTACT_FOUND,
             VERIFICATION_RESULT, PERSONA_SELECTED, DRAFT_GENERATED,
             LINT_FAILED, DRAFT_APPROVED, CADENCE_PREPARED, PUSH_PREPARED,
             PUSH_MARKED) + REPLY_EFFECT_EVENTS + PROVIDER_EVENTS
            + RESEARCH_EVENTS)

# Events that can only come from outside this system.
EXTERNAL = (EMAIL_DELIVERED, EMAIL_BOUNCED, REPLY_RECEIVED, LINKEDIN_CONNECTED)

# The cadence vocabulary, kept because phase 7 already acts on it. Each maps
# onto one of the names above so reporting sees a single stream.
CADENCE_TYPES = ("email_reply", "linkedin_reply", "connection_accepted")

REPLY_TYPES = ("email_reply", "linkedin_reply")

CADENCE_TO_EVENT = {
    "email_reply": REPLY_RECEIVED,
    "linkedin_reply": REPLY_RECEIVED,
    "connection_accepted": LINKEDIN_CONNECTED,
}

KNOWN = set(INTERNAL) | set(EXTERNAL) | set(CADENCE_TYPES)

EMAIL = "email"
LINKEDIN = "linkedin"


class UnknownEvent(RuntimeError):
    """An event this system has no vocabulary for. Never guessed at."""


# What makes two events the same event.
#
# `contact` rather than `contact_key`: that is the key `record()` actually
# stores, and hashing the absent name meant the contact never entered the id
# at all - so two touches to two different people, on the same channel in the
# same second, collided and the second was silently dropped as a duplicate.
# In account-based outreach, where several decision makers are touched in one
# run, that lost real touches and left the account graph quietly incomplete.
#
# `sender_id`, `day` and `step` are here because they are what distinguishes
# two touches to the *same* person: Anna's email and Mark's email to John are
# two facts, and an id that cannot tell them apart keeps only the first.
IDENTITY_FIELDS = ("provider", "type", "record_id", "contact", "channel",
                   "at", "provider_event_id", "sender_id", "day", "step")


def event_id(event):
    """A stable id for an event that arrives without one."""
    material = "|".join(str(event.get(k, "")) for k in IDENTITY_FIELDS)
    return "ev_" + hashlib.sha1(material.encode("utf-8")).hexdigest()[:16]


def record(rec, kind, contact_key=None, channel=None, at=None,
           provider=None, provider_event_id=None, **fields):
    """Append one event to a record. Returns the stored entry.

    Idempotent on `provider_event_id`: the same webhook delivered twice changes
    state once.
    """
    if kind not in KNOWN:
        raise UnknownEvent(f"unknown event type: {kind}")

    entry = {"type": kind, "contact": contact_key, "at": at or store.now()}
    if channel:
        entry["channel"] = channel
    if provider:
        entry["provider"] = provider
    if provider_event_id:
        entry["provider_event_id"] = provider_event_id
    entry.update({k: v for k, v in fields.items() if v not in (None, "", [], {})})
    entry["id"] = entry.get("id") or event_id({**entry, "record_id": rec.get("id")})

    existing = rec.setdefault("events", [])
    if provider_event_id and any(e.get("provider_event_id") == provider_event_id
                                 for e in existing):
        return None                      # already applied, do nothing twice
    if any(e.get("id") == entry["id"] for e in existing):
        return None
    existing.append(entry)
    return entry


def of(rec, *kinds):
    kinds = set(kinds) if kinds else None
    return [e for e in rec.get("events") or []
            if kinds is None or e.get("type") in kinds]


def is_reply(entry):
    return (entry.get("type") == REPLY_RECEIVED
            or entry.get("type") in REPLY_TYPES)


def is_acceptance(entry):
    return entry.get("type") in (LINKEDIN_CONNECTED, "connection_accepted")


# --------------------------------------------------------- the neutral shape

NEUTRAL_FIELDS = ("client", "record_id", "contact_key", "channel", "type",
                  "provider", "provider_event_id", "at")


def neutral(client=None, record_id=None, contact_key=None, channel=None,
            type=None, provider=None, provider_event_id=None, at=None, **extra):
    """The one shape every source is translated into before it is applied."""
    event = {"client": client, "record_id": record_id, "contact_key": contact_key,
             "channel": channel, "type": type, "provider": provider,
             "provider_event_id": provider_event_id, "at": at}
    event.update(extra)
    return event


def match_record(recs, event):
    """Find the record an event belongs to. Never guesses."""
    rid = event.get("record_id")
    if rid:
        for rec in recs:
            if rec.get("id") == rid:
                return rec
    address = (event.get("email") or "").lower()
    if address:
        # Ambiguity refused, exactly as the LinkedIn branch below refuses it.
        #
        # This returned the first record whose contact carried the address,
        # and `poller.run` passes the whole queue, so "first" means "whichever
        # tenant this event happened to reach first". Two clients working the
        # same decision maker is not exotic - it is the normal case for an
        # agency - and the tenancy check further down cannot save it, because
        # that check is skipped when the event carries no client, which is the
        # ordinary shape of a LinkedIn reply. Applied to the wrong record it
        # pauses the wrong company and writes the wrong log.
        found = [rec for rec in recs
                 for contact in (rec.get("contacts") or [])
                 if (contact.get("email") or "").lower() == address]
        distinct = {rec.get("id") for rec in found}
        if len(distinct) == 1:
            return found[0]
        if len(distinct) > 1:
            return None                       # shared address: never guessed
    # The LinkedIn URL is the primary correlation key for HeyReach, because
    # nothing else round-trips: customFields come back empty from both the
    # inbox and /lead/GetLead. So it is compared canonically - one profile has
    # many spellings - and never fuzzily. Two contacts sharing a URL is bad
    # data, and the event is left unmatched rather than attached to a guess.
    from . import linkedin
    profile = linkedin.canonical(event.get("linkedin"))
    if profile:
        found = []
        for rec in recs:
            for contact in rec.get("contacts") or []:
                if linkedin.canonical(contact.get("linkedin")) == profile:
                    found.append((rec, contact))
        if len(found) == 1:
            return found[0][0]
        if len(found) > 1:
            distinct = {(r.get("id"), c.get("key")) for r, c in found}
            if len(distinct) == 1:
                return found[0][0]
            return None                  # ambiguous: hold, never guess
    return None


def match_contact(rec, event):
    key = event.get("contact_key")
    if key:
        for contact in rec.get("contacts") or []:
            if contact.get("key") == key:
                return contact.get("key")
    from . import linkedin
    address = (event.get("email") or "").lower()
    profile = linkedin.canonical(event.get("linkedin"))
    matches = []
    for contact in rec.get("contacts") or []:
        if address and (contact.get("email") or "").lower() == address:
            return contact.get("key")
        if profile and linkedin.canonical(contact.get("linkedin")) == profile:
            matches.append(contact.get("key"))
    # One match is an answer. Two is bad data, and picking one would attribute
    # somebody's reply to the wrong person.
    return matches[0] if len(set(matches)) == 1 else None


def apply(recs, event):
    """Apply one neutral event. Returns what happened, and why if it did not.

    An event for a record or a contact we do not recognise is reported as
    unmatched and changed nothing: a guess here would pause the wrong company.
    """
    kind = event.get("type")
    if kind not in KNOWN:
        return {"status": "unknown", "why": f"unknown event type: {kind}",
                "event": event}

    rec = match_record(recs, event)
    if rec is None:
        return {"status": "unmatched", "why": "no record for this event",
                "event": event}
    if event.get("client") and rec.get("client") != event["client"]:
        return {"status": "unmatched", "why": "client does not match the record",
                "event": event}

    contact_key = match_contact(rec, event)
    if contact_key is None and event.get("contact_key"):
        return {"status": "unmatched", "why": "no contact for this event",
                "event": event, "record_id": rec["id"]}

    # THE ESTATE THE EVENT WAS READ FROM TRAVELS WITH IT.
    #
    # Nothing recorded it. An EmailBison credential's workspace is chosen in the
    # vendor's UI and has moved mid-session - it answered for four different
    # estates in three days - so a reply polled while bound to the wrong
    # workspace was applied to this client's record with no trace of where it
    # came from: the account paused, a positive-reply alert fired, and the reply
    # was counted in client-facing reporting. The event log is append-only, so
    # the false claim was not retractable and, worse, not even identifiable
    # afterwards.
    #
    # `provider_workspace` does not by itself refuse anything - the refusal
    # belongs at the poll, where `expect` now defaults to the deployment's pin.
    # What it does is make the question answerable a day later: which estate
    # said this. An event that cannot name its source cannot be audited, and an
    # unauditable event about a real person is the one thing an append-only log
    # must not contain.
    entry = record(rec, kind, contact_key=contact_key,
                   channel=event.get("channel"), at=event.get("at"),
                   provider=event.get("provider"),
                   provider_event_id=event.get("provider_event_id"),
                   provider_workspace=event.get("provider_workspace"))
    if entry is None:
        return {"status": "duplicate", "record_id": rec["id"],
                "why": "this provider event was already applied"}

    store.log(rec, "event", f"{kind} from {event.get('provider') or 'unknown'}",
              contact=contact_key, channel=event.get("channel"))

    effect = None
    if is_reply(entry):
        effect = apply_reply_policy(rec, entry, contact_key)
    return {"status": "applied", "record_id": rec["id"], "contact": contact_key,
            "event": entry, "paused": bool(rec.get("paused")),
            "effect": effect}


def apply_reply_policy(rec, entry, contact_key=None):
    """Hand a reply to the policy, which is the only thing that moves state.

    A reply arriving from a provider is unclassified - the classifier has
    not run yet - so the outcome here is UNKNOWN, which the policy resolves
    to a review at account scope: the whole company holds, exactly as it
    always has. `replies.apply` comes back through the policy once the
    classification exists, and only then can the effect narrow.

    "Almost always", as this used to read, was the bug. The outcome was
    left to `apply_reply`'s fallback, which reads the contact's last
    recorded classification - so only a contact's *first* reply was
    uncertain and every later one inherited an answer given to a different
    message.

    Imported late. `accountpolicy` reads the event log to classify an
    outcome, so it depends on this module; a module-level import here would
    close the circle.
    """
    from . import accountpolicy

    # UNKNOWN, said rather than derived. `apply_reply` falls back to
    # `classify_outcome`, which returns whatever this contact's *last*
    # reply was classified as - so a second reply arriving here inherited
    # the first one's verdict instead of being uncertain. "Not
    # interested" followed by "remove our whole company" re-applied
    # `negative`: nothing held, no review opened, and the escalation was
    # swallowed until something classified it.
    #
    # This reply is unclassified. That is a fact about this reply, not a
    # question to answer from history.
    return accountpolicy.apply_reply(
        rec, contact_key, accountpolicy.UNKNOWN, config=None,
        at=entry.get("at"), channel=entry.get("channel"),
        reason=entry.get("type"), workspace=rec.get("client"))


# `pause_company` lived here and is deleted rather than left. It was a second
# implementation of one canonical transition - `accountpolicy._hold_account`
# writes `rec["paused"]` itself and is the live path - and its docstring
# asserted a caller it did not have, which is what made it a trap rather than
# merely dead: the two records differ. `_hold_account` writes `outcome`
# alongside `reason` on purpose, because an audit that collapses "what arrived"
# into "what we made of it" cannot answer "we paused on a reply, but which
# reading of it". A caller who trusted the docstring would have produced a
# pause missing that field.
#
# Recorded as open in FINAL-SYSTEM-INTEGRITY-AUDIT.md and RELEASE-CANDIDATE.md,
# where it was left alone on the grounds that deleting it was not that audit's
# change to make.


def ingest(events, recs=None):
    """Apply a list of neutral events. Offline, idempotent, auditable."""
    own = recs is None
    recs = store.load() if own else recs
    results = [apply(recs, event) for event in events]
    if own and any(r["status"] == "applied" for r in results):
        store.save(recs)
    return results


# ----------------------------------------------------------- the adapters
#
# What a provider would send, mapped into the neutral shape. No call is made
# to build these: they take a payload and return events.

# The mappings themselves live in src/adapters.py, written against responses
# read from the live APIs. They are imported lazily because that module needs
# this one, and a provider's field names have no business being in the file
# that defines what an event is.

def from_emailbison(payload):
    """A page of EmailBison replies, or a webhook batch, into neutral events."""
    from . import adapters
    return adapters.from_emailbison(payload)


def from_heyreach(payload):
    """A page of the HeyReach inbox, or a webhook batch, into neutral events."""
    from . import adapters
    return adapters.from_heyreach(payload)


ADAPTERS = {"emailbison": from_emailbison, "heyreach": from_heyreach}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.events")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--id")
    pl.add_argument("--type")

    pi = sub.add_parser("ingest")
    pi.add_argument("--file", required=True, help="a saved provider payload")
    pi.add_argument("--provider", required=True, choices=sorted(ADAPTERS))

    a = p.parse_args(argv)

    if a.cmd == "list":
        for rec in store.load():
            if a.id and rec["id"] != a.id:
                continue
            for entry in of(rec, *( (a.type,) if a.type else () )):
                print(f"{rec['id']:<20} {entry['at']:<26} {entry['type']:<22} "
                      f"{entry.get('contact') or ''}")
        return 0

    with open(a.file, encoding="utf-8") as f:
        payload = json.load(f)
    results = ingest(ADAPTERS[a.provider](payload))
    for r in results:
        print(f"{r['status']:<10} {r.get('record_id') or ''} {r.get('why') or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
