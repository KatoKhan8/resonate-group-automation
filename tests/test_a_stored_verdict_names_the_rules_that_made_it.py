"""rules-4, and a digest that moves when the rules do.

THE FAULT THIS CLOSES REACHED A CLIENT. The agent reported three positive
replies where our own classifier says zero. A guard comparing
`classifier == replies.VERSION` looks correct and is a rubber stamp: the
release name does not move when the rules do.

`rules-3` survived two rule changes on 2026-09-23 unchanged - `0b78fd68`
rewrote a pattern and moved two phrases out of NEGATIVE, `83a30652` added
QUESTION and SEND_INFO across 210 lines - so a verdict stored before them
and one stored after carry the same string and compare equal.

`src/replyverdict.py` was written to refuse until this existed, and to need
no edit on the day it did. These tests check that it now answers, and that
the digest is derived rather than remembered: the failure being fixed is
exactly that somebody added two whole categories and nothing downstream
could tell.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import replies                                        # noqa: E402
from src import replyverdict                                   # noqa: E402


class TheRulesCanNowIdentifyThemselves(unittest.TestCase):

    def test_the_version_moved_to_rules_4(self):
        self.assertEqual(replies.VERSION, "rules-4")

    def test_the_hash_carries_the_release_and_a_digest(self):
        self.assertTrue(replies.RULE_HASH.startswith("rules-4+"))
        digest = replies.RULE_HASH.split("+", 1)[1]
        self.assertEqual(len(digest), 12)
        self.assertNotEqual(digest, "")

    def test_replyverdict_asks_and_is_answered(self):
        """It looks the attribute up by name; it needed no edit."""
        self.assertEqual(replyverdict.current_rule_identity(),
                         replies.RULE_HASH)
        self.assertTrue(replyverdict.rules_are_identifiable())

    def test_the_identity_is_not_the_bare_release_name(self):
        """Returning VERSION would make every stale row compare equal."""
        self.assertNotEqual(replyverdict.current_rule_identity(),
                            replies.VERSION)


class ThDigestMovesWhenARuleMoves(unittest.TestCase):
    """The whole point. A digest that had to be remembered would fail the
    same way the version string did."""

    def _digest_with(self, name, value):
        original = getattr(replies, name)
        setattr(replies, name, value)
        self.addCleanup(setattr, replies, name, original)
        return replies.rule_digest()

    def test_adding_a_pattern_changes_it(self):
        before = replies.rule_digest()
        after = self._digest_with(
            "POSITIVE_PATTERNS",
            tuple(replies.POSITIVE_PATTERNS) + (r"\bsounds like a plan\b",))
        self.assertNotEqual(before, after)

    def test_editing_a_pattern_changes_it(self):
        before = replies.rule_digest()
        edited = (r"\bcompletely different\b",) + tuple(
            replies.NEGATIVE_PATTERNS[1:])
        self.assertNotEqual(before, self._digest_with(
            "NEGATIVE_PATTERNS", edited))

    def test_a_WHOLE_NEW_CATEGORY_changes_it(self):
        """83a30652 added QUESTION and SEND_INFO and `rules-3` did not move."""
        before = replies.rule_digest()
        replies.ESCALATION_PATTERNS = (r"\bspeak to your manager\b",)
        self.addCleanup(delattr, replies, "ESCALATION_PATTERNS")
        self.assertNotEqual(before, replies.rule_digest())

    def test_REORDERING_RULES_changes_it(self):
        """RULES is a priority list - NOT_NOW sits above POSITIVE on purpose,
        so a reorder changes what a reply is classified as."""
        before = replies.rule_digest()
        flipped = (replies.RULES[1], replies.RULES[0]) + replies.RULES[2:]
        self.assertNotEqual(before, self._digest_with("RULES", flipped))

    def test_changing_a_confidence_changes_it(self):
        before = replies.rule_digest()
        category, patterns, confidence = replies.RULES[0]
        bumped = ((category, patterns, confidence - 0.1),) + replies.RULES[1:]
        self.assertNotEqual(before, self._digest_with("RULES", bumped))

    def test_changing_the_threshold_changes_it(self):
        """A scalar can change a verdict without touching a pattern."""
        before = replies.rule_digest()
        self.assertNotEqual(before, self._digest_with(
            "CONFIDENCE_THRESHOLD", replies.CONFIDENCE_THRESHOLD + 0.05))

    def test_it_is_stable_across_calls(self):
        self.assertEqual(replies.rule_digest(), replies.rule_digest())


class AStoredVerdictIsCheckableNow(unittest.TestCase):

    def test_a_fresh_verdict_carries_the_hash_and_is_confirmed(self):
        verdict = replies.classify(
            "Yes, that sounds interesting - can we find 20 minutes next week?")
        self.assertEqual(verdict["classification"], replies.POSITIVE)
        self.assertEqual(verdict["classifier"], replies.RULE_HASH)
        self.assertTrue(replyverdict.is_confirmed(verdict))

    def test_the_stale_rules_3_row_is_still_refused(self):
        """The row in replyverdict's own docstring - an EA, called positive."""
        self.assertFalse(replyverdict.is_confirmed(
            {"classification": "positive", "classifier": "rules-3",
             "confidence": "0.75"}))

    def test_a_row_naming_no_classifier_is_refused(self):
        self.assertFalse(replyverdict.is_confirmed({"classification": "positive"}))

    def test_a_row_from_a_DIFFERENT_rules_4_is_refused(self):
        """Same release, different rules. This is the case the release name
        could never catch."""
        self.assertFalse(replyverdict.is_confirmed(
            # Hex letters rather than a run of zeros: a plus sign followed
            # by twelve digits reads as a phone number to the hygiene guard,
            # which is right to say so rather than be widened for a fixture.
            # The guard reads COMMENTS too, so this one does not spell the
            # rejected value out either.
            {"classifier": "rules-4+deadbeefcafe"}))

    def test_no_writer_stamps_the_bare_release_name(self):
        """Six sites wrote `VERSION`; a seventh added later must not."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "replies.py")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn(
            '"classifier": VERSION', source,
            "a verdict stamped with the release name is unconfirmable for "
            "ever - stamp RULE_HASH")


if __name__ == "__main__":
    unittest.main()
