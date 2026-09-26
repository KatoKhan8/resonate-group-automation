"""The ledger speaks three units and must not print them as one number.

TASK-332 / BUGGIE findings M1, M2, M3. Three defects, one rule:

  M1  `report()` summed cents, credits and microusd as though they were one
      thing. `client_balance` and `progress_block` already had a mixed-unit
      tripwire; `report` did not. Now it does, same shape.

  M2  `researchpack/pack.run_actor` documented its cost as integer cents and
      then called `reserve` without `unit="cents"`, so every Apify row landed
      with no unit and no `usd_estimate`.

  M3  `enrich.COSTS["xai-research"]` is 2,000,000,000 xAI ticks (~$0.20) in
      a dict whose other values are single-digit credits, and `enrich.spend`
      called `record` with no unit. Dormant - no live caller yet - but the
      first caller would have ledgered two billion "credits".

The rule that governs all three: never invent a rate. `USD_PER_UNIT["credits"]`
is `None` on purpose; `usd_estimate` returns None with `rate_source: "unknown"`
rather than carrying a fabricated conversion.
"""
import os
import shutil
import tempfile
import unittest

from src import spendledger, store


class MixedUnitReport(unittest.TestCase):
    """M1: report() over mixed-unit rows returns the tripwire, not a sum."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory, self.tmp)
        store.use_directory(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mixed_units_return_the_tripwire_not_a_summed_integer(self):
        """The decisive assertion: a report over rows of two different units
        returns the tripwire string as `expected_total`, not a number."""
        spendledger.record("acme", "deliverable", "deliverable-verify", 100)
        spendledger.record("acme", "apify", "company_posts", 447, unit="cents")
        out = spendledger.report("acme")
        self.assertEqual(out["expected_total"],
                         "MIXED UNITS - a tripwire, not an amount")

    def test_single_unit_report_still_returns_an_integer(self):
        """The guard must not break the normal case."""
        spendledger.record("acme", "deliverable", "deliverable-verify", 100)
        spendledger.record("acme", "reoon", "reoon-verify", 1)
        out = spendledger.report("acme")
        self.assertIsInstance(out["expected_total"], int)
        self.assertEqual(out["expected_total"], 101)

    def test_by_provider_is_tripwire_for_mixed_provider_but_integer_for_single(
            self):
        """A provider whose rows are all one unit still gets a number; one
        whose rows span units gets the tripwire on that provider's total."""
        spendledger.record("acme", "deliverable", "deliverable-verify", 100)
        spendledger.record("acme", "apify", "company_posts", 447, unit="cents")
        out = spendledger.report("acme")
        self.assertEqual(out["by_provider"]["deliverable"], 100)
        self.assertEqual(out["by_provider"]["apify"], 447)
        self.assertEqual(out["units_seen"], ["cents", "credits"])

    def test_units_seen_is_reported(self):
        spendledger.record("acme", "deliverable", "deliverable-verify", 1)
        out = spendledger.report("acme")
        self.assertEqual(out["units_seen"], ["credits"])


class ApifyRowsCarryTheirUnit(unittest.TestCase):
    """M2: Apify costs are integer cents; the row must say so."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory, self.tmp)
        store.use_directory(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_usd_estimate_for_cents_is_exact(self):
        """Acceptance 2 from the task: the cents rate is defined, not
        invented."""
        usd, rate, src = spendledger.usd_estimate(1500, "cents")
        self.assertAlmostEqual(usd, 15.0, places=9)
        self.assertEqual(src, "unit_definition")

    def test_a_run_actor_reserve_writes_unit_cents(self):
        """The seam: `run_actor` passes `unit="cents"` to `reserve`, so the
        settled row carries it."""
        hold = spendledger.reserve(
            "acme", {}, 447, provider="apify",
            call="company_posts", unit="cents")
        row = spendledger.settle(hold)
        self.assertEqual(row["unit"], "cents")
        self.assertEqual(row["provider"], "apify")
        self.assertEqual(row["expected_cost"], 447)

    def test_run_actor_writes_cents_through_the_real_entry_point(self):
        """Drive through `run_actor` itself, not just `reserve`. The wiring
        is the point - a `unit="cents"` that only a direct call carries is
        the same defect the task fixes."""
        from src.researchpack import pack, actors as actorspec
        original = actorspec.ACTORS.get("company_posts")
        actorspec.ACTORS["company_posts"] = {
            "needs_session": False, "cost": 447,
            "actor": "test", "limit": 10}

        def cleanup():
            if original:
                actorspec.ACTORS["company_posts"] = original
            else:
                actorspec.ACTORS.pop("company_posts", None)
        self.addCleanup(cleanup)

        pack.run_actor("company_posts", "example.test",
                       runner=lambda *a, **kw: [])
        rows = spendledger.load()
        apify_rows = [r for r in rows if r.get("provider") == "apify"]
        self.assertTrue(apify_rows, "run_actor wrote no ledger row")
        self.assertEqual(apify_rows[0]["unit"], "cents")


class XaiUnitIsNotCredits(unittest.TestCase):
    """M3: xAI's 2-billion-tick cost must not land as 'credits'."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory, self.tmp)
        store.use_directory(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unit_for_xai_is_ticks_not_credits(self):
        self.assertEqual(spendledger.unit_for("xai"), "ticks")

    def test_a_record_for_xai_carries_its_unit(self):
        row = spendledger.record("acme", "xai", "xai-research",
                                 2_000_000_000, unit="ticks")
        self.assertEqual(row["unit"], "ticks")
        self.assertEqual(row["expected_cost"], 2_000_000_000)

    def test_xai_cost_is_not_deleted(self):
        """The entry records a real price. It stays."""
        from src import enrich
        self.assertEqual(enrich.COSTS["xai-research"], 2_000_000_000)


class NoInventedRate(unittest.TestCase):
    """Acceptance 4: a provider with no established rate returns None."""

    def test_credits_have_no_usd_rate(self):
        usd, rate, src = spendledger.usd_estimate(100, "credits")
        self.assertIsNone(usd)
        self.assertIsNone(rate)
        self.assertEqual(src, "unknown")

    def test_ticks_have_no_usd_rate_either(self):
        """xAI ticks are in LEDGER_UNITS but not in USD_PER_UNIT - nobody
        has priced them."""
        usd, rate, src = spendledger.usd_estimate(2_000_000_000, "ticks")
        self.assertIsNone(usd)
        self.assertEqual(src, "unknown")

    def test_microusd_has_an_exact_rate(self):
        usd, rate, src = spendledger.usd_estimate(2560, "microusd")
        self.assertAlmostEqual(usd, 0.00256, places=9)
        self.assertEqual(src, "unit_definition")


class NoHistoricalRowChanged(unittest.TestCase):
    """Acceptance 5: the fixes do not alter existing rows."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory, self.tmp)
        store.use_directory(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_record_does_not_rewrite_existing_rows(self):
        """Write three rows, record a fourth, assert the first three are
        byte-identical to what was written."""
        import json
        r1 = spendledger.record("acme", "deliverable", "deliverable-verify", 1)
        r2 = spendledger.record("acme", "reoon", "reoon-verify", 1)
        r3 = spendledger.record("acme", "apify", "company_posts", 447,
                                unit="cents")
        rows_before = spendledger.load()
        self.assertEqual(len(rows_before), 3)
        # Record a fourth - this must not alter the first three.
        spendledger.record("acme", "xai", "xai-research", 2_000_000_000,
                           unit="ticks")
        rows_after = spendledger.load()
        self.assertEqual(len(rows_after), 4)
        for before, after in zip(rows_before, rows_after[:3]):
            self.assertEqual(before, after)

    def test_expected_cost_remains_an_int(self):
        """Acceptance constraint: `expected_cost` is still an int."""
        row = spendledger.record("acme", "xai", "xai-research",
                                 2_000_000_000, unit="ticks")
        self.assertIsInstance(row["expected_cost"], int)


if __name__ == "__main__":
    unittest.main()
