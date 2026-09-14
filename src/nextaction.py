#!/usr/bin/env python3
"""What should happen next at this company, to whom, on what channel, and why.

## The question nothing answered

`ACCOUNT-OUTREACH.md` says the account is the unit of outreach. Every part
of that was built - `account.graph` says what happened there, `fatigue`
says how much more may, `collision` says what the provider estate holds,
`eligibility` says whether one step may go, `assignment` says which human
owns a contact, `cadencearms` says which sequence this account runs - and
nothing put them together. An operator asking "what do I do at Acme on
Monday" had six modules and no answer.

This is that answer, and it is deliberately a **read**. It writes nothing,
sends nothing, spends nothing and calls no provider. It composes the
authorities that already exist and reports which one decided.

## It is not a second state machine

Every verdict below is delegated:

    may this person hear anything          eligibility.must_not_contact
    which channels are open to them        channels.evaluate
    is the company worked to its limit     fatigue.account_check
    is this person worked to their limit   fatigue.contact_check
    what does the provider estate hold     collision.account_policy
    which human owns this contact          assignment.assigned / allocate
    which sequence does this account run   cadencearms + cadence.steps_for
    which wording                          cadence.variant_for
    where this person stands on LinkedIn   linkedinstate.plan_step
    what has actually happened here        account.graph

Nothing here re-derives any of those. Where a delegated authority says no,
this module reports its reason verbatim rather than translating it into a
verdict of its own, because two modules answering "is this person
suppressed" is how the two come to disagree.

## Never more permissive than the gate below it

`executionguard.authorize` requires `collision.account_policy(estate) ==
ALLOW`. So does this. An `ACT` this module returns that the send gate would
refuse is worse than useless: it is a plan somebody builds a week around.

`ACT` therefore means "every authority this module can consult says yes".
It is still not permission to send - `eligibility.decide` and
`executionguard.authorize` run against the real step and the real estate at
the moment of sending, and either may refuse. Nothing here reserves
anything.

## Three answers, and the middle one is the load-bearing one

    ACT    there is a person, a channel, a sender and a sequence position,
           and nothing argues against it right now
    WAIT   nothing may go now, and the reason may stop being true. The
           decision names what would have to change, and `execute_after`
           when the change is a clock
    STOP   nothing more goes to this account, and no clock changes that

`WAIT` is where account-based sequencing actually lives. "The second
stakeholder opens on day four" is not a rule written here; it is what
falls out of `account.min_hours_between_first_touches`, and moving that
number moves the plan. A hypothesis hard-coded into a planner is a
hypothesis nobody can test.

## `execute_after` is a floor, never a trigger

A time passing is not a reason to write to somebody - `revival` makes the
same point about ninety days. `execute_after` says the earliest moment an
action may be reconsidered, and reconsidering it runs every gate again.

## The provider estate is asked for, never fetched

`estate` is the result of `collision.check_account`, supplied by a caller
that has already paid for the read. This module never calls it: a planner
that fetched its own provider evidence would be a planner that spends
credits every time a screen is refreshed, and would make an offline plan
impossible.

Absent estate is **not** a clear sheet. It is `WAIT`, because somebody at
this account may be mid-sequence right now and nobody has looked.
"""
import argparse
import json

from . import (account, accountsaturation, assignment, cadence, cadencearms,
               channels, clients, collision, eligibility, fatigue,
               linkedinstate, personas, routing, senderidentity as si, store)

# ------------------------------------------------------------- the answers

ACT = "act"
WAIT = "wait"
STOP = "stop"
ACTIONS = (ACT, WAIT, STOP)

# ------------------------------------------------------------ why, exactly
#
# Stable vocabulary, because reports and screens read it. The human sentence
# lives beside each decision in `reason`; this is the thing to group by.

STOP_ANSWERED = "stop:account_answered"
STOP_SUPPRESSED = "stop:account_suppressed"
STOP_NO_WORKABLE_CONTACT = "stop:no_contact_can_be_worked"
STOP_SATURATED_UNSUBSCRIBED = "stop:contact_unsubscribed_stops_account"
STOP_SATURATED_POSITIVE = "stop:positive_reply_stops_account"

WAIT_ESTATE_UNREAD = "wait:provider_estate_unread"
WAIT_ESTATE_HOLD = "wait:provider_estate_hold"
WAIT_IN_SEQUENCE = "wait:someone_here_is_in_sequence"
WAIT_ACCOUNT_HELD = "wait:account_held"
WAIT_ACCOUNT_FATIGUE = "wait:account_fatigue"
# Deliberately not the same code as account fatigue. "This company has had
# enough this week" and "this company already has three people open" have
# different remedies - one is a clock, the other is a decision to close
# somebody out - and a screen that showed them as one reason would send an
# operator to wait for a week that was never the problem.
WAIT_ACCOUNT_CONCURRENCY = "wait:account_concurrency"
WAIT_CONTACT_FATIGUE = "wait:contact_fatigue"
WAIT_SPACING = "wait:spacing"
WAIT_NO_SENDER = "wait:no_sender_available"
WAIT_NO_CHANNEL = "wait:no_channel_open"
WAIT_NO_STEP = "wait:no_step_left"
WAIT_NO_CANDIDATE = "wait:no_contact_actionable_now"

# The LinkedIn branch. Four codes rather than one, because they are four
# different remedies and an operator acts on the remedy: wait for them to
# accept, go and read the provider, get the capability validated, or nothing
# - this person is not reachable on LinkedIn at all. `linkedinstate` decides;
# these are the planner's names for what it decided, mapped once in
# `_linkedin_reason` so there is one translation rather than one per branch.
WAIT_CONNECTION_PENDING = "wait:connection_request_pending"
WAIT_CONNECTION_UNREAD = "wait:connection_acceptance_unread"
WAIT_LINKEDIN_CAPABILITY = "wait:linkedin_capability_unproven"
WAIT_LINKEDIN_STATE = "wait:linkedin_state"

_LINKEDIN_REASON = {
    linkedinstate.HELD_REQUEST_OUTSTANDING: WAIT_CONNECTION_PENDING,
    linkedinstate.HELD_ACCEPTANCE_UNREAD: WAIT_CONNECTION_UNREAD,
    linkedinstate.HELD_CAPABILITY_UNPROVEN: WAIT_LINKEDIN_CAPABILITY,
    linkedinstate.HELD_INMAIL_UNAVAILABLE: WAIT_LINKEDIN_CAPABILITY,
    linkedinstate.HELD_ACTION_UNKNOWN: WAIT_LINKEDIN_CAPABILITY,
}


def _linkedin_reason(move):
    """One of this module's codes for what the LinkedIn branch decided.

    Unmapped is `WAIT_LINKEDIN_STATE` rather than a guess at a nearer code:
    a branch this planner has no name for is reported as the branch, with
    `linkedinstate`'s own sentence, exactly as an unmapped eligibility reason
    is reported verbatim rather than translated.
    """
    return _LINKEDIN_REASON.get(move.get("code"), WAIT_LINKEDIN_STATE)

# A bounce is a fact about one address. It closes that identity's email
# channel and it closes nothing else - not their LinkedIn, and not the
# account. Naming it here rather than folding it into "not sendable"
# because the remedy is different: a bounce needs a new address, and a
# failed verification needs a second verifier.
CONTACT_BOUNCED = "contact:email_bounced"

# `eligibility.must_not_contact` answers about a person, and its reasons
# divide into two kinds. These are the ones no clock undoes.
TERMINAL_CONTACT_REASONS = frozenset({
    eligibility.BLOCKED_UNSUBSCRIBED,
    eligibility.BLOCKED_SUPPRESSED,
    eligibility.BLOCKED_CLIENT_SUPPRESSED,
    eligibility.BLOCKED_AGENCY_DNC,
    eligibility.BLOCKED_ACCOUNT_SUPPRESSED,
    eligibility.BLOCKED_CONTACT_STOPPED,
    eligibility.BLOCKED_DROPPED,
    eligibility.BLOCKED_REPLIED,
    eligibility.BLOCKED_DUPLICATE,
    eligibility.BLOCKED_NOT_SELECTED,
    eligibility.BLOCKED_WRONG_RECORD,
})

# Reasons that mean the whole company is finished, whichever contact they
# arrived on.
ACCOUNT_TERMINAL_REASONS = frozenset({
    eligibility.BLOCKED_ACCOUNT_SUPPRESSED,
    eligibility.BLOCKED_SUPPRESSED,
    eligibility.BLOCKED_CLIENT_SUPPRESSED,
    eligibility.BLOCKED_AGENCY_DNC,
    eligibility.BLOCKED_DROPPED,
})

EMAIL = channels.EMAIL
LINKEDIN = channels.LINKEDIN

# Which channel to prefer when both are open and neither has been used.
# Email first is this client's own shape - `cadence.STEPS` opens on day 1
# with an email - and it is read from the sequence rather than stated, so a
# LinkedIn-led sequence leads on LinkedIn without an edit here.


def _decision(action, reason_code, reason, **fields):
    out = {
        "action": action,
        "reason_code": reason_code,
        "reason": reason,
        "person": None,
        "person_name": None,
        "channel": None,
        "sender": None,
        "campaign": None,
        "angle": None,
        "copy": None,
        "execute_after": None,
        "experiment": None,
        "linkedin": None,
        "considered": [],
    }
    out.update(fields)
    return out


# ------------------------------------------------------------------- time

def _plus_hours(iso, hours):
    """`iso` moved forward by `hours`, or None if it will not parse.

    Unparseable in means unparseable out. A planner that invented a
    timestamp here would hand an operator a date derived from nothing,
    which is worse than "we cannot say when".
    """
    import datetime

    if not iso or not hours:
        return None
    try:
        stamp = datetime.datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None
    return (stamp + datetime.timedelta(hours=float(hours))).isoformat()


def _latest(*stamps):
    found = [s for s in stamps if s]
    return max(found, key=str) if found else None


# ------------------------------------------------------- who, in what order

def _persona_priority(rec, config):
    """The client's own stated order of personas for a company this shape.

    `routing.strategy_for` reads the segment the qualifier already wrote.
    Nothing is invented: a record with no segment gets the fallback
    strategy, which is exactly what `routing` does for it everywhere else.
    """
    segment = (((rec.get("qualification") or {}).get("segment")) or {})
    name, why = routing.strategy_for(segment, config)
    spec = routing.settings(config)["strategies"][name]
    return name, why, list(spec["priority"]), spec["personas"]


def rank(rec, config=None):
    """Every contact on the record, best first, each carrying why it ranks.

    Ordering, in order of authority:

      1. the client's stated persona priority for a company this size and
         shape - a go-to-market decision, not a guess
      2. `primary`, which `personas.select` wrote onto exactly one sendable
         contact
      3. a usable address or profile
      4. the key, so the order is total and a rerun does not reshuffle

    Deliberately NOT `contact["selected"]`. Nothing in the live pipeline
    writes that field - `personas.select` writes `primary` - so ranking on
    it would rank every real contact identically while looking like it had
    an opinion - measured: 0 of 300 Productive records carry the field.
    """
    config = config or clients.load(rec.get("client"))
    strategy, why, priority, families = _persona_priority(rec, config)
    out = []
    for contact in account.contacts_of(rec):
        family, family_rank = personas.family_of(contact, priority, families)
        out.append({
            "contact": contact,
            "key": contact.get("key"),
            "name": contact.get("name"),
            "title": contact.get("title"),
            "persona": contact.get("persona"),
            "family": family,
            "family_rank": family_rank,
            "primary": bool(contact.get("primary")),
            "strategy": strategy,
            "why_rank": (f"{strategy}: {family or 'no persona family'} is "
                         f"#{family_rank + 1} of {len(priority)} for this "
                         f"client" + (", and this is the primary contact"
                                      if contact.get("primary") else "")),
        })
    out.sort(key=lambda e: (e["family_rank"],
                            0 if e["primary"] else 1,
                            0 if e["contact"].get("sendable") else 1,
                            0 if e["contact"].get("email") else 1,
                            str(e["key"] or "")))
    return out


# ------------------------------------------------------ the account gates

def _account_verdict(rec, graph, estate, config, at):
    """The company-level answer, or None when the company is workable.

    Order is most final first, and the provider estate is consulted before
    anything expensive: an account somebody else is mid-sequence at is not
    made workable by a well-ranked contact.
    """
    # 1. The reasons no clock undoes, read from canonical state.
    if (rec.get("suppression") or {}).get("unsubscribed"):
        return _decision(
            STOP, STOP_SUPPRESSED,
            "this company asked not to be contacted; that is not a hold "
            "somebody lifts")
    if rec.get("state") == "dropped" or rec.get("drop_reason"):
        why = rec.get("drop_reason") or "no reason recorded"
        return _decision(STOP, STOP_SUPPRESSED,
                         f"the record is dropped: {why}")

    # 1b. Account saturation: a contact-level event that reaches the whole
    #     account. An unsubscribe from one person stops the account -
    #     continuing to contact their colleagues reads as one organisation
    #     that does not talk to itself. A positive reply stops the account
    #     too - the conversation is starting and cold outreach to colleagues
    #     would undermine it.
    saturation = accountsaturation.verdict(rec, config=config, at=at)
    if saturation["state"] == accountsaturation.STOP:
        if saturation["reason"] == accountsaturation.UNSUBSCRIBED:
            return _decision(
                STOP, STOP_SATURATED_UNSUBSCRIBED, saturation["why"])
        if saturation["reason"] == accountsaturation.POSITIVE_REPLY:
            return _decision(
                STOP, STOP_SATURATED_POSITIVE, saturation["why"])
        return _decision(STOP, STOP_SUPPRESSED, saturation["why"])

    # 2. The provider estate. Absent is not clear.
    if estate is None:
        return _decision(
            WAIT, WAIT_ESTATE_UNREAD,
            "nobody has read the provider estate for this domain, so it "
            "cannot be said that nobody here is already in a sequence. "
            "Read it with collision.check_account before planning anything")
    decision, why = collision.account_policy(estate)
    if decision != collision.ALLOW:
        # `account_policy` says STOP for two different facts and an
        # orchestrator has to tell them apart: an answered account is
        # finished, and a mid-sequence account is a NOT YET. It is refined
        # here, never widened - neither branch can produce ACT.
        if decision == collision.STOP and estate.get("anyone_in_sequence"):
            return _decision(WAIT, WAIT_IN_SEQUENCE, why)
        if decision == collision.STOP:
            return _decision(STOP, STOP_ANSWERED, why)
        return _decision(WAIT, WAIT_ESTATE_HOLD, why)

    # 3. A reply somewhere here holds the company, and a review does too.
    #    Read through `eligibility`, which is the authority, rather than
    #    from the flags directly.
    if (rec.get("review") or {}).get("open"):
        return _decision(
            WAIT, WAIT_ACCOUNT_HELD,
            "a person has to look at this account before anything else "
            "goes out")
    if cadence.pause_state(rec, config):
        return _decision(
            WAIT, WAIT_ACCOUNT_HELD,
            "this company is held: somebody here replied and the reply "
            "policy holds the account")

    # 4. Fatigue, last of the account questions and the only one with a
    #    clock on it.
    verdict = fatigue.account_check(rec, at=at, config=config)
    if verdict["state"] == fatigue.BLOCK:
        return _decision(
            WAIT, WAIT_ACCOUNT_FATIGUE,
            "; ".join(f["why"] for f in verdict["findings"]),
            execute_after=_account_window_clears(graph, config, at),
            fatigue=verdict)
    return None


def _account_window_clears(graph, config, at):
    """When the company's rolling week has room again.

    The oldest touch inside the window ages out first, so that plus seven
    days is the earliest the count can fall. Returns None when there is no
    dated touch to measure from rather than guessing at one.
    """
    dated = sorted((t.get("at") for t in graph["confirmed_touches"]
                    if t.get("at")), key=str)
    if not dated:
        return None
    return _plus_hours(dated[0], 24 * 7)


# ------------------------------------------------------ the contact gates

def _channel_order(steps, contact_channels):
    """Which channel to try first, taken from the sequence rather than set.

    The sequence's own first contacting step decides. A LinkedIn-led
    cadence therefore leads on LinkedIn with no edit here, which is the
    difference between a configurable plan and a hard-coded one.
    """
    order = []
    for spec in steps:
        channel = spec.get("channel")
        if channel and channel not in order:
            order.append(channel)
    for channel in (EMAIL, LINKEDIN):
        if channel not in order:
            order.append(channel)
    return [c for c in order if c in contact_channels]


def _next_step(rec, contact, steps, channel, graph, config=None, at=None,
               observed=None):
    """The first step on this channel this contact may be sent. `(spec, move)`.

    Read from the confirmed and planned touches on the record, which is
    where "we already did that one" actually lives. A step already pushed
    is not offered again; `eligibility._already_pushed` says the same
    thing at the gate, and this is the plan-time half of it.

    On LinkedIn the sequence position is not enough, because the cadence
    BRANCHES: a connection request to somebody already connected is not the
    next step, it is a step that no longer applies, and the messages behind
    it are what is left. `linkedinstate.plan_step` is the authority on that
    and is asked per candidate step.

    The two answers it can give are not the same and the difference is the
    point. `skip` advances - the step is pointless and the lane carries on.
    `wait` stops - the lane is held, the step still belongs to the cadence,
    and walking past it would send a later message claiming a conversation
    the earlier one never opened. Nothing here silently drops a LinkedIn
    step: a cadence that reports eleven touches and sends ten is what that
    produces.
    """
    contact_key = (contact or {}).get("key")
    done = {t.get("step") for t in graph["touches"]
            if t.get("contact_key") == contact_key}
    for spec in steps:
        if spec.get("channel") != channel:
            continue
        if spec.get("key") in done:
            continue
        if channel != LINKEDIN:
            return spec, None
        move = linkedinstate.plan_step(rec, contact, spec, observed=observed,
                                       steps=steps, config=config, at=at)
        if move["status"] == linkedinstate.SKIP:
            continue
        if move["status"] == linkedinstate.WAIT:
            return None, move
        return spec, move
    return None, None


def _bounced_channels(rec, contact_key):
    """Channels this identity's own history has closed.

    An `email_bounced` event is a fact about one address at one company.
    It closes email for that person and nothing else: not their LinkedIn,
    and not their colleagues - a colleague's address is a different
    address, and a bounce is not an opinion about the company.
    """
    closed = {}
    for entry in account.bounces(rec, contact_key):
        closed[entry.get("channel") or EMAIL] = (
            "this address bounced on "
            f"{entry.get('at') or 'an unrecorded date'}; a bounced address "
            "is not a deliverability question, it is a wrong address")
    return closed


def _sender_for(rec, contact, channel, workspace, rows, config, campaign):
    """The human who owns this contact on this channel, and their account.

    The stored assignment wins, always: `assignment` exists because a
    prospect who hears from Anna on Monday must not hear from Mark on
    Friday because an inbox was added in between. Where nothing is stored,
    `allocate` is asked - it is pure and stores nothing, so a plan does not
    silently fix an assignment somebody has not acted on.
    """
    stored = assignment.assigned(contact, channel)
    if stored:
        return dict(stored, via=stored.get("via") or "stored"), None
    try:
        return assignment.allocate(workspace, contact.get("key"), channel,
                                   rows=rows, config=config,
                                   campaign=campaign), None
    except assignment.NoEligibleSender as e:
        return None, str(e)


def _consider(rec, entry, graph, steps, config, workspace, rows, campaign,
              at, suppressed, linkedin_observed=None):
    """One contact, every per-person gate, in order of finality.

    Returns a candidate dict. `ok` says whether it can be acted on now;
    `terminal` says whether a clock could ever change that.
    """
    contact = entry["contact"]
    key = entry["key"]
    out = dict(entry)
    out.pop("contact", None)
    out.update({"ok": False, "terminal": False, "channel": None,
                "sender": None, "step": None, "execute_after": None,
                "why": None, "reason_code": None, "linkedin": None})

    # 1. May this person hear anything at all.
    reasons = [r for r in eligibility.must_not_contact(
        rec, contact, config=config, suppressed=suppressed) if r]
    if reasons:
        out["reason_code"] = reasons[0]
        out["why"] = eligibility.explain(reasons[0])
        out["terminal"] = reasons[0] in TERMINAL_CONTACT_REASONS
        out["account_terminal"] = reasons[0] in ACCOUNT_TERMINAL_REASONS
        return out

    # 2. Which channels are open, and which this identity has closed.
    verdicts = channels.evaluate(rec, contact, config=config,
                                 suppressed=suppressed)
    open_channels = {c for c in (EMAIL, LINKEDIN)
                     if verdicts.get(f"{c}_eligible")}
    closed_why = {c: channels.explain(verdicts.get(f"{c}_excluded_reason"))
                  for c in (EMAIL, LINKEDIN) if c not in open_channels}
    bounced = _bounced_channels(rec, key)
    for channel, why in bounced.items():
        open_channels.discard(channel)
        closed_why[channel] = CONTACT_BOUNCED
    out["closed_channels"] = closed_why
    out["bounced"] = sorted(bounced)
    if not open_channels:
        out["reason_code"] = WAIT_NO_CHANNEL
        out["why"] = ("; ".join(f"{c}: {w}" for c, w in sorted(
            closed_why.items()) if w) or "no channel is open to this person")
        return out

    # 3. Pacing, both levels, through the one module that owns it.
    #
    # `fatigue.check` is asked rather than `contact_check`, because the
    # account half answers a question only a named candidate can ask:
    # `max_active_contacts` is about OPENING THIS PERSON, and
    # `account_check` without a `contact_key` cannot see the person about
    # to be added. Asking it at the account level - as the account gate
    # above does for the weekly count - would let a fourth decision maker
    # open at a company whose limit is three.
    verdict = fatigue.check(rec, key, at=at, config=config)
    if verdict["state"] == fatigue.BLOCK:
        blocking = [f["why"] for f in verdict["findings"]
                    if f["level"] == fatigue.BLOCK]
        contact_blocked = any(f["level"] == fatigue.BLOCK
                              for f in verdict["contact"]["findings"])
        out["reason_code"] = (WAIT_CONTACT_FATIGUE if contact_blocked
                              else WAIT_ACCOUNT_CONCURRENCY)
        out["why"] = "; ".join(blocking)
        out["execute_after"] = (_contact_window_clears(rec, key, config, at)
                                if contact_blocked else None)
        return out

    # 4. A channel with a step left, a sender, and a place in the sequence.
    problems = []
    for channel in _channel_order(steps, open_channels):
        spec, move = _next_step(rec, contact, steps, channel, graph,
                                config=config, at=at,
                                observed=linkedin_observed)
        if spec is None and move is not None:
            # The LinkedIn branch holds this lane. Its own sentence is
            # reported verbatim and its `execute_after` travels with it -
            # "they have not accepted yet" carries a window, and "nobody has
            # read the provider" carries no clock at all, because no amount
            # of waiting performs the read.
            problems.append((_linkedin_reason(move), move["why"],
                             move.get("execute_after")))
            out["linkedin"] = {"state": move["state"],
                               "action": move["action"],
                               "code": move["code"], "why": move["why"]}
            continue
        if spec is None:
            problems.append((WAIT_NO_STEP,
                             f"every {channel} step in this sequence has "
                             f"already been sent to this person", None))
            continue
        sender, refusal = _sender_for(rec, contact, channel, workspace, rows,
                                      config, campaign)
        if sender is None:
            problems.append((WAIT_NO_SENDER, refusal, None))
            continue
        if move is not None:
            out["linkedin"] = {"state": move["state"],
                               "action": move["action"],
                               "code": move["code"], "why": move["why"]}
        out.update({"ok": True, "channel": channel, "sender": sender,
                    "step": dict(spec),
                    "execute_after": _when(rec, graph, key, config, at)})
        return out

    if problems:
        out["reason_code"], out["why"], due = problems[0]
        out["execute_after"] = due
    else:
        out["reason_code"], out["why"] = (
            WAIT_NO_CHANNEL, "no channel is open to this person")
    return out


def _contact_window_clears(rec, contact_key, config, at):
    confirmed = account.touches(rec, contact_key, confirmed_only=True)
    dated = sorted((t.get("at") for t in confirmed if t.get("at")), key=str)
    if not dated:
        return None
    rules = fatigue.limits(config)
    return _latest(
        _plus_hours(dated[-1],
                    rules["contact.min_hours_between_touches"]["value"]),
        _plus_hours(dated[0], 24 * 7))


def _when(rec, graph, contact_key, config, at):
    """The earliest moment this touch may be reconsidered.

    Three floors, and the latest wins:

      the minimum gap since this person's own last touch
      the minimum gap since the last person here was OPENED, when this
        person has not been opened yet
      now

    The second is the whole of account-level sequencing. "The second
    stakeholder opens on day four" is `account.min_hours_between_first_
    touches` and nothing else, so moving that number moves the plan and a
    test can move it.
    """
    rules = fatigue.limits(config)
    mine = account.touches(rec, contact_key, confirmed_only=True)
    floors = [at]
    if mine:
        floors.append(_plus_hours(
            mine[-1].get("at"),
            rules["contact.min_hours_between_touches"]["value"]))
    else:
        opened = sorted((c["confirmed_touches"][0].get("at")
                         for c in graph["contacts"]
                         if c["confirmed_touches"]), key=str)
        if opened:
            floors.append(_plus_hours(
                opened[-1],
                rules["account.min_hours_between_first_touches"]["value"]))
    return _latest(*floors)


# --------------------------------------------------------- the experiment

def _experiment(campaign, rec, config):
    """Which arm this ACCOUNT is in, and the sequence that arm runs.

    Deterministic on `(experiment_id, unit_key, allocation_version)` and
    sticky: `cadencearms.choose` returns a recorded assignment unchanged
    and otherwise computes the same bucket every time, so a restart, a
    reload, or a second process land in the same arm.

    `choose` records nothing. An assignment written by whoever happened to
    open a screen is an assignment nobody decided.
    """
    exp = (campaign or {}).get(cadencearms.EXPERIMENT_KEY)
    if not exp:
        return None, cadence.steps_for(campaign, config, rec)
    entry, why = cadencearms.choose(exp, rec)
    if entry is None:
        return ({"experiment_id": exp.get("experiment_id"), "arm_id": None,
                 "unit": exp.get("unit"), "why": why},
                cadence.steps_for(campaign, config, rec))
    steps = entry.get("steps") or cadence.steps_for(campaign, config, rec)
    return ({"experiment_id": exp.get("experiment_id"),
             "arm_id": entry.get("arm_id"),
             "label": entry.get("label"),
             "unit": exp.get("unit"),
             "unit_key": cadencearms.unit_key(exp, rec),
             "recorded": bool(cadencearms.recorded(exp, rec)),
             "why": why}, cadence.validate_steps(steps))


# --------------------------------------------------------- the whole thing

def next_best_action(rec, *, config=None, campaign=None, workspace=None,
                     estate=None, rows=None, at=None, suppressed=None,
                     linkedin=None):
    """The one thing to do next at this company, or why nothing may be done.

    `estate` is `collision.check_account(domain, expect_workspace=...)`,
    already paid for by the caller. This function performs no provider
    call of any kind, and `None` means WAIT rather than clear.

    `linkedin` is the same arrangement for the other provider: a mapping of
    contact key to `linkedinstate.observation`, built from a read the caller
    has already performed. Absent is not "not connected" - it is the state
    machine's own `UNKNOWN_ACCEPTANCE` wherever a request has gone out,
    which is a WAIT naming the read that would settle it.

    Writes nothing. Reserves nothing. Returns a decision; acting on it
    still runs `eligibility.decide` and `executionguard.authorize`, both of
    which may refuse.
    """
    config = config or clients.load(rec.get("client"))
    workspace = workspace or (campaign or {}).get("client") or rec.get("client")
    rows = si.load() if rows is None else rows
    at = at or store.now()

    graph = account.graph(rec, workspace=workspace, rows=rows, config=config)
    base = {
        "record_id": rec.get("id"),
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "at": at,
        "campaign": (campaign or {}).get("campaign_id"),
        "counts": dict(graph["counts"]),
    }

    experiment, steps = _experiment(campaign, rec, config)
    base["experiment"] = experiment

    linkedin = linkedin or {}
    considered = [
        _consider(rec, entry, graph, steps, config, workspace, rows,
                  campaign, at, suppressed, linkedin.get(entry["key"]))
        for entry in rank(rec, config)
    ]
    base["considered"] = considered

    verdict = _account_verdict(rec, graph, estate, config, at)
    if verdict is not None:
        # Populate `considered` so the decision reports what was on the table.
        # A held account stays held; this is about what the decision reports
        # about itself, not about changing what is decided.
        verdict["considered"] = considered
        verdict.update(base)
        return verdict

    for candidate in considered:
        if candidate.get("account_terminal"):
            out = _decision(STOP, STOP_SUPPRESSED,
                            candidate["why"] or "this company is suppressed")
            out.update(base)
            return out

    ready = [c for c in considered if c["ok"]]
    if not ready:
        if considered and all(c["terminal"] for c in considered):
            out = _decision(
                STOP, STOP_NO_WORKABLE_CONTACT,
                "every decision maker we know here is finished: "
                + "; ".join(f"{c['name'] or c['key']} - {c['why']}"
                            for c in considered))
            out.update(base)
            return out
        soonest = _soonest(c.get("execute_after") for c in considered)
        out = _decision(
            WAIT, WAIT_NO_CANDIDATE,
            "; ".join(f"{c['name'] or c['key']} - {c['why']}"
                      for c in considered)
            or "there is nobody at this company to work",
            execute_after=soonest)
        out.update(base)
        return out

    # Whoever ranks best among those that can be acted on. The ranking is
    # `rank()`'s and is not re-derived here.
    best = ready[0]
    due = best["execute_after"]
    if due and str(due) > str(at):
        out = _decision(
            WAIT, WAIT_SPACING,
            f"{best['name'] or best['key']} is the next person here, and the "
            f"spacing policy puts the earliest touch at {due}",
            person=best["key"], person_name=best["name"],
            channel=best["channel"], sender=best["sender"],
            execute_after=due)
        out.update(base)
        out["considered"] = considered
        return out

    contact = next(c for c in account.contacts_of(rec)
                   if c.get("key") == best["key"])
    spec = best["step"]
    out = _decision(
        ACT, None,
        f"{best['name'] or best['key']} is #{1 + considered.index(best)} of "
        f"{len(considered)} here ({best['why_rank']}), {best['channel']} is "
        f"open, and no account, contact, provider or fatigue rule argues "
        f"against step {spec.get('key')} now",
        person=best["key"], person_name=best["name"],
        channel=best["channel"], sender=best["sender"],
        linkedin=best.get("linkedin"),
        angle=contact.get("angle"),
        copy=_copy(rec, contact, spec, config, campaign),
        execute_after=due or at)
    out.update(base)
    out["considered"] = considered
    return out


def _soonest(stamps):
    found = sorted((s for s in stamps if s), key=str)
    return found[0] if found else None


def _copy(rec, contact, spec, config, campaign):
    """Which words this step would carry, named rather than rendered.

    The variant is resolved because it is an experiment assignment and has
    to be reportable before anything is sent. The body is not rendered:
    generation, lint and approval own the words, and a planner producing a
    second copy of them is a second copy to fall out of step.
    """
    entry = cadence.variant_for(spec, campaign, contact.get("key"),
                                config=config)
    stored = ((rec.get("cadence") or {}).get(contact.get("key")) or {}).get(
        spec.get("key")) or {}
    return {
        "step_key": spec.get("key"),
        "day": spec.get("day"),
        "template": spec.get("template"),
        "generated": bool(spec.get("generated")),
        "variant_id": (entry or {}).get("variant_id"),
        "variant_style": (entry or {}).get("style"),
        "drafted": bool(stored.get("body") or stored.get("note")),
        "approved": bool(stored.get("approved")),
    }


# --------------------------------------------------------------- the plan

def plan(recs, *, config=None, campaign=None, workspace=None, estates=None,
         rows=None, at=None, observations=None):
    """`next_best_action` over a cohort, act-first.

    `estates` maps domain to a `collision.check_account` result. A record
    with no entry is planned as estate-unread, which is a WAIT with a named
    remedy rather than a silent omission.

    `observations` maps record id to `{contact_key: linkedinstate.
    observation}`, from a provider read the caller has already performed.
    Absent is the LinkedIn branch's own unread state, not a clear one.
    """
    estates = estates or {}
    observations = observations or {}
    rows = si.load() if rows is None else rows
    at = at or store.now()
    out = []
    for rec in recs:
        cfg = config or clients.load(rec.get("client"))
        out.append(next_best_action(
            rec, config=cfg, campaign=campaign, workspace=workspace,
            estate=estates.get(rec.get("domain")), rows=rows, at=at,
            linkedin=observations.get(rec.get("id"))))
    order = {ACT: 0, WAIT: 1, STOP: 2}
    out.sort(key=lambda d: (order.get(d["action"], 3),
                            str(d.get("execute_after") or ""),
                            str(d.get("record_id") or "")))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.nextaction",
                                description=__doc__)
    p.add_argument("--client", required=True)
    p.add_argument("--id", action="append", dest="ids")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    config = clients.load(a.client)
    recs = [r for r in store.load() if r.get("client") == a.client
            and (not a.ids or r.get("id") in a.ids)]
    rows = plan(recs, config=config, workspace=a.client)
    if a.json:
        print(json.dumps(rows, indent=2, default=str))
        return 0
    for row in rows:
        print(f"{row['action'].upper():<5} {row.get('domain') or row['record_id']}")
        if row.get("person"):
            print(f"      {row['person_name'] or row['person']} / "
                  f"{row.get('channel')} / "
                  f"{(row.get('sender') or {}).get('sender_id') or 'no sender'}")
        print(f"      {row.get('reason_code') or 'act'}: {row['reason']}")
        if row.get("execute_after"):
            print(f"      not before {row['execute_after']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
