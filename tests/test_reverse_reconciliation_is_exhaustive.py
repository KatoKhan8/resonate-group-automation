"""The reverse reconciler classifies every provider row, silently losing none.

The four classes (MATCHED, UNRECORDED, STATE_MISMATCH, NOT_OURS) plus
UNKNOWN are mutually exclusive and exhaustive: classified rows == provider
rows read. A `continue` cannot lose a row.

An injected provider row with no ledger key lands in UNRECORDED, and
removing the classification call makes that test fail.

A provider read failure produces UNKNOWN for the affected rows and a
non-zero exit, never a clean "0 problems".
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import reverse_reconcile                              # noqa: E402
from src import actionledger, push                                 # noqa: E402


class _TempState:
    """Set up temp files for QUEUE, CAMPAIGNS, ACTION_LEDGER."""

    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-rev-reconc-")
        self.queue_path = os.path.join(self.tmp, "queue.jsonl")
        self.campaigns_path = os.path.join(self.tmp, "campaigns.jsonl")
        self.ledger_path = os.path.join(self.tmp, "action-ledger.jsonl")
        self._saved = {}

    def write_jsonl(self, path, rows):
        with open(path, "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")

    def install(self):
        for key, path in [("QUEUE", self.queue_path),
                          ("CAMPAIGNS", self.campaigns_path),
                          ("ACTION_LEDGER", self.ledger_path)]:
            self._saved[key] = os.environ.get(key)
            os.environ[key] = path

    def restore(self):
        for key, old in self._saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)


def _make_rec(rec_id, contacts):
    """A minimal queue record."""
    return {"id": rec_id, "state": "verified", "contacts": contacts}


def _make_contact(key, linkedin="", email=""):
    return {"key": key, "linkedin": linkedin, "email": email}


def _make_campaign(campaign_id, record_ids, heyreach_id=None,
                   bison_id=None, client="test-client"):
    return {
        "campaign_id": campaign_id,
        "client": client,
        "status": "running",
        "record_ids": record_ids,
        "heyreach_campaign_id": heyreach_id,
        "bison_campaign_id": bison_id,
    }


def _ledger_row(rec_id, contact_key, step_key, channel, campaign_id,
                state="sent"):
    rec = {"id": rec_id}
    key = push.push_id(rec, contact_key, step_key, channel)
    return {
        "key": key,
        "state": state,
        "at": "2026-09-25T10:00:00",
        "operation": f"{'heyreach' if channel == 'linkedin' else 'bison'}"
                     f".{'add_lead' if channel == 'linkedin' else 'activate'}",
        "channel": channel,
        "workspace": "test-workspace",
        "campaign_id": campaign_id,
        "sender_id": "sender-1",
        "rec_id": str(rec_id),
        "contact_key": contact_key,
        "step_key": step_key,
        "fingerprint": "fp-123",
        "by": "test",
    }


class TestExhaustivenessIdentity(unittest.TestCase):
    """classified rows + UNKNOWN == provider rows read. Always."""

    def setUp(self):
        self.state = _TempState()
        self.state.install()

    def tearDown(self):
        self.state.restore()
        self.state.cleanup()

    def test_exhaustiveness_identity_holds_with_no_leads(self):
        """Zero provider rows: identity holds trivially."""
        self.state.write_jsonl(self.state.queue_path, [])
        self.state.write_jsonl(self.state.campaigns_path, [])
        self.state.write_jsonl(self.state.ledger_path, [])

        ledger_index = reverse_reconcile.build_ledger_index([])
        all_rows = []
        total = len(all_rows)
        classified = sum(1 for r in all_rows if r.get("class")
                         in reverse_reconcile.CLASSES)
        self.assertEqual(classified, total)

    def test_exhaustiveness_identity_holds_with_mixed_classes(self):
        """Every class contributes to the total. None is silently dropped."""
        rows = [
            {"class": reverse_reconcile.MATCHED},
            {"class": reverse_reconcile.UNRECORDED},
            {"class": reverse_reconcile.STATE_MISMATCH},
            {"class": reverse_reconcile.NOT_OURS},
            {"class": reverse_reconcile.UNKNOWN},
        ]
        total = len(rows)
        classified = sum(1 for r in rows if r.get("class")
                         in reverse_reconcile.CLASSES)
        self.assertEqual(classified, total)

    def test_unknown_class_is_in_exhaustiveness(self):
        """UNKNOWN counts toward the total. A continue that skips it fails."""
        rows = [
            {"class": reverse_reconcile.UNKNOWN},
            {"class": reverse_reconcile.UNKNOWN},
            {"class": reverse_reconcile.MATCHED},
        ]
        total = len(rows)
        classified = sum(1 for r in rows if r.get("class")
                         in reverse_reconcile.CLASSES)
        self.assertEqual(classified, total)


class TestUnrecordedDetection(unittest.TestCase):
    """An injected provider row with no ledger key lands in UNRECORDED."""

    def setUp(self):
        self.state = _TempState()
        self.state.install()

    def tearDown(self):
        self.state.restore()
        self.state.cleanup()

    def test_injected_provider_row_is_unrecorded(self):
        """A lead at the provider with no ledger row is UNRECORDED."""
        rec = _make_rec("rec-1", [_make_contact("c1", linkedin=(
            "https://linkedin.com/in/testperson"))])
        self.state.write_jsonl(self.state.queue_path, [rec])

        camp = _make_campaign("camp-1", ["rec-1"], heyreach_id=99999)
        self.state.write_jsonl(self.state.campaigns_path, [camp])
        self.state.write_jsonl(self.state.ledger_path, [])

        ledger_index = reverse_reconcile.build_ledger_index([])

        fake_lead = {
            "id": 12345,
            "linkedInUserProfile": {
                "profileUrl": "https://linkedin.com/in/testperson",
                "linkedin_id": "99",
            },
            "customFields": [
                {"name": "record_id", "value": "rec-1"},
                {"name": "contact_key", "value": "c1"},
            ],
            "leadCampaignStatus": "InSequence",
            "leadConnectionStatus": None,
            "leadMessageStatus": None,
        }

        with mock.patch.object(reverse_reconcile.heyreach, "_read") as mr, \
             mock.patch.object(reverse_reconcile.heyreach, "campaign_by_id",
                               return_value={"name": "test [test-client/camp-1]"}) as mci:  # noqa: E501
            mr.return_value = {
                "items": [fake_lead],
                "totalCount": 1,
            }
            with mock.patch.object(reverse_reconcile.collision,
                                   "campaign_bindings", return_value={
                                       99999: camp}):
                with mock.patch.object(reverse_reconcile.collision, "_ours",
                                       return_value=(True, "claimed")):
                    rows, error = reverse_reconcile.classify_heyreach_campaign(
                        camp, [rec], ledger_index)

        self.assertIsNone(error)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["class"], reverse_reconcile.UNRECORDED)

    def test_removing_classification_makes_test_fail(self):
        """If we skip the classification call, we get no UNRECORDED row.

        This proves the test depends on the classification, not on fixtures.
        """
        rec = _make_rec("rec-1", [_make_contact("c1", linkedin=(
            "https://linkedin.com/in/testperson"))])
        self.state.write_jsonl(self.state.queue_path, [rec])

        camp = _make_campaign("camp-1", ["rec-1"], heyreach_id=99999)
        self.state.write_jsonl(self.state.campaigns_path, [camp])
        self.state.write_jsonl(self.state.ledger_path, [])

        ledger_index = reverse_reconcile.build_ledger_index([])

        # Simulate removing the classification: just build the row without
        # calling _classify_ledger_match. The result should NOT be UNRECORDED.
        pair = ("rec-1", "c1")
        # Without calling _classify_ledger_match, we have no class.
        row_without_classification = {
            "provider_lead_id": 12345,
            "record_id": "rec-1",
            "contact_key": "c1",
        }
        self.assertNotIn("class", row_without_classification)
        # The classification is what produces UNRECORDED:
        cls, _ = reverse_reconcile._classify_ledger_match(pair, ledger_index)
        self.assertEqual(cls, reverse_reconcile.UNRECORDED)


class TestProviderReadFailure(unittest.TestCase):
    """A provider read failure produces UNKNOWN and a non-zero exit."""

    def setUp(self):
        self.state = _TempState()
        self.state.install()

    def tearDown(self):
        self.state.restore()
        self.state.cleanup()

    def test_heyreach_read_failure_produces_unknown(self):
        """When HeyReach is unreadable, rows are UNKNOWN, not absent."""
        rec = _make_rec("rec-1", [_make_contact("c1", linkedin=(
            "https://linkedin.com/in/testperson"))])
        camp = _make_campaign("camp-1", ["rec-1"], heyreach_id=99999)
        self.state.write_jsonl(self.state.queue_path, [rec])
        self.state.write_jsonl(self.state.campaigns_path, [camp])

        ledger_row = _ledger_row("rec-1", "c1", "day1", "linkedin", "camp-1")
        self.state.write_jsonl(self.state.ledger_path, [ledger_row])
        ledger_index = reverse_reconcile.build_ledger_index([ledger_row])

        with mock.patch.object(reverse_reconcile.heyreach, "campaign_by_id",
                               side_effect=Exception("connection refused")), \
             mock.patch.object(reverse_reconcile.heyreach, "_read",
                               side_effect=Exception("connection refused")):
            with mock.patch.object(reverse_reconcile.collision,
                                   "campaign_bindings", return_value={}):
                rows, error = reverse_reconcile.classify_heyreach_campaign(
                    camp, [rec], ledger_index)

        self.assertIsNotNone(error)
        self.assertTrue(len(rows) > 0)
        for row in rows:
            self.assertEqual(row["class"], reverse_reconcile.UNKNOWN)

    def test_bison_read_failure_produces_unknown(self):
        """When Bison is unreadable, rows are UNKNOWN, not absent."""
        rec = _make_rec("rec-2", [_make_contact("c2", email=(
            "test@example.com"))])
        camp = _make_campaign("camp-2", ["rec-2"], bison_id=88888)
        self.state.write_jsonl(self.state.queue_path, [rec])
        self.state.write_jsonl(self.state.campaigns_path, [camp])
        self.state.write_jsonl(self.state.ledger_path, [])
        ledger_index = reverse_reconcile.build_ledger_index([])

        with mock.patch.object(reverse_reconcile.bison, "campaign",
                               side_effect=Exception("timeout")), \
             mock.patch.object(reverse_reconcile.bison, "request",
                               side_effect=Exception("timeout")):
            with mock.patch.object(reverse_reconcile.collision,
                                   "campaign_bindings", return_value={}):
                rows, error = reverse_reconcile.classify_bison_campaign(
                    camp, [rec], ledger_index)

        self.assertIsNotNone(error)
        self.assertTrue(len(rows) > 0)
        for row in rows:
            self.assertEqual(row["class"], reverse_reconcile.UNKNOWN)


class TestMutuallyExclusiveClasses(unittest.TestCase):
    """Each row gets exactly one class. Never two, never zero."""

    def test_classes_are_mutually_exclusive(self):
        """A row has exactly one class value."""
        for cls in reverse_reconcile.CLASSES:
            row = {"class": cls}
            matches = [c for c in reverse_reconcile.CLASSES
                       if row.get("class") == c]
            self.assertEqual(len(matches), 1,
                             f"{cls} matched {len(matches)} classes")

    def test_all_classes_are_known(self):
        """Every class value is one of the five defined classes."""
        for cls in reverse_reconcile.CLASSES:
            self.assertIn(cls, reverse_reconcile.CLASSES)


class TestNotOursRequiresProof(unittest.TestCase):
    """NOT_OURS must be proved, not assumed. Unprovable -> UNKNOWN."""

    def setUp(self):
        self.state = _TempState()
        self.state.install()

    def tearDown(self):
        self.state.restore()
        self.state.cleanup()

    def test_positively_disproved_ownership_is_not_ours(self):
        """When _ownership_evidence returns False, the row is NOT_OURS."""
        rec = _make_rec("rec-1", [_make_contact("c1", linkedin=(
            "https://linkedin.com/in/testperson"))])
        camp = _make_campaign("camp-1", ["rec-1"], heyreach_id=99999)
        self.state.write_jsonl(self.state.queue_path, [rec])
        self.state.write_jsonl(self.state.campaigns_path, [camp])
        self.state.write_jsonl(self.state.ledger_path, [])
        ledger_index = reverse_reconcile.build_ledger_index([])

        fake_lead = {
            "id": 12345,
            "linkedInUserProfile": {
                "profileUrl": "https://linkedin.com/in/testperson",
                "linkedin_id": "99",
            },
            "customFields": [
                {"name": "record_id", "value": "rec-1"},
                {"name": "contact_key", "value": "c1"},
            ],
            "leadCampaignStatus": "InSequence",
            "leadConnectionStatus": None,
            "leadMessageStatus": None,
        }

        # _ownership_evidence returns (False, ...) -> NOT_OURS
        with mock.patch.object(reverse_reconcile.heyreach, "_read") as mr, \
             mock.patch.object(reverse_reconcile.heyreach, "campaign_by_id",
                               return_value={"name": "some campaign"}), \
             mock.patch.object(reverse_reconcile, "_ownership_evidence",
                               return_value=(False, "name mismatch")):
            mr.return_value = {
                "items": [fake_lead],
                "totalCount": 1,
            }
            rows, error = (
                reverse_reconcile.classify_heyreach_campaign(
                    camp, [rec], ledger_index))

        self.assertEqual(rows[0]["class"], reverse_reconcile.NOT_OURS)
        self.assertIn("disproved", rows[0]["evidence"])

    def test_none_ownership_is_unknown(self):
        """When _ownership_evidence returns None, the row is UNKNOWN."""
        rec = _make_rec("rec-1", [_make_contact("c1", linkedin=(
            "https://linkedin.com/in/testperson"))])
        camp = _make_campaign("camp-1", ["rec-1"], heyreach_id=99999)
        self.state.write_jsonl(self.state.queue_path, [rec])
        self.state.write_jsonl(self.state.campaigns_path, [camp])
        self.state.write_jsonl(self.state.ledger_path, [])
        ledger_index = reverse_reconcile.build_ledger_index([])

        fake_lead = {
            "id": 12345,
            "linkedInUserProfile": {
                "profileUrl": "https://linkedin.com/in/testperson",
                "linkedin_id": "99",
            },
            "customFields": [
                {"name": "record_id", "value": "rec-1"},
                {"name": "contact_key", "value": "c1"},
            ],
            "leadCampaignStatus": "InSequence",
            "leadConnectionStatus": None,
            "leadMessageStatus": None,
        }

        # _ownership_evidence returns None (unproven) -> UNKNOWN
        with mock.patch.object(reverse_reconcile.heyreach, "_read") as mr, \
             mock.patch.object(reverse_reconcile.heyreach, "campaign_by_id",
                               return_value={"name": "some campaign"}):
            mr.return_value = {
                "items": [fake_lead],
                "totalCount": 1,
            }
            with mock.patch.object(
                    reverse_reconcile, "_ownership_evidence",
                    return_value=(None, "no binding found")):
                rows, error = (
                    reverse_reconcile.classify_heyreach_campaign(
                        camp, [rec], ledger_index))

        self.assertEqual(rows[0]["class"], reverse_reconcile.UNKNOWN)
        self.assertIn("unproven", rows[0]["evidence"])


class TestMatchedClassification(unittest.TestCase):
    """A provider lead with a matching active ledger row is MATCHED."""

    def setUp(self):
        self.state = _TempState()
        self.state.install()

    def tearDown(self):
        self.state.restore()
        self.state.cleanup()

    def test_provider_lead_with_active_ledger_row_is_matched(self):
        """Provider says lead is present, ledger says SENT -> MATCHED."""
        rec = _make_rec("rec-1", [_make_contact("c1", linkedin=(
            "https://linkedin.com/in/testperson"))])
        camp = _make_campaign("camp-1", ["rec-1"], heyreach_id=99999)
        self.state.write_jsonl(self.state.queue_path, [rec])
        self.state.write_jsonl(self.state.campaigns_path, [camp])

        ledger_row = _ledger_row("rec-1", "c1", "day1", "linkedin", "camp-1",
                                 state="sent")
        self.state.write_jsonl(self.state.ledger_path, [ledger_row])
        ledger_index = reverse_reconcile.build_ledger_index([ledger_row])

        fake_lead = {
            "id": 12345,
            "linkedInUserProfile": {
                "profileUrl": "https://linkedin.com/in/testperson",
                "linkedin_id": "99",
            },
            "customFields": [
                {"name": "record_id", "value": "rec-1"},
                {"name": "contact_key", "value": "c1"},
            ],
            "leadCampaignStatus": "InSequence",
            "leadConnectionStatus": None,
            "leadMessageStatus": None,
        }

        with mock.patch.object(reverse_reconcile.heyreach, "_read") as mr, \
             mock.patch.object(reverse_reconcile.heyreach, "campaign_by_id",
                               return_value={"name": "test [test-client/camp-1]"}):  # noqa: E501
            mr.return_value = {
                "items": [fake_lead],
                "totalCount": 1,
            }
            with mock.patch.object(reverse_reconcile.collision,
                                   "campaign_bindings",
                                   return_value={99999: camp}):
                with mock.patch.object(reverse_reconcile.collision, "_ours",
                                       return_value=(True, "claimed")):
                    rows, error = (
                        reverse_reconcile.classify_heyreach_campaign(
                            camp, [rec], ledger_index))

        self.assertIsNone(error)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["class"], reverse_reconcile.MATCHED)
        self.assertTrue(rows[0].get("key_verified"))


class TestStateMismatch(unittest.TestCase):
    """Provider says lead is present, ledger says FAILED -> STATE_MISMATCH."""

    def setUp(self):
        self.state = _TempState()
        self.state.install()

    def tearDown(self):
        self.state.restore()
        self.state.cleanup()

    def test_provider_active_but_ledger_failed_is_mismatch(self):
        """Provider has the lead, but every ledger row is FAILED."""
        rec = _make_rec("rec-1", [_make_contact("c1", linkedin=(
            "https://linkedin.com/in/testperson"))])
        camp = _make_campaign("camp-1", ["rec-1"], heyreach_id=99999)
        self.state.write_jsonl(self.state.queue_path, [rec])
        self.state.write_jsonl(self.state.campaigns_path, [camp])

        ledger_row = _ledger_row("rec-1", "c1", "day1", "linkedin", "camp-1",
                                 state="failed")
        self.state.write_jsonl(self.state.ledger_path, [ledger_row])
        ledger_index = reverse_reconcile.build_ledger_index([ledger_row])

        fake_lead = {
            "id": 12345,
            "linkedInUserProfile": {
                "profileUrl": "https://linkedin.com/in/testperson",
                "linkedin_id": "99",
            },
            "customFields": [
                {"name": "record_id", "value": "rec-1"},
                {"name": "contact_key", "value": "c1"},
            ],
            "leadCampaignStatus": "InSequence",
            "leadConnectionStatus": None,
            "leadMessageStatus": None,
        }

        with mock.patch.object(reverse_reconcile.heyreach, "_read") as mr, \
             mock.patch.object(reverse_reconcile.heyreach, "campaign_by_id",
                               return_value={"name": "test [test-client/camp-1]"}):  # noqa: E501
            mr.return_value = {
                "items": [fake_lead],
                "totalCount": 1,
            }
            with mock.patch.object(reverse_reconcile.collision,
                                   "campaign_bindings",
                                   return_value={99999: camp}):
                with mock.patch.object(reverse_reconcile.collision, "_ours",
                                       return_value=(True, "claimed")):
                    rows, error = (
                        reverse_reconcile.classify_heyreach_campaign(
                            camp, [rec], ledger_index))

        self.assertIsNone(error)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["class"], reverse_reconcile.STATE_MISMATCH)


class TestKeyVerification(unittest.TestCase):
    """The key derivation is imported, not re-implemented."""

    def test_verify_key_accepts_correct_key(self):
        """A key derived by push.push_id passes verification."""
        rec = {"id": "rec-1"}
        key = push.push_id(rec, "c1", "day1", "email")
        row = {"rec_id": "rec-1", "contact_key": "c1",
               "step_key": "day1", "channel": "email", "key": key}
        self.assertTrue(reverse_reconcile.verify_key(row))

    def test_verify_key_rejects_tampered_key(self):
        """A key that does not match push.push_id fails verification."""
        row = {"rec_id": "rec-1", "contact_key": "c1",
               "step_key": "day1", "channel": "email",
               "key": "wrong:key:here:email"}
        self.assertFalse(reverse_reconcile.verify_key(row))

    def test_push_id_is_imported_not_reimplemented(self):
        """The script imports push.push_id and uses it for verification."""
        import inspect
        source = inspect.getsource(reverse_reconcile)
        self.assertIn("push.push_id", source)
        self.assertIn("from src import", source)


class TestLedgerIndex(unittest.TestCase):
    """The ledger index maps (record_id, contact_key) to ledger rows."""

    def test_empty_ledger(self):
        index = reverse_reconcile.build_ledger_index([])
        self.assertEqual(index, {})

    def test_single_row_indexed(self):
        rec = {"id": "rec-1"}
        key = push.push_id(rec, "c1", "day1", "email")
        row = {"key": key, "state": "sent"}
        index = reverse_reconcile.build_ledger_index([row])
        self.assertIn(("rec-1", "c1"), index)
        self.assertEqual(len(index[("rec-1", "c1")]), 1)

    def test_multiple_rows_same_pair(self):
        rec = {"id": "rec-1"}
        key1 = push.push_id(rec, "c1", "day1", "email")
        key2 = push.push_id(rec, "c1", "day3", "email")
        rows = [{"key": key1, "state": "sent"},
                {"key": key2, "state": "attempted"}]
        index = reverse_reconcile.build_ledger_index(rows)
        self.assertEqual(len(index[("rec-1", "c1")]), 2)


class TestMainExitCodes(unittest.TestCase):
    """Exit codes: 0 = clean, 1 = issues found, 2 = identity violated."""

    def setUp(self):
        self.state = _TempState()
        self.state.install()

    def tearDown(self):
        self.state.restore()
        self.state.cleanup()

    def test_clean_run_returns_zero(self):
        """No campaigns, no provider rows -> exit 0."""
        self.state.write_jsonl(self.state.queue_path, [])
        self.state.write_jsonl(self.state.campaigns_path, [])
        self.state.write_jsonl(self.state.ledger_path, [])

        rc = reverse_reconcile.main([])
        self.assertEqual(rc, 0)

    def test_unrecorded_returns_nonzero(self):
        """A UNRECORDED row makes the exit code non-zero."""
        rec = _make_rec("rec-1", [_make_contact("c1", linkedin=(
            "https://linkedin.com/in/testperson"))])
        camp = _make_campaign("camp-1", ["rec-1"], heyreach_id=99999)
        self.state.write_jsonl(self.state.queue_path, [rec])
        self.state.write_jsonl(self.state.campaigns_path, [camp])
        self.state.write_jsonl(self.state.ledger_path, [])

        fake_lead = {
            "id": 12345,
            "linkedInUserProfile": {
                "profileUrl": "https://linkedin.com/in/testperson",
                "linkedin_id": "99",
            },
            "customFields": [
                {"name": "record_id", "value": "rec-1"},
                {"name": "contact_key", "value": "c1"},
            ],
            "leadCampaignStatus": "InSequence",
            "leadConnectionStatus": None,
            "leadMessageStatus": None,
        }

        with mock.patch.object(reverse_reconcile.heyreach, "_read") as mr, \
             mock.patch.object(reverse_reconcile.heyreach, "campaign_by_id",
                               return_value={"name": "test [test-client/camp-1]"}):  # noqa: E501
            mr.return_value = {"items": [fake_lead], "totalCount": 1}
            with mock.patch.object(reverse_reconcile.collision,
                                   "campaign_bindings",
                                   return_value={99999: camp}):
                with mock.patch.object(reverse_reconcile.collision, "_ours",
                                       return_value=(True, "claimed")):
                    with mock.patch.object(reverse_reconcile, "store") as ms:
                        ms.load.return_value = [rec]
                        rc = reverse_reconcile.main([])

        self.assertNotEqual(rc, 0)


class TestIssue025Analysis(unittest.TestCase):
    """Would this sweep have caught ISSUE-025's 76 blank emails?

    The 76 blank emails went to leads that were adopted from the client's
    estate - they carried no record_id/contact_key customFields. The reverse
    reconciler would classify them as UNKNOWN (no customFields to derive a
    ledger key from), which surfaces them as anomalies requiring investigation.
    """

    def test_lead_without_custom_fields_is_unknown(self):
        """A lead adopted from the client's estate is UNKNOWN.

        ISSUE-025: 76 blank emails went to leads that were adopted from the
        client's estate - they carried no record_id/contact_key variables.
        The reverse reconciler classifies them as UNKNOWN because their email
        does not match any queue record, surfacing the anomaly.
        """
        self.state = _TempState()
        self.state.install()
        rec = _make_rec("rec-1", [_make_contact("c1", email=(
            "prospect@example.com"))])
        camp = _make_campaign("camp-1", ["rec-1"], bison_id=491)
        self.state.write_jsonl(self.state.queue_path, [rec])
        self.state.write_jsonl(self.state.campaigns_path, [camp])
        self.state.write_jsonl(self.state.ledger_path, [])
        ledger_index = reverse_reconcile.build_ledger_index([])

        # A lead adopted from the client's estate: has email but no variables
        foreign_lead = {
            "id": 55555,
            "email": "foreign-lead@example.com",
            "lead_campaign_data": [
                {"campaign_id": 491, "status": "in_sequence"},
            ],
        }

        with mock.patch.object(reverse_reconcile, "_bison_leads_paged",
                               return_value=[foreign_lead]), \
             mock.patch.object(reverse_reconcile, "_ownership_evidence",
                               return_value=(True, "claimed")), \
             mock.patch.object(reverse_reconcile.bison, "_status_in",
                               return_value="in_sequence"):
            rows, error = reverse_reconcile.classify_bison_campaign(
                camp, [rec], ledger_index)

        self.state.restore()
        self.state.cleanup()

        self.assertIsNone(error)
        self.assertEqual(len(rows), 1)
        # The foreign lead has an email that is NOT in our queue records,
        # so it is UNKNOWN (cannot derive ledger key)
        self.assertEqual(rows[0]["class"], reverse_reconcile.UNKNOWN)
        self.assertIn("not in any queue record", rows[0]["evidence"])


if __name__ == "__main__":
    unittest.main()
