#!/usr/bin/env python3
"""A subtest failure's name must not keep the `)` that closes the path.

## WHY THIS EXISTS

`normalise_test_name` reduces `unittest -v` output to the baseline's spelling.
For a subtest failure the closing line is

    FAIL: test_x (tests.mod.Cls.test_x) (i=1)

- TWO parenthesised groups, and on Python 3.14 the second is `(i=1)`, not the
`[i=1]` the function's own comment claims. `normalise_test_name` cut at
`inner.rfind(")")`, the LAST paren, so what was left of the path was
`tests.mod.Cls.test_x) (i=1`; the subtest-description branch then took
`inner.split()[0]`, which is `tests.mod.Cls.test_x)` - **with the stray `)`**.

MEASURED, one subtest failure, `raw-fx_paren.log`, Python 3.14.3:

    shipped bytes   -> 'fx_paren.FxParen.test_one_subtest_fails)'
    find(), not rfind() -> 'fx_paren.FxParen.test_one_subtest_fails'

## WHY IT MATTERS, AND WHY A TEST RATHER THAN A SHRUG

The gate subtracts a baseline of bare dotted names from the branch's failing
names. A name carrying a trailing `)` is not a name the baseline can contain, so
every subtest failure reads as "new (not in baseline)" on every branch, forever -
the same always-cry-wolf shape as the spelling mismatch this module's sibling
`test_the_glm_verdict_compares_like_with_like.py` pins. A verifier that cannot
emit PASS spends the credibility the check needs.

## WHAT THIS TEST DELIBERATELY DOES NOT ASSERT

It does not pin the dotted path. A mutant that reduced EVERY name to the
pre-paren token would satisfy any assertion phrased as "has no trailing paren",
and it is caught instead by the corpus control, which requires non-subtest names
to keep their dotted paths. The assertion here is the invariant that both arms
cannot share: **a subtest failure is named exactly as the same test is named
without the subtest.**
"""
import unittest

from scripts.glm_verify_branch import normalise_test_name


#: Byte-exact, taken from the real Python 3.14.3 run, and the shape the fix is
#: measured against. The two differ ONLY by the subtest group.
SUBTEST_LINE_3_14 = "test_two_subtests_both_fail (fx_paren2.FxParen2.test_two_subtests_both_fail) (i=1)"
PLAIN_LINE_3_14 = "test_two_subtests_both_fail (fx_paren2.FxParen2.test_two_subtests_both_fail)"

#: The bracket form the function's own comment documents. Older Pythons render
#: the subtest description this way, and it must keep working.
SUBTEST_LINE_BRACKET = "test_x (mod.Cls.test_x) [i=1]"


class TheSubtestSuffixIsPunctuation(unittest.TestCase):

    def test_a_subtest_failure_is_named_as_its_unsubtested_sibling(self):
        """The invariant both arms cannot share.

        Before the fix the left side ends `test_two_subtests_both_fail)` and the
        right side does not, so this is red on the pre-fix bytes.
        """
        self.assertEqual(
            normalise_test_name(PLAIN_LINE_3_14),
            normalise_test_name(SUBTEST_LINE_3_14))

    def test_the_subtest_name_carries_no_trailing_paren(self):
        name = normalise_test_name(SUBTEST_LINE_3_14)
        self.assertFalse(
            name.endswith(")"),
            f"{name!r} keeps the paren that closes the dotted path - the "
            f"baseline cannot contain that spelling, so every subtest failure "
            f"would be reported as new on every branch")

    def test_the_method_name_is_still_carried(self):
        """A control with teeth against over-cutting: whatever else changes,
        the name still names this test."""
        self.assertTrue(normalise_test_name(SUBTEST_LINE_3_14)
                        .endswith("test_two_subtests_both_fail"))

    def test_the_bracket_form_older_pythons_emit_still_works(self):
        """Green on both arms: the fix must not break the shape the comment
        documents while fixing the shape the interpreter actually emits."""
        self.assertEqual("mod.Cls.test_x",
                         normalise_test_name(SUBTEST_LINE_BRACKET))


class ThePlainFormIsUntouched(unittest.TestCase):

    def test_a_plain_failure_still_reduces_to_its_dotted_path(self):
        self.assertEqual("fx_paren2.FxParen2.test_two_subtests_both_fail",
                         normalise_test_name(PLAIN_LINE_3_14))

    def test_a_bare_dotted_name_is_still_idempotent(self):
        bare = "test_campaign_cannot_send.TheNarrowedSeals.test_a"
        self.assertEqual(bare, normalise_test_name(bare))
        self.assertEqual(bare, normalise_test_name(normalise_test_name(bare)))

    def test_the_tests_prefix_is_still_dropped(self):
        self.assertEqual("mod.Cls.test_a",
                         normalise_test_name("test_a (tests.mod.Cls.test_a)"))


if __name__ == "__main__":
    unittest.main()
