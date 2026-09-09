#!/usr/bin/env python3
"""What to talk to this company about, as structured input rather than copy.

No email is written here. What this produces is the brief a generator later
works from: which angles fit this vertical, which pains this persona actually
owns, and - critically - which of those the evidence supports.

The rule that keeps this honest: **a pain is only recommended where something
supports it**. A digital agency's COO probably does care about utilisation, and
"probably" is not a sentence we can put in an email. So every recommendation
carries `supported: true/false`, the supported ones come first, and the
unsupported ones are labelled as hypotheses for a human rather than quietly
handed to a model as facts.

  python -m src.strategy --describe
"""
import argparse
import json

from . import icp, segments

# ------------------------------------------------------------ pain model
#
# The categories Productive actually addresses. Each is a thing that goes wrong
# in a delivery business, phrased as the operator would describe it rather than
# as a feature.

RESOURCE_PLANNING = "resource_planning"
UTILIZATION = "utilization"
PROJECT_MARGIN = "project_margin"
DELIVERY_VISIBILITY = "delivery_visibility"
BUDGET_CONTROL = "budget_control"
CAPACITY_FORECASTING = "capacity_forecasting"
TIME_TRACKING = "time_tracking"
PROFITABILITY_REPORTING = "profitability_reporting"
TOOL_SPRAWL = "tool_sprawl"

PAINS = (RESOURCE_PLANNING, UTILIZATION, PROJECT_MARGIN, DELIVERY_VISIBILITY,
         BUDGET_CONTROL, CAPACITY_FORECASTING, TIME_TRACKING,
         PROFITABILITY_REPORTING, TOOL_SPRAWL)

PAIN_WORDS = {
    RESOURCE_PLANNING: "who is working on what next month",
    UTILIZATION: "how much of the team's time is billable",
    PROJECT_MARGIN: "whether a project made money",
    DELIVERY_VISIBILITY: "where a project actually is",
    BUDGET_CONTROL: "whether a budget is about to be overrun",
    CAPACITY_FORECASTING: "whether the work coming in can be delivered",
    TIME_TRACKING: "getting hours recorded without chasing people",
    PROFITABILITY_REPORTING: "seeing margin before the month closes",
    TOOL_SPRAWL: "the same numbers living in five different tools",
}

# Which ICP dimension, if it fired, supports which pain. This is the link that
# stops a recommendation being a guess: the evidence that scored the company is
# the evidence that justifies the angle.
SUPPORTED_BY = {
    RESOURCE_PLANNING: ("resource_planning_need", "delivery_complexity"),
    UTILIZATION: ("utilization_need",),
    PROJECT_MARGIN: ("profitability_need",),
    DELIVERY_VISIBILITY: ("delivery_complexity", "operational_complexity"),
    BUDGET_CONTROL: ("time_tracking_need", "profitability_need"),
    CAPACITY_FORECASTING: ("resource_planning_need", "distributed_teams"),
    TIME_TRACKING: ("time_tracking_need",),
    PROFITABILITY_REPORTING: ("profitability_need",),
    TOOL_SPRAWL: ("operational_complexity", "distributed_teams"),
}

# Which persona owns which pain. A CFO does not chase timesheets and a founder
# does not read a utilisation report; sending either the other's message is
# how a good product sounds irrelevant.
PERSONA_PAINS = {
    "founder": (PROJECT_MARGIN, DELIVERY_VISIBILITY, CAPACITY_FORECASTING,
                TOOL_SPRAWL),
    "operations": (RESOURCE_PLANNING, UTILIZATION, DELIVERY_VISIBILITY,
                   CAPACITY_FORECASTING),
    "finance": (PROJECT_MARGIN, PROFITABILITY_REPORTING, BUDGET_CONTROL,
                UTILIZATION),
    "delivery": (CAPACITY_FORECASTING, RESOURCE_PLANNING, DELIVERY_VISIBILITY,
                 TIME_TRACKING),
}

# Vertical-specific emphasis. The same pain lands differently depending on what
# the company sells.
VERTICAL_ANGLES = {
    segments.DIGITAL_MARKETING: (RESOURCE_PLANNING, UTILIZATION,
                                 DELIVERY_VISIBILITY, PROJECT_MARGIN),
    segments.PERFORMANCE_MARKETING: (UTILIZATION, PROJECT_MARGIN,
                                     BUDGET_CONTROL),
    segments.SEO: (UTILIZATION, RESOURCE_PLANNING, PROJECT_MARGIN),
    segments.PR: (UTILIZATION, TIME_TRACKING, PROJECT_MARGIN),
    segments.CREATIVE: (RESOURCE_PLANNING, PROJECT_MARGIN, DELIVERY_VISIBILITY),
    segments.DESIGN_UX: (RESOURCE_PLANNING, UTILIZATION, DELIVERY_VISIBILITY),
    segments.SOFTWARE_DEV: (CAPACITY_FORECASTING, RESOURCE_PLANNING,
                            DELIVERY_VISIBILITY, PROJECT_MARGIN),
    segments.PRODUCT_DEV: (CAPACITY_FORECASTING, DELIVERY_VISIBILITY,
                           PROJECT_MARGIN),
    segments.CONSULTING: (UTILIZATION, PROFITABILITY_REPORTING,
                          RESOURCE_PLANNING),
    segments.PROFESSIONAL_SERVICES: (UTILIZATION, TIME_TRACKING,
                                     PROFITABILITY_REPORTING),
    segments.ARCHITECTURE_ENGINEERING: (RESOURCE_PLANNING, BUDGET_CONTROL,
                                        PROJECT_MARGIN),
    segments.OTHER_AGENCY: (RESOURCE_PLANNING, UTILIZATION, PROJECT_MARGIN),
    segments.OTHER_PROFESSIONAL: (UTILIZATION, PROFITABILITY_REPORTING),
}


def settings(config):
    block = ((config or {}).get("messaging") or {})
    merged = {
        "max_angles": 3,
        # Whether an unsupported pain may be recommended at all. Off by
        # default: an angle nothing supports is a hypothesis, not a brief.
        "include_unsupported": block.get("include_unsupported") is True,
    }
    try:
        if block.get("max_angles") is not None:
            merged["max_angles"] = max(1, int(block["max_angles"]))
    except (TypeError, ValueError):
        pass
    return merged


def _fired(verdict):
    """The ICP dimensions that actually scored, as a set of names."""
    return {signal["dimension"] for signal in verdict.get("positive_signals")
            or [] if signal.get("weight", 0) > 0}


def _evidence_for(pain, verdict):
    fired = _fired(verdict)
    return [name for name in SUPPORTED_BY.get(pain, ()) if name in fired]


def for_company(segment, verdict, persona_plan, config=None):
    """Angles and pains for one company, split by what the evidence supports."""
    policy = settings(config)
    if verdict.get("icp_status") != icp.QUALIFIED:
        return {
            "recommended_angles": [],
            "persona_angles": {},
            "relevant_pain_categories": [],
            "unsupported_hypotheses": [],
            "why": (f"status is {verdict.get('icp_status')}: no messaging "
                    "strategy is produced for a company we have not qualified"),
        }

    vertical = segment.get("vertical")
    candidates = list(VERTICAL_ANGLES.get(vertical, ()))
    if not candidates:
        candidates = [RESOURCE_PLANNING, UTILIZATION, PROJECT_MARGIN]

    scored = []
    for pain in candidates:
        evidence = _evidence_for(pain, verdict)
        scored.append({
            "pain": pain,
            "describes": PAIN_WORDS[pain],
            "supported": bool(evidence),
            "supported_by": evidence,
            "why": (f"the company's own evidence fired {', '.join(evidence)}"
                    if evidence else
                    f"typical for {vertical}, but nothing in this company's "
                    "evidence supports it"),
        })

    supported = [row for row in scored if row["supported"]]
    unsupported = [row for row in scored if not row["supported"]]

    recommended = supported[:policy["max_angles"]]
    if policy["include_unsupported"]:
        recommended = (recommended
                       + unsupported[:policy["max_angles"] - len(recommended)])

    persona_angles = {}
    for persona in persona_plan.get("persona_priority") or []:
        owned = PERSONA_PAINS.get(persona, ())
        rows = [row for row in scored if row["pain"] in owned]
        rows.sort(key=lambda row: (not row["supported"],
                                   candidates.index(row["pain"])))
        persona_angles[persona] = [
            {"pain": row["pain"], "describes": row["describes"],
             "supported": row["supported"], "why": row["why"]}
            for row in rows[:policy["max_angles"]]]

    return {
        "vertical": vertical,
        "recommended_angles": [row["pain"] for row in recommended],
        "recommended_detail": recommended,
        "persona_angles": persona_angles,
        "relevant_pain_categories": [row["pain"] for row in supported],
        # Kept and labelled rather than dropped: they are the questions a
        # human might answer with one look at the website.
        "unsupported_hypotheses": [row["pain"] for row in unsupported],
        "why": (f"{len(supported)} of {len(scored)} typical {vertical} angles "
                "are supported by this company's own evidence"),
    }


def describe(config=None):
    return {
        "pains": {pain: PAIN_WORDS[pain] for pain in PAINS},
        "persona_pains": {k: list(v) for k, v in PERSONA_PAINS.items()},
        "vertical_angles": {k: list(v) for k, v in VERTICAL_ANGLES.items()},
        "supported_by": {k: list(v) for k, v in SUPPORTED_BY.items()},
        "policy": settings(config),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--describe", action="store_true")
    a = p.parse_args(argv)
    print(json.dumps(describe(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
