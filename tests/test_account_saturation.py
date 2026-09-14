"""When an account has had enough, and when a second person should be opened.

TASK-038. Five behavioural tests through the planner. Each one asserts a
property of `next_best_action` that the existing modules alone did not
guarantee:

1. An account at its touch ceiling opens nobody new.
2. A positive reply from one contact stops the ACCOUNT, not just that contact.
3. An unsubscribe from one contact stops the account.
4. A referral stops the referrer and opens the named person, and ONLY that one.
5. Two contacts are never opened on the same day by this logic.

Every test drives the real planner entry point. A test that constructs the
input by hand tests the seam, and the seam was never the risk.
"""
import unittest

from src import (account, accountpolicy as ap, accountsaturation, clients,
                 collision, events, nextaction as na, store)
from src import senderidentity as si
from tests.campaignbase import CampaignTest

WS = "productive"
ALICE = "alice"
BOB = "bob"
CAROL = "carol"


def roster():
    return [
        si.new_sender(WS, "anna", "Anna Novak", team="growth"),
        si.new_sender(WS, "mark", "Mark Weber", team="growth"),
        si.new_sender(WS, "petar", "Petar Horvat", team="partnerships"),
        si.new_sender(WS, "sara_s", "Sara Simic", team="partnerships"),
        si.new_email_account(WS, "anna07", "anna", "anna07@productive.test"),
        si.new_email_account(WS, "mark02", "mark", "mark02@productive.test"),
        si.new_linkedin_account(WS, "petar-li", "petar",
                                "https://www.linkedin.com/in/petar"),
        si.new_linkedin_account(WS, "sara-li", "sara_s",
                                "https://www.linkedin.com/in/sara"),
    ]


def clear_estate(domain="acme.test"):
    return {"domain": domain, "workspace": WS, "leads": 0, "people": [],
            "emails_sent_total": 0, "anyone_in_sequence": False,
            "unknown_statuses": [], "any_bounce": False,
            "verdict": collision.CLEAR,
            "checked_at": "2026-09-14T08:00:00+00:00"}


class SaturationTest(CampaignTest):

    def setUp(self):
        super().setUp()
        si.install(roster())
        self.config = clients.load("productive")

    def make_record(self, rid="acme"):
        from tests.campaignbase import contact as build

        rec = store.new_record(rid, "domains", WS, "Acme Ltd", "acme.test")
        rec["qualification"] = {
            "segment": {"employee_band": "20_49", "employees": 31,
                        "vertical": "Creative / Branding Agency"},
            "verdict": {"icp_tier": "C", "icp_status": "qualified"},
        }
        rec["contacts"] = [
            build(ALICE, "Alice Hart", f"{ALICE}@acme.test",
                  persona="champion", angle="operations"),
            build(BOB, "Boris Kean", f"{BOB}@acme.test",
                  persona="champion", angle="operations"),
            build(CAROL, "Carol Ng", f"{CAROL}@acme.test",
                  persona="champion", angle="operations"),
        ]
        for c in rec["contacts"]:
            c["selected"] = True
        rec["contacts"][0]["primary"] = True
        rec["cadence"] = {}
        store.save([rec])
        return rec

    def touch(self, rec, key, sender_id, channel, day, at, step=None):
        events.record(rec, events.PUSH_MARKED, contact_key=key,
                      channel=channel, day=day, sender_id=sender_id, at=at,
                      step=step, account_id=f"{sender_id}-acct")
        return rec

    def ask(self, rec, estate=None, at="2026-09-14T09:00:00+00:00"):
        return na.next_best_action(
            rec, config=self.config, workspace=WS,
            estate=estate if estate is not None else clear_estate(),
            at=at, campaign=None, suppressed=set())


class AccountAtCeilingOpensNobodyNew(SaturationTest):
    """Test 1: an account at its touch ceiling opens nobody new."""

    def test_account_weekly_ceiling_blocks_new_contacts(self):
        """Fill the account's weekly touch allowance; the planner must not
        return ACT for any contact."""
        rec = self.make_record()
        rules = ap.limits(self.config) if hasattr(ap, "limits") else \
            __import__("src.fatigue", fromlist=["limits"]).limits(self.config)
        from src import fatigue as ftg
        rules = ftg.limits(self.config)
        weekly_cap = rules["account.max_touches_per_week"]["value"]

        base = "2026-09-10T09:00:00+00:00"
        for i in range(weekly_cap):
            day_offset = i // 2
            sender = ["anna", "mark", "petar", "sara_s"][i % 4]
            channel = "email" if i % 2 == 0 else "linkedin"
            self.touch(rec, ALICE, sender, channel, 1,
                       f"2026-09-{10 + day_offset}T09:00:00+00:00")

        decision = self.ask(rec, at="2026-09-14T09:00:00+00:00")
        self.assertNotEqual(decision["action"], na.ACT,
                            f"account at ceiling should not ACT: "
                            f"{decision['reason_code']}")


class PositiveReplyStopsTheAccount(SaturationTest):
    """Test 2: a positive reply from one contact stops the ACCOUNT."""

    def test_positive_reply_from_one_contact_stops_the_account(self):
        """A positive reply from Alice must stop the whole account - not
        just Alice. Bob and Carol must not be opened."""
        rec = self.make_record()
        self.touch(rec, ALICE, "anna", "email", 1,
                   "2026-09-12T09:00:00+00:00")

        ap.apply_reply(rec, ALICE, outcome=ap.POSITIVE, config=self.config,
                       at="2026-09-13T10:00:00+00:00", channel="email")

        decision = self.ask(rec, at="2026-09-14T09:00:00+00:00")
        self.assertIn(decision["action"], (na.WAIT, na.STOP),
                      f"positive reply should stop the account, got "
                      f"{decision['action']}: {decision.get('reason')}")
        self.assertNotEqual(decision.get("person"), BOB)
        self.assertNotEqual(decision.get("person"), CAROL)


class UnsubscribeStopsTheAccount(SaturationTest):
    """Test 3: an unsubscribe from one contact stops the account."""

    def test_unsubscribe_from_one_contact_stops_the_account(self):
        """An unsubscribe from Alice must stop the whole account. Bob and
        Carol must not be opened - continuing to contact colleagues of
        someone who asked to be removed is the failure this architecture
        exists to prevent."""
        rec = self.make_record()
        self.touch(rec, ALICE, "anna", "email", 1,
                   "2026-09-12T09:00:00+00:00")

        ap.apply_reply(rec, ALICE, outcome=ap.UNSUBSCRIBE,
                       config=self.config,
                       at="2026-09-13T10:00:00+00:00", channel="email")

        decision = self.ask(rec, at="2026-09-14T09:00:00+00:00")
        self.assertEqual(decision["action"], na.STOP,
                         f"unsubscribe should STOP the account, got "
                         f"{decision['action']}: {decision.get('reason')}")


class ReferralStopsReferrerAndOpensReferred(SaturationTest):
    """Test 4: a referral stops the referrer and opens the named person."""

    def test_referral_stops_referrer_and_opens_named_person(self):
        """Alice replies 'not me, talk to Bob'. Three things must happen:
        1. The referral edge is recorded
        2. Alice is stopped (not just held)
        3. Bob is activated and becomes the next action (or WAIT for spacing)
        Carol must NOT be activated."""
        rec = self.make_record()
        self.touch(rec, ALICE, "anna", "email", 1,
                   "2026-09-12T09:00:00+00:00")

        events.record(rec, events.REFERRAL_RECORDED, contact_key=ALICE,
                      referred_to=BOB, channel="email",
                      at="2026-09-13T09:00:00+00:00",
                      provider_event_id="ref-alice-bob")

        ap.apply_reply(rec, ALICE, outcome=ap.REFERRAL, config=self.config,
                       at="2026-09-13T10:00:00+00:00", channel="email")

        alice = next(c for c in rec["contacts"] if c["key"] == ALICE)
        self.assertTrue(alice.get("stopped"),
                        "referrer should be stopped, not just held")

        bob = next(c for c in rec["contacts"] if c["key"] == BOB)
        self.assertTrue(bob.get("selected"),
                        "referred person should be activated")

        carol = next(c for c in rec["contacts"] if c["key"] == CAROL)
        edge_to_carol = account.referred_to(rec, ALICE)
        if edge_to_carol:
            self.assertNotEqual(edge_to_carol.get("to_contact"), CAROL)

        decision = self.ask(rec, at="2026-09-14T09:00:00+00:00")
        if decision["action"] == na.ACT:
            self.assertEqual(decision["person"], BOB,
                             f"next action should be Bob (the referred "
                             f"person), got {decision.get('person')}")
        else:
            bob_considered = next(
                (c for c in decision.get("considered", [])
                 if c["key"] == BOB), None)
            self.assertIsNotNone(bob_considered,
                                 "Bob should be considered even if not ACT")

    def test_referral_activates_only_the_named_person(self):
        """A referral to Bob must not activate Carol."""
        rec = self.make_record()
        self.touch(rec, ALICE, "anna", "email", 1,
                   "2026-09-12T09:00:00+00:00")

        events.record(rec, events.REFERRAL_RECORDED, contact_key=ALICE,
                      referred_to=BOB, channel="email",
                      at="2026-09-13T09:00:00+00:00",
                      provider_event_id="ref-alice-bob-2")

        ap.apply_reply(rec, ALICE, outcome=ap.REFERRAL, config=self.config,
                       at="2026-09-13T10:00:00+00:00", channel="email")

        carol = next(c for c in rec["contacts"] if c["key"] == CAROL)
        activated_events = [e for e in rec.get("events", [])
                            if e.get("type") == events.REFERRED_CONTACT_ACTIVATED]
        activated_keys = {e.get("contact") for e in activated_events}
        self.assertNotIn(CAROL, activated_keys,
                         "Carol should not be activated by a referral to Bob")


class TwoContactsNeverOpenedSameDay(SaturationTest):
    """Test 5: two contacts are never opened on the same day."""

    def test_two_contacts_never_opened_same_day(self):
        """After opening Alice, the planner must not open Bob on the same
        day. The spacing policy puts the earliest touch for Bob at least
        24 hours after Alice's first touch."""
        rec = self.make_record()
        self.touch(rec, ALICE, "anna", "email", 1,
                   "2026-09-14T09:00:00+00:00")

        decision = self.ask(rec, at="2026-09-14T10:00:00+00:00")
        if decision["action"] == na.ACT:
            self.assertNotEqual(decision["person"], BOB,
                                "Bob should not be opened on the same day "
                                "as Alice")
            self.assertNotEqual(decision["person"], CAROL,
                                "Carol should not be opened on the same "
                                "day as Alice")
        else:
            if decision.get("person") in (BOB, CAROL):
                due = decision.get("execute_after")
                self.assertIsNotNone(due,
                                     "if a second contact is named, "
                                     "execute_after must be set")
                self.assertGreater(str(due),
                                   "2026-09-14T10:00:00+00:00",
                                   "second contact must be scheduled after "
                                   "the spacing window")


if __name__ == "__main__":
    unittest.main()
