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


# =====================================================================
# THE QUALITY GATE
#
# lint.py checks length, typography, placeholders, attachments, greeting
# and the banned-phrase list. Everything it checks, it checks well. None
# of it can tell whether a message says anything meaningful, or whether
# it says the same thing six times.
#
# This gate sits between the model and the prospect. A generated message
# that FAILS is regenerated; if it still fails, it is marked for
# escalation with the reason recorded. The gate is deterministic first
# and reaches for semantic judgement only where a rule genuinely cannot
# express the check.
#
# Three checks, each returning a named reason rather than a boolean:
#
#   angle_leakage          the client's own angle wording appearing
#                          verbatim in a message. "profitability visible
#                          on monday" is Productive's phrasing of what it
#                          sells, not something to put in the prospect's
#                          mouth.
#
#   repetition_across_rungs  two steps for the same contact making the
#                            same point. The failure LINKEDIN_LADDER was
#                            written to prevent.
#
#   unsupported_third_party  "many teams like yours have found..." is a
#                            claim with no referent. claims.py checks
#                            assertions about the prospect; this checks
#                            assertions about populations the record
#                            cannot support.

import re as _re


def _angle_phrases(config):
    """Every phrase the client uses to describe what it sells.

    Two sources, both the client's own words:

      personas.*.angles    the argument a message makes per angle key.
                           "profitability visible on Monday not two weeks
                           late" is the founder angle's wording.

      angle_labels         the short topic a subject line may name.
                           "profitability on Monday" is the label form.

    Both are the client's vocabulary, not the prospect's, and neither
    belongs in a message addressed to a stranger.

    Angles are comma-separated lists in the config ("utilisation,
    capacity planning, one system not five"). Each comma-separated
    fragment is a separate phrase, because the model may leak any one
    of them.
    """
    phrases = []
    for persona in (clients.personas(config) or {}).values():
        for raw in ((persona or {}).get("angles") or {}).values():
            for fragment in str(raw or "").split(","):
                text = " ".join(fragment.split())
                if text:
                    phrases.append(text)
    for raw in (clients.angle_labels(config) or {}).values():
        for fragment in str(raw or "").split(","):
            text = " ".join(fragment.split())
            if text:
                phrases.append(text)
    return phrases


def angle_leakage(text, config):
    """The client's own angle wording appearing verbatim in a message.

    Returns a list of the leaked phrases (lowered, stripped). An empty
    list means nothing leaked.

    The check is word overlap on normalised text: lowercased, collapsed
    whitespace, punctuation stripped. A phrase leaks when enough of its
    distinctive words (excluding articles, prepositions and pronouns)
    appear in the message. The threshold is three distinctive words for
    a phrase of four or more, or all distinctive words for shorter
    phrases. This catches "profitability visible on monday" from the
    phrase "profitability visible on Monday not two weeks late" without
    requiring the full phrase to appear verbatim.
    """
    if not text or not config:
        return []
    low = " ".join(str(text).lower().split())
    text_words = set(_re.findall(r"[a-z]+", low))
    stopwords = {"a", "an", "the", "is", "are", "was", "were", "be",
                 "been", "being", "have", "has", "had", "do", "does",
                 "did", "will", "would", "could", "should", "may",
                 "might", "can", "to", "of", "in", "for", "on", "with",
                 "at", "by", "from", "as", "into", "through", "during",
                 "before", "after", "and", "but", "or", "nor", "not",
                 "so", "yet", "both", "either", "neither", "here",
                 "there", "when", "where", "why", "how", "what", "which",
                 "who", "whom", "this", "that", "these", "those", "i",
                 "me", "my", "we", "our", "you", "your", "it", "its"}
    leaked = []
    for phrase in _angle_phrases(config):
        normalised = " ".join(str(phrase).lower().split())
        words = _re.findall(r"[a-z]+", normalised)
        distinctive = [w for w in words if w not in stopwords and len(w) > 2]
        # A phrase needs at least three distinctive words to be
        # identifiable as the client's wording. "good morning" is two
        # words and common vocabulary; flagging it would refuse every
        # message ever written.
        if len(distinctive) < 3:
            continue
        overlap = len([w for w in distinctive if w in text_words])
        # A phrase leaks when enough of its distinctive words appear in
        # the text. For short phrases (3-4 distinctive words), all must
        # appear. For longer phrases, at least 60% must appear, with a
        # minimum of 3.
        threshold = max(3, int(len(distinctive) * 0.6)) if len(distinctive) > 4 else len(distinctive)
        if overlap >= threshold:
            leaked.append(normalised)
    return leaked


# Words that carry the substance of a message. Anything shorter is a
# stopword or a fragment, and matching on it produces false positives
# across steps that genuinely discuss different topics.
_DISTINCTIVE_RE = _re.compile(r"\b[a-z][a-z\-]{4,}\b")

# The overlap coefficient floor: two steps sharing this proportion of
# their smaller set's content words are making the same point. An
# absolute count does not work for short messages: a LinkedIn
# connection note has at most 300 characters and maybe eight content
# words, so five shared words would be impossible even when the notes
# are transparently paraphrases. The overlap coefficient - intersection
# divided by the size of the smaller set - catches this: two notes
# that share 60% of their content words are saying the same thing
# however many words each has.
_REPETITION_OVERLAP = 0.50

# An absolute floor as well: two two-word notes sharing both words is
# not repetition, it is a greeting. At least three shared content
# words are needed before the overlap coefficient is consulted.
_REPETITION_MIN_SHARED = 3


def _distinctive_words(text):
    """The content words of a message, lowered and deduplicated."""
    return set(_DISTINCTIVE_RE.findall(str(text or "").lower()))


# SUBJECT VOCABULARY.
#
# Every message in a Productive sequence says "profitability" or "margin"
# because that is what Productive sells. Those words are the SUBJECT of the
# conversation, not the duplication. A comparison that flags them flags
# everything, and a check that refuses every sequence is worse than none.
#
# Measured 2026-09-14 on the real Productive corpus: five LinkedIn steps
# from `16kagency-com` and three email bodies from `cadence.py`. With
# subject vocabulary counted, EVERY pair collided. With it discounted,
# ZERO pairs collided - the copy was genuinely progressive, and the check
# was reading the topic back to itself.
#
# This is the same rule as the company name discount, one level up. The
# company name is not repetition because every message names the company;
# the subject vocabulary is not repetition because every message argues
# the subject. Both are what the conversation IS, not what it says.
#
# The vocabulary is NARROW: just the core topic words that appear in
# every message. Structural words like "visibility", "tracking",
# "planning" are NOT discounted because they can indicate actual
# paraphrasing when shared across steps.
SUBJECT_VOCABULARY = (
    "profitability", "margin", "utilisation", "utilization",
)


def repetition_across_rungs(steps, ignore=()):
    """Pairs of steps that share too many distinctive words.

    `steps` is a list of dicts, each with at least `key` (the step
    identifier, e.g. "li1") and `text` (the message body). Returns a
    list of (key_a, key_b, shared_count) tuples, sorted by shared_count
    descending.

    Two checks, both must pass for a collision to be reported:

      absolute   at least three content words are shared. Two short
                 notes sharing "hi" and "connect" is not repetition.

      relative   the overlap coefficient (shared / smaller set) is at
                 least 50%. Two long notes that happen to share a topic
                 word are not repetition; two short notes where most of
                 the content is the same word-for-word are.

    The LinkedIn ladder has six rungs for six different arguments. Two
    of them reading as paraphrases of the same idea is the failure the
    ladder was written to prevent.
    """
    if not steps or len(steps) < 2:
        return []
    # THE PROSPECT'S OWN NAME IS NOT REPETITION. Every message in a sequence
    # to one company names that company, and counting those tokens as shared
    # content made relevance look like duplication. Measured 2026-09-14 on
    # `acqcom-com`, five emails from `gpt-4.1-mini`: two colliding pairs with
    # "acqcom", "digital" and "marketing" counted, and ZERO with them
    # discounted. The copy was fine and the check was reading the company
    # name back to itself.
    #
    # `ignore` is supplied by the caller because only the caller knows whose
    # company this is. An empty one keeps the old behaviour exactly.
    skip = {str(w).lower() for w in (ignore or ())}
    word_sets = [(s.get("key", ""),
                  _distinctive_words(s.get("text", "")) - skip)
                 for s in steps]
    collisions = []
    for i, (key_a, words_a) in enumerate(word_sets):
        for key_b, words_b in word_sets[i + 1:]:
            shared = words_a & words_b
            count = len(shared)
            if count < _REPETITION_MIN_SHARED:
                continue
            smaller = min(len(words_a), len(words_b))
            if smaller == 0:
                continue
            overlap = count / smaller
            if overlap >= _REPETITION_OVERLAP:
                collisions.append((key_a, key_b, count))
    collisions.sort(key=lambda t: -t[2])
    return collisions


def campaign_repetition(steps, company_name=None,
                        subject_vocabulary=SUBJECT_VOCABULARY):
    """Semantic duplicate detection across a whole campaign sequence.

    Returns a list of dicts, each naming a pair of steps that say the same
    thing in different words:

        {"step_a": "li2", "step_b": "li4",
         "shared_words": 5, "shared": ["track", "profitability", ...]}

    An empty list means the sequence is genuinely progressive.

    THIS IS NOT A SECOND IMPLEMENTATION. It calls `repetition_across_rungs`
    with the right ignore set: the company name (every message names the
    company) and the subject vocabulary (every message argues the subject).
    The comparison logic - distinctive words, overlap coefficient, minimum
    shared count - is the same one function, not two.

    THE THRESHOLD. 50% overlap of the smaller set's content words, with at
    least three shared. Measured 2026-09-14 on the real Productive corpus:

      SIX_NOTES (16kagency-com, gpt-4o-mini)
        with subject vocabulary counted: 15 of 15 pairs collide
        with subject vocabulary discounted: 10 of 15 pairs collide
        -> the notes ARE paraphrases; the check is correct to flag them

      cadence.py email bodies (persona_pain, comparable_proof, breakup)
        with subject vocabulary counted: 3 of 3 pairs collide
        with subject vocabulary discounted: 0 of 3 pairs collide
        -> the bodies are genuinely progressive; the check was reading the
           topic back to itself

      The six DISTINCT_BODIES from test_campaign_ready_funnel.py
        with subject vocabulary discounted: 0 of 15 pairs collide
        -> correct; they are six different arguments

    The threshold catches paraphrases (SIX_NOTES) and releases progressive
    copy (cadence.py bodies, DISTINCT_BODIES). That is the distribution it
    must produce, and it does.
    """
    if not steps or len(steps) < 2:
        return []
    ignore = set()
    if company_name:
        for token in _re.findall(r"[a-z]+", str(company_name).lower()):
            if len(token) >= 4:
                ignore.add(token)
    if subject_vocabulary:
        ignore.update(str(w).lower() for w in subject_vocabulary)
    raw = repetition_across_rungs(steps, ignore=ignore)
    # Enrich each collision with the actual shared words, so the refusal
    # can name what overlapped rather than just how many.
    skip = ignore
    word_map = {}
    for s in steps:
        word_map[s.get("key", "")] = _distinctive_words(
            s.get("text", "")) - skip
    result = []
    for key_a, key_b, count in raw:
        shared = sorted(word_map.get(key_a, set()) & word_map.get(key_b, set()))
        result.append({"step_a": key_a, "step_b": key_b,
                       "shared_words": count, "shared": shared})
    return result
# ------------------------------------------------ structural repetition
#
# TASK-047. Four of five staged Productive emails open with the same SHAPE:
#
#     [the company's own self-description]
#     -> [why I am writing, stated by role]
#     -> [the ask]
#
# Different words, one formula. `repetition_across_rungs` passed all of it
# correctly by its own rule: it counts shared distinctive WORDS, and a
# formula that varies its nouns shares almost none.
#
# This check catches the SHAPE, not the words. Two rungs collide when their
# opening move AND closing move AND self-reference pattern are all the same.
# The self-reference must be present in BOTH emails for a collision, because
# the formula includes "I am reaching out to you as the founder" as a
# load-bearing part of the shape.
#
# FINDING: The starting definition (opening+closing only) was too eager.
# Measured against the phase7 estate (twelve emails, six contacts, two
# steps each): 2 of 6 contacts collided, but the copy was good - both
# steps asked different questions. Requiring self_ref in both emails
# catches the formula and passes all phase7 contacts. Zero false positives
# on the estate, and the formula is still caught.

_SENTENCE_SPLIT = _re.compile(r'(?<=[.!?])\s+')

# Opening move: what the first sentence does.
OPENING_DESCRIBE_THEM = "describe_them"
OPENING_DESCRIBE_US = "describe_us"
OPENING_QUESTION = "question"
OPENING_OBSERVATION = "observation"

# Closing move: what the last sentence does.
CLOSING_QUESTION = "question"
CLOSING_CALL = "call_proposal"
CLOSING_OUT = "out"
CLOSING_STATEMENT = "statement"

# Patterns for the opening move. The first sentence is checked against
# these in order; the first match wins.
_OPENING_THEM_PATTERNS = _re.compile(
    r"\b(?:your|you(?:'re| are))\b"
    r"|(?:the\s+)?\b(?:team|company|agency|studio|firm)\b"
    r"|\bat\s+[A-Z]\w+\b",
    _re.I)

_OPENING_US_PATTERNS = _re.compile(
    r"\b(?:i\s+work|i\s+help|we\s+help|we\s+build|we\s+make|"
    r"our\s+(?:platform|tool|product|team)|i\s+lead|i\s+run|"
    r"i\s+am\s+(?:the|a)\s+(?:founder|ceo|cto))\b",
    _re.I)

# Patterns for the closing move. The last sentence is checked against
# these in order; the first match wins.
_CLOSING_QUESTION_RE = _re.compile(r'\?\s*$')
_CLOSING_CALL_PATTERNS = _re.compile(
    r"\b(?:call|meeting|chat|speaking|15\s*min|this\s+week|"
    r"schedule|book\s+(?:a\s+)?(?:time|a\s+)?(?:call|slot))\b",
    _re.I)
_CLOSING_OUT_PATTERNS = _re.compile(
    r"\b(?:no\s+worries|no\s+problem|if\s+not|easy\s+no|"
    r"permission\s+to\s+stop|happy\s+to\s+(?:leave|stop)|"
    r"not\s+the\s+right\s+time|if\s+this\s+isn|"
    r"last\s+(?:note|email|message)|no\s+pitch)\b",
    _re.I)


def _sentences(text):
    """Split text into sentences, stripping greeting prefixes.

    A greeting ("Hi Sam,") is not a sentence for shape classification:
    it is present in every message and says nothing about the shape.
    """
    text = str(text or "").strip()
    # Strip the greeting: "Hi Name," or "Hello Name," at the start.
    text = _re.sub(
        r'^(?:hi|hello|hey|dear|good\s+(?:morning|afternoon))'
        r'\s+[^,.!?\n]+[,]\s*',
        '', text, count=1, flags=_re.I)
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [s.strip() for s in parts if s.strip()]


def _classify_opening(sentence):
    """What the first sentence does: describe them, describe us, ask, observe."""
    if not sentence:
        return OPENING_OBSERVATION
    if sentence.rstrip().endswith("?"):
        return OPENING_QUESTION
    if _OPENING_US_PATTERNS.search(sentence):
        return OPENING_DESCRIBE_US
    if _OPENING_THEM_PATTERNS.search(sentence):
        return OPENING_DESCRIBE_THEM
    return OPENING_OBSERVATION


def _classify_closing(sentence):
    """What the last sentence does: ask, propose a call, offer an out, state."""
    if not sentence:
        return CLOSING_STATEMENT
    if _CLOSING_QUESTION_RE.search(sentence):
        return CLOSING_QUESTION
    if _CLOSING_OUT_PATTERNS.search(sentence):
        return CLOSING_OUT
    if _CLOSING_CALL_PATTERNS.search(sentence):
        return CLOSING_CALL
    return CLOSING_STATEMENT


def structural_shape(text):
    """The shape of a message: opening move, closing move, question count.

    Returns a dict with:
      opening     one of describe_them, describe_us, question, observation
      closing     one of question, call_proposal, out, statement
      questions   how many sentences end with ?
      self_ref    whether a sentence introduces the sender by role

    This is not a grammar parser. It classifies by heuristics that are
    good enough to catch the formula the task describes: four emails
    opening with [describe them] and closing with [statement/ask],
    varying only their nouns.
    """
    sents = _sentences(text)
    if not sents:
        return {"opening": OPENING_OBSERVATION, "closing": CLOSING_STATEMENT,
                "questions": 0, "self_ref": False}
    opening = _classify_opening(sents[0])
    closing = _classify_closing(sents[-1])
    questions = sum(1 for s in sents if s.rstrip().endswith("?"))
    self_ref = bool(_re.search(
        r"\b(?:i\s+am\s+reaching\s+out|"
        r"as\s+(?:the|a)\s+(?:founder|ceo|cto|coo)|"
        r"i\s+am\s+(?:the|a)\s+(?:founder|ceo|cto|coo))\b",
        text, _re.I))
    return {"opening": opening, "closing": closing,
            "questions": questions, "self_ref": self_ref}


def structural_repetition(steps, ignore=()):
    """Pairs of steps that share the same structural shape.

    `steps` is a list of dicts, each with at least `key` and `text`.
    Returns a list of (key_a, key_b, shape_detail) tuples.

    Two rungs collide when their opening move AND closing move AND
    self-reference pattern are all the same. The self-reference must
    be present in BOTH emails for a collision, because the formula
    TASK-047 describes includes "I am reaching out to you as the
    founder" as a load-bearing part of the shape.

    FINDING: The starting definition (opening+closing only) was too
    eager. Measured against the phase7 estate (twelve emails, six
    contacts, two steps each): 2 of 6 contacts collided, but the copy
    was good - both steps asked different questions. Requiring self_ref
    in both emails catches the formula (em1 and em2 both have "I am
    reaching out to you as the founder") and passes all phase7 contacts
    (none have self_ref). Zero false positives on the estate, and the
    formula is still caught.
    """
    if not steps or len(steps) < 2:
        return []
    shapes = []
    for s in steps:
        shape = structural_shape(s.get("text", ""))
        shapes.append((s.get("key", ""), shape))
    collisions = []
    for i, (key_a, shape_a) in enumerate(shapes):
        for key_b, shape_b in shapes[i + 1:]:
            # Both must have self_ref for a collision. The formula
            # includes "I am reaching out to you as the founder"; an
            # email without self_ref is not using the formula.
            if not (shape_a["self_ref"] and shape_b["self_ref"]):
                continue
            if (shape_a["opening"] == shape_b["opening"]
                    and shape_a["closing"] == shape_b["closing"]):
                collisions.append((key_a, key_b, {
                    "opening": shape_a["opening"],
                    "closing": shape_a["closing"],
                    "self_ref": True,
                }))
    return collisions


# THIRD-PARTY CLAIM PATTERNS.
#
# "many teams like yours have found..." is a claim about a population.
# The record holds facts about ONE company and ONE person; it cannot
# support a statement about what "many teams" or "companies we work
# with" have experienced. Each pattern below names the form; the check
# is deterministic.
#
# Deliberately NOT every sentence about other people. "most operations
# leads we speak to" is honest copy about our own experience and is
# already in `claims.GENERIC_SUBJECTS`. What is caught here is the form
# that asserts a specific outcome for a named population: "have found
# that X can transform Y", "have seen a Y% improvement", "report that
# X is the biggest challenge". A vague reference to what others do is
# not the same as a claim about what they achieved.

_THIRD_PARTY_OUTCOMES = (
    _re.compile(r"\b(?:many|most|several|numerous)\s+"
                r"(?:teams|companies|clients|customers|agencies|studios|"
                r"founders|leads|organisations|organizations|businesses)"
                r"(?:\s+like\s+yours)?\s+"
                r"(?:have\s+)?(?:found|seen|reported|experienced|"
                r"discovered|achieved|told\s+us)\b", _re.I),
    _re.compile(r"\b(?:teams|companies|clients|customers|agencies)\s+"
                r"(?:we\s+(?:work\s+)?with|like\s+yours)\s+"
                r"(?:have\s+)?(?:found|seen|reported|experienced|"
                r"discovered|achieved)\b", _re.I),
    _re.compile(r"\b(?:many|most)\s+(?:teams|companies|clients|"
                r"customers|agencies)\s+"
                r"(?:have\s+)?(?:found|seen|reported)\s+that\b", _re.I),
)


def unsupported_third_party(text):
    """Claims about third-party populations the record cannot support.

    Returns a list of matched phrases. An empty list means no
    unsupported third-party claim was found.

    This is NOT the same as `claims.check`, which verifies assertions
    about the prospect against stored evidence. This checks assertions
    about OTHER people - "many teams like yours have found..." - where
    the record holds no evidence about what those teams experienced.
    """
    if not text:
        return []
    found = []
    for pattern in _THIRD_PARTY_OUTCOMES:
        match = pattern.search(text)
        if match:
            found.append(match.group(0).strip())
    return found


# --------------------------------------------------------- the gate itself

PASS = "pass"
FAIL = "fail"

# The named reasons a message can fail the gate. Each is returned by
# exactly one check, so a failure can be traced to its source.
REASON_ANGLE_LEAKAGE = "angle_wording_leakage"
REASON_REPETITION = "repetition_across_rungs"
REASON_STRUCTURAL_REPETITION = "structural_repetition_across_rungs"
REASON_UNSUPPORTED_CLAIM = "unsupported_third_party_claim"


def gate(text, config, steps=None, channel="linkedin", ignore=()):
    """The quality gate for one message.

    Returns a dict with:
      verdict   PASS or FAIL
      reasons   a list of named reasons (empty on PASS)
      detail    a dict of check-specific findings

    `steps` is optional and is the full set of steps for this contact.
    When provided, the repetition check runs across the set. When
    absent, only the single-message checks run.

    THE ANGLE RULE IS NOT THE SAME ON BOTH CHANNELS, and applying the
    LinkedIn one to email fails almost everything. `prompts/linkedin_note.md`
    says of `angle_wording`: "Never put it in". `prompts/draft.md` says
    something narrower and different - do not ATTRIBUTE our words to them:

        "`angle_wording` is the CLIENT's phrasing of what they sell; it is
        not something the recipient has said, published or endorsed. 'HSMG
        states that profitability visible on Monday ... drives its strategic
        focus' puts our sales line in their mouth and is false."

    The same file tells the writer to USE the angle and not to invent a
    different pitch. So an email carrying the client's own line as OUR claim
    is correct copy, and an email attributing it to the prospect is not.

    Measured 2026-09-14, with this check applied to email: 51 of 70 staged
    steps failed, and so did the canary on campaign 451 - copy a human
    reviewed, approved and scheduled. A gate that fails good copy is worse
    than none.

    The email half of the rule is already covered and needs nothing here:
    `claims.check` flags exactly that attribution, in its own words,
    "'profitability' is asserted about them and nothing stored supports it".
    """
    reasons = []
    detail = {}

    if str(channel or "").lower() != "email":
        leaked = angle_leakage(text, config)
        if leaked:
            reasons.append(REASON_ANGLE_LEAKAGE)
            detail["leaked_phrases"] = leaked

    third_party = unsupported_third_party(text)
    if third_party:
        reasons.append(REASON_UNSUPPORTED_CLAIM)
        detail["unsupported_claims"] = third_party

    if steps is not None:
        collisions = repetition_across_rungs(steps, ignore=ignore)
        if collisions:
            reasons.append(REASON_REPETITION)
            detail["repetitions"] = [{"step_a": a, "step_b": b,
                                      "shared_words": n}
                                     for a, b, n in collisions]
        # STRUCTURAL REPETITION: same opening+closing shape across rungs.
        # Only on email, where the five-step ladder has distinct jobs per
        # rung and reusing the same shape is the defect TASK-047 names.
        # LinkedIn notes are too short for shape analysis to be meaningful.
        if str(channel or "").lower() == "email":
            shape_collisions = structural_repetition(steps, ignore=ignore)
            if shape_collisions:
                reasons.append(REASON_STRUCTURAL_REPETITION)
                detail["structural_repetitions"] = [
                    {"step_a": a, "step_b": b, "shape": s}
                    for a, b, s in shape_collisions]

    return {"verdict": PASS if not reasons else FAIL,
            "reasons": reasons,
            "detail": detail}


def gate_steps(steps, config):
    """The quality gate for a whole set of steps for one contact.

    `steps` is a list of dicts with `key` and `text`. Returns a dict
    keyed by step key, each value being the gate result for that step
    (including the cross-step repetition check).
    """
    results = {}
    for step in steps:
        result = gate(step.get("text", ""), config, steps=steps)
        results[step.get("key", "")] = result
    return results


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
