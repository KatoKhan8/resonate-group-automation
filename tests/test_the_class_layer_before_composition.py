"""The four class-layer repairs of 2026-09-23, each with its live case.

The reply engine was built draft-only and immediately found that the classes
it was told to act on were not the classes the classifier could produce. These
tests pin the repairs, and every one of them carries the real reply that
motivated it rather than an invented example.

    1  a non-English out-of-office is out_of_office, from its SUBJECT
    2  referral needs a human writer and a human target
    3  question and send_info exist, and outrank general warmth
    4  an objection is not a decline, and a decline still wins when present
"""
import unittest

from src import replies, replyengine


# ------------------------------------------------- 1. the subject detector

class AnAutoresponderAnnouncesItselfInTheSubject(unittest.TestCase):
    """Nine of nine unclassified replies on 2026-09-22 were autoresponders."""

    LIVE = (
        ("de", "Automatische Antwort: [EXTERN] where the margin gets lost",
         "Hallo, vielen Dank fuer Ihre Nachricht. Ich bin derzeit nicht in "
         "der Agentur."),
        ("de", "Abwesenheitsnotiz bis 25. September",
         "Guten Tag, ich bin derzeit nicht im Buero."),
        ("hu", "Szabadsag Re: Dot Creative + 4 tools?",
         "Kedves Levelira! Ezuton szeretnelek tajekoztatni."),
        ("cs", "Out of office 16. - 27. 9. 2025 Re: the number",
         "Dobry den, z duvodu dovolene poprosim urgentni veci resit."),
        ("da", "Autosvar: din henvendelse",
         "Hej, jeg er til European Agency Awards."),
        ("hr", "Automatski odgovor: vase pitanje",
         "Postovani, na godisnjem sam odmoru."),
        ("en", "Automatic reply: profitability visible on Monday",
         "Thanks for reaching out! As I work through my inbox."),
    )

    def test_every_language_we_have_seen(self):
        for lang, subject, body in self.LIVE:
            with self.subTest(lang=lang):
                found = replies.classify(body, subject=subject)
                self.assertEqual(found["classification"], replies.OUT_OF_OFFICE)
                self.assertTrue(found.get("subject_detected"))

    def test_the_engine_never_answers_them(self):
        for lang, subject, body in self.LIVE:
            with self.subTest(lang=lang):
                verdict = replies.classify(body, subject=subject)
                decision = replyengine.decide({"text": body}, verdict)
                self.assertEqual(decision.action, replyengine.NEVER)

    def test_a_subject_never_softens_a_stop(self):
        """A person writing "remove me" inside an autoresponder means it."""
        found = replies.classify(
            "Remove me from your list, do not contact me again.",
            subject="Out of Office Re: pricing")
        self.assertEqual(found["classification"], replies.UNSUBSCRIBE)

    def test_an_ordinary_subject_changes_nothing(self):
        found = replies.classify("Sounds great, happy to chat next week.",
                                 subject="Re: your note")
        self.assertEqual(found["classification"], replies.POSITIVE)


# ------------------------------------------------------- 2. referral gates

class AReferralNeedsAHumanWriterAndAHumanTarget(unittest.TestCase):
    """Draft #7 is the negative case, exactly as the operator specified."""

    DRAFT_7 = ("Sehr geehrte Damen und Herren, vielen Dank fuer Ihre "
               "Nachricht. In dringenden Faellen wenden Sie sich bitte an "
               "buero@erlebnismarketing.com.")

    def as_referral(self):
        return {"classification": "referral", "confidence": 0.85}

    def test_draft_seven_is_refused_as_machine_written(self):
        decision = replyengine.decide(
            {"text": self.DRAFT_7, "automated": True}, self.as_referral(),
            tz_offset_hours=2)
        self.assertEqual(decision.action, replyengine.REVIEW)
        self.assertIn("human reply", decision["why"])

    def test_draft_seven_is_also_refused_on_its_target(self):
        """Belt and braces: even called human, buero@ is a generic mailbox."""
        decision = replyengine.decide(
            {"text": self.DRAFT_7, "automated": False}, self.as_referral(),
            tz_offset_hours=2)
        self.assertEqual(decision.action, replyengine.REVIEW)
        self.assertIn("generic mailbox", decision["why"])
        self.assertIn("buero@erlebnismarketing.com",
                      decision.get("account_context") or [])

    def test_a_generic_target_is_account_context_not_an_enrolment(self):
        decision = replyengine.decide(
            {"text": "please send it to info@acme.io", "automated": False},
            self.as_referral(), tz_offset_hours=2)
        self.assertEqual(decision.get("account_context"), ["info@acme.io"])
        self.assertNotEqual(decision.action, replyengine.REPLY)

    def test_a_named_person_passes_both_gates(self):
        """It stops at the register, which is the composition refusal."""
        decision = replyengine.decide(
            {"text": "speak to marko.juric@acme.io, he owns this",
             "automated": False}, self.as_referral(), tz_offset_hours=2)
        checks = dict((name, ok) for name, ok, _why in decision["checks"])
        self.assertTrue(checks.get("referral_human"))
        self.assertTrue(checks.get("referral_target"))

    def test_the_generic_list_covers_the_shapes_we_see(self):
        for address in ("info@a.io", "office@a.io", "buero@a.io",
                        "kontakt@a.io", "hello@a.io", "sales@a.io",
                        "sales-eu@a.io", "office_2@a.hr", "noreply@a.io"):
            with self.subTest(address=address):
                self.assertTrue(replies.is_generic_mailbox(address))

    def test_a_person_is_not_a_generic_mailbox(self):
        for address in ("marko.juric@acme.io", "m.horvat@studio.de",
                        "megan@studionorth.com"):
            with self.subTest(address=address):
                self.assertFalse(replies.is_generic_mailbox(address))


# ------------------------------------------- 3. question and send_info exist

class TheTwoMissingClassesExist(unittest.TestCase):

    def test_they_are_in_the_vocabulary(self):
        self.assertIn(replies.QUESTION, replies.CATEGORIES)
        self.assertIn(replies.SEND_INFO, replies.CATEGORIES)

    def test_the_engine_routes_them_to_reply(self):
        self.assertEqual(replyengine.route_for("question"), replyengine.REPLY)
        self.assertEqual(replyengine.route_for("send_info"), replyengine.REPLY)

    def test_a_question_is_a_question(self):
        for text in ("How does it work with our existing setup?",
                     "Does it integrate with Xero?",
                     "Can you handle multi-currency?"):
            with self.subTest(text=text):
                self.assertEqual(replies.classify(text)["classification"],
                                 replies.QUESTION)

    def test_an_info_request_is_send_info(self):
        for text in ("Send over a deck when you can.",
                     "Could you share some information?"):
            with self.subTest(text=text):
                self.assertEqual(replies.classify(text)["classification"],
                                 replies.SEND_INFO)

    def test_warmth_outranks_the_request_and_that_is_a_choice(self):
        """The trade-off, asserted so it is visible rather than discovered.

        SEND_INFO and QUESTION rank BELOW POSITIVE. Ranked above it they took
        six replies off the positive signal that genuinely carried one -
        "Interested - what does it cost?", "Send me the details please" - and
        the positive count is a number the client reads.

        The cost is this: a warm reply that ALSO asks something is routed
        positive, and the engine answers positive with a booking link. Where
        the question is about price, terms or dates the commitment gate
        catches it first (asserted below), so the dangerous half is covered.
        Moving two lines in `replies.RULES` reverses the choice.
        """
        for text in ("Tell me more about the resourcing side.",
                     "Can you send me more details?"):
            with self.subTest(text=text):
                self.assertEqual(replies.classify(text)["classification"],
                                 replies.POSITIVE)

    def test_the_commitment_gate_covers_the_dangerous_half(self):
        """A warm reply asking about price never reaches a booking link."""
        text = "Interested - what does it cost?"
        verdict = replies.classify(text)
        decision = replyengine.decide({"text": text}, verdict,
                                      tz_offset_hours=2)
        self.assertEqual(decision.action, replyengine.REVIEW)
        self.assertIn("price", decision["why"])
        self.assertEqual(decision["ticket"]["to"], "#resonate-os")

    def test_plain_warmth_is_still_positive(self):
        found = replies.classify("Sounds great, happy to chat next week.")
        self.assertEqual(found["classification"], replies.POSITIVE)


# --------------------------------------------- 4. objection is not a decline

class AnObjectionIsAConversation(unittest.TestCase):
    """The operator's three shapes, and the decline that overrides them."""

    OBJECTIONS = (
        "We already use Harvest for this.",
        "We have a tool for this already.",
        "Not a priority right now.",
        "It is too expensive for us.",
    )

    DECLINES = (
        ("We already use Harvest, no thanks.", replies.NEGATIVE),
        ("We already use Harvest - not interested.", replies.NEGATIVE),
        ("Not a priority, and not interested.", replies.NEGATIVE),
        ("Not a priority right now, remove me.", replies.UNSUBSCRIBE),
    )

    def test_an_objection_on_its_own_is_an_objection(self):
        for text in self.OBJECTIONS:
            with self.subTest(text=text):
                self.assertEqual(replies.classify(text)["classification"],
                                 replies.OBJECTION)

    def test_a_decline_present_wins(self):
        """The mechanism is RULES order and nothing else."""
        for text, want in self.DECLINES:
            with self.subTest(text=text):
                self.assertEqual(replies.classify(text)["classification"], want)

    def test_an_objection_is_answerable_and_a_decline_is_not(self):
        self.assertEqual(replyengine.route_for(replies.OBJECTION),
                         replyengine.REPLY)
        self.assertEqual(replyengine.route_for(replies.NEGATIVE),
                         replyengine.REVIEW)
        self.assertEqual(replyengine.route_for(replies.UNSUBSCRIBE),
                         replyengine.NEVER)


if __name__ == "__main__":
    unittest.main()
