"""TASK-930: the research batch controller is capped, resumable, and dry-run
writes nothing.

The batch walks the operator's approved source in deterministic order and
runs the canonical enrichment path (`enrich_record` with `for_copy=True`) for
each account that `research.why(rec, for_copy=True)` reports as needing copy
evidence.

Five properties, all asserted on behaviour rather than source:

  1. A dry run performs no actor call and writes nothing to the estate.
  2. The account cap is required and refused rather than exceeded.
  3. Order is the CSV's, not the queue's.
  4. An account that already has sufficient evidence is QUALIFIED without
     being attempted.
  5. After research, re-evaluation produces the correct disposition.
"""
import csv
import io
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import clients, enrich, evidence as ev, research, store
from scripts.research_copy_batch import (
    AccountCap, QUALIFIED, HELD, NOT_QUALIFIED, NOT_ATTEMPTED,
    _admitted_count, _copy_sufficient, _domain_of, _eligible_for_research,
    main as batch_main,
)
from tests.base import canonical_research


def _make_rec(record_id, domain, rows=(), contacts=({"email": "a@b.test"},),
              icp_status=None, state="enriched"):
    rec = {
        "id": record_id, "domain": domain, "state": state,
        "client": "productive", "lane": "domains",
        "research": list(rows), "contacts": list(contacts),
        "company_facts": {"industry": "Advertising Services",
                          "headcount_signal": 10},
    }
    if icp_status:
        rec["qualification"] = {"verdict": {"icp_status": icp_status}}
    return rec


def _admissible(n, record_id="r1"):
    out = []
    for i in range(n):
        out += canonical_research(
            record_id,
            fact=("TestCorp opened office %d in Zagreb and is hiring "
                  "%d delivery project managers" % (i, 10 + i)),
            source_url="https://%s.test/p%d" % (record_id, i))
    return out


class TestAccountCap(unittest.TestCase):
    def test_cap_is_required(self):
        with self.assertRaises(ValueError):
            AccountCap(None)

    def test_cap_refuses_rather_than_exceeds(self):
        cap = AccountCap(2)
        self.assertTrue(cap.allow("a"))
        self.assertTrue(cap.allow("b"))
        self.assertFalse(cap.allow("c"))
        self.assertEqual(["c"], cap.refused)
        self.assertEqual(["a", "b"], cap.started)

    def test_cap_of_zero_refuses_everything(self):
        cap = AccountCap(0)
        self.assertFalse(cap.allow("a"))
        self.assertEqual(["a"], cap.refused)


class TestHelpers(unittest.TestCase):
    def test_domain_of_extracts_from_email(self):
        self.assertEqual("test.com", _domain_of("user@test.com"))
        self.assertEqual("", _domain_of(""))
        self.assertEqual("", _domain_of(None))

    def test_eligible_refuses_dropped(self):
        rec = _make_rec("r1", "test.com", state="dropped")
        self.assertFalse(_eligible_for_research(rec))

    def test_eligible_refuses_rejected(self):
        rec = _make_rec("r1", "test.com", icp_status="rejected")
        self.assertFalse(_eligible_for_research(rec))

    def test_eligible_refuses_no_contacts(self):
        rec = _make_rec("r1", "test.com", contacts=())
        self.assertFalse(_eligible_for_research(rec))

    def test_eligible_allows_normal_record(self):
        rec = _make_rec("r1", "test.com")
        self.assertTrue(_eligible_for_research(rec))

    def test_copy_sufficient_with_enough_evidence(self):
        rec = _make_rec("r1", "test.com",
                        rows=_admissible(research.MIN_COPY_EVIDENCE_ROWS))
        self.assertTrue(_copy_sufficient(rec))

    def test_copy_not_sufficient_with_no_evidence(self):
        rec = _make_rec("r1", "test.com")
        self.assertFalse(_copy_sufficient(rec))

    def test_copy_not_sufficient_for_rejected(self):
        rec = _make_rec("r1", "test.com",
                        rows=_admissible(research.MIN_COPY_EVIDENCE_ROWS),
                        icp_status="rejected")
        self.assertFalse(_copy_sufficient(rec))

    def test_admitted_count_zero_for_no_rows(self):
        rec = _make_rec("r1", "test.com")
        self.assertEqual(0, _admitted_count(rec))

    def test_admitted_count_counts_admissible_rows(self):
        rec = _make_rec("r1", "test.com", rows=_admissible(4))
        self.assertEqual(4, _admitted_count(rec))


class TestDryRunWritesNothing(unittest.TestCase):
    """PROPERTY 1: a dry run performs no actor call and writes nothing.

    Asserted on the ESTATE, not by reading the code. The queue file is
    snapshotted before and after; if they differ, the dry run wrote.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-batch-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._queue_env = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self._out_env = os.environ.get("OUT")
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        self._csv_path = os.path.join(self.tmp, "source.csv")

    def tearDown(self):
        q = self._queue_env
        if q is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = q
        o = self._out_env
        if o is None:
            os.environ.pop("OUT", None)
        else:
            os.environ["OUT"] = o
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_queue(self, recs):
        with open(self.queue, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

    def _write_csv(self, rows):
        with io.open(self._csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "Work Email", "Company", "First Name", "Last Name",
                "Job Title"])
            w.writeheader()
            for row in rows:
                w.writerow(row)

    def _read_queue_bytes(self):
        with open(self.queue, "rb") as f:
            return f.read()

    def test_dry_run_writes_nothing_to_the_estate(self):
        """The queue file is byte-identical before and after a dry run.

        `enrich_record` IS called with `live=False` (it plans but does not
        call providers), but `store.save` is not, so the file on disk is
        untouched. This is asserted on the ESTATE, not by reading the code.
        """
        recs = [
            _make_rec("r1", "alpha.test"),
            _make_rec("r2", "beta.test"),
        ]
        self._write_queue(recs)
        self._write_csv([
            {"Work Email": "a@alpha.test", "Company": "Alpha"},
            {"Work Email": "b@beta.test", "Company": "Beta"},
        ])

        before = self._read_queue_bytes()

        with mock.patch("scripts.research_copy_batch.SOURCE", self._csv_path):
            result = batch_main(["--cap", "5"])

        after = self._read_queue_bytes()
        self.assertEqual(before, after,
                         "the dry run modified the queue file")

    def test_dry_run_does_not_call_store_save(self):
        recs = [_make_rec("r1", "alpha.test")]
        self._write_queue(recs)
        self._write_csv([
            {"Work Email": "a@alpha.test", "Company": "Alpha"},
        ])

        with mock.patch("scripts.research_copy_batch.SOURCE", self._csv_path):
            with mock.patch.object(store, "save") as sv:
                batch_main(["--cap", "5"])
                sv.assert_not_called()


class TestBatchDispositions(unittest.TestCase):
    """Properties 3-5: order, qualification, and re-evaluation."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-batch-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._queue_env = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self._out_env = os.environ.get("OUT")
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        self._csv_path = os.path.join(self.tmp, "source.csv")

    def tearDown(self):
        q = self._queue_env
        if q is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = q
        o = self._out_env
        if o is None:
            os.environ.pop("OUT", None)
        else:
            os.environ["OUT"] = o
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_queue(self, recs):
        with open(self.queue, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

    def _write_csv(self, rows):
        with io.open(self._csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "Work Email", "Company", "First Name", "Last Name",
                "Job Title"])
            w.writeheader()
            for row in rows:
                w.writerow(row)

    def test_order_follows_the_csv_not_the_queue(self):
        recs = [
            _make_rec("r2", "beta.test"),
            _make_rec("r1", "alpha.test"),
        ]
        self._write_queue(recs)
        self._write_csv([
            {"Work Email": "a@alpha.test", "Company": "Alpha"},
            {"Work Email": "b@beta.test", "Company": "Beta"},
        ])

        with mock.patch("scripts.research_copy_batch.SOURCE", self._csv_path):
            result = batch_main(["--cap", "5"])

        domains = [d["domain"] for d in result["dispositions"]]
        self.assertEqual(["alpha.test", "beta.test"], domains)

    def test_already_sufficient_evidence_is_qualified_without_attempt(self):
        rows = _admissible(research.MIN_COPY_EVIDENCE_ROWS, "r1")
        recs = [_make_rec("r1", "alpha.test", rows=rows)]
        self._write_queue(recs)
        self._write_csv([
            {"Work Email": "a@alpha.test", "Company": "Alpha"},
        ])

        with mock.patch("scripts.research_copy_batch.SOURCE", self._csv_path):
            with mock.patch.object(enrich, "enrich_record") as er:
                result = batch_main(["--cap", "5"])
                er.assert_not_called()

        self.assertEqual(1, result["counts"][QUALIFIED])
        self.assertEqual(0, result["counts"][HELD])
        self.assertFalse(result["dispositions"][0]["attempted"])

    def test_rejected_account_is_not_qualified(self):
        recs = [_make_rec("r1", "alpha.test", icp_status="rejected")]
        self._write_queue(recs)
        self._write_csv([
            {"Work Email": "a@alpha.test", "Company": "Alpha"},
        ])

        with mock.patch("scripts.research_copy_batch.SOURCE", self._csv_path):
            result = batch_main(["--cap", "5"])

        self.assertEqual(1, result["counts"][NOT_QUALIFIED])

    def test_no_canonical_record_is_not_qualified(self):
        self._write_queue([])
        self._write_csv([
            {"Work Email": "a@unknown.test", "Company": "Unknown"},
        ])

        with mock.patch("scripts.research_copy_batch.SOURCE", self._csv_path):
            result = batch_main(["--cap", "5"])

        self.assertEqual(1, result["counts"][NOT_QUALIFIED])

    def test_account_cap_refuses_rather_than_exceeds(self):
        recs = [
            _make_rec("r1", "alpha.test"),
            _make_rec("r2", "beta.test"),
            _make_rec("r3", "gamma.test"),
        ]
        self._write_queue(recs)
        self._write_csv([
            {"Work Email": "a@alpha.test", "Company": "Alpha"},
            {"Work Email": "b@beta.test", "Company": "Beta"},
            {"Work Email": "c@gamma.test", "Company": "Gamma"},
        ])

        with mock.patch("scripts.research_copy_batch.SOURCE", self._csv_path):
            with mock.patch.object(enrich, "enrich_record") as er:
                result = batch_main(["--cap", "1"])

        self.assertEqual(1, len(result["account_cap"]["started"]))
        self.assertEqual(2, len(result["account_cap"]["refused"]))
        self.assertEqual(2, result["counts"][NOT_ATTEMPTED])
        er.assert_called_once()

    def test_re_evaluation_after_research(self):
        recs = [_make_rec("r1", "alpha.test")]
        self._write_queue(recs)
        self._write_csv([
            {"Work Email": "a@alpha.test", "Company": "Alpha"},
        ])

        def _enrich_that_adds_evidence(rec, *a, **kw):
            rec.setdefault("research", []).extend(
                _admissible(research.MIN_COPY_EVIDENCE_ROWS, rec["id"]))

        with mock.patch("scripts.research_copy_batch.SOURCE", self._csv_path):
            with mock.patch.object(enrich, "enrich_record",
                                   side_effect=_enrich_that_adds_evidence):
                result = batch_main(["--cap", "5"])

        self.assertEqual(1, result["counts"][QUALIFIED])
        self.assertTrue(result["dispositions"][0]["attempted"])

    def test_held_when_research_does_not_add_enough(self):
        recs = [_make_rec("r1", "alpha.test")]
        self._write_queue(recs)
        self._write_csv([
            {"Work Email": "a@alpha.test", "Company": "Alpha"},
        ])

        def _enrich_that_adds_one_row(rec, *a, **kw):
            rec.setdefault("research", []).extend(
                _admissible(1, rec["id"]))

        with mock.patch("scripts.research_copy_batch.SOURCE", self._csv_path):
            with mock.patch.object(enrich, "enrich_record",
                                   side_effect=_enrich_that_adds_one_row):
                result = batch_main(["--cap", "5"])

        self.assertEqual(1, result["counts"][HELD])
        self.assertEqual(1, result["dispositions"][0]["admitted"])

    def test_enrich_record_is_called_with_for_copy_true(self):
        recs = [_make_rec("r1", "alpha.test")]
        self._write_queue(recs)
        self._write_csv([
            {"Work Email": "a@alpha.test", "Company": "Alpha"},
        ])

        with mock.patch("scripts.research_copy_batch.SOURCE", self._csv_path):
            with mock.patch.object(enrich, "enrich_record") as er:
                batch_main(["--cap", "5"])

        _, kwargs = er.call_args
        self.assertTrue(kwargs.get("for_copy"),
                        "enrich_record was not called with for_copy=True")


if __name__ == "__main__":
    unittest.main()
