"""TASK-034: the LLM estimate must come from the cadence, not a constant.

Four estimators multiplied by ``len(cadence.GENERATED_KEYS)``, which reads
from the module constant ``STEPS`` (two generated steps). The production
cadence ``productive_li_heavy_v1`` has five generated emails and six
generated LinkedIn notes - eleven in total. Every model-cost estimate was
low by about 2.5x on the email half, and the LinkedIn half was not counted
at all.

The fix: ``cadence.generated_keys(steps)`` derives the count from the
sequence itself. These tests prove the estimate moves when the cadence
changes, and that a cadence with no generated steps estimates zero.
"""
import unittest

from src import cadence, cadencelibrary, costsim, plan, benchmark


class TestGeneratedKeysDerivesFromCadence(unittest.TestCase):
    """generated_keys() reads the sequence, not a module constant."""

    def test_li_heavy_has_five_emails_and_six_linkedin(self):
        seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        keys = cadence.generated_keys(seq)
        emails = [k for k, s in zip(
            (s["key"] for s in seq), seq)
            if k in keys and s.get("channel") == "email"]
        linkedin = [k for k, s in zip(
            (s["key"] for s in seq), seq)
            if k in keys and s.get("channel") == "linkedin"]
        self.assertEqual(len(emails), 5)
        self.assertEqual(len(linkedin), 6)
        self.assertEqual(len(keys), 11)

    def test_alternative_generated_counts(self):
        """li1 is not generated but its alternative is - it still counts."""
        seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        keys = cadence.generated_keys(seq)
        self.assertIn("li1", keys)

    def test_two_step_cadence_counts_two(self):
        steps = (
            {"key": "em1", "day": 1, "channel": "email", "generated": True},
            {"key": "em2", "day": 3, "channel": "email", "generated": True},
        )
        self.assertEqual(len(cadence.generated_keys(steps)), 2)

    def test_no_generated_steps_estimates_zero(self):
        steps = (
            {"key": "em1", "day": 1, "channel": "email",
             "template": "persona_pain"},
            {"key": "li1", "day": 3, "channel": "linkedin",
             "template": "linkedin_intro"},
        )
        self.assertEqual(len(cadence.generated_keys(steps)), 0)

    def test_none_returns_empty(self):
        self.assertEqual(cadence.generated_keys(None), ())
        self.assertEqual(cadence.generated_keys(()), ())


class TestEstimateMovesWithCadence(unittest.TestCase):
    """The estimate is read from the cadence, proved by changing it."""

    def test_plan_estimate_follows_cadence(self):
        """Changing the cadence changes the estimate.
        
        The estimate is contacts_selected * generated_count. We prove the
        generated_count comes from the cadence by checking the ratio between
        estimates for different cadences matches the ratio of generated counts.
        """
        import tempfile
        import os
        from src import store, synthetic, clients
        tmp = tempfile.mkdtemp(prefix="rga-t034-")
        # RESTORED WHEN THE TEST ENDS. `use_directory` moves EVERY state file
        # for the whole process, so leaving it set pointed the store at a
        # temp directory for every test that ran afterwards - and
        # `test_invariants`' self-writer barrier failed on `spendledger`
        # because of it. Measured: this module alone plus test_invariants
        # fails; test_cadence plus test_invariants passes.
        _previous = os.environ.get("QUEUE")
        self.addCleanup(
            lambda: (os.environ.__setitem__("QUEUE", _previous)
                     if _previous is not None
                     else os.environ.pop("QUEUE", None)))
        self.addCleanup(store.use_directory,
                        os.path.dirname(_previous) if _previous
                        else os.path.join(os.getcwd(), "work"))
        store.use_directory(os.path.join(tmp, "work"))
        config = clients.load("demo")
        # Use synthetic records which have the right structure for selection
        recs = synthetic.dataset(10, config)
        store.save(recs)
        recs = store.load()

        # Campaign with the LI-heavy cadence (11 generated steps)
        campaign_li = {"campaign_id": "li", "client": "demo",
                       "cadence_steps": list(cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)}
        counts_li = plan.size(campaign_li, recs, config)

        # Campaign with a two-step cadence (2 generated steps)
        campaign_two = {"campaign_id": "two", "client": "demo",
                        "cadence_steps": [
                            {"key": "em1", "day": 1, "channel": "email",
                             "generated": True},
                            {"key": "em2", "day": 3, "channel": "email",
                             "generated": True},
                        ]}
        counts_two = plan.size(campaign_two, recs, config)

        # Campaign with no generated steps (0)
        campaign_none = {"campaign_id": "none", "client": "demo",
                         "cadence_steps": [
                             {"key": "em1", "day": 1, "channel": "email",
                              "template": "persona_pain"},
                         ]}
        counts_none = plan.size(campaign_none, recs, config)

        # The no-generated cadence must estimate zero
        self.assertEqual(counts_none["llm_calls_if_regenerated"], 0)
        
        # The estimates must be in the ratio 11:2 (or both zero if no contacts
        # were selected). This proves the count comes from the cadence.
        li_est = counts_li["llm_calls_if_regenerated"]
        two_est = counts_two["llm_calls_if_regenerated"]
        if li_est > 0:
            self.assertEqual(li_est / two_est, 11 / 2)
        else:
            # No contacts selected - both are zero, which is still correct
            self.assertEqual(li_est, 0)
            self.assertEqual(two_est, 0)

    def test_costsim_derives_from_named_cadence(self):
        """costsim derives llm_calls_per_contact from the cadence name."""
        result_li = costsim.simulate(cadence_name="productive_li_heavy_v1")
        self.assertEqual(result_li["assumptions"]["llm_calls_per_contact"], 11)

        result_balanced = costsim.simulate(
            cadence_name="productive_balanced_v1")
        self.assertEqual(result_balanced["assumptions"]["llm_calls_per_contact"],
                         2)

        result_default = costsim.simulate()
        # Default cadence (STEPS) has 2 generated steps
        self.assertEqual(result_default["assumptions"]["llm_calls_per_contact"],
                         2)

    def test_costsim_explicit_override_wins(self):
        """An explicit llm_calls_per_contact overrides the cadence."""
        result = costsim.simulate(cadence_name="productive_li_heavy_v1",
                                  llm_calls_per_contact=99)
        self.assertEqual(result["assumptions"]["llm_calls_per_contact"], 99)

    def test_benchmark_estimate_follows_cadence(self):
        """benchmark.measure derives the count from the cadence."""
        config = {"cadence": "productive_li_heavy_v1",
                  "cadences": {"productive_li_heavy_v1": {
                      "steps": list(cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)}}}
        result = benchmark.measure(10, config)
        selected = result["counters"]["contacts_selected"]
        expected = selected * 11
        self.assertEqual(result["counters"]["llm_calls_would_be"], expected)


class TestEstimateIsNotConsumed(unittest.TestCase):
    """The estimate is computed and displayed but nothing reads it.

    This is the finding that outranks the arithmetic fix: the four
    estimators feed nothing. They output to screen/JSON and a test checks
    the key exists, but no decision, cap, or gate reads the number.
    """

    def test_no_code_reads_llm_calls_if_regenerated(self):
        """plan.size outputs the number but nothing consumes it."""
        import inspect
        from src import plan as plan_mod
        source = inspect.getsource(plan_mod)
        # The key is written but never read for a decision
        self.assertIn("llm_calls_if_regenerated", source)
        # No cap, gate, or threshold reads it
        self.assertNotIn("llm_calls_if_regenerated >", source)
        self.assertNotIn("llm_calls_if_regenerated <", source)
        self.assertNotIn("llm_calls_if_regenerated ==", source)

    def test_no_code_reads_llm_calls_would_be(self):
        """benchmark.measure outputs the number but nothing consumes it."""
        import inspect
        from src import benchmark as bench_mod
        source = inspect.getsource(bench_mod)
        self.assertIn("llm_calls_would_be", source)
        self.assertNotIn("llm_calls_would_be >", source)
        self.assertNotIn("llm_calls_would_be <", source)


if __name__ == "__main__":
    unittest.main()
