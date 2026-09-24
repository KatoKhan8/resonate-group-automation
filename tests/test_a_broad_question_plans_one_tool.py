""""What is going on" plans ONE tool, and a specific question still fans out.

MEASURED 2026-09-23. All six length failures in the replay were one question
shape - "what is running", "what are you working on", "what can we do now" -
answered in 9-11 sentences against a prompt asking for two to six. The cause
was never the prompt: five tools make a large material and the model
summarises what it is handed, so the length rule loses to the volume and the
fix belongs at the PLAN. Eleven of the twenty-one answered questions used the
full five-call budget and every one took over 82 seconds.

**The risk this trades for is the reason the matcher is narrow.** A false
positive answers a specific question with a whole-workspace summary, which is
worse than the fan-out it replaces - the fan-out at least contained the
answer somewhere. So the negative cases below are the load-bearing half.
"""
import unittest

from src import slackconversation as conversation
from src import slackscope


class Environment(unittest.TestCase):

    def internal(self):
        return slackscope.Scope(slackscope.INTERNAL, source="test")

    def unbound(self):
        return slackscope.Scope(slackscope.UNBOUND, source="test")


class TestTheBroadShapeIsCaught(Environment):

    BROAD = (
        "what's new",
        "What's new?",
        "what is running",
        "what are we working on",
        "what are you working on?",
        "what can we do now",
        "what's going on",
        "what's happening?",
        "how's it going",
        "how are things?",
        "status",
        "status update",
        "što ima",
        "šta ima?",
        "na čemu smo",
        "na cemu radimo?",
        "kako ide",
        "gdje smo?",
    )

    def test_every_one_of_them(self):
        for text in self.BROAD:
            with self.subTest(text=text):
                self.assertTrue(
                    conversation.broad_question(text, self.internal()),
                    "%r is the shape that cost six length failures" % text)


class TestASpecificQuestionIsNotBroad(Environment):
    """THE CONTROL. A matcher that caught everything would pass every test
    above and answer the whole corpus with one summary."""

    SPECIFIC = (
        "what's new with 491",
        "what is running on campaign 487?",
        "what's the status on 489",
        "how's it going with sending-domain-a.example.test",
        "what are we working on for @person",
        "what's new with the bounce rate on 491",
        "how many emails went out today",
        "which three campaigns are awaiting my approval?",
        "jesu puštene kampanje sada?",
        "na koliko leadova smo poslali ovaj tjedan?",
        "can you please stop sending messages to people who have replied????",
        "what went out this week?",
    )

    def test_none_of_them_is_routed_to_one_tool(self):
        for text in self.SPECIFIC:
            with self.subTest(text=text):
                self.assertFalse(
                    conversation.broad_question(text, self.internal()),
                    "%r names something or asks something specific, and "
                    "answering it with the workspace summary is the wrong "
                    "answer arriving faster" % text)

    def test_a_long_question_is_never_broad_however_it_opens(self):
        text = ("what's new - also I wanted to ask whether the sequence for "
                "the second cohort has been approved yet or not")
        self.assertFalse(conversation.broad_question(text, self.internal()))

    def test_empty_and_none_are_not_broad(self):
        for text in ("", "   ", None):
            self.assertFalse(conversation.broad_question(text, self.internal()))


class TestThePlanIsActuallyOneCall(Environment):

    def test_a_broad_question_plans_working_on_and_nothing_else(self):
        calls, clarify, how = conversation.plan(
            "what are we working on", self.internal(), [], model=None)
        self.assertIsNone(clarify)
        self.assertEqual([c["name"] for c in calls], ["working_on"])
        self.assertEqual(how, "broad question -> working_on")

    def test_it_does_not_spend_a_model_call_to_be_told_that(self):
        """Planning is itself a round trip, and this shape has one plan."""
        class Loud:
            model = "loud"
            calls = 0

            def complete(self, prompt, temperature=0):
                Loud.calls += 1
                return '{"tools": [{"name": "monitors"}], "clarify": null}'

        conversation.plan("what's new", self.internal(), [], model=Loud())
        self.assertEqual(Loud.calls, 0,
                         "the planner asked the model which tool to use for "
                         "a question with exactly one right plan")

    def test_a_specific_question_still_reaches_the_model_planner(self):
        """THE CONTROL for the short-circuit: it must not swallow the rest."""
        class Planner:
            model = "planner"
            calls = 0

            def complete(self, prompt, temperature=0):
                Planner.calls += 1
                return '{"tools": [{"name": "monitors"}], "clarify": null}'

        calls, _clarify, how = conversation.plan(
            "how many emails went out today", self.internal(), [],
            model=Planner())
        self.assertEqual(Planner.calls, 1)
        self.assertEqual(how, "model")
        self.assertEqual([c["name"] for c in calls], ["monitors"])

    def test_scope_still_decides_and_is_not_assumed(self):
        """An unbound channel has no `working_on`, so the short-circuit must
        not route to a tool that channel may not have."""
        scope = self.unbound()
        catalogue = conversation.tools.catalogue(scope)
        if "working_on" in catalogue:
            self.skipTest("working_on is available unbound; premise gone")
        calls, _clarify, how = conversation.plan(
            "what's new", scope, [], model=None)
        self.assertNotEqual(how, "broad question -> working_on")
        self.assertNotIn("working_on", [c["name"] for c in calls])


if __name__ == "__main__":
    unittest.main()
