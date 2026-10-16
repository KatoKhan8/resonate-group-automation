"""The cap a lane is ACTUALLY running against, and the three ways it is UNKNOWN.

WHAT THIS FILE IS FOR. Two watcher generations run at once in this estate.
`tools/lane_watcher.ps1` has said 150 minutes since 2026-10-15 22:20, but
PowerShell parses a `-File` script once, at load, so a running watcher keeps
whatever constant it started with. Measured 2026-10-16 06:38 from the logs
themselves: `pilotcaps`, `qwen`, `suppression` and `webapp` were all running
**90m** while the script on disk said 150m.

IT HAS ALREADY COST A NEAR-MISS. `pilotcaps/0220` ran 01:51:03 -> 03:16:50,
85m47s against a 90-minute cap - **4m13s of margin** - and the report from
that same session said the lane would next get "a full 150 minutes". It had
read the script. A lane budgeting 150 minutes on a 90-minute watcher is how
the timeout chain gets hit on purpose, and that chain has killed four
watchers in 29 hours.

So the authority is the `timeout=<n>m` field on THAT LANE's own last
`watcher up` line, and this file's whole job is to prove that no other
source can get in: not the script constant, not another lane's number, and
not an older `watcher up` line from the previous generation.

THE FIVE UNKNOWNS, EACH ITS OWN STATE. One empty cell for all of them would
be the same dead end as a wrong number, because the repairs differ: a log
with no `up` line needs the watcher restarted with logging, an `up` line
with no field needs the watcher's own format fixed, and an `up` line a
`watcher down.` has superseded needs the lane started again. The same
discipline on the other side of the subtraction: a brief in RUNNING\\ with
no START line, and one whose START has been closed by a DONE line, are
different facts and only the second one has a person's name on it.

NOTHING HERE READS THE REAL ESTATE. Every log is a string written into a
temporary directory and every process table is a dict handed to the reader.
The live estate was measured separately, by hand, and is recorded in
`LANE-webapp.md`.
"""
import datetime
import os
import re
import shutil
import tempfile
import unittest

from src import lanes
from src.web import api, pages

#: 2026-10-16 03:00 local. Every fixture stamp below is relative to it.
NOW = datetime.datetime(2026, 10, 16, 3, 0, 0)

#: Two lanes, because C3 cannot be stated with one. A single-lane test
#: cannot tell a per-lane read from a global one: both pass.
ALPHA = "alpha"
BETA = "beta"

PIDS = {ALPHA: 4242, BETA: 4343}


def line(lane, clock, message, day="2026-10-16"):
    """One watcher record, in the exact shape `lane_watcher.ps1` writes."""
    return "[%s %s] [%s] %s" % (day, clock, lane, message)


def up(lane, clock="00:00:00", timeout=90, field=True):
    """A `watcher up` line, with or without the `timeout=` field."""
    body = "watcher up. tree=C:\\somewhere mode=bypassPermissions"
    if field:
        body += " timeout=%dm" % timeout
    return line(lane, clock, body)


def minutes_ago(count):
    """A clock string `count` minutes before NOW, same day."""
    return (NOW - datetime.timedelta(minutes=count)).strftime("%H:%M:%S")


class Probe:
    """A process table handed to the reader, never measured.

    Both watchers alive with a child each: the clock is a question about the
    log and the RUNNING\\ listing, and a liveness answer must not be able to
    change any figure this file asserts.
    """

    def table(self):
        rows = {}
        for pid in PIDS.values():
            rows[pid] = (1, "powershell.exe")
            rows[pid + 1000] = (pid, "node.exe")
        return rows

    def cpu(self, pid):
        return 12.5


class Estate:
    """A two-lane estate, thrown away per test."""

    def setUp(self):
        super().setUp()
        self.root = tempfile.mkdtemp(prefix="rga-clock-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, "logs"))
        for lane in (ALPHA, BETA):
            os.makedirs(os.path.join(self.root, "queue", lane, "RUNNING"))
            os.makedirs(os.path.join(self.root, "queue", lane, "DONE"))
            self.write(os.path.join(self.root, "logs",
                                    "watcher-%s.pid" % lane),
                       "%d\n" % PIDS[lane])
            self.write(os.path.join(self.root, "LANE-%s.md" % lane),
                       "## entry 2026-10-16\n")
        self.write(os.path.join(self.root, "queue", "README.md"),
                   "# LANE QUEUE\n\n**Floor: never leave a lane below 3 "
                   "queued briefs.**\n")
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

    def log(self, lane, *rows):
        """Write this lane's log. Absent until called, which is a state."""
        path = os.path.join(self.root, "logs", "watcher-%s.log" % lane)
        self.write(path, "\n".join(rows) + "\n")
        return path

    def running(self, lane, *names):
        for name in names:
            self.write(os.path.join(self.root, "queue", lane, "RUNNING",
                                    name), "# in flight\n")

    # ------------------------------------------------------------ the readers

    def data(self, now=None):
        """The whole board payload, through the same call the route makes."""
        return api.lane_board(root=self.root, now=now or NOW, probe=Probe(),
                              samples={})

    def clock(self, lane, now=None):
        rows = self.data(now=now)["lanes"]
        return [r for r in rows if r["lane"] == lane][0]["clock"]

    def row(self, lane, now=None):
        rows = self.data(now=now)["lanes"]
        return [r for r in rows if r["lane"] == lane][0]

    def panel_text(self, now=None):
        """The rendered panel as readable text, tags and all.

        THE RENDER IS THE DELIVERABLE, so every control asserts on it as
        well as on the reader. A figure computed correctly that the page
        does not show is this repository's signature defect.
        """
        html = pages.lane_clocks(self.data(now=now))
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text.replace("&mdash;", "-")
                      .replace("&amp;", "&").replace("&#x27;", "'")
                      .replace("&quot;", '"').replace("&lt;", "<")
                      .replace("&gt;", ">"))

    def lane_cells(self, lane, now=None):
        """Just this lane's row of the rendered table, as text.

        Per-lane rather than whole-panel, because a panel-wide `assertIn`
        passes when the right words appear against the WRONG lane - which is
        exactly the global-read defect C3 exists to catch.
        """
        html = pages.lane_clocks(self.data(now=now))
        rows = re.findall(r"<tr>(.*?)</tr>", html, re.S)
        mine = [r for r in rows
                if re.search(r"<b>%s</b>" % re.escape(lane), r)]
        self.assertEqual(len(mine), 1,
                         "expected exactly one rendered row for %s" % lane)
        text = re.sub(r"<[^>]+>", " ", mine[0])
        return re.sub(r"\s+", " ", text.replace("&mdash;", "-")
                      .replace("&#x27;", "'"))


# ---------------------------------------------------------------------------
# C1 - the ordinary reading. 90m, 40 minutes in, 50 minutes left.
# ---------------------------------------------------------------------------

class C1AnOrdinaryClock(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.log(ALPHA, up(ALPHA, timeout=90),
                 line(ALPHA, minutes_ago(40), "START 0010-a.md"))
        self.running(ALPHA, "0010-a.md")

    def test_the_three_figures(self):
        clock = self.clock(ALPHA)
        self.assertEqual(clock["timeout_minutes"], 90)
        self.assertEqual(clock["timeout_state"], lanes.T_IN_FORCE)
        self.assertEqual(clock["elapsed_seconds"], 40 * 60)
        self.assertEqual(clock["elapsed_state"], lanes.E_FROM_START)
        self.assertEqual(clock["remaining_seconds"], 50 * 60)
        self.assertEqual(clock["remaining_state"], lanes.R_KNOWN)

    def test_the_brief_is_the_one_in_running(self):
        self.assertEqual(self.clock(ALPHA)["brief"], "0010-a.md")
        self.assertEqual(self.clock(ALPHA)["extra_briefs"], [])

    def test_fifty_minutes_left_is_not_near_the_timeout(self):
        self.assertIs(self.clock(ALPHA)["near_timeout"], False)

    def test_the_panel_prints_all_three(self):
        cells = self.lane_cells(ALPHA)
        self.assertIn("0010-a.md", cells)
        self.assertIn("90 min", cells)
        self.assertIn("40m00s", cells)
        self.assertIn("50m00s", cells)

    def test_the_panel_does_not_claim_an_alarm(self):
        cells = self.lane_cells(ALPHA)
        self.assertNotIn("PAST", cells)
        self.assertNotIn("UNDER", cells)
        self.assertNotIn("UNKNOWN", cells)


# ---------------------------------------------------------------------------
# C2 - no `watcher up` line at all. UNKNOWN, and the path to go and read.
#
# THE MUTATION THIS CONTROL EXISTS FOR is a fallback to the script constant,
# which is the one substitution that would read as helpful. C1 must stay
# green while this goes red: a reader that answers 150 for every lane is
# right about any lane that happens to be running 150.
# ---------------------------------------------------------------------------

class C2NoWatcherUpLine(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.log(ALPHA, line(ALPHA, minutes_ago(40), "START 0010-a.md"))
        self.running(ALPHA, "0010-a.md")

    def test_the_cap_is_unknown_and_not_a_hundred_and_fifty(self):
        clock = self.clock(ALPHA)
        self.assertIsNone(clock["timeout_minutes"])
        self.assertEqual(clock["timeout_state"], lanes.T_NO_UP_LINE)

    def test_the_elapsed_time_is_still_known(self):
        """The two sides fail independently, and only one of them failed."""
        clock = self.clock(ALPHA)
        self.assertEqual(clock["elapsed_seconds"], 40 * 60)
        self.assertEqual(clock["elapsed_state"], lanes.E_FROM_START)

    def test_the_remainder_is_unknown_and_never_computed(self):
        clock = self.clock(ALPHA)
        self.assertIsNone(clock["remaining_seconds"])
        self.assertEqual(clock["remaining_state"], lanes.R_UNKNOWN)
        self.assertIsNone(clock["over_seconds"])
        # NOT False. An unmeasurable remainder is not "comfortably far from
        # the timeout", and a False here would render as the all-clear.
        self.assertIsNone(clock["near_timeout"])

    def test_the_panel_names_the_log_to_read(self):
        cells = self.lane_cells(ALPHA)
        self.assertIn("UNKNOWN", cells)
        self.assertIn(os.path.join("logs", "watcher-%s.log" % ALPHA), cells)
        self.assertIn("lane_watcher.ps1 is NOT read", cells)

    def test_the_panel_prints_no_number_for_the_cap(self):
        """The whole defect, stated as a render: no minutes figure appears."""
        self.assertNotIn(" min", self.lane_cells(ALPHA))

    def test_the_path_is_the_tail_and_not_the_absolute_path(self):
        """A path on a screen is somebody's home directory in a screenshot."""
        self.assertNotIn(self.root, self.lane_cells(ALPHA))
        self.assertEqual(self.row(ALPHA)["log_path_shown"],
                         os.path.join("logs", "watcher-%s.log" % ALPHA))

    def test_the_head_counts_it(self):
        self.assertIn("NO CAP IN FORCE IS KNOWN", self.panel_text())


class C2bTheUpLineCarriesNoTimeoutField(Estate, unittest.TestCase):
    """The second UNKNOWN, and the one with a stale number next to it.

    An `up` line with no `timeout=` field after an older one that HAS a
    field. The walk must stop at the newest line: reaching past it answers
    with the PREVIOUS watcher generation's constant, which is this panel's
    own bug in the one place it would read as safe.
    """

    def setUp(self):
        super().setUp()
        self.log(ALPHA,
                 up(ALPHA, clock="00:00:00", timeout=90),
                 line(ALPHA, "00:01:00", "watcher down."),
                 up(ALPHA, clock="00:02:00", field=False),
                 line(ALPHA, minutes_ago(40), "START 0010-a.md"))
        self.running(ALPHA, "0010-a.md")

    def test_it_does_not_reach_back_to_the_older_line(self):
        clock = self.clock(ALPHA)
        self.assertIsNone(clock["timeout_minutes"])
        self.assertEqual(clock["timeout_state"], lanes.T_NO_FIELD)
        self.assertIsNone(clock["remaining_seconds"])

    def test_the_panel_says_which_unknown_this_is(self):
        self.assertIn("carries no timeout", self.lane_cells(ALPHA))


# ---------------------------------------------------------------------------
# C3 - two lanes, two caps, one render.
#
# WITHOUT THIS CONTROL a single-lane test cannot tell a per-lane read from a
# global one. The mutation is one timeout read once and applied to every
# lane, which is precisely the mistake the live estate makes available: four
# lanes on 90m and two on 150m at the same moment.
# ---------------------------------------------------------------------------

class C3EachLaneReadsItsOwn(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.log(ALPHA, up(ALPHA, timeout=90),
                 line(ALPHA, minutes_ago(40), "START 0010-a.md"))
        self.running(ALPHA, "0010-a.md")
        self.log(BETA, up(BETA, timeout=150),
                 line(BETA, minutes_ago(40), "START 0020-b.md"))
        self.running(BETA, "0020-b.md")

    def test_neither_lane_gets_the_other_s_cap(self):
        self.assertEqual(self.clock(ALPHA)["timeout_minutes"], 90)
        self.assertEqual(self.clock(BETA)["timeout_minutes"], 150)

    def test_the_remainders_differ_by_the_sixty_minutes_of_cap(self):
        self.assertEqual(self.clock(ALPHA)["remaining_seconds"], 50 * 60)
        self.assertEqual(self.clock(BETA)["remaining_seconds"], 110 * 60)

    def test_the_rendered_rows_differ(self):
        """ASSERTED PER ROW. A panel-wide `assertIn("150 min")` passes when
        both rows say 150, which is the defect itself."""
        alpha = self.lane_cells(ALPHA)
        beta = self.lane_cells(BETA)
        self.assertIn("90 min", alpha)
        self.assertIn("50m00s", alpha)
        self.assertNotIn("150 min", alpha)
        self.assertIn("150 min", beta)
        self.assertIn("110m00s", beta)

    def test_both_lanes_are_rows(self):
        text = self.panel_text()
        self.assertIn("0010-a.md", text)
        self.assertIn("0020-b.md", text)
        self.assertIn("2 in flight", text)


# ---------------------------------------------------------------------------
# C4 - the last `watcher up` is superseded by a `watcher down.`
#
# A watcher that has exited enforces nothing, so there is no cap in force.
# Measured live 2026-10-16 06:38: glm, glm-b and glm-c had all logged
# `watcher down.` at 01:46-01:48 and their last `up` lines still carried
# 150m, 90m and 150m.
# ---------------------------------------------------------------------------

class C4ADownLineSupersedesTheCap(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.log(ALPHA, up(ALPHA, clock="00:00:00", timeout=90),
                 line(ALPHA, minutes_ago(40), "START 0010-a.md"),
                 line(ALPHA, minutes_ago(5), "watcher down."))
        self.running(ALPHA, "0010-a.md")

    def test_the_stale_number_is_not_reported(self):
        clock = self.clock(ALPHA)
        self.assertIsNone(clock["timeout_minutes"])
        self.assertEqual(clock["timeout_state"], lanes.T_SUPERSEDED)
        self.assertIsNone(clock["remaining_seconds"])
        self.assertEqual(clock["remaining_state"], lanes.R_UNKNOWN)

    def test_the_panel_says_that_watcher_has_exited(self):
        cells = self.lane_cells(ALPHA)
        self.assertIn("that watcher has exited", cells)
        self.assertNotIn("90 min", cells)

    def test_a_down_BEFORE_the_up_line_does_not_supersede_it(self):
        """The ordinary restart. A `down` older than the newest `up` is the
        previous generation ending, not this one."""
        self.log(ALPHA, up(ALPHA, clock="00:00:00", timeout=90),
                 line(ALPHA, "00:01:00", "watcher down."),
                 up(ALPHA, clock="00:02:00", timeout=150),
                 line(ALPHA, minutes_ago(40), "START 0010-a.md"))
        self.assertEqual(self.clock(ALPHA)["timeout_minutes"], 150)

    def test_the_lane_reader_s_own_timeout_agrees(self):
        """`timeout_minutes` is an accessor over the same reading.

        TWO IMPLEMENTATIONS OF ONE RULE is the defect the 2026-10-16 suite
        lock mutation run found: a mutation to the real rule left every
        control green because an inline copy kept answering.
        """
        state, rows, _ = lanes._read_tail(
            os.path.join(self.root, "logs", "watcher-%s.log" % ALPHA))
        events = lanes.watcher_events(rows, ALPHA)
        self.assertEqual(state, lanes.PRESENT)
        self.assertIsNone(lanes.timeout_minutes(events))
        self.assertEqual(lanes.timeout_reading(events)["state"],
                         lanes.T_SUPERSEDED)


# ---------------------------------------------------------------------------
# C5 - past the cap with no DONE line. Its own reading, never a clamped zero.
#
# MEASURED LIVE while this was written: qwen's `0170` had been running since
# 00:58:53 against a 90-minute cap, 255 minutes over, with no DONE line, no
# TIMEOUT line and its watcher pid absent from the process table.
# ---------------------------------------------------------------------------

class C5PastTheCap(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.log(ALPHA, up(ALPHA, timeout=90),
                 line(ALPHA, minutes_ago(100), "START 0010-a.md"))
        self.running(ALPHA, "0010-a.md")

    def test_the_remainder_is_not_zero_and_not_negative(self):
        clock = self.clock(ALPHA)
        self.assertEqual(clock["remaining_state"], lanes.R_PAST)
        self.assertIsNone(clock["remaining_seconds"])
        self.assertNotEqual(clock["remaining_seconds"], 0)

    def test_how_far_past_is_reported(self):
        self.assertEqual(self.clock(ALPHA)["over_seconds"], 10 * 60)
        self.assertEqual(self.clock(ALPHA)["elapsed_seconds"], 100 * 60)

    def test_past_is_not_reported_as_inside_the_window(self):
        self.assertIs(self.clock(ALPHA)["near_timeout"], False)

    def test_the_panel_renders_the_past_state(self):
        cells = self.lane_cells(ALPHA)
        self.assertIn("PAST THIS LANE'S OWN TIMEOUT", cells)
        self.assertIn("over by 10m00s", cells)
        self.assertIn("no DONE line", cells)

    def test_the_head_names_the_lane_and_the_margin(self):
        self.assertIn("alpha over by 10m00s", self.panel_text())

    def test_a_done_line_closes_the_clock_instead(self):
        """The other half of the same state, and it is NOT past-the-cap.

        A DONE newer than the START means the log has closed this brief and
        the file in RUNNING\\ outlived its run. Nothing is counting against
        the cap, and an elapsed time here would be a stopped clock presented
        as a running one. `queue/README.md` says only a person clears it.
        """
        self.log(ALPHA, up(ALPHA, timeout=90),
                 line(ALPHA, minutes_ago(100), "START 0010-a.md"),
                 line(ALPHA, minutes_ago(95), "DONE  0010-a.md -> exit0"))
        clock = self.clock(ALPHA)
        self.assertEqual(clock["elapsed_state"], lanes.E_CLOSED)
        self.assertIsNone(clock["elapsed_seconds"])
        self.assertEqual(clock["remaining_state"], lanes.R_UNKNOWN)
        self.assertNotEqual(clock["remaining_state"], lanes.R_PAST)
        self.assertIn("CLOSED", self.lane_cells(ALPHA))


# ---------------------------------------------------------------------------
# C6 - the mark the brief asks for: under ten minutes left.
#
# The window in which the timeout chain fires, and the window in which a
# lane has to write its entry whatever else is unfinished. `pilotcaps/0220`
# finished 4m13s inside its cap.
# ---------------------------------------------------------------------------

class C6TheTenMinuteMark(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.log(ALPHA, up(ALPHA, timeout=90),
                 line(ALPHA, minutes_ago(85), "START 0010-a.md"))
        self.running(ALPHA, "0010-a.md")

    def test_the_flag_is_set(self):
        clock = self.clock(ALPHA)
        self.assertIs(clock["near_timeout"], True)
        self.assertEqual(clock["remaining_seconds"], 5 * 60)
        self.assertEqual(clock["near_window_seconds"], 10 * 60)

    def test_the_mark_is_visible_in_the_row(self):
        cells = self.lane_cells(ALPHA)
        self.assertIn("UNDER 10 MINUTES LEFT", cells)
        self.assertIn("5m00s", cells)

    def test_the_head_names_the_lane(self):
        self.assertIn("alpha has 5m00s left", self.panel_text())

    def test_the_seconds_survive_the_render(self):
        """`_duration` drops seconds and renders 4m13s as `4m`. In this
        window the seconds ARE the measurement."""
        self.log(ALPHA, up(ALPHA, timeout=90),
                 line(ALPHA, "01:34:13", "START 0010-a.md"))
        # 03:00:00 - 01:34:13 = 85m47s elapsed against a 90m cap, so 4m13s
        # left: `pilotcaps/0220`'s exact near-miss, as a fixture.
        self.assertEqual(self.clock(ALPHA)["elapsed_seconds"], 85 * 60 + 47)
        self.assertEqual(self.clock(ALPHA)["remaining_seconds"], 253)
        self.assertIn("4m13s", self.lane_cells(ALPHA))

    def test_exactly_ten_minutes_left_is_not_inside_the_window(self):
        """A threshold is stated once. `< window`, so 600s is outside it."""
        self.log(ALPHA, up(ALPHA, timeout=90),
                 line(ALPHA, minutes_ago(80), "START 0010-a.md"))
        clock = self.clock(ALPHA)
        self.assertEqual(clock["remaining_seconds"], 10 * 60)
        self.assertIs(clock["near_timeout"], False)


# ---------------------------------------------------------------------------
# The states that are neither an alarm nor a clean reading.
# ---------------------------------------------------------------------------

class TheOtherSidesOfTheSubtraction(Estate, unittest.TestCase):

    def test_a_brief_with_no_start_line_is_unknown_not_zero(self):
        """The brief is there and the log never mentions it."""
        self.log(ALPHA, up(ALPHA, timeout=90),
                 line(ALPHA, minutes_ago(40), "START 0010-a.md"),
                 line(ALPHA, minutes_ago(10), "DONE  0010-a.md -> exit0"))
        self.running(ALPHA, "0099-placed-by-hand.md")
        clock = self.clock(ALPHA)
        self.assertEqual(clock["brief"], "0099-placed-by-hand.md")
        self.assertEqual(clock["elapsed_state"], lanes.E_NO_START)
        self.assertIsNone(clock["elapsed_seconds"])
        self.assertEqual(clock["remaining_state"], lanes.R_UNKNOWN)
        self.assertIsNone(clock["near_timeout"])
        self.assertIn("no START line for this brief",
                      self.lane_cells(ALPHA))

    def test_an_unreadable_log_is_its_own_state(self):
        self.running(ALPHA, "0010-a.md")
        clock = self.clock(ALPHA)
        self.assertEqual(clock["elapsed_state"], lanes.E_LOG_UNREADABLE)
        self.assertEqual(clock["timeout_state"], lanes.T_NO_UP_LINE)
        self.assertEqual(clock["remaining_state"], lanes.R_UNKNOWN)

    def test_a_lane_with_nothing_in_running_is_not_a_row(self):
        self.log(ALPHA, up(ALPHA, timeout=90),
                 line(ALPHA, minutes_ago(40), "START 0010-a.md"),
                 line(ALPHA, minutes_ago(10), "DONE  0010-a.md -> exit0"))
        clock = self.clock(ALPHA)
        self.assertIsNone(clock["brief"])
        self.assertEqual(clock["elapsed_state"], lanes.E_NO_BRIEF)
        text = self.panel_text()
        self.assertIn("No lane has a brief in RUNNING", text)
        # The count is printed, so an empty table cannot read as "no lanes".
        self.assertIn("2 lane(s)", text)

    def test_a_second_file_in_running_is_named(self):
        """One task at a time, so a second file is a defect in itself."""
        self.log(ALPHA, up(ALPHA, timeout=90),
                 line(ALPHA, minutes_ago(40), "START 0010-a.md"))
        self.running(ALPHA, "0010-a.md", "0011-also-here.md")
        clock = self.clock(ALPHA)
        self.assertEqual(clock["brief"], "0010-a.md")
        self.assertEqual(clock["extra_briefs"], ["0011-also-here.md"])
        cells = self.lane_cells(ALPHA)
        self.assertIn("MORE FILE(S) IN RUNNING", cells)
        self.assertIn("0011-also-here.md", cells)
        # The clock itself is still read, and against the right brief.
        self.assertEqual(clock["remaining_seconds"], 50 * 60)


class EveryFigureHasAProvenanceRow(Estate, unittest.TestCase):
    """A figure added to this page with no provenance row renders UNKNOWN.

    `laneprovenance.coverage` walks the payload itself rather than a list
    somebody maintains, so this is the test that catches a clock field
    nobody sourced - including one added later.
    """

    def test_no_clock_path_is_uncovered(self):
        self.log(ALPHA, up(ALPHA, timeout=90),
                 line(ALPHA, minutes_ago(85), "START 0010-a.md"))
        self.running(ALPHA, "0010-a.md")
        data = self.data()
        # A COUNT, and zero is the whole assertion: one unsourced figure is
        # one number on the page nobody can trace.
        self.assertEqual(data["provenance"]["uncovered"], 0)
        covered = {row["path"] for row in data["provenance"]["rows"]}
        for leaf in ("timeout_minutes", "timeout_state", "elapsed_seconds",
                     "elapsed_state", "remaining_seconds", "remaining_state",
                     "over_seconds", "near_timeout", "near_window_seconds",
                     "brief", "started_at"):
            self.assertIn("lane_board.lanes[].clock." + leaf, covered)


class ThePanelIsOnThePage(Estate, unittest.TestCase):
    """The panel is rendered by the route's own page function.

    EXISTENCE IS NOT FUNCTION: a panel function nothing calls is this
    repository's recurring defect, and `lane_clocks` would pass every test
    above while being absent from the screen.
    """

    def test_the_board_page_contains_the_clock_panel(self):
        self.log(ALPHA, up(ALPHA, timeout=90),
                 line(ALPHA, minutes_ago(85), "START 0010-a.md"))
        self.running(ALPHA, "0010-a.md")
        html = pages.lane_board(self.data())
        self.assertIn("The clock each lane is running against", html)
        self.assertIn("UNDER 10 MINUTES LEFT", html)
        # And above the starvation panel, which is the next hour's problem.
        self.assertLess(html.index("The clock each lane is running against"),
                        html.index("Queue depth and starvation"))


if __name__ == "__main__":
    unittest.main()
