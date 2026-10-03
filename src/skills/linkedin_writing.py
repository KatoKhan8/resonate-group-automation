"""Stage F: LinkedIn message writing.

Write four LinkedIn messages that mirror the email cadence but do a
different job: start a conversation and ask short questions. Full sentences,
proper capitalisation, the same voice as the emails. The connection request
is under 280 characters with no company name and no pitch. Every message
after the connect opens with {firstName}.

The prompt lives in ``copystages.WRITER_SYSTEM`` (LinkedIn section). This
skill wraps it and declares stage_f as its consumer.
"""
import re

from .. import copystages
from . import Skill


class _Unknown(object):
    """THE CORPUS CANNOT ANSWER THIS BOUND.

    Not zero, not "no limit", not a number anybody may substitute. A guessed
    number is worse than a missing one, so this object refuses to behave like
    one: it has no truth value and no ordering against an integer, which means
    a reader that treats it as a bound raises rather than silently passing
    every length or refusing every length. The only legal test is `is UNKNOWN`.
    """

    __slots__ = ()

    def __repr__(self):
        return "UNKNOWN"

    def __bool__(self):
        raise TypeError(
            "UNKNOWN has no truth value: this bound was never measured. "
            "Test it with `is UNKNOWN` and decide what to do about a bound "
            "that does not exist.")

    __nonzero__ = __bool__

    def __int__(self):
        raise TypeError("UNKNOWN is not a number and must not become one")

    __index__ = __int__


#: The single instance. `is UNKNOWN` is the test; there is never a second one.
UNKNOWN = _Unknown()

#: THE LINKEDIN CHARACTER CONTRACT, AS DATA, BECAUSE A CONTRACT NOTHING CAN
#: READ IS NOT A CONTRACT. (floor, target, ceiling) in CHARACTERS, per role of
#: the LinkedIn sequence, and SINCE 2026-10-03 THE ONLY AUTHORITY FOR THE
#: LENGTH OF A LINKEDIN NOTE OR MESSAGE - operator ruling, that night, in those
#: terms, and the same shape as `cold_email_writing.WORD_CONTRACT`.
#:
#: Characters, not words, because characters are the unit LinkedIn itself
#: limits and the unit every measurement behind these numbers is in.
#:
#: MEASURED. Every number is derived in `docs/second-brain/linkedin.md`
#: section 14 over 54,647 outbound messages and 17,732 conversation-to-campaign
#: pairs on HeyReach organisation unit 118832, window 2026-04-01 to 2026-10-04,
#: classified by `replies.classify_rules` version "rules-4", no model.
#:
#:   li1   the connection request note.
#:         floor    UNKNOWN. The best-accepting note in the estate is 19
#:                  characters and it accepted 1,091 of 7,988 = 13.66%,
#:                  +3.13pp over the no-note baseline of 10.52% on n = 92,220.
#:                  ONE campaign is not a measurement of a floor, so no floor
#:                  is asserted; what IS established is that the 40 this gate
#:                  used to carry would have refused that note, which is why
#:                  40 is gone rather than replaced by 19.
#:         target   UNKNOWN. The three note bands rest on 1, 6 and 1 campaigns.
#:         ceiling  300, LinkedIn's own cap, and it has never bound: 0 of 47
#:                  note variants exceed it and the longest ever sent is 234.
#:                  `LI1_MEASURED_CEILING` below is the soft one.
#:   li2   the first message after acceptance.  100 to 299, aiming for 125.
#:   li3+  every follow-up.                     100 to 299, aiming for 173.
#:
#:         The 299 ceiling: strict positives per 100 touches, 100-299 against
#:         300-499, is 0.491 vs 0.285 at li2 (n = 6,923 / 8,776) and 0.291 vs
#:         0.217 across follow-ups (n = 14,774 / 14,719). The 100 floor: the
#:         60-99 band is 0.136 per 100 on n = 4,425, the worst bucket in the
#:         corpus. The targets are the median length of the messages inside
#:         the winning band that drew a strict positive (n = 34 and n = 43).
#:
#: WHAT THIS REPLACED, AND WHY, measured not asserted:
#:   NOTE_MIN_CHARS    40    REFUTED - see li1's floor above.
#:   MESSAGE_MAX_CHARS 1900  HAS NEVER BOUND. The longest outbound message in
#:                           54,647 is 1,097 characters and p99 is 801, while
#:                           the ceiling that actually separates outcomes is
#:                           299 - 6.4x lower. A cap at 1,900 is a buffer
#:                           check, not a copy contract.
#:   MESSAGE_MIN_CHARS 60    BELOW THE MEASURED FLOOR. The 60-99 band it
#:                           permitted is the worst bucket measured, and
#:                           1,608 of 54,647 outbound messages sat under 60.
#:   no target anywhere      THE GAP. `WORD_CONTRACT` gives the email writer a
#:                           number to aim at; the LinkedIn writer was given a
#:                           range 31x wider than the measured one and nothing
#:                           inside it to aim at.
#:
#: These numbers are declared HERE and nowhere else. `src.lint` imports this
#: mapping rather than carrying a second copy, `copystages`' prose is asserted
#: against it by `tests.test_the_linkedin_char_contract_is_measured`, and the
#: `validation` and `output_schema` below are rendered from it.
#:
#: THE CONTRACT IS A PRIOR, NOT A RESULT. Every row behind it is a pooled
#: across-campaign cut; no A/B exists in this estate. Section 14.4 lists the
#: five things that could not be measured, li2 below 100 characters among them.
LINKEDIN_CHAR_CONTRACT = {
    "li1": (UNKNOWN, UNKNOWN, 300),
    "li2": (100, 125, 299),
    "li3+": (100, 173, 299),
}

#: The connection note's SOFT ceiling, measured, and deliberately NOT in the
#: mapping above because it is not a refusal. The one campaign whose mean note
#: is at or above 180 (10 variants, mean 212, max 234) accepted 8.31% against
#: the no-note baseline of 10.52% - the only note band measured BELOW
#: baseline, -2.21pp, on 6,002 requests against 92,220. One campaign is not a
#: gate, so this is recorded as the number the writer should stay under while
#: the gate keeps LinkedIn's own 300 as the only hard cap on a note.
LI1_MEASURED_CEILING = 179

#: The roles that are MESSAGES rather than the connection request.
MESSAGE_ROLES = ("li2", "li3+")

_LI_KEY_RE = re.compile(r"^li(\d+)$")


def contract_role(step_key):
    """Which row of the contract a cadence step key belongs to, or None.

    `li1` is the connection request, `li2` is the first message after
    acceptance, and `li3`, `li4`, `li5` and anything beyond are `li3+`. None
    means "this contract says nothing about that key", NOT "anything goes":
    the caller keeps whatever other bounds it has.
    """
    key = str(step_key or "").strip().lower()
    if key in LINKEDIN_CHAR_CONTRACT:
        return key
    found = _LI_KEY_RE.match(key)
    if not found:
        return None
    number = int(found.group(1))
    if number < 1:
        return None
    return "li1" if number == 1 else "li2" if number == 2 else "li3+"


def char_bounds(role):
    """(floor, ceiling) for one contract role, or None if it names no role.

    Either bound may be `UNKNOWN`, which is not permission: it is the absence
    of a measurement, and a caller that cannot handle one must say so rather
    than substitute a number.
    """
    spec = LINKEDIN_CHAR_CONTRACT.get(contract_role(role))
    return (spec[0], spec[2]) if spec else None


def char_target(role):
    """The length this role aims for, or `UNKNOWN`, or None for no such role.

    The floor is not the target.
    """
    spec = LINKEDIN_CHAR_CONTRACT.get(contract_role(role))
    return spec[1] if spec else None


def strictest_message_bounds():
    """(floor, ceiling) common to EVERY message role - the strictest of them.

    For a step that is known to be a message but whose cadence key could not
    be recovered. Highest floor and lowest ceiling across `MESSAGE_ROLES`, so
    an unidentified message is never given a looser gate than the row it
    actually belongs to, and an UNKNOWN bound on any message role propagates
    rather than being quietly dropped.
    """
    floors = [LINKEDIN_CHAR_CONTRACT[r][0] for r in MESSAGE_ROLES]
    ceilings = [LINKEDIN_CHAR_CONTRACT[r][2] for r in MESSAGE_ROLES]
    floor = UNKNOWN if any(f is UNKNOWN for f in floors) else max(floors)
    ceiling = UNKNOWN if any(c is UNKNOWN for c in ceilings) else min(ceilings)
    return (floor, ceiling)


def bound_phrase(value):
    """A bound as text. UNKNOWN renders as the word, never as a number."""
    return "UNKNOWN" if value is UNKNOWN else str(value)


def chars_rule():
    """The whole contract as one sentence, rendered from the mapping itself."""
    return ("LinkedIn copy is inside its own role's character range: "
            + ", ".join(
                "%s %s-%s aiming for %s"
                % (role, bound_phrase(lo), bound_phrase(hi),
                   bound_phrase(target))
                for role, (lo, target, hi) in LINKEDIN_CHAR_CONTRACT.items()))


SKILL = Skill(
    name="linkedin_writing",
    purpose="Write four LinkedIn messages that mirror the email cadence but "
            "do a different job: start a conversation and ask short "
            "questions. Full sentences, proper capitalisation, the same "
            "voice as the emails. No company name in the connect, no pitch, "
            "no dashes.",
    inputs=("lead", "company", "facts", "plan", "capability_sentence",
            "has_linkedin"),
    secondbrain_sections=("profile", "customers", "messaging"),
    approved_tools=("claude-sonnet",),
    procedure=copystages.WRITER_SYSTEM,
    examples_good=(
        {
            "output": {
                "connect": "noticed you're building out the Brooklyn design "
                           "team - we're working with agencies on capacity "
                           "visibility",
                "msg1": "Hi {firstName}, I'm [name] with Productive. We help "
                        "agencies see project margin while the work is "
                        "running. Curious whether capacity planning is "
                        "something you track in real time at all?",
                "msg2": "One thing Productive does is show utilisation and "
                        "margin mid-project instead of at month-end. I also "
                        "sent you a note by email about this, so the two "
                        "channels line up. Open to a quick look?",
                "msg3": "No pressure either way. If it's useful down the "
                        "line, happy to reconnect.",
            },
        },
    ),
    examples_bad=(
        {
            "output": {"connect": "Hi, I noticed Brightwave is a leading "
                                  "design agency in Brooklyn. Productive helps "
                                  "agencies like yours with profitability."},
            "why": "the connect names the company and pitches; both are "
                   "banned. It must be under 280 chars, lowercase, one fact, "
                   "no pitch",
        },
        {
            "output": {"msg1": "Hi {firstName}, Just checking in to see if "
                               "you had a chance to review my last note."},
            "why": "'just checking in' is banned; msg1 must say who is "
                   "writing, what Productive does, and why them specifically",
        },
        {
            "output": {"msg1": "hi {firstname}, saw your post about "
                               "scaling."},
            "why": "LinkedIn messages use full sentences and proper "
                   "capitalisation; the connect is the only field that stays "
                   "lowercase",
        },
    ),
    validation=(
        "connect is under 280 characters",
        "connect contains no company name",
        "connect contains no pitch",
        "connect is lowercase register",
        "msg1 opens with 'Hi {firstName},'",
        "msg1 states who is writing and ONE line on what Productive does",
        "msg1 asks ONE question, different from the question email 1 asked",
        "msg2 names the capability in one line and cross-references the email",
        "msg3 is short and leaves the door open",
        "no dash in any message",
        # RENDERED FROM `LINKEDIN_CHAR_CONTRACT`, NOT TYPED. This line said
        # "no message is over 600 characters", a number no gate anywhere
        # enforced and 2x the measured ceiling.
        "the connection note is under %s characters, LinkedIn's own cap"
        % bound_phrase(LINKEDIN_CHAR_CONTRACT["li1"][2]),
        "a note at or over %d characters is the one note band measured BELOW "
        "the no-note acceptance baseline; stay under it"
        % LI1_MEASURED_CEILING,
        chars_rule(),
        "a question asked by email may not be asked again on LinkedIn",
    ),
    output_schema={
        "connect": "str (<280 chars, lowercase, no company, one fact, no pitch)",
        "msg1": "str (Hi {{firstName}}, who, what, why them, one question)",
        "msg2": "str (capability, email cross-reference, one soft ask)",
        "msg3": "str (short close)",
    },
    failure_handling="Return empty strings for all four messages when the "
                     "lead has no LinkedIn profile. Writing messages nobody "
                     "can send is the failure.",
    escalation="Escalate when the lead has a LinkedIn profile but no fact "
               "supports a personalised connect: a generic connect is worse "
               "than no connect.",
    consumer="stage_f",
)
