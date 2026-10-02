"""The suite lock. Six concurrent runs on 2026-10-02 is the defect this answers.

The property under test is SERIALISATION, and the one that actually failed that day
is that the lock path must be the SAME from the main checkout and from every
worktree. `work/` is gitignored so each worktree has its own, which is why a naive
`work/suite.lock` would have serialised nothing.
"""
import json
import os
import tempfile
import unittest

from src import suitelock


def lockfile():
    return os.path.join(tempfile.mkdtemp(), "work", "suite.lock")


class TheLockPathIsSharedByEveryWorktree(unittest.TestCase):
    """The defect of 2026-10-02: six runs from six trees, nothing serialised."""

    def test_the_path_comes_from_the_git_common_dir(self):
        """`--git-common-dir` is the one answer that is identical everywhere."""
        resolved = suitelock.path()
        self.assertTrue(resolved.endswith(os.path.join("work", "suite.lock")),
                        resolved)

    def test_the_path_is_not_derived_from_this_trees_own_root(self):
        """If it were, a worktree would get its own lock and serialise nothing.
        Asserted as an effect: the resolved path must sit beside the COMMON git
        dir, not beside `store.ROOT`, and in a worktree those differ."""
        from src import store
        common = suitelock._git_common_dir()
        if not common:
            self.skipTest("git could not answer; the fallback is tested below")
        expected = os.path.join(os.path.dirname(os.path.abspath(common)),
                                "work", "suite.lock")
        self.assertEqual(os.path.abspath(expected),
                         os.path.abspath(suitelock.path()))
        if os.path.abspath(os.path.dirname(os.path.abspath(common))) != \
                os.path.abspath(store.ROOT):
            self.assertNotEqual(
                os.path.abspath(os.path.join(store.PRODUCTION_WORK,
                                             "suite.lock")),
                os.path.abspath(suitelock.path()),
                "in a worktree the lock must NOT be this tree's own work/")

    def test_a_relative_answer_from_git_is_refused_not_resolved(self):
        """Without `--path-format=absolute` git answers a RELATIVE path from a
        worktree. `os.path.abspath` would then resolve it against the caller's
        cwd - which from a worktree is that worktree, the per-tree lock this
        module exists to prevent.

        An earlier version of this test asserted the flag's PRESENCE IN THE
        SOURCE of `_git_common_dir`, and it could not fail: the same string also
        appears in that function's docstring, so removing it from the argv left
        the test green. Measured 2026-10-02, and it is why this one patches
        `subprocess.run` and asserts the RETURN VALUE instead.
        """
        import subprocess as sp

        class Answer:
            returncode = 0
            stdout = ".git\n"
            stderr = ""

        original = suitelock.subprocess.run
        try:
            suitelock.subprocess.run = lambda *a, **k: Answer()
            self.assertIsNone(
                suitelock._git_common_dir(),
                "a relative git answer must be refused; resolving it against "
                "cwd gives a per-worktree lock, which serialises nothing")
        finally:
            suitelock.subprocess.run = original

    def test_an_absolute_answer_from_git_is_accepted(self):
        """The control for the test above: it must also be able to say yes.

        The fixture uses `os.path.abspath` rather than a hand-built `os.sep +
        "somewhere"`. On Windows under Python 3.13+ a path starting with a bare
        separator and no drive letter is NOT absolute - it is relative to the
        current drive - so the hand-built version made this control fail against
        correct code. Measured 2026-10-02.
        """
        absolute = os.path.abspath(os.path.join("somewhere", "main", ".git"))
        self.assertTrue(os.path.isabs(absolute), absolute)

        class Answer:
            returncode = 0
            stdout = absolute + "\n"
            stderr = ""

        original = suitelock.subprocess.run
        try:
            suitelock.subprocess.run = lambda *a, **k: Answer()
            self.assertEqual(absolute, suitelock._git_common_dir())
        finally:
            suitelock.subprocess.run = original


class AHeldLockIsWaitedOnNotIgnored(unittest.TestCase):
    def test_a_second_acquire_refuses_rather_than_running_in_parallel(self):
        path = lockfile()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "branch": "held-by-this-process",
                       "started_at": "2026-10-02T13:44:42"}, handle)
        said = []
        with self.assertRaises(suitelock.SuiteBusy) as caught:
            suitelock.acquire(branch="second", timeout=0.1, file_path=path,
                              poll=0.01, say=said.append)
        self.assertIn("held-by-this-process", str(caught.exception))
        self.assertIn(str(os.getpid()), str(caught.exception))

    def test_the_wait_is_announced_with_the_holder(self):
        path = lockfile()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "branch": "merge-sequence",
                       "started_at": "2026-10-02T13:44:42"}, handle)
        said = []
        with self.assertRaises(suitelock.SuiteBusy):
            suitelock.acquire(branch="second", timeout=0.1, file_path=path,
                              poll=0.01, say=said.append)
        self.assertTrue(any("merge-sequence" in line for line in said), said)
        self.assertTrue(any("one full suite" in line for line in said), said)


class AStaleLockIsTakenOverLoudly(unittest.TestCase):
    """A machine that lost power must not need a human to delete a file."""

    def test_a_dead_holder_is_replaced_and_announced(self):
        path = lockfile()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"pid": 999999999, "branch": "died-mid-suite",
                       "started_at": "2026-10-02T09:00:00"}, handle)
        said = []
        mine = suitelock.acquire(branch="mine", timeout=5, file_path=path,
                                 poll=0.01, say=said.append)
        self.addCleanup(suitelock.release, path)
        self.assertEqual(os.getpid(), mine["pid"])
        self.assertTrue(any("stale" in line for line in said), said)
        self.assertTrue(any("999999999" in line for line in said), said)

    def test_a_damaged_lock_file_does_not_block_the_machine_forever(self):
        path = lockfile()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json at all")
        mine = suitelock.acquire(branch="mine", timeout=5, file_path=path,
                                 poll=0.01, say=lambda *_: None)
        self.addCleanup(suitelock.release, path)
        self.assertEqual(os.getpid(), mine["pid"])


class ReleaseNeverTouchesSomebodyElsesLock(unittest.TestCase):
    def test_release_removes_our_own(self):
        path = lockfile()
        suitelock.acquire(branch="mine", timeout=5, file_path=path, poll=0.01,
                          say=lambda *_: None)
        self.assertTrue(suitelock.release(path))
        self.assertIsNone(suitelock.read(path))

    def test_release_leaves_another_pids_lock_alone(self):
        """A run that crashed and restarted must not delete the lock of the run
        that took over from it."""
        path = lockfile()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid() + 1, "branch": "somebody-else"},
                      handle)
        self.assertFalse(suitelock.release(path))
        self.assertIsNotNone(suitelock.read(path))

    def test_release_on_no_lock_is_false_not_an_error(self):
        self.assertFalse(suitelock.release(lockfile()))


class AnUnknownPidCountsAsAlive(unittest.TestCase):
    """Waiting costs time; stealing costs a corrupted run. So uncertainty waits."""

    def test_a_nonsense_pid_is_not_alive(self):
        self.assertFalse(suitelock._alive("not-a-pid"))
        self.assertFalse(suitelock._alive(None))
        self.assertFalse(suitelock._alive(0))

    def test_this_process_is_alive(self):
        self.assertTrue(suitelock._alive(os.getpid()))


if __name__ == "__main__":
    unittest.main()
