#!/usr/bin/env python3
"""Every specific claim in a message must be traceable to something we know.

## Why a lint rule is not enough

lint.py already refuses placeholders, banned phrases and the wrong length. None
of that catches the failure that actually damages a client: a fluent, confident
sentence about a company event that never happened. "Congratulations on the
Series B" reads perfectly and passes every stylistic check, and if there was no
Series B the prospect knows immediately that nobody read anything.

So specific claims are extracted from the finished text and each one is checked
against what the record actually holds: stored company facts, contact facts, the
evidence chosen for this message, and known thread context. A claim with no
support is a rejection, and the draft is regenerated.

## Rejected, never patched

There is no code here that edits a sentence to make it true. Deleting the
offending clause leaves a message shaped around a fact it no longer states, and
softening it ("I think you might be growing") is worse than either. The draft
goes back.

## What counts as a claim

Numbers, dates, place names, named events - the things a reader could check.
Ordinary sales prose is not a claim: "most operations leads we speak to lose a
day a month" is a statement about us, not about them, and needs no evidence
about their company.
"""
import re

from . import evidence

# A sentence containing one of these is making a checkable assertion about the
# prospect rather than a general statement.
CLAIM_MARKERS = (
    "you", "your", "you're", "youre", "they", "their",
)

# Things that make a sentence specific enough to be wrong.
NUMBER = re.compile(r"\b\d[\d,.]*\b")
MONTH = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october"
    r"|november|december|last month|this month|last week|recently|"
    r"two weeks ago|last quarter)\b", re.I)
EVENT_WORDS = (
    "raised", "funding", "series a", "series b", "series c", "acquired",
    "acquisition", "merger", "merged", "ipo", "launched", "launch", "opened",
    "opening", "expanded", "expansion", "hiring", "hired", "announced",
    "announcement", "partnership", "award", "certified", "moved to",
    "relocated", "office in", "appointed", "promoted", "published", "wrote",
    "posted", "spoke at", "keynote",
)

# Words that make a sentence about us or about the world, not about them.
GENERIC_SUBJECTS = ("we ", "our ", "i ", "most ", "many ", "teams ", "companies ")


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", str(text or ""))
    return [p.strip() for p in parts if p.strip()]


# A DECLARATIVE STATEMENT ABOUT WHAT THE PROSPECT DOES.
#
# `is_claim` recognised two things: a number and an event word. The sentence
# that actually went out to a real person was "you are running utilisation at
# the canary's company" - no number, no event, and a flat assertion about how somebody
# else's company operates, made on no evidence at all. It was not a claim as
# far as this module was concerned.
#
# These are second-person VERBS, not possessives. "your size" and "your team"
# appear in perfectly honest copy - the approved canary note says "curious how
# the canary's company handles it at your size" - and matching those would refuse the
# very sentences this system is trying to write. What is being caught is the
# form "you ARE X", "you HAVE X", "you RUN X": telling somebody a fact about
# their own business.
#
# Questions are still exempt by the rule below, so "are you running
# utilisation?" is a question and stays one.
# Constructions that suppose rather than state. A sentence carrying one of
# these is not telling the prospect a fact about themselves, whatever verb
# follows.
#
# The day-21 template is the reason this exists: "if {angle_phrase} is not
# something you are looking at right now, that is a fair answer in itself."
# Conditional, negated, and asserting nothing - the comment above it in
# `cadence.py` says as much - and a first version of the rule below refused
# it, which would have blocked the whole demo cadence. A guard that stops
# honest copy gets deleted rather than fixed.
HEDGES = ("if ", "unless ", "whether ", "in case ", "should you ",
          "suppose ", "assuming ", "not something", "maybe ", "perhaps ")

SECOND_PERSON_ASSERTIONS = (
    "you are ", "you're ", "you have ", "you've ", "you run ", "you use ",
    "you manage ", "you rely ", "you operate ", "you track ", "you bill ",
    "you struggle", "you need ", "you must be ", "your team is ",
    "your team has ", "your agency is ", "your studio is ",
)


def asserts_about_them(low):
    """Is this a flat statement about how the prospect OPERATES?

    Both halves are required, and the second half is what keeps this usable.
    "you are welcome to book a slot" is a second-person assertion and asserts
    nothing about their business; "you are running utilisation" says something
    about how they work that somebody could check. Only the second kind needs
    evidence, and demanding it of the first would refuse ordinary politeness.
    """
    if any(hedge in low for hedge in HEDGES):
        return False
    if not any(marker in low for marker in SECOND_PERSON_ASSERTIONS):
        return False
    return [t for t in evidence.OPERATIONAL_TERMS if t in low]


def is_claim(sentence):
    """Does this sentence assert something checkable about the prospect?"""
    low = sentence.lower()
    if not any(marker in low.split() or marker in low for marker in CLAIM_MARKERS):
        # No second person and no third party: it is about us.
        if not any(w in low for w in EVENT_WORDS):
            return False
    if low.startswith(GENERIC_SUBJECTS):
        # "We help teams like yours" - about us, even though it says yours.
        if not (NUMBER.search(low) or any(w in low for w in EVENT_WORDS)):
            return False
    if "?" in sentence and not NUMBER.search(low):
        return False                     # a question asserts nothing
    return bool(NUMBER.search(low) or MONTH.search(low)
                or asserts_about_them(low)
                or any(w in low for w in EVENT_WORDS))


def support_text(rec, contact=None, chosen=()):
    """Everything a claim is allowed to lean on, as one searchable blob."""
    parts = []
    facts = rec.get("company_facts") or {}
    for key, value in facts.items():
        if isinstance(value, (list, tuple)):
            # THE FIELD NAME AS WELL AS THE VALUES. A populated `offices` list
            # holding five city names is knowledge that this company has
            # offices, and dropping the key meant the word "office" appeared
            # nowhere in support - so "you run finance across five offices",
            # which the record fully supports, read as a fabrication.
            #
            # Only when it is POPULATED. An empty list is not evidence that we
            # know anything about the field, and appending the key regardless
            # would make every absent fact quietly assertable.
            if value:
                parts.append(str(key))
                parts.extend(str(v) for v in value)
        elif value not in (None, "", {}):
            parts.append(f"{key} {value}")
    parts.append(str(rec.get("company") or ""))
    parts.append(str(rec.get("domain") or ""))
    parts.append(str(rec.get("hook") or ""))
    diagnosis = rec.get("diagnosis") or {}
    parts.extend(str(v) for v in diagnosis.values() if v)
    if contact:
        for key in ("name", "title", "persona", "angle", "location"):
            if contact.get(key):
                parts.append(str(contact[key]))
    for entry in chosen or []:
        parts.append(str(entry.get("fact") or ""))
        parts.append(str(entry.get("published_at") or ""))
    for entry in rec.get("research") or []:
        parts.append(str(entry.get("fact") or ""))
    cited = rec.get("evidence") or {}
    if isinstance(cited, dict):
        for lines in cited.values():
            parts.extend(str(line) for line in (lines or []))
    return " ".join(parts).lower()


def _tokens(text):
    return set(re.findall(r"[a-z][a-z\-]{3,}", (text or "").lower()))


def check_sentence(sentence, support):
    """Is this claim supported? Returns (ok, why_not)."""
    low = sentence.lower()

    for number in NUMBER.findall(low):
        cleaned = number.strip(".,")
        if len(cleaned) >= 2 and cleaned not in support:
            return False, f"the figure {cleaned} appears in no stored fact"

    # A STATEMENT ABOUT HOW THEY OPERATE NEEDS SOMETHING BEHIND IT.
    #
    # "you are running utilisation at <their company>" carries no figure and no
    # event word, so every check below passed it and it went to a real person.
    #
    # STRICTER than the event-word branch, deliberately. The event branch
    # allows a paraphrase, because "you opened a Vienna office" against
    # evidence saying exactly that should pass on its content words. That
    # allowance is too generous here: a short second-person sentence is mostly
    # the recipient's own name and company, both of which are always in
    # support, so coverage passes on words that carry no claim at all. The
    # operational term IS the assertion, so it is what has to be supported.
    for term in (asserts_about_them(low) or []):
        if term not in support:
            return False, (f"'{term}' is asserted about them and nothing "
                           f"stored supports it")

    events_named = [w for w in EVENT_WORDS if w in low]
    for word in events_named:
        if word not in support and not _is_paraphrase(low, support):
            return False, (f"'{word}' is asserted but nothing stored "
                           "mentions it")
    return True, None


def _is_paraphrase(low, support):
    """Is most of this sentence's substance already in what we know?

    The test the event-word branch has always used, named so the operational
    branch can hold to it too. "Congratulations on your Series B" has nothing
    behind it and fails; "you opened a Vienna office" against stored evidence
    saying exactly that passes.
    """
    content = _tokens(low) - _tokens(" ".join(CLAIM_MARKERS))
    if not content:
        return False
    missing = [t for t in content if t not in support]
    return len(missing) * 2 <= len(content)


def check(text, rec, contact=None, chosen=()):
    """Every unsupported claim in this text. Empty means it may ship."""
    support = support_text(rec, contact, chosen)
    problems = []
    for sentence in sentences(text):
        if not is_claim(sentence):
            continue
        ok, why = check_sentence(sentence, support)
        if not ok:
            problems.append({"sentence": sentence[:160], "why": why})
    return problems


def verify(step, rec, contact=None, chosen=()):
    """Check a whole step - subject and body together."""
    text = " ".join(str(step.get(k) or "") for k in ("subject", "body", "note"))
    return check(text, rec, contact, chosen)


class UnsupportedClaim(RuntimeError):
    """A draft asserted something nothing supports. It is regenerated, not
    edited: a patched sentence leaves a message built around a fact it no
    longer makes."""


def require(step, rec, contact=None, chosen=()):
    problems = verify(step, rec, contact, chosen)
    if problems:
        raise UnsupportedClaim("; ".join(
            f"{p['sentence']!r}: {p['why']}" for p in problems[:2]))
    return True
