"""The suite lock. Six concurrent runs on 2026-10-02 is the defect this answers.

The property under test is SERIALISATION, and the one that actually failed that day
is that the lock path must be the SAME from the main checkout and from every
worktree. `work/` is gitignored so each worktree has its own, which is why a naive
`work/suite.lock` would have serialised nothing.
"""
import json
import os
import tempfile
import time
import unittest
from unittest import mock

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


class ADetachedCheckoutIsNamedByItsCommit(unittest.TestCase):
    """The field that says WHO is ahead of you must not say "HEAD".

    MEASURED 2026-10-02: every reference and gate checkout is detached on purpose,
    `git rev-parse --abbrev-ref HEAD` answers the literal string "HEAD" for those,
    and the lock recorded it. Three agents then investigated who held the lock by
    hand - the exact cost the field exists to prevent.
    """

    def test_the_literal_string_head_is_replaced_by_the_commit(self):
        with mock.patch.object(suitelock.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="abc1234\n",
                                         stderr="")
            written = suitelock.acquire(branch="HEAD", file_path=lockfile(),
                                        timeout=1, say=lambda *_: None)
        self.assertEqual("detached abc1234", written["branch"])

    def test_a_real_branch_name_is_left_alone_and_git_is_not_asked(self):
        """The control. If this also returned a SHA the test above would pass for
        the wrong reason - every branch renamed, not just the detached case."""
        with mock.patch.object(suitelock.subprocess, "run") as run:
            written = suitelock.acquire(branch="task-942-token-budget",
                                        file_path=lockfile(), timeout=1,
                                        say=lambda *_: None)
            self.assertEqual("task-942-token-budget", written["branch"])
            for call in run.call_args_list:
                self.assertNotIn("--short", call.args[0])

    def test_no_branch_at_all_is_also_resolved(self):
        with mock.patch.object(suitelock.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="deadbee\n",
                                         stderr="")
            written = suitelock.acquire(branch=None, file_path=lockfile(),
                                        timeout=1, say=lambda *_: None)
        self.assertEqual("detached deadbee", written["branch"])

    def test_when_git_cannot_answer_the_field_is_empty_not_a_lie(self):
        """`None` says "unknown". "HEAD" would say something false about a real
        branch, and an unreadable authority must never become an answer."""
        with mock.patch.object(suitelock.subprocess, "run",
                               side_effect=OSError("no git")):
            self.assertIsNone(suitelock._label("HEAD"))
            self.assertIsNone(suitelock._label(None))


class TheQueueIsFirstComeFirstServed(unittest.TestCase):
    """Arrival order has to buy a waiter something.

    MEASURED on the lock's first production use: four runs waited behind one
    holder and the grant went to whoever polled first after the release, so a run
    could be overtaken repeatedly. With a 46-minute suite and a 3-hour
    `--lock-wait`, four overtakes starve one.
    """

    def plant(self, lock_path, pid, seconds_ago):
        """Somebody else's ticket, older than ours by construction."""
        directory = suitelock._queue_dir(lock_path)
        os.makedirs(directory, exist_ok=True)
        name = "%020.6f-%d.json" % (time.time() - seconds_ago, pid)
        full = os.path.join(directory, name)
        with open(full, "w", encoding="utf-8") as handle:
            json.dump({"pid": pid}, handle)
        return full

    def test_a_later_arrival_waits_even_when_the_lock_is_free(self):
        """THE FIFO PROPERTY. No lock file exists at all here, so the old
        implementation would have taken it instantly. Ours must not, because
        somebody who arrived earlier is still queued."""
        lock = lockfile()
        self.plant(lock, os.getpid(), seconds_ago=100)
        with self.assertRaises(suitelock.SuiteBusy) as caught:
            suitelock.acquire(branch="late", file_path=lock, timeout=0.2,
                              poll=0.01, say=lambda *_: None)
        self.assertFalse(os.path.exists(lock), "took a lock out of turn")
        self.assertIn("in the queue", str(caught.exception))

    def test_the_control_without_an_earlier_ticket_it_takes_it_at_once(self):
        """The control for the test above. If this also refused, that test would
        be proving only that `acquire` can time out."""
        lock = lockfile()
        written = suitelock.acquire(branch="alone", file_path=lock, timeout=0.2,
                                    poll=0.01, say=lambda *_: None)
        self.assertEqual(os.getpid(), written["pid"])
        self.assertTrue(os.path.exists(lock))

    def test_a_dead_waiters_ticket_does_not_wedge_the_queue(self):
        lock = lockfile()
        stale = self.plant(lock, 999999, seconds_ago=100)
        suitelock.acquire(branch="behind-a-corpse", file_path=lock, timeout=1,
                          poll=0.01, say=lambda *_: None)
        self.assertTrue(os.path.exists(lock))
        self.assertFalse(os.path.exists(stale), "a dead ticket was left in place")

    def test_the_ticket_is_dropped_when_the_lock_is_granted(self):
        lock = lockfile()
        suitelock.acquire(branch="x", file_path=lock, timeout=1,
                          say=lambda *_: None)
        self.assertEqual([], suitelock._live_tickets(lock))

    def test_the_ticket_is_dropped_when_the_lock_is_refused(self):
        """A ticket left behind by a refused run would hold the queue against
        every later arrival until that PID died - starvation, reintroduced by the
        fix for starvation."""
        lock = lockfile()
        planted = self.plant(lock, os.getpid(), seconds_ago=100)
        with self.assertRaises(suitelock.SuiteBusy):
            suitelock.acquire(branch="refused", file_path=lock, timeout=0.2,
                              poll=0.01, say=lambda *_: None)
        self.assertEqual([os.path.abspath(planted)],
                         [os.path.abspath(p)
                          for p in suitelock._live_tickets(lock)])

    def test_ticketing_that_cannot_be_used_does_not_stop_a_run(self):
        """Fairness is the bonus; serialisation is the rule. If the queue cannot
        be created the run must still proceed, loudly."""
        lock = lockfile()
        os.makedirs(os.path.dirname(lock), exist_ok=True)
        blocker = lock + ".blocked"
        with open(blocker, "w", encoding="utf-8") as handle:
            handle.write("not a directory")
        said = []
        with mock.patch.object(suitelock, "_queue_dir",
                               return_value=os.path.join(blocker, "sub")):
            written = suitelock.acquire(branch="unticketed", file_path=lock,
                                        timeout=1, poll=0.01, say=said.append)
        self.assertEqual(os.getpid(), written["pid"])
        self.assertTrue(any("unordered" in line for line in said), said)

    def test_a_vanished_ticket_degrades_to_the_race_not_a_deadlock(self):
        """If anything pruned our ticket by mistake, waiting for a turn that can
        never arrive would park the run until its timeout and then refuse."""
        lock = lockfile()
        self.plant(lock, os.getpid(), seconds_ago=100)
        gone = os.path.join(suitelock._queue_dir(lock), "never-written-99.json")
        self.assertTrue(suitelock._my_turn(lock, gone))

    def test_ticket_names_sort_in_arrival_order_across_a_digit_boundary(self):
        """The hazard a plain `str(time.time())` would have shipped: "999.9"
        sorts AFTER "1000.0" lexicographically, so the queue would invert every
        time the clock crossed a power of ten."""
        earlier = "%020.6f-%d.json" % (999.9, 1)
        later = "%020.6f-%d.json" % (1000.0, 1)
        self.assertLess(earlier, later)
        self.assertLess(sorted([later, earlier])[0], later)

    def test_a_file_that_is_not_one_of_our_tickets_is_left_alone(self):
        """Deleting an unknown file is how a lock loses somebody else's state."""
        lock = lockfile()
        directory = suitelock._queue_dir(lock)
        os.makedirs(directory, exist_ok=True)
        foreign = os.path.join(directory, "README")
        with open(foreign, "w", encoding="utf-8") as handle:
            handle.write("not ours")
        self.assertIsNone(suitelock._pid_of_ticket("README"))
        self.assertEqual([], suitelock._live_tickets(lock))
        self.assertTrue(os.path.exists(foreign))


if __name__ == "__main__":
    unittest.main()
