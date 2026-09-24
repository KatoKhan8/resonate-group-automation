"""One fact, and what it is allowed to claim.

EVERY FACT CARRIES SOURCE, DATE AND SNIPPET. Operator, 2026-09-24. Not as
decoration: a research pack exists so a first line can say something true
about a company, and the next question anybody asks about a generated line
is "where did that come from". A fact that cannot answer that is not usable
in copy, so it is not representable here.

`src/copylint.py` enforces the other half - a claim in a draft has to be
traceable back to one of these - and the two agree through `fact_id`.
"""
import hashlib
import re

#: The kinds of thing a pack may assert, and where each comes from. A fact
#: whose `kind` is not here is refused rather than stored under a new name,
#: because the lint matches on these and a kind it has never seen reads as
#: "no supporting fact".
KINDS = ("company_post", "open_role", "person_post", "site_page")

#: How long a snippet may be. Long enough to be quotable, short enough that
#: nobody pastes a paragraph of somebody else's writing into an email.
SNIPPET_CHARS = 400

_WHITESPACE = re.compile(r"\s+")


class UnusableFact(ValueError):
    """Raised rather than stored. A fact missing its provenance is worse
    than an absent fact: absent is visible, unattributed is quotable."""


def clean(text, limit=SNIPPET_CHARS):
    return _WHITESPACE.sub(" ", str(text or "")).strip()[:limit]


def fact_id(kind, source_url, snippet):
    """Stable across runs, so a cached pack and a fresh one agree.

    Hashed from what the fact IS rather than when it was fetched - two runs
    a week apart that find the same post produce the same id, and a draft
    that cited it still traces.
    """
    basis = "|".join([str(kind), str(source_url), clean(snippet, 200)])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


#: A date arrives as a string on some actors and as an OBJECT on others -
#: harvestapi's posts carry `{"timestamp":…, "date":"2020-02-19T…"}`. The
#: first version did `str(published_at)[:10]`, which turns that dict into
#: the literal `{'timestam` and stamps it on the fact as a date. It stayed
#: invisible because every row from that actor was being dropped for a
#: different reason, which is the worst way for a bug like this to wait.
DATE_FIELDS = ("date", "postedAt", "publishedAt", "iso", "value")

#: A bare calendar date and nothing else.
DATE_ONLY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _date_of(value):
    """A `YYYY-MM-DD`, or None. Never a stringified object."""
    if value is None:
        return None
    if isinstance(value, dict):
        for field in DATE_FIELDS:
            found = _date_of(value.get(field))
            if found:
                return found
        return None
    if isinstance(value, (int, float)):
        # Epoch milliseconds, which is what `timestamp` carries.
        import datetime
        seconds = value / 1000 if value > 10 ** 11 else value
        try:
            return datetime.datetime.utcfromtimestamp(
                seconds).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()[:10]
    return text if DATE_ONLY.match(text) else None


def make(kind, source_url, published_at, snippet, subject=None, extra=None):
    """One fact, or `UnusableFact`.

    `published_at` is the date the SOURCE carries, not the date we fetched
    it. They are different questions and conflating them is how a four-year
    -old blog post becomes "they just announced". `retrieved_at` is stamped
    by the pack.
    """
    if kind not in KINDS:
        raise UnusableFact("unknown fact kind %r; add it to KINDS and teach "
                           "the lint about it in the same change" % (kind,))
    url = str(source_url or "").strip()
    if not url:
        raise UnusableFact("a %s fact with no source url" % kind)
    body = clean(snippet)
    if not body:
        raise UnusableFact("a %s fact with no snippet: nothing to quote and "
                           "nothing to check a claim against" % kind)
    when = _date_of(published_at)
    return {
        "fact_id": fact_id(kind, url, body),
        "kind": kind,
        "source_url": url,
        # MAY BE NONE, AND SAYS SO RATHER THAN GUESSING. An undated post is
        # a real thing; inventing a date for it would make "recent" a lie
        # the copy could lean on.
        "published_at": when,
        "snippet": body,
        "subject": subject,
        "extra": dict(extra or {}),
    }
