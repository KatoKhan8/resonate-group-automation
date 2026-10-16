#!/usr/bin/env python3
"""The suite that died four minutes in, and the lane that waited for it.

WHAT THIS IS ABOUT, measured 2026-10-16 and not hypothesised. Twice inside
ninety minutes a suite's fate and its launcher's knowledge came apart, in
OPPOSITE directions, and nothing in this estate could name either event.

    06:16:47  pilotcaps/0234b takes the suite lock under pid 83736 and
              launches a suite. At 06:20:08 the watcher logs
              `DONE 0234b-...md -> exit0` and the session ends - its final
              report opening "Suite is 3 minutes in (654 KB of 4.57 MB
              expected). I'll wait for its completion notification."
              There is no notification. The suite was already dying, and
              its lock is STILL stranded as this test is written.

    04:44     suppression/0220 launches a suite under pid 79556 and logs
              `DONE 0220-...md -> exit0` at 04:45:37 - 81 seconds later.
              The run took 51m05s, finished at 05:35:20.7 and RELEASED ITS
              LOCK CLEANLY. Two further sessions had come and gone before
              the result existed.

ORPHAN CANNOT STAND IN FOR THIS, AND THAT IS WHAT C1 AND C2 TOGETHER PROVE.
`src.lanes` already names ORPHAN - a lock whose holder is dead - and
`webapp/0140` built it. ORPHAN is a fact about a LOCK. DIED-UNREAD is a fact
about a SESSION, and the first instance above has both while the second has
only the second. A panel carrying one state for both would have reported the
0220 run as healthy: its lock was released, on time, by the book.

SIX CONTROLS, AND EACH IS PROVEN ABLE TO FAIL. A control that cannot go red
licenses nothing, and this repository has shipped more than one that could not.

    C1  the 0234b instance, replayed from the real log lines: DIED-UNREAD,
        and the lock said to be STRANDED
    C2  the 0220 instance, replayed: DIED-UNREAD with the lock RELEASED
        CLEANLY. C1 and C2 together are the independence proof; either alone
        proves a classifier that conflates the two axes
    C3  a launch whose launcher demonstrably recorded the result:
        FINISHED-READ. Without C3 this panel can only ever say every suite
        was abandoned
    C4  a launch with no identifiable launcher: UNKNOWN, and none of the
        other three
    C5  the paired control. Everything-DIED-UNREAD must kill C3;
        nothing-DIED-UNREAD must kill C1 and C2. Both directions, two named
        kill-sets
    C6  a first render with no prior CPU sample and an empty sample store:
        DIED-UNREAD and ORPHAN both still visible. `0140` departed from its
        own brief for exactly this reason - a delta-based rule hides the one
        state the panel exists for on every first page load

AND THE BOUNDARY. Two tests walk a fixture estate and the lock's own
directory before and after a render and require every file byte-identical,
because the evidence this panel reads is exactly what a second writer
destroys.

WHY C3 IS A RECONSTRUCTION AND SAYS SO. The real estate holds the instance
C3 describes - `suppression/0110` launched a suite that landed at 23:06:37
and closed at 23:07:58, 81 seconds later, and its own `.out` discusses the
233 real names in that result. It is UNPLACEABLE TODAY, because at 08:05:52
on 2026-10-16 a lane archiving artefacts wrote a byte-identical copy of that
verdict and a verdict carries no timestamp, so its only clock is an mtime
and the copy contradicted it. 15 of 20 distinct verdicts under `logs/` are in
that state. C3 is therefore that instance as it stood before its clock was
destroyed, which is the thing the panel has to be able to render.
"""
import datetime
import hashlib
import json
import os
import shutil
import tempfile
import unittest

from src import lanes
from src import suitefate as sf
from src.web import api
from src.web import pages


#: A pid that cannot be a live process on this machine. Windows pids are
#: bounded well below this.
IMPOSSIBLE_PID = 0x7FFFFFF0

#: The real pids, kept as the real numbers so a reader of this file can grep
#: them in `resonate-ops\logs\` and find the same two events.
PID_0234B = 83736
PID_0220 = 79556
PID_0110 = 65100


class Probe:
    """A process table presented without starting processes.

    The same seam `src.lanes` already reads through. `table=None` is the
    platform this has no reader for, which must make liveness UNKNOWN rather
    than dead - a holder is never called dead on a failed read.
    """

    def __init__(self, table=None, readable=True):
        self._table = {} if table is None else dict(table)
        self._readable = readable

    def table(self):
        return dict(self._table) if self._readable else None

    def cpu(self, pid):
        return None


class Estate:
    """A lane estate on disk: `queue/<lane>/`, a watcher log, `.out` files.

    Every watcher line written by the helpers below is a VERBATIM line from
    `resonate-ops\\logs\\watcher-<lane>.log`, quoted in the control that uses
    it. A fixture that paraphrased the format would be testing a format
    nothing writes.
    """

    def setUp(self):                                           # noqa: N802
        self.home = tempfile.mkdtemp(prefix="suitefate-")
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.logs = os.path.join(self.home, "logs")
        os.makedirs(self.logs)
        self.work = os.path.join(self.home, "work")
        os.makedirs(self.work)
        self.lock = os.path.join(self.work, "suite.lock")
        self.lines = {}

    # ----------------------------------------------------------- authoring

    def lane(self, name, tree=None):
        """A lane with a queue folder and a watcher `up` line.

        The `up` line is the one authority for which tree belongs to which
        lane, so the fixture has to carry one or `_lane_trees` will - rightly
        - refuse to map anything.
        """
        os.makedirs(os.path.join(self.home, "queue", name), exist_ok=True)
        tree = tree or os.path.join("C:\\", "trees", "wt-%s" % name)
        self.lines.setdefault(name, []).append(
            "[2026-10-15 01:30:47] [%s] watcher up. worktree=%s "
            "mode=bypassPermissions timeout=90m" % (name, tree))
        return tree

    def session(self, lane, brief, start, done=None, suffix="exit0",
                out=""):
        """A START, an optional DONE, and the `.out` the watcher writes.

        `done=None` is a session that has not closed - the only thing that
        may make a fate RUNNING - and it writes no DONE line, exactly as the
        real log holds none for a task still in flight.
        """
        self.lines.setdefault(lane, []).append(
            "[%s] [%s] START %s" % (start, lane, brief))
        if done is not None:
            self.lines[lane].append(
                "[%s] [%s] DONE  %s -> %s" % (done, lane, brief, suffix))
        stamp = datetime.datetime.strptime(
            start, "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d-%H%M%S")
        with open(os.path.join(self.logs, "task-%s-%s.out" % (lane, stamp)),
                  "w", encoding="utf-8") as handle:
            handle.write(out)

    def flush(self):
        """Write each lane's watcher log, BOM first.

        All seven real logs begin with a UTF-8 BOM because
        `Add-Content -Encoding UTF8` under Windows PowerShell 5.1 writes one,
        and `lanes._read_tail` strips exactly one. A fixture without it would
        be testing a file shape this estate does not have.
        """
        for lane, lines in self.lines.items():
            with open(os.path.join(self.logs, "watcher-%s.log" % lane),
                      "w", encoding="utf-8") as handle:
                handle.write("\ufeff" + "\n".join(lines) + "\n")

    def verdict(self, name, tree, wall, mtime, failures=228,
                status="FAIL", copies=()):
        """A `run_suite` verdict, in `build_verdict`'s own four-plus key shape.

        `copies` are additional paths holding the SAME BYTES at DIFFERENT
        mtimes - which is the whole copy hazard, and the reason `artefacts`
        groups by content rather than by path.
        """
        text = ("status=%s\nexit_code=1\nwall_seconds=%s\ntimed_out=False\n"
                "log_file=%s\nresults_reached=14657\nfailures=%d\n"
                "failures_are_partial=False\n"
                % (status, wall, os.path.join(tree, "scripts",
                                              "suite_run.log"), failures))
        written = []
        for path, when in [(name, mtime)] + list(copies):
            full = os.path.join(self.logs, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as handle:
                handle.write(text)
            stamp = when.timestamp()
            os.utime(full, (stamp, stamp))
            written.append(full)
        return written

    def lock_free(self):
        """No lock file at all, which is what a clean release looks like later.

        WHY NOT A LOCK NAMING SOMEBODY ELSE. A lock file naming a usable pid
        IS A LAUNCH, so parking one to make some other launch read RELEASED
        invents a second launch row - belonging to no lane, classified
        UNKNOWN - and every estate total in the test then counts it. That is
        how a mutation making an unplaceable launch read FINISHED-READ was
        able to redden C3, which is a fixture artefact and not a finding.
        An absent lock gives the same RELEASED answer and adds no row.
        """
        assert not os.path.exists(self.lock)

    def write_lock(self, **fields):
        """A holder's payload, in `suitelock.acquire`'s own shape."""
        payload = {"pid": 4242, "branch": "task-something",
                   "worktree": os.path.join("C:\\", "trees", "wt-thing"),
                   "queued_at": "2026-10-16T06:16:47",
                   "started_at": "2026-10-16T06:16:47",
                   "lock_path": self.lock}
        payload.update(fields)
        with open(self.lock, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return payload

    # ------------------------------------------------------------ reading

    def read(self, probe=None, now=None, lock=True):
        probe = probe if probe is not None else Probe()
        return sf.panel(root=self.home, probe=probe, table=probe.table(),
                        now=now or datetime.datetime(2026, 10, 16, 8, 30, 0),
                        lock_path=self.lock if lock else
                        os.path.join(self.work, "no-such.lock"))

    def rendered(self, probe=None, now=None, lock=True):
        """The real page, through the real assembler. Never a hand-built dict.

        `api.lane_suite_fates` is what attaches the label and the colour, so
        a test that called `pages` on a dict of its own would not be able to
        see a fate the assembler has no words for.
        """
        probe = probe if probe is not None else Probe()
        data = api.lane_suite_fates(
            root=self.home, probe=probe, table=probe.table(),
            now=now or datetime.datetime(2026, 10, 16, 8, 30, 0),
            lock_path=self.lock if lock else
            os.path.join(self.work, "no-such.lock"))
        return data, pages.lane_suite_fates(data)

    def only(self, data, lane=None, pid=None, source=None):
        """The one row matching, failing loudly rather than returning None.

        `source` matters more than it looks: a fixture that writes a lock in
        order to make SOME OTHER launch's lock read RELEASED thereby creates
        a second launch row - the lock's own holder. Selecting by lane alone
        then silently picks whichever came first, which is how a control
        starts asserting about the wrong row.
        """
        found = [r for r in data["rows"]
                 if (lane is None or r["lane"] == lane)
                 and (pid is None or r["pid"] == pid)
                 and (source is None or r["source"] == source)]
        assert len(found) == 1, (
            "expected exactly one row for lane=%r pid=%r source=%r, got %d: %r"
            % (lane, pid, source, len(found),
               [(r["lane"], r["pid"], r["source"], r["fate"])
                for r in data["rows"]]))
        return found[0]

    # --------------------------------------------- the two real instances

    def the_0234b_instance(self):
        """pilotcaps/0234b: a suite killed four minutes in, lock stranded.

        The two watcher lines are verbatim:

            [2026-10-16 06:01:58] [pilotcaps] START 0234b-the-line-no-test-reaches.md
            [2026-10-16 06:20:08] [pilotcaps] DONE  0234b-the-line-no-test-reaches.md -> exit0

        and the `.out`'s first line is verbatim too. There is NO verdict,
        because the process was killed before `run_suite` could write one -
        which the stranded lock proves, `release()` being in a `finally`.
        """
        tree = self.lane("pilotcaps",
                         os.path.join("C:\\", "Users", "Zvonimir", "Desktop",
                                      "wt-pilotcaps-2026-10-14"))
        self.session(
            "pilotcaps", "0234-second-observer-on-the-collision-repair.md",
            "2026-10-16 05:43:27", "2026-10-16 06:01:53")
        self.session(
            "pilotcaps", "0234b-the-line-no-test-reaches.md",
            "2026-10-16 06:01:58", "2026-10-16 06:20:08",
            out="Suite is 3 minutes in (654 KB of 4.57 MB expected). "
                "I'll wait for its completion notification.")
        self.session(
            "pilotcaps", "0234c-the-revert-that-rewrote-the-index.md",
            "2026-10-16 06:20:13", "2026-10-16 06:38:46")
        self.write_lock(pid=PID_0234B, worktree=tree,
                        branch="task-pilotcaps-pool-readback-2026-10-16",
                        queued_at="2026-10-16T06:16:47",
                        started_at="2026-10-16T06:16:47")
        return tree

    def the_0220_instance(self):
        """suppression/0220: a 51-minute suite launched 81s before closing.

        Verbatim lines:

            [2026-10-16 04:30:27] [suppression] START 0220-the-failure-nobody-would-ever-see.md
            [2026-10-16 04:45:37] [suppression] DONE  0220-the-failure-nobody-would-ever-see.md -> exit0

        and the announcement sentence from its `.out`, verbatim, which is the
        only thing in this estate that ties pid 79556 to the session that
        launched it.
        """
        tree = self.lane("suppression",
                         os.path.join("C:\\", "Users", "Zvonimir", "Desktop",
                                      "wt-suppression-2026-10-14"))
        self.session(
            "suppression", "0210-the-citation-that-was-typed.md",
            "2026-10-16 04:22:30", "2026-10-16 04:30:22")
        self.session(
            "suppression", "0220-the-failure-nobody-would-ever-see.md",
            "2026-10-16 04:30:27", "2026-10-16 04:45:37",
            out="So instead of holding idle I took the suite debt this "
                "branch has been carrying for four commits: the lock was "
                "free, and the branch's full suite is running now under pid "
                "79556 with `-v`, unpiped, env-clean.")
        self.session(
            "suppression", "0230-the-suite-that-outlived-its-session.md",
            "2026-10-16 04:54:22", "2026-10-16 05:05:00",
            out="I'm holding for the run rather than ending with it in "
                "flight - a monitor is armed on every terminal state.")
        # The artefact as `suppression/0260` filed it: pid in the NAME,
        # because `build_verdict` cannot write one.
        self.verdict(
            os.path.join("TASK-0260",
                         "suite-verdict-0260-pid79556-2026-10-16T0444.txt"),
            tree, "3064.7", datetime.datetime(2026, 10, 16, 5, 57, 47),
            failures=228,
            copies=[(os.path.join("TASK-0320", "copies", "verdict-copy.txt"),
                     datetime.datetime(2026, 10, 16, 8, 5, 53))])
        return tree


# --------------------------------------------------------------------------
# C1 AND C2: THE TWO THAT MUST BE ABLE TO DISAGREE ABOUT THE LOCK


class TheTwoInstancesThatCameApartInOppositeDirections(unittest.TestCase,
                                                        Estate):
    """DIED-UNREAD with a stranded lock, and DIED-UNREAD without one."""

    setUp = Estate.setUp

    def test_C1_the_0234b_instance_is_died_unread_and_names_the_lock(self):
        tree = self.the_0234b_instance()
        self.flush()
        data = self.read(Probe(table={9: (0, "python.exe")}))
        row = self.only(data, lane="pilotcaps")

        self.assertEqual(row["fate"], sf.FATE_DIED_UNREAD)
        # THE SECOND AXIS, and C1's whole point beside C2: this one IS
        # stranded, and the panel says so in its own column.
        self.assertEqual(row["lock_disposition"], sf.LOCKD_STRANDED)
        self.assertEqual(row["launcher"],
                         "0234b-the-line-no-test-reaches.md")
        self.assertEqual(row["pid"], PID_0234B)
        self.assertEqual(row["source"], "lock")
        # The launch time came from the lock's own content, which no file
        # copy can move.
        self.assertEqual(row["launch_clock"], sf.TIME_LOCK)
        self.assertEqual(row["launch_at"],
                         datetime.datetime(2026, 10, 16, 6, 16, 47))
        # And it is attributed to the session the launch fell INSIDE, not to
        # the one that happened to be open when somebody looked.
        self.assertEqual(row["launcher_done"],
                         datetime.datetime(2026, 10, 16, 6, 20, 8))
        self.assertIn("killed before it could write a verdict", row["why"])

    def test_C1_the_stranded_lock_is_rendered_as_a_stranded_lock(self):
        self.the_0234b_instance()
        self.flush()
        _data, html = self.rendered(Probe(table={9: (0, "python.exe")}))
        self.assertIn("DIED UNREAD", html)
        self.assertIn("LOCK STRANDED", html)
        self.assertIn("0234b-the-line-no-test-reaches.md", html)

    def test_C2_the_0220_instance_is_died_unread_with_a_clean_lock(self):
        self.the_0220_instance()
        self.flush()
        # The lock names SOMEBODY ELSE, which is what a clean release looks
        # like from a later reader's position.
        self.write_lock(pid=11111,
                        worktree=os.path.join("C:\\", "trees", "wt-other"))
        data = self.read(Probe(table={11111: (0, "python.exe")}))
        row = self.only(data, lane="suppression")

        self.assertEqual(row["fate"], sf.FATE_DIED_UNREAD)
        # THE INDEPENDENCE, as an assertion rather than a claim: same fate as
        # C1, opposite lock.
        self.assertEqual(row["lock_disposition"], sf.LOCKD_RELEASED)
        self.assertEqual(row["launcher"],
                         "0220-the-failure-nobody-would-ever-see.md")
        self.assertEqual(row["pid"], PID_0220)
        # Attributed BY PID, from the announcement in its own `.out` - not by
        # a clock, because this artefact's mtime is contradicted by a copy.
        self.assertEqual(row["attributed_by"], sf.BY_PID)
        self.assertEqual(row["result_clock"], sf.TIME_CLOBBERED)
        # THE PROOF USED NO FILE TIMESTAMP AT ALL. The session lived 15m10s
        # and the suite took 51m05s, so the result cannot have existed before
        # the session closed whatever any mtime says.
        self.assertIn("wall_seconds", row["why"])
        self.assertIn("15m10s", row["why"])
        self.assertIn("51m05s", row["why"])

    def test_an_uncontradicted_clock_also_proves_a_late_landing(self):
        """DIED-UNREAD by the clock, which is a different route from C2's.

        C2 needs no file timestamp: the suite outlasted the session, so the
        arithmetic settles it. THIS one is the case where the arithmetic
        cannot - the run is shorter than the session - and the only thing
        that settles it is an mtime NOTHING CONTRADICTS. A single surviving
        copy of a verdict is the one condition under which this reader will
        charge a launch as unread on a timestamp, and without a control the
        whole route is unwatched.
        """
        tree = self.lane("suppression",
                         os.path.join("C:\\", "Users", "Zvonimir", "Desktop",
                                      "wt-suppression-2026-10-14"))
        # A thirty-minute session that launched a ten-minute suite twenty-five
        # minutes in: the arithmetic permits a finish before the close, and
        # the clock says it did not happen.
        self.session("suppression", "0300-a-short-run-near-the-end.md",
                     "2026-10-16 07:00:00", "2026-10-16 07:30:00",
                     out="launched the branch suite under pid 90001")
        self.verdict("suite-verdict-pid90001.txt", tree, "600.0",
                     datetime.datetime(2026, 10, 16, 7, 35, 0))
        self.flush()
        self.lock_free()
        data = self.read(Probe(table={11111: (0, "python.exe")}))
        row = self.only(data, lane="suppression", source="verdict")

        self.assertEqual(row["fate"], sf.FATE_DIED_UNREAD)
        self.assertEqual(row["result_clock"], sf.TIME_MTIME)
        self.assertIn("no copy of that artefact", row["why"])
        # And the arithmetic route did NOT fire - the session was long enough
        # for the run, which is what makes this a test of the clock.
        self.assertNotIn("wall_seconds", row["why"])

    def test_C1_and_C2_together_are_the_independence_proof(self):
        """Both fates DIED-UNREAD; one lock stranded, one released.

        This is the test the brief asked for by name, and it is the reason
        ORPHAN could not simply have been reused: on this estate the two
        axes take all four combinations they are capable of, and a single
        state would have had to pick one.
        """
        self.the_0234b_instance()
        self.the_0220_instance()
        self.flush()
        data = self.read(Probe(table={9: (0, "python.exe")}))
        unread = [r for r in data["rows"] if r["fate"] == sf.FATE_DIED_UNREAD]
        self.assertEqual(len(unread), 2, [r["lane"] for r in data["rows"]])
        self.assertEqual(
            {r["lane"]: r["lock_disposition"] for r in unread},
            {"pilotcaps": sf.LOCKD_STRANDED,
             "suppression": sf.LOCKD_RELEASED})
        self.assertEqual(data["unread_lock_stranded"], 1)
        self.assertEqual(data["unread_lock_released"], 1)
        _d, html = self.rendered(Probe(table={9: (0, "python.exe")}))
        # And the page states it, so a person reading the screen is told the
        # two columns are not two views of one fact.
        self.assertIn("MEASURED INDEPENDENT", html.upper())

    def test_the_independence_banner_is_absent_when_it_does_not_hold(self):
        """A claim the data does not support may not be printed anyway.

        A mutation run proved this unwatched: forcing the banner on made no
        control fail. The banner says the two states were MEASURED
        independent, and on an estate holding only the stranded kind that
        sentence is false - and worse than merely false, because it is the
        page's own evidence that ORPHAN could not have been reused. A claim
        printed unconditionally is decoration.
        """
        self.the_0234b_instance()          # stranded only, no clean release
        self.flush()
        data, html = self.rendered(Probe(table={9: (0, "python.exe")}))
        self.assertEqual(data["unread_lock_stranded"], 1)
        self.assertEqual(data["unread_lock_released"], 0)
        self.assertIs(data["independent"], False)
        self.assertNotIn("MEASURED INDEPENDENT", html.upper())
        # The state itself is still on the page - withholding the banner is
        # not withholding the finding.
        self.assertIn("DIED UNREAD", html)
        self.assertIn("LOCK STRANDED", html)


# --------------------------------------------------------------------------
# C3: THE ONE WITHOUT WHICH THIS PANEL ONLY EVER SAYS "ABANDONED"


class ALaunchWhoseLauncherDidRecordTheResult(unittest.TestCase, Estate):
    """FINISHED-READ, reconstructed from the instance that really happened."""

    setUp = Estate.setUp

    def the_0110_instance(self, clobber=False):
        """suppression/0110: a result that landed 81 seconds before close.

        Verbatim lines:

            [2026-10-15 21:51:36] [suppression] START 0110-the-bounce-gate-and-the-other-two.md
            [2026-10-15 23:07:58] [suppression] DONE  0110-the-bounce-gate-and-the-other-two.md -> exit0

        `clobber=True` adds the byte-identical copy that a lane archiving
        artefacts really did write at 08:05:52 on 2026-10-16, and which is
        why this instance is UNPLACEABLE in the live estate today.
        """
        tree = self.lane("suppression",
                         os.path.join("C:\\", "Users", "Zvonimir", "Desktop",
                                      "wt-suppression-2026-10-14"))
        self.session(
            "suppression", "0100-apply-the-three.md",
            "2026-10-15 21:35:16", "2026-10-15 21:47:31")
        self.session(
            "suppression", "0110-the-bounce-gate-and-the-other-two.md",
            "2026-10-15 21:51:36", "2026-10-15 23:07:58",
            out="The run landed and I read it: the verdict is filed at "
                "verdict-233-task-suppression-9bd8648f5.txt and carries 234 "
                "names, of which the 233rd is real - a module-level "
                "`lint._POLICY_CACHE` leak.")
        copies = ([(os.path.join("TASK-0320", "copies", "v.txt"),
                    datetime.datetime(2026, 10, 16, 8, 5, 52))]
                  if clobber else [])
        self.verdict("verdict-233-task-suppression-9bd8648f5.txt", tree,
                     "3454.5", datetime.datetime(2026, 10, 15, 23, 6, 37),
                     failures=234, copies=copies)
        return tree

    def test_C3_a_result_read_by_its_launcher_is_FINISHED_READ(self):
        self.the_0110_instance()
        self.flush()
        self.lock_free()
        data = self.read(Probe(table={11111: (0, "python.exe")}))
        row = self.only(data, lane="suppression")

        self.assertEqual(row["fate"], sf.FATE_FINISHED_READ)
        self.assertEqual(row["launcher"],
                         "0110-the-bounce-gate-and-the-other-two.md")
        self.assertIs(row["recorded"], True)
        # The corroboration is SPECIFIC, and the test says which marker fired
        # rather than accepting that something did. "The word suite appears"
        # would make every session in this estate a reader.
        self.assertIn("verdict-233-task-suppression-9bd8648f5",
                      row["recorded_why"])
        self.assertEqual(data["read"], 1)
        self.assertEqual(data["unread"], 0)

    def test_C3_renders_as_read_and_the_lane_row_says_zero_of_one(self):
        self.the_0110_instance()
        self.flush()
        self.lock_free()
        _data, html = self.rendered(Probe(table={11111: (0, "python.exe")}))
        self.assertIn("RESULT READ", html)
        # A ZERO THAT MEANS SOMETHING GOOD, worded so it cannot be confused
        # with a lane that told this reader nothing. See the zero control.
        self.assertIn("0 of 1 unread", html)
        self.assertNotIn("NO LAUNCH READABLE</span>", html)

    def test_a_result_that_landed_in_time_and_was_not_written_down(self):
        """LANDED, NO RECORD - and it is neither of the two it sits between.

        THE STATE WITHOUT WHICH `_recorded` IS WATCHED BY NOTHING. The same
        instance as C3, with a session whose final report never mentions the
        result. It may not become FINISHED-READ, because nothing says anybody
        looked; and it may not become DIED-UNREAD, because the session had
        the result in hand for 81 seconds. Both of those would be a real
        misreport: the first flatters the estate and the second slanders a
        session that did its job.
        """
        tree = self.lane("suppression",
                         os.path.join("C:\\", "Users", "Zvonimir", "Desktop",
                                      "wt-suppression-2026-10-14"))
        self.session(
            "suppression", "0110-the-bounce-gate-and-the-other-two.md",
            "2026-10-15 21:51:36", "2026-10-15 23:07:58",
            out="Four briefs done, lane entries appended, branch pushed.")
        self.verdict("verdict-233-task-suppression-9bd8648f5.txt", tree,
                     "3454.5", datetime.datetime(2026, 10, 15, 23, 6, 37),
                     failures=234)
        self.flush()
        self.lock_free()
        data = self.read(Probe(table={11111: (0, "python.exe")}))
        row = self.only(data, lane="suppression", source="verdict")

        self.assertEqual(row["fate"], sf.FATE_LANDED_UNRECORDED)
        self.assertNotEqual(row["fate"], sf.FATE_FINISHED_READ)
        self.assertNotEqual(row["fate"], sf.FATE_DIED_UNREAD)
        self.assertIs(row["recorded"], False)
        self.assertIn("nothing in this session's record names this result",
                      row["recorded_why"])
        # It is in the denominator and in neither the read nor the unread
        # numerator, so it cannot quietly improve either rate.
        self.assertEqual(data["decided"], 1)
        self.assertEqual(data["read"], 0)
        self.assertEqual(data["unread"], 0)
        _d, html = self.rendered(Probe(table={11111: (0, "python.exe")}))
        self.assertIn("LANDED, NO RECORD", html)

    def test_the_archival_copy_is_what_made_this_instance_unplaceable(self):
        """The same instance, with the copy that really exists: UNKNOWN.

        Not DIED-UNREAD. The earliest surviving mtime is an UPPER BOUND on
        the write time once a copy contradicts it, and an upper bound later
        than the session's close proves nothing in either direction. Charging
        this launch as unread would be inventing a late landing out of a
        destroyed clock.
        """
        self.the_0110_instance(clobber=True)
        self.flush()
        self.lock_free()
        data = self.read(Probe(table={11111: (0, "python.exe")}))
        row = self.only(data, lane="suppression")
        self.assertEqual(row["fate"], sf.FATE_UNKNOWN)
        self.assertNotEqual(row["fate"], sf.FATE_DIED_UNREAD)
        self.assertEqual(row["result_clock"], sf.TIME_CLOBBERED)
        self.assertIn("contradicted by a copy", row["attribution"])


# --------------------------------------------------------------------------
# C4: A LAUNCH NOBODY CAN BE CHARGED WITH


class ALaunchWithNoIdentifiableLauncher(unittest.TestCase, Estate):
    """UNKNOWN, and none of the other three."""

    setUp = Estate.setUp

    def an_unplaceable_launch(self):
        """A verdict whose `log_file` is in no lane's tree.

        This is the shape 15 of the 20 real verdicts have: they ran in a
        Claude session's scratch directory under `Temp`, or in an ad-hoc
        reference tree, months before any watcher existed. There is no lane
        and there is no session.
        """
        self.lane("suppression")
        self.session("suppression", "0010-something.md",
                     "2026-10-16 04:00:00", "2026-10-16 04:10:00")
        self.verdict("reference-231-master-cd8e00bc.verdict.txt",
                     os.path.join("C:\\", "Users", "Zvonimir", "AppData",
                                  "Local", "Temp", "claude", "0cac0b96"),
                     "2111.8", datetime.datetime(2026, 10, 3, 0, 41, 3))

    def test_C4_an_unplaceable_launch_is_UNKNOWN_and_nothing_else(self):
        self.an_unplaceable_launch()
        self.flush()
        self.lock_free()
        data = self.read(Probe(table={11111: (0, "python.exe")}))
        row = self.only(data, lane=None, source="verdict")

        self.assertEqual(row["fate"], sf.FATE_UNKNOWN)
        # ALL THREE, NAMED. Asserting only `== UNKNOWN` would pass under a
        # mutation that made UNKNOWN an alias of one of the others.
        self.assertNotEqual(row["fate"], sf.FATE_FINISHED_READ)
        self.assertNotEqual(row["fate"], sf.FATE_DIED_UNREAD)
        self.assertNotEqual(row["fate"], sf.FATE_LANDED_UNRECORDED)
        self.assertIsNone(row["lane"])
        self.assertIsNone(row["launcher"])
        # It counts in no numerator and in no denominator of read-vs-unread.
        self.assertEqual(data["read"], 0)
        self.assertEqual(data["unread"], 0)
        self.assertEqual(data["decided"], 0)
        self.assertEqual(data["unknown"], 1)

    def test_C4_the_hole_is_published_rather_than_absorbed(self):
        self.an_unplaceable_launch()
        self.flush()
        data, html = self.rendered(Probe(table={11111: (0, "python.exe")}))
        self.assertEqual(data["hole"], 1)
        self.assertEqual(data["hole_share"], 100.0)
        self.assertIn("could not be placed at all", html)
        # And the lane with launches but none placeable is NOT shown as a
        # lane with nothing to report.
        self.assertIn("no lane", html)

    def test_a_launch_in_a_gap_between_two_sessions_is_UNKNOWN(self):
        """The watcher's five-second gap is not the next session's work.

        A launch landing between a DONE and the next START belongs to
        neither session, and `_session_at` must return None rather than the
        nearest one. Measured on the real estate: a glm-c verdict sits five
        seconds after that lane's DONE at 03:34:11.
        """
        tree = self.lane("glm-c")
        self.session("glm-c", "0060-apply-the-four-trims.md",
                     "2026-10-15 03:24:48", "2026-10-15 03:34:11")
        self.session("glm-c", "0070-apply-the-trims-mechanically.md",
                     "2026-10-15 03:44:56", "2026-10-15 04:06:54")
        self.verdict("baseline_console.txt", tree, "0.0",
                     datetime.datetime(2026, 10, 15, 3, 34, 16),
                     status="INCOMPLETE", failures=0)
        self.flush()
        self.lock_free()
        data = self.read(Probe(table={11111: (0, "python.exe")}))
        row = self.only(data, lane="glm-c")
        self.assertEqual(row["fate"], sf.FATE_UNKNOWN)
        self.assertIsNone(row["launcher"])

    def test_a_gap_launch_is_not_handed_to_an_older_unclosed_session(self):
        """The gap rule and the newest-first rule are two different guards.

        A mutation run proved it: with the walk reversed, replacing the gap's
        `return None` with `continue` changes nothing SO LONG AS every older
        session is closed, because sessions are serial and non-overlapping -
        so a `done` earlier than the launch is the only thing an older row
        can have. The one shape where it does matter is a gap launch with a
        STALE UNCLOSED START behind it, which `pilotcaps` really has
        (`0130-certify-the-halt-fix.md`, 10-15 16:02:10, no DONE). Then
        `continue` walks past the gap and hands the launch to a session from
        sixteen hours earlier. Without this control the gap rule is watched
        by nothing.
        """
        tree = self.lane("pilotcaps")
        self.lines["pilotcaps"].append(
            "[2026-10-15 16:02:10] [pilotcaps] START "
            "0130-certify-the-halt-fix.md")
        self.session("pilotcaps", "0234b-the-line-no-test-reaches.md",
                     "2026-10-16 06:01:58", "2026-10-16 06:20:08")
        self.session("pilotcaps", "0234c-the-revert.md",
                     "2026-10-16 06:20:13", "2026-10-16 06:38:46")
        # Five seconds into the gap between the two closed sessions.
        self.verdict("gap-after-0234b.txt", tree, "0.0",
                     datetime.datetime(2026, 10, 16, 6, 20, 10),
                     status="INCOMPLETE", failures=0)
        self.flush()
        self.lock_free()
        data = self.read(Probe(table={11111: (0, "python.exe")}))
        row = self.only(data, lane="pilotcaps", source="verdict")
        self.assertIsNone(row["launcher"])
        self.assertNotEqual(row["launcher"], "0130-certify-the-halt-fix.md")
        self.assertEqual(row["fate"], sf.FATE_UNKNOWN)

    def test_a_launch_with_no_pid_is_never_called_a_clean_release(self):
        """LOCK UNDETERMINED, and specifically not LOCK RELEASED.

        A mutation run proved this guard unwatched. The failure it permits is
        the exact fail-closed violation this panel exists to avoid: a launch
        whose pid nobody recorded would render "LOCK RELEASED - this run
        released it", which is a positive claim about a run nothing here can
        identify. Absence of a pid is absence of an answer.
        """
        tree = self.lane("suppression")
        self.session("suppression", "0110-no-pid-anywhere.md",
                     "2026-10-15 21:51:36", "2026-10-15 23:07:58",
                     out="read it: filed at nopid-verdict.txt")
        self.verdict("nopid-verdict.txt", tree, "3454.5",
                     datetime.datetime(2026, 10, 15, 23, 6, 37),
                     failures=234)
        self.flush()
        self.lock_free()
        data = self.read(Probe(table={11111: (0, "python.exe")}))
        row = self.only(data, lane="suppression", source="verdict")

        self.assertIsNone(row["pid"])
        self.assertEqual(row["lock_disposition"], sf.LOCKD_UNDETERMINED)
        self.assertNotEqual(row["lock_disposition"], sf.LOCKD_RELEASED)
        self.assertIn("no pid could be established", row["lock_why"])
        # And it may not be counted on either side of the independence sum,
        # which is what would make the banner a claim about nothing.
        self.assertEqual(data["unread_lock_released"], 0)
        self.assertEqual(data["unread_lock_stranded"], 0)

    def test_a_stale_unclosed_START_does_not_swallow_later_launches(self):
        """The defect that made the 0234b instance read as STILL OPEN.

        `pilotcaps` really holds `0130-certify-the-halt-fix.md`, STARTed at
        10-15 16:02:10 and never closed by a DONE line - a watcher generation
        boundary. Walking the sessions oldest-first, that stale START matched
        every launch for the following sixteen hours, so the one instance
        this module exists for came back RUNNING. The newest candidate must
        win, and this is the control that says so.
        """
        tree = self.the_0234b_instance()
        self.lines["pilotcaps"].insert(
            1, "[2026-10-15 16:02:10] [pilotcaps] START "
               "0130-certify-the-halt-fix.md")
        self.flush()
        data = self.read(Probe(table={9: (0, "python.exe")}))
        row = self.only(data, lane="pilotcaps")
        self.assertEqual(row["launcher"],
                         "0234b-the-line-no-test-reaches.md")
        self.assertNotEqual(row["launcher"], "0130-certify-the-halt-fix.md")
        self.assertEqual(row["fate"], sf.FATE_DIED_UNREAD)
        self.assertNotEqual(row["fate"], sf.FATE_RUNNING)


# --------------------------------------------------------------------------
# C6: THE FIRST LOAD, WHERE 0140 DEPARTED FROM ITS OWN BRIEF


class AFirstRenderWithNoPriorSample(unittest.TestCase, Estate):
    """DIED-UNREAD and ORPHAN are both visible on a cold first load."""

    setUp = Estate.setUp

    def test_C6_both_states_are_visible_with_an_empty_sample_store(self):
        """Nothing here may depend on having been loaded before.

        `webapp/0140`'s reason for departing from its own brief was that a
        delta-based rule makes the one state a panel exists for invisible on
        every first page load. This panel takes no CPU samples at all - the
        assertion is that the states render with an empty store and a probe
        that answers no CPU for any pid, which is exactly a first load.
        """
        self.the_0234b_instance()
        self.flush()
        probe = Probe(table={9: (0, "python.exe")})

        # The suite-fate panel: DIED-UNREAD, cold.
        data, html = self.rendered(probe)
        self.assertEqual(data["unread"], 1)
        self.assertIn("DIED UNREAD", html)

        # And ORPHAN, from `src.lanes`, on the same cold read with a fresh
        # empty sample store - so the two panels agree on the one holder.
        row = lanes.lock_row(probe=probe, table=probe.table(),
                             now=datetime.datetime(2026, 10, 16, 8, 30, 0),
                             samples={}, file_path=self.lock)
        self.assertEqual(row["state"], lanes.LOCK_ORPHAN)
        lock_html = pages.lane_locks({"locks": {
            "at": datetime.datetime(2026, 10, 16, 8, 30, 0),
            "table_read": True, "rows": [row], "held": 0, "free": 0,
            "orphan": 1, "held_unknown": 0, "unknown": 0,
            "glossary": [{"state": k, "label": a, "why": b}
                         for k, (a, b) in sorted(lanes.LOCK_TEXT.items())]}})
        self.assertIn("ORPHAN", lock_html)

    def test_C6_the_fate_reading_is_identical_on_a_second_call(self):
        """No memoised sample can change the answer between two loads."""
        self.the_0234b_instance()
        self.flush()
        probe = Probe(table={9: (0, "python.exe")})
        first = self.read(probe)
        second = self.read(probe)
        self.assertEqual([r["fate"] for r in first["rows"]],
                         [r["fate"] for r in second["rows"]])
        self.assertEqual(first["unread"], second["unread"])


# --------------------------------------------------------------------------
# A ZERO THAT MEANS NOTHING AND A ZERO THAT MEANS SOMETHING


class AZeroMustNotRenderLikeNoData(unittest.TestCase, Estate):
    """Three lanes, three different zeroes, three different sentences."""

    setUp = Estate.setUp

    def test_three_kinds_of_zero_are_three_different_sentences(self):
        # (a) a lane with nothing readable at all
        self.lane("qwen")
        self.session("qwen", "0010-a.md", "2026-10-16 04:00:00",
                     "2026-10-16 04:10:00")
        # (b) a lane with a launch nobody can place
        tree_b = self.lane("glm-b")
        self.session("glm-b", "0010-b.md", "2026-10-16 04:00:00",
                     "2026-10-16 04:10:00")
        self.verdict("glm-b-run.txt", tree_b, "2000.0",
                     datetime.datetime(2026, 10, 16, 3, 0, 0),
                     copies=[(os.path.join("c", "copy.txt"),
                              datetime.datetime(2026, 10, 16, 8, 0, 0))])
        # (c) a lane whose every launch was read
        tree_c = self.lane("suppression")
        self.session("suppression", "0110-read-it.md",
                     "2026-10-15 21:51:36", "2026-10-15 23:07:58",
                     out="read it: filed at supp-verdict-read-me.txt")
        self.verdict("supp-verdict-read-me.txt", tree_c, "3454.5",
                     datetime.datetime(2026, 10, 15, 23, 6, 37),
                     failures=234)
        self.flush()
        self.lock_free()
        data, html = self.rendered(Probe(table={11111: (0, "python.exe")}))

        rows = {r["lane"]: r for r in data["lane_rows"]}
        self.assertEqual((rows["qwen"]["launches"], rows["qwen"]["decided"]),
                         (0, 0))
        self.assertEqual((rows["glm-b"]["launches"],
                          rows["glm-b"]["decided"]), (1, 0))
        self.assertEqual((rows["suppression"]["launches"],
                          rows["suppression"]["decided"],
                          rows["suppression"]["unread"]), (1, 1, 0))
        # THE THREE SENTENCES, each asserted present. Without this the three
        # zeroes above would be indistinguishable to someone glancing at the
        # page, which is the defect the brief named.
        self.assertIn("NO LAUNCH READABLE", html)
        self.assertIn("NONE PLACEABLE", html)
        self.assertIn("0 of 1 unread", html)

    def test_a_lane_that_read_everything_is_not_painted_as_an_alarm(self):
        tree = self.lane("suppression")
        self.session("suppression", "0110-read-it.md",
                     "2026-10-15 21:51:36", "2026-10-15 23:07:58",
                     out="read it: filed at supp-verdict-read-me.txt")
        self.verdict("supp-verdict-read-me.txt", tree, "3454.5",
                     datetime.datetime(2026, 10, 15, 23, 6, 37),
                     failures=234)
        self.flush()
        self.lock_free()
        _data, html = self.rendered(Probe(table={11111: (0, "python.exe")}))
        self.assertIn('<span class="tag pass">0 of 1 unread', html)


# --------------------------------------------------------------------------
# THE REFUSALS: UNKNOWN IS NEVER READ, AND A FAILED READ IS NEVER A ZERO


class EveryUnanswerableQuestionIsAnsweredUNKNOWN(unittest.TestCase, Estate):

    setUp = Estate.setUp

    def test_an_unreadable_process_table_never_strands_a_lock(self):
        """A holder is never called dead on a failed read.

        That mistake took a live suite's lock on 2026-10-02 and is the defect
        `DAMAGED_GRACE` exists for. With the table unreadable the lock
        disposition must be UNDETERMINED, and the fate must not become
        DIED-UNREAD on the strength of it.
        """
        self.the_0234b_instance()
        self.flush()
        data = self.read(Probe(readable=False))
        row = self.only(data, lane="pilotcaps")
        self.assertEqual(row["lock_disposition"], sf.LOCKD_UNDETERMINED)
        self.assertNotEqual(row["lock_disposition"], sf.LOCKD_STRANDED)
        self.assertEqual(row["fate"], sf.FATE_UNKNOWN)
        self.assertNotEqual(row["fate"], sf.FATE_DIED_UNREAD)
        self.assertIs(data["table_read"], False)

    def test_an_unreadable_out_file_makes_recording_UNKNOWN_not_False(self):
        """Absence of a record this reader could not open is not absence."""
        tree = self.lane("suppression")
        self.session("suppression", "0110-read-it.md",
                     "2026-10-15 21:51:36", "2026-10-15 23:07:58",
                     out="whatever")
        self.verdict("supp-verdict.txt", tree, "3454.5",
                     datetime.datetime(2026, 10, 15, 23, 6, 37))
        self.flush()
        self.lock_free()
        # `_recorded` is the seam; a file that cannot be decoded is simulated
        # at the function rather than by breaking a filesystem permission,
        # which is not portable.
        recorded, why = sf._recorded(
            None, {"copies": [], "fields": {"failures": "228"}}, None)
        self.assertIsNone(recorded)
        self.assertIn("could not be read", why)

    def test_a_lock_naming_no_usable_pid_is_not_a_launch(self):
        """`isinstance(True, int)` is True in python, so the bool is excluded.

        A lock whose `pid` field reads `true` names no process and must
        produce no launch row at all, rather than a row about pid 1.
        """
        self.the_0220_instance()
        self.flush()
        self.write_lock(pid=True)
        data = self.read(Probe(table={11111: (0, "python.exe")}))
        self.assertEqual([r["source"] for r in data["rows"]], ["verdict"])
        self.assertIs(data["lock_readable"], True)

    def test_an_unconfigured_estate_renders_as_absent_not_as_all_read(self):
        data = sf.panel(root=None, probe=Probe(),
                        now=datetime.datetime(2026, 10, 16, 8, 30, 0))
        self.assertEqual(data["state"], lanes.UNCONFIGURED)
        html = pages.lane_suite_fates(data)
        self.assertIn("UNKNOWN", html)
        self.assertNotIn("RESULT READ", html)


# --------------------------------------------------------------------------
# THE BOUNDARY: THIS PANEL IS THE READER, NEVER THE WRITER


class NothingIsWrittenByLookingAtIt(unittest.TestCase, Estate):
    """The evidence this panel reads is exactly what a second writer destroys."""

    setUp = Estate.setUp

    def fingerprint(self, *roots):
        """`{relative path: md5}` over every file under each root."""
        found = {}
        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames.sort()
                for name in sorted(filenames):
                    path = os.path.join(dirpath, name)
                    with open(path, "rb") as handle:
                        found[os.path.relpath(path, self.home)] = (
                            hashlib.md5(handle.read()).hexdigest())
        return found

    def test_a_render_changes_no_byte_of_the_estate_or_the_lock(self):
        self.the_0234b_instance()
        self.the_0220_instance()
        self.flush()
        os.makedirs(self.lock + ".queue", exist_ok=True)
        with open(os.path.join(self.lock + ".queue", "0001-83736.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({"pid": PID_0234B}, handle)

        before = self.fingerprint(self.logs, self.work,
                                  os.path.join(self.home, "queue"))
        self.rendered(Probe(table={9: (0, "python.exe")}))
        after = self.fingerprint(self.logs, self.work,
                                 os.path.join(self.home, "queue"))
        self.assertEqual(before, after)
        # THE SHARP ONE. The obvious reader for the waiter queue is
        # `suitelock._live_tickets`, which UNLINKS a dead owner's ticket as
        # it walks - and this fixture's only ticket is owned by the dead pid
        # 83736. An instrument that prunes what it measures is not one.
        self.assertIn(os.path.join("work", "suite.lock.queue",
                                   "0001-83736.json"), after)
        self.assertEqual(len(before), len(after))

    def test_the_stranded_lock_is_still_there_afterwards(self):
        self.the_0234b_instance()
        self.flush()
        with open(self.lock, "rb") as handle:
            before = handle.read()
        self.rendered(Probe(table={9: (0, "python.exe")}))
        with open(self.lock, "rb") as handle:
            self.assertEqual(handle.read(), before)


# --------------------------------------------------------------------------
# THE WORDS TRAVEL WITH THE DATA


class NoPageHoldsATableOfItsOwn(unittest.TestCase, Estate):

    setUp = Estate.setUp

    def test_every_fate_has_a_label_a_reason_and_a_colour(self):
        self.assertEqual(sorted(sf.FATE_TEXT), sorted(
            [sf.FATE_FINISHED_READ, sf.FATE_DIED_UNREAD,
             sf.FATE_LANDED_UNRECORDED, sf.FATE_RUNNING, sf.FATE_UNKNOWN]))
        for state in sf.FATE_TEXT:
            self.assertIn(state, pages.FATE_KIND, state)
        for state in sf.LOCKD_TEXT:
            self.assertIn(state, pages.LOCKD_KIND, state)

    def test_a_fate_the_page_has_not_been_told_about_is_named(self):
        """Not filed into whichever bucket happened to be first."""
        self.the_0234b_instance()
        self.flush()
        data, _html = self.rendered(Probe(table={9: (0, "python.exe")}))
        data["rows"][0]["fate"] = "fate_something_new"
        data["rows"][0]["fate_label"] = None
        data["unrecognised_fates"] = ["fate_something_new"]
        html = pages.lane_suite_fates(data)
        self.assertIn("UNRECOGNISED", html)
        self.assertIn("fate_something_new", html)

    def test_the_two_vocabularies_do_not_collide(self):
        """A fifth vocabulary, and it may not reuse a word from the others."""
        self.assertEqual(set(sf.FATE_TEXT) & set(lanes.LOCK_TEXT), set())
        self.assertEqual(set(sf.FATE_TEXT) & set(lanes.VERDICT_TEXT), set())
        self.assertEqual(set(sf.LOCKD_TEXT) & set(lanes.LOCK_TEXT), set())

    def test_describe_states_the_independence_and_the_refusals(self):
        text = " ".join(sf.describe()).lower()
        self.assertIn("session", text)
        self.assertIn("lock", text)
        self.assertIn("writes nothing", text)


if __name__ == "__main__":
    unittest.main()
