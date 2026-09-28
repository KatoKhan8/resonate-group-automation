"""Every APPROVED file feeds work/training/; nothing else does.

TASK-310. The capture is urgent because a pair not written when the file is
approved is gone for good. Approval is the only moment the ground truth
exists.

These tests prove:
- A pair IS written when approval carries training data.
- A pair is NOT written when approval has no training data.
- Held leads are captured separately as negative examples.
- ``training.count()`` returns the right numbers.
- The acceptance command works end-to-end.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import reviewapproval, store, training


class TestTrainingCapture(unittest.TestCase):
    """A pair is written on approval and NOT written without one."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-training-")
        self.addCleanup(store.use_directory(self.tmp))

    def _pairs_file(self):
        return os.path.join(self.tmp, "training", "pairs.jsonl")

    def _held_file(self):
        return os.path.join(self.tmp, "training", "held.jsonl")

    def _read_jsonl(self, path):
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    # ------------------------------------------------------------------
    # The load-bearing test: approval with training data writes a pair.
    # ------------------------------------------------------------------

    def test_approval_with_training_data_writes_a_pair(self):
        """The one thing this task must prove: capture at approval."""
        pair = {
            "input": {"facts": ["fact 1", "fact 2"],
                      "angle": "margin erosion",
                      "persona": "agency owner",
                      "company_hook": "15-person shop",
                      "lead_role": "CTO"},
            "output": {"subject": "Your utilised margin",
                       "em1": "Hi John, I noticed your team...",
                       "linkedin_connect": "Wanted to reach out...",
                       "linkedin_msg1": "Thanks for connecting..."},
        }
        reviewapproval.record(
            campaign="493", review_hash="abc123", by="zvonimir",
            training_pairs=[pair])

        rows = self._read_jsonl(self._pairs_file())
        self.assertEqual(len(rows), 1,
                         "exactly one pair should be written on approval")
        self.assertEqual(rows[0]["input"]["angle"], "margin erosion")
        self.assertEqual(rows[0]["output"]["subject"], "Your utilised margin")

    # ------------------------------------------------------------------
    # The other half: approval WITHOUT training data writes nothing.
    # ------------------------------------------------------------------

    def test_approval_without_training_data_writes_nothing(self):
        """A pair not written at approval is gone. But if no data is given,
        there is nothing to write, and the file must not be created."""
        reviewapproval.record(
            campaign="493", review_hash="abc123", by="zvonimir")

        self.assertFalse(os.path.exists(self._pairs_file()),
                         "no training file should exist without training data")

    def test_approval_with_empty_lists_writes_nothing(self):
        """Empty lists are the same as no data."""
        reviewapproval.record(
            campaign="493", review_hash="abc123", by="zvonimir",
            training_pairs=[], training_held=[])

        self.assertFalse(os.path.exists(self._pairs_file()))
        self.assertFalse(os.path.exists(self._held_file()))

    # ------------------------------------------------------------------
    # Held leads as negative examples.
    # ------------------------------------------------------------------

    def test_held_leads_are_captured_separately(self):
        """Held leads go to a different file from approved pairs."""
        held = [{"facts": ["fact 1"], "hold_reason": "address not cleared",
                 "company": "Acme"}]
        pair = {
            "input": {"facts": ["fact 2"], "angle": "growth"},
            "output": {"subject": "Scaling", "em1": "Hi..."},
        }
        reviewapproval.record(
            campaign="493", review_hash="abc123", by="zvonimir",
            training_pairs=[pair], training_held=held)

        pairs = self._read_jsonl(self._pairs_file())
        held_rows = self._read_jsonl(self._held_file())
        self.assertEqual(len(pairs), 1)
        self.assertEqual(len(held_rows), 1)
        self.assertEqual(held_rows[0]["hold_reason"], "address not cleared")

    # ------------------------------------------------------------------
    # The counter the operator watches.
    # ------------------------------------------------------------------

    def test_count_returns_pairs_and_held(self):
        """The acceptance command: ``training.count()``."""
        pair = {"input": {"facts": []}, "output": {"subject": "Test"}}
        held = {"facts": [], "hold_reason": "no address"}

        reviewapproval.record(
            campaign="493", review_hash="h1", by="zvonimir",
            training_pairs=[pair])
        reviewapproval.record(
            campaign="489", review_hash="h2", by="zvonimir",
            training_pairs=[pair], training_held=[held])

        c = training.count()
        self.assertEqual(c["pairs"], 2)
        self.assertEqual(c["held"], 1)
        self.assertEqual(c["total"], 3)
        self.assertEqual(c["target"], 5000)

    def test_count_with_no_files_returns_zero(self):
        """Before any approval, the counter reads zero."""
        c = training.count()
        self.assertEqual(c["pairs"], 0)
        self.assertEqual(c["held"], 0)
        self.assertEqual(c["total"], 0)

    # ------------------------------------------------------------------
    # The acceptance command itself.
    # ------------------------------------------------------------------

    def test_acceptance_command(self):
        """``py -3 -c "import sys;sys.path.insert(0,'.');from src import
        training;print(training.count())"`` must work."""
        pair = {"input": {"facts": ["f1"]}, "output": {"subject": "Hi"}}
        reviewapproval.record(
            campaign="493", review_hash="abc", by="zvonimir",
            training_pairs=[pair])

        result = training.count()
        self.assertIsInstance(result, dict)
        self.assertIn("pairs", result)
        self.assertGreaterEqual(result["pairs"], 1)

    # ------------------------------------------------------------------
    # Append-only, never rewritten.
    # ------------------------------------------------------------------

    def test_pairs_are_append_only(self):
        """Two approvals write two pairs; the first is not overwritten."""
        pair1 = {"input": {"n": 1}, "output": {"subject": "First"}}
        pair2 = {"input": {"n": 2}, "output": {"subject": "Second"}}

        reviewapproval.record(
            campaign="493", review_hash="h1", by="zvonimir",
            training_pairs=[pair1])
        reviewapproval.record(
            campaign="489", review_hash="h2", by="zvonimir",
            training_pairs=[pair2])

        rows = self._read_jsonl(self._pairs_file())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["output"]["subject"], "First")
        self.assertEqual(rows[1]["output"]["subject"], "Second")

    # ------------------------------------------------------------------
    # Validation.
    # ------------------------------------------------------------------

    def test_pair_without_input_is_rejected(self):
        """A pair must have an 'input' key."""
        with self.assertRaises(ValueError):
            training.write_pair({"output": {"subject": "no input"}})

    def test_pair_without_output_is_rejected(self):
        """A pair must have an 'output' key."""
        with self.assertRaises(ValueError):
            training.write_pair({"input": {"facts": []}})

    def test_pair_must_be_a_dict(self):
        """A pair must be a dict, not a string or list."""
        with self.assertRaises(TypeError):
            training.write_pair("not a dict")


class TestTrainingPathIsolation(unittest.TestCase):
    """The TRAINING env override moves the training directory."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-training-iso-")
        self.addCleanup(store.use_directory(self.tmp))

    def test_training_dir_follows_queue(self):
        """``use_directory`` moves the training dir with the queue."""
        expected = os.path.join(self.tmp, "training")
        self.assertEqual(os.path.dirname(training.pairs_path()), expected)

    def test_training_env_override(self):
        """An explicit TRAINING env var takes precedence."""
        import tempfile as tf
        custom = tf.mkdtemp(prefix="rga-training-custom-")
        os.environ["TRAINING"] = custom
        try:
            self.assertEqual(os.path.dirname(training.pairs_path()), custom)
        finally:
            os.environ.pop("TRAINING", None)


if __name__ == "__main__":
    unittest.main()
