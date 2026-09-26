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
                "emails": {"em1": "Hi {firstName}, ... (60-90 words)"},
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
        "email bodies are 60-90 words",
    ),
    output_schema={
        "hold": "bool",
        "hold_reason": "str | null",
        "subject": "str",
        "subject_alt": "str",
        "subject_breakup": "str",
        "emails": {"em1": "str (60-90 words)", "em2": "str", "em3": "str",
                   "em4": "str", "em5": "str"},
        "ps": {"em1": "str", "em3": "str"},
        "ps_variant": "str",
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
