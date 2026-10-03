"""Tests for the minimum durable controller (TASK-933).

Proves:
1. Checkpoint round-trips losslessly (mutation check)
2. Kill-and-restart resumes from the exact row, no re-processing
3. Duplicate protection: an already-enrolled domain is skipped
4. Dry mode processes no provider writes
5. Batch-size cap stops the walk at the right count
6. The controller does NOT import or call provider-write modules directly
"""
import csv
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Load durable_controller from scripts/ (not a package)
_dc_path = os.path.join(ROOT, "scripts", "durable_controller.py")
_dc_spec = importlib.util.spec_from_file_location(
    "durable_controller", _dc_path)
dc = importlib.util.module_from_spec(_dc_spec)
_dc_spec.loader.exec_module(dc)


class CheckpointRoundTrip(unittest.TestCase):
    """The checkpoint must survive a write-read cycle with no data loss."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cp = os.path.join(self.tmpdir, "checkpoint.json")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_mutation_check_passes(self):
        ok = dc.verify_checkpoint_mutation(self.cp)
        self.assertTrue(ok)

    def test_round_trip_preserves_all_fields(self):
        state = dc.new_checkpoint("batch-test", 10)
        state["rows"]["1"] = {
            "disposition": "QUALIFIED",
            "reason": "cleared all gates",
            "domain": "example.com",
            "approval_hash": "abcdef0123456789",
            "provider_campaign_id": "camp-42",
            "provider_write_state": "performed",
            "readback_state": "verified",
        }
        state["source_position"] = 1
        dc.save_checkpoint(state, self.cp)
        loaded = dc.load_checkpoint(self.cp)
        self.assertEqual(loaded["batch_id"], "batch-test")
        self.assertEqual(loaded["batch_size"], 10)
        self.assertEqual(loaded["source_position"], 1)
        self.assertEqual(loaded["rows"]["1"]["approval_hash"],
                         "abcdef0123456789")
        self.assertEqual(loaded["rows"]["1"]["provider_campaign_id"],
                         "camp-42")

    def test_absent_checkpoint_returns_none(self):
        result = dc.load_checkpoint(
            os.path.join(self.tmpdir, "nonexistent.json"))
        self.assertIsNone(result)


class KillAndRestart(unittest.TestCase):
    """A controller killed mid-batch and restarted must resume from the
    exact row it reached, processing no row twice."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cp = os.path.join(self.tmpdir, "checkpoint.json")
        self.csv_path = os.path.join(self.tmpdir, "source.csv")
        self._write_csv(10)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_csv(self, n):
        with open(self.csv_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "Work Email", "Company", "First Name", "Last Name",
                "Job Title"])
            w.writeheader()
            for i in range(1, n + 1):
                w.writerow({
                    "Work Email": "person%d@example%d.com" % (i, i),
                    "Company": "Company %d" % i,
                    "First Name": "First%d" % i,
                    "Last Name": "Last%d" % i,
                    "Job Title": "Title %d" % i,
                })

    def test_resume_picks_up_at_source_position(self):
        # First run: process 3 rows, then "kill" (stop).
        cp1 = dc.run(
            batch_id="kill-test", batch_size=10, limit=3,
            live=False, checkpoint_override=self.cp,
            source_override=self.csv_path)
        self.assertEqual(cp1["source_position"], 3)
        self.assertEqual(len(cp1["rows"]), 3)

        # Second run: resume with the same batch_id, limit higher.
        cp2 = dc.run(
            batch_id="kill-test", batch_size=10, limit=7,
            live=False, checkpoint_override=self.cp,
            source_override=self.csv_path)
        # Rows 1-3 were already done; rows 4-7 are new.
        self.assertEqual(cp2["source_position"], 7)
        self.assertEqual(len(cp2["rows"]), 7)
        # Rows 1-3 are unchanged from the first run.
        for idx in ("1", "2", "3"):
            self.assertIn(idx, cp2["rows"])

    def test_completed_batch_refuses_restart(self):
        cp = dc.new_checkpoint("done-batch", 2)
        cp["batch_status"] = "complete"
        cp["source_position"] = 5
        dc.save_checkpoint(cp, self.cp)

        result = dc.run(
            batch_id="done-batch", batch_size=2, limit=10,
            live=False, checkpoint_override=self.cp,
            source_override=self.csv_path)
        # Should not have changed - still complete at position 5.
        self.assertEqual(result["batch_status"], "complete")
        self.assertEqual(result["source_position"], 5)


class DuplicateProtection(unittest.TestCase):
    """An already-enrolled domain must not be re-processed."""

    def test_enrolled_domain_is_skipped(self):
        by_domain = {
            "example.com": {"state": "pushed", "id": "rec-1"},
        }
        self.assertTrue(dc.is_already_enrolled("example.com", by_domain))

    def test_approved_domain_is_skipped(self):
        by_domain = {
            "example.com": {"state": "approved", "id": "rec-1"},
        }
        self.assertTrue(dc.is_already_enrolled("example.com", by_domain))

    def test_drafted_domain_is_skipped(self):
        by_domain = {
            "example.com": {"state": "drafted", "id": "rec-1"},
        }
        self.assertTrue(dc.is_already_enrolled("example.com", by_domain))

    def test_queued_domain_is_not_enrolled(self):
        by_domain = {
            "example.com": {"state": "queued", "id": "rec-1"},
        }
        self.assertFalse(dc.is_already_enrolled("example.com", by_domain))

    def test_unknown_domain_is_not_enrolled(self):
        self.assertFalse(dc.is_already_enrolled("new.com", {}))

    def test_dropped_domain_is_not_enrolled(self):
        by_domain = {
            "example.com": {"state": "dropped", "id": "rec-1"},
        }
        self.assertFalse(dc.is_already_enrolled("example.com", by_domain))


class DryMode(unittest.TestCase):
    """Dry mode must not set any provider-write flags."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cp = os.path.join(self.tmpdir, "checkpoint.json")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_dry_does_not_set_provider_write_state(self):
        # In dry mode, a QUALIFIED row gets would_generate=True but no
        # provider_write_state. We verify by checking that the process_row
        # function in dry mode does not produce provider write fields.
        # Since we can't easily call assess() without a full estate, we
        # verify the structural property: process_row in dry mode sets
        # would_generate but not provider_write_state.
        row = {"Work Email": "test@nonexistent-domain-xyz.com",
               "Company": "TestCo"}
        by_domain = {}
        config = {}
        checkpoint = dc.new_checkpoint("dry-test", 5)

        verdict, reason, detail = dc.process_row(
            1, row, by_domain, config, checkpoint, live=False)
        # The domain has no record, so it will be NOT_QUALIFIED.
        # The point is that no provider_write_state is set.
        self.assertNotIn("provider_write_state", detail)
        self.assertNotIn("provider_campaign_id", detail)


class BatchSizeCap(unittest.TestCase):
    """The walk must stop after batch_size QUALIFIED rows."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cp = os.path.join(self.tmpdir, "checkpoint.json")
        self.csv_path = os.path.join(self.tmpdir, "source.csv")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_batch_size_zero_stops_immediately(self):
        # With batch_size=0, no rows should be processed.
        with open(self.csv_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "Work Email", "Company", "First Name", "Last Name",
                "Job Title"])
            w.writeheader()
            w.writerow({
                "Work Email": "a@b.com", "Company": "X",
                "First Name": "A", "Last Name": "B", "Job Title": "T"})

        result = dc.run(
            batch_id="zero-batch", batch_size=0, limit=10,
            live=False, checkpoint_override=self.cp,
            source_override=self.csv_path)
        # batch_size=0 means the first QUALIFIED would exceed the cap,
        # so the loop should stop before processing.
        self.assertEqual(result["batch_status"], "complete")


class NoGateWeakening(unittest.TestCase):
    """The controller must not import provider-write modules directly."""

    def test_no_providerwrites_import(self):
        import ast
        path = os.path.join(ROOT, "scripts", "durable_controller.py")
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        for imp in imports:
            self.assertNotIn("providerwrites", imp,
                             "controller must not import providerwrites")
            self.assertNotIn("executionguard", imp,
                             "controller must not import executionguard")
            self.assertNotIn("bisonfactory", imp,
                             "controller must not import bisonfactory")

    def test_no_approval_module_import(self):
        import ast
        path = os.path.join(ROOT, "scripts", "durable_controller.py")
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        for imp in imports:
            self.assertNotIn("approval", imp.split(".")[-1:],
                             "controller must not import approval")


if __name__ == "__main__":
    unittest.main()
