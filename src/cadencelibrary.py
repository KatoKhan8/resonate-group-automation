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

SEQUENCES = {
    "productive_li_heavy_v1": PRODUCTIVE_LI_HEAVY_V1,
    "productive_balanced_v1": PRODUCTIVE_BALANCED_V1,
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
