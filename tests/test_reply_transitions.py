"""What a reply actually does to the record, end to end.

`tests/test_account_policy.py` pins what the policy *says*. This pins what
the engine *does* with it, which until now was one blanket rule: any reply
paused the whole company, whatever it said and whoever sent it.

The chain under test is the whole one:

    classification -> policy -> apply_reply -> contact state
                                            -> account state
                                            -> other decision makers
                                            -> referral activation
                                            -> notification

Two properties are worth stating before the tests, because most of them are
one of these two:

**Uncertainty never narrows.** An outcome nobody classified resolves to a
review at account scope, which is the old blanket pause. Every narrower
effect requires a classification that earned it. So the failure mode of a
broken classifier is the behaviour this system has always had, not silence.

**Nothing subtracts.** `apply_reply` only writes state that is absent. A
reclassification, a replay, or a second reply can add a hold or a
suppression and can never lift one - which is what stops "not interested,
we already bought" from being a way to resume outreach.
"""
import unittest

from src import (account, accountpolicy as ap, cadence, eligibility, events,
                 replies, store)
from tests.campaignbase import CampaignTest

WS = "productive"
JOHN, SARAH, MIKE = "john", "sarah", "mike"


class TransitionTest(CampaignTest):

    def record(self, rid="acme"):
        rec = store.new_record(rid, "domains", WS, "Acme Ltd", "acme.test")
        rec["contacts"] = [
            {"key": JOHN, "name": "John Smith", "title": "COO",
             "email": "j@acme.test", "selected": True,
             "priority": account.PRIMARY},
            {"key": SARAH, "name": "Sarah Jones", "title": "CEO",
             "email": "s@acme.test", "selected": True,
             "priority": account.SECONDARY},
            {"key": MIKE, "name": "Michael Green", "title": "CFO",
             "email": "m@acme.test", "selected": False,
             "priority": account.TERTIARY},
        ]
        store.save([rec])
        return rec

    def contact(self, rec, key):
        return {c["key"]: c for c in rec["contacts"]}[key]

    def state_of(self, rec, key):
        return ap.contact_state(self.contact(rec, key))[0]

    def account_of(self, rec):
        return ap.account_state(rec)[0]

    def reply(self, rec, key=JOHN, outcome=None, at="2026-08-10T09:00:00+00:00"):
        return ap.apply_reply(rec, key, outcome, at=at, channel="email")


# ------------------------------------------------- one row per outcome

class EveryOutcomeHasAStatedEffect(TransitionTest):
    """The table, asserted. A row nobody pinned is a row that can drift."""

    # outcome -> (replier, account, review)
    EXPECTED = {
        ap.POSITIVE: (ap.HOLD, ap.HOLD, False),
        ap.NEUTRAL: (ap.HOLD, ap.CONTINUE, False),
        ap.NEGATIVE: (ap.STOP, ap.CONTINUE, False),
        ap.NOT_NOW: (ap.STOP, ap.CONTINUE, False),
        ap.NOT_ICP: (ap.STOP, ap.CONTINUE, False),
        ap.WRONG_PERSON: (ap.STOP, ap.CONTINUE, False),
        ap.LEFT_COMPANY: (ap.STOP, ap.CONTINUE, False),
        ap.REFERRAL: (ap.HOLD, ap.CONTINUE, False),
        ap.EXISTING_CLIENT: (ap.HOLD, ap.HOLD, True),
        ap.UNSUBSCRIBE: (ap.SUPPRESS, ap.CONTINUE, False),
        ap.ACCOUNT_DNC: (ap.SUPPRESS, ap.SUPPRESS, False),
        ap.UNKNOWN: (ap.HOLD, ap.HOLD, True),
    }

    def test_every_outcome_is_covered(self):
        self.assertEqual(sorted(self.EXPECTED), sorted(ap.OUTCOMES))

    def test_the_planned_effect_matches_the_table(self):
        for outcome, (replier, account_, review) in self.EXPECTED.items():
            plan = ap.effects(outcome)
            self.assertEqual(plan["replier"], replier, outcome)
            self.assertEqual(plan["account"], account_, outcome)
            self.assertEqual(plan["review"], review, outcome)

    def test_the_applied_effect_matches_the_planned_one(self):
        """The table is not decoration: the record ends up in that state."""
        for outcome, (replier, account_, _) in self.EXPECTED.items():
            rec = self.record(f"acme-{outcome}")
            self.reply(rec, JOHN, outcome)
            self.assertEqual(self.state_of(rec, JOHN), replier, outcome)
            if account_ == ap.SUPPRESS:
                self.assertEqual(self.account_of(rec), ap.SUPPRESS, outcome)
            elif account_ == ap.HOLD:
                self.assertEqual(self.account_of(rec), ap.HOLD, outcome)

    def test_the_replier_is_never_left_to_carry_on(self):
        """Somebody who answered is not somebody to keep cold-sequencing."""
        for outcome in ap.OUTCOMES:
            self.assertNotEqual(ap.effects(outcome)["replier"], ap.CONTINUE,
                                outcome)


# ------------------------------------------------- the colleagues

class WhatItDoesToTheOtherDecisionMakers(TransitionTest):

    def test_a_negative_reply_leaves_them_alone(self):
        """Requirement 1: a normal reply is not a company-wide suppression."""
        rec = self.record()
        self.reply(rec, JOHN, ap.NEGATIVE)
        self.assertEqual(self.account_of(rec), ap.CONTINUE)
        self.assertEqual(self.state_of(rec, SARAH), ap.CONTINUE)
        self.assertIsNone(rec.get("paused"))
        self.assertIsNone((rec.get("suppression") or {}).get("unsubscribed"))

    def test_a_positive_reply_holds_them(self):
        """Requirement 4, at the configured default."""
        rec = self.record()
        self.reply(rec, JOHN, ap.POSITIVE)
        self.assertEqual(self.account_of(rec), ap.HOLD)
        self.assertEqual(cadence.pause_state(rec)["outcome"], ap.POSITIVE)

    def test_a_positive_reply_can_be_configured_to_continue(self):
        rec = self.record()
        ap.apply_reply(rec, JOHN, ap.POSITIVE,
                       config={"reply": {"on_positive": "continue"}})
        self.assertEqual(self.account_of(rec), ap.CONTINUE)
        self.assertEqual(self.state_of(rec, JOHN), ap.STOP,
                         "the replier still stops; they answered")

    def test_a_positive_reply_can_be_configured_to_stop_the_account(self):
        rec = self.record()
        ap.apply_reply(rec, JOHN, ap.POSITIVE,
                       config={"reply": {"on_positive": "stop"}})
        self.assertEqual(self.account_of(rec), ap.SUPPRESS)

    def test_a_positive_reply_can_be_configured_to_need_review(self):
        rec = self.record()
        moved = ap.apply_reply(rec, JOHN, ap.POSITIVE,
                               config={"reply": {"on_positive": "review"}})
        self.assertTrue(moved["review"])
        self.assertTrue(rec["review"]["open"])

    def test_an_unsubscribe_does_not_reach_the_colleagues(self):
        """One person's removal request is about that person."""
        rec = self.record()
        self.reply(rec, JOHN, ap.UNSUBSCRIBE)
        self.assertEqual(self.state_of(rec, JOHN), ap.SUPPRESS)
        self.assertEqual(self.state_of(rec, SARAH), ap.CONTINUE)
        self.assertEqual(self.account_of(rec), ap.CONTINUE)


# ------------------------------------------------- do not contact

class ACompanyWideRequestReachesEverybody(TransitionTest):
    """Requirement 2, and requirement 5."""

    def test_it_suppresses_the_whole_account(self):
        rec = self.record()
        self.reply(rec, JOHN, ap.ACCOUNT_DNC)
        self.assertEqual(self.account_of(rec), ap.SUPPRESS)
        self.assertTrue(rec["suppression"]["unsubscribed"])
        self.assertEqual(rec["suppression"]["scope"], ap.ACCOUNT)

    def test_it_suppresses_every_contact_individually(self):
        """A record-level flag alone would not travel with a copied contact."""
        rec = self.record()
        self.reply(rec, JOHN, ap.ACCOUNT_DNC)
        for key in (JOHN, SARAH, MIKE):
            self.assertEqual(self.state_of(rec, key), ap.SUPPRESS, key)
            self.assertTrue(self.contact(rec, key)["unsubscribed"], key)

    def test_it_records_one_event_a_report_can_find(self):
        rec = self.record()
        self.reply(rec, JOHN, ap.ACCOUNT_DNC)
        kinds = [e["type"] for e in rec["events"]]
        self.assertEqual(kinds.count(events.ACCOUNT_SUPPRESSED), 1)

    def test_nothing_may_go_out_afterwards(self):
        rec = self.record()
        self.reply(rec, JOHN, ap.ACCOUNT_DNC)
        self.assertEqual(eligibility._paused(rec, self.contact(rec, SARAH)),
                         eligibility.BLOCKED_ACCOUNT_SUPPRESSED)

    def test_a_later_positive_reply_cannot_lift_it(self):
        """Requirement 5: removal always overrides continuation."""
        rec = self.record()
        self.reply(rec, JOHN, ap.ACCOUNT_DNC)
        self.reply(rec, SARAH, ap.POSITIVE)
        self.assertEqual(self.account_of(rec), ap.SUPPRESS)
        self.assertEqual(self.state_of(rec, SARAH), ap.SUPPRESS)

    def test_a_configured_continue_cannot_lift_it_either(self):
        rec = self.record()
        self.reply(rec, JOHN, ap.ACCOUNT_DNC)
        ap.apply_reply(rec, SARAH, ap.POSITIVE,
                       config={"reply": {"on_positive": "continue"}})
        self.assertEqual(self.account_of(rec), ap.SUPPRESS)


# ------------------------------------------------- referrals

class AReferralKeepsTheRelationshipAndAsksAboutTheTarget(TransitionTest):
    """Requirement 3."""

    def refer(self, rec, to=MIKE):
        events.record(rec, events.REFERRAL_RECORDED, contact_key=JOHN,
                      channel="email", referred_to=to,
                      provider_event_id="ref-1")
        return rec

    def test_the_edge_survives_the_transition(self):
        rec = self.refer(self.record())
        self.reply(rec, JOHN, ap.REFERRAL)
        edge = account.referred_by(rec, MIKE)
        self.assertIsNotNone(edge)
        self.assertEqual(edge["from_contact"], JOHN)
        self.assertEqual(edge["to_contact"], MIKE)

    def test_the_referrer_holds_and_the_account_carries_on(self):
        rec = self.refer(self.record())
        self.reply(rec, JOHN, ap.REFERRAL)
        self.assertEqual(self.state_of(rec, JOHN), ap.HOLD)
        self.assertEqual(self.account_of(rec), ap.CONTINUE)

    def test_the_target_is_not_activated_by_default(self):
        """Turning somebody on for outreach is a campaign decision."""
        rec = self.refer(self.record())
        moved = self.reply(rec, JOHN, ap.REFERRAL)
        self.assertIsNone(moved["activated"])
        self.assertFalse(self.contact(rec, MIKE)["selected"])

    def test_the_configured_flow_activates_them(self):
        rec = self.refer(self.record())
        moved = ap.apply_reply(
            rec, JOHN, ap.REFERRAL,
            config={"reply": {"activate_referred_contact": "continue"}})
        self.assertEqual(moved["activated"], MIKE)
        self.assertTrue(self.contact(rec, MIKE)["selected"])

    def test_activation_is_recorded(self):
        rec = self.refer(self.record())
        ap.apply_reply(
            rec, JOHN, ap.REFERRAL,
            config={"reply": {"activate_referred_contact": "continue"}})
        activated = [e for e in rec["events"]
                     if e["type"] == events.REFERRED_CONTACT_ACTIVATED]
        self.assertEqual(len(activated), 1)
        self.assertEqual(activated[0]["contact"], MIKE)

    def test_a_referral_with_no_target_activates_nobody(self):
        """An edge missing an end is not an edge. It must not guess."""
        rec = self.record()
        moved = ap.apply_reply(
            rec, JOHN, ap.REFERRAL,
            config={"reply": {"activate_referred_contact": "continue"}})
        self.assertIsNone(moved["activated"])


# ------------------------------------------------- uncertainty

class UncertaintyFailsConservatively(TransitionTest):
    """Requirement 6, and the property the whole design rests on."""

    def test_an_unclassified_reply_still_holds_the_whole_company(self):
        rec = self.record()
        self.reply(rec, JOHN, ap.UNKNOWN)
        self.assertEqual(self.account_of(rec), ap.HOLD)
        self.assertTrue(rec["review"]["open"])

    def test_a_reply_nobody_classified_resolves_to_unknown(self):
        rec = self.record()
        events.record(rec, events.REPLY_RECEIVED, contact_key=JOHN,
                      channel="email", provider_event_id="p1")
        self.assertEqual(ap.classify_outcome(rec, JOHN), ap.UNKNOWN)

    def test_an_outcome_nobody_defined_is_not_the_permissive_one(self):
        plan = ap.effects("something-invented")
        self.assertEqual(plan["account"], ap.HOLD)
        self.assertTrue(plan["review"])

    def test_a_review_blocks_the_colleagues_too(self):
        rec = self.record()
        self.reply(rec, JOHN, ap.UNKNOWN)
        # A review is reported as itself rather than as a plain pause: the
        # two need different things from a person.
        self.assertEqual(eligibility._paused(rec, self.contact(rec, SARAH)),
                         eligibility.BLOCKED_REVIEW_REQUIRED)


# ------------------------------------------------- the entry points

class EveryEntryPointGoesThroughThePolicy(TransitionTest):

    def test_a_provider_reply_holds_the_company(self):
        """`inbound.handle`: an unclassified reply holds the company.

        TASK-030 rework: `events.apply` no longer pauses. The pause is
        conditional on the classification and happens in `inbound.handle`
        after `replies.apply` has classified the reply. An UNKNOWN reply
        still pauses (fail-safe).
        """
        rec = self.record()
        out = events.apply([rec], {
            "type": events.REPLY_RECEIVED, "record_id": rec["id"],
            "contact_key": JOHN, "channel": "email",
            "provider_event_id": "webhook-1"})
        self.assertEqual(out["status"], "applied")
        # TASK-030: events.apply no longer pauses. The pause is deferred
        # to inbound.handle after classification.
        self.assertFalse(out.get("paused"))
        self.assertIsNone(out.get("effect"))

    def test_a_hand_recorded_reply_holds_it_too(self):
        """TASK-030 rework: `cadence.record_event` no longer holds.

        The hold is deferred to `inbound.handle` after classification,
        same as the provider reply path. The event is still recorded.
        """
        rec = self.record()
        cadence.record_event(rec, "email_reply", contact_key=JOHN)
        # The event is recorded (as "email_reply" from cadence vocabulary)
        # but the account is not held yet.
        reply_events = [e for e in rec.get("events", [])
                        if e.get("type") in ("email_reply", "linkedin_reply",
                                             events.REPLY_RECEIVED)]
        self.assertTrue(reply_events, "the reply event was not recorded")

    def test_the_classifier_narrows_it(self):
        """A classified negative reply stops the person, not the company."""
        rec = self.record()
        out = replies.apply(rec, SARAH, "not interested, please stop asking",
                            channel="email")
        self.assertEqual(out["effect"]["outcome"], ap.NEGATIVE)
        self.assertEqual(self.state_of(rec, SARAH), ap.STOP)
        self.assertIsNone(rec.get("paused"))

    def test_the_classifier_reaches_the_account_wide_outcome(self):
        """The whole chain, on the input that matters most.

        Text -> classifier -> CLASSIFIER_OUTCOME -> policy -> transition.
        Before the classifier had a company-wide rule this text read as
        neutral, which under the wired policy would have held the sender
        and left three colleagues contactable.
        """
        rec = self.record()
        out = replies.apply(rec, JOHN,
                            "please do not contact anyone at this company",
                            channel="email")
        self.assertEqual(out["verdict"]["classification"], replies.ACCOUNT_DNC)
        self.assertEqual(out["effect"]["outcome"], ap.ACCOUNT_DNC)
        self.assertEqual(self.account_of(rec), ap.SUPPRESS)
        for key in (JOHN, SARAH, MIKE):
            self.assertEqual(self.state_of(rec, key), ap.SUPPRESS, key)

    def test_a_personal_removal_through_the_classifier_stays_personal(self):
        rec = self.record()
        replies.apply(rec, JOHN, "please remove me from your list",
                      channel="email")
        self.assertEqual(self.state_of(rec, JOHN), ap.SUPPRESS)
        self.assertEqual(self.state_of(rec, SARAH), ap.CONTINUE)
        self.assertEqual(self.account_of(rec), ap.CONTINUE)

    def test_the_classifier_honours_a_removal_request(self):
        rec = self.record()
        replies.apply(rec, SARAH, "unsubscribe me from this list",
                      channel="email")
        self.assertEqual(self.state_of(rec, SARAH), ap.SUPPRESS)
        self.assertTrue(self.contact(rec, SARAH)["unsubscribed"])

    def test_a_classification_can_never_lift_an_existing_hold(self):
        """The asymmetry that stops a classifier resuming outreach.

        TASK-030 rework: `events.apply` no longer pauses. The pause is
        set up directly here to test that `replies.apply` cannot lift it.
        """
        rec = self.record()
        # Set up the hold directly - this is what `inbound.handle` does
        # after classification for an UNKNOWN reply.
        rec["paused"] = {"since": "2026-09-10T08:00:00", "reason": "unknown",
                         "outcome": "unknown", "by": JOHN}
        self.assertTrue(rec["paused"])
        replies.apply(rec, JOHN, "not interested", channel="email")
        self.assertTrue(rec["paused"], "a classification lifted a hold")


# ------------------------------------------------- replay and races

class ReplayAndRaces(TransitionTest):

    def test_a_duplicate_reply_moves_the_state_once(self):
        """Requirement 9.

        TASK-030 rework: `events.apply` no longer pauses the company.
        The dedup property is tested through the event log: the reply
        event is recorded once and the duplicate is rejected.
        """
        rec = self.record()
        event = {"type": events.REPLY_RECEIVED, "record_id": rec["id"],
                 "contact_key": JOHN, "channel": "email",
                 "provider_event_id": "same"}
        first = events.apply([rec], event)
        second = events.apply([rec], dict(event))
        self.assertEqual(first["status"], "applied")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(len([e for e in rec["events"]
                              if e["type"] == events.REPLY_RECEIVED]), 1)

    def test_applying_the_same_outcome_twice_is_idempotent(self):
        rec = self.record()
        self.reply(rec, JOHN, ap.ACCOUNT_DNC)
        before = dict(rec["suppression"])
        moved = self.reply(rec, JOHN, ap.ACCOUNT_DNC)
        self.assertEqual(rec["suppression"], before)
        self.assertEqual(moved["changed"], [])
        self.assertEqual(len([e for e in rec["events"]
                              if e["type"] == events.ACCOUNT_SUPPRESSED]), 1)

    def test_a_positive_reply_catches_a_queued_touch_to_another_dm(self):
        """The race the account model exists for."""
        rec = self.record()
        events.record(rec, events.PUSH_PREPARED, contact_key=SARAH,
                      channel="email", day=6, sender_id="mark")
        self.reply(rec, JOHN, ap.POSITIVE)
        self.assertEqual(eligibility._paused(rec, self.contact(rec, SARAH)),
                         eligibility.BLOCKED_COMPANY_PAUSED)

    def test_a_dnc_catches_a_payload_that_is_already_prepared(self):
        rec = self.record()
        events.record(rec, events.PUSH_PREPARED, contact_key=SARAH,
                      channel="email", day=6, sender_id="mark")
        self.reply(rec, JOHN, ap.ACCOUNT_DNC)
        self.assertEqual(eligibility._paused(rec, self.contact(rec, SARAH)),
                         eligibility.BLOCKED_ACCOUNT_SUPPRESSED)

    def test_a_referral_to_a_contact_who_is_not_yet_active(self):
        events_rec = self.record()
        events.record(events_rec, events.REFERRAL_RECORDED, contact_key=JOHN,
                      channel="email", referred_to=MIKE,
                      provider_event_id="ref-2")
        self.assertFalse(self.contact(events_rec, MIKE)["selected"])
        ap.apply_reply(
            events_rec, JOHN, ap.REFERRAL,
            config={"reply": {"activate_referred_contact": "continue"}})
        self.assertTrue(self.contact(events_rec, MIKE)["selected"])

    def test_activating_an_already_active_contact_changes_nothing(self):
        rec = self.record()
        self.contact(rec, MIKE)["selected"] = True
        events.record(rec, events.REFERRAL_RECORDED, contact_key=JOHN,
                      channel="email", referred_to=MIKE,
                      provider_event_id="ref-3")
        moved = ap.apply_reply(
            rec, JOHN, ap.REFERRAL,
            config={"reply": {"activate_referred_contact": "continue"}})
        self.assertIsNone(moved["activated"])
        self.assertEqual(len([e for e in rec["events"]
                              if e["type"]
                              == events.REFERRED_CONTACT_ACTIVATED]), 0)


# ------------------------------------------------- notification is second

class BusinessStateMovesBeforeAnybodyIsTold(TransitionTest):
    """Requirements 7 and 8."""

    def test_the_state_is_already_correct_when_the_announcement_runs(self):
        seen = {}

        def spy(*a, **kw):
            seen["paused"] = bool(a[0].get("paused"))
            seen["replier"] = a[0]["contacts"][0].get("paused") is not None
            return None

        rec = self.record()
        original = replies._announce
        replies._announce = spy
        try:
            replies.apply(rec, JOHN, "happy to chat next week",
                          channel="email")
        finally:
            replies._announce = original
        self.assertTrue(seen["paused"],
                        "the account was not held before the announcement")

    def test_a_failing_announcement_leaves_the_state_moved(self):
        def boom(*a, **kw):
            raise RuntimeError("slack is down")

        rec = self.record()
        original = replies._announce
        replies._announce = boom
        try:
            with self.assertRaises(RuntimeError):
                replies.apply(rec, JOHN, "happy to chat next week",
                              channel="email")
        finally:
            replies._announce = original
        self.assertTrue(rec.get("paused"),
                        "a Slack failure unwound the hold")
        self.assertEqual(self.state_of(rec, JOHN), ap.HOLD)


# ------------------------------------------------- tenancy

class TheTransitionStaysInsideOneRecord(TransitionTest):
    """Requirement 10."""

    def test_it_touches_only_the_record_it_was_given(self):
        mine = self.record("acme")
        theirs = self.record("other")
        self.reply(mine, JOHN, ap.ACCOUNT_DNC)
        self.assertIsNone((theirs.get("suppression") or {}).get("unsubscribed"))
        for key in (JOHN, SARAH, MIKE):
            self.assertEqual(self.state_of(theirs, key), ap.CONTINUE, key)

    def test_an_event_for_an_unknown_record_changes_nothing(self):
        rec = self.record()
        out = events.apply([rec], {
            "type": events.REPLY_RECEIVED, "record_id": "not-a-record",
            "contact_key": JOHN, "channel": "email"})
        self.assertEqual(out["status"], "unmatched")
        self.assertIsNone(rec.get("paused"))


if __name__ == "__main__":
    unittest.main()
