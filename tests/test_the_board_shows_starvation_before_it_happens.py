"""Which lane is about to run out of work, and the state nothing measured.

WHAT THIS FILE IS FOR. TASK 0040's board answers "what is each lane doing".
Over 2026-10-15 01:30 -> 2026-10-16 00:45 the seven lanes did 38.8 lane-hours
of work in ~137 lane-hours of wall clock - 28% - and **89.9 of the 94.3
lane-hours lost to gaps were an empty queue, not a broken lane**. The board
could not see that, because queue depth without a per-lane task duration is
not an answer about autonomy.

THE STATE THAT MATTERS MOST, and it is a correction rather than a feature. A
watcher whose task owner has died writes

    a task is already in RUNNING: <brief>, not starting another

every twenty seconds. 139 of those across five lanes in one day, 7.66
lane-hours. `watcher_events` did not parse the line at all - it is not a
`REFUSING:` line - so the reader saw only the stale START with no DONE, the
watcher process WAS alive, and both authorities agreed on RUNNING. **A lane
doing nothing for 97 minutes read as healthy, twice.** So:

    the log is MOVING, so every freshness check calls it healthy;
    RUNNING/ has a brief in it, so that signal calls it busy;
    the process table has the watcher alive, so that calls it alive.

All three are satisfied by a dead lane. The only thing that distinguishes it
is the refusal line itself, and it must outlive THAT LANE's own timeout -
which is read from its own `watcher up` line, because PowerShell parses a
`-File` script once at load and a running watcher keeps the constant it
started with.

NOTHING HERE READS THE REAL ESTATE. Every log is a string this test writes
into a temporary directory and every process table is a dict handed to the
reader. The three signals TASK 0040 measured wrong are not used by any
assertion here, and three tests prove they are not consulted.
"""
import datetime
import os
import shutil
import tempfile
import unittest

from src import lanes
from src.web import api, pages

NOW = datetime.datetime(2026, 10, 16, 3, 0, 0)
LANE = "alpha"

#: The pid the fixture estate's `watcher-<lane>.pid` names. The reader finds
#: the watcher through that file and walks its descendants, so a test that
#: writes no pid file gets UNCROSSED - correctly, because liveness then has
#: no authority at all.
WATCHER_PID = 4242


def line(clock, message, lane=LANE, day="2026-10-16"):
    """One watcher record, in the exact shape `lane_watcher.ps1` writes."""
    return "[%s %s] [%s] %s" % (day, clock, lane, message)


def up(clock="00:00:00", timeout=90, day="2026-10-16"):
    return line(clock, "watcher up. tree=C:\\somewhere mode=bypassPermissions "
                       "timeout=%dm" % timeout, day=day)


def blocked(clock, brief="0010-a.md", day="2026-10-16"):
    """The refusal loop line, verbatim from the real logs."""
    return line(clock, "a task is already in RUNNING: %s, "
                       "not starting another" % brief, day=day)


class Estate:
    """A temporary lane estate, thrown away per test."""

    def setUp(self):
        super().setUp()
        self.root = tempfile.mkdtemp(prefix="rga-starve-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, "logs"))
        os.makedirs(os.path.join(self.root, "queue", LANE, "RUNNING"))
        os.makedirs(os.path.join(self.root, "queue", LANE, "DONE"))
        # THE FLOOR IS READ, NOT ASSUMED, so a fixture estate without this
        # file has an UNKNOWN floor and no breach verdict at all - which is
        # the behaviour `tests/test_a_breach_of_the_floor_is_only_known_...`
        # asserts directly. Written here in the operator's own words so the
        # reader under test is exercised against the real sentence.
        self.readme(3)
        with open(os.path.join(self.root, "logs", "watcher-%s.pid" % LANE),
                  "w", encoding="utf-8", newline="\n") as handle:
            handle.write("%d\n" % WATCHER_PID)
        with open(os.path.join(self.root, "LANE-%s.md" % LANE), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("## entry 2026-10-16\n")
        previous = os.environ.get(lanes.OPS_DIR)
        os.environ[lanes.OPS_DIR] = self.root
        self.addCleanup(self._restore, previous)

    @staticmethod
    def _restore(previous):
        if previous is None:
            os.environ.pop(lanes.OPS_DIR, None)
        else:
            os.environ[lanes.OPS_DIR] = previous

    def readme(self, floor):
        """`queue/README.md` as the operator writes it, or no floor at all.

        `floor=None` writes a README with everything EXCEPT the floor
        sentence, which is the case the reader has to call UNSTATED rather
        than fill in with 3.
        """
        body = ["# LANE QUEUE", "", "## Queue depth"]
        if floor is not None:
            body.append("**Floor: never leave a lane below %d queued "
                        "briefs.**" % floor)
        with open(os.path.join(self.root, "queue", "README.md"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(body) + "\n")

    def log(self, *rows):
        path = os.path.join(self.root, "logs", "watcher-%s.log" % LANE)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(rows) + "\n")
        return path

    def queue(self, *names):
        for name in names:
            with open(os.path.join(self.root, "queue", LANE, name), "w",
                      encoding="utf-8", newline="\n") as handle:
                handle.write("# a brief\n")

    def running(self, name):
        with open(os.path.join(self.root, "queue", LANE, "RUNNING", name),
                  "w", encoding="utf-8", newline="\n") as handle:
            handle.write("# in flight\n")

    def events(self):
        state, rows, _ = lanes._read_tail(
            os.path.join(self.root, "logs", "watcher-%s.log" % LANE))
        self.assertEqual(state, lanes.PRESENT)
        return lanes.watcher_events(rows, LANE)

    def row(self, alive=True, now=None, watcher=True,
            unreadable_table=False):
        """One lane row, with a supplied process table rather than a real one."""
        probe = FakeProbe(alive=alive, watcher=watcher,
                          unreadable_table=unreadable_table)
        data = lanes.board(root=self.root, now=now or NOW, probe=probe,
                           samples={})
        return [r for r in data["lanes"] if r["lane"] == LANE][0]


class FakeProbe:
    """A process table handed to the reader, never measured.

    `alive=False` returns a table holding the watcher and NOTHING under it,
    which is the real shape of a lane whose task has gone: the watcher is
    still there, its child is not.

    `watcher=False` drops the WATCHER ITSELF from the table, which is the
    shape of a lane whose watcher was taken by `Stop-Process`: the pid file
    still names it and the table does not hold it. That is a different state
    from `alive=False` and the two were previously indistinguishable here,
    which is why the second disjunct of DOWN went unbuilt.

    `unreadable_table=True` is the refusal: no table at all, so liveness is
    UNKNOWN and must not produce DOWN any more than it produces healthy.
    """

    def __init__(self, alive=True, watcher=True, unreadable_table=False):
        self.alive = alive
        self.watcher = watcher
        self.unreadable_table = unreadable_table

    def table(self):
        # `{pid: (parent_pid, image)}` - the shape `_nt_table` returns. Built
        # by hand here so that a change to that shape fails in this file
        # rather than producing a board that reads every lane UNCROSSED.
        if self.unreadable_table:
            return None
        rows = {}
        if self.watcher:
            rows[WATCHER_PID] = (1, "powershell.exe")
        else:
            # Something unrelated, so the table is READ and simply does not
            # hold this watcher - which is a measurement, not an absence.
            rows[7777] = (1, "explorer.exe")
        if self.alive:
            rows[4243] = (WATCHER_PID, "node.exe")
        return rows

    def cpu(self, pid):
        return 12.5


# --------------------------------------------------------------------------
# STUCK - the refusal loop. The most expensive state in the estate.
# --------------------------------------------------------------------------

class TheRefusalLoopIsNotRunning(Estate, unittest.TestCase):

    def stuck_log(self, started="00:10:00", last="02:40:00", timeout=90):
        """A task started, then refusals, with the watcher still alive."""
        rows = [up(timeout=timeout), line(started, "START 0010-a.md")]
        clock = 1
        while clock <= 40:
            rows.append(blocked("%02d:%02d:00" % (clock // 60 + 2, clock % 60)))
            clock += 1
        rows.append(blocked(last))
        return self.log(*rows)

    def test_the_refusal_line_is_parsed_at_all(self):
        """It is not a `REFUSING:` line, so the reader ignored it entirely
        and the lane read RUNNING off the stale START."""
        self.stuck_log()
        kinds = {e["kind"] for e in self.events()}
        self.assertIn("blocked", kinds)

    def test_the_blocked_event_carries_the_brief_it_names(self):
        self.stuck_log()
        found = [e for e in self.events() if e["kind"] == "blocked"]
        self.assertTrue(found)
        self.assertEqual(found[0]["task"], "0010-a.md")

    def test_a_loop_past_the_lanes_own_timeout_is_stuck(self):
        self.stuck_log(started="00:10:00", last="02:40:00", timeout=90)
        row = self.row(alive=True)
        self.assertEqual(row["verdict"], lanes.V_STUCK)
        self.assertTrue(row["is_stuck"])

    def test_stuck_outranks_the_two_authorities_that_both_say_running(self):
        """The log has an open START and the watcher IS alive, so the cross
        agreed on RUNNING while the lane did nothing. That is the defect."""
        self.stuck_log()
        row = self.row(alive=True)
        self.assertEqual(row["status"], lanes.RUNNING,
                         "the log alone still says running - that is why "
                         "the cross got it wrong")
        self.assertGreater(row["cpu"]["count"], 0,
                           "a process IS alive under this watcher")
        self.assertEqual(row["verdict"], lanes.V_STUCK)

    def test_a_loop_inside_the_timeout_is_not_yet_stuck(self):
        """Before the timeout the task may simply be long. Shown, not
        cleared - hiding it until it qualifies would hide the lead time."""
        self.stuck_log(started="02:30:00", last="02:50:00", timeout=90)
        row = self.row(alive=True)
        self.assertFalse(row["is_stuck"])
        self.assertNotEqual(row["verdict"], lanes.V_STUCK)
        self.assertIsNotNone(row["refusal_loop"])

    def test_a_loop_whose_timeout_is_unknown_is_undecidable_not_healthy(self):
        """No `timeout=` field, so whether the loop has outlived it cannot
        be decided - and it is NOT called healthy."""
        self.log(line("00:00:00", "watcher up. tree=C:\\x mode=bypass"),
                 line("00:10:00", "START 0010-a.md"),
                 blocked("02:40:00"))
        row = self.row(alive=True)
        self.assertIsNone(row["timeout_minutes"])
        self.assertFalse(row["is_stuck"])
        self.assertTrue(row["stuck_undecidable"])
        self.assertIsNotNone(row["refusal_loop"])

    def test_a_start_after_the_loop_ends_it(self):
        """The lane moved, so the loop is history and not the current state."""
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 blocked("00:20:00"), blocked("00:21:00"),
                 line("00:30:00", "DONE  0010-a.md -> exit0"),
                 line("00:31:00", "START 0020-b.md"))
        row = self.row(alive=True)
        self.assertIsNone(row["refusal_loop"])
        self.assertEqual(row["verdict"], lanes.V_RUNNING)

    def test_a_different_brief_restarts_the_count(self):
        """Two loops are not one longer loop; counting them together would
        overstate how long this one has been open."""
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 blocked("00:20:00", brief="0010-a.md"),
                 blocked("00:21:00", brief="0010-a.md"),
                 blocked("00:22:00", brief="0020-b.md"))
        loop = lanes.stuck_run(self.events())
        self.assertEqual(loop["task"], "0020-b.md")
        self.assertEqual(loop["count"], 1)

    def test_the_elapsed_is_measured_from_the_start_not_the_first_refusal(self):
        """The task began at the START. Measuring from the first refusal
        would understate it by however long the task ran before dying."""
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 blocked("02:00:00"))
        loop = lanes.stuck_run(self.events())
        self.assertTrue(loop["from_a_start"])
        self.assertEqual(loop["began_at"], "2026-10-16 00:10:00")

    def test_a_loop_with_no_preceding_start_measures_from_the_refusal(self):
        self.log(up(), blocked("02:00:00"))
        loop = lanes.stuck_run(self.events())
        self.assertFalse(loop["from_a_start"])
        self.assertEqual(loop["began_at"], "2026-10-16 02:00:00")

    def test_no_refusals_means_no_loop(self):
        """A warning that is always on is a warning nobody reads."""
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 line("00:30:00", "DONE  0010-a.md -> exit0"))
        self.assertIsNone(lanes.stuck_run(self.events()))


# --------------------------------------------------------------------------
# The other four states, one fixture log each.
# --------------------------------------------------------------------------

class EachStateHasItsOwnWord(Estate, unittest.TestCase):

    def test_working(self):
        """START with no DONE, inside the timeout, something alive."""
        self.log(up(), line("02:50:00", "START 0010-a.md"))
        row = self.row(alive=True)
        self.assertEqual(row["verdict"], lanes.V_RUNNING)

    def test_idle(self):
        """Watcher up, newest record a DONE, nothing alive."""
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 line("00:30:00", "DONE  0010-a.md -> exit0"))
        row = self.row(alive=False)
        self.assertEqual(row["verdict"], lanes.V_IDLE)

    def test_down(self):
        """The last record is `watcher down`. NOT idle: idle means waiting
        for work, this means waiting for a person."""
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 line("00:30:00", "DONE  0010-a.md -> exit0"),
                 line("00:31:00", "watcher down"))
        row = self.row(alive=False)
        self.assertEqual(row["verdict"], lanes.V_DOWN)
        self.assertTrue(row["watcher_went_down"])

    def test_down_outranks_a_deep_queue(self):
        """Nothing is dispatched here however much work is waiting."""
        self.queue("0010-a.md", "0020-b.md", "0030-c.md", "0040-d.md")
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 line("00:30:00", "DONE  0010-a.md -> exit0"),
                 line("00:31:00", "watcher down"))
        row = self.row(alive=False)
        self.assertEqual(row["verdict"], lanes.V_DOWN)
        self.assertEqual(row["queue_depth"], 4)
        self.assertFalse(row["below_floor"])

    def test_unknown(self):
        """An unreadable log is UNKNOWN and is shown as itself. A board that
        renders it as IDLE is catalogue family 1."""
        row = self.row(alive=True)          # no log written at all
        self.assertEqual(row["verdict"], lanes.V_UNKNOWN)
        self.assertEqual(row["status"], lanes.UNKNOWN)

    def test_unknown_is_not_idle_and_carries_no_depth_claim(self):
        row = self.row(alive=True)
        self.assertNotEqual(row["verdict"], lanes.V_IDLE)
        self.assertIsNone(row["median_task_minutes"])
        self.assertIsNone(row["starvation_minutes"])

    def test_every_verdict_the_reader_can_return_has_words(self):
        """A verdict with no entry here arrives at the page as None and is
        rendered UNRECOGNISED - but it should never happen silently."""
        for name in dir(lanes):
            if name.startswith("V_"):
                self.assertIn(getattr(lanes, name), lanes.VERDICT_TEXT, name)


# --------------------------------------------------------------------------
# Depth, median, starvation, utilisation.
# --------------------------------------------------------------------------

class StarvationIsDepthTimesThisLanesOwnMedian(Estate, unittest.TestCase):

    def three_tasks(self):
        """Durations of 10, 20 and 30 minutes. Median 20."""
        return self.log(
            up(),
            line("00:00:00", "START 0001-a.md"),
            line("00:10:00", "DONE  0001-a.md -> exit0"),
            line("00:20:00", "START 0002-b.md"),
            line("00:40:00", "DONE  0002-b.md -> exit0"),
            line("01:00:00", "START 0003-c.md"),
            line("01:30:00", "DONE  0003-c.md -> exit0"))

    def test_the_median_is_this_lanes_own(self):
        self.three_tasks()
        self.assertEqual(lanes.median_minutes(self.events()), 20.0)

    def test_the_durations_are_paired_by_name_not_by_position(self):
        """An orphan START must not be paired with the NEXT task's DONE -
        that is two tasks plus a gap, and it would inflate the median the
        starvation estimate rests on."""
        self.log(up(),
                 line("00:00:00", "START 0001-killed.md"),
                 line("00:20:00", "START 0002-b.md"),
                 line("00:30:00", "DONE  0002-b.md -> exit0"))
        self.assertEqual(lanes.task_durations(self.events()), [10.0])

    def test_a_done_stamped_before_its_own_start_is_dropped(self):
        """Real artifact: lanes write their own DONE files and `Move-Item`
        preserves the original mtime, so a DONE can precede its START."""
        self.log(up(),
                 line("00:20:00", "START 0001-a.md"),
                 line("00:10:00", "DONE  0001-a.md -> exit0"))
        self.assertEqual(lanes.task_durations(self.events()), [])

    def test_starvation_is_depth_times_the_median(self):
        self.three_tasks()
        self.queue("0010-a.md", "0020-b.md", "0030-c.md")
        row = self.row(alive=False)
        self.assertEqual(row["queue_depth"], 3)
        self.assertEqual(row["median_task_minutes"], 20.0)
        self.assertEqual(row["starvation_minutes"], 60.0)

    def test_an_empty_queue_is_zero_minutes_of_autonomy(self):
        self.three_tasks()
        row = self.row(alive=False)
        self.assertEqual(row["queue_depth"], 0)
        self.assertEqual(row["starvation_minutes"], 0.0)
        self.assertTrue(row["below_floor"])

    def test_a_lane_with_no_completed_task_has_no_starvation_estimate(self):
        """None, not 0. "no autonomy left" and "nobody knows how much
        autonomy is left" are different alarms."""
        self.log(up(), line("02:50:00", "START 0010-a.md"))
        self.queue("0010-a.md", "0020-b.md")
        row = self.row(alive=True)
        self.assertIsNone(row["median_task_minutes"])
        self.assertIsNone(row["starvation_minutes"])

    def test_starvation_refuses_an_unknown_depth(self):
        self.assertIsNone(lanes.starvation(None, 20.0))

    def test_starvation_refuses_an_unknown_median(self):
        self.assertIsNone(lanes.starvation(3, None))

    def test_below_the_floor_is_named_and_the_floor_travels_with_the_data(self):
        self.three_tasks()
        self.queue("0010-a.md", "0020-b.md")
        row = self.row(alive=False)
        self.assertTrue(row["below_floor"])
        # THE FLOOR CAME OFF THE OPERATOR'S FILE, not off a constant in
        # `src.lanes`: the fixture wrote `**Floor: never leave a lane below 3
        # queued briefs.**` into `queue/README.md` and the row carries 3
        # because of that sentence. `lanes.FLOOR` no longer exists, and the
        # assertion below is what keeps it from coming back.
        self.assertEqual(row["floor"], 3)
        self.assertFalse(hasattr(lanes, "FLOOR"))

    def test_at_the_floor_is_not_below_it(self):
        self.three_tasks()
        self.queue("0010-a.md", "0020-b.md", "0030-c.md")
        self.assertFalse(self.row(alive=False)["below_floor"])

    def test_an_unreadable_queue_is_neither_a_breach_nor_compliance(self):
        self.three_tasks()
        shutil.rmtree(os.path.join(self.root, "queue", LANE))
        row = self.row(alive=False)
        self.assertIsNone(row["queue_depth"])
        self.assertIsNone(row["below_floor"])
        self.assertIsNone(row["starvation_minutes"])


class TheTimeoutComesFromTheLogAndNotTheScript(Estate, unittest.TestCase):
    """PowerShell parses a `-File` script once at load, so a running watcher
    keeps whatever constant it started with. `queue/README.md` records the
    constant moving to 150m while five of seven watchers still ran 90m."""

    def test_it_is_read_from_the_watcher_up_line(self):
        self.log(up(timeout=150), line("02:50:00", "START 0010-a.md"))
        self.assertEqual(lanes.timeout_minutes(self.events()), 150)

    def test_the_newest_watcher_up_line_wins(self):
        self.log(up(clock="00:00:00", timeout=90),
                 line("00:01:00", "watcher down"),
                 up(clock="00:02:00", timeout=150))
        self.assertEqual(lanes.timeout_minutes(self.events()), 150)

    def test_a_line_with_no_timeout_field_gives_none_not_a_default(self):
        """A guessed timeout would make every STUCK verdict a guess."""
        self.log(line("00:00:00", "watcher up. tree=C:\\x mode=bypass"))
        self.assertIsNone(lanes.timeout_minutes(self.events()))

    def test_the_row_says_where_the_timeout_came_from(self):
        self.log(up(timeout=90), line("02:50:00", "START 0010-a.md"))
        row = self.row(alive=True)
        self.assertEqual(row["timeout_minutes"], 90)
        self.assertIn("watcher up", row["timeout_from"])


class UtilisationComesFromPairedIntervals(Estate, unittest.TestCase):

    def test_busy_is_the_paired_interval(self):
        self.log(up(),
                 line("01:00:00", "START 0001-a.md"),
                 line("02:00:00", "DONE  0001-a.md -> exit0"))
        use = lanes.utilisation(self.events(), NOW)
        self.assertEqual(use["busy_seconds"], 3600)

    def test_an_open_start_counts_up_to_now(self):
        self.log(up(), line("02:00:00", "START 0001-a.md"))
        use = lanes.utilisation(self.events(), NOW)
        self.assertEqual(use["busy_seconds"], 3600)

    def test_a_gap_is_not_busy(self):
        self.log(up(),
                 line("00:00:00", "START 0001-a.md"),
                 line("00:30:00", "DONE  0001-a.md -> exit0"))
        use = lanes.utilisation(self.events(), NOW)
        self.assertEqual(use["busy_seconds"], 1800)
        self.assertLess(use["percent"], 100.0)

    def test_work_older_than_the_window_is_clipped_out(self):
        self.log(up(day="2026-10-13"),
                 line("01:00:00", "START 0001-a.md", day="2026-10-13"),
                 line("05:00:00", "DONE  0001-a.md -> exit0",
                      day="2026-10-13"))
        use = lanes.utilisation(self.events(), NOW)
        self.assertEqual(use["busy_seconds"], 0)

    def test_it_refuses_an_unknown_clock(self):
        self.log(up(), line("01:00:00", "START 0001-a.md"))
        self.assertIsNone(lanes.utilisation(self.events(), None))


# --------------------------------------------------------------------------
# The three signals that must not be used.
# --------------------------------------------------------------------------

class TheThreeRejectedSignalsAreNotConsulted(Estate, unittest.TestCase):

    def base(self):
        return self.log(up(),
                        line("00:00:00", "START 0001-a.md"),
                        line("00:30:00", "DONE  0001-a.md -> exit0"))

    def test_a_done_filename_does_not_move_the_verdict_or_the_depth(self):
        """Lanes write their own DONE files and `Move-Item` preserves the
        original mtime, so a DONE file can be stamped before its own START."""
        self.base()
        before = self.row(alive=False)
        for name in ("20261016-000000-exit0-0090-invented.md",
                     "20261016-000001-exit0-0091-invented.md",
                     "20261016-000002-exit0-0092-invented.md"):
            with open(os.path.join(self.root, "queue", LANE, "DONE", name),
                      "w", encoding="utf-8", newline="\n") as handle:
                handle.write("# not a completion\n")
        after = self.row(alive=False)
        self.assertEqual(before["verdict"], after["verdict"])
        self.assertEqual(before["queue_depth"], after["queue_depth"])
        self.assertEqual(before["starvation_minutes"],
                         after["starvation_minutes"])

    def test_an_out_files_size_does_not_move_the_verdict(self):
        """It fills at the END of a task, so 0 bytes mid-run is normal and a
        large one beside finished work proves nothing."""
        self.base()
        before = self.row(alive=False)
        with open(os.path.join(self.root, "logs",
                               "task-%s-20261016-000000.out" % LANE), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("x" * 50000)
        self.assertEqual(self.row(alive=False)["verdict"], before["verdict"])

    def test_a_brief_in_running_does_not_make_a_lane_busy(self):
        """Two lanes sat with a brief in RUNNING whose owner was dead, for
        97 minutes each."""
        self.base()
        self.running("0090-orphaned.md")
        row = self.row(alive=False)
        self.assertEqual(row["verdict"], lanes.V_IDLE,
                         "a brief in RUNNING must not make this WORKING")

    def test_an_empty_running_does_not_make_a_lane_idle(self):
        self.log(up(), line("02:50:00", "START 0010-a.md"))
        row = self.row(alive=True)
        self.assertEqual(row["inflight"], [])
        self.assertEqual(row["verdict"], lanes.V_RUNNING)


# --------------------------------------------------------------------------
# DOWN has two disjuncts and only one was built.
# --------------------------------------------------------------------------


class TheWatcherNobodyHeardStopIsAlsoDown(Estate, unittest.TestCase):
    """The second half of DOWN, added 2026-10-16 as a correction.

    The state to detect is "last line is `watcher down`, OR the log has not
    moved and no watcher pid is live". Only the first was implemented, and
    `VERDICT_TEXT[V_DOWN]` promised both in prose - so the board documented
    a check it did not make.

    It matters because the common way a watcher dies writes no `watcher
    down` line at all: `Stop-Process` takes it and the log simply stops. The
    reader already held both facts - `watcher_alive` False, and its own
    liveness text "that watcher is gone, so this lane is consuming nothing
    whatever its log last said" - and still returned IDLE. Measured on this
    module before the fix: verdict `idle`, `watcher_alive` False,
    `log_has_gone_quiet` True, depth 0.

    IDLE means waiting for work. This means waiting for a person, and the
    two must not share a word.
    """

    def quiet(self):
        """Newest record is a DONE 2.5 h before `now`, against a documented
        5-minute idle heartbeat. No `watcher down` line anywhere."""
        return self.log(up(), line("00:10:00", "START 0010-a.md"),
                        line("00:30:00", "DONE  0010-a.md -> exit0"))

    def test_a_dead_watcher_with_a_quiet_log_is_down_not_idle(self):
        self.quiet()
        row = self.row(alive=False, watcher=False)
        self.assertIs(row["watcher_alive"], False)
        self.assertTrue(row["log_has_gone_quiet"])
        self.assertEqual(row["verdict"], lanes.V_DOWN)

    def test_it_is_down_however_deep_the_queue_behind_it(self):
        """A dead watcher dispatches nothing, so depth is not reassurance."""
        self.quiet()
        self.queue("0010-a.md", "0020-b.md", "0030-c.md", "0040-d.md")
        row = self.row(alive=False, watcher=False)
        self.assertEqual(row["verdict"], lanes.V_DOWN)
        self.assertEqual(row["queue_depth"], 4)

    def test_the_two_disjuncts_are_told_apart(self):
        """Which one fired is a different fact and the row carries both.
        `watcher_went_down` stays the LOG's claim; the inferred case is its
        own field, so a reader is never told the watcher logged something it
        did not."""
        self.quiet()
        inferred = self.row(alive=False, watcher=False)
        self.assertFalse(inferred["watcher_went_down"])
        self.assertTrue(inferred["watcher_inferred_down"])

        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 line("00:30:00", "DONE  0010-a.md -> exit0"),
                 line("00:31:00", "watcher down"))
        logged = self.row(alive=False, watcher=False)
        self.assertTrue(logged["watcher_went_down"])
        self.assertFalse(logged["watcher_inferred_down"])
        self.assertEqual(logged["verdict"], lanes.V_DOWN)

    # ------------------------------------------------ the controls, fail-closed

    def test_a_quiet_log_on_a_LIVE_watcher_is_not_down(self):
        """BOTH halves are required. A live watcher with a quiet log is the
        0040 warning - its single authority stopped answering - and it is
        still a process that will take the next brief."""
        self.quiet()
        row = self.row(alive=False, watcher=True)
        self.assertTrue(row["log_has_gone_quiet"])
        self.assertIs(row["watcher_alive"], True)
        self.assertFalse(row["watcher_inferred_down"])
        self.assertEqual(row["verdict"], lanes.V_IDLE)

    def test_a_dead_watcher_whose_log_just_moved_is_not_yet_down(self):
        """Inside the heartbeat tolerance a watcher that has just died and
        one that is about to write its next line are not distinguishable, so
        the verdict waits. BOTH halves are required, as the brief writes it.

        The cost is bounded and the page does not hide it while it runs:
        this asserts the row still carries the watcher as gone, and that the
        rendered liveness column says so in words."""
        self.log(up(), line("02:50:00", "START 0010-a.md"),
                 line("02:58:00", "DONE  0010-a.md -> exit0"))
        row = self.row(alive=False, watcher=False)
        self.assertFalse(row["log_has_gone_quiet"])
        self.assertFalse(row["watcher_inferred_down"])
        self.assertIs(row["watcher_alive"], False)
        self.assertEqual(row["verdict"], lanes.V_IDLE)
        self.assertIn(pages.esc("names a process that is gone"),
                      pages.lane_board(api.lane_board(
                          now=NOW, probe=FakeProbe(alive=False,
                                                   watcher=False),
                          samples={})))

    def test_an_unreadable_process_table_cannot_produce_down(self):
        """None is not False. An unknown liveness must not produce a DOWN
        verdict any more than it produces a healthy one - and UNCROSSED is
        the word for exactly one authority answering."""
        self.quiet()
        row = self.row(unreadable_table=True)
        self.assertIsNone(row["watcher_alive"])
        self.assertFalse(row["watcher_inferred_down"])
        self.assertEqual(row["verdict"], lanes.V_UNCROSSED)

    def test_no_pid_file_cannot_produce_down(self):
        """With no file naming a watcher there is no pid to find in the
        table, so its absence from one proves nothing."""
        self.quiet()
        os.remove(os.path.join(self.root, "logs", "watcher-%s.pid" % LANE))
        row = self.row(alive=False, watcher=False)
        self.assertIsNone(row["watcher_alive"])
        self.assertFalse(row["watcher_inferred_down"])
        self.assertEqual(row["verdict"], lanes.V_UNCROSSED)

    def test_an_open_task_with_a_dead_watcher_stays_stalled(self):
        """STALLED is the finer word and is NOT collapsed into DOWN: it says
        a brief is sitting in RUNNING that a person has to move. Losing that
        would trade one wrong word for another."""
        self.log(up(), line("02:50:00", "START 0010-a.md"))
        self.running("0010-a.md")
        row = self.row(alive=False, watcher=False)
        self.assertEqual(row["verdict"], lanes.V_STALLED)

    def test_an_unreadable_log_with_a_dead_watcher_is_still_unknown(self):
        """A log that cannot be read cannot be said to have stopped moving,
        so neither disjunct can be evaluated and UNKNOWN stands. Not a
        precedence claim: `gone_quiet` is unreachable without a readable
        log, which this asserts rather than assumes."""
        row = self.row(alive=False, watcher=False)   # no log written at all
        self.assertEqual(row["verdict"], lanes.V_UNKNOWN)
        self.assertFalse(row["log_has_gone_quiet"])
        self.assertFalse(row["watcher_inferred_down"])

    def test_a_refusal_loop_and_an_inferred_down_cannot_co_occur(self):
        """Not a precedence test, because there is no precedence to test -
        and asserting one would be a control that observes nothing.

        The refusal loop writes a line every 20 seconds, so a STUCK lane's
        log is MOVING BY DEFINITION, and `gone_quiet` is the statement that
        a log has stopped. The two states are mutually exclusive by
        construction; this asserts that exclusion on the STUCK fixture,
        with the watcher absent from the table so the other half of the
        inference is satisfied and only the log half can refuse it."""
        rows = [up(timeout=90), line("00:10:00", "START 0010-a.md")]
        rows += [blocked("02:%02d:00" % n) for n in range(0, 50)]
        self.log(*rows)
        row = self.row(alive=True, watcher=False)
        self.assertEqual(row["verdict"], lanes.V_STUCK)
        self.assertIs(row["watcher_alive"], False)
        self.assertFalse(row["log_has_gone_quiet"])
        self.assertFalse(row["watcher_inferred_down"])


# --------------------------------------------------------------------------
# The page.
# --------------------------------------------------------------------------

class ThePanelRenders(Estate, unittest.TestCase):

    def html(self, alive=True, now=None, watcher=True,
             unreadable_table=False):
        probe = FakeProbe(alive=alive, watcher=watcher,
                          unreadable_table=unreadable_table)
        return pages.lane_board(api.lane_board(now=now or NOW, probe=probe,
                                               samples={}))

    def test_the_starvation_panel_is_on_the_board(self):
        self.log(up(), line("00:00:00", "START 0001-a.md"),
                 line("00:30:00", "DONE  0001-a.md -> exit0"))
        body = self.html(alive=False)
        self.assertIn("Queue depth and starvation", body)
        self.assertIn("Autonomy left", body)

    def test_a_floor_breach_is_called_out_plainly(self):
        self.log(up(), line("00:00:00", "START 0001-a.md"),
                 line("00:30:00", "DONE  0001-a.md -> exit0"))
        self.assertIn("BELOW THE FLOOR", self.html(alive=False))

    def test_a_lane_at_the_floor_raises_no_breach(self):
        self.log(up(), line("00:00:00", "START 0001-a.md"),
                 line("00:30:00", "DONE  0001-a.md -> exit0"))
        self.queue("0010-a.md", "0020-b.md", "0030-c.md")
        self.assertNotIn("BELOW THE FLOOR", self.html(alive=False))

    def test_a_stuck_lane_renders_as_stuck_and_not_as_running(self):
        rows = [up(timeout=90), line("00:10:00", "START 0010-a.md")]
        rows += [blocked("02:%02d:00" % n) for n in range(0, 50)]
        self.log(*rows)
        body = self.html(alive=True)
        self.assertIn("STUCK", body)
        self.assertIn("Refusal loop", body)

    def test_the_stuck_verdict_has_a_colour_of_its_own(self):
        self.assertEqual(pages.VERDICT_KIND[lanes.V_STUCK], "block")
        self.assertEqual(pages.VERDICT_KIND[lanes.V_DOWN], "block")

    def test_every_verdict_the_page_can_meet_has_a_colour(self):
        for name in dir(lanes):
            if name.startswith("V_"):
                self.assertIn(getattr(lanes, name), pages.VERDICT_KIND, name)

    def test_an_unknown_lane_is_not_rendered_as_idle(self):
        body = self.html(alive=True)        # no log at all
        self.assertIn("UNKNOWN", body)

    def test_the_panel_names_the_three_rejected_signals(self):
        self.log(up(), line("00:00:00", "START 0001-a.md"),
                 line("00:30:00", "DONE  0001-a.md -> exit0"))
        body = self.html(alive=False)
        self.assertIn(pages.esc("DONE"), body)
        self.assertIn(pages.esc(".out"), body)

    def test_a_stuck_lane_is_sent_to_the_hand_clear_procedure(self):
        """The brief's requirement, and the reason for it: nothing clears a
        stranded brief automatically, so a board that names the state and
        not the remedy leaves the reader to find it. The authority is
        `queue/README.md`, by name, with its section."""
        rows = [up(timeout=90), line("00:10:00", "START 0010-a.md")]
        rows += [blocked("02:%02d:00" % n) for n in range(0, 50)]
        self.log(*rows)
        body = self.html(alive=True)
        self.assertIn("STUCK", body)
        self.assertIn(pages.esc("queue/README.md"), body)
        self.assertIn(pages.esc("When a lane goes quiet"), body)
        # The elapsed time, beside it.
        self.assertIn(pages.esc("0010-a.md"), body)

    def test_a_healthy_board_does_not_offer_the_hand_clear_procedure(self):
        """A remedy shown where there is nothing to remedy is how a reader
        learns to stop reading the panel."""
        self.log(up(), line("00:00:00", "START 0001-a.md"),
                 line("00:30:00", "DONE  0001-a.md -> exit0"))
        self.assertNotIn(pages.esc("When a lane goes quiet"),
                         self.html(alive=False))

    def test_the_inflight_elapsed_is_shown_against_this_lanes_timeout(self):
        """The brief: "against that lane's timeout as its log reports it,
        not as the script on disk reports it". Without it the reader crosses
        two tables and does the arithmetic by hand."""
        self.log(up(timeout=90), line("02:00:00", "START 0010-a.md"))
        self.running("0010-a.md")
        body = self.html(alive=True)
        self.assertIn(pages.esc("of 90 min"), body)

    def test_an_inflight_task_past_its_timeout_is_called_out(self):
        """A task older than the cap its own watcher is running, with no
        TIMEOUT line, is a question - the watcher should have killed it."""
        self.log(up(timeout=90), line("00:10:00", "START 0010-a.md"))
        self.running("0010-a.md")
        self.assertIn(pages.esc("past this lane's own timeout"),
                      self.html(alive=True))

    def test_an_inflight_task_inside_its_timeout_is_not_called_out(self):
        self.log(up(timeout=90), line("02:50:00", "START 0010-a.md"))
        self.running("0010-a.md")
        self.assertNotIn(pages.esc("past this lane's own timeout"),
                         self.html(alive=True))

    def test_exactly_at_the_timeout_is_not_past_it(self):
        """The boundary, decided and watched. A mutation from `>` to `>=`
        survived until this existed: 90 minutes into a 90-minute cap is AT
        the cap, and the watcher has not yet failed to do anything."""
        self.log(up(timeout=90), line("01:30:00", "START 0010-a.md"))
        self.running("0010-a.md")
        row = self.row(alive=True)
        self.assertEqual(row["since_seconds"], 90 * 60)
        self.assertNotIn(pages.esc("past this lane's own timeout"),
                         self.html(alive=True))

    def test_one_minute_past_the_timeout_is_past_it(self):
        """The other side of the same boundary."""
        self.log(up(timeout=90), line("01:29:00", "START 0010-a.md"))
        self.running("0010-a.md")
        self.assertIn(pages.esc("past this lane's own timeout"),
                      self.html(alive=True))

    def test_an_idle_lanes_done_age_is_never_read_as_an_elapsed_time(self):
        """`since_seconds` is the age of the DONE line when a lane is
        between tasks, and comparing THAT to a timeout would put a false
        alarm on the healthiest lane on the board - a lane that finished
        three hours ago is not a task running three hours. A mutation
        dropping the status guard survived until this existed."""
        self.log(up(timeout=90), line("00:00:00", "START 0010-a.md"),
                 line("00:10:00", "DONE  0010-a.md -> exit0"))
        row = self.row(alive=False)
        self.assertEqual(row["status"], lanes.IDLE)
        self.assertGreater(row["since_seconds"], 90 * 60)
        body = self.html(alive=False)
        self.assertNotIn(pages.esc("past this lane's own timeout"), body)
        self.assertNotIn(pages.esc("of 90 min"), body)

    def test_an_unknown_timeout_is_not_rendered_as_a_comparison(self):
        """No `timeout=` field, so the cap this watcher is running is
        UNKNOWN - and an elapsed time compared against a guess would be a
        guess."""
        self.log(line("00:00:00", "watcher up. tree=/x mode=bypass"),
                 line("02:00:00", "START 0010-a.md"))
        self.running("0010-a.md")
        body = self.html(alive=True)
        self.assertNotIn(pages.esc("past this lane's own timeout"), body)
        self.assertIn(pages.esc("this lane's own timeout is UNKNOWN"), body)

    def test_an_inferred_down_lane_says_it_was_inferred(self):
        """No `watcher down` line exists, so the page must not imply one was
        read: it names the two facts it crossed instead."""
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 line("00:30:00", "DONE  0010-a.md -> exit0"))
        body = self.html(alive=False, watcher=False)
        self.assertIn("WATCHER DOWN", body)
        self.assertIn(pages.esc("no `watcher down` line"), body)

    def test_a_logged_down_lane_does_not_claim_an_inference(self):
        self.log(up(), line("00:10:00", "START 0010-a.md"),
                 line("00:30:00", "DONE  0010-a.md -> exit0"),
                 line("00:31:00", "watcher down"))
        body = self.html(alive=False, watcher=False)
        self.assertIn("WATCHER DOWN", body)
        self.assertNotIn(pages.esc("no `watcher down` line"), body)

    def test_the_panel_prints_no_absolute_path(self):
        self.log(up(), line("00:00:00", "START 0001-a.md"),
                 line("00:30:00", "DONE  0001-a.md -> exit0"))
        self.assertNotIn(self.root, self.html(alive=False))


if __name__ == "__main__":
    unittest.main()
