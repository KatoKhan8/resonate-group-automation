"""The query layer a segment explorer UI will sit on, and how it behaves at scale.

Two properties carry this file. A filter either matches stated vocabulary or
raises - a UI that silently returns everything for a typo'd filter teaches
people to trust a number that is wrong. And qualification has to stay linear:
it runs over the whole upload before anything is spent, so a quadratic pass
here is the difference between six seconds and an afternoon.
"""
import datetime
import time
import unittest

from src import (campaignseg, companies, dmplan, explorer, icp, qualify,
                 report, scalesim, schedule, segments, store)
from tests.campaignbase import CampaignTest


class ExplorerTest(CampaignTest):
    SIZE = 200

    def batch(self, size=None):
        recs = companies.dataset(size or self.SIZE, client="productive",
                                 batch="b1")
        return qualify.run(recs, client="productive", batch="b1",
                           store_result=False)

    def companies(self, size=None):
        return self.batch(size)["companies"]


class TestFiltering(ExplorerTest):
    def test_every_documented_filter_can_be_applied(self):
        entries = self.companies()
        for name in explorer.FILTERS:
            source, field, values = explorer.FILTERS[name]
            value = (values[0] if values else
                     explorer._value(entries[0], source, field))
            if isinstance(value, list):
                value = value[0] if value else None
            explorer.apply_filters(entries, {name: value})

    def test_an_unknown_filter_raises_rather_than_matching_everything(self):
        entries = self.companies()
        with self.assertRaises(KeyError):
            explorer.apply_filters(entries, {"vibes": "good"})

    def test_filters_combine_with_and(self):
        entries = self.companies()
        qualified = explorer.apply_filters(entries, {"icp_status": "qualified"})
        both = explorer.apply_filters(entries, {"icp_status": "qualified",
                                                "icp_tier": icp.TIER_A})
        self.assertLessEqual(len(both), len(qualified))

    def test_a_score_range_filters_on_the_number(self):
        entries = self.companies()
        high = explorer.apply_filters(entries, {"score_min": 70})
        for entry in high:
            self.assertGreaterEqual(entry["verdict"]["icp_score"], 70)

    def test_the_manual_review_flag_covers_both_review_buckets(self):
        entries = self.companies()
        flagged = explorer.apply_filters(entries, {"manual_review": True})
        for entry in flagged:
            self.assertIn(entry["verdict"]["icp_status"],
                          (icp.REVIEW, icp.UNKNOWN))

    def test_the_enrichment_flag_matches_the_cost_plan(self):
        entries = self.companies()
        needed = explorer.apply_filters(entries, {"requires_enrichment": True})
        for entry in needed:
            self.assertTrue(entry["cost_plan"]["enrichment_required"])
            self.assertGreater(entry["cost_plan"]["expected_credits"], 0)

    def test_the_schedulable_flag_matches_the_timezone(self):
        entries = self.companies()
        for entry in explorer.apply_filters(entries, {"schedulable": False}):
            self.assertIsNone(entry["segment"]["timezone"])

    def test_a_persona_filter_matches_membership_not_equality(self):
        entries = self.companies()
        found = explorer.apply_filters(entries, {"persona": "operations"})
        for entry in found:
            self.assertIn("operations",
                          entry["persona_plan"]["persona_priority"])

    def test_a_state_filter_reads_the_record_state(self):
        entries = self.companies()
        for name in (dmplan.NOT_PROCESSED,):
            explorer.apply_filters(entries, {"state": name})


class TestListing(ExplorerTest):
    def test_the_total_is_reported_beside_the_page(self):
        entries = self.companies()
        page = explorer.list_companies(entries, limit=5)
        self.assertEqual(page["returned"], 5)
        self.assertEqual(page["total"], len(entries))
        self.assertGreater(page["total"], page["returned"])

    def test_paging_walks_the_whole_result(self):
        entries = self.companies()
        first = explorer.list_companies(entries, limit=10, offset=0)
        second = explorer.list_companies(entries, limit=10, offset=10)
        self.assertNotEqual([r["record_id"] for r in first["rows"]],
                            [r["record_id"] for r in second["rows"]])

    def test_the_default_sort_is_the_priority_order(self):
        entries = self.companies()
        page = explorer.list_companies(entries, limit=5)
        self.assertEqual(page["rows"][0]["icp_tier"], icp.TIER_A)

    def test_sorting_is_deterministic(self):
        entries = self.companies()
        first = explorer.list_companies(entries, limit=20)["rows"]
        second = explorer.list_companies(entries, limit=20)["rows"]
        self.assertEqual([r["record_id"] for r in first],
                         [r["record_id"] for r in second])

    def test_a_row_carries_enough_to_decide_without_the_dossier(self):
        row = explorer.list_companies(self.companies(), limit=1)["rows"][0]
        for field in ("company", "domain", "icp_status", "icp_tier",
                      "icp_score", "vertical", "region", "timezone",
                      "max_contacts", "segment_key"):
            self.assertIn(field, row, field)


class TestFacets(ExplorerTest):
    def test_every_facet_is_counted(self):
        counts = explorer.facets(self.companies())
        for name in explorer.FACETS:
            self.assertIn(name, counts, name)

    def test_a_facet_total_matches_the_company_count(self):
        entries = self.companies()
        counts = explorer.facets(entries)
        self.assertEqual(sum(counts["icp_status"].values()), len(entries))

    def test_facets_are_ordered_by_size(self):
        counts = explorer.facets(self.companies())["vertical"]
        values = list(counts.values())
        self.assertEqual(values, sorted(values, reverse=True))


class TestTheDrillPath(ExplorerTest):
    def test_the_batch_level_lists_its_segments(self):
        result = self.batch()
        view = explorer.batch_view(result)
        self.assertEqual(view["level"], "batch")
        self.assertTrue(view["segments"])
        self.assertIn("summary", view)

    def test_a_segment_explains_why_its_members_are_together(self):
        result = self.batch()
        view = explorer.batch_view(result)
        key = view["segments"][0]["segment_key"]
        segment = explorer.segment_view(result["companies"], key)
        self.assertEqual(segment["segment_key"], key)
        self.assertTrue(segment["why_together"])
        self.assertTrue(segment["shared"])

    def test_an_empty_segment_says_so_rather_than_erroring(self):
        view = explorer.segment_view(self.companies(), "PRODUCTIVE-NOWHERE")
        self.assertEqual(view["companies"], 0)
        self.assertIn("no company", view["why"])

    def test_a_company_drills_to_its_full_dossier(self):
        entries = self.companies()
        record_id = entries[0]["record"]["id"]
        view = explorer.company_view(entries, record_id)
        self.assertEqual(view["level"], "company")
        self.assertIn("icp", view)
        self.assertIn("cost_plan", view)

    def test_an_unknown_company_returns_nothing_rather_than_guessing(self):
        self.assertIsNone(explorer.company_view(self.companies(), "nope"))

    def test_the_persona_level_declares_contacts_as_a_future_level(self):
        entries = self.companies()
        view = explorer.persona_view(entries, entries[0]["record"]["id"])
        self.assertEqual(view["contacts"], [])
        self.assertFalse(view["contacts_available"])
        self.assertTrue(view["why_no_contacts"])

    def test_the_contract_documents_the_whole_path(self):
        contract = explorer.contract()
        self.assertEqual(contract["drill"],
                         ["batch", "segment", "company", "persona_plan",
                          "contacts"])
        self.assertTrue(contract["filters"])
        self.assertTrue(contract["notes"])

    def test_nothing_in_the_explorer_spends_anything(self):
        import inspect
        source = inspect.getsource(explorer)
        for banned in ("providers.request", "enrich.run", "push.run",
                       "live=True"):
            self.assertNotIn(banned, source, banned)

    def test_no_provider_was_called(self):
        self.batch()
        self.assertEqual(self.cassette.calls, [])


class TestQualificationStaysLinear(unittest.TestCase):
    """A quadratic pass here is six seconds against an afternoon.

    It runs over the entire upload before anything is spent, so it is the one
    place where 5,000 rather than 500 has to cost ten times as much and not a
    hundred.
    """

    # Best of three, after a warm-up. A single wall-clock sample is the wrong
    # instrument for this question: one GC pause during the large run reads as
    # superlinear growth and fails a test about an algorithm. The floor of
    # several runs is what "does this scale" actually asks about, and it is
    # stable to within a few percent where a single sample is not.
    TRIALS = 3

    def _best(self, fn, recs):
        return min(self._once(fn, recs) for _ in range(self.TRIALS))

    def _once(self, fn, recs):
        start = time.perf_counter()
        fn(recs)
        return time.perf_counter() - start

    def ratio(self, fn, small=200, large=800):
        quick = companies.dataset(small, client="productive")
        slow = companies.dataset(large, client="productive")
        self._once(fn, quick)                    # warm caches, compile regexes
        first = self._best(fn, quick)
        second = self._best(fn, slow)
        if first < 0.01:
            return 1.0
        return (second / first) / (large / small)

    def test_qualification_is_linear(self):
        self.assertLess(
            self.ratio(lambda recs: qualify.run(recs, client="productive",
                                                store_result=False)),
            2.0)

    def test_segment_assignment_is_linear(self):
        def assign(recs):
            result = qualify.run(recs, client="productive", store_result=False)
            campaignseg.assign(result["companies"])
        self.assertLess(self.ratio(assign), 2.0)

    def test_scoring_alone_is_linear(self):
        def score_all(recs):
            for rec in recs:
                icp.score(rec)
        self.assertLess(self.ratio(score_all), 2.0)

    def test_classification_alone_is_linear(self):
        def classify_all(recs):
            for rec in recs:
                segments.classify(rec)
        self.assertLess(self.ratio(classify_all), 2.0)

    def test_filtering_a_large_batch_is_linear(self):
        def filter_all(recs):
            result = qualify.run(recs, client="productive", store_result=False)
            explorer.apply_filters(result["companies"],
                                   {"icp_status": "qualified"})
        self.assertLess(self.ratio(filter_all), 2.0)

    def test_contradiction_detection_is_linear(self):
        """It runs inside every score, so a quadratic here is a quadratic in
        the whole qualification pass."""
        def detect(recs):
            for rec in recs:
                icp.contradictions(rec, segments.classify(rec))
        self.assertLess(self.ratio(detect), 2.0)

    def test_confidence_components_are_linear(self):
        def components(recs):
            for rec in recs:
                segment = segments.classify(rec)
                icp.confidence_components(rec, 6, [], segment,
                                          icp.DEFAULT_THRESHOLDS)
        self.assertLess(self.ratio(components), 2.0)

    def test_scheduling_a_batch_is_linear(self):
        """A batch schedule builds one timeline per company and must not
        compare companies to each other to do it."""
        start = datetime.date(2026, 9, 1)

        def schedule_all(recs):
            segs = [dict(segments.classify(rec), domain=rec.get("domain"))
                    for rec in recs]
            schedule.for_batch(segs, start)
        self.assertLess(self.ratio(schedule_all), 2.0)

    def test_the_qualification_report_is_linear(self):
        """It walks the batch once per section, not once per record."""
        def report_all(recs):
            qualify.run(recs, client="productive", store_result=True)
            report.qualification_report(recs=recs)
        self.assertLess(self.ratio(report_all), 2.0)


class TestTheScaleSimulation(CampaignTest):
    def test_it_reports_every_number_the_brief_asks_for(self):
        result = scalesim.qualify_scale(120, self.config)
        for name in ("seconds", "memory_mb", "status", "tier", "confidence",
                     "needs_manual_review", "schedulable", "distribution",
                     "segments", "cost"):
            self.assertIn(name, result, name)

    def test_the_distributions_cover_the_gtm_dimensions(self):
        result = scalesim.qualify_scale(120, self.config)
        for name in ("vertical", "subvertical", "region", "country",
                     "employee_band", "timezone", "business_model"):
            self.assertIn(name, result["distribution"], name)

    def test_the_cost_reports_expected_and_maximum_separately(self):
        cost = scalesim.qualify_scale(120, self.config)["cost"]
        self.assertLess(cost["expected_credits"], cost["maximum_credits"])
        self.assertGreater(cost["fallback_exposure"], 0)

    def test_every_status_appears_in_a_realistic_mix(self):
        result = scalesim.qualify_scale(120, self.config)
        for status in icp.STATUSES:
            self.assertGreater(result["status"][status], 0, status)

    def test_it_names_the_slowest_phase(self):
        result = scalesim.qualify_scale(120, self.config)
        self.assertIn(result["bottleneck"], scalesim.QUALIFY_PHASES)

    def test_it_calls_no_provider(self):
        scalesim.qualify_scale(120, self.config)
        self.assertEqual(self.cassette.calls, [])

    def test_five_thousand_companies_stay_inside_a_sane_budget(self):
        """The real thing, once. Nothing here touches a network."""
        result = scalesim.qualify_scale(5000, self.config)
        self.assertEqual(sum(result["status"].values()), 5000)
        self.assertLess(result["seconds"], 120,
                        f"5,000 companies took {result['seconds']}s")
        # A segment may stay under the floor only where the ladder ran out.
        #
        # This asserted zero, which was a property of one distribution rather
        # than of the system: `campaignseg` merges up `LADDER` and stops at
        # `persona_only`, so a persona with fewer companies than the minimum
        # has nowhere left to merge and cannot reach it. Softening the ICP
        # changed the qualified mix and produced exactly that case. What must
        # remain true is that nothing gives up early.
        from src import campaignseg
        self.assertEqual(
            [r for r in result["segments"]["below_minimum_rungs"]
             if r != campaignseg.LADDER[-1]], [],
            "a segment stopped short of the last rung with room left to merge")
        self.assertGreater(result["cost"]["planned_dm_searches"], 0)
        # The point of the whole pipeline: most of the upload costs nothing.
        self.assertLess(result["cost"]["planned_dm_searches"], 5000)


if __name__ == "__main__":
    unittest.main()
