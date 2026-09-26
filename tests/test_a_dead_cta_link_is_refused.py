"""TASK-354: a CTA link that does not resolve is refused.

Four states, none may collapse:

    200 (or 2xx)              PASS
    4xx/5xx/DNS failure       REFUSE, rule ``cta_link_dead``
    could not be checked      REFUSE, rule ``cta_link_unverified``
    no link in the message    PASS

The allowlist is exactly one URL: ``https://productive.io/get-started/``.
Any other prospect-facing URL is refused as ``cta_link_not_allowlisted``
regardless of whether it resolves.

THE PRODUCTION PATH, NOT A DIRECT CALL. The acceptance tests drive the
lint through ``check_batch``, the function ``bisonfactory._refuse_copylint``
already calls. A test that calls ``check_cta_links`` directly proves the
function but not the wiring; CLAUDE.md §4: existence is not function.
"""
import unittest

from src import copylint


class ExtractUrlsTests(unittest.TestCase):
    """URL extraction from rendered copy."""

    def test_no_urls_returns_empty(self):
        self.assertEqual(copylint.extract_urls("hello world"), [])

    def test_one_url(self):
        urls = copylint.extract_urls(
            "book here: https://productive.io/get-started/")
        self.assertEqual(urls, ["https://productive.io/get-started/"])

    def test_strips_trailing_period(self):
        urls = copylint.extract_urls(
            "see https://productive.io/get-started/. thanks")
        self.assertEqual(urls, ["https://productive.io/get-started/"])

    def test_deduplicates(self):
        text = ("https://productive.io/get-started/ and "
                "https://productive.io/get-started/")
        urls = copylint.extract_urls(text)
        self.assertEqual(len(urls), 1)


class AllowlistTests(unittest.TestCase):
    """The allowlist is exactly one URL. Anything else is refused."""

    ALLOWED = "https://productive.io/get-started/"

    def test_allowlisted_url_passes(self):
        result = copylint.check_cta_links([self.ALLOWED], resolve=False)
        self.assertEqual(result["not_allowlisted"], [])
        self.assertEqual(result["dead"], [])
        self.assertEqual(result["unverified"], [])
        self.assertIn(self.ALLOWED, result["allowlisted"])

    def test_book_a_demo_refused_despite_resolving(self):
        """book-a-demo returns HEAD 200 but is NOT the allowed URL."""
        url = "https://productive.io/book-a-demo/"
        result = copylint.check_cta_links([url], resolve=False)
        self.assertIn(url, result["not_allowlisted"])
        self.assertEqual(result["allowlisted"], [])

    def test_webflow_refused(self):
        url = "https://productive-web.webflow.io/something"
        result = copylint.check_cta_links([url], resolve=False)
        self.assertIn(url, result["not_allowlisted"])

    def test_reserved_tld_refused(self):
        url = "https://productive.test/get-started/"
        result = copylint.check_cta_links([url], resolve=False)
        self.assertIn(url, result["not_allowlisted"])


class _FakeResolver:
    """A test resolver that returns canned results per URL."""

    def __init__(self, results):
        self._results = results
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        return self._results.get(url, "dead")


class ResolutionTests(unittest.TestCase):
    """HEAD/GET resolution for allowlisted URLs."""

    ALLOWED = "https://productive.io/get-started/"

    def test_dead_allowlisted_url_refused_as_dead(self):
        old = copylint._URL_RESOLVE_HOOK
        try:
            copylint._URL_RESOLVE_HOOK = _FakeResolver({self.ALLOWED: "dead"})
            result = copylint.check_cta_links([self.ALLOWED], resolve=True)
            self.assertIn(self.ALLOWED, result["dead"])
            self.assertEqual(result["allowlisted"], [])
        finally:
            copylint._URL_RESOLVE_HOOK = old

    def test_unverified_allowlisted_url_refused_as_unverified(self):
        old = copylint._URL_RESOLVE_HOOK
        try:
            copylint._URL_RESOLVE_HOOK = _FakeResolver(
                {self.ALLOWED: "unverified"})
            result = copylint.check_cta_links([self.ALLOWED], resolve=True)
            self.assertIn(self.ALLOWED, result["unverified"])
            self.assertEqual(result["dead"], [])
            self.assertEqual(result["allowlisted"], [])
        finally:
            copylint._URL_RESOLVE_HOOK = old

    def test_pass_allowlisted_url_accepted(self):
        old = copylint._URL_RESOLVE_HOOK
        try:
            copylint._URL_RESOLVE_HOOK = _FakeResolver({self.ALLOWED: "pass"})
            result = copylint.check_cta_links([self.ALLOWED], resolve=True)
            self.assertIn(self.ALLOWED, result["allowlisted"])
            self.assertEqual(result["dead"], [])
        finally:
            copylint._URL_RESOLVE_HOOK = old


class CacheTests(unittest.TestCase):
    """One resolution per distinct URL, not one per lead."""

    ALLOWED = "https://productive.io/get-started/"

    def test_one_resolve_per_distinct_url_in_batch(self):
        """50 leads sharing one booking_link -> one resolve call."""
        old = copylint._URL_RESOLVE_HOOK
        try:
            resolver = _FakeResolver({self.ALLOWED: "pass"})
            copylint._URL_RESOLVE_HOOK = resolver
            leads = [
                {"id": "lead-%d" % i,
                 "steps": [{"body": "book: %s" % self.ALLOWED}]}
                for i in range(50)
            ]
            report = copylint.check_batch(leads)
            self.assertEqual(len(resolver.calls), 1,
                             "expected 1 resolve call for 50 leads sharing "
                             "one URL, got %d" % len(resolver.calls))
            self.assertEqual(
                report["counts"].get("cta_link_dead", 0), 0)
            self.assertEqual(
                report["counts"].get("cta_link_not_allowlisted", 0), 0)
        finally:
            copylint._URL_RESOLVE_HOOK = old


class ProductionPathTests(unittest.TestCase):
    """Drive the lint through ``check_batch``, the function the production
    path already calls. Not ``check_cta_links`` directly."""

    ALLOWED = "https://productive.io/get-started/"

    def _batch_with_url(self, url):
        leads = [{"id": "lead-1",
                  "steps": [{"body": "book here: %s" % url}]}]
        return copylint.check_batch(leads)

    def test_allowlisted_url_passes_through_check_batch(self):
        report = self._batch_with_url(self.ALLOWED)
        self.assertEqual(
            report["counts"].get("cta_link_not_allowlisted", 0), 0)
        self.assertEqual(report["counts"].get("cta_link_dead", 0), 0)

    def test_book_a_demo_refused_through_check_batch(self):
        """The allowlist assertion: book-a-demo resolves HEAD 200 but is
        NOT the allowed URL. Refused through the production path."""
        report = self._batch_with_url(
            "https://productive.io/book-a-demo/")
        self.assertGreater(
            report["counts"].get("cta_link_not_allowlisted", 0), 0,
            "book-a-demo should be refused by the allowlist")
        self.assertTrue(report["refused"])

    def test_dead_link_refused_through_check_batch(self):
        old = copylint._URL_RESOLVE_HOOK
        try:
            copylint._URL_RESOLVE_HOOK = _FakeResolver({self.ALLOWED: "dead"})
            report = self._batch_with_url(self.ALLOWED)
            self.assertGreater(
                report["counts"].get("cta_link_dead", 0), 0)
            self.assertTrue(report["refused"])
        finally:
            copylint._URL_RESOLVE_HOOK = old

    def test_unverified_refused_with_distinct_rule_name(self):
        """Transport failure -> cta_link_unverified, NOT cta_link_dead
        and NOT a pass. This is the assertion that closes the task."""
        old = copylint._URL_RESOLVE_HOOK
        try:
            copylint._URL_RESOLVE_HOOK = _FakeResolver(
                {self.ALLOWED: "unverified"})
            report = self._batch_with_url(self.ALLOWED)
            self.assertGreater(
                report["counts"].get("cta_link_unverified", 0), 0,
                "transport failure must fire cta_link_unverified")
            self.assertEqual(
                report["counts"].get("cta_link_dead", 0), 0,
                "transport failure must NOT fire cta_link_dead")
            self.assertTrue(report["refused"])
        finally:
            copylint._URL_RESOLVE_HOOK = old

    def test_no_link_passes(self):
        """A message with no CTA link is not a defect."""
        leads = [{"id": "lead-1",
                  "steps": [{"body": "hello, worth a chat?"}]}]
        report = copylint.check_batch(leads)
        self.assertEqual(
            report["counts"].get("cta_link_not_allowlisted", 0), 0)
        self.assertEqual(report["counts"].get("cta_link_dead", 0), 0)
        self.assertEqual(
            report["counts"].get("cta_link_unverified", 0), 0)


class SkipReasonTests(unittest.TestCase):
    """CTA_LINK_SKIP_REASON is a documented off switch. A skip that is
    not named in the report is a silent pass."""

    ALLOWED = "https://productive.io/get-started/"

    def test_skip_reason_recorded_in_report(self):
        old = copylint.CTA_LINK_SKIP_REASON
        try:
            copylint.CTA_LINK_SKIP_REASON = "offline test run"
            leads = [{"id": "lead-1",
                      "steps": [{"body": "book: %s" % self.ALLOWED}]}]
            report = copylint.check_batch(leads)
            self.assertEqual(report["cta_link_skip_reason"],
                             "offline test run")
            lines = copylint.report_lines(report)
            skip_lines = [l for l in lines if "SKIPPED" in l]
            self.assertTrue(skip_lines,
                            "skip reason must appear in report_lines output")
        finally:
            copylint.CTA_LINK_SKIP_REASON = old

    def test_skip_does_not_disable_allowlist(self):
        """Setting the skip reason does NOT let a non-allowlisted URL pass."""
        old = copylint.CTA_LINK_SKIP_REASON
        try:
            copylint.CTA_LINK_SKIP_REASON = "offline test run"
            leads = [{"id": "lead-1",
                      "steps": [{"body": "see https://evil.com/"}]}]
            report = copylint.check_batch(leads)
            self.assertGreater(
                report["counts"].get("cta_link_not_allowlisted", 0), 0,
                "allowlist must still fire when resolution is skipped")
            self.assertTrue(report["refused"])
        finally:
            copylint.CTA_LINK_SKIP_REASON = old


class GuardFailureTests(unittest.TestCase):
    """Break the wiring, confirm the test fails. CLAUDE.md §4."""

    ALLOWED = "https://productive.io/get-started/"

    def test_removing_allowlist_check_lets_dead_link_through(self):
        """Temporarily widen the allowlist to include book-a-demo.
        The refusal must disappear. This proves the allowlist is doing
        the work, not something else."""
        old = copylint.CTA_LINK_ALLOWLIST
        try:
            copylint.CTA_LINK_ALLOWLIST = frozenset({
                self.ALLOWED,
                "https://productive.io/book-a-demo/",
            })
            leads = [{"id": "lead-1",
                      "steps": [{"body": "book: "
                              "https://productive.io/book-a-demo/"}]}]
            report = copylint.check_batch(leads)
            self.assertEqual(
                report["counts"].get("cta_link_not_allowlisted", 0), 0,
                "widening the allowlist must remove the refusal")
        finally:
            copylint.CTA_LINK_ALLOWLIST = old


class OfflineTests(unittest.TestCase):
    """Tests must pass with no network. The allowlist check is a string
    comparison and needs no network. Resolution is stubbed via the hook."""

    ALLOWED = "https://productive.io/get-started/"

    def test_allowlist_refusal_works_offline(self):
        """No network, no resolver. The allowlist check still refuses."""
        old = copylint._URL_RESOLVE_HOOK
        try:
            copylint._URL_RESOLVE_HOOK = _FakeResolver({})
            leads = [{"id": "lead-1",
                      "steps": [{"body": "see https://evil.com/"}]}]
            report = copylint.check_batch(leads)
            self.assertGreater(
                report["counts"].get("cta_link_not_allowlisted", 0), 0)
            self.assertTrue(report["refused"])
        finally:
            copylint._URL_RESOLVE_HOOK = old

    def test_unverified_refused_offline(self):
        """Simulate a transport failure with the hook. The rule name is
        cta_link_unverified, not cta_link_dead."""
        old = copylint._URL_RESOLVE_HOOK
        try:
            copylint._URL_RESOLVE_HOOK = _FakeResolver(
                {self.ALLOWED: "unverified"})
            leads = [{"id": "lead-1",
                      "steps": [{"body": "book: %s" % self.ALLOWED}]}]
            report = copylint.check_batch(leads)
            self.assertGreater(
                report["counts"].get("cta_link_unverified", 0), 0)
            self.assertEqual(
                report["counts"].get("cta_link_dead", 0), 0)
        finally:
            copylint._URL_RESOLVE_HOOK = old


if __name__ == "__main__":
    unittest.main()
