"""Every APPROVED file feeds work/training/; drafts do not.

TASK-310. The capture is urgent because a pair not written when the file is
approved is gone for good. Approval is the only moment the ground truth
exists.

Two things are proved:
  1. A pair IS written when reviewapproval.record receives pairs.
  2. NO pair is written when reviewapproval.record receives no pairs
     (the approval still succeeds - the capture is best-effort).
  3. training.count() returns the number of approved pairs.
  4. Held leads are captured separately.
  5. A malformed pair does not prevent the approval from succeeding.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import reviewapproval, training, store               # noqa: E402


class _TrainingCaptureTestBase(unittest.TestCase):
    """Each test gets its own temp work/ directory.

    training and reviewapproval both resolve paths through store.queue_path,
    so pointing QUEUE at a temp file moves everything.
    """

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="training-test-")
        self._old_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = os.path.join(self._tmp, "queue.jsonl")
        # Ensure the work directory exists so reviewapproval can write
        os.makedirs(self._tmp, exist_ok=True)

    def tearDown(self):
        if self._old_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._old_queue
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _make_pair(self, review_hash="abc123", campaign="503"):
        return {
            "review_hash": review_hash,
            "campaign": campaign,
            "model": "sonnet",
            "confidence": 0.85,
            "approval": {"campaign": campaign, "review_hash": review_hash,
                         "by": "zvonimir"},
            "input": {"facts": ["fact 1", "fact 2"], "angle": "efficiency",
                      "persona": "ops-lead", "company": "Acme",
                      "lead_role": "CTO"},
            "output": {"subject": "Quick question", "body": "Hi..."},
        }


class TestPairIsWrittenOnApproval(_TrainingCaptureTestBase):

    def test_approval_with_pairs_writes_them(self):
        """The core invariant: approval produces training data."""
        pair = self._make_pair()
        reviewapproval.record("503", "abc123", by="zvonimir",
                              pairs=[pair])
        self.assertEqual(training.count(), 1)
        rows = training._read_all(training.pair_path())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["review_hash"], "abc123")
        self.assertEqual(rows[0]["campaign"], "503")
        self.assertEqual(rows[0]["output"]["subject"], "Quick question")

    def test_approval_without_pairs_writes_none(self):
        """An approval without pairs is still an approval, but no training.

        This is the normal path today: most approvals happen without the
        caller building pairs. The approval must succeed regardless.
        """
        reviewapproval.record("503", "abc123", by="zvonimir")
        self.assertEqual(training.count(), 0)
        self.assertFalse(os.path.exists(training.pair_path()))

    def test_multiple_pairs_from_one_approval(self):
        """A review file covers several leads; all become pairs."""
        pairs = [self._make_pair(campaign="503"),
                 self._make_pair(campaign="503")]
        reviewapproval.record("503", "abc123", by="zvonimir",
                              pairs=pairs)
        self.assertEqual(training.count(), 2)

    def test_count_reflects_all_approvals(self):
        """Two approvals, three pairs total."""
        reviewapproval.record("503", "abc123", by="zvonimir",
                              pairs=[self._make_pair()])
        reviewapproval.record("504", "def456", by="zvonimir",
                              pairs=[self._make_pair(review_hash="def456",
                                                     campaign="504"),
                                     self._make_pair(review_hash="def456",
                                                     campaign="504")])
        self.assertEqual(training.count(), 3)


class TestHeldLeadsCapturedSeparately(_TrainingCaptureTestBase):

    def test_held_examples_go_to_a_different_file(self):
        held = [{"review_hash": "abc123", "campaign": "503",
                 "input": {"facts": []}, "output": {},
                 "held_reason": "no supporting facts"}]
        reviewapproval.record("503", "abc123", by="zvonimir",
                              pairs=[self._make_pair()], held=held)
        self.assertEqual(training.count(), 1)
        self.assertEqual(training.held_count(), 1)
        self.assertTrue(os.path.exists(training.held_path()))
        self.assertTrue(os.path.exists(training.pair_path()))

    def test_held_only_no_pairs(self):
        """An approval with only held examples writes no pairs."""
        held = [{"review_hash": "abc123", "campaign": "503",
                 "input": {"facts": []}, "output": {}}]
        reviewapproval.record("503", "abc123", by="zvonimir",
                              held=held)
        self.assertEqual(training.count(), 0)
        self.assertEqual(training.held_count(), 1)


class TestMalformedPairDoesNotBreakApproval(_TrainingCaptureTestBase):

    def test_bad_pair_is_skipped_approval_succeeds(self):
        """The approval must never fail because a training row was bad."""
        bad_pair = {"review_hash": "abc123"}  # missing required fields
        good_pair = self._make_pair()
        reviewapproval.record("503", "abc123", by="zvonimir",
                              pairs=[bad_pair, good_pair])
        # The good pair was written, the bad one was skipped
        self.assertEqual(training.count(), 1)
        # The approval itself was recorded
        approvals = reviewapproval.load()
        self.assertEqual(len(approvals), 1)

    def test_non_dict_pair_is_skipped(self):
        reviewapproval.record("503", "abc123", by="zvonimir",
                              pairs=["not a dict", 42, None])
        self.assertEqual(training.count(), 0)


class TestCountCommand(unittest.TestCase):
    """The acceptance command from the task."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="training-test-")
        self._old_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = os.path.join(self._tmp, "queue.jsonl")

    def tearDown(self):
        if self._old_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._old_queue
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_count_returns_zero_when_no_pairs(self):
        self.assertEqual(training.count(), 0)

    def test_count_returns_correct_number(self):
        pair = {"review_hash": "abc", "campaign": "1",
                "approval": {}, "input": {}, "output": {}}
        training.write_pair(pair)
        training.write_pair(pair)
        self.assertEqual(training.count(), 2)


class TestProgressCounter(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="training-test-")
        self._old_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = os.path.join(self._tmp, "queue.jsonl")

    def tearDown(self):
        if self._old_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._old_queue
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_progress_shows_distance_to_target(self):
        p = training.progress()
        self.assertEqual(p["pairs"], 0)
        self.assertEqual(p["target"], training.FINE_TUNE_TARGET)
        self.assertEqual(p["remaining"], training.FINE_TUNE_TARGET)

    def test_progress_updates_after_write(self):
        pair = {"review_hash": "abc", "campaign": "1",
                "approval": {}, "input": {}, "output": {}}
        training.write_pair(pair)
        p = training.progress()
        self.assertEqual(p["pairs"], 1)
        self.assertEqual(p["remaining"], training.FINE_TUNE_TARGET - 1)


class TestAppendOnly(unittest.TestCase):
    """Pairs are never rewritten, only appended."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="training-test-")
        self._old_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = os.path.join(self._tmp, "queue.jsonl")

    def tearDown(self):
        if self._old_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._old_queue
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_writes_append_not_overwrite(self):
        pair_a = {"review_hash": "aaa", "campaign": "1",
                  "approval": {}, "input": {}, "output": {}}
        pair_b = {"review_hash": "bbb", "campaign": "2",
                  "approval": {}, "input": {}, "output": {}}
        training.write_pair(pair_a)
        training.write_pair(pair_b)
        rows = training._read_all(training.pair_path())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["review_hash"], "aaa")
        self.assertEqual(rows[1]["review_hash"], "bbb")


if __name__ == "__main__":
    unittest.main()
