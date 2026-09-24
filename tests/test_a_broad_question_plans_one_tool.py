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


class TestTheShapeREALTRAFFICARRIVESIN(Environment):
    """THE TEST THAT WAS MISSING, AND IT MADE THE FEATURE INERT.

    Every phrasing in the class above is typed the way a person writes in a
    document. Nobody addresses a bot that way. Real questions arrive as

        <@U0C3CBAP6BB> what is running

    and `NAMES_SOMETHING` matches a bare `@`, so the guard written to reject
    "what's new with 491" rejected the entire corpus. **Replaying the 33
    real questions on 2026-09-24 showed the broad route taken ZERO times**,
    with all eighteen tests green.

    `requests.strip_mentions` already existed and three other modules
    already called it. The defect was the fixture.
    """

    #: Verbatim from `work/slack-agent.jsonl`, mention and all.
    REAL = (
        "<@U0C3CBAP6BB> what is running",
        "<@U0C3CBAP6BB> what are you working on ?",
        "<@U0C3CBAP6BB> what can we do now ?",
        "<@U0C3CBAP6BB> what's new?",
        "What are you working on now? <@U0C3CBAP6BB>",
        "what's next? <@U0C3CBAP6BB>",
        "<@U0C3CBAP6BB> what is running right now? *Sent using* <@U0ASV6PQ>",
    )

    def test_every_real_broad_question_takes_the_route(self):
        for text in self.REAL:
            with self.subTest(text=text):
                self.assertTrue(
                    conversation.broad_question(text, self.internal()),
                    "%r is how the question ARRIVES. A matcher that only "
                    "works on the tidied-up version is not in the path."
                    % text)

    #: Also verbatim, and also carrying a mention. The guard still has to
    #: hold once the mention stops defeating it.
    REAL_SPECIFIC = (
        "<@U0C3CBAP6BB> which three campaigns are awaiting my approval?",
        "<@U0C3CBAP6BB> how many leads have been processed",
        "<@U0C3CBAP6BB> where can I buy kebab?",
        "<@U0C3CBAP6BB> what is running right now, and which monitors are up?",
        "<@U0C3CBAP6BB> do we have any inboxes in prod",
        "<@U0C3CBAP6BB> what was sent today?",
    )

    def test_a_real_specific_question_still_fans_out(self):
        for text in self.REAL_SPECIFIC:
            with self.subTest(text=text):
                self.assertFalse(
                    conversation.broad_question(text, self.internal()),
                    "%r was routed to the whole-workspace summary" % text)

    def test_the_mention_alone_does_not_make_a_question_broad(self):
        """The control on the stripping: removing mentions must not turn
        a question INTO a broad one."""
        self.assertFalse(conversation.broad_question(
            "<@U0C3CBAP6BB>", self.internal()))
        self.assertFalse(conversation.broad_question(
            "<@U0C3CBAP6BB> <@U0ASV6PQ>", self.internal()))


if __name__ == "__main__":
    unittest.main()
