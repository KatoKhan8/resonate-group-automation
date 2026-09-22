"""Answering in the asker's language, and only when asked to.

OPERATOR, 2026-09-22, both from one real thread. A Productive person wrote
in Croatian to two Resonate colleagues by name; the agent was not mentioned
and must not have answered. When a Resonate person relays it, the agent
answers the ORIGINAL question, in ITS language, opening with a line saying
the list came from the system so the people it was addressed to are not
misrepresented as having written it.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import llm, slackconversation as conversation           # noqa: E402
from src import slacklanguage as language, slackscope            # noqa: E402
from tests.slackbase import IsolatedState                        # noqa: E402

#: The real message, verbatim, from #productive-resonate-outbound.
THE_QUESTION = (
    "bok <@U0AFFQ7CA8Y|Jelena Ilijasev> i <@U09UV3LDW0Y|Tina>, kako ste? "
    "Trebam od vas popis domena s kojih šaljete mailove u email "
    "kampanjama, možete tu pasteati popis, u thread")

INTERNAL = "C0INTERNALZ"
OPERATOR_USER = "U0OPERATORZ"
CLIENT_USER = "U0CLIENTZZZ"


class TheLanguageOfTheQuestion(unittest.TestCase):

    def test_the_real_croatian_question_is_croatian(self):
        self.assertEqual(language.detect(THE_QUESTION), language.CROATIAN)

    def test_the_english_form_of_the_same_question_is_english(self):
        self.assertEqual(
            language.detect("which domains do you send our email campaigns "
                            "from? can you paste the list in this thread"),
            language.ENGLISH)

    def test_croatian_without_diacritics_is_still_croatian(self):
        """Plenty of real Croatian is typed without them, which is why the
        function words carry half the weight."""
        self.assertEqual(
            language.detect("trebam popis domena s kojih saljete mailove"),
            language.CROATIAN)

    def test_a_mention_is_not_a_word_in_anybody_s_language(self):
        self.assertIsNone(language.detect("<@U0C3CBAP6BB>"))

    def test_a_message_it_cannot_place_abstains(self):
        """None is a real answer: it means mirror it, rather than guess."""
        self.assertIsNone(language.detect("ok"))
        self.assertIsNone(language.detect("2026-09-22"))

    def test_the_instruction_names_the_language(self):
        self.assertIn("Croatian", language.instruction(THE_QUESTION))
        self.assertIn("English", language.instruction("how many senders?"))

    def test_the_instruction_says_figures_are_not_translated(self):
        text = language.instruction(THE_QUESTION)
        self.assertIn("domains", text)
        self.assertIn("not", text.lower())


class TheAgentIsSilentUnlessItIsAsked(IsolatedState, unittest.TestCase):
    """A bot that answers a question addressed to two named colleagues has
    answered FOR them."""

    def setUp(self):
        self.isolate()
        self._prev = {k: os.environ.get(k) for k in
                      (slackscope.INTERNAL_CHANNELS_VAR,
                       slackscope.INTERNAL_USERS_VAR)}
        os.environ[slackscope.INTERNAL_CHANNELS_VAR] = INTERNAL
        os.environ[slackscope.INTERNAL_USERS_VAR] = OPERATOR_USER

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.restore()

    def test_a_client_message_naming_colleagues_is_not_a_relay(self):
        self.assertFalse(conversation.is_relay_request(
            THE_QUESTION, CLIENT_USER, None))

    def test_a_resonate_person_saying_answer_this_is_a_relay(self):
        self.assertTrue(conversation.is_relay_request(
            "<@U0C3CBAP6BB> answer this", OPERATOR_USER, None))

    def test_the_croatian_trigger_works_too(self):
        self.assertTrue(conversation.is_relay_request(
            "<@U0C3CBAP6BB> odgovori na ovo", OPERATOR_USER, None))

    def test_a_client_saying_answer_this_is_NOT_a_relay(self):
        """It is a client asking a question, and it is answered as one. It
        is not authority to answer on Resonate's behalf in a thread
        addressed to named colleagues."""
        self.assertFalse(conversation.is_relay_request(
            "answer this please", CLIENT_USER, None))

    def test_an_unknown_user_cannot_relay(self):
        self.assertFalse(conversation.is_relay_request(
            "answer this", "U0STRANGERR", None))

    def test_no_trigger_is_no_relay(self):
        self.assertFalse(conversation.is_relay_request(
            "thanks, that's great", OPERATOR_USER, None))


class ARelayAnswersTheParentAndSaysWhereItCameFrom(IsolatedState,
                                                   unittest.TestCase):

    class Stub:
        model = "stub"

        def complete(self, prompt, temperature=0):
            if "Answer with JSON" in prompt:
                return '{"tools": [{"name": "timeline"}], "clarify": null}'
            # Echo the question back so the test can see WHICH question
            # reached the answering prompt.
            return "The project started on 2026-09-09."

    def setUp(self):
        self.isolate()
        self._prev = os.environ.get(slackscope.INTERNAL_CHANNELS_VAR)
        os.environ[slackscope.INTERNAL_CHANNELS_VAR] = INTERNAL

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(slackscope.INTERNAL_CHANNELS_VAR, None)
        else:
            os.environ[slackscope.INTERNAL_CHANNELS_VAR] = self._prev
        self.restore()

    def relay(self, model=None):
        return conversation.respond(
            "<@U0C3CBAP6BB> answer this", channel=INTERNAL,
            user=OPERATOR_USER, thread_ts="T-REAL",
            model=model or llm.NoModel(), relay_of=THE_QUESTION)

    def test_the_relay_is_marked_as_one(self):
        self.assertTrue(self.relay()["relayed"])

    def test_the_language_comes_from_the_PARENT_not_the_trigger(self):
        """"answer this" is English. The question is Croatian."""
        self.assertEqual(self.relay()["language"], language.CROATIAN)

    def test_the_reply_opens_with_the_system_attribution(self):
        reply = self.relay()["reply"]
        self.assertTrue(reply.startswith("Ovo je automatski izvje"))
        self.assertIn("nije odgovor kolega", reply)

    def test_the_attribution_names_nobody(self):
        """An earlier draft named the two colleagues from the thread it was
        written against, which would have put their names on every relayed
        answer in every channel."""
        for code in ("hr", "en"):
            line = conversation.relay_preface(code)
            self.assertNotIn("Jelena", line)
            self.assertNotIn("Tina", line)

    def test_an_ordinary_turn_carries_no_attribution(self):
        result = conversation.respond(
            "when did this start?", channel=INTERNAL, user=OPERATOR_USER,
            model=llm.NoModel())
        self.assertFalse(result["relayed"])
        self.assertNotIn("nije odgovor kolega", result["reply"])
        self.assertNotIn("system readback", result["reply"])

    def test_the_trigger_itself_is_never_the_question(self):
        """Taking "answer this" literally would answer "answer this"."""
        result = self.relay(model=self.Stub())
        self.assertNotIn("answer this", result["reply"].lower())


class TheListingIsAppendedNotRetyped(unittest.TestCase):

    def test_a_short_answer_gets_no_appended_block(self):
        self.assertEqual(conversation._with_listing("hello", None), "hello")

    def test_a_listing_is_appended_verbatim(self):
        out = conversation._with_listing("intro", "a.test\nb.test")
        self.assertTrue(out.endswith("a.test\nb.test"))
        self.assertTrue(out.startswith("intro"))

    def test_the_model_is_told_the_list_is_coming(self):
        """The defect this exists for: the model wrote "I won't paste you
        half a list, I'll ask the team for a full one" and the full list
        was appended immediately underneath."""
        notice = conversation.LISTING_NOTICE.lower()
        self.assertIn("appended below", notice)
        self.assertIn("do not retype", notice)
        self.assertIn("already grouped by sender", notice)


if __name__ == "__main__":
    unittest.main()
