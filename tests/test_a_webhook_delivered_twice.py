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


def _data(lead_id=4001, campaign_id=487, email="champ@example.test",
          occurred_at="2026-09-17T10:00:00Z"):
    """The REAL `data` shape, measured from 1,200 provider events.

    This file previously built `{"lead_id": ..., "campaign_id": ...,
    "email": ..., "occurred_at": ...}` - four flat keys, none of which exist
    in an EmailBison event. The tests passed against a payload the provider
    has never sent, and `normalise` rejected 100% of real events. The
    fixtures are corrected here rather than the assertions weakened.
    """
    return {
        "campaign": {"id": campaign_id, "name": "A Campaign"},
        "campaign_event": {"id": 9001, "type": "sent",
                           "created_at": occurred_at,
                           "created_at_local": occurred_at,
                           "local_timezone": "Europe/Zagreb"},
        "lead": {"id": lead_id, "email": email, "first_name": "Champ",
                 "company": "Example Co", "status": "in_sequence"},
        "scheduled_email": {"id": 7001, "lead_id": lead_id,
                            "sent_at": occurred_at,
                            "raw_message_id": "<msg-1@example.test>",
                            "status": "sent", "sequence_step_id": 4742},
        "sender_email": {"id": 2736, "email": "sender@example.test",
                         "daily_limit": 15},
    }


def _payload(event_type="EMAIL_SENT", workspace_id=10, data=None,
             event_id=None):
    """One synthetic payload in the shape the provider really sends.

    `event_id` now lands on an ENVELOPE around the payload rather than inside
    `event`, because `event.id` was measured ABSENT in 1,200 of 1,200 real
    events and the provider's identity lives on the `/api/events` row as
    `uuid`.
    """
    base = {
        "event": {
            "type": event_type,
            "name": event_type.replace("_", " ").title(),
            "instance_url": "https://dedi.emailbison.com",
            "workspace_id": workspace_id,
            "workspace_name": "Productive",
        },
        "data": data if data is not None else _data(),
    }
    if event_id is not None:
        return {"id": 1, "uuid": event_id, "created_at": "2026-09-17T10:00:00Z",
                "updated_at": "2026-09-17T10:00:00Z",
                "webhook_deliveries": [], "payload": base}
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
                        data=_data(lead_id=4001, campaign_id=487,
                       email="champ@example.test",
                       occurred_at="2026-09-17T10:00:00Z"))
        replied = _payload(event_type="CONTACT_REPLIED", event_id="evt-2",
                           data=_data(lead_id=4001, campaign_id=487,
                       email="champ@example.test",
                       occurred_at="2026-09-17T11:00:00Z"))
        e1 = bisonevents.normalise(sent)
        e2 = bisonevents.normalise(replied)
        self.assertNotEqual(bisonevents.event_key(e1),
                            bisonevents.event_key(e2))

    def test_same_lead_same_type_different_time_are_different_events(self):
        """A second send to the same lead is a different event, not a dup."""
        first = _payload(event_type="EMAIL_SENT", event_id="evt-10",
                         data=_data(lead_id=4001, campaign_id=487,
                       email="champ@example.test",
                       occurred_at="2026-09-17T10:00:00Z"))
        second = _payload(event_type="EMAIL_SENT", event_id="evt-11",
                          data=_data(lead_id=4001, campaign_id=487,
                       email="champ@example.test",
                       occurred_at="2026-09-17T14:00:00Z"))
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
            data=_data(lead_id=4001, campaign_id=487,
                       email="champ@example.test",
                       occurred_at="2026-09-17T10:30:00Z"))
        late_sent_payload = _payload(
            event_type="EMAIL_SENT", event_id="evt-s1",
            data=_data(lead_id=4001, campaign_id=487,
                       email="champ@example.test",
                       occurred_at="2026-09-17T10:00:00Z"))
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


class GLMsThreeDefeats(unittest.TestCase):
    """Found by GLM's adversarial review, run BEFORE this module had a caller.

    That timing is the point. All three are in the two expressions that decide
    whether an unauthenticated inbound payload reaches our state, and all
    three would have been found by a production 5xx instead.
    """

    def setUp(self):
        self._prev = os.environ.get("BISON_WORKSPACE_ID")
        os.environ["BISON_WORKSPACE_ID"] = "10"
        self.addCleanup(self._restore)

    def _restore(self):
        if self._prev is None:
            os.environ.pop("BISON_WORKSPACE_ID", None)
        else:
            os.environ["BISON_WORKSPACE_ID"] = self._prev

    def payload(self, workspace_id):
        return {"event": {"type": "EMAIL_SENT",
                          "workspace_id": workspace_id},
                "data": _data(lead_id=1, email="someone@example.test")}

    def test_a_non_numeric_workspace_is_refused_not_a_valueerror(self):
        """`int("bison")` raised a bare ValueError. A handler catches the two
        exceptions this module documents; an undocumented third becomes a 5xx,
        and this provider retries those five times over 24 hours."""
        with self.assertRaises(bisonevents.MalformedPayload):
            bisonevents.normalise(self.payload("bison"))

    def test_the_refusal_precedes_nothing_that_leaks_which_tenant_we_are(self):
        """A malformed id and a foreign-but-valid id must both be refusals,
        not a 500 and a refusal - two distinguishable answers are a probe
        signal."""
        with self.assertRaises(bisonevents.MalformedPayload):
            bisonevents.normalise(self.payload("bison"))
        with self.assertRaises(bisonevents.TenancyRefused):
            bisonevents.normalise(self.payload(11))

    def test_a_boolean_workspace_id_is_refused(self):
        """`bool` is a subclass of `int` and `int(True) == 1`, so a JSON
        `true` would PASS tenancy on a workspace pinned to 1. This estate is
        pinned to 10, which made it safe by accident."""
        with self.assertRaises(bisonevents.MalformedPayload):
            bisonevents.normalise(self.payload(True))

    def test_a_float_workspace_id_is_refused(self):
        with self.assertRaises(bisonevents.MalformedPayload):
            bisonevents.normalise(self.payload(1.0))

    def test_a_digit_string_workspace_id_is_still_accepted(self):
        """The refusals must not cost the ordinary case."""
        self.assertEqual(bisonevents.normalise(self.payload("10"))["kind"],
                         "sent")

    def test_an_event_key_without_occurred_at_refuses_classified(self):
        """It raised a bare KeyError. Classified now, so a handler can dead
        letter one event without taking the rest of a batch with it."""
        with self.assertRaises(bisonevents.MalformedPayload):
            bisonevents.event_key({"kind": "sent", "workspace_id": 10,
                                   "campaign_id": 487, "lead_id": 1})

    def test_a_null_lead_id_never_collapses_two_leads_onto_one_key(self):
        """THE WRONG FIX, asserted so nobody applies it. `.get(k, "")` would
        turn the loud failure above into a silent mass collision: a batch
        sharing one `occurred_at` with `lead_id: null` collapses N leads onto
        one key, first write wins, N-1 silently deduped. If the kind is
        `unsubscribed`, those people keep getting mail."""
        base = {"kind": "unsubscribed", "workspace_id": 10,
                "campaign_id": 487, "occurred_at": "2026-09-17T10:00:00Z"}
        with self.assertRaises(bisonevents.MalformedPayload):
            bisonevents.event_key(dict(base, lead_id=None))
        first = bisonevents.event_key(dict(base, lead_id=1))
        second = bisonevents.event_key(dict(base, lead_id=2))
        self.assertNotEqual(first, second)


class TheRealEventTypes(unittest.TestCase):
    """Pins the type names MEASURED on the provider, 2026-09-17.

    The module's assumed reply type was `CONTACT_REPLIED`. The provider sends
    `LEAD_REPLIED`. An unmapped type normalises to "unknown", so before this
    was measured a real reply produced an event that suppressed nothing -
    against the one invariant the system calls absolute.
    """

    def setUp(self):
        os.environ["BISON_WORKSPACE_ID"] = "10"

    def tearDown(self):
        os.environ.pop("BISON_WORKSPACE_ID", None)

    def test_lead_replied_is_a_reply(self):
        event = bisonevents.normalise(_payload(event_type="LEAD_REPLIED"))
        self.assertEqual(event["kind"], "replied")

    def test_every_observed_type_maps_to_a_known_kind(self):
        """All five seen in 1,200 real events. None may read "unknown"."""
        for event_type, expected in (("EMAIL_SENT", "sent"),
                                     ("LEAD_REPLIED", "replied"),
                                     ("EMAIL_BOUNCED", "bounced"),
                                     ("EMAIL_SEND_FAILED", "send_failed"),
                                     ("LEAD_FIRST_CONTACTED",
                                      "first_contacted")):
            with self.subTest(event_type=event_type):
                event = bisonevents.normalise(_payload(event_type=event_type))
                self.assertEqual(event["kind"], expected)
                self.assertNotEqual(event["kind"], "unknown")

    def test_an_envelope_and_a_bare_payload_both_normalise(self):
        """Which one a webhook POSTs is not documented, so both are accepted."""
        bare = _payload()
        enveloped = {"id": 5, "uuid": "u-5", "created_at": "2026-09-17T10:00:00Z",
                     "webhook_deliveries": [], "payload": bare}
        a = bisonevents.normalise(bare)
        b = bisonevents.normalise(enveloped)
        self.assertEqual(a["kind"], b["kind"])
        self.assertEqual(a["lead_id"], b["lead_id"])
        self.assertIsNone(a["provider_event_id"])
        self.assertEqual(b["provider_event_id"], "u-5",
                         "the envelope's uuid is the provider's event id; "
                         "event.id was absent in 1,200 of 1,200 real events")

    def test_the_timestamp_source_is_reported_not_flattened(self):
        event = bisonevents.normalise(_payload())
        self.assertEqual(event["occurred_at_source"], "campaign_event")

    def test_a_reply_without_a_scheduled_email_still_normalises(self):
        """`reply` rides on LEAD_REPLIED and EMAIL_BOUNCED only.

        A normaliser that required it would reject the other three types.
        """
        data = _data()
        data["reply"] = {"id": 77, "body_snippet": "not interested"}
        event = bisonevents.normalise(
            _payload(event_type="LEAD_REPLIED", data=data))
        self.assertEqual(event["kind"], "replied")
