"""A LIVE pid must never read as dead, because that hands out a running suite's lock.

MEASURED 2026-10-14. `suitelock._alive` ended in:

    return str(pid) in (out.stdout or "")

That expression cannot tell the process table SAYING THERE IS NO SUCH PID from
the process table BEING UNREADABLE. Both produce a string without the pid in it,
and both answered False - dead. `tasklist` returning zero rows for every query is
a measured property of this environment, recorded in CLAUDE.md, so the
broken-instrument case is real rather than theoretical.

The direction of the failure is the one that costs a run. `_takeable` reads
`if _alive(...): return False`, so a live holder read as dead makes the lock
TAKEABLE, and two full suites then run at once - the exact incident `suitelock`
was written after, where a port collision and a half-torn-down demo estate are
indistinguishable from a real failure.

WHAT THIS MODULE PINS, AND WHY EACH ONE IS HERE:

* an unreadable table is UNKNOWN, and UNKNOWN is never DEAD
* a live holder's lock is NOT takeable when the table cannot be read -
  `TheMutationControl` proves that assertion is load-bearing by collapsing
  UNKNOWN back into DEAD and watching the same lock become takeable again
* a MEASURED dead holder is STILL takeable, because a fix that made every lock
  unstealable would break recovery from a power loss and would pass every test
  above it
* the instrument self-checks against `os.getpid()` before DEAD stands
* a waiter's queue ticket is not deleted on an unreadable table either, which is
  the second place the same answer did harm: the FIFO position the ticket queue
  exists to protect

THE PATTERN THIS BELONGS TO. Four controls in this repository have been found
unable to fail: `test_invariants`' allowlist exempting 258/258 files,
`CAPS_ENFORCED_ELSEWHERE` naming absent keys, `run_suite` classifying
`Ran 0 tests` as PASS, and this one. A FIFTH is worth recording here because it
is in the test suite rather than in production code: `test_one_full_suite_at_a_time`
already carries a class named `AnUnknownPidCountsAsAlive`, and it asserts only
that `"not-a-pid"`, `None` and `0` are not alive and that `os.getpid()` is. Those
are malformed INPUTS, not unknown ANSWERS. The property in the class's own name -
that an unreadable process table counts as alive - was never once asserted, which
is how the defect survived under a test named for it.
"""
import json
import os
import time
import unittest

from src import suitelock


#: One row of `tasklist /NH` output, in the shape this machine produces it.
ROW = "python.exe                   %d Console                    1     13,712 K"

#: `tasklist`'s own positive statement that a pid does not exist.
NO_SUCH = "INFO: No tasks are running which match the specified criteria."


class Answer:
    """What `subprocess.run` returns, as much of it as `_read_table` reads."""

    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = ""


def table(alive=(), returncode=0, blank=False, raises=None):
    """A process-table reader, injected the way `liststaging` injects a reader.

    HONEST BY DEFAULT: it reports the pids in `alive` as running and positively
    denies every other one, which is what the real instrument does. That matters
    for the self-check - a fake that denied every pid including `os.getpid()`
    would make every answer UNKNOWN and the DEAD cases below would pass for the
    wrong reason.
    """
    def run(cmd, **_):
        if raises is not None:
            raise raises
        if blank:
            return Answer("", returncode)
        pid = int(cmd[2].split()[-1])           # cmd[2] is "PID eq <n>"
        if pid in alive:
            return Answer(ROW % pid, returncode)
        return Answer(NO_SUCH, returncode)
    return run


def lockfile(tmpdir, holder):
    """A lock file on disk naming `holder`, since `_takeable` reads its mtime."""
    path = os.path.join(tmpdir, "suite.lock")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(holder, handle)
    return path


class TheInstrumentIsCheckedBeforeItIsBelieved(unittest.TestCase):

    def test_the_real_process_table_finds_this_process(self):
        """THE POSITIVE CONTROL, and it is not ceremony.

        Every other test here injects a fake table. This one asks the REAL one,
        with no runner, for a pid that is certainly alive - this process. If it
        fails, the instrument is void on this machine and no answer `suitelock`
        gives about any holder means anything. That is worth a red test rather
        than a skip.
        """
        self.assertIs(suitelock.ALIVE, suitelock._probe(os.getpid()))

    def test_a_pid_the_table_positively_denies_is_dead(self):
        """A measurement, not an absence of one: `tasklist` said so in words."""
        foreign = os.getpid() + 1
        probe = suitelock._probe(foreign, runner=table(alive=(os.getpid(),)))
        self.assertIs(suitelock.DEAD, probe)

    def test_an_empty_table_is_unknown_not_dead(self):
        """THE MEASURED FAILURE. Zero bytes is not a statement about the pid."""
        probe = suitelock._probe(os.getpid(), runner=table(blank=True))
        self.assertIs(suitelock.UNKNOWN, probe)

    def test_the_old_expression_would_have_called_that_same_pid_dead(self):
        """The defect, next to the fix, on the one input that distinguishes them."""
        live = os.getpid()
        produced_by_a_broken_table = ""
        self.assertFalse(str(live) in produced_by_a_broken_table)   # the old DEAD
        self.assertIs(suitelock.UNKNOWN,
                      suitelock._probe(live, runner=table(blank=True)))

    def test_a_table_that_could_not_be_run_at_all_is_unknown(self):
        probe = suitelock._probe(os.getpid(), runner=table(raises=OSError("no exe")))
        self.assertIs(suitelock.UNKNOWN, probe)

    def test_a_nonzero_exit_is_unknown_even_with_plausible_output(self):
        """Output that arrived alongside a failure is not a reading."""
        probe = suitelock._probe(os.getpid() + 1,
                                 runner=table(alive=(os.getpid(),), returncode=1))
        self.assertIs(suitelock.UNKNOWN, probe)

    def test_the_self_check_turns_a_dead_answer_into_unknown(self):
        """An instrument that cannot find THIS process cannot find anything.

        The fake here denies every pid, `os.getpid()` included. Without the
        self-check the foreign pid would read DEAD - which is exactly the shape
        of the Git Bash reading that briefly reported a live holder gone.
        """
        deny_everything = table(alive=())
        self.assertIs(suitelock.DEAD, suitelock._read_table(os.getpid(),
                                                            deny_everything))
        self.assertIs(suitelock.UNKNOWN,
                      suitelock._probe(os.getpid() + 1, runner=deny_everything))

    def test_a_row_naming_a_different_pid_is_not_this_pid(self):
        """`768` is a substring of `57681`. The old check matched on substrings."""
        def one_row(cmd, **_):
            return Answer(ROW % 57681)
        self.assertIsNot(suitelock.ALIVE, suitelock._probe(768, runner=one_row))

    def test_a_malformed_pid_is_dead_rather_than_unknown(self):
        """Kept deliberately: a damaged lock carries `pid: None`, and its own
        `DAMAGED_GRACE` path - tested below - depends on that reading as dead
        rather than as an unreadable table."""
        for bad in (None, "not-a-pid", 0, -1):
            self.assertIs(suitelock.DEAD, suitelock._probe(bad), bad)

    def test_alive_reports_an_unknown_answer_as_alive(self):
        """The contract `_alive`'s docstring always claimed, now kept."""
        self.assertTrue(suitelock._alive(os.getpid(), runner=table(blank=True)))
        self.assertTrue(suitelock._alive(os.getpid() + 1, runner=table(blank=True)))


class AnUnreadableTableNeverStealsALock(unittest.TestCase):
    """The consequence the three-way answer exists for."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="suitelock-probe-")
        self.holder = {"pid": os.getpid(), "branch": "a-run-that-is-working",
                       "started_at": "2026-10-14T19:07:15"}
        self.path = lockfile(self.tmp, self.holder)

    def test_a_live_holders_lock_is_not_takeable_when_the_table_is_blank(self):
        """THE TEST THAT GOES RED IF THE DISTINCTION IS REMOVED.

        The holder is genuinely alive - it is this process. The table cannot be
        read. Collapse UNKNOWN into DEAD and this lock becomes takeable, two
        suites run, and the module has failed at the one thing it exists for.
        """
        self.assertFalse(suitelock._takeable(self.path, self.holder,
                                             runner=table(blank=True)))

    def test_nor_when_the_table_could_not_be_run(self):
        self.assertFalse(suitelock._takeable(
            self.path, self.holder, runner=table(raises=OSError("no exe"))))

    def test_nor_when_the_lock_is_old_enough_that_a_grace_would_have_expired(self):
        """`DAMAGED_GRACE` must NOT be applied to an unreadable table.

        A suite runs for 2100-2720s, so a working holder's lock is minutes old by
        construction. Any grace measured against the lock's mtime expires while
        the holder is still working - a slower version of the same theft. The
        lock here is aged well past the grace and must still be refused.
        """
        old = time.time() - (suitelock.DAMAGED_GRACE + 600)
        os.utime(self.path, (old, old))
        self.assertFalse(suitelock._takeable(self.path, self.holder,
                                             runner=table(blank=True)))

    def test_a_measured_dead_holder_is_still_takeable(self):
        """THE CONTROL ON THE FIX ITSELF.

        A fix that simply never took a lock would pass every test above it and
        would break the property the module documents: a machine that lost power
        mid-suite must not need a human to delete a file. So a holder the table
        positively denies must still be takeable.
        """
        dead = {"pid": os.getpid() + 1, "branch": "died-mid-suite"}
        path = lockfile(self.tmp, dead)
        self.assertTrue(suitelock._takeable(path, dead,
                                            runner=table(alive=(os.getpid(),))))

    def test_a_damaged_lock_is_still_governed_by_the_grace(self):
        """The pre-existing property, unchanged by this work, in both directions."""
        damaged = {"pid": None, "damaged": True}
        path = lockfile(self.tmp, damaged)
        self.assertFalse(suitelock._takeable(path, damaged))
        old = time.time() - (suitelock.DAMAGED_GRACE + 60)
        os.utime(path, (old, old))
        self.assertTrue(suitelock._takeable(path, damaged))


class TheMutationControl(unittest.TestCase):
    """Proof that the assertion above is load-bearing rather than incidental.

    Same shape as `test_a_suite_that_ran_nothing_is_not_a_pass`: break the one
    distinction deliberately and show the verdict flips back to the dangerous
    answer. If this test ever fails, the test above it is passing for some other
    reason and is no longer evidence.
    """

    def test_collapsing_unknown_into_dead_makes_the_live_holders_lock_takeable(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="suitelock-mutant-")
        holder = {"pid": os.getpid(), "branch": "a-run-that-is-working"}
        path = lockfile(tmp, holder)
        blank = table(blank=True)

        self.assertFalse(suitelock._takeable(path, holder, runner=blank))

        original = suitelock._probe

        def collapsed(pid, runner=None):
            """`_probe` as it would be with the distinction removed."""
            answer = original(pid, runner)
            return suitelock.DEAD if answer is suitelock.UNKNOWN else answer

        suitelock._probe = collapsed
        try:
            self.assertTrue(
                suitelock._takeable(path, holder, runner=blank),
                "the mutant did not reintroduce the defect, so the test above "
                "it is not proving what it claims")
        finally:
            suitelock._probe = original

        self.assertFalse(suitelock._takeable(path, holder, runner=blank))


class AWaitersTicketSurvivesAnUnreadableTable(unittest.TestCase):
    """The second place the same answer did harm.

    `_live_tickets` deletes the ticket of any pid that is not alive. A live waiter
    read as dead loses its FIFO position - and the ticket queue exists because a
    waiter overtaken repeatedly times out without running a single test, which
    cost this project its frozen master reference once.
    """

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="suitelock-queue-")
        self.lock = os.path.join(self.tmp, "suite.lock")
        directory = suitelock._queue_dir(self.lock)
        os.makedirs(directory, exist_ok=True)
        self.ticket = os.path.join(
            directory, "%020.6f-%d.json" % (time.time() - 100, os.getpid()))
        with open(self.ticket, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid()}, handle)

    def swap_probe(self, answer):
        original = suitelock._probe
        suitelock._probe = lambda pid, runner=None: answer
        self.addCleanup(lambda: setattr(suitelock, "_probe", original))

    def test_an_unknown_pid_keeps_its_place_in_the_queue(self):
        self.swap_probe(suitelock.UNKNOWN)
        self.assertIn(self.ticket, suitelock._live_tickets(self.lock))
        self.assertTrue(os.path.exists(self.ticket))

    def test_a_measured_dead_pid_is_reaped_so_the_queue_cannot_wedge(self):
        """The control: UNKNOWN must not have made the queue un-reapable."""
        self.swap_probe(suitelock.DEAD)
        self.assertEqual([], suitelock._live_tickets(self.lock))
        self.assertFalse(os.path.exists(self.ticket))


if __name__ == "__main__":
    unittest.main()
