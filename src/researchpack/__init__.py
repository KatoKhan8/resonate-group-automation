"""Research packs: what is true about an account, with a source for each.

Operator, 2026-09-24, lane 1: research packs on every lead, from Apify
actors that need no LinkedIn session, plus the site crawl already here.

    from src import researchpack
    pack = researchpack.build("acme.test")                  # cache only
    pack = researchpack.build("acme.test", live=True)       # buys runs

## WHY IT IS NOT UNDER `src/providers/`

Two reasons and the second is the one that matters. It is not a provider:
it composes several, caches across them, and holds a vocabulary
(`facts.KINDS`) that the copy lint reads. And `src/providers/*` is
forbidden to this branch, so a new module there could not be written here
at all - `providers/apify.py` is IMPORTED and never edited.

## WHAT IT IS FOR

A first line that says something true and checkable. `src/copylint.py`
refuses a batch whose step 1 opens without a pack fact behind it, and the
two modules agree through `fact_id`. Neither is useful alone: a pack
nobody cites is research nobody reads, and a lint with no pack to check
against can only count dashes.
"""
from .facts import KINDS, UnusableFact, fact_id, make          # noqa: F401
from .pack import PackRefused, build, run_actor                # noqa: F401
from . import actors, cache, facts, pack                       # noqa: F401

__all__ = ["build", "run_actor", "PackRefused", "KINDS", "make", "fact_id",
           "UnusableFact", "actors", "cache", "facts", "pack"]
