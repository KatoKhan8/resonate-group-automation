#!/usr/bin/env python3
"""A GLM verdict's "new failures" must be a real set difference.

## WHY THIS EXISTS

`scripts/glm_verify_branch.py` decides a branch's verdict partly by subtracting
the standing suite baseline from the branch's failing tests. The two sides were
shaped differently and nobody reconciled them:

    unittest -v writes      FAIL: test_x (tests.mod.Class.test_x)
    the baseline holds      FAIL tests.mod.Class.test_x

The extractor stored the whole `"test_x (tests.mod.Class.test_x)"` string and
subtracted bare dotted names from it. **The two sets could never intersect**, so
every failing test was reported as "new (not in baseline)" and every verdict was
FAIL - including for branches whose failures were entirely baseline names.

Measured on 2026-09-28, which is what this module pins: the TASK-364 verdict
named two "new" failures and BOTH are in the baseline file; the TASK-400 verdict
named seventeen and every one sampled was in the baseline too.

The reason this is worth a test rather than a fix and a shrug: the operator's
standing merge rule is **"a valid GLM PASS means merge"**. A verifier that can
never emit PASS does not make merging slower - it teaches everyone to discount
the verifier, and then a real finding gets waved through months later. A broken
check that always cries wolf is more dangerous than no check, because it spends
the credibility the check needs.

It is the same class of defect as the one this repository already names: two
numbers compared without being shaped the same way. The suite baseline is a LIST
for exactly that reason, and a diff is only evidence once both sides are
normalised.
"""
import unittest

from scripts.glm_verify_branch import normalise_test_name, _load_baseline


#: The two names the TASK-364 verdict called "new". Both are baseline entries -
#: lines 62 and 63 of docs/state/SUITE-BASELINE-2026-09-26.txt.
MISREPORTED_AS_NEW = (
    "test_add_lead_is_refused_for_finished "
    "(tests.test_campaign_cannot_send.TheNarrowedSeals."
    "test_add_lead_is_refused_for_finished)",
    "test_finished_is_not_proven_safe "
    "(tests.test_campaign_cannot_send.ThePredicateReadsProviderTruth."
    "test_finished_is_not_proven_safe)",
)


class TheTwoSidesAreShapedTheSame(unittest.TestCase):

    def test_unittest_output_reduces_to_the_baselines_spelling(self):
        """`test_x (tests.mod.Class.test_x)` becomes `mod.Class.test_x`."""
        self.assertEqual(
            "test_campaign_cannot_send.TheNarrowedSeals."
            "test_add_lead_is_refused_for_finished",
            normalise_test_name(MISREPORTED_AS_NEW[0]))

    def test_it_is_idempotent_so_either_side_may_be_normalised(self):
        """A name already in baseline shape survives unchanged.

        The comparison has to be symmetric: normalising the baseline as well
        must not corrupt it, or fixing one side breaks the other.
        """
        bare = "test_campaign_cannot_send.TheNarrowedSeals.test_a"
        self.assertEqual(bare, normalise_test_name(bare))
        self.assertEqual(bare, normalise_test_name(normalise_test_name(bare)))

    def test_the_leading_tests_package_is_dropped(self):
        """The baseline does not carry the `tests.` prefix, so neither may we."""
        self.assertEqual(
            "mod.Class.test_a",
            normalise_test_name("test_a (tests.mod.Class.test_a)"))

    def test_nothing_useful_becomes_none(self):
        self.assertIsNone(normalise_test_name(""))
        self.assertIsNone(normalise_test_name(None))


class TheRegressionItself(unittest.TestCase):
    """The two names GLM called new are found IN the baseline after normalising.

    This is the test that would have caught the defect, and it asserts on the
    real baseline file rather than a fixture - because the defect was a
    disagreement between the parser and that exact file, and a fixture of my own
    shaping could have agreed with the parser while the file did not.
    """

    def setUp(self):
        self.baseline = _load_baseline()
        if not self.baseline:
            self.skipTest("baseline file absent")

    def test_the_baseline_is_a_list_of_names_and_it_loaded(self):
        self.assertGreater(len(self.baseline), 100,
                           "the baseline should hold ~128 named failures")

    def test_both_misreported_names_are_baseline_members(self):
        for raw in MISREPORTED_AS_NEW:
            name = normalise_test_name(raw)
            self.assertIn(
                name, self.baseline,
                f"{name} was reported as a NEW failure by a GLM verdict, but it "
                f"is in the standing baseline. That verdict was void on this "
                f"ground and the branch it failed was merged after independent "
                f"verification")

    def test_a_genuinely_new_name_is_still_reported_as_new(self):
        """The control. Without it, a normaliser that mapped everything onto an
        existing baseline entry would pass every test above and silence every
        real regression - which is the opposite failure and the worse one."""
        invented = normalise_test_name(
            "test_nothing (tests.test_module_that_does_not_exist."
            "Class.test_nothing)")
        self.assertNotIn(invented, self.baseline)


if __name__ == "__main__":
    unittest.main()
