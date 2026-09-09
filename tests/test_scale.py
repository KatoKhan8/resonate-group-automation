"""Scale properties, checked offline: linearity, caching, and no wasted spend.

The point of these is not speed. It is that the *shape* of the work is right:
research follows selection, company pages are read once, and nothing walks the
whole queue once per record.
"""
import os
import shutil
import tempfile
import time
import unittest

from src import benchmark, cadence, clients, costsim, personalization
from tests.campaignbase import CampaignTest


class ScaleTest(CampaignTest):
    def config_with_research(self, **over):
        config = dict(self.config)
        config["research"] = {"recent_signals": {"enabled": True, **over}}
        return config


class TestTheWorkIsLinear(ScaleTest):
    def test_a_bigger_batch_does_not_cost_more_per_record(self):
        """The quadratic pause scan used to show up exactly here."""
        config = self.config
        small = benchmark.measure(40, config)
        large = benchmark.measure(400, config)
        per_small = small["seconds"] / 40
        per_large = large["seconds"] / 400
        self.assertLess(per_large, per_small * 3,
                        f"per-record cost grew: {per_small:.5f} -> {per_large:.5f}")

    def test_the_pause_lookup_is_computed_once_per_batch(self):
        """Passing paused_set is what keeps cadence linear."""
        import inspect
        source = inspect.getsource(cadence.build)
        self.assertIn("paused_set", source)
        self.assertIn("paused_set", inspect.getsource(benchmark.measure))

    def test_a_precomputed_pause_set_gives_the_same_answer(self):
        recs = self.seed_records()
        recs[0]["paused"] = {"since": "x", "reason": "reply_received"}
        precomputed = cadence.paused_domains(recs)
        with_set = cadence.build(recs[0], self.config, paused_set=precomputed)
        with_recs = cadence.build(recs[0], self.config, recs=recs)
        self.assertEqual(bool(with_set["paused"]), bool(with_recs["paused"]))

    def test_a_paused_sibling_still_pauses_through_the_set(self):
        recs = self.seed_records()
        extra = dict(recs[0])
        extra["id"] = "acme-2"
        extra["paused"] = {"since": "x", "reason": "reply_received"}
        recs.append(extra)
        paused_set = cadence.paused_domains(recs)
        timeline = cadence.build(recs[0], self.config, paused_set=paused_set)
        self.assertTrue(timeline["paused"])


class TestNoWastedResearch(ScaleTest):
    def test_person_research_is_planned_per_selected_contact_never_per_found(self):
        """The whole cost argument in one assertion: six people are found per
        company and two are selected, so research is planned twice, not six
        times. At 5,000 domains that difference is 20,000 calls."""
        result = benchmark.measure(200, self.config)
        counters = result["counters"]
        self.assertEqual(counters["contacts_found"],
                         200 * benchmark.FOUND_PER_COMPANY)
        self.assertEqual(counters["person_research_planned"],
                         counters["contacts_selected"])
        self.assertLess(counters["person_research_planned"],
                        counters["contacts_found"])

    def test_company_research_is_planned_once_per_domain_at_most(self):
        result = benchmark.measure(200, self.config)
        self.assertLessEqual(result["counters"]["company_research_planned"], 200)

    def test_selected_is_a_fraction_of_found(self):
        result = benchmark.measure(100, self.config)
        counters = result["counters"]
        self.assertLess(counters["contacts_selected"], counters["contacts_found"])
        self.assertEqual(counters["contacts_selected"],
                         100 * benchmark.CONTACTS_PER_COMPANY)

    def test_verification_follows_selection_not_discovery(self):
        counters = benchmark.measure(100, self.config)["counters"]
        self.assertEqual(counters["verification_ops_would_be"],
                         counters["contacts_selected"])

    def test_llm_calls_follow_selection_too(self):
        counters = benchmark.measure(100, self.config)["counters"]
        self.assertEqual(
            counters["llm_calls_would_be"],
            counters["contacts_selected"] * len(cadence.GENERATED_KEYS))

    def test_company_research_is_not_repeated_per_contact(self):
        rec = self.seed_records()[0]
        config = self.config_with_research()
        first = personalization.plan(rec, config)
        self.assertTrue(first["company"]["planned"])
        personalization.mark_company_done(rec)
        for _ in range(5):
            again = personalization.plan(rec, config)
            self.assertFalse(again["company"]["planned"])

    def test_the_benchmark_touches_no_network(self):
        benchmark.measure(10, self.config)
        self.assertEqual(self.cassette.calls, [])


class TestTheBenchmarkRuns(ScaleTest):
    def test_it_reports_counts_and_timings(self):
        result = benchmark.measure(20, self.config)
        for field in ("size", "seconds", "records_per_second", "timings",
                      "counters"):
            self.assertIn(field, result)

    def test_memory_is_reported_or_absent_never_guessed(self):
        result = benchmark.measure(10, self.config)
        memory = result["memory_mb"]
        self.assertTrue(memory is None or isinstance(memory, float))

    def test_five_thousand_is_offline_and_finishes(self):
        """Slow-ish by test standards, and the whole point of the exercise."""
        started = time.perf_counter()
        result = benchmark.measure(5000, self.config)
        self.assertEqual(result["size"], 5000)
        self.assertEqual(result["counters"]["records"], 5000)
        self.assertEqual(self.cassette.calls, [])
        self.assertLess(time.perf_counter() - started, 120)


class TestTheCostSimulator(unittest.TestCase):
    def test_it_reports_three_columns(self):
        result = costsim.simulate()
        for value in result["operations"].values():
            if isinstance(value, dict):
                self.assertEqual(sorted(value), ["expected", "high", "low"])

    def test_unknown_prices_are_named_rather_than_invented(self):
        result = costsim.simulate()
        for name, value in result["unknown_costs"].items():
            self.assertEqual(value, costsim.UNKNOWN, name)

    def test_known_credit_costs_are_computed(self):
        result = costsim.simulate(domains=1000)
        self.assertGreater(result["known_costs"]["contactout_credits"]["expected"], 0)

    def test_the_assumptions_are_adjustable(self):
        few = costsim.simulate(domains=5000, contacts_per_company=1.0)
        many = costsim.simulate(domains=5000, contacts_per_company=4.0)
        self.assertLess(few["operations"]["contacts_selected"]["expected"],
                        many["operations"]["contacts_selected"]["expected"])

    def test_email_credits_track_selection_not_discovery(self):
        result = costsim.simulate(domains=1000)
        selected = result["operations"]["contacts_selected"]["expected"]
        emails = result["operations"]["contactout_email_credits"]["expected"]
        self.assertEqual(emails, selected)

    def test_the_free_count_runs_on_every_domain(self):
        result = costsim.simulate(domains=1000)
        self.assertEqual(result["operations"]["contactout_people_count"]["expected"],
                         1000)


if __name__ == "__main__":
    unittest.main()
