#!/usr/bin/env python3
"""Which approach fits this account, and what it rests on.

## What was missing

Two template systems already exist and neither is this one.
`cadencegraph.TEMPLATES` holds cadence *shapes* - which steps, which
channels, where the branches are. `cadence.TEMPLATES` holds message
*copy*. Between them sits the decision nobody had written down: given a
50-person German agency that is hiring, which shape, which angle, which
proof, which ask?

A playbook is that bundle. It is the answer to "how do we approach this
kind of account", named once so it can be argued with, rather than
re-derived by whoever builds the next campaign.

## It recommends; it does not assign

Nothing here selects a cadence, writes copy, changes a campaign or sends
anything. `recommend()` returns ranked candidates with the reason for each
and the conditions each one failed, and a person or a later step decides.

That restraint is the same one `priority` and `gtm` are built on, for the
same reason: a system that quietly picks the approach is a system whose
choices nobody reviews. The recommendation is an argument, and an argument
has to be legible to be refused.

## "Nothing here fits" is an answer

`recommend()` is allowed to return nothing above the confidence floor, and
says so. The alternative - always naming a best match - turns a weak fit
into a recommendation, which is how a generic sequence ends up being sent
to an account that deserved a different one. `strategy` already refuses to
promote an unsupported pain to a brief; this refuses to promote a poor
match to a plan.

## A playbook licenses nothing

Choosing the "hiring surge" playbook does **not** permit a message to
mention hiring. It selects an angle - operational scalability - which is a
different thing from a claim. `outreachclaims` remains the only authority
on what a message may assert, and no claim type covers an observation.
See ACCOUNT-INTELLIGENCE.md.
"""
from . import cadencegraph, signals as signal_module, strategy

# ------------------------------------------------------------------ matching
#
# A condition is a question asked of one account, answered from canonical
# state. Every one of them can come back "unknown", and unknown is never
# treated as a match - a playbook chosen because a field was empty is a
# playbook chosen for no reason.

ANY = "any"

MATCH_EMPLOYEES = "employee_band"
MATCH_VERTICAL = "vertical"
MATCH_COUNTRY = "country"
MATCH_SIGNAL = "signal"
MATCH_PERSONA = "persona"
MATCH_TIER = "priority_tier"
MATCH_ENGAGED = "engaged"

CONDITION_LABEL = {
    MATCH_EMPLOYEES: "company size",
    MATCH_VERTICAL: "vertical",
    MATCH_COUNTRY: "country",
    MATCH_SIGNAL: "a live signal",
    MATCH_PERSONA: "the right persona, reachable",
    MATCH_TIER: "priority tier",
    MATCH_ENGAGED: "prior engagement",
}

# How much of a playbook's conditions must hold before it is worth
# offering. Below this it is not a recommendation, it is a coincidence.
CONFIDENCE_FLOOR = 0.6


def _band(rec):
    return ((rec.get("qualification") or {}).get("segment") or {}).get(
        "employee_band")


def _vertical(rec):
    return ((rec.get("qualification") or {}).get("segment") or {}).get(
        "vertical")


def _country(rec):
    return ((rec.get("qualification") or {}).get("segment") or {}).get(
        "country")


# ------------------------------------------------------------- the library
#
# Deliberately few. A library of thirty playbooks is a library nobody has
# read, and the useful question is not "which of thirty" but "is this one
# of the handful of situations we know how to handle".
#
# `proof` and `cta` are strategy, not copy: they say what kind of evidence
# and what kind of ask, and the generator still writes the sentence.

LIBRARY = (
    {
        "id": "operational_scale",
        "name": "Growing past their process",
        "when": "The company is adding people faster than its operating "
                "model was built for",
        "cadence": "standard",
        "personas": ("champion", "economic_buyer"),
        "lead_pain": strategy.RESOURCE_PLANNING,
        "second_pain": strategy.CAPACITY_FORECASTING,
        "proof": "a team that grew through the same band",
        "cta": "a question about how they plan capacity today",
        "requires": {
            MATCH_SIGNAL: (signal_module.HIRING_SURGE,
                           signal_module.HEADCOUNT_GROWTH,
                           signal_module.JOB_POSTING),
        },
        "prefers": {MATCH_EMPLOYEES: ("11-50", "51-200")},
    },
    {
        "id": "margin_visibility",
        "name": "Delivering well, measuring late",
        "when": "An established services business where the numbers arrive "
                "after the month they describe",
        "cadence": "standard",
        "personas": ("economic_buyer", "champion"),
        "lead_pain": strategy.PROJECT_MARGIN,
        "second_pain": strategy.PROFITABILITY_REPORTING,
        "proof": "a comparable firm's before and after on margin visibility",
        "cta": "an offer to show what the view looks like",
        "requires": {MATCH_VERTICAL: ("professional_services", "agency")},
        "prefers": {MATCH_EMPLOYEES: ("51-200", "201-500")},
    },
    {
        "id": "new_leadership",
        "name": "A new person with a mandate",
        "when": "Somebody has just taken a role that owns this problem, and "
                "is deciding what to change",
        "cadence": "linkedin_heavy",
        "personas": ("economic_buyer",),
        "lead_pain": strategy.DELIVERY_VISIBILITY,
        "second_pain": strategy.UTILIZATION,
        "proof": "what a peer changed in their first quarter",
        "cta": "a low-friction offer to compare notes",
        "requires": {
            MATCH_SIGNAL: (signal_module.NEW_EXECUTIVE,
                           signal_module.PROMOTION,
                           signal_module.NEW_ROLE),
        },
        "prefers": {},
    },
    {
        "id": "multi_dm_account",
        "name": "Worth more than one conversation",
        "when": "A high-priority account where the decision needs more than "
                "one person",
        "cadence": "account_multi_dm",
        "personas": ("champion", "economic_buyer", "influencer"),
        "lead_pain": strategy.DELIVERY_VISIBILITY,
        "second_pain": strategy.PROJECT_MARGIN,
        "proof": "a case that names both the operational and the financial "
                "outcome",
        "cta": "a request for the right person rather than a meeting",
        "requires": {MATCH_TIER: ("high",), MATCH_PERSONA: ANY},
        "prefers": {},
    },
    {
        "id": "back_to_the_account",
        "name": "Coming back to a warm account",
        "when": "We have been here before and it did not end badly",
        "cadence": "reengagement",
        "personas": ("champion",),
        "lead_pain": strategy.CAPACITY_FORECASTING,
        "second_pain": strategy.TOOL_SPRAWL,
        "proof": "what has changed since we last spoke",
        "cta": "an explicit acknowledgement of the earlier conversation",
        "requires": {MATCH_ENGAGED: ANY},
        "prefers": {},
    },
    {
        "id": "segment_default",
        "name": "The segment approach",
        "when": "Nothing specific is known about this account beyond the "
                "segment it belongs to",
        "cadence": "standard",
        "personas": ("champion",),
        "lead_pain": strategy.UTILIZATION,
        "second_pain": strategy.TIME_TRACKING,
        "proof": "a comparable company in the same vertical and size band",
        "cta": "a question rather than a meeting request",
        # Deliberately unconditional. It is the honest fallback, and it is
        # ranked last because it earns nothing from the account itself.
        "requires": {},
        "prefers": {},
    },
)

BY_ID = {play["id"]: play for play in LIBRARY}


def _answer(condition, wanted, rec, assessment):
    """Does this account satisfy one condition? Returns (bool, why, known).

    `known` is the third state, and the reason this returns three things
    rather than two: an account whose employee band was never established
    has not failed the size condition, it has not been asked. Treating the
    two the same is how "we know nothing about this company" turns into
    "this company is a poor fit".
    """
    if condition == MATCH_SIGNAL:
        live = [s for s in (assessment or {}).get("signals") or []
                if s["freshness"] != signal_module.STALE
                and s["scope"] != signal_module.ENGAGEMENT]
        hit = [s for s in live if wanted is ANY or s["type"] in wanted]
        if hit:
            return True, f"{hit[0]['label'].lower()}: {hit[0]['evidence']}", True
        return False, "nothing observed at this company", bool(live)

    if condition == MATCH_TIER:
        tier = (assessment or {}).get("tier")
        if tier is None:
            return False, "not scored", False
        return (wanted is ANY or tier in wanted), f"{tier} priority", True

    if condition == MATCH_PERSONA:
        selected = [c for c in rec.get("contacts") or [] if c.get("selected")]
        if not selected:
            return False, "no decision maker selected", True
        names = {c.get("persona") for c in selected if c.get("persona")}
        if wanted is ANY:
            return True, f"{len(selected)} decision maker(s) selected", True
        overlap = names & set(wanted)
        if overlap:
            return True, f"{', '.join(sorted(overlap))} selected", True
        return False, f"none of {', '.join(wanted)} selected", True

    if condition == MATCH_ENGAGED:
        engaged = [s for s in (assessment or {}).get("signals") or []
                   if s["scope"] == signal_module.ENGAGEMENT]
        if engaged:
            return True, engaged[0]["evidence"], True
        return False, "no prior contact", True

    value = {MATCH_EMPLOYEES: _band, MATCH_VERTICAL: _vertical,
             MATCH_COUNTRY: _country}[condition](rec)
    if not value:
        # Unknown, not absent. Never a match, and never counted as a miss
        # either - see `recommend`.
        return False, f"{CONDITION_LABEL[condition]} not established", False
    if wanted is ANY or value in wanted:
        return True, f"{value}", True
    return False, f"{value}, not {' or '.join(wanted)}", True


def evaluate(play, rec, assessment=None):
    """One playbook against one account, with every condition answered."""
    met, missed, unknown = [], [], []
    for condition, wanted in (play.get("requires") or {}).items():
        ok, why, known = _answer(condition, wanted, rec, assessment)
        entry = {"condition": condition,
                 "label": CONDITION_LABEL[condition], "why": why,
                 "required": True}
        (met if ok else unknown if not known else missed).append(entry)
    for condition, wanted in (play.get("prefers") or {}).items():
        ok, why, known = _answer(condition, wanted, rec, assessment)
        entry = {"condition": condition,
                 "label": CONDITION_LABEL[condition], "why": why,
                 "required": False}
        (met if ok else unknown if not known else missed).append(entry)

    required = len(play.get("requires") or {})
    required_met = len([e for e in met if e["required"]])
    # A required condition that could not be answered is not a pass. The
    # score counts what is known to hold, over everything that was asked.
    asked = len(met) + len(missed) + len(unknown)
    score = (len(met) / asked) if asked else 1.0

    return {
        "playbook": play["id"],
        "name": play["name"],
        "when": play["when"],
        "cadence": play["cadence"],
        "lead_pain": play["lead_pain"],
        "lead_pain_words": strategy.PAIN_WORDS.get(play["lead_pain"]),
        "second_pain": play["second_pain"],
        "proof": play["proof"],
        "cta": play["cta"],
        "personas": list(play["personas"]),
        "met": met,
        "missed": missed,
        "unknown": unknown,
        "score": round(score, 2),
        # Every required condition holds. The score can still be low if the
        # preferences did not, which is a weaker recommendation rather than
        # a wrong one.
        "eligible": required_met == required,
    }


def recommend(rec, assessment=None, config=None, limit=3):
    """Ranked playbooks for one account, and an honest "none of these".

    The fallback is offered separately rather than mixed into the ranking,
    because "the segment approach, because we know nothing else" and "the
    new-leadership approach, because their COO started in August" are
    different kinds of recommendation and a list that ranks them together
    hides which one is which.
    """
    scored = [evaluate(play, rec, assessment) for play in LIBRARY
              if play["id"] != "segment_default"]
    fits = [row for row in scored
            if row["eligible"] and row["score"] >= CONFIDENCE_FLOOR]
    fits.sort(key=lambda r: (-r["score"], r["playbook"]))

    fallback = evaluate(BY_ID["segment_default"], rec, assessment)
    return {
        "record_id": rec.get("id"),
        "company": rec.get("company"),
        "recommended": fits[:limit],
        "fallback": fallback,
        # Said plainly rather than left to be inferred from an empty list.
        "why": (f"{len(fits)} playbook(s) fit this account"
                if fits else
                "Nothing specific is known about this account that would "
                "single out an approach, so the segment default is the "
                "honest choice"),
        "considered": len(scored),
        "floor": CONFIDENCE_FLOOR,
        # A playbook selects an angle. It licenses no claim, and the
        # distinction matters most exactly here, where a hiring signal has
        # just chosen an approach.
        "note": ("A playbook chooses how to approach an account. It does "
                 "not license a message to mention what chose it: what may "
                 "be said is decided by the claim rules."),
    }


def describe():
    """The library, for a screen or the CLI. No account involved."""
    return [{"id": p["id"], "name": p["name"], "when": p["when"],
             "cadence": p["cadence"],
             "cadence_name": (cadencegraph.TEMPLATES.get(p["cadence"]) or {})
             .get("name") or p["cadence"],
             "lead_pain": p["lead_pain"],
             "lead_pain_words": strategy.PAIN_WORDS.get(p["lead_pain"]),
             "proof": p["proof"], "cta": p["cta"],
             "personas": list(p["personas"]),
             "requires": [CONDITION_LABEL[c]
                          for c in (p.get("requires") or {})]}
            for p in LIBRARY]
