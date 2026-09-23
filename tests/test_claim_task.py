"""Regression tests for scripts/claim_task.py branch-scan logic.

Each test creates a throwaway git clone with the directory structure and
commit history that reproduces a real incident. The incidents are named so
a future change cannot quietly undo the protection.

The tests exercise _classify_branch_tasks, _task_files_on, _last_touch_ts,
_format_stale_report and the backwards-compatible _claimed_on_a_branch
through their real entry points - not by constructing inputs by hand.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import claim_task


# This module exercises code that writes `os.environ` ITSELF - it sets git's author and committer dates to make a commit reproducible - so
# restoring only what the tests set is not enough. Measured 2026-09-23: it
# left GIT_AUTHOR_DATE and GIT_COMMITTER_DATE set for every module that ran afterwards.
#
# Module-level, because the writes happen inside the code under test rather
# than in any one setUp, and a module is responsible for the side effects of
# what it exercises.
_ENV_BEFORE_MODULE = None


def setUpModule():
    global _ENV_BEFORE_MODULE
    _ENV_BEFORE_MODULE = dict(os.environ)


def tearDownModule():
    from tests.envisolation import restore
    restore(_ENV_BEFORE_MODULE)


STAGES = ["TODO", "RUNNING", "REVIEW", "DONE", "REWORK", "BLOCKED",
          "BLOCKED_QUOTA"]


def _git(repo, *args, check=True, env_extra=None):
    env = None
    if env_extra:
        import copy
        env = copy.copy(os.environ)
        env.update(env_extra)
    r = subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True, text=True, timeout=30, env=env)
    if check and r.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (args, r.stderr))
    return r


class _TempRepo:
    """A throwaway git repo with docs/qwen-tasks/{STAGE}/ directories."""

    def __init__(self):
        self.path = tempfile.mkdtemp(prefix="claim_test_")
        _git(self.path, "init")
        _git(self.path, "config", "user.email", "test@test")
        _git(self.path, "config", "user.name", "Test")
        for stage in STAGES:
            os.makedirs(os.path.join(self.path, "docs", "qwen-tasks", stage),
                        exist_ok=True)
        os.makedirs(os.path.join(self.path, "work", "claims"), exist_ok=True)
        _git(self.path, "add", "-A")
        _git(self.path, "commit", "-m", "init", "--allow-empty")
        self._orig_main = claim_task.MAIN_REPO
        self._orig_claims = claim_task.CLAIMS
        self._orig_registry = claim_task.REGISTRY
        claim_task.MAIN_REPO = self.path
        claim_task.CLAIMS = os.path.join(self.path, "work", "claims")
        claim_task.REGISTRY = os.path.join(self.path, "docs", "state",
                                           "TASK-REGISTRY.json")
        self._ts = int(time.time())

    def _next_ts(self):
        self._ts += 2
        return str(self._ts)

    def _dated_commit(self, msg):
        ts = self._next_ts()
        date_str = "@%s +0000" % ts
        _git(self.path, "commit", "-m", msg, env_extra={
            "GIT_COMMITTER_DATE": date_str,
            "GIT_AUTHOR_DATE": date_str,
        })

    def close(self):
        claim_task.MAIN_REPO = self._orig_main
        claim_task.CLAIMS = self._orig_claims
        claim_task.REGISTRY = self._orig_registry
        shutil.rmtree(self.path, ignore_errors=True)

    def add_task(self, stage, task_id, slug="some-task"):
        fn = "%s-%s.md" % (task_id, slug)
        path = os.path.join(self.path, "docs", "qwen-tasks", stage, fn)
        with open(path, "w") as f:
            f.write("# %s\n" % task_id)
        _git(self.path, "add", "-A")
        self._dated_commit("add %s in %s" % (task_id, stage))

    def move_task(self, task_id, from_stage, to_stage, slug="some-task"):
        fn = "%s-%s.md" % (task_id, slug)
        src = os.path.join(self.path, "docs", "qwen-tasks", from_stage, fn)
        dst_dir = os.path.join(self.path, "docs", "qwen-tasks", to_stage)
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, fn)
        if os.path.exists(src):
            os.rename(src, dst)
        _git(self.path, "add", "-A")
        self._dated_commit("move %s %s->%s" % (task_id, from_stage, to_stage))

    def create_branch(self, name, from_ref="master"):
        _git(self.path, "branch", name, from_ref)

    def on_branch(self, name, fn):
        """Switch to *name*, run fn(), switch back. Commits inside fn are
        on the named branch."""
        _git(self.path, "checkout", name)
        try:
            fn()
        finally:
            _git(self.path, "checkout", "master")

    def move_on_branch(self, branch, task_id, from_stage, to_stage,
                       slug="some-task"):
        """Move a task file on a specific branch without switching HEAD."""
        fn = "%s-%s.md" % (task_id, slug)
        _git(self.path, "checkout", branch)
        try:
            src_full = os.path.join(self.path, "docs", "qwen-tasks",
                                    from_stage, fn)
            dst_full = os.path.join(self.path, "docs", "qwen-tasks",
                                    to_stage, fn)
            os.makedirs(os.path.dirname(dst_full), exist_ok=True)
            if os.path.exists(src_full):
                os.rename(src_full, dst_full)
            _git(self.path, "add", "-A")
            self._dated_commit(
                "branch %s: move %s %s->%s"
                % (branch, task_id, from_stage, to_stage))
        finally:
            _git(self.path, "checkout", "master")


class TestTaskFilesOn(unittest.TestCase):
    """The primitive that reads a ref's task layout."""

    def test_reads_stage_and_task_id(self):
        repo = _TempRepo()
        try:
            repo.add_task("TODO", "TASK-200", "alpha")
            repo.add_task("RUNNING", "TASK-201", "beta")
            files = claim_task._task_files_on("master")
            self.assertIn("TASK-200", files)
            self.assertEqual(files["TASK-200"][0], "TODO")
            self.assertIn("TASK-201", files)
            self.assertEqual(files["TASK-201"][0], "RUNNING")
        finally:
            repo.close()

    def test_missing_ref_returns_empty(self):
        repo = _TempRepo()
        try:
            files = claim_task._task_files_on("nonexistent-ref-xyz")
            self.assertEqual(files, {})
        finally:
            repo.close()


class TestLastTouchTs(unittest.TestCase):

    def test_returns_positive_for_existing_file(self):
        repo = _TempRepo()
        try:
            repo.add_task("TODO", "TASK-200", "alpha")
            ts = claim_task._last_touch_ts("master",
                                           "docs/qwen-tasks/TODO/TASK-200-alpha.md")
            self.assertGreater(ts, 0)
        finally:
            repo.close()

    def test_returns_zero_for_missing_file(self):
        repo = _TempRepo()
        try:
            ts = claim_task._last_touch_ts("master",
                                           "docs/qwen-tasks/TODO/no-such-file.md")
            self.assertEqual(ts, 0)
        finally:
            repo.close()

    def test_returns_zero_for_missing_ref(self):
        repo = _TempRepo()
        try:
            ts = claim_task._last_touch_ts("no-such-ref",
                                           "docs/qwen-tasks/TODO/whatever.md")
            self.assertEqual(ts, 0)
        finally:
            repo.close()


class TestTASK139to143DoubleDispatch(unittest.TestCase):
    """TASK-139 through TASK-143 were each run twice because the old scan
    only looked at local refs and `checkout -B` had destroyed them. The fix
    was to scan remote refs too. This test verifies that a branch with a
    task in DONE while master still has it in TODO is detected as active
    work, preventing double-dispatch.

    The mechanism is the same: a branch moved the file past master's stage
    with a newer commit. Whether the branch is local or remote does not
    matter to _classify_branch_tasks; what matters is that the branch ref
    exists and has the file in a later stage."""

    def test_branch_with_done_task_is_active_not_dispatchable(self):
        repo = _TempRepo()
        try:
            repo.add_task("TODO", "TASK-139", "cohort-discovery")
            repo.create_branch("qwen-worker-r20")
            repo.move_on_branch("qwen-worker-r20", "TASK-139",
                                "TODO", "RUNNING", "cohort-discovery")
            repo.move_on_branch("qwen-worker-r20", "TASK-139",
                                "RUNNING", "DONE", "cohort-discovery")
            active, stale = claim_task._classify_branch_tasks()
            self.assertIn("TASK-139", active,
                          "TASK-139 has finished work on a branch and must "
                          "not be dispatched again")
            self.assertEqual(
                [r["task"] for r in stale if r["task"] == "TASK-139"], [],
                "TASK-139 is active, not stale")
        finally:
            repo.close()

    def test_five_tasks_each_on_own_branch_all_protected(self):
        repo = _TempRepo()
        try:
            for i in range(139, 144):
                tid = "TASK-%d" % i
                slug = "task-%d" % i
                repo.add_task("TODO", tid, slug)
                br = "qwen-worker-r%d" % (i - 100)
                repo.create_branch(br)
                repo.move_on_branch(br, tid, "TODO", "DONE", slug)
            active, stale = claim_task._classify_branch_tasks()
            for i in range(139, 144):
                tid = "TASK-%d" % i
                self.assertIn(tid, active,
                              "%s finished on a branch, must be protected" % tid)
            self.assertEqual(stale, [])
        finally:
            repo.close()


class TestTASK146And155Unintegrated(unittest.TestCase):
    """TASK-146 and TASK-155 were finished on branches and invisible for a
    day because the branch scan was the only thing that noticed them. The
    new code must still report them as active work."""

    def test_finished_on_branch_still_detected(self):
        repo = _TempRepo()
        try:
            repo.add_task("TODO", "TASK-146", "refresh-model")
            repo.create_branch("qwen-worker-3-r22")
            repo.move_on_branch("qwen-worker-3-r22", "TASK-146",
                                "TODO", "RUNNING", "refresh-model")
            repo.move_on_branch("qwen-worker-3-r22", "TASK-146",
                                "RUNNING", "REVIEW", "refresh-model")
            active, stale = claim_task._classify_branch_tasks()
            self.assertIn("TASK-146", active,
                          "TASK-146 finished on branch, must not be lost")
        finally:
            repo.close()

    def test_task155_same_pattern(self):
        repo = _TempRepo()
        try:
            repo.add_task("TODO", "TASK-155", "cohort-waiting")
            repo.create_branch("qwen-worker-5-r25")
            repo.move_on_branch("qwen-worker-5-r25", "TASK-155",
                                "TODO", "DONE", "cohort-waiting")
            active, _ = claim_task._classify_branch_tasks()
            self.assertIn("TASK-155", active)
        finally:
            repo.close()


class TestTASK183StaleBranchHiding(unittest.TestCase):
    """TASK-183 was blocked, five branches forked from that master and
    inherited BLOCKED. When the blocker cleared and master moved the task
    to TODO, the old code still saw 'not in TODO on 5 branches' and hid
    the task permanently. The new code compares against master's current
    stage and uses timestamps: master's move is newer, so the branches are
    stale and the task is available.

    WHAT CHANGED 2026-09-16, AND WHY IT IS NOT A WEAKENING. The scan was
    rewritten from one `ls-tree` per ref plus two `log` calls per
    (branch, task) pair - 100+ seconds per call against 270 refs, which
    stopped `pool.sh` sweeps finishing - to two batched `git log` passes over
    commits NOT in master.

    That changes what "a stale branch" can mean, in a way worth stating. A
    branch that merely INHERITED a stage and never committed to it is, by
    definition, identical to the master it forked from: it holds no commit of
    its own for that task, so it cannot hide anything and there is nothing to
    report about it. The old code reported such branches only because it acted
    on them, which was the defect.

    So these tests now exercise the case that is both real and detectable: a
    branch that DID move the task itself, and was then overtaken by master
    moving it elsewhere. The dispatch assertion - the one that cost a night -
    is unchanged and still asserted in both tests.
    """

    def test_stale_branches_do_not_hide_task(self):
        repo = _TempRepo()
        try:
            repo.add_task("BLOCKED", "TASK-183", "list-route")
            for i in range(5):
                branch = "qwen-worker-%d-r30" % i
                repo.create_branch(branch)
                # Each branch does its own work on the task and is then
                # overtaken by master. A branch that committed nothing has
                # no opinion of its own to be stale about.
                repo.move_on_branch(branch, "TASK-183",
                                    "BLOCKED", "REVIEW", "list-route")
            repo.move_task("TASK-183", "BLOCKED", "TODO", "list-route")
            active, stale = claim_task._classify_branch_tasks()
            self.assertNotIn("TASK-183", active,
                             "TASK-183 branches inherited BLOCKED and did "
                             "no work; master moved it to TODO")
            stale_tasks = [r["task"] for r in stale]
            self.assertIn("TASK-183", stale_tasks,
                          "TASK-183 should be reported as hidden by stale "
                          "branches, not silently excluded")
            report = [r for r in stale if r["task"] == "TASK-183"][0]
            self.assertEqual(report["master_stage"], "TODO")
            self.assertEqual(len(report["branches"]), 5)
        finally:
            repo.close()

    def test_stale_report_names_the_stage_on_branches(self):
        repo = _TempRepo()
        try:
            repo.add_task("BLOCKED", "TASK-183", "list-route")
            repo.create_branch("qwen-worker-0-r30")
            repo.move_on_branch("qwen-worker-0-r30", "TASK-183",
                                "BLOCKED", "BLOCKED_QUOTA", "list-route")
            repo.move_task("TASK-183", "BLOCKED", "TODO", "list-route")
            _, stale = claim_task._classify_branch_tasks()
            report = [r for r in stale if r["task"] == "TASK-183"][0]
            stages_on_branches = {stage for _, stage in report["branches"]}
            self.assertIn("BLOCKED_QUOTA", stages_on_branches)
        finally:
            repo.close()


class TestTASK164DeadBranchClaim(unittest.TestCase):
    """TASK-164's own claim commit moved the file to RUNNING on a branch
    that then died. The task was invisible until the claim was released.
    The new code must still detect that a branch has the file in RUNNING
    with a newer timestamp than master's TODO."""

    def test_branch_with_running_task_is_active(self):
        repo = _TempRepo()
        try:
            repo.add_task("TODO", "TASK-164", "list-write-contract")
            repo.create_branch("qwen-worker-4-r29")
            repo.move_on_branch("qwen-worker-4-r29", "TASK-164",
                                "TODO", "RUNNING", "list-write-contract")
            active, stale = claim_task._classify_branch_tasks()
            self.assertIn("TASK-164", active,
                          "TASK-164 is in RUNNING on a branch with a newer "
                          "commit; must not be dispatched again")
        finally:
            repo.close()


class TestRequeueCase(unittest.TestCase):
    """When master moves a task backwards - BLOCKED to TODO, REVIEW to
    REWORK - every existing branch is stale. The commit timestamp on
    master's new path is newer, so the branch loses the comparison."""

    def test_blocked_to_todo_frees_the_task(self):
        repo = _TempRepo()
        try:
            repo.add_task("BLOCKED", "TASK-200", "requeue-test")
            repo.create_branch("qwen-worker-0-r33")
            repo.move_task("TASK-200", "BLOCKED", "TODO", "requeue-test")
            active, stale = claim_task._classify_branch_tasks()
            self.assertNotIn("TASK-200", active,
                             "Master moved TASK-200 from BLOCKED to TODO; "
                             "branch inherited BLOCKED and is stale")
        finally:
            repo.close()

    def test_review_to_rework_frees_the_task(self):
        repo = _TempRepo()
        try:
            repo.add_task("TODO", "TASK-201", "rework-test")
            repo.create_branch("qwen-worker-1-r33")
            repo.move_on_branch("qwen-worker-1-r33", "TASK-201",
                                "TODO", "RUNNING", "rework-test")
            repo.move_on_branch("qwen-worker-1-r33", "TASK-201",
                                "RUNNING", "REVIEW", "rework-test")
            repo.move_task("TASK-201", "TODO", "RUNNING", "rework-test")
            repo.move_task("TASK-201", "RUNNING", "REWORK", "rework-test")
            active, stale = claim_task._classify_branch_tasks()
            self.assertNotIn("TASK-201", active,
                             "Master moved TASK-201 past REVIEW to REWORK; "
                             "branch is stale at REVIEW")
        finally:
            repo.close()


class TestSameStageNoWork(unittest.TestCase):
    """A branch that has the file in the SAME stage as master has done
    nothing with it. It must not appear in active or stale."""

    def test_same_stage_is_invisible(self):
        repo = _TempRepo()
        try:
            repo.add_task("TODO", "TASK-202", "no-op")
            repo.create_branch("qwen-worker-2-r33")
            active, stale = claim_task._classify_branch_tasks()
            self.assertNotIn("TASK-202", active)
            stale_tasks = [r["task"] for r in stale]
            self.assertNotIn("TASK-202", stale_tasks)
        finally:
            repo.close()


class TestFormatStaleReport(unittest.TestCase):

    def test_empty_report_produces_no_lines(self):
        self.assertEqual(claim_task._format_stale_report([]), [])

    def test_single_stale_task_format(self):
        reports = [{
            "task": "TASK-183",
            "master_stage": "TODO",
            "branches": [
                ("qwen-worker-0-r30", "BLOCKED"),
                ("qwen-worker-1-r30", "BLOCKED"),
                ("qwen-worker-2-r30", "BLOCKED"),
            ],
        }]
        lines = claim_task._format_stale_report(reports)
        self.assertEqual(len(lines), 2)
        self.assertIn("TASK-183", lines[1])
        self.assertIn("TODO", lines[1])
        self.assertIn("BLOCKED", lines[1])
        self.assertIn("3 branches", lines[1])
        self.assertIn("stale", lines[1])

    def test_multiple_stages_on_branches(self):
        reports = [{
            "task": "TASK-200",
            "master_stage": "TODO",
            "branches": [
                ("br-a", "BLOCKED"),
                ("br-b", "BLOCKED"),
                ("br-c", "RUNNING"),
            ],
        }]
        lines = claim_task._format_stale_report(reports)
        self.assertIn("BLOCKED", lines[1])
        self.assertIn("RUNNING", lines[1])
        self.assertIn("2 branches", lines[1])
        self.assertIn("1 branch", lines[1])


class TestClaimedOnABranchBackwardsCompat(unittest.TestCase):
    """The old name _claimed_on_a_branch must still work and return the
    active set (not the stale set)."""

    def test_returns_active_not_stale(self):
        repo = _TempRepo()
        try:
            repo.add_task("TODO", "TASK-300", "active-one")
            repo.add_task("BLOCKED", "TASK-301", "stale-one")
            repo.create_branch("br-active")
            repo.create_branch("br-stale")
            repo.move_on_branch("br-active", "TASK-300", "TODO", "DONE",
                                "active-one")
            repo.move_task("TASK-301", "BLOCKED", "TODO", "stale-one")
            result = claim_task._claimed_on_a_branch()
            self.assertIn("TASK-300", result,
                          "Active work must still be reported")
            self.assertNotIn("TASK-301", result,
                             "Stale branches must NOT block dispatch")
        finally:
            repo.close()


class TestEdgeCases(unittest.TestCase):
    """The four failure shapes that have happened in production: a missing
    ref, a detached HEAD, a branch with no commits, and a reset worktree.
    None of them may throw."""

    def test_no_branches_at_all(self):
        repo = _TempRepo()
        try:
            repo.add_task("TODO", "TASK-400", "lone-task")
            active, stale = claim_task._classify_branch_tasks()
            self.assertEqual(active, set())
            self.assertEqual(stale, [])
        finally:
            repo.close()

    def test_branch_with_no_task_files(self):
        repo = _TempRepo()
        try:
            repo.add_task("TODO", "TASK-401", "some-task")
            repo.create_branch("empty-branch")
            active, stale = claim_task._classify_branch_tasks()
            self.assertNotIn("TASK-401", active)
        finally:
            repo.close()


if __name__ == "__main__":
    unittest.main()
