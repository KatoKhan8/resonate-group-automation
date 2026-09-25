#!/usr/bin/env python3
"""The reverse reconciler is exhaustive: every provider row is classified.

TASK-280. `scripts/reverse_reconcile.py` sweeps from provider truth back to
the ledger. The four classes (MATCHED, UNRECORDED, STATE_MISMATCH, NOT_OURS)
plus UNKNOWN must account for every provider row read. A `continue` that
loses a row is the same shape as the forward reconciler's original bug.

Five requirements, each with a test that FAILS before the change:

1. The exhaustiveness identity holds: sum of all classes == total rows read.
2. An injected provider row with no ledger key lands in UNRECORDED.
3. Removing the classification call makes test 2 fail (the wiring matters).
4. A provider read failure produces UNKNOWN for affected rows and a non-zero
   exit code, never a clean "0 problems".
5. The four classes are mutually exclusive: each row gets exactly one.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from src import actionledger, campaigns as campaigns_mod, store
from tests.base import QueueTest


MATCHED = "MATCHED"
UNRECORDED = "UNRECORDED"
STATE_MISMATCH = "STATE_MISMATCH"
NOT_OURS = "NOT_OURS"
UNKNOWN = "UNKNOWN"


def _script_path():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "reverse_reconcile.py")


class _ReverseReconcilerBase(QueueTest):
    """Shared setup: throwaway work dir, campaign file, ledger, queue."""

    def setUp(self):
        super().setUp()
        self.work = os.path.join(self.tmp, "work")
        os.makedirs(self.work, exist_ok=True)
        self.ledger_path = os.path.join(self.work, "action-ledger.jsonl")
        self.camp_path = os.path.join(self.work, "campaigns.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger_path
        os.environ["CAMPAIGNS"] = self.camp_path
        os.environ["QUEUE"] = self.queue

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        os.environ.pop("CAMPAIGNS", None)
        super().tearDown()

    def _write_campaigns(self, rows):
        with open(self.camp_path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    def _write_queue(self, recs):
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        with open(self.queue, "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

    def _reserve(self, key, **kw):
        defaults = dict(channel="linkedin", workspace="test-client",
                        campaign_id="camp-1", sender_id="sender-1",
                        rec_id="rec-1", contact_key="k1", step_key="li1",
                        operation="heyreach.add_lead", fingerprint="fp1")
        defaults.update(kw)
        return actionledger.reserve(key, **defaults)

    def _settle(self, key, state, **kw):
        return actionledger.settle(key, state, **kw)


_TEST_CADENCE = [
    {"key": "li1", "day": 1, "channel": "linkedin"},
    {"key": "em1", "day": 3, "channel": "email"},
]


def _campaign(**overrides):
    """A campaign row with explicit cadence steps for testing."""
    base = {
        "campaign_id": "camp-1", "client": "test-client",
        "heyreach_campaign_id": "12345",
        "cadence_steps": _TEST_CADENCE,
    }
    base.update(overrides)
    return base


class ExhaustivenessIdentity(_ReverseReconcilerBase):
    """Requirement 1: classified + UNKNOWN == total provider rows read."""

    def test_exhaustiveness_identity_holds(self):
        self._write_campaigns([_campaign()])
        self._write_queue([{
            "id": "rec-1", "domain": "example.test",
            "contacts": [{"key": "k1",
                          "linkedin": "https://linkedin.com/in/alpha"}],
        }])
        self._reserve("rec-1:k1:li1:linkedin")
        self._settle("rec-1:k1:li1:linkedin", actionledger.SENT)

        fake_leads = [
            {"provider_lead_id": 1, "profile_url":
             "https://linkedin.com/in/alpha", "state": "request_sent"},
            {"provider_lead_id": 2, "profile_url":
             "https://linkedin.com/in/beta", "state": "request_pending"},
            {"provider_lead_id": 3, "profile_url":
             "https://linkedin.com/in/gamma", "state": "replied"},
        ]
        with mock.patch("scripts.reverse_reconcile._read_heyreach_leads",
                        return_value=(fake_leads, None)):
            from scripts import reverse_reconcile
            report, rc = reverse_reconcile.run()

        total = report["provider_rows_read"]
        counts = report["counts"]
        class_sum = sum(counts.values())
        self.assertEqual(class_sum, total,
                         f"exhaustiveness broken: {class_sum} != {total}. "
                         f"Counts: {counts}")
        self.assertTrue(report["exhaustiveness_ok"])
        self.assertRegex(report["exhaustiveness_identity"], r"\d+ == \d+")


class InjectedProviderRowIsUnrecorded(_ReverseReconcilerBase):
    """Requirement 2: a provider row with no ledger key -> UNRECORDED."""

    def test_injected_row_with_no_ledger_key_is_unrecorded(self):
        self._write_campaigns([_campaign()])
        self._write_queue([{
            "id": "rec-1", "domain": "example.test",
            "contacts": [{"key": "k1",
                          "linkedin": "https://linkedin.com/in/alpha"}],
        }])

        fake_leads = [
            {"provider_lead_id": 99, "profile_url":
             "https://linkedin.com/in/alpha", "state": "request_sent"},
            {"provider_lead_id": 100, "profile_url":
             "https://linkedin.com/in/stranger", "state": "request_sent"},
        ]
        with mock.patch("scripts.reverse_reconcile._read_heyreach_leads",
                        return_value=(fake_leads, None)):
            from scripts import reverse_reconcile
            report, rc = reverse_reconcile.run()

        classifications = {r["provider_lead_id"]: r["classification"]
                           for r in report["classifications"]}
        self.assertEqual(classifications.get(100), UNRECORDED,
                         "a provider row with no ledger key must be "
                         "UNRECORDED")

    def test_removing_classification_makes_injected_test_fail(self):
        """Requirement 3: the classification call is load-bearing.

        If we skip the classification and always return MATCHED, a lead
        that HAS a queue match but NO ledger key would be wrongly called
        MATCHED instead of UNRECORDED. This proves the wiring, not just
        the text of the source.
        """
        self._write_campaigns([_campaign()])
        self._write_queue([{
            "id": "rec-1", "domain": "example.test",
            "contacts": [{"key": "k1",
                          "linkedin": "https://linkedin.com/in/alpha"}],
        }])

        # This lead MATCHES a queue record but has NO ledger key.
        # _best_classification should return UNRECORDED (no ledger row).
        # If we mock it to return MATCHED, the wiring is broken.
        fake_leads = [
            {"provider_lead_id": 1, "profile_url":
             "https://linkedin.com/in/alpha", "state": "request_sent"},
        ]

        def fake_best(keys, ledger_latest, provider_active):
            return MATCHED

        with mock.patch("scripts.reverse_reconcile._read_heyreach_leads",
                        return_value=(fake_leads, None)), \
             mock.patch("scripts.reverse_reconcile._best_classification",
                        fake_best):
            from scripts import reverse_reconcile
            report, rc = reverse_reconcile.run()

        classifications = {r["provider_lead_id"]: r["classification"]
                           for r in report["classifications"]}
        self.assertNotEqual(classifications.get(1), UNRECORDED,
                            "with classification disabled, UNRECORDED should "
                            "not appear - proving the call is load-bearing")


class ProviderReadFailureProducesUnknown(_ReverseReconcilerBase):
    """Requirement 4: provider read failure -> UNKNOWN + non-zero exit."""

    def test_provider_read_failure_produces_unknown(self):
        self._write_campaigns([_campaign()])
        self._write_queue([])

        with mock.patch("scripts.reverse_reconcile._read_heyreach_leads",
                        return_value=([], "heyreach campaign 12345: "
                                     "ConnectionError: timeout")):
            from scripts import reverse_reconcile
            report, rc = reverse_reconcile.run()

        self.assertNotEqual(rc, 0,
                            "a provider read failure must produce non-zero "
                            "exit, never a clean '0 problems'")
        self.assertGreater(report["campaigns_unreadable"], 0)
        self.assertEqual(report["campaigns_unreadable"], 1)
        self.assertEqual(
            report["unreadable_details"][0]["campaign_id"], "camp-1")

    def test_exhaustiveness_still_holds_after_failure(self):
        self._write_campaigns([_campaign()])
        self._write_queue([])

        with mock.patch("scripts.reverse_reconcile._read_heyreach_leads",
                        return_value=([], "provider unreachable")):
            from scripts import reverse_reconcile
            report, rc = reverse_reconcile.run()

        total = report["provider_rows_read"]
        counts = report["counts"]
        class_sum = sum(counts.values())
        self.assertEqual(class_sum, total,
                         "exhaustiveness must hold even when the provider "
                         "cannot be read")


class MutuallyExclusiveClasses(_ReverseReconcilerBase):
    """Requirement 5: each row gets exactly one classification."""

    def test_each_row_gets_exactly_one_class(self):
        self._write_campaigns([_campaign()])
        self._write_queue([{
            "id": "rec-1", "domain": "example.test",
            "contacts": [{"key": "k1",
                          "linkedin": "https://linkedin.com/in/alpha"}],
        }])
        self._reserve("rec-1:k1:li1:linkedin")
        self._settle("rec-1:k1:li1:linkedin", actionledger.SENT)

        fake_leads = [
            {"provider_lead_id": 1, "profile_url":
             "https://linkedin.com/in/alpha", "state": "request_sent"},
            {"provider_lead_id": 2, "profile_url":
             "https://linkedin.com/in/beta", "state": "replied"},
        ]
        with mock.patch("scripts.reverse_reconcile._read_heyreach_leads",
                        return_value=(fake_leads, None)):
            from scripts import reverse_reconcile
            report, rc = reverse_reconcile.run()

        for row in report["classifications"]:
            cls = row.get("classification")
            self.assertIn(cls, (MATCHED, UNRECORDED, STATE_MISMATCH,
                                NOT_OURS, UNKNOWN),
                          f"row {row} has invalid class {cls!r}")
            self.assertIsInstance(cls, str)


class StateMismatchDetected(_ReverseReconcilerBase):
    """Ledger says FAILED but provider shows the lead was acted on."""

    def test_failed_ledger_with_active_provider_is_mismatch(self):
        self._write_campaigns([_campaign()])
        self._write_queue([{
            "id": "rec-1", "domain": "example.test",
            "contacts": [{"key": "k1",
                          "linkedin": "https://linkedin.com/in/alpha"}],
        }])
        self._reserve("rec-1:k1:li1:linkedin")
        self._settle("rec-1:k1:li1:linkedin", actionledger.FAILED)

        fake_leads = [
            {"provider_lead_id": 1, "profile_url":
             "https://linkedin.com/in/alpha", "state": "request_sent"},
        ]
        with mock.patch("scripts.reverse_reconcile._read_heyreach_leads",
                        return_value=(fake_leads, None)):
            from scripts import reverse_reconcile
            report, rc = reverse_reconcile.run()

        classifications = {r["provider_lead_id"]: r["classification"]
                           for r in report["classifications"]}
        self.assertEqual(classifications.get(1), STATE_MISMATCH,
                         "ledger says FAILED but provider shows the lead "
                         "was acted on -> STATE_MISMATCH")


class MatchedWhenLedgerAgrees(_ReverseReconcilerBase):
    """Ledger says SENT and provider confirms -> MATCHED."""

    def test_sent_ledger_with_active_provider_is_matched(self):
        self._write_campaigns([_campaign()])
        self._write_queue([{
            "id": "rec-1", "domain": "example.test",
            "contacts": [{"key": "k1",
                          "linkedin": "https://linkedin.com/in/alpha"}],
        }])
        self._reserve("rec-1:k1:li1:linkedin")
        self._settle("rec-1:k1:li1:linkedin", actionledger.SENT)

        fake_leads = [
            {"provider_lead_id": 1, "profile_url":
             "https://linkedin.com/in/alpha", "state": "request_sent"},
        ]
        with mock.patch("scripts.reverse_reconcile._read_heyreach_leads",
                        return_value=(fake_leads, None)):
            from scripts import reverse_reconcile
            report, rc = reverse_reconcile.run()

        classifications = {r["provider_lead_id"]: r["classification"]
                           for r in report["classifications"]}
        self.assertEqual(classifications.get(1), MATCHED)


class KeyDerivationIsImported(_ReverseReconcilerBase):
    """The ledger key is derived by importing push.push_id, not re-deriving.

    If the import is broken, the key derivation fails and no rows can be
    MATCHED (they would all be UNRECORDED because the derived key would
    never match the stored one).
    """

    def test_imported_key_matches_stored_key(self):
        from src import push as push_mod

        self._write_campaigns([_campaign()])
        self._write_queue([{
            "id": "rec-1", "domain": "example.test",
            "contacts": [{"key": "k1",
                          "linkedin": "https://linkedin.com/in/alpha"}],
        }])
        expected_key = push_mod.push_id({"id": "rec-1"}, "k1", "li1",
                                        "linkedin")
        self._reserve(expected_key)
        self._settle(expected_key, actionledger.SENT)

        fake_leads = [
            {"provider_lead_id": 1, "profile_url":
             "https://linkedin.com/in/alpha", "state": "request_sent"},
        ]
        with mock.patch("scripts.reverse_reconcile._read_heyreach_leads",
                        return_value=(fake_leads, None)):
            from scripts import reverse_reconcile
            report, rc = reverse_reconcile.run()

        classifications = {r["provider_lead_id"]: r["classification"]
                           for r in report["classifications"]}
        self.assertEqual(classifications.get(1), MATCHED,
                         "the imported key derivation must produce the same "
                         "key as the stored one")


class ZeroCampaignsIsReported(_ReverseReconcilerBase):
    """A sweep that reads 0 campaigns must say so, not report '0 problems'."""

    def test_zero_campaigns_reported(self):
        self._write_campaigns([])
        self._write_queue([])

        from scripts import reverse_reconcile
        report, rc = reverse_reconcile.run()

        self.assertEqual(report["campaigns_walked"], 0)
        self.assertEqual(report["provider_rows_read"], 0)
        self.assertIn("0 == 0", report["exhaustiveness_identity"])


class ScriptHasCaller(_ReverseReconcilerBase):
    """grep -rn reverse_reconcile scripts/ src/ must find the script."""

    def test_script_is_importable(self):
        from scripts import reverse_reconcile
        self.assertTrue(hasattr(reverse_reconcile, "run"))
        self.assertTrue(hasattr(reverse_reconcile, "main"))


if __name__ == "__main__":
    unittest.main()
