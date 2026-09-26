"""Stage A: ICP qualification.

Is this company a services agency that runs client projects? A software
product company, a data platform, an affiliate network, a staffing business
or a freelancer does not qualify, however much the website sounds like one.

The prompt lives in ``copyprompts.ICP_SYSTEM``. This skill wraps it and
declares stage_a as its consumer.
"""
from .. import copyprompts
from . import Skill

SKILL = Skill(
    name="signal_verification",
    purpose="Decide whether a company is a services agency that runs client "
            "projects and bills for that work. Reject software products, "
            "platforms, affiliates, staffing businesses and freelancers.",
    inputs=("company", "domain", "sources"),
    secondbrain_sections=("market", "customers"),
    approved_tools=("gpt-oss-120b",),
    procedure=copyprompts.ICP_SYSTEM,
    examples_good=(
        {
            "input": {"company": "Acme Agency", "domain": "acme.com",
                      "sources": [{"text": "We deliver marketing campaigns for "
                                            "B2B clients on a retainer basis."}]},
            "output": {"is_agency": True, "confidence": 0.9,
                       "evidence": "deliver marketing campaigns for B2B clients "
                                   "on a retainer basis"},
        },
    ),
    examples_bad=(
        {
            "input": {"company": "ToolCo", "domain": "toolco.com",
                      "sources": [{"text": "We sell software to agencies."}]},
            "output": {"is_agency": True},
            "why": "a software vendor is not an agency, however many agencies "
                   "buy it",
        },
    ),
    validation=(
        "is_agency is boolean",
        "confidence is 0.0 to 1.0",
        "evidence is a verbatim quote from the sources",
        "when confidence < 0.6, is_agency is false",
    ),
    output_schema={
        "is_agency": "bool",
        "confidence": "float",
        "evidence": "str",
        "what_they_actually_are": "str | null",
    },
    failure_handling="Hold the lead when confidence < 0.6. Do not invent an "
                     "ICP verdict from a slogan or a menu label.",
    escalation="Escalate when the sources are navigation text, boilerplate or "
               "contradictory and no verdict is defensible.",
    consumer="stage_a",
)
