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
                or any(w in low for w in EVENT_WORDS))


def support_text(rec, contact=None, chosen=()):
    """Everything a claim is allowed to lean on, as one searchable blob."""
    parts = []
    facts = rec.get("company_facts") or {}
    for key, value in facts.items():
        if isinstance(value, (list, tuple)):
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

    events_named = [w for w in EVENT_WORDS if w in low]
    for word in events_named:
        if word not in support:
            # The event word itself is nowhere in what we know. That is allowed
            # only when the sentence is a paraphrase of something we do know -
            # so most of its content words must already appear in support.
            # "Congratulations on your Series B" has nothing behind it and is
            # refused; "you opened a Vienna office" against stored evidence
            # saying exactly that is not.
            content = _tokens(low) - _tokens(" ".join(CLAIM_MARKERS))
            missing = [t for t in content if t not in support]
            if not content or len(missing) * 2 > len(content):
                return False, (f"'{word}' is asserted but nothing stored "
                               "mentions it")
    return True, None


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
