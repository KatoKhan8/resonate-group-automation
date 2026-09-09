#!/usr/bin/env python3
"""Who to look for at this company, and how many of them.

The mistake this replaces is searching the same titles everywhere. A four-
person studio has no Head of Resource Management, and a 300-person agency's
founder has not thought about timesheets in six years. Searching for the wrong
titles is not merely ineffective - each search is a paid ContactOut call, so a
strategy that ignores company size spends real money finding people who do not
exist.

Routing is decided from the segment: vertical, employee band, business model
and how much operational evidence there is. Every strategy is client
configuration, because the right person to open with is a go-to-market opinion
that will change without this module changing.

The cap is the other half. Tier decides how many contacts are worth paying for,
and a company under review is worth **zero** until a human says otherwise.

  python -m src.routing --describe
"""
import argparse
import json

from . import icp, segments

# ---------------------------------------------------------- the strategies
#
# Ordered by company size, because that is what changes who owns the problem.
# The names are stable: they appear in the dossier, in segment keys and in
# reporting, so renaming one is a migration rather than an edit.

FOUNDER_LED = "founder_led"
OPERATIONS_LED = "operations_led"
FINANCE_LED = "finance_led"
DELIVERY_LED = "delivery_led"
STRATEGIES = (FOUNDER_LED, OPERATIONS_LED, FINANCE_LED, DELIVERY_LED)

# The one persona whose titles are identical wherever it appears, so they are
# declared once. Resource management is a family of its own rather than a few
# titles inside `delivery`: where the role exists at all it owns scheduling
# outright, and a persona that means two different jobs cannot be given one
# angle. It is last in every priority list because it only exists above a
# certain size - `personas_for` drops a persona nobody holds.
RESOURCE_MANAGEMENT_TITLES = ["Head of Resource Management", "Resource Manager",
                              "Resourcing Manager", "Head of Resourcing",
                              "Traffic Manager", "Studio Manager"]

# The persona families this client can route to. Named so a config that
# invents one is refused rather than silently producing a persona with no
# angle behind it.
PERSONA_FAMILIES = ("founder", "operations", "finance", "delivery",
                    "resource_management")

# persona -> titles. A persona is the role that owns the pain; the titles are
# how that role is spelled at companies of this size.
DEFAULT_STRATEGIES = {
    FOUNDER_LED: {
        "why": "at this size the founder still owns delivery, resourcing and "
               "the P&L, and nobody else can act on any of it",
        "personas": {
            "founder": ["Founder", "Co-Founder", "CEO",
                        "Chief Executive Officer", "Managing Director",
                        "Owner"],
            "operations": ["Head of Operations", "Operations Manager", "COO",
                           "Chief Operating Officer"],
        },
        "priority": ["founder", "operations"],
    },
    OPERATIONS_LED: {
        "why": "past about fifty people resourcing stops fitting in one head, "
               "and an operations lead owns the problem before finance does",
        "personas": {
            "operations": ["COO", "Chief Operating Officer",
                           "Operations Director", "Head of Operations",
                           "Head of Delivery", "Operations Manager"],
            "finance": ["Finance Director", "Head of Finance", "Financial "
                        "Controller"],
            "resource_management": RESOURCE_MANAGEMENT_TITLES,
            "founder": ["Founder", "CEO", "Chief Executive Officer",
                        "Managing Director"],
        },
        "priority": ["operations", "finance", "resource_management",
                     "founder"],
    },
    FINANCE_LED: {
        "why": "at this size project margin is a board-level number and "
               "finance owns the question before operations hears about it",
        "personas": {
            "finance": ["CFO", "Chief Financial Officer",
                        "Finance Director", "VP Finance",
                        "Head of Finance"],
            "operations": ["COO", "Chief Operating Officer", "VP Operations",
                           "Director of Operations"],
            "delivery": ["Director of Delivery", "Head of Delivery",
                         "VP Delivery"],
            "resource_management": RESOURCE_MANAGEMENT_TITLES,
        },
        "priority": ["finance", "operations", "delivery",
                     "resource_management"],
    },
    DELIVERY_LED: {
        "why": "engineering-heavy delivery makes capacity and forecasting the "
               "first question, and the delivery lead feels it first",
        "personas": {
            "delivery": ["Head of Delivery", "Delivery Director",
                         "Head of Engineering", "VP Engineering"],
            "operations": ["COO", "Chief Operating Officer",
                           "Operations Director", "Head of Operations"],
            "resource_management": RESOURCE_MANAGEMENT_TITLES,
            "finance": ["Finance Director", "CFO", "Chief Financial Officer"],
        },
        "priority": ["delivery", "operations", "resource_management",
                     "finance"],
    },
}

# Which strategy fits which band. Bands come from src/segments.py, so a new
# band has to be routed deliberately rather than silently falling through.
DEFAULT_BAND_STRATEGY = {
    "1_9": FOUNDER_LED,
    "10_19": FOUNDER_LED,
    "20_49": OPERATIONS_LED,
    "50_99": OPERATIONS_LED,
    "100_199": OPERATIONS_LED,
    "200_499": FINANCE_LED,
    "500_999": FINANCE_LED,
    "1000_PLUS": FINANCE_LED,
}

# Verticals where delivery leads rather than operations, at mid size and up.
DELIVERY_LED_VERTICALS = (segments.SOFTWARE_DEV, segments.PRODUCT_DEV)

# How many contacts each tier is worth paying to find.
DEFAULT_CAPS = {
    icp.TIER_A: 3,
    icp.TIER_B: 2,
    icp.TIER_C: 1,
    icp.TIER_REVIEW: 0,
    icp.TIER_NOT_ICP: 0,
}


def settings(config):
    """The client's routing model, all of it overridable."""
    block = ((config or {}).get("routing") or {})
    caps = dict(DEFAULT_CAPS)
    for tier, value in (block.get("caps") or {}).items():
        if tier in DEFAULT_CAPS:
            try:
                caps[tier] = max(0, int(value))
            except (TypeError, ValueError):
                pass

    bands = dict(DEFAULT_BAND_STRATEGY)
    known = {name for name, _, _ in segments.bands(config)} | {segments.UNKNOWN}
    for band, strategy in (block.get("band_strategy") or {}).items():
        if band in known and strategy in STRATEGIES:
            bands[band] = strategy

    strategies = {name: {"why": spec["why"],
                         "personas": {k: list(v) for k, v in
                                      spec["personas"].items()},
                         "priority": list(spec["priority"])}
                  for name, spec in DEFAULT_STRATEGIES.items()}
    for name, given in (block.get("strategies") or {}).items():
        if name not in strategies or not isinstance(given, dict):
            continue
        for persona, titles in (given.get("personas") or {}).items():
            if isinstance(titles, list) and titles:
                strategies[name]["personas"][persona] = [str(t) for t in titles]
        priority = given.get("priority")
        if isinstance(priority, list) and priority:
            kept = [p for p in priority if p in strategies[name]["personas"]]
            if kept:
                strategies[name]["priority"] = kept

    return {
        "caps": caps,
        "band_strategy": bands,
        "strategies": strategies,
        # An unknown band cannot be routed by size, so it is routed by the
        # safest strategy rather than by the largest.
        "fallback_strategy": (block.get("fallback_strategy")
                              if block.get("fallback_strategy") in STRATEGIES
                              else FOUNDER_LED),
    }


def strategy_for(segment, config=None):
    """Which strategy this company gets, and why."""
    policy = settings(config)
    band = segment.get("employee_band") or segments.UNKNOWN
    vertical = segment.get("vertical")

    if band == segments.UNKNOWN:
        return (policy["fallback_strategy"],
                "company size is unknown, so the smallest-company strategy is "
                "used: it targets roles that exist at every size")

    name = policy["band_strategy"].get(band, policy["fallback_strategy"])

    # An engineering-heavy agency past the founder stage is a delivery
    # conversation before it is an operations one.
    if (vertical in DELIVERY_LED_VERTICALS
            and segments.band_order(band, config)
            >= segments.band_order("20_49", config)):
        return (DELIVERY_LED,
                f"{vertical} at {band}: capacity and forecasting land with "
                "delivery before operations")

    if name == OPERATIONS_LED and segment.get("business_model") == segments.CONSULTANCY:
        return (FINANCE_LED,
                f"a consultancy at {band}: utilisation is a finance number "
                "here rather than an operations one")

    return name, f"{band} maps to the {name} strategy"


def plan(rec, segment, verdict, config=None):
    """The persona plan for one company: who, what titles, and how many.

    `max_contacts_to_enrich` is the number that controls spend, and it is zero
    for anything not qualified. A company under review is not a cheap company -
    it is a company nobody has decided about yet.
    """
    policy = settings(config)
    name, why = strategy_for(segment, config)
    spec = policy["strategies"][name]
    tier = verdict.get("icp_tier")
    status = verdict.get("icp_status")

    cap = policy["caps"].get(tier, 0)
    cap_why = f"tier {tier} allows up to {cap} contact(s)"
    if status != icp.QUALIFIED:
        cap = 0
        cap_why = (f"status is {status}: no person enrichment is planned until "
                   "a human decides")

    priority = spec["priority"]
    titles = []
    for persona in priority:
        titles.extend(spec["personas"].get(persona, []))

    return {
        "record_id": rec.get("id"),
        "domain": rec.get("domain"),
        "strategy": name,
        "strategy_reason": why,
        "persona_priority": list(priority),
        "persona_reason": spec["why"],
        "personas": {p: list(spec["personas"].get(p, [])) for p in priority},
        # Ordered: the first title is the one a search should try first.
        "target_titles": titles,
        "max_contacts_to_enrich": cap,
        "cap_reason": cap_why,
        "icp_tier": tier,
        "icp_status": status,
    }


def describe(config=None):
    policy = settings(config)
    return {
        "strategies": {name: {"why": spec["why"],
                              "priority": spec["priority"],
                              "personas": spec["personas"]}
                       for name, spec in policy["strategies"].items()},
        "band_strategy": policy["band_strategy"],
        "caps": policy["caps"],
        "delivery_led_verticals": list(DELIVERY_LED_VERTICALS),
        "fallback_strategy": policy["fallback_strategy"],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--describe", action="store_true")
    p.add_argument("--client")
    a = p.parse_args(argv)

    from . import clients
    config = {}
    if a.client:
        try:
            config = clients.load(a.client)
        except Exception:
            config = {}
    print(json.dumps(describe(config), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
