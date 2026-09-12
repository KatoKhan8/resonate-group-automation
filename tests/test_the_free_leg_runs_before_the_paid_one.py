#!/usr/bin/env python3
"""A socket costs nothing, so it is tried before the compute units.

`src/webfetch.py` was complete and had ZERO callers. Bounded pages, bytes,
redirects and wall-clock; robots respected; same-domain only; and it follows
the site's OWN links rather than guessing `/about` and `/team` the way the
Apify proposal does - two of five guessed paths 404'd on the first live run
and the navigation text was kept as though the page were real. Its docstring
describes the waterfall: "reads the site directly first and falls back to a
paid crawl only for the sites that genuinely defeat this."

The pipeline went straight to Apify every time.

MEASURED on the Productive cohort: 103 of 300 records carry no research
evidence at all. Reading ten under-floor records' own sites for free returned
HTTP_SUCCESS on four, keeping six pages including `about` and `services`
pages the paid crawl had never fetched - and classified the other six
honestly (three NON_2XX, two JS_RENDERING_REQUIRED, one BLOCKED) rather than
storing a shell as evidence.

WHAT IT DOES NOT FIX, because the same run proved it: zero of those pages
stated a team size. Company websites do not publish headcount, so the
headcount failures need a different SOURCE rather than more crawling. This
buys evidence coverage for the criteria that websites DO answer - vertical,
services model, geography - and nothing about size.
"""
import unittest
from unittest import mock

from src import research, store, webfetch


def a_record(domain="acme.test"):
    rec = store.new_record("acct", "domains", "productive", "Acme", domain)
    rec["company_facts"] = {"industry": "Advertising Services"}
    return rec


def a_page(url="https://acme.test/about", field="about", text=None):
    return {"source_type": "local_http", "provider": "local_http",
            "source_url": url, "http_status": 200, "field": field,
            "fact": text or ("We are an independent creative studio working "
                             "with retained clients across Europe on brand "
                             "and campaign delivery. " * 6),
            "content_hash": "abc123", "chars": 400}


def site(outcome="HTTP_SUCCESS", pages=None, fallback=False):
    return {"domain": "acme.test", "outcome": outcome,
            "pages": pages if pages is not None else [a_page()],
            "stats": {}, "retrieved_at": "2026-09-12T00:00:00+00:00",
            "fallback_worthy": fallback}


PROPOSAL = {"planned": True, "actor": "apify~website-content-crawler",
            "reason": "public_evidence_required_for_icp_dimensions",
            "urls": [{"url": "https://acme.test/", "source": "company_website"}]}


class TheFreeLegSettlesIt(unittest.TestCase):
    """`research.plan` is stubbed to say a crawl is wanted, because what is
    under test is the ORDER of the two legs once one is - not the planning
    gate, which has its own tests and would otherwise decide these cases
    before either leg ran."""

    def run_it(self, result, **over):
        rec = a_record()
        spend = mock.Mock(return_value=True)
        with mock.patch.object(research, "plan", return_value=dict(PROPOSAL)):
            with mock.patch.object(webfetch, "research",
                                   return_value=result) as free:
                with mock.patch.object(research, "apify") as paid:
                    paid.settings.return_value = {"enabled": True,
                                                  "max_items_per_run": 20,
                                                  "max_runs_per_batch": 75}
                    out = research.run(rec, {}, live=True, spend=spend, **over)
        return rec, out, free, paid, spend

    def test_a_readable_site_is_read_for_free(self):
        rec, out, free, paid, spend = self.run_it(site())
        self.assertEqual(len(out), 1)
        free.assert_called_once()
        self.assertEqual(rec["research"][0]["provider"], "local_http")

    def test_and_the_paid_crawl_is_never_started(self):
        """The point of a waterfall. A site this reads must not also be
        bought."""
        rec, out, free, paid, spend = self.run_it(site())
        paid.start_run.assert_not_called()
        spend.assert_not_called()

    def test_a_site_that_defeats_it_falls_through(self):
        """`JS_RENDERING_REQUIRED` is a real answer that routes the account
        onward, not a failure to hide."""
        rec, out, free, paid, spend = self.run_it(
            site(outcome="JS_RENDERING_REQUIRED", pages=[], fallback=True))
        self.assertTrue(spend.called, "the paid leg was never reached")

    def test_a_blocked_site_falls_through_too(self):
        rec, out, free, paid, spend = self.run_it(
            site(outcome="BLOCKED", pages=[], fallback=True))
        self.assertTrue(spend.called)

    def test_boilerplate_is_refused_rather_than_stored(self):
        """The same filter the paid leg uses. A cookie policy must not reach
        `segments.text_of`, which appends every research fact to the text the
        vertical classifier reads."""
        cookies = a_page(text="We use cookies. Accept all cookies. "
                              "Cookie policy. Privacy policy. " * 8)
        rec, out, free, paid, spend = self.run_it(site(pages=[cookies]))
        self.assertTrue(spend.called,
                        "a page of boilerplate was treated as evidence")
        self.assertEqual(rec.get("research") or [], [])

    def test_a_crash_in_the_free_leg_never_breaks_the_run(self):
        rec = a_record()
        spend = mock.Mock(return_value=True)
        with mock.patch.object(research, "plan", return_value=dict(PROPOSAL)):
            with mock.patch.object(webfetch, "research",
                                   side_effect=OSError("socket")):
                with mock.patch.object(research, "apify") as paid:
                    paid.settings.return_value = {"enabled": True,
                                                  "max_items_per_run": 20}
                    research.run(rec, {}, live=True, spend=spend)
        self.assertTrue(spend.called, "a free-leg failure stopped the run")

    def test_a_record_with_no_domain_is_not_fetched(self):
        rec = a_record(domain="")
        with mock.patch.object(research, "plan", return_value=dict(PROPOSAL)):
            with mock.patch.object(webfetch, "research") as free:
                with mock.patch.object(research, "apify") as paid:
                    paid.settings.return_value = {"enabled": True,
                                                  "max_items_per_run": 20}
                    research.run(rec, {}, live=True,
                                 spend=mock.Mock(return_value=True))
        free.assert_not_called()


if __name__ == "__main__":
    unittest.main()
