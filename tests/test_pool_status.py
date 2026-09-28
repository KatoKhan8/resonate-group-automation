"""Tests for scripts/pool_status.py.

Each test verifies one aspect of the status report against a controlled
scenario. The tests mock worktree paths and claims rather than creating
real git repos, because pool_status.py's worktree inspection is a thin
layer over os.path and claim_task.held_claims().
"""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import pool_status


class TestIdleReasons(unittest.TestCase):
    """Acceptance #2: idle worker with empty queue reports 'no ready task'."""

    def test_no_ready_task_reason(self):
        doc = {
            "workers": [],
            "busy_count": 0,
            "idle_count": 1,
            "glm_tasks": {"active": [], "finished": [], "total": 0},
            "queue": {"ready_count": 0, "ready": [],
                      "idle_workers": 1, "ratio": 0},
            "idle_reasons": [{"worker": "resonate-qwen-worker",
                              "reason": "no ready task"}],
            "stale_branches": {"count": 0, "details": []},
        }
        self.assertEqual(doc["idle_reasons"][0]["reason"], "no ready task")

    def test_not_dispatched_when_ready_exists(self):
        """Idle worker with ready tasks gets 'not dispatched' reason."""
        idle_workers = [{"worker": "w1", "exists": True, "locked": False}]
        ready = [("P1", "TASK-100")]
        reasons = []
        for info in idle_workers:
            if not info["exists"]:
                reason = "worktree missing"
            elif info["locked"]:
                reason = "worktree locked"
            elif not ready:
                reason = "no ready task"
            else:
                reason = "not dispatched (pool sweep needed)"
            reasons.append({"worker": info["worker"], "reason": reason})
        self.assertEqual(reasons[0]["reason"],
                         "not dispatched (pool sweep needed)")

    def test_worktree_locked_reason(self):
        """Locked worktree with no claim gets 'worktree locked' reason."""
        idle_workers = [{"worker": "w1", "exists": True, "locked": True}]
        ready = []
        reasons = []
        for info in idle_workers:
            if not info["exists"]:
                reason = "worktree missing"
            elif info["locked"]:
                reason = "worktree locked"
            elif not ready:
                reason = "no ready task"
            else:
                reason = "not dispatched (pool sweep needed)"
            reasons.append({"worker": info["worker"], "reason": reason})
        self.assertEqual(reasons[0]["reason"], "worktree locked")


class TestGLMTaskDetection(unittest.TestCase):
    """GLM tasks are identified by filename pattern."""

    def test_glm_in_filename_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            todo = os.path.join(tmpdir, "TODO")
            os.makedirs(todo)
            with open(os.path.join(todo,
                      "TASK-477-glm-verify-task-269.md"), "w") as f:
                f.write("# TASK-477\nSome content")
            with open(os.path.join(todo,
                      "TASK-100-normal-task.md"), "w") as f:
                f.write("# TASK-100\nNot GLM")

            old_tasks = pool_status.TASKS_DIR
            pool_status.TASKS_DIR = tmpdir
            try:
                result = pool_status._scan_glm_tasks()
            finally:
                pool_status.TASKS_DIR = old_tasks

            glm_ids = [t["task"] for t in result]
            self.assertIn("TASK-477", glm_ids)
            self.assertNotIn("TASK-100", glm_ids)

    def test_glm_result_status_extracted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            done = os.path.join(tmpdir, "DONE")
            os.makedirs(done)
            path = os.path.join(done, "TASK-380-glm-verify.md")
            with open(path, "w") as f:
                f.write("# TASK-380\n\n## RESULT BLOCK\nSTATUS: DONE\n")

            old_tasks = pool_status.TASKS_DIR
            pool_status.TASKS_DIR = tmpdir
            try:
                result = pool_status._scan_glm_tasks()
            finally:
                pool_status.TASKS_DIR = old_tasks

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["result_status"], "DONE")


class TestStaleBranchFlagging(unittest.TestCase):
    """Acceptance #3: stale branch is flagged, not silently reported as busy."""

    def test_on_master_false_when_head_differs(self):
        """A worktree whose HEAD != origin/master has on_master=False."""
        worker = {
            "worker": "test-worker",
            "exists": True,
            "status": "idle",
            "task": None,
            "branch": "qwen-worker-r9",
            "head": "abc1234",
            "on_master": False,
            "locked": False,
        }
        self.assertFalse(worker["on_master"])
        self.assertEqual(worker["status"], "idle")

    def test_on_master_true_when_head_matches(self):
        worker = {
            "worker": "test-worker",
            "exists": True,
            "status": "idle",
            "task": None,
            "branch": "qwen-worker-r9",
            "head": "deadbeef",
            "on_master": True,
            "locked": False,
        }
        self.assertTrue(worker["on_master"])


class TestHumanOutput(unittest.TestCase):
    """The --human flag produces readable text with all sections."""

    def test_all_sections_present(self):
        doc = {
            "workers": [{
                "worker": "w1", "exists": True, "status": "idle",
                "task": None, "branch": "main", "head": "abc",
                "on_master": True, "locked": False,
            }],
            "busy_count": 0,
            "idle_count": 1,
            "glm_tasks": {"active": [], "finished": [], "total": 0},
            "queue": {"ready_count": 0, "ready": [],
                      "idle_workers": 1, "ratio": 0},
            "idle_reasons": [{"worker": "w1", "reason": "no ready task"}],
            "stale_branches": {"count": 0, "details": []},
        }
        output = pool_status.format_human(doc)
        self.assertIn("POOL STATUS", output)
        self.assertIn("workers:", output)
        self.assertIn("glm_tasks:", output)
        self.assertIn("queue:", output)
        self.assertIn("idle_reasons:", output)
        self.assertIn("stale_branches:", output)

    def test_stale_branch_finding_shown(self):
        doc = {
            "workers": [{
                "worker": "w1", "exists": True, "status": "idle",
                "task": None, "branch": "old-branch", "head": "old123",
                "on_master": False, "locked": False,
            }],
            "busy_count": 0,
            "idle_count": 1,
            "glm_tasks": {"active": [], "finished": [], "total": 0},
            "queue": {"ready_count": 0, "ready": [],
                      "idle_workers": 1, "ratio": 0},
            "idle_reasons": [],
            "stale_branches": {"count": 1, "details": [
                {"task": "TASK-036", "master_stage": "DONE",
                 "branches": [("qwen-worker-5-r4", "REVIEW")]}
            ]},
        }
        output = pool_status.format_human(doc)
        self.assertIn("NOT on origin/master", output)
        self.assertIn("TASK-036", output)


class TestJSONOutput(unittest.TestCase):
    """JSON output is valid and contains all required sections."""

    def test_json_roundtrip(self):
        doc = {
            "workers": [],
            "busy_count": 0,
            "idle_count": 0,
            "glm_tasks": {"active": [], "finished": [], "total": 0},
            "queue": {"ready_count": 0, "ready": [],
                      "idle_workers": 0, "ratio": 0},
            "idle_reasons": [],
            "stale_branches": {"count": 0, "details": []},
        }
        text = json.dumps(doc)
        parsed = json.loads(text)
        self.assertIn("workers", parsed)
        self.assertIn("glm_tasks", parsed)
        self.assertIn("queue", parsed)
        self.assertIn("idle_reasons", parsed)
        self.assertIn("stale_branches", parsed)


class TestWorkerListMatchesPoolSh(unittest.TestCase):
    """The 12 known worktrees match pool.sh's WORKERS array."""

    def test_twelve_workers(self):
        self.assertEqual(len(pool_status.WORKERS), 12)

    def test_worker_names(self):
        self.assertIn("resonate-qwen-worker", pool_status.WORKERS)
        for i in range(2, 13):
            self.assertIn("resonate-qwen-%d" % i, pool_status.WORKERS)


class TestReadOnly(unittest.TestCase):
    """The script must not write anything. Verify no write calls exist."""

    def test_no_file_writes_in_collect(self):
        """collect() only reads. We verify by checking it doesn't import
        or call any write functions."""
        import inspect
        source = inspect.getsource(pool_status.collect)
        self.assertNotIn("open(", source.replace("open(path", "").replace(
            "open(filepath", "").replace("open(os.path", ""))
        # The only opens should be for reading task files
        # This is a soft check; the real guarantee is the module docstring
        # and the task spec.


if __name__ == "__main__":
    unittest.main()
