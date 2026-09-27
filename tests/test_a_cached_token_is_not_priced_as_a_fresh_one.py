"""TASK-355: cached tokens price at their own rates, not as fresh input.

A cache read is much cheaper than a fresh input token. A cache write is
more expensive. A model with no published cache rate must NOT have one
invented - the cached portion is unpriced, not free and not guessed.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from src import modelprices as M


class CacheReadIsCheaperThanFresh(unittest.TestCase):
    """Acceptance 1: cache read costs less than fresh input for same count."""

    def test_cache_read_cheaper_than_fresh(self):
        M.reload()
        fresh = M.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"input_tokens": 1000, "output_tokens": 0})
        cached = M.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"cache_read_input_tokens": 1000, "output_tokens": 0})
        self.assertGreater(fresh, 0, "fresh input must cost something")
        self.assertGreater(cached, 0, "cache read must cost something")
        self.assertLess(cached, fresh,
                        "a cache read is not cheaper than a fresh token")
        ratio = cached / fresh
        self.assertLess(ratio, 0.5,
                        f"cache read ratio {ratio:.3f} should be ~0.1")


class CacheWriteCostsMoreThanFresh(unittest.TestCase):
    """Acceptance 2: cache write costs MORE than fresh input."""

    def test_cache_write_more_expensive(self):
        M.reload()
        fresh = M.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"input_tokens": 1000, "output_tokens": 0})
        write = M.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"cache_creation_input_tokens": 1000, "output_tokens": 0})
        self.assertGreater(write, fresh,
                           "cache write must cost more than fresh input")
        ratio = write / fresh
        self.assertGreater(ratio, 1.0,
                           f"cache write ratio {ratio:.3f} should be ~1.25")


class UnpricedCacheRateReturnsNull(unittest.TestCase):
    """Acceptance 3: no cache rate -> usd_estimate None, rate_source unknown."""

    def test_unpriced_cache_returns_null(self):
        M.reload()
        # glm-5.3 has no cache rates in the yaml
        details = M.cost_details(
            "glm-5.3",
            {"input_tokens": 1000, "cache_read_input_tokens": 500,
             "output_tokens": 100})
        self.assertIsNone(details["usd_estimate"],
                          "unpriced cache portion must yield None, not a guess")
        self.assertEqual(details["rate_source"], "unknown")
        # The cache_read component must show rate_per_1m: None
        cr = details["components"].get("cache_read")
        self.assertIsNotNone(cr, "cache_read component must exist")
        self.assertIsNone(cr["rate_per_1m"],
                          "absent rate must be None, not derived")
        self.assertEqual(cr["cost_micro_usd"], 0,
                         "unpriced portion costs 0, not a fabricated amount")


class TotalReconcilesWithComponents(unittest.TestCase):
    """Acceptance 4: total equals sum of four priced components."""

    def test_total_reconciles(self):
        M.reload()
        usage = {
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_creation_input_tokens": 500,
            "cache_read_input_tokens": 3000,
        }
        details = M.cost_details("claude-sonnet-4-20250514", usage)
        component_sum = sum(c["cost_micro_usd"]
                            for c in details["components"].values())
        self.assertEqual(details["cost_micro_usd"], component_sum,
                         "total must equal sum of components - "
                         "a kind cannot be silently dropped")
        # Also check cost_micro_usd agrees
        total = M.cost_micro_usd("claude-sonnet-4-20250514", usage)
        self.assertEqual(total, details["cost_micro_usd"])


class GuardIsSeenToFail(unittest.TestCase):
    """Acceptance 5: reverting cache-rate lookup makes test 1 fail.

    This test does NOT revert anything - it ASSERTS that the lookup is wired.
    The operator manually reverts and restores; this test pins the wiring.
    """

    def test_cache_rates_are_read_separately(self):
        M.reload()
        creation_rate, read_rate = M.cache_rates_for("claude-sonnet-4-20250514")
        self.assertIsNotNone(creation_rate,
                             "cache creation rate must be present")
        self.assertIsNotNone(read_rate,
                             "cache read rate must be present")
        self.assertGreater(creation_rate, 0)
        self.assertLess(read_rate, 1.0,
                        "cache read rate must be a large discount")
        # The rates are NOT equal to the input rate
        inp, _, _, _ = M.price_for("claude-sonnet-4-20250514")
        self.assertNotEqual(read_rate, inp,
                            "cache read rate must differ from input rate")
        self.assertNotEqual(creation_rate, inp,
                            "cache creation rate must differ from input rate")


class NoExistingRowRepriced(unittest.TestCase):
    """Acceptance 6: historical rows keep their recorded expected_cost.

    The yaml change added new keys but did not alter input_per_1m or
    output_per_1m for any model. A call with only prompt_tokens and
    completion_tokens must produce the same cost before and after.
    """

    def test_legacy_usage_unchanged(self):
        M.reload()
        # Claude Sonnet 4: $3 input, $15 output - unchanged by this task
        cost = M.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"prompt_tokens": 1000, "completion_tokens": 100})
        # 1000 * 3.00 / 1M + 100 * 15.00 / 1M = 0.003 + 0.0015 = 0.0045
        # = 4500 micro-USD
        self.assertEqual(cost, 4500,
                         "legacy prompt/completion pricing must be unchanged")

        # GLM: $0.40 input, $1.60 output - unchanged
        cost_glm = M.cost_micro_usd(
            "glm-5.3",
            {"prompt_tokens": 1000, "completion_tokens": 100})
        # 1000 * 0.40 / 1M + 100 * 1.60 / 1M = 0.0004 + 0.00016 = 0.00056
        # = 560 micro-USD
        self.assertEqual(cost_glm, 560)


class BackwardsCompatiblePromptTokens(unittest.TestCase):
    """prompt_tokens and completion_tokens still work alongside input_tokens."""

    def test_both_key_styles_work(self):
        M.reload()
        cost_prompt = M.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"prompt_tokens": 1000, "completion_tokens": 100})
        cost_input = M.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"input_tokens": 1000, "output_tokens": 100})
        self.assertEqual(cost_prompt, cost_input,
                         "prompt_tokens and input_tokens must price the same")


if __name__ == "__main__":
    unittest.main()
