"""The minimum durable controller: checkpoint, duplicate protection, restart.

The kill-and-restart test is the one that matters: start the controller,
process some rows, interrupt it, restart it, and prove that no row was
enrolled twice and no source position was lost.
"""
import csv
import json
import os
import shutil
import tempfile
import unittest

from src import durablecontroller as dc, store


class _ControllerTest(unittest.TestCase):
    """Isolated temp directory for every test."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-ctrl-test-")
        self._prev = {}
        for k in ("QUEUE", "CONTROLLER_CHECKPOINT", "OUT"):
            self._prev[k] = os.environ.get(k)
        os.environ["QUEUE"] = os.path.join(self.tmp, "work", "queue.jsonl")
        os.environ["CONTROLLER_CHECKPOINT"] = os.path.join(
            self.tmp, "work", "controller_checkpoint.json")
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        os.makedirs(os.path.join(self.tmp, "work"), exist_ok=True)

    def tearDown(self):
        for k, v in self._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_csv(self, rows):
        """Write a CSV with the columns canary_candidate_walk.assess expects."""
        path = os.path.join(self.tmp, "source.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "Work Email", "Company", "First Name", "Last Name",
                "Job Title"])
            w.writeheader()
            for row in rows:
                w.writerow(row)
        return path

    def _load_cp(self):
        return dc.load_checkpoint()


class TestCheckpointPersistence(_ControllerTest):

    def test_empty_checkpoint_has_correct_shape(self):
        cp = dc.load_checkpoint()
        self.assertEqual(cp["version"], dc.CHECKPOINT_VERSION)
        self.assertEqual(cp["source_position"], 0)
        self.assertIsNone(cp["batch_id"])
        self.assertIsNone(cp["batch_state"])
        self.assertEqual(cp["enrolled"], {})

    def test_save_and_reload(self):
        cp = dc._empty_checkpoint()
        cp["batch_id"] = "batch-test-001"
        cp["batch_state"] = dc.BATCH_RUNNING
        cp["source_position"] = 5
        cp["enrolled"]["3"] = {
            "record_id": "rec-abc",
            "disposition": dc.DISPOSITION_QUALIFIED,
            "reason": "cleared all gates",
            "approval_hash": "hash123",
            "provider_campaign_id": "camp-1",
            "write_state": dc.WRITE_PENDING,
        }
        dc.save_checkpoint(cp)
        loaded = dc.load_checkpoint()
        self.assertEqual(loaded["batch_id"], "batch-test-001")
        self.assertEqual(loaded["source_position"], 5)
        self.assertIn("3", loaded["enrolled"])
        self.assertEqual(loaded["enrolled"]["3"]["record_id"], "rec-abc")

    def test_corrupt_checkpoint_is_treated_as_empty(self):
        path = dc.checkpoint_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("not json at all")
        cp = dc.load_checkpoint()
        self.assertEqual(cp["source_position"], 0)
        self.assertIsNone(cp["batch_id"])

    def test_wrong_version_is_treated_as_empty(self):
        path = dc.checkpoint_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"version": 999, "source_position": 50}, f)
        cp = dc.load_checkpoint()
        self.assertEqual(cp["source_position"], 0)


class TestDuplicateProtection(_ControllerTest):

    def test_is_duplicate(self):
        cp = dc._empty_checkpoint()
        self.assertFalse(dc.is_duplicate(cp, 1))
        cp["enrolled"]["1"] = {"record_id": "rec-1", "disposition": "QUALIFIED"}
        self.assertTrue(dc.is_duplicate(cp, 1))
        self.assertFalse(dc.is_duplicate(cp, 2))

    def test_enrolled_record_id(self):
        cp = dc._empty_checkpoint()
        self.assertIsNone(dc.enrolled_record_id(cp, 1))
        cp["enrolled"]["1"] = {"record_id": "rec-1"}
        self.assertEqual(dc.enrolled_record_id(cp, 1), "rec-1")

    def test_write_state(self):
        cp = dc._empty_checkpoint()
        self.assertIsNone(dc.write_state(cp, 1))
        cp["enrolled"]["1"] = {"write_state": dc.WRITE_PENDING}
        self.assertEqual(dc.write_state(cp, 1), dc.WRITE_PENDING)

    def test_update_write_state(self):
        cp = dc._empty_checkpoint()
        cp["enrolled"]["1"] = {"write_state": dc.WRITE_PENDING}
        dc.save_checkpoint(cp)
        dc.update_write_state(1, dc.WRITE_PERFORMED)
        loaded = dc.load_checkpoint()
        self.assertEqual(loaded["enrolled"]["1"]["write_state"],
                         dc.WRITE_PERFORMED)

    def test_update_write_state_refuses_unknown_state(self):
        cp = dc._empty_checkpoint()
        cp["enrolled"]["1"] = {"write_state": dc.WRITE_PENDING}
        dc.save_checkpoint(cp)
        with self.assertRaises(ValueError):
            dc.update_write_state(1, "bogus")

    def test_update_write_state_refuses_unenrolled_row(self):
        cp = dc._empty_checkpoint()
        dc.save_checkpoint(cp)
        with self.assertRaises(KeyError):
            dc.update_write_state(99, dc.WRITE_PERFORMED)


class TestKillAndRestart(_ControllerTest):
    """The test that matters: interrupt, restart, no duplicates."""

    def _assess_all_qualified(self, row):
        return dc.DISPOSITION_QUALIFIED, "cleared all gates", {}

    def _assess_alternating(self, row):
        email = (row.get("Work Email") or "").strip()
        if "qualified" in email:
            return dc.DISPOSITION_QUALIFIED, "cleared", {}
        if "held" in email:
            return dc.DISPOSITION_HELD, "held for reason", {}
        return dc.DISPOSITION_NOT_QUALIFIED, "no email", {}

    def test_restart_does_not_re_enrol(self):
        """Kill after 3 rows, restart, prove rows 1-3 are not re-processed."""
        rows = [
            {"Work Email": "qualified@test.com", "Company": "Acme",
             "First Name": "A", "Last Name": "B", "Job Title": "CEO"},
            {"Work Email": "qualified@test2.com", "Company": "Beta",
             "First Name": "C", "Last Name": "D", "Job Title": "CTO"},
            {"Work Email": "qualified@test3.com", "Company": "Gamma",
             "First Name": "E", "Last Name": "F", "Job Title": "CFO"},
            {"Work Email": "qualified@test4.com", "Company": "Delta",
             "First Name": "G", "Last Name": "H", "Job Title": "COO"},
            {"Work Email": "qualified@test5.com", "Company": "Epsilon",
             "First Name": "I", "Last Name": "J", "Job Title": "VP"},
        ]
        csv_path = self._write_csv(rows)
        enrolled_ids = []

        def enroll(row, source_row, detail):
            rid = "rec-%d" % source_row
            enrolled_ids.append(rid)
            return rid

        ctrl = dc.Controller(csv_path, live=True,
                             assess_fn=self._assess_all_qualified,
                             enroll_fn=enroll)
        result1 = ctrl.run(limit=3)
        self.assertEqual(result1["counts"]["assessed"], 3)
        self.assertEqual(result1["counts"]["enrolled"], 3)
        self.assertEqual(len(enrolled_ids), 3)

        cp_after_first = dc.load_checkpoint()
        self.assertEqual(cp_after_first["source_position"], 3)

        enrolled_ids.clear()
        ctrl2 = dc.Controller(csv_path, live=True,
                              assess_fn=self._assess_all_qualified,
                              enroll_fn=enroll)
        result2 = ctrl2.run()
        self.assertEqual(result2["counts"]["assessed"], 2)
        self.assertEqual(result2["counts"]["enrolled"], 2)
        self.assertEqual(result2["counts"]["skipped_duplicate"], 0)
        self.assertEqual(len(enrolled_ids), 2)

        final_cp = dc.load_checkpoint()
        self.assertEqual(final_cp["source_position"], 5)
        self.assertEqual(final_cp["batch_state"], dc.BATCH_COMPLETE)
        self.assertEqual(len(final_cp["enrolled"]), 5)

        all_record_ids = {
            final_cp["enrolled"][str(i)]["record_id"] for i in range(1, 6)}
        self.assertEqual(len(all_record_ids), 5)

    def test_restart_after_interrupt_resumes_from_checkpoint(self):
        """Simulate an interrupt mid-batch and prove resumption."""
        rows = [
            {"Work Email": "a@test.com", "Company": "A",
             "First Name": "A", "Last Name": "A", "Job Title": "A"},
            {"Work Email": "b@test.com", "Company": "B",
             "First Name": "B", "Last Name": "B", "Job Title": "B"},
            {"Work Email": "c@test.com", "Company": "C",
             "First Name": "C", "Last Name": "C", "Job Title": "C"},
        ]
        csv_path = self._write_csv(rows)

        ctrl = dc.Controller(csv_path, live=False,
                             assess_fn=self._assess_all_qualified)
        ctrl.run(limit=2)

        cp = dc.load_checkpoint()
        self.assertEqual(cp["source_position"], 2)
        self.assertEqual(cp["batch_state"], dc.BATCH_RUNNING)

        ctrl2 = dc.Controller(csv_path, live=False,
                              assess_fn=self._assess_all_qualified)
        result = ctrl2.run()
        self.assertEqual(result["counts"]["assessed"], 1)
        final_cp = dc.load_checkpoint()
        self.assertEqual(final_cp["source_position"], 3)
        self.assertEqual(final_cp["batch_state"], dc.BATCH_COMPLETE)

    def test_completed_batch_is_not_re_run(self):
        """A completed batch refuses to run again."""
        rows = [
            {"Work Email": "a@test.com", "Company": "A",
             "First Name": "A", "Last Name": "A", "Job Title": "A"},
        ]
        csv_path = self._write_csv(rows)
        ctrl = dc.Controller(csv_path, live=False,
                             assess_fn=self._assess_all_qualified)
        ctrl.run()
        cp = dc.load_checkpoint()
        self.assertEqual(cp["batch_state"], dc.BATCH_COMPLETE)

        ctrl2 = dc.Controller(csv_path, live=False,
                              assess_fn=self._assess_all_qualified)
        result = ctrl2.run()
        self.assertEqual(result["status"], "already_complete")

    def test_held_rows_are_recorded_but_not_enrolled(self):
        """HELD rows get a checkpoint entry but no record_id."""
        rows = [
            {"Work Email": "held@test.com", "Company": "A",
             "First Name": "A", "Last Name": "A", "Job Title": "A"},
            {"Work Email": "qualified@test.com", "Company": "B",
             "First Name": "B", "Last Name": "B", "Job Title": "B"},
        ]
        csv_path = self._write_csv(rows)
        ctrl = dc.Controller(csv_path, live=False,
                             assess_fn=self._assess_alternating)
        result = ctrl.run()
        self.assertEqual(result["counts"]["held"], 1)
        self.assertEqual(result["counts"]["qualified"], 1)
        cp = dc.load_checkpoint()
        self.assertEqual(cp["enrolled"]["1"]["disposition"], dc.DISPOSITION_HELD)
        self.assertIsNone(cp["enrolled"]["1"]["record_id"])
        self.assertEqual(cp["enrolled"]["2"]["disposition"],
                         dc.DISPOSITION_QUALIFIED)
        self.assertIsNotNone(cp["enrolled"]["2"]["record_id"])


class TestNoGateWeakening(_ControllerTest):
    """The controller wires state, not policy. Prove it does not touch gates."""

    def test_controller_does_not_import_gate_modules(self):
        """The controller module does not import approval, killswitch,
        executionguard, or providerwrites directly. It wires through them."""
        import importlib
        mod = importlib.import_module("src.durablecontroller")
        source_file = mod.__file__
        with open(source_file, encoding="utf-8") as f:
            source = f.read()
        for gate_mod in ("approval", "killswitch", "executionguard",
                         "providerwrites"):
            self.assertNotIn(
                "from . import %s" % gate_mod, source,
                "controller imports %s directly - it should wire through "
                "existing paths, not open a second door" % gate_mod)
            self.assertNotIn(
                "import %s" % gate_mod, source,
                "controller imports %s directly" % gate_mod)

    def test_controller_does_not_weaken_store_transaction(self):
        """The controller uses store.transaction for queue mutations, not
        a bare save or direct file write."""
        import importlib
        mod = importlib.import_module("src.durablecontroller")
        source_file = mod.__file__
        with open(source_file, encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("store.save(", source,
                         "controller calls store.save directly instead of "
                         "using store.transaction")

    def test_dry_by_default(self):
        """The controller is dry by default. live=False means no enrollment."""
        rows = [
            {"Work Email": "a@test.com", "Company": "A",
             "First Name": "A", "Last Name": "A", "Job Title": "A"},
        ]
        csv_path = self._write_csv(rows)
        enroll_called = []

        def enroll(row, source_row, detail):
            enroll_called.append(source_row)
            return "rec-live"

        ctrl = dc.Controller(csv_path, live=False,
                             assess_fn=self._assess_all_qualified,
                             enroll_fn=enroll)
        ctrl.run()
        self.assertEqual(enroll_called, [],
                         "dry run called enroll_fn - it should not")

    def test_live_permits_enrollment(self):
        """live=True delegates to the enroll_fn."""
        rows = [
            {"Work Email": "a@test.com", "Company": "A",
             "First Name": "A", "Last Name": "A", "Job Title": "A"},
        ]
        csv_path = self._write_csv(rows)
        enroll_called = []

        def enroll(row, source_row, detail):
            enroll_called.append(source_row)
            return "rec-live"

        ctrl = dc.Controller(csv_path, live=True,
                             assess_fn=self._assess_all_qualified,
                             enroll_fn=enroll)
        ctrl.run()
        self.assertEqual(enroll_called, [1])

    def _assess_all_qualified(self, row):
        return dc.DISPOSITION_QUALIFIED, "cleared all gates", {}


class TestSlackNotifications(_ControllerTest):

    def test_notifications_are_sent(self):
        """The controller sends operational events via the notify_fn."""
        rows = [
            {"Work Email": "a@test.com", "Company": "A",
             "First Name": "A", "Last Name": "A", "Job Title": "A"},
        ]
        csv_path = self._write_csv(rows)
        events = []

        def capture(event_type, fields):
            events.append((event_type, fields))

        def assess(row):
            return dc.DISPOSITION_QUALIFIED, "ok", {}

        ctrl = dc.Controller(csv_path, live=False,
                             assess_fn=assess, notify_fn=capture)
        ctrl.run()
        event_types = [e[0] for e in events]
        self.assertIn("controller_batch_started", event_types)
        self.assertIn("controller_batch_complete", event_types)

    def test_notify_is_optional(self):
        """The controller works without a notify_fn."""
        rows = [
            {"Work Email": "a@test.com", "Company": "A",
             "First Name": "A", "Last Name": "A", "Job Title": "A"},
        ]
        csv_path = self._write_csv(rows)

        def assess(row):
            return dc.DISPOSITION_QUALIFIED, "ok", {}

        ctrl = dc.Controller(csv_path, live=False, assess_fn=assess)
        result = ctrl.run()
        self.assertEqual(result["status"], "complete")


if __name__ == "__main__":
    unittest.main()
