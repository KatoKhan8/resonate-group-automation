#!/usr/bin/env python3
"""The named sequences a client may choose between.

WHY THIS IS A LIBRARY AND NOT A CLIENT FILE. `cadence.steps_for` already
resolves a sequence from the campaign, then the client's named cadence, then
the constant - so selecting a strategy is already configuration. What the
client file cannot hold is the sequence ITSELF: `clients.parse` reads scalars
and inline scalar lists, and a step is a mapping. An inline list of mappings
comes back split on its commas.

So the sequences live here, once, and a client file picks one by name:

    cadence: productive_li_heavy_v1

Comparing two intensities is then a one-line edit to that file, which is the
property that matters - the alternative is a sequence pasted into several
modules, which is what "do not hard-code the cadence" is about.

WHAT A LINKEDIN STEP MAY SAY. `requires` already existed and gated a step on
`connection_accepted`. The LinkedIn-heavy cadence needs more than one branch,
so a step may also carry:

    linkedin_action   connect | message | inmail | open_profile_message
    requires          the prospect state this step needs, or absent
    capability        a PROVIDER capability this step depends on

THE MESSAGES ARE GENERATED, NOT TEMPLATED. Only two LinkedIn templates exist
- `linkedin_intro`, the connection note, and `linkedin_followup` - and four
messages that each have a different job cannot come from one of them. A first
version named five templates nothing defines, which renders as a KeyError the
moment a timeline is built: a cadence that looks configured and crashes.

`capability` is the load-bearing one. Whether HeyReach can detect an Open
Profile, or send an InMail, or report that a connection request was declined,
is not yet established - it is being measured. A step naming a capability the
provider has not been proven to support must be HELD by the state machine,
never silently skipped and never executed as if it worked. A cadence that
quietly drops its InMail fallback reports eleven touches and sends ten.
"""

# ---------------------------------------------------------------- states

OPEN_PROFILE = "open_profile"
CONNECTED = "connected"
CONNECTION_ACCEPTED = "connection_accepted"
CONNECTION_NOT_ACCEPTED = "connection_not_accepted"

# ---------------------------------------------------------- capabilities
#
# Named so a step can say what it depends on and the planner can refuse
# rather than guess. None of these is proven on HeyReach yet.

CAP_OPEN_PROFILE = "linkedin.open_profile_message"
CAP_INMAIL = "linkedin.inmail"
CAP_CONNECT = "linkedin.connection_request"
CAP_MESSAGE = "linkedin.message"

# --------------------------------------------------------- email ladders
#
# Each sequence names which ladder its email steps resolve against. The
# ladder is looked up by name in LADDER_REGISTRY; `generate._resolve_ladder`
# reads the `_ladder` attribute off the sequence tuple.
#
# THE FIVE-STEP LADDER IS UNCHANGED. It is the production ladder for
# `productive_li_heavy_v1` and must not change: EmailBison campaign 481 is
# staged with nine real leads carrying approved subject_5/body_5, and
# changing rung 5 would silently rewrite the final email of a live sequence.
EMAIL_FIVE_LADDER = (
    "Relevance. Why you are writing to THIS person at THIS company, in their "
    "own operational language. One question they can answer in a line.",
    "A different angle from the first email. Not the same argument rephrased: "
    "a different part of how the business runs, and a different question.",
    "New value. One concrete use case or consequence a team their size would "
    "recognise, and what changes when it is visible rather than reconstructed.",
    "A short bump that makes a DIFFERENT argument from every email before it. "
    "The shortest message in the sequence - and still a whole one: the "
    "forty-word floor applies here exactly as it does everywhere else. "
    "One idea, one question, no recap.",
    "Close the loop. Give them an easy no, make no new pitch, ask for nothing "
    "beyond permission to stop.",
)

# The eight-step ladder, read off the client's best-performing sequence
# (12.23% reply rate at 8 steps, n=17,690). Rungs 1-4 match the five-step
# ladder; rungs 5-7 are new; rung 8 is the breakup moved from rung 5.
EMAIL_EIGHT_LADDER = (
    "Relevance. Why you are writing to THIS person at THIS company, in their "
    "own operational language. One question they can answer in a line.",
    "A different angle from the first email. Not the same argument rephrased: "
    "a different part of how the business runs, and a different question.",
    "New value. One concrete use case or consequence a team their size would "
    "recognise, and what changes when it is visible rather than reconstructed.",
    "A short bump that makes a DIFFERENT argument from every email before it. "
    "The shortest message in the sequence - and still a whole one: the "
    "forty-word floor applies here exactly as it does everywhere else. "
    "One idea, one question, no recap.",
    "The cost of the current way of doing it. What the existing approach "
    "actually spends in time, risk or reconstruction - not a feature pitch, "
    "a number they can recognise.",
    "What a team their size found when they looked. The pattern, not the "
    "product: what changed when visibility arrived during the work rather "
    "than after it.",
    "The referral ask. Am I talking to the right person about this, and who "
    "should I be talking to. This is the rung that feeds stakeholder "
    "escalation in ACCOUNT-OUTREACH.md.",
    "Close the loop. Give them an easy no, make no new pitch, ask for nothing "
    "beyond permission to stop.",
)

LINKEDIN_DEFAULT_LADDER = (
    "A connection request note. One line on why you are writing to them "
    "specifically, in the operational language of their angle. No ask beyond "
    "connecting, and no question that needs a considered answer.",
    "A short first message. One operational angle, put as a question about "
    "how they handle it today. Different words and a different angle from "
    "the connection note.",
    "A second, different operational angle. Name the consequence of not "
    "having it rather than the feature that provides it.",
    "The use case. What a team their size actually changed, and what it was "
    "costing them before. This is the rung where evidence belongs, if there "
    "is any; if there is none, describe the pattern as ours rather than "
    "theirs.",
    "A concise final follow-up. One line, one question, no new argument and "
    "no summary of the previous ones.",
    "Close the loop. An easy no, and leave it there.",
)

LADDER_REGISTRY = {
    "email_five": EMAIL_FIVE_LADDER,
    "email_eight": EMAIL_EIGHT_LADDER,
    "linkedin_default": LINKEDIN_DEFAULT_LADDER,
}


# The operator's initial production hypothesis, 2026-09-13: roughly five email
# touches and six LinkedIn activities - four of them messages - across three
# weeks. It is a hypothesis to measure, not a rule: `productive_balanced_v1`
# below exists to be compared against it.
#
# Day 1 carries two steps on purpose. Equal days are allowed; only a step
# EARLIER than its predecessor is refused.
PRODUCTIVE_LI_HEAVY_V1 = (
    # Day 1 - both channels open together.
    {"key": "li1", "day": 1, "channel": "linkedin",
     "linkedin_action": "connect", "capability": CAP_CONNECT,
     "template": "linkedin_intro",
     # The Open Profile branch: where the provider says a direct message needs
     # no connection, the first action should not be spent asking for one.
     "alternative": {"requires": OPEN_PROFILE,
                     "linkedin_action": "open_profile_message",
                     "capability": CAP_OPEN_PROFILE,
                     "generated": True}},
    {"key": "em1", "day": 1, "channel": "email", "generated": True},

    {"key": "li2", "day": 3, "channel": "linkedin",
     "linkedin_action": "message", "capability": CAP_MESSAGE,
     "requires": CONNECTED, "generated": True},
    {"key": "em2", "day": 4, "channel": "email", "generated": True},

    # The fork. Connected, this is the second message; unaccepted after the
    # wait window, it is the InMail fallback - and an InMail is NOT sent
    # merely because the request has not been accepted yet.
    {"key": "li3", "day": 6, "channel": "linkedin",
     "linkedin_action": "message", "capability": CAP_MESSAGE,
     "requires": CONNECTED, "generated": True,
     "alternative": {"requires": CONNECTION_NOT_ACCEPTED,
                     "linkedin_action": "inmail", "capability": CAP_INMAIL,
                     "generated": True}},
    {"key": "em3", "day": 8, "channel": "email", "generated": True},

    {"key": "li4", "day": 10, "channel": "linkedin",
     "linkedin_action": "message", "capability": CAP_MESSAGE,
     "requires": CONNECTED, "generated": True},
    {"key": "em4", "day": 12, "channel": "email", "generated": True},

    {"key": "li5", "day": 15, "channel": "linkedin",
     "linkedin_action": "message", "capability": CAP_MESSAGE,
     "requires": CONNECTED, "generated": True},
    {"key": "li6", "day": 18, "channel": "linkedin",
     "linkedin_action": "message", "capability": CAP_MESSAGE,
     "requires": CONNECTED, "generated": True},
    {"key": "em5", "day": 21, "channel": "email", "generated": True},
)

# The shape that ran before: seven steps, email-led. Kept as a named
# alternative so cadence INTENSITY is a comparable variable rather than a
# rewrite - §14 of the operator's brief asks for exactly this pair.
PRODUCTIVE_BALANCED_V1 = (
    {"key": "day1", "day": 1, "channel": "email", "generated": True},
    {"key": "day3", "day": 3, "channel": "linkedin",
     "linkedin_action": "connect", "capability": CAP_CONNECT,
     "template": "linkedin_intro"},
    {"key": "day5", "day": 5, "channel": "email", "template": "persona_pain"},
    {"key": "day8", "day": 8, "channel": "linkedin",
     "linkedin_action": "message", "capability": CAP_MESSAGE,
     "template": "linkedin_followup", "requires": CONNECTION_ACCEPTED},
    {"key": "day10", "day": 10, "channel": "email",
     "template": "comparable_proof",
     "variant_if_accepted": "comparable_proof_short"},
    {"key": "day15", "day": 15, "channel": "email", "generated": True},
    {"key": "day21", "day": 21, "channel": "email", "template": "breakup"},
)

# The eight-step email cadence. TASK-028.
#
# Read off the client's best-performing sequence: 12.23% reply rate at 8
# steps (n=17,690). The waits mirror the best performer's 2/3/2/3/3/3/3/1
# pattern: days 1, 3, 6, 8, 11, 14, 17, 20.
#
# This is email-led with NO LinkedIn steps. The existing li_heavy cadence
# carries six LinkedIn activities; this one carries zero. The comparison
# is sequence LENGTH on the email channel, not total touch count. An
# eight-email cadence alongside six LinkedIn steps would be fourteen
# touches, and the fatigue caps are paced for eleven.
#
# The ladder is `email_eight`, which has eight rungs. Rung 5 is NOT the
# breakup (that is rung 8); the five-step cadence's ladder is unaffected.
PRODUCTIVE_EMAIL_EIGHT_V1 = (
    {"key": "em1", "day": 1, "channel": "email", "generated": True},
    {"key": "em2", "day": 3, "channel": "email", "generated": True},
    {"key": "em3", "day": 6, "channel": "email", "generated": True},
    {"key": "em4", "day": 8, "channel": "email", "generated": True},
    {"key": "em5", "day": 11, "channel": "email", "generated": True},
    {"key": "em6", "day": 14, "channel": "email", "generated": True},
    {"key": "em7", "day": 17, "channel": "email", "generated": True},
    {"key": "em8", "day": 20, "channel": "email", "generated": True},
)

# --------------------------------------------------------- ladder tagging
#
# Each sequence carries the name of the ladder its email steps resolve
# against. `generate._resolve_ladder` calls `ladder_name_for` to look up
# the ladder; sequences absent from this mapping fall through to the
# default ladder in generate.LADDERS.
#
# PRODUCTIVE_LI_HEAVY_V1 uses `email_five` - the same five-rung ladder that
# has been production since the beginning. This is NOT a change: the ladder
# content is identical to generate.EMAIL_LADDER. The tagging just makes it
# explicit so the eight-step cadence can use a different one.
#
# Keyed by cadence NAME, not id(). `cadence.steps_for` runs every sequence
# through `validate_steps`, which returns a new tuple of new dicts - so
# id() never matches through the path production actually uses. The name
# is the canonical identity: `SEQUENCES` is already a name-to-sequence
# mapping and `named()` reads it.
_SEQUENCE_LADDERS = {
    "productive_li_heavy_v1": {"email": "email_five"},
    "productive_balanced_v1": {"email": "email_five"},
    "productive_email_eight_v1": {"email": "email_eight"},
}


def ladder_name_for(sequence, channel):
    """The ladder name this sequence uses for this channel, or None.

    None means 'use the default ladder in generate.LADDERS'. A sequence
    not in the mapping, or a channel it does not name, returns None.

    Matches by step keys - the one thing that survives `validate_steps`.
    `cadence.steps_for` returns a new tuple of new dicts, so id() and
    content equality both fail. Keys are preserved through validation
    and are the identity a step key is: unique within a sequence.
    """
    if sequence is None:
        return None
    keys = tuple(s.get("key") for s in sequence)
    for name, seq in SEQUENCES.items():
        if tuple(s.get("key") for s in seq) == keys:
            mapping = _SEQUENCE_LADDERS.get(name)
            if mapping:
                return mapping.get(channel)
    return None

SEQUENCES = {
    "productive_li_heavy_v1": PRODUCTIVE_LI_HEAVY_V1,
    "productive_balanced_v1": PRODUCTIVE_BALANCED_V1,
    "productive_email_eight_v1": PRODUCTIVE_EMAIL_EIGHT_V1,
}


def named(name):
    """The sequence with this name, or None. Never a near match."""
    return SEQUENCES.get(str(name or ""))


def capabilities_used(steps):
    """Every provider capability this sequence depends on.

    What a planner asks a provider adapter about before it plans anything: a
    sequence whose InMail fallback is unsupported is a different sequence,
    and it should be reported as such rather than discovered a fortnight in.
    """
    found = set()
    for step in steps or ():
        for node in (step, step.get("alternative") or {}):
            if node.get("capability"):
                found.add(node["capability"])
    return sorted(found)


def shape(steps):
    """How many touches, by channel. For reporting a cadence honestly."""
    email = sum(1 for s in steps or () if s.get("channel") == "email")
    linkedin = [s for s in steps or () if s.get("channel") == "linkedin"]
    messages = sum(1 for s in linkedin
                   if s.get("linkedin_action") in ("message",
                                                   "open_profile_message"))
    return {"email": email, "linkedin": len(linkedin),
            "linkedin_messages": messages,
            "total": email + len(linkedin),
            "days": max([int(s.get("day") or 0) for s in steps or ()] or [0])}
