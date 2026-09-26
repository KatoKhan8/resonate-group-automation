"""A CTA link that does not resolve is refused.

TASK-354, operator decision 2026-09-26. Four states, none collapsing:

    200 (or 2xx)              PASS
    4xx / 5xx / DNS failure   REFUSE, rule `cta_link_dead`
    could not be checked      REFUSE, rule `cta_link_unverified`
    no link in the message    PASS

`cta_link_unverified` is its OWN rule name. A transport failure is not a
dead link. An operator seeing `cta_link_dead` will go and fix a link that
is fine.

The Productive allowlist has exactly one URL:
`https://productive.io/get-started/`. A URL that resolves but is not on the
allowlist is refused under `cta_link_not_allowed`.
"""
import unittest
from unittest import mock

from src import copylint


class ALiveLinkPasses(unittest.TestCase):
    """Acceptance 1: the real value passes."""

    def setUp(self):
        copylint.clear_link_cache()
        copylint.clear_cta_link_skip()

    def test_productive_io_get_started_passes(self):
        report = copylint.check_cta_links(
            ["https://productive.io/get-started/"])
        self.assertEqual(len(report["pass"]), 1)
        self.assertEqual(len(report["dead"]), 0)
        self.assertEqual(len(report["unverified"]), 0)
        self.assertEqual(len(report["not_allowed"]), 0)


class ADeadLinkIsRefused(unittest.TestCase):
    """Acceptance 2: a dead link REFUSEs with `cta_link_dead`.

    `productive.test` is a reserved TLD that can never resolve.
    """

    def setUp(self):
        copylint.clear_link_cache()
        copylint.clear_cta_link_skip()

    def test_reserved_tld_is_refused_as_dead(self):
        report = copylint.check_cta_links(
            ["https://productive.test/get-started/"])
        self.assertEqual(len(report["dead"]), 1,
                         "a reserved TLD must be dead, not unverified")
        self.assertEqual(len(report["unverified"]), 0,
                         "DNS failure is dead, not unverified")
        self.assertEqual(len(report["pass"]), 0)

    def test_http_404_is_dead(self):
        with mock.patch.object(copylint, "_do_resolve",
                               return_value={"status": "dead", "code": 404,
                                             "final_url": "https://x.test/"}):
            copylint.clear_link_cache()
            report = copylint.check_cta_links(["https://x.test/"])
        self.assertEqual(len(report["dead"]), 1)
        self.assertEqual(report["dead"][0]["detail"], "HTTP 404")


class AnUnreachableCheckIsUnverified(unittest.TestCase):
    """Acceptance 3: transport failure -> `cta_link_unverified`, NOT dead.

    This is the assertion that closes the task.
    """

    def setUp(self):
        copylint.clear_link_cache()
        copylint.clear_cta_link_skip()

    def test_timeout_is_unverified_not_dead(self):
        with mock.patch.object(copylint, "_do_resolve",
                               return_value={"status": "unverified",
                                             "error": "timed out",
                                             "final_url": "https://x.test/"}):
            copylint.clear_link_cache()
            report = copylint.check_cta_links(["https://x.test/"])
        self.assertEqual(len(report["unverified"]), 1,
                         "a transport failure is cta_link_unverified")
        self.assertEqual(len(report["dead"]), 0,
                         "a transport failure is NOT cta_link_dead")
        self.assertEqual(len(report["pass"]), 0,
                         "a transport failure is NOT a pass")

    def test_no_network_is_unverified(self):
        with mock.patch.object(copylint, "_do_resolve",
                               return_value={"status": "unverified",
                                             "error": "network unreachable",
                                             "final_url": "https://x.test/"}):
            copylint.clear_link_cache()
            report = copylint.check_cta_links(["https://x.test/"])
        self.assertEqual(len(report["unverified"]), 1)


class OneHeadPerDistinctUrl(unittest.TestCase):
    """Acceptance 4: one HEAD per distinct URL, not per lead.

    A 300-lead cohort shares one booking_link; that is ONE HEAD request.
    """

    def setUp(self):
        copylint.clear_link_cache()
        copylint.clear_cta_link_skip()

    def test_fifty_leads_one_request(self):
        call_count = 0
        original_resolve = copylint._do_resolve

        def counting_resolve(url, head=True):
            nonlocal call_count
            call_count += 1
            return {"status": "pass", "code": 200, "final_url": url}

        with mock.patch.object(copylint, "_do_resolve",
                               side_effect=counting_resolve):
            copylint.clear_link_cache()
            urls = ["https://productive.io/get-started/"] * 50
            copylint.check_cta_links(urls)

        self.assertEqual(call_count, 1,
                         "50 leads sharing one URL must make 1 request, "
                         "not 50. Got %d" % call_count)

    def test_two_distinct_urls_two_requests(self):
        call_count = 0

        def counting_resolve(url, head=True):
            nonlocal call_count
            call_count += 1
            return {"status": "pass", "code": 200, "final_url": url}

        with mock.patch.object(copylint, "_do_resolve",
                               side_effect=counting_resolve):
            copylint.clear_link_cache()
            urls = (["https://productive.io/get-started/"] * 25 +
                    ["https://productive.io/"] * 25)
            copylint.check_cta_links(urls)

        self.assertEqual(call_count, 2)


class TheAllowlistRefusesNonAllowedUrls(unittest.TestCase):
    """Acceptance addition: book-a-demo is REFUSED despite resolving.

    Resolving is not sufficient; it must be the one allowed URL.
    """

    def setUp(self):
        copylint.clear_link_cache()
        copylint.clear_cta_link_skip()

    def test_book_a_demo_is_refused(self):
        with mock.patch.object(copylint, "_do_resolve",
                               return_value={"status": "pass", "code": 200,
                                             "final_url": "https://productive.io/book-a-demo/"}):
            copylint.clear_link_cache()
            report = copylint.check_cta_links(
                ["https://productive.io/book-a-demo/"])
        self.assertEqual(len(report["not_allowed"]), 1,
                         "book-a-demo resolves but is NOT the allowed URL")
        self.assertEqual(len(report["pass"]), 0)

    def test_get_started_is_allowed(self):
        with mock.patch.object(copylint, "_do_resolve",
                               return_value={"status": "pass", "code": 200,
                                             "final_url": "https://productive.io/get-started/"}):
            copylint.clear_link_cache()
            report = copylint.check_cta_links(
                ["https://productive.io/get-started/"])
        self.assertEqual(len(report["pass"]), 1)
        self.assertEqual(len(report["not_allowed"]), 0)


class TheOfflineOptOut(unittest.TestCase):
    """An explicit, loud opt-out - not a silent default."""

    def setUp(self):
        copylint.clear_link_cache()
        copylint.clear_cta_link_skip()

    def tearDown(self):
        copylint.clear_cta_link_skip()

    def test_skip_is_visible_in_result(self):
        copylint.skip_cta_link_check("offline run, no network")
        report = copylint.check_cta_links(
            ["https://productive.io/get-started/"])
        self.assertIn("skipped", report)
        self.assertEqual(report["skipped"], "offline run, no network")

    def test_default_is_not_skipped(self):
        self.assertIsNone(copylint.CTA_LINK_SKIP_REASON)

    def test_skip_appears_in_report_lines(self):
        copylint.skip_cta_link_check("offline test")
        lines = copylint.cta_link_report(
            ["https://productive.io/get-started/"])
        self.assertTrue(any("SKIPPED" in line for line in lines))


class NoLinkIsNotADefect(unittest.TestCase):
    """A message with no CTA link is not a defect."""

    def test_empty_url_list_passes(self):
        report = copylint.check_cta_links([])
        self.assertEqual(len(report["pass"]), 0)
        self.assertEqual(len(report["dead"]), 0)
        self.assertEqual(len(report["unverified"]), 0)
        self.assertEqual(len(report["not_allowed"]), 0)


class UrlExtraction(unittest.TestCase):
    """URLs are extracted from rendered copy correctly."""

    def test_extracts_http_and_https(self):
        text = ("Visit https://productive.io/get-started/ or "
                "http://example.com/page for details.")
        urls = copylint.extract_urls(text)
        self.assertIn("https://productive.io/get-started/", urls)
        self.assertIn("http://example.com/page", urls)

    def test_no_urls_returns_empty(self):
        self.assertEqual(copylint.extract_urls("no links here"), [])

    def test_deduplicates(self):
        text = ("https://productive.io/get-started/ and "
                "https://productive.io/get-started/")
        urls = copylint.extract_urls(text)
        self.assertEqual(len(urls), 1)


class HeadFallbackToGet(unittest.TestCase):
    """Some hosts refuse HEAD. Fall back to GET, do not record 405 as dead."""

    def setUp(self):
        copylint.clear_link_cache()
        copylint.clear_cta_link_skip()

    def test_405_on_head_falls_back_to_get(self):
        import urllib.error
        calls = []

        def mock_urlopen(req, timeout=None):
            calls.append(req.get_method())
            if req.get_method() == "HEAD":
                raise urllib.error.HTTPError(
                    req.full_url, 405, "Method Not Allowed", {}, None)
            class FakeResp:
                def getcode(self): return 200
                def geturl(self): return req.full_url
            return FakeResp()

        with mock.patch("urllib.request.urlopen", side_effect=mock_urlopen):
            copylint.clear_link_cache()
            result = copylint._do_resolve("https://stubborn.example.com/")

        self.assertEqual(result["status"], "pass")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], "HEAD")
        self.assertEqual(calls[1], "GET")


if __name__ == "__main__":
    unittest.main()
