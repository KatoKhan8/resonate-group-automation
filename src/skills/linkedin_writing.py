"""Stage F: LinkedIn message writing.

Write four LinkedIn messages that mirror the email cadence but do a
different job: start a conversation and ask short questions. Full sentences,
proper capitalisation, the same voice as the emails. The connection request
is under 280 characters with no company name and no pitch. Every message
after the connect opens with {firstName}.

The prompt lives in ``copystages.WRITER_SYSTEM`` (LinkedIn section). This
skill wraps it and declares stage_f as its consumer.
"""
from .. import copystages
from . import Skill

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
        "no message is over 600 characters",
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
