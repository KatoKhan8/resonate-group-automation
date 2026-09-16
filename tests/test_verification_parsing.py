"""TASK-196: Deliverable parser tests for the confirmed response shape.

The response shape was read live on 2026-09-07 and documented in
CONFIRMED_RESPONSE_SHAPE. The vocabulary is:
    deliverable | undeliverable | risky | unknown

Each word maps to an explicit classification. Unknown shapes fail closed.
"""
import unittest

from src.providers import deliverable


def real_answer(email_status, catch_all=False, processing="completed"):
    """The real envelope, as recorded from a live call on 2026-09-07."""
    return {
        "message": {"status": "success", "statusCode": 200,
                    "description": "Email task status fetched successfully"},
        "data": {"processing_status": processing, "task_id": "t-1",
                 "email": "someone@example.test", "email_status": email_status,
                 "is_catch_all": catch_all, "provider": "Private"},
    }


class TestConfirmedResponseShape(unittest.TestCase):
    """The response shape is documented in CONFIRMED_RESPONSE_SHAPE."""

    def test_the_shape_is_confirmed_in_code(self):
        """The gate opens because the shape was read and documented."""
        self.assertTrue(deliverable.result_shape_confirmed())

    def test_the_contract_is_verified_when_transport_is_complete(self):
        """Transport is complete (endpoints, auth documented), shape is confirmed."""
        self.assertTrue(deliverable.contract_verified())

    def test_require_contract_does_not_raise(self):
        """The parser is now allowed to run."""
        deliverable.require_contract()

    def test_the_documented_shape_names_the_verdict_field(self):
        self.assertEqual(deliverable.CONFIRMED_RESPONSE_SHAPE["verdict_field"],
                         "email_status")

    def test_the_documented_vocabulary_has_four_words(self):
        vocab = deliverable.CONFIRMED_RESPONSE_SHAPE["vocabulary"]
        self.assertEqual(set(vocab.keys()),
                         {"deliverable", "undeliverable", "risky", "unknown"})


class TestEachRealResponseShapeMapsExplicitly(unittest.TestCase):
    """Each word in the known vocabulary maps to an explicit classification."""

    def classify_real(self, email_status, **kw):
        payload = real_answer(email_status, **kw)
        body = deliverable.unwrap(payload)
        return deliverable.classify(body)

    def test_deliverable_maps_to_valid(self):
        self.assertEqual(self.classify_real("deliverable"), "valid")

    def test_undeliverable_maps_to_invalid(self):
        """Not valid. The whole-word matching prevents substring confusion."""
        self.assertEqual(self.classify_real("undeliverable"), "invalid")

    def test_risky_maps_to_unknown(self):
        """Fail-closed: risky holds the address, never sends."""
        self.assertEqual(self.classify_real("risky"), "unknown")

    def test_unknown_maps_to_unknown(self):
        self.assertEqual(self.classify_real("unknown"), "unknown")

    def test_catch_all_is_reported_regardless_of_verdict(self):
        self.assertEqual(self.classify_real("deliverable", catch_all=True),
                         "accept_all")

    def test_an_unrecognized_status_fails_closed(self):
        """A status the provider invents tomorrow is unknown, never valid."""
        self.assertEqual(self.classify_real("something_new"), "unknown")

    def test_an_empty_status_fails_closed(self):
        self.assertEqual(self.classify_real(""), "unknown")


class TestNegationHandling(unittest.TestCase):
    """Negated labels are never read as valid."""

    def classify(self, payload):
        body = deliverable.unwrap(payload) if "data" in payload else payload
        return deliverable.classify(body)

    def test_not_deliverable_is_not_valid(self):
        self.assertNotEqual(self.classify({"email_status": "not_deliverable"}),
                            "valid")

    def test_not_deliverable_is_unknown_not_invalid(self):
        """Unknown holds and asks. Invalid is a definite answer."""
        self.assertEqual(self.classify({"email_status": "not_deliverable"}),
                         "unknown")

    def test_non_deliverable_is_not_valid(self):
        self.assertNotEqual(self.classify({"email_status": "non_deliverable"}),
                            "valid")


class TestPendingDetection(unittest.TestCase):
    """The async flow uses processing_status, not status."""

    def test_a_running_task_is_pending(self):
        payload = real_answer("unknown", processing="pending")
        self.assertTrue(deliverable.pending(payload))

    def test_a_completed_task_is_not_pending(self):
        payload = real_answer("deliverable", processing="completed")
        self.assertFalse(deliverable.pending(payload))

    def test_processing_is_pending(self):
        payload = real_answer("unknown", processing="processing")
        self.assertTrue(deliverable.pending(payload))


class TestNormaliseWithRealEnvelope(unittest.TestCase):
    """The normaliser unwraps the data envelope and reads email_status."""

    def norm(self, email_status, **kw):
        payload = real_answer(email_status, **kw)
        return deliverable.normalise(payload, "someone@example.test")

    def test_the_provider_is_deliverable(self):
        entry = self.norm("deliverable")
        self.assertEqual(entry["provider"], "deliverable")

    def test_the_email_is_preserved(self):
        entry = self.norm("deliverable")
        self.assertEqual(entry["email"], "someone@example.test")

    def test_a_valid_verdict_has_deliverable_true(self):
        entry = self.norm("deliverable")
        self.assertEqual(entry["status"], "valid")

    def test_an_invalid_verdict_has_deliverable_false_or_status_invalid(self):
        entry = self.norm("undeliverable")
        self.assertEqual(entry["status"], "invalid")

    def test_catch_all_is_reported(self):
        entry = self.norm("deliverable", catch_all=True)
        self.assertEqual(entry["status"], "accept_all")
        self.assertTrue(entry["catch_all"])


class TestUnmappedFieldsTripwire(unittest.TestCase):
    """unmapped_fields reports anything the normaliser ignores."""

    def test_the_real_answer_has_no_unmapped_fields(self):
        payload = real_answer("deliverable")
        self.assertEqual(deliverable.unmapped_fields(payload), [])

    def test_a_new_field_is_reported(self):
        payload = real_answer("deliverable")
        payload["data"]["mystery_field"] = 42
        self.assertIn("mystery_field", deliverable.unmapped_fields(payload))


if __name__ == "__main__":
    unittest.main()
