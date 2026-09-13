#!/usr/bin/env python3
"""Which seats we may SEND from is not which seats hold OUR history.

The two questions shared one list, and the narrow answer was being used for
both. `our_linkedin_seats` is the attested sending pool - seats a human signed
off, because a seat reaches a prospect under a real person's name. Scoping the
INBOX to that same list discarded every conversation on a seat nobody had
attested, labelled `other_tenants_conversations_ignored`.

That label was false. Measured on the live estate, 2026-09-13:

    all 82 HeyReach campaigns carry organizationUnitId 118832
    39 of 41 seats appear in those campaigns
    23,617 conversations on roster seats + 2,422 off-roster = 26,039,
      which is the entire inbox
    of the 2,422 discarded, 188 are people who REPLIED

So 188 people who answered this client's own seats would have come back CLEAR,
and a second sender would have written to them. There is no second tenant
behind this key; there was a second list.

The tenant boundary is derived from the CAMPAIGNS, which are the only rows
that state an organisation unit - seat rows carry none. A key that sees two
units cannot attribute an inbox conversation from the answer alone, and that
refuses rather than guessing in either direction.
"""
import unittest
from unittest import mock

from src import collision


ROSTER = [{"provider_account_id": "1"}, {"provider_account_id": "2"}]
ALL_SEATS = [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]
CONFIG = {"providers": {"heyreach": {"org_unit": 118832}}}


def one_tenant(*units):
    return ([{"organizationUnitId": u} for u in (units or (118832,))], {})


class ScopeTest(unittest.TestCase):
    """The tenant scope is cached per process, so it is cleared per test.

    Found by this file failing only when run after another test that had
    already resolved it - a cache that outlives a test is a cache that
    answers the next one.
    """

    def setUp(self):
        collision.forget_tenant_scope()
        self.addCleanup(collision.forget_tenant_scope)


class TheTwoQuestionsAreAskedSeparately(ScopeTest):

    def test_the_sending_pool_is_the_attested_roster(self):
        with mock.patch("src.senderidentity.linkedin_accounts",
                        return_value=ROSTER):
            self.assertEqual(collision.our_linkedin_seats("productive"),
                             {"1", "2"})

    def test_the_history_scope_is_the_whole_tenant(self):
        with mock.patch("src.senderidentity.linkedin_accounts",
                        return_value=ROSTER), \
             mock.patch.object(collision.heyreach, "campaigns",
                               return_value=one_tenant()), \
             mock.patch.object(collision.heyreach, "all_li_accounts",
                               return_value=(ALL_SEATS, {})):
            seats = collision.seats_whose_conversations_are_ours(
                "productive", config=CONFIG)
        self.assertEqual(seats, {"1", "2", "3", "4"})

    def test_the_history_scope_is_strictly_wider(self):
        """The bug in one line: it used to be the same set."""
        with mock.patch("src.senderidentity.linkedin_accounts",
                        return_value=ROSTER), \
             mock.patch.object(collision.heyreach, "campaigns",
                               return_value=one_tenant()), \
             mock.patch.object(collision.heyreach, "all_li_accounts",
                               return_value=(ALL_SEATS, {})):
            sending = collision.our_linkedin_seats("productive")
            history = collision.seats_whose_conversations_are_ours(
                "productive", config=CONFIG)
        self.assertTrue(sending < history,
                        "the inbox scope is no wider than the sending pool")

    def test_an_attested_seat_the_provider_dropped_is_still_ours(self):
        """Its conversations are still this client's history."""
        with mock.patch("src.senderidentity.linkedin_accounts",
                        return_value=[{"provider_account_id": "99"}]), \
             mock.patch.object(collision.heyreach, "campaigns",
                               return_value=one_tenant()), \
             mock.patch.object(collision.heyreach, "all_li_accounts",
                               return_value=(ALL_SEATS, {})):
            seats = collision.seats_whose_conversations_are_ours(
                "productive", config=CONFIG)
        self.assertIn("99", seats)


class AMixedInboxCannotBeAttributed(ScopeTest):

    def test_two_organisation_units_refuse(self):
        with mock.patch("src.senderidentity.linkedin_accounts",
                        return_value=ROSTER), \
             mock.patch.object(collision.heyreach, "campaigns",
                               return_value=one_tenant(118832, 999)), \
             mock.patch.object(collision.heyreach, "all_li_accounts",
                               return_value=(ALL_SEATS, {})):
            with self.assertRaises(collision.CollisionUnknown) as caught:
                collision.seats_whose_conversations_are_ours(
                    "productive", config=CONFIG)
        self.assertIn("mixes tenants", str(caught.exception))

    def test_a_unit_that_is_not_ours_refuses_even_alone(self):
        with mock.patch("src.senderidentity.linkedin_accounts",
                        return_value=ROSTER), \
             mock.patch.object(collision.heyreach, "campaigns",
                               return_value=one_tenant(999)), \
             mock.patch.object(collision.heyreach, "all_li_accounts",
                               return_value=(ALL_SEATS, {})):
            with self.assertRaises(collision.CollisionUnknown):
                collision.seats_whose_conversations_are_ours(
                    "productive", config=CONFIG)

    def test_an_estate_stating_no_unit_at_all_refuses(self):
        """Missing evidence is not evidence of a single tenant."""
        with mock.patch("src.senderidentity.linkedin_accounts",
                        return_value=ROSTER), \
             mock.patch.object(collision.heyreach, "campaigns",
                               return_value=([{"id": 1}], {})), \
             mock.patch.object(collision.heyreach, "all_li_accounts",
                               return_value=(ALL_SEATS, {})):
            with self.assertRaises(collision.CollisionUnknown):
                collision.seats_whose_conversations_are_ours(
                    "productive", config=CONFIG)


if __name__ == "__main__":
    unittest.main()
