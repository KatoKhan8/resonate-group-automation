"""Stage F: cold email writing.

Write only the parts of the email that change per lead: the subject, the
first line of email 1, one bridge sentence opening each of emails 2-5, and
the P.S. lines. The standing paragraphs are approved copy supplied by the
template; the writer fills the gaps. No dashes, no signatures, no computed
numbers, no pain phrases in subjects.

The prompt lives in ``copystages.WRITER_SYSTEM``. This skill wraps it and
declares stage_f as its consumer.
"""
from .. import copystages
from . import Skill

#: THE WORD CONTRACT, AS DATA, BECAUSE A CONTRACT NOTHING CAN READ IS NOT A
#: CONTRACT. (floor, target, ceiling) in words, per step of the five-email
#: sequence, and SINCE 2026-10-02 THE ONLY AUTHORITY FOR AN EMAIL BODY'S WORD
#: COUNT - operator ruling, that day, in those terms.
#:
#: em1 and em3 open threads and are 60 to 90 aiming for 75. em2 and em4 are the
#: same-thread follow-ups and are 45 to 90 aiming for 60: `copystages` specifies
#: them as shorter than the mail they answer, so their floor is the lower one and
#: their ceiling is not. em5 is 45 to 90 aiming for 65.
#:
#: These numbers are declared HERE and nowhere else. The prose in `validation`
#: and `output_schema` below is rendered from them, `copystages.WRITER_SYSTEM`
#: and `copystages.FINAL_CHECK` render their own instructions from them, and
#: `src.lint` imports this mapping rather than carrying a second copy. Measured
#: 2026-10-02: the contract was prose in three renderings, `lint.py` contained no
#: 60 and no 90 as a word bound at all, and the one approved canary copy shipped
#: an em2 of 41 words and an em3 of 53 - under contract by 19 and 7 - through
#: both lint doors clean. A declared range nothing reads is a preference.
#:
#: EVERY RANGE HAS ROOM IN IT, asserted by
#: `tests.test_word_contract_enforced.TestEveryRangeHasRoom`: at least 30 legal
#: lengths per step. That guard exists because the abolished 15-to-60 thread
#: reply range and a 60-to-90 em2 intersected to the single value 60. One legal
#: length is an equality, not a threshold, and no writer hits it reliably.
WORD_CONTRACT = {
    "em1": (60, 75, 90),
    "em2": (45, 60, 90),
    "em3": (60, 75, 90),
    "em4": (45, 60, 90),
    "em5": (45, 65, 90),
}


def word_range(step_key):
    """(floor, ceiling) for one step key, or None if it is not one of the five.

    None means "this contract says nothing about that step", NOT "anything
    goes": the caller keeps whatever other bounds it has. A LinkedIn message
    and the single-email draft shape have their own contracts elsewhere.
    """
    spec = WORD_CONTRACT.get(str(step_key or "").strip().lower())
    return (spec[0], spec[2]) if spec else None


def word_target(step_key):
    """The middle of the range this step aims for. The floor is not the target."""
    spec = WORD_CONTRACT.get(str(step_key or "").strip().lower())
    return spec[1] if spec else None


def _words_phrase(step_key):
    lo, target, hi = WORD_CONTRACT[step_key]
    return "~%d words, %d-%d range" % (target, lo, hi)


def words_rule():
    """The whole contract as one sentence, rendered from the mapping itself.

    Per step rather than one range for all five, because the five are no longer
    the same: an em2 told "60-90 words" when its own range is 45-90 is being told
    the wrong number, which is the defect this contract was made readable to fix.
    """
    return "email bodies are inside their own step's range: " + ", ".join(
        "%s %d-%d aiming for %d" % (step, lo, hi, target)
        for step, (lo, target, hi) in WORD_CONTRACT.items())

SKILL = Skill(
    name="cold_email_writing",
    purpose="Write the per-lead spans of a five-email cold outreach "
            "sequence: subjects, first line, bridge sentences and P.S. "
            "lines. The standing paragraphs are supplied; the writer fills "
            "the gaps. The first line quotes one fact about the prospect's "
            "company. No dashes, no signatures, no computed numbers.",
    inputs=("lead", "company", "facts", "plan", "capability_sentence",
            "ps_variant", "has_linkedin"),
    secondbrain_sections=("profile", "customers", "messaging", "offers"),
    approved_tools=("claude-sonnet",),
    procedure=copystages.WRITER_SYSTEM,
    examples_good=(
        {
            "output": {
                "subject": "your brooklyn design hires",
                "first_line": "Saw you're adding three designers to the "
                              "Brooklyn team this quarter.",
                "bridges": {"em2": "The teams that grow fastest are usually "
                                   "the ones where the numbers arrive too "
                                   "late to act on."},
                "emails": {"em1": "Hi {firstName}, ... (%s)"
                                  % _words_phrase("em1")},
                "confidence": 0.85,
            },
        },
    ),
    examples_bad=(
        {
            "output": {"subject": "Profitability Visible On Monday Not Two "
                                   "Weeks Late"},
            "why": "pain phrase in the subject, Title Case, over 9 words; "
                   "all three are banned",
        },
        {
            "output": {"first_line": "Agencies like yours often struggle "
                                     "with margin visibility."},
            "why": "generic - true of every agency, not about THIS company; "
                   "the first line must quote a fact about them",
        },
        {
            "output": {"bridges": {"em2": "As I mentioned earlier..."}},
            "why": "a bridge must not restate the first line or another "
                   "bridge; 'as I mentioned' restates",
        },
    ),
    validation=(
        "subject is 4-9 words, lowercase except real proper nouns",
        "subject contains no banned phrase and no pain phrase",
        "first_line quotes or closely paraphrases one supplied fact",
        "no dash (em, en, or separator hyphen) in any field",
        "no signature or sign-off name",
        "no number computed from a date",
        "no two subjects in a batch are identical",
        "each bridge is one sentence and does not restate another",
        words_rule(),
    ),
    output_schema={
        "hold": "bool",
        "hold_reason": "str | null",
        "subject": "str",
        "subject_alt": "str",
        "subject_breakup": "str",
        "emails": {k: "str (%s, required)" % _words_phrase(k)
                   for k in WORD_CONTRACT},
        "ps": {"em1": "str", "em3": "str"},
        "ps_variant": "str",
        "linkedin": {"li1": "str (under 280 chars, required)",
                     "li2": "str (under 280 chars, required)",
                     "li3": "str (under 280 chars, required)",
                     "li4": "str (under 280 chars, required)",
                     "li5": "str (under 280 chars, required)"},
        "facts_used": {"em1": "int", "ps_em1": "int"},
        "confidence": "float",
        "why_this_lead": "str",
    },
    failure_handling="Set hold=true with a hold_reason when the facts do not "
                     "support a real first line. Holding is better than "
                     "sending something generic.",
    escalation="Escalate when hold=true and the lead has three or more true "
               "specific facts: holding a lead we have material for is not "
               "the intended outcome.",
    consumer="stage_f",
)
