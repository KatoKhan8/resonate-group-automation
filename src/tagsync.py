#!/usr/bin/env python3
"""What the providers should be told about a contact, and whether they know.

## Resonate is authoritative, and this is downstream of that

An engagement state lives in the event log. EmailBison and HeyReach hold
*copies* of a conclusion, so that a person looking at a lead in the
provider's own UI sees what we know. Nothing here is allowed to read a
provider tag back and change canonical state - the arrow points one way, and
a module that could reverse it would make the provider the database.

## Why an outbox rather than a call

Ingesting a reply must not depend on a provider being up. The order is:

    authoritative reply
      -> canonical state (accountpolicy.apply_reply)
      -> desired tag state (here)
      -> a provider call, later, by something else
      -> result recorded, retried if it failed

So a provider outage delays a tag and cannot lose a suppression. That is the
same reason the Slack notification is last in `replies.apply`.

## Desired state, not an instruction queue

A row here says *what should be true*, keyed by (workspace, record, contact,
provider). Re-ingesting the same reply recomputes the same desired state and
writes the same row, which is why repeated ingestion cannot produce duplicate
operations: there is nothing to duplicate. Attempts, last error and last
success live beside the desired state rather than in it.

## Tags accumulate; one operational tag does not

`resonate_dnc` and `resonate_positive` are both true of somebody who replied
warmly in March and asked to be removed in June, and both stay. What does
*not* accumulate is the single `resonate_stage` tag, which names where the
contact is now - so an operator filtering in EmailBison for "current stage"
gets one answer. History lives in the event log, which is immutable; the
provider holds a summary and is allowed to be a summary.

## Identity, and the reason nothing here fuzzy-matches

A row is only ever written for a contact whose provider lead id we hold, or
whose canonical email (EmailBison) or canonical LinkedIn URL (HeyReach) we
hold. Tagging the wrong lead is worse than tagging none: it writes our
conclusion about one person onto another. `dedupe` defines identity and this
uses it.

## Nothing here sends

There is no live mutation in this module and no code path that could
perform one. `plan()` builds rows, `preview()` renders what would be sent,
and the adapters describe a request without issuing it.

**LIVE CONTRACT VALIDATION REQUIRED.** No tag endpoint on either provider
has been exercised. EmailBison's custom variables round-trip for `subject`
and `body` only; HeyReach was confirmed on 2026-08-26 to return
`customFields: []` on every conversation, so its tags need its own tag or
list API, whose shape nobody here has seen. See LIVE-VALIDATION-PLAN.md.
"""
import json
import os

from . import accountpolicy as ap, dedupe, linkedin, store

# ------------------------------------------------------------- the tags
#
# Stable, prefixed, lower case, no spaces. The prefix is not decoration: a
# provider account is shared with the client's own sequences and a bare
# `positive` would collide with whatever they already use.
PREFIX = "resonate_"

POSITIVE = PREFIX + "positive"
REPLIED = PREFIX + "replied"
FOLLOW_UP = PREFIX + "follow_up"
NOT_INTERESTED = PREFIX + "not_interested"
REFERRAL = PREFIX + "referral"
WRONG_PERSON = PREFIX + "wrong_person"
LEFT_COMPANY = PREFIX + "left_company"
DNC = PREFIX + "dnc"
ACCOUNT_DNC = PREFIX + "account_dnc"
EXISTING_CLIENT = PREFIX + "existing_client"
MEETING = PREFIX + "meeting"
REVIEW = PREFIX + "review"

TAGS = (POSITIVE, REPLIED, FOLLOW_UP, NOT_INTERESTED, REFERRAL, WRONG_PERSON,
        LEFT_COMPANY, DNC, ACCOUNT_DNC, EXISTING_CLIENT, MEETING, REVIEW)

# Which tags one canonical outcome asserts. `REPLIED` is on every row: the
# coarsest true thing, and the one a client's own sequence is most likely to
# already filter on.
OUTCOME_TAGS = {
    ap.POSITIVE: (REPLIED, POSITIVE),
    ap.NEUTRAL: (REPLIED,),
    ap.NEGATIVE: (REPLIED, NOT_INTERESTED),
    ap.NOT_NOW: (REPLIED, FOLLOW_UP),
    ap.NOT_ICP: (REPLIED, NOT_INTERESTED),
    ap.WRONG_PERSON: (REPLIED, WRONG_PERSON),
    ap.LEFT_COMPANY: (REPLIED, LEFT_COMPANY),
    ap.REFERRAL: (REPLIED, REFERRAL),
    ap.EXISTING_CLIENT: (REPLIED, EXISTING_CLIENT),
    ap.UNSUBSCRIBE: (REPLIED, DNC),
    ap.ACCOUNT_DNC: (REPLIED, DNC, ACCOUNT_DNC),
    ap.UNKNOWN: (REPLIED, REVIEW),
}

# The one tag that is replaced rather than added: where this contact is now.
# Everything else in `TAGS` accumulates.
STAGE_OF = {
    ap.POSITIVE: POSITIVE,
    ap.NEUTRAL: REPLIED,
    ap.NEGATIVE: NOT_INTERESTED,
    ap.NOT_NOW: FOLLOW_UP,
    ap.NOT_ICP: NOT_INTERESTED,
    ap.WRONG_PERSON: WRONG_PERSON,
    ap.LEFT_COMPANY: LEFT_COMPANY,
    ap.REFERRAL: REFERRAL,
    ap.EXISTING_CLIENT: EXISTING_CLIENT,
    ap.UNSUBSCRIBE: DNC,
    ap.ACCOUNT_DNC: ACCOUNT_DNC,
    ap.UNKNOWN: REVIEW,
}

EMAILBISON = "emailbison"
HEYREACH = "heyreach"
PROVIDERS = (EMAILBISON, HEYREACH)

# Sync status. `BLOCKED` is not a failure: it means we have no authoritative
# way to name this lead to that provider, which is a reason never to try.
PENDING = "pending"
SENT = "sent"
FAILED = "failed"
BLOCKED = "blocked"
STATUSES = (PENDING, SENT, FAILED, BLOCKED)


class TagSyncRefused(RuntimeError):
    """A live provider mutation was attempted. This build cannot do that."""


# ---------------------------------------------------------------- identity

def target(contact, provider):
    """How this provider would name this contact, or None if we cannot.

    Never a name, never a company. EmailBison addresses a lead by its own
    lead id or by the mailbox; HeyReach by its own lead id or the canonical
    profile URL, which `src/linkedin.py` already normalises and which is the
    key its replies are matched on.
    """
    contact = contact or {}
    ids = {key.split(":", 1)[0]: key.split(":", 1)[1]
           for key in dedupe.provider_ids(contact)}
    if provider == EMAILBISON:
        if ids.get("bison_lead_id"):
            return {"by": "provider_lead_id", "value": ids["bison_lead_id"]}
        email = dedupe.normalise_email(contact.get("email"))
        return {"by": "email", "value": email} if email else None
    if provider == HEYREACH:
        if ids.get("heyreach_lead_id"):
            return {"by": "provider_lead_id", "value": ids["heyreach_lead_id"]}
        profile = linkedin.canonical(contact.get("linkedin"))
        return {"by": "linkedin_url", "value": profile} if profile else None
    raise ValueError(f"unknown provider: {provider!r}")


# ------------------------------------------------------------ desired state

def desired(rec, contact_key, config=None, outcome=None):
    """Which tags should be true of this contact, and which stage they are at.

    `outcome` is the one the caller just applied. It matters: `apply_reply`
    can be handed an outcome directly - that is how the classifier narrows a
    reply - and re-deriving it from the log would read the *unclassified*
    receipt and tag the contact `review` when we had just decided otherwise.

    Falls back to the log when no outcome is given, so a caller with only a
    record still gets the canonical answer, and recomputing for the same
    reply gives the same result either way, which is what makes writing it
    idempotent.
    """
    outcome = outcome or ap.classify_outcome(rec, contact_key)
    contact = next((c for c in rec.get("contacts") or []
                    if c.get("key") == contact_key), None)
    tags = set(OUTCOME_TAGS.get(outcome, (REPLIED, REVIEW)))

    # Facts that outrank the last reply. A meeting and a suppression are both
    # true whatever the most recent message said.
    from . import events as event_model
    if any(e.get("type") == event_model.MEETING_MARKED
           and e.get("contact") == contact_key
           for e in rec.get("events") or []):
        tags.add(MEETING)
    state, _why = ap.contact_state(contact)
    if state == ap.SUPPRESS:
        tags.add(DNC)
    if (rec.get("suppression") or {}).get("unsubscribed"):
        tags.update((DNC, ACCOUNT_DNC))

    return {"outcome": outcome, "tags": sorted(tags),
            "stage": STAGE_OF.get(outcome, REVIEW)}


def plan(rec, contact_key, workspace, config=None, providers=PROVIDERS,
         outcome=None):
    """One desired-state row per provider. Pure: writes nothing, sends nothing."""
    want = desired(rec, contact_key, config, outcome)
    contact = next((c for c in rec.get("contacts") or []
                    if c.get("key") == contact_key), None)
    rows = []
    for provider in providers:
        where = target(contact, provider)
        rows.append({
            "workspace": workspace,
            "record_id": rec.get("id"),
            "contact_key": contact_key,
            "provider": provider,
            "outcome": want["outcome"],
            "tags": want["tags"],
            "stage": want["stage"],
            "target": where,
            # No authoritative way to name this lead to this provider. Not a
            # failure and never retried: there is nothing to retry.
            "status": PENDING if where else BLOCKED,
            "why": None if where else
                   f"no authoritative {provider} identity for this contact",
        })
    return rows


def key_of(row):
    """What makes two rows the same desired state. The idempotency key."""
    return "|".join(str(row[k]) for k in
                    ("workspace", "record_id", "contact_key", "provider"))


# ------------------------------------------------------------- the outbox

def path():
    # Beside the queue, not beside the repository. `store.queue_path()` is
    # already redirected by every test and by any deployment that moves its
    # state, so this follows it - a path anchored to `store.ROOT` wrote a
    # test's provider outbox into the working copy.
    return os.path.abspath(
        os.environ.get("TAG_OUTBOX")
        or os.path.join(os.path.dirname(store.queue_path()), "tag-outbox.jsonl"))


def load(file_path=None):
    """The outbox, newest row per key. Append-only on disk, collapsed here."""
    file_path = file_path or path()
    if not os.path.exists(file_path):
        return {}
    out = {}
    with open(file_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            out[key_of(row)] = row
    return out


def enqueue(rec, contact_key, workspace, config=None, file_path=None,
            at=None, outcome=None):
    """Record what the providers should know. Never calls one.

    Idempotent by construction: the desired state is recomputed from the
    event log, so the same reply produces the same row. A row whose desired
    tags and stage are unchanged is not written again, which is what keeps a
    replayed webhook from queueing a second operation.
    """
    file_path = file_path or path()
    current = load(file_path)
    written = []
    for row in plan(rec, contact_key, workspace, config, outcome=outcome):
        key = key_of(row)
        before = current.get(key)
        if (before and before.get("tags") == row["tags"]
                and before.get("stage") == row["stage"]
                and before.get("status") in (SENT, BLOCKED)):
            continue                    # already true, or already unreachable
        if before and before.get("tags") == row["tags"] \
                and before.get("stage") == row["stage"] \
                and before.get("status") == PENDING:
            continue                    # already queued, unchanged
        row = dict(row, queued_at=at or store.now(),
                   attempts=(before or {}).get("attempts", 0),
                   last_error=(before or {}).get("last_error"),
                   last_success=(before or {}).get("last_success"))
        written.append(row)
    if written:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "a", encoding="utf-8") as handle:
            for row in written:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    return written


def record_attempt(row, ok, error=None, file_path=None, at=None):
    """Append the result of one attempt. Used by whatever eventually sends."""
    file_path = file_path or path()
    stamp = at or store.now()
    updated = dict(row,
                   attempts=(row.get("attempts") or 0) + 1,
                   status=SENT if ok else FAILED,
                   last_error=None if ok else str(error or "unknown"),
                   last_success=stamp if ok else row.get("last_success"),
                   attempted_at=stamp)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(updated, sort_keys=True) + "\n")
    return updated


def pending(file_path=None):
    """Rows still owed to a provider, oldest first."""
    rows = [r for r in load(file_path).values()
            if r.get("status") in (PENDING, FAILED)]
    return sorted(rows, key=lambda r: str(r.get("queued_at") or ""))


def status_for(rec_id, contact_key, file_path=None):
    """Per-provider sync status for one contact, for an operator screen."""
    rows = load(file_path)
    out = {}
    for provider in PROVIDERS:
        row = rows.get("|".join(("", "", "", provider)))
        out[provider] = None
    for row in rows.values():
        if row.get("record_id") == rec_id and \
                row.get("contact_key") == contact_key:
            out[row["provider"]] = row
    return out


# ------------------------------------------------------------- the adapters
#
# What a request *would* be. Each returns a description; none of them has a
# code path that issues one, and `send` exists only to say so out loud.

def emailbison_request(row):
    """The shape a tag write would take. Endpoint unvalidated - see docs."""
    if row["provider"] != EMAILBISON:
        raise ValueError("not an EmailBison row")
    return {
        "provider": EMAILBISON,
        "method": "POST",
        # Named so it is reviewable, exactly as `bison.leads_endpoint` is.
        # Nothing has confirmed this path exists.
        "path": "/leads/tags",
        "identify": row["target"],
        "body": {"tags": row["tags"], "stage": row["stage"]},
        "validated": False,
    }


def heyreach_request(row):
    """The shape a tag write would take. HeyReach exposes no custom fields.

    Confirmed live on 2026-08-26: `customFields` comes back empty on every
    conversation and `/lead/GetLead` exposes none, so the tags cannot ride
    along on the lead payload the way `record_id` does. A real
    implementation needs HeyReach's own tag or list API.
    """
    if row["provider"] != HEYREACH:
        raise ValueError("not a HeyReach row")
    return {
        "provider": HEYREACH,
        "method": "POST",
        "path": "/lead/AddTags",
        "identify": row["target"],
        "body": {"tags": row["tags"], "stage": row["stage"]},
        "validated": False,
    }


ADAPTERS = {EMAILBISON: emailbison_request, HEYREACH: heyreach_request}


def preview(rows):
    """Every request that would be issued, for review. Issues none."""
    out = []
    for row in rows:
        if row.get("status") == BLOCKED:
            out.append({"provider": row["provider"], "skipped": row["why"]})
            continue
        out.append(ADAPTERS[row["provider"]](row))
    return out


def send(row, live=False):
    """Refuses. The contract has never been validated against either wire.

    Kept so the seam is visible and so a caller that assumed it could send
    fails loudly here rather than silently doing nothing somewhere else.
    """
    raise TagSyncRefused(
        "provider tag mutation is not implemented in this build: no tag "
        "endpoint on EmailBison or HeyReach has been validated against the "
        "live contract. The desired state is recorded and previewable. See "
        "LIVE-VALIDATION-PLAN.md.")
