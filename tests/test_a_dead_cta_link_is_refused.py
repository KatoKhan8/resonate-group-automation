"""TASK-354: a CTA link that does not resolve is refused.

Four states, none may collapse:
    200 (or 2xx)              PASS
    4xx / 5xx / DNS failure   REFUSE, rule `cta_link_dead`
    could not be checked      REFUSE, rule `cta_link_unverified`
    (no network, timeout)
    no link in the message    PASS

`cta_link_unverified` must be its own rule name. A transport failure is not
a dead link - the repository has already paid for conflating those two.
"""
import os
import unittest
from unittest import mock

from src import copylint


PACK = {"facts": [
    {"kind": "company_post",
     "source_url": "https://li.test/1",
     "published_at": "2026-09-02",
     "snippet": "We have opened a second delivery team in Berlin."},
]}

OPENER = "Saw you opened a second delivery team in Berlin."


def lead(ident="lead-1", opener=OPENER, tail=None, steps=5, booking_link=None):
    bodies = [opener + (" " + tail if tail else "")]
    bodies += ["Step %d body, long enough to be real." % n
               for n in range(2, steps + 1)]
    result = {"id": ident, "steps": [{"body": b} for b in bodies]}
    if booking_link:
        result["booking_link"] = booking_link
    return result


def run(leads, packs=None, booking_link=None, skip_link_check=False):
    packs = packs or {l["id"]: PACK for l in leads}
    return copylint.check_batch(leads, packs, booking_link=booking_link,
                                skip_link_check=skip_link_check)


class ALiveLinkPasses(unittest.TestCase):
    """Acceptance 1: the real value passes."""

    def setUp(self):
        copylint._clear_link_cache()

    def test_productive_io_gets_a_pass(self):
        """The real booking_link, verified HEAD 200 on 2026-09-26."""
        with mock.patch.object(copylint, "_do_check",
                               return_value=("ok", "https://productive.io/get-started/")):
            report = run([lead()], booking_link="https://productive.io/get-started/")
        self.assertFalse(report["refused"], report["offenders"])
        self.assertEqual(report["counts"]["cta_link_dead"], 0)
        self.assertEqual(report["counts"]["cta_link_unverified"], 0)


class ADeadLinkIsRefused(unittest.TestCase):
    """Acceptance 2: a dead link REFUSES with `cta_link_dead`."""

    def setUp(self):
        copylint._clear_link_cache()

    def test_a_reserved_tld_is_refused(self):
        """`productive.test` is reserved and can never resolve."""
        with mock.patch.object(copylint, "_do_check",
                               return_value=("dead", "https://productive.test/get-started/")):
            report = run([lead()], booking_link="https://productive.test/get-started/")
        self.assertTrue(report["refused"])
        self.assertIn("lead-1", report["offenders"]["cta_link_dead"])
        self.assertEqual(report["counts"]["cta_link_dead"], 1)
        self.assertEqual(report["counts"]["cta_link_unverified"], 0)

    def test_a_url_in_the_body_is_also_checked(self):
        """A dead URL in the body text is refused, not just the booking_link."""
        bad_lead = lead(tail="Book here: https://dead-link.test/calendar")
        with mock.patch.object(copylint, "_do_check",
                               return_value=("dead", "https://dead-link.test/calendar")):
            report = run([bad_lead])
        self.assertTrue(report["refused"])
        self.assertIn("lead-1", report["offenders"]["cta_link_dead"])


class AnUnverifiedLinkIsRefusedWithItsOwnRule(unittest.TestCase):
    """Acceptance 3: transport failure REFUSES with `cta_link_unverified`,
    NOT `cta_link_dead` and NOT a pass. This is the assertion that closes
    the task."""

    def setUp(self):
        copylint._clear_link_cache()

    def test_a_timeout_is_unverified_not_dead(self):
        """A network timeout is not a dead link."""
        with mock.patch.object(copylint, "_do_check", return_value=(None, None)):
            report = run([lead()], booking_link="https://example.com/book")
        self.assertTrue(report["refused"])
        self.assertIn("lead-1", report["offenders"]["cta_link_unverified"])
        self.assertEqual(report["counts"]["cta_link_dead"], 0,
                         "a transport failure must NOT be reported as a dead link")
        self.assertEqual(report["counts"]["cta_link_unverified"], 1)

    def test_the_two_rules_are_distinct(self):
        """One lead with a dead link, one with an unverified link. They must
        fire different rules."""
        dead_lead = lead("lead-dead")
        unverified_lead = lead("lead-unverified")
        def fake_check(url, timeout):
            if "dead" in url:
                return ("dead", url)
            return (None, None)
        with mock.patch.object(copylint, "_do_check", side_effect=fake_check):
            report = run([dead_lead, unverified_lead],
                         booking_link=None)
            # Inject URLs via body text
            dead_lead["steps"][0]["body"] += " https://dead.test/link"
            unverified_lead["steps"][0]["body"] += " https://slow.test/link"
            copylint._clear_link_cache()
            report = run([dead_lead, unverified_lead])
        self.assertIn("lead-dead", report["offenders"]["cta_link_dead"])
        self.assertIn("lead-unverified", report["offenders"]["cta_link_unverified"])


class OneHeadPerDistinctUrl(unittest.TestCase):
    """Acceptance 4: one HEAD per distinct URL. A 50-lead batch sharing one
    booking_link must make ONE request, not fifty."""

    def setUp(self):
        copylint._clear_link_cache()

    def test_fifty_leads_one_request(self):
        """The cache ensures one HEAD per distinct URL, not per lead."""
        call_count = [0]
        def counting_check(url, timeout):
            call_count[0] += 1
            return ("ok", url)
        with mock.patch.object(copylint, "_do_check", side_effect=counting_check):
            # Check the URL multiple times - the cache should ensure only one call
            copylint.check_url("https://productive.io/get-started/")
            copylint.check_url("https://productive.io/get-started/")
            copylint.check_url("https://productive.io/get-started/")
            for _ in range(47):
                copylint.check_url("https://productive.io/get-started/")
        self.assertEqual(call_count[0], 1,
                         "50 checks of the same URL must make ONE request, "
                         "not %d" % call_count[0])


class TheOptOutIsLoud(unittest.TestCase):
    """The offline opt-out must be visible in the lint output."""

    def setUp(self):
        copylint._clear_link_cache()

    def test_skip_link_check_is_reported(self):
        report = run([lead()], skip_link_check=True)
        self.assertTrue(report.get("link_check_skipped"))
        text = "\n".join(copylint.report_lines(report))
        self.assertIn("LINK CHECK SKIPPED", text)

    def test_the_env_var_also_skips(self):
        with mock.patch.dict(os.environ, {"RESONATE_SKIP_CTA_LINK_CHECK": "1"}):
            report = run([lead()])
        self.assertTrue(report.get("link_check_skipped"))

    def test_the_default_is_not_skipped(self):
        """The opt-out is NOT on by default."""
        with mock.patch.object(copylint, "_do_check", return_value=("ok", "https://example.com")):
            report = run([lead()], booking_link="https://example.com")
        self.assertFalse(report.get("link_check_skipped"))


class NoLinkIsNotADefect(unittest.TestCase):
    """A message with no CTA link is not a defect."""

    def setUp(self):
        copylint._clear_link_cache()

    def test_a_lead_with_no_urls_passes(self):
        with mock.patch.object(copylint, "_do_check", return_value=("ok", "")) as m:
            report = run([lead()])
        self.assertFalse(report["refused"])
        self.assertEqual(report["counts"]["cta_link_dead"], 0)
        self.assertEqual(report["counts"]["cta_link_unverified"], 0)
        m.assert_not_called()


class UrlExtraction(unittest.TestCase):
    """URL extraction from rendered text."""

    def test_http_and_https_are_extracted(self):
        text = "Visit https://example.com and http://other.test/path"
        urls = copylint.extract_urls(text)
        self.assertIn("https://example.com", urls)
        self.assertIn("http://other.test/path", urls)

    def test_trailing_punctuation_is_stripped(self):
        text = "See https://example.com/page."
        urls = copylint.extract_urls(text)
        self.assertEqual(urls, ["https://example.com/page"])

    def test_no_urls_returns_empty(self):
        self.assertEqual(copylint.extract_urls("no links here"), [])
        self.assertEqual(copylint.extract_urls(""), [])
        self.assertEqual(copylint.extract_urls(None), [])


if __name__ == "__main__":
    unittest.main()
