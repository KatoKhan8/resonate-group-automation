"""Queue depth that is there, and queue depth that can run. Not one number.

WHAT THIS FILE IS FOR. The operator's floor - "never leave a lane below 3
queued briefs" - is enforced against a count of files in `queue/<lane>/`,
and on 2026-10-16 that count was wrong in two directions at once. Sixteen
briefs across `glm`, `glm-b`, `glm-c` and `qwen` sat behind watchers that
had been gone since 01:46-01:48 and 00:58:53; by file count all four were at
or above the floor and not one of those briefs could start. `pilotcaps` sat
AT the floor with two of its three briefs already recorded as done in its
own lane file. `src.queuedepth` renders both numbers and re-derives the
floor verdict from the second one, and this file is the proof that it can
be wrong in every direction it is allowed to answer.

NOTHING HERE READS THE REAL ESTATE. Every watcher log, pid file, lane file
and brief below is written into a temporary directory, and every process
table is a dict handed to the reader. `C7` replays the real 05:46 state, but
as a FIXTURE built from those bytes rather than by opening the estate, so the
regression is deterministic and needs neither the lanes nor a live watcher.

THE SEVEN CONTROLS. `C1` alone would pass for a reader that always answers
"consumable"; `C2` and `C3` are the two subtractions and each has a mutation
that must redden it alone. `C4` is the locked brief in `RUNNING\\`, which is
neither queued nor running. `C5` is the fail-closed control and it is the one
for the defect that cost this estate most on 2026-10-15: an unknown reported
as the nearest available name. `C6` is the PAIRED direction - `0130` recorded
that one of its controls could not detect a classifier answering the same
every time, and that the pair was the measurement - so the consumable
calculation is mutated to always-0 and to always-raw, and a kill-set is named
each way. `C7` is the regression against tonight.

ZERO AND UNKNOWN ARE KEPT APART IN EVERY ASSERTION. A lane with nothing left
to consume reads 0 and is STARVED; a lane whose consumable depth could not
be established reads UNKNOWN and has no floor verdict at all. A lane whose
watcher is gone reads 0 and is STRANDED, which is a different emergency with
a different owner - and `CStarvationIsNotStranding` proves the panel cannot
print them as the same thing.
"""
import datetime
import os
import shutil
import tempfile
import unittest

from src import lanes
from src import queuedepth as qd
from src.web import api, pages

NOW = datetime.datetime(2026, 10, 16, 8, 0, 0)
DAY = "2026-10-16"

#: The floor the fixture's `queue/README.md` states, in the operator's own
#: words. Read by `src.lanes.read_floor`, never a constant in the reader.
FLOOR = 3

#: Parent of every watcher in the fake process table. Any pid will do; the
#: reader walks DOWN from the watcher and never up.
SYSTEM = 1


def line(clock, message, lane, day=DAY):
    """One watcher record, in the exact shape `lane_watcher.ps1` writes."""
    return "[%s %s] [%s] %s" % (day, clock, lane, message)


def up(lane, clock="00:00:00", timeout=90):
    return line(clock, "watcher up. tree=C:\\somewhere "
                       "mode=bypassPermissions timeout=%dm" % timeout, lane)


def start(lane, clock, brief):
    return line(clock, "START %s" % brief, lane)


def done(lane, clock, brief, suffix="exit0"):
    return line(clock, "DONE  %s -> %s" % (brief, suffix), lane)


def down(lane, clock):
    return line(clock, "watcher down.", lane)


def guard(lane, clock, failures=3):
    return line(clock, "%d consecutive failures. Exiting rather than looping "
                       "on a broken task." % failures, lane)


class FakeProbe:
    """A process table handed to the reader, never measured.

    `live` is the set of watcher pids the table holds. A pid file naming a
    pid outside it is the shape of a watcher taken by `Stop-Process`: the
    file survives and the table does not hold the process. `table=None` is
    the refusal - no table at all, so liveness is UNKNOWN and must produce
    neither an alarm nor a pass.
    """

    def __init__(self, live=(), children=(), table=True):
        self.live = set(live)
        self.children = set(children)
        self.has_table = table

    def table(self):
        if not self.has_table:
            return None
        rows = {SYSTEM: (0, "system")}
        for pid in self.live:
            rows[pid] = (SYSTEM, "powershell.exe")
        for pid, parent in self.children:
            rows[pid] = (parent, "node.exe")
        return rows

    def cpu(self, pid):
        return 11.0


class Estate:
    """A temporary lane estate. One directory per test, thrown away after."""

    def setUp(self):
        super().setUp()
        self.root = tempfile.mkdtemp(prefix="rga-depth-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, "logs"))
        os.makedirs(os.path.join(self.root, "queue"))
        self.readme(FLOOR)
        self.live = set()
        self.children = set()
        self.has_table = True

    def readme(self, floor):
        """`queue/README.md` as the operator writes it, or no floor at all.

        The floor is READ from this file and never a constant in the reader,
        so a fixture that omits the sentence has an UNKNOWN floor and gets no
        breach verdict at all.
        """
        body = ["# LANE QUEUE", "", "## Queue depth"]
        if floor is not None:
            body.append("**Floor: never leave a lane below %d queued "
                        "briefs.**" % floor)
        self._write(os.path.join(self.root, "queue", "README.md"),
                    "\n".join(body) + "\n")

    @staticmethod
    def _write(path, text):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def lane(self, name, queued=(), running=(), log=None, pid=None,
             alive=False, child=False, lane_file="", no_lane_file=False,
             unreadable_lane_file=False):
        """One lane, with every authority the reader crosses.

        `pid=None` writes no pid file at all, which is the AMBIGUOUS state -
        the watcher removes it on a clean exit and a hard kill leaves it
        behind - so liveness is UNKNOWN unless the log settles it.
        """
        queue_dir = os.path.join(self.root, "queue", name)
        os.makedirs(os.path.join(queue_dir, "RUNNING"), exist_ok=True)
        for brief in queued:
            self._write(os.path.join(queue_dir, brief), "# a brief\n")
        for brief in running:
            self._write(os.path.join(queue_dir, "RUNNING", brief),
                        "# in flight\n")
        rows = log if log is not None else [up(name),
                                            start(name, "07:00:00", "x.md"),
                                            done(name, "07:30:00", "x.md")]
        self._write(os.path.join(self.root, "logs", "watcher-%s.log" % name),
                    "\n".join(rows) + "\n")
        if pid is not None:
            self._write(os.path.join(self.root, "logs",
                                     "watcher-%s.pid" % name), "%d\n" % pid)
            if alive:
                self.live.add(pid)
            if child:
                self.children.add((pid * 10 + 1, pid))
        path = os.path.join(self.root, "LANE-%s.md" % name)
        if unreadable_lane_file:
            # A DIRECTORY where the reader expects a file: it exists, so it
            # is not ABSENT, and it cannot be opened, so it is UNREADABLE.
            # Those are two different states with two different repairs and
            # `_read_text` keeps them apart.
            os.makedirs(path, exist_ok=True)
        elif not no_lane_file:
            self._write(path, lane_file)

    def entry(self, lane, task, text="done"):
        """One appended entry in `LANE-<lane>.md`, in this estate's shape."""
        path = os.path.join(self.root, "LANE-%s.md" % lane)
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write("## %s \u2014 TASK %s \u2014 %s\n\nbody\n\n"
                         % (DAY, task, text))

    # ------------------------------------------------------------ the reads

    def probe(self):
        return FakeProbe(live=self.live, children=self.children,
                         table=self.has_table)

    def data(self, now=None):
        return qd.consumable(root=self.root, now=now or NOW,
                             probe=self.probe(), samples={})

    def row(self, lane, now=None):
        found = [r for r in self.data(now=now)["lanes"] if r["lane"] == lane]
        self.assertEqual(len(found), 1, "expected one row for %r" % lane)
        return found[0]

    def rendered(self, now=None):
        """The panel's HTML, through the api that attaches the words."""
        data = api.queue_depth(root=self.root, now=now or NOW,
                               probe=self.probe(), samples={})
        return pages.queue_depth(data)


# --------------------------------------------------------------------------
# C1 - a live watcher with real work. The control that a reader answering
# "nothing is consumable" would fail.
# --------------------------------------------------------------------------

class C1LiveWatcherWithWork(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.lane("alpha", queued=["0010-a.md", "0020-b.md", "0030-c.md"],
                  pid=4242, alive=True, lane_file="# nothing landed yet\n")

    def test_the_raw_depth_is_the_file_count(self):
        self.assertEqual(self.row("alpha")["raw_depth"], 3)

    def test_the_consumable_depth_equals_the_raw_depth(self):
        """Nothing is subtracted: the watcher is live and no brief has
        landed. A reader that always answered 0 would fail here and nowhere
        else, which is what makes C6's first direction a measurement."""
        self.assertEqual(self.row("alpha")["consumable_depth"], 3)

    def test_the_watcher_reads_live(self):
        row = self.row("alpha")
        self.assertEqual(row["watcher"], qd.W_LIVE)

    def test_it_is_not_below_the_floor_on_either_number(self):
        row = self.row("alpha")
        self.assertIs(row["below_floor"], False)
        self.assertIs(row["below_floor_raw"], False)
        self.assertFalse(row["verdicts_disagree"])

    def test_the_state_is_ok_and_not_starved(self):
        self.assertEqual(self.row("alpha")["state"], qd.S_OK)

    def test_nothing_is_unknown_and_the_reason_list_is_empty(self):
        row = self.row("alpha")
        self.assertEqual(row["unknown_because"], [])
        self.assertTrue(row["consumable_known"])

    def test_the_estate_totals_cover_every_lane(self):
        data = self.data()
        self.assertEqual(data["raw_total"], 3)
        self.assertEqual(data["consumable_total"], 3)
        self.assertEqual(data["consumable_lanes"], data["lane_count"])
        self.assertTrue(data["consumable_complete"])
        self.assertEqual(data["stranded_briefs"], 0)


# --------------------------------------------------------------------------
# C2 - a dead watcher. Raw depth above the floor, consumable 0, and the raw
# number still on the page.
# --------------------------------------------------------------------------

class C2DeadWatcherConsumesNothing(Estate, unittest.TestCase):

    BRIEFS = ["0010-a.md", "0020-b.md", "0030-c.md", "0040-d.md",
              "0050-e.md"]

    def setUp(self):
        super().setUp()
        # The pid file survives and the table does not hold the process:
        # `Stop-Process` took the watcher and it never got to log anything.
        self.lane("beta", queued=self.BRIEFS, pid=5151, alive=False,
                  lane_file="# nothing landed\n")

    def test_the_raw_depth_is_still_five(self):
        """THE RAW NUMBER IS NEVER REPLACED. Those five briefs are real work
        and a panel that dropped them because they cannot start would hide
        exactly what it exists to show."""
        self.assertEqual(self.row("beta")["raw_depth"], 5)

    def test_the_consumable_depth_is_zero(self):
        self.assertEqual(self.row("beta")["consumable_depth"], 0)

    def test_the_watcher_reads_dead_from_the_pid_table(self):
        row = self.row("beta")
        self.assertEqual(row["watcher"], qd.W_DEAD)
        self.assertIn("table does not hold", row["watcher_why"])

    def test_zero_is_a_measurement_and_not_an_unknown(self):
        """A dead watcher is an ANSWER. Reporting UNKNOWN here would throw
        away the strongest alarm on the panel - and 0 is an upper bound, so
        it is provable whatever the other two subtractions say."""
        row = self.row("beta")
        self.assertTrue(row["consumable_known"])
        self.assertEqual(row["unknown_because"], [])

    def test_below_floor_is_re_derived_from_the_dead_watchers_zero(self):
        row = self.row("beta")
        self.assertIs(row["below_floor"], True)

    def test_the_raw_verdict_said_it_was_compliant(self):
        """The whole finding, in one assertion: five queued briefs are at or
        above a floor of three, so the number the floor was enforced against
        read this lane as fine."""
        row = self.row("beta")
        self.assertIs(row["below_floor_raw"], False)
        self.assertTrue(row["verdicts_disagree"])

    def test_the_state_is_stranded_and_not_starved(self):
        self.assertEqual(self.row("beta")["state"], qd.S_STRANDED)

    def test_the_estate_counts_the_stranded_briefs(self):
        data = self.data()
        self.assertEqual(data["stranded_briefs"], 5)
        self.assertEqual(data["stranded_lanes"], ["beta"])
        self.assertEqual(data["starved_lanes"], [])

    def test_a_watcher_that_logged_its_own_exit_is_dead_too(self):
        """The other way to be dead, and the one `glm`, `glm-b` and `glm-c`
        were in at 07:50: no pid file at all, and a log whose last record is
        `watcher down.`. Liveness from the pid table alone would call all
        three UNKNOWN."""
        self.lane("gamma", queued=["0010-a.md", "0020-b.md", "0030-c.md"],
                  log=[up("gamma"), start("gamma", "01:00:00", "y.md"),
                       done("gamma", "01:40:00", "y.md", "exit1"),
                       guard("gamma", "01:46:23"), down("gamma", "01:46:23")],
                  pid=None, lane_file="# nothing landed\n")
        row = self.row("gamma")
        self.assertEqual(row["watcher"], qd.W_DEAD)
        self.assertIn("watcher down.", row["watcher_why"])
        self.assertEqual(row["consumable_depth"], 0)
        self.assertEqual(row["raw_depth"], 3)
        self.assertIs(row["below_floor"], True)
        self.assertIs(row["below_floor_raw"], False)

    def test_a_dead_watcher_with_an_empty_queue_is_not_stranded(self):
        """Nothing is being denied to a lane that could not take it. A
        restart alone would leave this lane starved, which is why it has its
        own word."""
        self.lane("delta", queued=[], pid=6161, alive=False,
                  lane_file="# nothing\n")
        row = self.row("delta")
        self.assertEqual(row["state"], qd.S_DEAD_EMPTY)
        self.assertEqual(row["consumable_depth"], 0)
        self.assertEqual(row["raw_depth"], 0)


# --------------------------------------------------------------------------
# C3 - briefs whose work has already landed. Subtraction 2, and it is
# `src.lanerework`'s classifier consumed rather than rebuilt.
# --------------------------------------------------------------------------

class C3AlreadyLandedIsNotConsumableWork(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.lane("alpha", queued=["0010-a.md", "0020-b.md", "0030-c.md"],
                  pid=4242, alive=True, lane_file="# LANE-alpha\n\n")
        self.estate_entries()

    def estate_entries(self):
        self.entry("alpha", "0010", "the first one, already done")
        self.entry("alpha", "0020", "the second one, already done")

    def test_the_raw_depth_is_three(self):
        self.assertEqual(self.row("alpha")["raw_depth"], 3)

    def test_the_consumable_depth_is_one(self):
        self.assertEqual(self.row("alpha")["consumable_depth"], 1)

    def test_the_landed_briefs_are_named_with_their_entry_lines(self):
        """A claim a reader cannot check is a claim they have to trust. The
        entry's line number is what makes it checkable."""
        row = self.row("alpha")
        self.assertEqual([item["brief"] for item in row["landed"]],
                         ["0010-a.md", "0020-b.md"])
        for item in row["landed"]:
            self.assertEqual(item["entries"], 1)
            self.assertTrue(all(n > 0 for n in item["lines"]))

    def test_below_floor_is_re_derived_from_the_one_brief_left(self):
        row = self.row("alpha")
        self.assertIs(row["below_floor"], True)
        self.assertIs(row["below_floor_raw"], False)
        self.assertTrue(row["verdicts_disagree"])

    def test_the_two_depths_and_the_subtraction_are_consistent(self):
        """`consumable + landed == raw` holds by construction, because the
        consumable number is COUNTED over the briefs that survive rather
        than subtracted - a subtraction can go negative from a double count
        and would then need a `max(0, ...)` that hides the arithmetic."""
        row = self.row("alpha")
        self.assertEqual(row["consumable_depth"] + row["landed_count"],
                         row["raw_depth"])

    def test_the_id_is_compared_for_equality_and_not_containment(self):
        """`0234b` is a different brief from `0234`, with its own dispatch
        and its own budget. The comparison is `src.lanerework`'s."""
        self.lane("beta", queued=["0234-a.md", "0234b-b.md"], pid=7171,
                  alive=True, lane_file="# LANE-beta\n\n")
        self.entry("beta", "0234b", "only the b one landed")
        row = self.row("beta")
        self.assertEqual([item["brief"] for item in row["landed"]],
                         ["0234b-b.md"])
        self.assertEqual(row["consumable_depth"], 1)

    def test_a_brief_with_no_task_id_takes_the_lane_to_unknown(self):
        """Not classifiable either way, so it is named rather than quietly
        counted as fresh work."""
        self.lane("gamma", queued=["notes.md"], pid=8181, alive=True,
                  lane_file="# LANE-gamma\n")
        row = self.row("gamma")
        self.assertEqual(row["unnamed_briefs"], ["notes.md"])
        self.assertIn(qd.U_BRIEF_ID, row["unknown_because"])
        self.assertIsNone(row["consumable_depth"])
        self.assertIsNone(row["below_floor"])

    def test_an_empty_lane_file_is_an_answer_and_lands_nothing(self):
        """It exists and says nothing, which is an authority answering. That
        is NOT the same as an absent one, and `src.lanerework` keeps the two
        apart for exactly this reason."""
        self.lane("delta", queued=["0010-a.md"], pid=9191, alive=True,
                  lane_file="")
        row = self.row("delta")
        self.assertEqual(row["lane_file_state"], lanes.EMPTY)
        self.assertEqual(row["landed_count"], 0)
        self.assertEqual(row["consumable_depth"], 1)


# --------------------------------------------------------------------------
# C4 - the brief locked in RUNNING\ behind a dead watcher. Neither queued
# nor running, and nothing here clears it.
# --------------------------------------------------------------------------

class C4LockedInRunningIsItsOwnState(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.lane("qwen", queued=["0171-a.md", "0175-b.md"],
                  running=["0170-the-two-free-suite-lock-wins.md"],
                  log=[up("qwen"), done("qwen", "00:58:48", "0160-x.md"),
                       start("qwen", "00:58:53",
                             "0170-the-two-free-suite-lock-wins.md")],
                  pid=66028, alive=False, lane_file="# LANE-qwen\n")

    def test_the_locked_brief_is_named_under_its_own_heading(self):
        row = self.row("qwen")
        self.assertEqual(row["locked"],
                         ["0170-the-two-free-suite-lock-wins.md"])
        self.assertEqual(row["locked_count"], 1)

    def test_it_is_not_counted_as_queued(self):
        """`RUNNING\\` is a subdirectory and was never in the file count.
        Folding it in would overstate the depth of the one lane whose depth
        is already the most misleading on the board."""
        row = self.row("qwen")
        self.assertEqual(row["raw_depth"], 2)
        self.assertEqual(row["consumable_depth"], 0)

    def test_it_is_not_counted_as_running(self):
        self.assertEqual(self.row("qwen")["running"], [])

    def test_the_lane_is_stranded_and_the_brief_is_reported_estate_wide(self):
        data = self.data()
        self.assertEqual(data["locked_briefs"],
                         [{"lane": "qwen",
                           "brief": "0170-the-two-free-suite-lock-wins.md"}])
        self.assertEqual(data["stranded_lanes"], ["qwen"])

    def test_the_same_brief_under_a_live_watcher_is_simply_running(self):
        """The distinction is the watcher, not the folder. A brief in
        `RUNNING\\` with a live watcher is a task doing its work."""
        self.lane("webapp", queued=["0180-a.md"], running=["0170-b.md"],
                  log=[up("webapp"), start("webapp", "07:47:38", "0170-b.md")],
                  pid=31148, alive=True, child=True,
                  lane_file="# LANE-webapp\n")
        row = self.row("webapp")
        self.assertEqual(row["running"], ["0170-b.md"])
        self.assertEqual(row["locked"], [])
        self.assertEqual(row["locked_count"], 0)

    def test_liveness_unknown_places_it_in_neither(self):
        """Not locked, not running, and not folded into whichever came
        first. The brief says it is its own thing; an unanswered liveness
        makes it an unplaced one."""
        self.lane("mu", queued=["0010-a.md"], running=["0005-x.md"],
                  log=[up("mu"), start("mu", "07:00:00", "0005-x.md")],
                  pid=None, lane_file="# LANE-mu\n")
        row = self.row("mu")
        self.assertEqual(row["watcher"], qd.W_UNKNOWN)
        self.assertEqual(row["locked"], [])
        self.assertEqual(row["running"], [])
        self.assertEqual(row["inflight_unplaced"], ["0005-x.md"])

    def test_nothing_in_running_was_touched(self):
        """Read-only, asserted on the directory rather than claimed in a
        docstring: the brief forbids clearing a `RUNNING\\` entry and this
        module must not even rename one."""
        path = os.path.join(self.root, "queue", "qwen", "RUNNING")
        before = sorted(os.listdir(path))
        self.data()
        self.assertEqual(sorted(os.listdir(path)), before)


# --------------------------------------------------------------------------
# C5 - FAIL-CLOSED. The control for the defect that cost this estate most on
# 2026-10-15: an unknown reported as the nearest available name.
# --------------------------------------------------------------------------

class C5AnUnknownNeverBecomesTheRawNumber(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.lane("alpha", queued=["0010-a.md", "0020-b.md", "0030-c.md",
                                   "0040-d.md"],
                  pid=4242, alive=True, unreadable_lane_file=True)

    def test_the_lane_file_reads_unreadable(self):
        self.assertEqual(self.row("alpha")["lane_file_state"],
                         lanes.UNREADABLE)

    def test_the_landed_count_is_unknown_and_not_zero(self):
        """Zero would mean the authority answered. It could not be opened."""
        self.assertIsNone(self.row("alpha")["landed_count"])

    def test_the_consumable_depth_is_unknown(self):
        row = self.row("alpha")
        self.assertIsNone(row["consumable_depth"])
        self.assertFalse(row["consumable_known"])

    def test_it_does_not_fall_back_on_the_raw_depth(self):
        """FOUR WOULD BE THE NEAREST AVAILABLE NAME and it is the one answer
        this control exists to forbid: with the lane file unopenable, four
        consumable briefs is a guess that reads as a measurement."""
        row = self.row("alpha")
        self.assertNotEqual(row["consumable_depth"], row["raw_depth"])
        self.assertIsNone(row["consumable_depth"])

    def test_below_floor_is_unknown_too(self):
        """Not the raw verdict, and not 'assume consumable'. `0110` set this
        discipline for `below_floor` and it is kept."""
        row = self.row("alpha")
        self.assertIsNone(row["below_floor"])
        self.assertIs(row["below_floor_raw"], False)
        self.assertFalse(row["verdicts_disagree"],
                         "an UNKNOWN beside a False is an absence, not a "
                         "disagreement")

    def test_the_reason_is_named_with_its_repair(self):
        row = self.row("alpha")
        self.assertEqual(row["unknown_because"], [qd.U_LANE_FILE])
        self.assertIn("absent authority does not clear",
                      qd.UNKNOWN_TEXT[qd.U_LANE_FILE])

    def test_the_state_is_unknown_and_not_ok(self):
        row = self.row("alpha")
        self.assertEqual(row["state"], qd.S_UNKNOWN)
        self.assertNotEqual(row["state"], qd.S_OK)

    def test_an_absent_lane_file_is_unknown_as_well(self):
        """`src.lanerework`'s own rule: a lane file that is not there cannot
        answer "did an entry exist", and reading its absence as "no entry
        existed" would hand every brief a clean verdict off a missing
        authority."""
        self.lane("beta", queued=["0010-a.md"], pid=7171, alive=True,
                  no_lane_file=True)
        row = self.row("beta")
        self.assertEqual(row["lane_file_state"], lanes.ABSENT)
        self.assertIsNone(row["consumable_depth"])
        self.assertIsNone(row["below_floor"])

    def test_an_unreadable_queue_folder_is_unknown_in_both_depths(self):
        """An unreadable queue is not an empty one, and the RAW number is
        UNKNOWN there too - this is the one case where the raw column has no
        number to show."""
        self.lane("gamma", queued=[], pid=8181, alive=True,
                  lane_file="# LANE-gamma\n")
        shutil.rmtree(os.path.join(self.root, "queue", "gamma"))
        self._write(os.path.join(self.root, "queue", "gamma"), "not a dir\n")
        row = self.row("gamma")
        self.assertEqual(row["queue_state"], lanes.UNREADABLE)
        self.assertIsNone(row["raw_depth"])
        self.assertIsNone(row["consumable_depth"])
        self.assertIn(qd.U_QUEUE, row["unknown_because"])

    def test_an_unreadable_process_table_is_unknown_and_not_an_alarm(self):
        """UNKNOWN liveness produces neither STRANDED nor a pass. The table
        could not be read; nothing about the watcher was established."""
        self.has_table = False
        row = self.row("alpha")
        self.assertEqual(row["watcher"], qd.W_UNKNOWN)
        self.assertIn(qd.U_WATCHER, row["unknown_because"])
        self.assertIsNone(row["consumable_depth"])
        self.assertNotEqual(row["state"], qd.S_STRANDED)

    def test_an_absent_pid_file_is_ambiguous_rather_than_dead(self):
        """`_read_pid_file`'s own documentation: the watcher removes it on a
        clean exit and a hard kill leaves it behind. With no `watcher down.`
        line to settle it, that is UNKNOWN - never dead, never alive."""
        self.lane("delta", queued=["0010-a.md"], pid=None,
                  lane_file="# LANE-delta\n")
        row = self.row("delta")
        self.assertEqual(row["watcher"], qd.W_UNKNOWN)
        self.assertIsNone(row["consumable_depth"])

    def test_an_unknown_floor_yields_no_breach_verdict(self):
        """A breach is a comparison and a comparison needs both sides. 3 is
        NOT assumed - the floor is the operator's, from his own file."""
        self.readme(None)
        row = self.row("alpha")
        self.assertIsNone(row["floor"])
        self.assertIsNone(row["below_floor"])

    def test_an_unknown_lane_is_in_neither_total(self):
        """Summed in as zero it would make the estate total a different
        question, and summed in as its raw depth it would be the fallback
        this whole class forbids."""
        self.lane("beta", queued=["0010-a.md", "0020-b.md"], pid=7171,
                  alive=True, lane_file="# nothing\n")
        data = self.data()
        self.assertEqual(data["unknown_lanes"], ["alpha"])
        self.assertEqual(data["consumable_total"], 2)
        self.assertEqual(data["consumable_lanes"], 1)
        self.assertEqual(data["lane_count"], 2)
        self.assertFalse(data["consumable_complete"])


# --------------------------------------------------------------------------
# Starvation is not stranding. Two emergencies, two owners, and this estate
# has recorded the cost of merging them.
# --------------------------------------------------------------------------

class CStarvationIsNotStranding(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        # Live watcher, nothing queued: it will take a brief and has none.
        self.lane("live", queued=[], pid=1111, alive=True,
                  lane_file="# LANE-live\n")
        # Dead watcher, four queued: the work exists and cannot start.
        self.lane("dead", queued=["0010-a.md", "0020-b.md", "0030-c.md",
                                  "0040-d.md"],
                  pid=2222, alive=False, lane_file="# LANE-dead\n")

    def test_both_read_consumable_zero(self):
        self.assertEqual(self.row("live")["consumable_depth"], 0)
        self.assertEqual(self.row("dead")["consumable_depth"], 0)

    def test_and_they_are_different_states(self):
        self.assertEqual(self.row("live")["state"], qd.S_STARVED)
        self.assertEqual(self.row("dead")["state"], qd.S_STRANDED)
        self.assertNotEqual(self.row("live")["state"],
                            self.row("dead")["state"])

    def test_the_estate_lists_them_separately(self):
        data = self.data()
        self.assertEqual(data["starved_lanes"], ["live"])
        self.assertEqual(data["stranded_lanes"], ["dead"])

    def test_the_repairs_published_for_the_two_are_different(self):
        """The words travel with the data, and they name different owners:
        one needs a brief written, the other needs a watcher restarted."""
        self.assertIn("WRITE A BRIEF", qd.STATE_TEXT[qd.S_STARVED][1])
        self.assertIn("RESTART THE WATCHER", qd.STATE_TEXT[qd.S_STRANDED][1])

    def test_the_page_prints_them_as_two_alarms(self):
        html = self.rendered()
        self.assertIn("STRANDED", html)
        self.assertIn("STARVED", html)
        self.assertIn("writing another brief would change nothing", html)


# --------------------------------------------------------------------------
# The panel. A figure computed correctly that nothing renders is this
# repository's named defect, so every number above is asserted on the HTML.
# --------------------------------------------------------------------------

class CRenderBothNumbers(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.lane("dead", queued=["0010-a.md", "0020-b.md", "0030-c.md",
                                  "0040-d.md", "0050-e.md"],
                  pid=2222, alive=False, lane_file="# LANE-dead\n")
        self.lane("unknown", queued=["0010-a.md", "0020-b.md"], pid=3333,
                  alive=True, unreadable_lane_file=True)

    def test_the_raw_depth_is_still_on_the_page(self):
        """The sixteen stranded briefs must not vanish because they cannot
        start. The raw column is the measure of what is waiting."""
        html = self.rendered()
        self.assertIn("raw", html)
        self.assertIn(">5<", html)

    def test_both_columns_exist_and_are_labelled(self):
        html = self.rendered()
        self.assertIn("below floor (consumable)", html)
        self.assertIn("below floor (raw)", html)

    def test_an_unknown_renders_as_unknown_and_never_as_zero(self):
        html = self.rendered()
        self.assertIn("UNKNOWN", html)
        self.assertIn("WHY UNKNOWN", html)

    def test_the_unknown_names_the_authority_that_was_missing(self):
        html = self.rendered()
        self.assertIn("LANE-&lt;lane&gt;.md", html)

    def test_the_consumable_floor_cell_is_unknown_and_never_a_no(self):
        """WRITTEN BECAUSE A MUTATION SURVIVED. `M8` makes `below_floor`
        fall back on the raw verdict when the consumable depth is UNKNOWN,
        and every test that saw it worked on the data. On the PAGE the
        consumable cell would still have said UNKNOWN while the floor cell
        beside it printed a clean verdict off an authority nobody opened -
        a row contradicting itself, which is the render half of the defect
        and was observed by nothing.

        The two cells asserted here are, in order, `below floor
        (consumable)` and `below floor (raw)` for the lane whose lane file
        could not be read: UNKNOWN, then the raw count's own BELOW."""
        html = self.rendered()
        self.assertIn("<td>%s</td><td>%s</td>" % (pages._floor_cell(None),
                                                  pages._floor_cell(True)),
                      html)

    def test_the_disagreement_is_stated_rather_than_left_to_be_spotted(self):
        html = self.rendered()
        self.assertIn("THE TWO VERDICTS DISAGREE", html)
        self.assertIn("read these lanes as compliant", html)

    def test_the_denominator_is_printed_with_every_total(self):
        html = self.rendered()
        self.assertIn("Raw depth totals 7 across 2 of 2 lanes", html)
        self.assertIn("consumable 0 across 1 of 2", html)

    def test_the_floor_sentence_is_named_as_the_operators_and_unchanged(self):
        html = self.rendered()
        self.assertIn("queue/README.md", html)
        self.assertIn("NOT THIS PANEL", html)

    def test_an_unconfigured_estate_does_not_render_an_empty_table(self):
        data = {"state": "unconfigured", "variable": lanes.OPS_DIR}
        html = pages.queue_depth(data)
        self.assertIn("absence of an answer", html)
        self.assertNotIn("<tbody>", html)

    def test_the_page_is_reachable_from_the_lane_board_route(self):
        """A panel nothing renders is the defect, so the composition itself
        is asserted: `/admin/lanes` holds this panel's own heading."""
        import inspect
        source = inspect.getsource(api)
        self.assertIn("def queue_depth(", source)
        from src.web import app
        self.assertIn("pages.queue_depth(api.queue_depth(board=board))",
                      inspect.getsource(app))


# --------------------------------------------------------------------------
# One board, read once. Two readings of one process table is how two numbers
# on one page disagree - which is the defect this panel exists for.
# --------------------------------------------------------------------------

class COneBoardReadOnce(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.lane("alpha", queued=["0010-a.md"], pid=4242, alive=True,
                  lane_file="# LANE-alpha\n")

    def test_a_supplied_board_is_used_and_no_second_one_is_read(self):
        board = lanes.board(root=self.root, now=NOW, probe=self.probe(),
                            samples={})

        class Exploding:
            def table(self):
                raise AssertionError("the process table was read twice")

            def cpu(self, pid):
                raise AssertionError("the process table was read twice")

        data = qd.consumable(board_data=board, probe=Exploding())
        self.assertEqual(data["lanes"][0]["raw_depth"], 1)

    def test_the_raw_depth_and_the_names_are_one_listing(self):
        """`queue_depth` is the length of `queued` on the same row, so a
        count and a name-set on one page cannot be two readings of one
        folder."""
        board = lanes.board(root=self.root, now=NOW, probe=self.probe(),
                            samples={})
        for row in board["lanes"]:
            if row["queue_state"] == lanes.PRESENT:
                self.assertEqual(row["queue_depth"], len(row["queued"]))

    def test_the_floor_comes_from_the_board_and_is_not_re_read(self):
        board = lanes.board(root=self.root, now=NOW, probe=self.probe(),
                            samples={})
        board["floor"] = 99
        data = qd.consumable(board_data=board, probe=self.probe())
        self.assertEqual(data["floor"], 99)
        self.assertIs(data["lanes"][0]["below_floor"], True)


# --------------------------------------------------------------------------
# Read-only, proven on the fixture estate by a before/after walk. The live
# estate is proven by `scripts/depth_panel.py`'s write trap, which raises.
# --------------------------------------------------------------------------

class CReadOnly(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.lane("alpha", queued=["0010-a.md", "0020-b.md"],
                  running=["0005-x.md"], pid=4242, alive=False,
                  lane_file="# LANE-alpha\n\n")
        self.entry("alpha", "0010")

    def walk(self):
        found = {}
        for base, dirs, files in os.walk(self.root):
            dirs.sort()
            for name in sorted(files):
                path = os.path.join(base, name)
                info = os.stat(path)
                with open(path, "rb") as handle:
                    found[os.path.relpath(path, self.root)] = (
                        info.st_size, handle.read())
        return found

    def test_the_walk_is_identical_before_and_after(self):
        before = self.walk()
        self.data()
        self.rendered()
        self.assertEqual(self.walk(), before)

    def test_the_module_writes_through_no_entry_point(self):
        """Asserted on the import graph and on the source's calls rather
        than on words in a docstring. A reader that writes is not read-only
        however carefully it says it is."""
        import src.queuedepth as module
        import inspect
        source = inspect.getsource(module)
        for forbidden in ("open(", "os.remove", "os.rename", "os.replace",
                          "os.mkdir", "os.makedirs", "shutil.",
                          "subprocess."):
            self.assertNotIn(forbidden, source,
                             "%r appears in src/queuedepth.py" % forbidden)

    def test_no_ledger_is_appended_to(self):
        """`0130` appended no row to the ledger it was measuring. This panel
        does not reach the ledger at all, which is the stronger statement."""
        import src.queuedepth as module
        import inspect
        self.assertNotIn("floorledger", inspect.getsource(module))


# --------------------------------------------------------------------------
# C7 - tonight, replayed. Four lanes, sixteen briefs, no watcher; pilotcaps
# at the floor with two of three already landed; qwen with 0170 locked.
# --------------------------------------------------------------------------

#: The real 05:46 state, from the real logs and the real queue folders. The
#: brief counts are the real ones and they sum to sixteen.
TONIGHT = (
    # lane, queued briefs, how its watcher died, when
    ("glm", ["0067b-save-sweep.md",
             "0072-the-two-prospect-facing-bypasses.md",
             "0073-the-zero-that-means-unknown.md"], "01:48:09"),
    ("glm-b", ["0170-the-twenty-four-scoped-by-file.md",
               "0180-the-vertical-slot.md",
               "0190-finish-0170.md"], "01:46:23"),
    ("glm-c", ["0161-save-sweep.md",
               "0220-the-remaining-bypasses-tiered.md",
               "0230-the-ledger-row-with-no-step.md",
               "0240-the-attach-that-never-passes-the-door.md"], "01:48:09"),
)


class C7TonightReplayed(Estate, unittest.TestCase):

    def setUp(self):
        super().setUp()
        for lane, briefs, clock in TONIGHT:
            # No pid file - all three watchers were gone without one - and a
            # log whose last two records are the failure guard and
            # `watcher down.`.
            self.lane(lane, queued=briefs, pid=None,
                      log=[up(lane), start(lane, "01:00:00", "a.md"),
                           done(lane, "01:40:00", "a.md", "exit1"),
                           guard(lane, clock), down(lane, clock)],
                      lane_file="# LANE-%s\n\n" % lane)
        # `qwen`: pid file naming a process the table does not hold, an open
        # START from 00:58:53, and `0170` still in RUNNING\.
        self.lane("qwen",
                  queued=["0171-did-an-orphan-finish-0170.md",
                          "0175-the-refusal-that-eats-a-brief.md",
                          "0180-rotate-a-lane-without-killing-it.md",
                          "0190-verify-the-boundary-then-close-the-push-"
                          "hole.md",
                          "0200-the-orphaned-running-brief.md",
                          "0210-the-launcher-counts-failures-as-starts.md"],
                  running=["0170-the-two-free-suite-lock-wins.md"],
                  log=[up("qwen"), done("qwen", "00:58:48", "0160-x.md"),
                       start("qwen", "00:58:53",
                             "0170-the-two-free-suite-lock-wins.md")],
                  pid=66028, alive=False, lane_file="# LANE-qwen\n\n")
        # `pilotcaps`: live watcher, depth 3, and 0234 and 0235 already have
        # entries - 05:43:22's report, verbatim: "0234 and 0235 already have
        # entries at lines 10937 and 8673 - no unstarted brief exists".
        self.lane("pilotcaps",
                  queued=["0233-a.md", "0234-b.md", "0235-c.md"],
                  log=[up("pilotcaps"),
                       start("pilotcaps", "07:30:00", "0232-x.md"),
                       done("pilotcaps", "07:32:45", "0232-x.md")],
                  pid=78160, alive=True, lane_file="# LANE-pilotcaps\n\n")
        self.entry("pilotcaps", "0234", "already done")
        self.entry("pilotcaps", "0235", "already done")
        self.entry("pilotcaps", "0233", "already done")

    def test_the_sixteen_stranded_briefs_are_counted(self):
        """3 + 3 + 4 + 6. The headline number of the whole panel."""
        self.assertEqual(self.data()["stranded_briefs"], 16)

    def test_every_one_of_the_four_reads_consumable_zero(self):
        for lane in ("glm", "glm-b", "glm-c", "qwen"):
            row = self.row(lane)
            self.assertEqual(row["consumable_depth"], 0, lane)
            self.assertEqual(row["watcher"], qd.W_DEAD, lane)

    def test_not_one_of_the_four_renders_as_healthy(self):
        """THE FINDING, STATED AS AN ASSERTION. If any of them came back OK
        this panel would be the instrument the board already was."""
        for lane in ("glm", "glm-b", "glm-c", "qwen"):
            row = self.row(lane)
            self.assertEqual(row["state"], qd.S_STRANDED, lane)
            self.assertIs(row["below_floor"], True, lane)

    def test_the_raw_verdict_called_all_four_compliant(self):
        """What the floor was being enforced against, and why three hourly
        runs had to decline to top these lanes up by hand."""
        for lane in ("glm", "glm-b", "glm-c", "qwen"):
            self.assertIs(self.row(lane)["below_floor_raw"], False, lane)
        # FIVE, not four: `pilotcaps` disagrees too, by the other
        # subtraction. Its file count is 3 and its consumable depth is 0, so
        # the raw verdict called it compliant for a different reason - which
        # is the second direction the floor was wrong in tonight.
        self.assertEqual(sorted(self.data()["disagreeing_lanes"]),
                         ["glm", "glm-b", "glm-c", "pilotcaps", "qwen"])

    def test_the_raw_depths_are_all_still_rendered(self):
        for lane, briefs, _clock in TONIGHT:
            self.assertEqual(self.row(lane)["raw_depth"], len(briefs), lane)
        self.assertEqual(self.row("qwen")["raw_depth"], 6)

    def test_pilotcaps_sat_at_the_floor_with_nothing_to_do(self):
        """Depth 3 with every brief already recorded as landed. By file
        count it was compliant; it had no unstarted brief at all."""
        row = self.row("pilotcaps")
        self.assertEqual(row["raw_depth"], 3)
        self.assertEqual(row["landed_count"], 3)
        self.assertEqual(row["consumable_depth"], 0)
        self.assertIs(row["below_floor_raw"], False)
        self.assertIs(row["below_floor"], True)

    def test_pilotcaps_is_starved_and_not_stranded(self):
        """Its watcher is alive, so the repair is a brief and not a restart.
        This is the pair of states the panel must not merge."""
        self.assertEqual(self.row("pilotcaps")["state"], qd.S_STARVED)
        self.assertEqual(self.data()["starved_lanes"], ["pilotcaps"])

    def test_qwens_locked_brief_is_named_and_counted_nowhere_else(self):
        row = self.row("qwen")
        self.assertEqual(row["locked"],
                         ["0170-the-two-free-suite-lock-wins.md"])
        self.assertEqual(row["raw_depth"], 6)
        self.assertEqual(row["running"], [])

    def test_the_estate_totals_name_both_numbers(self):
        data = self.data()
        self.assertEqual(data["raw_total"], 19)
        self.assertEqual(data["consumable_total"], 0)
        self.assertEqual(data["unknown_lanes"], [])
        self.assertTrue(data["consumable_complete"])

    def test_the_whole_estate_renders_without_one_healthy_lane(self):
        html = self.rendered()
        self.assertIn("STRANDED", html)
        self.assertIn("STARVED", html)
        self.assertIn("0170-the-two-free-suite-lock-wins.md", html)
        for lane in ("glm", "glm-b", "glm-c", "qwen", "pilotcaps"):
            self.assertIn(lane, html)


class CTheKillSetCanNameOneControl(unittest.TestCase):
    """No two tests in this file share a method name.

    WRITTEN BECAUSE IT HAPPENED. `test_below_floor_is_re_derived_as_a_breach`
    was defined in both `C2` and `C3` on the first mutation run, and the
    kill-set - which is reported by METHOD name, because that is what the
    standing rule's name-set diff compares - could then not say which
    control had observed the mutation. A kill-set that names two controls
    at once is not a measurement of either.
    """

    def test_every_test_name_in_this_file_is_unique(self):
        import re
        path = os.path.abspath(__file__)
        with open(path, encoding="utf-8") as handle:
            names = re.findall(r"^    def (test_\w+)", handle.read(),
                               re.MULTILINE)
        duplicates = sorted({n for n in names if names.count(n) > 1})
        self.assertEqual(duplicates, [], "these names are defined twice, so "
                                         "a kill-set naming them cannot say "
                                         "which control was observed")


if __name__ == "__main__":                                  # pragma: no cover
    unittest.main()
