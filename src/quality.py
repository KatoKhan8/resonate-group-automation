#!/usr/bin/env python3
"""How personalised this message actually is, broken into parts you can argue with.

A single number between 0 and 1 is worse than useless here. "Personalisation:
0.62" tells an operator nothing they can act on, and its main effect is to make
a weak message feel measured. So this module exposes five named components,
each computed from stored evidence by arithmetic anybody can follow, and then
derives a band from a rule written out in full below.

    company_specificity   is there a dated, attributable fact about THIS
                          company, beyond industry and headcount?
    person_specificity    is there anything about THIS person, beyond a title?
    evidence_recency      how old is the best thing we found?
    evidence_reliability  did it come from somewhere attributable?
    persona_relevance     does the evidence actually bear on this persona's
                          angle, or is it merely true?

The band is low / medium / high, the thresholds are constants at the top of the
file, and a campaign may set a minimum band below which contacts are HELD for a
human rather than sent.

No model is involved in any of this. It is all arithmetic over stored evidence,
so the same record scores the same way in any process, forever.
"""
import argparse
import json

from . import clients, evidence, personalization, store

LOW = "low"
MEDIUM = "medium"
HIGH = "high"
BANDS = (LOW, MEDIUM, HIGH)
BAND_ORDER = {LOW: 0, MEDIUM: 1, HIGH: 2}

COMPONENTS = ("company_specificity", "person_specificity", "evidence_recency",
              "evidence_reliability", "persona_relevance")

# ------------------------------------------------------------- the rule
#
# Written out rather than tuned: a threshold nobody can explain is a threshold
# nobody can defend to a client.
#
#   high    the best evidence is strong AND recent AND relevant, and there is
#           something specific about either the person or the company
#   medium  there is something specific and attributable, but it is older,
#           weaker, or only about the company
#   low     nothing specific: role and industry only, which is a template
#           wearing a first name
#
# A component at exactly 0 caps the band at low when it is company_specificity,
# because a message with nothing specific about the company is not personalised
# whatever else is true of it.

STRONG_ENOUGH = 0.7
PRESENT = 0.4

# ------------------------------------------------- source reliability
#
# How well a claim survives being questioned by the person who receives it.
# "You are hiring a delivery manager" is unarguable if their own careers page
# says so; the same claim sourced from an aggregator is a claim about a claim.
#
# Two vocabularies reach this table and both are real:
#
#   the crawl vocabulary   `src/providers/apify.py` stamps every crawled page
#                          with source_type "apify" and keeps the page kind in
#                          `field`, one of apify.SOURCES. "apify" says how we
#                          fetched it, not how good it is, so the page kind is
#                          what actually decides.
#
#   the descriptive        fixtures, the demo dataset and any manually entered
#   vocabulary             evidence name the kind directly: careers_page,
#                          company_announcement, public_post. These are the
#                          same concepts under different names, so they are
#                          aliased onto the canonical kinds rather than scored
#                          twice and allowed to drift apart.
#
# The canonical kinds are grouped by who is making the claim and whether it is
# tied to a moment, because that is what decides whether it can be argued with.

# First-party and dated: the company said this, publicly, on a day.
CANONICAL_RELIABILITY = {
    "careers": 0.95,               # they are hiring; the page is the proof
    "company_announcement": 0.95,  # they announced it themselves
    "press_release": 0.95,
    "news": 0.90,                  # dated, and usually attributed
    "blog": 0.90,                  # first-party, dated, and specific

    # First-party and standing: true, but every competitor could say it.
    "about": 0.80,
    "team": 0.80,
    "company_website": 0.75,

    # Attributable to the person rather than to the company.
    "public_post": 0.85,
    "interview": 0.85,
    "conference": 0.80,

    # Structured provider data. Paid for and dependable, and never specific
    # enough on its own to make a message feel written for one company.
    "provider_structured": 0.70,
    "contactout": 0.70,
    "aiark": 0.60,
}

# The descriptive names, mapped onto the canonical kind they describe. One
# mapping, so adding a name cannot quietly create a second scale.
SOURCE_ALIASES = {
    "careers_page": "careers",
    "jobs_page": "careers",
    "company_blog": "blog",
    "news_article": "news",
    "press": "press_release",
    "about_page": "about",
    "team_page": "team",
    "homepage": "company_website",
    "website": "company_website",
    "case_study": "blog",
    "public_profile": "public_post",
    "public_article": "public_post",
    "podcast": "interview",
    "conference_talk": "conference",
    "structured": "provider_structured",
}

# Everything a crawl can come back as. Kept as an explicit alias set rather
# than assumed equal to apify.SOURCES, so a new crawl source has to be given a
# reliability deliberately instead of inheriting one.
CRAWL_FIELDS = ("company_website", "about", "team", "careers", "blog", "news")

# What a source nobody has classified is worth. Deliberately below PRESENT, so
# unknown-sourced evidence cannot reach even the middle band on reliability:
# an unrecognised source is a reason to look, not a reason to send.
DEFAULT_RELIABILITY = 0.30

# The scale as one flat lookup, for callers that just want the number.
SOURCE_RELIABILITY = dict(CANONICAL_RELIABILITY)
SOURCE_RELIABILITY.update({alias: CANONICAL_RELIABILITY[kind]
                           for alias, kind in SOURCE_ALIASES.items()
                           if kind in CANONICAL_RELIABILITY})

# What each extra corroborating source adds, and the floor a source must reach
# before it corroborates anything at all. Five unrecognised pages saying the
# same thing is five unrecognised pages, not evidence.
CORROBORATION_BONUS = 0.05
CORROBORATION_FLOOR = 0.40


UNKNOWN_SOURCE = "unknown"


def canonical_source(item):
    """The canonical kind for one piece of evidence.

    A crawl resolves by the page it came off; a descriptive name resolves
    through the alias table; anything else stays unknown, by name, so the
    caller can say so rather than guess.
    """
    source = str((item or {}).get("source_type") or "").strip().lower()
    if source == "apify":
        field = str((item or {}).get("field") or "company_website").lower()
        return field if field in CRAWL_FIELDS else UNKNOWN_SOURCE
    if source in CANONICAL_RELIABILITY:
        return source
    if source in SOURCE_ALIASES:
        return SOURCE_ALIASES[source]
    return UNKNOWN_SOURCE


def reliability_of(item):
    """One piece of evidence, scored by where it came from."""
    return CANONICAL_RELIABILITY.get(canonical_source(item),
                                     DEFAULT_RELIABILITY)


# Kept under the old private name too: it is called from tests and reads
# better at the call site than the public one.
_reliability_of = reliability_of


def known_sources():
    """Every source type this system scores, canonical names and aliases."""
    return tuple(sorted(set(CANONICAL_RELIABILITY) | set(SOURCE_ALIASES)
                        | {"apify"}))


DEFAULTS = {"minimum_band": LOW, "hold_below_minimum": True}


def settings(config):
    """The client's quality policy. An unknown band name is ignored, not obeyed."""
    block = ((config or {}).get("personalization") or {}).get("quality") or {}
    merged = dict(DEFAULTS)
    band = str(block.get("minimum_band", DEFAULTS["minimum_band"])).strip().lower()
    if band in BANDS:
        merged["minimum_band"] = band
    merged["hold_below_minimum"] = block.get(
        "hold_below_minimum", DEFAULTS["hold_below_minimum"]) is not False
    return merged


# --------------------------------------------------------- the components

def _selected(rec, contact, today=None):
    """The evidence this contact's draft was written from, re-aged.

    Read by evidence id rather than through `personalization.stored`, so it
    needs the same re-ageing: the band this module reports is about the
    message that would go out now, and `evidence_recency` reading a bucket
    frozen weeks ago reports the recency of a decision rather than of a
    fact.
    """
    decision = contact.get("personalization") or {}
    ids = set(decision.get("selected_evidence_ids") or [])
    return [evidence.recheck(item, today)
            for item in (rec.get("research") or [])
            if item.get("evidence_id") in ids]


def company_specificity(rec, chosen):
    """Industry and headcount are not specificity. A dated fact is."""
    company_facts = [i for i in chosen if i.get("subject") == evidence.COMPANY]
    if not company_facts:
        # A hook written from structured data is something, but it is the
        # weakest something: every competitor could write the same sentence.
        return 0.25 if rec.get("hook") else 0.0
    best = max(company_facts, key=lambda i: i.get("relevance_score") or 0)
    dated = bool(best.get("published_at"))
    attributable = bool(best.get("source_url"))
    # Attributability outweighs the date deliberately. A fact we cannot point
    # at is one we cannot defend when the recipient asks where we got it, and
    # the weights are set so that missing it lands below STRONG_ENOUGH on its
    # own - being dated is not a substitute for being checkable.
    score = 0.45
    if dated:
        score += 0.20
    if attributable:
        score += 0.35
    return round(score, 3)


def person_specificity(rec, contact, chosen):
    """A title is a category. A fact about this person is specificity."""
    person_facts = [i for i in chosen if i.get("subject") == evidence.PERSON]
    if person_facts:
        best = max(person_facts, key=lambda i: i.get("relevance_score") or 0)
        # Same rule as the company side: unattributable stays below the top
        # threshold rather than sitting exactly on it.
        return round(0.65 + (0.35 if best.get("source_url") else 0.0), 3)
    # Role data is real, and it is the floor rather than nothing. Saying so
    # keeps anyone from filling the gap with an invented LinkedIn post.
    if contact.get("title"):
        return 0.3
    return 0.0


def evidence_recency(chosen):
    if not chosen:
        return 0.0
    buckets = [i.get("freshness_bucket") for i in chosen]
    if evidence.HIGH in buckets:
        return 1.0
    if evidence.MEDIUM in buckets:
        return 0.7
    if evidence.LOW in buckets:
        return 0.4
    if evidence.BACKGROUND in buckets:
        return 0.2
    return 0.0


def evidence_reliability(chosen):
    """The best source carries the message; corroboration adds a little.

    Only sources that clear CORROBORATION_FLOOR corroborate. Otherwise
    quantity manufactures reliability: six unrecognised pages would score
    0.30 + 5 x 0.05 = 0.55 and cross into the middle band without a single
    identifiable source behind them.
    """
    if not chosen:
        return 0.0
    scores = [reliability_of(item) for item in chosen]
    best = max(scores)
    corroborating = sum(1 for score in scores
                        if score >= CORROBORATION_FLOOR) - 1
    if best < CORROBORATION_FLOOR:
        return round(best, 3)
    return round(min(1.0, best + CORROBORATION_BONUS * max(0, corroborating)),
                 3)


def persona_relevance(chosen):
    """True is not the same as relevant. This is the difference."""
    if not chosen:
        return 0.0
    return round(max(i.get("relevance_score") or 0.0 for i in chosen), 3)


def components_for(rec, contact, config=None):
    chosen = _selected(rec, contact)
    return {
        "company_specificity": company_specificity(rec, chosen),
        "person_specificity": person_specificity(rec, contact, chosen),
        "evidence_recency": evidence_recency(chosen),
        "evidence_reliability": evidence_reliability(chosen),
        "persona_relevance": persona_relevance(chosen),
    }


def band_for(components):
    """The documented rule, applied. No weights, no averaging, no mystery."""
    company = components["company_specificity"]
    person = components["person_specificity"]
    recency = components["evidence_recency"]
    reliability = components["evidence_reliability"]
    relevance = components["persona_relevance"]

    if company <= 0.0:
        return LOW
    specific = max(company, person)
    if (specific >= STRONG_ENOUGH and recency >= STRONG_ENOUGH
            and relevance >= STRONG_ENOUGH and reliability >= STRONG_ENOUGH):
        return HIGH
    if specific >= PRESENT and reliability >= PRESENT and relevance >= PRESENT:
        return MEDIUM
    return LOW


def why(components, band):
    """The sentence an operator reads next to the band."""
    if band == HIGH:
        return ("a specific, recent, attributable fact that bears on this "
                "persona")
    weakest = min(components, key=lambda name: components[name])
    if components["company_specificity"] <= 0.0:
        return ("nothing specific about this company: the message would read "
                "as a template with a first name in it")
    if band == MEDIUM:
        return f"specific enough to send, held back by {weakest}"
    return f"not specific enough: {weakest} is {components[weakest]}"


def assess(rec, contact, config=None):
    """The whole assessment for one contact, including the contradictions."""
    policy = settings(config)
    components = components_for(rec, contact, config)
    band = band_for(components)
    decision = contact.get("personalization") or {}
    chosen = _selected(rec, contact)

    warnings = []
    # A stored decision claiming quality with nothing selected is the one
    # inconsistency worth shouting about: it means a page would show a
    # confident label over an empty evidence list.
    if decision.get("quality") in evidence.USABLE and not chosen:
        warnings.append(
            f"the stored decision claims {decision['quality']} personalisation "
            "but selected no evidence; the claim is not counted here")
    dangling = [eid for eid in (decision.get("selected_evidence_ids") or [])
                if eid not in {i.get("evidence_id")
                               for i in (rec.get("research") or [])}]
    if dangling:
        warnings.append(f"{len(dangling)} selected evidence id(s) no longer "
                        "exist on the record")

    minimum = policy["minimum_band"]
    meets = BAND_ORDER[band] >= BAND_ORDER[minimum]
    return {
        "record_id": rec.get("id"),
        "contact_key": contact.get("key"),
        "components": components,
        "band": band,
        "why": why(components, band),
        "evidence_count": len(chosen),
        "minimum_band": minimum,
        "meets_minimum": meets,
        "held": bool(not meets and policy["hold_below_minimum"]),
        "warnings": warnings,
    }


def for_record(rec, config=None, selected_only=True):
    contacts = (personalization.selected_contacts(rec, config) if selected_only
                else (rec.get("contacts") or []))
    return [assess(rec, contact, config) for contact in contacts]


def distribution(recs, config=None, selected_only=True):
    """The band spread across a batch, plus what is held and why."""
    counts = {band: 0 for band in BANDS}
    held, warnings = 0, 0
    weakest = {name: 0 for name in COMPONENTS}
    total = 0
    for rec in recs or []:
        for result in for_record(rec, config, selected_only):
            total += 1
            counts[result["band"]] += 1
            held += int(result["held"])
            warnings += len(result["warnings"])
            name = min(result["components"], key=lambda n: result["components"][n])
            weakest[name] += 1
    return {
        "contacts": total,
        "bands": counts,
        "held": held,
        "warnings": warnings,
        "weakest_component": weakest,
        "share": {band: (round(counts[band] / total, 3) if total else None)
                  for band in BANDS},
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client")
    p.add_argument("--record")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    recs = store.load()
    if a.record:
        recs = [r for r in recs if r.get("id") == a.record]
    if a.client:
        recs = [r for r in recs if r.get("client") == a.client]
    config = {}
    try:
        config = clients.load(a.client or (recs[0].get("client") if recs else None))
    except Exception:
        config = {}

    if a.record:
        for result in for_record(recs[0] if recs else {}, config):
            if a.json:
                print(json.dumps(result, indent=2))
                continue
            print(f"{result['contact_key']}: {result['band'].upper()} "
                  f"— {result['why']}")
            for name in COMPONENTS:
                print(f"    {name:<22} {result['components'][name]}")
            for warning in result["warnings"]:
                print(f"    WARNING: {warning}")
        return 0

    result = distribution(recs, config)
    print(json.dumps(result, indent=2) if a.json else
          "\n".join([f"  contacts {result['contacts']}"]
                    + [f"  {b:<8} {result['bands'][b]}" for b in BANDS]
                    + [f"  held     {result['held']}"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
