"""The lane board, and the three authorities that read healthy while broken.

WHAT THIS FILE IS FOR. On 2026-10-15 the operator asked four times whether the
lane workers were running. Every honest answer needed a shell, because each of
the three authorities a person reaches for is wrong in a different direction:

    the task's `.out` file   0 bytes until the task ENDS, so a lane that is
                             working looks dead. The webapp lane's own 0030
                             run proved it over thirty minutes
    the `DONE/` folder       wrong in BOTH directions - a task has finished
                             with no DONE record, and a file has been moved
                             in by hand under a name no watcher writes
    a queue listing          says nothing about what is in flight

The invariant under test is NOT "the page exists" and NOT the text of any
docstring - a test that greps source fails when somebody writes a comment,
which is this repository's own named anti-pattern. It is the behaviour:

    an absence is reported as an absence, and UNKNOWN never becomes idle,
    zero or ok;

    the two authorities that ARE sound - the watcher's own log line, and
    whether anything is alive under that lane's watcher - are CROSSED, and
    neither is allowed to overrule the other, because each one reads
    perfectly healthy in a state the other calls broken;

    a DONE suffix is never flattened: `exit0`, `NOWORK` and `TIMEOUT` are
    three different outcomes and two of them need a person.

NOTHING HERE REACHES A PROVIDER, A NETWORK OR A REAL LANE. Every estate in
this file is a directory this test writes into a temporary folder, and every
process table is a dict this test hands to the reader. One test patches
`socket.socket` to raise and then calls the reader, so "it opens no socket" is
a measurement rather than a claim. The only socket in play is the loopback
listener `tests/webbase.WebTest` owns, on an ephemeral port - never 8765-8799.
"""
import os
import shutil
import socket
import tempfile
import types
import unittest
import datetime

from src import lanes
from src.web import api, pages
from src.web.app import permission_for
from src.web.security import esc
from tests.webbase import WebTest

PATH = "/admin/lanes"
SUPER = "root@resonate.test"
ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"

NOW = datetime.datetime(2026, 10, 15, 23, 30, 0)


def line(lane, clock, message):
    """One watcher record, in the exact shape `lane_watcher.ps1` writes.

    `[2026-10-15 23:04:00] [webapp] START 0040.md`. Written here rather than
    imported, so that a change to the watcher's format shows up as a failure
    in this file instead of as a board that quietly reads every lane UNKNOWN.
    """
    return "[2026-10-15 %s] [%s] %s" % (clock, lane, message)


class FakeProbe:
    """A process table and a CPU clock, supplied rather than measured.

    `table=None` is the real refusal: the table could not be read, which must
    make every liveness answer UNKNOWN rather than zero.
    """

    def __init__(self, table=None, cpu=None, unreadable_table=False):
        self._table = None if unreadable_table else (table or {})
        self._cpu = cpu or {}

    def table(self):
        return self._table

    def cpu(self, pid):
        return self._cpu.get(pid)


class Estate:
    """A disposable lane estate: `queue/<lane>/`, `logs/`, `LANE-<lane>.md`."""

    def an_estate(self):
        root = tempfile.mkdtemp(prefix="rga-lanes-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        os.makedirs(os.path.join(root, "queue"))
        os.makedirs(os.path.join(root, "logs"))
        self.root = root
        return root

    def a_lane(self, name, log=None, pid=None, queued=(), inflight=(),
               lane_file=None, done=(), out_bytes=None, no_queue_dir=False,
               unreadable_log=False, unreadable_queue=False):
        root = self.root
        if not no_queue_dir:
            queue = os.path.join(root, "queue", name)
            os.makedirs(os.path.join(queue, "RUNNING"), exist_ok=True)
            os.makedirs(os.path.join(queue, "DONE"), exist_ok=True)
            for brief in queued:
                self._write(os.path.join(queue, brief), "brief\n")
            for brief in inflight:
                self._write(os.path.join(queue, "RUNNING", brief), "brief\n")
            # Stuffed deliberately. The board must not read it: this folder's
            # count is the authority that is wrong in both directions.
            for brief in done:
                self._write(os.path.join(queue, "DONE", brief), "brief\n")
            if unreadable_queue:
                shutil.rmtree(queue)
                # A file where the folder should be: it exists, so the absent
                # branch is not taken, and listing it raises on every
                # platform this runs on.
                self._write(queue, "not a directory\n")
        log_path = os.path.join(root, "logs", "watcher-%s.log" % name)
        if unreadable_log:
            # A directory, which is the portable way to make a path that
            # exists and cannot be read.
            os.makedirs(log_path, exist_ok=True)
        elif log is not None:
            self._write(log_path, "\n".join(log) + "\n")
        if pid is not None:
            self._write(os.path.join(root, "logs", "watcher-%s.pid" % name),
                        "%d\n" % pid)
        if lane_file is not None:
            self._write(os.path.join(root, "LANE-%s.md" % name), lane_file)
        if out_bytes is not None:
            self._write(
                os.path.join(root, "logs", "task-%s-20261015-230000.out"
                             % name), "x" * out_bytes)

    @staticmethod
    def _write(path, text):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def board(self, probe=None, now=NOW, samples=None):
        return lanes.board(root=self.root, now=now,
                           probe=probe or FakeProbe({1: (0, "powershell.exe")}),
                           samples={} if samples is None else samples)

    def row(self, lane, **kwargs):
        rows = {r["lane"]: r for r in self.board(**kwargs)["lanes"]}
        self.assertIn(lane, rows, "the estate did not produce a row for %r"
                                  % lane)
        return rows[lane]


# --------------------------------------------------------------------------
# AN ABSENCE IS AN ABSENCE


class AnAbsenceIsNeverIdleAndNeverZero(unittest.TestCase, Estate):
    """The rule that has cost this estate three findings in one day."""

    def test_an_unset_variable_is_UNCONFIGURED_and_not_an_empty_board(self):
        previous = os.environ.pop(lanes.OPS_DIR, None)
        self.addCleanup(
            lambda: os.environ.__setitem__(lanes.OPS_DIR, previous)
            if previous is not None else None)
        data = lanes.board(probe=FakeProbe())
        self.assertEqual(data["state"], lanes.UNCONFIGURED)
        self.assertEqual(data["lanes"], [])
        body = pages.lane_board(api.lane_board(probe=FakeProbe(), samples={}))
        self.assertIn("Not configured", body)
        self.assertIn(lanes.OPS_DIR, body)
        # The distinction IS the point. It must not read as an estate with
        # nothing in it, nor as an estate that is resting.
        self.assertNotIn("IDLE", body)
        self.assertNotIn("RUNNING", body)

    def test_a_root_that_is_not_a_directory_is_ABSENT(self):
        data = lanes.board(root=os.path.join(tempfile.mkdtemp(), "nope"),
                           probe=FakeProbe())
        self.assertEqual(data["state"], lanes.ABSENT)
        self.assertEqual(data["lanes"], [])

    def test_a_blank_variable_counts_as_unset(self):
        previous = os.environ.get(lanes.OPS_DIR)
        os.environ[lanes.OPS_DIR] = "   "
        self.addCleanup(self._restore, previous)
        self.assertIsNone(lanes.ops_root())

    def test_a_missing_watcher_log_is_UNKNOWN_and_not_idle(self):
        self.an_estate()
        self.a_lane("alpha", log=None, pid=1)
        row = self.row("alpha")
        self.assertEqual(row["log_state"], lanes.ABSENT)
        self.assertEqual(row["status"], lanes.UNKNOWN)
        self.assertEqual(row["verdict"], lanes.V_UNKNOWN)
        self.assertIsNone(row["since_seconds"])

    def test_an_unreadable_watcher_log_is_UNKNOWN_and_not_idle(self):
        self.an_estate()
        self.a_lane("alpha", pid=1, unreadable_log=True)
        row = self.row("alpha")
        self.assertEqual(row["log_state"], lanes.UNREADABLE)
        self.assertEqual(row["verdict"], lanes.V_UNKNOWN)

    def test_a_readable_log_with_no_START_is_NEVER_RAN_and_not_idle(self):
        self.an_estate()
        self.a_lane("alpha", pid=1, log=[line("alpha", "22:00:00",
                                              "watcher up. tree=x")])
        row = self.row("alpha")
        self.assertEqual(row["status"], lanes.NEVER_RAN)
        self.assertEqual(row["verdict"], lanes.V_NEVER_RAN)

    def test_a_queue_folder_that_cannot_be_read_is_UNKNOWN_not_zero(self):
        self.an_estate()
        self.a_lane("alpha", pid=1, unreadable_queue=True,
                    log=[line("alpha", "23:00:00", "START a.md")])
        row = self.row("alpha")
        self.assertEqual(row["queue_state"], lanes.UNREADABLE)
        self.assertIsNone(row["queue_depth"], "a depth nobody read is not 0")

    def test_an_unreadable_depth_is_excluded_from_the_total_and_counted(self):
        self.an_estate()
        self.a_lane("alpha", pid=1, unreadable_queue=True,
                    log=[line("alpha", "23:00:00", "START a.md")])
        self.a_lane("beta", pid=1, queued=["1.md", "2.md"],
                    log=[line("beta", "23:00:00", "START a.md")])
        data = self._board_through_api()
        self.assertEqual(data["queued_total"], 2)
        self.assertEqual(data["queue_unreadable"], 1)

    def test_an_unreadable_process_table_makes_every_verdict_UNCROSSED(self):
        self.an_estate()
        self.a_lane("alpha", pid=1,
                    log=[line("alpha", "23:00:00", "START a.md")])
        data = self.board(probe=FakeProbe(unreadable_table=True))
        self.assertIs(data["table_read"], False)
        row = data["lanes"][0]
        self.assertEqual(row["verdict"], lanes.V_UNCROSSED)
        # The log's own answer survives next to it. Losing it would be the
        # opposite error: discarding the authority that did answer.
        self.assertEqual(row["status"], lanes.RUNNING)
        self.assertIsNone(row["cpu"]["seconds"])

    def _board_through_api(self):
        os.environ[lanes.OPS_DIR] = self.root
        self.addCleanup(os.environ.pop, lanes.OPS_DIR, None)
        return api.lane_board(now=NOW, samples={},
                              probe=FakeProbe({1: (0, "powershell.exe")}))

    def _restore(self, previous):
        if previous is None:
            os.environ.pop(lanes.OPS_DIR, None)
        else:
            os.environ[lanes.OPS_DIR] = previous


# --------------------------------------------------------------------------
# THE TWO AUTHORITIES, CROSSED


class TheTwoAuthoritiesAreCrossedAndNeitherWins(unittest.TestCase, Estate):
    """Each authority alone reads healthy in a state the other calls broken.

    This is the whole reason the page exists rather than a `ps` alias. A
    watcher log with an open START looks like work in progress whether or not
    anything is alive; a live process under a watcher looks like work whether
    or not its task was ever recorded as finished.
    """

    OPEN = [line("alpha", "22:00:00", "START a.md"),
            line("alpha", "22:30:00", "DONE  a.md -> exit0"),
            line("alpha", "23:00:00", "START b.md")]
    CLOSED = [line("alpha", "22:00:00", "START a.md"),
              line("alpha", "22:30:00", "DONE  a.md -> exit0")]

    def test_an_open_task_with_a_live_process_is_RUNNING(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.OPEN, inflight=["b.md"])
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe"),
                                        11: (10, "cmd.exe")},
                                       cpu={11: 42.0}))
        self.assertEqual(row["verdict"], lanes.V_RUNNING)
        self.assertEqual(row["cpu"]["count"], 1)
        self.assertEqual(row["cpu"]["seconds"], 42.0)
        self.assertEqual(row["since_seconds"], 1800)

    def test_an_open_task_with_nothing_alive_is_STALLED_not_idle(self):
        """The condition two real lanes were in when this page was built.

        Killed at the timeout, no DONE line ever written, brief still in
        RUNNING, watcher gone. The log alone says RUNNING. The process table
        alone says nothing is happening. Neither is the answer.
        """
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.OPEN, inflight=["b.md"],
                    queued=["c.md", "d.md"])
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertEqual(row["verdict"], lanes.V_STALLED)
        self.assertNotEqual(row["verdict"], lanes.V_IDLE)
        self.assertNotEqual(row["verdict"], lanes.V_RUNNING)
        self.assertEqual(row["status"], lanes.RUNNING, "the log still says so")
        # And the cost is visible: two briefs behind a lane that is consuming
        # nothing.
        self.assertEqual(row["queue_depth"], 2)

    def test_a_watcher_whose_pid_is_gone_is_reported_dead_not_idle(self):
        self.an_estate()
        self.a_lane("alpha", pid=999, log=self.OPEN)
        row = self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertIs(row["watcher_alive"], False)
        self.assertEqual(row["verdict"], lanes.V_STALLED)
        self.assertIn("not in the table", row["cpu"]["why"])

    def test_a_closed_task_with_nothing_alive_is_IDLE(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.CLOSED)
        row = self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertEqual(row["verdict"], lanes.V_IDLE)
        self.assertEqual(row["since_seconds"], 3600)

    def test_a_closed_task_with_a_live_process_is_ORPHANED(self):
        """A measured failure in this estate, not a hypothetical one.

        `lane_watcher.ps1` documents it: an orphaned grandchild survived its
        task by 27 minutes, holding the brief open as its inherited stdin.
        """
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.CLOSED)
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe"),
                                        11: (10, "python.exe")},
                                       cpu={11: 5.0}))
        self.assertEqual(row["verdict"], lanes.V_ORPHANED)
        self.assertEqual(row["status"], lanes.IDLE, "the log still says so")

    def test_the_console_host_is_not_a_task_so_an_idle_lane_stays_IDLE(self):
        """The defect that made IDLE unreachable, and it reached the estate.

        MEASURED 2026-10-15 23:36 across all five live watchers: `conhost.exe`
        is a PERMANENT child of every `powershell.exe` watcher, and it was the
        ONLY descendant of the one lane that was between tasks. So `count > 0`
        held for every live watcher, IDLE could never be reached, and that
        lane rendered ORPHANED PROCESS - a verdict about to be written into a
        lane file as a finding about somebody else's lane.
        """
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.CLOSED)
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe"),
                                        11: (10, "conhost.exe")},
                                       cpu={11: 0.015}))
        self.assertEqual(row["cpu"]["count"], 0)
        self.assertEqual(row["verdict"], lanes.V_IDLE)
        self.assertNotEqual(row["verdict"], lanes.V_ORPHANED)

    def test_a_console_host_does_not_hide_a_real_task_beside_it(self):
        """The exclusion must not swallow the task sitting next to it: the
        real shape is `cmd.exe` and `conhost.exe` as siblings."""
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.OPEN)
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe"),
                                        11: (10, "conhost.exe"),
                                        12: (10, "cmd.exe"),
                                        13: (12, "claude.exe")},
                                       cpu={11: 0.01, 12: 1.0, 13: 300.0}))
        self.assertEqual(row["cpu"]["count"], 2)
        self.assertEqual(row["cpu"]["seconds"], 301.0,
                         "the console host's time is not in the figure")
        self.assertEqual(row["verdict"], lanes.V_RUNNING)

    def test_the_walk_passes_THROUGH_an_ignored_image(self):
        """Excluded from the result, not treated as a leaf. Not walking
        through it would be a second assumption about a measured tree."""
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.OPEN)
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe"),
                                        11: (10, "conhost.exe"),
                                        12: (11, "cmd.exe")},
                                       cpu={12: 4.0}))
        self.assertEqual(row["cpu"]["pids"], [12])
        self.assertEqual(row["cpu"]["seconds"], 4.0)

    def test_no_watcher_pid_file_leaves_liveness_UNKNOWN_not_zero(self):
        self.an_estate()
        self.a_lane("alpha", log=self.OPEN)
        row = self.row("alpha")
        self.assertEqual(row["watcher_pid_state"], lanes.ABSENT)
        self.assertIsNone(row["watcher_alive"])
        self.assertIsNone(row["cpu"]["seconds"])
        self.assertEqual(row["verdict"], lanes.V_UNCROSSED)

    def test_a_pid_file_that_is_not_a_number_is_UNREADABLE(self):
        self.an_estate()
        self.a_lane("alpha", log=self.OPEN)
        self._write(os.path.join(self.root, "logs", "watcher-alpha.pid"),
                    "not a pid\n")
        row = self.row("alpha")
        self.assertEqual(row["watcher_pid_state"], lanes.UNREADABLE)
        self.assertIsNone(row["watcher_pid"])

    def test_the_watcher_image_check_is_the_watchers_own(self):
        """A live pid that is not a shell is probably not this lane's watcher.

        `lane_watcher.ps1` refuses to honour a lock whose pid is alive and is
        not a powershell process, for exactly this reason: a pid is reused.
        """
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.OPEN)
        row = self.row("alpha", probe=FakeProbe({10: (1, "notepad.exe")}))
        self.assertIs(row["watcher_image_ok"], False)
        self.assertIs(row["watcher_alive"], True)

    def test_the_root_watcher_is_excluded_from_the_cpu_sum(self):
        """A polling loop accrues CPU forever; including it means nothing."""
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.CLOSED)
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe")},
                                       cpu={10: 9999.0}))
        self.assertEqual(row["cpu"]["count"], 0)
        self.assertEqual(row["cpu"]["seconds"], 0.0)
        self.assertEqual(row["verdict"], lanes.V_IDLE)

    def test_a_descendant_two_levels_down_is_counted(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.OPEN)
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe"),
                                        11: (10, "cmd.exe"),
                                        12: (11, "node.exe")},
                                       cpu={11: 1.0, 12: 2.0}))
        self.assertEqual(row["cpu"]["count"], 2)
        self.assertEqual(row["cpu"]["seconds"], 3.0)

    def test_a_cycle_in_the_table_does_not_hang_the_walk(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.OPEN)
        row = self.row("alpha",
                       probe=FakeProbe({10: (11, "powershell.exe"),
                                        11: (10, "cmd.exe")},
                                       cpu={11: 1.0}))
        self.assertEqual(row["cpu"]["count"], 1)

    @staticmethod
    def _write(path, text):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)


# --------------------------------------------------------------------------
# LIVENESS


class LivenessIsTwoSamplesAndNeverASpinner(unittest.TestCase, Estate):
    """CPU time that moved between two reads. Nothing else qualifies."""

    LOG = [line("alpha", "23:00:00", "START b.md")]

    def test_the_first_look_has_no_delta_and_says_why(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.LOG)
        row = self.row("alpha", probe=self._probe(10.0))
        self.assertEqual(row["cpu"]["seconds"], 10.0)
        self.assertIsNone(row["cpu"]["delta_seconds"], "never a zero")
        self.assertIn("first sample", row["cpu"]["why"])

    def test_the_second_look_produces_the_delta_and_the_wall_time(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.LOG)
        store = {}
        self.row("alpha", probe=self._probe(10.0), samples=store)
        later = NOW + datetime.timedelta(seconds=60)
        row = self.row("alpha", probe=self._probe(14.5), samples=store,
                       now=later)
        self.assertEqual(row["cpu"]["delta_seconds"], 4.5)
        self.assertEqual(row["cpu"]["wall_seconds"], 60)

    def test_a_delta_of_zero_is_reported_as_zero_and_not_as_absent(self):
        """A task waiting on a lock burns no CPU. That is a real zero."""
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.LOG)
        store = {}
        self.row("alpha", probe=self._probe(10.0), samples=store)
        row = self.row("alpha", probe=self._probe(10.0), samples=store,
                       now=NOW + datetime.timedelta(seconds=60))
        self.assertEqual(row["cpu"]["delta_seconds"], 0.0)
        self.assertIsNotNone(row["cpu"]["delta_seconds"])

    def test_two_samples_in_the_same_second_produce_no_delta(self):
        """Found by this module's own tests: one process rendered the page
        twice in the same instant and the row said "+0.0s in 0s", which
        reads as a stall that was never observed. A window of zero cannot
        measure anything, so the delta is UNKNOWN."""
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.LOG)
        store = {}
        self.row("alpha", probe=self._probe(10.0), samples=store)
        row = self.row("alpha", probe=self._probe(10.0), samples=store)
        self.assertIsNone(row["cpu"]["delta_seconds"])
        self.assertIsNone(row["cpu"]["wall_seconds"])
        self.assertIn("same second", row["cpu"]["why"])

    def test_a_sample_that_went_backwards_is_UNKNOWN_with_the_reason(self):
        """Accumulated CPU cannot fall, so the pids are not the same ones."""
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.LOG)
        store = {}
        self.row("alpha", probe=self._probe(100.0), samples=store)
        row = self.row("alpha", probe=self._probe(3.0), samples=store,
                       now=NOW + datetime.timedelta(seconds=60))
        self.assertIsNone(row["cpu"]["delta_seconds"])
        self.assertIn("backwards", row["cpu"]["why"])

    def test_a_process_whose_cpu_cannot_be_read_is_counted_not_zeroed(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.LOG)
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe"),
                                        11: (10, "cmd.exe"),
                                        12: (10, "cmd.exe")},
                                       cpu={11: 7.0}))
        self.assertEqual(row["cpu"]["count"], 2)
        self.assertEqual(row["cpu"]["unmeasured"], [12])
        self.assertEqual(row["cpu"]["seconds"], 7.0)

    def test_when_no_descendant_cpu_can_be_read_the_figure_is_UNKNOWN(self):
        """Not 0.0. Processes are alive and none of them could be measured."""
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.LOG)
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe"),
                                        11: (10, "cmd.exe")}, cpu={}))
        self.assertEqual(row["cpu"]["count"], 1)
        self.assertIsNone(row["cpu"]["seconds"])
        self.assertEqual(row["verdict"], lanes.V_RUNNING,
                         "a process IS alive; only its CPU is unknown")

    def test_samples_for_a_vanished_lane_are_pruned(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.LOG)
        store = {}
        self.row("alpha", probe=self._probe(10.0), samples=store)
        self.assertEqual(len(store), 1)
        os.remove(os.path.join(self.root, "logs", "watcher-alpha.pid"))
        shutil.rmtree(os.path.join(self.root, "queue", "alpha"))
        os.remove(os.path.join(self.root, "logs", "watcher-alpha.log"))
        lanes.board(root=self.root, now=NOW, probe=self._probe(10.0),
                    samples=store)
        self.assertEqual(store, {})

    @staticmethod
    def _probe(seconds):
        return FakeProbe({10: (1, "powershell.exe"), 11: (10, "cmd.exe")},
                         cpu={11: seconds})


# --------------------------------------------------------------------------
# THE LOG IS SHARED WITH PROSE


class TheLogIsSharedWithProseAndStillParses(unittest.TestCase, Estate):
    """The watcher appends each task's whole stdout into the same file.

    No delimiter, so model prose sits between watcher records - and tonight's
    real logs contain lines quoting watcher output back. Anchoring on the full
    `[stamp] [lane] ` prefix AND on the lane tag is what removes it.
    """

    def test_status_comes_from_order_and_not_from_the_last_line(self):
        """A DONE line is followed by the task's own output and more records.

        "the last line mentions DONE" is not the test and never was.
        """
        self.an_estate()
        self.a_lane("alpha", pid=10, log=[
            line("alpha", "22:00:00", "START a.md"),
            line("alpha", "22:30:00", "DONE  a.md -> exit0"),
            line("alpha", "22:30:01", "MOVED a.md -> 1-exit0-a.md"),
            "## some task's own markdown, appended verbatim",
            "it mentions START and DONE and a suffix of exit0",
            line("alpha", "22:35:00", "idle: queue empty, RUNNING empty"),
        ])
        row = self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertEqual(row["status"], lanes.IDLE)
        self.assertEqual(row["last_done_suffix"], "exit0")

    def test_prose_mentioning_START_does_not_become_a_record(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=[
            line("alpha", "22:00:00", "START a.md"),
            line("alpha", "22:30:00", "DONE  a.md -> exit0"),
            "    22:00:18   START of the suite window, per my own notes",
            "START b.md",
        ])
        row = self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertEqual(row["records"], 2)
        self.assertEqual(row["status"], lanes.IDLE)

    def test_a_record_tagged_with_another_lane_is_ignored(self):
        """A lane's log quotes another lane's lines; tonight's logs do."""
        self.an_estate()
        self.a_lane("alpha", pid=10, log=[
            line("alpha", "22:00:00", "START a.md"),
            line("alpha", "22:30:00", "DONE  a.md -> exit0"),
            line("suppression", "23:00:00", "START stolen.md"),
        ])
        row = self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertEqual(row["status"], lanes.IDLE,
                         "another lane's START must not reopen this one")
        self.assertEqual(row["records"], 2)

    def test_a_timeout_with_no_DONE_line_leaves_the_task_open(self):
        """Exactly what two lanes looked like when this page was written."""
        self.an_estate()
        self.a_lane("alpha", pid=10, log=[
            line("alpha", "21:35:10", "START b.md"),
            line("alpha", "23:05:10", "TIMEOUT after 90 minutes, killing it"),
        ])
        row = self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertEqual(row["status"], lanes.RUNNING)
        self.assertEqual(row["verdict"], lanes.V_STALLED)
        self.assertIsNone(row["last_done_line"])
        self.assertEqual(row["last_event_kind"], "timeout_notice")

    def test_the_first_record_is_not_lost_to_a_byte_order_mark(self):
        """MEASURED: all seven real logs begin with a UTF-8 BOM, because
        `Add-Content -Encoding UTF8` under Windows PowerShell 5.1 writes one.
        It sits in front of the first record's `[`, so an anchored parser
        skips line 1 - and after a rotation that line is a START."""
        self.an_estate()
        self.a_lane("alpha", pid=10)
        with open(os.path.join(self.root, "logs", "watcher-alpha.log"), "w",
                  encoding="utf-8-sig", newline="\n") as handle:
            handle.write(line("alpha", "23:00:00", "START b.md") + "\n")
        row = self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertEqual(row["records"], 1, "the only record was skipped")
        self.assertEqual(row["status"], lanes.RUNNING)

    def test_an_idle_lane_that_stopped_logging_is_flagged_as_quiet(self):
        """MEASURED 2026-10-15 23:40: a watcher process was alive and had
        written nothing for 19 minutes - no MOVED after its DONE and not one
        idle heartbeat, though `lane_watcher.ps1` logs one every five minutes
        and swallows a failed write. Both crossed authorities said IDLE,
        correctly, and neither could say the lane had also gone silent."""
        self.an_estate()
        self.a_lane("alpha", pid=10, log=[
            line("alpha", "22:00:00", "START a.md"),
            line("alpha", "22:30:00", "DONE  a.md -> exit0")])
        row = self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertEqual(row["verdict"], lanes.V_IDLE)
        self.assertEqual(row["log_silent_seconds"], 3600)
        self.assertTrue(row["log_has_gone_quiet"])
        body = pages.lane_board(self._api())
        self.assertIn("the log has gone quiet", body)

    def test_a_watcher_mid_task_is_not_flagged_for_being_quiet(self):
        """A task runs for an hour and its watcher says nothing in between.
        That is the design, not a fault - so the question is only asked of a
        lane whose log says idle."""
        self.an_estate()
        self.a_lane("alpha", pid=10,
                    log=[line("alpha", "21:00:00", "START b.md")])
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe"),
                                        11: (10, "cmd.exe")}, cpu={11: 9.0}))
        self.assertEqual(row["log_silent_seconds"], 9000)
        self.assertFalse(row["log_has_gone_quiet"])

    def test_an_idle_lane_inside_the_heartbeat_window_is_not_flagged(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=[
            line("alpha", "23:00:00", "START a.md"),
            line("alpha", "23:28:00", "DONE  a.md -> exit0")])
        row = self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertEqual(row["verdict"], lanes.V_IDLE)
        self.assertEqual(row["log_silent_seconds"], 120)
        self.assertFalse(row["log_has_gone_quiet"])

    def _api(self):
        os.environ[lanes.OPS_DIR] = self.root
        self.addCleanup(os.environ.pop, lanes.OPS_DIR, None)
        return api.lane_board(now=NOW, samples={},
                              probe=FakeProbe({10: (1, "powershell.exe")}))

    def test_a_stamp_that_cannot_be_parsed_gives_no_duration(self):
        self.an_estate()
        self.a_lane("alpha", pid=10,
                    log=["[2026-13-45 99:99:99] [alpha] START b.md"])
        row = self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))
        # The shape matched, so it IS a record; the stamp did not, so there
        # is no age. None rather than 0 - a zero would read as "just now".
        self.assertEqual(row["status"], lanes.RUNNING)
        self.assertIsNone(row["since_seconds"])

    def test_a_truncated_log_says_so_and_drops_the_partial_line(self):
        self.an_estate()
        filler = "x" * 200
        body = [filler] * ((lanes.MAX_LOG_BYTES // len(filler)) + 20)
        body.append(line("alpha", "23:00:00", "START b.md"))
        self.a_lane("alpha", pid=10, log=body)
        row = self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertTrue(row["log_truncated"])
        self.assertEqual(row["status"], lanes.RUNNING)


# --------------------------------------------------------------------------
# THE DONE SUFFIX


class TheThreeDoneSuffixesAreNotFlattened(unittest.TestCase, Estate):
    """`exit0`, `NOWORK` and `TIMEOUT` are three outcomes, not one."""

    def _lane_with(self, suffix):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=[
            line("alpha", "22:00:00", "START a.md"),
            line("alpha", "22:30:00", "DONE  a.md -> %s" % suffix)])
        return self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))

    def test_each_suffix_is_carried_verbatim_with_its_own_meaning(self):
        seen = set()
        for suffix in ("exit0", "NOWORK", "TIMEOUT"):
            row = self._lane_with(suffix)
            self.assertEqual(row["last_done_suffix"], suffix)
            self.assertIn("-> " + suffix, row["last_done_line"])
            short, why = lanes.DONE_MEANINGS[suffix]
            seen.add((short, why))
        self.assertEqual(len(seen), 3, "three suffixes, three meanings")

    def test_a_nonzero_exit_is_not_read_as_exit0(self):
        """The claim in the name: `exit1` does not flatten into `exit0`.

        THE SECOND ASSERTION USED TO BE `exit1 not in DONE_MEANINGS`, with
        `exit1` standing in for "a suffix nothing describes". TASK 0250
        measured `exit1` seventeen times across the seven watcher logs and
        described it, so that stand-in stopped being one - and a rule keyed
        on which tokens happen to be undescribed today is a rule that
        expires. The rule itself is unchanged and is now asserted against a
        token that is genuinely not described, which cannot expire:
        `test_an_unrecognised_suffix_renders_as_unrecognised` below is the
        same rule at the render.
        """
        row = self._lane_with("exit1")
        self.assertEqual(row["last_done_suffix"], "exit1")
        self.assertNotEqual(row["last_done_suffix"], "exit0")
        self.assertNotIn("something-nobody-has-written",
                         lanes.DONE_MEANINGS,
                         "an unrecognised suffix must stay unrecognised")
        short, _why, described = lanes.done_meaning(
            "something-nobody-has-written")
        self.assertEqual(short, "UNKNOWN TOKEN")
        self.assertFalse(described)

    def test_an_unrecognised_suffix_renders_as_unrecognised(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=[
            line("alpha", "22:00:00", "START a.md"),
            line("alpha", "22:30:00", "DONE  a.md -> something-new")])
        body = pages.lane_board(self._api())
        self.assertIn("something-new", body)
        self.assertIn("unrecognised suffix", body)

    def test_the_page_shows_the_DONE_line_verbatim(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=[
            line("alpha", "22:00:00", "START 0030-build-the-first-page.md"),
            line("alpha", "22:39:54",
                 "DONE  0030-build-the-first-page.md -> exit0")])
        body = pages.lane_board(self._api())
        self.assertIn("DONE  0030-build-the-first-page.md -&gt; exit0", body)

    def _api(self):
        os.environ[lanes.OPS_DIR] = self.root
        self.addCleanup(os.environ.pop, lanes.OPS_DIR, None)
        return api.lane_board(now=NOW, samples={},
                              probe=FakeProbe({10: (1, "powershell.exe")}))


# --------------------------------------------------------------------------
# THE OWED-GATE MARKER


class AnOwedMarkerIsReportedAndNeverInterpreted(unittest.TestCase, Estate):
    """The detector matches phrases in prose. It judges nothing.

    MEASURED ON TONIGHT'S SEVEN REAL LANE FILES, which is why the contract is
    this weak: a plain substring test for "owed" matches "swallowed", and the
    verb-phrase pattern matches "Nothing else is owed", which is the opposite
    claim. So the reader reports the LINE and the page says plainly that no
    marker is not evidence that nothing is owed.
    """

    def test_a_marker_in_the_last_section_is_found_with_its_line(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, lane_file=(
            "## 2026-10-15 - TASK 0030\n"
            "some prose\n"
            "### SUITE: NOT OBTAINED - second consecutive run\n"))
        row = self.row("alpha")
        self.assertEqual(len(row["owed"]["hits"]), 1)
        self.assertEqual(row["owed"]["hits"][0]["line"], 3)
        self.assertEqual(row["owed"]["hits"][0]["marker"], "not-obtained")
        self.assertIn("SUITE: NOT OBTAINED", row["owed"]["hits"][0]["text"])

    def test_swallowed_followed_and_allowed_are_not_owed(self):
        """The substring bug, pinned. It fired on a real lane file tonight.

        EACH LINE HERE WATCHES A DIFFERENT PART OF THE PATTERN, and that is
        measured rather than hoped: with only the first three lines, removing
        EITHER word boundary left this test GREEN, because a plain substring
        is the only form that matches "swallowed". So two more lines, each
        the realistic phrase that makes one boundary load-bearing:

            "this owed reference"    the LEADING one. "th-is owed" contains
                                     "is owed", so a passing mention matches
                                     without it
            "is owed_by_nobody"      the TRAILING one. An underscore is a
                                     word character, so `owed\\b` rejects an
                                     identifier and a bare `owed` does not -
                                     and these files quote snake_case
                                     identifiers in prose constantly
        """
        self.an_estate()
        self.a_lane("alpha", pid=10, lane_file=(
            "## 2026-10-15 - TASK 0030\n"
            "swallowed by the recorder's own except, and it was allowed\n"
            "the followed path showed nothing\n"
            "a note about this owed reference, which is not a declaration\n"
            "the flag is owed_by_nobody, a variable rather than a gate\n"))
        row = self.row("alpha")
        self.assertEqual(row["owed"]["hits"], [])
        self.assertEqual(row["owed"]["before"], 0)

    def test_a_declared_owed_phrase_is_found(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, lane_file=(
            "## 2026-10-15 - TASK 0030\n"
            "A full-suite reference is OWED: tests/ changed.\n"))
        row = self.row("alpha")
        self.assertEqual(len(row["owed"]["hits"]), 1)
        self.assertEqual(row["owed"]["hits"][0]["marker"], "declared-owed")

    def test_no_marker_is_not_rendered_as_nothing_is_owed(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, lane_file=(
            "## 2026-10-15 - TASK 0030\nall clean\n"))
        row = self.row("alpha")
        self.assertEqual(row["owed"]["hits"], [])
        body = pages.lane_board(self._api())
        self.assertIn("not evidence that nothing is owed", body)

    def test_markers_outside_the_scope_are_counted_and_not_hidden(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, lane_file=(
            "## 2026-10-14 - TASK 0010\n"
            "SUITE: NOT OBTAINED\n"
            "a full suite is still OWED\n"
            "## 2026-10-15 - TASK 0020\n"
            "clean\n"))
        row = self.row("alpha")
        self.assertEqual(row["owed"]["hits"], [])
        self.assertEqual(row["owed"]["before"], 2)

    def test_an_undated_last_heading_is_flagged_as_a_narrow_scope(self):
        """Measured on a real lane file: one lane writes several `## `
        headings inside one entry, so the last `## ` is narrower than the
        last entry and its earlier markers fall out of scope."""
        self.an_estate()
        self.a_lane("alpha", pid=10, lane_file=(
            "## 2026-10-15 - TASK 0160\n"
            "SUITE: NOT OBTAINED\n"
            "## FOR HIM - six questions\n"
            "nothing here\n"))
        row = self.row("alpha")
        self.assertIs(row["owed"]["heading_dated"], False)
        self.assertEqual(row["owed"]["hits"], [])
        self.assertEqual(row["owed"]["before"], 1)
        body = pages.lane_board(self._api())
        self.assertIn("that heading is not dated", body)

    def test_a_missing_lane_file_is_UNKNOWN_and_not_no_marker(self):
        self.an_estate()
        self.a_lane("alpha", pid=10)
        row = self.row("alpha")
        self.assertEqual(row["owed"]["state"], lanes.ABSENT)
        body = pages.lane_board(self._api())
        self.assertIn("not available", body)

    def test_an_unreadable_lane_file_is_UNKNOWN(self):
        self.an_estate()
        self.a_lane("alpha", pid=10)
        os.makedirs(os.path.join(self.root, "LANE-alpha.md"))
        row = self.row("alpha")
        self.assertEqual(row["owed"]["state"], lanes.UNREADABLE)

    def _api(self):
        os.environ[lanes.OPS_DIR] = self.root
        self.addCleanup(os.environ.pop, lanes.OPS_DIR, None)
        return api.lane_board(now=NOW, samples={},
                              probe=FakeProbe({10: (1, "powershell.exe")}))


# --------------------------------------------------------------------------
# THE AUTHORITIES THIS PAGE REFUSES


class TheThreeWrongAuthoritiesAreNotRead(unittest.TestCase, Estate):
    """Refusal proven by behaviour: the wrong authority is made to lie.

    Each test below sets up an estate where reading the refused authority
    would produce a DIFFERENT answer from the right one. If the board's
    answer moves, it read the wrong file.
    """

    OPEN = [line("alpha", "23:00:00", "START b.md")]
    CLOSED = [line("alpha", "22:00:00", "START a.md"),
              line("alpha", "22:30:00", "DONE  a.md -> exit0")]

    def test_a_zero_byte_out_file_does_not_make_a_working_lane_look_dead(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.OPEN, out_bytes=0)
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe"),
                                        11: (10, "cmd.exe")}, cpu={11: 5.0}))
        self.assertEqual(row["verdict"], lanes.V_RUNNING)

    def test_a_large_out_file_does_not_make_an_idle_lane_look_busy(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.CLOSED, out_bytes=50000)
        row = self.row("alpha", probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertEqual(row["verdict"], lanes.V_IDLE)

    def test_the_DONE_folder_is_not_read_for_depth_or_for_verdict(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.OPEN,
                    queued=["c.md"],
                    done=["1-exit0-a.md", "2-TIMEOUT-but-complete-b.md",
                          "3-hand-named-by-nobody.md"])
        row = self.row("alpha",
                       probe=FakeProbe({10: (1, "powershell.exe"),
                                        11: (10, "cmd.exe")}, cpu={11: 1.0}))
        self.assertEqual(row["queue_depth"], 1,
                         "three DONE files must not inflate the depth")
        self.assertEqual(row["verdict"], lanes.V_RUNNING)
        self.assertEqual(row["last_done_line"], None,
                         "the log has no DONE line, whatever the folder holds")

    def test_the_page_names_each_refused_authority(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, log=self.OPEN)
        os.environ[lanes.OPS_DIR] = self.root
        self.addCleanup(os.environ.pop, lanes.OPS_DIR, None)
        data = api.lane_board(now=NOW, samples={},
                              probe=FakeProbe({10: (1, "pwsh.exe")}))
        self.assertEqual(len(data["refused"]), 4)
        body = pages.lane_board(data)
        for entry in data["refused"]:
            # Through the same escaper the page uses. Hand-rolling the
            # escaping here would make this a test of my own replace().
            self.assertIn(esc(entry["authority"]), body)


# --------------------------------------------------------------------------
# IT WRITES NOTHING AND REACHES NOTHING


class ItWritesNothingAndOpensNoSocket(unittest.TestCase, Estate):
    """The constraint the task was given, measured rather than asserted."""

    def test_reading_the_board_changes_no_byte_in_the_estate(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, queued=["c.md"], inflight=["b.md"],
                    lane_file="## 2026-10-15\nSUITE: NOT OBTAINED\n",
                    log=[line("alpha", "23:00:00", "START b.md")])
        before = self._snapshot()
        self.board(probe=FakeProbe({10: (1, "powershell.exe")}))
        self.board(probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertEqual(before, self._snapshot())

    def test_the_board_opens_no_socket(self):
        """`socket.socket` is made to raise, and then the board is read."""
        self.an_estate()
        self.a_lane("alpha", pid=10,
                    log=[line("alpha", "23:00:00", "START b.md")])
        real = socket.socket

        def refuse(*_args, **_kwargs):
            raise AssertionError("the lane board opened a socket")

        socket.socket = refuse
        self.addCleanup(setattr, socket, "socket", real)
        data = self.board(probe=FakeProbe({10: (1, "powershell.exe")}))
        self.assertEqual(len(data["lanes"]), 1)

    def test_the_reader_imports_no_transport_and_no_provider(self):
        """On the import graph, not on the text of the source."""
        offenders = []
        for name, value in vars(lanes).items():
            if not isinstance(value, types.ModuleType):
                continue
            root = value.__name__.split(".")[0]
            if root in ("socket", "ssl", "urllib", "http", "requests"):
                offenders.append(name)
            if value.__name__.startswith("src.providers"):
                offenders.append(name)
        self.assertEqual(offenders, [])

    def test_the_reader_reads_no_state_file_of_this_product(self):
        """`src.store` is not in its graph: the lane estate is not our state.

        Conflating the two would put the queue and the campaign ledger behind
        the same reader, and `work/` is a different authority entirely.
        """
        self.assertNotIn("store", [
            name for name, value in vars(lanes).items()
            if isinstance(value, types.ModuleType)])

    def _snapshot(self):
        found = {}
        for base, _dirs, files in os.walk(self.root):
            for name in files:
                full = os.path.join(base, name)
                stat = os.stat(full)
                found[os.path.relpath(full, self.root)] = (stat.st_size,
                                                           stat.st_mtime_ns)
        return found


# --------------------------------------------------------------------------
# WHICH LANES EXIST


class ALaneIsFoundInBothAuthoritiesOrOne(unittest.TestCase, Estate):
    """A lane with a folder and no log has never run. Both are worth seeing."""

    def test_a_lane_with_only_a_queue_folder_is_listed(self):
        self.an_estate()
        self.a_lane("alpha")
        row = self.row("alpha")
        self.assertEqual(row["found_in"], "queue")
        self.assertEqual(row["verdict"], lanes.V_UNKNOWN)

    def test_a_lane_with_only_a_log_is_listed(self):
        self.an_estate()
        self.a_lane("alpha", no_queue_dir=True, pid=10,
                    log=[line("alpha", "23:00:00", "START b.md")])
        row = self.row("alpha")
        self.assertEqual(row["found_in"], "log")
        self.assertEqual(row["queue_state"], lanes.ABSENT)
        self.assertIsNone(row["queue_depth"])

    def test_a_lane_in_both_says_both(self):
        self.an_estate()
        self.a_lane("alpha", pid=10,
                    log=[line("alpha", "23:00:00", "START b.md")])
        self.assertEqual(self.row("alpha")["found_in"], "both")

    def test_an_underscore_file_in_the_queue_root_is_not_a_lane(self):
        self.an_estate()
        self.a_lane("alpha")
        self._write(os.path.join(self.root, "queue", "_STANDING-RULES.md"),
                    "rules\n")
        os.makedirs(os.path.join(self.root, "queue", "_private"))
        names = [n for n, _ in lanes.lane_names(self.root)]
        self.assertEqual(names, ["alpha"])

    def test_the_queue_is_ordered_the_way_the_watcher_orders_it(self):
        """Case-insensitively by name, so `next_up` is what it will take."""
        self.an_estate()
        self.a_lane("alpha", pid=10, queued=["0050-b.md", "0040-a.md",
                                             "ZZZ.md"],
                    log=[line("alpha", "23:00:00", "START b.md")])
        self.assertEqual(self.row("alpha")["next_up"], "0040-a.md")

    def test_a_non_md_file_in_the_queue_is_not_a_brief(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, queued=["0040-a.md"],
                    log=[line("alpha", "23:00:00", "START b.md")])
        self._write(os.path.join(self.root, "queue", "alpha", "notes.txt"),
                    "x\n")
        self.assertEqual(self.row("alpha")["queue_depth"], 1)

    def test_two_briefs_in_RUNNING_is_surfaced_as_an_alarm(self):
        self.an_estate()
        self.a_lane("alpha", pid=10, inflight=["a.md", "b.md"],
                    log=[line("alpha", "23:00:00", "START a.md")])
        os.environ[lanes.OPS_DIR] = self.root
        self.addCleanup(os.environ.pop, lanes.OPS_DIR, None)
        body = pages.lane_board(
            api.lane_board(now=NOW, samples={},
                           probe=FakeProbe({10: (1, "powershell.exe")})))
        self.assertIn("2 briefs in RUNNING", body)

    @staticmethod
    def _write(path, text):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)


# --------------------------------------------------------------------------
# THE ROUTE AND ITS GATE


class TheRouteIsGatedTheWayAdminIs(WebTest):
    """An account-level check, not a workspace permission.

    The lane estate is a fact about this machine - the same rows whichever
    workspace the session points at - so a workspace permission would be a
    permission over data no workspace owns, and `operations.view` reaches a
    client-facing REVIEWER.
    """

    def setUp(self):
        self.estate = tempfile.mkdtemp(prefix="rga-lanes-web-")
        self.addCleanup(shutil.rmtree, self.estate, ignore_errors=True)
        os.makedirs(os.path.join(self.estate, "queue", "alpha", "RUNNING"))
        os.makedirs(os.path.join(self.estate, "logs"))
        with open(os.path.join(self.estate, "logs", "watcher-alpha.log"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write(line("alpha", "22:00:00", "START a.md") + "\n")
            handle.write(line("alpha", "22:30:00",
                              "DONE  a.md -> TIMEOUT") + "\n")
        previous = os.environ.get(lanes.OPS_DIR)
        os.environ[lanes.OPS_DIR] = self.estate
        self.addCleanup(self._restore, previous)

    @staticmethod
    def _restore(previous):
        if previous is None:
            os.environ.pop(lanes.OPS_DIR, None)
        else:
            os.environ[lanes.OPS_DIR] = previous

    def test_a_super_admin_gets_the_page(self):
        status, body, _ = self.signin(SUPER).get(PATH)
        self.assertEqual(status, 200)
        self.assertIn("Lane board", body)
        self.assertIn("alpha", body)
        self.assertIn("-&gt; TIMEOUT", body)

    def test_a_workspace_admin_is_refused(self):
        status, body, _ = self.signin(ADMIN).get(PATH)
        self.assertEqual(status, 404, "404 rather than 403, as /admin does")
        self.assertNotIn("alpha", body)

    def test_an_operator_is_refused(self):
        status, body, _ = self.signin(OPERATOR).get(PATH)
        self.assertEqual(status, 404)
        self.assertNotIn("alpha", body)

    def test_an_anonymous_caller_is_never_served_the_board(self):
        """The opener follows the redirect, so 200 is the sign-in page.

        Asserting on the status alone would therefore pass for a served
        board and fail for a correct redirect - which is why the assertion
        is on what reached the caller.
        """
        status, body, _ = self.anonymous().get(PATH)
        self.assertIn(status, (200, 303))
        self.assertNotIn("Lane board", body)
        self.assertNotIn("alpha", body)
        self.assertIn("Sign in", body)

    def test_the_route_is_not_gated_by_a_workspace_permission(self):
        """If it ever acquires one, the super-admin check is what moved.

        This is the mutation that mattered on 0030: a handler gate nothing
        watched. Here the two gates are mutually exclusive by design, so
        asserting both is what makes either one's removal visible.
        """
        self.assertIsNone(permission_for(PATH))

    def test_a_POST_is_not_accepted(self):
        session = self.signin(SUPER)
        status, _body, _ = session.post(PATH, {"csrf": session.csrf()})
        self.assertNotEqual(status, 200)

    def test_the_navigation_entry_is_super_admin_only(self):
        found = [entry for _k, _t, _h, items in pages.SECTIONS
                 for entry in items if entry[0] == PATH]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][2], "__super_admin__")

    def test_the_page_renders_every_verdict_it_can_name(self):
        """The glossary comes from the reader, so it cannot drift from it."""
        _status, body, _ = self.signin(SUPER).get(PATH)
        for label, _why in lanes.VERDICT_TEXT.values():
            self.assertIn(label, body, "%r is not on the page" % label)


class TheVariableIsRegisteredWhereCredentialNamesLive(unittest.TestCase):
    """A name read from `config.VARIABLES` is a name nobody can invent.

    This repository has lost an afternoon to four guessed variable names. The
    reader and the registry must agree, and `--verify` has to be able to see
    this one.
    """

    def test_the_variable_the_reader_uses_is_in_the_registry(self):
        from src import config
        self.assertIn(lanes.OPS_DIR, config.BY_NAME)

    def test_it_is_optional_so_it_cannot_block_production_startup(self):
        from src import config
        classification, _group, _why = config.BY_NAME[lanes.OPS_DIR]
        self.assertEqual(classification, config.OPTIONAL)


if __name__ == "__main__":
    unittest.main()
