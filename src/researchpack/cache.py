"""A 30-day research cache, keyed by DOMAIN AND PROFILE.

Operator, 2026-09-24. Two keys and not one, because the pack is assembled
per account but the expensive parts are per person: a champion's posts and
an exec's posts are separate actor runs against separate profiles, and one
account whose champion changed must not re-buy the exec.

NEVER PERSISTED OUTSIDE `work/`, and it asks `refuse_production_write`
before it writes. `spendledger` carries a comment about being outside that
barrier and writing 19 rows of fabricated spend into the operator's real
ledger from a test; a cache that records what has already been paid for is
the same hazard with a quieter symptom - a test run that "warms" it makes
the next real run skip a call it never actually made.
"""
import json
import os

from .. import evidence, store

TTL_DAYS = 30

CACHE_VAR = "RESEARCH_PACK_CACHE"
CACHE_NAME = "research-pack-cache.json"


def path():
    override = (os.environ.get(CACHE_VAR) or "").strip()
    if override:
        return os.path.abspath(override)
    return os.path.join(os.path.dirname(store.queue_path()), CACHE_NAME)


def key_for(domain, profile=None):
    """`domain` alone for company-level work, `domain::profile` for a person.

    Lower-cased, because a cache that misses on capitalisation buys the
    same actor run twice and reports it as two accounts' worth of cost.
    """
    domain = str(domain or "").strip().lower().lstrip("@")
    if not domain:
        raise ValueError("a research cache key needs a domain")
    profile = str(profile or "").strip().lower()
    return "%s::%s" % (domain, profile) if profile else domain


def load():
    try:
        with open(path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _fresh(entry, now=None):
    """Age is computed from `retrieved_at`, which is always written here.

    `research.age_of` carries the reason in full: the estate's `age_days`
    column is NULL on every row because nothing ever wrote it, and a TTL
    read off a field nobody populates never fires. This module writes
    `retrieved_at` on every `put` and reads the same field back.
    """
    at = str((entry or {}).get("retrieved_at") or "")[:10]
    if not at:
        return False
    days = evidence.days_between(at, (now or store.now())[:10])
    return days is not None and days < TTL_DAYS


def get(domain, profile=None, now=None, data=None):
    """The cached entry, or None. Expiry is checked on READ.

    On read rather than by sweeping: a sweep is a second process that has
    to be remembered, and a stale entry nobody swept is indistinguishable
    from a fresh one at the call site that matters.
    """
    entry = (load() if data is None else data).get(key_for(domain, profile))
    if not entry or not _fresh(entry, now):
        return None
    return entry


def put(domain, facts, profile=None, cost=0, now=None):
    """Record a completed lookup. Returns the entry written."""
    target = path()
    store.refuse_production_write(target)
    data = load()
    entry = {"domain": str(domain).strip().lower(),
             "profile": profile or None,
             "retrieved_at": now or store.now(),
             "facts": list(facts or []),
             "cost": int(cost or 0)}
    data[key_for(domain, profile)] = entry
    tmp = target + ".tmp"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, default=str)
    os.replace(tmp, target)
    return entry
