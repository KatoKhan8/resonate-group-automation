"""Stage B: fact extraction from company sources.

Extract 3-5 verifiable facts from scraped company material. Each fact must
be a complete sentence supported by a span of the source text, with a
verbatim quote and a source index. No inference, no generalisation, no URLs.

The prompt lives in ``copyprompts.EXTRACT_SYSTEM``. This skill wraps it and
declares stage_b as its consumer.
"""
from .. import copyprompts
from . import Skill

SKILL = Skill(
    name="account_research",
    purpose="Extract 3-5 verifiable facts about a company from its own "
            "published material. Each fact is a complete sentence backed by "
            "a verbatim quote from a numbered source block. No inference, no "
            "URLs, no numbers computed from dates.",
    inputs=("company", "domain", "sources"),
    secondbrain_sections=("profile", "market", "customers"),
    approved_tools=("gpt-oss-120b",),
    procedure=copyprompts.EXTRACT_SYSTEM,
    examples_good=(
        {
            "output": {
                "facts": [
                    {"text": "Brightwave hired three designers in Brooklyn "
                             "this quarter.",
                     "quote": "We're expanding our Brooklyn design team with "
                              "three new roles this quarter.",
                     "source_index": 2, "kind": "role", "confidence": 0.95},
                ],
                "angle": "growth_without_systems",
                "company_hook": "Brightwave is a Brooklyn design agency "
                                "expanding its team this quarter.",
                "usable": True,
            },
        },
    ),
    examples_bad=(
        {
            "output": {
                "facts": [
                    {"text": "Brightwave is a leading design agency.",
                     "quote": "", "source_index": 0, "kind": "site",
                     "confidence": 0.5},
                ],
            },
            "why": "a slogan with no verbatim span is not a fact; an empty "
                   "quote fails the character-for-character check",
        },
        {
            "output": {
                "facts": [
                    {"text": "Brightwave has been in business for 14 years.",
                     "quote": "Founded in 2011", "source_index": 1,
                     "kind": "site", "confidence": 0.8},
                ],
            },
            "why": "computing a number from a date is banned; the source says "
                   "'since 2011' and that is what the fact must say",
        },
    ),
    validation=(
        "between 3 and 5 facts when usable is true",
        "every fact has a non-empty quote that appears verbatim in the source",
        "source_index is a valid index into the source list",
        "angle is one of the allowed values or null",
        "no URL in any fact text",
        "no number computed from a date",
    ),
    output_schema={
        "facts": [{"text": "str", "quote": "str", "source_index": "int",
                    "kind": "post|role|site|profile", "confidence": "float"}],
        "angle": "str | null",
        "angle_reason": "str",
        "company_hook": "str",
        "usable": "bool",
        "why_this_lead": "str",
    },
    failure_handling="Set usable=false when fewer than three real facts can "
                     "be extracted. Padding to reach three is the failure.",
    escalation="Escalate when all sources are navigation text, cookie banners "
               "or slogans and no fact is extractable.",
    consumer="stage_b",
)
