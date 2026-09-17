"""A Bison webhook delivered twice is one event, not two.

EmailBison retries every webhook five times over twenty-four hours and
`/api/events` replays the last ten days.  Duplicate delivery is documented
and normal, so the normaliser must produce one `event_key` for two
deliveries of the same occurrence and a different key for two genuinely
different events.

The falsifiable targets, all in this file:

- Two identical payloads produce one event_key.
- Two genuinely different events never share an event_key.
- An unknown event.type normalises to kind "unknown" and is never mapped
  to a known kind.
- A payload for another workspace_id raises.
- A payload missing `data` entirely raises rather than returning empty fields.
- occurred_at orders a late `sent` after an earlier `replied` correctly.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import bisonevents


def _payload(event_type="EMAIL_SENT", workspace_id=10, data=None,
             event_id=None):
    """One synthetic payload.  Every field the normaliser reads is named."""
    base = {
        "event": {
            "type": event_type,
            "name": event_type.replace("_", " ").title(),
            "instance_url": "https://dedi.emailbison.com",
            "workspace_id": workspace_id,
            "workspace_name": "Productive",
        },
        "data": data if data is not None else {
            "lead_id": 4001,
            "campaign_id": 487,
            "email": "champ@example.test",
            "occurred_at": "2026-09-17T10:00:00Z",
        },
    }
    if event_id is not None:
        base["event"]["id"] = event_id
    return base


class IdempotencyKey(unittest.TestCase):
    """Two deliveries of one event, one key.  Two different events, two keys."""

    def setUp(self):
        os.environ["BISON_WORKSPACE_ID"] = "10"

    def tearDown(self):
        os.environ.pop("BISON_WORKSPACE_ID", None)

    def test_two_identical_payloads_produce_one_key(self):
        payload = _payload(event_id="evt-abc-123")
        first = bisonevents.normalise(payload)
        second = bisonevents.normalise(payload)
        self.assertEqual(bisonevents.event_key(first),
                         bisonevents.event_key(second))

    def test_two_different_events_never_share_a_key(self):
        sent = _payload(event_type="EMAIL_SENT", event_id="evt-1",
                        data={"lead_id": 4001, "campaign_id": 487,
                              "email": "champ@example.test",
                              "occurred_at": "2026-09-17T10:00:00Z"})
        replied = _payload(event_type="CONTACT_REPLIED", event_id="evt-2",
                           data={"lead_id": 4001, "campaign_id": 487,
                                 "email": "champ@example.test",
                                 "occurred_at": "2026-09-17T11:00:00Z"})
        e1 = bisonevents.normalise(sent)
        e2 = bisonevents.normalise(replied)
        self.assertNotEqual(bisonevents.event_key(e1),
                            bisonevents.event_key(e2))

    def test_same_lead_same_type_different_time_are_different_events(self):
        """A second send to the same lead is a different event, not a dup."""
        first = _payload(event_type="EMAIL_SENT", event_id="evt-10",
                         data={"lead_id": 4001, "campaign_id": 487,
                               "email": "champ@example.test",
                               "occurred_at": "2026-09-17T10:00:00Z"})
        second = _payload(event_type="EMAIL_SENT", event_id="evt-11",
                          data={"lead_id": 4001, "campaign_id": 487,
                                "email": "champ@example.test",
                                "occurred_at": "2026-09-17T14:00:00Z"})
        e1 = bisonevents.normalise(first)
        e2 = bisonevents.normalise(second)
        self.assertNotEqual(bisonevents.event_key(e1),
                            bisonevents.event_key(e2))


class UnknownTypeIsNeverFoldedIntoAKnownKind(unittest.TestCase):
    """heyreach.lead_state does this: unseen values get LIFECYCLE_UNKNOWN.

    The same rule here: an event type this module has never seen maps to
    kind "unknown" and is never silently mapped to a neighbouring kind.
    """

    def setUp(self):
        os.environ["BISON_WORKSPACE_ID"] = "10"

    def tearDown(self):
        os.environ.pop("BISON_WORKSPACE_ID", None)

    def test_unknown_type_maps_to_unknown(self):
        payload = _payload(event_type="SOMETHING_NEW_FROM_VENDOR")
        event = bisonevents.normalise(payload)
        self.assertEqual(event["kind"], "unknown")

    def test_tag_attached_is_not_mapped_to_replied(self):
        """TAG_ATTACHED is documented but is not a reply or a send."""
        payload = _payload(event_type="TAG_ATTACHED")
        event = bisonevents.normalise(payload)
        self.assertEqual(event["kind"], "unknown")
        self.assertNotIn(event["kind"],
                         ("replied", "sent", "bounced", "opened"))


class Tenancy(unittest.TestCase):
    """A webhook for another workspace is REFUSED, not ignored.

    A webhook is an unauthenticated inbound from the internet until proven
    otherwise.  An event for another tenant reaching our state is the worst
    outcome in this file.
    """

    def test_payload_for_another_workspace_raises(self):
        os.environ["BISON_WORKSPACE_ID"] = "10"
        payload = _payload(workspace_id=999)
        with self.assertRaises(bisonevents.TenancyRefused):
            bisonevents.normalise(payload)

    def test_payload_for_our_workspace_is_accepted(self):
        os.environ["BISON_WORKSPACE_ID"] = "10"
        payload = _payload(workspace_id=10)
        event = bisonevents.normalise(payload)
        self.assertEqual(event["workspace_id"], 10)

    def test_unpinned_workspace_refuses_everything(self):
        """No pin means no basis for acceptance.  Honest rather than safe."""
        os.environ.pop("BISON_WORKSPACE_ID", None)
        payload = _payload(workspace_id=10)
        with self.assertRaises(bisonevents.TenancyRefused):
            bisonevents.normalise(payload)

    def tearDown(self):
        os.environ.pop("BISON_WORKSPACE_ID", None)


class MissingDataRaises(unittest.TestCase):
    """A payload missing `data` raises rather than returning empty fields.

    An empty-field normalised event would flow downstream as a kind with no
    lead, no campaign and no timestamp - indistinguishable from a real event
    that happened to have nothing to say.  That is worse than a crash.
    """

    def setUp(self):
        os.environ["BISON_WORKSPACE_ID"] = "10"

    def tearDown(self):
        os.environ.pop("BISON_WORKSPACE_ID", None)

    def test_missing_data_raises(self):
        payload = {"event": {"type": "EMAIL_SENT", "workspace_id": 10}}
        with self.assertRaises(bisonevents.MalformedPayload):
            bisonevents.normalise(payload)

    def test_missing_event_type_raises(self):
        payload = {"event": {"workspace_id": 10},
                   "data": {"lead_id": 1, "campaign_id": 1,
                            "email": "champ@example.test",
                            "occurred_at": "2026-09-17T10:00:00Z"}}
        with self.assertRaises(bisonevents.MalformedPayload):
            bisonevents.normalise(payload)

    def test_missing_workspace_id_raises(self):
        payload = {"event": {"type": "EMAIL_SENT"},
                   "data": {"lead_id": 1, "campaign_id": 1,
                            "email": "champ@example.test",
                            "occurred_at": "2026-09-17T10:00:00Z"}}
        with self.assertRaises(bisonevents.MalformedPayload):
            bisonevents.normalise(payload)


class OutOfOrder(unittest.TestCase):
    """A `sent` arriving AFTER a `replied` does not undo the reply.

    Events arrive late and out of sequence.  The normaliser must carry
    occurred_at so a consumer can order them.  This test does NOT implement
    the suppression itself - it proves the normalised events carry enough
    to order them correctly.
    """

    def setUp(self):
        os.environ["BISON_WORKSPACE_ID"] = "10"

    def tearDown(self):
        os.environ.pop("BISON_WORKSPACE_ID", None)

    def test_late_sent_carries_an_earlier_timestamp_than_the_reply(self):
        """The reply happened first; the send was just delivered late."""
        reply_payload = _payload(
            event_type="CONTACT_REPLIED", event_id="evt-r1",
            data={"lead_id": 4001, "campaign_id": 487,
                  "email": "champ@example.test",
                  "occurred_at": "2026-09-17T10:30:00Z"})
        late_sent_payload = _payload(
            event_type="EMAIL_SENT", event_id="evt-s1",
            data={"lead_id": 4001, "campaign_id": 487,
                  "email": "champ@example.test",
                  "occurred_at": "2026-09-17T10:00:00Z"})
        reply = bisonevents.normalise(reply_payload)
        sent = bisonevents.normalise(late_sent_payload)
        self.assertLess(sent["occurred_at"], reply["occurred_at"])
        self.assertEqual(reply["kind"], "replied")
        self.assertEqual(sent["kind"], "sent")

    def test_occurred_at_is_always_present(self):
        payload = _payload()
        event = bisonevents.normalise(payload)
        self.assertIn("occurred_at", event)
        self.assertIsNotNone(event["occurred_at"])


class NormalisedShape(unittest.TestCase):
    """The trimmed dict carries every field a consumer needs."""

    def setUp(self):
        os.environ["BISON_WORKSPACE_ID"] = "10"

    def tearDown(self):
        os.environ.pop("BISON_WORKSPACE_ID", None)

    def test_required_fields_are_present(self):
        payload = _payload(event_id="evt-xyz")
        event = bisonevents.normalise(payload)
        for field in ("provider_event_type", "provider_event_id",
                      "workspace_id", "campaign_id", "lead_id",
                      "email", "occurred_at", "kind", "raw_keys"):
            self.assertIn(field, event, f"missing field: {field}")

    def test_kind_is_from_allowlist(self):
        for event_type, expected_kind in (
            ("EMAIL_SENT", "sent"),
            ("EMAIL_OPENED", "opened"),
            ("CONTACT_REPLIED", "replied"),
            ("EMAIL_BOUNCED", "bounced"),
            ("CONTACT_UNSUBSCRIBED", "unsubscribed"),
            ("CONTACT_INTERESTED", "interested"),
        ):
            payload = _payload(event_type=event_type)
            event = bisonevents.normalise(payload)
            self.assertEqual(event["kind"], expected_kind,
                             f"{event_type} -> {event['kind']}, "
                             f"expected {expected_kind}")

    def test_raw_keys_carries_the_provider_field_names(self):
        payload = _payload()
        event = bisonevents.normalise(payload)
        self.assertIsInstance(event["raw_keys"], (list, tuple))
        self.assertTrue(len(event["raw_keys"]) > 0)


if __name__ == "__main__":
    unittest.main()
