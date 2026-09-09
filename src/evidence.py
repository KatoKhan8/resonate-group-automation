#!/usr/bin/env python3
"""What we know about a company or a person, and how much it is worth.

## The point

Personalisation is only worth anything if it is true and specific. "I noticed
you're growing" is not personalisation; it is a sentence that could be sent to
anyone, and a prospect reads it as exactly that. "Your careers page has five
implementation-manager openings across Germany and Austria" is worth sending
because it could only be sent to one company, and because someone could check
it.

So every observation this system is allowed to make is an *evidence* object
with a source, a date and an id. A claim with no evidence id behind it does not
go out - src/claims.py enforces that - and a piece of evidence with no date is
marked UNKNOWN rather than assumed recent.

## Three scores, all deterministic

  freshness   how old is it? Computed from published_at and nothing else.
  relevance   does it match this persona and angle? Computed from the client's
              own configured vocabulary, not from a model's opinion.
  quality     is it worth a sentence at all? STRONG / MEDIUM / WEAK / UNUSABLE.

They are separate because they fail separately. A hiring post from last week is
fresh and relevant but might be pure boilerplate; a detailed operations essay
from a year ago is stale but says more about the person than anything recent.
Collapsing them into one number hides which one was the problem.

Nothing here calls a provider, and nothing here invents a date.
"""
import datetime
import hashlib
import re

# ------------------------------------------------------------------ subjects

COMPANY = "company"
PERSON = "person"
SUBJECTS = (COMPANY, PERSON)

# The four levels the personalisation model works in. Level 4 is preferred
# where it exists and is real; the others are what keep a message honest when
# it does not.
LEVEL_COMPANY = 1
LEVEL_PERSONA = 2
LEVEL_PERSON = 3
LEVEL_RECENT = 4

# ---------------------------------------------------------------- freshness

HIGH = "high"
MEDIUM = "medium"
LOW = "low"
BACKGROUND = "background"
UNKNOWN = "unknown"

DEFAULT_FRESHNESS = {"high_days": 30, "medium_days": 90, "maximum_days": 365}


def _parse_date(value):
    """A date, or None. Never a guess: an unparseable date is unknown."""
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    for pattern in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
                    "%d/%m/%Y", "%d %B %Y", "%B %d, %Y"):
        try:
            return datetime.datetime.strptime(text[:len(text)], pattern).date()
        except ValueError:
            continue
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return datetime.date(*(int(g) for g in match.groups()))
        except ValueError:
            return None
    return None


def days_between(first, second):
    """Whole days from `first` to `second`, or None if either is unknown.

    Distinct from `age_days` below, which defaults its second date to
    today. A caller measuring the gap between two recorded timestamps -
    a first touch and a reply, say - must not silently get a number
    measured from now because one of them was unreadable.
    """
    start, end = _parse_date(first), _parse_date(second)
    if start is None or end is None:
        return None
    return (end - start).days


def age_days(published_at, today=None):
    """How old, in days, or None when the date is unknown."""
    published = _parse_date(published_at)
    if published is None:
        return None
    today = _parse_date(today) or datetime.date.today()
    return (today - published).days


def freshness(published_at, today=None, policy=None):
    """(bucket, score, age_days). Deterministic, and honest about not knowing.

    The score is a straight line from 1.0 on the day of publication to 0.0 at
    the maximum age, so two pieces of evidence in the same bucket still order
    sensibly. An unknown date scores 0.0 and is bucketed UNKNOWN - never
    treated as old, and never treated as fresh.
    """
    policy = {**DEFAULT_FRESHNESS, **(policy or {})}
    age = age_days(published_at, today)
    if age is None:
        return UNKNOWN, 0.0, None
    if age < 0:
        # A future date is bad data, not fresh news.
        return UNKNOWN, 0.0, age
    maximum = max(1, int(policy["maximum_days"]))
    score = round(max(0.0, 1.0 - (age / maximum)), 3)
    if age <= policy["high_days"]:
        return HIGH, score, age
    if age <= policy["medium_days"]:
        return MEDIUM, score, age
    if age <= maximum:
        return LOW, score, age
    return BACKGROUND, score, age


# ---------------------------------------------------------------- relevance

# Words that make a sentence about the work rather than about the weather.
# Deliberately a plain vocabulary: it is auditable, and a client can extend it
# through their own angle text without anyone changing code.
OPERATIONAL_TERMS = (
    "utilisation", "utilization", "capacity", "resourcing", "resource",
    "margin", "profitability", "billing", "invoicing", "timesheet",
    "time tracking", "forecast", "budget", "scope", "handoff", "hand-off",
    "delivery", "project", "portfolio", "reconcile", "reconciliation",
    "headcount", "hiring", "recruit", "onboarding", "retention", "churn",
    "expansion", "office", "acquisition", "merger", "launch", "rollout",
    "implementation", "integration", "migration", "process", "workflow",
    "efficiency", "visibility", "reporting", "consolidation",
)

# A concrete, dated company change is a first-class reason to write, whether or
# not it happens to use the client's own angle vocabulary. "You opened a Vienna
# office last month" is the whole "why now" the system exists to find, and an
# earlier version scored it below the usability bar because the sentence did
# not contain the word "utilisation".
CHANGE_TERMS = (
    "opened", "opening", "expansion", "expanded", "relocated", "moved to",
    "acquisition", "acquired", "merger", "merged", "launch", "launched",
    "hiring", "hired", "recruiting", "appointed", "promoted", "raised",
    "funding", "new office", "second location", "partnership", "certified",
)

# Words for small numbers, because "four delivery leads" is as specific as "4".
SPELLED_NUMBERS = (
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "dozen", "fifteen", "twenty", "thirty", "fifty",
    "hundred",
)

# Signals that a piece of text is social noise rather than business evidence.
NOISE_TERMS = (
    "happy holidays", "merry christmas", "happy new year", "seasons greetings",
    "congratulations to", "congrats to", "proud to announce that our team",
    "throwback", "monday motivation", "rise and grind", "hustle",
    "grateful for", "humbled to", "blessed", "great year ahead",
    "excited for another", "what a year", "team offsite", "christmas party",
    "wonderful evening", "great to catch up", "thanks for having me",
)


def _terms_of(text):
    return set(re.findall(r"[a-z][a-z\-]{2,}", (text or "").lower()))


def relevance(fact, persona=None, angle_words=None, subject=COMPANY,
              authored_by_person=False, freshness_score=0.0):
    """0.0 to 1.0, with the reasons it scored that way.

    Every component is small and named, so a score can be argued with. Nothing
    here asks a model what it thinks.
    """
    text = (fact or "").lower()
    reasons, score = [], 0.0

    if not text.strip():
        return 0.0, ["empty"]

    angle_terms = _terms_of(" ".join(angle_words or []))
    hits = sorted(t for t in angle_terms if len(t) > 3 and t in text)
    if hits:
        score += 0.35
        reasons.append(f"matches the angle: {', '.join(hits[:4])}")

    operational = sorted(t for t in OPERATIONAL_TERMS if t in text)
    if operational:
        score += 0.25
        reasons.append(f"operational subject: {', '.join(operational[:4])}")

    changes = sorted(t for t in CHANGE_TERMS if t in text)
    if changes:
        score += 0.35
        reasons.append(f"a company change: {', '.join(changes[:3])}")

    if persona and persona.lower().replace("_", " ") in text:
        score += 0.05
        reasons.append("names the persona")

    if authored_by_person:
        score += 0.15
        reasons.append("the person wrote it themselves")

    if subject == PERSON:
        score += 0.05
        reasons.append("about the person rather than the company")

    # A specific number or date is what separates an observation from a mood.
    if re.search(r"\b\d+\b", text):
        score += 0.10
        reasons.append("contains a specific figure")

    score += 0.10 * float(freshness_score or 0.0)
    if freshness_score:
        reasons.append(f"recency {freshness_score}")

    noise = [n for n in NOISE_TERMS if n in text]
    if noise:
        score -= 0.45
        reasons.append(f"social noise: {noise[0]}")

    return round(min(1.0, max(0.0, score)), 3), reasons


# ------------------------------------------------------------------ quality

STRONG = "strong"
MEDIUM_Q = "medium"
WEAK = "weak"
UNUSABLE = "unusable"

MIN_RELEVANCE = 0.65


def quality(relevance_score, freshness_bucket, fact="", min_relevance=MIN_RELEVANCE):
    """Is this worth a sentence? STRONG / MEDIUM / WEAK / UNUSABLE.

    UNUSABLE is not a low score, it is a refusal: nothing is written from it,
    and the message falls back to a verified company fact plus persona pain.
    """
    text = (fact or "").strip()
    if not text or len(text.split()) < 4:
        return UNUSABLE
    if any(n in text.lower() for n in NOISE_TERMS) and relevance_score < 0.5:
        return UNUSABLE
    if relevance_score < 0.35:
        return UNUSABLE
    if relevance_score < min_relevance:
        return WEAK
    # Past the policy maximum age this caps at WEAK however relevant the
    # fact is. `freshness` has computed BACKGROUND for evidence older than
    # that since it was written, and nothing read it - so a three-year-old
    # article could be the sentence a cold email led with, on a relevance
    # score alone. Age is not a tiebreaker there: leading with it reads as
    # having researched the company once, a long time ago.
    #
    # WEAK rather than UNUSABLE because the fact is still true and still
    # worth showing on a dossier. What is refused is writing *from* it,
    # which is a narrower statement than refusing to know it.
    if freshness_bucket == BACKGROUND:
        return WEAK
    if freshness_bucket in (HIGH, MEDIUM) and relevance_score >= 0.75:
        return STRONG
    if freshness_bucket == UNKNOWN and relevance_score >= 0.85:
        return STRONG
    return MEDIUM_Q


USABLE = (STRONG, MEDIUM_Q)


# --------------------------------------------------------------- the object

def evidence_id(record_id, source_url, fact, contact_key=None):
    """A stable id for one observation.

    Derived from what the evidence *is*, so the same fact discovered twice
    keeps one id and a draft that references it keeps working across a re-run.
    """
    material = "|".join(str(p or "") for p in
                        (record_id, contact_key, source_url, (fact or "")[:200]))
    return "ev_" + hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]


def make(fact, source_url, source_type, provider, record_id, contact_key=None,
         published_at=None, subject=COMPANY, persona=None, angle_words=None,
         authored_by_person=False, today=None, policy=None,
         min_relevance=MIN_RELEVANCE, retrieved_at=None, confidence=None):
    """One normalised piece of evidence, scored. Never a raw page."""
    fact = re.sub(r"\s+", " ", str(fact or "")).strip()
    bucket, fresh_score, age = freshness(published_at, today, policy)
    score, reasons = relevance(fact, persona, angle_words, subject,
                               authored_by_person, fresh_score)
    return {
        "evidence_id": evidence_id(record_id, source_url, fact, contact_key),
        "fact": fact,
        "source_type": source_type,
        "provider": provider,
        "source_url": source_url,
        "published_at": published_at,
        "retrieved_at": retrieved_at,
        "subject": subject,
        "record_id": record_id,
        "contact_key": contact_key,
        "confidence": confidence,
        "age_days": age,
        "freshness_score": fresh_score,
        "freshness_bucket": bucket,
        "relevance_score": score,
        "relevance_reasons": reasons,
        "quality": quality(score, bucket, fact, min_relevance),
        "authored_by_person": bool(authored_by_person),
    }



# ------------------------------------------------------- and then time passes


def recheck(item, today=None, policy=None, min_relevance=MIN_RELEVANCE):
    """One stored piece of evidence, re-aged against today.

    `make()` scored this row on the day the fact was found and froze the
    answer. Everything downstream then read the frozen `quality` - `usable`,
    `select`, the dossier, the personalisation decision, the preview, the
    quality band - so a draft written in March could still be sent in
    September describing its supporting fact as fresh, because the number
    saying it was fresh was written in March.

    Time is the one input to that score which changes on its own. Nothing
    else here does: `relevance_score` is a function of the fact's words
    against a persona's angle, and neither moves while the row sits in
    state.

    So this re-derives exactly what time touched - age, freshness, and the
    quality that reads freshness - and leaves the rest as scored. Re-scoring
    relevance would need the persona and angle words that produced it, which
    are not on the row; inventing them here to get a rounder number would be
    the worse error. The stored relevance was computed against a *higher*
    freshness score than today's, which makes it optimistic - and the
    freshness bucket, which is re-derived, is what `quality` reads to refuse
    STRONG. The conservative direction is the one that survives.

    When the verdict moved it says so, because "this was strong when we
    found it" is what an operator needs to see beside a draft that no longer
    has a reason to exist.
    """
    fresh = dict(item or {})
    bucket, score, age = freshness(fresh.get("published_at"), today, policy)
    was = fresh.get("quality")
    fresh["age_days"] = age
    fresh["freshness_score"] = score
    fresh["freshness_bucket"] = bucket
    fresh["quality"] = quality(float(fresh.get("relevance_score") or 0.0),
                               bucket, fresh.get("fact") or "", min_relevance)
    if was is not None and fresh["quality"] != was:
        fresh["quality_was"] = was
        fresh["aged_out"] = was in USABLE and fresh["quality"] not in USABLE
    return fresh


def reaged(items, today=None, policy=None, min_relevance=MIN_RELEVANCE):
    """Every row re-aged. The read path for anything that scores evidence."""
    return [recheck(item, today, policy, min_relevance) for item in items or []]

def rank(items):
    """Best first: quality, then relevance, then freshness."""
    order = {STRONG: 0, MEDIUM_Q: 1, WEAK: 2, UNUSABLE: 3}
    return sorted(items or [], key=lambda e: (
        order.get(e.get("quality"), 9),
        -float(e.get("relevance_score") or 0),
        -float(e.get("freshness_score") or 0),
        e.get("evidence_id") or ""))


def usable(items, today=None, policy=None):
    """The rows good enough to write from, re-aged against today first.

    `today` defaults to today rather than to the day the row was scored, so
    a caller that passes nothing gets the current answer rather than the
    stored one. That is the safe default in the direction that matters:
    evidence only gets worse with age, so re-deriving can drop a row from
    this list and can never add one that was not already relevant enough.
    """
    return [e for e in rank(reaged(items, today, policy))
            if e.get("quality") in USABLE]


def select(items, limit=3, today=None, policy=None):
    """The evidence a message may draw on. Small on purpose.

    Three facts is already more than any cold email should use. The cap is here
    rather than in the prompt because a prompt is a request and this is a rule.
    """
    return usable(items, today, policy)[:max(0, limit)]
