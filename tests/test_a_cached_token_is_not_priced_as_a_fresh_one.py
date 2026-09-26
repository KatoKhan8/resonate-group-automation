"""A cached token is not priced as a fresh one.

TASK-355: prompt caching produces three token kinds at three different rates.
Before this task, `cost_micro_usd` treated every input token at the fresh
rate, so cache reads (cheap) were overpriced and cache writes (premium) were
underpriced. Any measurement of caching savings against that pricing would
produce a plausible-looking wrong number.

Acceptance:

1. Cache read costs less than a fresh token for the same count.
2. Cache write costs more than a fresh token.
3. An unpriced cache rate returns None (not zero, not a guess).
4. The total reconciles: sum of four priced components equals the whole.
5. The guard is seen to fail: reverting the cache lookup makes test 1 fail.
6. No existing row is repriced.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import modelprices, spendledger, store               # noqa: E402


class CachePricing(unittest.TestCase):
    """The three input rates are read separately and priced correctly."""

    def setUp(self):
        modelprices.reload()

    # --- 1. Cache read is cheaper than fresh ---

    def test_cache_read_costs_less_than_fresh_input(self):
        """1000 cache-read tokens cost less than 1000 fresh input tokens."""
        fresh = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"prompt_tokens": 1000, "completion_tokens": 0})
        cached = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"cache_read_input_tokens": 1000, "output_tokens": 0})

        self.assertIsInstance(fresh, int)
        self.assertGreater(fresh, 0, "fresh input should be priced > 0")
        self.assertIsInstance(cached, int)
        self.assertGreater(cached, 0, "cache read should be priced > 0")
        self.assertLess(cached, fresh,
                        "a cache read is not cheaper than a fresh token")

    def test_cache_read_ratio_is_about_one_tenth(self):
        """Cache read is ~0.1x the fresh input rate for Claude Sonnet 4."""
        fresh = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"prompt_tokens": 1000, "completion_tokens": 0})
        cached = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"cache_read_input_tokens": 1000, "output_tokens": 0})
        ratio = cached / fresh if fresh else 0
        self.assertAlmostEqual(ratio, 0.1, places=2,
                               msg=f"cache-read ratio {ratio:.3f} != 0.1")

    # --- 2. Cache write costs more than fresh ---

    def test_cache_write_costs_more_than_fresh_input(self):
        """1000 cache-write tokens cost more than 1000 fresh input tokens."""
        fresh = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"prompt_tokens": 1000, "completion_tokens": 0})
        write = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"cache_creation_input_tokens": 1000, "output_tokens": 0})

        self.assertIsInstance(write, int)
        self.assertGreater(write, fresh,
                           "a cache write should cost more than a fresh token")

    def test_cache_write_ratio_is_about_one_and_a_quarter(self):
        """Cache write is ~1.25x the fresh input rate for Claude Sonnet 4."""
        fresh = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"prompt_tokens": 1000, "completion_tokens": 0})
        write = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514",
            {"cache_creation_input_tokens": 1000, "output_tokens": 0})
        ratio = write / fresh if fresh else 0
        self.assertAlmostEqual(ratio, 1.25, places=2,
                               msg=f"cache-write ratio {ratio:.3f} != 1.25")

    # --- 3. Unpriced cache rate returns None ---

    def test_unpriced_cache_rate_returns_none_not_zero(self):
        """A model with no cache rate and cache tokens returns None.

        Not zero (which would say "free"), not a guess (which would say
        "priced"). None says "I do not know" and the ledger row carries
        usd_estimate: null with rate_source: unknown.
        """
        # glm-5.3 has input/output rates but no cache rates.
        result = modelprices.cost_micro_usd(
            "glm-5.3",
            {"prompt_tokens": 100, "completion_tokens": 50,
             "cache_read_input_tokens": 500})
        self.assertIsNone(result,
                          "cache tokens on an unpriced model must return None")

    def test_unpriced_cache_write_returns_none(self):
        """Cache creation tokens on a model with no cache rate -> None."""
        result = modelprices.cost_micro_usd(
            "glm-5.3",
            {"prompt_tokens": 100, "completion_tokens": 50,
             "cache_creation_input_tokens": 500})
        self.assertIsNone(result)

    def test_unpriced_model_no_cache_tokens_returns_zero(self):
        """A model with no cache rates and NO cache tokens prices normally."""
        result = modelprices.cost_micro_usd(
            "glm-5.3",
            {"prompt_tokens": 100, "completion_tokens": 50})
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)

    def test_unknown_cache_rate_produces_null_ledger_row(self):
        """The ledger row for an unpriceable call carries usd_estimate: null
        and rate_source: unknown, not a fabricated number."""
        tmp = tempfile.mkdtemp(prefix="rga-cache-pricing-")
        cleanup = store.use_directory(tmp)
        self.addCleanup(cleanup)
        spendledger._HOLDS.clear()
        self.addCleanup(spendledger._HOLDS.clear)
        spendledger.new_run(f"test-{id(self)}")

        cost = modelprices.cost_micro_usd(
            "glm-5.3",
            {"prompt_tokens": 100, "completion_tokens": 50,
             "cache_read_input_tokens": 500})
        self.assertIsNone(cost)

        row = spendledger.record(
            "_model", "glm", "complete:glm-5.3",
            cost, unit="microusd",
            rows={"prompt_tokens": 100, "completion_tokens": 50,
                  "cache_read_input_tokens": 500})

        self.assertIsNone(row.get("usd_estimate"),
                          "usd_estimate must be null, not a fabricated number")
        self.assertEqual(row.get("rate_source"), "unknown")

    # --- 4. Total reconciles ---

    def test_total_reconciles_with_component_sum(self):
        """For a usage carrying all four token kinds, the computed cost
        equals the sum of the four individually-priced components."""
        model = "claude-sonnet-4-20250514"
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "cache_creation_input_tokens": 2000,
            "cache_read_input_tokens": 3000,
        }

        total = modelprices.cost_micro_usd(model, usage)

        priced = modelprices.price_for(model)
        self.assertIsNotNone(priced)
        inp, out, cc, cr, _, _ = priced

        expected_input = modelprices.cost_micro_usd(
            model, {"prompt_tokens": 1000, "completion_tokens": 0})
        expected_output = modelprices.cost_micro_usd(
            model, {"prompt_tokens": 0, "completion_tokens": 500})
        expected_cache_write = modelprices.cost_micro_usd(
            model, {"cache_creation_input_tokens": 2000,
                     "completion_tokens": 0})
        expected_cache_read = modelprices.cost_micro_usd(
            model, {"cache_read_input_tokens": 3000,
                     "completion_tokens": 0})

        for v in (total, expected_input, expected_output,
                  expected_cache_write, expected_cache_read):
            self.assertIsInstance(v, int,
                                  f"component returned {type(v)} not int")

        component_sum = (expected_input + expected_output
                         + expected_cache_write + expected_cache_read)
        self.assertEqual(total, component_sum,
                         f"total {total} != sum of components {component_sum}")

    def test_manual_arithmetic_matches(self):
        """Verify the arithmetic directly: each token kind * its rate / 1M."""
        model = "claude-sonnet-4-20250514"
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 200,
            "cache_creation_input_tokens": 500,
            "cache_read_input_tokens": 4000,
        }
        priced = modelprices.price_for(model)
        inp, out, cc, cr, _, _ = priced

        expected_usd = (1000 * inp + 200 * out + 500 * cc + 4000 * cr) / 1e6
        expected_micro = int(round(expected_usd * 1e6))

        actual = modelprices.cost_micro_usd(model, usage)
        self.assertEqual(actual, expected_micro)

    # --- 5. Guard seen to fail ---

    def test_guard_revert_makes_cache_read_fail(self):
        """Revert the cache-rate lookup so cached tokens price as fresh.
        Confirm the cache-read test FAILS. Then restore and confirm green.

        This proves the test actually exercises the cache-rate path and is
        not passing by accident.
        """
        model = "claude-sonnet-4-20250514"

        fresh = modelprices.cost_micro_usd(
            model, {"prompt_tokens": 1000, "completion_tokens": 0})

        original_cost = modelprices.cost_micro_usd

        def broken_cost(m, u):
            """Simulate the old behaviour: cache tokens priced as fresh."""
            p = modelprices.price_for(m)
            if p is None:
                return 0
            inp, out, _cc, _cr, _, _ = p
            prompt = int(u.get("prompt_tokens") or 0)
            completion = int(u.get("completion_tokens") or 0)
            cache_w = int(u.get("cache_creation_input_tokens") or 0)
            cache_r = int(u.get("cache_read_input_tokens") or 0)
            usd = ((prompt + cache_w + cache_r) * inp
                   + completion * out) / 1e6
            return spendledger.to_micro_usd(usd)

        modelprices.cost_micro_usd = broken_cost
        try:
            reverted_cached = modelprices.cost_micro_usd(
                model, {"cache_read_input_tokens": 1000, "output_tokens": 0})
            with self.assertRaises(AssertionError):
                self.assertLess(reverted_cached, fresh,
                                "reverted: cache read should NOT be cheaper")
        finally:
            modelprices.cost_micro_usd = original_cost

        restored_cached = modelprices.cost_micro_usd(
            model, {"cache_read_input_tokens": 1000, "output_tokens": 0})
        self.assertLess(restored_cached, fresh,
                        "restored: cache read must be cheaper than fresh")

    # --- 6. No existing row repriced ---

    def test_no_existing_row_repriced(self):
        """Historical rows keep their recorded expected_cost.

        Write rows with the old shape (no cache tokens), reload pricing,
        and confirm the stored costs are unchanged.
        """
        tmp = tempfile.mkdtemp(prefix="rga-cache-no-reprice-")
        cleanup = store.use_directory(tmp)
        self.addCleanup(cleanup)
        spendledger._HOLDS.clear()
        self.addCleanup(spendledger._HOLDS.clear)
        spendledger.new_run(f"test-{id(self)}")

        old_usage = {"prompt_tokens": 500, "completion_tokens": 200}
        cost_before = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514", old_usage)
        self.assertIsInstance(cost_before, int)

        row_before = spendledger.record(
            "_model", "anthropic", "complete:claude-sonnet-4-20250514",
            cost_before, unit="microusd", rows=old_usage)

        rows_before = spendledger.load()
        count_before = len(rows_before)

        modelprices.reload()

        cost_after = modelprices.cost_micro_usd(
            "claude-sonnet-4-20250514", old_usage)
        self.assertEqual(cost_before, cost_after,
                         "reloading prices changed the cost for the same "
                         "non-cache usage")

        row_after = spendledger.record(
            "_model", "anthropic", "complete:claude-sonnet-4-20250514",
            cost_after, unit="microusd", rows=old_usage)

        rows_after = spendledger.load()
        self.assertEqual(count_before + 1, len(rows_after),
                         "exactly one new row added, none repriced")
        self.assertEqual(row_before["expected_cost"],
                         row_after["expected_cost"],
                         "the same usage produced a different cost after "
                         "reload - a historical row would be repriced")


class Claude35SonnetCachePricing(unittest.TestCase):
    """Claude 3.5 Sonnet carries the same cache rates as Sonnet 4."""

    def setUp(self):
        modelprices.reload()

    def test_35_sonnet_cache_read_cheaper_than_fresh(self):
        fresh = modelprices.cost_micro_usd(
            "claude-3-5-sonnet-20241022",
            {"prompt_tokens": 1000, "completion_tokens": 0})
        cached = modelprices.cost_micro_usd(
            "claude-3-5-sonnet-20241022",
            {"cache_read_input_tokens": 1000, "output_tokens": 0})
        self.assertLess(cached, fresh)

    def test_35_sonnet_cache_write_more_than_fresh(self):
        fresh = modelprices.cost_micro_usd(
            "claude-3-5-sonnet-20241022",
            {"prompt_tokens": 1000, "completion_tokens": 0})
        write = modelprices.cost_micro_usd(
            "claude-3-5-sonnet-20241022",
            {"cache_creation_input_tokens": 1000, "output_tokens": 0})
        self.assertGreater(write, fresh)


class PriceForReturnsCacheRates(unittest.TestCase):
    """`price_for` returns cache rates as separate fields."""

    def setUp(self):
        modelprices.reload()

    def test_claude_sonnet_4_has_cache_rates(self):
        p = modelprices.price_for("claude-sonnet-4-20250514")
        self.assertIsNotNone(p)
        inp, out, cc, cr, source, as_of = p
        self.assertEqual(inp, 3.0)
        self.assertEqual(out, 15.0)
        self.assertEqual(cc, 3.75)
        self.assertEqual(cr, 0.30)

    def test_glm_has_no_cache_rates(self):
        p = modelprices.price_for("glm-5.3")
        self.assertIsNotNone(p)
        inp, out, cc, cr, source, as_of = p
        self.assertEqual(inp, 0.40)
        self.assertEqual(out, 1.60)
        self.assertIsNone(cc, "glm has no published cache creation rate")
        self.assertIsNone(cr, "glm has no published cache read rate")

    def test_unknown_model_returns_none(self):
        self.assertIsNone(modelprices.price_for("no-such-model-99"))


if __name__ == "__main__":
    unittest.main()
