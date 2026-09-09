#!/usr/bin/env python3
"""The account is the unit of outreach, not the contact.

## Why this module exists

`src/touch.py` answers "what has happened to this contact". That was the right
question while a campaign was one person, one email sender, one LinkedIn
sender, one linear cadence. It is the wrong question for account-based
outreach, where a single company is worked by several humans across several
channels against several decision makers at once.

The question this module answers is:

    What has Resonate done at this company, by whom, to whom, on what
    channel, when, and how sure are we?

Everything downstream - what a message may claim, whether a fifth touch this
week is too many, whether the CFO may be activated because the COO referred
us - reads from one graph rather than from five contact-shaped views that can
disagree with each other.

## The graph is derived, never stored

`graph()` reads the record's own event log and the sender roster and builds
the answer. There is no second copy of the truth to fall out of step. That
costs a walk over the events each time and buys the property that matters:
the account view and the contact view cannot disagree, because one is a
projection of the other.

## Confirmed means confirmed

The state vocabulary is `touch.py`'s, unchanged and deliberately not
re-derived here: `planned`, `approved`, `payload_ready` are intentions.
`sent`, `delivered`, `replied`, `positive_reply` are things that happened.

Every account-level answer distinguishes the two, and every consumer that
asks "has this person been contacted" gets the confirmed set unless it
explicitly asks for the plan. A module that blurred them would let a message
say "my colleague emailed you last week" about an email still sitting in a
queue, which is the single failure this architecture exists to prevent.

## Referrals are recorded, never inferred

A referral edge exists because a reply was classified as one and a person or
a classifier named the target. Nothing here reads "Sarah handles this" out of
free text and creates an edge; `referrals()` returns what `events` recorded
and nothing else. An inferred referral is a fabricated introduction, and it
arrives in the prospect's inbox as "John suggested I reach out" when John did
no such thing.
"""
import collections

from . import assignment, events, senderidentity as si, touch

# The states that mean a thing happened, borrowed rather than restated. If
# `touch.py` ever changes its mind about what counts as confirmed, this module
# changes with it and no second definition drifts.
CONFIRMED = touch.CONFIRMED_STATES

# Which events put a touch on the graph at all, and what state each means.
#
# `touch.CONFIRMING_EVENTS` only maps the events that confirm, because that is
# the only question it needs. An account view has to show intent as well - a
# planned second approach to the CFO is exactly what an operator wants to see
# before it happens - so the planned events are mapped here too, and
# `confirmed` on each touch is what keeps the two apart.
TOUCH_EVENTS = dict(touch.CONFIRMING_EVENTS)
TOUCH_EVENTS[events.PUSH_PREPARED] = touch.PLANNED
TOUCH_EVENTS[events.DRAFT_APPROVED] = touch.APPROVED

# Decision-maker priority. A campaign says who to open with and who to
# escalate to; nothing here decides that on its own.
PRIMARY = "primary"
SECONDARY = "secondary"
TERTIARY = "tertiary"
REFERRED = "referral"
PRIORITIES = (PRIMARY, SECONDARY, TERTIARY, REFERRED)

# How a contact stands in the account right now.
ACTIVE = "active"
ENGAGED = "engaged"
PAUSED = "paused"
SUPPRESSED = "suppressed"
STOPPED = "stopped"
NOT_STARTED = "not_started"


def _sender_names(workspace, rows=None):
    """sender_id -> display name, once, so a timeline is not N lookups."""
    if not workspace:
        return {}
    return {s["sender_id"]: s.get("display_name") or s["sender_id"]
            for s in si.senders(workspace, rows)}


def contacts_of(rec):
    """Every decision maker on the record, selected or not.

    Unselected contacts are included deliberately. An account view that hid
    them would answer "who do we know at this company" wrongly, and knowing
    that a CFO exists but was not selected is exactly the kind of thing an
    operator escalating an account needs to see.
    """
    return list(rec.get("contacts") or [])


def touches(rec, contact_key=None, confirmed_only=False):
    """Every touch on the account, or on one contact, newest last.

    A touch is one attempt to reach one person on one channel by one human.
    It carries the sender recorded *on the event*, never the sender currently
    assigned - a reassignment must not rewrite who sent what.
    """
    found = []
    for entry in rec.get("events") or []:
        kind = entry.get("type")
        state = TOUCH_EVENTS.get(kind)
        if state is None:
            continue
        if contact_key and entry.get("contact") != contact_key:
            continue
        if confirmed_only and state not in CONFIRMED:
            continue
        found.append({
            "contact_key": entry.get("contact"),
            "channel": entry.get("channel"),
            "step": entry.get("step"),
            "day": entry.get("day"),
            "at": entry.get("at"),
            "state": state,
            "confirmed": state in CONFIRMED,
            "sender_id": entry.get("sender_id"),
            "account_id": entry.get("account_id"),
            # Which copy this touch actually carried. Recorded on the event
            # so a later allocation change cannot rewrite what was sent -
            # attribution reads this, never the current assignment.
            "variant_id": entry.get("variant_id"),
            "variant_style": entry.get("variant_style"),
            # Which *wording* of that variant. Editing a
            # variant's copy without this pools the results of
            # two different messages under one id.
            "variant_version": entry.get("variant_version"),
            "event": kind,
        })
    found.sort(key=lambda t: (str(t.get("at") or ""), t.get("day") or 0))
    return found


def replies(rec, contact_key=None):
    """Reply events, with their classification where one was recorded."""
    found = []
    for entry in rec.get("events") or []:
        if entry.get("type") not in (events.REPLY_RECEIVED,
                                     events.REPLY_CLASSIFIED,
                                     events.POSITIVE_REPLY_DETECTED):
            continue
        if contact_key and entry.get("contact") != contact_key:
            continue
        found.append({
            "contact_key": entry.get("contact"),
            "channel": entry.get("channel"),
            "at": entry.get("at"),
            "type": entry.get("type"),
            "classification": entry.get("classification"),
            "positive": entry.get("type") == events.POSITIVE_REPLY_DETECTED,
        })
    found.sort(key=lambda r: str(r.get("at") or ""))
    return found


def contact_name(rec, contact_key):
    """This decision maker's display name, falling back to their key.

    Screens and claim reasons both need it, and both were printing the raw
    key - "referred by john-smith" under a table whose next column says
    "John Smith". The key is the identity; the name is what a human reads.
    """
    for contact in contacts_of(rec):
        if contact.get("key") == contact_key:
            return contact.get("name") or contact_key
    return contact_key


def referrals(rec):
    """Recorded referral edges. Never inferred from reply text.

    An edge exists because `events.REFERRAL_RECORDED` was written with both
    ends named. Reading "Sarah handles this" out of a reply and creating an
    edge would manufacture an introduction that did not happen, and the next
    message would open by claiming it did.
    """
    found = []
    for entry in rec.get("events") or []:
        if entry.get("type") != events.REFERRAL_RECORDED:
            continue
        if not entry.get("contact") or not entry.get("referred_to"):
            continue
        found.append({
            "from_contact": entry.get("contact"),
            "to_contact": entry.get("referred_to"),
            "from_name": contact_name(rec, entry.get("contact")),
            "to_name": contact_name(rec, entry.get("referred_to")),
            "at": entry.get("at"),
            "evidence": entry.get("provider_event_id") or entry.get("note"),
            "channel": entry.get("channel"),
        })
    found.sort(key=lambda r: str(r.get("at") or ""))
    return found


def referred_by(rec, contact_key):
    """Who referred us to this person, if anybody did."""
    for edge in referrals(rec):
        if edge["to_contact"] == contact_key:
            return edge
    return None


def referred_to(rec, contact_key):
    """The most recent person this contact pointed us at, if anybody.

    The mirror of `referred_by`. A referral has two ends and both are asked
    about: "who sent us to Sarah" and "who did John send us to" are
    different questions and the second is the one a referral policy needs.
    """
    found = [e for e in referrals(rec) if e["from_contact"] == contact_key]
    return found[-1] if found else None


def graph(rec, workspace=None, rows=None, config=None):
    """The whole account, as one object.

    This is the canonical answer to every account-level question, and every
    screen, claim resolver and fatigue check reads it rather than walking the
    event log again with its own idea of what counts.
    """
    rows = si.load() if rows is None else rows
    names = _sender_names(workspace, rows)
    every_touch = touches(rec)
    every_reply = replies(rec)
    edges = referrals(rec)
    paused = rec.get("paused") or {}

    by_contact = collections.OrderedDict()
    for contact in contacts_of(rec):
        key = contact.get("key")
        mine = [t for t in every_touch if t["contact_key"] == key]
        theirs = [r for r in every_reply if r["contact_key"] == key]
        confirmed = [t for t in mine if t["confirmed"]]
        senders = assignment.describe(contact) or {}
        by_contact[key] = {
            "key": key,
            "name": contact.get("name"),
            "title": contact.get("title"),
            "persona": contact.get("persona"),
            "priority": contact.get("priority") or PRIMARY,
            "selected": bool(contact.get("selected")),
            "email": bool(contact.get("email")),
            "linkedin": bool(contact.get("linkedin")),
            "touches": mine,
            "confirmed_touches": confirmed,
            "replies": theirs,
            "positive": any(r["positive"] for r in theirs),
            "senders": senders,
            "sender_names": sorted({names.get(t["sender_id"], t["sender_id"])
                                    for t in confirmed if t.get("sender_id")}),
            "channels": sorted({t["channel"] for t in confirmed
                                if t.get("channel")}),
            "referred_by": referred_by(rec, key),
            "state": _contact_state(contact, confirmed, theirs, paused),
            "last_touch_at": confirmed[-1]["at"] if confirmed else None,
        }

    confirmed_all = [t for t in every_touch if t["confirmed"]]
    engaged = [c for c in by_contact.values() if c["replies"]]
    return {
        "record_id": rec.get("id"),
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "workspace": workspace,
        "client": rec.get("client"),
        "contacts": list(by_contact.values()),
        "by_contact": by_contact,
        "touches": every_touch,
        "confirmed_touches": confirmed_all,
        "replies": every_reply,
        "referrals": edges,
        "team": sorted({names.get(t["sender_id"], t["sender_id"])
                        for t in confirmed_all if t.get("sender_id")}),
        "channels": sorted({t["channel"] for t in confirmed_all
                            if t.get("channel")}),
        "paused": dict(paused) if paused else None,
        "suppressed": bool(paused) or rec.get("state") == "dropped",
        "counts": {
            "decision_makers": len(by_contact),
            "contacted": len([c for c in by_contact.values()
                              if c["confirmed_touches"]]),
            "engaged": len(engaged),
            "positive": len([c for c in by_contact.values() if c["positive"]]),
            "touches": len(confirmed_all),
            "planned": len(every_touch) - len(confirmed_all),
            "referrals": len(edges),
        },
    }


def _contact_state(contact, confirmed, their_replies, account_paused):
    """Where this person stands.

    Account pause outranks everything the account decides, but not what this
    person decided: suppression and a stop are facts about them, and reading
    `paused` for either would invite somebody to resume them when the account
    lifts. Below those, a reply pauses the whole company - so a contact nobody
    has written to can still be `paused`, and saying `not_started` there would
    invite somebody to start.
    """
    if contact.get("suppressed") or contact.get("unsubscribed"):
        return SUPPRESSED
    # A negative or wrong-person reply stops the contact without pausing the
    # account, so `their_replies` is truthy and this used to read `engaged` -
    # green, on the screen used to pick who to work next. `eligibility` reads
    # the same flag and refuses correctly; only the display disagreed.
    if contact.get("stopped"):
        return STOPPED
    if account_paused:
        return PAUSED
    if their_replies:
        return ENGAGED
    if confirmed:
        return ACTIVE
    return NOT_STARTED


def timeline(rec, workspace=None, rows=None):
    """One chronological account-wide feed: touches, replies and referrals.

    The view §22 of the brief asks for, and the reason it is worth building:
    an operator looking at a company wants one column of "what happened",
    not three tables to interleave by eye.
    """
    rows = si.load() if rows is None else rows
    names = _sender_names(workspace, rows)
    contacts = {c.get("key"): c for c in contacts_of(rec)}

    def who(key):
        contact = contacts.get(key) or {}
        return contact.get("name") or key

    entries = []
    for item in touches(rec):
        sender = names.get(item["sender_id"], item["sender_id"])
        entries.append({
            "at": item["at"],
            "day": item["day"],
            "kind": "touch",
            "channel": item["channel"],
            "state": item["state"],
            "confirmed": item["confirmed"],
            "contact_key": item["contact_key"],
            "contact": who(item["contact_key"]),
            "sender": sender,
            "account_id": item["account_id"],
            "summary": (f"{sender or 'a sender'} to {who(item['contact_key'])}"
                        f" - {item['channel'] or 'unknown channel'}"),
        })
    for item in replies(rec):
        if item["type"] == events.REPLY_CLASSIFIED:
            continue                    # the reply itself already appears
        entries.append({
            "at": item["at"],
            "day": None,
            "kind": "reply",
            "channel": item["channel"],
            "state": "positive_reply" if item["positive"] else "replied",
            "confirmed": True,
            "contact_key": item["contact_key"],
            "contact": who(item["contact_key"]),
            "sender": None,
            "summary": (f"{who(item['contact_key'])} replied"
                        + (" - positive" if item["positive"] else "")),
        })
    for edge in referrals(rec):
        entries.append({
            "at": edge["at"],
            "day": None,
            "kind": "referral",
            "channel": edge.get("channel"),
            "state": "referral",
            "confirmed": True,
            "contact_key": edge["from_contact"],
            "contact": edge["from_name"],
            "sender": None,
            "summary": (f"{edge['from_name']} referred us to "
                        f"{edge['to_name']}"),
        })
    entries.sort(key=lambda e: (str(e.get("at") or ""), e["kind"]))
    return entries


def team_for(rec, workspace=None, rows=None):
    """Every human who has actually touched this account, by channel.

    Read from confirmed touches rather than from the campaign's authorised
    team: this answers "who has the prospect heard from", which is the
    question a message about colleagues has to be checked against.
    """
    rows = si.load() if rows is None else rows
    names = _sender_names(workspace, rows)
    by_channel = collections.defaultdict(set)
    for item in touches(rec, confirmed_only=True):
        if item.get("sender_id") and item.get("channel"):
            by_channel[item["channel"]].add(item["sender_id"])
    return {channel: sorted({names.get(s, s) for s in senders})
            for channel, senders in sorted(by_channel.items())}


def has_confirmed_touch(rec, contact_key, sender_id=None, channel=None):
    """Did this specific thing actually happen?

    The single question every outreach claim reduces to, kept here so that
    `src/outreachclaims.py` and the QA checks cannot answer it differently.
    """
    for item in touches(rec, contact_key, confirmed_only=True):
        if sender_id and item.get("sender_id") != sender_id:
            continue
        if channel and item.get("channel") != channel:
            continue
        return item
    return None


def has_reply(rec, contact_key, positive_only=False):
    for item in replies(rec, contact_key):
        if positive_only and not item["positive"]:
            continue
        if item["type"] == events.REPLY_CLASSIFIED:
            continue
        return item
    return None
