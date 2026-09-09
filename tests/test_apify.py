"""Apify: optional public-web evidence, and everything that stops it.

The interesting tests here are the refusals. A scraper that will fetch whatever
it is handed is a server-side request forgery waiting to happen, and one that
cannot make an address sendable is the difference between research and a
shortcut round verification.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import clients, lint, store, verification
from src.providers import apify
from tests.base import ProviderTest


class ApifyTest(ProviderTest):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-apify-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def enabled(self, **overrides):
        research = {"enabled": True}
        research.update(overrides)
        return {"research": {"apify": research}}


class TestOffByDefault(ApifyTest):
    def test_a_client_that_has_not_asked_for_it_does_not_scrape(self):
        """A real client file with the opt-in removed, not a named client.

        This asserted `clients.load("productive")` was off, which made the
        test a statement about one client's config rather than about the
        default - and it broke the day that client opted in, which is not a
        defect in the default.
        """
        self.assertFalse(apify.settings({})["enabled"])
        self.assertFalse(apify.settings({"research": {}})["enabled"])
        no_optin = dict(clients.load("productive"), research={})
        self.assertFalse(apify.settings(no_optin)["enabled"])

    def test_enabling_it_is_explicit(self):
        self.assertTrue(apify.settings(self.enabled())["enabled"])

    def test_a_plan_reports_whether_it_is_even_allowed(self):
        planned = apify.plan("example.test", "public evidence required")
        self.assertFalse(planned["enabled"])

    def test_a_scrape_with_no_stated_reason_is_refused(self):
        with self.assertRaises(apify.ScrapeRefused):
            apify.plan("example.test", "")


class TestUrlSafety(ApifyTest):
    def refuses(self, url, **kw):
        with self.assertRaises(apify.UnsafeURL, msg=url):
            apify.check_url(url, resolve=False, **kw)

    def test_localhost_is_refused(self):
        for url in ("http://localhost/admin", "https://localhost:443/",
                    "http://LOCALHOST/"):
            self.refuses(url)

    def test_loopback_addresses_are_refused(self):
        for url in ("http://127.0.0.1/", "http://127.5.5.5/", "https://[::1]/"):
            self.refuses(url)

    def test_private_ipv4_ranges_are_refused(self):
        for url in ("http://10.0.0.1/", "http://172.16.4.4/",
                    "http://192.168.1.1/", "http://100.64.0.1/"):
            self.refuses(url)

    def test_link_local_is_refused(self):
        for url in ("http://169.254.169.254/latest/meta-data/",
                    "https://[fe80::1]/"):
            self.refuses(url)

    def test_private_ipv6_is_refused(self):
        for url in ("https://[fc00::1]/", "https://[::]/"):
            self.refuses(url)

    def test_internal_hostnames_are_refused(self):
        for url in ("http://intranet.local/", "https://db.internal/",
                    "http://box.lan/", "https://wiki.corp/"):
            self.refuses(url)

    def test_unsupported_schemes_are_refused(self):
        for url in ("file:///etc/passwd", "ftp://example.test/x",
                    "gopher://example.test/", "javascript:alert(1)",
                    "data:text/html,hi"):
            self.refuses(url)

    def test_malformed_urls_are_refused(self):
        for url in ("", "   ", "not a url", "http://", "https:///path"):
            self.refuses(url)

    def test_credentials_in_the_url_are_refused(self):
        self.refuses("https://user:pass@example.test/")

    def test_an_unusual_port_is_refused(self):
        self.refuses("http://example.test:8080/")

    def test_a_url_off_the_company_domain_is_refused(self):
        self.refuses("https://elsewhere.test/about", allowed_domain="example.test")

    def test_a_subdomain_of_the_company_domain_is_allowed(self):
        self.assertTrue(apify.check_url("https://www.example.test/about",
                                        allowed_domain="example.test",
                                        resolve=False))

    def test_a_hostname_that_resolves_privately_is_refused(self):
        original = apify.resolve_all
        apify.resolve_all = lambda host: ["10.1.2.3"]
        try:
            with self.assertRaises(apify.UnsafeURL) as e:
                apify.check_url("https://example.test/", allowed_domain="example.test")
            self.assertIn("private address", str(e.exception))
        finally:
            apify.resolve_all = original

    def test_a_hostname_that_resolves_publicly_is_allowed(self):
        original = apify.resolve_all
        apify.resolve_all = lambda host: ["93.184.216.34"]
        try:
            self.assertTrue(apify.check_url("https://example.test/",
                                            allowed_domain="example.test"))
        finally:
            apify.resolve_all = original

    def test_the_blocked_ranges_cover_the_documented_networks(self):
        for address in ("127.0.0.1", "10.0.0.1", "172.31.255.255", "192.168.0.1",
                        "169.254.0.1", "::1", "fe80::1", "fc00::1", "0.0.0.0"):
            self.assertTrue(apify.is_blocked_ip(address), address)
        for address in ("93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"):
            self.assertFalse(apify.is_blocked_ip(address), address)


class TestBounds(ApifyTest):
    def test_urls_are_deduplicated(self):
        urls = apify.candidate_urls("example.test",
                                    ["company_website", "about", "about"])
        self.assertEqual(len(urls), len({u["url"] for u in urls}))

    def test_the_page_cap_is_enforced(self):
        urls = apify.candidate_urls("example.test", list(apify.SOURCES),
                                    max_pages=3)
        self.assertEqual(len(urls), 3)

    def test_a_client_cannot_raise_the_hard_ceilings(self):
        conf = apify.settings(self.enabled(max_pages_per_domain=9999,
                                           max_items_per_run=9999,
                                           max_text_chars_per_page=10 ** 7))
        self.assertLessEqual(conf["max_pages_per_domain"], apify.MAX_PAGES)
        self.assertLessEqual(conf["max_items_per_run"], apify.MAX_ITEMS)
        self.assertLessEqual(conf["max_text_chars_per_page"], apify.MAX_TEXT_CHARS)

    def test_an_unknown_source_is_dropped(self):
        conf = apify.settings(self.enabled(allowed_sources=["about", "darkweb"]))
        self.assertEqual(conf["allowed_sources"], ["about"])

    def test_oversized_text_is_trimmed(self):
        text = apify.clean_text("x" * 50000, 100)
        self.assertEqual(len(text), 100)

    def test_html_never_survives_normalisation(self):
        text = apify.clean_text("<p>Hello <b>world</b></p><script>bad()</script>", 500)
        self.assertNotIn("<", text)
        self.assertNotIn("script", text.lower())

    def test_polling_is_bounded_and_gives_up(self):
        calls = []
        original = apify.run_status
        apify.run_status = lambda rid: calls.append(rid) or {
            "id": rid, "status": "RUNNING", "dataset_id": None}
        try:
            result = apify.wait_for("run-1", attempts=3, interval=0,
                                    sleep=lambda s: None)
        finally:
            apify.run_status = original
        self.assertEqual(result["status"], "TIMEOUT")
        self.assertEqual(len(calls), 3)

    def test_polling_stops_as_soon_as_the_run_finishes(self):
        calls = []
        original = apify.run_status
        apify.run_status = lambda rid: calls.append(rid) or {
            "id": rid, "status": "SUCCEEDED", "dataset_id": "ds-1"}
        try:
            result = apify.wait_for("run-1", attempts=5, interval=0,
                                    sleep=lambda s: None)
        finally:
            apify.run_status = original
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(len(calls), 1)


class TestEvidenceAndProvenance(ApifyTest):
    def items(self):
        return [
            {"url": "https://example.test/careers", "title": "Careers",
             "text": "We are hiring three project managers in Manchester.",
             "html": "<html>" + "x" * 40000 + "</html>", "crawledAt": "2026-08-26"},
            {"url": "https://example.test/about", "title": "About",
             "text": "Founded in 2011, forty people across two offices."},
            {"url": "https://elsewhere.test/x", "text": "off domain"},
            {"url": "https://example.test/about", "text": "a duplicate url"},
        ]

    def evidence(self, **conf):
        settings = apify.settings(self.enabled(**conf))
        return apify.evidence_from_items(
            self.items(), "example.test", apify.DEFAULT_ACTOR,
            sources_by_url={"https://example.test/careers": "careers",
                            "https://example.test/about": "about"},
            conf=settings)

    def test_every_fact_carries_its_provenance(self):
        for entry in self.evidence():
            for field in ("source_type", "provider", "source_url", "actor",
                          "field", "fact"):
                self.assertIn(field, entry)
            self.assertEqual(entry["provider"], "apify")
            self.assertTrue(entry["source_url"].startswith("https://example.test"))

    def test_off_domain_items_are_dropped(self):
        urls = [e["source_url"] for e in self.evidence()]
        self.assertFalse(any("elsewhere.test" in u for u in urls))

    def test_duplicate_urls_are_dropped(self):
        urls = [e["source_url"] for e in self.evidence()]
        self.assertEqual(len(urls), len(set(urls)))

    def test_raw_html_never_reaches_the_evidence(self):
        blob = json.dumps(self.evidence())
        self.assertNotIn("<html>", blob)
        self.assertNotIn("xxxxxxxxxx", blob)

    def test_the_text_bound_is_per_page(self):
        evidence = self.evidence(max_text_chars_per_page=20)
        for entry in evidence:
            self.assertLessEqual(len(entry["fact"]), 20)

    def test_the_item_cap_is_enforced(self):
        self.assertLessEqual(len(self.evidence(max_pages_per_domain=1)), 1)


class TestApifyCannotMakeAnAddressSendable(ApifyTest):
    def test_an_address_found_by_a_scrape_is_not_sendable(self):
        contact = {"name": "Someone", "key": "someone",
                   "email": "someone@example.test", "email_source": "apify"}
        self.assertFalse(lint.sendable(contact))
        self.assertFalse(verification.is_sendable(contact))

    def test_the_module_never_writes_sendable_or_a_verdict(self):
        """It may say the word in a docstring. It may not assign it."""
        import inspect
        import re
        source = inspect.getsource(apify)
        for field in ("sendable", "verdict", "verification"):
            self.assertIsNone(
                re.search(rf"\[[\"']{field}[\"']\]\s*=", source), field)
            self.assertIsNone(re.search(rf"{field}\s*=", source), field)

    def test_the_module_is_not_a_verifier(self):
        self.assertFalse(hasattr(apify, "email_verifier"))
        from src import verification as verif
        self.assertNotIn("apify", verif.COSTS)


class TestHealthAndConfig(ApifyTest):
    def test_a_missing_token_fails_cleanly(self):
        self.clear_keys()
        os.environ.pop("APIFY_TOKEN", None)
        result = apify.check()
        self.assertFalse(result["ok"])
        self.assertIn("APIFY_TOKEN", result["note"])

    def test_the_health_check_reads_account_metadata_only(self):
        os.environ["APIFY_TOKEN"] = "test-key-not-real"
        try:
            apify.check()
        except Exception:
            pass
        for call in self.cassette.calls:
            self.assertEqual(call["method"], "GET")
            self.assertIn("/users/me", call["url"])

    def test_the_token_is_redacted_in_output(self):
        from src import providers
        redacted = providers.redact("https://api.apify.com/v2/users/me?token=secret123")
        self.assertNotIn("secret123", redacted)
        self.assertIn("token=***", redacted)

    def test_a_plan_makes_no_network_call(self):
        apify.plan("example.test", "public evidence required", self.enabled())
        self.assertEqual(self.cassette.calls, [])

    def test_a_plan_states_why_and_what_bounds_it(self):
        planned = apify.plan("example.test", "careers evidence required",
                             self.enabled())
        self.assertEqual(planned["reason"], "careers evidence required")
        self.assertFalse(planned["cost"]["known"])
        self.assertIn("page", planned["cost"]["bounded_by"])
        self.assertTrue(planned["urls"])


if __name__ == "__main__":
    unittest.main()
