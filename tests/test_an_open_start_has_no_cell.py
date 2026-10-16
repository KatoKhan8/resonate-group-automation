"""An open ``START``: is anyone still listening?

WHAT THIS FILE IS FOR. ``LANE_DEADLINE`` lets a task ask *can I finish?*.
Nothing let it ask *is anyone still listening?*, and the consequence is on
file twice: ``CONTINUITY.md`` section 4 trap 13 filed the check on 2026-10-16
and nobody built it, and ``webapp/0270`` section 6 filed it again because a
dispatch with no ``DONE`` line is never asked the landing question at all.

THE INVARIANT UNDER TEST IS NOT "the module exists" and is never the text of
a docstring - a test that greps source fails when somebody writes a comment,
which is this repository's own named anti-pattern. It is the behaviour:

    the naive check is refused. An open ``START`` older than its lane's own
    timeout is NOT by itself a lost lane, because a session that runs past
    its brief sits open far longer than the brief's own span while working
    perfectly - two lanes did exactly that on 2026-10-16;

    an unmeasurable liveness is UNDETERMINED. Never ALIVE, which would be an
    instrument reporting clean while blind, and never DEAD, because trap 1 is
    explicit that re-queuing is what loses the work;

    the timeout comes from THIS lane's own ``watcher up`` line. Not the
    constant in the script, not another lane's: ``pilotcaps/0220`` claimed 150
    against its own log's 90 and closed 85m47s in;

    a coded ending is never swallowed. ``qwen/0177`` took the ``TIMEOUT`` path
    with a 0-byte ``.out``, which is byte-identical to trap 13's, and it must
    not appear as an open ``START``;

    a lane file's mtime may demote a row and never promote one, which is
    ``webapp/0250``'s rule and is kept here by construction.

NOTHING HERE REACHES A PROVIDER, A NETWORK, A REAL LANE OR A REAL PROCESS.
Every estate is a directory written into a temporary folder; every process
table is a dict handed to the reader; no pid is ever signalled.
"""
import datetime
import os
import shutil
import tempfile
import unittest

from src import laneopen, lanes

#: Every stamp in this file is on one day, so an elapsed time is readable as
#: a subtraction rather than as a date calculation.
DAY = "2026-10-16"
NOW = datetime.datetime(2026, 10, 16, 21, 0, 0)


def line(lane, clock, message):
    """One watcher record, in the exact shape ``lane_watcher.ps1`` writes.

    Written here rather than imported, so that a change to the watcher's
    format fails in this file instead of producing a board of empty cells.
    """
    return "[%s %s] [%s] %s" % (DAY, clock, lane, message)


def up(lane, clock="08:00:00", timeout="150m"):
    tail = (" timeout=" + timeout) if timeout else ""
    return line(lane, clock, "watcher up. tree=X mode=acceptEdits" + tail)


class Probe:
    """A process table and a CPU clock, supplied rather than measured.

    ``blind=True`` is the real refusal: the table could not be read, which
    must make every liveness answer UNDETERMINED rather than zero.
    """

    def __init__(self, table=None, cpu=None, blind=False):
        self._table = None if blind else (table or {})
        self._cpu = cpu or {}

    def table(self):
        return self._table

    def cpu(self, pid):
        return self._cpu.get(pid)


class Estate(unittest.TestCase):
    """A disposable lane estate and the one call that renders a row from it."""

    lane = "plant"

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="t0266-")
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(os.path.join(self.root, "logs"))
        os.makedirs(os.path.join(self.root, "queue", self.lane, "RUNNING"))
        os.makedirs(os.path.join(self.root, "queue", self.lane, "DONE"))
        self.lane_file = os.path.join(self.root, "LANE-%s.md" % self.lane)
        self.write_lane("# LANE %s\n" % self.lane)

    def write_log(self, *lines):
        path = os.path.join(self.root, "logs", "watcher-%s.log" % self.lane)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def write_pid(self, pid):
        path = os.path.join(self.root, "logs", "watcher-%s.pid" % self.lane)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(str(pid))

    def write_lane(self, text, when=None):
        with open(self.lane_file, "w", encoding="utf-8") as handle:
            handle.write(text)
        if when is not None:
            stamp = when.timestamp()
            os.utime(self.lane_file, (stamp, stamp))

    def row(self, now=NOW, probe=None, samples=None):
        # `samples or {}` would be a bug here and was one for ten minutes:
        # an EMPTY dict is falsy, so the first of two renders would store its
        # sample into a throwaway and no delta could ever exist. The same
        # shape as a falsy root argument falling through to the environment.
        data = lanes.board(root=self.root, now=now,
                           probe=probe or Probe(),
                           samples={} if samples is None else samples)
        for item in data["lanes"]:
            if item["lane"] == self.lane:
                return item
        self.fail("no row for lane %r" % self.lane)

    def only_open(self, **kwargs):
        cell = self.row(**kwargs)["open_start"]
        self.assertEqual(len(cell["open"]), 1, cell["open"])
        return cell["open"][0]

    def alive_probe(self, pid=4242, child=99, cpu=10.0):
        return Probe(table={pid: (1, "powershell.exe"), child: (pid, "x.exe")},
                     cpu={child: cpu})

    def two_samples(self, first=10.0, second=31.0, pid=4242, child=99,
                    now=NOW, gap=30):
        """Render twice with one shared sample store, so a delta exists.

        A CPU figure is not a liveness answer; a RISE between two readings
        is. Rendering once and asserting ALIVE would be asserting the thing
        the module refuses to do.
        """
        samples = {}
        self.row(now=now, probe=self.alive_probe(pid, child, first),
                 samples=samples)
        return self.only_open(now=now + datetime.timedelta(seconds=gap),
                              probe=self.alive_probe(pid, child, second),
                              samples=samples)


class TheNaiveCheckIsRefused(Estate):
    """Elapsed alone never decides. Trap 14 is why."""

    def test_an_open_start_past_the_timeout_is_not_dead_while_it_is_alive(self):
        # webapp/0260's measured shape: open for 53 minutes and healthy. Made
        # worse than the real case on purpose - this one is 415 minutes past
        # a 90-minute cap, so elapsed could not be more damning - and it
        # still may not read as lost while something is burning CPU.
        self.write_log(up(self.lane, timeout="90m"),
                       line(self.lane, "14:05:00", "START 0010-planted.md"))
        self.write_pid(4242)
        row = self.two_samples()
        self.assertEqual(row["elapsed_seconds"], 415 * 60 + 30)
        self.assertEqual(row["deadline_state"], laneopen.D_PAST)
        self.assertEqual(row["liveness"]["group"], laneopen.LIVE)
        self.assertEqual(row["verdict"], laneopen.OPEN_ALIVE)

    def test_the_same_dispatch_with_nothing_alive_reads_no_liveness(self):
        # The paired direction, and the only input that changed is the
        # process table. Without this the test above passes on a classifier
        # that can never say anything else.
        self.write_log(up(self.lane, timeout="90m"),
                       line(self.lane, "14:05:00", "START 0010-planted.md"))
        self.write_pid(4242)
        row = self.only_open(probe=Probe(table={4242: (1, "powershell.exe")}))
        self.assertEqual(row["liveness"]["state"], laneopen.L_NO_CHILD)
        self.assertEqual(row["verdict"], laneopen.OPEN_NO_LIVENESS)

    def test_inside_the_deadline_with_nothing_alive_is_not_dead_either(self):
        self.write_log(up(self.lane, timeout="90m"),
                       line(self.lane, "20:05:00", "START 0010-planted.md"))
        self.write_pid(4242)
        row = self.only_open(probe=Probe(table={4242: (1, "powershell.exe")}))
        self.assertEqual(row["deadline_state"], laneopen.D_WITHIN)
        self.assertEqual(row["verdict"], laneopen.OPEN_WITHIN_DEADLINE)


class UnmeasurableIsNeverAGuess(Estate):
    """Failure family five: an instrument that cannot report its own blindness."""

    def setUp(self):
        super().setUp()
        self.write_log(up(self.lane, timeout="90m"),
                       line(self.lane, "14:05:00", "START 0010-planted.md"))
        self.write_pid(4242)

    def test_an_unreadable_process_table_is_undetermined_not_dead(self):
        row = self.only_open(probe=Probe(blind=True))
        self.assertEqual(row["liveness"]["state"], laneopen.L_NO_TABLE)
        self.assertEqual(row["verdict"], laneopen.OPEN_UNDETERMINED)

    def test_an_unreadable_process_table_is_undetermined_not_alive(self):
        row = self.only_open(probe=Probe(blind=True))
        self.assertNotEqual(row["verdict"], laneopen.OPEN_ALIVE)
        self.assertNotEqual(row["liveness"]["group"], laneopen.LIVE)

    def test_the_same_fixture_with_a_readable_table_does_decide(self):
        # The control on the two above: they pass because the PROBE is blind,
        # not because the fixture is unclassifiable.
        row = self.only_open(probe=Probe(table={4242: (1, "powershell.exe")}))
        self.assertEqual(row["verdict"], laneopen.OPEN_NO_LIVENESS)

    def test_one_sample_is_not_a_liveness_answer(self):
        # A CPU figure is not a rise. The first look in a process has no
        # delta, and a board that called that ALIVE would be reading a
        # number nobody compared with anything.
        row = self.only_open(probe=self.alive_probe())
        self.assertEqual(row["liveness"]["state"], laneopen.L_ONE_SAMPLE)
        self.assertEqual(row["verdict"], laneopen.OPEN_UNDETERMINED)

    def test_a_flat_subtree_is_undetermined_rather_than_dead(self):
        # conhost.exe is a child of every watcher and a session waiting on an
        # API burns no measurable CPU, so a flat reading proves nothing in
        # either direction.
        row = self.two_samples(first=10.0, second=10.0)
        self.assertEqual(row["liveness"]["state"], laneopen.L_FLAT)
        self.assertEqual(row["verdict"], laneopen.OPEN_UNDETERMINED)

    def test_a_missing_pid_file_is_undetermined(self):
        os.remove(os.path.join(self.root, "logs",
                               "watcher-%s.pid" % self.lane))
        row = self.only_open(probe=Probe(table={}))
        self.assertEqual(row["liveness"]["state"], laneopen.L_NO_PID)
        self.assertEqual(row["verdict"], laneopen.OPEN_UNDETERMINED)

    def test_every_liveness_reading_is_classified_explicitly(self):
        # A reading added without a group must raise rather than defaulting
        # into whichever bucket looks safest. The grouping is the whole
        # three-way decision and a silent default would hide it.
        self.assertEqual(set(laneopen.LIVENESS_GROUP),
                         set(laneopen.LIVENESS_TEXT))
        with self.assertRaises(KeyError):
            laneopen._group("a reading nobody classified")

    def test_the_blinded_probe_the_board_takes_on_every_render(self):
        self.assertEqual(laneopen.blind_probe_verdict(NOW),
                         laneopen.OPEN_UNDETERMINED)


class TheTimeoutAuthority(Estate):
    """This lane's own ``watcher up`` line, and the line is printed."""

    def test_the_cap_comes_from_this_lane_s_own_up_line(self):
        self.write_log(up(self.lane, timeout="90m"),
                       line(self.lane, "20:05:00", "START 0010-planted.md"))
        self.write_pid(4242)
        cell = self.row(probe=Probe(table={4242: (1, "powershell.exe")}))[
            "open_start"]
        self.assertEqual(cell["timeout_minutes"], 90)
        self.assertIn("timeout=90m", cell["timeout_from_line"])

    def test_the_newest_up_line_wins_over_an_older_one(self):
        self.write_log(up(self.lane, "07:00:00", timeout="90m"),
                       up(self.lane, "08:00:00", timeout="150m"),
                       line(self.lane, "20:05:00", "START 0010-planted.md"))
        self.write_pid(4242)
        cell = self.row(probe=Probe(table={4242: (1, "powershell.exe")}))[
            "open_start"]
        self.assertEqual(cell["timeout_minutes"], 150)
        self.assertIn("timeout=150m", cell["timeout_from_line"])

    def test_an_unknown_cap_cannot_produce_a_dead_verdict(self):
        # The deadline is a comparison and a comparison needs both sides. An
        # `up` line with no `timeout=` field leaves one side missing, and the
        # answer is UNDETERMINED rather than the 150 in the script on disk.
        self.write_log(up(self.lane, timeout=None),
                       line(self.lane, "14:05:00", "START 0010-planted.md"))
        self.write_pid(4242)
        row = self.only_open(probe=Probe(table={4242: (1, "powershell.exe")}))
        self.assertIsNone(row["deadline_state"] == laneopen.D_PAST or None)
        self.assertEqual(row["deadline_state"], laneopen.D_NO_TIMEOUT)
        self.assertEqual(row["verdict"], laneopen.OPEN_UNDETERMINED)

    def test_the_same_fixture_with_a_cap_does_reach_a_dead_verdict(self):
        self.write_log(up(self.lane, timeout="90m"),
                       line(self.lane, "14:05:00", "START 0010-planted.md"))
        self.write_pid(4242)
        row = self.only_open(probe=Probe(table={4242: (1, "powershell.exe")}))
        self.assertEqual(row["verdict"], laneopen.OPEN_NO_LIVENESS)


class ACodedEndingIsNeverSwallowed(Estate):
    """``qwen/0177`` is the row that proves it: a TIMEOUT, not an open START."""

    def test_a_timeout_is_a_closed_dispatch_and_not_an_open_start(self):
        self.write_log(up(self.lane),
                       line(self.lane, "14:05:00", "START 0010-planted.md"),
                       line(self.lane, "16:35:00",
                            "DONE  0010-planted.md -> TIMEOUT"))
        self.write_pid(4242)
        cell = self.row(probe=Probe(table={4242: (1, "powershell.exe")}))[
            "open_start"]
        self.assertEqual(cell["open"], [])
        self.assertEqual(cell["closed_count"], 1)
        self.assertEqual(cell["endings"], ["TIMEOUT"])
        self.assertIsNone(cell["verdict"])

    def test_the_same_dispatch_with_its_done_line_removed_is_open(self):
        self.write_log(up(self.lane),
                       line(self.lane, "14:05:00", "START 0010-planted.md"))
        self.write_pid(4242)
        cell = self.row(probe=Probe(table={4242: (1, "powershell.exe")}))[
            "open_start"]
        self.assertEqual(cell["open_count"], 1)
        self.assertEqual(cell["verdict"], laneopen.OPEN_NO_LIVENESS)

    def test_the_done_folder_is_not_an_authority(self):
        # Nine `DONE\\` entries stamped 20261016-0042-0145 read `exit1` for
        # briefs that never ran, so a filename there can be positively false.
        # A file in DONE\\ with no DONE LINE leaves the dispatch open.
        self.write_log(up(self.lane),
                       line(self.lane, "14:05:00", "START 0010-planted.md"))
        self.write_pid(4242)
        done = os.path.join(self.root, "queue", self.lane, "DONE",
                            "20261016-140500-exit0-0010-planted.md")
        open(done, "w").close()
        cell = self.row(probe=Probe(table={4242: (1, "powershell.exe")}))[
            "open_start"]
        self.assertEqual(cell["open_count"], 1)

    def test_an_empty_running_folder_is_not_an_authority_either(self):
        # webapp/0265's exact shape: the brief was moved out of RUNNING\\ by
        # hand at 20:47 and no DONE line was ever written.
        self.write_log(up(self.lane),
                       line(self.lane, "14:05:00", "START 0010-planted.md"))
        self.write_pid(4242)
        running = os.path.join(self.root, "queue", self.lane, "RUNNING")
        self.assertEqual(os.listdir(running), [])
        cell = self.row(probe=Probe(table={4242: (1, "powershell.exe")}))[
            "open_start"]
        self.assertEqual(cell["open_count"], 1)


class ALaterStartMeansNobodyIsListening(Estate):
    """The one answer that needs no process table, and the error it forecloses."""

    def test_a_superseded_dispatch_is_not_alive_on_the_next_one_s_child(self):
        # THE MEASURED ERROR THIS EXISTS FOR. webapp/0265 sat open from 16:10
        # while 0266's session ran under the SAME watcher pid. Walking the
        # watcher's children and finding a live process would report an
        # abandoned four-hour-old dispatch as ALIVE.
        self.write_log(up(self.lane),
                       line(self.lane, "16:10:00", "START 0265-older.md"),
                       line(self.lane, "20:47:46", "START 0266-newer.md"))
        self.write_pid(4242)
        samples = {}
        self.row(probe=self.alive_probe(cpu=10.0), samples=samples)
        cell = self.row(now=NOW + datetime.timedelta(seconds=30),
                        probe=self.alive_probe(cpu=31.0),
                        samples=samples)["open_start"]
        rows = {row["task"]: row for row in cell["open"]}
        self.assertEqual(rows["0265-older.md"]["verdict"],
                         laneopen.OPEN_NO_LIVENESS)
        self.assertEqual(rows["0265-older.md"]["liveness"]["state"],
                         laneopen.L_SUPERSEDED)
        self.assertEqual(rows["0265-older.md"]["superseded_by"],
                         "0266-newer.md")
        # And the newest one, on the SAME render and the same CPU rise, is
        # the ALIVE row. One table, two opposite answers, which is the whole
        # point of keying supersession off the log.
        self.assertEqual(rows["0266-newer.md"]["verdict"],
                         laneopen.OPEN_ALIVE)

    def test_supersession_survives_an_unreadable_process_table(self):
        self.write_log(up(self.lane),
                       line(self.lane, "16:10:00", "START 0265-older.md"),
                       line(self.lane, "20:47:46", "START 0266-newer.md"))
        self.write_pid(4242)
        cell = self.row(probe=Probe(blind=True))["open_start"]
        rows = {row["task"]: row for row in cell["open"]}
        self.assertEqual(rows["0265-older.md"]["verdict"],
                         laneopen.OPEN_NO_LIVENESS)
        # The one WITHOUT the log evidence still refuses to guess.
        self.assertEqual(rows["0266-newer.md"]["verdict"],
                         laneopen.OPEN_UNDETERMINED)

    def test_supersession_does_not_need_the_deadline(self):
        # qwen/0170 lost its supervisor 14 minutes in and 75 minutes BEFORE
        # its own deadline. A cap that can never fire is not a reason to wait.
        self.write_log(up(self.lane, timeout="150m"),
                       line(self.lane, "20:00:00", "START 0010-older.md"),
                       line(self.lane, "20:14:00", "START 0020-newer.md"))
        self.write_pid(4242)
        cell = self.row(probe=Probe(table={4242: (1, "powershell.exe")}))[
            "open_start"]
        older = [row for row in cell["open"]
                 if row["task"] == "0010-older.md"][0]
        self.assertEqual(older["deadline_state"], laneopen.D_WITHIN)
        self.assertEqual(older["verdict"], laneopen.OPEN_NO_LIVENESS)

    def test_a_done_line_closes_the_right_start_when_two_are_open(self):
        # `glm` holds two open STARTs from 2026-10-15. Pairing by position
        # rather than by task id would close the wrong one.
        self.write_log(up(self.lane),
                       line(self.lane, "14:00:00", "START 0010-a.md"),
                       line(self.lane, "15:00:00", "START 0020-b.md"),
                       line(self.lane, "16:00:00", "DONE  0020-b.md -> exit0"))
        path = os.path.join(self.root, "logs", "watcher-%s.log" % self.lane)
        with open(path, encoding="utf-8") as handle:
            events = lanes.watcher_events(handle.read().splitlines(),
                                          self.lane)
        rows = {row["task"]: row for row in laneopen.dispatches(events)}
        self.assertEqual(rows["0020-b.md"]["ending"], "exit0")
        self.assertIsNone(rows["0010-a.md"]["ending"])

    def test_the_watcher_itself_being_gone_is_its_own_reading(self):
        self.write_log(up(self.lane, timeout="90m"),
                       line(self.lane, "14:05:00", "START 0010-planted.md"))
        self.write_pid(4242)
        row = self.only_open(probe=Probe(table={777: (1, "powershell.exe")}))
        self.assertEqual(row["liveness"]["state"], laneopen.L_WATCHER_GONE)
        self.assertTrue(row["liveness"]["nobody_listening"])
        self.assertEqual(row["verdict"], laneopen.OPEN_NO_LIVENESS)


class RunningPastTheBrief(Estate):
    """Trap 14's positive signature, and ``webapp/0250``'s mtime rule kept."""

    def setUp(self):
        super().setUp()
        self.write_log(up(self.lane),
                       line(self.lane, "20:05:00", "START 0010-planted.md"))
        self.write_pid(4242)

    def test_a_newer_heading_for_another_id_reads_past_brief(self):
        self.write_lane("# LANE\n\n## TASK 0010 - the dispatched one\n\nx\n\n"
                        "## TASK 0020 - written past the brief\n\ny\n",
                        when=datetime.datetime(2026, 10, 16, 20, 42, 2))
        row = self.two_samples()
        self.assertEqual(row["past"]["state"], laneopen.P_FOUND)
        self.assertEqual(row["verdict"], laneopen.OPEN_PAST_BRIEF)

    def test_an_mtime_older_than_the_start_demotes_and_never_promotes(self):
        # webapp/0250's rule, and the reason the leg reads the mtime at all:
        # these files are appended to, so one older than the START was not
        # appended to since it. The SAME file content, dated before.
        self.write_lane("# LANE\n\n## TASK 0010 - the dispatched one\n\nx\n\n"
                        "## TASK 0020 - written past the brief\n\ny\n",
                        when=datetime.datetime(2026, 10, 16, 20, 1, 0))
        row = self.two_samples()
        self.assertEqual(row["past"]["state"], laneopen.P_NONE)
        self.assertEqual(row["verdict"], laneopen.OPEN_ALIVE)

    def test_a_newer_heading_for_the_dispatched_id_is_not_past_brief(self):
        self.write_lane("# LANE\n\n## TASK 0010 - the dispatched one\n\nx\n",
                        when=datetime.datetime(2026, 10, 16, 20, 42, 2))
        row = self.two_samples()
        self.assertEqual(row["verdict"], laneopen.OPEN_ALIVE)

    def test_an_artefact_naming_another_id_reads_past_brief(self):
        path = os.path.join(self.root, "%s-0020-entry.md" % self.lane)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("x")
        stamp = datetime.datetime(2026, 10, 16, 20, 42, 2).timestamp()
        os.utime(path, (stamp, stamp))
        row = self.two_samples()
        self.assertEqual(row["past"]["state"], laneopen.P_FOUND)
        self.assertEqual([w["task_id"] for w in row["past"]["writes"]], ["20"])
        self.assertEqual(row["verdict"], laneopen.OPEN_PAST_BRIEF)

    def test_an_artefact_for_ANOTHER_lane_is_not_charged_to_this_one(self):
        # Lane names contain hyphens, so the prefix is matched literally.
        # `qwen-coder-0030` is not lane `qwen` task `coder`.
        path = os.path.join(self.root, "someoneelse-0020-entry.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("x")
        stamp = datetime.datetime(2026, 10, 16, 20, 42, 2).timestamp()
        os.utime(path, (stamp, stamp))
        row = self.two_samples()
        self.assertEqual(row["verdict"], laneopen.OPEN_ALIVE)

    def test_a_task_folder_is_only_charged_to_a_lane_that_dispatched_that_id(self):
        # `TASK-0399\\` carries no lane in its name. The suppression lane
        # dispatched 0399, so it answers for suppression and for nobody else.
        folder = os.path.join(self.root, "TASK-0020")
        os.makedirs(folder)
        stamp = datetime.datetime(2026, 10, 16, 20, 42, 2).timestamp()
        os.utime(folder, (stamp, stamp))
        self.assertEqual(self.two_samples()["verdict"], laneopen.OPEN_ALIVE)
        # Now the lane has 0020 in its own queue, so the folder is its own.
        open(os.path.join(self.root, "queue", self.lane, "0020-next.md"),
             "w").close()
        os.utime(folder, (stamp, stamp))
        self.assertEqual(self.two_samples()["verdict"],
                         laneopen.OPEN_PAST_BRIEF)

    def test_the_question_is_not_asked_where_liveness_is_unproven(self):
        # An unasked question is not a negative answer, and asking it would
        # walk the estate once per idle lane on every render.
        self.write_lane("# LANE\n\n## TASK 0020 - written past the brief\n\ny\n",
                        when=datetime.datetime(2026, 10, 16, 20, 42, 2))
        row = self.only_open(probe=Probe(blind=True))
        self.assertEqual(row["past"]["state"], laneopen.P_NOT_ASKED)
        self.assertEqual(row["verdict"], laneopen.OPEN_UNDETERMINED)

    def test_an_unreadable_lane_file_leaves_the_row_plain_alive(self):
        os.remove(self.lane_file)
        row = self.two_samples()
        self.assertEqual(row["verdict"], laneopen.OPEN_ALIVE)
        self.assertTrue(row["past"]["unread"])


class TheVocabularyIsItsOwn(unittest.TestCase):
    """No landing word and no board verdict is reused, by assertion."""

    def test_no_verdict_here_collides_with_a_landing_verdict(self):
        from src import lanerework
        mine = set(laneopen.OPEN_ORDER)
        theirs = set(lanerework.LANDING_ORDER) | set(lanerework.VERDICT_ORDER)
        self.assertEqual(mine & theirs, set())

    def test_no_verdict_here_collides_with_a_lane_board_verdict(self):
        self.assertEqual(set(laneopen.OPEN_ORDER) & set(lanes.VERDICT_TEXT),
                         set())

    def test_every_verdict_carries_a_label_a_why_and_a_remedy(self):
        for verdict in laneopen.OPEN_ORDER:
            self.assertIn(verdict, laneopen.OPEN_TEXT)
            self.assertIn(verdict, laneopen.WHAT_TO_DO)
            self.assertTrue(laneopen.OPEN_TEXT[verdict][1].strip())
            self.assertTrue(laneopen.WHAT_TO_DO[verdict].strip())

    def test_the_no_liveness_remedy_refuses_a_re_queue_first(self):
        # Trap 1: re-queuing is what loses the work. The only cell on this
        # page that could invite one has to say so in its own words.
        remedy = laneopen.WHAT_TO_DO[laneopen.OPEN_NO_LIVENESS].upper()
        self.assertIn("DO NOT RE-QUEUE", remedy)

    def test_describe_names_every_verdict_and_every_liveness_reading(self):
        described = laneopen.describe()
        self.assertEqual({row["verdict"] for row in described["verdicts"]},
                         set(laneopen.OPEN_ORDER))
        self.assertEqual({row["state"] for row in described["liveness"]},
                         set(laneopen.LIVENESS_GROUP))


class TheControlsRefuseTheColumn(Estate):
    """C6: the column does not print unless C1, C2 and C4 are observed."""

    def test_an_estate_with_no_open_row_fails_all_three(self):
        checks = laneopen.controls([{"open": []}])
        self.assertEqual([check["ok"] for check in checks],
                         [False, False, False])

    def test_the_blinded_probe_satisfies_c4_on_its_own(self):
        checks = {check["name"]: check for check in
                  laneopen.controls([{"open": []}],
                                    probe_blind=laneopen.OPEN_UNDETERMINED)}
        self.assertTrue(checks["C4"]["ok"])
        self.assertFalse(checks["C1"]["ok"])

    def test_a_broken_blinded_probe_does_not_satisfy_c4(self):
        checks = {check["name"]: check for check in
                  laneopen.controls([{"open": []}],
                                    probe_blind=laneopen.OPEN_ALIVE)}
        self.assertFalse(checks["C4"]["ok"])

    def test_an_estate_holding_all_three_states_passes(self):
        self.write_log(up(self.lane, timeout="90m"),
                       line(self.lane, "14:05:00", "START 0010-dead.md"),
                       line(self.lane, "20:05:00", "START 0020-live.md"))
        self.write_pid(4242)
        samples = {}
        self.row(probe=self.alive_probe(cpu=10.0), samples=samples)
        cell = self.row(now=NOW + datetime.timedelta(seconds=30),
                        probe=self.alive_probe(cpu=31.0),
                        samples=samples)["open_start"]
        checks = {check["name"]: check for check in
                  laneopen.controls([cell],
                                    probe_blind=laneopen.OPEN_UNDETERMINED)}
        self.assertTrue(checks["C1"]["ok"], cell["open"])
        self.assertTrue(checks["C2"]["ok"], cell["open"])
        self.assertTrue(checks["C4"]["ok"])


if __name__ == "__main__":
    unittest.main()
