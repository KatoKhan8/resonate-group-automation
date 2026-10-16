"""The lock's holder is a PID and a start time, because a PID is not an identity.

MEASURED 2026-10-16, by two lanes, and neither half is in dispute:

* a run that died at process start - `exit_code=3221225794`, `wall_seconds=0.0`,
  a 0-byte log - left its lock held for 89 minutes, and nothing released it;
* a reader got two OPPOSITE liveness answers for one pid four minutes apart,
  because the dead holder's number had been recycled onto one of that reader's
  own shell's transient processes.

`_alive` was correct about the pid both times. **The pid was not the holder.**
The second half is the one that matters: a ghost holder is not recoverable by
waiting, and no instrument in the estate would have reported it. `_holder_alive`
is the reader that can tell the two apart.

THE TESTS THAT CARRY THE DEFECT GO THROUGH `_takeable` AND `_live_tickets`, which
existed before the fix, so they fail on the pre-change module BY ASSERTION and not
by a missing attribute. A test that reddens only because a new name is absent
proves nothing about the old reader's answer, and the difference matters here.

THE FIXTURES DO NOT COME FROM A CLOCK, AND THEY ARE NOT A DEAD PID. The recycled
fixture pairs THIS process's pid - which is unquestionably alive - with a recorded
start time that is not any process's, or with the PARENT's, which belongs to a
different, live process that started strictly before this one. Each test using
one asserts the pid really is alive first, so it cannot pass by the OTHER guard, a
dead pid, firing instead.

WHAT THIS FILE DELIBERATELY DOES NOT DO. It runs no full suite and takes no suite
lock: every lock and every ticket it uses is a temp file of its own.
"""
import json
import os
import tempfile
import time
import unittest
from unittest import mock

from src import suitelock

#: A recorded start time that is not this process's, and cannot be any process's.
#: A real reading is the process's creation time as a digit string, so `"0"` - the
#: epoch of the clock it is measured on, four centuries ago - is provably foreign
#: without asking the OS anything, which is what lets the negative fixtures below
#: be built and read on the PRE-CHANGE module as well as this one.
NOT_THIS_PROCESS = "0"


def lockfile():
    return os.path.join(tempfile.mkdtemp(), "work", "suite.lock")


def plant(path, holder):
    """A lock or ticket file on disk, exactly as another process left it."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(holder, handle)
    return path


def mothers_start_time():
    """The parent's start time - a real one, belonging to a different live
    process that started strictly before this one. That pair IS the shape of a
    recycled pid: a live number carrying a foreign identity.

    The parent is used rather than a child that is spawned and killed because it
    is live for as long as the test runs and nothing has to be awaited or cleaned
    up afterwards.
    """
    return suitelock._proc_start(os.getppid())


class TheStartTimeIsARealIdentityAndNotAConstant(unittest.TestCase):
    """The primitive, on its own, before anything is judged by it.

    Without these, every reader test could pass against a `_proc_start` that
    returned a CONSTANT - every holder would "match", a recycled one included - so
    the primitive is measured rather than trusted.
    """

    def test_it_is_read_repeatedly_the_same_for_one_process(self):
        first = suitelock._proc_start(os.getpid())
        time.sleep(0.05)
        self.assertIsNotNone(first, "the OS answered nothing for a live pid")
        self.assertEqual(first, suitelock._proc_start(os.getpid()),
                         "a process's start time cannot change while it runs")

    def test_two_live_processes_have_two_different_start_times(self):
        self.assertIsNotNone(mothers_start_time())
        self.assertNotEqual(mothers_start_time(),
                            suitelock._proc_start(os.getpid()))

    def test_a_process_that_started_earlier_has_a_smaller_start_time(self):
        """Ordering, so the token is a clock and not a per-pid random value."""
        parent = mothers_start_time()
        mine = suitelock._proc_start(os.getpid())
        self.assertTrue(parent.isdigit() and mine.isdigit(), (parent, mine))
        self.assertLess(int(parent), int(mine))

    def test_a_pid_that_cannot_exist_answers_None_and_never_a_guess(self):
        """None means THIS MACHINE COULD NOT ANSWER. It is not "it differed", and
        the reader must not treat it as one - see the test below."""
        self.assertIsNone(suitelock._proc_start(999999999))
        self.assertIsNone(suitelock._proc_start(None))
        self.assertIsNone(suitelock._proc_start("not-a-pid"))
        self.assertIsNone(suitelock._proc_start(0))


class ALivePidThatIsNotTheHolderIsStale(unittest.TestCase):
    """THE DEFECT. A recycled pid held a lock that nothing was holding."""

    def test_the_negative_control_a_recycled_pid_reads_STALE(self):
        """RED on the pre-change module, by assertion: the old reader answers
        "held" for a live pid whatever start time it carries, and waits - for 89
        minutes, as measured, and then out to its six-hour timeout.

        The pid is asserted alive first so this cannot pass by the OTHER guard, a
        dead pid, firing first.
        """
        pid = os.getpid()
        self.assertTrue(suitelock._alive(pid), "the fixture pid must be alive, or "
                        "a dead pid answers this and identity is never reached")
        holder = {"pid": pid, "proc_start": NOT_THIS_PROCESS}
        self.assertTrue(suitelock._takeable(lockfile(), holder),
                        "a live pid carrying a start time that is not its own is "
                        "a RECYCLED pid, and the lock it names is not held")

    def test_a_foreign_start_time_from_a_real_live_process_is_also_stale(self):
        """The same, with a real token rather than a sentinel: the parent is a
        live process, so what makes this stale is the identity and nothing else.
        """
        pid = os.getpid()
        foreign = mothers_start_time()
        self.assertTrue(suitelock._alive(pid))
        self.assertNotEqual(foreign, suitelock._proc_start(pid))
        self.assertFalse(suitelock._holder_alive({"pid": pid,
                                                  "proc_start": foreign}))
        self.assertTrue(suitelock._takeable(lockfile(),
                                            {"pid": pid,
                                             "proc_start": foreign}))

    def test_the_positive_control_matching_identity_reads_LIVE(self):
        """If this file cannot print LIVE, it is not watching the reader."""
        holder = {"pid": os.getpid(),
                  "proc_start": suitelock._proc_start(os.getpid())}
        self.assertTrue(suitelock._holder_alive(holder))
        self.assertFalse(suitelock._takeable(lockfile(), holder))

    def test_the_os_cannot_answer_so_the_holder_is_not_stolen(self):
        """The fail-safe direction. An unreadable identity is UNKNOWN, not a
        mismatch, and an unknown liveness answer counts as ALIVE in this module -
        waiting costs time, stealing costs a corrupted run."""
        holder = {"pid": os.getpid(), "proc_start": NOT_THIS_PROCESS}
        with mock.patch.object(suitelock, "_proc_start", return_value=None):
            self.assertTrue(suitelock._holder_alive(holder))
            self.assertFalse(suitelock._takeable(lockfile(), holder))


class ALockFromBeforeThisChangeIsWaitedOnNotStolen(unittest.TestCase):
    """Backward compatibility in both directions, and the decision written into
    `suitelock`'s docstring: a missing start time is UNKNOWN, not a mismatch.

    ASSERTED THROUGH `_takeable`, which the pre-change module also has, so the
    contract is demonstrated against both versions rather than assumed. The cost
    of this reading is named in that docstring rather than hidden - an old-format
    lock whose holder is DEAD is waited on too.
    """

    def test_a_missing_start_time_with_a_LIVE_pid_is_not_stolen(self):
        """This is the reference run's lock, on the machine this was written on.
        Reading the absent field as a mismatch would have stolen it mid-suite."""
        path = plant(lockfile(), {"pid": os.getpid(), "branch": "old-format"})
        holder = suitelock.read(path)
        self.assertIsNone(holder.get("proc_start"),
                          "the fixture must carry no start time at all")
        self.assertTrue(suitelock._alive(holder.get("pid")))
        self.assertFalse(suitelock._takeable(path, holder))

    def test_a_missing_start_time_with_a_DEAD_pid_is_taken_over(self):
        """The control for the test above, and the other direction: the absent
        field must not make every old lock immortal, or a machine that lost power
        would need a human to delete a file before tests could run again."""
        path = plant(lockfile(), {"pid": 999999999, "branch": "old-format"})
        holder = suitelock.read(path)
        self.assertIsNone(holder.get("proc_start"))
        self.assertFalse(suitelock._alive(holder.get("pid")))
        self.assertTrue(suitelock._takeable(path, holder))


class MutatingTheHolderIntoARecycledOne(unittest.TestCase):
    """The same lock file read twice, with one field changed in between.

    Only the recorded start time moves; the pid, the branch and the file's age do
    not. If the verdict follows that one byte, it cannot be coming from any of the
    others.
    """

    def test_only_the_recorded_start_time_decides_the_verdict(self):
        path = lockfile()
        own = suitelock._proc_start(os.getpid())
        plant(path, {"pid": os.getpid(), "proc_start": own,
                     "started_at": "2026-10-16T00:00:00"})
        self.assertTrue(suitelock._holder_alive(suitelock.read(path)))
        plant(path, {"pid": os.getpid(), "proc_start": NOT_THIS_PROCESS,
                     "started_at": "2026-10-16T00:00:00"})
        self.assertFalse(suitelock._holder_alive(suitelock.read(path)))


class TheAcquirePathUsesTheIdentityToo(unittest.TestCase):
    """Not just the helper: the run that is actually waiting."""

    def test_a_recycled_holder_is_taken_over_and_named_as_recycled(self):
        """RED on the pre-change module: it waited out the whole timeout and then
        refused, for a holder that had been dead for 89 minutes."""
        path = plant(lockfile(), {"pid": os.getpid(),
                                  "proc_start": NOT_THIS_PROCESS,
                                  "branch": "died-at-process-start",
                                  "started_at": "2026-10-16T00:00:00"})
        said = []
        try:
            mine = suitelock.acquire(branch="next", timeout=1.0, file_path=path,
                                     poll=0.01, say=said.append)
        except suitelock.SuiteBusy as refused:
            self.fail("waited on a recycled pid until it timed out: %s" % refused)
        self.addCleanup(suitelock.release, path)
        self.assertEqual(os.getpid(), mine["pid"])
        joined = " ".join(said)
        self.assertIn("stale", joined, joined)
        self.assertIn("RECYCLED", joined,
                      "the operator must be told this was a RECYCLED pid and not "
                      "a dead one - the two need different answers: " + joined)

    def test_the_control_an_old_format_live_holder_is_still_waited_on(self):
        """Without a control, the test above would pass for a reader that takes
        every lock it sees. This holder carries a live pid and no start time, so
        it is the UNVERIFIED case, and it must still be waited on."""
        path = plant(lockfile(), {"pid": os.getpid(), "branch": "holding"})
        with self.assertRaises(suitelock.SuiteBusy):
            suitelock.acquire(branch="second", timeout=0.2, file_path=path,
                              poll=0.01, say=lambda *_: None)
        self.assertTrue(os.path.exists(path), "an unverified holder was stolen")

    def test_the_control_a_verified_live_holder_is_still_waited_on(self):
        """The other control: identity VERIFIED and matching. Both controls are
        needed - each alone would pass on a reader that never waits."""
        path = plant(lockfile(), {"pid": os.getpid(),
                                  "proc_start": suitelock._proc_start(
                                      os.getpid()),
                                  "branch": "holding"})
        with self.assertRaises(suitelock.SuiteBusy):
            suitelock.acquire(branch="second", timeout=0.2, file_path=path,
                              poll=0.01, say=lambda *_: None)
        self.assertTrue(os.path.exists(path))

    def test_acquire_records_its_own_start_time_beside_its_pid(self):
        """A lock that does not record it cannot be checked by the next reader
        and would be waited on forever instead - see the old-format tests."""
        path = lockfile()
        mine = suitelock.acquire(branch="writer", timeout=1.0, file_path=path,
                                 say=lambda *_: None)
        self.addCleanup(suitelock.release, path)
        self.assertIn("proc_start", mine,
                      "the lock must record what makes its pid an identity")
        self.assertEqual(suitelock._proc_start(os.getpid()),
                         mine["proc_start"])
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(mine["proc_start"], json.load(handle)["proc_start"])


class AGhostTicketDoesNotHoldTheQueue(unittest.TestCase):
    """The same defect one layer down, and it is the worse of the two.

    A lock's ghost blocks whoever is behind that lock. A QUEUE's ghost blocks the
    whole queue: `_my_turn` is False for every arrival while the earliest live
    ticket belongs to a pid that was recycled, so every waiter burns its full
    timeout and then refuses.
    """

    def ticket(self, lock, holder, seconds_ago=100):
        name = "%020.6f-%d.json" % (time.time() - seconds_ago, holder["pid"])
        return plant(os.path.join(suitelock._queue_dir(lock), name), holder)

    def test_a_recycled_waiters_ticket_is_not_held_against_the_queue(self):
        """RED on the pre-change module, by assertion: `_live_tickets` answered
        from the pid alone, so this ticket was returned as a live waiter's."""
        lock = lockfile()
        pid = os.getpid()
        self.assertTrue(suitelock._alive(pid))
        ghost = self.ticket(lock, {"pid": pid, "proc_start": NOT_THIS_PROCESS})
        self.assertEqual([], suitelock._live_tickets(lock),
                         "a recycled pid's ticket held the whole queue")
        self.assertFalse(os.path.exists(ghost))

    def test_the_control_a_real_waiters_ticket_is_kept(self):
        """Without this the test above would pass on a `_live_tickets` that
        deleted everything, which would destroy the queue's fairness."""
        holder = {"pid": os.getpid()}
        lock = lockfile()
        real = self.ticket(lock, holder)
        self.assertEqual([os.path.abspath(real)],
                         [os.path.abspath(p)
                          for p in suitelock._live_tickets(lock)])

    def test_the_other_control_a_matching_identity_is_kept(self):
        """The same control with the identity VERIFIED, so the deletion above
        cannot be coming from the field merely being present."""
        lock = lockfile()
        real = self.ticket(lock, {"pid": os.getpid(),
                                  "proc_start": suitelock._proc_start(
                                      os.getpid())})
        self.assertEqual([os.path.abspath(real)],
                         [os.path.abspath(p)
                          for p in suitelock._live_tickets(lock)])

    def test_a_ticket_of_a_dead_pid_is_still_dropped(self):
        """The pre-existing behaviour, which the identity check must not break: a
        crashed waiter cannot wedge the queue behind it."""
        lock = lockfile()
        dead = self.ticket(lock, {"pid": 999999, "proc_start": NOT_THIS_PROCESS})
        self.assertEqual([], suitelock._live_tickets(lock))
        self.assertFalse(os.path.exists(dead))


if __name__ == "__main__":
    unittest.main()
