#!/usr/bin/env python3
"""What came back, what it is allowed to answer, and what nothing recorded.

## Why this exists now, with one observation in it

There is exactly one live send in this system: EmailBison campaign 451, one
scheduled email to one person, still `scheduled`. Nothing here can be
concluded from that and nothing here tries to. The reason to build this
before the volume arrives is the opposite one - **the metadata a question
needs has to be on the event when the event is written**, and an event
written today without a variant id or an evidence id is a message whose
result is unattributable for ever. A learning layer added after a thousand
sends learns about the thousand-and-first.

## Three questions that look like one

    the OBSERVATION    what happened to this person, joined to everything a
                       later question will need to group it by
    the READINESS      whether the thing a question groups by is actually
                       persisted, or merely computed somewhere
    the ANSWER         what the evidence supports, which today is nothing

The middle one is the one this repository keeps getting wrong. An evaluator
that returns INSUFFICIENT_DATA because nobody has replied yet and an
evaluator that returns INSUFFICIENT_DATA because nothing ever wrote the
field it reads are indistinguishable from outside, and they need opposite
fixes - wait, versus change the producer. So `answer()` returns
`NOT_INSTRUMENTED` and names the field when the dimension is absent from
every row, and `INSUFFICIENT_DATA` only when the dimension is there and the
sample is not.

## Nothing here is a second store

Every row is derived. The event log on the record is the truth about what
happened; `work/lead-observations.jsonl` is the truth about what the
provider says; `work/campaigns.jsonl` is the truth about which campaign.
This module joins them and holds nothing of its own, which is why a
correction to the event log corrects this too rather than leaving two
answers to drift apart.

## The thresholds are borrowed, never loosened

`src/variants.py` is the evaluator, and `variants.evaluate` is called here
rather than reimplemented: 30 exposures on the smallest cell, 8 outcomes in
total, 30% lift before the word "winner" is used, Wilson bounds on every
rate. A dimension with four replies against three produces NO_CLEAR_WINNER
here for exactly the same reason it does there.

## Provenance travels with every row

A persona read off the contact today is not the persona the message was
written to - somebody may have changed it since. So every dimension carries
where it came from, and the row's `confidence` is the weakest of them.
`ATTRIBUTED` means the provider handed our own identifier back; `RECORDED`
means our own event carried it at the time; `INFERRED` means it was read
from current state and could have moved; `ABSENT` means nothing holds it.

  python -m src.outcomes --observations
  python -m src.outcomes --questions
  python -m src.outcomes --run-report
"""
import argparse
import json

from . import (account, cadenceexposure, campaigns, events, leadobserve,
               store, touch, variants)

# ------------------------------------------------------------- provenance
#
# Ordered weakest last. `confidence` on a row is the weakest source among the
# dimensions an answer would group by, so a row whose variant is ABSENT can
# never be reported as well attributed because its persona happens to be.

ATTRIBUTED = "attributed"
RECORDED = "recorded_at_send"
INFERRED = "inferred_from_current_state"
ABSENT = "absent"

PROVENANCE = (ATTRIBUTED, RECORDED, INFERRED, ABSENT)

PROVENANCE_WHY = {
    ATTRIBUTED: "the provider handed this back off its own state",
    RECORDED: "our own event carried this when the action happened",
    INFERRED: "read from current state, which may have moved since the send",
    ABSENT: "nothing holds this",
}

# What a delivery question can be answered with.
CONFIRMED = "confirmed"
BOUNCED = "bounced"
NOT_REPORTED = "not_reported"


def _worst(*sources):
    """The weakest provenance among these. ABSENT beats everything."""
    present = [s for s in sources if s in PROVENANCE]
    if not present:
        return ABSENT
    return max(present, key=PROVENANCE.index)


# ------------------------------------------------------ the observation

def _campaign_index(rows=None):
    """record id -> the campaign row that owns it."""
    out = {}
    for campaign in (campaigns.load() if rows is None else rows):
        for record_id in campaign.get("record_ids") or []:
            out[record_id] = campaign
    return out


def _provider_index(rows=None):
    """The latest provider observation per scheduled email.

    Keyed by scheduled email id because that is the identifier that survives
    the round trip - it is on the provider's row and on our own event.
    """
    out = {}
    for row in (leadobserve.load() if rows is None else rows):
        key = row.get("scheduled_email_id")
        if key is None:
            continue
        out[str(key)] = row
    return out


def _contact_of(rec, contact_key):
    for contact in account.contacts_of(rec):
        if contact.get("key") == contact_key:
            return contact
    return {}


def _step_copy(rec, contact_key, step_key):
    """The copy the cadence holds for this step today, or {}."""
    return (((rec.get("cadence") or {}).get(contact_key) or {})
            .get(step_key) or {})


def _actions(rec, contact_key):
    """One entry per confirmed touch, deduplicated by step.

    Deduplicated the way `cadenceexposure._confirmed_steps` does it: a step
    that was marked sent and later reported delivered is one action with two
    facts about it, not two actions. The strongest state wins, which is what
    `touch.history` means by strongest rather than latest.
    """
    seen, out = {}, []
    for row in account.touches(rec, contact_key, confirmed_only=True):
        if row.get("state") not in touch.CONFIRMED_STATES:
            continue
        key = row.get("step") or f"~{row.get('channel')}:{row.get('at')}"
        if key in seen:
            # Keep the earliest timestamp and the richest attribution: the
            # first event is when it happened, and a later one may be the
            # only one carrying the sender.
            held = seen[key]
            for field in ("sender_id", "account_id", "variant_id",
                          "variant_style", "variant_version"):
                held[field] = held.get(field) or row.get(field)
            continue
        entry = dict(row)
        entry["_key"] = key
        seen[key] = entry
        out.append(entry)
    out.sort(key=lambda r: str(r.get("at") or ""))
    return out


def _event_for_action(rec, contact_key, step_key, channel):
    """The confirming event behind one action, for the fields touches drop.

    `account.touches` returns a trimmed view and does not carry
    `scheduled_email_id`, `campaign_id` or `evidence_ids`. Those are what
    join an action to provider truth and to the evidence it was written
    from, so they are read from the event itself.
    """
    found = None
    for entry in rec.get("events") or []:
        if entry.get("type") not in touch.CONFIRMING_EVENTS:
            continue
        if entry.get("contact") != contact_key:
            continue
        if channel and entry.get("channel") != channel:
            continue
        if step_key and entry.get("step") != step_key:
            continue
        found = found or entry
        # A later event may carry an identifier the first did not.
        for field in ("scheduled_email_id", "campaign_id", "evidence_ids",
                      "sender_account_id", "lead_id", "provider"):
            if entry.get(field) and not found.get(field):
                found = {**found, field: entry[field]}
    return found or {}


def _reply_state(rec, contact_key, at=None):
    """What this person said, and when, from `account.replies`."""
    rows = account.replies(rec, contact_key)
    if at:
        rows = [r for r in rows if str(r.get("at") or "") >= str(at)]
    if not rows:
        return {"replied": False, "at": None, "classification": None,
                "positive": False, "negative": False}
    classified = {r.get("classification") for r in rows}
    return {
        "replied": True,
        "at": rows[0].get("at"),
        "classification": next((c for c in classified if c), None),
        "positive": any(r.get("positive") for r in rows),
        "negative": bool({"negative", "unsubscribe"} & classified),
    }


def _meeting(rec, contact_key):
    for entry in rec.get("events") or []:
        if (entry.get("type") == events.MEETING_MARKED
                and entry.get("contact") == contact_key):
            return {"booked": True, "at": entry.get("at")}
    return {"booked": False, "at": None}


def observation_of(rec, contact, action, campaign=None, provider_rows=None):
    """One provider-backed action, joined to everything a question needs."""
    contact_key = contact.get("key")
    step_key = action.get("step")
    channel = action.get("channel")
    entry = _event_for_action(rec, contact_key, step_key, channel)
    provider_row = (provider_rows or {}).get(
        str(entry.get("scheduled_email_id") or ""))

    # --- evidence. Read from the event first so the day somebody records it
    # at send time this reads the recorded value without a second change.
    evidence_ids = list(entry.get("evidence_ids") or [])
    decision = contact.get("personalization") or {}
    if evidence_ids:
        evidence_source = RECORDED
    elif decision.get("selected_evidence_ids"):
        evidence_ids = list(decision["selected_evidence_ids"])
        evidence_source = INFERRED
    else:
        evidence_source = ABSENT
    evidence = {
        "ids": evidence_ids,
        "level": decision.get("level"),
        "quality": decision.get("quality"),
        "freshness": decision.get("freshness"),
        "source_url": decision.get("source_url"),
        "provenance": evidence_source,
    }

    # --- the message. Provider truth where it exists, because it is what was
    # rendered rather than what is stored.
    copy = _step_copy(rec, contact_key, step_key)
    if provider_row:
        message = {"subject_chars": provider_row.get("subject_chars"),
                   "body_chars": provider_row.get("body_chars"),
                   "body_words": provider_row.get("body_words"),
                   "provenance": ATTRIBUTED}
    elif copy.get("body"):
        body = str(copy.get("body") or "")
        message = {"subject_chars": len(str(copy.get("subject") or "")),
                   "body_chars": len(body), "body_words": len(body.split()),
                   "provenance": INFERRED}
    else:
        message = {"subject_chars": None, "body_chars": None,
                   "body_words": None, "provenance": ABSENT}

    variant = {"variant_id": action.get("variant_id"),
               "style": action.get("variant_style"),
               "version": action.get("variant_version"),
               "provenance": (RECORDED if action.get("variant_id") else ABSENT)}

    # Two different senders, and the distinction is `touch.py`'s. `sender_id`
    # is the human a message may NAME; `sender_account_id` is the inbox it
    # left from. Either one recorded on the event answers "who sent this", so
    # either one is enough for RECORDED - but only `sender_id` licenses copy,
    # which is `touch.context`'s question and not this one.
    sender_account_id = (entry.get("sender_account_id")
                         or (provider_row or {}).get("sender_account_id"))
    sender = {"sender_id": action.get("sender_id"),
              "account_id": action.get("account_id"),
              "sender_account_id": sender_account_id,
              "sender_email": (provider_row or {}).get("sender_email"),
              "nameable": bool(action.get("sender_id")),
              "provenance": (
                  RECORDED if action.get("sender_id")
                  or entry.get("sender_account_id")
                  else ATTRIBUTED if sender_account_id else ABSENT)}

    reply = _reply_state(rec, contact_key, at=action.get("at"))
    bounced = any(e.get("type") == events.EMAIL_BOUNCED
                  and e.get("contact") == contact_key
                  for e in rec.get("events") or [])
    delivered = any(e.get("type") == events.EMAIL_DELIVERED
                    and e.get("contact") == contact_key
                    for e in rec.get("events") or [])

    return {
        "client": rec.get("client"),
        "account": {"record_id": rec.get("id"), "domain": rec.get("domain"),
                    "company": rec.get("company")},
        # THE EVENT FIRST, THE CONTACT ONLY AS A FALLBACK.
        #
        # Persona and angle live on the contact and a later generation
        # overwrites them, so reading the contact answers "what do we think
        # today" when the question is "what did we send". `push.mark_pushed`
        # pins both onto the confirming event at send time, and a pinned
        # value is a measurement rather than a reconstruction - so it is
        # RECORDED where it exists and INFERRED where it does not, which is
        # every send made before that producer was wired.
        "person": {"contact_key": contact_key,
                   "persona": (entry.get("persona")
                               or contact.get("persona")),
                   "angle": entry.get("angle") or contact.get("angle"),
                   "title": contact.get("title"),
                   "provenance": (
                       RECORDED if entry.get("persona")
                       else INFERRED if contact.get("persona") else ABSENT)},
        "channel": channel,
        "step": step_key,
        "day": action.get("day"),
        "campaign": {
            "campaign_id": (campaign or {}).get("campaign_id"),
            "provider": entry.get("provider"),
            "provider_campaign_id": (entry.get("campaign_id")
                                     or (campaign or {}).get("bison_campaign_id")
                                     or (campaign or {}).get(
                                         "heyreach_campaign_id")),
        },
        "sender": sender,
        "variant": variant,
        "evidence": evidence,
        "message": message,
        "at": action.get("at"),
        "state": action.get("state"),
        "provider_status": (provider_row or {}).get("raw_status"),
        "provider_observed_at": (provider_row or {}).get("at"),
        # Three answers, not two. `not_reported` is the honest one for email:
        # EmailBison's queue reports `sent`, which is not a delivery.
        "delivery": (BOUNCED if bounced else CONFIRMED if delivered
                     else NOT_REPORTED),
        "bounced": bounced,
        "reply": reply,
        "meeting": _meeting(rec, contact_key),
        "stop_reason": cadenceexposure.termination(rec, contact),
        # Opens are recorded and never optimised for - `variants.OBJECTIVES`
        # leaves them out on purpose. The flag is here because 0 opens with
        # tracking off is not a fact about the reader.
        "opens": (provider_row or {}).get("opens"),
        "open_tracking": (provider_row or {}).get("open_tracking"),
        "attributable": bool(provider_row) or bool(entry.get("scheduled_email_id")),
        "confidence": _worst(evidence["provenance"], message["provenance"],
                             variant["provenance"], sender["provenance"]),
    }


def observations(recs=None, campaign_rows=None, provider_rows=None):
    """Every provider-backed action in the estate, oldest first."""
    recs = store.load() if recs is None else recs
    owners = _campaign_index(campaign_rows)
    provider = _provider_index(provider_rows)
    out = []
    for rec in recs:
        campaign = owners.get(rec.get("id"))
        for contact in account.contacts_of(rec):
            for action in _actions(rec, contact.get("key")):
                out.append(observation_of(rec, contact, action, campaign,
                                          provider))
    out.sort(key=lambda r: str(r.get("at") or ""))
    return out


# --------------------------------------------------------- the questions
#
# Each names the cell it groups by, the unit the denominator counts, and the
# metadata that has to be on the event BEFORE the sends happen. The last
# column is the whole point of writing this down now.

ACTION = "action"
PERSON = "person"
ACCOUNT = "account"

NOT_INSTRUMENTED = "not_instrumented"

# A unit this question does not apply to at all. Distinct from a unit whose
# dimension is missing: a contact's FIRST touch has no spacing, and counting
# it as "spacing was not recorded" would report an instrumentation gap that
# is not there. Three negatives, three different fixes.
NOT_APPLICABLE = "__not_applicable__"

# How message length is grouped. Three buckets rather than a regression,
# because a regression on eleven sends is a straight line through noise.
LENGTH_BUCKETS = ((60, "under_60_words"), (120, "60_to_120_words"))
SPACING_BUCKETS = ((3, "within_3_days"), (7, "4_to_7_days"))
COUNT_BUCKETS = ((1, "1_stakeholder"), (2, "2_stakeholders"))


def _bucket(value, buckets, above):
    if value is None:
        return None
    for edge, label in buckets:
        if value <= edge:
            return label
    return above


QUESTIONS = (
    {
        "key": "persona",
        "question": "Which personas reply?",
        "unit": PERSON,
        "cells_expected": 4,
        "objective": variants.POSITIVE_REPLIES,
        "groups_by": "person.persona",
        "needs": (
            "the persona the message was written to, pinned to the send",),
        "why": "persona lives on the contact and a later run can change it, "
               "so a persona read at evaluation time may not be the one the "
               "message was written to",
    },
    {
        "key": "angle",
        "question": "Which angles work?",
        "unit": PERSON,
        "cells_expected": 5,
        "objective": variants.POSITIVE_REPLIES,
        "groups_by": "person.angle",
        "needs": ("the angle the message led with, pinned to the send",),
        "why": "same as persona: the angle is a mutable field on the contact",
    },
    {
        "key": "evidence",
        "question": "Which evidence creates replies?",
        "unit": ACTION,
        "cells_expected": 4,
        "objective": variants.REPLIES,
        "groups_by": "evidence.level",
        "needs": ("evidence_ids on the confirming event",),
        "why": "the personalization decision is stored on the CONTACT and is "
               "overwritten by the next generation, so the evidence a sent "
               "message used is not recoverable afterwards. This is the one "
               "dimension that is lost rather than merely diluted",
    },
    {
        "key": "length",
        "question": "Does message length change the reply rate?",
        "unit": ACTION,
        "cells_expected": 3,
        "objective": variants.REPLIES,
        "groups_by": "message.body_words",
        "needs": ("the length of what the provider actually rendered",),
        "why": "the provider's scheduled-email row carries the rendered copy, "
               "so length is provider truth where an observation exists",
    },
    {
        "key": "channel_first",
        "question": "Email first or LinkedIn first?",
        "unit": PERSON,
        "cells_expected": 2,
        "objective": variants.REPLIES,
        "groups_by": "the channel of this person's first confirmed touch",
        "needs": ("channel and timestamp on every confirming event",),
        "why": "both are already on the event",
    },
    {
        "key": "spacing",
        "question": "How far apart should touches be?",
        "unit": ACTION,
        "cells_expected": 3,
        "objective": variants.REPLIES,
        "groups_by": "days since this contact's previous confirmed touch",
        "needs": ("a timestamp on every confirming event",),
        "why": "already on the event, and dated by the PROVIDER's clock "
               "rather than by when a poll ran",
    },
    {
        "key": "stakeholders",
        "question": "How many stakeholders per account should be contacted?",
        "unit": ACCOUNT,
        "cells_expected": 3,
        "objective": variants.REPLIES,
        "groups_by": "distinct contacts touched at the account",
        "needs": ("record id and contact key on every confirming event",),
        "why": "already on the event",
    },
    {
        "key": "penetration",
        "question": "Where does extra account penetration stop helping?",
        "unit": ACCOUNT,
        "cells_expected": 3,
        "objective": variants.POSITIVE_REPLIES,
        "groups_by": "distinct contacts touched at the account",
        "needs": ("record id and contact key on every confirming event",
                  "a classified reply, so positive is separable from any"),
        "why": "the marginal answer needs the positive rate per additional "
               "stakeholder, not the reply rate",
    },
)

QUESTION = {q["key"]: q for q in QUESTIONS}


def _cell(key, row, context):
    """Which cell this row falls in for one question, or None if unknown."""
    if key == "persona":
        return row["person"].get("persona")
    if key == "angle":
        return row["person"].get("angle")
    if key == "evidence":
        return row["evidence"].get("level")
    if key == "length":
        return _bucket(row["message"].get("body_words"), LENGTH_BUCKETS,
                       "over_120_words")
    if key == "channel_first":
        return context.get("first_channel")
    if key == "spacing":
        if context.get("is_first"):
            return NOT_APPLICABLE
        return _bucket(context.get("gap_days"), SPACING_BUCKETS,
                       "over_7_days")
    if key in ("stakeholders", "penetration"):
        return _bucket(context.get("stakeholders"), COUNT_BUCKETS,
                       "3_or_more_stakeholders")
    raise KeyError(key)


def _context(rows):
    """Per-row facts that need the rows either side of it.

    First channel, gap since the previous touch on this contact, and how
    many distinct people were touched at the account. None of these is a
    field on an event; all of them are derived from several, which is why
    they are computed once here rather than in each question.
    """
    by_contact, by_account = {}, {}
    for row in rows:
        contact = (row["account"]["record_id"], row["person"]["contact_key"])
        by_contact.setdefault(contact, []).append(row)
        by_account.setdefault(row["account"]["record_id"], set()).add(
            row["person"]["contact_key"])

    out = {}
    for contact, mine in by_contact.items():
        mine.sort(key=lambda r: str(r.get("at") or ""))
        first_channel = mine[0].get("channel")
        previous = None
        for index, row in enumerate(mine):
            out[id(row)] = {
                "first_channel": first_channel,
                "is_first": index == 0,
                "gap_days": _days_between(previous, row.get("at")),
                "stakeholders": len(by_account[row["account"]["record_id"]]),
            }
            previous = row.get("at")
    return out


def _days_between(earlier, later):
    if not earlier or not later:
        return None
    try:
        from datetime import datetime
        a = datetime.fromisoformat(str(earlier).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(later).replace("Z", "+00:00"))
    except ValueError:
        # Unparseable is unknown, never zero. A zero would put every
        # unreadable timestamp in the "same day" bucket.
        return None
    return abs((b - a).days)


def _outcome(row, objective):
    if objective == variants.MEETINGS:
        return bool(row["meeting"]["booked"])
    if objective == variants.POSITIVE_REPLIES:
        return bool(row["reply"]["positive"])
    return bool(row["reply"]["replied"])


def _units(question, rows, context):
    """(cell, outcome) per unit of this question's denominator.

    For an ACTION question a reply is credited to the last confirmed touch
    before it - the same last-touch convention `variants.results_from` uses,
    and the same caveat applies: it is a reporting convention, not a claim
    about cause.
    """
    key, unit, objective = question["key"], question["unit"], question["objective"]
    if unit == ACTION:
        out = []
        credited = _last_touch_credit(rows, objective)
        for row in rows:
            out.append((_cell(key, row, context.get(id(row), {})),
                        id(row) in credited))
        return out

    groups = {}
    for row in rows:
        if unit == PERSON:
            mark = (row["account"]["record_id"], row["person"]["contact_key"])
        else:
            mark = row["account"]["record_id"]
        groups.setdefault(mark, []).append(row)

    out = []
    for mine in groups.values():
        mine.sort(key=lambda r: str(r.get("at") or ""))
        cell = _cell(key, mine[0], context.get(id(mine[0]), {}))
        out.append((cell, any(_outcome(r, objective) for r in mine)))
    return out


def _last_touch_credit(rows, objective):
    """The id() of each action a unit's outcome is credited to."""
    by_contact = {}
    for row in rows:
        by_contact.setdefault(
            (row["account"]["record_id"], row["person"]["contact_key"]),
            []).append(row)
    credited = set()
    for mine in by_contact.values():
        mine.sort(key=lambda r: str(r.get("at") or ""))
        winner = next((r for r in mine if _outcome(r, objective)), None)
        if winner is None:
            continue
        outcome_at = str(winner["reply"].get("at")
                         or winner["meeting"].get("at") or "")
        before = [r for r in mine if str(r.get("at") or "") <= outcome_at]
        credited.add(id(before[-1] if before else mine[0]))
    return credited


def minimum_for(question, config=None):
    """The smallest sample that would make this question's answer mean
    something, stated in the evaluator's own thresholds."""
    rules = variants.settings(config)
    cells = int(question["cells_expected"])
    return {
        "cells": cells,
        "per_cell": rules["minimum_per_variant"],
        "total_units": cells * int(rules["minimum_per_variant"]),
        "outcomes": rules["minimum_outcomes"],
        "lift": rules["minimum_lift"],
        "why": ("borrowed from src/variants.py, which is the evaluator this "
                "calls. Nothing here loosens them"),
    }


def answer(key, rows=None, config=None, context=None):
    """What this question can honestly be said to show. Usually: nothing.

    Three different negatives, kept apart because their fixes are opposite:

        no rows at all            nothing has been sent
        rows, dimension absent    NOT_INSTRUMENTED - change the producer
        rows, dimension present   INSUFFICIENT_DATA - wait, or send more
    """
    question = QUESTION[key]
    rows = observations() if rows is None else rows
    minimum = minimum_for(question, config)
    context = _context(rows) if context is None else context

    base = {"key": key, "question": question["question"],
            "unit": question["unit"], "groups_by": question["groups_by"],
            "objective": question["objective"],
            "objective_label": variants.OBJECTIVE_LABEL[question["objective"]],
            "minimum": minimum, "needs": list(question["needs"]),
            "why_metadata": question["why"]}

    if not rows:
        return {**base, "state": variants.INSUFFICIENT_DATA, "cells": [],
                "units": 0, "outcomes": 0, "unassignable": 0,
                "why": "no confirmed provider-backed action exists yet"}

    units = _units(question, rows, context)
    applicable = [pair for pair in units if pair[0] != NOT_APPLICABLE]
    placed = [(cell, outcome) for cell, outcome in applicable if cell]
    not_applicable = len(units) - len(applicable)
    unassignable = len(applicable) - len(placed)

    if not applicable:
        return {**base, "state": variants.INSUFFICIENT_DATA, "cells": [],
                "units": 0, "outcomes": 0, "unassignable": 0,
                "not_applicable": not_applicable,
                "why": (f"none of the {len(units)} unit(s) is one this "
                        f"question applies to yet")}

    if not placed:
        return {**base, "state": NOT_INSTRUMENTED, "cells": [],
                "units": len(applicable), "outcomes": 0,
                "unassignable": unassignable,
                "not_applicable": not_applicable,
                "why": (f"{len(applicable)} unit(s) this question applies to "
                        f"exist and none carries {question['groups_by']}, so "
                        f"it cannot be asked of them however many there are. "
                        f"Record it on the confirming event")}

    results = {}
    for cell, outcome in placed:
        row = results.setdefault(cell, {"exposures": 0,
                                        question["objective"]: 0})
        row["exposures"] += 1
        if outcome:
            row[question["objective"]] += 1

    # The evaluator, not a copy of it. A cell is presented to
    # `variants.evaluate` as a variant because that is exactly what it is:
    # one arm of a comparison with an exposure count and an outcome count.
    node = {"type": None, "objective": question["objective"],
            "variants": [{"variant_id": cell, "style": cell,
                          "status": variants.ACTIVE}
                         for cell in sorted(results)]}
    verdict = variants.evaluate(node, results, config,
                                objective=question["objective"])

    return {**base, "state": verdict["state"],
            "state_label": variants.STATE_LABEL.get(verdict["state"],
                                                    verdict["state"]),
            "why": verdict["why"], "leader": verdict.get("leader"),
            "cells": verdict["rows"], "units": len(applicable),
            "outcomes": sum(r[question["objective"]] for r in results.values()),
            "unassignable": unassignable,
            "not_applicable": not_applicable}


def answers(rows=None, config=None):
    rows = observations() if rows is None else rows
    context = _context(rows)
    return [answer(q["key"], rows, config, context) for q in QUESTIONS]


def readiness(rows=None, config=None):
    """Which questions the current instrumentation can ever answer.

    Separate from `answers` on purpose. "Not enough data" is a schedule
    problem and "the field is never written" is a code problem, and a
    dashboard that shows both as one grey box gets the second one ignored
    for a quarter.
    """
    rows = observations() if rows is None else rows
    out = []
    for found in answers(rows, config):
        out.append({
            "key": found["key"],
            "question": found["question"],
            "instrumented": found["state"] != NOT_INSTRUMENTED,
            "state": found["state"],
            "units": found["units"],
            "needed_units": found["minimum"]["total_units"],
            "needed_outcomes": found["minimum"]["outcomes"],
            "needs": found["needs"],
            "why": found["why"],
        })
    return out


# ------------------------------------------------- the production run report
#
# The stage names the operator asked for, each read from canonical state and
# each naming the state it is read from. A stage nothing can observe says so
# rather than reporting zero: "nobody replied" and "replies are not wired" are
# different facts and only one of them is a result.

STAGES = ("DATASET", "ICP PASS", "CONTACTS", "EMAIL READY", "LINKEDIN READY",
          "RESEARCH READY", "CAMPAIGN READY", "STAGED", "ACTIVE", "SCHEDULED",
          "SENT", "DELIVERED", "BOUNCED", "REPLIED", "POSITIVE", "MEETINGS")

# Counters that mean somebody should look. Read from the process-level
# observability counters, which is where things that belong to no record land.
SAFETY_COUNTERS = (events.WEBHOOK_REJECTED, events.EVENT_UNKNOWN,
                   events.CAMPAIGN_MAPPING_FAILED, events.SLACK_POST_FAILED)


# The dimensions an observation carries and where each is looked for. Named
# so "what is missing" is a list rather than a search.
DIMENSIONS = ("evidence", "message", "variant", "sender", "person")


def missing_dimensions(rows):
    """How many actions hold nothing at all for each dimension.

    A count rather than a boolean, because "one of our two sends has no
    variant id" and "neither does" are different sizes of the same problem.
    """
    out = {}
    for name in DIMENSIONS:
        absent = sum(1 for row in rows
                     if (row.get(name) or {}).get("provenance") == ABSENT)
        if absent:
            out[name] = absent
    return out


def _stage(name, count, truth, observable=True, note=None):
    return {"stage": name, "count": count, "truth": truth,
            "observable": observable, "note": note}


def run_report(client=None, recs=None, campaign_rows=None, config=None):
    """Every stage of one production run, from canonical state only.

    Nothing here is typed in. A number that cannot be derived is absent with
    a reason, which is what makes the document re-runnable tomorrow and
    comparable with today.
    """
    from . import funnel

    recs = store.load() if recs is None else recs
    campaign_rows = campaigns.load() if campaign_rows is None else campaign_rows
    if client:
        recs = [r for r in recs if r.get("client") == client]
        campaign_rows = [c for c in campaign_rows if c.get("client") == client]

    counted = funnel.counts(recs)
    rows = observations(recs, campaign_rows)
    provider = leadobserve.load()
    ids = {r.get("id") for r in recs}

    scheduled = {}
    for row in provider:
        if row.get("scheduled_email_id") is None:
            continue
        if row.get("record_id") and row["record_id"] not in ids:
            continue
        scheduled[str(row["scheduled_email_id"])] = row
    still_scheduled = sum(1 for row in scheduled.values()
                          if row.get("state") == leadobserve.SCHEDULED)

    staged = {(row.get("provider") or leadobserve.HEYREACH,
               str(row.get("campaign_id")),
               str(row.get("provider_lead_id")))
              for row in provider
              if row.get("provider_lead_id") is not None
              and (not row.get("record_id") or row["record_id"] in ids)}

    kinds = {}
    for rec in recs:
        for entry in rec.get("events") or []:
            kinds[entry.get("type")] = kinds.get(entry.get("type"), 0) + 1

    active = [c for c in campaign_rows
              if (c.get("bison_campaign_id") or c.get("heyreach_campaign_id"))
              and c.get("status") not in ("draft", "paused", "completed")]
    disagreements = _disagreements(campaign_rows, provider)

    stages = [
        _stage("DATASET", counted["input_domains"], "queue rows"),
        _stage("ICP PASS", counted["qualified"], "verdict.icp_status"),
        _stage("CONTACTS", counted["people_found"], "rec.contacts on qualified"),
        _stage("EMAIL READY", counted["emails_2_of_2_verified"],
               "contact.verification.confirmation_count >= 2",
               note="two independent verifier confirmations, not one"),
        _stage("LINKEDIN READY", counted["linkedin_found"], "contact.linkedin"),
        _stage("RESEARCH READY", counted["researched"], "rec.research"),
        _stage("CAMPAIGN READY", counted["campaign_ready"],
               "eligibility.decide == eligible"),
        _stage("STAGED", len(staged), "work/lead-observations.jsonl",
               note="leads the PROVIDER holds. The action ledger reads "
                    f"{counted['provider_staged']} because staging done by a "
                    "person in a vendor UI reserves nothing here"),
        # Canonical state, never the provider's word. A provider status read
        # once and stored ages: HeyReach 594061 was last observed IN_PROGRESS
        # and has been paused since, by a confirmed write. So the count is
        # what this system has approved to be running, and where the provider
        # last said otherwise that is reported as a disagreement rather than
        # silently preferred in either direction.
        _stage("ACTIVE", len(active),
               "campaigns.jsonl bound to a provider campaign and not draft, "
               "paused or completed",
               note=(f"{len(disagreements)} campaign(s) where the provider "
                     f"last said something else" if disagreements else None)),
        _stage("SCHEDULED", still_scheduled,
               "EmailBison scheduled-email rows still in state scheduled"),
        _stage("SENT", len(rows), "confirmed touches in the event log",
               note="push_marked, email_delivered and linkedin_connected. "
                    "push_prepared is excluded by name"),
        _stage("DELIVERED", kinds.get(events.EMAIL_DELIVERED, 0),
               "rec.events email_delivered", observable=False,
               note="no surface reports delivery. EmailBison's queue reports "
                    "`sent`, which says it handed the message to SMTP and "
                    "nothing about a mailbox accepting it"),
        _stage("BOUNCED", kinds.get(events.EMAIL_BOUNCED, 0),
               "rec.events email_bounced",
               note="classified off the /replies feed and off the "
                    "scheduled-email queue"),
        _stage("REPLIED", kinds.get(events.REPLY_RECEIVED, 0),
               "rec.events reply_received"),
        _stage("POSITIVE", kinds.get(events.POSITIVE_REPLY_DETECTED, 0),
               "rec.events positive_reply_detected"),
        _stage("MEETINGS", kinds.get(events.MEETING_MARKED, 0),
               "rec.events meeting_marked", observable=False,
               note="nothing observes a booking; a person marks it"),
    ]

    return {
        "client": client,
        "at": store.now(),
        "stages": stages,
        "campaigns": [_campaign_row(c) for c in campaign_rows],
        "campaign_disagreements": disagreements,
        "senders": _seats(campaign_rows),
        "safety": _safety(recs, campaign_rows),
        "observations": {
            "actions": len(rows),
            "attributable": sum(1 for r in rows if r["attributable"]),
            "by_confidence": {name: sum(1 for r in rows
                                        if r["confidence"] == name)
                              for name in PROVENANCE
                              if any(r["confidence"] == name for r in rows)},
            # Which dimension nothing holds, per action. This is the line that
            # says what to change before the next send rather than after the
            # next hundred: a touch written today without a variant id is a
            # message whose result is unattributable for ever.
            "missing": missing_dimensions(rows),
        },
        "questions": readiness(rows, config),
        # Two lines that are deliberately not numbers. Neither has a canonical
        # source: a bug is found in a conversation and fixed in a commit, and a
        # replay is a simulation nobody records running. Inventing either from
        # the event log would be the exact defect this whole layer is about.
        "bugs": {"observable": False,
                 "why": "no canonical state records a defect found or fixed. "
                        "git history is the source and it is not queue state"},
        "replays": {"observable": False,
                    "why": "src/replaysim.py simulates against a record and "
                           "writes nothing, so a count of replays run has "
                           "nowhere to be read from"},
    }


def _campaign_row(campaign):
    return {
        "campaign_id": campaign.get("campaign_id"),
        "client": campaign.get("client"),
        "status": campaign.get("status"),
        "records": len(campaign.get("record_ids") or []),
        "bison_campaign_id": campaign.get("bison_campaign_id"),
        "heyreach_campaign_id": campaign.get("heyreach_campaign_id"),
        "launch": (campaign.get("launch") or {}).get("state"),
        "approved": bool(campaign.get("approval")),
    }


# What each provider calls a campaign that is sending. Words, not guesses:
# EmailBison answers `active` and HeyReach answers `IN_PROGRESS`.
PROVIDER_RUNNING = frozenset({"active", "in_progress", "inprogress",
                              "running", "started"})

# What this system's own campaign status means by "running".
LOCAL_STOPPED = frozenset({"draft", "paused", "completed", "rejected"})


def _disagreements(campaign_rows, provider_rows):
    """Campaigns where the provider last said something else.

    Neither side wins here and that is deliberate. A stored provider status
    ages - it is what the provider said when somebody last looked - and
    canonical state can be behind a change an operator made in a vendor UI.
    Campaign 451 is the live example: approved and staged, canonical status
    `draft`, and EmailBison answering `active` with a send queued for Monday.
    Reporting either number alone would hide the thing a person has to act on.
    """
    latest = {}
    for row in provider_rows:
        key = (row.get("provider") or leadobserve.HEYREACH,
               str(row.get("campaign_id")))
        if row.get("campaign_status") is None:
            continue
        held = latest.get(key)
        if held is None or str(row.get("at") or "") >= str(held.get("at") or ""):
            latest[key] = row

    out = []
    for campaign in campaign_rows:
        for provider, bound in ((leadobserve.EMAILBISON,
                                 campaign.get("bison_campaign_id")),
                                (leadobserve.HEYREACH,
                                 campaign.get("heyreach_campaign_id"))):
            if not bound:
                continue
            seen = latest.get((provider, str(bound)))
            if seen is None:
                continue
            said = str(seen.get("campaign_status") or "").strip().lower()
            running_there = said in PROVIDER_RUNNING
            running_here = campaign.get("status") not in LOCAL_STOPPED
            if running_there == running_here:
                continue
            out.append({
                "campaign_id": campaign.get("campaign_id"),
                "provider": provider,
                "provider_campaign_id": bound,
                "provider_status": seen.get("campaign_status"),
                "provider_observed_at": seen.get("at"),
                "local_status": campaign.get("status"),
                "why": ("the provider says it is running and this system does "
                        "not" if running_there else
                        "this system says it is running and the provider does "
                        "not"),
                "note": "a stored provider status is what the provider said "
                        "when somebody last looked, not what it says now",
            })
    return out


def _seats(campaign_rows):
    """Senders and seats, from what the campaigns are actually bound to.

    Read from the campaign rather than from the sender inventory on purpose:
    an inventory says who exists, and this report is about who is sending.
    """
    email, linkedin = set(), set()
    for campaign in campaign_rows:
        senders = campaign.get("senders") or {}
        for entry in senders.get("email") or []:
            email.add(str(entry.get("provider_account_id")
                          or entry.get("id") or entry))
        for entry in senders.get("linkedin") or []:
            linkedin.add(str(entry.get("id")
                             or entry.get("provider_account_id") or entry))
    return {"email_senders": sorted(email), "linkedin_seats": sorted(linkedin),
            "email_sender_count": len(email), "seat_count": len(linkedin),
            "truth": "campaigns.jsonl senders block"}


def _safety(recs, campaign_rows):
    """Anything that should stop somebody, counted rather than narrated."""
    from . import killswitch, observability

    counts = observability.counts()
    incidents = [{"what": name, "count": counts[name]}
                 for name in SAFETY_COUNTERS if counts.get(name)]
    paused = [c.get("campaign_id") for c in campaign_rows
              if c.get("status") == "paused"]
    held = [r.get("id") for r in recs if r.get("paused")]
    suppressed = [r.get("id") for r in recs
                  if (r.get("suppression") or {}).get("suppressed")]
    global_state = killswitch.global_state()
    return {
        "incidents": incidents,
        "kill_switch": {"sending": global_state.get("sending"),
                        "why": global_state.get("why")},
        "campaigns_paused": paused,
        "accounts_held": held,
        "accounts_suppressed": suppressed,
        "truth": "work/observability.jsonl counters, killswitch state, and "
                 "the paused and suppression fields on canonical state",
    }


# ------------------------------------------------------------- rendering

def render(report):
    lines = [f"PRODUCTION RUN  client={report.get('client') or 'all'}  "
             f"at={report['at']}", ""]
    for row in report["stages"]:
        mark = "" if row["observable"] else "   NOT OBSERVABLE"
        lines.append(f"  {row['stage']:<16}{row['count']:>8}{mark}")
        if row.get("note"):
            lines.append(f"                    {row['note']}")
    lines += ["", "CAMPAIGNS"]
    for row in report["campaigns"]:
        lines.append(f"  {str(row['campaign_id']):<36} {row['status']:<18} "
                     f"{row['records']:>3} record(s)  "
                     f"bison={row['bison_campaign_id']} "
                     f"heyreach={row['heyreach_campaign_id']}")
    for row in report["campaign_disagreements"]:
        lines.append(f"  DISAGREEMENT {row['campaign_id']}: here "
                     f"{row['local_status']!r}, {row['provider']} said "
                     f"{row['provider_status']!r} at "
                     f"{row['provider_observed_at']}")
    seats = report["senders"]
    lines += ["", f"SENDERS  {seats['email_sender_count']} email, "
                  f"{seats['seat_count']} LinkedIn seat(s)"]
    safety = report["safety"]
    lines += ["", f"SAFETY   sending={safety['kill_switch']['sending']}  "
                  f"{len(safety['incidents'])} incident type(s), "
                  f"{len(safety['campaigns_paused'])} campaign(s) paused, "
                  f"{len(safety['accounts_held'])} account(s) held"]
    for row in safety["incidents"]:
        lines.append(f"  {row['what']:<28}{row['count']:>6}")
    seen = report["observations"]
    lines += ["", f"OBSERVATIONS  {seen['actions']} action(s), "
                  f"{seen['attributable']} attributable to a provider row"]
    for name, count in sorted(seen["missing"].items()):
        lines.append(f"  no {name} recorded on {count} of {seen['actions']} "
                     f"action(s)")
    lines += ["", "QUESTIONS"]
    for row in report["questions"]:
        state = row["state"] if row["instrumented"] else "NOT INSTRUMENTED"
        lines.append(f"  {row['question']:<52} {state}")
        lines.append(f"      {row['units']} of {row['needed_units']} unit(s), "
                     f"{row['needed_outcomes']} outcome(s) needed")
    lines += ["",
              f"BUGS     not observable: {report['bugs']['why']}",
              f"REPLAYS  not observable: {report['replays']['why']}"]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.outcomes",
                                description=__doc__)
    p.add_argument("--client")
    p.add_argument("--observations", action="store_true")
    p.add_argument("--questions", action="store_true")
    p.add_argument("--run-report", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    recs = store.load()
    if a.client:
        recs = [r for r in recs if r.get("client") == a.client]

    if a.observations:
        rows = observations(recs)
        print(json.dumps(rows, indent=1, default=str) if a.json
              else _render_observations(rows))
        return 0

    if a.questions:
        found = answers(observations(recs))
        if a.json:
            print(json.dumps(found, indent=1, default=str))
            return 0
        for row in found:
            print(f"{row['question']}")
            print(f"  {row['state'].upper()}: {row['why']}")
            print(f"  minimum: {row['minimum']['total_units']} unit(s) across "
                  f"{row['minimum']['cells']} cell(s), "
                  f"{row['minimum']['outcomes']} outcome(s)")
        return 0

    report = run_report(a.client, recs)
    print(json.dumps(report, indent=1, default=str) if a.json
          else render(report))
    return 0


def _render_observations(rows):
    if not rows:
        return ("no confirmed provider-backed action exists yet. That is a "
                "result, not an empty screen")
    out = []
    for row in rows:
        out.append(f"{row['at']}  {row['account']['record_id']}/"
                   f"{row['person']['contact_key']}  {row['channel']}/"
                   f"{row['step']}  {row['state']}  "
                   f"persona={row['person']['persona']} "
                   f"angle={row['person']['angle']}  "
                   f"delivery={row['delivery']}  "
                   f"confidence={row['confidence']}")
    return "\n".join(out)


if __name__ == "__main__":
    raise SystemExit(main())
