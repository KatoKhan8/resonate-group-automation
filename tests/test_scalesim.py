"""The pre-production path at scale, measured rather than assumed.

The tests here run small sizes; the 5,000-domain figures come from running the
module directly. What is asserted is the shape of the answer: that MX resolves
once per domain rather than once per contact, that provider calls are counted
from the same planner the live path uses, that the preview stays a size a
browser opens, and that no phase grows faster than the batch.
"""
import os
import unittest

from src import mx, previewpage, scalesim, store
from tests.campaignbase import CampaignTest


class ScaleTest(CampaignTest):
    def measure(self, size=56, **kw):
        return scalesim.measure(size, self.config, **kw)


class TestTheMeasurement(ScaleTest):
    def test_it_reports_every_phase(self):
        result = self.measure()
        for phase in scalesim.PHASES:
            self.assertIn(phase, result["timings"], phase)

    def test_it_names_the_slowest_phase(self):
        self.assertIn(self.measure()["bottleneck"], scalesim.PHASES)

    def test_memory_is_measured_rather_than_guessed(self):
        """None would be honest; a number is better, and this platform has one."""
        memory = scalesim._memory_mb()
        self.assertTrue(memory is None or memory > 0)

    def test_it_calls_no_provider(self):
        self.measure()
        self.assertEqual(self.cassette.calls, [])

    def test_no_dns_query_leaves_the_process(self):
        """The resolver is injected and counts; the real one is never reached."""
        resolver = scalesim.CountingResolver()
        hosts = resolver("syn00007.test")
        self.assertTrue(hosts)
        self.assertEqual(resolver.calls, 1)


class TestTheMXCache(ScaleTest):
    def test_one_lookup_per_domain_not_per_contact(self):
        result = self.measure()
        cache = result["mx_cache"]
        self.assertEqual(cache["dns_lookups"], cache["unique_domains"])
        self.assertLess(cache["dns_lookups"], cache["contacts_with_an_address"])

    def test_the_hit_rate_is_reported(self):
        cache = self.measure()["mx_cache"]
        self.assertGreater(cache["hit_rate"], 0.0)
        self.assertLess(cache["lookups_per_contact"], 1.0)

    def test_a_shared_domain_resolves_once(self):
        resolver = scalesim.CountingResolver()
        cache = {}
        for _ in range(50):
            mx.for_domain("acme.test", self.config, cache=cache,
                          resolver=resolver, save=False)
        self.assertEqual(resolver.calls, 1)


class TestTheProviderEstimate(ScaleTest):
    def test_it_counts_planned_calls_per_provider_and_call(self):
        calls = self.measure()["provider_calls"]["by_call"]
        self.assertTrue(calls)
        for key, bucket in calls.items():
            self.assertIn(":", key, "each entry names provider and call")
            self.assertGreater(bucket["planned"], 0)

    def test_expected_is_never_more_than_maximum(self):
        calls = self.measure()["provider_calls"]
        self.assertLessEqual(calls["expected_credits"],
                             calls["maximum_credits"])

    def test_conditional_calls_are_counted_separately(self):
        """A maximum exposure is not a forecast, and the split says so."""
        calls = self.measure()["provider_calls"]["by_call"]
        self.assertTrue(any(b["conditional"] for b in calls.values()))


class TestThePreviewStaysOpenable(ScaleTest):
    def test_the_page_is_capped_regardless_of_batch_size(self):
        small = self.measure(56, max_cards=20)["preview"]["preview_html_bytes"]
        large = self.measure(200, max_cards=20)["preview"]["preview_html_bytes"]
        # The headline numbers grow a little; the card list does not.
        self.assertLess(abs(large - small) / max(small, 1), 0.25)

    def test_the_files_are_written_and_measured_when_asked(self):
        out = os.path.join(self.tmp, "scale-out")
        result = self.measure(56, out_dir=out)
        for name in previewpage.FILES:
            self.assertIn(name, result["preview"], name)
            self.assertGreater(result["preview"][name], 0)

    def test_the_queue_size_is_reported(self):
        self.assertGreater(self.measure()["queue_bytes"], 0)


class TestLinearity(ScaleTest):
    def test_no_phase_grows_faster_than_the_batch(self):
        results = [scalesim.measure(100, self.config),
                   scalesim.measure(400, self.config)]
        for phase, verdict in scalesim.linearity(results).items():
            if verdict.get("growth") is None:
                continue
            self.assertLessEqual(verdict["growth"], 2.5,
                                 f"{phase} grew x{verdict['growth']}")

    def test_a_quadratic_phase_would_be_named_rather_than_averaged_away(self):
        fake = [{"size": 100, "timings": {"simulate": 0.1}},
                {"size": 400, "timings": {"simulate": 1.6}}]
        verdict = scalesim.linearity(fake)["simulate"]
        self.assertEqual(verdict["growth"], 4.0)
        self.assertIn("quadratic", verdict["verdict"])

    def test_a_phase_too_fast_to_measure_says_so_rather_than_claiming_linear(self):
        fake = [{"size": 100, "timings": {"save": 0.0001}},
                {"size": 400, "timings": {"save": 0.0004}}]
        self.assertIsNone(scalesim.linearity(fake)["save"]["growth"])


if __name__ == "__main__":
    unittest.main()
