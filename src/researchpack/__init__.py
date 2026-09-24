"""Research packs: what is true about an account, with a source for each.

Operator, 2026-09-24, lane 1: research packs on every lead, on four
sources, from Apify actors that need no LinkedIn session.

    from src import researchpack
    pack = researchpack.build("acme.test")                  # cache only
    pack = researchpack.build("acme.test", live=True,       # buys runs
                              company="Acme Ltd")

The four are `open_roles`, `company_posts`, `person_posts` for a champion
and an exec, and `site_content` - the company's own site, through the
crawler this repository already had. `actors.py` says what each one costs
and where its id was verified; `docs/RESEARCH-PACK-PILOT-2026-09-24.md`
says what each one actually covered over 25 real accounts.

## WHY IT IS NOT UNDER `src/providers/`

It is not a provider: it composes several, caches across them, and holds a
vocabulary (`facts.KINDS`) that the copy lint reads.

The second reason this docstring used to give - that `src/providers/*` was
forbidden to the branch this was written on - has expired. The branch was
merged, and adding LinkedIn actors needed `providers/apify.check_url` to
allow a host off the record's own domain. That widening was made THERE,
where the rest of the URL guard lives, rather than worked around here: see
`providers.apify.RESEARCH_HOSTS`. A second URL check in this package would
have been the drift the original note was trying to avoid.

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
