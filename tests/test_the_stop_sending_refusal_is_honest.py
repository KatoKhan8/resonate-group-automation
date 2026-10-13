"""The refusal to `stop sending to people who have replied` no longer
promises a ticket nobody will create.

MEASURED BEFORE THE CHANGE, 2026-10-13 on `f19d46832`, driving the real
`respond`:

    requests.recognise(...)   -> (None, {})          no kind matches
    respond(..., internal)    -> how: refused        REFUSAL_INTERNAL
    tools called              -> none
    request journal           -> NOTHING WRITTEN

`REFUSAL_INTERNAL` closes with "say so plainly and I will raise it as a
change request for you to approve", and `REFUSAL_CLIENT` with "I'll pass it
to the Resonate team". For THIS ask both are false: no kind is recognised,
so nothing is raised, logged or passed. The reply was honest about
permission and wrong about what happens next - and that is the worse half,
because somebody reads "I'll pass it on" and stops chasing it.

## WHAT CHANGED, AND WHAT DELIBERATELY DID NOT

Changed: the WORDS, for an action ask that `recognise` cannot turn into a
request. `refusal_text` returns the unticketable variant and the turn
carries `unticketable: True`.

NOT changed: `how` is still `refused`; no seventh request kind was added,
because a kind implies an executable change request and nothing here could
execute this one; no tool was added; `CLIENT_CHANNEL_GAG` is untouched and
a client channel is still silenced for this ask; a per-object ask still
takes the ticket route.

Every test drives the REAL `respond` offline: `llm.NoModel`, the request
journal pointed at a throwaway directory, and `tools.run_all` replaced by a
spy that RAISES if it is ever reached - so "no tool was called" is enforced
rather than observed. The spy's own ability to fire is proved by
`test_the_tool_spy_can_actually_fire`.
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import llm                                              # noqa: E402
from src import slackagenttools as agenttools                    # noqa: E402
from src import slackconversation as conversation                # noqa: E402
from src import slackrequests as requests                        # noqa: E402
from src import store                                            # noqa: E402
from src import slackscope                                       # noqa: E402

from tests.test_a_request_to_stop_sending_has_no_safe_answer import (
    AS_CATALOGUED, THE_ASK, TestNoFalselySuccessfulAnswer,  # noqa: E402
    TestThePoliteQuestionsThatMustNotBeCaught)

INTERNAL = slackscope.Scope(slackscope.INTERNAL, source="test")
CLIENT = slackscope.Scope(slackscope.CLIENT, workspace="productive",
                          source="test")
UNBOUND = slackscope.Scope(slackscope.UNBOUND, source="test")

#: The detector lives in the sibling module so the two files cannot drift
#: into disagreeing about what a false claim looks like.
CLAIMS_ACTION = TestNoFalselySuccessfulAnswer.CLAIMS_ACTION
POLITE_READS = TestThePoliteQuestionsThatMustNotBeCaught.POLITE_READS


class Offline(unittest.TestCase):
    """Shared rig: no model, no provider, no network, no real journal.

    THE STORE IS ISOLATED FIRST, and it has to be: the ticket route in
    `test_a_targeted_ask_keeps_the_ticket_route` writes thread memory, and
    `store.refuse_production_write` correctly raised
    `ProductionStateUnderTest` against this worktree's own
    `work/slack-threads.jsonl` until it was. That guard firing is the
    reason no test here can touch production state, so it is pointed at a
    throwaway directory rather than worked around.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="slack-unticketable-")
        self.state = tempfile.mkdtemp(prefix="slack-state-")
        self._real_store_dir = getattr(store, "DIRECTORY", None)
        store.use_directory(self.state)
        self._env = {}
        for var, value in (("SLACK_REQUESTS_DIR", self.tmp),
                           ("SLACK_REQUESTS",
                            os.path.join(self.tmp,
                                         "slack-requests.jsonl"))):
            self._env[var] = os.environ.get(var)
            os.environ[var] = value
        self.calls = []
        self._real_run_all = agenttools.run_all
        self._real_resolve = slackscope.resolve

        def spy(scope, calls):
            self.calls.append([c.get("name") for c in calls])
            raise AssertionError("a tool was planned and called: %r"
                                 % (calls,))

        agenttools.run_all = spy

    def tearDown(self):
        agenttools.run_all = self._real_run_all
        slackscope.resolve = self._real_resolve
        if self._real_store_dir is not None:
            store.use_directory(self._real_store_dir)
        shutil.rmtree(self.state, ignore_errors=True)
        for var, value in self._env.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def answer(self, question, scope=None):
        slackscope.resolve = lambda *a, **k: (scope or INTERNAL)
        try:
            return conversation.respond(question, channel="C-TEST",
                                        user="U-TEST",
                                        model=llm.NoModel())
        finally:
            slackscope.resolve = self._real_resolve

    def journalled(self):
        return [name for _b, _d, names in os.walk(self.tmp)
                for name in names]


class TheAnswerSaysTheActionDidNotHappen(Offline):

    def test_the_premise_still_holds_no_kind_is_recognised(self):
        """If a kind is ever added for this, the new text stops applying
        and this whole file needs rereading."""
        for text in (THE_ASK, AS_CATALOGUED):
            self.assertIsNone(requests.recognise(text)[0])

    def test_nothing_changed_and_nothing_is_queued(self):
        out = self.answer(AS_CATALOGUED)
        self.assertEqual(out["how"], "refused")
        self.assertTrue(out["unticketable"])
        low = (out["reply"] or "").lower()
        self.assertIn("nothing has changed", low)
        self.assertIn("nothing is queued", low)

    def test_it_says_why__no_writing_tool_and_no_permission(self):
        """Both halves the increment was asked for, asserted apart."""
        low = (self.answer(AS_CATALOGUED)["reply"] or "").lower()
        self.assertIn("every tool i can call is a read", low,
                      "the reply must say no tool of its own can write")
        self.assertIn("no write permission", low,
                      "the reply must say it has no permission to write")

    def test_it_no_longer_promises_a_change_request(self):
        reply = (self.answer(AS_CATALOGUED)["reply"] or "")
        self.assertNotEqual(reply, conversation.REFUSAL_INTERNAL)
        self.assertIn("cannot raise as a change request", reply.lower())
        for promise in ("i will raise it", "i'll pass it"):
            self.assertNotIn(
                promise, reply.lower(),
                "the reply promises %r while nothing is journalled"
                % (promise,))

    def test_nothing_is_journalled_so_the_sentence_is_true(self):
        """"Nothing is queued" is only honest if nothing is."""
        self.answer(AS_CATALOGUED)
        self.assertEqual(
            self.journalled(), [],
            "something WAS recorded, so the reply is now false: %r"
            % (self.journalled(),))

    def test_it_names_no_tool_and_no_figure(self):
        """An action ask must not be answered with a reply COUNT.

        The old `REFUSAL_INTERNAL` offered a list of reads. For an ask that
        cannot be actioned, offering numbers answers a question nobody
        asked, so the new text names none.
        """
        low = (self.answer(AS_CATALOGUED)["reply"] or "").lower()
        for tool in sorted(agenttools.REGISTRY):
            self.assertNotIn(tool.replace("_", " "), low,
                             "the refusal advertises %r" % (tool,))
        self.assertNotIn("how many", low)


class NoToolIsCalled(Offline):

    def test_no_tool_is_called_for_the_ask(self):
        out = self.answer(AS_CATALOGUED)
        self.assertEqual(out["tools"], [])
        self.assertEqual(self.calls, [],
                         "run_all was reached: %r" % (self.calls,))

    def test_the_tool_spy_can_actually_fire(self):
        """POSITIVE CONTROL. A spy that was never wired would make the
        test above a statement about the rig, not the agent."""
        with self.assertRaises(AssertionError):
            self.answer("what is running")
        self.assertTrue(self.calls,
                        "the spy recorded nothing, so it is not wired")


class AFalseClaimWouldFailTheControl(Offline):

    def test_the_shipped_reply_is_not_a_claim(self):
        reply = self.answer(AS_CATALOGUED)["reply"] or ""
        self.assertIsNone(
            CLAIMS_ACTION.search(reply),
            "the shipped refusal reads as a claim that it acted: %r"
            % (reply,))

    def test_the_same_assertion_fails_on_a_lying_reply(self):
        """THE NEGATIVE CONTROL. Without it, the test above passes for a
        detector that matches nothing at all."""
        for liar in ("Done - we have stopped sending to anyone who "
                     "replied.",
                     "That is now stopped.",
                     "I will stop those sends today.",
                     "They are no longer sending to repliers.",
                     "Consider it done."):
            self.assertIsNotNone(
                CLAIMS_ACTION.search(liar),
                "the detector missed a false claim: %r" % (liar,))
            with self.assertRaises(AssertionError):
                self.assertIsNone(CLAIMS_ACTION.search(liar))

    def test_the_reply_never_says_stopped_or_paused_of_itself(self):
        low = (self.answer(AS_CATALOGUED)["reply"] or "").lower()
        for claim in ("have stopped", "has stopped", "is stopped",
                      "have paused", "is paused", "no longer sending"):
            self.assertNotIn(claim, low)


class PoliteInformativeQuestionsAreUntouched(Offline):

    def test_none_of_them_is_read_as_a_change_request(self):
        for question in POLITE_READS:
            self.assertFalse(
                conversation.wants_an_action(question, INTERNAL),
                "%r is now read as an action ask and would be refused"
                % (question,))
            self.assertIsNone(requests.recognise(question)[0],
                              "%r became a request kind" % (question,))

    def test_each_one_still_reaches_the_planner(self):
        """Proved by the spy firing: they plan reads, they are not
        refused."""
        for question in POLITE_READS:
            self.calls = []
            with self.assertRaises(AssertionError):
                self.answer(question)
            self.assertTrue(self.calls,
                            "%r planned no read at all" % (question,))

    def test_and_the_english_lead_question_too(self):
        self.calls = []
        with self.assertRaises(AssertionError):
            self.answer("how many leads did we email this week?")
        self.assertIn("lead_counts", self.calls[0])


class TheGagAndOutboundAreUnchanged(Offline):

    def test_a_client_channel_is_still_silenced_for_this_ask(self):
        out = self.answer(AS_CATALOGUED, scope=CLIENT)
        self.assertEqual(
            out["how"], "gagged",
            "the refusal change must not have moved the gag")
        self.assertIsNone(out["reply"])
        self.assertEqual(out["tools"], [])

    def test_the_gag_constant_is_untouched(self):
        self.assertTrue(
            conversation.CLIENT_CHANNEL_GAG,
            "the gag is no longer set; that is the operator's decision")
        self.assertIn("2026-09-23", conversation.CLIENT_CHANNEL_GAG)

    def test_an_unbound_channel_keeps_its_own_refusal(self):
        out = self.answer(AS_CATALOGUED, scope=UNBOUND)
        self.assertEqual(out["reply"], conversation.REFUSAL_UNBOUND)
        self.assertFalse(out["unticketable"])

    def test_a_targeted_ask_keeps_the_ticket_route(self):
        """The control that this change did not swallow real requests."""
        for question, kind in (
                ("please pause campaign 487", "pause_campaign"),
                ("please remove john@acme.example from the list",
                 "remove_lead")):
            out = self.answer(question)
            self.assertEqual(out["how"], "request_restated",
                             "%r lost the ticket route" % (question,))
            self.assertEqual(out["request_kind"], kind)
            self.assertIsNone(
                out.get("unticketable"),
                "a ticketable ask must not be flagged unticketable")

    def test_no_registry_tool_gained_a_write_path(self):
        """Outbound behaviour, asserted structurally rather than assumed.

        `test_slack_agent_cannot_act` owns this guarantee; this is the
        cheap restatement so a refusal-text change cannot be the thing
        that quietly broke it.
        """
        self.assertEqual(len(agenttools.REGISTRY), 29)
        self.assertNotIn("stop_sending", agenttools.REGISTRY)
        self.assertNotIn("pause_sending", agenttools.REGISTRY)

    def test_no_seventh_request_kind_was_added(self):
        self.assertEqual(len(requests.KINDS), 6)
        self.assertEqual(sorted(requests.KINDS),
                         ["add_lead", "change_copy", "change_window",
                          "pause_campaign", "remove_lead", "stop_account"])


if __name__ == "__main__":
    unittest.main()


class ADraftingRequestKeepsTheStandardRefusal(Offline):
    """THE REGRESSION THAT NARROWED THIS, kept as a test.

    The first version applied the unticketable text to every action ask
    `recognise` could not place.
    `test_internal_assistant_mode.test_the_refusal_is_the_client_one`
    caught it: "write a short summary of how the stop works" asks to
    change nothing, and answering it with "nothing has changed and nothing
    is queued" answers a question nobody asked.

    `stop` is a NOUN there, which is why `MUTATING_ASK` requires the verb
    to take a gerund or a scope word rather than just appearing.
    """

    DRAFTING = (
        "write a short summary of how the stop works",
        "write a summary of the stop policy",
        "draft a note about the opt-out stop",
    )

    def test_a_drafting_request_is_not_flagged_unticketable(self):
        for question in self.DRAFTING:
            text, unticketable = conversation.refusal_text(
                scope=CLIENT, question=question)
            self.assertFalse(
                unticketable,
                "%r is a drafting request, not an ask to stop sending"
                % (question,))
            self.assertEqual(text, conversation.REFUSAL_CLIENT)

    def test_the_noun_stop_does_not_trigger_the_pattern(self):
        for question in self.DRAFTING:
            self.assertIsNone(
                conversation.MUTATING_ASK.search(question),
                "%r matched MUTATING_ASK; `stop` is a noun there"
                % (question,))

    def test_the_pattern_still_catches_the_real_asks(self):
        """POSITIVE CONTROL. A pattern that matched nothing would also
        pass the two tests above."""
        for question in (THE_ASK, AS_CATALOGUED,
                         "please stop emailing everyone who replied",
                         "can you stop all sending to repliers"):
            self.assertIsNotNone(
                conversation.MUTATING_ASK.search(question),
                "%r no longer matches MUTATING_ASK" % (question,))

    def test_no_polite_read_matches_the_pattern(self):
        for question in POLITE_READS:
            self.assertIsNone(
                conversation.MUTATING_ASK.search(question),
                "%r matched MUTATING_ASK" % (question,))
