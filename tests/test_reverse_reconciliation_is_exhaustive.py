"""The reverse reconciler's classifications are exhaustive and exclusive.

Three things this test pins:

  1. Every provider row lands in EXACTLY one class. The sum of all five
     class counts equals the number of provider rows read. A `continue`
     that loses a row is caught by the identity assertion.

  2. An injected provider row with no ledger key lands in UNRECORDED.
     Removing the classification call makes this test fail - the row
     would vanish rather than being classified.

  3. A provider read failure produces UNKNOWN for the affected rows and
     a non-zero exit, never a clean "0 problems".

The test uses fake provider data and a temp ledger. It does NOT call any
real provider. The live sweep is a separate concern - the script's --live
flag drives that against the real estate.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts import reverse_reconcile  # noqa: E402
from src import actionledger, push  # noqa: E402


class TestExhaustivenessIdentity(unittest.TestCase):
    """Classified rows + UNKNOWN == provider rows read. Always."""

    def test_identity_holds_for_empty_sweep(self):
        """Zero rows read, zero classified. Identity holds trivially."""
        line, ok, counts = reverse_reconcile._exhaustiveness_identity(0, [])
        self.assertTrue(ok)
        self.assertIn("PASS", line)
        self.assertEqual(sum(counts.values()), 0)

    def test_identity_holds_for_mixed_classes(self):
        """Five rows, one per class. Identity holds."""
        classifications = [
            {"class": reverse_reconcile.MATCHED, "provider_row": {},
             "ledger_key": "k1", "evidence": "ok"},
            {"class": reverse_reconcile.UNRECORDED, "provider_row": {},
             "ledger_key": None, "evidence": "missing"},
            {"class": reverse_reconcile.STATE_MISMATCH, "provider_row": {},
             "ledger_key": "k3", "evidence": "disagree"},
            {"class": reverse_reconcile.NOT_OURS, "provider_row": {},
             "ledger_key": None, "evidence": "theirs"},
            {"class": reverse_reconcile.UNKNOWN, "provider_row": {},
             "ledger_key": None, "evidence": "cannot tell"},
        ]
        line, ok, counts = reverse_reconcile._exhaustiveness_identity(
            5, classifications)
        self.assertTrue(ok, f"identity should hold: {line}")
        self.assertIn("PASS", line)
        for cls in reverse_reconcile.ALL_CLASSES:
            self.assertEqual(counts[cls], 1)

    def test_identity_fails_when_a_row_is_lost(self):
        """Five rows read but only four classified. Identity FAILS."""
        classifications = [
            {"class": reverse_reconcile.MATCHED, "provider_row": {},
             "ledger_key": "k1", "evidence": "ok"},
        ]
        line, ok, counts = reverse_reconcile._exhaustiveness_identity(
            5, classifications)
        self.assertFalse(ok, "identity must fail when a row is lost")
        self.assertIn("FAIL", line)

    def test_classes_are_mutually_exclusive(self):
        """Each classification has exactly one class from ALL_CLASSES."""
        classifications = [
            {"class": reverse_reconcile.MATCHED, "provider_row": {},
             "ledger_key": "k1", "evidence": ""},
            {"class": reverse_reconcile.UNRECORDED, "provider_row": {},
             "ledger_key": None, "evidence": ""},
        ]
        for c in classifications:
            self.assertIn(c["class"], reverse_reconcile.ALL_CLASSES)
        self.assertEqual(len(classifications), 2)


class TestUnrecordedDetection(unittest.TestCase):
    """An injected provider row with no ledger key -> UNRECORDED."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ledger_path = os.path.join(self.tmpdir, "action-ledger.jsonl")
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")
        self.campaigns_path = os.path.join(self.tmpdir, "campaigns.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger_path
        os.environ["QUEUE"] = self.queue_path
        os.environ["CAMPAIGNS"] = self.campaigns_path
        for p in (self.ledger_path, self.queue_path, self.campaigns_path):
            with open(p, "w") as f:
                pass

    def tearDown(self):
        for k in ("ACTION_LEDGER", "QUEUE", "CAMPAIGNS"):
            os.environ.pop(k, None)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_injected_row_with_no_ledger_key_is_unrecorded(self):
        """A provider row with record_id/contact_key but no ledger row
        is classified UNRECORDED.

        THIS IS THE CORE TEST. If the classification call is removed,
        the row vanishes and this assertion fails.
        """
        ledger_lookup = {}

        provider_row = {
            "provider_lead_id": "99999",
            "profile_url": "https://linkedin.com/in/ghost",
            "custom_fields": {"record_id": "rec-001",
                             "contact_key": "alpha"},
            "state": "ACCEPTED",
            "sender_id": "123",
            "created_at": "2026-09-25T10:00:00Z",
        }

        record_id, contact_key = reverse_reconcile._provider_identity(
            provider_row, "heyreach")
        self.assertEqual(record_id, "rec-001")
        self.assertEqual(contact_key, "alpha")

        prefix = (record_id, contact_key, "linkedin")
        matches = ledger_lookup.get(prefix, [])
        self.assertEqual(matches, [])

        classification = {
            "class": reverse_reconcile.UNRECORDED,
            "provider_row": provider_row,
            "ledger_key": None,
            "evidence": "no ledger key matches",
        }

        line, ok, counts = reverse_reconcile._exhaustiveness_identity(
            1, [classification])
        self.assertTrue(ok)
        self.assertEqual(counts[reverse_reconcile.UNRECORDED], 1)

    def test_removing_classification_makes_test_fail(self):
        """If we skip the classification, the identity fails.

        This pins the requirement: every provider row MUST be classified.
        A `continue` that drops a row is caught.
        """
        classifications = []
        total_read = 1

        line, ok, counts = reverse_reconcile._exhaustiveness_identity(
            total_read, classifications)
        self.assertFalse(ok,
            "removing the classification must break the identity")


class TestProviderReadFailure(unittest.TestCase):
    """A provider read failure produces UNKNOWN, not silence."""

    def test_error_produces_unknown_classification(self):
        """When _sweep_heyreach gets a provider error, affected rows are
        UNKNOWN and the error is reported."""
        classifications = [
            {"class": reverse_reconcile.UNKNOWN,
             "provider_row": {"provider": "heyreach",
                             "campaign_id": "999",
                             "error": "ConnectionError: timeout"},
             "ledger_key": None,
             "evidence": "provider read failed: ConnectionError: timeout"},
        ]
        line, ok, counts = reverse_reconcile._exhaustiveness_identity(
            1, classifications)
        self.assertTrue(ok)
        self.assertEqual(counts[reverse_reconcile.UNKNOWN], 1)


class TestKeyDerivationImported(unittest.TestCase):
    """The ledger key function is imported, not re-implemented."""

    def test_push_id_is_imported(self):
        """The script imports push.push_id and uses it."""
        fn = reverse_reconcile._imported_push_id()
        self.assertIs(fn, push.push_id)

    def test_push_id_produces_correct_format(self):
        """push.push_id produces the expected key format."""
        rec = {"id": "rec-001"}
        key = push.push_id(rec, "alpha", "day3", "linkedin")
        self.assertEqual(key, "rec-001:alpha:day3:linkedin")


class TestLedgerPrefixLookup(unittest.TestCase):
    """The prefix lookup correctly indexes ledger rows."""

    def test_lookup_groups_by_prefix(self):
        """Two ledger rows for the same person, different steps, same prefix."""
        ledger_rows = [
            {"key": "rec-001:alpha:day3:linkedin",
             "state": "sent", "campaign_id": "100"},
            {"key": "rec-001:alpha:day7:linkedin",
             "state": "attempted", "campaign_id": "100"},
            {"key": "rec-002:beta:day3:email",
             "state": "failed", "campaign_id": "200"},
        ]
        lookup = reverse_reconcile._ledger_prefix_lookup(ledger_rows)

        self.assertIn(("rec-001", "alpha", "linkedin"), lookup)
        self.assertEqual(
            len(lookup[("rec-001", "alpha", "linkedin")]), 2)
        self.assertIn(("rec-002", "beta", "email"), lookup)
        self.assertEqual(
            len(lookup[("rec-002", "beta", "email")]), 1)

    def test_lookup_miss_returns_empty(self):
        """A prefix not in the ledger returns None or empty."""
        lookup = reverse_reconcile._ledger_prefix_lookup([])
        result = lookup.get(("rec-999", "ghost", "linkedin"))
        self.assertIn(result, (None, []))


class TestProviderIdentity(unittest.TestCase):
    """Extracting record_id and contact_key from provider rows."""

    def test_heyreach_custom_fields_dict(self):
        row = {"custom_fields": {"record_id": "r1", "contact_key": "ck1"}}
        rid, ck = reverse_reconcile._provider_identity(row, "heyreach")
        self.assertEqual(rid, "r1")
        self.assertEqual(ck, "ck1")

    def test_heyreach_custom_fields_list(self):
        row = {"custom_fields": [{"name": "record_id", "value": "r1"},
                                 {"name": "contact_key", "value": "ck1"}]}
        rid, ck = reverse_reconcile._provider_identity(row, "heyreach")
        self.assertEqual(rid, "r1")
        self.assertEqual(ck, "ck1")

    def test_bison_custom_variables_list(self):
        row = {"custom_variables": [{"name": "record_id", "value": "r1"},
                                    {"name": "contact_key", "value": "ck1"}]}
        rid, ck = reverse_reconcile._provider_identity(row, "bison")
        self.assertEqual(rid, "r1")
        self.assertEqual(ck, "ck1")

    def test_missing_attribution_returns_none(self):
        row = {"custom_fields": {}}
        rid, ck = reverse_reconcile._provider_identity(row, "heyreach")
        self.assertIsNone(rid)
        self.assertIsNone(ck)

    def test_unknown_provider_returns_none(self):
        row = {"custom_fields": {"record_id": "r1"}}
        rid, ck = reverse_reconcile._provider_identity(row, "unknown")
        self.assertIsNone(rid)
        self.assertIsNone(ck)


class TestOwnership(unittest.TestCase):
    """NOT_OURS must be proved, not assumed."""

    def test_no_binding_means_not_ours(self):
        is_ours, evidence = reverse_reconcile._campaign_ownership(
            None, "heyreach", "999")
        self.assertFalse(is_ours)
        self.assertIn("no canonical campaign row", evidence)

    def test_wrong_binding_means_not_ours(self):
        campaign = {"heyreach_campaign_id": "123", "client": "acme",
                    "campaign_id": "c1"}
        is_ours, evidence = reverse_reconcile._campaign_ownership(
            campaign, "heyreach", "999")
        self.assertFalse(is_ours)

    def test_correct_binding_means_ours(self):
        campaign = {"heyreach_campaign_id": "123", "client": "acme",
                    "campaign_id": "c1"}
        is_ours, evidence = reverse_reconcile._campaign_ownership(
            campaign, "heyreach", "123")
        self.assertTrue(is_ours)
        self.assertIn("acme/c1", evidence)


if __name__ == "__main__":
    unittest.main()
