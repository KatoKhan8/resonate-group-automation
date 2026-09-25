"""Stage E: sequence strategy.

Plan a nine-message outreach sequence BEFORE any copy is written. Decide
what each message is FOR: its objective, angle, proof and CTA. This exists
because the previous engine wrote five emails that each made the same
argument in different words.

The prompt lives in ``copystages.STRATEGY_SYSTEM``. This skill wraps it and
declares stage_e as its consumer.
"""
from .. import copystages
from . import Skill

SKILL = Skill(
    name="campaign_strategy",
    purpose="Plan a nine-message outreach sequence before any copy is "
            "written. Each message gets an objective, an angle different "
            "from every earlier one, a proof basis and one CTA. A step with "
            "no credible new angle is set null rather than filled with "
            "filler.",
    inputs=("company", "hypothesis", "capability", "what_changes",
            "role_title", "facts", "assets_available"),
    secondbrain_sections=("profile", "market", "customers", "messaging"),
    approved_tools=("gpt-oss-120b",),
    procedure=copystages.STRATEGY_SYSTEM,
    examples_good=(
        {
            "output": {
                "emails": {
                    "em1": {"objective": "establish relevance",
                            "angle": "hiring surge outpacing process",
                            "proof": "fact 2: three new Brooklyn roles",
                            "cta": "discovery: do you track capacity in "
                                   "real time?"},
                    "em2": {"objective": "adjacent problem",
                            "angle": "margin visibility lag",
                            "proof": "product capability",
                            "cta": "qualification: dedicated platform or "
                                   "mix of tools?"},
                },
                "dropped": [],
            },
        },
    ),
    examples_bad=(
        {
            "output": {
                "emails": {
                    "em1": {"objective": "introduce Productive",
                            "angle": "project margin visibility",
                            "proof": "product", "cta": "meeting request"},
                    "em2": {"objective": "follow up",
                            "angle": "project margin visibility",
                            "proof": "product", "cta": "meeting request"},
                },
            },
            "why": "em2 restates em1's angle and CTA; a meeting request "
                   "before relevance is established is banned",
        },
    ),
    validation=(
        "every angle is different from every earlier angle",
        "no CTA is repeated across messages",
        "CTAs progress: discovery, qualification, resource, meeting",
        "a step set to null is listed in dropped with a reason",
        "LinkedIn messages declare which email they must not duplicate",
    ),
    output_schema={
        "emails": {"em1": {"objective": "str", "angle": "str",
                            "proof": "str", "cta": "str"},
                   "em2": "same", "em3": "same", "em4": "same",
                   "em5": "same"},
        "linkedin": {"connect": {"objective": "str", "angle": "str",
                                  "cta": "str"},
                     "msg1": "same + must_not_repeat",
                     "msg2": "same", "msg3": "same"},
        "dropped": ["str"],
        "repetition_check": "str",
    },
    failure_handling="Set a step to null and list it in dropped when no "
                     "credible new angle exists. Four good messages beat "
                     "five where one is filler.",
    escalation="Escalate when no assets are available AND the hypothesis is "
               "thin: the sequence cannot be planned on product claims alone.",
    consumer="stage_e",
)
