"""TASK-208: the free crawler goes before anything paid, and Grok goes fourth.

The PROVIDER-ROUTING-POLICY.md order is:

    1 ContactOut   2 ContactOut cache   3 FREE crawler
    4 Grok / xAI   5 other paid providers   6 Claude

These tests assert the waterfall table matches that order. Every change must
move free EARLIER or paid LATER, never the reverse.
"""
import unittest

from src import waterfall


class TestFreeCrawlBeforePaid(unittest.TestCase):
    """The free crawler precedes every paid provider in each stage."""

    def _paid_providers(self, stage):
        """Providers in a stage that are neither ContactOut nor webfetch."""
        return [s["provider"] for s in waterfall.STAGES[stage]["providers"]
                if s["provider"] not in (waterfall.CONTACTOUT,
                                         waterfall.WEBFETCH)]

    def test_company_info_webfetch_before_every_paid(self):
        """In company_information, webfetch precedes every paid provider."""
        providers = [s["provider"] for s in
                     waterfall.STAGES[waterfall.COMPANY_INFO]["providers"]]
        if waterfall.WEBFETCH not in providers:
            self.fail("webfetch is not in company_information")
        wf_idx = providers.index(waterfall.WEBFETCH)
        for paid in (waterfall.BLITZ, waterfall.APIFY, waterfall.XAI):
            if paid in providers:
                self.assertLess(wf_idx, providers.index(paid),
                                f"webfetch must precede {paid} in "
                                f"company_information")

    def test_company_research_webfetch_before_apify(self):
        """In company_research, webfetch precedes Apify (paid)."""
        providers = [s["provider"] for s in
                     waterfall.STAGES[waterfall.COMPANY_RESEARCH]["providers"]]
        if waterfall.WEBFETCH not in providers:
            self.fail("webfetch is not in company_research")
        self.assertLess(providers.index(waterfall.WEBFETCH),
                        providers.index(waterfall.APIFY),
                        "webfetch must precede Apify in company_research")

    def test_webfetch_is_free(self):
        """webfetch costs zero in every stage where it appears."""
        for stage in waterfall.STAGE_NAMES:
            step = waterfall.step_for(stage, waterfall.WEBFETCH,
                                      "webfetch-crawl")
            if step is None:
                continue
            from src import enrich
            self.assertEqual(enrich.COSTS.get("webfetch-crawl", -1), 0,
                             f"webfetch-crawl must be free in {stage}")

    def test_every_change_moves_free_earlier_or_paid_later(self):
        """Direction check: no paid provider was moved ahead of webfetch."""
        for stage in (waterfall.COMPANY_INFO, waterfall.COMPANY_RESEARCH):
            providers = [s["provider"] for s in
                         waterfall.STAGES[stage]["providers"]]
            if waterfall.WEBFETCH not in providers:
                continue
            wf_idx = providers.index(waterfall.WEBFETCH)
            for i, p in enumerate(providers):
                if p in (waterfall.CONTACTOUT, waterfall.WEBFETCH):
                    continue
                self.assertLess(wf_idx, i,
                                f"{p} at position {i} is before webfetch "
                                f"at {wf_idx} in {stage}; direction is wrong")


class TestGrokPosition(unittest.TestCase):
    """Grok is layer 4: after ContactOut and free crawl, before paid."""

    def test_xai_exists_in_company_information(self):
        providers = [s["provider"] for s in
                     waterfall.STAGES[waterfall.COMPANY_INFO]["providers"]]
        self.assertIn(waterfall.XAI, providers,
                      "Grok must have a position in company_information")

    def test_xai_is_a_fallback(self):
        step = waterfall.step_for(waterfall.COMPANY_INFO, waterfall.XAI,
                                  "xai-research")
        self.assertIsNotNone(step, "xai step must exist in company_information")
        self.assertTrue(step.get("is_fallback"),
                        "xai must be marked as a fallback")

    def test_xai_requires_reason(self):
        step = waterfall.step_for(waterfall.COMPANY_INFO, waterfall.XAI,
                                  "xai-research")
        self.assertTrue(step.get("requires_reason"),
                        "xai must require a reason to be called")

    def test_xai_reason_is_confirmed_miss_not_error_or_timeout(self):
        """Grok is licensed by a ContactOut confirmed miss, never an error."""
        reasons = waterfall.accepted_reasons(waterfall.COMPANY_INFO,
                                             waterfall.XAI, "xai-research")
        self.assertTrue(reasons, "xai must have at least one accepted reason")
        error_reasons = {"contactout_error", "contactout_timeout",
                         "contactout_rate_limited"}
        for r in reasons:
            self.assertNotIn(r, error_reasons,
                             f"xai must not accept error/timeout reason: {r}")

    def test_xai_after_contactout_and_webfetch(self):
        """Grok is after ContactOut and the free crawl in company_information."""
        providers = [s["provider"] for s in
                     waterfall.STAGES[waterfall.COMPANY_INFO]["providers"]]
        xai_idx = providers.index(waterfall.XAI)
        co_idx = providers.index(waterfall.CONTACTOUT)
        self.assertGreater(xai_idx, co_idx,
                           "xai must be after ContactOut")
        if waterfall.WEBFETCH in providers:
            wf_idx = providers.index(waterfall.WEBFETCH)
            self.assertGreater(xai_idx, wf_idx,
                               "xai must be after the free crawl")

    def test_xai_before_paid_providers(self):
        """Grok is layer 4: before Blitz and Apify (layer 5)."""
        providers = [s["provider"] for s in
                     waterfall.STAGES[waterfall.COMPANY_INFO]["providers"]]
        xai_idx = providers.index(waterfall.XAI)
        for paid in (waterfall.BLITZ, waterfall.APIFY):
            if paid in providers:
                self.assertLess(xai_idx, providers.index(paid),
                                f"xai must precede {paid} (layer 4 < layer 5)")

    def test_xai_cost_is_usd_shaped(self):
        """~$0.20 per domain, in xAI ticks (10B ticks per dollar)."""
        from src import enrich
        cost = enrich.COSTS.get("xai-research")
        self.assertIsNotNone(cost, "xai-research must have a cost entry")
        self.assertGreater(cost, 0, "xai-research must cost something")
        ticks_per_usd = 10_000_000_000
        usd = cost / ticks_per_usd
        self.assertAlmostEqual(usd, 0.20, places=1,
                               msg="xai-research should cost ~$0.20")

    def test_xai_cost_unit_is_named(self):
        """The cost unit must name ticks, not present the cost as free."""
        step = waterfall.step_for(waterfall.COMPANY_INFO, waterfall.XAI,
                                  "xai-research")
        unit = waterfall.COST_UNITS.get(waterfall.XAI, "").lower()
        self.assertIn("xai", unit,
                      "xai cost unit must reference xAI ticks")


class TestContactOutStillFirst(unittest.TestCase):
    """The invariant survives: every stage still starts with ContactOut."""

    def test_every_stage_starts_with_contactout(self):
        for stage in waterfall.STAGE_NAMES:
            self.assertTrue(waterfall.contactout_is_first(stage), stage)


class TestXaiOffByDefault(unittest.TestCase):
    """Grok must not be callable in a production run without explicit enable."""

    def test_xai_has_no_caller_in_src(self):
        """The adapter is reachable only through the waterfall table.

        No module in src/ imports xai for production use. The waterfall table
        declares the step; an operator must explicitly enable it.
        """
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", "from.*xai import\\|import.*xai", "src/"],
            capture_output=True, text=True)
        hits = [line for line in result.stdout.strip().split("\n")
                if line and "test_" not in line
                and "providers/xai.py" not in line]
        self.assertEqual(hits, [],
                         f"xai should have no production caller in src/: "
                         f"{hits}")


if __name__ == "__main__":
    unittest.main()
