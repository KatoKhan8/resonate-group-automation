#!/usr/bin/env python3
"""The one question asked before anybody is contacted: may we?

TASK-SUPPRESSION-2026-10-14. **This module is new.** `src/suppression.py` has
never existed in any commit on any ref in this repository - checked with
`git log --all -- src/suppression.py`, which is empty, and by walking the tree
of every local and remote ref. Nothing here is being restored or refactored;
the behaviour below did not exist before.

## Why a module and not a check

Before this file, "is this person suppressed" was answered in three places
that could disagree:

  * `eligibility.must_not_contact` - the person-level reasons, read from the
    record. The real one, and this module does NOT replace it.
  * `executionguard.authorize` gate 4 - compares `eligibility.decide`'s
    reasons against `SUPPRESSION_REASONS` when it mints a token.
  * `providerwrites.CONDITIONAL[EMAIL_RESUME]` - re-reads suppression from
    disk, but for exactly one verb, because a resume is not `facing` and so
    skips the guard entirely.

That third entry is the shape of the problem: a verb that did not go through
the guard needed its own copy of the question. This module is the question,
asked once, so a fourth verb cannot need a fourth copy.

## What is NOT reimplemented here

The BLOCK set is `eligibility.must_not_contact`, called, not re-derived. A
second implementation of "has this person unsubscribed" is the one thing this
file must not become, and `eligibility._replied`'s docstring says the same
thing about reply text: suppression is read from the contact, never
re-classified from the message. This module adds the HOLD rules that had no
home and consults the existing BLOCK rules through their owner.

## Attribution and suppression are different questions

Only sends recorded in the provider-write ledger are Resonate OS activity.
Suppression does not care who sent: a person worked by the client, by an
operator by hand, or by an agency six months ago has still been touched, and
the holds below are about THEM, not about us.

The record's event log knows only touches this system made. So
`provider_touches` is an argument, and when it is absent the answer is HOLD,
never ALLOW - see `UNKNOWN_IS_NOT_A_PASS`. The merge this module is based on
is titled "an internal campaign is never touched, and UNKNOWN is never a
pass"; this is that rule applied to touch history.

## The thresholds are provisional

Every number here is config, not a constant, because the client has not
confirmed any of them. `thresholds()` resolves them per call so a config edit
needs no code change and no restart - which matters, because roughly fifteen
loops import this process once and never reload it.
"""
import datetime

from . import account, eligibility

#: Suppression verdicts, weakest first.
ALLOW = "allow"
HOLD = "hold"
BLOCK = "block"
VERDICTS = (ALLOW, HOLD, BLOCK)

_RANK = {ALLOW: 0, HOLD: 1, BLOCK: 2}

# ---------------------------------------------------------------- reasons
#: A permanent refusal. Neither is lifted by the passage of time.
BLOCK_SUPPRESSED = "block:suppressed"
BLOCK_REPLIED = "block:replied"

#: A reversible hold. A person reads it and decides.
HOLD_ACTIVE_SEQUENCE = "hold:active_sequence_elsewhere"
HOLD_RECENT_TOUCH = "hold:last_touch_within_window"
HOLD_SEND_VOLUME = "hold:total_sends_above_threshold"
HOLD_TOUCH_HISTORY_UNKNOWN = "hold:provider_touch_history_unknown"

REASONS = (BLOCK_SUPPRESSED, BLOCK_REPLIED, HOLD_ACTIVE_SEQUENCE,
           HOLD_RECENT_TOUCH, HOLD_SEND_VOLUME, HOLD_TOUCH_HISTORY_UNKNOWN)

BLOCK_REASONS = (BLOCK_SUPPRESSED, BLOCK_REPLIED)
HOLD_REASONS = (HOLD_ACTIVE_SEQUENCE, HOLD_RECENT_TOUCH, HOLD_SEND_VOLUME,
                HOLD_TOUCH_HISTORY_UNKNOWN)

HUMAN = {
    BLOCK_SUPPRESSED: "this person has been suppressed",
    BLOCK_REPLIED: "this person replied; their sequence is answered",
    HOLD_ACTIVE_SEQUENCE: "they are in an active sequence somewhere",
    HOLD_RECENT_TOUCH: "they were contacted recently",
    HOLD_SEND_VOLUME: "they have been contacted many times already",
    HOLD_TOUCH_HISTORY_UNKNOWN:
        "we cannot see what the providers have already sent them",
}

# ---------------------------------------------------------------- config
#: PROVISIONAL. Every one of these is awaiting client confirmation.
DEFAULTS = {
    # A last touch inside this window holds. Provisional.
    "hold_after_last_touch_days": 30,
    # More than this many sends EVER holds for manual review. Provisional.
    "hold_above_total_sends": 10,
    # After this long an account or lead may be contacted again. The operator
    # has confirmed 90 is correct; it is still config, because the other two
    # are not confirmed and a split between constant and config is how the
    # three drift apart.
    "cooling_days": 90,
    # An active sequence anywhere holds until it finishes.
    "hold_on_active_sequence": True,
}

#: Absent provider touch history is a HOLD, not a pass. Flip this and the
#: module will cheerfully allow a send to somebody it knows nothing about.
UNKNOWN_IS_NOT_A_PASS = True

# ---------------------------------------------------------------- scope
#
# ONE function answers the question; it is asked at two moments, and the two
# moments can see different things. The scope is an argument rather than a
# second function so that there is exactly one implementation of every rule.
#
#: Before a person is put into a sequence. Everything is evaluated, and the
#: caller is expected to have read provider touch history - that is the
#: moment at which reading it is cheap and correct.
SCOPE_ENROL = "enrol"
#: Immediately before a provider write, inside the door. The permanent
#: refusals are re-read from disk and enforced; the HOLD rules are NOT
#: evaluated, because touch history is not readable here without a provider
#: call, and a rule that cannot be evaluated must not be reported as a hold
#: that stops every send in the estate. The holds are an enrolment decision.
SCOPE_SEND = "send"
SCOPES = (SCOPE_ENROL, SCOPE_SEND)


def thresholds(config=None):
    """The live thresholds. Resolved per call, never cached at import."""
    out = dict(DEFAULTS)
    section = ((config or {}).get("suppression") or {})
    for key in DEFAULTS:
        if key in section and section[key] is not None:
            out[key] = section[key]
    return out


# ------------------------------------------------- what was consulted, really
#: Every `decide` call appends here. A test asserting that suppression refused
#: proves nothing unless it can also prove suppression was ASKED - four
#: controls in this repository have already been found unable to fail, and the
#: usual mechanism is a guard nobody called. `consultations()` is how a test
#: tells "it refused" from "it was never reached".
_CONSULTATIONS = []


def consultations():
    """Every (rec_id, contact_key, action) this module has answered."""
    return list(_CONSULTATIONS)


def reset_consultations():
    del _CONSULTATIONS[:]


class Verdict:
    """What suppression says, and why.

    Deliberately not a dict, for the same reason `executionguard.Authorization`
    is not: a dict can be assembled by anybody, and a caller must not be able
    to hand the write layer something shaped like a pass.
    """

    __slots__ = ("action", "reasons", "detail", "rec_id", "contact_key", "at")

    def __init__(self, action, reasons=(), detail=None, rec_id=None,
                 contact_key=None, at=None):
        self.action = action
        self.reasons = tuple(reasons)
        self.detail = detail or {}
        self.rec_id = rec_id
        self.contact_key = contact_key
        self.at = at

    @property
    def sendable(self):
        return self.action == ALLOW

    def explain(self):
        if not self.reasons:
            return "nothing argues against contacting this person"
        return "; ".join(HUMAN.get(r, r) for r in self.reasons)

    def as_dict(self):
        return {"action": self.action, "reasons": list(self.reasons),
                "detail": self.detail, "rec_id": self.rec_id,
                "contact_key": self.contact_key, "at": self.at}

    def __repr__(self):
        return "<Verdict %s %s>" % (self.action, list(self.reasons))


class Suppressed(RuntimeError):
    """The send must not happen. Carries the verdict that refused it."""

    def __init__(self, verdict):
        self.verdict = verdict
        super().__init__("%s: %s" % (verdict.action, verdict.explain()))


def _parse(value):
    """An aware datetime, or None. A naive stamp is unreadable, not assumed UTC."""
    text = str(value or "")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else None


def _now(now=None):
    if isinstance(now, datetime.datetime):
        return now if now.tzinfo else datetime.datetime.now(datetime.timezone.utc)
    return _parse(now) or datetime.datetime.now(datetime.timezone.utc)


def _days_since(value, now):
    at = _parse(value)
    if at is None:
        return None
    return (now - at).total_seconds() / 86400.0


def _verdict(reasons, detail, rec, contact, at):
    """Rank the reasons into an action, record the consultation, return it.

    THE ONLY PLACE A VERDICT IS BUILT, so that every exit from `decide` is
    recorded in `_CONSULTATIONS`. An early return that forgot to append would
    be a send the audit cannot see.
    """
    action = ALLOW
    for reason in reasons:
        candidate = BLOCK if reason in BLOCK_REASONS else HOLD
        if _RANK[candidate] > _RANK[action]:
            action = candidate
    verdict = Verdict(action, list(dict.fromkeys(reasons)), detail,
                      rec_id=(rec or {}).get("id"),
                      contact_key=(contact or {}).get("key"),
                      at=at.isoformat())
    _CONSULTATIONS.append((verdict.rec_id, verdict.contact_key, verdict.action))
    return verdict


def decide(rec, contact, config=None, now=None, provider_touches=None,
           suppressed=None, agency=None, scope=SCOPE_ENROL):
    """May we contact this person? ALLOW, HOLD or BLOCK, with reasons.

    `provider_touches` is what the PROVIDERS know, regardless of who sent it:

        {"last_touch_at": <iso>, "total_sends": <int>, "active_sequence": <bool>}

    At `SCOPE_ENROL`, omitting it means the touch rules cannot be evaluated,
    which is a HOLD. Passing `{}` is not a way to say "no touches" - say
    `{"total_sends": 0, "last_touch_at": None, "active_sequence": False}`.

    At `SCOPE_SEND` the HOLD rules are skipped entirely; see `SCOPE_SEND`.
    """
    if scope not in SCOPES:
        raise ValueError("unknown suppression scope: %r" % (scope,))
    rec = rec or {}
    contact = contact or {}
    at = _now(now)
    limits = thresholds(config)
    reasons = []
    detail = {"thresholds": limits, "scope": scope}

    # 1. THE PERMANENT REFUSALS, asked of their owner. `must_not_contact`
    #    returns one slot per check, most final first, `None` where it did
    #    not fire. It is not re-derived here and must never be.
    fired = [r for r in eligibility.must_not_contact(
        rec, contact, config=config, suppressed=suppressed) if r]
    if fired:
        detail["eligibility_reasons"] = fired
        reasons.append(BLOCK_REPLIED if fired == [eligibility.BLOCKED_REPLIED]
                       else BLOCK_SUPPRESSED)

    # 2. A REPLY BLOCKS. `must_not_contact` reads the contact's own flags and
    #    its reply events; this adds the account's reply log, because a reply
    #    recorded against the contact but not flagged on it is still a reply.
    if BLOCK_REPLIED not in reasons:
        if account.replies(rec, contact.get("key")):
            reasons.append(BLOCK_REPLIED)

    # 3. THE HOLD RULES. Every one of them is reversible, and the volume and
    #    recency holds expire after `cooling_days`.
    #
    #    NOT EVALUATED AT THE DOOR. At `SCOPE_SEND` there is no provider read
    #    available and no honest way to answer them, so they are not asked -
    #    rather than asked, unanswerable, and reported as a hold that would
    #    stop every send in the estate. The permanent refusals above ARE
    #    enforced there, and they are the ones a prospect would care about.
    if scope == SCOPE_SEND:
        detail["hold_rules"] = "not evaluated at SCOPE_SEND"
        return _verdict(reasons, detail, rec, contact, at)

    known = isinstance(provider_touches, dict) and bool(provider_touches)
    if not known:
        # What the record knows is only what WE sent. That is not the question
        # the hold rules ask, so it is not quietly substituted for it.
        own = account.touches(rec, contact.get("key"), confirmed_only=True)
        detail["os_confirmed_touches"] = len(own)
        detail["provider_touches"] = "not supplied"
        if UNKNOWN_IS_NOT_A_PASS:
            reasons.append(HOLD_TOUCH_HISTORY_UNKNOWN)
    else:
        last = provider_touches.get("last_touch_at")
        total = provider_touches.get("total_sends")
        active = provider_touches.get("active_sequence")
        detail["provider_touches"] = dict(provider_touches)

        since = _days_since(last, at)
        detail["days_since_last_touch"] = since
        cooled = since is not None and since >= limits["cooling_days"]
        detail["cooled"] = cooled

        if limits["hold_on_active_sequence"] and active:
            # An active sequence is a fact about now, not about history, so
            # cooling does not lift it: there is nothing to cool from while
            # somebody is still being sent to.
            reasons.append(HOLD_ACTIVE_SEQUENCE)

        if last is not None and since is None:
            # A timestamp we cannot read is not a timestamp outside the window.
            reasons.append(HOLD_TOUCH_HISTORY_UNKNOWN)
        elif since is not None and since < limits["hold_after_last_touch_days"]:
            reasons.append(HOLD_RECENT_TOUCH)

        if total is None:
            reasons.append(HOLD_TOUCH_HISTORY_UNKNOWN)
        elif isinstance(total, int) and total > limits["hold_above_total_sends"]:
            # 90-DAY COOLING APPLIES HERE. The operator confirmed that after
            # the cooling window an account or lead may be contacted again,
            # and a volume hold is exactly a statement about past sends.
            if not cooled:
                reasons.append(HOLD_SEND_VOLUME)

    return _verdict(reasons, detail, rec, contact, at)


def require(rec, contact, **kw):
    """`decide`, but a non-ALLOW raises. The form a send path should call."""
    verdict = decide(rec, contact, **kw)
    if verdict.action != ALLOW:
        raise Suppressed(verdict)
    return verdict


# ------------------------------------------- the provider's own suppression
#
# CANARY-01, 2026-10-14: "EmailBison keeps its own blacklist and stops a
# sequence for anyone on it. That is a second suppression list, provider-side,
# which nothing in this system has ever reconciled against ours. Someone may
# be blocked here and not there, or there and not here."
#
# THE LIST ITSELF CANNOT BE READ, and that is measured rather than assumed.
# `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md` lines 612-613 record
# `/blocklist/emails` and `/blocklist/domains` as **404**, and
# `scripts/reengagement_provider_confirmed.py` says the same of
# `/unsubscribes`, `/suppressions` and `/do-not-contact`. `src/providers/bison.py`
# declares no such route, so nothing in this system could have read one.
#
# WHAT IS READABLE IS THE EFFECT, PER LEAD. A lead's campaign-membership
# status and its queue-row status both carry the provider's own verdict -
# `unsubscribed`, `opted_out`, `complained`, `blocked`, `suppressed`. So the
# reconciliation that is actually possible is per-person, over people we
# already hold, and it is ASYMMETRIC in what it can prove:
#
#   * Somebody the provider has blocked, whom we think is contactable, is
#     detectable - but only if we hold them. A person on their blacklist whom
#     we have never staged is invisible until we stage them, at which point
#     the provider silently stops them and we read "no reply".
#   * Somebody WE have suppressed who is still in an active sequence there is
#     also detectable, and it is the dangerous direction: the provider keeps
#     sending to a person who asked us to stop, and no gate of ours is in that
#     path. This is the same fact `HOLD_ACTIVE_SEQUENCE` exists for.
#
# So absence from a provider snapshot is NEVER evidence that somebody is
# contactable there. `UNKNOWN_THERE` is a finding, not a pass.

#: Both lists say the same thing about this person.
AGREE = "agree"
#: The provider has stopped them; we have not. We would keep trying, and read
#: the provider's silence as "no reply".
BLOCKED_THERE_ONLY = "blocked_at_provider_not_here"
#: We have stopped them; the provider still has them in an active sequence.
#: THE DANGEROUS ONE - the provider keeps sending.
SUPPRESSED_HERE_ONLY = "suppressed_here_still_active_there"
#: The snapshot says nothing about them. Not a pass; see above.
UNKNOWN_THERE = "provider_state_unknown"

RECONCILIATION = (AGREE, BLOCKED_THERE_ONLY, SUPPRESSED_HERE_ONLY,
                  UNKNOWN_THERE)

#: Provider-side statuses that mean the provider has stopped this person.
#: Taken from `scripts/reengagement_provider_confirmed.py`, which established
#: them against the live instance, rather than invented here - a second
#: vocabulary for one provider's words is how the two come to disagree.
PROVIDER_STOPPED = frozenset({
    "unsubscribed", "unsubscribe", "opted_out", "complained", "complaint",
    "blocked", "suppressed", "bounced", "bounce", "hard_bounced",
    "soft_bounced",
})

#: Provider-side statuses that mean this person is still being sent to.
PROVIDER_ACTIVE = frozenset({"in_sequence", "active", "sending", "scheduled",
                             "queued"})


def reconcile(rec, contact, provider_status=None, config=None, now=None):
    """Compare our suppression state with the provider's, for one person.

    `provider_status` is the status string the provider reports for this
    person - from campaign membership or a queue row - or `None` when the
    snapshot does not mention them. It is a string rather than a fetch
    because this module makes no provider calls; the caller supplies what it
    read.

    Returns `(finding, detail)`. The finding is never `AGREE` on the strength
    of absence.
    """
    verdict = decide(rec, contact, config=config, now=now,
                     scope=SCOPE_SEND)
    stopped_here = verdict.action == BLOCK
    status = str(provider_status or "").strip().lower()

    detail = {"ours": verdict.action, "our_reasons": list(verdict.reasons),
              "theirs": status or None}

    if not status:
        # The blacklist is not readable, so "not in the snapshot" cannot mean
        # "not on their list". It means we do not know.
        return UNKNOWN_THERE, detail

    stopped_there = status in PROVIDER_STOPPED
    active_there = status in PROVIDER_ACTIVE

    if stopped_here and stopped_there:
        return AGREE, detail
    if stopped_there and not stopped_here:
        return BLOCKED_THERE_ONLY, detail
    if stopped_here and active_there:
        return SUPPRESSED_HERE_ONLY, detail
    if stopped_here and not stopped_there:
        # Stopped here, and the provider reports something that is neither a
        # stop nor an active sequence - a draft, a finished sequence, a word
        # we have not seen. Not provably safe, so not AGREE.
        return SUPPRESSED_HERE_ONLY, detail
    if not stopped_here and active_there:
        return AGREE, detail
    return UNKNOWN_THERE, detail


def reconcile_all(recs, provider_statuses, config=None, now=None):
    """`reconcile` over an estate. Returns findings grouped by kind.

    `provider_statuses` maps a normalised email to the provider's status
    string. Keyed on email because that is the identifier both sides share;
    a name never reaches this function, for `agencydnc.keys_for`'s reason.
    """
    from . import dedupe

    lookup = {}
    for key, value in (provider_statuses or {}).items():
        normalised = dedupe.normalise_email(key)
        if normalised:
            lookup[normalised] = value

    out = {kind: [] for kind in RECONCILIATION}
    for rec in recs or []:
        for contact in rec.get("contacts") or []:
            email = dedupe.normalise_email(contact.get("email"))
            finding, detail = reconcile(
                rec, contact, provider_status=lookup.get(email),
                config=config, now=now)
            out[finding].append({
                "rec_id": rec.get("id"),
                "contact_key": contact.get("key"),
                **detail})
    return out
