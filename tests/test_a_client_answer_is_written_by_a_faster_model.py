"""Which model WRITES the reply, and the three turns that keep the stronger one.

OPERATOR, 2026-09-24, after the replay: client p50 25.4s and p95 37.8s
against a 15s/30s target, with the provider work already done. A 0-tool
turn costs 4.4s and a 1-tool turn 26.2s while the A/B says its reads are
5.4s, so the remainder is one model call and nothing about caching or
parallelism touches it.

**THE CATALOGUE MARKS NOTHING "REASONING-HEAVY".** The instruction was to
keep Opus for what it marks that way; the marking does not exist. So it is
defined in `slackconversation` from the corpus, and these tests are where
its size is pinned - a definition nobody can see the edges of is how a
cost decision turns into a quality one quietly.

Three things are tested, and the second matters most:

  1. A client answer is written by the faster model.
  2. **Internal is untouched, and so is every turn that cannot be made
     faster safely** - a relay, a wide turn, an explanation, and any
     configuration where the faster model is not available.
  3. Planning is unchanged. Only composition moved.
"""
import os
import unittest

from src import llm
from src import slackconversation as conversation
from src import slackscope


class Fake:
    """Stands in for a configured model, and remembers its name."""

    def __init__(self, name="stronger"):
        self.model = name
        self.prompts = []

    def complete(self, prompt, temperature=0):
        self.prompts.append(prompt)
        return "an answer"


class ModelChoice(unittest.TestCase):

    def setUp(self):
        self._prev = os.environ.get(conversation.CLIENT_MODEL_VAR)
        self.addCleanup(self._restore)

    def _restore(self):
        if self._prev is None:
            os.environ.pop(conversation.CLIENT_MODEL_VAR, None)
        else:
            os.environ[conversation.CLIENT_MODEL_VAR] = self._prev

    def client(self):
        return slackscope.Scope(slackscope.CLIENT, workspace="alpha",
                                source="test")

    def internal(self):
        return slackscope.Scope(slackscope.INTERNAL, source="test")


class TestTheClientAnswerMoves(ModelChoice):

    def test_a_plain_client_turn_is_written_by_the_faster_model(self):
        strong = Fake()
        chosen = conversation.answer_model(
            self.client(), strong, "what went out this week?", tool_count=1)
        self.assertIsNot(chosen, strong)
        self.assertEqual(chosen.model, conversation.CLIENT_ANSWER_MODEL)

    def test_the_name_is_overridable_without_touching_the_code(self):
        os.environ[conversation.CLIENT_MODEL_VAR] = "anthropic/claude-haiku-4-5"
        chosen = conversation.answer_model(
            self.client(), Fake(), "what went out this week?", tool_count=1)
        self.assertEqual(chosen.model, "anthropic/claude-haiku-4-5")

    def test_the_default_is_sonnet_and_it_is_named_once(self):
        self.assertEqual(conversation.CLIENT_ANSWER_MODEL,
                         "anthropic/claude-sonnet-5")


class TestWhatKeepsTheStrongerModel(ModelChoice):
    """THE CONTROL, AND THE LOAD-BEARING HALF.

    A router that sent everything to the cheaper model would pass every
    test in the class above and would be a quality decision disguised as a
    latency one.
    """

    def test_internal_is_untouched(self):
        strong = Fake()
        self.assertIs(
            conversation.answer_model(self.internal(), strong,
                                      "what went out this week?",
                                      tool_count=5),
            strong, "an internal answer changed model. Only client scope "
                    "was asked for.")

    def test_a_relay_keeps_it(self):
        """The 74.1s outlier in the replay is a relay, and it is also the
        only client turn that failed `numbers`."""
        strong = Fake()
        self.assertIs(
            conversation.answer_model(self.client(), strong,
                                      "Bruno pita jesmo li provukli struju",
                                      tool_count=5, relayed=True),
            strong)

    def test_a_wide_turn_keeps_it(self):
        strong = Fake()
        self.assertIs(
            conversation.answer_model(self.client(), strong,
                                      "what went out this week?",
                                      tool_count=conversation.WIDE_TURN_TOOLS),
            strong)

    def test_one_tool_below_wide_does_not_keep_it(self):
        """The boundary, so `WIDE_TURN_TOOLS` means something."""
        strong = Fake()
        self.assertIsNot(
            conversation.answer_model(
                self.client(), strong, "what went out this week?",
                tool_count=conversation.WIDE_TURN_TOOLS - 1),
            strong)

    def test_an_explanation_keeps_it(self):
        strong = Fake()
        for question in ("explain how the cross-channel stop works",
                         "why is campaign 491 paused",
                         "how does the follow-up work",
                         "objasni kako radi stop"):
            with self.subTest(question=question):
                self.assertIs(
                    conversation.answer_model(self.client(), strong,
                                              question, tool_count=1),
                    strong)

    def test_a_mention_does_not_hide_an_explanation(self):
        """Real questions arrive with `<@U...>` in front. The matcher has
        to see past it, which is the defect the broad-question route
        shipped with."""
        strong = Fake()
        self.assertIs(
            conversation.answer_model(
                self.client(), strong,
                "<@U0C3CBAP6BB> explain how the stop works", tool_count=1),
            strong)

    def test_no_model_configured_stays_no_model(self):
        none = llm.NoModel()
        self.assertIs(
            conversation.answer_model(self.client(), none, "anything"),
            none, "a NoModel turn was handed a live model, which would "
                  "make a deterministic answer a billed one.")

    def test_an_unconfigured_faster_model_falls_back(self):
        """No key, no route: the turn must still be answered, by the model
        that was already working."""
        os.environ[conversation.CLIENT_MODEL_VAR] = "a/model-that-is-not-set-up"
        strong = Fake()
        chosen = conversation.answer_model(self.client(), strong,
                                           "what went out?", tool_count=1)
        if chosen is not strong:
            # The route IS configured in this environment, so the fallback
            # cannot be exercised here - say so rather than pass silently.
            self.assertTrue(chosen.configured())
            self.skipTest("the LLM route is configured, so an unknown model "
                          "name still reports configured; the fallback is "
                          "exercised where it is not")


class TestPlanningIsUnchanged(ModelChoice):

    def test_the_planner_still_uses_the_model_it_was_given(self):
        """Only composition moved. A planner on a different model would be
        a second change wearing this one's justification."""
        class Planner:
            model = "planner"
            seen = []

            def complete(self, prompt, temperature=0):
                Planner.seen.append(prompt)
                return '{"tools": [], "clarify": null}'

        planner = Planner()
        conversation.plan("how many emails went out today",
                          self.internal(), [], planner)
        self.assertEqual(len(Planner.seen), 1)


class TestTheLengthRuleIsShorterForAClient(unittest.TestCase):

    def test_a_client_gets_a_tighter_budget_than_internal(self):
        client = conversation.LENGTH_RULE[slackscope.CLIENT]
        internal = conversation.LENGTH_RULE[slackscope.INTERNAL]
        self.assertNotEqual(client, internal)
        self.assertIn("FOUR", client)
        self.assertIn("six", internal)

    def test_every_scope_has_one(self):
        """A missing scope would format the prompt with a KeyError or, if
        it were a `.get` with no default, with nothing at all - and an
        answer prompt silently missing its length rule is how the six
        length failures would come back unnoticed."""
        for kind in (slackscope.CLIENT, slackscope.INTERNAL,
                     slackscope.UNBOUND):
            self.assertTrue(conversation.LENGTH_RULE[kind].strip())


if __name__ == "__main__":
    unittest.main()
