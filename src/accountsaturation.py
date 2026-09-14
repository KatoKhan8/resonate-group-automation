#!/usr/bin/env python3
"""When an account has had enough, and when a second person should be opened.

## The question this answers

`nextaction` composes six modules and says what to do next. `fatigue` says
how much more one person or one company may take. `accountpolicy` says what
a reply does. But nothing composes them into the two account-level questions
an operator actually asks:

    Has this company had enough?
    Should a second person be opened?

This module answers both, from canonical state, using the caps that already
exist in configuration rather than inventing new ones.

## Saturation is derived, never stored

`verdict()` reads the event log, the contact list, the pause state and the
fatigue limits. It does not write anything. A second copy of the truth to
fall out of step with the first is the failure this architecture exists to
prevent.

## The conditions

An account is saturated when any of these is true:

1. A positive reply was received from any contact. The conversation is
   started; cold outreach to colleagues stops. The account is held, not
   suppressed - it may resume if the conversation goes cold.

2. An unsubscribe was received from any contact. One person asking to be
   removed is a signal about the company, not just the person. The account
   stops.

3. The account touch ceiling is reached. `fatigue.account_check` already
   enforces this; the saturation verdict reports it as the reason.

4. Every known contact is terminal. Nothing more can usefully be sent.

## Escalation

A second stakeholder becomes eligible when:

- The first has been contacted (there is a confirmed touch)
- AND the account is not saturated
- AND the spacing rules are respected (`account.min_hours_between_first_touches`)
- AND a referral explicitly names them, OR the first contact has reached
  their touch ceiling without a terminal outcome

The referral case is special: it stops the referrer AND activates the
referred person. This is handled by `accountpolicy.apply_reply` for the
REFERRAL outcome, which this module reads but does not re-derive.
"""
from . import account, accountpolicy as ap, events, fatigue, store

# The saturation reasons, in order of finality.
POSITIVE_REPLY = "saturated:positive_reply"
UNSUBSCRIBED = "saturated:unsubscribed"
ACCOUNT_SUPPRESSED = "saturated:account_suppressed"
ALL_CONTACTS_TERMINAL = "saturated:all_contacts_terminal"
TOUCH_CEILING = "saturated:touch_ceiling"

STOP = "stop"
WAIT = "wait"
OK = "ok"


def _any_positive_reply(rec):
    """Whether any contact at this account had a positive reply.

    Read from events, never from the contact's `positive` flag - the flag
    is derived from the same events, and reading it here would be two
    derivations of the same fact that could disagree.
    """
    for entry in rec.get("events") or []:
        if entry.get("type") == events.POSITIVE_REPLY_DETECTED:
            return True
        if entry.get("type") == events.REPLY_CLASSIFIED:
            outcome = str(entry.get("outcome") or "").strip().lower()
            if outcome == ap.POSITIVE:
                return True
            classification = str(entry.get("classification") or "").strip().lower()
            if classification == "positive":
                return True
    return False


def _any_unsubscribed(rec):
    """Whether any contact at this account asked to be removed.

    A person-level unsubscribe is a fact about one address, but it is also
    a signal about the company: continuing to contact their colleagues
    reads as one organisation that does not talk to itself.
    """
    for contact in account.contacts_of(rec):
        if contact.get("unsubscribed") or contact.get("suppressed"):
            return True
    return False


def _account_suppressed(rec):
    """Whether the account itself is suppressed."""
    return (rec.get("suppression") or {}).get("unsubscribed")


def _all_contacts_terminal(rec):
    """Whether every contact at this account is finished.

    Terminal means: stopped, suppressed, or dropped. A contact who replied
    negatively is stopped; a contact who unsubscribed is suppressed. A
    contact who was never contacted is not terminal - they have not started.
    """
    contacts = account.contacts_of(rec)
    if not contacts:
        return True
    for contact in contacts:
        if contact.get("excluded"):
            continue
        state, _ = ap.contact_state(contact)
        has_touches = bool(account.touches(rec, contact.get("key"),
                                           confirmed_only=True))
        if state in (ap.CONTINUE,) and not has_touches:
            return False
        if state in (ap.CONTINUE,) and has_touches:
            return False
        if state == ap.HOLD:
            return False
    return True


def verdict(rec, config=None, at=None):
    """Whether this account has had enough, and why.

    Returns a dict with:
      - `state`: OK, WAIT, or STOP
      - `reason`: the saturation reason code, or None
      - `why`: a human-readable explanation

    The planner consults this before deciding what to do next. Where this
    says STOP, no contact at this account may be opened. Where it says
    WAIT, the account is paused but may resume.
    """
    at = at or store.now()

    if _account_suppressed(rec):
        return {"state": STOP, "reason": ACCOUNT_SUPPRESSED,
                "why": "the company asked not to be contacted"}

    if _any_unsubscribed(rec):
        return {"state": STOP, "reason": UNSUBSCRIBED,
                "why": ("a contact at this company asked to be removed; "
                        "the account stops")}

    if _any_positive_reply(rec):
        return {"state": STOP, "reason": POSITIVE_REPLY,
                "why": ("a positive reply was received; the conversation "
                        "is starting and cold outreach to colleagues stops")}

    graph = account.graph(rec, config=config)
    fatigue_verdict = fatigue.account_check(rec, at=at, config=config)
    if fatigue_verdict["state"] == fatigue.BLOCK:
        return {"state": WAIT, "reason": TOUCH_CEILING,
                "why": "; ".join(f["why"] for f in fatigue_verdict["findings"]),
                "fatigue": fatigue_verdict}

    if _all_contacts_terminal(rec):
        return {"state": STOP, "reason": ALL_CONTACTS_TERMINAL,
                "why": "every decision maker at this company is finished"}

    return {"state": OK, "reason": None, "why": "the account is workable"}
