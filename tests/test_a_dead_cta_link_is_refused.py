"""TASK-354 - a CTA link that does not resolve is refused.

Four states, none may collapse into another:
    2xx                          PASS
    4xx / 5xx / DNS failure      REFUSE  cta_link_dead
    could not be checked         REFUSE  cta_link_unverified (DISTINCT rule)
    no link in the message       PASS
"""
import unittest
from unittest import mock

from src import copylint


PACK = {"facts": [
    {"kind": "company_post",
     "source_url": "https://li.test/1",
     "published_at": "2026-09-02",
     "snippet": "We have opened a second delivery team in Berlin and are "
                "taking on platform work through Q4."},
]}

OPENER = "Saw you opened a second delivery team in Berlin."


def lead(ident="lead-1", opener=OPENER, booking_link=None, body_url=None,
           steps=5):
    bodies = [opener]
    if body_url:
        bodies[0] += " Book here: " + body_url
    bodies += ["Step %d body, long enough to be real." % n
               for n in range(2, steps + 1)]
    result = {"id": ident, "steps": [{"body": b} for b in bodies]}
    if booking_link:
        result["booking_link"] = booking_link
    return result


class ARealBookingLinkPasses(unittest.TestCase):
    """Acceptance 1: the real value passes."""

    def test_productive_io_gets_a_200(self):
        result = copylint.check_cta_links(
            ["https://productive.io/get-started/"])
        self.assertFalse(result["refused"])
        self.assertEqual(result["dead"], [])
        self.assertEqual(result["unverified"], [])
        self.assertIn("https://productive.io/get-started/", result["ok"])


class ADeadLinkIsRefused(unittest.TestCase):
    """Acceptance 2: a dead link REFUSES with cta_link_dead.

    `.test` is a reserved TLD (RFC 2606) that can never resolve.
    """

    def test_productive_test_is_refused_as_dead(self):
        result = copylint.check_cta_links(
            ["https://productive.test/get-started/"])
        self.assertTrue(result["refused"])
        self.assertEqual(result["dead"],
                         ["https://productive.test/get-started/"])
        self.assertEqual(result["unverified"], [])

    def test_the_batch_rule_fires_cta_link_dead(self):
        batch = [lead("lead-1",
                       booking_link="https://productive.test/get-started/")]
        report = copylint.check_batch(batch,
                                       packs={"lead-1": PACK},
                                       skip_cta_link_check=False)
        self.assertIn("lead-1", report["offenders"]["cta_link_dead"])
        self.assertEqual(report["offenders"]["cta_link_unverified"], [])


class AnUnreachableCheckIsRefusedWithItsOwnRule(unittest.TestCase):
    """Acceptance 3: a transport failure REFUSES with cta_link_unverified,
    NOT cta_link_dead and NOT a pass. This is the assertion that closes
    the task.
    """

    def test_a_timeout_is_unverified_not_dead(self):
        with mock.patch.object(copylint.urllib.request, "urlopen",
                               side_effect=TimeoutError("timed out")):
            result = copylint.check_cta_links(
                ["https://example.com/real-page"])
        self.assertTrue(result["refused"])
        self.assertEqual(result["dead"], [])
        self.assertEqual(result["unverified"],
                         ["https://example.com/real-page"])
        verdict, _ = result["results"]["https://example.com/real-page"]
        self.assertEqual(verdict, "unverified")

    def test_a_dns_failure_is_dead_not_unverified(self):
        """Control: a DNS failure IS dead, not unverified. The distinction
        matters - an operator seeing cta_link_dead will fix a link that
        is fine if transport failures were folded in."""
        import urllib.error
        with mock.patch.object(copylint.urllib.request, "urlopen",
                               side_effect=urllib.error.URLError(
                                   "Name or service not known")):
            result = copylint.check_cta_links(
                ["https://example.com/real-page"])
        self.assertTrue(result["refused"])
        self.assertEqual(result["dead"],
                         ["https://example.com/real-page"])
        self.assertEqual(result["unverified"], [])

    def test_the_batch_rule_fires_cta_link_unverified_on_timeout(self):
        batch = [lead("lead-1",
                       booking_link="https://example.com/book")]
        with mock.patch.object(copylint.urllib.request, "urlopen",
                               side_effect=TimeoutError("timed out")):
            report = copylint.check_batch(batch,
                                           packs={"lead-1": PACK},
                                           skip_cta_link_check=False)
        self.assertIn("lead-1", report["offenders"]["cta_link_unverified"])
        self.assertEqual(report["offenders"]["cta_link_dead"], [])


class OneHeadPerDistinctUrl(unittest.TestCase):
    """Acceptance 4: count the requests for a 50-lead batch sharing one
    booking_link and assert the count is 1.
    """

    def test_fifty_leads_one_url_one_request(self):
        url = "https://productive.io/get-started/"
        batch = [lead("lead-%d" % i, booking_link=url) for i in range(50)]

        real_resolve = copylint._resolve_url
        call_count = [0]

        def counting_resolve(u, cache=None):
            if cache is not None and u in cache:
                return cache[u]
            call_count[0] += 1
            return real_resolve(u, cache)

        with mock.patch.object(copylint, "_resolve_url",
                               side_effect=counting_resolve):
            report = copylint.check_batch(batch,
                                           packs={l["id"]: PACK for l in batch},
                                           skip_cta_link_check=False)
        self.assertEqual(call_count[0], 1,
                         "50 leads sharing one URL must make ONE request, "
                         "not 50; got %d" % call_count[0])


class NoLinkIsNotADefect(unittest.TestCase):
    """A message with no CTA link is not a defect."""

    def test_a_lead_without_any_url_passes_the_cta_check(self):
        batch = [lead("lead-1")]
        report = copylint.check_batch(batch,
                                       packs={"lead-1": PACK},
                                       skip_cta_link_check=False)
        self.assertEqual(report["offenders"]["cta_link_dead"], [])
        self.assertEqual(report["offenders"]["cta_link_unverified"], [])


class TheOptOutIsLoud(unittest.TestCase):
    """The skip flag must be visible in the report."""

    def test_skip_is_recorded_in_the_report(self):
        batch = [lead("lead-1",
                       booking_link="https://productive.io/get-started/")]
        report = copylint.check_batch(batch,
                                       packs={"lead-1": PACK},
                                       skip_cta_link_check=True)
        self.assertTrue(report["cta_link_check_skipped"])
        text = "\n".join(copylint.report_lines(report))
        self.assertIn("CTA LINK CHECK SKIPPED", text)

    def test_default_is_not_skipped(self):
        batch = [lead("lead-1")]
        report = copylint.check_batch(batch, packs={"lead-1": PACK})
        self.assertFalse(report["cta_link_check_skipped"])


class HeadFallbacksToGet(unittest.TestCase):
    """Some hosts refuse HEAD. Fall back to GET and discard the body."""

    def test_a_405_on_head_falls_back_to_get(self):
        import urllib.error
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(req.get_method())
            if req.get_method() == "HEAD":
                raise urllib.error.HTTPError(
                    req.full_url, 405, "Method Not Allowed",
                    {}, None)
            resp = mock.MagicMock()
            resp.getcode.return_value = 200
            resp.geturl.return_value = req.full_url
            return resp

        with mock.patch.object(copylint.urllib.request, "urlopen",
                               side_effect=fake_urlopen):
            result = copylint.check_cta_links(["https://example.com/page"])
        self.assertEqual(calls, ["HEAD", "GET"])
        self.assertFalse(result["refused"])
        self.assertIn("https://example.com/page", result["ok"])


class ExtractCtaUrls(unittest.TestCase):
    """The extractor pulls URLs from every place a prospect sees them."""

    def test_booking_link_is_extracted(self):
        l = lead(booking_link="https://example.com/book")
        urls = copylint.extract_cta_urls(l)
        self.assertIn("https://example.com/book", urls)

    def test_body_url_is_extracted(self):
        l = lead(body_url="https://example.com/demo")
        urls = copylint.extract_cta_urls(l)
        self.assertIn("https://example.com/demo", urls)

    def test_ps_url_is_extracted(self):
        l = lead()
        l["ps"] = {"1": "See https://example.com/ps-link for details."}
        urls = copylint.extract_cta_urls(l)
        self.assertIn("https://example.com/ps-link", urls)

    def test_no_urls_returns_empty(self):
        l = lead()
        urls = copylint.extract_cta_urls(l)
        self.assertEqual(urls, [])


if __name__ == "__main__":
    unittest.main()
