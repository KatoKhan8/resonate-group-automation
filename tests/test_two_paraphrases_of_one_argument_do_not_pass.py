"""Two paraphrases of one argument must not pass the sequence gate.

TASK-339.  The gate's lexical overlap check was blind to paraphrases:
two steps arguing the same thing in different words scored 0.0 against
a 0.45 threshold and passed.  The semantic check added in TASK-339 uses
concept groups (semantic roles) to catch paraphrases deterministically,
without a model call.  It adds refusals; it never removes a lexical
failure.
"""
import unittest

from src import sequencegate


# The exact pair from sequencegate.py's own comment - the measured
# counter-example that proved lexical overlap cannot see a paraphrase.
PARAPHRASE_A = (
    "Your margins are thin on fixed scope work and nobody sees it.")
PARAPHRASE_B = (
    "Profit on flat fee projects gets squeezed, invisible until later.")


def _check(emails):
    """Run sequencegate.check on a minimal sequence with qualification."""
    s = {
        "company": "Acme",
        "hypothesis": "Agencies often find margin visible only after "
                      "delivery.",
        "subjects": {"A": "acme work", "B": "follow-up", "C": "last note"},
        "emails": emails,
    }
    return sequencegate.check(s, qualification="QUALIFIED_RICH")


class ParaphraseDetection(unittest.TestCase):
    """The known counter-example now fails."""

    def test_the_exact_counter_example_from_the_comment_now_fails(self):
        # Lexical overlap: 0.0.  Semantic overlap: 1.0 (MARGIN, LOW,
        # PROJECT_TYPE, UNSEEN all shared).  Before TASK-339 this passed.
        lex = sequencegate.overlap(PARAPHRASE_A, PARAPHRASE_B)
        self.assertLess(lex, 0.45,
                        "lexical overlap should be below threshold (%.3f)"
                        % lex)
        sem = sequencegate.semantic_overlap(PARAPHRASE_A, PARAPHRASE_B)
        self.assertGreater(sem, 0.0,
                           "semantic overlap should be nonzero (%.3f)" % sem)
        r = _check({"em1": PARAPHRASE_A, "em2": PARAPHRASE_B})
        self.assertFalse(r["passed"],
                         "paraphrase pair must not pass the gate")
        f = [x for x in r["failures"]
             if x["check"] == "followup_adds_value"]
        self.assertTrue(f, "expected a followup_adds_value failure")
        self.assertEqual(f[0]["step"], "em2")
        self.assertIn("paraphrases", f[0]["why"])

    def test_a_third_paraphrase_of_the_same_argument_also_fails(self):
        c = ("Return on fixed-fee engagements is eroded and you only "
             "see it afterwards.")
        sem = sequencegate.semantic_overlap(PARAPHRASE_A, c)
        self.assertGreater(sem, 0.0)
        r = _check({"em1": PARAPHRASE_A, "em2": c})
        self.assertFalse(r["passed"])

    def test_near_duplicate_still_fails_via_lexical_overlap(self):
        r = _check({"em1": PARAPHRASE_A, "em2": PARAPHRASE_A})
        self.assertFalse(r["passed"])
        f = [x for x in r["failures"]
             if x["check"] == "followup_adds_value"]
        self.assertTrue(f)
        self.assertIn("repeats", f[0]["why"])


class GenuinelyDifferentArgumentsStillPass(unittest.TestCase):
    """A gate that refuses every sequence is not a fix.

    These are pairs that make genuinely different arguments and must PASS.
    The _check helper only tests the followup_adds_value dimension - other
    checks (claims_supported, reason_for_outreach) are not relevant here
    because we supply no facts.
    """

    def _pair_passes_semantic(self, a, b):
        """True when no followup_adds_value failure fires."""
        r = _check({"em1": a, "em2": b})
        sem_failures = [f for f in r["failures"]
                        if f["check"] == "followup_adds_value"]
        return not sem_failures, sem_failures

    def test_hiring_versus_margin(self):
        ok, failures = self._pair_passes_semantic(
            "We help agencies track project margin while work runs.",
            "Saw you are hiring a senior brand designer in New York.")
        self.assertTrue(ok, failures)

    def test_speed_versus_profit(self):
        ok, failures = self._pair_passes_semantic(
            "Your margins are thin on fixed scope work.",
            "Deploying to production takes your team three days.")
        self.assertTrue(ok, failures)

    def test_cost_analysis_versus_margin(self):
        ok, failures = self._pair_passes_semantic(
            "Your margins are thin on fixed scope work.",
            "Cloud costs are high across the industry.")
        self.assertTrue(ok, failures)

    def test_customer_churn_versus_margin(self):
        ok, failures = self._pair_passes_semantic(
            "Your margins are thin on fixed scope work.",
            "Customer churn is high for saas companies.")
        self.assertTrue(ok, failures)

    def test_pricing_strategy_versus_margin(self):
        ok, failures = self._pair_passes_semantic(
            "Your margins are thin on fixed scope work.",
            "Your pricing strategy needs a redesign.")
        self.assertTrue(ok, failures)

    def test_automation_versus_profitability(self):
        ok, failures = self._pair_passes_semantic(
            "Agencies lose money on fixed fee projects.",
            "Manual QA is slowing your release cycle.")
        self.assertTrue(ok, failures)

    def test_revenue_growth_versus_cost_cutting(self):
        ok, failures = self._pair_passes_semantic(
            "Revenue is growing faster than expected this quarter.",
            "We need to cut costs in operations.")
        self.assertTrue(ok, failures)

    def test_hiring_versus_customer_retention(self):
        ok, failures = self._pair_passes_semantic(
            "Hiring developers is taking too long.",
            "Customer retention dropped ten percent last quarter.")
        self.assertTrue(ok, failures)

    def test_product_launch_versus_margin(self):
        ok, failures = self._pair_passes_semantic(
            "Your margins are thin on fixed scope work.",
            "The new product launch went well last week.")
        self.assertTrue(ok, failures)

    def test_office_relocation_versus_profit(self):
        ok, failures = self._pair_passes_semantic(
            "Profit on flat fee projects gets squeezed.",
            "Are you considering an office relocation?")
        self.assertTrue(ok, failures)

    def test_five_step_good_sequence_still_passes(self):
        s = {
            "company": "Huemor",
            "hypothesis": "Agencies running many short website projects "
                          "often find margin is only visible after delivery.",
            "subjects": {"A": "x", "B": "y", "C": "z"},
            "emails": {
                "em1": "Jeff, Huemor designs websites and digital strategies "
                       "for B2B clients. Agencies running many short projects "
                       "often find margin only shows up after delivery. "
                       "Productive puts budget against time while the "
                       "project runs. Are you tracking that live or after "
                       "the fact?",
                "em2": "Hiring a senior brand designer usually means "
                       "resourcing gets tighter before it gets easier. Who "
                       "decides which project they land on first?",
                "em3": "A quick note on how the budget view works in "
                       "practice. Hours book against a quote, and the burn "
                       "is visible daily. Useful if I sent an example?",
                "em4": "One benchmark worth knowing: most agencies discover "
                       "overruns at invoicing. Reviewing weekly changes "
                       "that.",
                "em5": "Closing the loop here. Happy to leave it if the "
                       "timing is wrong.",
            },
        }
        r = sequencegate.check(s, qualification="QUALIFIED_RICH")
        sem_failures = [f for f in r["failures"]
                        if f["check"] == "followup_adds_value"]
        self.assertFalse(sem_failures,
                         "good sequence must not trigger semantic failure: %s"
                         % sem_failures)


class SemanticCannotOverrideDeterministic(unittest.TestCase):
    """The semantic layer adds refusals; it never removes them.

    Directives section 9: 'Keep deterministic safety gates authoritative.
    Semantic validation may add another layer, but an LLM score must never
    override deterministic failures.'

    The semantic check is deterministic, but the principle applies: when
    the lexical check fails, the semantic check cannot rescue it.
    """

    def test_lexical_failure_stands_regardless_of_semantic(self):
        text = "Your margins are thin on fixed scope work and nobody sees it."
        near_copy = ("Your margins are thin on fixed scope work and nobody "
                     "sees it until later.")
        r = _check({"em1": text, "em2": near_copy})
        self.assertFalse(r["passed"])
        lex_failures = [f for f in r["failures"]
                        if "repeats" in f.get("why", "")]
        self.assertTrue(lex_failures,
                        "lexical failure must be present")

    def test_both_checks_can_fire_on_different_steps(self):
        em1 = "Your margins are thin on fixed scope work and nobody sees it."
        em2 = "Something about hiring a designer and resourcing."
        em3 = ("Your margins are thin on fixed scope work and nobody sees "
               "it until later.")
        em4 = "Profit on flat fee projects gets squeezed, invisible until later."
        r = _check({"em1": em1, "em2": em2, "em3": em3, "em4": em4})
        self.assertFalse(r["passed"])
        steps_failed = {f["step"] for f in r["failures"]
                        if f["check"] == "followup_adds_value"}
        self.assertIn("em3", steps_failed,
                       "near-copy must fail via lexical overlap")
        self.assertIn("em4", steps_failed,
                       "paraphrase must fail via semantic overlap")


class SemanticOverlapUnitTests(unittest.TestCase):
    """Unit tests for the semantic_overlap function itself."""

    def test_identical_texts_score_high(self):
        t = "margin thin on fixed scope work"
        s = sequencegate.semantic_overlap(t, t)
        self.assertGreater(s, 0.6)

    def test_completely_different_texts_score_zero(self):
        a = "the quick brown fox jumps over the lazy dog"
        b = "python javascript typescript rust golang"
        self.assertEqual(sequencegate.semantic_overlap(a, b), 0.0)

    def test_empty_text_returns_zero(self):
        self.assertEqual(sequencegate.semantic_overlap("", "hello"), 0.0)
        self.assertEqual(sequencegate.semantic_overlap("hello", ""), 0.0)

    def test_one_shared_concept_is_not_enough(self):
        # min_shared_concepts=2 by default.  One shared concept should
        # return 0 even if concept_overlap would be 1.0.
        a = "margin thin"
        b = "margin high"
        self.assertEqual(sequencegate.semantic_overlap(a, b), 0.0)

    def test_same_direction_different_concepts_is_not_enough(self):
        # Both LOW but different concepts.
        a = "margin thin"
        b = "churn high"
        self.assertEqual(sequencegate.semantic_overlap(a, b), 0.0)


if __name__ == "__main__":
    unittest.main()
