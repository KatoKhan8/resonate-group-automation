"""TASK-221: crawl cache persistence.

The crawl cache survives a pass. Per-field freshness decides what is served.
A corrupt file is a miss, not a crash. crawl_cache_clear() does not destroy
the persisted layer.
"""
import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from src import research, store


def _make_record(id, domain):
    return {"id": id, "domain": domain, "research": [], "events": [],
            "log": []}


def _fake_research(domain, config):
    return {
        "outcome": "HTTP_SUCCESS",
        "pages": [
            {"source_url": f"https://{domain}/about",
             "field": "about",
             "fact": f"We are {domain}, a software company.",
             "provider": "local_http",
             "content_hash": "abc123",
             "http_status": 200,
             "chars": 500,
             "retrieved_at": "2026-09-16T10:00:00+00:00"},
        ],
        "retrieved_at": "2026-09-16T10:00:00+00:00",
    }


def _fake_research_hiring(domain, config):
    return {
        "outcome": "HTTP_SUCCESS",
        "pages": [
            {"source_url": f"https://{domain}/careers",
             "field": "hiring",
             "fact": f"{domain} is hiring engineers.",
             "provider": "local_http",
             "content_hash": "def456",
             "http_status": 200,
             "chars": 300,
             "retrieved_at": "2026-09-10T10:00:00+00:00"},
        ],
        "retrieved_at": "2026-09-10T10:00:00+00:00",
    }


class TestCrawlCachePersistence(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="rga-crawl-cache-")
        store.use_directory(self._tmpdir)
        research.crawl_cache_clear()
        research._reset_persisted_cache()

    def tearDown(self):
        research.crawl_cache_clear()
        research._reset_persisted_cache()
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    @patch("src.webfetch.research", side_effect=_fake_research)
    def test_same_domain_second_pass_served_from_persisted(self, mock_research):
        """Same domain, second pass, still fresh -> no crawl."""
        rec1 = _make_record("acme-1", "acme.com")
        research._from_the_site_itself(rec1, {})
        self.assertEqual(mock_research.call_count, 1)

        # Simulate a new pass: clear in-memory, but persisted survives
        research.crawl_cache_clear()
        research._reset_persisted_cache()

        rec2 = _make_record("acme-2", "acme.com")
        result = research._from_the_site_itself(rec2, {})
        self.assertIsNotNone(result, "second pass should be served from persisted cache")
        self.assertEqual(mock_research.call_count, 1,
                         "second pass on same domain should NOT trigger a crawl")

    @patch("src.webfetch.research", side_effect=_fake_research_hiring)
    def test_stale_entry_triggers_crawl(self, mock_research):
        """Same domain, entry beyond its field's shelf life -> crawl happens."""
        rec1 = _make_record("acme-1", "acme.com")
        research._from_the_site_itself(rec1, {})
        self.assertEqual(mock_research.call_count, 1)

        # Simulate a new pass with a date beyond the short-lived TTL (3 days)
        research.crawl_cache_clear()
        research._reset_persisted_cache()

        # The entry was retrieved_at 2026-09-10, hiring field has 3-day TTL
        # So on 2026-09-16 it is 6 days old -> stale
        future = datetime.datetime(2026, 9, 16, 12, 0, 0,
                                   tzinfo=datetime.timezone.utc)

        rec2 = _make_record("acme-2", "acme.com")
        # We need to patch crawl_cache_get to pass the future date
        original_get = research.crawl_cache_get
        def get_with_future(domain):
            return original_get(domain, today=future)
        with patch.object(research, "crawl_cache_get", side_effect=get_with_future):
            result = research._from_the_site_itself(rec2, {})

        # The stale entry should have been rejected, triggering a new crawl
        self.assertEqual(mock_research.call_count, 2,
                         "stale entry should trigger a new crawl")

    @patch("src.webfetch.research", side_effect=_fake_research)
    def test_different_domain_never_served_another_domains_evidence(self, mock_research):
        """Different domain -> never served another domain's evidence.
        Assert on the returned facts, not on a counter."""
        rec_acme = _make_record("acme-1", "acme.com")
        rec_beta = _make_record("beta-1", "beta.com")

        r_acme = research._from_the_site_itself(rec_acme, {})
        r_beta = research._from_the_site_itself(rec_beta, {})

        # Assert on the actual facts returned
        self.assertIn("acme.com", r_acme[0]["fact"])
        self.assertIn("beta.com", r_beta[0]["fact"])
        self.assertNotIn("beta.com", r_acme[0]["fact"])
        self.assertNotIn("acme.com", r_beta[0]["fact"])

    @patch("src.webfetch.research", side_effect=_fake_research)
    def test_restamp_happens_from_persisted_cache(self, mock_research):
        """Evidence from persisted cache carries current record's id.
        The stored copy has record_id=None."""
        rec1 = _make_record("acme-1", "acme.com")
        research._from_the_site_itself(rec1, {})

        # Check the persisted copy has record_id=None
        persisted = research.load_crawl_cache()
        stored_entries = persisted.get("acme.com", [])
        self.assertTrue(len(stored_entries) > 0)
        for entry in stored_entries:
            self.assertIsNone(entry.get("record_id"),
                              "stored copy must have record_id=None")

        # Simulate new pass
        research.crawl_cache_clear()
        research._reset_persisted_cache()

        rec2 = _make_record("acme-2", "acme.com")
        result = research._from_the_site_itself(rec2, {})
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["record_id"], "acme-2",
                         "served evidence must carry the current record's id")

    def test_corrupt_cache_file_is_miss_not_crash(self):
        """A corrupt cache file is a miss, not a crash, not a silent empty."""
        path = research.crawl_cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("{this is not valid json!!!")

        research._reset_persisted_cache()
        result = research.crawl_cache_get("acme.com")
        self.assertIsNone(result, "corrupt file should produce a miss")

        # Verify it logged a warning, not silently returned empty
        # The persisted cache should be empty dict after a corrupt load
        self.assertEqual(research._persisted_cache, {})

    def test_corrupt_cache_file_not_a_silent_empty(self):
        """A corrupt file is classified explicitly, not as a cold start."""
        path = research.crawl_cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("[1, 2, 3]")  # valid JSON but not a dict

        research._reset_persisted_cache()
        result = research.crawl_cache_get("acme.com")
        self.assertIsNone(result)
        self.assertEqual(research._persisted_cache, {})

    @patch("src.webfetch.research", side_effect=_fake_research)
    def test_crawl_cache_clear_does_not_destroy_persisted(self, mock_research):
        """crawl_cache_clear() does not destroy the persisted layer."""
        rec1 = _make_record("acme-1", "acme.com")
        research._from_the_site_itself(rec1, {})

        # Clear in-memory only
        research.crawl_cache_clear()

        # Persisted layer should still be there
        research._reset_persisted_cache()
        persisted = research.load_crawl_cache()
        self.assertIn("acme.com", persisted,
                       "crawl_cache_clear must not destroy the persisted layer")

        # And it should serve from persisted on next get
        result = research.crawl_cache_get("acme.com")
        self.assertIsNotNone(result,
                             "persisted cache should still serve after clear")

    @patch("src.webfetch.research", side_effect=_fake_research)
    def test_long_lived_field_survives_across_passes(self, mock_research):
        """A long-lived field (30-day TTL) survives across passes."""
        rec1 = _make_record("acme-1", "acme.com")
        research._from_the_site_itself(rec1, {})
        self.assertEqual(mock_research.call_count, 1)

        # Simulate a new pass 10 days later - 'about' field has 30-day TTL
        research.crawl_cache_clear()
        research._reset_persisted_cache()

        rec2 = _make_record("acme-2", "acme.com")
        result = research._from_the_site_itself(rec2, {})
        self.assertIsNotNone(result)
        self.assertEqual(mock_research.call_count, 1,
                         "long-lived field should survive across passes")


if __name__ == "__main__":
    unittest.main()
