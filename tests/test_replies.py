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

    def test_something_unreadable_is_neutral_never_positive(self):
        self.assertEqual(self.verdict("ok"), replies.NEUTRAL)

    def test_every_verdict_carries_its_evidence(self):
        verdict = replies.classify("Not interested, thanks.")
        self.assertTrue(verdict["evidence"])
        self.assertEqual(verdict["classifier"], replies.VERSION)
        self.assertIn("reason", verdict)

    def test_the_excerpt_is_trimmed_rather_than_stored_whole(self):
        verdict = replies.classify("x " * 400)
        self.assertLessEqual(len(verdict["excerpt"]), 201)


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
        verdict = replies.classify("Hmm.",
                                   model=lambda t: {"classification": "amazing"})
        self.assertEqual(verdict["classification"], replies.NEUTRAL)

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
        self.assertEqual(paused["reason"], events.REPLY_RECEIVED)
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
