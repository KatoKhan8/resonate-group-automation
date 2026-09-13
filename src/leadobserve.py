#!/usr/bin/env python3
"""What the provider did to a staged lead, recorded when it changes.

## Why this exists

Nothing in this system could record that a LinkedIn invitation went out.
`touch.CONFIRMING_EVENTS` is writable only by a send path that raises or by a
webhook HeyReach does not expose, so a canary's first touch was unrecordable by
construction - the funnel would report zero confirmed actions for ever while a
real person sat in a live campaign.

`heyreach.campaign_leads` answers it per lead. This is the durable half: read
provider truth, compare it to the last thing recorded, and append a row ONLY
when the state actually moved.

## Rules

**A transition is provider truth or it does not exist.** Nothing here derives a
state from elapsed time, from campaign status, or from a counter.
`progressStats` is never consulted: it is a residual that counts a lead which
has done nothing and goes negative on live campaigns.

**Campaign ACTIVE is not a send.** The canary campaign moved to `IN_PROGRESS`
the moment an operator unpaused it, while its one lead still read
`Pending / None / lastActionTime null`. Anything that treated the campaign
status as the action would have reported a message nobody received.

**Exactly once.** A row is appended only when `state` differs from the last row
for that lead, so polling every minute for a week leaves one row per real
change. That is what makes "transition the logical action to OBSERVING exactly
once" enforceable rather than aspirational.

**UNKNOWN is recorded, not resolved.** An unrecognised provider value becomes
`heyreach.LIFECYCLE_UNKNOWN` upstream and is stored with the raw words beside
it, so a vocabulary change shows up as a row a person can read rather than as a
silently neighbouring state.

## What it is not

It is not the action ledger. The ledger records what THIS SYSTEM did and is the
authority on duplicate suppression; this records what the PROVIDER did, which
for a hand-staged canary is the only record there is. They are reconciled by
`reconcile()`, which states plainly when one has a row the other does not -
today that is the normal case, because the canary was staged by a person in the
vendor UI and no reservation was ever written.

## The second provider

Email is the same problem with a different noun. `bison.scheduled_emails`
publishes one row per queued send, moving `scheduled` -> `sent` | `bounced` |
`stopped`, and until this module read it nothing in the codebase did: the
function had no caller at all. So the first live email canary would have sent
on a Monday morning and the only record of it would have been a person
noticing.

Two things make that half different from the LinkedIn half and both are
recorded rather than assumed:

**The join key round-trips.** A scheduled email carries `lead.custom_variables`
holding the `record_id`, `contact_key` and `client` this system staged, read
back off the provider's own state - measured on campaign 451 on 2026-09-13.
That is the opposite of HeyReach, whose `customFields` come back empty, and it
is why `match_scheduled` never has to correlate on an email address.

**`sent` is not `delivered`.** EmailBison's `sent` says it handed the message
to SMTP. It does not say a mailbox accepted it, so `sent` records
`push_marked` - confirmed SENT - and never `email_delivered`. No delivery
confirmation exists on this surface, and reporting an absent one as zero is
the failure this whole layer is built to avoid.
"""
import argparse
import html as html_module
import json
import os
import re
import sys

from . import events, linkedin, store, touch
from .providers import bison, heyreach

# Every observation, append-only, beside the queue - the same argument the
# spend ledger makes: the records and what happened to them move together.
FILE = "lead-observations.jsonl"

# Which provider a row came from. Rows written before this field existed are
# all HeyReach - the file held exactly one campaign, 594061 - so a row with no
# provider is read as HeyReach explicitly rather than matched against
# everything. Campaign ids are per-provider and 451 and 594061 are only
# accidentally different numbers.
HEYREACH = "heyreach"
EMAILBISON = "emailbison"


def path():
    return os.path.abspath(os.environ.get("LEAD_OBSERVATIONS")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           FILE))


def load():
    try:
        return store.read_jsonl(path())
    except FileNotFoundError:
        return []


def _last(rows, provider, campaign_id, field, value):
    """The most recent row for one thing at one provider, or None.

    Provider-scoped on purpose. Two providers number their campaigns
    independently, so "campaign 451" and "campaign 594061" are only
    accidentally different and a match on the number alone would let one
    provider's history answer for the other's.
    """
    found = None
    for row in rows:
        if (row.get("provider") or HEYREACH) != provider:
            continue
        if str(row.get("campaign_id")) != str(campaign_id):
            continue
        if str(row.get(field)) != str(value):
            continue
        found = row
    return found


def last_for(campaign_id, lead_id, rows=None):
    """The most recent recorded state for one HeyReach lead, or None."""
    return _last(load() if rows is None else rows, HEYREACH, campaign_id,
                 "provider_lead_id", lead_id)


def observe(campaign_id, now=None):
    """Read the provider and append a row for every lead that moved.

    Returns the rows appended, which is empty on a quiet poll - and an empty
    list is the ordinary answer. A poller that wrote something every tick would
    make a week of nothing look like a week of activity.
    """
    leads, total = heyreach.campaign_leads(campaign_id)
    stats = heyreach.campaign_stats(campaign_id)
    campaign = heyreach.campaign_by_id(campaign_id) or {}
    rows = load()
    appended = []
    for lead in leads:
        previous = last_for(campaign_id, lead.get("provider_lead_id"), rows)
        if previous is not None and previous.get("state") == lead.get("state"):
            continue
        appended.append({
            "at": now or store.now(),
            "provider": HEYREACH,
            "campaign_id": str(campaign_id),
            "campaign_status": campaign.get("status"),
            "provider_lead_id": lead.get("provider_lead_id"),
            "provider_profile_id": lead.get("provider_profile_id"),
            "sender_id": lead.get("sender_id"),
            "state": lead.get("state"),
            "was": (previous or {}).get("state"),
            # The provider's own words and its own timestamp. `at` above is
            # when this system looked; `provider_at` is when the provider says
            # it happened, and conflating them would date every action to
            # whenever a poll happened to run.
            "provider_at": lead.get("at"),
            "raw": lead.get("raw"),
            "error_code": lead.get("error_code"),
            "why": lead.get("why"),
            "lead_count": total,
            "campaign_stats": stats,
        })
    if appended:
        with store.file_transaction(path()) as existing:
            existing.extend(appended)
    return appended


def history(campaign_id=None, provider=None):
    rows = load()
    if provider is not None:
        rows = [r for r in rows if (r.get("provider") or HEYREACH) == provider]
    if campaign_id is None:
        return rows
    return [r for r in rows if str(r.get("campaign_id")) == str(campaign_id)]


def reached(campaign_id):
    """HeyReach leads the provider says have actually been contacted.

    `heyreach.REACHED` deliberately excludes FAILED: a failed lead may already
    have been accepted, and 28 of 851 sampled leads were exactly that.
    """
    seen = {}
    for row in history(campaign_id, provider=HEYREACH):
        seen[row.get("provider_lead_id")] = row.get("state")
    return {lead for lead, state in seen.items() if state in heyreach.REACHED}


class Ambiguous(RuntimeError):
    """One provider lead matched more than one contact. Nobody may guess."""


def match_lead(lead, recs):
    """(record, contact) for the human this provider lead is, or None.

    Matched on `linkedin.canonical`, because it is the only identifier that
    survives the round trip: HeyReach returns `customFields: []` on every
    conversation, so the record id and contact key this system sends are
    write-only decoration and cannot be read back.

    Refuses to guess. Two contacts behind one profile raises rather than
    picking the first - a wrong person is the one outcome this whole module
    exists to prevent, and "probably them" is how that happens.
    """
    key = linkedin.key(lead.get("profile_url"))
    if not key:
        return None
    found = [(rec, contact)
             for rec in recs
             for contact in (rec.get("contacts") or [])
             if contact.get("linkedin")
             and linkedin.key(contact["linkedin"]) == key]
    if len(found) > 1:
        raise Ambiguous(
            f"provider lead {lead.get('provider_lead_id')!r} matches "
            f"{len(found)} contacts: "
            + ", ".join(f"{r.get('id')}/{c.get('key')}" for r, c in found)
            + ". Reconcile the duplicate before recording a touch")
    return found[0] if found else None


def _linkedin_step(rec, contact_key):
    """The one LinkedIn step this contact has, or None if it is not one.

    Only used to date the touch onto a cadence day so
    `eligibility._separation` can see it. When it cannot be determined the
    touch is still recorded - a touch nobody can place on a day is worth far
    more than no touch at all, and `fatigue` reads the event either way.
    """
    steps = ((rec.get("cadence") or {}).get(contact_key) or {})
    linkedin_steps = [(key, step) for key, step in steps.items()
                      if (step or {}).get("channel") == "linkedin"]
    return linkedin_steps[0] if len(linkedin_steps) == 1 else (None, {})


def confirm_touches(campaign_id, recs=None, live=False):
    """Record the canonical confirmed touch for a lead the PROVIDER reached.

    THE OTHER HALF OF THE DUPLICATION LAW. `providerwrites.perform` records a
    touch when THIS system writes to the provider. The canary is the opposite
    case: an operator staged the lead and unpaused the campaign by hand, so
    `eligibility` answers `blocked:campaign_already_launched` and HeyReach
    sends the connection request on its own schedule. Resonate OS is not the
    executor there - it can only observe.

    Without this, the moment that invitation goes out the provider knows and
    nothing here does: `funnel` reports zero confirmed actions for ever,
    `touch` sees nothing, and the duplication law has no touch to refuse a
    second action against. That is this repository's named recurring defect -
    a thing computed correctly that nothing downstream reads - sitting on the
    single most safety-relevant fact the provider publishes.

    Idempotent by construction. The event carries a `provider_event_id` of
    (provider, campaign, lead, state), and `events.record` returns None for a
    duplicate, so polling every minute for a week records one touch per real
    transition. The provider's OWN timestamp dates the event, never now(): a
    reconciliation run days later must not claim the invitation went out
    today.

    Dry by default; `live=True` writes. Either way `recorded` is the touch
    this found, `already` is a touch the record already carried, and
    `unmatched` is a lead the provider reached that nothing here can place.
    """
    recs = store.load() if recs is None else recs
    leads, _total = heyreach.campaign_leads(campaign_id)
    recorded, unmatched, already = [], [], []
    for lead in leads:
        if lead.get("state") not in heyreach.REACHED:
            continue
        found = match_lead(lead, recs)
        if found is None:
            # Reported, never guessed. A lead the provider reached that this
            # system cannot place is a reconciliation question for a person.
            unmatched.append(lead.get("provider_lead_id"))
            continue
        rec, contact = found
        step_key, step = _linkedin_step(rec, contact.get("key"))
        entry = {
            "rec_id": rec.get("id"), "contact_key": contact.get("key"),
            "provider_lead_id": lead.get("provider_lead_id"),
            "state": lead.get("state"), "at": lead.get("at"),
            "step": step_key,
        }
        # `recorded` means "this is the touch", dry or live. The first version
        # filed a dry-run entry under `already`, which reads as "we knew that"
        # - the opposite of what a dry run is telling you.
        recorded.append(entry)
        if not live:
            continue
        with store.transaction() as rows:
            live_rec = store.get(rec.get("id"), rows)
            if live_rec is None:
                continue
            written = events.record(
                live_rec, events.PUSH_MARKED,
                contact_key=contact.get("key"), channel="linkedin",
                at=lead.get("at") or store.now(),
                provider="heyreach",
                provider_event_id=(f"heyreach:{campaign_id}:"
                                   f"{lead.get('provider_lead_id')}:"
                                   f"{lead.get('state')}"),
                step=step_key, day=(step or {}).get("day"),
                sender_id=lead.get("sender_id"),
                campaign_id=str(campaign_id))
            if written is None:
                recorded.pop()
                already.append(entry)
    return {"live": live, "recorded": recorded, "already": already,
            "unmatched": unmatched}


def reconcile(campaign_id):
    """What the provider did, beside what this system recorded doing.

    For a hand-staged canary the honest answer is that the ledger is empty and
    the provider acted anyway, because a person staged the lead in the vendor
    UI. That is a difference worth stating rather than smoothing over: it is
    the reason `funnel.provider_staged` reads 0 while a real prospect sits in a
    live campaign.
    """
    from . import actionledger

    ledger = {row.get("key") for row in actionledger.load()
              if str(row.get("campaign_id")) == str(campaign_id)}
    seen = reached(campaign_id)
    rows = history(campaign_id, provider=HEYREACH)
    if not rows:
        note = "nothing observed yet; this campaign has never been read"
    elif seen and not ledger:
        note = ("the provider has acted on leads this system never reserved: "
                "the campaign was staged by hand in the vendor UI, so there is "
                "no ledger row to reconcile against")
    elif seen and ledger:
        note = "both sides have rows; compare them lead by lead"
    else:
        note = ("observed, and the provider has not contacted anybody yet. "
                "The leads are enrolled and waiting on the provider's own "
                "schedule")
    return {"campaign_id": str(campaign_id),
            "provider_reached": sorted(str(x) for x in seen),
            "ledger_keys": sorted(ledger),
            "observations": len(rows),
            "note": note}


# ----------------------------------------------------------- EmailBison
#
# The pre-send queue as provider truth. Every state below is a word EmailBison
# itself uses; nothing is derived from elapsed time, from campaign status or
# from a counter, for the same reason `progressStats` is refused above.

SCHEDULED = "scheduled"
SENT = "sent"
BOUNCED = "bounced"
STOPPED = "stopped"

EMAIL_STATES = (SCHEDULED, SENT, BOUNCED, STOPPED)

# A status this module has never seen. Recorded with the provider's own word
# beside it, never folded into a neighbouring state - a vocabulary change must
# surface as a row a person reads, not as a quietly wrong transition.
EMAIL_STATE_UNKNOWN = "email_state_unknown"

# What each state means in canonical vocabulary, and what it deliberately does
# not mean.
#
#   scheduled  nothing has happened to anybody. Not a touch, not an exposure.
#   sent       PUSH_MARKED - touch.SENT. NOT email_delivered: EmailBison's
#              `sent` says it handed the message to SMTP and says nothing
#              about a mailbox accepting it.
#   bounced    EMAIL_BOUNCED, which `touch.CONFIRMING_EVENTS` deliberately
#              excludes. A send was attempted and failed; nobody was reached.
#   stopped    PROVIDER_STOP_CONFIRMED - the provider states this person will
#              receive nothing further from this campaign.
EVENT_FOR = {
    SENT: events.PUSH_MARKED,
    BOUNCED: events.EMAIL_BOUNCED,
    STOPPED: events.PROVIDER_STOP_CONFIRMED,
}

# The states that mean the provider actually put a message in front of a
# person. `bounced` is absent by name.
EMAIL_REACHED = frozenset({SENT})

_TAG = re.compile(r"<[^>]+>")
_BREAK = re.compile(r"<br\s*/?>|</p>|</div>", re.I)
_SPACE = re.compile(r"\s+")


def _plain(markup):
    """The words a person will read, out of the provider's rendered HTML.

    Used only to measure length, which is one of the things a later question
    asks about. The text itself is never stored: the approved copy already
    lives on the record and a second copy of it here would be a second
    representation of the same truth, free to drift from the first.
    """
    text = _BREAK.sub("\n", str(markup or ""))
    text = _TAG.sub("", text)
    return _SPACE.sub(" ", html_module.unescape(text)).strip()


def _email_state(status):
    text = str(status or "").strip().lower()
    return text if text in EMAIL_STATES else EMAIL_STATE_UNKNOWN


def scheduled_rows(campaign_id):
    """EmailBison's pre-send queue for one campaign, trimmed.

    `bison.scheduled_emails` returns the provider's whole row: the rendered
    HTML body, the sender's email signature, the nested campaign object. None
    of that is kept. What is kept is what a later question needs and what a
    person reconciling by hand would ask for - the identity, the state, the
    provider's own timestamps, the measured length of what was rendered, and
    the counters with the flag that says whether they mean anything.

    `open_tracking` travels beside `opens` for exactly that reason. This
    campaign has tracking off, so its opens are 0 forever, and a report that
    printed "0 opens" without the flag would be stating that nobody opened it.
    """
    out = []
    for row in bison.scheduled_emails(campaign_id):
        if not isinstance(row, dict):
            continue
        lead = row.get("lead") if isinstance(row.get("lead"), dict) else {}
        sender = (row.get("sender_email")
                  if isinstance(row.get("sender_email"), dict) else {})
        campaign = (row.get("campaign")
                    if isinstance(row.get("campaign"), dict) else {})
        variables = bison.variables_of(lead)
        body = _plain(row.get("email_body"))
        subject = _plain(row.get("email_subject"))
        out.append({
            "provider": EMAILBISON,
            "campaign_id": str(campaign_id),
            "campaign_status": campaign.get("status"),
            "scheduled_email_id": row.get("id"),
            "sequence_step_id": row.get("sequence_step_id"),
            "state": _email_state(row.get("status")),
            "raw_status": row.get("status"),
            # Two clocks, kept apart exactly as `provider_at` is above.
            "scheduled_at": row.get("scheduled_date"),
            "sent_at": row.get("sent_at"),
            "provider_message_id": row.get("raw_message_id"),
            "provider_lead_id": lead.get("id"),
            "email": lead.get("email"),
            # Our own identifiers, read back off the provider's state. This is
            # what makes an observation attributable without a guess.
            "record_id": variables.get("record_id"),
            "contact_key": variables.get("contact_key"),
            "client": variables.get("client"),
            "sender_account_id": sender.get("id"),
            "sender_email": sender.get("email"),
            # Measured, not stored. See `_plain`.
            "subject_chars": len(subject),
            "body_chars": len(body),
            "body_words": len(body.split()) if body else 0,
            "opens": row.get("opens"),
            "unique_opens": row.get("unique_opens"),
            "clicks": row.get("clicks"),
            "replies": row.get("replies"),
            "unique_replies": row.get("unique_replies"),
            "interested": row.get("interested"),
            # Without this the counters above are unreadable.
            "open_tracking": campaign.get("open_tracking"),
        })
    return out


def observe_emails(campaign_id, now=None):
    """Read EmailBison and append a row for every scheduled email that moved.

    The same law as `observe`: a row is appended only when the state actually
    differs from the last one recorded, so polling every minute through a
    weekend leaves one row per real transition and a quiet poll returns an
    empty list.
    """
    rows = scheduled_rows(campaign_id)
    existing = load()
    appended = []
    for row in rows:
        previous = _last(existing, EMAILBISON, campaign_id,
                         "scheduled_email_id", row["scheduled_email_id"])
        if previous is not None and previous.get("state") == row["state"]:
            continue
        entry = dict(row)
        entry["at"] = now or store.now()
        entry["was"] = (previous or {}).get("state")
        appended.append(entry)
    if appended:
        with store.file_transaction(path()) as held:
            held.extend(appended)
    return appended


def match_scheduled(row, recs):
    """Who this scheduled email is for, or a refusal that says why.

    Never guesses, and the refusals are the point. `events.match_record` and
    `events.match_contact` are the canonical matchers and they already refuse
    an ambiguous address rather than picking the first hit; this adds the
    tenancy check `events.apply` makes, because a `client` custom variable
    that disagrees with the record means the lead in front of us is not the
    lead we think it is.
    """
    probe = {"record_id": row.get("record_id"), "email": row.get("email"),
             "contact_key": row.get("contact_key")}
    rec = events.match_record(recs, probe)
    if rec is None:
        return {"rec": None, "contact_key": None,
                "why": "no record matches this lead's record_id or address"}
    if row.get("client") and rec.get("client") != row["client"]:
        return {"rec": None, "contact_key": None,
                "why": (f"the lead says client {row['client']!r} and record "
                        f"{rec.get('id')!r} belongs to "
                        f"{rec.get('client')!r}")}
    contact_key = events.match_contact(rec, probe)
    if contact_key is None:
        return {"rec": None, "contact_key": None,
                "why": (f"record {rec.get('id')!r} matched, but no single "
                        f"contact on it does")}
    return {"rec": rec, "contact_key": contact_key, "why": None}


def _step_of(rec, contact_key, scheduled_email_id):
    """Which cadence step this scheduled email is, from what we already wrote.

    RECONCILIATION, NOT INFERENCE. When this system staged the send it
    recorded `scheduled_email_id` on the event, so the provider's row and our
    own log share an identifier and the step comes back exactly. Nothing is
    matched on rendered subject text, which would silently pick the wrong step
    the first time two steps opened the same way.

    None when there is no such event - a lead somebody staged in the vendor UI
    has no step here, and a touch that cannot be placed on a cadence day is
    still worth far more than no touch at all.
    """
    for entry in rec.get("events") or []:
        if entry.get("contact") not in (None, contact_key):
            continue
        if str(entry.get("scheduled_email_id") or "") == str(scheduled_email_id):
            return entry.get("step")
    return None


def _already_confirmed(rec, contact_key, step, scheduled_email_id):
    """A confirmed touch this record already carries for this send, or None.

    THE DUPLICATION LAW, on the read side. The canary's first touch was
    written by hand at staging time and carries no `provider_event_id`, so
    idempotency on the provider's id alone would not have seen it: the poller
    would have added a second confirmed touch for one message the moment
    EmailBison moved the row to `sent`, and every rate with exposures
    underneath it would have counted that message twice.
    """
    for entry in rec.get("events") or []:
        if entry.get("type") not in touch.CONFIRMING_EVENTS:
            continue
        if entry.get("contact") != contact_key:
            continue
        if entry.get("channel") != events.EMAIL:
            continue
        if str(entry.get("scheduled_email_id") or "") == str(scheduled_email_id):
            return entry
        if step and entry.get("step") == step:
            return entry
    return None


def confirm_email_touches(campaign_id, recs=None, live=False):
    """Record the canonical event for every scheduled email that has moved.

    The email half of what `confirm_touches` does for LinkedIn, and the reason
    the first canary send will be captured without anybody watching for it.

    Four outcomes and no fifth:

        recorded   a state the provider reports and this record did not carry
        already    reconciled - the record already has this fact, from the
                   hand-written staging touch or from an earlier poll
        waiting    still `scheduled`, or a status this module does not know.
                   Nothing has happened to anybody, and recording something
                   would be the exact error `push_prepared` is excluded for
        unmatched  a lead this system cannot place. Reported, never guessed
        refused    the provider stated something the event vocabulary cannot
                   hold. Loud rather than dropped - see below

    `refused` exists because of a live defect. `events.PROVIDER_STOP_CONFIRMED`
    is defined and is in neither `INTERNAL` nor `EXTERNAL`, so it is not in
    `events.KNOWN` and `events.record` raises on it. Nothing noticed because
    the one writer, `leadstop._record`, appends the dict to `rec["events"]`
    itself and never goes through the canonical writer - so the event carries
    no id and no idempotency either. This module will not open a second such
    bypass to get around it. A provider-confirmed stop that cannot be written
    is reported as a refusal a person can read, and the day the type joins
    `INTERNAL` it is recorded here with no further change.

    Dry by default. The provider's OWN timestamp dates the event - a
    reconciliation run on Tuesday must not claim Monday's send happened on
    Tuesday.
    """
    recs = store.load() if recs is None else recs
    rows = scheduled_rows(campaign_id)
    recorded, already, unmatched, waiting, refused = [], [], [], [], []
    for row in rows:
        kind = EVENT_FOR.get(row["state"])
        if kind is not None and kind not in events.KNOWN:
            refused.append({"scheduled_email_id": row["scheduled_email_id"],
                            "state": row["state"], "event": kind,
                            "why": (f"{kind!r} is not in events.KNOWN, so the "
                                    f"canonical writer refuses it. Nothing "
                                    f"here writes around that")})
            continue
        if kind is None:
            waiting.append({"scheduled_email_id": row["scheduled_email_id"],
                            "state": row["state"],
                            "raw_status": row.get("raw_status"),
                            "scheduled_at": row.get("scheduled_at")})
            continue
        found = match_scheduled(row, recs)
        if found["rec"] is None:
            unmatched.append({"scheduled_email_id": row["scheduled_email_id"],
                              "provider_lead_id": row.get("provider_lead_id"),
                              "why": found["why"]})
            continue
        rec, contact_key = found["rec"], found["contact_key"]
        step = _step_of(rec, contact_key, row["scheduled_email_id"])
        entry = {"rec_id": rec.get("id"), "contact_key": contact_key,
                 "scheduled_email_id": row["scheduled_email_id"],
                 "state": row["state"], "event": kind, "step": step,
                 "at": row.get("sent_at") or row.get("scheduled_at")}
        if kind == events.PUSH_MARKED:
            prior = _already_confirmed(rec, contact_key, step,
                                       row["scheduled_email_id"])
            if prior is not None:
                already.append({**entry, "why": (
                    "this record already carries a confirmed email touch for "
                    "this send; reconciled rather than recorded twice"),
                    "evidence_event_id": prior.get("id")})
                continue
        recorded.append(entry)
        if not live:
            continue
        with store.transaction() as held:
            live_rec = store.get(rec.get("id"), held)
            if live_rec is None:
                continue
            written = events.record(
                live_rec, kind, contact_key=contact_key,
                channel=events.EMAIL,
                at=entry["at"] or store.now(),
                provider=EMAILBISON,
                provider_event_id=(f"emailbison:{campaign_id}:"
                                   f"{row['scheduled_email_id']}:"
                                   f"{row['state']}"),
                step=step,
                campaign_id=str(campaign_id),
                scheduled_email_id=row["scheduled_email_id"],
                lead_id=row.get("provider_lead_id"),
                sender_account_id=row.get("sender_account_id"),
                provider_message_id=row.get("provider_message_id"))
            if written is None:
                recorded.pop()
                already.append({**entry, "why": "this provider event was "
                                                "already applied"})
    return {"live": live, "campaign_id": str(campaign_id),
            "recorded": recorded, "already": already, "waiting": waiting,
            "unmatched": unmatched, "refused": refused}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.leadobserve",
                                description=__doc__)
    p.add_argument("--campaign", required=True, help="provider campaign id")
    p.add_argument("--provider", default=HEYREACH,
                   choices=(HEYREACH, EMAILBISON))
    p.add_argument("--json", action="store_true")
    p.add_argument("--history", action="store_true",
                   help="print what has been recorded, without reading the "
                        "provider")
    p.add_argument("--confirm", action="store_true",
                   help="record a canonical confirmed touch for every lead "
                        "the provider has reached. Dry unless --live")
    p.add_argument("--live", action="store_true",
                   help="with --confirm, actually write the touches")
    a = p.parse_args(argv)

    if a.confirm:
        if a.provider == EMAILBISON:
            out = confirm_email_touches(a.campaign, live=a.live)
        else:
            out = confirm_touches(a.campaign, live=a.live)
        if a.json:
            print(json.dumps(out, indent=1))
            return 0
        print(f"{a.provider} campaign {a.campaign}: "
              f"{len(out['recorded'])} event(s) recorded, "
              f"{len(out['already'])} already known, "
              f"{len(out.get('waiting') or [])} waiting, "
              f"{len(out.get('refused') or [])} refused, "
              f"{len(out['unmatched'])} unmatched"
              + ("" if out["live"] else "   (DRY - pass --live to write)"))
        for row in out["unmatched"]:
            detail = row if isinstance(row, dict) else {"provider_lead_id": row}
            why = detail.get("why") or ("the provider reached somebody this "
                                        "system cannot place")
            print(f"  UNMATCHED lead {detail.get('provider_lead_id')}: {why}. "
                  f"Reconcile by hand.")
        for row in out.get("refused") or []:
            print(f"  REFUSED {row['state']}: {row['why']}")
        return 0

    if a.history:
        rows = history(a.campaign, provider=a.provider)
    elif a.provider == EMAILBISON:
        rows = observe_emails(a.campaign)
    else:
        rows = observe(a.campaign)
    if a.json:
        print(json.dumps(rows, indent=1))
        return 0
    if not rows:
        print(f"campaign {a.campaign}: no change since the last observation")
        return 0
    for row in rows:
        subject = (row.get("provider_lead_id") if a.provider == HEYREACH
                   else row.get("scheduled_email_id"))
        print(f"{row['at']}  {a.provider} {subject}  "
              f"{row.get('was') or '-'} -> {row['state']}"
              + (f"  ({row['error_code']})" if row.get("error_code") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
