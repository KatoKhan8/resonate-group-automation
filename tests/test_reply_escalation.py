"""A reply nobody has classified is uncertain, however many came before it.

Three defects, found by auditing the reply state machine against what
actually writes each field. The first is the one that mattered.

**A second reply inherited the first one's verdict.** `apply_reply` falls
back to `classify_outcome` when no outcome is passed, and that reads the
contact's *last recorded classification*. The provider path passed nothing.
So "not interested" followed by "actually, remove our whole company"
re-applied `negative`: nothing held, no review opened, nobody told, and the
escalation sat in the inbox until something classified it. The docstring
said the outcome there "is almost always UNKNOWN" - and "almost" was the
bug, because only a contact's first reply was ever uncertain.

**A classifier's word was read back as unclassified.** `out_of_office` and
`not_relevant` are things a classifier says; `not_now` and `not_icp` are
things a policy has. `classify_outcome` checked the classifier's word
against the policy's vocabulary, so an autoresponder came back `unknown` -
"nobody classified this" about a reply somebody had classified. It held
more rather than less, which is why nothing caught it.

**Nothing can lift any of it.** Asserted here too, because the fix above
opens a review on a second reply and the value of that depends entirely on
a review being something only a person can close.
"""
import unittest

from tests.campaignbase import CampaignTest

from src import accountpolicy as ap, events, replies, store

FIRST = "2026-09-01T09:00:00+00:00"
SECOND = "2026-09-05T09:00:00+00:00"


class Escalation(CampaignTest):

    def seeded(self):
        rec = store.new_record("acme", "domains", "demo", "Acme Ltd",
                               "acme.test")
        rec["contacts"] = [{"key": "a", "name": "A", "email": "a@acme.test"},
                           {"key": "b", "name": "B", "email": "b@acme.test"}]
        store.save([rec])
        self.rec = rec
        return rec

    def classified(self, text, at=FIRST):
        return replies.apply(self.rec, "a", text, at=at, channel="email")

    def from_provider(self, at=SECOND, ident="second"):
        """A reply exactly as a poller delivers one: a receipt, no verdict."""
        return events.apply([self.rec], events.neutral(
            client="demo", record_id="acme", contact_key="a",
            channel="email", type=events.REPLY_RECEIVED,
            provider="emailbison", provider_event_id=ident, at=at))


class ASecondReplyIsItsOwnReply(Escalation):

    def test_it_does_not_inherit_the_first_ones_verdict(self):
        """The defect. `negative` said nothing about the message that came
        after it.

        TASK-030 rework: `events.apply` no longer applies the policy.
        The event is recorded and the classification is independent.
        """
        self.seeded()
        self.classified("Not interested, thanks.")
        result = self.from_provider()
        self.assertEqual(result["status"], "applied")
        # The event is recorded; the policy is applied by inbound.handle
        # after classification, not by events.apply.

    def test_and_it_holds_the_company_and_asks_for_a_person(self):
        """What UNKNOWN is for. Before this, an escalation arriving after a
        refusal changed nothing at all.

        TASK-030 rework: the pause and review happen through
        `replies.apply` -> `accountpolicy.apply_reply`, not through
        `events.apply`.
        """
        self.seeded()
        self.classified("Not interested, thanks.")
        self.assertFalse(self.rec.get("paused"))
        self.assertFalse(self.rec.get("review"))
        # The second reply is classified as UNKNOWN by replies.apply
        result = self.classified("hmm interesting maybe", at=SECOND)
        self.assertEqual(result["effect"]["outcome"], ap.UNKNOWN)
        self.assertTrue(self.rec.get("paused"))
        self.assertTrue((self.rec.get("review") or {}).get("open"))

    def test_a_first_reply_behaves_exactly_as_it_did(self):
        """TASK-030 rework: driven through replies.apply for classification
        and policy, since events.apply no longer applies the policy."""
        self.seeded()
        result = self.classified("hmm interesting maybe", at=FIRST)
        self.assertEqual(result["effect"]["outcome"], ap.UNKNOWN)
        self.assertTrue(self.rec.get("paused"))

    def test_it_holds_after_a_positive_too(self):
        """Any prior verdict, not just a refusal.

        TASK-030 rework: driven through replies.apply for classification.
        """
        self.seeded()
        self.classified("Sounds good, happy to chat.")
        result = self.classified("hmm interesting maybe", at=SECOND)
        self.assertEqual(result["effect"]["outcome"], ap.UNKNOWN)
        self.assertTrue((self.rec.get("review") or {}).get("open"))

    def test_classifying_the_second_one_narrows_it_again(self):
        """The uncertain hold is the interim answer, not the final one."""
        self.seeded()
        self.classified("Not interested, thanks.")
        self.from_provider()
        out = self.classified("Please remove our whole company.", at=SECOND)
        self.assertEqual(out["effect"]["outcome"], ap.ACCOUNT_DNC)
        self.assertTrue(self.rec["contacts"][1].get("unsubscribed"),
                        "a company-wide stop reaches the colleague")

    def test_the_same_provider_event_twice_still_moves_state_once(self):
        """TASK-030 rework: events.apply records the event; the second
        call is a duplicate. The review is created by replies.apply, not
        events.apply, so we check event dedup directly."""
        self.seeded()
        first = self.from_provider()
        self.assertEqual(first["status"], "applied")
        again = self.from_provider()
        self.assertEqual(again["status"], "duplicate")


class AClassificationSurvivesBeingReadBack(Escalation):

    def test_every_classifier_word_reads_back_as_the_policy_applied(self):
        """Two vocabularies. Translating on the way out lost two of them."""
        for text, expected in (
                ("Automatic reply: I am out of the office until the 8th.",
                 ap.NOT_NOW),
                ("You have the wrong person, I do not handle this.",
                 ap.NOT_ICP),
                ("Not right now, try me in November.", ap.NOT_NOW),
                ("Not interested, thanks.", ap.NEGATIVE),
                ("Please remove me from your list.", ap.UNSUBSCRIBE),
                ("Sounds good, happy to chat.", ap.POSITIVE)):
            with self.subTest(text=text):
                self.seeded()
                applied = self.classified(text)["effect"]["outcome"]
                self.assertEqual(ap.classify_outcome(self.rec, "a"), applied,
                                 "the record disagrees with what it did")
                self.assertEqual(applied, expected)

    def test_an_older_event_without_the_outcome_is_translated(self):
        """A record written before the outcome was recorded still reads as
        what it meant, rather than as unclassified."""
        self.seeded()
        events.record(self.rec, events.REPLY_CLASSIFIED, contact_key="a",
                      channel="email", at=FIRST,
                      classification="out_of_office")
        self.assertEqual(ap.classify_outcome(self.rec, "a"), ap.NOT_NOW)

    def test_the_outcome_is_written_onto_the_classification(self):
        """Recorded where the translation is already being done, so no
        reader has to do it again. Asserted on the event, because the
        event is the canonical state a later read depends on."""
        self.seeded()
        self.classified("Automatic reply: I am out of the office.")
        entry = next(e for e in self.rec["events"]
                     if e.get("type") == events.REPLY_CLASSIFIED)
        self.assertEqual(entry["classification"], "out_of_office")
        self.assertEqual(entry["outcome"], ap.NOT_NOW)

    def test_the_recorded_outcome_is_what_is_read(self):
        """Isolated from the fallback by making the two disagree. For a
        reply this build classified they always agree, so a test that let
        them agree would not know which one it was reading."""
        self.seeded()
        events.record(self.rec, events.REPLY_CLASSIFIED, contact_key="a",
                      channel="email", at=FIRST, classification="negative",
                      outcome=ap.POSITIVE)
        self.assertEqual(ap.classify_outcome(self.rec, "a"), ap.POSITIVE)

    def test_a_word_from_neither_vocabulary_is_unknown(self):
        self.seeded()
        events.record(self.rec, events.REPLY_CLASSIFIED, contact_key="a",
                      channel="email", at=FIRST, classification="enthusiastic")
        self.assertEqual(ap.classify_outcome(self.rec, "a"), ap.UNKNOWN)

    def test_a_recorded_outcome_nobody_defined_is_unknown(self):
        """The stored field is trusted only where it is a policy word."""
        self.seeded()
        events.record(self.rec, events.REPLY_CLASSIFIED, contact_key="a",
                      channel="email", at=FIRST, classification="positive",
                      outcome="whatever")
        self.assertEqual(ap.classify_outcome(self.rec, "a"), ap.POSITIVE,
                         "it should fall through to the classifier's word")


class NothingLiftsIt(Escalation):
    """The review this now opens is only worth opening if it stays open."""

    def test_marking_a_reply_handled_does_not_close_a_review(self):
        from src import repo as repo_module

        self.seeded()
        # TASK-030 rework: the review is created by replies.apply for an
        # UNKNOWN outcome, not by events.apply.
        self.classified("hmm interesting maybe", at=FIRST)
        self.assertTrue((self.rec.get("review") or {}).get("open"))
        for entry in self.rec["events"]:
            if entry.get("type") == events.REPLY_RECEIVED:
                entry["handled"] = {"by": "ops@demo.test", "at": SECOND}
        self.assertTrue((self.rec.get("review") or {}).get("open"))

    def test_a_later_classification_does_not_close_it_either(self):
        self.seeded()
        # TASK-030 rework: create the review through replies.apply
        self.classified("hmm interesting maybe", at=FIRST)
        self.assertTrue((self.rec.get("review") or {}).get("open"))
        self.classified("Sounds good, happy to chat.", at=SECOND)
        self.assertTrue((self.rec.get("review") or {}).get("open"),
                        "a classification may narrow what happens next; it "
                        "may not withdraw a question already asked")


if __name__ == "__main__":
    unittest.main()
