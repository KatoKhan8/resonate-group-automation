"""A lane that looped and then exited is DOWN, not STUCK.

WHAT THIS FILE IS FOR. `LANE-webapp.md`, TASK-0260 section 8, filed this as
a gap left open and did not fix it:

    `stuck_run` does not treat a `watcher down.` record as ending a refusal
    loop, so a lane that looped and then exited can read `V_STUCK` - *"the
    watcher is alive and REFUSING"* - which outranks the down branch and
    would mask all three STOP verdicts. **It is not firing today**:
    `is_stuck` is False on all seven, measured at 14:00 and again at 14:22,
    so the real three are unaffected. The fix is one line in `stuck_run`,
    and it changes a verdict this brief did not send me to change. **Filed,
    not fixed.**

TASK-0290 is the file that was written for it. The fix is the one line
section 8 named: a `down` event ends a refusal run exactly as a START or a
DONE ends one.

WHY THE DIRECTION MATTERS. `V_STUCK` is taken BEFORE the down branch, on
purpose - a refusal loop with a live watcher outranks everything, because
both of the authorities the cross reads agree on RUNNING while the lane does
nothing. But the verdict's own words are *"the watcher is alive and
REFUSING"*, and after a `watcher down.` record neither half of that is true.
So the loop that STUCK describes has ended, and the three verdicts behind the
down branch - STOPPED, STOP-EXPIRED and DOWN-UNEXPLAINED - are what a reader
needs, because each has a different repair and one of them says *do not
restart this lane*.

BOTH DIRECTIONS, AND THE TEETH. `TheLoopStillHasTeeth` is not decoration: a
fix that made `stuck_run` return `None` more often could be a fix or could be
the refusal loop detector switched off, and those are indistinguishable from
the down case alone. Every one of its tests passes BEFORE the change as well
as after, and `test_a_loop_that_resumes_after_the_down_is_a_loop_again`
proves the run ENDS at the record rather than being disabled by it.

NOTHING HERE READS THE REAL ESTATE. Every log, pid file and STOP file below
is a string this test writes into a temporary directory, and the process
table is a dict handed to the reader.
"""
import datetime
import os
import shutil
import tempfile
import unittest

from src import lanes

#: Late enough that a loop opened at 00:10 has outlived the fixture lane's own
#: 90-minute timeout, which is what `is_stuck` requires. A loop inside the
#: timeout is not STUCK at all and could not mask anything.
NOW = datetime.datetime(2026, 10, 16, 3, 0, 0)
LANE = "alpha"
WATCHER_PID = 4242
DAY = "2026-10-16"


def line(clock, message, lane=LANE, day=DAY):
    """One watcher record, in the shape `lane_watcher.ps1` writes."""
    return "[%s %s] [%s] %s" % (day, clock, lane, message)


def up(clock="00:00:00", timeout=90):
    return line(clock, "watcher up. tree=C:\\somewhere mode=bypassPermissions "
                       "timeout=%dm" % timeout)


def blocked(clock, brief="0010-a.md"):
    """The refusal loop line, verbatim from the real logs."""
    return line(clock, "a task is already in RUNNING: %s, "
                       "not starting another" % brief)


def down(clock):
    """The watcher's own exit record, verbatim from the real logs."""
    return line(clock, "watcher down.")


class FakeProbe:
    """`{pid: (parent_pid, image)}`, handed to the reader and never measured.

    The watcher is IN the table and a child is under it, so every liveness
    signal this board reads says the lane is alive. That is deliberate: it is
    the state in which the old `stuck_run` produced STUCK, and a fixture that
    killed the watcher in the table too would be proving the fix with the
    wrong authority.
    """

    def table(self):
        return {WATCHER_PID: (1, "powershell.exe"),
                4243: (WATCHER_PID, "node.exe")}

    def cpu(self, pid):
        return 12.5


class Estate:

    def setUp(self):
        super().setUp()
        self.root = tempfile.mkdtemp(prefix="rga-0290-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, "logs"))
        os.makedirs(os.path.join(self.root, "queue", LANE, "RUNNING"))
        os.makedirs(os.path.join(self.root, "queue", LANE, "DONE"))
        self.write(os.path.join(self.root, "queue", "README.md"),
                   "# LANE QUEUE\n\n**Floor: never leave a lane below 3 "
                   "queued briefs.**\n")
        self.write(os.path.join(self.root, "logs", "watcher-%s.pid" % LANE),
                   "%d\n" % WATCHER_PID)
        self.write(os.path.join(self.root, "LANE-%s.md" % LANE),
                   "## entry 2026-10-16\n")
        previous = os.environ.get(lanes.OPS_DIR)
        os.environ[lanes.OPS_DIR] = self.root
        self.addCleanup(self._restore, previous)

    @staticmethod
    def _restore(previous):
        if previous is None:
            os.environ.pop(lanes.OPS_DIR, None)
        else:
            os.environ[lanes.OPS_DIR] = previous

    @staticmethod
    def write(path, text):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def log(self, *rows):
        self.write(os.path.join(self.root, "logs", "watcher-%s.log" % LANE),
                   "\n".join(rows) + "\n")

    def stop_file(self, text):
        self.write(os.path.join(self.root, lanes.STOP_PREFIX + LANE), text)

    def events(self):
        state, rows, _ = lanes._read_tail(
            os.path.join(self.root, "logs", "watcher-%s.log" % LANE))
        self.assertEqual(state, lanes.PRESENT)
        return lanes.watcher_events(rows, LANE)

    def row(self, now=None):
        data = lanes.board(root=self.root, now=now or NOW, probe=FakeProbe(),
                           samples={})
        return [item for item in data["lanes"] if item["lane"] == LANE][0]

    def looped(self, *tail):
        """A START, two hours of refusals, then whatever the case adds."""
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 blocked("01:00:00"), blocked("02:00:00"), *tail)


class ADownRecordEndsTheRun(Estate, unittest.TestCase):
    """The seam. `stuck_run` is the one function section 8 named."""

    def test_the_down_record_is_parsed_as_a_down_event(self):
        """The premise, measured rather than assumed: if the reader did not
        parse the line at all there would be nothing for the run to end on,
        and the repair would be in `watcher_events` instead."""
        self.looped(down("02:30:00"))
        kinds = [event["kind"] for event in self.events()]
        self.assertEqual(kinds, ["up", "start", "blocked", "blocked", "down"])

    def test_a_loop_the_watcher_exited_out_of_is_not_a_loop(self):
        self.looped(down("02:30:00"))
        self.assertIsNone(lanes.stuck_run(self.events()))

    def test_the_whole_run_is_dropped_and_not_merely_shortened(self):
        """A fix that only stopped COUNTING the refusals after the record
        would still return a loop, and `is_stuck` only reads `began_when`."""
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 blocked("01:00:00"), down("02:30:00"))
        self.assertIsNone(lanes.stuck_run(self.events()))


class TheSecondGuardSectionEightDidNotKnowAbout(Estate, unittest.TestCase):
    """Section 8's CONSEQUENCE did not survive measurement, and this is it.

    Section 8 wrote that STUCK *"outranks the down branch and would mask all
    three STOP verdicts"*. In the shape it describes - a lane that looped and
    then exited - **it cannot**, and the reason is a different mechanism than
    the one it named. `timeout_reading` walks the log backwards and returns
    `T_SUPERSEDED` the moment the newest up/down record is a `down`:

        A `watcher down.` NEWER THAN THAT LINE SUPERSEDES IT. A watcher that
        has exited is enforcing nothing, so there is no timeout in force

    `is_stuck` requires `lane_timeout is not None`, so with no timeout in
    force it is False whatever `stuck_run` returns, and the three STOP
    verdicts print. **EVERY TEST IN THIS CLASS PASSES BEFORE THE FIX AS WELL
    AS AFTER**, and that is the finding rather than a weakness: they are
    reachability controls on a second, independent guard, and if somebody
    ever removes `T_SUPERSEDED` they are what says the masking has become
    live. `TheShapeWhereTheMaskingDoesFire` holds the shape that gets past
    this guard, and that one does move with the fix.
    """

    def test_a_log_ending_in_the_down_record_has_no_timeout_in_force(self):
        """The guard itself, asserted directly rather than inferred from the
        verdict it produces."""
        self.looped(down("02:30:00"))
        reading = lanes.timeout_reading(self.events())
        self.assertEqual(reading["state"], lanes.T_SUPERSEDED)
        self.assertIsNone(reading["minutes"])
        self.assertIn("watcher down.", reading["from_line"])

    def test_stopped_is_not_masked(self):
        """Down on purpose, with a lift moment that has not arrived. The one
        verdict that says DO NOT RESTART THIS LANE."""
        self.looped(down("02:30:00"))
        self.stop_file("Operator stopped this lane; quota.\n"
                       "Resumes 2026-10-20 09:00.\n")
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_STOPPED)
        self.assertFalse(row["is_stuck"])

    def test_stop_expired_is_not_masked(self):
        """The lift moment has passed and the file is still there, so a
        person has to clear it. Not the same instruction as STOPPED."""
        self.looped(down("02:30:00"))
        self.stop_file("Operator stopped this lane.\nResumes 2026-10-14 "
                       "09:00.\n")
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_STOP_EXPIRED)

    def test_down_unexplained_is_not_masked(self):
        """No STOP file at all. The watcher exited and nothing says why -
        which is the fail-closed default and still not STUCK."""
        self.looped(down("02:30:00"))
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_DOWN_UNEXPLAINED)

    def test_the_row_no_longer_claims_a_live_refusal_loop(self):
        """The one test in this class that DOES move with the fix, and the
        one cell section 8's shape was getting wrong: the verdict was right
        all along and the row beside it still reported a refusal loop
        belonging to a watcher that had exited."""
        self.looped(down("02:30:00"))
        self.stop_file("Operator stopped this lane.\nResumes 2026-10-20.\n")
        row = self.row()
        self.assertIsNone(row["refusal_loop"])
        self.assertFalse(row["stuck_undecidable"])


class TheShapeWhereTheMaskingDoesFire(Estate, unittest.TestCase):
    """The log shape that gets PAST `T_SUPERSEDED`, and it is reachable.

    A `down` record with a LATER `watcher up` puts a timeout back in force,
    so the backward walk never reaches the down record and `is_stuck` is
    decidable again. Under the pre-fix `stuck_run` the refusal run before the
    `down` was still the trailing run - `up` and `idle` do not end a run,
    only START, DONE and (now) `down` do - so a loop from the DEAD watcher's
    generation was measured against the LIVE one's timeout, read STUCK, and
    outranked the down branch. Measured both directions on 2026-10-17: with
    the one-line fix this shape prints STOPPED, and with it reverted it
    prints STUCK.

    THE REAL SEQUENCE THIS IS: a watcher logged `watcher down.`, the launcher
    brought it back up, and the new one was taken by `Stop-Process` - which
    writes no record at all and is documented as the common way a watcher
    dies. DOWN's second disjunct (`watcher_alive is False and gone_quiet`)
    is what then reaches the down branch, so the fixture's process table must
    NOT hold the watcher - which is the one thing that differs from the class
    above.
    """

    def setUp(self):
        super().setUp()
        self.log(up("00:00:00"),
                 line("00:10:00", "START 0010-a.md"),
                 line("00:20:00", "DONE  0010-a.md -> exit0"),
                 blocked("01:00:00", brief="0020-b.md"),
                 blocked("01:30:00", brief="0020-b.md"),
                 down("02:00:00"),
                 up("02:01:00"))

    def row(self, now=None):
        """The same board, with the watcher ABSENT from the process table."""
        data = lanes.board(root=self.root, now=now or NOW,
                           probe=NoWatcherProbe(), samples={})
        return [item for item in data["lanes"] if item["lane"] == LANE][0]

    def test_the_timeout_is_back_in_force_so_the_second_guard_is_silent(self):
        """The premise. Without this the class would be proving nothing
        beyond what `T_SUPERSEDED` already proves."""
        reading = lanes.timeout_reading(self.events())
        self.assertEqual(reading["state"], lanes.T_IN_FORCE)
        self.assertEqual(reading["minutes"], 90)

    def test_the_refusals_are_in_the_log_so_the_fixture_is_not_empty(self):
        """A fixture with no refusal lines in it would print STOPPED for a
        reason that has nothing to do with the fix."""
        kinds = [event["kind"] for event in self.events()]
        self.assertEqual(kinds.count("blocked"), 2)

    def test_the_dead_generations_loop_is_not_the_current_state(self):
        self.assertIsNone(lanes.stuck_run(self.events()))

    def test_stopped_prints_instead_of_stuck(self):
        self.stop_file("Operator stopped this lane; quota.\n"
                       "Resumes 2026-10-20 09:00.\n")
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_STOPPED)
        self.assertFalse(row["is_stuck"])

    def test_down_unexplained_prints_instead_of_stuck(self):
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_DOWN_UNEXPLAINED)


class NoWatcherProbe:
    """The pid file names a watcher the table does not hold.

    `Stop-Process` took it and the log simply stopped, which is the shape
    DOWN's second disjunct exists for. Kept apart from `FakeProbe` on
    purpose: with the watcher ALIVE in the table this estate is not down at
    all, and the masking has nothing to mask.
    """

    def table(self):
        return {7777: (1, "explorer.exe")}

    def cpu(self, pid):
        return 0.0


class TheLoopStillHasTeeth(Estate, unittest.TestCase):
    """The control FOR the fix. Every test here passes before it as well.

    `stuck_run` returning `None` more often is exactly what a switched-off
    refusal detector looks like. These are the cases that must not move.
    """

    def test_a_live_loop_with_no_down_record_is_still_stuck(self):
        self.looped()
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_STUCK)
        self.assertTrue(row["is_stuck"])
        self.assertEqual(row["refusal_loop"]["count"], 2)

    def test_stuck_still_outranks_a_stop_file_while_the_watcher_lives(self):
        """A STOP file beside a LIVE refusal loop is a contradiction, and
        the live state wins: something is still running in that lane."""
        self.looped()
        self.stop_file("Operator stopped this lane.\nResumes 2026-10-20.\n")
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_STUCK)

    def test_the_elapsed_is_still_measured_from_the_start(self):
        self.looped()
        loop = lanes.stuck_run(self.events())
        self.assertTrue(loop["from_a_start"])
        self.assertEqual(loop["began_at"], "2026-10-16 00:10:00")

    def test_a_loop_that_resumes_after_the_down_is_a_loop_again(self):
        """The record ENDS a run; it does not disable detection for the rest
        of the log. A watcher that came back up and started refusing is a
        new loop, and it is the current state of the lane."""
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 blocked("00:20:00"), down("00:30:00"),
                 up("00:40:00"), blocked("01:00:00"), blocked("02:00:00"))
        loop = lanes.stuck_run(self.events())
        self.assertIsNotNone(loop)
        self.assertEqual(loop["count"], 2)
        self.assertEqual(loop["began_at"], "2026-10-16 01:00:00")
        self.assertFalse(loop["from_a_start"],
                         "the START before the down record is not this "
                         "loop's start - the task it named is long gone")
        self.assertEqual(self.row()["verdict"], lanes.V_STUCK)

    def test_a_loop_with_no_down_record_at_all_is_untouched(self):
        """The population the fix must not reach: a refusal run with no
        `down` record anywhere in the log.

        THE VERDICT IS DELIBERATELY NOT ASSERTED HERE. In this shape, with
        the watcher ABSENT from the process table, the board prints STUCK -
        measured 2026-10-17 - and `VERDICT_TEXT[V_STUCK]` says the watcher
        is alive and REFUSING, which it is not: `is_stuck` never consults
        `watcher_alive`. That is an adjacent defect of the same family,
        FILED by TASK-0290 and not fixed by it, and asserting the current
        verdict here would freeze it into the suite.
        """
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 line("00:20:00", "DONE  0010-a.md -> exit0"),
                 blocked("01:00:00", brief="0020-b.md"),
                 blocked("01:30:00", brief="0020-b.md"))
        loop = lanes.stuck_run(self.events())
        self.assertEqual(loop["count"], 2)
        self.assertEqual(loop["task"], "0020-b.md")

    def test_a_down_before_any_refusal_changes_nothing(self):
        """The ordinary shape of every lane log in the estate: watchers go
        down and come up again all day. A `down` record earlier in the file
        must not reach a loop that opened after it."""
        self.log(up(), down("00:05:00"), up("00:06:00"),
                 line("00:10:00", "START 0010-a.md"),
                 blocked("01:00:00"), blocked("02:00:00"))
        self.assertEqual(lanes.stuck_run(self.events())["count"], 2)
        self.assertEqual(self.row()["verdict"], lanes.V_STUCK)


if __name__ == "__main__":
    unittest.main()
