#!/usr/bin/env python3
"""Pack fact validation for the review file gate.

OPERATOR REQUIREMENT, 2026-09-25: the quoted span must be a complete sentence
carrying a verb, taken from the site BODY, never nav or menu text. A lead
with no such sentence is HELD, not sent generic.

## What this module does

Given a research pack's facts[], determine which fact (if any) is usable as
personalisation in step 1's opener. A usable fact:

  - Has kind "site_page" (from the site body, not a post or role listing)
  - Contains a verb (is a complete sentence, not a fragment)
  - Is not navigation text (menu items, links, boilerplate)

## What "nav text" looks like

The incident's personalisation was:

    "Order your favorite dishes in seconds! Order Online Skip to
     main content Drinks Menu Order Catering Kerrville ..."

This is navigation chrome. It has verbs ("Order", "Skip") but they are
imperative UI instructions, not statements about the company. The gate
below refuses this pattern.

## Why this is separate from copylint

`copylint.step1_without_pack_fact` checks whether the opener's tokens
appear in ANY pack fact. This module checks whether a pack fact is USABLE
at all. A pack of five nav fragments would pass copylint's token match
but should not be quoted to a prospect. The two checks are complementary.
"""
import re

#: Facts whose kind is not site_page are not from the site body.
USABLE_KINDS = ("site_page",)

#: Navigation and UI boilerplate. A snippet matching any of these patterns
#: is navigation chrome, not a statement about the company.
NAV_PATTERNS = (
    re.compile(r"\b(?:skip\s+to\s+main)\b", re.I),
    re.compile(r"\b(?:menu|nav|navigation)\b", re.I),
    re.compile(r"\b(?:order\s+online|order\s+catering)\b", re.I),
    re.compile(r"\b(?:sign\s+(?:up|in|out)|log\s+(?:in|out))\b", re.I),
    re.compile(r"\b(?:subscribe|cookie|privacy\s+policy|terms\s+of\s+service)\b", re.I),
    re.compile(r"\b(?:home|about\s+us|contact\s+us|our\s+team|blog|careers)\b", re.I),
    re.compile(r"\b(?:follow\s+us|share|tweet|like)\b", re.I),
)

#: English verb indicators. Not a complete list - just enough to distinguish
#: a sentence ("We help agencies track time") from a fragment ("Time tracking
#: software for agencies"). A usable fact has at least one subject-verb pair.
VERB_PATTERNS = re.compile(
    r"\b(?:is|are|was|were|has|have|had|do|does|did|will|would|could|should|"
    r"can|may|might|shall|must|need|help|work|make|build|create|provide|"
    r"offer|serve|deliver|manage|track|monitor|improve|increase|reduce|"
    r"grow|scale|support|enable|allow|give|take|bring|develop|design|"
    r"launch|open|close|start|stop|run|move|change|shift|focus|drive|"
    r"lead|own|handle|cover|include|combine|unify|replace|simplify|"
    r"automate|streamline|centralise|centralize|consolidate|integrate|"
    r"connect|share|show|reveal|deliver|generate|produce|publish|announce|"
    r"hire|expand|acquire|partner|win|serve|reach|pass|complete|finish|"
    r"achieve|reach|enter|open|begin)\b",
    re.I
)

#: Minimum length for a usable fact snippet. Too short is a fragment.
MIN_SNIPPET_WORDS = 6


def is_nav_text(snippet):
    """True when the snippet reads as navigation or UI chrome."""
    text = str(snippet or "")
    return any(p.search(text) for p in NAV_PATTERNS)


def has_verb(snippet):
    """True when the snippet contains at least one verb form."""
    return bool(VERB_PATTERNS.search(str(snippet or "")))


def word_count(text):
    return len(str(text or "").split())


def usable_fact(fact):
    """Whether a single fact is usable as personalisation.

    Returns True when the fact:
    - Has a usable kind (site_page)
    - Is long enough to be a sentence
    - Contains a verb
    - Is not navigation text
    """
    if not isinstance(fact, dict):
        return False
    kind = fact.get("kind") or ""
    if kind not in USABLE_KINDS:
        return False
    snippet = fact.get("snippet") or ""
    if word_count(snippet) < MIN_SNIPPET_WORDS:
        return False
    if is_nav_text(snippet):
        return False
    if not has_verb(snippet):
        return False
    return True


def select_fact(facts):
    """The first usable fact from a pack's fact list, or None.

    `facts` is the `facts[]` array from a researchpack JSONL row. Returns
    the first fact that passes `usable_fact`, or None when no fact is
    usable. The caller decides what to do with None - typically HELD.
    """
    for fact in (facts or []):
        if usable_fact(fact):
            return fact
    return None


def classify_facts(facts):
    """Classify every fact in a pack as usable or not.

    Returns a list of dicts with the fact and its classification:
    [{"fact": {...}, "usable": True/False, "reason": "..."}]

    The review file shows ALL facts, not just the selected one, so a
    reader can see what was available and why some were not used.
    """
    out = []
    for fact in (facts or []):
        if not isinstance(fact, dict):
            continue
        if usable_fact(fact):
            out.append({"fact": fact, "usable": True, "reason": ""})
        else:
            kind = fact.get("kind") or "?"
            snippet = str(fact.get("snippet") or "")[:60]
            if kind not in USABLE_KINDS:
                reason = f"kind is {kind}, not site_page"
            elif word_count(snippet) < MIN_SNIPPET_WORDS:
                reason = "snippet too short to be a sentence"
            elif is_nav_text(snippet):
                reason = "navigation or UI chrome"
            elif not has_verb(snippet):
                reason = "no verb - fragment, not a sentence"
            else:
                reason = "unknown"
            out.append({"fact": fact, "usable": False, "reason": reason})
    return out
