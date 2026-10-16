"""A lane the operator stopped is not a lane to restart, and the board says so.

WHY THIS FILE EXISTS, and it is a measured gap rather than a feature idea. At
2026-10-16 13:30 the operator stopped every GLM call until the weekly quota
renews and wrote three files - `STOP-glm`, `STOP-glm-b`, `STOP-glm-c` - so that
the decision would be mechanical rather than remembered: `START-ALL-LANES.ps1`
skips a lane that has one. Three of seven lanes therefore had no watcher and no
running task, ON PURPOSE.

The board had no word for it. `src.lanes` held nine verdicts and not one of
them was STOPPED, so all three rendered `V_DOWN` - "WATCHER DOWN ... this is
NOT idle: idle means waiting for work, this means waiting for a person" - and
`src.queuedepth` rendered them STRANDED in red, with "the repair is restarting
the watcher" printed beside twelve briefs. One five-hour GLM window costs 28K
credits against 34.14K left for five days. Both pages were inviting the one
action that spends the rest of the week's budget.

THE AUTHORITY IS THE FILE THE LAUNCHER TESTS, and deliberately not a second
record of the operator's decision: a copy is a second thing that can disagree
with the launcher, and the launcher is what actually holds the line. The date
is read out of the file's bytes at every render and is nowhere in this
codebase as a constant - which is what the `A_DIFFERENT_DATE` fixture below
proves, because a reader that had `2026-10-21` written into it would pass
every other test here.

DOWN-UNEXPLAINED IS THE FAIL-CLOSED DEFAULT AND IS MOST OF THIS FILE. No STOP
file, an unreadable one, an empty one, one with no parsable date - every one of
them is DOWN-UNEXPLAINED and not one of them is STOPPED. A lane that is down
for a reason nobody wrote down must never render as a lane that is down on
purpose; substituting the nearest token a reader happens to have for a state it
cannot establish is this estate's sixth failure family.

NOTHING HERE TOUCHES THE REAL ESTATE. Every lane root is a temporary directory
this module creates, every STOP file is a string it writes there, and every
process table is a dict handed to the reader. No test reads
`C:\\Users\\Zvonimir\\Desktop\\resonate-ops`, and `test_the_reader_writes_nothing`
proves the reader is incapable of creating or removing one of those files.
"""
import datetime
import os
import re
import shutil
import tempfile
import unittest

from src import lanes, queuedepth
from src.web import api, pages

#: `now` for every test. Fixed, because "has the stop lifted" is a comparison
#: against a clock and a test that used the real one would change its answer
#: on 2026-10-21.
NOW = datetime.datetime(2026, 10, 16, 14, 0, 0)

LANE = "alpha"
WATCHER_PID = 4242

#: The real `STOP-glm`, byte-for-byte as the operator wrote it at 13:22:10,
#: including the three dates in it. Used so that the latest-of-many rule is
#: exercised against the actual prose and not against a convenient
#: simplification of it - the file is Croatian, so a reader keyed to an
#: English label would find nothing in it.
REAL_STOP = """STOP-glm
Postavljeno 2026-10-16 13:30 po operaterovoj uputi: "glm smo ispraznili,
prestani zvati glm dok se ne obnovi."

GLM tjedna kvota je iscrpljena. Mjereno na z.ai stranici u 12:54:
  petosatni  28.03K / 28K   100%   reset 20:14
  tjedni    105.86K / 140K   75%   reset 2026-10-21 21:00
Ostalo 34.14K za pet dana, a jedan petosatni prozor kosta 28K.

OVAJ FILE POSTOJI DA ODLUKA BUDE MEHANICKA, A NE ZAPAMCENA.
START-ALL-LANES.ps1 preskace traku koja ima STOP-<lane> file. Dakle i ako
netko pokrene launcher, ova traka ostaje dolje - sto je i namjera.

NE BRISATI prije 2026-10-21 21:00, osim ako operater izricito ne kaze
drugacije. Kad se brise, obrisati sva tri i tek onda pokrenuti launcher.

Posao ove trake nije izgubljen - stoji u queue\\glm\\ i ceka.
"""

#: THE SAME SHAPE WITH A DIFFERENT DATE. A reader holding `2026-10-21` as a
#: constant passes every other test in this file and fails this one.
A_DIFFERENT_DATE = """STOP-alpha
Down until 2027-03-04 06:30 and not before.
"""

#: A past date, which is the control most likely to be vacuous: the three real
#: files all name a future one, so if this branch cannot be made to fire it
#: does not exist.
AN_EXPIRED_DATE = """STOP-alpha
Down until 2026-10-15 09:00. That moment has passed.
"""

#: A reason with no date in it at all.
NO_DATE_AT_ALL = """STOP-alpha
Taking this lane down. I will say when it comes back.
"""


def line(clock, message, lane=LANE, day="2026-10-16"):
    """One watcher record, in the exact shape `lane_watcher.ps1` writes."""
    return "[%s %s] [%s] %s" % (day, clock, lane, message)


def up(clock="00:00:00", timeout=90, day="2026-10-16"):
    return line(clock, "watcher up. tree=C:\\somewhere mode=bypassPermissions "
                       "timeout=%dm" % timeout, day=day)


class FakeProbe:
    """A process table handed to the reader, never measured.

    `watcher=False` drops the watcher itself from the table, which is the
    shape of a lane whose watcher is gone. `unreadable=True` returns no table
    at all - liveness is then UNKNOWN, and UNKNOWN must not produce STOPPED
    any more than it produces healthy.
    """

    def __init__(self, watcher=True, child=False, unreadable=False):
        self.watcher = watcher
        self.child = child
        self.unreadable = unreadable

    def table(self):
        if self.unreadable:
            return None
        rows = {1: (0, "explorer.exe")}
        if self.watcher:
            rows[WATCHER_PID] = (1, "powershell.exe")
        if self.child:
            rows[WATCHER_PID + 1] = (WATCHER_PID, "node.exe")
        return rows

    def cpu(self, pid):
        return 1.0


class Estate:
    """A temporary lane estate, thrown away per test."""

    def setUp(self):
        super().setUp()
        self.root = tempfile.mkdtemp(prefix="rga-stopfile-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, "logs"))
        os.makedirs(os.path.join(self.root, "queue", LANE, "RUNNING"))
        with open(os.path.join(self.root, "logs", "watcher-%s.pid" % LANE),
                  "w", encoding="utf-8", newline="\n") as handle:
            handle.write("%d\n" % WATCHER_PID)
        with open(os.path.join(self.root, "LANE-%s.md" % LANE), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("## entry 2026-10-16\n")
        with open(os.path.join(self.root, "queue", "README.md"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("**Floor: never leave a lane below 3 queued "
                         "briefs.**\n")

    # ------------------------------------------------------------- fixtures

    def log(self, *rows, lane=LANE):
        path = os.path.join(self.root, "logs", "watcher-%s.log" % lane)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(rows) + "\n")
        return path

    def watcher_logged_down(self, lane=LANE):
        """The exact shape all three real lanes are in: three refusals, the
        failure guard, and the watcher's own exit line."""
        return self.log(up(), line("12:00:00", "START 0010-a.md"),
                        line("12:26:11", "DONE  0010-a.md -> exit1"),
                        line("12:26:11", "3 consecutive failures. Exiting "
                                         "rather than looping on a broken "
                                         "task."),
                        line("12:26:11", "watcher down."), lane=lane)

    def stop_file(self, body, lane=LANE):
        path = os.path.join(self.root, lanes.STOP_PREFIX + lane)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
        return path

    def remove_stop_file(self, lane=LANE):
        os.remove(os.path.join(self.root, lanes.STOP_PREFIX + lane))

    def queue(self, *names, lane=LANE):
        for name in names:
            with open(os.path.join(self.root, "queue", lane, name), "w",
                      encoding="utf-8", newline="\n") as handle:
                handle.write("# a brief\n")

    # -------------------------------------------------------------- readers

    def board(self, watcher=False, child=False, unreadable=False, now=None):
        return lanes.board(root=self.root, now=now or NOW,
                           probe=FakeProbe(watcher=watcher, child=child,
                                           unreadable=unreadable),
                           samples={})

    def row(self, lane=LANE, **kwargs):
        data = self.board(**kwargs)
        return [r for r in data["lanes"] if r["lane"] == lane][0]

    def page(self, **kwargs):
        data = api.lane_board(root=self.root, now=NOW, samples={},
                              probe=FakeProbe(**kwargs))
        return data, pages.lane_board(data)


# ---------------------------------------------------------------- the verdicts


class TheThreeVerdictsAreReachable(Estate, unittest.TestCase):
    """C1, C2 and C3. An instrument that cannot fail reports clean."""

    def test_C2_stopped_fires(self):
        """A dead watcher and a STOP file whose date has not arrived."""
        self.watcher_logged_down()
        self.stop_file(REAL_STOP)
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_STOPPED)
        self.assertEqual(row["stop"]["state"], lanes.PRESENT)
        self.assertIs(row["stop"]["expired"], False)

    def test_C3_stop_expired_fires(self):
        """THE CONTROL MOST LIKELY TO BE VACUOUS. The three real files all
        name a future date, so if this branch cannot be made to print, it
        does not exist and saying so is the finding. It can."""
        self.watcher_logged_down()
        self.stop_file(AN_EXPIRED_DATE)
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_STOP_EXPIRED)
        self.assertIs(row["stop"]["expired"], True)
        self.assertEqual(row["stop"]["lift_at"], "2026-10-15 09:00")

    def test_C1_down_unexplained_fires(self):
        """A dead watcher log and NO STOP file. If this prints STOPPED, or
        prints nothing, the whole instrument is unsafe."""
        self.watcher_logged_down()
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_DOWN_UNEXPLAINED)
        self.assertEqual(row["stop"]["state"], lanes.ABSENT)
        self.assertIsNone(row["stop"]["expired"])

    def test_the_old_down_verdict_is_no_longer_produced(self):
        """`V_DOWN` is split, not joined. A row that still answered `down`
        would be a fourth state nobody renders."""
        for body in (REAL_STOP, AN_EXPIRED_DATE, NO_DATE_AT_ALL, None):
            self.watcher_logged_down()
            if body is None:
                if os.path.exists(os.path.join(self.root,
                                               lanes.STOP_PREFIX + LANE)):
                    self.remove_stop_file()
            else:
                self.stop_file(body)
            self.assertNotEqual(self.row()["verdict"], lanes.V_DOWN)

    def test_every_new_verdict_has_words_and_a_colour(self):
        """A verdict with no entry in either table renders UNRECOGNISED,
        which is the guard `lane_board` already carries. This is the test
        that keeps it from firing."""
        for verdict in (lanes.V_STOPPED, lanes.V_STOP_EXPIRED,
                        lanes.V_DOWN_UNEXPLAINED):
            self.assertIn(verdict, lanes.VERDICT_TEXT)
            self.assertIn(verdict, pages.VERDICT_KIND)
        # And STOPPED is NEUTRAL. A red tile on a lane that is down on
        # purpose teaches the operator that the estate is broken and that
        # the fix is a restart.
        self.assertEqual(pages.VERDICT_KIND[lanes.V_STOPPED], "")
        self.assertEqual(pages.VERDICT_KIND[lanes.V_DOWN_UNEXPLAINED],
                         "block")


class TheDateComesFromTheFile(Estate, unittest.TestCase):
    """Read the bytes. Do not hard-code 2026-10-21."""

    def test_a_different_date_is_read_as_itself(self):
        """THE TEST A HARD-CODED READER FAILS AND ONLY THIS ONE."""
        self.watcher_logged_down()
        self.stop_file(A_DIFFERENT_DATE)
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_STOPPED)
        self.assertEqual(row["stop"]["lift_at"], "2027-03-04 06:30")

    def test_the_latest_of_several_dates_is_used(self):
        """The real file names three: when the stop was set, when the
        five-hour window resets and when the weekly quota renews. The one
        that matters is the last."""
        self.watcher_logged_down()
        self.stop_file(REAL_STOP)
        stop = self.row()["stop"]
        self.assertEqual(stop["lift_at"], "2026-10-21 21:00")
        self.assertEqual(stop["candidates"],
                         ["2026-10-16 13:30", "2026-10-21 21:00",
                          "2026-10-21 21:00"])
        # AND THE LINE IT CAME FROM TRAVELS TOO, so the choice is checkable
        # on the page rather than taken on trust. The file names that moment
        # TWICE - the provider's weekly reset, and "do not delete before" -
        # and the tie-break is POSITIONAL, so the quoted line is the file's
        # own first mention of it rather than whichever of the two happens
        # to alphabetise first.
        self.assertIn("reset 2026-10-21 21:00", stop["lift_from"])
        self.assertIn("tjedni", stop["lift_from"])

    def test_the_first_date_is_not_used(self):
        """Taking the EARLIEST would expire this stop five days early, which
        is the one direction that costs money: an expired stop reads as
        'clean this up and start it'."""
        self.watcher_logged_down()
        self.stop_file(REAL_STOP)
        self.assertEqual(self.row()["verdict"], lanes.V_STOPPED)
        # 2026-10-16 13:30 is in the file and is already past at `NOW`.
        self.assertLess(datetime.datetime(2026, 10, 16, 13, 30), NOW)

    def test_a_bare_date_is_the_end_of_that_day(self):
        """`2026-10-21` with no time could mean any instant in it, and the
        first would expire the stop up to 24 hours early."""
        self.watcher_logged_down()
        self.stop_file("STOP-alpha\nDown until 2026-10-16, no time given.\n")
        row = self.row(now=datetime.datetime(2026, 10, 16, 12, 0, 0))
        self.assertEqual(row["verdict"], lanes.V_STOPPED)
        self.assertEqual(row["stop"]["lift_at"], "2026-10-16")
        self.assertEqual(row["stop"]["lift_when"],
                         datetime.datetime(2026, 10, 16, 23, 59, 59))

    def test_a_string_shaped_like_a_date_and_is_not_one_is_skipped(self):
        """`2026-13-45` matches the shape. Clamping it into the nearest
        plausible day would invent a lift moment."""
        self.watcher_logged_down()
        self.stop_file("STOP-alpha\nnonsense 2026-13-45 and 2026-10-30 08:00\n")
        stop = self.row()["stop"]
        self.assertEqual(stop["candidates"], ["2026-10-30 08:00"])
        self.assertEqual(stop["lift_at"], "2026-10-30 08:00")


class EveryUnreadableStopIsDownUnexplained(Estate, unittest.TestCase):
    """THE FAIL-CLOSED HALF, and the reason the verdict exists.

    Each of these has a STOP file in some condition and NONE of them may
    render STOPPED. A reader that answered STOPPED here would be reporting
    the operator's intention from a file it could not read.
    """

    def test_a_stop_file_with_no_date_is_not_stopped(self):
        self.watcher_logged_down()
        self.stop_file(NO_DATE_AT_ALL)
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_DOWN_UNEXPLAINED)
        self.assertEqual(row["stop"]["state"], lanes.PRESENT)
        self.assertEqual(row["stop"]["lift_state"], lanes.LIFT_UNSTATED)
        self.assertIsNone(row["stop"]["expired"])
        # The operator's words still reach the page: the verdict is loud and
        # the evidence is not thrown away with it.
        self.assertIn("Taking this lane down",
                      " ".join(row["stop"]["reason_lines"]))

    def test_an_empty_stop_file_is_not_stopped(self):
        """The launcher skips on PRESENCE alone, so the lane really is down -
        and the file says nothing about why or until when."""
        self.watcher_logged_down()
        self.stop_file("   \n\n")
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_DOWN_UNEXPLAINED)
        self.assertEqual(row["stop"]["state"], lanes.EMPTY)

    def test_an_unreadable_stop_file_is_not_stopped(self):
        """A directory by that name exists for `os.path.exists` and cannot be
        read by `open`, which is the cheapest honest UNREADABLE on Windows."""
        self.watcher_logged_down()
        os.makedirs(os.path.join(self.root, lanes.STOP_PREFIX + LANE))
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_DOWN_UNEXPLAINED)
        self.assertEqual(row["stop"]["state"], lanes.UNREADABLE)

    def test_an_unreadable_log_stays_unknown_beside_a_stop_file(self):
        """A STOP FILE IS NOT EVIDENCE THAT A WATCHER IS DOWN. With no log at
        all nothing can be said about this lane, and UNKNOWN is not STOPPED:
        the launcher refuses to START a lane that has one and cannot stop a
        watcher that is already up."""
        self.stop_file(REAL_STOP)          # no log written at all
        row = self.row()
        self.assertEqual(row["verdict"], lanes.V_UNKNOWN)
        self.assertEqual(row["stop"]["state"], lanes.PRESENT)

    def test_an_unreadable_process_table_does_not_produce_stopped(self):
        """UNCROSSED. One authority answered and the other did not, and a
        STOP file does not stand in for the missing one."""
        self.log(up(), line("12:00:00", "START 0010-a.md"))
        self.stop_file(REAL_STOP)
        row = self.row(unreadable=True)
        self.assertEqual(row["verdict"], lanes.V_UNCROSSED)

    def test_a_live_lane_with_a_stop_file_keeps_its_verdict_and_is_flagged(self):
        """The contradiction, named rather than resolved. A watcher started
        by hand would do exactly this, and the page must not pick a side."""
        self.log(up(), line("13:50:00", "START 0010-a.md"))
        self.stop_file(REAL_STOP)
        row = self.row(watcher=True, child=True)
        self.assertEqual(row["verdict"], lanes.V_RUNNING)
        self.assertTrue(row["stop_contradicted"])
        _data, html = self.page(watcher=True, child=True)
        self.assertIn("a STOP file sits on a lane that is ALIVE", html)

    def test_a_down_lane_is_not_flagged_as_a_contradiction(self):
        """The flag fires only beside a verdict that CLAIMS something is
        alive. Firing it on every stopped lane would cry wolf on all three."""
        self.watcher_logged_down()
        self.stop_file(REAL_STOP)
        self.assertFalse(self.row()["stop_contradicted"])


class TheReaderReadsTheDisk(Estate, unittest.TestCase):
    """C4. A reader that caches the first answer passes C1-C3 and is blind."""

    def test_the_same_lane_flips_back_in_one_process_run(self):
        self.watcher_logged_down()
        self.stop_file(REAL_STOP)
        self.assertEqual(self.row()["verdict"], lanes.V_STOPPED)
        self.remove_stop_file()
        self.assertEqual(self.row()["verdict"], lanes.V_DOWN_UNEXPLAINED)
        # And back again, so the second answer is not itself a one-way door.
        self.stop_file(REAL_STOP)
        self.assertEqual(self.row()["verdict"], lanes.V_STOPPED)

    def test_an_edited_date_is_seen_without_a_restart(self):
        """Not only presence. A file whose date is changed under a running
        process must change the verdict with it."""
        self.watcher_logged_down()
        self.stop_file(A_DIFFERENT_DATE)
        self.assertEqual(self.row()["verdict"], lanes.V_STOPPED)
        self.stop_file(AN_EXPIRED_DATE)
        self.assertEqual(self.row()["verdict"], lanes.V_STOP_EXPIRED)

    def test_the_reader_writes_nothing(self):
        """IT MUST NOT BE ABLE TO LOSE ONE OF THOSE FILES. `resonate-ops`
        carries no remote, so a deleted STOP file is gone - and the brief
        forbids creating one for a lane that has none."""
        self.watcher_logged_down()
        path = self.stop_file(REAL_STOP)
        before = sorted(os.listdir(self.root))
        with open(path, "rb") as handle:
            bytes_before = handle.read()
        self.page(watcher=False)
        lanes.board(root=self.root, now=NOW, probe=FakeProbe(), samples={})
        queuedepth.consumable(root=self.root, now=NOW,
                              probe=FakeProbe(), samples={})
        self.assertEqual(sorted(os.listdir(self.root)), before)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), bytes_before)


class TheEstateWideStop(Estate, unittest.TestCase):
    """`STOP-ALL` is read, and is never a lane's verdict."""

    def test_it_is_said_once_at_the_top_and_decides_no_row(self):
        self.watcher_logged_down()
        with open(os.path.join(self.root, lanes.STOP_ALL), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("estate down for the night\n")
        row = self.row()
        # STILL UNEXPLAINED. A global stop does not explain THIS lane, and
        # the launcher's per-lane test is the per-lane authority.
        self.assertEqual(row["verdict"], lanes.V_DOWN_UNEXPLAINED)
        data, html = self.page(watcher=False)
        self.assertTrue(data["stop_all"]["present"])
        self.assertIn("An estate-wide stop is in force", html)
        self.assertIn("estate down for the night", html)

    def test_its_absence_is_not_a_note(self):
        self.watcher_logged_down()
        data, html = self.page(watcher=False)
        self.assertFalse(data["stop_all"]["present"])
        self.assertNotIn("An estate-wide stop is in force", html)


# ------------------------------------------------------- what a human is told


class TheCellSaysWhatAHumanNeeds(Estate, unittest.TestCase):
    """The operator is away and reads this cold.

    Three facts decide what he does, and all three are in the cell rather
    than one click away: the date it lifts, that the queued work is intact
    and waiting, and that restarting it before the date spends budget rather
    than buying work.
    """

    def cell(self, body=REAL_STOP, briefs=3):
        self.watcher_logged_down()
        if body is not None:
            self.stop_file(body)
        self.queue(*["%04d-brief.md" % (n * 10) for n in range(1, briefs + 1)])
        _data, html = self.page(watcher=False)
        return html

    def test_the_date_it_lifts_is_in_the_cell(self):
        self.assertIn("lifts 2026-10-21 21:00", self.cell())

    def test_the_queued_work_is_named_as_intact(self):
        html = self.cell(briefs=3)
        self.assertIn("3 brief(s) queued here, untouched", html)
        self.assertIn("The work is not lost", html)

    def test_restarting_early_is_named_as_a_cost(self):
        self.assertIn("spends budget rather than buying work", self.cell())

    def test_the_operators_own_first_line_is_quoted(self):
        self.assertIn("its first line reads: STOP-glm", self.cell())

    def test_the_file_is_named_without_a_code_chip(self):
        """HE PASTES FENCED CONTENT AS COMMANDS AND HAS THREE TIMES. The
        path is named in prose; a bare path in a `<code>` chip beside a
        STOP file is a file deleted.

        THE ASSERTION IS OVER EVERY `<code>` SPAN ON THE PAGE AND NOT OVER
        THE TWO BYTES IN FRONT OF THE PATH. The first version of this test
        asserted `"<code>" + path_shown` was absent, and the mutation that
        wraps the whole line - `<div class="small muted"><code>` - SURVIVED
        it, because the chip then opens on "the file is " and the path sits
        four words further in. A control has to observe the claim it makes.
        """
        html = self.cell()
        self.assertIn("the same path START-ALL-LANES.ps1 tests", html)
        # The path itself, in prose, ending in the file's own name. The tail
        # is relative to whatever estate root this fixture made, which is
        # the point: the renderer never prints an absolute one.
        path_shown = self.row()["stop"]["path_shown"]
        self.assertTrue(path_shown.endswith("STOP-alpha"), path_shown)
        self.assertIn("the file is " + path_shown, html)

        chips = re.findall(r"<code>(.*?)</code>", html, re.S)
        for chip in chips:
            self.assertNotIn("STOP-", chip, chips)
            self.assertNotIn(path_shown, chip, chips)
        # AND THE PAGE DOES HAVE CHIPS, so the loop above is not vacuous.
        # An assertion over an empty list passes for free.
        self.assertTrue(chips, "no <code> chip on the page at all - the "
                               "loop above proved nothing")

    def test_an_unknown_queue_is_not_rendered_as_intact(self):
        """UNKNOWN IS NOT ZERO AND IT IS NOT 'UNTOUCHED'. A queue folder
        that could not be read says nothing about whether the work survived."""
        self.watcher_logged_down()
        self.stop_file(REAL_STOP)
        shutil.rmtree(os.path.join(self.root, "queue", LANE))
        _data, html = self.page(watcher=False)
        self.assertIn("queued work UNKNOWN", html)
        self.assertIn("UNKNOWN is not zero", html)
        self.assertNotIn("brief(s) queued here, untouched", html)

    def test_the_expired_cell_asks_for_a_person(self):
        html = self.cell(body=AN_EXPIRED_DATE)
        self.assertIn("the date it named has passed", html)
        self.assertIn("Deleting the file and starting the watcher", html)
        self.assertIn("goes on skipping this lane until somebody does", html)
        # AND IT DOES NOT SAY THE LANE IS STOPPED. A board that still said
        # STOPPED a week later would be explaining an outage away.
        self.assertNotIn("lifts 2026-10-15 09:00", html)

    def test_the_unexplained_cell_does_not_offer_a_lift_date(self):
        html = self.cell(body=None)
        self.assertIn("DOWN - UNEXPLAINED", html)
        self.assertIn("no STOP-alpha file exists", html)
        self.assertNotIn("lifts ", html)

    def test_the_head_counts_the_stopped_lanes_neutrally(self):
        self.watcher_logged_down()
        self.stop_file(REAL_STOP)
        data, html = self.page(watcher=False)
        self.assertEqual(data["tally"].get("stopped"), 1)
        self.assertIn("stopped on purpose", html)
        self.assertEqual(data["unrecognised_verdicts"], [])


class TheDepthPanelDoesNotAskForARestart(Estate, unittest.TestCase):
    """The second page that renders these lanes, and the one with the
    sentence that costs money: `STRANDED` reads "SOMEBODY HAS TO RESTART THE
    WATCHER", which is right for a watcher that died and the exact opposite
    of right for one the operator stopped."""

    def depth(self, body=REAL_STOP, briefs=3):
        self.watcher_logged_down()
        if body is not None:
            self.stop_file(body)
        self.queue(*["%04d-brief.md" % (n * 10) for n in range(1, briefs + 1)])
        board = api.lane_board(root=self.root, now=NOW, samples={},
                               probe=FakeProbe(watcher=False))
        return api.queue_depth(root=self.root, now=NOW, board=board)

    def test_a_stopped_lane_is_not_stranded(self):
        data = self.depth()
        row = data["lanes"][0]
        self.assertEqual(row["state"], queuedepth.S_STOPPED)
        self.assertEqual(data["stopped_lanes"], [LANE])
        self.assertEqual(data["stranded_lanes"], [])
        self.assertEqual(row["stop_lift_at"], "2026-10-21 21:00")

    def test_the_restart_sentence_is_not_printed_for_it(self):
        data = self.depth()
        html = pages.queue_depth(data)
        self.assertIn("STOPPED ON PURPOSE", html)
        self.assertIn("the repair is NOT a restart", html)
        self.assertNotIn("the repair is restarting the watcher", html)

    def test_the_briefs_are_counted_and_not_lost_to_the_split(self):
        """Taking them out of `stranded_briefs` without printing them
        anywhere would turn twelve briefs that cannot start into a zero."""
        data = self.depth(briefs=6)
        self.assertEqual(data["stopped_briefs"], 6)
        self.assertEqual(data["stranded_briefs"], 0)
        text = queuedepth.describe(data)
        self.assertIn("6 brief(s) queued on a lane the operator STOPPED",
                      text)
        self.assertIn("due back 2026-10-21 21:00", text)

    def test_an_unexplained_lane_is_still_stranded(self):
        """The red sentence is RIGHT there, and must survive."""
        data = self.depth(body=None)
        self.assertEqual(data["lanes"][0]["state"], queuedepth.S_STRANDED)
        self.assertEqual(data["stranded_lanes"], [LANE])
        self.assertEqual(data["stopped_lanes"], [])

    def test_a_stopped_lane_with_nothing_queued_is_still_stopped(self):
        """`DEAD AND EMPTY` would tell the reader to restart it too."""
        data = self.depth(briefs=0)
        self.assertEqual(data["lanes"][0]["state"], queuedepth.S_STOPPED)

    def test_no_state_arrives_unrecognised(self):
        self.assertEqual(self.depth()["unrecognised"], [])


class TheTerminalRenderSaysItToo(Estate, unittest.TestCase):
    """A lane session reads the terminal, not the page."""

    def test_the_whole_label_is_printed(self):
        """`.split()[0]` printed `WATCHER DOWN` as `WATCHER`, which was
        lossy and tolerable - and would print `DOWN - UNEXPLAINED` as `DOWN`,
        the old word for the state this reader exists to tell apart."""
        self.watcher_logged_down()
        text = lanes.describe(self.board())
        self.assertIn("DOWN - UNEXPLAINED", text)

    def test_the_stopped_line_carries_the_date_and_the_depth(self):
        self.watcher_logged_down()
        self.stop_file(REAL_STOP)
        self.queue("0010-a.md", "0020-b.md")
        text = lanes.describe(self.board())
        self.assertIn("DOWN ON PURPOSE until 2026-10-21 21:00", text)
        self.assertIn("2 brief(s) wait here, intact", text)
        self.assertIn("Do NOT restart it before then", text)


if __name__ == "__main__":
    unittest.main()
