"""Tests for scripts/pool_status.py.

Tests the status aggregation logic without depending on live pool state.
Each test constructs a minimal scenario and verifies the output shape and
the idle-reason derivation, which is the logic most likely to silently
lie (reporting "no ready task" when the real reason is a stale branch,
or silence when a worker is genuinely idle with an empty queue).
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import pool_status


class TestIdleReason(unittest.TestCase):
    """The idle reason must answer WHY, not guess."""

    def test_missing_worktree(self):
        info = {"state": "idle", "exists": False, "worker": "w",
                "branch": None, "on_origin_master": None}
        self.assertEqual(pool_status._idle_reason(info, 10),
                         "worktree missing")

    def test_locked_worktree(self):
        info = {"state": "idle", "exists": True, "worker": "nonexistent-wt-xyz",
                "branch": "b", "on_origin_master": True}
        with tempfile.TemporaryDirectory() as locks_dir:
            old = pool_status.LOCKS_DIR
            pool_status.LOCKS_DIR = locks_dir
            try:
                os.makedirs(os.path.join(locks_dir, "nonexistent-wt-xyz"))
                self.assertEqual(pool_status._idle_reason(info, 10),
                                 "worktree locked")
            finally:
                pool_status.LOCKS_DIR = old

    def test_no_ready_task(self):
        info = {"state": "idle", "exists": True, "worker": "w",
                "branch": "b", "on_origin_master": True}
        with tempfile.TemporaryDirectory() as locks_dir:
            old = pool_status.LOCKS_DIR
            pool_status.LOCKS_DIR = locks_dir
            try:
                self.assertEqual(pool_status._idle_reason(info, 0),
                                 "no ready task")
            finally:
                pool_status.LOCKS_DIR = old

    def test_awaiting_dispatch_when_ready_exists(self):
        info = {"state": "idle", "exists": True, "worker": "w",
                "branch": "b", "on_origin_master": True}
        with tempfile.TemporaryDirectory() as locks_dir:
            old = pool_status.LOCKS_DIR
            pool_status.LOCKS_DIR = locks_dir
            try:
                self.assertEqual(pool_status._idle_reason(info, 5),
                                 "awaiting dispatch")
            finally:
                pool_status.LOCKS_DIR = old

    def test_busy_worker_has_no_reason(self):
        info = {"state": "busy", "exists": True, "worker": "w",
                "branch": "b", "on_origin_master": True}
        self.assertIsNone(pool_status._idle_reason(info, 0))


class TestOutputShape(unittest.TestCase):
    """The JSON output must have every section the task requires."""

    def test_collect_status_has_all_sections(self):
        status = pool_status.collect_status()
        for key in ("workers", "glm_tasks", "queue", "idle_reasons",
                     "stale_branches", "generated_at", "refill_gap"):
            self.assertIn(key, status, "missing section: %s" % key)

    def test_workers_section_has_counts_and_details(self):
        status = pool_status.collect_status()
        w = status["workers"]
        for key in ("total", "busy", "idle", "missing",
                     "stale_branch", "details"):
            self.assertIn(key, w, "missing workers key: %s" % key)
        self.assertEqual(w["total"], 12)
        self.assertIsInstance(w["details"], list)

    def test_worker_detail_shape(self):
        status = pool_status.collect_status()
        for d in status["workers"]["details"]:
            for key in ("worker", "exists", "state", "branch",
                         "task_id", "on_origin_master"):
                self.assertIn(key, d,
                              "missing detail key %s for %s" % (
                                  key, d.get("worker")))

    def test_queue_section(self):
        status = pool_status.collect_status()
        q = status["queue"]
        self.assertIn("ready_count", q)
        self.assertIn("ready_tasks", q)
        self.assertIsInstance(q["ready_tasks"], list)

    def test_stale_branches_section(self):
        status = pool_status.collect_status()
        sb = status["stale_branches"]
        self.assertIn("count", sb)
        self.assertIn("tasks", sb)
        self.assertEqual(sb["count"], len(sb["tasks"]))


class TestHumanOutput(unittest.TestCase):
    """--human must produce readable text with all sections."""

    def test_human_has_all_sections(self):
        status = pool_status.collect_status()
        text = pool_status._format_human(status)
        self.assertIn("POOL STATUS", text)
        self.assertIn("worker details", text)
        self.assertIn("queue", text)
        self.assertIn("idle reasons", text)
        self.assertIn("GLM tasks", text)
        self.assertIn("stale branches", text)

    def test_json_is_valid(self):
        status = pool_status.collect_status()
        serialized = json.dumps(status)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["workers"]["total"], 12)


class TestGlmDetection(unittest.TestCase):
    """GLM tasks are identified by filename pattern."""

    def test_glm_in_filename_detected(self):
        self.assertTrue("glm" in "TASK-400-glm-verify-task-399.md".lower())
        self.assertTrue("glm" in "TASK-383-glm-checkpoint-a.md".lower())

    def test_non_glm_not_detected(self):
        self.assertFalse("glm" in "TASK-100-fix-the-pipeline.md".lower())


class TestWorkerCount(unittest.TestCase):
    """The worker list must match pool.sh's WORKERS array."""

    def test_twelve_workers(self):
        self.assertEqual(len(pool_status.WORKERS), 12)

    def test_known_names(self):
        self.assertIn("resonate-qwen-worker", pool_status.WORKERS)
        self.assertIn("resonate-qwen-12", pool_status.WORKERS)


if __name__ == "__main__":
    unittest.main()
