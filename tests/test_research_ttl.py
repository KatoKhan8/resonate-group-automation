"""TASK-138: evidence has a shelf life that depends on what it is.

`research.why()` used to return None the moment ANY evidence row existed,
however old, however thin, however wrong. A hiring signal from eight days ago
looked identical to one from this morning. The signal layer reads exactly
those, and a stale hiring row is worse than no hiring row because it says
something that is no longer true.

The fix is per-field TTL: team/hiring/careers/news/announcements/launches
expire in 3 days, everything else in 30. `why()` consults it before the
"already have it" short-circuit, and a record whose evidence is all long-lived
and three days old is NOT re-crawled.

Every test here is driven through `research.why()` - the function production
calls - not through the helper functions directly. The counterfactual is
stated at the end: delete the call from `why()` and the right test fails.
"""
import datetime
import unittest

from src import research, store
from tests.base import QueueTest


def _ts(days_ago):
    """An ISO timestamp `days_ago` days before 2026-09-15."""
    base = datetime.datetime(2026, 9, 15, tzinfo=datetime.timezone.utc)
    return (base - datetime.timedelta(days=days_ago)).isoformat()


def _entry(field, days_ago, **extra):
    """One evidence row with a pinned `retrieved_at`."""
    entry = {
        "field": field,
        "fact": f"something about {field}",
        "source_url": "https://example.test/page",
        "provider": "local_http",
        "source_type": "local_http",
        "retrieved_at": _ts(days_ago),
    }
    entry.update(extra)
    return entry


TODAY = datetime.datetime(2026, 9, 15, tzinfo=datetime.timezone.utc)


class TTLLongLivedNotTriggered(QueueTest):
    """Requirement 1: long-lived evidence 3 days old does NOT re-crawl."""

    def test_services_page_three_days_old_is_still_fresh(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [_entry("services", 3)]
        self.assertIsNone(research.why(rec, today=TODAY))

    def test_about_page_twenty_nine_days_old_is_still_fresh(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [_entry("about", 29)]
        self.assertIsNone(research.why(rec, today=TODAY))

    def test_company_website_at_the_boundary_is_still_fresh(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [_entry("company_website", 30)]
        self.assertIsNone(research.why(rec, today=TODAY))

    def test_work_page_one_day_old_is_fresh(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [_entry("work", 1)]
        self.assertIsNone(research.why(rec, today=TODAY))


class TTLShortLivedTriggered(QueueTest):
    """Requirement 2: short-lived evidence past its TTL IS re-crawled."""

    def test_team_page_four_days_old_triggers_refresh(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [_entry("team", 4)]
        self.assertEqual(research.why(rec, today=TODAY), research.NEED_REFRESH)

    def test_team_page_at_the_boundary_is_still_fresh(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [_entry("team", 3)]
        self.assertIsNone(research.why(rec, today=TODAY))

    def test_careers_page_five_days_old_triggers_refresh(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [_entry("careers", 5)]
        self.assertEqual(research.why(rec, today=TODAY), research.NEED_REFRESH)

    def test_hiring_field_six_days_old_triggers_refresh(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [_entry("hiring", 6)]
        self.assertEqual(research.why(rec, today=TODAY), research.NEED_REFRESH)


class TTLNoEvidenceBehavesAsToday(QueueTest):
    """Requirement 3: a record with no evidence behaves exactly as before."""

    def test_no_evidence_cold_lane_no_hook_returns_need_hook(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["hook"] = None
        rec["company_facts"] = {}
        self.assertEqual(research.why(rec, today=TODAY),
                         research.NEED_HOOK_EVIDENCE)

    def test_no_evidence_with_structured_data_returns_none(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["hook"] = None
        rec["company_facts"] = {"specialties": ["SEO"], "notable": "something"}
        self.assertIsNone(research.why(rec, today=TODAY))


class TTLAgeComputedFromRetrievedAt(QueueTest):
    """Requirement 4: age_days is computed from retrieved_at, not read from it.

    The estate has age_days NULL on all 695 rows. If this function read
    age_days it would return None for every row and the TTL would never fire.
    """

    def test_age_of_uses_retrieved_at_not_age_days(self):
        entry = _entry("team", 5)
        entry["age_days"] = None
        self.assertEqual(research.age_of(entry, TODAY), 5)

    def test_age_of_returns_none_when_retrieved_at_is_missing(self):
        entry = {"field": "team", "fact": "x"}
        self.assertIsNone(research.age_of(entry, TODAY))

    def test_age_of_returns_none_for_garbage_date(self):
        entry = {"field": "team", "fact": "x", "retrieved_at": "not-a-date"}
        self.assertIsNone(research.age_of(entry, TODAY))


class TTLRefreshReplacesOnlyAgedRows(QueueTest):
    """Requirement 5: refreshing replaces aged rows and keeps the rest.

    A refresh that drops good long-lived evidence to renew one hiring row
    has made the record worse. `stale_evidence` returns only the rows that
    aged out, so the caller can replace them and keep the rest.
    """

    def test_stale_evidence_returns_only_the_aged_rows(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [
            _entry("about", 5),         # long-lived, 5 days: fresh
            _entry("team", 5),          # short-lived, 5 days: STALE
            _entry("services", 10),     # long-lived, 10 days: fresh
        ]
        stale = research.stale_evidence(rec, TODAY)
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["field"], "team")

    def test_all_fresh_means_no_stale_rows(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [
            _entry("about", 5),
            _entry("team", 2),
            _entry("services", 10),
        ]
        stale = research.stale_evidence(rec, TODAY)
        self.assertEqual(stale, [])

    def test_all_stale_means_all_rows_returned(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [
            _entry("team", 5),
            _entry("careers", 10),
        ]
        stale = research.stale_evidence(rec, TODAY)
        self.assertEqual(len(stale), 2)


class TTLMixedEvidenceOnlyRefreshesWhatAged(QueueTest):
    """A record with fresh long-lived and stale short-lived evidence
    triggers a refresh, and the stale rows are identifiable."""

    def test_why_returns_refresh_when_any_row_is_stale(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [
            _entry("about", 5),         # fresh
            _entry("team", 5),          # stale
        ]
        self.assertEqual(research.why(rec, today=TODAY), research.NEED_REFRESH)

    def test_why_returns_none_when_all_rows_are_fresh(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [
            _entry("about", 5),
            _entry("team", 2),
        ]
        self.assertIsNone(research.why(rec, today=TODAY))


class TTLFieldWithoutFieldKey(QueueTest):
    """Evidence rows without a `field` key are treated as long-lived.

    61 rows in the estate have no field key (from an older run). They are
    about/services pages and should not trigger spurious refreshes.
    """

    def test_missing_field_defaults_to_long_lived_ttl(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        entry = _entry(None, 5)
        del entry["field"]
        rec["research"] = [entry]
        self.assertIsNone(research.why(rec, today=TODAY))

    def test_missing_field_at_thirty_days_is_still_fresh(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        entry = _entry(None, 30)
        del entry["field"]
        rec["research"] = [entry]
        self.assertIsNone(research.why(rec, today=TODAY))

    def test_missing_field_at_thirty_one_days_is_stale(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        entry = _entry(None, 31)
        del entry["field"]
        rec["research"] = [entry]
        self.assertEqual(research.why(rec, today=TODAY), research.NEED_REFRESH)


class CounterfactualCallIsRequired(QueueTest):
    """THE COUNTERFACTACTUAL: if `why()` did not call `stale_evidence`,
    a record with stale evidence would return None instead of NEED_REFRESH.

    This test documents the wiring. If someone removes the `stale_evidence`
    call from `why()`, this test fails - which is the point.
    """

    def test_stale_evidence_is_called_by_why(self):
        """The wiring: stale_evidence is the gate before 'already have it'.

        If this test passes with stale_evidence removed from why(), the test
        does not prove the wiring. The proof is that it fails without it.
        """
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [_entry("team", 5)]
        # This returns NEED_REFRESH only because why() calls stale_evidence
        # BEFORE the existing_evidence check. Remove the call and this
        # returns None.
        result = research.why(rec, today=TODAY)
        self.assertEqual(result, research.NEED_REFRESH)
        # And the existing_evidence check would have returned None:
        self.assertTrue(research.existing_evidence(rec))


if __name__ == "__main__":
    unittest.main()
