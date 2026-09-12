#!/usr/bin/env python3
"""The one place that decides whether a step may go out.

## Why one place

Every sender that reconstructs "is this allowed" reconstructs it slightly
differently, and the difference is always discovered afterwards. So this module
is the only thing that answers, and the provider payload builders call it
rather than re-deriving anything. When a new condition is added, it is added
here once and every channel gains it.

## Never a boolean

A caller needs to know *why*, and the answer has four shapes rather than two:

    eligible   every condition passes
    held       a condition might pass later: verification unknown, DNS failed,
               approval went stale. Nothing is wrong; nothing may go yet
    blocked    a condition will not pass: suppressed, replied, duplicate,
               dropped. This step is over
    skipped    this step does not apply to this contact at all: the email
               channel is closed, or there is no LinkedIn profile

The distinction matters operationally. Held is a queue to work through; blocked
is a decision to record; skipped is neither, and counting them together makes a
campaign look broken when it is merely narrower than expected.

## Re-derived, never trusted

Everything here is computed from primary state at the moment of asking. A
stored `sendable`, a stored `approved`, a stored MX verdict - each is
recomputed from what it was derived from, so tampering with a cached field
upstream changes nothing. That is the whole point of `decide()` being called
immediately before the payload is built rather than once at planning time.
"""
from . import (approval, cadence, campaigns, claims, clients, dedupe, events,
               evidence, ingest, lint, linkedin, mx, push, store,
               verification)

# ------------------------------------------------------------------ verdicts

ELIGIBLE = "eligible"
HELD = "held"
BLOCKED = "blocked"
SKIPPED = "skipped"
VERDICTS = (ELIGIBLE, HELD, BLOCKED, SKIPPED)

# Stable reason codes. Renaming one breaks reporting, so these are vocabulary.
BLOCKED_SUPPRESSED = "blocked:suppressed"
BLOCKED_CLIENT_SUPPRESSED = "blocked:client_suppressed"
# Somebody told RESONATE, not a client, never to contact them again.
# `src/agencydnc.py` holds the whole mechanism - a one-way hash per identifier,
# a closed reason vocabulary, and a lookup that answers yes and nothing else -
# and until now its only callers were the web layer and referral promotion.
# Nothing on the SEND path asked it, so the strongest suppression this agency
# has was the one no send consulted.
BLOCKED_AGENCY_DNC = "blocked:agency_dnc"
BLOCKED_DROPPED = "blocked:record_dropped"
BLOCKED_COMPANY_PAUSED = "blocked:company_paused"
BLOCKED_CONTACT_PAUSED = "blocked:contact_paused"
BLOCKED_REPLIED = "blocked:replied"
BLOCKED_UNSUBSCRIBED = "blocked:unsubscribed"
BLOCKED_ACCOUNT_SUPPRESSED = "blocked:account_suppressed"
BLOCKED_CONTACT_STOPPED = "blocked:contact_stopped"
BLOCKED_REVIEW_REQUIRED = "blocked:review_required"
BLOCKED_DUPLICATE = "blocked:duplicate_identity"
BLOCKED_ALREADY_PUSHED = "blocked:already_pushed"
BLOCKED_NOT_SENDABLE = "blocked:verification_not_sendable"
BLOCKED_MX = "blocked:mx_security_provider"
BLOCKED_LINT = "blocked:lint_failed"
BLOCKED_UNSUPPORTED_CLAIM = "blocked:unsupported_claim"
BLOCKED_NO_RECIPIENT = "blocked:no_recipient"
BLOCKED_NO_PROFILE = "blocked:no_linkedin_profile"
BLOCKED_WRONG_RECORD = "blocked:contact_not_on_record"
BLOCKED_NOT_SELECTED = "blocked:not_selected_for_campaign"
BLOCKED_CAMPAIGN_REJECTED = "blocked:campaign_rejected"
BLOCKED_CAMPAIGN_LAUNCHED = "blocked:campaign_already_launched"
BLOCKED_CAMPAIGN_FROZEN = "blocked:campaign_frozen"
BLOCKED_RECORD_IN_TWO_CAMPAIGNS = "blocked:record_in_two_campaigns"
BLOCKED_CAMPAIGN_STOPPED = "blocked:campaign_stopped"

HELD_VERIFICATION_UNKNOWN = "held:verification_unknown"
# Distinct from `verification_unknown` on purpose. "Nobody could tell us" and
# "one provider told us and we require two" are different problems: the first
# needs a better address, the second needs one more call. A reviewer told only
# that verification is "unknown" goes looking for the wrong fix.
HELD_INSUFFICIENT_CONFIRMATIONS = "held:insufficient_verification_confirmations"
HELD_DNS_FAILURE = "held:dns_failure"
HELD_APPROVAL_MISSING = "held:draft_not_approved"
HELD_EVIDENCE_AGED_OUT = "held:evidence_aged_out"
HELD_APPROVAL_STALE = "held:approval_stale"
HELD_CAMPAIGN_UNAPPROVED = "held:campaign_not_approved"
HELD_CAMPAIGN_STALE = "held:campaign_approval_stale"
HELD_NOT_DUE = "held:step_not_due"
HELD_AWAITING_DEPENDENCY = "held:awaiting_dependency"
HELD_NO_MAPPING = "held:provider_mapping_missing"
HELD_CHANNEL_SEPARATION = "held:channel_separation"
HELD_ACCOUNT_FATIGUE = "held:account_fatigue"

SKIPPED_EMAIL_CHANNEL = "skipped:email_channel_disabled"
SKIPPED_LINKEDIN_ONLY = "skipped:linkedin_only"
SKIPPED_NO_STEP = "skipped:no_such_step"

REASONS = tuple(v for k, v in sorted(globals().items())
                if k.startswith(("BLOCKED_", "HELD_", "SKIPPED_")))

# The sentence behind each code, for a person reading a screen. The codes are
# vocabulary - stable, greppable, safe to count - and this is the prose, kept
# apart from them for the same reason `channels.HUMAN` is.
#
# The distinction each sentence has to preserve is *what the reader should do
# next*, because that is what a reason is for. "Blocked" and "held" are not
# severities, they are different jobs: a block needs a different contact, a
# hold needs one more thing to happen. A table that flattened them into "not
# eligible" would leave a reviewer with no idea which they were looking at.
#
# `tests/test_eligibility.py` asserts every code in REASONS has an entry, so a
# new code without a sentence is a failing build rather than a screen that
# prints its own internals at somebody.
HUMAN = {
    BLOCKED_SUPPRESSED:
        "this domain is on the global suppression list",
    BLOCKED_CLIENT_SUPPRESSED:
        "this client's own suppression list names this domain",
    # Deliberately says nothing about who asked or when. `agencydnc` exists so
    # that answering this question cannot leak another client's prospect, and a
    # sentence here that said "they replied to somebody else" would undo the
    # whole privacy model in the one place a person reads.
    BLOCKED_AGENCY_DNC:
        "this person asked Resonate not to contact them, so no client may",
    BLOCKED_DROPPED: "this record was dropped from the batch",
    BLOCKED_COMPANY_PAUSED:
        "somebody at this company replied, which pauses both channels for the "
        "whole company",
    BLOCKED_CONTACT_PAUSED: "this contact is paused",
    BLOCKED_REPLIED: "this person replied, so the sequence stops here",
    BLOCKED_UNSUBSCRIBED: "this person asked us to stop",
    BLOCKED_ACCOUNT_SUPPRESSED:
        "somebody asked us to stop contacting this company, which reaches "
        "everybody there",
    BLOCKED_CONTACT_STOPPED:
        "this person's sequence was ended by what their reply said",
    BLOCKED_REVIEW_REQUIRED:
        "a reply here needs a person to look before anything else goes out",
    BLOCKED_DUPLICATE:
        "this person is already being contacted under another record",
    BLOCKED_ALREADY_PUSHED:
        "this step was already handed to the provider once",
    BLOCKED_NOT_SENDABLE:
        "the address did not clear double verification",
    BLOCKED_MX:
        "this domain's email-security gateway filters cold mail",
    BLOCKED_LINT: "the copy did not pass lint",
    BLOCKED_UNSUPPORTED_CLAIM:
        "the copy makes a claim nothing on the record supports",
    BLOCKED_NO_RECIPIENT: "there is no address to send to",
    BLOCKED_NO_PROFILE: "there is no usable LinkedIn profile",
    BLOCKED_WRONG_RECORD:
        "this contact does not belong to the record it was asked for",
    BLOCKED_NOT_SELECTED: "this contact was not selected for the campaign",
    BLOCKED_CAMPAIGN_REJECTED: "the campaign was rejected",
    BLOCKED_CAMPAIGN_LAUNCHED:
        "the campaign already launched, so this would be a second send",
    BLOCKED_CAMPAIGN_FROZEN: "the campaign is frozen",
    BLOCKED_RECORD_IN_TWO_CAMPAIGNS: (
        "this record is claimed by two live campaigns, so which "
        "sequence it is in cannot be answered"),
    BLOCKED_CAMPAIGN_STOPPED:
        "the campaign is not running: it has been paused, or it has "
        "finished",

    HELD_VERIFICATION_UNKNOWN:
        "nobody could tell us whether the address is real: it needs a better "
        "address, not another call",
    HELD_INSUFFICIENT_CONFIRMATIONS:
        "one provider confirmed the address and this client requires two: it "
        "needs one more call, not a better address",
    HELD_DNS_FAILURE:
        "DNS did not answer for this domain, so the step is held rather than "
        "assumed safe",
    HELD_APPROVAL_MISSING: "nobody has approved this draft yet",
    HELD_APPROVAL_STALE:
        "the draft changed after it was approved, so the approval is stale",
    HELD_EVIDENCE_AGED_OUT:
        "the fact this message was written from is no longer current enough "
        "to write from. The approval is still valid - the words have not "
        "changed - which is exactly why nothing else caught it. Regenerate "
        "the draft rather than editing the sentence",
    HELD_CAMPAIGN_UNAPPROVED: "nobody has approved this campaign yet",
    HELD_CAMPAIGN_STALE:
        "the campaign changed after it was approved, so the approval no "
        "longer describes it",
    HELD_NOT_DUE: "this step is not due yet",
    HELD_AWAITING_DEPENDENCY:
        "an earlier step in this sequence has not happened",
    HELD_NO_MAPPING:
        "no provider campaign has been created for this workspace to submit to",
    HELD_CHANNEL_SEPARATION:
        "another channel touches this person too close to this step",
    HELD_ACCOUNT_FATIGUE:
        "this company is already being worked as hard as policy allows",

    SKIPPED_EMAIL_CHANNEL: "the email channel is closed for this contact",
    SKIPPED_LINKEDIN_ONLY:
        "this contact is LinkedIn-only, so the email steps do not apply",
    SKIPPED_NO_STEP: "the cadence has no such step",
}


def explain(reason):
    """A sentence for a human, from a code.

    An unknown code is passed through rather than swallowed, the same as
    `channels.explain` does: a code nobody can explain is a bug, and hiding it
    behind an empty cell is how it stays one.
    """
    if not reason:
        return ""
    return HUMAN.get(reason, reason)

EMAIL = "email"
LINKEDIN = "linkedin"

# The smallest gap between two touches to one person, in days. A campaign that
# fires email and LinkedIn on the same morning reads as automation.
DEFAULT_MIN_SEPARATION_DAYS = 1


class Decision(dict):
    """A verdict with its reasons. Truthy only when eligible."""

    def __bool__(self):
        return self.get("verdict") == ELIGIBLE

    @property
    def eligible(self):
        return self.get("verdict") == ELIGIBLE


def _claim_detail(unsupported):
    """WHICH claim, not merely that there was one.

    `blocked:unsupported_claim` on its own sends whoever reads it hunting
    through a generated body for a sentence the checker already identified.
    Twice tonight that cost several minutes; the checker knew the answer both
    times.
    """
    out = []
    for problem in (unsupported or [])[:2]:
        if isinstance(problem, dict):
            why = str(problem.get("why") or "").strip()
            sentence = str(problem.get("sentence") or "").strip()[:90]
            out.append(f"claim:{why} :: {sentence}" if why else f"claim:{sentence}")
        else:
            out.append(f"claim:{str(problem)[:110]}")
    return out


def _decide(verdict, reasons, **extra):
    reasons = [r for r in (reasons or []) if r]
    decision = Decision({"verdict": verdict, "reasons": reasons,
                         "reason": reasons[0] if reasons else None})
    decision.update(extra)
    return decision


# ------------------------------------------------------------- the conditions
#
# Each returns a reason code or None. Ordered inside decide() from cheapest and
# most final to most expensive.

def _suppressed(rec, config, suppressed=None, contact=None, agency=None):
    """Every do-not-contact instruction, most binding first.

    THE AGENCY LIST IS CHECKED HERE, and it was checked nowhere on this path
    before. `agencydnc` is the list somebody joins by telling Resonate directly,
    so it has to hold whichever workspace next imports them - and a person on it
    reached `held:draft_not_approved`, an APPROVAL gate, which means approving
    the copy would have sent to them. Reproduced on 2026-09-11.

    Read from disk on every call, like the client list one line up. A cached
    suppression is a suppression that arrived after the cache.
    """
    domain = (rec.get("domain") or "").lower()
    suppressed = ingest.load_suppress() if suppressed is None else suppressed
    if domain and domain in suppressed:
        return BLOCKED_SUPPRESSED
    if (rec.get("drop_reason") or "").startswith("suppress"):
        return BLOCKED_CLIENT_SUPPRESSED
    if contact is not None:
        from . import agencydnc

        if agencydnc.lookup(contact, index=agency):
            return BLOCKED_AGENCY_DNC
    return None


def _record_state(rec):
    if rec.get("state") == "dropped" or rec.get("drop_reason"):
        return BLOCKED_DROPPED
    if rec.get("state") in lint.UNSHIPPABLE and rec.get("state") != "pushed":
        return BLOCKED_DROPPED
    return None


def _paused(rec, contact, config=None):
    """The account-level question: may anything go out to this company?

    Most final first. A company-wide do-not-contact is not a pause somebody
    lifts, so it is reported as itself rather than folded into one.
    """
    if (rec.get("suppression") or {}).get("unsubscribed"):
        return BLOCKED_ACCOUNT_SUPPRESSED
    if (rec.get("review") or {}).get("open"):
        return BLOCKED_REVIEW_REQUIRED
    # `config` so a workspace that reconfigured a reply policy is honoured
    # here too, not only where the transition was written.
    if cadence.pause_state(rec, config):
        return BLOCKED_COMPANY_PAUSED
    if (contact or {}).get("paused"):
        return BLOCKED_CONTACT_PAUSED
    return None


def must_not_contact(rec, contact, config=None, suppressed=None):
    """The person-level reasons this person hears nothing further.

    Public because `decide` is not the only caller that needs it and must not
    become a second implementation of it. `decide` answers about a STEP - it
    needs a timeline, a step key and content, and answers `skipped:no_such_step`
    for a person with no planned step. Whether somebody has unsubscribed is a
    fact about the person, true whether or not anything is scheduled for them,
    and `leadstop.sweep` asks exactly that question of everybody this system
    has staged at a provider.

    Returns reasons in the order `decide` evaluates them, most final first,
    with `None` for each check that did not fire.
    """
    return (_suppressed(rec, config, suppressed, contact=contact),
            _record_state(rec),
            _replied(rec, contact),
            _paused(rec, contact, config))


def _replied(rec, contact):
    """What this person's own reply did to their own sequence.

    This used to read "any reply from this company stops everything,
    whatever it said" - a second blanket rule sitting behind the account
    pause, so that even with a policy-driven pause this gate would still
    stop a colleague who had never replied.

    It is now about *this contact*; the account-level question is
    `_paused`'s. The two together are the whole answer, and a reply reaches
    everybody only when the policy says it does.

    Suppression is read from the contact, never re-derived from event text.
    `accountpolicy.apply_reply` writes `unsubscribed` when it honours a
    removal request, and this reads that. A gate that classified the text
    again would be a second implementation of the one rule that must not
    have two.
    """
    contact = contact or {}
    if contact.get("unsubscribed") or contact.get("suppressed"):
        return BLOCKED_UNSUBSCRIBED
    if contact.get("stopped"):
        return BLOCKED_CONTACT_STOPPED
    if contact.get("paused"):
        return BLOCKED_CONTACT_PAUSED
    key = contact.get("key")
    for entry in rec.get("events") or []:
        if events.is_reply(entry) and entry.get("contact") == key:
            return BLOCKED_REPLIED
    return None


def _identity(rec, contact):
    if not contact:
        return BLOCKED_NO_RECIPIENT
    if contact not in (rec.get("contacts") or []):
        keys = {c.get("key") for c in rec.get("contacts") or []}
        if contact.get("key") not in keys:
            return BLOCKED_WRONG_RECORD
    if dedupe.is_duplicate(contact):
        return BLOCKED_DUPLICATE
    return None


def _selected(rec, contact, campaign=None):
    """Is this contact part of this campaign?

    Deliberately NOT personalization.selected_contacts(): that caps how many
    people are worth RESEARCHING, which is a spending decision. Who gets
    written to is the campaign's contact list, and conflating the two silently
    drops everyone past the research cap.
    """
    if contact.get("excluded"):
        return BLOCKED_NOT_SELECTED
    if campaign is not None:
        ids = set(campaign.get("record_ids") or [])
        if ids and rec.get("id") not in ids:
            return BLOCKED_NOT_SELECTED
    return None


def _campaign(campaign, recs, config, approval_current=None):
    """The campaign's own state. None when there is no campaign in play.

    `approval_current` IS THE SAME ANSWER, COMPUTED ONCE FOR A BATCH.
    `campaigns.approval_is_current` rebuilds the campaign's whole approval
    material, and `material()` rebuilds the cadence for EVERY record in the
    campaign - so asking it once per contact per step made a batch quadratic.
    Measured on 2026-09-11 over a synthetic campaign: `cadence.build` was
    called 5.03 x K^2 times (510 at K=10, 8,040 at K=40), and per-record cost
    grew from 8.6ms at K=10 to 252ms at K=160, fitting K^2.27.

    It is safe to hoist because it is a FACT about (campaign, recs, config),
    all three of which are fixed for the life of a batch loop, and `decide` is
    read-only. It is not an authorization: `executionguard` computes this gate
    freshly at send time on its own path, so a stale batch answer can hold a
    step but can never release one.
    """
    if campaign is None:
        return None
    # BEFORE EVERY OTHER QUESTION, because none of them can be answered.
    # `campaigns.by_record` used to answer `None` here, and `None` returns
    # above as "no campaign in play" - so a record in two live campaigns had
    # its freeze, its pause, its rejection, its launch state and its approval
    # staleness all stop applying at once. Duplicating an intent detached the
    # stop button on the original.
    if campaign.get("ambiguous"):
        return BLOCKED_RECORD_IN_TWO_CAMPAIGNS
    given = campaign.get("approval") or {}
    # Checked before anything else about the campaign: a freeze outranks
    # approval, staleness and launch state, because it is the stop button.
    if campaigns.is_frozen(campaign):
        return BLOCKED_CAMPAIGN_FROZEN
    # Pause is the other stop button, and it stopped nothing here.
    #
    # `orchestrator.pause` sets `status` to `paused`, and this function -
    # which is what decides whether a payload may be built - asked about
    # the freeze, the rejection, the launch state and the approval, and
    # never about the status. So a campaign an operator paused because
    # somebody replied returned `None` from here, and
    # `verify_before_payload` passed it. `campaigns.UNLAUNCHABLE` knows
    # these statuses and is only ever consulted by `validate`, at launch
    # and resume time, which is too late to be a stop button.
    #
    # Deliberately not all of `UNLAUNCHABLE`: the pre-approval statuses
    # are already answered, correctly and more precisely, by
    # `HELD_CAMPAIGN_UNAPPROVED` below. These three are the ones that mean
    # "this campaign was running and is not any more", which is a block
    # rather than a hold - nothing downstream may lift it.
    if campaign.get("status") in (campaigns.PAUSED, campaigns.COMPLETED,
                                  campaigns.FAILED):
        return BLOCKED_CAMPAIGN_STOPPED
    if given.get("action") == "reject" or campaign.get("status") == campaigns.REJECTED:
        return BLOCKED_CAMPAIGN_REJECTED
    if (campaign.get("launch") or {}).get("state") == "launched":
        return BLOCKED_CAMPAIGN_LAUNCHED
    if not given:
        return HELD_CAMPAIGN_UNAPPROVED
    current = (campaigns.approval_is_current(campaign, recs, config)
               if approval_current is None else approval_current)
    if not current:
        return HELD_CAMPAIGN_STALE
    return None


def _mapping(campaign, channel):
    if campaign is None:
        return None
    if channel == EMAIL and not campaign.get("bison_campaign_id"):
        return HELD_NO_MAPPING
    if channel == LINKEDIN and not campaign.get("heyreach_campaign_id"):
        return HELD_NO_MAPPING
    return None


def _already_pushed(rec, contact_key, step_key):
    if push.already_pushed(rec, contact_key, step_key):
        return BLOCKED_ALREADY_PUSHED
    return None


def _due(step, day):
    if day is None:
        return None
    return None if step.get("day", 0) <= day else HELD_NOT_DUE


def _dependency(rec, contact, spec_key, step, timeline):
    """A later step must know what happened to the earlier ones.

    Deliberately narrower than "every earlier step must already be sent". A
    catch-up run legitimately prepares day 1 and day 5 in the same batch, and
    holding the later one because the earlier one is in the same batch would
    stop every backfill the system will ever do.

    What it does catch is a step whose predecessor is *waiting on something*:
    a LinkedIn follow-up whose connection request has not been accepted, or an
    earlier step held on a dependency of its own. Running past one of those is
    how a message arrives referring to a conversation that never happened.
    """
    if step.get("status") == "waiting":
        return HELD_AWAITING_DEPENDENCY
    steps = (timeline or {}).get(contact.get("key")) or {}
    channel = step.get("channel")
    for key, previous in steps.items():
        if previous.get("channel") != channel:
            continue
        if previous.get("day", 0) >= step.get("day", 0):
            continue
        if previous.get("status") == "waiting":
            return HELD_AWAITING_DEPENDENCY
    return None


def _account_fatigue(rec, contact, config):
    """Is the company as a whole already being worked to its limit?

    `_separation` below asks about one person and cannot see a second decision
    maker at the same company on the same day. `fatigue.account_check` asks
    about the company - touches in the last week across every contact, and how
    many decision makers are active at once - and emits BLOCK when either is
    past policy.

    `revival` and `oooreturn` have always enforced it. This path, which sends
    far more than either, did not: `fatigue` had no importer in `eligibility`,
    so the account limits were computed for reports and never for a decision.
    That is what "the account is the unit of outreach" has to mean here.

    Deterministic despite asking a question about time. `at` is left None on
    purpose, and `account_check` then derives its window from the last
    confirmed touch on the record rather than from the clock - so this
    survives a re-run, which is the property `_separation` documents and the
    reason it uses cadence days.
    """
    from . import fatigue

    verdict = fatigue.account_check(rec, config=config,
                                    contact_key=(contact or {}).get("key"))
    return HELD_ACCOUNT_FATIGUE if verdict.get("state") == fatigue.BLOCK else None


def _separation(rec, contact, step, min_days):
    """Two touches to one person should not land on the same day.

    Uses the cadence's own days rather than a clock, so it is deterministic and
    survives a re-run. Where a timezone would matter it is not invented: the
    separation is in whole cadence days.
    """
    if not min_days:
        return None
    day = step.get("day")
    if day is None:
        return None
    for entry in rec.get("events") or []:
        if entry.get("type") != events.PUSH_MARKED:
            continue
        if entry.get("contact") != contact.get("key"):
            continue
        other = entry.get("day")
        if isinstance(other, int) and abs(other - day) < min_days:
            return HELD_CHANNEL_SEPARATION
    return None


# --------------------------------------------------------------- the decision

def decide(rec, contact, step_key, channel=None, campaign=None, recs=None,
           config=None, day=None, timeline=None, suppressed=None,
           min_separation_days=DEFAULT_MIN_SEPARATION_DAYS, step=None,
           approval_current=None):
    """May this one step go out right now? The only authority on the question.

    `step` is the exact content about to be sent. Pass it: a caller that has a
    payload in hand must have THAT text linted and claim-checked, not a freshly
    rebuilt copy. The timeline is still consulted for status and dependencies,
    so a tampered body is caught and a tampered status is ignored.
    """
    if config is None:
        try:
            config = clients.load(rec.get("client"))
        except Exception:
            config = {}
    # Kept apart on purpose. `recs` defaults to this one record so that the
    # per-record questions below - pausing, duplication, separation - can be
    # answered without loading the world. The campaign's own state is not a
    # per-record question: `approval_is_current` fingerprints every record
    # the campaign names, and handing it a one-record list makes every other
    # record look missing, so a live approval reads as stale. A caller that
    # supplied no record set gets None there, which means "load them".
    given_recs = recs
    recs = [rec] if recs is None else recs

    if timeline is None:
        timeline = cadence.build(rec, config, recs=recs,
                                 campaign=campaign).get("contacts") or {}
    steps = timeline.get((contact or {}).get("key")) or {}
    planned = steps.get(step_key)
    if planned is None and step is None:
        return _decide(SKIPPED, [SKIPPED_NO_STEP], step=step_key)
    # Content comes from the caller when it has one; status and dependency
    # always come from the timeline, which the caller cannot fake.
    content = step if step is not None else planned
    planned = planned if planned is not None else step
    channel = channel or content.get("channel") or planned.get("channel")

    # Cheapest and most final first: nothing later can undo these.
    for reason in (*must_not_contact(rec, contact, config=config,
                                     suppressed=suppressed),
                   _identity(rec, contact),
                   _selected(rec, contact, campaign),
                   _already_pushed(rec, contact.get("key"), step_key),
                   # Last of the account-level questions, and before any
                   # content work: a company already worked to its limit is
                   # not made eligible by a well-linted draft, and asking here
                   # means a held account costs no lint and no claim check.
                   _account_fatigue(rec, contact, config)):
        if reason:
            return _decide(BLOCKED if reason.startswith("blocked") else HELD,
                           [reason], step=step_key, channel=channel)

    campaign_reason = _campaign(campaign, given_recs, config, approval_current)
    if campaign_reason:
        return _decide(BLOCKED if campaign_reason.startswith("blocked") else HELD,
                       [campaign_reason], step=step_key, channel=channel)

    checks = (_email_checks if channel == EMAIL else _linkedin_checks)
    verdict, reasons = checks(rec, contact, content, step_key, config)
    if verdict != ELIGIBLE:
        return _decide(verdict, reasons, step=step_key, channel=channel)

    for reason in (_mapping(campaign, channel),
                   _due(planned, day),
                   _dependency(rec, contact, step_key, planned, timeline),
                   _separation(rec, contact, planned, min_separation_days)):
        if reason:
            return _decide(HELD, [reason], step=step_key, channel=channel)

    return _decide(ELIGIBLE, [], step=step_key, channel=channel,
                   push_id=push.push_id(rec, contact.get("key"), step_key,
                                        channel))


def _email_checks(rec, contact, step, step_key, config):
    if not contact.get("email"):
        return BLOCKED, [BLOCKED_NO_RECIPIENT]

    # MX first: it is free, and a blocked gateway makes the rest moot.
    allowed, why = mx.allows_email(contact, config)
    if not allowed:
        # Re-derived from the hostnames, so a tampered status cannot choose a
        # softer reason code than the evidence supports.
        fresh = mx.fresh_decision(contact, config) or mx.stored_decision(contact)
        status = fresh.get("status")
        if status == mx.DNS_FAILURE:
            return HELD, [HELD_DNS_FAILURE]
        if status == mx.KNOWN_BLOCKED:
            return SKIPPED, [SKIPPED_EMAIL_CHANNEL, BLOCKED_MX]
        return SKIPPED, [SKIPPED_EMAIL_CHANNEL]

    # Recomputed from the evidence, never read from the record. `lint.sendable`
    # delegates to `verification.is_sendable`, which re-decides every time, so
    # a hand-edited state or a record enriched under an older policy cannot
    # carry a stale clearance into a payload.
    decision = verification.resolve(contact)
    if not lint.sendable(contact):
        if decision.get("insufficient_confirmations"):
            return HELD, [HELD_INSUFFICIENT_CONFIRMATIONS]
        state = decision.get("state")
        if state in (None, "unknown", "accept_all_uncleared", "held"):
            return HELD, [HELD_VERIFICATION_UNKNOWN]
        return BLOCKED, [BLOCKED_NOT_SENDABLE]

    failures = lint.check(rec, contact.get("key"), step)
    if failures:
        return BLOCKED, [BLOCKED_LINT] + [f"blocked:lint:{f}" for f in failures]

    unsupported = claims.verify(step, rec, contact,
                                _chosen_evidence(rec, contact))
    if unsupported:
        return BLOCKED, [BLOCKED_UNSUPPORTED_CLAIM] + _claim_detail(unsupported)

    if _evidence_aged_out(rec, contact):
        return HELD, [HELD_EVIDENCE_AGED_OUT]

    if not approval.is_approved(rec, contact.get("key"), step_key, step):
        stored = approval.approval_of(rec, contact.get("key"), step_key)
        return HELD, [HELD_APPROVAL_STALE if stored else HELD_APPROVAL_MISSING]
    return ELIGIBLE, []


def _linkedin_checks(rec, contact, step, step_key, config):
    if not linkedin.canonical(contact.get("linkedin")):
        return BLOCKED, [BLOCKED_NO_PROFILE]
    if not (step.get("note") or "").strip():
        return HELD, [HELD_APPROVAL_MISSING]
    if step.get("status") == "waiting":
        return HELD, [HELD_AWAITING_DEPENDENCY]

    # THE SAME TWO CHECKS THE EMAIL BRANCH HAS, ON THE CHANNEL THE DEFECT
    # ACTUALLY HAPPENED ON.
    #
    # `_email_checks` runs `lint.check` and then `claims.verify`. This branch
    # ran neither. The fabrication that prompted all of this - a note telling a
    # real person "you are running utilisation at <their company>", about a company
    # that had never said so - was a LINKEDIN NOTE, and the only code that
    # would have caught it is `executionguard`, which the routine
    # `push.py` -> `eligibility.decide` path does not go through.
    #
    # So the guard existed, was correct, was documented, and was wired to one
    # of the two channels. That is the same shape as the collision check that
    # was hardened on email and left open on LinkedIn.
    failures = lint.check_linkedin(rec, contact.get("key"), step)
    if failures:
        return BLOCKED, [BLOCKED_LINT] + [f"blocked:lint:{f}" for f in failures]

    unsupported = claims.verify(step, rec, contact,
                                _chosen_evidence(rec, contact))
    if unsupported:
        return BLOCKED, [BLOCKED_UNSUPPORTED_CLAIM] + _claim_detail(unsupported) + _claim_detail(unsupported)

    if _evidence_aged_out(rec, contact):
        return HELD, [HELD_EVIDENCE_AGED_OUT]
    if not approval.is_approved(rec, contact.get("key"), step_key, step):
        stored = approval.approval_of(rec, contact.get("key"), step_key)
        return HELD, [HELD_APPROVAL_STALE if stored else HELD_APPROVAL_MISSING]
    return ELIGIBLE, []


def _evidence_aged_out(rec, contact, today=None):
    """Was this draft written from evidence that is no longer usable?

    Approval is a fingerprint of the text, so an approved draft stays
    approved for as long as its words do not change. Its words do not
    change when the fact behind them gets old. That is the gap: a message
    written in March from a fact published in February is approved once and
    remains sendable in September, still saying "recently".

    Only a draft that actually leans on evidence can go stale this way. A
    decision that selected nothing fell back to a verified company fact and
    persona pain, and neither of those ages - `personalization.decide`
    records that as `selected_evidence_ids: []`, and this returns False for
    it rather than holding every fallback message in the estate.

    Held rather than blocked, and the fix is to regenerate: a draft built
    around a fact is not repaired by deleting the sentence that carries it.
    """
    decision = contact.get("personalization") or {}
    ids = {i for i in (decision.get("selected_evidence_ids") or []) if i}
    if not ids:
        return False
    rows = [e for e in rec.get("research") or []
            if e.get("evidence_id") in ids]
    if not rows:
        # The evidence this draft names is not on the record at all. Not
        # staleness - a message citing something we cannot produce - and
        # refused the same way, because the repair is the same.
        return True
    return not evidence.usable(rows, today)


def _chosen_evidence(rec, contact):
    decision = contact.get("personalization") or {}
    ids = set(decision.get("selected_evidence_ids") or [])
    return [e for e in rec.get("research") or [] if e.get("evidence_id") in ids]


# ------------------------------------------------------------------ batching

def for_record(rec, campaign=None, recs=None, config=None, day=None,
               suppressed=None, paused_set=None, approval_current=None):
    """Every step of every contact on one record, decided.

    `paused_set` and `suppressed` are the two things a caller looping over a
    whole batch must hoist. Without them this rescans every record and rereads
    the suppression file once per record, which is quadratic and was measured
    at fifteen seconds for 5,000 domains before it was removed elsewhere.

    `approval_current` IS THE THIRD, and it was the expensive one. See
    `_campaign`: it was measured at 5.03 x K^2 `cadence.build` calls across a
    batch. Hoisted here per record, and a batch caller should hoist it once
    for the whole loop and pass it in.
    """
    if config is None:
        try:
            config = clients.load(rec.get("client"))
        except Exception:
            config = {}
    recs = [rec] if recs is None else recs
    if paused_set is None:
        paused_set = cadence.paused_domains(recs)
    # Asked ONCE for this record rather than once per contact per step. A
    # caller looping a batch should pass it in and pay for it once overall.
    if approval_current is None and campaign is not None:
        approval_current = campaigns.approval_is_current(campaign, recs, config)
    timeline = cadence.build(rec, config, recs=recs, paused_set=paused_set,
                             campaign=campaign).get("contacts") or {}
    suppressed = ingest.load_suppress() if suppressed is None else suppressed
    out = []
    for contact in rec.get("contacts") or []:
        for step_key in (timeline.get(contact.get("key")) or {}):
            out.append({
                "record_id": rec.get("id"), "contact_key": contact.get("key"),
                "step": step_key,
                "decision": decide(rec, contact, step_key, campaign=campaign,
                                   recs=recs, config=config, day=day,
                                   timeline=timeline, suppressed=suppressed,
                                   approval_current=approval_current),
            })
    return out


def summarise(rows):
    counts = {v: 0 for v in VERDICTS}
    reasons = {}
    for row in rows or []:
        decision = row["decision"]
        counts[decision["verdict"]] = counts.get(decision["verdict"], 0) + 1
        for reason in decision["reasons"]:
            reasons[reason] = reasons.get(reason, 0) + 1
    return {"counts": counts, "reasons": reasons}


def require(rec, contact, step_key, channel=None, **kw):
    """Raise unless eligible. What a payload builder calls."""
    decision = decide(rec, contact, step_key, channel=channel, **kw)
    if not decision.eligible:
        raise NotEligible(
            f"{rec.get('id')}:{contact.get('key')}:{step_key}: "
            f"{decision['verdict']} - {', '.join(decision['reasons'])}")
    return decision


class NotEligible(RuntimeError):
    """This step may not go out. The reasons are in the message."""
