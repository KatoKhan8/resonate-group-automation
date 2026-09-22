"""The agent never states a number it was not given.

OPERATOR, 2026-09-21: "Every number in an answer traces to the pack or a
readback; the model never invents one."

This project's register is a list of figures that were true once and quoted
later: 26 unresolved keys that were 18, twelve stranded branches that were
six, a DEGRADED reading that was an inference from a zero. A model that
rounds 878 to "about 900" is doing the same thing at conversational speed,
so the check is mechanical: every numeric token in the answer has to appear
in the material the model was handed, or the answer is DISCARDED and the
deterministic one is posted instead.

Discarded rather than patched, because a number that is not in the material
is not a wording problem.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackconversation as conversation                # noqa: E402
from src import slackknowledge as knowledge                      # noqa: E402
from src import slackscope                                       # noqa: E402
from tests.slackbase import IsolatedState                        # noqa: E402

MATERIAL = ("878 candidates against a 360 pacing cap. Campaign 489 has "
            "emails_sent 2 of 8 queue rows, read at 2026-09-21T13:34:48Z. "
            "159 mailboxes across 8 humans.")


class Tokens(unittest.TestCase):

    def test_a_date_is_not_read_as_three_numbers(self):
        self.assertEqual(knowledge.numeric_tokens("on 2026-09-21"), set())

    def test_a_timestamp_is_not_read_as_numbers(self):
        self.assertEqual(
            knowledge.numeric_tokens("at 2026-09-21T13:34:48Z"), set())

    def test_a_clock_time_is_not_read_as_numbers(self):
        self.assertEqual(knowledge.numeric_tokens("the 09:00 window"), set())

    def test_a_thousands_separator_is_one_token(self):
        self.assertEqual(knowledge.numeric_tokens("10,671 tests"), {"10671"})

    def test_a_percentage_keeps_its_sign(self):
        """"2" and "2%" are different claims and must not match."""
        self.assertEqual(knowledge.numeric_tokens("0.83% bounce"), {"0.83%"})
        self.assertEqual(knowledge.numeric_tokens("2 sent"), {"2"})


class TheGuardCatchesAnInventedNumber(unittest.TestCase):

    def test_a_number_in_the_material_is_supported(self):
        self.assertEqual(
            conversation.unsupported_numbers("878 candidates", MATERIAL), [])

    def test_a_number_that_is_not_in_the_material_is_caught(self):
        self.assertEqual(
            conversation.unsupported_numbers("about 900 candidates",
                                             MATERIAL), ["900"])

    def test_a_plausible_rounding_is_still_caught(self):
        self.assertIn("880",
                      conversation.unsupported_numbers("roughly 880 leads",
                                                       MATERIAL))

    def test_small_numbers_are_language_not_claims(self):
        """"two sends", "step 3" and "the first one" are words."""
        self.assertEqual(
            conversation.unsupported_numbers(
                "there are 3 steps and 2 of them are email", MATERIAL), [])

    def test_an_invented_rate_is_caught_however_small(self):
        """A bounce rate is a claim, not language. 2% is the hard stop."""
        self.assertEqual(
            conversation.unsupported_numbers("bounce rate is 2%", MATERIAL),
            ["2%"])
        self.assertEqual(
            conversation.unsupported_numbers("0.4 replies per account",
                                             MATERIAL), ["0.4"])

    def test_a_count_does_not_license_the_same_figure_as_a_rate(self):
        self.assertEqual(
            conversation.unsupported_numbers("2% bounced",
                                             "emails_sent 2 today"), ["2%"])

    def test_a_date_in_the_answer_never_trips_the_guard(self):
        self.assertEqual(
            conversation.unsupported_numbers(
                "sent on 2026-09-22 at 07:15", MATERIAL), [])


class ALyingModelIsDiscarded(IsolatedState, unittest.TestCase):
    """The property end to end: a model that invents is not posted."""

    class Liar:
        """Answers the planner honestly and then states a false figure."""

        model = "liar"

        def __init__(self):
            self.calls = 0

        def complete(self, prompt, temperature=0):
            self.calls += 1
            if "Answer with JSON" in prompt:
                return '{"tools": [{"name": "timeline"}], "clarify": null}'
            return "We have contacted 74211 people this week."

    class Honest(Liar):
        def complete(self, prompt, temperature=0):
            self.calls += 1
            if "Answer with JSON" in prompt:
                return '{"tools": [{"name": "timeline"}], "clarify": null}'
            return "The project started on 2026-09-09 and is still running."

    def setUp(self):
        self.isolate()
        self._prev = os.environ.get(slackscope.INTERNAL_CHANNELS_VAR)
        os.environ[slackscope.INTERNAL_CHANNELS_VAR] = "C_INTERNAL"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(slackscope.INTERNAL_CHANNELS_VAR, None)
        else:
            os.environ[slackscope.INTERNAL_CHANNELS_VAR] = self._prev
        self.restore()

    def test_the_invented_figure_is_never_posted(self):
        result = conversation.respond("how are we doing?",
                                      channel="C_INTERNAL", user="U",
                                      model=self.Liar())
        self.assertNotIn("74211", result["reply"])
        self.assertIn("guard", result)
        self.assertIn("74211", result["guard"])
        self.assertTrue(result["how"].startswith("deterministic"))

    def test_an_honest_answer_is_posted_as_written(self):
        result = conversation.respond("when did this start?",
                                      channel="C_INTERNAL", user="U",
                                      model=self.Honest())
        self.assertEqual(result["how"], "model")
        self.assertIn("2026-09-09", result["reply"])


class OneRetryForNumbersAndNoneForScope(IsolatedState, unittest.TestCase):
    """A number is a wording fault. A scope violation is not.

    The first live guard trip in an internal channel reported "unsupported
    number(s): 101, 46, 52, 61, 72" and posted a raw readback dump instead
    of prose. Two things were wrong: the discarded answer was not recorded,
    so nobody could find out where those figures came from, and a model
    that knows the answer and added arithmetic nobody asked for is one
    sentence away from a good reply.

    Asking a model that has just named ANOTHER CLIENT to try again is a
    different thing entirely - it is asking it to leak more carefully - so
    that trip is never retried.
    """

    class InventsThenBehaves:
        model = "invents-then-behaves"

        def __init__(self):
            self.answers = 0

        def complete(self, prompt, temperature=0):
            if "Answer with JSON" in prompt:
                return '{"tools": [{"name": "timeline"}], "clarify": null}'
            self.answers += 1
            if self.answers == 1:
                return "We contacted 74211 people, starting 2026-09-09."
            return "We started on 2026-09-09."

    class LeaksTwice:
        model = "leaks"

        def __init__(self):
            self.answers = 0

        def complete(self, prompt, temperature=0):
            if "Answer with JSON" in prompt:
                return '{"tools": [{"name": "timeline"}], "clarify": null}'
            self.answers += 1
            return "Qwen is working on it."

    def setUp(self):
        self.isolate()
        self._prev = os.environ.get(slackscope.INTERNAL_CHANNELS_VAR)
        os.environ[slackscope.INTERNAL_CHANNELS_VAR] = "C_INTERNAL"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(slackscope.INTERNAL_CHANNELS_VAR, None)
        else:
            os.environ[slackscope.INTERNAL_CHANNELS_VAR] = self._prev
        self.restore()

    def test_an_invented_number_is_retried_once_and_the_retry_is_posted(
            self):
        model = self.InventsThenBehaves()
        result = conversation.respond("when did we start?",
                                      channel="C_INTERNAL", user="U",
                                      model=model)
        self.assertEqual(model.answers, 2, "it should retry exactly once")
        self.assertEqual(result["how"], "model (retried)")
        self.assertNotIn("74211", result["reply"])
        self.assertIn("2026-09-09", result["reply"])

    def test_the_rejected_answer_is_recorded_so_a_trip_can_be_diagnosed(
            self):
        result = conversation.respond("when did we start?",
                                      channel="C_INTERNAL", user="U",
                                      model=self.InventsThenBehaves())
        self.assertIn("74211", result["rejected"])
        self.assertIn("74211", result["guard"])

    def test_a_scope_violation_is_never_retried(self):
        scope = slackscope.Scope(slackscope.CLIENT, workspace="alpha",
                                 source="test", slugs=("alpha",))
        model = self.LeaksTwice()
        checked, why = conversation.guard("Qwen is working on it.",
                                          "material", scope)
        self.assertIsNone(checked)
        self.assertFalse(why.startswith("unsupported number"),
                         "a scope trip must not take the retry branch")

    def test_a_retry_that_still_invents_falls_back(self):
        class NeverLearns(self.InventsThenBehaves):
            def complete(self, prompt, temperature=0):
                if "Answer with JSON" in prompt:
                    return '{"tools": [{"name": "timeline"}], ' \
                           '"clarify": null}'
                self.answers += 1
                return "We contacted 74211 people."

        model = NeverLearns()
        result = conversation.respond("when did we start?",
                                      channel="C_INTERNAL", user="U",
                                      model=model)
        self.assertEqual(model.answers, 2)
        self.assertIn("guard twice", result["how"])
        self.assertNotIn("74211", result["reply"])
        self.assertIn("74211", result["rejected_retry"])


class EveryAnswerSaysWhenItWasRead(unittest.TestCase):

    def test_the_stamp_is_added(self):
        self.assertIn("as of", conversation.stamp("two sends today"))

    def test_a_stamp_is_not_added_twice(self):
        once = conversation.stamp("two sends today")
        self.assertEqual(once, conversation.stamp(once))


if __name__ == "__main__":
    unittest.main()
