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
#:
#: RAISED FROM 400 TO 2000. Operator, 2026-09-25, on lane K's measurement.
#: `webfetch.readable_text` returns a page in READING ORDER, so the first 400
#: characters of a modern site are its navigation bar: of the 14,491 facts
#: captured on the US cohort at 400, **11,719 (80.9%) were navigation-led**,
#: and on 4,512 domains EVERY fact was. `copylint.pack_text` then matches
#: rule 1 against a menu, which is how `software`, `teams` and `services`
#: came to be the words doing the work.
#:
#: Probed on 79 domains at 400 / 1000 / 2000 / 8000 characters: rule-1 passes
#: 68 -> 74 -> 76 -> 76, passes resting on a SINGLE WORD 18 -> 14 -> 8 -> 4,
#: menu words per 400 characters 4.16 -> 2.16 -> 1.47 -> 1.25. 2000 takes
#: nearly all of the grounding 8000 offers at a quarter of the text, and it
#: is the only step that improves the pass rate and the quality of the pass
#: in the same direction. Beyond it the curve is flat and the objection in
#: the line above - nobody should paste a page of somebody else's writing
#: into an email - starts to bite.
#:
#: `webfetch.DEFAULTS["max_text_chars_per_page"]` is 8000, so this cap is
#: still the binding one and no crawl bound moved to make room for it.
SNIPPET_CHARS = 2000

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
    return {
        "fact_id": fact_id(kind, url, body),
        "kind": kind,
        "source_url": url,
        # MAY BE NONE, AND SAYS SO RATHER THAN GUESSING. An undated post is
        # a real thing; inventing a date for it would make "recent" a lie
        # the copy could lean on.
        "published_at": str(published_at)[:10] if published_at else None,
        "snippet": body,
        "subject": subject,
        "extra": dict(extra or {}),
    }
