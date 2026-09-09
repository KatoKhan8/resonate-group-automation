"""`--spend` with no `--cap` was an unbounded spend over a whole batch.

`enrich.Budget(None)` means UNLIMITED, and neither `--cap` had a default. So
`python -m src.run --spend` over a 30,000-domain queue had no ceiling at all: on
the order of 420,000 credits at policy defaults, with nothing in the process able
to stop it. The pilot ceilings cap companies, contacts and sends rather than
credits, and `dm_plan.max_batch_credits` is parsed from client config and used
only to compute a display string.

CLAUDE.md's rule is "Cap before you fan out". So the CLI refuses rather than
picking a number - a default ceiling is a guess about somebody else's budget, and
a guess that is too high is indistinguishable from none.

WHERE THE CHECK LIVES IS THE DESIGN. It is at the CLI, not inside `run()`,
because `cap=None` written in code is a choice and `--cap` omitted at a terminal
is an oversight. Every test that exercises enrichment logic rather than budget
policy keeps calling `run(live=True)` directly, which is why the first version of
this - a refusal inside `run()` - turned dozens of unrelated tests red for a
reason that had nothing to do with what they were testing.
"""
import unittest

from src import enrich


class ALiveRunNeedsACeiling(unittest.TestCase):
    def test_live_with_no_cap_is_refused(self):
        with self.assertRaises(enrich.NoBudget):
            enrich.require_cap(True, None)

    def test_the_refusal_says_what_to_do_instead(self):
        """A refusal nobody can act on gets worked around."""
        with self.assertRaises(enrich.NoBudget) as caught:
            enrich.require_cap(True, None)
        self.assertIn("--cap", str(caught.exception))
        self.assertIn("--cap 0", str(caught.exception))

    def test_an_explicit_cap_is_accepted(self):
        self.assertTrue(enrich.require_cap(True, 200))

    def test_an_explicit_zero_is_accepted_and_is_not_read_as_absent(self):
        """Zero is a real answer: plan everything, spend nothing."""
        self.assertTrue(enrich.require_cap(True, 0))

    def test_a_dry_run_never_needs_a_cap(self):
        """Dry is always safe, so requiring a ceiling for it would be theatre."""
        self.assertTrue(enrich.require_cap(False, None))


class TheBudgetItselfStillMeansWhatItSaid(unittest.TestCase):
    """The refusal is at the CLI. `Budget` is unchanged, and a library caller
    keeps the explicit semantics it already had."""

    def test_an_unlimited_budget_is_still_expressible_in_code(self):
        budget = enrich.Budget(None)
        self.assertTrue(budget.affordable(10 ** 6))
        self.assertIsNone(budget.remaining())

    def test_a_zero_budget_refuses_anything_that_costs(self):
        budget = enrich.Budget(0)
        self.assertFalse(budget.affordable(1))
        self.assertFalse(budget.charge(1, "decision-makers"))
        self.assertEqual(budget.refused, ["decision-makers"])

    def test_a_zero_budget_still_permits_a_free_call(self):
        """Recorded rather than fixed: `people-count` costs 0, so `--cap 0`
        still performs free provider reads. It spends no credits, which is what
        the cap governs, but it is not the same as making no call."""
        budget = enrich.Budget(0)
        self.assertTrue(budget.affordable(0))
        self.assertTrue(budget.charge(0, "people-count"))
        self.assertEqual(budget.spent, 0)

    def test_a_budget_refuses_rather_than_going_over(self):
        budget = enrich.Budget(10)
        self.assertTrue(budget.charge(10, "decision-makers"))
        self.assertFalse(budget.charge(1, "email-verifier"))
        self.assertEqual(budget.spent, 10)


class TheCliRefusesRatherThanRunning(unittest.TestCase):
    """Exit code 2 and no run, on both entry points."""

    def test_enrich_main_refuses_live_with_no_cap(self):
        self.assertEqual(enrich.main(["--live"]), 2)

    def test_run_main_refuses_spend_with_no_cap(self):
        from src import run as runner
        self.assertEqual(runner.main(["--spend"]), 2)


if __name__ == "__main__":
    unittest.main()
