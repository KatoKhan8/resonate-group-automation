"""What a reply from one decision maker does to everybody else.

Account-based outreach forces a question the old one-contact model could not
ask: John replies positively, and Sarah and Michael have outreach planned.

Leaving that implicit means the software decides, which is the one thing it
must not do with a decision this consequential. So it is a policy with a
stated default, and these tests pin the defaults and the scoping.

The defaults lean towards holding. Every test that asserts one is asserting a
judgement, not a fact, and the judgement is: a hold somebody lifts costs a
day, and a message sent into a conversation that had already started cannot
be recalled.
"""
import unittest

from src import account, accountpolicy as ap, events, store
from tests.campaignbase import CampaignTest

WS = "productive"
JOHN, SARAH, MIKE = "john", "sarah", "mike"


class PolicyTest(CampaignTest):

    def record(self):
        rec = store.new_record("acme", "domains", WS, "Acme Ltd", "acme.test")
        rec["contacts"] = [
            {"key": JOHN, "name": "John Smith", "title": "COO",
             "email": "j@acme.test", "selected": True,
             "priority": account.PRIMARY},
            {"key": SARAH, "name": "Sarah Jones", "title": "CEO",
             "email": "s@acme.test", "selected": True,
             "priority": account.SECONDARY},
            {"key": MIKE, "name": "Michael Green", "title": "CFO",
             "email": "m@acme.test", "selected": True,
             "priority": account.TERTIARY},
        ]
        store.save([rec])
        return rec

    def touched(self):
        rec = self.record()
        events.record(rec, events.PUSH_MARKED, contact_key=JOHN,
                      channel="email", day=1, sender_id="anna")
        events.record(rec, events.PUSH_PREPARED, contact_key=SARAH,
                      channel="email", day=6, sender_id="mark")
        events.record(rec, events.PUSH_PREPARED, contact_key=MIKE,
                      channel="linkedin", day=9, sender_id="petar")
        return rec


class TheDefaultsLeanTowardsHolding(unittest.TestCase):

    def test_a_positive_reply_holds_the_account(self):
        """The moment an account is most likely to be mishandled."""
        found = ap.policy("reply.on_positive")
        self.assertEqual(found["action"], ap.HOLD)
        self.assertEqual(found["scope"], ap.ACCOUNT)

    def test_one_person_declining_is_not_the_company_declining(self):
        found = ap.policy("reply.on_negative")
        self.assertEqual(found["action"], ap.CONTINUE)
        self.assertEqual(found["scope"], ap.CONTACT)

    def test_an_unsubscribe_stops_that_person_permanently(self):
        found = ap.policy("reply.on_unsubscribe")
        self.assertEqual(found["action"], ap.STOP)
        self.assertEqual(found["scope"], ap.CONTACT)

    def test_a_company_wide_request_reaches_the_whole_company(self):
        """The one case where contact scope would be a compliance problem."""
        found = ap.policy("reply.on_account_dnc")
        self.assertEqual(found["action"], ap.STOP)
        self.assertEqual(found["scope"], ap.ACCOUNT)

    def test_every_policy_says_why_it_is_what_it_is(self):
        for entry in ap.policies():
            self.assertTrue(entry["why"], entry["key"])
            self.assertGreater(len(entry["why"]), 30, entry["key"])

    def test_every_default_is_a_real_action(self):
        for entry in ap.policies():
            self.assertIn(entry["action"], ap.ACTIONS, entry["key"])

    def test_nothing_is_configured_out_of_the_box(self):
        for entry in ap.policies():
            self.assertFalse(entry["configured"], entry["key"])

    def test_a_configured_action_replaces_the_default(self):
        found = ap.policy("reply.on_positive",
                          {"reply": {"on_positive": "stop"}})
        self.assertEqual(found["action"], ap.STOP)
        self.assertTrue(found["configured"])

    def test_a_nonsense_action_falls_back_to_the_default(self):
        """A typo in configuration must not widen anything."""
        found = ap.policy("reply.on_positive",
                          {"reply": {"on_positive": "carry-on-regardless"}})
        self.assertEqual(found["action"], ap.HOLD)
        self.assertFalse(found["configured"])


class AnUnknownOutcomeIsReviewed(unittest.TestCase):

    def test_an_outcome_with_no_policy_asks_a_person(self):
        decision = ap.resolve("something-nobody-defined")
        self.assertEqual(decision["action"], ap.REVIEW)

    def test_the_unknown_case_is_not_the_permissive_one(self):
        self.assertNotEqual(ap.resolve(ap.UNKNOWN)["action"], ap.CONTINUE)

    def test_the_reason_says_a_person_decides(self):
        self.assertIn("a person decides",
                      ap.resolve("whatever")["why"])


class ScopeDecidesWhoIsAffected(PolicyTest):

    def test_an_account_scoped_outcome_reaches_everybody(self):
        effect = ap.affected(self.touched(), JOHN, ap.POSITIVE)
        self.assertEqual(len(effect["contacts"]), 3)
        for entry in effect["contacts"]:
            self.assertEqual(entry["action"], ap.HOLD, entry["contact"])

    def test_a_contact_scoped_outcome_reaches_only_the_replier(self):
        effect = ap.affected(self.touched(), JOHN, ap.NEGATIVE)
        by_key = {c["contact_key"]: c for c in effect["contacts"]}
        self.assertEqual(by_key[SARAH]["action"], ap.CONTINUE)
        self.assertEqual(by_key[MIKE]["action"], ap.CONTINUE)
        self.assertIn("only the person who sent it", by_key[SARAH]["why"])

    def test_a_company_wide_stop_reaches_everybody(self):
        effect = ap.affected(self.touched(), JOHN, ap.ACCOUNT_DNC)
        for entry in effect["contacts"]:
            self.assertEqual(entry["action"], ap.STOP, entry["contact"])
        self.assertEqual(len(effect["stopped"]), 3)

    def test_an_unsubscribe_does_not_stop_the_colleagues(self):
        effect = ap.affected(self.touched(), JOHN, ap.UNSUBSCRIBE)
        by_key = {c["contact_key"]: c for c in effect["contacts"]}
        self.assertEqual(by_key[JOHN]["action"], ap.STOP)
        self.assertEqual(by_key[SARAH]["action"], ap.CONTINUE)

    def test_it_counts_the_planned_touches_a_hold_would_catch(self):
        effect = ap.affected(self.touched(), JOHN, ap.POSITIVE)
        by_key = {c["contact_key"]: c for c in effect["contacts"]}
        self.assertEqual(by_key[SARAH]["planned"], 1)
        self.assertEqual(by_key[MIKE]["planned"], 1)

    def test_the_replier_is_marked_as_such(self):
        effect = ap.affected(self.touched(), JOHN, ap.POSITIVE)
        by_key = {c["contact_key"]: c for c in effect["contacts"]}
        self.assertTrue(by_key[JOHN]["replier"])
        self.assertFalse(by_key[SARAH]["replier"])


class TheOutcomeIsReadNotInferred(PolicyTest):

    def test_an_unclassified_reply_is_unknown(self):
        rec = self.touched()
        events.record(rec, events.REPLY_RECEIVED, contact_key=JOHN,
                      channel="email")
        self.assertEqual(ap.classify_outcome(rec, JOHN), ap.UNKNOWN)

    def test_a_classified_reply_reports_its_classification(self):
        rec = self.touched()
        events.record(rec, events.REPLY_CLASSIFIED, contact_key=JOHN,
                      channel="email", classification="not_now")
        self.assertEqual(ap.classify_outcome(rec, JOHN), ap.NOT_NOW)

    def test_a_positive_detection_reports_positive(self):
        rec = self.touched()
        events.record(rec, events.POSITIVE_REPLY_DETECTED, contact_key=JOHN,
                      channel="email")
        self.assertEqual(ap.classify_outcome(rec, JOHN), ap.POSITIVE)

    def test_a_recorded_referral_reports_a_referral(self):
        rec = self.touched()
        events.record(rec, events.REFERRAL_RECORDED, contact_key=JOHN,
                      referred_to=SARAH, channel="email")
        self.assertEqual(ap.classify_outcome(rec, JOHN), ap.REFERRAL)

    def test_a_classification_nobody_defined_is_unknown_not_honoured(self):
        rec = self.touched()
        events.record(rec, events.REPLY_CLASSIFIED, contact_key=JOHN,
                      channel="email", classification="delighted")
        self.assertEqual(ap.classify_outcome(rec, JOHN), ap.UNKNOWN)

    def test_a_contact_who_has_not_replied_is_unknown(self):
        self.assertEqual(ap.classify_outcome(self.touched(), SARAH),
                         ap.UNKNOWN)


class ItSaysWhatTheEngineActuallyDoesToday(PolicyTest):
    """A policy screen that disagreed with behaviour would be worse than none.

    This used to assert the screen said "these policies are not wired in".
    They are now, so the same property is checked the other way round: the
    sentence claims the policies are in force, and the assertions below make
    the engine demonstrate it.
    """

    def test_the_screen_claims_the_policies_are_in_force(self):
        effect = ap.affected(self.touched(), JOHN, ap.NEGATIVE)
        self.assertIn("in force", effect["current_behaviour"])
        self.assertNotIn("separate, deliberate change",
                         effect["current_behaviour"])

    def test_and_a_negative_reply_really_does_leave_the_account_alone(self):
        """The case where policy and the old behaviour differed most."""
        rec = self.touched()
        ap.apply_reply(rec, JOHN, ap.NEGATIVE)
        self.assertIsNone(rec.get("paused"),
                          "a negative reply must not hold the whole company")
        self.assertEqual(ap.resolve(ap.NEGATIVE)["action"], ap.CONTINUE)

    def test_and_an_unclassified_one_really_does_hold_it(self):
        """The sentence also claims the uncertain case still holds."""
        rec = self.touched()
        ap.apply_reply(rec, JOHN, ap.UNKNOWN)
        self.assertIsNotNone(rec.get("paused"))
        self.assertIn("must not narrow", effect_text := ap.CURRENT_BEHAVIOUR)
        self.assertIn("unclassified", effect_text)


class OnePauseImplementation(unittest.TestCase):
    """`events.pause_company` was a second implementation of this transition
    and is deleted. It wrote `rec["paused"]` without `outcome`, while its
    docstring asserted that `accountpolicy._hold_account` called it - which it
    never did. A caller who trusted that would have produced a pause the audit
    cannot read.

    What is pinned here is the property that made the two differ, not the
    absence of a function: a pause records both what arrived and what we made
    of it. `_hold_account`'s own comment says why - "an audit that collapses
    them cannot answer 'we paused on a reply, but which reading of it'".
    """

    def paused_record(self):
        rec = {"id": "acme", "client": "demo",
               "contacts": [{"key": "a", "name": "Ada L",
                             "email": "ada@acme.test"}],
               "events": []}
        ap.apply_reply(
            rec, "a", ap.UNKNOWN, config=None,
            at="2026-09-09T10:00:00+00:00", channel="email",
            reason="email_reply", workspace="demo")
        return rec

    def test_an_unclassified_reply_holds_the_account(self):
        self.assertTrue(self.paused_record().get("paused"))

    def test_the_pause_records_what_arrived(self):
        self.assertEqual(self.paused_record()["paused"]["reason"],
                         "email_reply")

    def test_the_pause_records_what_we_made_of_it(self):
        """The field the deleted implementation omitted."""
        self.assertEqual(self.paused_record()["paused"]["outcome"],
                         ap.UNKNOWN)

    def test_those_are_two_facts_not_one(self):
        """If they were the same value the field would carry no information
        and dropping it would have been harmless."""
        paused = self.paused_record()["paused"]
        self.assertNotEqual(paused["reason"], paused["outcome"])


if __name__ == "__main__":
    unittest.main()
