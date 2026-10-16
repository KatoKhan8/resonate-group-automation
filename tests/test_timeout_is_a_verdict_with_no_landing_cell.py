"""TIMEOUT, and the lane file's own clock as the fifth authority.

WHAT THIS FILE IS FOR, TASK 0250. `glm-c/0220` closed
`DONE 0220-the-remaining-bypasses-tiered.md -> TIMEOUT` at 11:47:00 on
2026-10-16 after 150.1 minutes, and the board had no landing verdict for it
at all - `row["landing"]` was computed only for a suffix in
`KILLED_SUFFIXES`, which held `exit-1` and nothing else. So the one dispatch
in this estate that was killed AT THE CAP got `landing: None`: not LANDED,
not LOST, not even NOT DETERMINED.

**THE BRIEF'S OWN PREMISE DID NOT SURVIVE, and the correction is the first
thing this file tests.** The brief says TIMEOUT is a token
`DONE_MEANINGS` "has not met". It had an entry the whole time. What it did
not have was a MECHANISM - a place in `KILLED_SUFFIXES` that makes the
landing question get asked - and a description of what it does NOT mean.
Those are different defects with different fixes and this file pins both.

THE SECOND FINDING IS A SUBTRACTION. Enumerated by content over **203 DONE
lines across seven watcher logs, 0 unparsed**: SIX distinct verdict tokens
against FOUR described. `exit1` seventeen times and a BARE `exit` fifteen -
the latter being a watcher that wrote the word and no number, so fifteen
briefs were consumed with no recorded outcome of any kind.

THE THIRD IS AN ASYMMETRY THAT HAS TO SURVIVE INTO THE CODE. `CONTINUITY.md`
§3 licenses the lane-file mtime in ONE direction: an mtime before START is
evidence nothing was appended; an mtime after DONE proves nothing, because a
later task may have written it. `glm-c/0220` is the live instance - its lane
file is 12:11:47 against a DONE of 11:47:00 - so the row that motivated this
work is exactly the row that must never render as LANDED on this leg.

NOTHING HERE READS THE REAL ESTATE. Every watcher log and lane file is a
string in a temporary directory, every mtime is set with `os.utime`, and the
commit window is a `(shas, complete)` pair handed to the reader through the
git seam `src.lanerework`'s own docstring requires.
"""
import datetime
import os
import shutil
import tempfile
import unittest

from src import lanerework as lr
from src import lanes
from src.web import api, pages

DAY = "2026-10-16"
KNOWN = ("glm", "glm-b", "glm-c", "pilotcaps", "qwen", "suppression",
         "webapp")

#: A body long enough to count as a report. `MIN_ENTRY_BODY_WORDS` is 20.
REPORT = " ".join(["measured"] * 40)


def stamp(clock, day=DAY):
    return "%s %s" % (day, clock)


def when(clock, day=DAY):
    return datetime.datetime.strptime(stamp(clock, day), "%Y-%m-%d %H:%M:%S")


def up(lane, clock="00:00:00", day=DAY):
    return ("[%s] [%s] watcher up. tree=C:\\somewhere mode=bypassPermissions "
            "timeout=150m" % (stamp(clock, day), lane))


def start(lane, clock, brief, day=DAY):
    return "[%s] [%s] START %s" % (stamp(clock, day), lane, brief)


def done(lane, clock, brief, suffix="TIMEOUT", day=DAY):
    return "[%s] [%s] DONE  %s -> %s" % (stamp(clock, day), lane, brief,
                                         suffix)


def heading(task, body=REPORT):
    return "## %s \u2014 TASK-%s: the thing\n\n%s\n" % (DAY, task, body)


class Estate(object):
    """A temporary lane estate whose lane-file mtime this test controls."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="timeout-0250-")
        os.makedirs(os.path.join(self.root, "logs"))
        os.makedirs(os.path.join(self.root, "queue"))

    def log(self, lane, lines):
        path = os.path.join(self.root, "logs", "watcher-%s.log" % lane)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\ufeff" + "\n".join(lines) + "\n")

    def lane_file(self, lane, text, mtime=None):
        path = os.path.join(self.root, "LANE-%s.md" % lane)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        if mtime is not None:
            # THE WHOLE POINT OF THIS FIXTURE. The leg under test reads this
            # number, so the test sets it rather than hoping the filesystem
            # produces the case.
            os.utime(path, (mtime.timestamp(), mtime.timestamp()))
        return path

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class Base(unittest.TestCase):

    def setUp(self):
        self.estate = Estate()
        self.addCleanup(self.estate.close)

    def read(self, lane):
        # `cwd` is the temp root, which is not a git repository, so the
        # commit leg reads UNKNOWN rather than reaching this machine's.
        return lr.lane_rework(self.estate.root, lane, commits={},
                              offset_hours=2.0, known=KNOWN,
                              cwd=self.estate.root)

    def row_for(self, lane, brief):
        got = self.read(lane)
        for row in got["rows"]:
            if row["brief"] == brief:
                return row
        raise AssertionError("no row for %s in %s"
                             % (brief, [r["brief"] for r in got["rows"]]))


# --------------------------------------------------------------------------
# THE PREMISE, CHECKED AGAINST THE CODE BEFORE ANY WORK WAS BUILT ON IT.
# --------------------------------------------------------------------------

class ThePremiseDidNotSurvive(unittest.TestCase):

    def test_timeout_already_had_a_description(self):
        """The brief says `DONE_MEANINGS` has not met TIMEOUT. It had.

        Pinned so that nobody re-derives the wrong diagnosis from the brief:
        a token can be described and still have no mechanism, and those need
        different fixes.
        """
        self.assertIn("TIMEOUT", lanes.DONE_MEANINGS)

    def test_what_it_did_not_have_was_a_place_in_killed_suffixes(self):
        """Which is what made the landing question not get asked."""
        self.assertIn("TIMEOUT", lr.KILLED_SUFFIXES)
        self.assertIn("exit-1", lr.KILLED_SUFFIXES)

    def test_exit1_is_deliberately_not_a_killed_suffix(self):
        """It means ran-and-failed, which is an ordinary outcome.

        Asserted so that a later reader does not "complete" the tuple by
        adding every token in the dictionary: that would mean a `git log`
        per row for 17 rows that do not have the question.
        """
        self.assertNotIn("exit1", lr.KILLED_SUFFIXES)
        self.assertNotIn("exit0", lr.KILLED_SUFFIXES)

    def test_the_description_says_what_it_does_not_mean(self):
        """`0220`'s shape: the mechanism, then the refusal, then what else
        must be read."""
        short, why = lanes.DONE_MEANINGS["TIMEOUT"]
        self.assertIn("that is all this says", short)
        self.assertIn("DOES NOT SAY", why)
        self.assertIn("lanerework.landing", why)


# --------------------------------------------------------------------------
# A TIMEOUT NOW GETS A VERDICT AT ALL.
# --------------------------------------------------------------------------

class ATimeoutGetsALandingVerdict(Base):

    BRIEF = "0220-the-remaining-bypasses-tiered.md"

    def estate_with(self, lane_mtime, suffix="TIMEOUT", entries=True):
        self.estate.log("glm-c", [
            up("glm-c"),
            start("glm-c", "09:16:52", self.BRIEF),
            done("glm-c", "11:47:00", self.BRIEF, suffix),
        ])
        self.estate.lane_file("glm-c",
                              heading("0220") if entries else "# nothing\n",
                              mtime=lane_mtime)

    def test_a_timeout_row_carries_a_landing_dict_and_not_none(self):
        """The defect in one assertion. Before TIMEOUT joined
        `KILLED_SUFFIXES` this was `None` - no verdict of any kind."""
        self.estate_with(when("12:11:47"))
        row = self.row_for("glm-c", self.BRIEF)
        self.assertEqual(row["done_suffix"], "TIMEOUT")
        self.assertIsNotNone(row["landing"])
        self.assertIn(row["landing"]["verdict"],
                      (lr.LANDED, lr.NOT_DETERMINED, lr.LOST))

    def test_the_live_shape_is_not_determined_and_not_landed(self):
        """One START, an entry, and a lane file written AFTER the close.

        With a single START the entry leg would fire and the row would read
        LANDED - and it does, which is correct, because an entry naming the
        id with exactly one dispatch can only be that dispatch's. The
        mtime leg must NOT be what licenses it.
        """
        self.estate_with(when("12:11:47"))
        found = self.row_for("glm-c", self.BRIEF)["landing"]
        self.assertEqual(found["lane_mtime_state"], lr.LANE_MTIME_AFTER)
        self.assertIsNone(found["legs"]["lane_mtime"])

    def test_an_exit0_row_still_gets_no_landing_question(self):
        """The question is only open for a killed dispatch. `exit0` already
        proves the lane file grew."""
        self.estate_with(when("12:11:47"), suffix="exit0")
        self.assertIsNone(self.row_for("glm-c", self.BRIEF)["landing"])


# --------------------------------------------------------------------------
# THE ASYMMETRY. This is the class the brief is really about.
# --------------------------------------------------------------------------

class TheAsymmetrySurvivesIntoTheCode(unittest.TestCase):

    START = when("09:16:52")
    DONE = when("11:47:00")

    def test_mtime_before_start_is_not_appended_and_is_a_real_negative(self):
        state, leg = lr.lane_mtime_leg(when("09:00:00"), self.START,
                                       self.DONE)
        self.assertEqual(state, lr.LANE_MTIME_NOT_APPENDED)
        self.assertIs(leg, False)

    def test_mtime_inside_the_window_is_appended_during_the_run(self):
        state, leg = lr.lane_mtime_leg(when("10:30:00"), self.START,
                                       self.DONE)
        self.assertEqual(state, lr.LANE_MTIME_DURING)
        self.assertIs(leg, True)

    def test_mtime_after_done_is_inconclusive_and_never_positive(self):
        """THE SENTENCE THE BRIEF ASKS TO SURVIVE INTO THE CODE.

        `Do not let a later-mtime case render as LANDED.` Asserted on the
        leg being None rather than on the verdict, because the verdict could
        be LANDED for a different and legitimate reason - another leg - and
        this test is about THIS leg contributing nothing.
        """
        state, leg = lr.lane_mtime_leg(when("12:11:47"), self.START,
                                       self.DONE)
        self.assertEqual(state, lr.LANE_MTIME_AFTER)
        self.assertIsNone(leg)

    def test_an_unreadable_mtime_is_unread_and_not_inconclusive(self):
        """Two different words with two different repairs: go and look,
        versus there is nothing to look at."""
        state, leg = lr.lane_mtime_leg(None, self.START, self.DONE)
        self.assertEqual(state, lr.LANE_MTIME_UNREAD)
        self.assertIsNone(leg)
        self.assertNotEqual(state, lr.LANE_MTIME_AFTER)

    def test_a_missing_done_is_inconclusive_and_not_positive(self):
        """Still running, or a DONE the reader could not find. There is no
        upper bound to place the mtime against."""
        state, leg = lr.lane_mtime_leg(when("10:30:00"), self.START, None)
        self.assertEqual(state, lr.LANE_MTIME_AFTER)
        self.assertIsNone(leg)

    def test_an_after_done_mtime_alone_cannot_reach_landed(self):
        """Through `landing`, with every other leg given nothing."""
        found = lr.landing([], starts_for_task=None,
                           lane_mtime_state=lr.LANE_MTIME_AFTER)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)

    def test_an_in_window_mtime_alone_cannot_reach_landed_either(self):
        """CORRECTED BY TASK-0270, AND THE OLD NAME ASSERTED THE DEFECT.

        This test was `..._can_reach_landed` and required `LANDED` off an
        mtime alone, on the reasoning that the paired direction had to
        contribute something or the test above would be vacuous. The
        measurement that refuted it: a dispatch whose lane file names its
        id NOWHERE - `entry` leg FALSE, the authority answering NO - read
        LANDED off nothing but the file having been touched inside the
        window, and the page then printed "at least one positive authority
        was read: a lane-file entry that only this dispatch could have
        written" about a row with no entry. Every lane file is touched by
        something during a 150-minute window.

        `CONTINUITY.md` §3 licenses the mtime as evidence of ABSENCE only,
        and `landing`'s own interlock says so in those words.

        THE LEG STILL CONTRIBUTES, so the test above is still not vacuous -
        it contributes by keeping LOST out of reach, which the next test
        asserts directly.
        """
        found = lr.landing([], starts_for_task=None,
                           lane_mtime_state=lr.LANE_MTIME_DURING)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)
        self.assertIs(found["legs"]["lane_mtime"], True)

    def test_an_in_window_mtime_still_blocks_lost(self):
        """What the leg is FOR, now that it does not license LANDED.

        Every other authority read and empty, which is the LOST shape, and
        the mtime says something was written while this dispatch was alive.
        LOST needs every authority read AND empty, so it is out of reach -
        and the honest answer is the middle state.
        """
        lost = lr.landing([], starts_for_task=1, commits_in_window=[],
                          artefacts_in_window=[], requeued=False,
                          lane_mtime_state=lr.LANE_MTIME_NOT_APPENDED)
        self.assertEqual(lost["verdict"], lr.LOST)
        # The control: the SAME five authorities with only the mtime word
        # changed. Without it this test would pass against a reader that
        # never reaches LOST at all.
        found = lr.landing([], starts_for_task=1, commits_in_window=[],
                           artefacts_in_window=[], requeued=False,
                           lane_mtime_state=lr.LANE_MTIME_DURING)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)

    def test_a_row_with_no_entry_at_all_never_reads_landed(self):
        """The live-shaped case, end to end through the page's own reader.

        A TIMEOUT dispatch, a lane file that exists and names a DIFFERENT
        task, and an mtime inside the window - which is what every lane
        file's mtime looks like during a 150-minute run. Before TASK-0270
        this printed LANDED with `unread` empty, so the page offered no
        hint that the entry authority had answered NO.
        """
        found = lr.landing([], starts_for_task=1,
                           lane_mtime_state=lr.LANE_MTIME_DURING)
        self.assertIs(found["legs"]["entry"], False)
        self.assertNotEqual(found["verdict"], lr.LANDED)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)
        # AND THE MISSING AUTHORITIES ARE NAMED, which they were not while
        # the verdict was LANDED: `unread` is emptied for LANDED on purpose.
        self.assertIn("commit", found["unread"])
        self.assertIn("artefact", found["unread"])

    def test_every_state_has_a_glossary_entry(self):
        for state in (lr.LANE_MTIME_NOT_APPENDED, lr.LANE_MTIME_DURING,
                      lr.LANE_MTIME_AFTER, lr.LANE_MTIME_UNREAD):
            self.assertIn(state, lr.LANE_MTIME_TEXT)
            label, why = lr.LANE_MTIME_TEXT[state]
            self.assertTrue(label and why)


class TheInterlock(unittest.TestCase):
    """The one place a leg can take another leg away.

    A lane file untouched since before START cannot hold anything THIS
    dispatch wrote, so an entry in it is an earlier dispatch's and may not
    license LANDED for this one.
    """

    def entry(self):
        return [{"body": REPORT, "text": "TASK-0220", "task_ids": ["220"]}]

    def test_an_entry_with_one_start_normally_licenses_landed(self):
        """The control. Without it the test below passes because the entry
        leg never fired in the first place."""
        found = lr.landing(self.entry(), starts_for_task=1)
        self.assertEqual(found["verdict"], lr.LANDED)
        self.assertIs(found["legs"]["entry"], True)
        self.assertFalse(found["entry_demoted_by_mtime"])

    def test_a_not_appended_mtime_withdraws_that_entry_leg(self):
        found = lr.landing(self.entry(), starts_for_task=1,
                           lane_mtime_state=lr.LANE_MTIME_NOT_APPENDED)
        self.assertIsNone(found["legs"]["entry"])
        self.assertTrue(found["entry_demoted_by_mtime"])
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)

    def test_the_withdrawal_is_published_and_not_silent(self):
        """A leg taken away without a reason is a page that disagrees with
        its own evidence and will not say why."""
        found = lr.landing(self.entry(), starts_for_task=1,
                           lane_mtime_state=lr.LANE_MTIME_NOT_APPENDED)
        self.assertIn("entry_demoted_by_mtime", found)
        self.assertTrue(found["entry_demoted_by_mtime"])

    def test_the_interlock_runs_in_one_direction_only(self):
        """An in-window mtime must not turn a False entry leg into True.

        The mtime is licensed as evidence of ABSENCE and never of presence,
        so it may weaken the entry leg and never strengthen it.
        """
        found = lr.landing([], starts_for_task=1,
                           lane_mtime_state=lr.LANE_MTIME_DURING)
        self.assertIs(found["legs"]["entry"], False)
        self.assertFalse(found["entry_demoted_by_mtime"])

    def test_an_inconclusive_mtime_withdraws_nothing(self):
        found = lr.landing(self.entry(), starts_for_task=1,
                           lane_mtime_state=lr.LANE_MTIME_AFTER)
        self.assertIs(found["legs"]["entry"], True)
        self.assertFalse(found["entry_demoted_by_mtime"])

    def test_lost_now_needs_the_fifth_leg_read_and_empty_too(self):
        """LOST was all four read and empty. It is all FIVE now."""
        four = lr.landing([], starts_for_task=1, commits_in_window=[],
                          artefacts_in_window=[], requeued=False)
        self.assertEqual(four["verdict"], lr.NOT_DETERMINED,
                         "the fifth leg is unread, so LOST is out of reach")
        five = lr.landing([], starts_for_task=1, commits_in_window=[],
                          artefacts_in_window=[], requeued=False,
                          lane_mtime_state=lr.LANE_MTIME_NOT_APPENDED)
        self.assertEqual(five["verdict"], lr.LOST)


# --------------------------------------------------------------------------
# THE TOKENS, AND THE ONE THAT MUST NOT BE BUCKETED.
# --------------------------------------------------------------------------

class TheTokenEnumerator(Base):

    def estate_with_tokens(self):
        self.estate.log("glm-c", [
            up("glm-c"),
            start("glm-c", "01:41:56", "0220-a.md"),
            done("glm-c", "01:45:01", "0220-a.md", "exit1"),
            start("glm-c", "09:16:52", "0220-b.md"),
            done("glm-c", "11:47:00", "0220-b.md", "TIMEOUT"),
            start("glm-c", "11:48:00", "0230-c.md"),
            done("glm-c", "11:49:00", "0230-c.md", "exit"),
        ])

    def test_every_token_written_is_counted_with_a_denominator(self):
        self.estate_with_tokens()
        got = lanes.watcher_tokens(self.estate.root)
        self.assertEqual(got["state"], lanes.PRESENT)
        self.assertEqual(got["done_lines"], 3)
        self.assertEqual(got["tokens"],
                         {"exit1": 1, "TIMEOUT": 1, "exit": 1})
        self.assertEqual(got["unparsed"], [])

    def test_a_token_nobody_described_is_listed_as_unknown(self):
        """C3. The planted verdict goes through the SAME reader and must
        come back named, not bucketed."""
        self.estate_with_tokens()
        got = lanes.watcher_tokens(self.estate.root, extra_lines=[
            done("glm-c", "11:50:00", "0240-d.md", "BANANA")])
        self.assertIn("BANANA", got["tokens"])
        self.assertEqual(got["tokens"]["BANANA"], 1)
        self.assertEqual(got["unknown"], ["BANANA"])
        # AND IT DID NOT LAND IN A KNOWN BUCKET. The counts of the described
        # tokens are unchanged by the plant, which is the measurement that
        # rules out silent bucketing.
        self.assertEqual(got["tokens"]["exit1"], 1)
        self.assertEqual(got["tokens"]["TIMEOUT"], 1)

    def test_an_undescribed_token_renders_as_unknown_token(self):
        short, why, described = lanes.done_meaning("BANANA")
        self.assertEqual(short, "UNKNOWN TOKEN")
        self.assertFalse(described)
        self.assertIn("NOT rounded", why)

    def test_done_meaning_never_returns_a_blank(self):
        """A blank cell reads as "no problem here", which is the opposite of
        what an unknown token means."""
        for token in ("", None, "exit0", "TIMEOUT", "nonsense"):
            short, why, _described = lanes.done_meaning(token)
            self.assertTrue(short, token)
            self.assertTrue(why, token)

    def test_a_described_token_says_it_is_described(self):
        """The paired direction, so the test above is not satisfied by a
        reader that answers UNKNOWN to everything."""
        for token in sorted(lanes.DONE_MEANINGS):
            short, why, described = lanes.done_meaning(token)
            self.assertTrue(described, token)
            self.assertNotEqual(short, "UNKNOWN TOKEN", token)

    def test_a_malformed_done_line_is_counted_not_skipped(self):
        """A denominator that silently drops what it could not read is not a
        denominator."""
        self.estate.log("glm-c", [
            up("glm-c"),
            "[%s] [glm-c] DONE  a-brief-with-no-arrow.md" % stamp("11:00:00"),
        ])
        got = lanes.watcher_tokens(self.estate.root)
        self.assertEqual(got["done_lines"], 1)
        self.assertEqual(len(got["unparsed"]), 1)
        self.assertEqual(got["tokens"], {})

    def test_the_two_tokens_this_task_described_are_described(self):
        """`exit1` and a bare `exit` were written and named by nothing."""
        for token in ("exit1", "exit"):
            self.assertIn(token, lanes.DONE_MEANINGS, token)
        self.assertIn("NO EXIT CODE WAS RECORDED",
                      lanes.DONE_MEANINGS["exit"][0])

    def test_an_absent_log_directory_is_a_state_and_not_zero_tokens(self):
        folder = tempfile.mkdtemp(prefix="timeout-0250-empty-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        got = lanes.watcher_tokens(folder)
        self.assertEqual(got["state"], lanes.ABSENT)
        self.assertEqual(got["tokens"], {})
        self.assertEqual(got["done_lines"], 0)

    def test_an_unconfigured_estate_is_its_own_state(self):
        """Nobody has said where the estate is - and the EMPTY STRING is not
        how you say that to this reader.

        `watcher_tokens(root="")` falls through `root or ops_root()`, so a
        blank argument does not mean "unconfigured", it means "ask the
        environment". With `LANE_OPS_DIR` set - which is the only
        environment in which the page actually renders - this assertion was
        reading the LIVE estate and the state was `present`. The variable is
        cleared and restored here, so the test asserts what its name says
        whatever the caller's shell holds. Measured 2026-10-16 by running
        this module with `LANE_OPS_DIR` set: 1 failure, `- present`.
        """
        previous = os.environ.pop(lanes.OPS_DIR, None)
        if previous is not None:
            self.addCleanup(os.environ.__setitem__, lanes.OPS_DIR, previous)
        self.assertIsNone(lanes.ops_root())
        got = lanes.watcher_tokens("")
        self.assertEqual(got["state"], lanes.UNCONFIGURED)


# --------------------------------------------------------------------------
# C4: THE COLUMN IS WITHHELD WHEN A CONTROL FAILS.
# --------------------------------------------------------------------------

class TheColumnIsWithheldWhenAControlFails(Base):

    def rows_with_an_unread_leg(self):
        return [{"lane": "glm-c", "brief": "0220.md", "at": "x",
                 "done": "y", "suffix": "TIMEOUT", "minutes": 150.1,
                 "landing": lr.landing([], starts_for_task=None,
                                       lane_mtime_state=lr.LANE_MTIME_AFTER)}]

    def test_the_controls_pass_on_real_rows(self):
        checks = lr.clock_controls(self.rows_with_an_unread_leg())
        self.assertEqual(len(checks), 5)
        for check in checks:
            self.assertTrue(check["ok"],
                            "%s: %s" % (check["name"], check["detail"]))

    def test_rows_not_passed_is_a_failure_and_not_a_pass(self):
        """A check that could not look did not pass."""
        checks = {check["name"]: check for check in lr.clock_controls(None)}
        self.assertFalse(
            checks["at least one rendered cell reads UNREAD"]["ok"])

    def test_a_table_with_no_unread_cell_fails_the_control(self):
        """A board with no UNREAD anywhere is a board that is guessing.

        Every leg is given a definite value, which cannot happen on the real
        page - the worktree leg is unreadable from a page by construction -
        so this state existing at all would mean a refusal had been quietly
        turned into an answer.
        """
        rows = [{"landing": lr.landing(
            [{"body": REPORT, "task_ids": ["220"]}], starts_for_task=1,
            commits_in_window=["abc"], artefacts_in_window=["f"],
            requeued=False, lane_mtime_state=lr.LANE_MTIME_DURING)}]
        legs = rows[0]["landing"]["legs"]
        self.assertFalse([k for k, v in legs.items() if v is None],
                         "this fixture is meant to have no UNREAD leg")
        checks = {check["name"]: check for check in lr.clock_controls(rows)}
        self.assertFalse(
            checks["at least one rendered cell reads UNREAD"]["ok"])

    def test_the_renderer_prints_the_column_when_the_controls_pass(self):
        html = pages.lane_rework(self.payload(ok=True))
        self.assertIn("lane file&#x27;s clock", html)
        self.assertIn("the clock leg can print NOT APPENDED", html)
        self.assertNotIn("COLUMN WITHHELD", html)

    def test_the_renderer_withholds_the_column_when_one_fails(self):
        html = pages.lane_rework(self.payload(ok=False))
        self.assertNotIn("lane file&#x27;s clock", html)
        self.assertIn("COLUMN WITHHELD", html)
        # AND THE OTHER FOUR LEGS SURVIVE. Withholding one column is not a
        # reason to stop answering the question the panel exists for.
        self.assertIn("re-queued", html)

    def payload(self, ok):
        """A real `api.lane_rework` payload with the controls forced.

        BUILT BY THE REAL SERVICE LAYER against this test's own temporary
        estate - `LANE_OPS_DIR` is pointed at it and restored - and then only
        the three fields the renderer reads for this decision are set. A
        hand-written dict would be a second copy of the payload shape and
        would pass while the real one broke, which is how a renderer test
        comes to test nothing.
        """
        previous = os.environ.get(lanes.OPS_DIR)
        os.environ[lanes.OPS_DIR] = self.estate.root
        try:
            data = api.lane_rework()
        finally:
            if previous is None:
                os.environ.pop(lanes.OPS_DIR, None)
            else:
                os.environ[lanes.OPS_DIR] = previous
        rows = self.rows_with_an_unread_leg()
        checks = lr.clock_controls(rows if ok else None)
        data["killed_rows"] = rows
        data["killed"] = len(rows)
        data["landing_tally"] = {"not_determined": 1}
        data["clock_controls"] = checks
        data["clock_controls_ok"] = all(check["ok"] for check in checks)
        data["clock_controls_failed"] = [check["name"] for check in checks
                                         if not check["ok"]]
        return data


class TheLiveEstateIsNotRead(unittest.TestCase):
    """The boundary, asserted rather than promised."""

    def test_the_reader_takes_its_root_as_an_argument(self):
        """So a test can point it at a temporary directory, and so this
        module never touches `LANE_OPS_DIR`."""
        import inspect
        self.assertIn("root",
                      inspect.signature(lanes.watcher_tokens).parameters)
        self.assertIn("root",
                      inspect.signature(lr.lane_rework).parameters)


if __name__ == "__main__":                                  # pragma: no cover
    unittest.main()
