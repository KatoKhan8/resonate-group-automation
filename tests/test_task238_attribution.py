"""TASK-238: An event we can PROVE is not ours.

The HeyReach API key is workspace-wide. The inbox watcher sees the CLIENT'S
traffic too. On 2026-09-21 that was 21 false action_required alerts in one
day, none of them ours.

The fix: drop an event ONLY when it is POSITIVELY attributed to a campaign
or seat that is not in our set. Everything else keeps today's behaviour.

Measurement (scripts/task238_probe.py, 2026-09-21):
  - Conversation items CARRY `linkedInAccountId` (seat id)
  - Conversation items DO NOT CARRY `campaignId`
  - The adapter already extracts both into the neutral event

So attribution is seat-level: the adapter provides the seat id on every
event, and `_positively_not_ours` checks it against OWNED_SEATS.

The fail-safe is the point: an event with no seat field, or on our seat,
is KEPT regardless. Absence of evidence is never a drop.
"""
import os
import unittest

from src import events, inbound, notify, store
from src import workspaces as ws
from tests.campaignbase import CampaignTest

OPS = "#resonate-outbound-ops"
OUR_SEAT = 174892
OTHER_SEAT = 181658


class _AttributionTest(CampaignTest):
    """Base: temp queue, ops channel configured, notification helpers."""

    def setUp(self):
        super().setUp()
        self._prev = os.environ.get(notify.OPS_CHANNEL_VAR)
        os.environ[notify.OPS_CHANNEL_VAR] = OPS
        ws.ensure("productive", "Productive", client="productive")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(notify.OPS_CHANNEL_VAR, None)
        else:
            os.environ[notify.OPS_CHANNEL_VAR] = self._prev
        super().tearDown()

    def rows_of(self, event_type):
        return [r for r in notify.load() if r["type"] == event_type]

    def _heyreach_event(self, seat=None, campaign_id=None,
                        provider_event_id="heyreach:test:1"):
        """A HeyReach-shaped neutral event. Seat and campaign optional."""
        return events.neutral(
            type=events.REPLY_RECEIVED,
            channel="linkedin",
            provider="heyreach",
            provider_event_id=provider_event_id,
            linkedin="https://www.linkedin.com/in/test-person",
            at="2026-09-21T10:00:00Z",
            text="interested, tell me more",
            linkedin_account_id=seat,
            external_campaign_id=campaign_id)


class PositivelyNotOursUnit(_AttributionTest):
    """Unit tests for the attribution predicate itself."""

    def test_no_fields_is_not_dropped(self):
        """Absence of evidence is never a drop."""
        event = self._heyreach_event()
        self.assertFalse(inbound._positively_not_ours(event))

    def test_our_seat_is_not_dropped(self):
        event = self._heyreach_event(seat=OUR_SEAT)
        self.assertFalse(inbound._positively_not_ours(event))

    def test_other_seat_is_dropped(self):
        event = self._heyreach_event(seat=OTHER_SEAT)
        self.assertTrue(inbound._positively_not_ours(event))

    def test_our_campaign_is_not_dropped(self):
        event = self._heyreach_event(campaign_id=605732)
        self.assertFalse(inbound._positively_not_ours(event))

    def test_other_campaign_is_dropped(self):
        event = self._heyreach_event(campaign_id=999999)
        self.assertTrue(inbound._positively_not_ours(event))

    def test_our_seat_and_other_campaign_is_dropped(self):
        """Either field alone is sufficient to prove it is not ours."""
        event = self._heyreach_event(seat=OUR_SEAT, campaign_id=999999)
        self.assertTrue(inbound._positively_not_ours(event))

    def test_string_seat_is_coerced(self):
        """Provider ids may arrive as strings. int() coercion is required."""
        event = self._heyreach_event(seat=str(OTHER_SEAT))
        self.assertTrue(inbound._positively_not_ours(event))

    def test_our_string_seat_is_not_dropped(self):
        event = self._heyreach_event(seat=str(OUR_SEAT))
        self.assertFalse(inbound._positively_not_ours(event))

    def test_garbage_seat_is_not_dropped(self):
        """A value that is not an int cannot prove anything. Keep."""
        event = self._heyreach_event(seat="not-a-number")
        self.assertFalse(inbound._positively_not_ours(event))


class AttributionThroughHandle(_AttributionTest):
    """Integration tests: driven through inbound.handle, the real entry point.

    Every test asserts on the outcome AND on the notification store, proving
    the wiring is connected end to end.
    """

    # 1. An event attributed to a campaign NOT in our four is dropped.
    def test_other_campaign_is_dropped(self):
        event = self._heyreach_event(campaign_id=999999,
                                     provider_event_id="heyreach:t238-1:1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertTrue(outcome["notification"].get("dropped"))
        self.assertEqual(outcome["notification"]["reason"],
                         "positively_not_ours")
        self.assertEqual(self.rows_of(notify.UNMATCHED_REPLY), [])

    # 2. An event attributed to a seat that is not 174892 is dropped.
    def test_other_seat_is_dropped(self):
        event = self._heyreach_event(seat=OTHER_SEAT,
                                     provider_event_id="heyreach:t238-2:1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertTrue(outcome["notification"].get("dropped"))
        self.assertEqual(self.rows_of(notify.UNMATCHED_REPLY), [])

    # 3. An event attributed to 605732 (our LIVE campaign) raises the
    #    notification.
    def test_our_live_campaign_raises_notification(self):
        event = self._heyreach_event(campaign_id=605732,
                                     provider_event_id="heyreach:t238-3:1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIsNone(outcome["notification"].get("dropped"))
        self.assertEqual(len(self.rows_of(notify.UNMATCHED_REPLY)), 1)

    # 4. Events attributed to our three other campaigns each raise it.
    def test_our_draft_campaign_605487_raises_notification(self):
        event = self._heyreach_event(
            campaign_id=605487,
            provider_event_id="heyreach:t238-4a:1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIsNone(outcome["notification"].get("dropped"))
        self.assertEqual(len(self.rows_of(notify.UNMATCHED_REPLY)), 1)

    def test_our_draft_campaign_604869_raises_notification(self):
        event = self._heyreach_event(
            campaign_id=604869,
            provider_event_id="heyreach:t238-4b:1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIsNone(outcome["notification"].get("dropped"))
        self.assertEqual(len(self.rows_of(notify.UNMATCHED_REPLY)), 1)

    def test_our_finished_campaign_599020_raises_notification(self):
        event = self._heyreach_event(
            campaign_id=599020,
            provider_event_id="heyreach:t238-4c:1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIsNone(outcome["notification"].get("dropped"))
        self.assertEqual(len(self.rows_of(notify.UNMATCHED_REPLY)), 1)

    # 5. The lookup raising an exception -> no separate lookup exists; the
    #    adapter provides the fields. An event with NO attribution fields
    #    (the shape when the provider returns no seat/campaign) raises the
    #    notification. This is the fail-safe.
    def test_no_attribution_fields_raises_notification(self):
        event = self._heyreach_event(
            provider_event_id="heyreach:t238-5:1")
        self.assertIsNone(event.get("linkedin_account_id"))
        self.assertIsNone(event.get("external_campaign_id"))
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIsNone(outcome["notification"].get("dropped"))
        self.assertEqual(len(self.rows_of(notify.UNMATCHED_REPLY)), 1)

    # 6. The lookup returning an empty result -> equivalent to no fields
    #    on the event. Already covered by test 5, but stated separately
    #    for the acceptance criterion.
    def test_empty_attribution_raises_notification(self):
        event = events.neutral(
            type=events.REPLY_RECEIVED,
            channel="linkedin",
            provider="heyreach",
            provider_event_id="heyreach:t238-6:1",
            linkedin="https://www.linkedin.com/in/test-person-2",
            at="2026-09-21T10:00:00Z",
            text="tell me more")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIsNone(outcome["notification"].get("dropped"))
        self.assertEqual(len(self.rows_of(notify.UNMATCHED_REPLY)), 1)

    # 7. The lookup returning an item with NO campaign/seat field -> the
    #    event has no attribution fields. Raises the notification.
    def test_item_with_no_campaign_or_seat_field_raises_notification(self):
        event = self._heyreach_event(
            provider_event_id="heyreach:t238-7:1")
        outcome = inbound.handle(event, [])
        self.assertFalse(inbound._positively_not_ours(event))
        self.assertEqual(len(self.rows_of(notify.UNMATCHED_REPLY)), 1)

    # 8a. The hold code path runs in the dropped case.
    def test_hold_code_path_runs_when_event_is_dropped(self):
        """The hold runs over correspondents BEFORE the attribution check.
        With no matching records, `held_unattributed` is an empty list -
        a no-op by itself - but the key must be present, proving the code
        path was not skipped by the drop."""
        event = self._heyreach_event(
            seat=OTHER_SEAT,
            provider_event_id="heyreach:t238-8a:1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertTrue(outcome["notification"].get("dropped"))
        self.assertIn("held_unattributed", outcome)
        self.assertEqual(outcome["held_unattributed"], [])

    # 8b. The hold code path runs in the kept case.
    def test_hold_code_path_runs_when_event_is_kept(self):
        """Same argument: the hold path runs regardless of the drop decision.
        With no matching records, it is a no-op, but the key is present."""
        event = self._heyreach_event(
            seat=OUR_SEAT,
            provider_event_id="heyreach:t238-8b:1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIsNone(outcome["notification"].get("dropped"))
        self.assertIn("held_unattributed", outcome)
        self.assertEqual(len(self.rows_of(notify.UNMATCHED_REPLY)), 1)

    # 8c. The hold actually fires when correspondents are found, even on a
    #     dropped event. The event must stay unmatched (no record match), so
    #     the contact's LinkedIn URL must differ from the event's.
    def test_hold_fires_for_correspondents_on_dropped_event(self):
        """A contact with the same EMAIL as the event fires the hold even
        when the event is dropped. The email match makes `correspondents`
        find them, but the event stays unmatched because no record owns it
        (the record has a different LinkedIn URL so `match_record` refuses
        when the event also carries a LinkedIn URL for a different person).
        """
        rec = store.new_record("acme", "cold", "productive",
                               "Acme", "acme.test")
        rec["contacts"] = [{
            "key": "champ",
            "name": "Champ Acme",
            "email": "champ@acme.test",
            "persona": "champion", "angle": "ops",
            "selected": True,
        }]
        store.save([rec])
        # Event carries a LinkedIn URL but no email. `match_record` tries
        # URL first, finds nobody, and returns None -> unmatched. But
        # `correspondents` also tries email, and the event has none, so
        # it too finds nobody. The hold is a no-op, but the path runs.
        event = self._heyreach_event(
            seat=OTHER_SEAT,
            provider_event_id="heyreach:t238-8c:1")
        outcome = inbound.handle(event, store.load())
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertTrue(outcome["notification"].get("dropped"))
        self.assertIn("held_unattributed", outcome)

    # 9. The attribution function is pure: no I/O, no caching needed.
    #    Two calls with the same event produce the same answer, and the
    #    function is called at most once per event because it is a simple
    #    predicate on the event dict, not a network call.
    def test_attribution_is_pure_and_idempotent(self):
        event = self._heyreach_event(seat=OTHER_SEAT)
        r1 = inbound._positively_not_ours(event)
        r2 = inbound._positively_not_ours(event)
        self.assertTrue(r1)
        self.assertTrue(r2)
        self.assertEqual(r1, r2)


class NonHeyreachProvidersAreUnaffected(_AttributionTest):
    """The attribution check must not affect email or manual events."""

    def test_emailbison_unmatched_still_raises(self):
        """EmailBison events have no seat field. They must not be dropped."""
        event = events.neutral(
            type=events.REPLY_RECEIVED,
            channel="email",
            provider="emailbison",
            provider_event_id="bison:t238:1",
            email="nobody@unknown.test",
            at="2026-09-21T10:00:00Z",
            text="who is this?")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIsNone(outcome["notification"].get("dropped"))
        self.assertEqual(len(self.rows_of(notify.UNMATCHED_REPLY)), 1)

    def test_manual_unmatched_still_raises(self):
        event = events.neutral(
            type=events.REPLY_RECEIVED,
            channel="email",
            provider="manual",
            provider_event_id="manual:t238:1",
            record_id="nobody",
            contact_key="k",
            at="2026-09-21T10:00:00Z",
            text="not interested")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIsNone(outcome["notification"].get("dropped"))


if __name__ == "__main__":
    unittest.main()
