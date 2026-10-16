"""The floor nobody could prove was breached, and the four ways to fake it.

WHAT THIS FILE IS FOR. `queue/README.md` carries the operator's floor - never
leave a lane below three queued briefs - and TASK 0080 measured what breaking
it costs over 2026-10-15 01:30 -> 2026-10-16 00:45: 28% estate utilisation,
89.9 of the 94.3 lane-hours lost to gaps were an EMPTY QUEUE rather than a
broken lane, and one shared gap, 03:21 -> 18:02, was 46.8 lane-hours on its
own. Two further breaches happened while that measurement was being written -
`suppression` at depth 0 with nothing in RUNNING since 02:40, `webapp` at
depth 0 behind its running brief since 02:19 - and a person found both by
reading `queue/` at 02:46, because no instrument in this estate records
depth over time.

So there is a ledger now. The interesting part is not the counting; it is the
four ways this page could show a clean estate while the estate starved, and
each one has a control here.

    C1  a planted breach is COUNTED. 40 minutes at depth 1 is 40 minutes
        below the floor, and the window is named.
    C2  a planted GAP reads UNKNOWN. The same fixture with 40 minutes of
        rows deleted reports UNKNOWN for that stretch and does NOT report
        zero below-floor minutes for it. Proven able to fail: the carry-
        forward mutation makes C2 red and leaves C1 green.
    C3  an EMPTY ledger reports NO TOTALS. Coverage "none" and no numbers.
        Proven able to fail: licensing every ledger makes an empty one print
        a clean estate - which this codebase has shipped before.
    C4  the FLOOR is read, not assumed. An unreadable floor is UNKNOWN with
        the path named, and 3 is never substituted. A hardcoded floor is the
        hand-kept denominator, failure family 2 in this estate's catalogue.

NOTHING HERE READS THE REAL ESTATE. Every ledger is a string this test writes
into a temporary directory, every watcher log is a string, and every process
table is a dict handed to the reader.
"""
import datetime
import json
import os
import shutil
import tempfile
import unittest

from src import floorledger, lanes
from src.web import api, pages

#: The instant every fixture is read at. Fixed, because a coverage claim is
#: an arithmetic statement about the distance between `now` and a row.
NOW = datetime.datetime(2026, 10, 16, 4, 0, 0)

LANE = "alpha"
OTHER_LANE = "beta"
WATCHER_PID = 4242


def stamp(when):
    return when.strftime(lanes._STAMP)


def at(minutes_before_now):
    return NOW - datetime.timedelta(minutes=minutes_before_now)


class Estate:
    """A temporary lane estate with a ledger, thrown away per test."""

    def setUp(self):
        super().setUp()
        self.root = tempfile.mkdtemp(prefix="rga-floor-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, "logs"))
        for lane in (LANE, OTHER_LANE):
            os.makedirs(os.path.join(self.root, "queue", lane, "RUNNING"))
            self.write(os.path.join(self.root, "LANE-%s.md" % lane),
                       "## entry 2026-10-16\n")
            self.write(os.path.join(self.root, "logs",
                                    "watcher-%s.pid" % lane),
                       "%d\n" % WATCHER_PID)
        self.readme(3)
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

    def readme(self, floor):
        """`queue/README.md` in the operator's own words, or without a floor.

        `floor=None` writes everything EXCEPT the floor sentence, which is
        the case the reader must call UNSTATED rather than fill in with 3.
        `floor` may also be a list, for the file that states two.
        """
        body = ["# LANE QUEUE", "", "## Queue depth"]
        floors = [] if floor is None else (
            floor if isinstance(floor, list) else [floor])
        for value in floors:
            body.append("**Floor: never leave a lane below %d queued "
                        "briefs.**" % value)
        # The arithmetic paragraph from the real file, which carries four
        # other numbers next to the word "brief". A loose floor pattern
        # would read the floor off one of these.
        body += ["", "    1 brief queued   ->  18 min of autonomy",
                 "    3 briefs         ->  54 min",
                 "    10 briefs        ->  3 hours",
                 "    17 briefs        ->  covers the overnight gap"]
        self.write(os.path.join(self.root, "queue", "README.md"),
                   "\n".join(body) + "\n")

    def ledger(self, *rows):
        """Write the ledger file from scratch. Fixture only.

        The PRODUCTION writer only ever appends - `test_the_ledger_is_append
        _only` is what holds it to that. A fixture may plant a history,
        because planting one is the whole method here.
        """
        path = floorledger.ledger_path(self.root)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.write(path, "".join(rows))
        return path

    @staticmethod
    def row(when, lane=LANE, depth=1, running=False,
            state=lanes.V_IDLE, floor=3, version=floorledger.SCHEMA):
        return json.dumps({"v": version, "at": stamp(when), "lane": lane,
                           "depth": depth, "running": running,
                           "state": state, "floor": floor},
                          sort_keys=True) + "\n"

    def series(self, minutes, step=5, **kwargs):
        """Samples every `step` minutes covering `minutes` ending at `now`.

        `minutes / step + 1` rows, because the newest sample speaks for
        nothing: a reading is an instant and only the stretch BETWEEN two of
        them is a duration.
        """
        count = minutes // step
        return [self.row(at(minutes - n * step), **kwargs)
                for n in range(count + 1)]

    def read(self):
        return floorledger.read(floorledger.ledger_path(self.root))

    def window(self, lane=LANE, minutes=None, **kwargs):
        seconds = (floorledger.WINDOW_SECONDS if minutes is None
                   else minutes * 60)
        return floorledger.lane_window(self.read(), lane, NOW,
                                       window_seconds=seconds, **kwargs)

    def log(self, lane, *rows):
        self.write(os.path.join(self.root, "logs", "watcher-%s.log" % lane),
                   "\n".join(rows) + "\n")

    def queue(self, lane, *names):
        for name in names:
            self.write(os.path.join(self.root, "queue", lane, name),
                       "# a brief\n")


class Probe:
    """A process table handed to the reader. No real process is consulted.

    `{pid: (parent_pid, image)}` - the shape `lanes._nt_table` returns, built
    by hand so a change to that shape fails here rather than producing a
    board that reads every lane UNCROSSED.
    """

    def __init__(self, alive=True):
        self.alive = alive

    def table(self):
        rows = {WATCHER_PID: (1, "powershell.exe")}
        if self.alive:
            rows[WATCHER_PID + 1] = (WATCHER_PID, "node.exe")
        return rows

    @staticmethod
    def cpu(pid):
        return 12.5


# ---------------------------------------------------------------------------
# C1. A planted breach is counted.


class C1APlantedBreachIsCounted(Estate, unittest.TestCase):
    """40 minutes at depth 1, against a floor of 3, is 40 minutes below it."""

    def test_forty_minutes_at_depth_one_is_forty_below_the_floor(self):
        self.ledger(*self.series(40, depth=1))
        row = self.window()
        self.assertEqual(row["below_floor_seconds"], 40 * 60)

    def test_the_window_is_named(self):
        """Not just a quantity: the stretch, with its two ends."""
        self.ledger(*self.series(40, depth=1))
        run = self.window()["longest_below_floor_run"]
        self.assertEqual(run["seconds"], 40 * 60)
        self.assertEqual(run["from"], at(40))
        self.assertEqual(run["to"], NOW)

    def test_depth_one_is_not_depth_zero(self):
        """A lane with one brief left is breaching and is NOT starved."""
        self.ledger(*self.series(40, depth=1))
        row = self.window()
        self.assertEqual(row["depth_zero_seconds"], 0)
        self.assertEqual(row["below_floor_seconds"], 40 * 60)

    def test_depth_zero_is_counted_as_both(self):
        self.ledger(*self.series(40, depth=0))
        row = self.window()
        self.assertEqual(row["depth_zero_seconds"], 40 * 60)
        self.assertEqual(row["below_floor_seconds"], 40 * 60)

    def test_at_the_floor_is_not_below_it(self):
        self.ledger(*self.series(40, depth=3))
        row = self.window()
        self.assertEqual(row["below_floor_seconds"], 0)
        self.assertEqual(row["within_floor_seconds"], 40 * 60)

    def test_the_newest_sample_speaks_for_nothing(self):
        """One reading is not a duration, and this is where that bites.

        Nine rows five minutes apart cover forty minutes, not forty-five.
        The stretch after the last row - including the sample this very
        render wrote - is UNKNOWN.
        """
        rows = self.series(40, depth=1)
        self.assertEqual(len(rows), 9)
        self.ledger(*rows)
        self.assertEqual(self.window()["below_floor_seconds"], 40 * 60)

    def test_a_window_the_ledger_covers_exactly_is_covered(self):
        self.ledger(*self.series(40, depth=1))
        self.assertTrue(self.window(minutes=40)["covers_window"])

    def test_a_window_wider_than_the_ledger_is_not_covered(self):
        """And the total is still reported - for the covered span, labelled.

        Refusing the number outright would leave the reader with nothing;
        presenting it as a statement about the day would be the lie. So the
        number stands and `covers_window` is False beside it.
        """
        self.ledger(*self.series(40, depth=1))
        row = self.window(minutes=120)
        self.assertFalse(row["covers_window"])
        self.assertEqual(row["below_floor_seconds"], 40 * 60)
        self.assertEqual(row["unknown_seconds"], 80 * 60)

    def test_the_hole_after_the_newest_row_is_named_and_is_not_zero(self):
        """One sample is not a duration, and this is the fixture that shows it.

        Rows from now-50 to now-10 and nothing since. The last ten minutes
        are UNKNOWN: no reading observed the lane in them, and that includes
        the sample a live render has just written - which is why a freshly
        sampled estate never reads as fully covered.
        """
        self.ledger(*[self.row(at(50 - n * 5), depth=1) for n in range(9)])
        row = self.window(minutes=50)
        holes = row["coverage"]["holes"]
        self.assertEqual([hole["why"] for hole in holes], ["after_last_row"])
        self.assertEqual(holes[0]["seconds"], 10 * 60)
        self.assertEqual(holes[0]["from"], at(10))
        self.assertEqual(holes[0]["to"], NOW)
        self.assertEqual(row["below_floor_seconds"], 40 * 60)
        self.assertEqual(row["unknown_seconds"], 10 * 60)
        self.assertFalse(row["covers_window"])

    def test_the_hole_before_the_first_row_is_named_and_is_not_zero(self):
        self.ledger(*self.series(40, depth=1))
        holes = self.window(minutes=120)["coverage"]["holes"]
        self.assertEqual([hole["why"] for hole in holes],
                         ["before_first_row"])
        self.assertEqual(holes[0]["seconds"], 80 * 60)


# ---------------------------------------------------------------------------
# C2. A planted gap reads UNKNOWN - and the control can fail.


class C2APlantedGapReadsUnknown(Estate, unittest.TestCase):
    """The same fixture with 40 minutes of rows deleted.

    80 minutes of samples at depth 1, middle 40 removed. The stretch with no
    row in it is UNKNOWN. It is not interpolated, it is not filled with the
    previous value, and it is NOT reported as zero below-floor minutes -
    which is the reading that would make a lane that stopped being sampled
    look like a lane that stopped breaching the floor.
    """

    def planted(self):
        """80 minutes of rows, with the 40 in the middle deleted.

        Five rows covering `now-80 .. now-60`, nothing at all until
        `now-20`, then five more to `now`. 20 observed minutes at each end
        and a 40-minute hole between them.
        """
        kept = self.series(80, depth=1)[:5] + self.series(20, depth=1)
        self.assertEqual(len(kept), 10)
        first = json.loads(kept[0])["at"]
        self.assertEqual(first, stamp(at(80)))
        return self.ledger(*kept)

    def planted_window(self):
        """The window the ledger has rows at both ends of.

        80 minutes exactly, so the only hole inside it is the planted one -
        a 24-hour window would also hold the much larger "before the first
        row" hole, which is a different control and would hide this one in
        the total.
        """
        return self.window(minutes=80)

    def test_the_deleted_stretch_is_unknown(self):
        self.planted()
        holes = [hole for hole in
                 self.planted_window()["coverage"]["holes"]
                 if hole["why"] == "gap"]
        self.assertEqual(len(holes), 1)
        self.assertEqual(holes[0]["seconds"], 40 * 60)
        self.assertEqual(holes[0]["from"], at(60))
        self.assertEqual(holes[0]["to"], at(20))

    def test_the_deleted_stretch_is_not_zero_below_floor(self):
        """THE ASSERTION THAT MATTERS. 40 observed minutes, 40 unknown.

        If the gap were read as compliant the below-floor total would be 40
        and the unknown total 0. If it were carried forward the total would
        be 80. Both are wrong and they are wrong in opposite directions, so
        the only honest answer names both numbers.
        """
        self.planted()
        row = self.planted_window()
        self.assertEqual(row["below_floor_seconds"], 40 * 60)
        self.assertEqual(row["unknown_seconds"], 40 * 60)
        self.assertFalse(row["covers_window"])

    def test_the_gap_breaks_the_run_rather_than_joining_it(self):
        """Two breaches with a hole between them are not one long breach."""
        self.planted()
        row = self.planted_window()
        self.assertEqual([run["seconds"] for run in row["below_floor_runs"]],
                         [20 * 60, 20 * 60])
        self.assertEqual(row["longest_below_floor_run"]["seconds"], 20 * 60)

    def test_a_compliant_stretch_between_two_breaches_breaks_the_run(self):
        """And it is CONTIGUOUS, which is what makes this the fixture.

        Depth 1 for 20 minutes, depth 3 for 10, depth 1 for 20 - no hole
        anywhere. The two breaches abut the compliant stretch exactly, so the
        contiguity check cannot tell them apart and the reset on a non-breach
        span is the only thing that refuses the join. Without it this reads
        as one 50-minute breach, 10 minutes of which was compliant.
        """
        rows = (self.series(50, depth=1)[:5]        # now-50 .. now-30
                + self.series(30, depth=3)[:3]      # now-30 .. now-20
                + self.series(20, depth=1))         # now-20 .. now
        self.ledger(*rows)
        row = self.window(minutes=50)
        self.assertEqual(row["unknown_seconds"], 0)
        self.assertEqual(row["below_floor_seconds"], 40 * 60)
        self.assertEqual(row["within_floor_seconds"], 10 * 60)
        self.assertEqual([run["seconds"] for run in row["below_floor_runs"]],
                         [20 * 60, 20 * 60])
        self.assertEqual(row["longest_below_floor_run"]["seconds"], 20 * 60)

    def test_a_zero_length_compliant_reading_does_not_break_the_run(self):
        """THE MEASURED LIMITATION, asserted so it cannot change in silence.

        A compliant reading taken in the SAME SECOND as the breach readings
        either side of it produces a span with no duration, and `_clip`
        drops a span with no duration before the run builder sees it. So the
        two breaches are reported as one continuous run.

        This is recorded rather than engineered around, and the reason is the
        size of it: the below-floor TOTAL is unaffected - the dropped span
        was zero seconds - and only the shape of the run moves. Written as an
        assertion rather than a comment because a comment would not notice if
        the behaviour changed. The page names it under "Not visible here".
        """
        self.ledger(self.row(at(20), depth=1), self.row(at(10), depth=1),
                    self.row(at(10), depth=3), self.row(at(10), depth=1),
                    self.row(NOW, depth=1))
        row = self.window(minutes=20)
        self.assertEqual(row["below_floor_seconds"], 20 * 60)
        self.assertEqual([run["seconds"] for run in row["below_floor_runs"]],
                         [20 * 60])

    def test_a_gap_inside_the_ceiling_is_attributed(self):
        """The ceiling is a ceiling, not a requirement to sample often.

        Two samples ten minutes apart - exactly `MAX_SAMPLE_GAP_SECONDS` -
        are still one attributable stretch. Eleven minutes are not.
        """
        self.ledger(self.row(at(10), depth=1), self.row(NOW, depth=1))
        self.assertEqual(self.window(minutes=10)["below_floor_seconds"],
                         10 * 60)
        self.ledger(self.row(at(11), depth=1), self.row(NOW, depth=1))
        row = self.window(minutes=11)
        self.assertEqual(row["below_floor_seconds"], 0)
        self.assertEqual(row["unknown_seconds"], 11 * 60)

    # --------------------------------------------------- it can go red
    #
    # THE MUTATION IS CARRY-FORWARD, which is exactly the defect the brief
    # names: make the gap detector hold the last value forward across the
    # hole. `_unknown_span` is the one place that decides a stretch cannot be
    # attributed, so replacing it with an attributed span IS that mutation.

    @staticmethod
    def _carry_forward(earlier, later, why):
        """The mutation. The hole becomes the state before it, held forward."""
        return floorledger._known_span(
            earlier, later, int((later["when"]
                                 - earlier["when"]).total_seconds()))

    def test_the_gap_detector_can_fail_and_c2_goes_red(self):
        """Run C2's own assertions under the mutation and watch them fail.

        THE UNMUTATED ANSWER IS ASSERTED FIRST. A test that was already red
        cannot be mistaken for a kill, and a mutation that reddens something
        for an unrelated reason is not a kill either - so the exact numbers
        the mutation produces are asserted, not merely the failure.
        """
        self.planted()
        clean = self.planted_window()
        self.assertEqual(clean["below_floor_seconds"], 40 * 60)
        self.assertEqual(clean["unknown_seconds"], 40 * 60)

        original = floorledger._unknown_span
        floorledger._unknown_span = self._carry_forward
        try:
            mutated = self.planted_window()
        finally:
            floorledger._unknown_span = original

        # The hole is now charged to the state before it: 80 minutes of
        # breach, nothing unknown, and the window reads fully covered.
        self.assertEqual(mutated["below_floor_seconds"], 80 * 60)
        self.assertEqual(mutated["unknown_seconds"], 0)
        self.assertTrue(mutated["covers_window"])
        # And the two runs have become one, which is the second half of the
        # same lie: a stretch nobody observed, presented as continuous.
        self.assertEqual(len(mutated["below_floor_runs"]), 1)
        self.assertEqual(mutated["longest_below_floor_run"]["seconds"],
                         80 * 60)

        with self.assertRaises(AssertionError):
            self.assertEqual(mutated["unknown_seconds"], 40 * 60)

    def test_c1_stays_green_under_the_same_mutation(self):
        """The control the brief asks for: C1 must NOT move.

        C1's fixture has no hole in it, so `_unknown_span` is never reached
        and the mutation is invisible to it. A mutation that reddens
        everything proves nothing about which guard was load-bearing.
        """
        self.ledger(*self.series(40, depth=1))
        original = floorledger._unknown_span
        floorledger._unknown_span = self._carry_forward
        try:
            row = self.window(minutes=40)
        finally:
            floorledger._unknown_span = original
        self.assertEqual(row["below_floor_seconds"], 40 * 60)
        self.assertEqual(row["longest_below_floor_run"]["seconds"], 40 * 60)
        self.assertEqual(row["unknown_seconds"], 0)


# ---------------------------------------------------------------------------
# C3. An empty ledger reports no totals - and the control can fail.


class C3AnEmptyLedgerReportsNoTotals(Estate, unittest.TestCase):
    """Zero rows is not zero breaches.

    Without this control an instrument with no data prints a clean estate,
    which this codebase has shipped: an evaluator reported INSUFFICIENT_DATA
    forever because nothing wrote the field it read, and the shape here is
    the same one with the sign flipped.
    """

    def ready(self):
        """A working estate, so the only thing missing is the ledger."""
        self.log(LANE, "[2026-10-16 00:00:00] [%s] watcher up. timeout=90m"
                 % LANE,
                 "[2026-10-16 03:00:00] [%s] START 0010-a.md" % LANE)
        self.log(OTHER_LANE,
                 "[2026-10-16 00:00:00] [%s] watcher up. timeout=90m"
                 % OTHER_LANE)
        self.queue(LANE, "0020-b.md")

    def shaped(self, write=False):
        self.ready()
        return api.floor_ledger(now=NOW, probe=Probe(), samples={},
                                write=write)

    def test_an_absent_ledger_licenses_nothing(self):
        self.assertFalse(floorledger.totals_licensed(self.read()))

    def test_an_empty_ledger_licenses_nothing(self):
        self.ledger()
        parsed = self.read()
        self.assertEqual(parsed["state"], floorledger.EMPTY)
        self.assertFalse(floorledger.totals_licensed(parsed))

    def test_a_whitespace_only_ledger_is_empty_and_not_present(self):
        self.ledger("\n", "   \n")
        self.assertEqual(self.read()["state"], floorledger.EMPTY)

    def test_the_shaper_reports_no_totals_and_says_why(self):
        data = self.shaped()
        self.assertFalse(data["totals_available"])
        self.assertIsNone(data["estate"])
        self.assertIn("ZERO ROWS IS NOT ZERO BREACHES", data["no_totals_why"])

    def test_the_page_says_coverage_none_and_prints_no_total(self):
        body = pages.floor_ledger(self.shaped())
        self.assertIn("COVERAGE: NONE", body)
        self.assertIn("Zero rows is not zero breaches", body)
        # The panel that holds every number is not rendered at all. Not a
        # table of dashes, not a row of zeros: absent.
        self.assertNotIn("Minutes below the floor", body)
        self.assertNotIn("Below the floor", body)
        self.assertNotIn("Longest single run", body)

    def test_an_empty_ledger_prints_no_minute_figure_anywhere(self):
        """Asserted over the whole page, not over one panel.

        A total that escaped into a stat tile or a note would satisfy every
        assertion above and still be the thing C3 exists to catch.
        """
        body = pages.floor_ledger(self.shaped())
        self.assertNotIn(" min<", body)
        self.assertNotIn("lane-minutes", body)

    def test_an_unreadable_ledger_is_not_an_empty_one(self):
        """A directory where the file should be: UNREADABLE, not ABSENT."""
        path = floorledger.ledger_path(self.root)
        os.makedirs(path, exist_ok=True)
        parsed = self.read()
        self.assertEqual(parsed["state"], floorledger.UNREADABLE)
        self.assertFalse(floorledger.totals_licensed(parsed))

    def test_an_oversize_ledger_is_refused_rather_than_tailed(self):
        """A tail would make the coverage a claim about the buffer size."""
        self.ledger(*self.series(40, depth=1))
        parsed = floorledger.read(floorledger.ledger_path(self.root),
                                  max_bytes=10)
        self.assertEqual(parsed["state"], floorledger.OVERSIZE)
        self.assertEqual(parsed["rows"], [])
        self.assertFalse(floorledger.totals_licensed(parsed))

    # --------------------------------------------------- it can go red

    def test_licensing_every_ledger_makes_an_empty_one_look_clean(self):
        """The mutation: `totals_licensed` always says yes.

        One patch, because the gate is named and lives in one place. Under it
        an empty ledger produces a full page of zeros - a clean estate drawn
        from nothing, which is precisely what C3 refuses.
        """
        self.ready()
        clean = pages.floor_ledger(self.shaped())
        self.assertIn("COVERAGE: NONE", clean)

        original = floorledger.totals_licensed
        floorledger.totals_licensed = lambda parsed: True
        try:
            data = api.floor_ledger(now=NOW, probe=Probe(), samples={},
                                    write=False)
            mutated = pages.floor_ledger(data)
        finally:
            floorledger.totals_licensed = original

        self.assertTrue(data["totals_available"])
        self.assertEqual(data["estate"]["totals"]["below_floor_seconds"], 0)
        self.assertIn("Minutes below the floor", mutated)
        self.assertNotIn("COVERAGE: NONE", mutated)
        with self.assertRaises(AssertionError):
            self.assertNotIn("Minutes below the floor", mutated)


# ---------------------------------------------------------------------------
# C4. The floor is read from the operator's file, never assumed.


class C4TheFloorIsReadNotAssumed(Estate, unittest.TestCase):
    """A hardcoded floor is the hand-kept denominator.

    `src.lanes` held `FLOOR = 3` with a docstring saying the real authority
    was `queue/README.md`. That fails in the one direction that matters: the
    operator raises the floor in his own file, nothing in the code changes,
    and every lane reads compliant against a number nobody is holding them
    to. A doc comment naming an authority is not reading it.
    """

    def floor(self):
        return lanes.read_floor(self.root)

    def test_the_operators_sentence_is_read(self):
        state, floor, path, line = self.floor()
        self.assertEqual(state, lanes.PRESENT)
        self.assertEqual(floor, 3)
        self.assertTrue(path.endswith(os.path.join("queue", "README.md")))
        self.assertIn("never leave a lane below 3 queued briefs", line)

    def test_a_raised_floor_is_followed(self):
        """The whole point. The file moves and the instrument moves with it."""
        self.readme(5)
        self.assertEqual(self.floor()[1], 5)

    def test_the_arithmetic_paragraph_is_not_mistaken_for_the_floor(self):
        """The same file says "1 brief queued", "3 briefs", "10", "17"."""
        self.readme(5)
        self.assertEqual(self.floor()[1], 5)

    def test_a_file_with_no_floor_is_unstated_and_not_three(self):
        self.readme(None)
        state, floor, path, _ = self.floor()
        self.assertEqual(state, lanes.FLOOR_UNSTATED)
        self.assertIsNone(floor)
        self.assertTrue(path)

    def test_a_file_that_states_two_floors_is_ambiguous(self):
        """UNKNOWN rather than first-wins: which is in force is his answer."""
        self.readme([3, 5])
        state, floor, _, line = self.floor()
        self.assertEqual(state, lanes.FLOOR_AMBIGUOUS)
        self.assertIsNone(floor)
        self.assertIn("|", line)

    def test_the_same_floor_stated_twice_is_not_ambiguous(self):
        self.readme([3, 3])
        self.assertEqual(self.floor()[0], lanes.PRESENT)
        self.assertEqual(self.floor()[1], 3)

    def test_an_absent_file_names_the_path_it_wanted(self):
        os.remove(os.path.join(self.root, "queue", "README.md"))
        state, floor, path, _ = self.floor()
        self.assertEqual(state, lanes.ABSENT)
        self.assertIsNone(floor)
        self.assertTrue(path.endswith("README.md"))

    def test_an_unreadable_file_is_not_an_absent_one(self):
        target = os.path.join(self.root, "queue", "README.md")
        os.remove(target)
        os.makedirs(target)
        self.assertEqual(self.floor()[0], lanes.UNREADABLE)

    def test_an_empty_file_is_not_an_unstated_one(self):
        self.write(os.path.join(self.root, "queue", "README.md"), "")
        self.assertEqual(self.floor()[0], lanes.EMPTY)

    def test_every_floor_state_has_a_sentence(self):
        """A state the page cannot explain would render as a blank reason."""
        for state in (lanes.PRESENT, lanes.ABSENT, lanes.UNREADABLE,
                      lanes.EMPTY, lanes.FLOOR_UNSTATED,
                      lanes.FLOOR_AMBIGUOUS):
            self.assertTrue(lanes.FLOOR_STATE_TEXT.get(state), state)

    def test_there_is_no_floor_constant_left_to_fall_back_on(self):
        """The guard against the defect coming back by convenience."""
        self.assertFalse(hasattr(lanes, "FLOOR"))

    def test_an_unknown_floor_produces_no_breach_verdict(self):
        """Not a breach, and very much not compliance."""
        self.readme(None)
        self.log(LANE, "[2026-10-16 00:00:00] [%s] watcher up. timeout=90m"
                 % LANE)
        board = lanes.board(root=self.root, now=NOW, probe=Probe(),
                            samples={})
        self.assertIsNone(board["floor"])
        self.assertEqual(board["floor_state"], lanes.FLOOR_UNSTATED)
        row = [r for r in board["lanes"] if r["lane"] == LANE][0]
        self.assertEqual(row["queue_depth"], 0)
        self.assertIsNone(row["below_floor"])

    def test_an_unknown_floor_is_said_on_the_page_with_the_path(self):
        self.readme(None)
        self.log(LANE, "[2026-10-16 00:00:00] [%s] watcher up. timeout=90m"
                 % LANE)
        body = pages.floor_ledger(
            api.floor_ledger(now=NOW, probe=Probe(), samples={}, write=False))
        self.assertIn("THE FLOOR IS UNKNOWN", body)
        self.assertIn("3 IS NOT ASSUMED", body)
        self.assertIn("README.md", body)

    def test_a_sample_records_the_floor_in_force_at_the_time(self):
        """So a floor that changes is visible in the series.

        History is not re-judged against a number nobody was held to when it
        happened.
        """
        self.log(LANE, "[2026-10-16 00:00:00] [%s] watcher up. timeout=90m"
                 % LANE)
        board = lanes.board(root=self.root, now=NOW, probe=Probe(),
                            samples={})
        rows = floorledger.sample_rows(board, at=NOW)
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row["floor"], 3)

    def test_a_row_with_no_floor_is_undecidable_and_not_compliant(self):
        self.ledger(*self.series(40, depth=1, floor=None))
        row = self.window()
        self.assertEqual(row["undecidable_seconds"], 40 * 60)
        self.assertEqual(row["below_floor_seconds"], 0)
        self.assertEqual(row["within_floor_seconds"], 0)
        self.assertFalse(row["covers_window"])

    def test_a_floor_that_changed_is_reported_rather_than_applied_back(self):
        self.ledger(*(self.series(40, depth=4, floor=3)[:5]
                      + self.series(20, depth=4, floor=5)))
        row = self.window()
        self.assertEqual(row["floors_seen"], [3, 5])
        # Depth 4 was compliant under a floor of 3 and is a breach under 5.
        self.assertEqual(row["below_floor_seconds"], 20 * 60)
        self.assertEqual(row["within_floor_seconds"], 20 * 60)


# ---------------------------------------------------------------------------
# A row that will not parse, and a row that is out of order.


class ADamagedRowPoisonsItsWindow(Estate, unittest.TestCase):
    """It is not skipped silently, and the count is printed."""

    def test_an_unparseable_row_is_counted(self):
        self.ledger(self.row(at(20), depth=1), "{not json\n",
                    self.row(at(10), depth=1), self.row(NOW, depth=1))
        parsed = self.read()
        self.assertEqual(len(parsed["rows"]), 3)
        self.assertEqual(len(parsed["damaged"]), 1)
        self.assertEqual(parsed["damaged"][0]["line_number"], 2)

    def test_the_stretch_it_sits_in_is_unknown(self):
        self.ledger(self.row(at(20), depth=1), "{not json\n",
                    self.row(at(10), depth=1), self.row(NOW, depth=1))
        row = self.window(minutes=20)
        holes = [hole for hole in row["coverage"]["holes"]
                 if hole["why"] == "damaged"]
        self.assertEqual(len(holes), 1)
        self.assertEqual(holes[0]["seconds"], 10 * 60)
        self.assertEqual(row["below_floor_seconds"], 10 * 60)
        self.assertEqual(row["unknown_seconds"], 10 * 60)

    def test_a_damaged_row_poisons_every_lane_not_just_one(self):
        """It may not even say which lane it was about.

        The bound that survives is its POSITION: the file is appended in time
        order, so a broken line lies between the rows either side of it.
        """
        self.ledger(self.row(at(20), lane=LANE, depth=1),
                    self.row(at(20), lane=OTHER_LANE, depth=1),
                    "}}}\n",
                    self.row(at(10), lane=LANE, depth=1),
                    self.row(at(10), lane=OTHER_LANE, depth=1),
                    self.row(NOW, lane=LANE, depth=1),
                    self.row(NOW, lane=OTHER_LANE, depth=1))
        for lane in (LANE, OTHER_LANE):
            holes = [hole for hole in
                     self.window(lane=lane)["coverage"]["holes"]
                     if hole["why"] == "damaged"]
            self.assertEqual(len(holes), 1, lane)

    def test_a_row_this_reader_does_not_know_the_version_of_is_damaged(self):
        self.ledger(self.row(at(10), depth=1, version=99),
                    self.row(NOW, depth=1))
        parsed = self.read()
        self.assertEqual(len(parsed["rows"]), 1)
        self.assertEqual(len(parsed["damaged"]), 1)

    def test_a_row_with_an_unparseable_timestamp_is_damaged(self):
        self.ledger(json.dumps({"v": 1, "at": "yesterday", "lane": LANE,
                                "depth": 1, "running": False,
                                "state": "idle", "floor": 3}) + "\n",
                    self.row(NOW, depth=1))
        self.assertEqual(len(self.read()["damaged"]), 1)

    def test_a_null_depth_is_a_valid_row_and_not_a_damaged_one(self):
        """UNKNOWN is the thing this ledger exists to record."""
        self.ledger(self.row(at(10), depth=None), self.row(NOW, depth=None))
        parsed = self.read()
        self.assertEqual(len(parsed["damaged"]), 0)
        self.assertIsNone(parsed["rows"][0]["depth"])

    def test_a_null_depth_is_undecidable_and_never_depth_zero(self):
        """An unreadable queue is not an empty queue."""
        self.ledger(*self.series(40, depth=None))
        row = self.window()
        self.assertEqual(row["depth_zero_seconds"], 0)
        self.assertEqual(row["below_floor_seconds"], 0)
        self.assertEqual(row["undecidable_seconds"], 40 * 60)

    def test_a_negative_depth_is_damaged(self):
        self.ledger(json.dumps({"v": 1, "at": stamp(NOW), "lane": LANE,
                                "depth": -1, "running": False,
                                "state": "idle", "floor": 3}) + "\n")
        self.assertEqual(len(self.read()["damaged"]), 1)

    def test_a_boolean_depth_is_damaged_rather_than_counted_as_one(self):
        """`True` is an `int` in Python and would silently read as depth 1."""
        self.ledger(json.dumps({"v": 1, "at": stamp(NOW), "lane": LANE,
                                "depth": True, "running": False,
                                "state": "idle", "floor": 3}) + "\n")
        self.assertEqual(len(self.read()["damaged"]), 1)

    def test_rows_out_of_order_are_unknown_rather_than_negative(self):
        self.ledger(self.row(NOW, depth=1), self.row(at(10), depth=1))
        row = self.window(minutes=10)
        self.assertEqual([hole["why"] for hole in row["coverage"]["holes"]],
                         ["disorder"])
        self.assertEqual(row["below_floor_seconds"], 0)
        # THE HOLE IS THE REAL STRETCH BETWEEN THE TWO READINGS. Taking the
        # ends in file order made it run backwards, and a backwards span
        # clips to nothing - so the hole vanished and the stretch read as
        # covered. That is what this assertion holds.
        self.assertEqual(row["unknown_seconds"], 10 * 60)
        self.assertFalse(row["covers_window"])

    def test_two_samples_in_the_same_second_are_a_zero_length_stretch(self):
        """Two renders inside one second is ordinary, not a defect."""
        self.ledger(self.row(NOW, depth=1), self.row(NOW, depth=1))
        row = self.window()
        self.assertEqual(row["below_floor_seconds"], 0)
        self.assertEqual([hole["why"] for hole
                          in row["coverage"]["holes"]], ["before_first_row"])

    def test_the_damaged_count_reaches_the_page(self):
        self.log(LANE, "[2026-10-16 00:00:00] [%s] watcher up. timeout=90m"
                 % LANE)
        self.ledger(self.row(at(10), depth=1), "oops\n", self.row(NOW,
                                                                  depth=1))
        data = api.floor_ledger(now=NOW, probe=Probe(), samples={},
                                write=False)
        self.assertEqual(data["damaged_rows"], 1)
        body = pages.floor_ledger(data)
        self.assertIn("UNPARSEABLE ROWS", body)


# ---------------------------------------------------------------------------
# Busy or already starved.


class TheSplitIsTheUsefulPart(Estate, unittest.TestCase):
    """Depth 0 behind a running task is a countdown. Depth 0 with nothing
    running is a stopped lane - and those are the minutes actually lost."""

    def test_below_floor_while_working_is_a_countdown(self):
        self.ledger(*self.series(40, depth=0, state=lanes.V_RUNNING,
                                 running=True))
        row = self.window()
        self.assertEqual(row["below_floor_by_bucket"][floorledger.WORKING],
                         40 * 60)
        self.assertEqual(row["below_floor_by_bucket"][floorledger.IDLE_], 0)

    def test_below_floor_while_idle_is_a_stopped_lane(self):
        self.ledger(*self.series(40, depth=0, state=lanes.V_IDLE))
        row = self.window()
        self.assertEqual(row["below_floor_by_bucket"][floorledger.IDLE_],
                         40 * 60)
        self.assertEqual(row["below_floor_by_bucket"][floorledger.WORKING], 0)

    def test_a_stuck_lane_is_neither_busy_nor_waiting(self):
        """It has an open task and is doing nothing. Both buckets are wrong.

        7.66 lane-hours went here in 23 hours, and the whole reason `0080`
        built the STUCK verdict is that every other signal called it healthy.
        """
        self.ledger(*self.series(40, depth=0, state=lanes.V_STUCK,
                                 running=True))
        row = self.window()
        self.assertEqual(row["below_floor_by_bucket"][floorledger.OTHER],
                         40 * 60)
        self.assertEqual(row["below_floor_by_bucket"][floorledger.WORKING], 0)
        self.assertEqual(row["below_floor_by_bucket"][floorledger.IDLE_], 0)
        self.assertEqual(row["other_states"], [(lanes.V_STUCK, 40 * 60)])

    def test_a_down_lane_is_not_idle(self):
        """IDLE means waiting for work; DOWN means waiting for a person."""
        self.ledger(*self.series(40, depth=0, state=lanes.V_DOWN))
        row = self.window()
        self.assertEqual(row["below_floor_by_bucket"][floorledger.IDLE_], 0)
        self.assertEqual(row["below_floor_by_bucket"][floorledger.OTHER],
                         40 * 60)

    def test_the_buckets_sum_to_the_below_floor_total(self):
        self.ledger(*(self.series(40, depth=0, state=lanes.V_RUNNING)[:5]
                      + self.series(20, depth=0, state=lanes.V_IDLE)))
        row = self.window()
        self.assertEqual(sum(row["below_floor_by_bucket"].values()),
                         row["below_floor_seconds"])

    def test_every_verdict_lands_in_exactly_one_bucket(self):
        """A verdict added to `src.lanes` cannot be silently absorbed."""
        for verdict in lanes.VERDICT_TEXT:
            bucket = floorledger.bucket_for(verdict)
            self.assertIn(bucket, (floorledger.WORKING, floorledger.IDLE_,
                                   floorledger.OTHER), verdict)
        self.assertEqual(floorledger.bucket_for(lanes.V_RUNNING),
                         floorledger.WORKING)
        self.assertEqual(floorledger.bucket_for(lanes.V_IDLE),
                         floorledger.IDLE_)
        self.assertEqual(floorledger.bucket_for("a verdict nobody has named"),
                         floorledger.OTHER)

    def test_every_bucket_has_a_sentence(self):
        for bucket in (floorledger.WORKING, floorledger.IDLE_,
                       floorledger.OTHER):
            self.assertTrue(floorledger.BUCKET_TEXT[bucket][1], bucket)

    def test_the_split_does_not_come_from_the_running_folder(self):
        """`0080` measured that signal wrong in both directions.

        A brief in `RUNNING/` whose owner is dead is not a busy lane: two sat
        like that for 97 minutes each. So a row saying `running: true` with a
        STUCK verdict is charged to neither bucket, and the verdict decides.
        """
        self.ledger(*self.series(40, depth=0, state=lanes.V_STALLED,
                                 running=True))
        row = self.window()
        self.assertEqual(row["below_floor_by_bucket"][floorledger.WORKING], 0)


class TheSampleRecordsTheCrossedVerdict(Estate, unittest.TestCase):
    """What `sample_rows` writes down, and why it is not the log's answer.

    A watcher whose task owner has died writes `a task is already in
    RUNNING: <brief>, not starting another` every twenty seconds. The log
    still holds a START with no DONE, so the LOG's own status is RUNNING, the
    process table has the watcher alive, and `RUNNING/` has a brief in it.
    All three signals say busy about a lane doing nothing - 7.66 lane-hours
    in 23 hours. Only the crossed verdict says STUCK, and the crossed verdict
    is what goes into the ledger.
    """

    def stuck_lane(self):
        rows = ["[2026-10-16 00:00:00] [%s] watcher up. "
                "tree=C:\\somewhere timeout=90m" % LANE,
                "[2026-10-16 00:10:00] [%s] START 0010-a.md" % LANE]
        rows += ["[2026-10-16 02:%02d:00] [%s] a task is already in RUNNING: "
                 "0010-a.md, not starting another" % (n, LANE)
                 for n in range(0, 50)]
        self.log(LANE, *rows)
        self.log(OTHER_LANE,
                 "[2026-10-16 00:00:00] [%s] watcher up. timeout=90m"
                 % OTHER_LANE)
        return lanes.board(root=self.root, now=NOW, probe=Probe(),
                           samples={})

    def test_the_log_says_running_and_the_verdict_says_stuck(self):
        """The premise, asserted before anything is built on it."""
        board = self.stuck_lane()
        row = [r for r in board["lanes"] if r["lane"] == LANE][0]
        self.assertEqual(row["status"], lanes.RUNNING)
        self.assertEqual(row["verdict"], lanes.V_STUCK)

    def test_the_sample_records_the_verdict_and_not_the_log_status(self):
        board = self.stuck_lane()
        rows = {row["lane"]: row for row in
                floorledger.sample_rows(board, at=NOW)}
        self.assertEqual(rows[LANE]["state"], lanes.V_STUCK)
        self.assertNotEqual(rows[LANE]["state"], lanes.RUNNING)

    def test_that_sample_is_charged_to_neither_bucket(self):
        """End to end: the recorded state decides the split."""
        board = self.stuck_lane()
        rows = floorledger.sample_rows(board, at=NOW)
        state = {row["lane"]: row["state"] for row in rows}[LANE]
        self.assertEqual(floorledger.bucket_for(state), floorledger.OTHER)

    def test_running_is_recorded_but_is_not_the_authority(self):
        """The brief asks for it; `0080` measured it wrong in both
        directions. It is written down for reconciliation and nothing on the
        page reads it as busy."""
        self.write(os.path.join(self.root, "queue", LANE, "RUNNING",
                                "0010-a.md"), "# in flight\n")
        board = self.stuck_lane()
        rows = {row["lane"]: row for row in
                floorledger.sample_rows(board, at=NOW)}
        self.assertTrue(rows[LANE]["running"])
        self.assertEqual(rows[LANE]["state"], lanes.V_STUCK)
        self.assertEqual(floorledger.bucket_for(rows[LANE]["state"]),
                         floorledger.OTHER)


# ---------------------------------------------------------------------------
# The writer.


class TheLedgerIsAppendOnly(Estate, unittest.TestCase):
    """The file is the only record of what was observed."""

    def ready(self):
        self.log(LANE, "[2026-10-16 00:00:00] [%s] watcher up. timeout=90m"
                 % LANE,
                 "[2026-10-16 03:00:00] [%s] START 0010-a.md" % LANE)
        self.log(OTHER_LANE,
                 "[2026-10-16 00:00:00] [%s] watcher up. timeout=90m"
                 % OTHER_LANE)
        self.queue(LANE, "0020-b.md")

    def raw(self):
        with open(floorledger.ledger_path(self.root), encoding="utf-8") as h:
            return h.read()

    def test_a_render_appends_one_row_per_lane(self):
        self.ready()
        report = floorledger.render(root=self.root, now=NOW, probe=Probe(),
                                    samples={})
        self.assertEqual(report["append"]["state"], floorledger.WRITTEN)
        self.assertEqual(report["append"]["written"], 2)
        self.assertEqual(len(report["ledger"]["rows"]), 2)

    def test_a_second_render_adds_and_never_rewrites(self):
        self.ready()
        floorledger.render(root=self.root, now=at(5), probe=Probe(),
                           samples={})
        first = self.raw()
        floorledger.render(root=self.root, now=NOW, probe=Probe(),
                           samples={})
        second = self.raw()
        # The earlier bytes are still there, unchanged, at the front.
        self.assertTrue(second.startswith(first))
        self.assertGreater(len(second), len(first))

    def test_every_row_of_one_render_carries_the_same_instant(self):
        """The span arithmetic depends on it: a hole has to be locatable in
        every lane's series at once."""
        self.ready()
        report = floorledger.render(root=self.root, now=NOW, probe=Probe(),
                                    samples={})
        stamps = {row["at"] for row in report["ledger"]["rows"]}
        self.assertEqual(stamps, {stamp(NOW)})

    def test_the_numbers_are_read_back_from_the_file(self):
        """Not from the rows handed to `append`. A tool reporting success is
        not evidence the write landed."""
        self.ready()
        report = floorledger.render(root=self.root, now=NOW, probe=Probe(),
                                    samples={})
        self.assertEqual(report["ledger"]["path"],
                         floorledger.ledger_path(self.root))
        self.assertEqual(len(report["ledger"]["rows"]), 2)

    def test_a_write_that_fails_is_reported_rather_than_swallowed(self):
        """A ledger silently not growing is indistinguishable from an estate
        that never breached."""
        self.ready()
        path = floorledger.ledger_path(self.root)
        os.makedirs(path, exist_ok=True)
        report = floorledger.render(root=self.root, now=NOW, probe=Probe(),
                                    samples={})
        self.assertEqual(report["append"]["state"], floorledger.UNWRITABLE)
        self.assertEqual(report["append"]["written"], 0)
        self.assertTrue(floorledger.APPEND_TEXT[floorledger.UNWRITABLE])

    def test_write_false_grows_nothing(self):
        self.ready()
        report = floorledger.render(root=self.root, now=NOW, probe=Probe(),
                                    samples={}, write=False)
        self.assertEqual(report["append"]["state"],
                         floorledger.NOTHING_TO_WRITE)
        self.assertFalse(os.path.exists(floorledger.ledger_path(self.root)))

    def test_the_ledger_lives_under_runtime_and_nowhere_else(self):
        path = floorledger.ledger_path(self.root)
        self.assertEqual(os.path.dirname(path),
                         os.path.join(self.root, floorledger.RUNTIME_DIR))

    def test_rendering_writes_no_brief_and_touches_no_queue(self):
        """THE BOUNDARY. A brief invented by a measuring instrument is the
        worst possible thing to put in front of the dispatcher."""
        self.ready()
        before = {}
        for walk_root, dirs, files in os.walk(
                os.path.join(self.root, "queue")):
            for name in files:
                full = os.path.join(walk_root, name)
                before[full] = os.path.getsize(full)
        floorledger.render(root=self.root, now=NOW, probe=Probe(),
                           samples={})
        after = {}
        for walk_root, dirs, files in os.walk(
                os.path.join(self.root, "queue")):
            for name in files:
                full = os.path.join(walk_root, name)
                after[full] = os.path.getsize(full)
        self.assertEqual(before, after)

    def test_rendering_touches_no_watcher_log(self):
        self.ready()
        logs = os.path.join(self.root, "logs")
        before = {name: os.path.getsize(os.path.join(logs, name))
                  for name in os.listdir(logs)}
        floorledger.render(root=self.root, now=NOW, probe=Probe(),
                           samples={})
        after = {name: os.path.getsize(os.path.join(logs, name))
                 for name in os.listdir(logs)}
        self.assertEqual(before, after)

    def test_a_sample_records_the_depth_as_unknown_when_it_is(self):
        self.ready()
        shutil.rmtree(os.path.join(self.root, "queue", OTHER_LANE))
        report = floorledger.render(root=self.root, now=NOW, probe=Probe(),
                                    samples={})
        rows = {row["lane"]: row for row in report["ledger"]["rows"]}
        self.assertIsNone(rows[OTHER_LANE]["depth"])
        self.assertEqual(rows[LANE]["depth"], 1)


# ---------------------------------------------------------------------------
# The estate total, and the page.


class TheEstateTotalIsLaneMinutes(Estate, unittest.TestCase):

    def test_two_lanes_below_the_floor_sum_as_lane_seconds(self):
        self.ledger(*(self.series(40, lane=LANE, depth=1)
                      + self.series(40, lane=OTHER_LANE, depth=0)))
        estate = floorledger.estate_window(self.read(), [LANE, OTHER_LANE],
                                           NOW)
        self.assertEqual(estate["totals"]["below_floor_seconds"], 80 * 60)
        self.assertEqual(estate["totals"]["depth_zero_seconds"], 40 * 60)

    def test_one_lane_with_a_hole_disqualifies_the_estate_window(self):
        self.ledger(*(self.series(40, lane=LANE, depth=1)
                      + [self.row(at(80), lane=OTHER_LANE, depth=1),
                         self.row(NOW, lane=OTHER_LANE, depth=1)]))
        estate = floorledger.estate_window(self.read(), [LANE, OTHER_LANE],
                                           NOW, window_seconds=40 * 60)
        self.assertFalse(estate["covers_window"])
        self.assertEqual(estate["lanes_not_covering"], [OTHER_LANE])

    def test_the_longest_run_names_its_lane(self):
        self.ledger(*(self.series(20, lane=LANE, depth=1)
                      + self.series(40, lane=OTHER_LANE, depth=1)))
        estate = floorledger.estate_window(self.read(), [LANE, OTHER_LANE],
                                           NOW)
        self.assertEqual(estate["longest_below_floor_run"]["lane"],
                         OTHER_LANE)
        self.assertEqual(estate["longest_below_floor_run"]["seconds"],
                         40 * 60)

    def test_a_lane_with_no_row_is_unknown_and_not_compliant(self):
        self.ledger(*self.series(40, lane=LANE, depth=1))
        estate = floorledger.estate_window(self.read(), [LANE, OTHER_LANE],
                                           NOW, window_seconds=40 * 60)
        rows = {row["lane"]: row for row in estate["lanes"]}
        self.assertEqual(rows[OTHER_LANE]["unknown_seconds"], 40 * 60)
        self.assertEqual(rows[OTHER_LANE]["below_floor_seconds"], 0)
        self.assertFalse(rows[OTHER_LANE]["covers_window"])
        self.assertEqual(
            [hole["why"] for hole in rows[OTHER_LANE]["coverage"]["holes"]],
            ["no_rows"])


class ThePageSaysTheCoverageOutLoud(Estate, unittest.TestCase):

    def ready(self):
        self.log(LANE, "[2026-10-16 00:00:00] [%s] watcher up. timeout=90m"
                 % LANE,
                 "[2026-10-16 03:00:00] [%s] START 0010-a.md" % LANE)
        self.log(OTHER_LANE,
                 "[2026-10-16 00:00:00] [%s] watcher up. timeout=90m"
                 % OTHER_LANE)

    def body(self):
        self.ready()
        return pages.floor_ledger(
            api.floor_ledger(now=NOW, probe=Probe(), samples={}, write=False))

    def test_the_coverage_is_printed_above_the_totals(self):
        self.ledger(*(self.series(40, lane=LANE, depth=1)
                      + self.series(40, lane=OTHER_LANE, depth=1)))
        body = self.body()
        self.assertIn("What this ledger can speak for", body)
        self.assertIn("Minutes below the floor", body)
        self.assertLess(body.index("What this ledger can speak for"),
                        body.index("Minutes below the floor"))

    def test_the_sentence_is_on_the_page_not_in_a_footnote(self):
        self.ledger(*(self.series(40, lane=LANE, depth=1)
                      + self.series(40, lane=OTHER_LANE, depth=1)))
        body = self.body()
        self.assertIn("EVERYTHING BEFORE THE FIRST ROW IS UNKNOWN, NOT ZERO",
                      body)
        self.assertIn("COVERAGE", body)

    def test_a_window_the_ledger_does_not_cover_is_labelled(self):
        self.ledger(*(self.series(40, lane=LANE, depth=1)
                      + self.series(40, lane=OTHER_LANE, depth=1)))
        body = self.body()
        self.assertIn("NOT A TOTAL FOR THE WINDOW", body)
        self.assertNotIn("FULL WINDOW", body)

    def test_a_gap_is_shown_as_unknown_and_never_interpolated(self):
        rows = (self.series(80, lane=LANE, depth=1)[:5]
                + self.series(20, lane=LANE, depth=1)
                + self.series(80, lane=OTHER_LANE, depth=1))
        self.ledger(*rows)
        body = self.body()
        self.assertIn("UNKNOWN", body)
        self.assertIn("never interpolated", body)

    def test_the_longest_run_is_named_with_both_ends(self):
        self.ledger(*(self.series(40, lane=LANE, depth=1)
                      + self.series(40, lane=OTHER_LANE, depth=3)))
        body = self.body()
        self.assertIn("LONGEST SINGLE RUN", body)
        self.assertIn(stamp(at(40)), body)

    def test_the_split_is_explained_on_the_page(self):
        self.ledger(*(self.series(40, lane=LANE, depth=0,
                                  state=lanes.V_IDLE)
                      + self.series(40, lane=OTHER_LANE, depth=0,
                                    state=lanes.V_RUNNING)))
        body = self.body()
        self.assertIn("already starved", body)
        self.assertIn("COUNTDOWN", body)

    def test_no_absolute_path_is_printed(self):
        """A path on a screen is somebody's home directory in a screenshot."""
        self.ledger(*self.series(40, lane=LANE, depth=1))
        body = self.body()
        self.assertNotIn(self.root, body)
        self.assertIn(os.path.basename(self.root), body)

    def test_the_page_reaches_no_provider_and_opens_no_socket(self):
        """Asserted on the import graph rather than on the source text."""
        import src.floorledger as module
        source = module.__dict__
        self.assertNotIn("requests", source)
        self.assertNotIn("urllib", source)
        self.assertNotIn("socket", source)


if __name__ == "__main__":                                  # pragma: no cover
    unittest.main()
