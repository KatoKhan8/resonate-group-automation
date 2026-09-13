#!/usr/bin/env python3
"""Where one prospect stands on LinkedIn, and what that permits next.

## The question nothing answered

`cadence.accepted_connection` returns a boolean. That was the whole of this
system's LinkedIn state model, and a boolean cannot tell apart the three
facts an event-driven cadence has to act on differently:

    they declined                     nobody ever asked
    they have not accepted YET        nobody has READ whether they accepted

All three answer `False`, and every one of them wants a different next
action. Treating the second and third as "not accepted" is what would send
an InMail to somebody whose acceptance simply has not been read, and
treating the first as "not yet" is what would leave a lane waiting for ever.

So the connection axis gets a state with a word for each, an explicit
unknown, and a rule that no clock ever produces evidence.

## One axis, and deliberately only one

Three kinds of state exist at an account and this module holds exactly one
of them:

    ACCOUNT state    `accountpolicy.account_state`, `cadence.pause_state`
    PERSON state     `eligibility.must_not_contact` - suppressed, stopped,
                     unsubscribed, replied. Canonical, and NOT copied here
    CHANNEL state    this module, for LinkedIn; `channels.email_verdict`
                     for email

`SUPPRESSED` and `STOPPED` are person facts and they are not represented
here at all: a second copy of "has this person asked us to stop" is how the
two come to disagree, and that is the one rule in this repository that must
not have two implementations. A caller runs the person gate first. What
this module adds on top is one guard it shares with `eligibility._replied`
- a recorded reply from this contact ends the connection axis, whichever
channel it arrived on - kept for the reason `ACCOUNT-OUTREACH.md` §12 gives
for keeping two independent cross-channel stops: they fail for different
reasons, so both are worth naming.

## It reads the cadence's own vocabulary

`src/cadencelibrary.py` is where a LinkedIn step says what it is:
`linkedin_action` (connect, message, inmail, open_profile_message),
`requires` (the prospect state it needs) and `capability` (the provider
capability it depends on). Every word below is that module's, imported
rather than restated, so a sequence and the machine that runs it cannot
disagree about what a step asked for.

`alternative` is the branch. A step may carry one, and where the
alternative's `requires` is satisfied the alternative IS the step - it is
never a silent fallback in either direction. A cadence that quietly drops
its InMail fallback reports eleven touches and sends ten; a cadence that
quietly runs the primary instead sends a connection request to somebody it
had decided to InMail.

## Missing evidence is never positive evidence

Every state here is read from a recorded event or from a provider
observation a caller already paid for. Nothing is derived from elapsed
time, from campaign status, or from the absence of a record.

The wait window is the sharp case. "Not accepted after seven days" reads
like a timer and it is not one: the window decides when the QUESTION may be
asked, and only provider truth answers it. A window that has expired with
nobody having read the provider returns `UNKNOWN_ACCEPTANCE`, which is a
wait naming the read that would settle it - the same shape as
`nextaction`'s absent provider estate, and for the same reason.

## The provider is asked for, never fetched

`observed` is a trimmed dict a caller supplies, built from a read it has
already performed - `leadobserve.observe` / `heyreach.lead_state`. This
module performs no provider call of any kind and imports no provider, so a
plan can be built offline and a screen refresh spends nothing.

`from_provider_lifecycle` is the one translation table, an ALLOWLIST. A
word this system has never seen becomes `UNKNOWN` and is reported with the
word beside it, never folded into a neighbouring state.

## An unproven capability is a HOLD, not an assumption

`CAPABILITIES` classifies every capability a sequence may name. Two are
proven and two are not:

`linkedin.connection_request` and `linkedin.message` are node types
observed in real HeyReach sequences read from this repository -
`heyreach.LINKEDIN_ONLY_NODES` is that allowlist - and `CADENCE-MODEL.md`
§4 marks the same two validated.

`linkedin.open_profile_message` is unproven: nothing anywhere here reads
whether a profile is open. `linkedin.inmail` is unproven: no InMail node
has ever been observed in a sequence read from here, and the only InMail
field in this repository is `inMailCooldown` on a SEAT, which is a fact
about our sender rather than about whether this prospect can receive one.

A step naming an unproven capability is held with that named as the reason,
and a capability nobody has classified at all is held too. Flipping an
entry to `True` is what a validated capability looks like; nothing else
here changes when one is proven.
"""
import argparse
import datetime
import json

from . import cadencelibrary as cl
from . import events, store

LINKEDIN = "linkedin"

# --------------------------------------------------------- the connection axis
#
# Closed vocabulary. Screens and reports group by these, so they are the
# stable thing and the human sentence travels beside them in `why`.
#
# The four words a cadence step may REQUIRE are `cadencelibrary`'s and are
# imported rather than restated - a sequence asking for `connected` and a
# machine answering `CONNECTED` have to be the same string or the branch
# silently never fires.

OPEN_PROFILE = cl.OPEN_PROFILE
CONNECTED = cl.CONNECTED
CONNECTION_ACCEPTED = cl.CONNECTION_ACCEPTED
CONNECTION_NOT_ACCEPTED = cl.CONNECTION_NOT_ACCEPTED

NO_EVIDENCE = "no_evidence"
NOT_CONNECTED = "not_connected"
REQUEST_PENDING = "connection_request_pending"
UNKNOWN_ACCEPTANCE = "connection_acceptance_unread"
REPLIED = "replied"
UNKNOWN = "unknown"

STATES = (NO_EVIDENCE, OPEN_PROFILE, NOT_CONNECTED, REQUEST_PENDING,
          CONNECTION_ACCEPTED, CONNECTION_NOT_ACCEPTED, CONNECTED,
          UNKNOWN_ACCEPTANCE, REPLIED, UNKNOWN)

# The states in which a direct message may be sent at all. Membership is the
# whole safety property of the LinkedIn lane: messaging somebody we cannot
# prove is reachable is the "stranger messaging out of nowhere" failure
# `providers/heyreach.py` names when it refuses to infer acceptance from an
# inbox row.
MESSAGEABLE = (OPEN_PROFILE, CONNECTION_ACCEPTED, CONNECTED)

STATE_LABEL = {
    NO_EVIDENCE: "nothing recorded on LinkedIn yet",
    OPEN_PROFILE: "an open profile - no connection needed",
    NOT_CONNECTED: "not connected, and no request is outstanding",
    REQUEST_PENDING: "a connection request is outstanding",
    CONNECTION_ACCEPTED: "the connection request was accepted",
    CONNECTION_NOT_ACCEPTED: "the connection request was not accepted",
    CONNECTED: "already connected before we asked",
    UNKNOWN_ACCEPTANCE: "a request went out and nobody has read whether it "
                        "was accepted",
    REPLIED: "this person has replied",
    UNKNOWN: "the provider reported something this system has never seen",
}

# ------------------------------------------------------------------- InMail

INMAIL_ELIGIBLE = "inmail_eligible"
INMAIL_NOT_AVAILABLE = "inmail_not_available"
INMAIL_UNKNOWN = "inmail_unknown"
INMAIL_STATES = (INMAIL_ELIGIBLE, INMAIL_NOT_AVAILABLE, INMAIL_UNKNOWN)

# ---------------------------------------------------- what a step is asking for
#
# `cadencelibrary`'s `linkedin_action` words. `CONNECT` is the only one that
# needs no existing relationship; everything else needs a reachable person or
# a capability nobody has proven.

CONNECT = "connect"
MESSAGE = "message"
INMAIL = "inmail"
OPEN_PROFILE_MESSAGE = "open_profile_message"
ACTIONS = (CONNECT, MESSAGE, INMAIL, OPEN_PROFILE_MESSAGE)

# Actions that put words in front of a person directly.
MESSAGE_ACTIONS = (MESSAGE, OPEN_PROFILE_MESSAGE)

UNKNOWN_ACTION = "unknown_action"

# The word a legacy linear step uses to say it needs an accepted connection.
# `cadence.STEPS` carries `requires: connection_accepted` on day 8 and
# predates `linkedin_action` entirely, so a LinkedIn step with no action and
# that requirement is read as a message and one without it as the request -
# which is exactly what `cadence.status_for` and `eligibility._dependency`
# already mean by `requires`.
LEGACY_ACCEPT_REQUIREMENT = CONNECTION_ACCEPTED

# --------------------------------------------------------- what may be done

GO = "go"
WAIT = "wait"
SKIP = "skip"

# Why, exactly. Stable vocabulary, because a planner groups by it and a
# screen reads it; the human sentence lives beside each answer in `why`.
# Each code is one REMEDY: "wait for them to accept" and "go and read the
# provider" are different problems, and a screen that showed them as one
# would send an operator to wait for a window that was never the question.
HELD_REPLIED = "linkedin:replied"
HELD_PROVIDER_STATE_UNKNOWN = "linkedin:provider_state_unknown"
HELD_ACTION_UNKNOWN = "linkedin:action_unknown"
HELD_CAPABILITY_UNPROVEN = "linkedin:capability_unproven"
HELD_REQUIRES_UNMET = "linkedin:step_requirement_unmet"
HELD_REQUEST_OUTSTANDING = "linkedin:connection_request_outstanding"
HELD_ACCEPTANCE_UNREAD = "linkedin:acceptance_unread"
HELD_NOT_REACHABLE = "linkedin:not_reachable"
HELD_INMAIL_UNAVAILABLE = "linkedin:inmail_unavailable"
SKIP_ALREADY_REACHABLE = "linkedin:already_reachable"

# ------------------------------------------------------------- capabilities
#
# Statements about what THIS BUILD can prove, not about what LinkedIn or
# HeyReach can do. The distinction is `providers/heyreach.py`'s and it is the
# whole of it: "the provider has no webhooks" would justify polling for ever,
# and "we have never called them" does not.

CAPABILITIES = {
    cl.CAP_CONNECT: (True,
                     "CONNECTION_REQUEST is a node type observed in real "
                     "HeyReach sequences read from this repository"),
    cl.CAP_MESSAGE: (True,
                     "MESSAGE is a node type observed in real HeyReach "
                     "sequences read from this repository"),
    cl.CAP_OPEN_PROFILE: (False,
                          "nothing in this build reads whether a profile is "
                          "open, so a step that messages one cannot be "
                          "planned from evidence"),
    cl.CAP_INMAIL: (False,
                    "no InMail node has ever been observed in a sequence read "
                    "from here, and the only InMail field in this repository "
                    "is a cooldown on our own seat"),
}

# Nothing in this build reads whether a profile is open. Named as a constant
# because the OPEN_PROFILE state is reachable only from an explicit
# observation, and its absence must read as "nobody looked" rather than as
# "the profile is closed".
PROVIDER_REPORTS_OPEN_PROFILE = False


def capability(name):
    """Is this capability proven in this build? `(bool, why)`.

    A capability nobody has classified is False. An unrecognised dependency
    is not a satisfied one.
    """
    if not name:
        return True, "this step depends on no named provider capability"
    found = CAPABILITIES.get(name)
    if found is None:
        return False, (f"{name!r} is a provider capability nothing here has "
                       "classified, so nothing may be planned on it")
    return found


# ----------------------------------------------------------- configuration

WAIT_DAYS_KEY = "linkedin.connection_wait_days"
INMAIL_ENABLED_KEY = "linkedin.inmail.enabled"

# Seven days. Stated as a default rather than presented as best practice - it
# is a number somebody chose, and the person choosing it should be the
# client's operator. `settings()` reports which values were configured, for
# the reason `fatigue.limits` gives: a screen showing "7 days" without saying
# whether anybody chose 7 invites an operator to treat a fallback as a
# decision.
DEFAULT_WAIT_DAYS = 7


def _at(config, dotted):
    node = config or {}
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def settings(config=None):
    """The LinkedIn branch settings in force, and where each came from."""
    raw = _at(config, WAIT_DAYS_KEY)
    try:
        days, chosen = int(raw), True
    except (TypeError, ValueError):
        days, chosen = DEFAULT_WAIT_DAYS, False
    inmail = _at(config, INMAIL_ENABLED_KEY)
    return {
        "connection_wait_days": {
            "key": WAIT_DAYS_KEY, "value": days, "configured": chosen,
            "default": DEFAULT_WAIT_DAYS,
            "label": "Days to wait after a connection request before asking "
                     "whether it was accepted"},
        "inmail_enabled": {
            "key": INMAIL_ENABLED_KEY, "value": inmail is True,
            "configured": inmail is not None, "default": False,
            "label": "Whether this workspace permits InMail at all"},
    }


def wait_days(config=None):
    return settings(config)["connection_wait_days"]["value"]


# ------------------------------------------------------- provider translation

# HeyReach's lifecycle words, mapped onto this module's vocabulary. An
# ALLOWLIST, for the polarity argument `heyreach.lead_state` makes: a value
# this system has never seen becomes UNKNOWN and is recorded with the
# provider's own word beside it, never folded into a neighbouring state.
#
# `failed` and `ended_no_action` are deliberately refused rather than mapped
# to "not connected". 27 of 851 observed leads read `(Failed,
# ConnectionAccepted, MessageSent)`, so Failed does not mean nothing reached
# the prospect, and calling it NOT_CONNECTED would re-invite somebody who had
# already accepted.
PROVIDER_LIFECYCLE = {
    "accepted": CONNECTION_ACCEPTED,
    "connectionaccepted": CONNECTION_ACCEPTED,
    "request_sent": REQUEST_PENDING,
    "connectionsent": REQUEST_PENDING,
    "request_pending": NO_EVIDENCE,
    "replied": REPLIED,
    "none": NO_EVIDENCE,
}

PROVIDER_REFUSED = {
    "failed": "the provider reports a failed step, which does not mean the "
              "prospect was not reached - failed leads are observed carrying "
              "an accepted connection and a sent message",
    "ended_no_action": "the sequence finished with no connection request "
                       "recorded, which says what the provider did not do "
                       "and nothing about whether this person is connected",
    "unknown": "the provider used a value this system has never seen",
}


def from_provider_lifecycle(word):
    """A provider lifecycle word as a connection state. `(state, why)`.

    Never raises and never guesses. Anything outside the allowlist is
    `UNKNOWN` carrying the word, so a vocabulary change surfaces as a row a
    person can read rather than as a silently neighbouring state.
    """
    key = str(word if word is not None else "").strip().lower().replace(" ", "")
    if key in PROVIDER_LIFECYCLE:
        return PROVIDER_LIFECYCLE[key], None
    if key in PROVIDER_REFUSED:
        return UNKNOWN, PROVIDER_REFUSED[key]
    return UNKNOWN, (f"the provider reported {word!r}, which this system has "
                     "no state for")


def observation(state=None, lifecycle=None, open_profile=None, inmail=None,
                at=None, source=None):
    """The trimmed shape a caller hands in. Built from a read, never fetched.

    `lifecycle` is a provider word and is translated here; `state` is one of
    this module's own words, for a caller that has already translated.

    An observation that can say nothing is still an observation - it records
    that somebody looked - which is the difference between "not accepted" and
    "nobody read it".
    """
    why = None
    if state is None and lifecycle is not None:
        state, why = from_provider_lifecycle(lifecycle)
    if state is not None and state not in STATES:
        state, why = UNKNOWN, f"{state!r} is not a state this module has"
    return {"state": state, "lifecycle": lifecycle, "why": why,
            "open_profile": open_profile is True,
            "open_profile_known": open_profile is not None,
            "inmail": inmail, "at": at, "source": source or "caller"}


# ----------------------------------------------------------------- the clock

def _plus_days(iso, days):
    """`iso` moved forward by `days`, or None if it will not parse.

    Unparseable in, unparseable out. A window derived from a timestamp
    nobody can read would be a date invented here.
    """
    if not iso or not days:
        return None
    try:
        stamp = datetime.datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None
    return (stamp + datetime.timedelta(days=float(days))).isoformat()


# ------------------------------------------------------------ reading a step

def action_of(node):
    """Which LinkedIn action this step or branch is, or None if it is not one.

    `linkedin_action` is authority - it is the field `cadencelibrary` writes.
    The fallback reads `requires`, for the linear sequence in `cadence.STEPS`
    that predates it.

    An action word this module does not know returns UNKNOWN_ACTION, which
    `plan_step` holds. An unrecognised action is not a message.
    """
    node = node or {}
    declared = node.get("linkedin_action")
    if declared:
        return declared if declared in ACTIONS else UNKNOWN_ACTION
    if node.get("requires") == LEGACY_ACCEPT_REQUIREMENT:
        return MESSAGE
    return CONNECT


def is_linkedin(spec):
    return (spec or {}).get("channel") == LINKEDIN


def branches(spec):
    """This step's alternative first, then the step itself.

    Order is the selection order and it is the operator's branch read
    literally: an open profile skips the connection request, and a refused
    connection takes the InMail path. The alternative is the more specific
    reading of the same step, so it is asked first.
    """
    spec = spec or {}
    out = []
    alternative = spec.get("alternative")
    if isinstance(alternative, dict):
        # An alternative inherits everything it does not restate - the key,
        # the day and the channel are the step's, and only the action, the
        # requirement and the capability differ.
        merged = {k: v for k, v in spec.items() if k != "alternative"}
        merged.update(alternative)
        merged["is_alternative"] = True
        out.append(merged)
    out.append(dict(spec, is_alternative=False))
    return out


def satisfies(requirement, state):
    """Does this connection state satisfy what a step requires? `(bool, why)`.

    `connected` and `connection_accepted` are the same requirement written
    twice - the new sequences say the first, `cadence.STEPS` says the second
    - and both mean "this person can be sent a direct message". So both are
    satisfied by the whole `MESSAGEABLE` set, an open profile included: a
    step that wants to send a DM is satisfied by a person who can receive
    one.

    `connection_not_accepted` is satisfied ONLY by the state the provider
    actually reported. `UNKNOWN_ACCEPTANCE` - a window that closed with
    nobody reading it - does not satisfy it, which is the single rule that
    stops an InMail going to somebody who accepted on day two.
    """
    if not requirement:
        return True, "this step names no prospect state"
    if requirement in (CONNECTED, CONNECTION_ACCEPTED):
        if state in MESSAGEABLE:
            return True, STATE_LABEL.get(state)
        return False, ("this step needs a person who can be sent a direct "
                       "message, and the state here is: "
                       + STATE_LABEL.get(state, str(state)))
    if requirement == OPEN_PROFILE:
        if state == OPEN_PROFILE:
            return True, STATE_LABEL[OPEN_PROFILE]
        return False, ("this step needs an open profile and nothing reports "
                       "one for this person")
    if requirement == CONNECTION_NOT_ACCEPTED:
        if state == CONNECTION_NOT_ACCEPTED:
            return True, STATE_LABEL[CONNECTION_NOT_ACCEPTED]
        if state == UNKNOWN_ACCEPTANCE:
            return False, ("this step needs a refused connection and the "
                           "acceptance has not been read - an unread window "
                           "is not a refusal")
        return False, ("this step needs a refused connection, and the state "
                       "here is: " + STATE_LABEL.get(state, str(state)))
    return False, (f"{requirement!r} is not a prospect state this system "
                   "knows how to establish")


def connection_requests(steps):
    """Every step in a sequence that would send a connection request."""
    return [s for s in steps or ()
            if is_linkedin(s) and any(action_of(b) == CONNECT
                                      for b in branches(s))]


def _action_of_recorded(rec, contact_key, step_key, steps=None):
    """What a LinkedIn step we already performed actually was.

    The live sequence is authority. Where a caller supplies none, the
    record's own stored copy of the step answers the same question about the
    plan that was run - `cadence.expand_step` writes `channel` and `requires`
    onto it. Where neither can say, the answer is UNKNOWN_ACTION and nothing
    downstream reads it as a connection request.
    """
    for spec in steps or ():
        if spec.get("key") == step_key and is_linkedin(spec):
            return action_of(spec)
    stored = ((rec.get("cadence") or {}).get(contact_key) or {}).get(step_key)
    if isinstance(stored, dict) and is_linkedin(stored):
        return action_of(stored)
    return UNKNOWN_ACTION


# -------------------------------------------------------------- the evidence

def evidence(rec, contact_key, steps=None):
    """Every recorded fact about this person's LinkedIn connection.

    Read from the event log directly rather than through `account.touches`,
    which is the right projection for "how often have we reached this person"
    and the wrong one here: it maps `linkedin_connected` to a DELIVERED
    touch, so an ACCEPTANCE and a message we sent are one shape in it.
    `account.py` reads the log directly for `bounces()` and `replies()` for
    the same reason - the projection has to match the question.
    """
    found = {"request_at": None, "accepted_at": None, "replied_at": None,
             "unplaceable_action_at": None, "actions": 0}
    for entry in rec.get("events") or []:
        if entry.get("contact") != contact_key:
            continue
        if events.is_acceptance(entry):
            found["accepted_at"] = found["accepted_at"] or entry.get("at")
            continue
        if events.is_reply(entry):
            # Channel-agnostic on purpose, and the same predicate
            # `eligibility._replied` uses. A reply on either channel ends the
            # cold cadence on both - there is one hold, not one per channel.
            found["replied_at"] = found["replied_at"] or entry.get("at")
            continue
        if (entry.get("type") != events.PUSH_MARKED
                or entry.get("channel") != LINKEDIN):
            continue
        found["actions"] += 1
        performed = _action_of_recorded(rec, contact_key, entry.get("step"),
                                        steps)
        if performed == CONNECT:
            found["request_at"] = found["request_at"] or entry.get("at")
        elif performed == UNKNOWN_ACTION:
            # A confirmed LinkedIn action nobody can name. It is not a
            # connection request, and it is not evidence that there was one;
            # it is recorded so the state can say why it cannot say.
            found["unplaceable_action_at"] = (found["unplaceable_action_at"]
                                              or entry.get("at"))
    return found


# ------------------------------------------------------------ the connection

def connection(rec, contact, observed=None, steps=None, config=None, at=None):
    """Where this person stands on LinkedIn, and what says so.

    Order is most final first, and provider truth outranks our own plan: an
    acceptance we recorded and an acceptance the provider reports are the
    same fact, and the provider is the only thing that can move a lane a
    hand-staged campaign is running.
    """
    at = at or store.now()
    key = (contact or {}).get("key")
    facts = evidence(rec, key, steps)
    observed = observed or {}
    days = wait_days(config)

    def answer(state, why, **extra):
        out = {"state": state, "why": why, "label": STATE_LABEL.get(state),
               "contact_key": key, "at": at, "wait_days": days,
               "request_at": facts["request_at"],
               "accepted_at": facts["accepted_at"],
               "replied_at": facts["replied_at"],
               "wait_until": None, "source": "the record's own event log",
               "observed": observed.get("state"), "evidence": facts}
        out.update(extra)
        return out

    # 1. A reply ends this axis, whichever channel it arrived on.
    if facts["replied_at"]:
        return answer(REPLIED,
                      "this person replied, so nothing cold goes to them on "
                      "either channel")

    # 2. An open profile, which is only ever an explicit observation. Its
    #    absence is not evidence that the profile is closed - it is the
    #    normal case, because nothing here reads it - so it falls through to
    #    the connection question below rather than holding the lane.
    if observed.get("open_profile"):
        return answer(OPEN_PROFILE,
                      "an observation records this as an open profile, so a "
                      "connection request is not needed",
                      source=observed.get("source") or "observation")

    # 2b. A provider-reported removal outranks a stale event-log acceptance.
    #     The same shape as the open profile above: provider truth wins.
    #     NOT_CONNECTED is the correct state (not CONNECTION_NOT_ACCEPTED)
    #     because the latter would fire the InMail fallback, and InMail is
    #     for a refused request, not a removed connection.
    if observed.get("state") == NOT_CONNECTED and facts["accepted_at"]:
        return answer(NOT_CONNECTED,
                      "the provider reports this person is no longer "
                      "connected; a recorded acceptance is stale",
                      source=observed.get("source") or "observation")

    # 3. Acceptance. Ours if we asked, theirs if we did not.
    if facts["accepted_at"] or observed.get("state") == CONNECTION_ACCEPTED:
        when = facts["accepted_at"] or observed.get("at")
        if facts["request_at"]:
            return answer(CONNECTION_ACCEPTED,
                          "the connection request we sent was accepted",
                          accepted_at=when)
        return answer(CONNECTED,
                      "this person is connected and we have no record of "
                      "sending the request, so the connection was already "
                      "there",
                      accepted_at=when)

    # 4. A provider word we have no state for. Recorded, never resolved.
    if observed.get("state") == UNKNOWN:
        return answer(UNKNOWN,
                      observed.get("why") or "the provider reported a state "
                      "this system has never seen",
                      source=observed.get("source") or "observation")

    # 5. A request is outstanding - ours, or one the provider reports.
    request_at = facts["request_at"]
    if observed.get("state") == REQUEST_PENDING:
        request_at = request_at or observed.get("at")
    if request_at:
        until = _plus_days(request_at, days)
        if until is None or str(at) < str(until):
            return answer(REQUEST_PENDING,
                          f"the request went out on {request_at} and the "
                          f"{days}-day window has not closed",
                          wait_until=until, request_at=request_at)
        # THE WINDOW OPENS THE QUESTION. IT DOES NOT ANSWER IT.
        #
        # An expired window plus no reading is not a refusal. Somebody may
        # have accepted on day two and nobody looked, and acting on elapsed
        # time here is the fabrication this module exists to refuse.
        if not observed.get("state"):
            return answer(UNKNOWN_ACCEPTANCE,
                          f"the {days}-day window closed on {until} and "
                          "nobody has read whether the request was accepted. "
                          "Read the provider before treating this as a "
                          "refusal",
                          wait_until=until, request_at=request_at)
        return answer(CONNECTION_NOT_ACCEPTED,
                      f"the provider still reports no acceptance and the "
                      f"{days}-day window closed on {until}",
                      wait_until=until, request_at=request_at,
                      source=observed.get("source") or "observation")

    # 6. A confirmed LinkedIn action whose step nobody can name. It is not a
    #    request, and treating it as one would start a window nothing began.
    if facts["unplaceable_action_at"]:
        return answer(UNKNOWN_ACCEPTANCE,
                      "a LinkedIn action is recorded against this person on "
                      f"{facts['unplaceable_action_at']} and the step it "
                      "belonged to was not recorded, so it cannot be said "
                      "whether a connection request has gone out")

    # 7. An observation that positively reports nothing outstanding.
    if observed.get("state") == NO_EVIDENCE:
        return answer(NOT_CONNECTED,
                      "the provider reports nothing sent and no connection",
                      source=observed.get("source") or "observation")

    # 8. Nothing at all. Not the same as "not connected": it is the opening
    #    position, and the only action it permits is the request itself.
    return answer(NO_EVIDENCE,
                  "nothing has been recorded or observed about this person "
                  "on LinkedIn")


# ------------------------------------------------------------------- InMail

def evaluate_inmail(state, observed=None, config=None):
    """May an InMail be sent to this person? `(verdict, why)`.

    Three independent conditions, which is why this cannot collapse into a
    boolean on the contact:

      the branch has reached the point of asking - a request went out and
        the provider says it was not accepted
      the workspace permits InMail at all
      something can say this person is InMail-reachable

    `plan_step` adds the fourth, which is whether this build can send one at
    all, and refuses on it even when all three of these hold. An eligibility
    nothing can act on is not a permission.
    """
    observed = observed or {}
    if state != CONNECTION_NOT_ACCEPTED:
        return INMAIL_NOT_AVAILABLE, (
            "an InMail is only evaluated after a connection request the "
            f"provider says was not accepted; this person is "
            f"{STATE_LABEL.get(state, state)}")
    if not settings(config)["inmail_enabled"]["value"]:
        return INMAIL_NOT_AVAILABLE, (
            f"this workspace has not enabled InMail ({INMAIL_ENABLED_KEY})")
    reported = observed.get("inmail")
    if reported is None:
        return INMAIL_UNKNOWN, (
            "nothing reports whether this person can receive an InMail, and "
            "an unread eligibility is not an eligibility")
    if reported is not True:
        return INMAIL_NOT_AVAILABLE, (
            "the observation reports this person cannot receive an InMail")
    return INMAIL_ELIGIBLE, "the observation reports an InMail is available"


# --------------------------------------------------------------- the branch

def plan_step(rec, contact, spec, observed=None, steps=None, config=None,
              at=None):
    """May this one LinkedIn step go now? `go` / `wait` / `skip`, and why.

    This is the LinkedIn branch and nothing else. It answers about the
    connection axis and it is never a permission to send: the person gate
    (`eligibility.must_not_contact`), the account gate, fatigue, lint and
    approval all run around it and any of them may refuse.

    `skip` is for a step that is not wrong but pointless - a connection
    request to somebody already reachable - and a caller advances past it to
    the next step rather than holding the lane behind it. Everything else
    that cannot go is a `wait`, because a LinkedIn step that is quietly
    dropped is a cadence that reports a touch it never made.
    """
    found = connection(rec, contact, observed=observed, steps=steps,
                       config=config, at=at)
    state = found["state"]
    chosen = None
    considered = []

    def answer(status, action, why, code=None, **extra):
        out = {"status": status, "action": action, "why": why, "code": code,
               "state": state, "connection": found, "inmail": None,
               "node": chosen, "considered": considered,
               "execute_after": found.get("wait_until")}
        out.update(extra)
        return out

    if not is_linkedin(spec):
        return answer(GO, None, "this step is not a LinkedIn step")

    # 1. Which branch of this step applies. The alternative is asked first
    #    because it is the more specific reading; where its requirement is
    #    satisfied it IS the step, and a capability it cannot use holds the
    #    step rather than falling back to the primary. A cadence that
    #    quietly ran the primary instead of the InMail it had decided on
    #    would send a different message from the one it reports.
    branch_list = branches(spec)
    for node in branch_list:
        ok, why = satisfies(node.get("requires"), state)
        considered.append({"is_alternative": node.get("is_alternative"),
                           "action": action_of(node),
                           "requires": node.get("requires"),
                           "satisfied": ok, "why": why})
        if ok and chosen is None:
            chosen = node
    # Nothing applies: the step is held as authored, and the PRIMARY's
    # refusal is the one reported - the alternative not applying is normal.
    satisfied = chosen is not None
    chosen = chosen if satisfied else branch_list[-1]
    action = action_of(chosen)

    # 2. A reply ends the axis whatever the step says.
    if state == REPLIED:
        return answer(WAIT, action, found["why"], HELD_REPLIED,
                      execute_after=None)
    if state == UNKNOWN:
        return answer(WAIT, action, found["why"],
                      HELD_PROVIDER_STATE_UNKNOWN, execute_after=None)

    # 3. An action this module has no branch for is held, never run.
    if action == UNKNOWN_ACTION:
        return answer(WAIT, action,
                      f"step {spec.get('key')!r} names the LinkedIn action "
                      f"{chosen.get('linkedin_action')!r}, which this system "
                      "has no branch for", HELD_ACTION_UNKNOWN,
                      execute_after=None)

    # 4. The provider capability this branch depends on. Unproven is a hold
    #    with the reason named - never a silent skip, and never an execution
    #    as if it worked.
    supported, why = capability(chosen.get("capability"))
    if not supported:
        return answer(WAIT, action, why, HELD_CAPABILITY_UNPROVEN,
                      execute_after=None)

    # 5. What the step itself requires of the prospect. Asked after the
    #    capability so an unproven capability is reported as one rather than
    #    as a prospect who is in the wrong state for it.
    if not satisfied:
        return answer(WAIT, action, considered[-1]["why"],
                      HELD_ACCEPTANCE_UNREAD
                      if state == UNKNOWN_ACCEPTANCE else HELD_REQUIRES_UNMET)

    # 6. The connection request itself.
    if action == CONNECT:
        if state in MESSAGEABLE:
            return answer(SKIP, action,
                          f"{found['why']}, so the connection request is "
                          "skipped and the messages are what is left",
                          SKIP_ALREADY_REACHABLE)
        if state == REQUEST_PENDING:
            return answer(WAIT, action,
                          "a connection request is already outstanding; a "
                          "second invitation to one person is not a retry",
                          HELD_REQUEST_OUTSTANDING)
        if state in (CONNECTION_NOT_ACCEPTED, UNKNOWN_ACCEPTANCE):
            return answer(WAIT, action,
                          "a connection request has already gone out to this "
                          f"person: {found['why']}",
                          HELD_ACCEPTANCE_UNREAD
                          if state == UNKNOWN_ACCEPTANCE
                          else HELD_NOT_REACHABLE, execute_after=None)
        # NO_EVIDENCE and NOT_CONNECTED. The request is the one LinkedIn
        # action that is safe with no connection evidence: it is what the
        # sequence does to a cold prospect and it asserts nothing about a
        # relationship.
        return answer(GO, action,
                      "nothing is outstanding and this person is not known to "
                      "be reachable, so the connection request opens the lane",
                      execute_after=None)

    # 7. A direct message.
    if action in MESSAGE_ACTIONS:
        if state in MESSAGEABLE:
            return answer(GO, action, found["why"], execute_after=None)
        if state == REQUEST_PENDING:
            return answer(WAIT, action,
                          "the connection request has not been accepted yet, "
                          "and a message before it lands is a stranger "
                          "messaging out of nowhere", HELD_REQUEST_OUTSTANDING)
        return answer(WAIT, action,
                      "this person cannot be sent a direct message: "
                      + found["why"],
                      HELD_ACCEPTANCE_UNREAD if state == UNKNOWN_ACCEPTANCE
                      else HELD_NOT_REACHABLE, execute_after=None)

    # 8. An InMail. The branch reached it, the workspace may permit it, and
    #    this build still cannot send one.
    verdict, why = evaluate_inmail(state, observed, config)
    return answer(WAIT, action,
                  ("an InMail is reported available and nothing here has a "
                   "validated way to send one, so it is held rather than "
                   "skipped" if verdict == INMAIL_ELIGIBLE else why),
                  HELD_INMAIL_UNAVAILABLE, inmail=verdict,
                  execute_after=None)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.linkedinstate",
                                description=__doc__)
    p.add_argument("--client")
    p.add_argument("--id", action="append", dest="ids")
    a = p.parse_args(argv)

    from . import clients

    config = clients.load(a.client) if a.client else {}
    rows = []
    for rec in store.load():
        if a.client and rec.get("client") != a.client:
            continue
        if a.ids and rec.get("id") not in a.ids:
            continue
        for contact in rec.get("contacts") or []:
            found = connection(rec, contact, config=config)
            rows.append({"record": rec.get("id"),
                         "contact": contact.get("key"),
                         "state": found["state"], "why": found["why"]})
    print(json.dumps({"settings": settings(config),
                      "capabilities": {k: v[0] for k, v in
                                       CAPABILITIES.items()},
                      "contacts": rows}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
