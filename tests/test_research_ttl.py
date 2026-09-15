#!/usr/bin/env python3
"""Evidence has a shelf life that depends on what it is.

TASK-138: `why()` used to return None the moment any evidence row existed,
however old. Three days is tolerable for "this company builds software for
agencies". It is NOT tolerable for a hiring signal, and the signal layer
reads exactly those.

The TTL depends on the field:
  LONG-LIVED (30 days): company_website, about, team
  SHORT-LIVED (7 days): careers, blog, news

Tests are driven through `research.why()` - the function production calls -
not through the helper functions directly. The counterfactual is proven:
delete the call from `why()`, and the right test fails.
"""
import datetime
import unittest

from src import research
from tests.base import QueueTest


class TTLLongLivedNotRecrawled(QueueTest):
    """A record whose evidence is all long-lived and 3 days old is NOT
    re-crawled."""

    def test_long_lived_evidence_three_days_old_is_fresh(self):
        rec = self._record_with_evidence(
            field="company_website",
            retrieved_at="2026-09-12T10:00:00Z",
        )
        today = datetime.date(2026, 9, 15)
        self.assertIsNone(research.why(rec, today=today))

    def test_about_page_three_days_old_is_fresh(self):
        rec = self._record_with_evidence(
            field="about",
            retrieved_at="2026-09-12T10:00:00Z",
        )
        today = datetime.date(2026, 9, 15)
        self.assertIsNone(research.why(rec, today=today))

    def test_team_page_three_days_old_is_fresh(self):
        rec = self._record_with_evidence(
            field="team",
            retrieved_at="2026-09-12T10:00:00Z",
        )
        today = datetime.date(2026, 9, 15)
        self.assertIsNone(research.why(rec, today=today))

    def test_long_lived_evidence_twenty_nine_days_old_is_still_fresh(self):
        rec = self._record_with_evidence(
            field="company_website",
            retrieved_at="2026-08-17T10:00:00Z",
        )
        today = datetime.date(2026, 9, 15)
        self.assertIsNone(research.why(rec, today=today))

    def _record_with_evidence(self, field, retrieved_at):
        rec = {
            "id": "test-record",
            "domain": "acme.test",
            "lane": "cold",
            "hook": "some hook",
            "company_facts": {"specialties": ["SEO"]},
            "research": [{
                "field": field,
                "fact": "Acme is a software company.",
                "source_url": "https://acme.test/about",
                "retrieved_at": retrieved_at,
                "provider": "apify",
            }],
        }
        return rec


class TTLShortLivedRecrawled(QueueTest):
    """A record carrying a hiring or announcement row older than that type's
    life IS re-crawled, and `why()` says so."""

    def test_careers_page_eight_days_old_triggers_refresh(self):
        rec = self._record_with_evidence(
            field="careers",
            retrieved_at="2026-09-07T10:00:00Z",
        )
        today = datetime.date(2026, 9, 15)
        self.assertEqual(research.why(rec, today=today),
                         research.NEED_REFRESH_EVIDENCE)

    def test_news_page_eight_days_old_triggers_refresh(self):
        rec = self._record_with_evidence(
            field="news",
            retrieved_at="2026-09-07T10:00:00Z",
        )
        today = datetime.date(2026, 9, 15)
        self.assertEqual(research.why(rec, today=today),
                         research.NEED_REFRESH_EVIDENCE)

    def test_blog_page_eight_days_old_triggers_refresh(self):
        rec = self._record_with_evidence(
            field="blog",
            retrieved_at="2026-09-07T10:00:00Z",
        )
        today = datetime.date(2026, 9, 15)
        self.assertEqual(research.why(rec, today=today),
                         research.NEED_REFRESH_EVIDENCE)

    def test_careers_page_six_days_old_is_still_fresh(self):
        rec = self._record_with_evidence(
            field="careers",
            retrieved_at="2026-09-09T10:00:00Z",
        )
        today = datetime.date(2026, 9, 15)
        self.assertIsNone(research.why(rec, today=today))

    def _record_with_evidence(self, field, retrieved_at):
        rec = {
            "id": "test-record",
            "domain": "acme.test",
            "lane": "cold",
            "hook": "some hook",
            "company_facts": {"specialties": ["SEO"]},
            "research": [{
                "field": field,
                "fact": "Acme is hiring delivery managers.",
                "source_url": "https://acme.test/careers",
                "retrieved_at": retrieved_at,
                "provider": "apify",
            }],
        }
        return rec


class TTLMixedEvidence(QueueTest):
    """A record with both fresh long-lived and stale short-lived evidence
    is re-crawled for the stale part only."""

    def test_mixed_fresh_and_stale_triggers_refresh(self):
        rec = {
            "id": "test-record",
            "domain": "acme.test",
            "lane": "cold",
            "hook": "some hook",
            "company_facts": {"specialties": ["SEO"]},
            "research": [
                {
                    "field": "about",
                    "fact": "Acme is a software company.",
                    "source_url": "https://acme.test/about",
                    "retrieved_at": "2026-09-12T10:00:00Z",  # 3 days old, fresh
                    "provider": "apify",
                },
                {
                    "field": "careers",
                    "fact": "Acme is hiring.",
                    "source_url": "https://acme.test/careers",
                    "retrieved_at": "2026-09-01T10:00:00Z",  # 14 days old, stale
                    "provider": "apify",
                },
            ],
        }
        today = datetime.date(2026, 9, 15)
        self.assertEqual(research.why(rec, today=today),
                         research.NEED_REFRESH_EVIDENCE)

    def test_aged_out_entries_returns_only_stale_rows(self):
        rec = {
            "id": "test-record",
            "research": [
                {
                    "field": "about",
                    "retrieved_at": "2026-09-12T10:00:00Z",  # fresh
                },
                {
                    "field": "careers",
                    "retrieved_at": "2026-09-01T10:00:00Z",  # stale
                },
            ],
        }
        today = datetime.date(2026, 9, 15)
        stale = research.aged_out_entries(rec, today=today)
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["field"], "careers")


class AgeOfEntryComputedFromRetrievedAt(QueueTest):
    """`age_days` is COMPUTED from `retrieved_at` rather than read from the
    NULL column. A field nothing writes is not a source of truth."""

    def test_age_computed_from_retrieved_at(self):
        entry = {
            "retrieved_at": "2026-09-10T10:00:00Z",
            "age_days": None,  # stored field is NULL
        }
        today = datetime.date(2026, 9, 15)
        self.assertEqual(research.age_of_entry(entry, today=today), 5)

    def test_age_returns_none_when_no_retrieved_at(self):
        entry = {"retrieved_at": None}
        self.assertIsNone(research.age_of_entry(entry))

    def test_age_handles_datetime_objects(self):
        entry = {
            "retrieved_at": datetime.datetime(2026, 9, 10, 10, 0, 0),
        }
        today = datetime.date(2026, 9, 15)
        self.assertEqual(research.age_of_entry(entry, today=today), 5)


class ForPromptIncludesComputedAge(QueueTest):
    """Something reads the computed `age_days`. `for_prompt` is the consumer
    that passes evidence to the model, and it now includes the computed age."""

    def test_for_prompt_includes_age_days(self):
        rec = {
            "id": "test-record",
            "research": [{
                "field": "about",
                "fact": "Acme is a software company.",
                "source_url": "https://acme.test/about",
                "retrieved_at": "2026-09-10T10:00:00Z",
            }],
        }
        today = datetime.date(2026, 9, 15)
        result = research.for_prompt(rec, today=today)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["age_days"], 5)


class NoEvidenceBehavesAsBefore(QueueTest):
    """A record with no evidence behaves exactly as it does today."""

    def test_no_evidence_cold_lane_no_hook_returns_need(self):
        rec = {
            "id": "test-record",
            "domain": "acme.test",
            "lane": "cold",
            "hook": None,
            "company_facts": {},
            "research": [],
        }
        self.assertEqual(research.why(rec), research.NEED_HOOK_EVIDENCE)

    def test_no_evidence_with_structured_data_returns_none(self):
        rec = {
            "id": "test-record",
            "domain": "acme.test",
            "lane": "cold",
            "hook": None,
            "company_facts": {"specialties": ["SEO"], "notable": "something"},
            "research": [],
        }
        self.assertIsNone(research.why(rec))


class TTLForField(QueueTest):
    """The TTL classification comes from the evidence row's own `field`."""

    def test_careers_is_short_lived(self):
        self.assertEqual(research.ttl_for_field("careers"),
                         research.SHORT_LIVED_TTL_DAYS)

    def test_blog_is_short_lived(self):
        self.assertEqual(research.ttl_for_field("blog"),
                         research.SHORT_LIVED_TTL_DAYS)

    def test_news_is_short_lived(self):
        self.assertEqual(research.ttl_for_field("news"),
                         research.SHORT_LIVED_TTL_DAYS)

    def test_company_website_is_long_lived(self):
        self.assertEqual(research.ttl_for_field("company_website"),
                         research.LONG_LIVED_TTL_DAYS)

    def test_about_is_long_lived(self):
        self.assertEqual(research.ttl_for_field("about"),
                         research.LONG_LIVED_TTL_DAYS)

    def test_team_is_long_lived(self):
        self.assertEqual(research.ttl_for_field("team"),
                         research.LONG_LIVED_TTL_DAYS)

    def test_unknown_field_falls_to_long_lived(self):
        # An unrecognised field defaults to long-lived, not short-lived.
        # This is conservative: we don't want to re-crawl unnecessarily.
        self.assertEqual(research.ttl_for_field("unknown_field"),
                         research.LONG_LIVED_TTL_DAYS)


if __name__ == "__main__":
    unittest.main()
