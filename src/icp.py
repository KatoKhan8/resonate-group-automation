#!/usr/bin/env python3
"""Is this company actually a Productive prospect, and what is the evidence?

Not a model's yes or no. Every dimension below is scored from stored company
facts and retained evidence by arithmetic a person can follow, and the answer
carries the signals that produced it. An operator who disagrees with a verdict
must be able to see which dimension is wrong and change a weight in config
rather than argue with a black box.

Three rules the whole module is built around:

**Missing information is never positive evidence.** A company with no
employee count does not get the benefit of the doubt on size; it gets a
`missing` note, its confidence drops, and if enough is missing the verdict is
`unknown` rather than a confident guess in either direction.

**Confidence and score are different questions.** A low score with good
evidence is a rejection. A low score with almost no evidence is `unknown`, and
those two must never share a bucket, because one is a decision and the other is
a task.

**Nothing is deleted.** A rejected company keeps its record and its reasons, so
"why did we not contact them?" is answerable a year later.

  python -m src.icp --describe
  python -m src.icp --record northwind
"""
import argparse
import json

from . import evidence, segments, store

# ------------------------------------------------------------- the verdict

QUALIFIED = "qualified"
REVIEW = "review"
REJECTED = "rejected"
UNKNOWN = "unknown"
STATUSES = (QUALIFIED, REVIEW, REJECTED, UNKNOWN)

TIER_A = "A"
TIER_B = "B"
TIER_C = "C"
TIER_REVIEW = "REVIEW"
TIER_NOT_ICP = "NOT_ICP"
TIERS = (TIER_A, TIER_B, TIER_C, TIER_REVIEW, TIER_NOT_ICP)

HIGH = "high"
MEDIUM = "medium"
LOW = "low"
CONFIDENCE = (HIGH, MEDIUM, LOW)


# --------------------------------------------------------- the dimensions
#
# Each dimension answers one question about whether Productive would help this
# company. The weights are defaults and every one is overridable in client
# config: Productive's ICP will change, and it must change in a YAML file
# rather than in this module.

DIMENSIONS = (
    "agency_fit",                 # is this a client-services business at all
    "project_delivery",           # does it deliver client projects
    "employee_count",             # is it big enough to feel the problem
    "delivery_complexity",        # more than one team, more than one discipline
    "distributed_teams",          # several offices or remote delivery
    "resource_planning_need",     # signals about scheduling people
    "profitability_need",         # signals about project margin
    "utilization_need",           # signals about billable time
    "time_tracking_need",         # signals about timesheets and budgets
    "operational_complexity",     # retainers plus projects, many clients
    "geography",                  # in a market this client sells to
    "service_not_product",        # sells time, not licences
)

DEFAULT_WEIGHTS = {
    "agency_fit": 20,
    "project_delivery": 12,
    "employee_count": 15,
    "delivery_complexity": 8,
    "distributed_teams": 5,
    "resource_planning_need": 8,
    "profitability_need": 8,
    "utilization_need": 6,
    "time_tracking_need": 5,
    "operational_complexity": 5,
    "geography": 4,
    "service_not_product": 4,
}

# Subtracted, not scaled: a negative signal is a reason, not a discount.
DEFAULT_PENALTIES = {
    "product_company": 40,
    "ecommerce": 40,
    "not_a_service_business": 30,
    "too_small": 25,
    "irrelevant_industry": 25,
    "holding_entity": 35,
    # A company far above the size this client sells to. Not a rejection on
    # its own - large agencies exist and buy - but a 20,000-person listed
    # group is a different motion from an outbound email to a COO.
    "unsuitable_enterprise": 20,
    "insufficient_evidence": 0,    # handled by confidence, never by score
    # Two facts that cannot both be true. Scored small on purpose: the damage
    # a contradiction does is to *confidence*, and pretending it is a rejection
    # would throw away a company whose evidence merely needs a second look.
    "contradictory_evidence": 10,
}

# Bumped whenever a weight, penalty, threshold or rule changes the number a
# given company would score. Stored on every verdict so a batch scored under an
# older model is visible as such rather than silently compared to a newer one.
SCORING_VERSION = "2026-08-27.1"

DEFAULT_THRESHOLDS = {
    "tier_a": 75,
    "tier_b": 60,
    "tier_c": 45,
    "reject_below": 30,
    # Below this many scored dimensions we do not claim to know anything.
    "min_dimensions_for_a_verdict": 4,
    "min_employees": 10,
    # Above this a company is penalised as an enterprise rather than an agency.
    # None disables the check, which is the right default for a client whose
    # ICP genuinely has no ceiling.
    "max_employees": 5000,
}

# Keyword evidence for the "need" dimensions. Deliberately phrases rather than
# single words: "capacity" alone appears on every consultancy's homepage.
NEED_SIGNALS = {
    "resource_planning_need": ("resource planning", "resourcing", "capacity "
                               "planning", "scheduling", "allocate", "bookings",
                               "who is available", "team planning"),
    "profitability_need": ("project profitability", "margin", "profitability",
                           "budget overrun", "cost control", "project margin"),
    "utilization_need": ("utilisation", "utilization", "billable", "chargeable",
                         "non-billable", "bench"),
    "time_tracking_need": ("time tracking", "timesheet", "timesheets",
                           "budget tracking", "logged hours"),
    "operational_complexity": ("multiple clients", "client portfolio",
                               "retainer", "concurrent projects",
                               "delivery teams", "practice areas"),
    "delivery_complexity": ("delivery team", "project manager", "account "
                            "manager", "producers", "disciplines", "studio",
                            "departments"),
}


def settings(config):
    """The client's ICP model. Everything here is meant to be edited."""
    block = ((config or {}).get("icp") or {})
    weights = dict(DEFAULT_WEIGHTS)
    for name, value in (block.get("weights") or {}).items():
        if name in DEFAULT_WEIGHTS:
            try:
                weights[name] = float(value)
            except (TypeError, ValueError):
                pass
    penalties = dict(DEFAULT_PENALTIES)
    for name, value in (block.get("penalties") or {}).items():
        if name in DEFAULT_PENALTIES:
            try:
                penalties[name] = float(value)
            except (TypeError, ValueError):
                pass
    thresholds = dict(DEFAULT_THRESHOLDS)
    for name, value in (block.get("thresholds") or {}).items():
        if name in DEFAULT_THRESHOLDS:
            try:
                thresholds[name] = float(value)
            except (TypeError, ValueError):
                pass
    # `icp.markets` if it is set, otherwise the client's own `market.geos`.
    #
    # These were two names for one answer and only the first was read. The
    # product writes the second: `/settings` exposes `market.geos` through
    # `workspaces.POLICY_KEYS`, and `icp.markets` appears in no policy key, no
    # starter template and no client file. So an operator could set Markets,
    # see the onboarding checklist go green, run a batch - and have the
    # geography dimension skipped for every company, silently, because the
    # scorer was reading a key the product cannot write. `productive.yaml`
    # works around it by transcribing the list a second time by hand, which is
    # the workaround becoming the documentation.
    #
    # `icp.markets` still wins where it is set, because a client may want to
    # score against regions while flagging on countries.
    stated = block.get("markets") or ((config or {}).get("market") or {}).get("geos")
    markets = [str(m).strip() for m in (stated or []) if str(m).strip()]
    return {"weights": weights, "penalties": penalties,
            "thresholds": thresholds, "markets": markets,
            "allow_review_enrichment": block.get("allow_review_enrichment")
            is True}


def _signal(name, weight, why, matched=()):
    return {"dimension": name, "weight": round(weight, 1), "why": why,
            "matched": list(matched)[:5]}


def score(rec, config=None, segment=None):
    """Score one company. Returns the number, the verdict and the reasons."""
    policy = settings(config)
    segment = segment if segment is not None else segments.classify(rec, config)
    text = segments.text_of(rec)
    weights = policy["weights"]
    thresholds = policy["thresholds"]

    positive, negative, missing = [], [], []
    total = 0.0
    scored_dimensions = 0

    # --- is this a client-services business at all -----------------------
    vertical = segment["vertical"]
    # Asked by kind rather than by membership of the built-in tuples, so a
    # vertical a client declared for its own market scores like the kind of
    # business it said it was. Without this the whole ICP model is Productive's
    # taxonomy: a company outside those fourteen categories fell through every
    # branch, scored nothing on the heaviest dimension, and took its confidence
    # down with it.
    kind = segments.kind_of(vertical, config)
    if kind == segments.AGENCY_KIND:
        total += weights["agency_fit"]
        scored_dimensions += 1
        positive.append(_signal("agency_fit", weights["agency_fit"],
                                f"classified as {vertical}",
                                segment["vertical_matched"]))
    elif kind == segments.NON_ICP_KIND:
        penalty = policy["penalties"]["not_a_service_business"]
        total -= penalty
        scored_dimensions += 1
        negative.append(_signal("agency_fit", -penalty,
                                f"{vertical} is a market this client has "
                                "declared it does not sell to",
                                segment["vertical_matched"]))
    elif kind == segments.SERVICE_KIND:
        total += weights["agency_fit"] * 0.7
        scored_dimensions += 1
        positive.append(_signal("agency_fit", weights["agency_fit"] * 0.7,
                                f"a services business ({vertical}) rather than "
                                "an agency", segment["vertical_matched"]))
    elif vertical == segments.NON_ICP:
        kinds = [s["kind"] for s in segment["non_icp_signals"]]
        penalty = policy["penalties"]["not_a_service_business"]
        if "saas" in kinds:
            penalty = policy["penalties"]["product_company"]
        elif "ecommerce" in kinds:
            penalty = policy["penalties"]["ecommerce"]
        elif "holding" in kinds:
            penalty = policy["penalties"]["holding_entity"]
        total -= penalty
        scored_dimensions += 1
        negative.append(_signal("agency_fit", -penalty,
                                f"not a project-delivery business: "
                                f"{', '.join(kinds) or 'no service evidence'}",
                                segment["vertical_matched"]))
    else:
        missing.append("vertical could not be classified from the available "
                       "evidence")

    # --- does it deliver client projects ---------------------------------
    if segment["delivery_model"] in (segments.PROJECT, segments.MIXED,
                                     segments.RETAINER):
        total += weights["project_delivery"]
        scored_dimensions += 1
        positive.append(_signal("project_delivery", weights["project_delivery"],
                                f"delivery model looks {segment['delivery_model']}",
                                segment["delivery_matched"]))
    elif segment["delivery_model"] == segments.STAFF_AUG:
        total += weights["project_delivery"] * 0.5
        scored_dimensions += 1
        positive.append(_signal("project_delivery",
                                weights["project_delivery"] * 0.5,
                                "staff augmentation: fits, but resourcing "
                                "matters more than project margin"))
    else:
        missing.append("no evidence of how client work is delivered")

    # --- size -------------------------------------------------------------
    employees = segment.get("employees")
    band = segment["employee_band"]
    if isinstance(employees, int) and employees > 0:
        scored_dimensions += 1
        floor = thresholds["min_employees"]
        soft_floor, _ = soft_band(floor)
        ceiling = thresholds.get("max_employees")
        _, soft_ceiling = soft_band(ceiling)
        if floor and employees < floor:
            penalty = policy["penalties"]["too_small"]
            near = soft_floor is not None and employees >= soft_floor
            if near:
                # Inside the tolerance band: smaller than the target, and not
                # a different kind of company. Half the penalty, and recorded
                # under a dimension that is not decisive, so this reaches a
                # human rather than a rejection.
                total -= penalty * 0.5
                negative.append(_signal(
                    "employee_count_soft", -penalty * 0.5,
                    f"{employees} people: just under the {int(floor)} this "
                    f"client targets, within the {int(SOFT_TOLERANCE * 100)}% "
                    "tolerance"))
            else:
                total -= penalty
                negative.append(_signal("employee_count", -penalty,
                                        f"{employees} people: below the "
                                        f"{int(floor)} needed to feel this "
                                        "problem"))
        elif ceiling and employees > ceiling:
            penalty = policy["penalties"]["unsuitable_enterprise"]
            near = soft_ceiling is not None and employees <= soft_ceiling
            total -= penalty * (0.5 if near else 1.0)
            negative.append(_signal(
                "unsuitable_enterprise", -penalty * (0.5 if near else 1.0),
                f"{employees} people ({band}): above the {int(ceiling)} this "
                "client sells to, so this is an enterprise motion rather than "
                "an outbound one"))
        elif employees >= 200:
            total += weights["employee_count"]
            positive.append(_signal("employee_count", weights["employee_count"],
                                    f"{employees} people ({band})"))
        elif employees >= 50:
            total += weights["employee_count"]
            positive.append(_signal("employee_count", weights["employee_count"],
                                    f"{employees} people ({band}): the size "
                                    "where resourcing stops fitting in a "
                                    "spreadsheet"))
        else:
            total += weights["employee_count"] * 0.6
            positive.append(_signal("employee_count",
                                    weights["employee_count"] * 0.6,
                                    f"{employees} people ({band})"))
    else:
        # Never treated as "probably fine". It is a gap, and it costs
        # confidence rather than score.
        missing.append("employee count unknown")

    # --- the need signals -------------------------------------------------
    for name in ("delivery_complexity", "resource_planning_need",
                 "profitability_need", "utilization_need", "time_tracking_need",
                 "operational_complexity"):
        found = segments._hits(text, NEED_SIGNALS[name])
        if found:
            total += weights[name]
            scored_dimensions += 1
            positive.append(_signal(name, weights[name],
                                    f"{len(found)} signal(s): "
                                    f"{', '.join(found[:3])}", found))
        else:
            missing.append(f"no evidence for {name.replace('_', ' ')}")

    # --- distributed teams -------------------------------------------------
    if segment.get("distributed"):
        total += weights["distributed_teams"]
        scored_dimensions += 1
        positive.append(_signal("distributed_teams", weights["distributed_teams"],
                                f"{segment.get('office_count')} offices"))
    elif segment.get("office_count"):
        scored_dimensions += 1
    else:
        missing.append("office footprint unknown")

    # --- geography ---------------------------------------------------------
    if policy["markets"]:
        region = segment.get("region")
        country = (segment.get("country") or "").title()
        if region in policy["markets"] or country in policy["markets"]:
            total += weights["geography"]
            scored_dimensions += 1
            positive.append(_signal("geography", weights["geography"],
                                    f"{region} is a market this client sells to"))
        elif segment.get("country"):
            penalty = policy["penalties"]["irrelevant_industry"] * 0.4
            total -= penalty
            scored_dimensions += 1
            negative.append(_signal("geography", -penalty,
                                    f"{country or region} is outside the "
                                    "client's stated markets"))
        else:
            missing.append("location unknown")
    elif not segment.get("country"):
        missing.append("location unknown")

    # --- service, not product ---------------------------------------------
    if segment["business_model"] == segments.AGENCY:
        total += weights["service_not_product"]
        scored_dimensions += 1
        positive.append(_signal("service_not_product",
                                weights["service_not_product"],
                                "sells delivery rather than licences"))
    elif segment["business_model"] in (segments.PRODUCT, segments.ECOMMERCE):
        penalty = policy["penalties"]["product_company"] * 0.5
        total -= penalty
        scored_dimensions += 1
        negative.append(_signal("service_not_product", -penalty,
                                f"business model looks "
                                f"{segment['business_model']}"))
    elif segment["business_model"] == segments.HYBRID:
        positive.append(_signal("service_not_product", 0,
                                "sells both services and a product: worth a "
                                "human read"))
        scored_dimensions += 1

    # Contradictions are scored before the verdict so a company whose evidence
    # disagrees with itself cannot arrive as a confident answer.
    components = confidence_components(rec, scored_dimensions, missing,
                                       segment, thresholds)
    if components["contradictions"]:
        penalty = policy["penalties"]["contradictory_evidence"]
        total -= penalty
        negative.append(_signal(
            "contradictory_evidence", -penalty,
            "; ".join(c["why"] for c in components["contradictions"])))

    bounded = max(0.0, min(100.0, total))
    confidence = _confidence(scored_dimensions, missing, segment, thresholds,
                             components)
    status, tier, why = _verdict(bounded, confidence, scored_dimensions,
                                 segment, negative, thresholds)

    result = {
        "record_id": rec.get("id"),
        "domain": rec.get("domain"),
        "icp_score": round(bounded, 1),
        "icp_raw_score": round(total, 1),
        "icp_tier": tier,
        "icp_status": status,
        "icp_confidence": confidence,
        "positive_signals": positive,
        "negative_signals": negative,
        "missing_evidence": missing,
        "classification_reasons": [why] + [s["why"] for s in negative[:2]]
        + [s["why"] for s in positive[:3]],
        "evidence_used": [item.get("evidence_id")
                          for item in (rec.get("research") or [])],
        "dimensions_scored": scored_dimensions,
        "confidence_components": components,
        "contradictions": components["contradictions"],
        "icp_grade": None,             # filled in below, needs the verdict
        "scoring_version": SCORING_VERSION,
        "scored_at": store.now(),
    }
    # How well it matches, said separately from whether we may spend on it.
    result["icp_grade"] = grade(result)
    return result


# ------------------------------------------------------------ contradictions
#
# Two stored facts that cannot both be true. The point is not to adjudicate
# them - we usually cannot - but to stop a verdict being reported as certain
# while the evidence under it disagrees with itself.

def _structured_text(rec):
    """What a provider states about the company, without its own marketing.

    Deliberately not `segments.text_of`, which folds in every research page.
    """
    facts = (rec or {}).get("company_facts") or {}
    parts = [str(facts.get("industry") or ""),
             str(facts.get("description") or ""),
             str(facts.get("tagline") or "")]
    parts.extend(str(s) for s in (facts.get("specialties") or []))
    parts.extend(str(s) for s in (facts.get("services") or []))
    return " ".join(parts).lower()


def contradictions(rec, segment):
    """Pairs of facts that cannot both hold. Reported, never resolved."""
    found = []
    facts = (rec or {}).get("company_facts") or {}

    # An agency that is also unmistakably a product business - judged on what
    # the company *is*, not on the vocabulary of its marketing site.
    #
    # `segment["non_icp_signals"]` is derived from `segments.text_of`, which
    # includes every retained research page. Once website copy is collected,
    # an ordinary agency saying "our platform", "pricing plans" or "free
    # trial" produces a contradiction about its own nature - and a
    # contradiction demotes confidence to LOW, which forces `review` whatever
    # the score is. Measured on fifty real companies: reading their sites took
    # this from one contradiction to nine, and pushed accounts that had just
    # earned a qualifying score back into the review queue. The research made
    # the picture worse by being read.
    #
    # So the signal has to come from the structured record - the industry and
    # specialties a provider states about the company - where "SaaS" is a
    # claim about the business rather than a word on a page it published.
    structured = _structured_text(rec)
    non_icp = [s for s in (segment.get("non_icp_signals") or [])
               if any(segments._hits(structured, [word])
                      for word in (s.get("matched") or []))]
    if segments.kind_of(segment.get("vertical")) == segments.AGENCY_KIND and non_icp:
        kinds = sorted({s["kind"] for s in non_icp})
        found.append({
            "kind": "vertical_vs_non_icp",
            "why": f"classified as {segment['vertical']} while its stated "
                   f"industry and specialties show {', '.join(kinds)} signals",
        })

    # A headcount that disagrees with the office footprint it claims.
    employees = facts.get("employees")
    offices = segment.get("office_count")
    if (isinstance(employees, int) and isinstance(offices, int)
            and offices > 1 and employees < offices):
        found.append({
            "kind": "size_vs_offices",
            "why": f"{employees} people across {offices} offices",
        })

    # More profiles than the company says it has people.
    #
    # This compared `employees` against `headcount_signal` in both directions
    # and called any factor of two a contradiction. They are not two claims
    # about the same quantity: `headcount_signal` is the number of LinkedIn
    # profiles `people-count` can see at the domain, and `employees` is a
    # stated headcount. A firm of seventy-eight with twenty-nine profiles has
    # ordinary LinkedIn adoption, not disagreeing sources - and calling it a
    # contradiction cost that company its confidence band, and with it a
    # qualifying score.
    #
    # The asymmetry is the whole signal. Fewer profiles than staff is normal.
    # Substantially *more* profiles than the company claims staff is not: it
    # says the domain is shared, the headcount is understated, or the profiles
    # belong to somebody else.
    profiles = facts.get("headcount_signal")
    if (isinstance(employees, int) and isinstance(profiles, int)
            and employees > 0 and profiles >= employees * 2):
        found.append({
            "kind": "headcount_sources_disagree",
            "why": f"{profiles} profiles at a company stating {employees} "
                   f"staff",
        })

    # Founded in the future, or before companies existed. A typo, but a typo
    # that feeds company_maturity.
    founded = facts.get("founded")
    if isinstance(founded, int) and (founded > 2026 or founded < 1800):
        found.append({
            "kind": "implausible_founding_year",
            "why": f"founded {founded}",
        })
    return found


# The five things that make evidence worth believing. Kept as an explicit list
# so the band below is arithmetic anybody can follow rather than a judgement.
CONFIDENCE_COMPONENTS = ("coverage", "source_diversity", "source_quality",
                         "recency", "consistency")


def confidence_components(rec, scored, missing, segment, thresholds):
    """Each component scored 0..1, with the sentence behind it."""
    research = [item for item in ((rec or {}).get("research") or [])
                if isinstance(item, dict)]

    total_dimensions = len(DIMENSIONS)
    coverage = min(1.0, scored / float(total_dimensions))

    providers = {item.get("provider") for item in research if item.get("provider")}
    types = {item.get("source_type") for item in research if item.get("source_type")}
    # One source saying five things is one source. Diversity counts distinct
    # places the picture came from, which is what makes it corroboration.
    distinct = len(providers | types)
    diversity = 0.0 if distinct <= 1 else min(1.0, (distinct - 1) / 3.0)
    if not research:
        # Company facts alone: a single provider, so no corroboration at all.
        diversity = 0.0

    strong = sum(1 for item in research
                 if item.get("quality") in (evidence.STRONG, evidence.MEDIUM_Q))
    quality_score = (min(1.0, strong / 3.0) if research else 0.0)

    dated = [item.get("freshness_score") for item in research
             if item.get("freshness_score") is not None]
    recency = (sum(dated) / len(dated)) if dated else 0.0

    clashes = contradictions(rec, segment)
    consistency = max(0.0, 1.0 - 0.5 * len(clashes))

    return {
        "coverage": {"score": round(coverage, 3),
                     "why": f"{scored} of {total_dimensions} dimensions scored, "
                            f"{len(missing)} gaps"},
        "source_diversity": {"score": round(diversity, 3),
                             "why": f"{distinct} distinct source(s)"},
        "source_quality": {"score": round(quality_score, 3),
                           "why": f"{strong} usable piece(s) of evidence"},
        "recency": {"score": round(recency, 3),
                    "why": (f"mean freshness {round(recency, 2)} over "
                            f"{len(dated)} dated fact(s)") if dated
                           else "nothing dated to judge recency by"},
        # Whether research ran at all, which is a different fact from research
        # having run and found nothing.
        "researched": bool(research),
        "consistency": {"score": round(consistency, 3),
                        "why": (f"{len(clashes)} contradiction(s): "
                                + "; ".join(c["why"] for c in clashes))
                               if clashes else "no contradictory evidence"},
        "contradictions": clashes,
    }


def _confidence(scored, missing, segment, thresholds, components=None):
    """How much of the picture we actually have.

    Separate from the score on purpose: a company can score badly on good
    evidence, which is a rejection, or badly on no evidence, which is a task.

    Coverage sets the ceiling and the other four can only lower it. That
    ordering is deliberate: no amount of corroboration makes up for not having
    scored the dimensions, and a contradiction has to be able to pull a
    well-covered company down into review rather than being averaged away by
    four components that happen to look fine.
    """
    if segment["vertical"] == segments.UNKNOWN:
        return LOW
    if scored < thresholds["min_dimensions_for_a_verdict"]:
        return LOW

    if len(missing) >= 6:
        band = MEDIUM if scored >= 6 else LOW
    elif scored >= 7 and len(missing) <= 3:
        band = HIGH
    else:
        band = MEDIUM

    if components:
        # A contradiction is never compatible with HIGH: the evidence disagrees
        # with itself, and that is precisely the case a human should see.
        if components["contradictions"]:
            band = MEDIUM if band == HIGH else LOW
        # Corroboration is only demanded of companies that *have* research.
        # Qualification runs before any research does - that is the whole point
        # of company-first - so requiring a second source here would put every
        # company in the batch at MEDIUM and make the tiers meaningless.
        # What is worth catching is the opposite case: research ran, came back
        # from a single source, and none of it was usable. That is thin
        # evidence dressed up as thorough.
        if (band == HIGH and components["researched"]
                and components["source_diversity"]["score"] <= 0
                and components["source_quality"]["score"] <= 0):
            band = MEDIUM
    return band


# Dimensions where a negative signal settles the question on its own.
#
# The distinction that matters: these are cases where the evidence we have is
# unambiguous, not cases where we happen to have a lot of it. Not knowing a
# SaaS company's headcount does not make "this is a product business" any less
# certain, so the decisive check has to run *before* the how-much-do-we-know
# gate - otherwise every obvious rejection arrives as `unknown` and a human is
# asked to re-read what the system already knew.
DECISIVE_NEGATIVES = ("agency_fit", "employee_count")
DECISIVE_WEIGHT = -20

# How far outside a soft numeric boundary a company may sit before the miss
# stops being a near miss.
#
# An ICP is a description of who a product is for, not a fence with a guard on
# it. `min_employees` was both: a company one person under it took the full
# `too_small` penalty on the `employee_count` dimension, which is decisive, and
# was rejected outright - while the company one person above it was scored
# normally. Nothing about a services business changes between nine people and
# ten, and a rule that says otherwise is describing its own arithmetic rather
# than the market.
#
# Inside the band the penalty still applies, because the company really is
# smaller than the target and that is worth points. What it stops doing is
# ending the conversation: the miss is recorded under a dimension that is not
# in DECISIVE_NEGATIVES, so the company reaches a human instead of a
# rejection. Outside the band it is decisive again - a two-person studio is
# not a near miss for a product sold to delivery teams.
SOFT_TOLERANCE = 0.30

# What the verdict says about fit, separately from what it says about
# certainty. `icp_status` answers "may we spend on this", and these answer
# "how well does this match", which is the question an operator reading a
# review queue is actually asking.
STRONG_ICP = "strong_icp"
GOOD_ICP = "good_icp"
BORDERLINE_ICP = "borderline_icp"
WEAK_ICP = "weak_icp"
CLEAR_NON_ICP = "clear_non_icp"
GRADES = (STRONG_ICP, GOOD_ICP, BORDERLINE_ICP, WEAK_ICP, CLEAR_NON_ICP)


def soft_band(boundary, tolerance=SOFT_TOLERANCE):
    """The range around a soft boundary where a miss is still a near miss."""
    if not boundary:
        return None, None
    return boundary * (1.0 - tolerance), boundary * (1.0 + tolerance)


def grade(verdict):
    """How well this company matches, on the evidence actually held.

    Deliberately not derived from `icp_status` alone: a company can be held at
    `review` for want of evidence and still be an obvious fit, and an operator
    triaging a queue needs to see the difference. Only `clear_non_icp` is a
    statement that the answer is no; `weak_icp` says the evidence points away
    and `borderline_icp` says it is close, and neither is a rejection.
    """
    if _decisive(verdict.get("negative_signals") or []):
        return CLEAR_NON_ICP
    tier = verdict.get("icp_tier")
    if tier == TIER_A:
        return STRONG_ICP
    if tier == TIER_B:
        return GOOD_ICP
    if tier == TIER_C:
        return BORDERLINE_ICP
    score = verdict.get("icp_score")
    if score is None:
        return WEAK_ICP
    return BORDERLINE_ICP if score >= 30 else WEAK_ICP


def _decisive(negative):
    return [s for s in negative
            if s["dimension"] in DECISIVE_NEGATIVES
            and s["weight"] <= DECISIVE_WEIGHT]


def _verdict(bounded, confidence, scored, segment, negative, thresholds):
    """Status and tier. Confidence gates the confident answers.

    Order is the whole design here: something we know for certain outranks how
    much else we happen to know.
    """
    decisive = _decisive(negative)
    if decisive:
        return (REJECTED, TIER_NOT_ICP, decisive[0]["why"])

    if segment["vertical"] == segments.UNKNOWN:
        return (UNKNOWN, TIER_REVIEW,
                "the vertical could not be determined, so no ICP judgement is "
                "made either way")
    if scored < thresholds["min_dimensions_for_a_verdict"]:
        return (UNKNOWN, TIER_REVIEW,
                f"only {scored} dimension(s) could be scored: not enough to "
                "call this either way")

    if bounded < thresholds["reject_below"]:
        if confidence == LOW:
            return (UNKNOWN, TIER_REVIEW,
                    f"scored {bounded:.0f} on thin evidence: unknown rather "
                    "than rejected")
        return (REJECTED, TIER_NOT_ICP,
                f"scored {bounded:.0f}, below the rejection threshold of "
                f"{int(thresholds['reject_below'])}")

    if confidence == LOW:
        return (REVIEW, TIER_REVIEW,
                f"scored {bounded:.0f} but confidence is low: a human should "
                "look before anything is spent")

    if bounded >= thresholds["tier_a"]:
        return (QUALIFIED, TIER_A,
                f"scored {bounded:.0f}: strong fit on {scored} dimensions")
    if bounded >= thresholds["tier_b"]:
        return (QUALIFIED, TIER_B, f"scored {bounded:.0f}: good fit")
    if bounded >= thresholds["tier_c"]:
        return (QUALIFIED, TIER_C, f"scored {bounded:.0f}: plausible fit")
    return (REVIEW, TIER_REVIEW,
            f"scored {bounded:.0f}: between the rejection and qualification "
            "thresholds")


def summarise(results):
    counts = {status: 0 for status in STATUSES}
    tiers = {tier: 0 for tier in TIERS}
    confidence = {level: 0 for level in CONFIDENCE}
    for result in results:
        counts[result["icp_status"]] = counts.get(result["icp_status"], 0) + 1
        tiers[result["icp_tier"]] = tiers.get(result["icp_tier"], 0) + 1
        confidence[result["icp_confidence"]] += 1
    scores = [r["icp_score"] for r in results]
    return {
        "companies": len(results),
        "status": counts,
        "tier": tiers,
        "confidence": confidence,
        "needs_manual_review": counts[REVIEW] + counts[UNKNOWN],
        "mean_score": round(sum(scores) / len(scores), 1) if scores else None,
    }


def describe(config=None):
    policy = settings(config)
    return {
        "dimensions": {name: policy["weights"][name] for name in DIMENSIONS},
        "penalties": policy["penalties"],
        "thresholds": policy["thresholds"],
        "markets": policy["markets"],
        "statuses": list(STATUSES),
        "tiers": list(TIERS),
        "confidence_levels": list(CONFIDENCE),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--describe", action="store_true")
    p.add_argument("--record")
    p.add_argument("--client")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    from . import clients
    config = {}
    if a.client:
        try:
            config = clients.load(a.client)
        except Exception:
            config = {}

    if a.describe or not a.record:
        print(json.dumps(describe(config), indent=2))
        return 0

    rec = store.get(a.record)
    if rec is None:
        print(f"REFUSED: no such record: {a.record}")
        return 2
    result = score(rec, config)
    if a.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"{result['domain']}: {result['icp_status'].upper()} "
          f"tier {result['icp_tier']} score {result['icp_score']} "
          f"confidence {result['icp_confidence']}")
    for reason in result["classification_reasons"]:
        print(f"    {reason}")
    for signal in result["negative_signals"]:
        print(f"    - {signal['dimension']}: {signal['why']}")
    for gap in result["missing_evidence"][:5]:
        print(f"    ? {gap}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
