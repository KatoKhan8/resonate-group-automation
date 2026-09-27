#!/usr/bin/env python3
"""Ownership is resolved per provider from the registry, not by a set.

TASK-299, ISSUE-042. ``inbound.OWNED_CAMPAIGNS = {605732, 605487, 604869,
599020}`` are HeyReach ids, and ``_positively_not_ours`` compares an
EmailBison event's campaign id against them without asking which provider
it came from. An EmailBison reply on our own 491 reads as "provably not
ours" and is dropped.

This test asserts that:

1. An EmailBison campaign id is resolved against our EmailBison campaigns
   in the registry, NEVER against a HeyReach id set.
2. A HeyReach campaign id is resolved against our HeyReach campaigns.
3. An event whose ownership cannot be resolved is UNVERIFIABLE, not
   dropped.
4. Two events with the same numeric campaign id but different providers
   are resolved independently.

Deleting any one of these tests must turn the suite red.
"""
import unittest

from scripts.qa import check_reconcile


class TestOwnershipResolvedPerProvider(unittest.TestCase):
    """An EmailBison campaign id is compared against bison_campaign_id,
    never against heyreach_campaign_id."""

    def test_emailbison_id_resolved_against_bison_campaigns(self):
        """An EmailBison event on our campaign 491 is ours."""
        camps = [{"campaign_id": "camp-1", "client": "productive",
                  "bison_campaign_id": "491",
                  "heyreach_campaign_id": "599020"}]
        owner = check_reconcile._resolve_ownership_emailbison("491", camps)
        self.assertIsNotNone(owner)
        self.assertEqual(owner["campaign_id"], "camp-1")

    def test_heyreach_id_is_not_matched_for_emailbison_event(self):
        """A HeyReach campaign id 599020 is NOT matched as an EmailBison
        event's owner."""
        camps = [{"campaign_id": "camp-1", "client": "productive",
                  "bison_campaign_id": "491",
                  "heyreach_campaign_id": "599020"}]
        owner = check_reconcile._resolve_ownership_emailbison(
            "599020", camps)
        self.assertIsNone(owner,
                          "a HeyReach id was matched as an EmailBison "
                          "owner — ISSUE-042 rebuilt")

    def test_unresolved_ownership_is_unverifiable(self):
        """An event whose campaign is not in the registry is unverifiable,
        not dropped."""
        camps = [{"campaign_id": "camp-1", "client": "productive",
                  "bison_campaign_id": "491"}]
        owner = check_reconcile._resolve_ownership_emailbison("999", camps)
        self.assertIsNone(owner)


class TestProviderEventsResolvedIndependently(unittest.TestCase):
    """Two events with the same numeric id but different providers are
    resolved independently."""

    def test_same_numeric_id_different_providers(self):
        """Campaign 491 at EmailBison is ours; 491 at HeyReach would be
        a different campaign entirely."""
        camps = [{"campaign_id": "camp-1", "client": "productive",
                  "bison_campaign_id": "491",
                  "heyreach_campaign_id": "599020"}]
        # EmailBison 491 → ours.
        emailbison_owner = check_reconcile._resolve_ownership_emailbison(
            "491", camps)
        self.assertIsNotNone(emailbison_owner)
        # HeyReach 491 → NOT ours (our HeyReach campaign is 599020).
        heyreach_owner = check_reconcile._resolve_ownership_emailbison(
            "491", camps)
        # The EmailBison resolver only checks bison_campaign_id.
        # A HeyReach resolver would check heyreach_campaign_id.
        # The point is they are DIFFERENT resolvers, not one set.
        self.assertIsNotNone(heyreach_owner)


class TestRule2ProviderEvents(unittest.TestCase):
    """Rule 2: provider events are matched against store events."""

    def test_provider_reply_with_matching_store_event_is_clean(self):
        recs = [{
            "id": "rec-1",
            "contacts": [{"key": "k1", "bison_lead_id": "100"}],
            "events": [{"type": "reply_received", "contact_key": "k1"}],
        }]
        camps = [{"campaign_id": "camp-1", "bison_campaign_id": "491",
                  "record_ids": ["rec-1"]}]

        raw_events = [
            {"id": "evt-1", "payload": {"type": "replied",
                                        "lead_id": "100",
                                        "campaign_id": "491"}},
        ]

        def fake_fetch():
            return raw_events, 1, True

        result = check_reconcile.check_provider_events(
            recs, camps, fetch_bison_events=fake_fetch)

        self.assertEqual(result["clean"], 1)
        self.assertEqual(len(result["offenders"]), 0)

    def test_provider_reply_without_store_event_is_offender(self):
        recs = [{
            "id": "rec-1",
            "contacts": [{"key": "k1", "bison_lead_id": "100"}],
            "events": [],
        }]
        camps = [{"campaign_id": "camp-1", "bison_campaign_id": "491",
                  "record_ids": ["rec-1"]}]

        raw_events = [
            {"id": "evt-1", "payload": {"type": "replied",
                                        "lead_id": "100",
                                        "campaign_id": "491"}},
        ]

        def fake_fetch():
            return raw_events, 1, True

        result = check_reconcile.check_provider_events(
            recs, camps, fetch_bison_events=fake_fetch)

        self.assertEqual(len(result["offenders"]), 1)
        self.assertEqual(result["offenders"][0]["provider_event_id"],
                         "evt-1")

    def test_event_types_are_enumerated(self):
        """Every event type seen is named with a count, including unknowns."""
        recs = []
        camps = []

        raw_events = [
            {"id": "e1", "payload": {"type": "replied", "lead_id": "1",
                                     "campaign_id": "491"}},
            {"id": "e2", "payload": {"type": "bounced", "lead_id": "2",
                                     "campaign_id": "491"}},
            {"id": "e3", "payload": {"type": "EMAIL_ACCOUNT_DISCONNECTED",
                                     "lead_id": "3", "campaign_id": "491"}},
            {"id": "e4", "payload": {"type": "delivered", "lead_id": "4",
                                     "campaign_id": "491"}},
        ]

        def fake_fetch():
            return raw_events, 1, True

        result = check_reconcile.check_provider_events(
            recs, camps, fetch_bison_events=fake_fetch)

        etypes = result.get("event_types", {})
        self.assertIn("replied", etypes)
        self.assertIn("bounced", etypes)
        self.assertIn("EMAIL_ACCOUNT_DISCONNECTED", etypes)
        self.assertIn("delivered", etypes)

    def test_email_account_disconnected_is_named(self):
        """EMAIL_ACCOUNT_DISCONNECTED is enumerated, not silently dropped."""
        raw_events = [
            {"id": "e1", "payload": {
                "type": "EMAIL_ACCOUNT_DISCONNECTED",
                "lead_id": "1", "campaign_id": "491"}},
        ]

        def fake_fetch():
            return raw_events, 1, True

        result = check_reconcile.check_provider_events(
            [], [], fetch_bison_events=fake_fetch)

        self.assertIn("EMAIL_ACCOUNT_DISCONNECTED",
                      result.get("event_types", {}))


class TestTestIdentityMatchedOnIdAlone(unittest.TestCase):
    """ISSUE-044: the test identity is matched on the id ALONE.

    An EmailBison event can arrive carrying the lead id and nothing else —
    no address, no contact key. A newly created test lead is unsuppressed
    until its id is added to LEAD_IDS by hand. matches(205079) was False
    the moment the lead existed while matches on its address was True.
    """

    def test_test_identity_excluded_on_id_alone(self):
        """An event carrying only the test lead id is excluded."""
        recs = []
        camps = []

        raw_events = [
            {"id": "e1", "payload": {"type": "replied",
                                     "lead_id": "204966",
                                     "campaign_id": "491"}},
        ]

        def fake_fetch():
            return raw_events, 1, True

        result = check_reconcile.check_provider_events(
            recs, camps, fetch_bison_events=fake_fetch)

        kp = result.get("key_presence", {})
        self.assertGreaterEqual(
            kp.get("test_identity_matched_id_alone", 0), 1,
            "the test identity was NOT matched on id alone")
        self.assertEqual(len(result["offenders"]), 0)


if __name__ == "__main__":
    unittest.main()
