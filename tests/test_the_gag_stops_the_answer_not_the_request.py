"""Where `CLIENT_CHANNEL_GAG` sits, and why it is not the first line.

Moved 2026-09-24. It used to return before section 2a of `_respond`, so a
client asking us to CHANGE something produced a `kind: gagged` row in
`work/slack-agent.jsonl`, one line on the loop's stdout, and **nothing
else** - no ticket, no internal post, nobody told. The question catalogue's
highest-severity shape in the whole corpus is a client change request, and
that is what it got. It was also 31 tests red.

THE GAG'S THREE FAULTS WERE ALL IN THE MODEL-ANSWERED PATH: a provider flag
read as a classification, the model reaching for the fallback, and sixteen
serial provider round trips. The request intake calls no model and reads no
provider.

**AND THIS IS A LOOSENING, WHICH IS WHY BOTH HALVES ARE PINNED HERE.** The
agent posts to a client channel again, for change requests only. The tests
below say exactly how far that goes, so the next person can see the size of
the hole rather than infer it - and so that widening it further has to be
done on purpose.
"""
import os
import unittest
import unittest.mock as mock

from src import slackconversation as conversation
from src import slackscope
from tests.slackbase import IsolatedState

ALPHA = "C_ALPHA_GAGTEST"
INTERNAL = "C_INTERNAL_GAGTEST"

def _workspace(slug, name, policy):
    return {"kind": "workspace", "slug": slug, "name": name, "client": slug,
            "settings": {"policy": policy}}


#: THE SHAPE MATTERS AND GETTING IT WRONG IS SILENT. A row `resolve` does
#: not understand does not raise - the channel simply resolves UNBOUND, and
#: an unbound turn is never gagged, so every assertion here passed against
#: a scope the test was not about. Copied from `test_slack_agent_scope`,
#: which is the file that owns this fixture.
ROWS = [
    _workspace("alpha", "Alpha", {
        slackscope.AGENT_CHANNEL_KEY: ALPHA,
        slackscope.WORKSPACE_USERS_KEY: ["U_ALPHA"],
    }),
]


class GagTest(IsolatedState, unittest.TestCase):

    def setUp(self):
        self.isolate()
        self.addCleanup(self.restore)
        self._prev = os.environ.get(slackscope.INTERNAL_CHANNELS_VAR)
        os.environ[slackscope.INTERNAL_CHANNELS_VAR] = INTERNAL
        self.addCleanup(self._restore_channels)
        self.assertTrue(
            conversation.CLIENT_CHANNEL_GAG,
            "the gag is lifted. If that is the operator's decision these "
            "tests describe a state the system is no longer in - read them "
            "and delete them deliberately, do not retune them.")

    def _restore_channels(self):
        if self._prev is None:
            os.environ.pop(slackscope.INTERNAL_CHANNELS_VAR, None)
        else:
            os.environ[slackscope.INTERNAL_CHANNELS_VAR] = self._prev

    def ask(self, text, thread="T1"):
        return conversation.respond(text, channel=ALPHA, user="U_ALPHA",
                                    thread_ts=thread, rows=ROWS,
                                    model=self.LoudModel())

    class LoudModel:
        """Fails the test if the gagged path ever reaches a model."""
        model = "loud"
        used = False

        def complete(self, prompt, temperature=0):
            type(self).used = True
            return "the model should never have been asked"


class TheAnswerIsStillGagged(GagTest):
    """The half that did NOT change. Everything below the line."""

    def test_an_ordinary_client_question_gets_nothing(self):
        result = self.ask("what went out this week?")
        self.assertEqual(result["scope"], slackscope.CLIENT)
        self.assertIsNone(result["reply"])
        self.assertEqual(result["how"], "gagged")
        self.assertTrue(result.get("gag_reason"))

    def test_no_model_is_asked_for_a_gagged_turn(self):
        self.LoudModel.used = False
        self.ask("how are the campaigns doing?")
        self.assertFalse(
            self.LoudModel.used,
            "a gagged turn reached the model. The seven-minute turn that "
            "helped cause the gag is below that line.")

    def test_no_tool_is_run_for_a_gagged_turn(self):
        result = self.ask("how many replies have we had?")
        self.assertEqual(result["tools"], [])


class TheREQUESTIsNotGagged(GagTest):
    """The half that changed, and the reason the move was made."""

    def test_a_client_change_request_is_restated_rather_than_ignored(self):
        result = self.ask("can you pause the campaign for us please")
        self.assertNotEqual(
            result["how"], "gagged",
            "a client asked us to change something and the agent said "
            "nothing at all. That is the defect this file is about.")
        self.assertTrue(result["reply"])

    def test_it_still_costs_no_model_call(self):
        """The whole argument for letting it through. Template text only."""
        self.LoudModel.used = False
        self.ask("can you pause the campaign for us please")
        self.assertFalse(
            self.LoudModel.used,
            "the change-request path reached a model, so it is no longer "
            "the template-text path the gag was moved around.")

    def test_confirming_it_raises_a_ticket(self):
        """The intake is worth nothing if the second turn is still gagged.

        The campaign has to actually BELONG to this workspace or
        `check_ownership` answers `request_not_yours` - correctly - and the
        ticket path is never reached. That refusal is itself template text
        above the gag line, which is why it surfaced here rather than as
        silence.
        """
        with mock.patch.object(conversation.tools, "_campaign_rows",
                               lambda slug: [{"bison_campaign_id": "491"}]):
            return self._confirm()

    def _confirm(self):
        first = self.ask("please pause campaign 491", thread="T2")
        self.assertEqual(first["how"], "request_restated")
        second = self.ask("yes", thread="T2")
        self.assertEqual(second["how"], "request_raised")
        self.assertTrue(second.get("ticket"))
        self.assertTrue(
            second.get("post_to_internal"),
            "the ticket was raised and the operator was not told, which is "
            "the worst state this feature has.")


class TheOfferPathStaysGagged(GagTest):
    """The one client path deliberately left behind the gag.

    Registering a follow-up PROMISES the client a later message and reads
    the provider for its reply marker. Neither of the two things that make
    the request intake safe under the gag is true of it.
    """

    def test_accepting_the_first_send_offer_is_not_registered(self):
        with mock.patch.object(conversation, "_offer_on_the_table",
                               lambda c, t: {"campaign_id": "491"}), \
             mock.patch.object(conversation, "accepts_offer",
                               lambda q: True):
            result = self.ask("yes please", thread="T3")
        self.assertEqual(
            result["how"], "gagged",
            "a gagged client channel was promised a later message.")


class TheLineIsWhereTheCommentSaysItIs(GagTest):
    """A control: if the gag stopped gagging anything, every test in
    `TheAnswerIsStillGagged` would still pass on an empty answer."""

    def test_an_internal_channel_is_not_gagged_at_all(self):
        class Planner:
            model = "p"

            def complete(self, prompt, temperature=0):
                return '{"tools": [], "clarify": null}'

        result = conversation.respond("what went out this week?",
                                      channel=INTERNAL, user="U",
                                      model=Planner())
        self.assertEqual(result["scope"], slackscope.INTERNAL)
        self.assertNotEqual(result["how"], "gagged")


if __name__ == "__main__":
    unittest.main()
