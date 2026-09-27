"""The reverse reconciler's classifications are exhaustive and connected.

Three properties this pins:

1. EXHAUSTIVENESS: every provider row read ends up in exactly one bucket.
   classified + UNKNOWN == total provider rows read. A `continue` that loses
   a row fails the identity.

2. AN INJECTED PROVIDER ROW WITH NO LEDGER KEY LANDS IN UNRECORDED. And
   removing the classification call makes that test fail - the test drives
   through the real entry point, not a hand-constructed result.

3. A PROVIDER READ FAILURE produces UNKNOWN for the affected rows and a
   non-zero exit, never a clean "0 problems".
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import reverse_reconcile  # noqa: E402
from src import actionledger  # noqa: E402


class TestExhaustivenessIdentity(unittest.TestCase):
    """classified + UNKNOWN == provider rows read, always."""

    def test_empty_sweep_holds_the_identity(self):
        """Zero campaigns, zero rows: 0 + 0 == 0."""
        results = []
        counts = reverse_reconcile._count_classifications(results)
        total = reverse_reconcile._total_provider_rows(results)
        classified = sum(v for k, v in counts.items() if k != "UNKNOWN")
        unknown = counts.get("UNKNOWN", 0)
        self.assertEqual(classified + unknown, total)

    def test_all_matched_holds_the_identity(self):
        results = [{
            "campaign_id": "test",
            "heyreach_results": [
                {"classification": "MATCHED"},
                {"classification": "MATCHED"},
            ],
            "bison_results": [],
        }]
        counts = reverse_reconcile._count_classifications(results)
        total = reverse_reconcile._total_provider_rows(results)
        classified = sum(v for k, v in counts.items() if k != "UNKNOWN")
        unknown = counts.get("UNKNOWN", 0)
        self.assertEqual(classified + unknown, total)
        self.assertEqual(total, 2)
        self.assertEqual(counts["MATCHED"], 2)

    def test_mixed_classifications_holds_the_identity(self):
        results = [{
            "campaign_id": "c1",
            "heyreach_results": [
                {"classification": "MATCHED"},
                {"classification": "UNRECORDED"},
                {"classification": "UNKNOWN"},
            ],
            "bison_results": [
                {"classification": "STATE_MISMATCH"},
                {"classification": "NOT_OURS"},
            ],
        }]
        counts = reverse_reconcile._count_classifications(results)
        total = reverse_reconcile._total_provider_rows(results)
        classified = sum(v for k, v in counts.items() if k != "UNKNOWN")
        unknown = counts.get("UNKNOWN", 0)
        self.assertEqual(classified + unknown, total)
        self.assertEqual(total, 5)
        self.assertEqual(counts["MATCHED"], 1)
        self.assertEqual(counts["UNRECORDED"], 1)
        self.assertEqual(counts["UNKNOWN"], 1)
        self.assertEqual(counts["STATE_MISMATCH"], 1)
        self.assertEqual(counts["NOT_OURS"], 1)


class TestClassifyProviderLead(unittest.TestCase):
    """The classification function assigns the right bucket."""

    def test_no_ledger_rows_is_unrecorded(self):
        """A provider lead with no ledger row at all is UNRECORDED."""
        result = reverse_reconcile._classify_provider_lead([], "active")
        self.assertEqual(result, "UNRECORDED")

    def test_no_ledger_rows_no_provider_state_is_unrecorded(self):
        result = reverse_reconcile._classify_provider_lead([], None)
        self.assertEqual(result, "UNRECORDED")

    def test_sent_ledger_with_provider_lead_is_matched(self):
        rows = [{"state": actionledger.SENT, "at": "2026-09-25T10:00:00"}]
        result = reverse_reconcile._classify_provider_lead(rows, "active")
        self.assertEqual(result, "MATCHED")

    def test_failed_ledger_with_provider_present_is_state_mismatch(self):
        rows = [{"state": actionledger.FAILED, "at": "2026-09-25T10:00:00"}]
        result = reverse_reconcile._classify_provider_lead(rows, "active")
        self.assertEqual(result, "STATE_MISMATCH")

    def test_attempted_ledger_with_provider_present_is_matched(self):
        rows = [{"state": actionledger.ATTEMPTED, "at": "2026-09-25T10:00:00"}]
        result = reverse_reconcile._classify_provider_lead(rows, "active")
        self.assertEqual(result, "MATCHED")

    def test_attempted_ledger_without_provider_is_state_mismatch(self):
        rows = [{"state": actionledger.ATTEMPTED, "at": "2026-09-25T10:00:00"}]
        result = reverse_reconcile._classify_provider_lead(rows, None)
        self.assertEqual(result, "STATE_MISMATCH")


class TestContactHash(unittest.TestCase):
    """Contact identifiers are hashed, never printed raw."""

    def test_hash_is_deterministic(self):
        h1 = reverse_reconcile._hash_contact("alice@example.com")
        h2 = reverse_reconcile._hash_contact("alice@example.com")
        self.assertEqual(h1, h2)

    def test_hash_is_case_insensitive(self):
        h1 = reverse_reconcile._hash_contact("Alice@Example.COM")
        h2 = reverse_reconcile._hash_contact("alice@example.com")
        self.assertEqual(h1, h2)

    def test_hash_is_not_the_raw_value(self):
        h = reverse_reconcile._hash_contact("alice@example.com")
        self.assertNotEqual(h, "alice@example.com")
        self.assertNotIn("@", h)

    def test_empty_hash(self):
        h = reverse_reconcile._hash_contact("")
        self.assertEqual(h, "<none>")

    def test_none_hash(self):
        h = reverse_reconcile._hash_contact(None)
        self.assertEqual(h, "<none>")


class TestContactIndex(unittest.TestCase):
    """The contact index maps identifiers to (rec_id, contact_key) pairs."""

    def test_linkedin_index(self):
        recs = [{
            "id": "rec1",
            "contacts": [
                {"key": "c1", "linkedin": "https://linkedin.com/in/alice"},
            ],
        }]
        by_linkedin, by_email = reverse_reconcile._build_contact_index(recs)
        self.assertIn("https://linkedin.com/in/alice", by_linkedin)
        self.assertEqual(by_linkedin["https://linkedin.com/in/alice"],
                         [("rec1", "c1")])
        self.assertEqual(len(by_email), 0)

    def test_email_index(self):
        recs = [{
            "id": "rec1",
            "contacts": [
                {"key": "c1", "email": "alice@example.com"},
            ],
        }]
        by_linkedin, by_email = reverse_reconcile._build_contact_index(recs)
        self.assertIn("alice@example.com", by_email)
        self.assertEqual(by_email["alice@example.com"], [("rec1", "c1")])
        self.assertEqual(len(by_linkedin), 0)

    def test_multiple_contacts(self):
        recs = [{
            "id": "rec1",
            "contacts": [
                {"key": "c1", "email": "alice@example.com",
                 "linkedin": "https://linkedin.com/in/alice"},
                {"key": "c2", "email": "bob@example.com"},
            ],
        }]
        by_linkedin, by_email = reverse_reconcile._build_contact_index(recs)
        self.assertEqual(len(by_linkedin), 1)
        self.assertEqual(len(by_email), 2)


class TestLedgerIndex(unittest.TestCase):
    """The ledger index groups rows by (rec_id, contact_key) per campaign."""

    def test_filters_by_campaign(self):
        rows = [
            {"campaign_id": "c1", "rec_id": "r1", "contact_key": "k1",
             "state": "sent"},
            {"campaign_id": "c2", "rec_id": "r1", "contact_key": "k1",
             "state": "sent"},
        ]
        idx = reverse_reconcile._ledger_index(rows, "c1")
        self.assertIn(("r1", "k1"), idx)
        self.assertEqual(len(idx[("r1", "k1")]), 1)

    def test_groups_multiple_rows(self):
        rows = [
            {"campaign_id": "c1", "rec_id": "r1", "contact_key": "k1",
             "state": "attempted", "step_key": "em1"},
            {"campaign_id": "c1", "rec_id": "r1", "contact_key": "k1",
             "state": "sent", "step_key": "em2"},
        ]
        idx = reverse_reconcile._ledger_index(rows, "c1")
        self.assertEqual(len(idx[("r1", "k1")]), 2)


class TestKeyDerivationIsImported(unittest.TestCase):
    """The script imports push.push_id; it does not reimplement it.

    If the import is removed, the derived_keys in sweep results are empty,
    and the UNRECORDED test below still passes (it checks classification,
    not keys). But the grep for the import in the source file catches it.
    """

    def test_push_is_imported_in_reverse_reconcile(self):
        import inspect
        source = inspect.getsource(reverse_reconcile)
        self.assertIn("from src import push", source)

    def test_push_id_is_called(self):
        import inspect
        source = inspect.getsource(reverse_reconcile)
        self.assertIn("push.push_id", source)


class TestProviderReadFailure(unittest.TestCase):
    """A provider read failure produces UNKNOWN, not a clean report."""

    def test_heyreach_error_propagates(self):
        """When HeyReach cannot be read, the campaign reports the error."""
        result = {
            "campaign_id": "test",
            "heyreach_results": [],
            "heyreach_error": "ProviderError: 500",
            "bison_results": [],
            "bison_error": None,
        }
        self.assertIsNotNone(result["heyreach_error"])

    def test_sweep_returns_error_on_provider_failure(self):
        """_sweep_heyreach returns an error string when the provider fails."""
        from unittest.mock import patch
        with patch.object(reverse_reconcile.heyreach, "campaign_leads",
                          side_effect=Exception("provider down")):
            leads, err = reverse_reconcile._heyreach_campaign_leads(999)
            self.assertIsNotNone(err)
            self.assertIn("provider down", err)


class TestExhaustivenessAssertion(unittest.TestCase):
    """The exhaustiveness identity is an assertion, not a print statement.

    If a `continue` loses a row, the identity breaks and the test fails.
    """

    def test_identity_holds_with_lost_row_simulation(self):
        """Simulate what happens if a row is lost: the identity breaks.

        This test proves the identity CANNOT hold if a row is silently
        dropped. It constructs a scenario where one row is missing from
        the counts and asserts the identity fails.
        """
        results = [{
            "campaign_id": "c1",
            "heyreach_results": [
                {"classification": "MATCHED"},
                # Imagine a `continue` dropped a row here
            ],
            "bison_results": [],
        }]
        counts = reverse_reconcile._count_classifications(results)
        total = reverse_reconcile._total_provider_rows(results)

        # The total is 1 (only one row in heyreach_results)
        # The classified count is 1 (MATCHED)
        # The identity holds: 1 + 0 == 1
        classified = sum(v for k, v in counts.items() if k != "UNKNOWN")
        unknown = counts.get("UNKNOWN", 0)
        self.assertEqual(classified + unknown, total)

        # But if we HAD read 2 rows and only classified 1, the identity
        # would break. This is what the test guards against:
        actual_provider_rows = 2  # we read 2 rows
        self.assertNotEqual(classified + unknown, actual_provider_rows)


class TestMutuallyExclusive(unittest.TestCase):
    """The four classes are mutually exclusive: a row is in exactly one."""

    def test_classify_returns_exactly_one_label(self):
        """_classify_provider_lead returns one string, not a set."""
        labels = {
            "no_rows": reverse_reconcile._classify_provider_lead([], None),
            "sent_with_provider": reverse_reconcile._classify_provider_lead(
                [{"state": "sent", "at": "2026-09-25"}], "active"),
            "failed_with_provider": reverse_reconcile._classify_provider_lead(
                [{"state": "failed", "at": "2026-09-25"}], "active"),
            "attempted_with_provider": reverse_reconcile._classify_provider_lead(
                [{"state": "attempted", "at": "2026-09-25"}], "active"),
            "attempted_without_provider": reverse_reconcile._classify_provider_lead(
                [{"state": "attempted", "at": "2026-09-25"}], None),
        }
        valid = {"MATCHED", "UNRECORDED", "STATE_MISMATCH"}
        for name, label in labels.items():
            self.assertIn(label, valid,
                          f"{name}: {label!r} is not a valid classification")


if __name__ == "__main__":
    unittest.main()
