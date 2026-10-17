"""Shared fixture date for tests that exercise the crawl-cache staleness path.

Evidence rows in crawl-cache fixtures carry `retrieved_at` dates anchored to a
specific day (normally 2026-09-16). Because `research.crawl_cache_get` computes
age from `datetime.datetime.now(utc)`, any run more than LONG_LIVED_DAYS=30 days
after that anchor sees the entry as stale, triggering an unwanted re-crawl that
breaks the assertion counters.

This module provides a small helper that patches
``research.crawl_cache_get`` to always supply ``today`` against the chosen
fixture date, keeping the production code untouched.

Authorised callers pin ``_FIXTURE_TODAY = datetime(...)`` and invoke
``freeze_crawl_cache_get`` / ``thaw_crawl_cache_get`` from setUp / tearDown.
"""
import datetime

_original_crawl_cache_get = None


#: When overridden, must be a timezone-aware datetime matching the fixture's
#: ``retrieved_at`` anchor (e.g. 2026-09-16T00:00:00+00:00).
_FIXTURE_TODAY = None


def freeze(today=None):
    """Wrap ``research.crawl_cache_get`` to inject ``today``.

    Usage (in a test setUp)::

        self._freeze = freeze.freeze(_FIXTURE_TODAY)
        self.addCleanup(freeze.thaw)

    *today* defaults to 2026-09-16 if omitted.
    """
    global _original_crawl_cache_get, _FIXTURE_TODAY
    import src.research as research
    if today is None:
        today = datetime.datetime(2026, 9, 16, tzinfo=datetime.timezone.utc)
    _FIXTURE_TODAY = today
    _original_crawl_cache_get = research.crawl_cache_get

    def patched(domain, **kwargs):
        # If another layer already set today (e.g. stale_entry_triggers_crawl's
        # own patch), honour it. Otherwise supply the fixture date.
        if "today" not in kwargs:
            kwargs["today"] = today
        return _original_crawl_cache_get(domain, **kwargs)

    research.crawl_cache_get = patched
    return patched


def thaw():
    """Restore the original ``crawl_cache_get``. Call from tearDown."""
    global _original_crawl_cache_get
    if _original_crawl_cache_get is not None:
        import src.research as research
        research.crawl_cache_get = _original_crawl_cache_get
        _original_crawl_cache_get = None
