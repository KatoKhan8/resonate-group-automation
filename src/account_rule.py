#!/usr/bin/env python3
"""The account rule: stagger by persona rather than block the whole account.

THE DEFECT THIS EXISTS TO FIX. On 2026-09-24 the guard refused 212 accounts
because the effective rule was "somebody at this account was touched, so
refuse", and the US cohort was empty that night. The operator's actual rule is
staggered, and it is stated here in the operator's own words:

    the same contact                          NEVER twice
    the same account, a NEW persona           allowed after 5 days with no
                                              human reply
    a third persona                           after 7 more days
    any reply or unsubscribe at the account   stops all others
    a stop carrying OUR OWN reason plus an
      operator-recorded move                  is NOT an account-level hold

That last line is ISSUE-035, and it is the reason this module exists rather
than a tightening of `collision.account_policy`. On 2026-09-24 this system
stopped 63 leads deliberately, to move them to fresh campaigns, and the gate
then refused to re-push them because "a campaign at this account ended early
(stopped)". The containment created the block on its own remediation. The gate
was right and could not know it.

## WHERE THIS SITS RELATIVE TO `collision`

`collision.account_policy` answers a different question and keeps answering
it: what has somebody ELSE - the client's own estate - already done at this
account. It reads the provider. This module answers what WE may do next given
what we ourselves have confirmed, and the two are ANDed at the call site:
`collision` may still STOP an account this module would allow. Nothing here
widens `collision`; it only narrows what `collision` has already allowed.

## THE GAP IS MEASURED FROM A CONFIRMED TOUCH, AND `push_prepared` IS NOT ONE

`src/touch.py` excludes `push_prepared` by name and the reason is the whole
safety of the model: a payload is constructed for every planned touch, so
counting one as a send makes every planned touch look like it happened. This
module therefore reads `account.touches(..., confirmed_only=True)`, whose
confirming events are `push_marked`, `email_delivered` and
`linkedin_connected` - the same three the rest of the system trusts - and
never a cached `last_touch_at`.

`last_touch_at` is not read here, deliberately and by name. It is stale by up
to 109 days on the measured snapshot (lead 133283 reads 2026-06-05 in
`work/stage/last-touch.json` while its last confirmed send is 2026-09-22 from
our own campaign 491), and nothing in `src/` ever writes it onto a queue
record, so a read of it would return `None` on every record in the store and
a gap computed from `None` is a gap that never refuses.

## FAILING CLOSED IS THE DESIGN, IN THREE PLACES

**A stop we cannot prove is ours holds the account.** `our_stop` and
`operator_recorded` are absent from every one of the 8 `contact_stopped`
events in the live store. A missing field reads as "not ours" and the account
holds. The exception has to be EARNED by evidence that is present, never
granted by evidence that is missing - which is the ISSUE-041 failure this
codebase keeps producing.

**A reply nobody classified is a human reply.** An unclassified
`reply_received` could be an out-of-office or it could be a person saying
stop. Until something says which, it stops the account.

**Reply state that cannot be read is not reply state that is empty.** If the
account carries a confirmed LinkedIn touch and no contact there carries the
`heyreach_lead_id` that LinkedIn replies are ingested against, then "no reply
recorded" is a statement about our plumbing and not about the prospect. One
contact in 1,065 carries that id today and it is the operator's own test
identity, so this arm is live for every real account.
"""
import datetime

from . import account, events, replies, testidentity

ALLOW = "ALLOW"
REFUSE = "REFUSE"

#: Days of silence required at the account before the Nth persona may be
#: approached, keyed by how many DISTINCT people there have already been
#: confirmed-touched. One touched person -> 5 days. Two -> 5 + 7 = 12, which
#: is "a third after 7 more days" read cumulatively, and it is the reading
#: TASK-275's own day-11/day-12 assertions encode. See MERGE-REQUEST
#: 2026-09-25 for why the other reading was rejected.
REQUIRED_GAP_DAYS = {0: 0.0, 1: 5.0, 2: 12.0}

#: The rule names a first, a second and a third persona and stops. A fourth
#: is not "allowed after more days" - it is undefined, and an undefined case
#: refuses.
MAX_PERSONAS = 3

#: Reply classifications that are a removal request rather than a reply.
UNSUBSCRIBE_WORDS = frozenset({"unsubscribe", "account_do_not_contact"})

#: A stop reason this system generates for its own deliberate moves. A stop
#: carrying one of these is "our own reason" for the ISSUE-035 exception; it
#: is still only HALF the exception, and the operator attestation is the
#: other half.
OUR_OWN_STOP_REASONS = frozenset({
    "operator_move", "campaign_move", "moved_to_fresh_campaign",
    "we_stopped_it",
})


def _parse(at):
    """A timestamp from any shape the live store actually carries.

    Measured in `work/queue.jsonl`: `2026-09-22T14:40:49.000000Z`,
    `2026-09-23T11:12:33.194Z` and `2026-09-13T08:48:43+00:00` all occur.
    An unparseable timestamp returns None and its caller treats that as
    "cannot establish a gap", which refuses.
    """
    if not at:
        return None
    text = str(at).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def _now(now=None):
    if now is None:
        return datetime.datetime.now(datetime.timezone.utc)
    parsed = _parse(now) if not isinstance(now, datetime.datetime) else now
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def _verdict(verdict, why, rule):
    return {"verdict": verdict, "why": why, "rule": rule}


def _entries(rec, *types):
    return [e for e in (rec.get("events") or [])
            if isinstance(e, dict) and e.get("type") in types]


# ------------------------------------------------------------------ replies

def _classification_for(rec, entry):
    """What a `reply_received` was later classified as, or None.

    The two events are separate rows carrying the same `at` and contact, so
    the classification is looked up rather than assumed. `None` here means
    nobody has classified it yet, and the caller fails closed on that.
    """
    if entry.get("type") == events.REPLY_CLASSIFIED:
        return entry.get("classification") or entry.get("outcome")
    for other in _entries(rec, events.REPLY_CLASSIFIED):
        if (other.get("contact") == entry.get("contact")
                and other.get("at") == entry.get("at")):
            return other.get("classification") or other.get("outcome")
    return None


def _account_answer(rec):
    """The first unsubscribe or human reply at the account, or None.

    Returns (kind, contact_key, classification). `kind` is "unsubscribe" or
    "human_reply". An automated reply - out-of-office, assistant redirect, a
    bare machine acknowledgement - is not a human reply and is skipped, which
    is the operator's rule and `replies.is_automated`'s job to define.
    """
    seen = _entries(rec, events.REPLY_RECEIVED, events.REPLY_CLASSIFIED,
                    events.POSITIVE_REPLY_DETECTED)
    for entry in seen:
        who = entry.get("contact")
        classification = _classification_for(rec, entry)
        outcome = entry.get("outcome")
        if (str(classification or "") in UNSUBSCRIBE_WORDS
                or str(outcome or "") in UNSUBSCRIBE_WORDS):
            return "unsubscribe", who, classification
    for entry in seen:
        who = entry.get("contact")
        if entry.get("type") == events.POSITIVE_REPLY_DETECTED:
            return "human_reply", who, "positive"
        classification = _classification_for(rec, entry)
        # An unclassified reply is not an automated one. Nobody has said what
        # it is, and "we could not tell" must not read as "it was a robot".
        if classification is None:
            return "human_reply", who, None
        if replies.is_automated(classification):
            continue
        return "human_reply", who, classification
    return None


# -------------------------------------------------------------------- stops

def _is_our_stop(entry):
    """Did WE make this stop, deliberately, for a reason we generated?

    `our_stop` absent is not `our_stop` false-by-accident - it is the field
    never having been written, which is exactly the case that must not lift
    the hold. Both this and `_operator_recorded` must be positively true.
    """
    if entry.get("our_stop") is True:
        return True
    return str(entry.get("reason") or "") in OUR_OWN_STOP_REASONS


def _operator_recorded(entry):
    return entry.get("operator_recorded") is True


def _account_stop(rec):
    """The first stop at the account that is NOT excused, or None.

    Returns (contact_key, reason, excused_count). A stop is excused only when
    BOTH arms of ISSUE-035 hold: our own reason AND an operator-recorded
    move. One arm alone holds the account.
    """
    excused = 0
    for entry in _entries(rec, events.CONTACT_STOPPED,
                          events.PROVIDER_STOP_CONFIRMED,
                          events.CONTACT_SUPPRESSED,
                          events.ACCOUNT_SUPPRESSED):
        if _is_our_stop(entry) and _operator_recorded(entry):
            excused += 1
            continue
        return entry.get("contact"), entry.get("reason"), excused
    return None


# ------------------------------------------------------- the LinkedIn hole

def _linkedin_reply_state_is_readable(rec):
    """Can a LinkedIn reply at this account even reach us?

    LinkedIn replies are ingested against `heyreach_lead_id`. A record whose
    contacts carry none has no path for a HeyReach reply to land on it, so
    the absence of a reply there is an absence of plumbing.
    """
    for contact in rec.get("contacts") or []:
        if isinstance(contact, dict) and contact.get("heyreach_lead_id"):
            return True
    return False


def _has_confirmed_linkedin_touch(touches):
    return any(t.get("channel") == "linkedin" for t in touches)


# --------------------------------------------------------------- the rule

def evaluate(rec, contact_key, now=None, config=None):
    """May we approach `contact_key` at this account right now?

    Returns {"verdict": ALLOW|REFUSE, "why": <sentence>, "rule": <name>}.
    The `why` is what an operator reads in a refusal, so it names the account
    fact rather than the rule number.
    """
    if not isinstance(rec, dict):
        return _verdict(REFUSE, "no record to evaluate", "unreadable")
    moment = _now(now)

    confirmed = [t for t in account.touches(rec, confirmed_only=True)
                 if _parse(t.get("at"))]

    # 1. THE SAME CONTACT IS NEVER CONTACTED TWICE. This outranks everything
    #    below it, including the ISSUE-035 exception: a deliberate move of
    #    ours is a reason to approach somebody ELSE at the account, never a
    #    reason to write to the same person again.
    mine = [t for t in confirmed if t.get("contact_key") == contact_key]
    if mine:
        channels = sorted({str(t.get("channel") or "?") for t in mine})
        return _verdict(
            REFUSE,
            f"this contact was already contacted "
            f"({len(mine)} confirmed touch(es) on {', '.join(channels)}); "
            f"the same contact is never contacted twice",
            "same_contact_twice")

    # 2. AN UNSUBSCRIBE OR A HUMAN REPLY ANYWHERE AT THE ACCOUNT STOPS ALL
    #    OTHERS. Checked before the stagger, because a reply on day 6 does
    #    not become harmless by the gap being satisfied.
    answer = _account_answer(rec)
    if answer:
        kind, who, classification = answer
        if kind == "unsubscribe":
            return _verdict(
                REFUSE,
                f"somebody at this account ({who}) unsubscribed; an "
                f"unsubscribe stops every other persona here",
                "account_unsubscribed")
        said = (f"classified {classification}" if classification
                else "not yet classified, so it is not an automated one")
        return _verdict(
            REFUSE,
            f"somebody at this account ({who}) replied ({said}); the "
            f"account has answered and whoever is having that conversation "
            f"owns it",
            "account_answered")

    # 3. A STOP AT THE ACCOUNT HOLDS IT, UNLESS IT IS OURS AND ATTESTED.
    stop = _account_stop(rec)
    if stop:
        who, reason, _ = stop
        named = f" ({reason})" if reason else ""
        return _verdict(
            REFUSE,
            f"a contact at this account ({who}) was stopped{named} and the "
            f"stop does not carry both our own reason and an "
            f"operator-recorded move; a stop we cannot prove is ours holds "
            f"the account",
            "account_stopped")

    # 4. REPLY STATE WE CANNOT READ IS NOT REPLY STATE THAT IS EMPTY.
    if (_has_confirmed_linkedin_touch(confirmed)
            and not _linkedin_reply_state_is_readable(rec)):
        return _verdict(
            REFUSE,
            "this account carries a confirmed LinkedIn touch and no contact "
            "here carries a heyreach_lead_id, so a LinkedIn reply has no "
            "path to reach us; no reply recorded is not no reply",
            "linkedin_reply_state_unreadable")

    # 5. THE STAGGER.
    others = sorted({t.get("contact_key") for t in confirmed
                     if t.get("contact_key") and t.get("contact_key") != contact_key})
    if not others:
        return _verdict(ALLOW, "nobody at this account has been contacted",
                        "first_persona")
    if len(others) >= MAX_PERSONAS:
        return _verdict(
            REFUSE,
            f"{len(others)} people at this account have already been "
            f"contacted; the rule names a first, a second and a third "
            f"persona and does not define a fourth",
            "persona_cap")

    latest = max(_parse(t.get("at")) for t in confirmed)
    gap = (moment - latest).total_seconds() / 86400.0
    need = REQUIRED_GAP_DAYS[len(others)]
    ordinal = {1: "second", 2: "third"}[len(others)]
    if gap < need:
        return _verdict(
            REFUSE,
            f"the last confirmed touch at this account was {gap:.1f} days "
            f"ago and a {ordinal} persona needs {need:.0f} days of silence; "
            f"{need - gap:.1f} days short",
            "stagger_gap")
    return _verdict(
        ALLOW,
        f"{len(others)} persona(s) contacted here, last {gap:.1f} days ago "
        f"with no human reply; a {ordinal} persona needs {need:.0f} days and "
        f"has them",
        "stagger_satisfied")


def is_test_identity(rec, contact_key=None):
    """The operator's own test identity is not a prospect.

    Kept here so a measurement of this rule's effect cannot count it as one.
    """
    if rec.get("id") in testidentity.RECORD_IDS:
        return True
    if contact_key and contact_key in testidentity.CONTACT_KEYS:
        return True
    return False
