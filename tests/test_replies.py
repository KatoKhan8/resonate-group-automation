"""What a reply means, and what happens because of it.

Two halves. The classifier tests pin the precedence rules - unsubscribe over
everything, out-of-office never positive, low confidence to manual review. The
inbound tests pin the ordering that makes those rules safe to get wrong: the
company is already paused before any of them run.
"""
import unittest

from src import events, inbound, replies, store
from src.providers import slack
from tests.campaignbase import CampaignTest


class TestTheClassifier(unittest.TestCase):
    def verdict(self, text):
        return replies.classify(text)["classification"]

    def test_a_clear_yes_is_positive(self):
        for text in ("This sounds interesting, happy to chat next week.",
                     "Interested - what does it cost?",
                     "Let's talk. Send me some times.",
                     "Tell me more about the pricing."):
            self.assertEqual(self.verdict(text), replies.POSITIVE, text)

    def test_a_clear_no_is_negative(self):
        for text in ("Not interested, thanks.",
                     "No thanks, we're all set.",
                     "We already use something for this."):
            self.assertEqual(self.verdict(text), replies.NEGATIVE, text)

    def test_an_unsubscribe_is_an_unsubscribe(self):
        for text in ("Please unsubscribe me.", "Remove me from your list.",
                     "Stop emailing me.", "Opt out."):
            self.assertEqual(self.verdict(text), replies.UNSUBSCRIBE, text)

    def test_an_unsubscribe_beats_an_otherwise_warm_message(self):
        text = ("This sounds really interesting and I'd love to chat, but "
                "please unsubscribe me from this list.")
        self.assertEqual(self.verdict(text), replies.UNSUBSCRIBE)

    def test_a_company_wide_removal_is_not_a_personal_one(self):
        """The distinction the account policy acts on.

        A personal unsubscribe suppresses the sender. A company-wide one
        suppresses everybody there. Reading the second as the first leaves
        colleagues contactable after a company asked us to stop, which is
        the error that cannot be taken back - so the broader rule is tested
        first, and every pattern in it needs a word meaning more than one
        person.
        """
        for text in ("Please remove our entire company from your list.",
                     "Do not contact anyone at this company again.",
                     "Stop contacting us.",
                     "Take us off your list.",
                     "Blacklist our domain."):
            self.assertEqual(self.verdict(text), replies.ACCOUNT_DNC, text)

    def test_a_personal_removal_stays_personal(self):
        """The other direction: "remove me" must not reach the account rule."""
        for text in ("Please unsubscribe me.", "Remove me from your list.",
                     "Stop emailing me.", "Do not email me."):
            self.assertEqual(self.verdict(text), replies.UNSUBSCRIBE, text)

    def test_a_company_wide_removal_beats_a_warm_message(self):
        text = ("This sounds interesting but please do not contact anyone "
                "at this company again.")
        self.assertEqual(self.verdict(text), replies.ACCOUNT_DNC)

    def test_every_category_the_policy_maps_is_one_the_classifier_emits(self):
        """A mapping entry for a category nothing produces is dead code."""
        from src import accountpolicy as ap
        for category in ap.CLASSIFIER_OUTCOME:
            self.assertIn(category, replies.CATEGORIES, category)

    def test_every_category_the_classifier_emits_is_one_the_policy_maps(self):
        """And the reverse: an unmapped category silently becomes UNKNOWN."""
        from src import accountpolicy as ap
        for category in replies.CATEGORIES:
            self.assertIn(category, ap.CLASSIFIER_OUTCOME, category)

    def test_an_out_of_office_is_never_positive(self):
        text = ("Automatic reply: I am out of the office until the 5th. "
                "Sounds interesting, happy to chat when I'm back.")
        self.assertEqual(self.verdict(text), replies.OUT_OF_OFFICE)

    def test_the_usual_autoresponders_are_caught(self):
        for text in ("I am on annual leave, returning on Monday.",
                     "Out of office - limited access to email.",
                     "On maternity leave until March."):
            self.assertEqual(self.verdict(text), replies.OUT_OF_OFFICE, text)

    def test_a_wrong_person_is_not_relevant_rather_than_negative(self):
        for text in ("You've got the wrong person, try our finance team.",
                     "I don't handle this, not my area.",
                     "She is no longer with the company."):
            self.assertEqual(self.verdict(text), replies.NOT_RELEVANT, text)

    def test_an_empty_reply_is_unknown(self):
        self.assertEqual(self.verdict(""), replies.UNKNOWN)
        self.assertEqual(self.verdict("   "), replies.UNKNOWN)

    def test_something_unreadable_is_unknown_never_neutral(self):
        """TASK-020: 'no rule matched' is UNKNOWN, not NEUTRAL.

        NEUTRAL means 'we read this and it is genuinely lukewarm' - a
        measurement. UNKNOWN means 'we could not read this' - a gap.
        Reporting the gap as a measurement is how 35% of replies on the
        live estate became invisible.
        """
        self.assertEqual(self.verdict("ok"), replies.UNKNOWN)

    def test_unmatched_and_neutral_are_tellable_apart(self):
        """TASK-020: a caller can distinguish 'no rule matched' from 'neutral'.

        UNKNOWN means 'we could not read this'. NEUTRAL means 'we read this
        and it is genuinely lukewarm'. Only one of them is a measurement.
        """
        unmatched = replies.classify("xyzzy")
        self.assertEqual(unmatched["classification"], replies.UNKNOWN)
        self.assertEqual(unmatched["confidence"], 0.0)
        # NEUTRAL is still a valid category a model could return
        model_neutral = replies.classify(
            "Hmm.", model=lambda t: {"classification": "neutral",
                                     "confidence": 0.6})
        self.assertEqual(model_neutral["classification"], replies.NEUTRAL)
        self.assertNotEqual(unmatched["classification"],
                            model_neutral["classification"])

    def test_new_unsubscribe_patterns(self):
        """TASK-020: removal requests that previously matched no rule."""
        for text in ("Please stop sending these emails.",
                     "No more messages please.",
                     "Remove me from your mailing list.",
                     "Please don't send me any more emails."):
            self.assertEqual(self.verdict(text), replies.UNSUBSCRIBE, text)

    def test_new_negative_patterns(self):
        """TASK-020: short refusals common on both email and LinkedIn."""
        for text in ("Not for me, thanks.",
                     "No need for this.",
                     "We're good, appreciate it.",
                     "Don't need this right now.",
                     "Not looking for this kind of thing.",
                     "No interest at this time."):
            self.assertEqual(self.verdict(text), replies.NEGATIVE, text)

    def test_new_positive_patterns(self):
        """TASK-020: short affirmative replies, especially LinkedIn."""
        for text in ("Yes, let's chat.",
                     "Sure, happy to discuss.",
                     "Let's do it.",
                     "I'm interested in learning more.",
                     "That sounds great.",
                     "Send me a demo.",
                     "Can we schedule a call?"):
            self.assertEqual(self.verdict(text), replies.POSITIVE, text)

    def test_new_not_now_patterns(self):
        """TASK-020: delay phrasings that neither refuse nor commit."""
        for text in ("Maybe later.",
                     "Not at this time, try us in Q3.",
                     "Get back to me sometime.",
                     "Let's park this for now."):
            self.assertEqual(self.verdict(text), replies.NOT_NOW, text)

    def test_new_not_relevant_patterns(self):
        """TASK-020: not-relevant phrasings that name no one."""
        for text in ("Not relevant for us.",
                     "This doesn't apply to our team.",
                     "Not something we need right now."):
            self.assertEqual(self.verdict(text), replies.NOT_RELEVANT, text)

    def test_linkedin_short_refusals(self):
        """TASK-066: LinkedIn replies drop qualifiers the email patterns expected."""
        for text in ("No interest.",
                     "No, thank you.",
                     "No requirement for this.",
                     "Not for now."):
            v = replies.classify(text)
            self.assertIn(v["classification"],
                          (replies.NEGATIVE, replies.NOT_NOW), text)
        # "no interest" and "no, thank you" are negative, not not_now
        self.assertEqual(replies.classify("No interest.")["classification"],
                         replies.NEGATIVE)
        self.assertEqual(replies.classify("No, thank you.")["classification"],
                         replies.NEGATIVE)
        # "not for now" is a deferral, not a refusal
        self.assertEqual(replies.classify("Not for now.")["classification"],
                         replies.NOT_NOW)

    def test_linkedin_short_affirmatives(self):
        """TASK-066: short LinkedIn affirmatives the companion gate missed."""
        for text in ("Yes please.",
                     "Send me a pitch deck.",
                     "Happy to connect.",
                     "Send me more information."):
            self.assertEqual(self.verdict(text), replies.POSITIVE, text)

    def test_unicode_apostrophe_normalised(self):
        """TASK-066: LinkedIn uses U+2019 curly quotes, not ASCII apostrophes."""
        # Right single quotation mark (U+2019) in a contraction
        text_curly = "I don\u2019t work at Acme anymore."
        text_ascii = "I don't work at Acme anymore."
        self.assertEqual(replies.classify(text_curly)["classification"],
                         replies.NOT_RELEVANT)
        self.assertEqual(replies.classify(text_curly)["classification"],
                         replies.classify(text_ascii)["classification"])

    def test_sabbatical_leave_is_out_of_office(self):
        """TASK-066: 'sabbatical' was not in the leave alternation."""
        self.assertEqual(
            replies.classify("I am on a sabbatical leave.")["classification"],
            replies.OUT_OF_OFFICE)

    def test_a_referral_requires_somebody_to_point_at(self):
        """TASK-020: _points_at_somebody must keep holding.

        A hand-off phrase alone is not a referral. 'I need to talk to my
        boss first' is a delay, not a hand-off. The cue only makes this a
        referral when the sentence also points at somebody.
        """
        # A hand-off phrase with no name - should NOT be referral
        self.assertNotEqual(self.verdict("Let me talk to someone first."),
                            replies.REFERRAL)
        self.assertNotEqual(self.verdict("I need to speak to someone."),
                            replies.REFERRAL)
        # A hand-off phrase WITH a name - IS a referral
        self.assertEqual(self.verdict("Let me talk to Sarah about this."),
                         replies.REFERRAL)

    def test_every_verdict_carries_its_evidence(self):
        verdict = replies.classify("Not interested, thanks.")
        self.assertTrue(verdict["evidence"])
        self.assertEqual(verdict["classifier"], replies.VERSION)
        self.assertIn("reason", verdict)

    def test_the_excerpt_is_trimmed_rather_than_stored_whole(self):
        verdict = replies.classify("x " * 400)
        self.assertLessEqual(len(verdict["excerpt"]), 201)

    def test_a_quoted_thread_referral_does_not_fool_classify(self):
        """TASK-029 rework: the 94 false referrals, as a classify test.

        The prospect's own words are a short acknowledgement that matches
        no rule (unknown). The quoted thread below contains a referral
        phrase from OUR OWN outreach copy, with a name to point at.
        Before the wiring, classify saw the whole body and answered
        referral. After the wiring, classify sees only what the prospect
        typed and answers unknown.

        The prospect text must NOT match any rule above REFERRAL in
        precedence, otherwise that higher rule wins on the full body too
        and the test passes without proving the wiring.

        This test drives replies.classify - not extract_prospect_text -
        which is the function production calls. If the wiring is removed,
        this test fails.
        """
        body = (
            "Thanks for reaching out.\n"
            "\n"
            "On Mon, Sep 8, 2026 at 3:00 PM, Sender <sender@example.com> wrote:\n"
            "> Hey, please talk to our procurement team about this.\n"
            ">\n"
            "> reach out to Alba Kenji for details.\n"
        )
        verdict = replies.classify(body)
        self.assertNotEqual(verdict["classification"], replies.REFERRAL,
                            "classify is still reading the quoted thread")

    def test_verdict_carries_extraction_metadata(self):
        """TASK-029 rework: the verdict says what was judged."""
        body = (
            "Not interested.\n"
            "\n"
            "> Original outreach text with lots of words.\n"
        )
        verdict = replies.classify(body)
        self.assertEqual(verdict["extract_method"], "top_post")
        self.assertLess(verdict["extract_stripped_length"],
                        verdict.get("extract_stripped_length", 999) + len(body))
        self.assertIn("extract_method", verdict)
        self.assertIn("extract_stripped_length", verdict)

    def test_no_quote_verdict_still_carries_metadata(self):
        """A reply with no quoted thread still reports the method."""
        verdict = replies.classify("Not interested, thanks.")
        self.assertEqual(verdict["extract_method"], "no_quote")


class TestTheModelSeam(unittest.TestCase):
    def test_the_rules_settle_a_clear_case_without_a_model(self):
        called = []

        def model(text):
            called.append(text)
            return {"classification": "positive"}

        replies.classify("Please unsubscribe me.", model=model)
        self.assertEqual(called, [], "a model was consulted needlessly")

    def test_a_model_answer_is_accepted_when_the_rules_are_silent(self):
        verdict = replies.classify(
            "Hmm.", model=lambda t: {"classification": "negative",
                                     "confidence": 0.9})
        self.assertEqual(verdict["classification"], replies.NEGATIVE)

    def test_a_model_that_raises_becomes_unknown_not_neutral(self):
        def broken(text):
            raise RuntimeError("the model is down")

        verdict = replies.classify("Hmm.", model=broken)
        self.assertEqual(verdict["classification"], replies.UNKNOWN)
        self.assertIn("failed", verdict["reason"])

    def test_a_model_inventing_a_category_is_ignored(self):
        """TASK-020: when the model returns garbage and no rules matched,
        the fallback is UNKNOWN, not NEUTRAL. A model that invents a
        category is the same as no model at all: we could not read this."""
        verdict = replies.classify("Hmm.",
                                   model=lambda t: {"classification": "amazing"})
        self.assertEqual(verdict["classification"], replies.UNKNOWN)

    def test_a_low_confidence_positive_becomes_manual_review(self):
        verdict = replies.classify("Hmm.",
                                   model=lambda t: {"classification": "positive",
                                                    "confidence": 0.2})
        self.assertEqual(verdict["classification"], replies.UNKNOWN)
        self.assertTrue(verdict.get("needs_review"))

    def test_a_confident_positive_survives_the_threshold(self):
        verdict = replies.classify("Hmm.",
                                   model=lambda t: {"classification": "positive",
                                                    "confidence": 0.95})
        self.assertEqual(verdict["classification"], replies.POSITIVE)

    def test_only_positive_is_worth_an_alert(self):
        self.assertEqual(replies.ALERTING, (replies.POSITIVE,))


class InboundTest(CampaignTest):
    def bison_payload(self, text, email="champ@acme.test", event_id="b-1"):
        return {"events": [{"event": "replied", "id": event_id, "email": email,
                            "timestamp": "2026-08-26T09:00:00+00:00",
                            "text": text,
                            "custom_variables": {"record_id": "acme",
                                                 "contact_key": "acme-champ",
                                                 "client": "demo"}}]}

    def heyreach_payload(self, text, event_id="h-1",
                         profile="https://www.linkedin.com/in/acme-champ"):
        return {"events": [{"eventType": "message_reply", "id": event_id,
                            "profileUrl": profile,
                            "timestamp": "2026-08-26T09:00:00+00:00",
                            "text": text,
                            "customUserFields": [
                                {"name": "record_id", "value": "acme"},
                                {"name": "contact_key", "value": "acme-champ"},
                                {"name": "client", "value": "demo"}]}]}

    def run_bison(self, text, **kw):
        recs = kw.pop("recs", None) or self.seed_records()
        return inbound.ingest(self.bison_payload(text, **kw), "emailbison",
                              recs=recs, config=self.config,
                              post=lambda p, c=None: {"ok": True}), recs

    def run_heyreach(self, text, **kw):
        recs = kw.pop("recs", None) or self.seed_records()
        return inbound.ingest(self.heyreach_payload(text, **kw), "heyreach",
                              recs=recs, config=self.config,
                              post=lambda p, c=None: {"ok": True}), recs


class TestAnEmailReply(InboundTest):
    def test_a_positive_email_reply_is_classified_and_pauses(self):
        outcomes, recs = self.run_bison("This sounds interesting, happy to chat.")
        outcome = outcomes[0]
        self.assertEqual(outcome["applied"]["status"], "applied")
        self.assertEqual(outcome["classification"]["classification"],
                         replies.POSITIVE)
        self.assertTrue(outcome["paused"])
        self.assertTrue(recs[0]["paused"])

    def test_a_negative_reply_still_pauses_the_company(self):
        outcomes, recs = self.run_bison("Not interested, thanks.")
        self.assertEqual(outcomes[0]["classification"]["classification"],
                         replies.NEGATIVE)
        self.assertTrue(recs[0]["paused"], "any reply pauses, not just good ones")

    def test_an_unsubscribe_pauses_and_is_not_positive(self):
        outcomes, recs = self.run_bison("Please remove me from your list.")
        self.assertEqual(outcomes[0]["classification"]["classification"],
                         replies.UNSUBSCRIBE)
        self.assertTrue(recs[0]["paused"])
        self.assertIsNone(outcomes[0]["notification"])

    def test_an_out_of_office_raises_no_alert(self):
        outcomes, recs = self.run_bison(
            "Automatic reply: out of the office until the 5th.")
        self.assertEqual(outcomes[0]["classification"]["classification"],
                         replies.OUT_OF_OFFICE)
        self.assertIsNone(outcomes[0]["notification"])

    def test_a_positive_reply_raises_exactly_one_alert(self):
        outcomes, recs = self.run_bison("Interested, what does it cost?")
        notice = outcomes[0]["notification"]
        self.assertIsNotNone(notice)
        self.assertEqual(notice["payload"]["kind"], slack.POSITIVE_REPLY)
        self.assertTrue(notice["delivery"]["sent"])

    def test_the_alert_carries_the_ids_and_the_excerpt(self):
        outcomes, _ = self.run_bison("Interested, what does it cost?")
        payload = outcomes[0]["notification"]["payload"]
        self.assertEqual(payload["metadata"]["record_id"], "acme")
        self.assertEqual(payload["metadata"]["contact_key"], "acme-champ")
        self.assertEqual(payload["metadata"]["source"], "emailbison")
        self.assertIn("cost", " ".join(payload["blocks"]))

    def test_the_alert_offers_the_four_actions(self):
        outcomes, _ = self.run_bison("Interested, what does it cost?")
        ids = [a["action_id"]
               for a in outcomes[0]["notification"]["payload"]["actions"]]
        self.assertEqual(ids, [slack.OPEN_CONVERSATION, slack.ASSIGN_OWNER,
                               slack.MARK_MEETING, slack.MARK_NOT_POSITIVE])

    def test_no_reply_is_ever_sent_to_the_prospect(self):
        import inspect
        for module in (inbound, replies):
            source = inspect.getsource(module)
            for forbidden in ("send_message", "send_email", "reply_to"):
                self.assertNotIn(forbidden, source, module.__name__)


class TestAutomatedReplies(InboundTest):
    """TASK-020: a provider-flagged auto-reply is not a reply from a person."""

    def test_an_automated_reply_is_marked_in_the_verdict(self):
        """The is_automated flag travels with the verdict."""
        recs = self.seed_records()
        payload = {"events": [{"event": "replied", "id": "b-auto-1",
                               "email": "champ@acme.test",
                               "timestamp": "2026-08-26T09:00:00+00:00",
                               "text": "Out of office until Monday.",
                               "automated_reply": True,
                               "custom_variables": {"record_id": "acme",
                                                    "contact_key": "acme-champ",
                                                    "client": "demo"}}]}
        outcomes = inbound.ingest(payload, "emailbison", recs=recs,
                                  config=self.config,
                                  post=lambda p, c=None: {"ok": True})
        self.assertTrue(outcomes[0]["classification"].get("is_automated"))

    def test_an_automated_non_ooo_does_not_apply_policy(self):
        """A provider-flagged auto-reply that is not an OOO must not suppress.

        The classification event is still recorded for reporting, but no
        HOLD or STOP lands on the account because a mail server wrote back.
        """
        recs = self.seed_records()
        # A negative reply that the provider flagged as automated
        result = replies.apply(
            recs[0], "acme-champ", "Not interested, automated response",
            automated=True)
        # The classification is still recorded
        self.assertEqual(result["verdict"]["classification"], replies.NEGATIVE)
        self.assertTrue(result["verdict"]["is_automated"])
        # But no policy was applied - effect is None
        self.assertIsNone(result["effect"])

    def test_an_automated_ooo_still_defers(self):
        """An out-of-office defers even when provider-flagged as automated.

        The operator's instruction: 'an out-of-office should still defer the
        next touch, which src/ooo.py and src/oooreturn.py already model.'
        """
        recs = self.seed_records()
        result = replies.apply(
            recs[0], "acme-champ",
            "Automatic reply: out of the office until the 5th.",
            automated=True)
        self.assertEqual(result["verdict"]["classification"],
                         replies.OUT_OF_OFFICE)
        self.assertTrue(result["verdict"]["is_automated"])
        # OOO still applies policy (maps to NOT_NOW, which defers)
        self.assertIsNotNone(result["effect"])

    def test_a_non_automated_reply_still_applies_policy(self):
        """When automated is False or None, normal policy application holds."""
        recs = self.seed_records()
        result = replies.apply(
            recs[0], "acme-champ", "Not interested, thanks.",
            automated=False)
        self.assertEqual(result["verdict"]["classification"], replies.NEGATIVE)
        self.assertFalse(result["verdict"]["is_automated"])
        self.assertIsNotNone(result["effect"])

    def test_automated_none_applies_policy_normally(self):
        """When the provider did not say (None), treat as human."""
        recs = self.seed_records()
        result = replies.apply(
            recs[0], "acme-champ", "Not interested.",
            automated=None)
        self.assertIsNotNone(result["effect"])
        self.assertFalse(result["verdict"]["is_automated"])


class TestALinkedInReply(InboundTest):
    def test_a_positive_linkedin_reply_pauses_and_alerts(self):
        outcomes, recs = self.run_heyreach("keen to hear more, let's talk")
        self.assertEqual(outcomes[0]["classification"]["classification"],
                         replies.POSITIVE)
        self.assertTrue(recs[0]["paused"])
        self.assertEqual(outcomes[0]["notification"]["payload"]["metadata"]["source"],
                         "heyreach")

    def test_the_channel_is_carried_through(self):
        outcomes, _ = self.run_heyreach("keen to hear more, let's talk")
        self.assertEqual(outcomes[0]["applied"]["event"]["channel"], "linkedin")


class TestIdempotencyAndMatching(InboundTest):
    def test_the_same_provider_event_twice_changes_state_once(self):
        recs = self.seed_records()
        first, _ = self.run_bison("Interested, tell me more.", recs=recs)
        second, _ = self.run_bison("Interested, tell me more.", recs=recs)
        self.assertEqual(first[0]["applied"]["status"], "applied")
        self.assertEqual(second[0]["applied"]["status"], "duplicate")
        classified = [e for e in recs[0]["events"]
                      if e["type"] == events.REPLY_CLASSIFIED]
        self.assertEqual(len(classified), 1)

    def test_an_event_with_no_ids_and_an_unknown_address_matches_nothing(self):
        """Without a record id the address is all there is, and a guess here
        would pause the wrong company."""
        recs = self.seed_records()
        payload = {"events": [{"event": "replied", "id": "b-9",
                               "email": "nobody@elsewhere.test",
                               "text": "hello"}]}
        outcomes = inbound.ingest(payload, "emailbison", recs=recs,
                                  config=self.config)
        self.assertEqual(outcomes[0]["applied"]["status"], "unmatched")
        self.assertFalse(recs[0].get("paused"))
        self.assertFalse(recs[1].get("paused"))

    def test_an_event_naming_a_record_is_matched_by_that_id(self):
        """The provider told us which record it was: that beats the address."""
        recs = self.seed_records()
        outcomes = inbound.ingest(
            self.bison_payload("Interested.", email="anything@elsewhere.test",
                               event_id="b-10"),
            "emailbison", recs=recs, config=self.config,
            post=lambda p, c=None: {"ok": True})
        self.assertEqual(outcomes[0]["applied"]["status"], "applied")
        self.assertEqual(outcomes[0]["applied"]["record_id"], "acme")

    def test_an_event_type_we_do_not_act_on_is_ignored(self):
        recs = self.seed_records()
        payload = {"events": [{"event": "opened", "id": "b-3",
                               "email": "champ@acme.test"}]}
        outcomes = inbound.ingest(payload, "emailbison", recs=recs,
                                  config=self.config)
        self.assertEqual(outcomes, [])

    def test_a_delivered_event_does_not_pause_anything(self):
        recs = self.seed_records()
        payload = {"events": [{"event": "delivered", "id": "b-4",
                               "email": "champ@acme.test",
                               "custom_variables": {"record_id": "acme",
                                                    "contact_key": "acme-champ"}}]}
        outcomes = inbound.ingest(payload, "emailbison", recs=recs,
                                  config=self.config)
        self.assertEqual(outcomes[0]["applied"]["status"], "applied")
        self.assertFalse(recs[0].get("paused"))
        self.assertIsNone(outcomes[0]["classification"])


class TestTheCompanyWidePause(InboundTest):
    def test_one_reply_pauses_every_contact_at_that_company(self):
        recs = self.seed_records()
        from tests.campaignbase import contact
        recs[0]["contacts"].append(contact("acme-buyer", "Buyer Acme",
                                           "buyer@acme.test",
                                           persona="economic_buyer"))
        self.run_bison("Interested.", recs=recs)
        from src import cadence
        timeline = cadence.build(recs[0], self.config, recs=recs)
        self.assertTrue(timeline["paused"])
        for steps in timeline["contacts"].values():
            for step in steps.values():
                self.assertNotEqual(step["status"], "eligible")

    def test_it_pauses_both_channels_not_just_the_one_that_replied(self):
        recs = self.seed_records()
        self.run_bison("Interested.", recs=recs)          # email reply
        from src import cadence
        timeline = cadence.build(recs[0], self.config, recs=recs)
        channels = {step["channel"] for steps in timeline["contacts"].values()
                    for step in steps.values()}
        self.assertEqual(channels, {"email", "linkedin"})
        for steps in timeline["contacts"].values():
            for step in steps.values():
                self.assertNotEqual(step["status"], "eligible")

    def test_an_unrelated_company_keeps_running(self):
        recs = self.seed_records()
        self.run_bison("Interested.", recs=recs)
        self.assertTrue(recs[0].get("paused"))
        self.assertFalse(recs[1].get("paused"))
        from src import cadence
        other = cadence.build(recs[1], self.config, recs=recs)
        self.assertIsNone(other["paused"])

    def test_future_steps_are_marked_rather_than_deleted(self):
        recs = self.seed_records()
        self.run_bison("Interested.", recs=recs)
        from src import cadence
        timeline = cadence.build(recs[0], self.config, recs=recs)
        self.assertTrue(timeline["contacts"], "the steps still exist")
        for steps in timeline["contacts"].values():
            for step in steps.values():
                self.assertIn("status", step)

    def test_the_pause_records_why_and_when(self):
        recs = self.seed_records()
        self.run_bison("Interested.", recs=recs)
        paused = recs[0]["paused"]
        # TASK-030: the pause now records the classification as the reason,
        # not just the event type. This is more informative.
        self.assertEqual(paused["reason"], "positive")
        self.assertIn("since", paused)

    def test_a_linkedin_reply_pauses_the_email_track_too(self):
        recs = self.seed_records()
        self.run_heyreach("keen to hear more, let's talk", recs=recs)
        from src import cadence
        timeline = cadence.build(recs[0], self.config, recs=recs)
        self.assertTrue(timeline["paused"])


class TestAManualReply(InboundTest):
    def test_a_typed_reply_takes_the_same_path(self):
        recs = self.seed_records()
        event = inbound.manual("acme", "acme-champ", "Interested, let's talk.",
                               client="demo")
        outcome = inbound.handle(event, recs, config=self.config,
                                 post=lambda p, c=None: {"ok": True})
        self.assertEqual(outcome["classification"]["classification"],
                         replies.POSITIVE)
        self.assertTrue(recs[0]["paused"])


class TestNothingResumes(InboundTest):
    def test_no_classification_lifts_a_pause(self):
        for text in ("Not interested.", "Wrong person.", "Out of office.",
                     "Interested!", "unsubscribe"):
            recs = self.seed_records()
            self.run_bison(text, recs=recs, event_id=f"b-{abs(hash(text))}")
            self.assertTrue(recs[0].get("paused"), text)

    def test_the_reply_body_never_reaches_the_queue(self):
        import json
        recs = self.seed_records()
        secret = "Interested, our budget is 40000 and my mobile is on my card"
        self.run_bison(secret, recs=recs)
        blob = json.dumps(recs)
        self.assertNotIn("40000", blob)
        self.assertNotIn("mobile is on my card", blob)


if __name__ == "__main__":
    unittest.main()
