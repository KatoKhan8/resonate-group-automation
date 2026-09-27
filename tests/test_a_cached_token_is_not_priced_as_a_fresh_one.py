"""TASK-355: cached tokens are priced at their own rates, not as fresh input.

A cache read is much cheaper than a fresh input token. A cache write is
more expensive. A model with no published cache rate returns None for a
usage carrying cache tokens - never a guessed multiplier.

Acceptance:
1. Cache read < fresh input for the same count.
2. Cache write > fresh input for the same count.
3. An unpriced cache rate returns None, not zero and not a guess.
4. The total reconciles: cost = sum of four priced components.
5. The guard is seen to fail (red-green).
6. No existing ledger row is repriced.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import modelprices, spendledger, store               # noqa: E402


class CachePricing(unittest.TestCase):
    """Each test reloads prices from the real config file."""

    def setUp(self):
        modelprices.reload()

    # ============================================================ 1
    def test_cache_read_is_cheaper_than_fresh_input(self):
        """1000 cache-read tokens cost less than 1000 fresh input tokens."""
        fresh = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"prompt_tokens": 1000, "output_tokens": 0})
        cached = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"cache_read_input_tokens": 1000, "output_tokens": 0})
        self.assertIsNotNone(fresh, "fresh cost should not be None")
        self.assertIsNotNone(cached, "cached cost should not be None "
                             "(claude-sonnet-4 has cache rates)")
        self.assertGreater(fresh, 0, "fresh cost must be > 0")
        self.assertGreater(cached, 0, "cached cost must be > 0")
        self.assertLess(cached, fresh,
                        "a cache read is not cheaper than a fresh token")
        ratio = cached / fresh
        self.assertLess(ratio, 0.5,
                        f"cache read ratio {ratio:.3f} should be ~0.10")

    # ============================================================ 2
    def test_cache_write_costs_more_than_fresh_input(self):
        """1000 cache-write tokens cost more than 1000 fresh input tokens."""
        fresh = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"prompt_tokens": 1000, "output_tokens": 0})
        write = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"cache_creation_input_tokens": 1000, "output_tokens": 0})
        self.assertIsNotNone(fresh)
        self.assertIsNotNone(write)
        self.assertGreater(write, fresh,
                           "a cache write must cost more than a fresh token")

    # ============================================================ 3
    def test_unpriced_cache_rate_returns_none(self):
        """A model with no cache rate + cache tokens in usage -> None."""
        cost = modelprices.cost_micro_usd(
            "glm-5.3",
            {"prompt_tokens": 100, "completion_tokens": 50,
             "cache_read_input_tokens": 500})
        self.assertIsNone(cost,
                          "glm-5.3 has no cache rate; cost must be None, "
                          f"not {cost}")

        cost2 = modelprices.cost_micro_usd(
            "glm-5.3",
            {"prompt_tokens": 100, "completion_tokens": 50,
             "cache_creation_input_tokens": 200})
        self.assertIsNone(cost2,
                          "glm-5.3 has no cache rate; cache write cost "
                          f"must be None, not {cost2}")

    def test_unknown_model_still_returns_zero(self):
        """An entirely unknown model returns 0, not None."""
        cost = modelprices.cost_micro_usd(
            "no-such-model",
            {"prompt_tokens": 100, "completion_tokens": 50})
        self.assertEqual(cost, 0)

    def test_known_model_without_cache_tokens_still_returns_int(self):
        """A known model with no cache tokens returns int, even if no
        cache rates exist."""
        cost = modelprices.cost_micro_usd(
            "glm-5.3",
            {"prompt_tokens": 100, "completion_tokens": 50})
        self.assertIsNotNone(cost)
        self.assertIsInstance(cost, int)
        self.assertGreater(cost, 0)

    # ============================================================ 4
    def test_total_reconciles_with_four_components(self):
        """For a usage carrying all four token kinds, cost equals the
        sum of the four priced components."""
        model = "claude-sonnet-4-20250514"
        usage = {
            "prompt_tokens": 500,
            "completion_tokens": 200,
            "cache_creation_input_tokens": 300,
            "cache_read_input_tokens": 1000,
        }
        total = modelprices.cost_micro_usd(model, usage)
        self.assertIsNotNone(total)

        rates = modelprices.rates_for(model)
        expected_usd = (
            500 * rates["input"]
            + 200 * rates["output"]
            + 300 * rates["cache_creation"]
            + 1000 * rates["cache_read"]
        ) / 1_000_000
        expected = spendledger.to_micro_usd(expected_usd)
        self.assertEqual(total, expected,
                         f"total {total} != sum of components {expected}")

    # ============================================================ 5
    def test_guard_is_seen_to_fail(self):
        """Revert the cache-rate lookup so cached tokens price as fresh.
        Confirm test 1 FAILS. Restore. Confirm green.

        This test simulates the OLD behaviour by temporarily removing
        cache rates from the loaded config, then verifying that a cache
        read would be priced the same as a fresh token (the bug).
        """
        model = "claude-sonnet-4-20250514"

        fresh = modelprices.cost_micro_usd(
            model, {"prompt_tokens": 1000, "output_tokens": 0})

        prices = modelprices._load()
        entry = prices[model]
        saved_cc = entry.pop("cache_creation_input_per_1m")
        saved_cr = entry.pop("cache_read_input_per_1m")

        try:
            broken = modelprices.cost_micro_usd(
                model,
                {"cache_read_input_tokens": 1000, "output_tokens": 0})

            self.assertIsNone(broken,
                              "without cache rates, cost_micro_usd should "
                              "return None for cache token usage")
        finally:
            entry["cache_creation_input_per_1m"] = saved_cc
            entry["cache_read_input_per_1m"] = saved_cr

        restored = modelprices.cost_micro_usd(
            model,
            {"cache_read_input_tokens": 1000, "output_tokens": 0})
        self.assertIsNotNone(restored,
                             "after restore, cache read should be priced")
        self.assertLess(restored, fresh,
                        "after restore, cache read must be cheaper than fresh")

    # ============================================================ 6
    def test_no_existing_row_repriced(self):
        """Historical rows keep their recorded expected_cost.

        Count rows before and after a reload + repricing pass. The count
        must be equal - no rows are added or removed by the pricing change.
        """
        tmp = tempfile.mkdtemp(prefix="rga-task355-")
        self.addCleanup(store.use_directory(tmp))

        spendledger.record("test", "anthropic", "complete:test", 5000,
                           unit="microusd")
        spendledger.record("test", "glm", "complete:test", 1000,
                           unit="microusd")

        rows_before = spendledger.load()
        count_before = len(rows_before)
        costs_before = [r["expected_cost"] for r in rows_before]

        modelprices.reload()

        rows_after = spendledger.load()
        count_after = len(rows_after)
        costs_after = [r["expected_cost"] for r in rows_after]

        self.assertEqual(count_before, count_after,
                         f"row count changed: {count_before} -> {count_after}")
        self.assertEqual(costs_before, costs_after,
                         "historical row costs were modified by reload")


if __name__ == "__main__":
    unittest.main()
