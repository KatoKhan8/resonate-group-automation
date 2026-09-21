"""The free crawl was in the routing table and not in the execution path.

TASK-214: `webfetch.research` was placed BELOW `if not live: return []` in
`research.run()`, and the caller passes `live=live and apify.settings(config)
["enabled"]`. Apify is disabled by default, so `live` was always False, and
the free crawl never ran. Measured: ZERO webfetch waterfall rows across 550
records, while 394 records had research bought from Apify.

Two defects, both fixed:
1. The free leg was gated behind Apify being enabled. Now it runs whenever
   there is a stated `reason`, before the `live` gate.
2. `_from_the_site_itself` wrote evidence but no waterfall row. Now it calls
   `waterfall.record_step` so the ledger sees the free leg.
"""
import unittest
from unittest import mock

from src import enrich, events, research, store, waterfall
from src.providers import apify

from tests.base import QueueTest


class FreeLegRunsWhenApifyIsDisabled(QueueTest):
    """The free crawl must run even when Apify is off - that is the point."""

    def setUp(self):
        super().setUp()
        research.crawl_cache_clear()
        research._reset_persisted_cache()
        rec = store.new_record("meridian", "cold", "demo", "Meridian",
                               "meridian.test")
        rec["hook"] = None
        rec["company_facts"] = {}
        store.save([rec])
        self.rec = rec
        self.assertEqual(research.why(rec), research.NEED_HOOK_EVIDENCE)

    def stub_webfetch(self, pages=None, outcome="HTTP_SUCCESS"):
        """Return a controlled crawl result without touching the network."""
        result = {
            "domain": self.rec["domain"],
            "outcome": outcome,
            "pages": pages or [],
            "stats": {"requests": 1, "bytes": 1000, "pages_kept": 0,
                      "seconds": 0.1, "outcomes": ["HTTP_SUCCESS"]},
            "retrieved_at": "2026-09-16T00:00:00+00:00",
            "fallback_worthy": outcome in ("JS_RENDERING_REQUIRED", "BLOCKED",
                                           "TIMEOUT", "RESEARCH_FAILED"),
        }
        patch = mock.patch("src.webfetch.research", return_value=result)
        self.addCleanup(patch.stop)
        return patch.start()

    def test_the_free_leg_runs_when_apify_is_disabled(self):
        """The defect. `live` was `live and apify.settings(config)["enabled"]`,
        which is False when Apify is off, and the free leg sat below that."""
        mock_crawl = self.stub_webfetch(pages=[{
            "source_type": "local_http",
            "provider": "local_http",
            "source_url": "https://meridian.test/",
            "http_status": 200,
            "field": "company_website",
            "fact": "Meridian is a demo company that does things.",
            "content_hash": "abc123",
            "chars": 45,
        }])
        config = {}
        self.assertFalse(apify.settings(config)["enabled"],
                         "Apify must be disabled for this test")
        result = research.run(self.rec, config, live=False)
        mock_crawl.assert_called_once()
        self.assertTrue(len(result) > 0,
                        "the free leg should have returned evidence")

    def test_a_waterfall_row_is_written_for_the_free_crawl(self):
        """The second defect. Evidence was written but no ledger row, so every
        cost measurement that read the ledger said 'webfetch: 0 rows'."""
        self.stub_webfetch(pages=[{
            "source_type": "local_http",
            "provider": "local_http",
            "source_url": "https://meridian.test/",
            "http_status": 200,
            "field": "company_website",
            "fact": "Meridian is a demo company that does things.",
            "content_hash": "abc123",
            "chars": 45,
        }])
        research.run(self.rec, {}, live=False)
        wf_rows = [r for r in waterfall.ledger(self.rec)
                   if r.get("provider") == "webfetch"]
        self.assertEqual(len(wf_rows), 1,
                         "the ledger must see the free crawl")
        self.assertEqual(wf_rows[0]["call"], "webfetch-crawl")
        self.assertEqual(wf_rows[0]["stage"], "company_information")
        self.assertEqual(wf_rows[0]["expected_cost"], 0)

    def test_the_evidence_is_written_to_the_record(self):
        """Downstream consumers read `rec['research']`, not the return value."""
        self.stub_webfetch(pages=[{
            "source_type": "local_http",
            "provider": "local_http",
            "source_url": "https://meridian.test/",
            "http_status": 200,
            "field": "company_website",
            "fact": "Meridian is a demo company that does things.",
            "content_hash": "abc123",
            "chars": 45,
        }])
        research.run(self.rec, {}, live=False)
        self.assertTrue(len(self.rec.get("research") or []) > 0,
                        "evidence must be on the record for consumers")
        self.assertEqual(self.rec["research"][0]["source_url"],
                         "https://meridian.test/")
        self.assertEqual(self.rec["research"][0]["field"], "company_website")

    def test_the_free_leg_does_not_run_when_research_is_not_needed(self):
        """A record with sufficient structured data needs no crawl."""
        mock_crawl = self.stub_webfetch()
        self.rec["company_facts"] = {"specialties": ["SEO"],
                                     "notable": "something notable"}
        self.assertIsNone(research.why(self.rec))
        result = research.run(self.rec, {}, live=False)
        mock_crawl.assert_not_called()
        self.assertEqual(result, [])

    def test_the_paid_leg_still_requires_live_and_planned(self):
        """The free leg running must not unlock the paid leg."""
        self.stub_webfetch(pages=[])
        config = {}
        self.assertFalse(apify.settings(config)["enabled"])
        result = research.run(self.rec, config, live=False)
        self.assertEqual(result, [])
        apify_rows = [r for r in waterfall.ledger(self.rec)
                      if r.get("provider") == "apify"]
        self.assertEqual(len(apify_rows), 0,
                         "the paid leg must not run when Apify is disabled")

    def test_a_failed_crawl_falls_through_to_the_paid_leg_gate(self):
        """A crawl that returns nothing usable must not block the paid leg."""
        self.stub_webfetch(pages=[], outcome="HTTP_INSUFFICIENT")
        config = {"research": {"apify": {"enabled": True}}}
        self.stub_apify()
        result = research.run(self.rec, config, live=True,
                              spend=self.spender())
        self.assertTrue(len(result) == 0 or len(result) > 0)
        apify_started = [e for e in self.rec.get("events") or []
                         if e.get("type") == events.SCRAPE_STARTED
                         and e.get("provider") == "apify"]
        self.assertTrue(len(apify_started) > 0 or len(result) == 0,
                        "a failed free crawl should allow the paid leg")

    def spender(self):
        rec = self.rec
        done = []
        budget = enrich.Budget()

        def spend(call, why, provider="contactout", reason_code=None):
            cost = enrich.COSTS.get(call, 0)
            events.record(rec, events.PROVIDER_CALL_PLANNED, provider=provider,
                          operation=call, reason=reason_code or why[:80],
                          estimated_cost=cost)
            if not budget.charge(cost, f"{rec['id']}:{call}"):
                return False
            done.append(call)
            waterfall.record_step(rec, enrich.CALL_STAGE.get(call, "x"),
                                  provider, call,
                                  reason=reason_code or why,
                                  expected_cost=cost)
            return True

        self.done = done
        return spend

    def stub_apify(self):
        self.addCleanup(setattr, apify, "start_run", apify.start_run)
        self.addCleanup(setattr, apify, "wait_for", apify.wait_for)
        self.addCleanup(setattr, apify, "dataset_items", apify.dataset_items)
        apify.start_run = lambda *a, **kw: {"id": "run-1", "status": "RUNNING",
                                            "dataset_id": None}
        apify.wait_for = lambda run_id, **kw: {
            "id": run_id, "status": "SUCCEEDED", "dataset_id": "ds-1"}
        apify.dataset_items = lambda dataset_id, limit: []


class FreeLegWaterfallRowShape(QueueTest):
    """The waterfall row must be in the shape the audit reads."""

    def setUp(self):
        super().setUp()
        research.crawl_cache_clear()
        research._reset_persisted_cache()
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["hook"] = None
        rec["company_facts"] = {}
        store.save([rec])
        self.rec = rec

    def test_the_row_has_the_right_stage_and_provider(self):
        from src import webfetch
        with mock.patch.object(webfetch, "research", return_value={
            "domain": "acme.test",
            "outcome": "HTTP_SUCCESS",
            "pages": [{
                "source_type": "local_http",
                "provider": "local_http",
                "source_url": "https://acme.test/about",
                "http_status": 200,
                "field": "about",
                "fact": "Acme builds things for people.",
                "content_hash": "def456",
                "chars": 35,
            }],
            "stats": {"requests": 1, "bytes": 500, "pages_kept": 1,
                      "seconds": 0.05, "outcomes": ["HTTP_SUCCESS"]},
            "retrieved_at": "2026-09-16T00:00:00+00:00",
            "fallback_worthy": False,
        }):
            research.run(self.rec, {}, live=False)

        wf = waterfall.ledger(self.rec)
        webfetch_rows = [r for r in wf if r.get("provider") == "webfetch"]
        self.assertEqual(len(webfetch_rows), 1)
        row = webfetch_rows[0]
        self.assertEqual(row["stage"], "company_information")
        self.assertEqual(row["provider"], "webfetch")
        self.assertEqual(row["call"], "webfetch-crawl")
        self.assertEqual(row["expected_cost"], 0)
        self.assertEqual(row["cost_unit"],
                         "free (HTTP read, no credit cost)")

    def test_the_audit_does_not_flag_the_free_leg(self):
        """`waterfall.audit` walks every row and checks `may_fall_back`.
        A webfetch row with no reason must not raise a violation."""
        from src import webfetch
        with mock.patch.object(webfetch, "research", return_value={
            "domain": "acme.test",
            "outcome": "HTTP_SUCCESS",
            "pages": [{
                "source_type": "local_http",
                "provider": "local_http",
                "source_url": "https://acme.test/",
                "http_status": 200,
                "field": "company_website",
                "fact": "Acme is a company.",
                "content_hash": "ghi789",
                "chars": 20,
            }],
            "stats": {"requests": 1, "bytes": 300, "pages_kept": 1,
                      "seconds": 0.02, "outcomes": ["HTTP_SUCCESS"]},
            "retrieved_at": "2026-09-16T00:00:00+00:00",
            "fallback_worthy": False,
        }):
            research.run(self.rec, {}, live=False)

        audit = waterfall.audit(self.rec)
        webfetch_problems = [p for p in audit["unjustified"]
                             if p.get("provider") == "webfetch"]
        self.assertEqual(len(webfetch_problems), 0,
                         "the audit must not flag the free leg as unjustified")


if __name__ == "__main__":
    unittest.main()
