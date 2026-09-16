"""TASK-208: company-level crawl cache.

One crawl per company per pass, reused across every contact on that company.
Pass-scoped: cleared at the start of each `enrich.run()` pass.

Counterfactual tests (modelled on TASK-162):
- N contacts on one company produce ONE crawl.
- A cleared cache produces N.
"""
import unittest
from unittest.mock import patch, MagicMock

from src import research, store


def _make_record(id, domain):
    return {"id": id, "domain": domain, "research": [], "events": [],
            "log": []}


def _fake_research(domain, config):
    """A webfetch.research fake that returns usable pages."""
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


class TestCompanyLevelCrawlCache(unittest.TestCase):

    def setUp(self):
        research.crawl_cache_clear()

    def tearDown(self):
        research.crawl_cache_clear()

    @patch("src.webfetch.research", side_effect=_fake_research)
    def test_n_contacts_on_one_company_produce_one_crawl(self, mock_research):
        """N records on the same domain: webfetch.research called ONCE."""
        rec1 = _make_record("acme-1", "acme.com")
        rec2 = _make_record("acme-2", "acme.com")
        rec3 = _make_record("acme-3", "acme.com")

        r1 = research._from_the_site_itself(rec1, {})
        r2 = research._from_the_site_itself(rec2, {})
        r3 = research._from_the_site_itself(rec3, {})

        self.assertIsNotNone(r1, "first contact should get evidence")
        self.assertIsNotNone(r2, "second contact should get cached evidence")
        self.assertIsNotNone(r3, "third contact should get cached evidence")
        self.assertEqual(len(r1), 1)
        self.assertEqual(len(r2), 1)
        self.assertEqual(len(r3), 1)
        self.assertEqual(mock_research.call_count, 1,
                         "three contacts on one domain should produce ONE "
                         "crawl, not three")

    @patch("src.webfetch.research", side_effect=_fake_research)
    def test_cleared_cache_produces_n_crawls(self, mock_research):
        """After clearing the cache, each record triggers its own crawl."""
        rec1 = _make_record("acme-1", "acme.com")
        research._from_the_site_itself(rec1, {})
        self.assertEqual(mock_research.call_count, 1)

        research.crawl_cache_clear()

        rec2 = _make_record("acme-2", "acme.com")
        research._from_the_site_itself(rec2, {})
        self.assertEqual(mock_research.call_count, 2,
                         "after clearing the cache, a second crawl should "
                         "occur for the same domain")

    @patch("src.webfetch.research", side_effect=_fake_research)
    def test_cache_preserves_provenance(self, mock_research):
        """Cached evidence retains source_url, content_hash, retrieved_at."""
        rec1 = _make_record("acme-1", "acme.com")
        r1 = research._from_the_site_itself(rec1, {})
        rec2 = _make_record("acme-2", "acme.com")
        r2 = research._from_the_site_itself(rec2, {})

        self.assertEqual(r1[0]["source_url"], "https://acme.com/about")
        self.assertEqual(r2[0]["source_url"], "https://acme.com/about")
        self.assertEqual(r1[0]["content_hash"], "abc123")
        self.assertEqual(r2[0]["content_hash"], "abc123")
        self.assertEqual(r1[0]["retrieved_at"], "2026-09-16T10:00:00+00:00")
        self.assertEqual(r2[0]["retrieved_at"], "2026-09-16T10:00:00+00:00")

    @patch("src.webfetch.research", side_effect=_fake_research)
    def test_cache_preserves_record_id_per_contact(self, mock_research):
        """Each contact gets its own record_id, even from cache."""
        rec1 = _make_record("acme-1", "acme.com")
        rec2 = _make_record("acme-2", "acme.com")
        r1 = research._from_the_site_itself(rec1, {})
        r2 = research._from_the_site_itself(rec2, {})

        self.assertEqual(r1[0]["record_id"], "acme-1")
        self.assertEqual(r2[0]["record_id"], "acme-2")

    def test_cache_is_pass_scoped(self):
        """crawl_cache_clear empties the cache completely."""
        research.crawl_cache_set("acme.com", [{"field": "about"}])
        self.assertIsNotNone(research.crawl_cache_get("acme.com"))
        research.crawl_cache_clear()
        self.assertIsNone(research.crawl_cache_get("acme.com"))

    @patch("src.webfetch.research", side_effect=_fake_research)
    def test_different_domains_are_independent(self, mock_research):
        """Different domains have separate cache entries."""
        rec1 = _make_record("acme-1", "acme.com")
        rec2 = _make_record("beta-1", "beta.com")
        research._from_the_site_itself(rec1, {})
        research._from_the_site_itself(rec2, {})

        self.assertEqual(mock_research.call_count, 2,
                         "different domains should each trigger a crawl")

    @patch("src.webfetch.research",
           return_value={"outcome": "HTTP_INSUFFICIENT", "pages": []})
    def test_failed_crawl_is_not_cached(self, mock_research):
        """A crawl that returns no usable pages is not cached."""
        rec1 = _make_record("acme-1", "acme.com")
        result = research._from_the_site_itself(rec1, {})
        self.assertIsNone(result)
        self.assertIsNone(research.crawl_cache_get("acme.com"),
                          "a failed crawl should not populate the cache")


if __name__ == "__main__":
    unittest.main()
