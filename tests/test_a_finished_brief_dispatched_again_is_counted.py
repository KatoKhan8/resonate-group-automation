"""A brief the lane had already finished, dispatched again, counted and priced.

WHAT THIS FILE IS FOR. The watcher dispatches the lowest-numbered file in
`queue/<lane>/`. A lane session that runs ahead of its own queue - which the
standing rules require - cannot tell it, and it cannot ask. So a finished
brief gets dispatched again and a whole run is spent re-deriving an artifact
that already exists. Six instances were recorded by hand on 2026-10-16 in six
hours; `src.lanerework` finds them and prices them, and this file is the
proof that it can be wrong in every direction it is allowed to answer.

NOTHING HERE READS THE REAL ESTATE. Every watcher log and every lane file
below is a string written into a temporary directory, and every commit date
is a dict handed to the reader. `C6` replays the six real instances, but as
LITERAL lines copied out of the real logs and lane files - the exact bytes,
with the exact em dashes and the exact `Z` suffixes - so the regression is
deterministic and needs neither the estate nor a git repository.

THE CONTROLS, AND WHY THERE ARE SIX. `C1` alone proves a classifier that
says yes; `C2` and `C3` are the paired controls that make it a measurement.
`C4` holds the fail-closed rung: an entry nothing dates is UNKNOWN and never
becomes clean. `C5` is the control FOR the controls - `0130` recorded that
its own C4 could not detect a classifier calling everything LOGGED, and that
the PAIR was the real measurement - so it mutates in both directions and
names a kill-set each way. `C6` is the regression.

THE FOUR STATES ARE KEPT APART ON PURPOSE. A START the lane file never
mentions (`NO_ENTRY`) and a START whose entry cannot be dated (`UNDATED`)
are different facts with different repairs, and only the second is UNKNOWN.
A lane whose log cannot be read (`UNREADABLE`) is UNKNOWN in every cell
rather than zero in all of them, and `C_RENDER` proves the panel cannot
print those two as the same thing.
"""
import datetime
import os
import shutil
import tempfile
import unittest

from src import lanerework as lr

#: The machine this estate runs on. Measured, not assumed: the lane headings
#: that carry a `Z` are UTC and the watcher's own stamps are naive local, so
#: a reader with the wrong offset mis-dates every `Z` entry by two hours.
OFFSET = 2.0

#: Two lanes, because a single-lane fixture cannot tell a per-lane read from
#: a global one - both pass. `beta` also makes the lane-name refusal in the
#: commit rung testable at all.
ALPHA = "alpha"
BETA = "beta"
KNOWN = (ALPHA, BETA)

DAY = "2026-10-16"


def stamp(clock, day=DAY):
    return "%s %s" % (day, clock)


def when(clock, day=DAY):
    return datetime.datetime.strptime(stamp(clock, day), "%Y-%m-%d %H:%M:%S")


def up(lane, clock="00:00:00", day=DAY):
    return ("[%s] [%s] watcher up. tree=C:\\somewhere mode=bypassPermissions "
            "timeout=90m" % (stamp(clock, day), lane))


def start(lane, clock, brief, day=DAY):
    return "[%s] [%s] START %s" % (stamp(clock, day), lane, brief)


def done(lane, clock, brief, suffix="exit0", day=DAY):
    return "[%s] [%s] DONE  %s -> %s" % (stamp(clock, day), lane, brief,
                                         suffix)


class Estate(object):
    """A temporary ops root. Nothing in it is read by anything but the test."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="rework-")
        os.makedirs(os.path.join(self.root, "logs"))
        os.makedirs(os.path.join(self.root, "queue"))

    def log(self, lane, lines):
        path = os.path.join(self.root, "logs", "watcher-%s.log" % lane)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\ufeff" + "\n".join(lines) + "\n")

    def lane_file(self, lane, text):
        path = os.path.join(self.root, "LANE-%s.md" % lane)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class Base(unittest.TestCase):

    def setUp(self):
        self.estate = Estate()
        self.addCleanup(self.estate.close)

    def read(self, lane, commits=None):
        return lr.lane_rework(self.estate.root, lane, commits=commits or {},
                              offset_hours=OFFSET, known=KNOWN)

    def row(self, lane, brief, commits=None):
        data = self.read(lane, commits=commits)
        self.assertEqual(data["state"], "present", data)
        matches = [item for item in data["rows"] if item["brief"] == brief]
        self.assertEqual(len(matches), 1,
                         "expected exactly one START for %r, got %r"
                         % (brief, [item["brief"] for item in data["rows"]]))
        return matches[0], data


# --------------------------------------------------------------------- C1


class C1ClosedBeforeTheStart(Base):
    """A START at T whose entry closed at T-10 is a re-dispatch, named."""

    BRIEF = "0010-the-thing.md"

    def setUp(self):
        super(C1ClosedBeforeTheStart, self).setUp()
        self.estate.log(ALPHA, [up(ALPHA),
                                start(ALPHA, "03:00:00", self.BRIEF),
                                done(ALPHA, "03:12:00", self.BRIEF)])
        # Closed at 02:50, ten minutes before the START at 03:00.
        self.estate.lane_file(ALPHA,
                              "# 2026-10-16 02:40-02:50 \u2014 TASK 0010 "
                              "\u2014 the thing, done\n\nbody\n")

    def test_c1_the_verdict_is_rework(self):
        row, _ = self.row(ALPHA, self.BRIEF)
        self.assertEqual(row["verdict"], lr.REWORK)

    def test_c1_names_the_entry_the_field_and_the_value(self):
        """Not just the verdict. A control that reads only the verdict passes
        when a DIFFERENT rung answered first, which is how a guard gets
        credited for a decision it did not make."""
        row, _ = self.row(ALPHA, self.BRIEF)
        self.assertEqual(row["field"], lr.D_RANGE)
        self.assertEqual(row["value"], when("02:50:59"))
        self.assertEqual(row["entry"], 1)
        self.assertIn("TASK 0010", row["detail"])

    def test_c1_the_cost_is_the_dispatched_runs_own_elapsed_time(self):
        row, data = self.row(ALPHA, self.BRIEF)
        self.assertAlmostEqual(row["minutes"], 12.0)
        self.assertAlmostEqual(data["minutes"], 12.0)
        self.assertEqual(data["minutes_unknown"], 0)

    def test_c1_the_tally_counts_it_once_against_one_start(self):
        _, data = self.row(ALPHA, self.BRIEF)
        self.assertEqual(data["starts"], 1)
        self.assertEqual(data["tally"], {lr.REWORK: 1})


# --------------------------------------------------------------------- C2


class C2ClosedAfterTheStart(Base):
    """A START at T whose entry closed at T+30 is NOT a re-dispatch.

    Without this, C1 has proven a classifier that answers yes.
    """

    BRIEF = "0010-the-thing.md"

    def setUp(self):
        super(C2ClosedAfterTheStart, self).setUp()
        self.estate.log(ALPHA, [up(ALPHA),
                                start(ALPHA, "03:00:00", self.BRIEF),
                                done(ALPHA, "03:31:00", self.BRIEF)])
        self.estate.lane_file(ALPHA,
                              "# 2026-10-16 03:00-03:30 \u2014 TASK 0010 "
                              "\u2014 the thing, done\n\nbody\n")

    def test_c2_the_verdict_is_fresh(self):
        row, _ = self.row(ALPHA, self.BRIEF)
        self.assertEqual(row["verdict"], lr.FRESH)

    def test_c2_fresh_is_not_unknown_and_not_rework(self):
        row, data = self.row(ALPHA, self.BRIEF)
        self.assertNotIn(row["verdict"], lr.UNKNOWN_VERDICTS)
        self.assertIn(row["verdict"], lr.NOT_REWORK)
        self.assertEqual(data["tally"], {lr.FRESH: 1})

    def test_c2_contributes_no_minutes(self):
        """The cost column prices re-dispatches only. A 31-minute first run
        is work, not waste, and adding it would make the figure the lane's
        whole runtime."""
        data = self.read(ALPHA)
        self.assertAlmostEqual(data["minutes"], 0.0)
        self.assertEqual(data["unpriced"], [])


# --------------------------------------------------------------------- C3


class C3NoEntryAtAll(Base):
    """A START the lane file never mentions is NOT a re-dispatch, and NOT
    UNKNOWN.

    WHICH, AND THE JUSTIFICATION. The authority the brief names is
    `LANE-<lane>.md`, and here it is readable and it answers: it records no
    entry for this id, so no work was recorded as landed before the
    dispatch. That is a positive answer from a readable authority, which is
    categorically different from an authority that cannot be read.

    ITS LIMIT IS STATED RATHER THAN HIDDEN, and `C3_LIMIT` below pins it:
    `glm/0060` committed six mutation-proven tests and wrote no lane entry,
    so a run whose work DID land can look exactly like this. The state is
    therefore its own - `NO_ENTRY`, not `FRESH` - it is counted in
    `blind_spots()` with its denominator, and `commit_only()` prices the
    cohort against git. What it must never be is folded into the clean
    bucket and forgotten, which is the whole reason it is not `FRESH`.
    """

    BRIEF = "0010-the-thing.md"

    def setUp(self):
        super(C3NoEntryAtAll, self).setUp()
        self.estate.log(ALPHA, [up(ALPHA),
                                start(ALPHA, "03:00:00", self.BRIEF),
                                done(ALPHA, "03:31:00", self.BRIEF)])
        self.estate.lane_file(ALPHA,
                              "# 2026-10-16 \u2014 TASK 0020 \u2014 "
                              "a different brief entirely\n\nbody\n")

    def test_c3_the_verdict_is_no_entry(self):
        row, _ = self.row(ALPHA, self.BRIEF)
        self.assertEqual(row["verdict"], lr.NO_ENTRY)
        self.assertEqual(row["entries"], 0)

    def test_c3_is_not_rework_and_not_unknown(self):
        row, _ = self.row(ALPHA, self.BRIEF)
        self.assertIn(row["verdict"], lr.NOT_REWORK)
        self.assertNotIn(row["verdict"], lr.UNKNOWN_VERDICTS)

    def test_c3_is_a_state_of_its_own_and_not_merged_into_fresh(self):
        """The two are both 'not a re-dispatch' and they are not the same
        fact, so the panel counts them in separate columns."""
        row, data = self.row(ALPHA, self.BRIEF)
        self.assertNotEqual(row["verdict"], lr.FRESH)
        self.assertEqual(data["tally"], {lr.NO_ENTRY: 1})

    def test_c3_limit_is_counted_with_its_denominator(self):
        """The blind spot is a figure on the panel, not a sentence in a
        docstring. A limit nobody reads is a limit nobody applies."""
        data = lr.rework(root=self.estate.root, lanes_wanted=[ALPHA],
                         commits={}, now=when("09:00:00"))
        spot = lr.blind_spots(data)[0]
        self.assertEqual(spot["size"], 1)
        self.assertEqual(spot["denominator"], 1)


# --------------------------------------------------------------------- C4


class C4EntryWithNoReadableCloseTime(Base):
    """An entry that exists and cannot be dated is UNKNOWN.

    THE FAIL-CLOSED RUNG. `0?:??` is a real heading in LANE-pilotcaps.md,
    and a reader that shrugged at it and said "not a re-dispatch" would
    render an absence of evidence as evidence of absence - the defect
    `OUTCOME_TEXT[refused]` shipped, where eight tasks that ran 158.5
    unrecorded minutes were described as having NEVER RUN.
    """

    BRIEF = "0010-the-thing.md"

    def setUp(self):
        super(C4EntryWithNoReadableCloseTime, self).setUp()
        self.estate.log(ALPHA, [up(ALPHA),
                                start(ALPHA, "03:00:00", self.BRIEF),
                                done(ALPHA, "03:31:00", self.BRIEF)])
        # Same DAY as the START, so the date rung cannot order it, and an
        # unreadable clock, so no time rung can either.
        self.estate.lane_file(ALPHA,
                              "# 2026-10-16 0?:?? \u2014 TASK 0010 \u2014 "
                              "the thing, at some point\n\nbody\n")

    def test_c4_the_verdict_is_undated(self):
        row, _ = self.row(ALPHA, self.BRIEF)
        self.assertEqual(row["verdict"], lr.UNDATED)

    def test_c4_undated_is_unknown_and_never_clean(self):
        row, data = self.row(ALPHA, self.BRIEF)
        self.assertIn(row["verdict"], lr.UNKNOWN_VERDICTS)
        self.assertNotIn(row["verdict"], lr.NOT_REWORK)
        self.assertEqual(data["tally"], {lr.UNDATED: 1})

    def test_c4_the_estate_rollup_files_it_as_unknown_and_not_as_clean(self):
        """The lane tally and the estate rollup are two pieces of code.

        `M1` - the fallback this control forbids - was killed by the two
        tests above and SURVIVED at the estate level until this one existed,
        because `rework()` buckets a verdict by its membership of
        `UNKNOWN_VERDICTS` and `NOT_REWORK` in its own loop. A panel reads
        the estate figure, not the lane tally.
        """
        data = lr.rework(root=self.estate.root, lanes_wanted=[ALPHA],
                         commits={}, now=when("09:00:00"))
        self.assertEqual(data["unknown"], 1)
        self.assertEqual(data["not_rework"], 0)
        self.assertEqual(data["rework"], 0)
        self.assertEqual(data["starts"], 1)
        self.assertEqual(data["lanes_unknown"], 0)

    def test_c4_the_entry_was_found_and_only_its_date_was_not(self):
        """The distinction C3 and C4 exist to keep apart: the entry IS
        there. A reader that reported zero entries here would be describing
        a different fact with the same word."""
        row, _ = self.row(ALPHA, self.BRIEF)
        self.assertEqual(row["entries"], 1)
        self.assertEqual(row["field"], lr.D_NONE)
        self.assertEqual([item["position"] for item in row["placements"]],
                         [lr.UNDATABLE])


# -------------------------------------------------------- C_RENDER, C_UNREAD


class CUnreadableLaneIsNotZero(Base):
    """A lane with no readable log is UNKNOWN in every cell, not zero."""

    def test_an_absent_log_is_unreadable_not_an_idle_lane(self):
        self.estate.lane_file(ALPHA, "# 2026-10-16 \u2014 TASK 0010\n")
        data = self.read(ALPHA)
        self.assertEqual(data["state"], lr.UNREADABLE)
        self.assertIsNone(data["starts"])
        self.assertEqual(data["rows"], [])
        self.assertEqual(data["tally"], {})

    def test_an_unreadable_lane_file_is_unreadable_too(self):
        """The log is readable and the authority it must be crossed against
        is not. Reporting "no entries found" here would turn a missing
        authority into a clean sheet for every START in the lane."""
        self.estate.log(ALPHA, [up(ALPHA),
                                start(ALPHA, "03:00:00", "0010-a.md")])
        data = self.read(ALPHA)
        self.assertEqual(data["state"], lr.UNREADABLE)
        self.assertEqual(data["lane_file_state"], "absent")
        self.assertIsNone(data["starts"])

    def test_an_unreadable_lane_is_in_no_estate_column(self):
        """The estate denominator is the number of starts actually read, and
        the panel says how many lanes are missing from it. A lane summed in
        as zero would make the estate ratio a different question."""
        self.estate.log(BETA, [up(BETA),
                               start(BETA, "03:00:00", "0010-b.md"),
                               done(BETA, "03:10:00", "0010-b.md")])
        self.estate.lane_file(BETA, "# 2026-10-16 \u2014 TASK 0020 \u2014 x\n")
        data = lr.rework(root=self.estate.root, lanes_wanted=[ALPHA, BETA],
                         commits={}, now=when("09:00:00"))
        self.assertEqual(data["lanes_unknown"], 1)
        self.assertEqual(data["lane_count"], 2)
        self.assertEqual(data["starts"], 1)

    def test_the_rendered_words_for_zero_and_unknown_differ(self):
        """The brief requires the distinction be visible to someone
        glancing. Asserted on the words that travel with the data, because
        a renderer holding its own table is a second authority."""
        self.assertIn("UNKNOWN", lr.VERDICT_TEXT[lr.UNDATED][0])
        self.assertIn("UNKNOWN", lr.VERDICT_TEXT[lr.UNREADABLE][0])
        self.assertNotIn("UNKNOWN", lr.VERDICT_TEXT[lr.FRESH][0])
        self.assertNotIn("UNKNOWN", lr.VERDICT_TEXT[lr.NO_ENTRY][0])
        self.assertNotEqual(lr.VERDICT_TEXT[lr.UNDATED],
                            lr.VERDICT_TEXT[lr.UNREADABLE])
        for name in lr.VERDICT_ORDER:
            self.assertIn(name, lr.VERDICT_TEXT)


# ------------------------------------------------------- the filename trap


class AFilenameIsNotATask(Base):
    """`0234b` is not `0234`, and a rewritten brief is flagged, not counted.

    The brief is explicit: pilotcaps 0233 and 0235 were rewritten while
    keeping their filenames, deliberately, so the dispatcher's sort order
    would hold. Filename equality is not task equality - and neither is id
    equality, which is why the brief's mtime is read and the row is marked.
    """

    def test_a_suffixed_id_does_not_answer_for_its_stem(self):
        self.estate.log(ALPHA, [up(ALPHA),
                                start(ALPHA, "03:00:00", "0234-a.md"),
                                done(ALPHA, "03:10:00", "0234-a.md")])
        self.estate.lane_file(
            ALPHA, "# 2026-10-16 02:00-02:30 \u2014 TASK 0234b \u2014 the "
                   "other brief\n\nbody\n")
        row, _ = self.row(ALPHA, "0234-a.md")
        self.assertEqual(row["verdict"], lr.NO_ENTRY)
        self.assertEqual(row["entries"], 0)

    def test_leading_zeros_do_not_make_two_briefs(self):
        self.estate.log(ALPHA, [up(ALPHA),
                                start(ALPHA, "03:00:00", "0010-a.md"),
                                done(ALPHA, "03:10:00", "0010-a.md")])
        self.estate.lane_file(ALPHA,
                             "# 2026-10-16 02:00-02:30 \u2014 TASK 10 "
                             "\u2014 same brief, written without the "
                             "padding\n\nbody\n")
        row, _ = self.row(ALPHA, "0010-a.md")
        self.assertEqual(row["verdict"], lr.REWORK)

    def test_a_brief_rewritten_after_its_entry_is_flagged(self):
        os.makedirs(os.path.join(self.estate.root, "queue", ALPHA))
        path = os.path.join(self.estate.root, "queue", ALPHA, "0010-a.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("a brief rewritten in place\n")
        # mtime after the entry's 02:30 close and before the 03:00 START.
        rewritten = when("02:45:00").timestamp()
        os.utime(path, (rewritten, rewritten))
        self.estate.log(ALPHA, [up(ALPHA),
                                start(ALPHA, "03:00:00", "0010-a.md"),
                                done(ALPHA, "03:10:00", "0010-a.md")])
        self.estate.lane_file(ALPHA,
                             "# 2026-10-16 02:00-02:30 \u2014 TASK 0010 "
                             "\u2014 the first version\n\nbody\n")
        row, _ = self.row(ALPHA, "0010-a.md")
        self.assertEqual(row["verdict"], lr.REWORK)
        self.assertTrue(row["rewritten"])


# ------------------------------------------ the commit rung's lane refusal


class TheCommitRungRefusesAnotherLane(Base):
    """A task NUMBER is per-lane and a commit message is not.

    This cost the module seven false positives on its first real run:
    `38c0db9c4` is "TASK 0100 (GLM-C)" and the `pilotcaps` lane quotes it
    inside its own `TASK 0100` entry, because certifying another lane's
    commit is what that lane is for.
    """

    BRIEF = "0100-a.md"
    SHA = "38c0db9c4"

    def setUp(self):
        super(TheCommitRungRefusesAnotherLane, self).setUp()
        self.estate.log(ALPHA, [up(ALPHA),
                                start(ALPHA, "03:00:00", self.BRIEF),
                                done(ALPHA, "03:10:00", self.BRIEF)])

    def commits(self, subject):
        return {self.SHA: {"when": when("02:00:00"), "subject": subject}}

    def test_a_commit_whose_subject_names_another_lane_is_refused(self):
        self.estate.lane_file(
            ALPHA, "# 2026-10-16 \u2014 TASK 0100 \u2014 certification\n\n"
                   "Measured on `%s`.\n" % self.SHA)
        row, _ = self.row(ALPHA, self.BRIEF,
                          commits=self.commits("TASK 0100 (BETA): the trim"))
        self.assertEqual(row["verdict"], lr.UNDATED)

    def test_a_citing_line_that_names_another_lane_is_refused(self):
        """The subject carries no lane here, so the refusal has to come off
        the entry's own words: `(glm-c commit 21dae6a70)` is how the real
        corpus writes it."""
        self.estate.lane_file(
            ALPHA, "# 2026-10-16 \u2014 TASK 0100 \u2014 certification\n\n"
                   "at beta `%s`, their commit\n" % self.SHA)
        row, _ = self.row(ALPHA, self.BRIEF,
                          commits=self.commits("TASK 0100: the trim"))
        self.assertEqual(row["verdict"], lr.UNDATED)

    def test_this_lanes_own_commit_still_convicts(self):
        """The paired control. Without it the two refusals above have proven
        a rung that refuses everything."""
        self.estate.lane_file(
            ALPHA, "# 2026-10-16 \u2014 TASK 0100 \u2014 certification\n\n"
                   "Measured on `%s`.\n" % self.SHA)
        row, _ = self.row(ALPHA, self.BRIEF,
                          commits=self.commits("TASK 0100: the trim"))
        self.assertEqual(row["verdict"], lr.REWORK)
        self.assertEqual(row["field"], lr.D_COMMIT)
        self.assertEqual(row["attribution"], lr.A_UNCONTRADICTED)

    def test_a_subject_naming_this_lane_is_positively_attributed(self):
        self.estate.lane_file(
            ALPHA, "# 2026-10-16 \u2014 TASK 0100 \u2014 certification\n\n"
                   "Measured on `%s`.\n" % self.SHA)
        row, _ = self.row(ALPHA, self.BRIEF,
                          commits=self.commits("TASK 0100 (ALPHA): the trim"))
        self.assertEqual(row["verdict"], lr.REWORK)
        self.assertEqual(row["attribution"], lr.A_SUBJECT)

    def test_a_commit_not_naming_this_task_is_not_evidence_about_it(self):
        self.estate.lane_file(
            ALPHA, "# 2026-10-16 \u2014 TASK 0100 \u2014 certification\n\n"
                   "Measured on `%s`.\n" % self.SHA)
        row, _ = self.row(ALPHA, self.BRIEF,
                          commits=self.commits("TASK 0090: something else"))
        self.assertEqual(row["verdict"], lr.UNDATED)

    def test_the_longer_lane_name_is_matched_first(self):
        """`glm` is a prefix of `glm-c`. A reader that matches the short
        name first reads `task-glm-c-2026-10-14` as the `glm` lane's own
        branch and accepts a commit belonging to someone else."""
        self.assertEqual(lr.lane_tokens("task-glm-c-2026-10-14", "glm",
                                        ("glm", "glm-b", "glm-c")), ["glm-c"])
        self.assertEqual(lr.lane_tokens("task-glm-review-2026-10-14", "glm",
                                        ("glm", "glm-b", "glm-c")), [])


# -------------------------------------------------- the declaration is not a date


class TheLaneSaysSoItself(Base):
    """An entry declaring itself a re-dispatch convicts its own START.

    AND IT IS NOT ON THE DATING LADDER, which the first version of this
    module got wrong and lost four real re-dispatches to. The two answer
    different questions: the range says when THIS run ran, the declaration
    says the work pre-existed it. A re-dispatch entry answers them in
    opposite directions by construction - `TASK 0030 RE-DISPATCHED (third
    run of this brief)` carries `22:09-22:40` against its own START of
    22:09:20.
    """

    BRIEF = "0030-a.md"

    def setUp(self):
        super(TheLaneSaysSoItself, self).setUp()
        self.estate.log(ALPHA, [up(ALPHA),
                                start(ALPHA, "22:09:20", self.BRIEF),
                                done(ALPHA, "22:40:00", self.BRIEF)])

    def test_a_declaration_convicts_even_when_its_own_range_is_after(self):
        self.estate.lane_file(
            ALPHA, "# 2026-10-16 22:09-22:40 \u2014 TASK 0030 RE-DISPATCHED "
                   "(third run of this brief)\n\nbody\n")
        row, _ = self.row(ALPHA, self.BRIEF)
        self.assertEqual(row["verdict"], lr.REWORK)
        self.assertEqual(row["field"], lr.D_DECLARED)
        self.assertIsNone(row["value"])

    def test_a_clock_rung_is_reported_in_preference_to_the_prose(self):
        """The declaration is prose a model wrote about its own situation,
        and pilotcaps 0230 stamped its re-dispatch entry 76 seconds AFTER
        the START it described. So where a clock reaches the answer, the
        clock is what the panel cites."""
        self.estate.lane_file(
            ALPHA, "# 2026-10-16 20:00-21:00 \u2014 TASK 0030 \u2014 the "
                   "first run\n\nbody\n\n"
                   "# 2026-10-16 22:09-22:40 \u2014 TASK 0030 RE-DISPATCHED"
                   "\n\nbody\n")
        row, _ = self.row(ALPHA, self.BRIEF)
        self.assertEqual(row["verdict"], lr.REWORK)
        self.assertEqual(row["field"], lr.D_RANGE)
        self.assertEqual(row["value"], when("21:00:59"))

    def test_a_future_re_dispatch_is_not_a_declaration(self):
        """`re-dispatch after glm-b's 0040 lands` is a request about the
        future. Reading it as a report about this run would convict a START
        whose work had not landed at all."""
        self.estate.lane_file(
            ALPHA, "# 2026-10-16 \u2014 TASK 0030 \u2014 DEPENDENCY UNMET; "
                   "re-dispatch after beta's 0040 lands\n\nbody\n")
        row, _ = self.row(ALPHA, self.BRIEF)
        self.assertEqual(row["verdict"], lr.UNDATED)
        self.assertFalse(lr.declares("re-dispatch after beta's 0040 lands"))

    def test_a_declaration_convicts_only_the_last_start_of_a_brief(self):
        """With two dispatches of one brief, the declaring run is the second
        and the first is a genuine first run. Convicting both would charge
        the lane twice for one repetition."""
        self.estate.log(ALPHA, [up(ALPHA),
                                start(ALPHA, "20:00:00", self.BRIEF),
                                done(ALPHA, "21:00:00", self.BRIEF),
                                start(ALPHA, "22:09:20", self.BRIEF),
                                done(ALPHA, "22:40:00", self.BRIEF)])
        self.estate.lane_file(
            ALPHA, "# 2026-10-16 0?:?? \u2014 TASK 0030 \u2014 undatable "
                   "first run\n\nbody\n\n"
                   "# 2026-10-16 0?:?? \u2014 TASK 0030 RE-DISPATCHED\n\n"
                   "body\n")
        data = self.read(ALPHA)
        verdicts = [(item["at"], item["verdict"]) for item in data["rows"]]
        self.assertEqual(verdicts, [(stamp("20:00:00"), lr.UNDATED),
                                    (stamp("22:09:20"), lr.REWORK)])


# ----------------------------------------------------- the dating ladder itself


class TheLadderReadsEveryShapeTheCorpusWrites(unittest.TestCase):
    """Every heading form in the real corpus, parsed, with its bound.

    The bound is always the LAST instant the reading could name, because
    every comparison asks "is this before the START" and bounding a fuzzy
    reading at its latest possible instant can only ever UNDER-report.
    """

    def parse(self, text):
        return lr.parse_heading(text, offset_hours=OFFSET)

    def test_an_iso_date_is_not_mistaken_for_a_time_range(self):
        """`2026-10-15 23:04-23:55` holds three hyphens. A reader that looks
        for the range before removing the date finds `10-15`."""
        out = self.parse("2026-10-15 23:04-23:55 \u2014 TASK 0040")
        self.assertEqual(out["shape"], "range")
        self.assertEqual(out["range_end"],
                         when("23:55:59", day="2026-10-15"))

    def test_an_en_dash_is_a_range_separator_and_an_em_dash_is_not(self):
        out = self.parse("TASK-0260 \u2014 2026-10-16 05:55\u201306:05 \u2014 x")
        self.assertEqual(out["range_end"], when("06:05:59"))

    def test_a_zulu_range_is_converted_with_the_measured_offset(self):
        out = self.parse("2026-10-16 02:01Z-02:11Z \u2014 TASK 0231")
        self.assertEqual(out["range_end"], when("04:11:59"))

    def test_a_range_crossing_midnight_lands_on_the_next_day(self):
        out = self.parse("2026-10-15 23:57-00:0x \u2014 TASK 0035")
        self.assertEqual(out["range_end"], when("00:09:59", day="2026-10-16"))

    def test_an_approximate_time_is_bounded_at_the_end_of_its_hour(self):
        out = self.parse("2026-10-16 ~01:40Z \u2014 TASK 0235")
        self.assertEqual(out["shape"], "single")
        self.assertEqual(out["single"], when("03:59:59"))

    def test_a_partial_minute_is_bounded_at_that_tens_digit(self):
        out = self.parse("2026-10-16 00:5x \u2014 TASK 0161")
        self.assertEqual(out["single"], when("00:59:59"))

    def test_an_unreadable_hour_yields_no_time_at_all(self):
        out = self.parse("2026-10-15 0?:?? \u2014 TASK 0020 PILOTCAPS")
        self.assertIsNone(out["single"])
        self.assertIsNone(out["range_end"])
        self.assertEqual(out["date"],
                         datetime.date(2026, 10, 15))

    def test_the_first_date_is_the_entrys_date(self):
        """`2026-10-16 (started 2026-10-15 late)` carries two, and the
        second is a parenthetical about the run."""
        out = self.parse("2026-10-16 (started 2026-10-15 late) \u2014 "
                         "TASK 0160")
        self.assertEqual(out["date"], datetime.date(2026, 10, 16))
        self.assertEqual(out["dates_seen"], 2)

    def test_task_ids_are_read_in_every_shape_the_corpus_writes(self):
        for text, expected in (("TASK 0010", ["10"]),
                               ("TASK-0130", ["130"]),
                               ("TASK 0234c", ["234c"]),
                               ("TASK 1 closed", ["1"]),
                               ("TASK 0161 (GLM-C): save sweep", ["161"]),
                               ("TASK 0020 PILOTCAPS", ["20"]),
                               ("TASK-0233 (REWRITTEN BRIEF)", ["233"])):
            self.assertEqual(self.parse(text)["task_ids"], expected, text)

    def test_a_single_time_never_clears_a_start(self):
        """The corpus writes a dispatch time (`21:07 dispatch`), a start
        time (`01:30 watcher re-run`) and a close time all as one bare
        reading, so it cannot be read as a close time. It is used in the
        strictly-before direction only."""
        entry = {"text": "2026-10-16 05:00 \u2014 TASK 0050", "body": "",
                 "range_end": None, "single": when("05:00:59"),
                 "date": datetime.date(2026, 10, 16)}
        before = lr.rung_readings(entry, "50", when("06:00:00"), {})
        self.assertEqual(before[lr.D_SINGLE]["position"], lr.BEFORE)
        after = lr.rung_readings(entry, "50", when("04:00:00"), {})
        self.assertEqual(after[lr.D_SINGLE]["position"], lr.AT_OR_AFTER)

    def test_a_date_alone_decides_only_across_a_day_boundary(self):
        entry = {"text": "2026-10-15 \u2014 TASK 0010", "body": "",
                 "range_end": None, "single": None,
                 "date": datetime.date(2026, 10, 15)}
        rungs = lr.rung_readings(entry, "10", when("03:00:00"), {})
        self.assertEqual(rungs[lr.D_DATE]["position"], lr.BEFORE)
        same = lr.rung_readings(entry, "10",
                                when("03:00:00", day="2026-10-15"), {})
        self.assertEqual(same[lr.D_DATE]["position"], lr.UNDATABLE)
        earlier = lr.rung_readings(entry, "10",
                                   when("03:00:00", day="2026-10-14"), {})
        self.assertEqual(earlier[lr.D_DATE]["position"], lr.AT_OR_AFTER)

    def test_every_rung_has_a_sentence_and_every_verdict_a_label(self):
        for name in lr.LADDER + (lr.D_NONE, lr.D_DECLARED):
            self.assertIn(name, lr.FIELD_TEXT)
        for name in (lr.A_SUBJECT, lr.A_BRANCHES, lr.A_UNCONTRADICTED):
            self.assertIn(name, lr.ATTRIBUTION_TEXT)


# --------------------------------------------------------------- heading blocks


class AnEntrysBlockEndsAtTheNextEntry(unittest.TestCase):
    """The commit rung reads SHAs out of the entry's own body only.

    `282b22658` is "TASK 0231 re-dispatch" and it is quoted inside the 0234
    entry in LANE-pilotcaps.md. A reader whose block ran to end-of-file
    would hand every entry every SHA in the lane file.
    """

    TEXT = ("# first \u2014 TASK 0010\n"
            "aaa\n"
            "## a subsection of the first\n"
            "bbb\n"
            "# second \u2014 TASK 0020\n"
            "ccc\n")

    def test_a_deeper_heading_stays_inside_its_entry(self):
        found = lr.headings(self.TEXT)
        first = [item for item in found if item["line"] == 1][0]
        self.assertIn("bbb", first["body"])
        self.assertNotIn("ccc", first["body"])

    def test_entries_are_found_at_every_heading_level(self):
        """`suppression` and `pilotcaps` write task entries at `#` and
        `webapp` and `glm-b` at `##`. A reader anchored on `##` finds
        nothing in two of the seven lanes."""
        found = lr.headings("# a \u2014 TASK 0010\nx\n"
                            "## b \u2014 TASK 0020\ny\n"
                            "### c \u2014 TASK 0030\nz\n")
        self.assertEqual([item["level"] for item in found], [1, 2, 3])
        for task in ("10", "20", "30"):
            self.assertEqual(len(lr.entries_for(found, task)), 1, task)


# --------------------------------------------------------------------- C6


#: The six instances the brief records, replayed from the real logs. Each is
#: `(lane, START clock, DONE clock, brief, the real entry heading, the real
#: citing line, {sha: (committer clock, subject)}, expected rung)`. Every
#: string is the exact bytes from `logs/watcher-<lane>.log` and
#: `LANE-<lane>.md` on 2026-10-16.
SIX = (
    ("suppression", "04:22:30", "04:30:22",
     "0210-the-citation-that-was-typed.md",
     "# 2026-10-16 \u2014 TASK-0210 \u2014 nothing verified a line number, "
     "and the premise named the wrong commit",
     "**Measured on `6308f6789`**, pushed and verified (local HEAD and",
     {"6308f6789": ("03:53:30",
                    "TASK-0210: nothing verified a line number, and the "
                    "premise named the wrong commit")},
     lr.D_COMMIT, 7.9),
    ("suppression", "04:30:27", "04:45:37",
     "0220-the-failure-nobody-would-ever-see.md",
     "# 2026-10-16 \u2014 TASK-0220 \u2014 one writer, zero readers, and an "
     "unbounded silence",
     "**Measured on `e59b70258`**, pushed and verified (local HEAD and",
     {"e59b70258": ("04:08:50",
                    "TASK-0220: the bounce recorder's failure is "
                    "unobservable, and the obvious fix does not work")},
     lr.D_COMMIT, 15.2),
    ("pilotcaps", "04:38:59", "04:53:13",
     "0231-criterion-seven-from-the-signature-column.md",
     "# 2026-10-16 02:01Z-02:11Z \u2014 TASK 0231 (pilotcaps): criterion 7 "
     "without a provider call. THE OFFLINE ROUTE WORKS, AND IT IS NOT ENOUGH",
     "no commit quoted in this entry", {}, lr.D_RANGE, 14.2),
    ("pilotcaps", "04:53:18", "05:28:48",
     "0232-the-collision-that-cannot-be-green.md",
     "# 2026-10-16 02:12Z-02:24Z \u2014 TASK 0232 (pilotcaps): two greens "
     "that cannot both hold. REPAIRED, AND THE ATTRIBUTION ON RECORD IS "
     "REFUTED",
     "no commit quoted in this entry", {}, lr.D_RANGE, 35.5),
    ("pilotcaps", "05:43:27", "06:01:53",
     "0234-second-observer-on-the-collision-repair.md",
     "# 2026-10-16 \u2014 TASK 0234 (pilotcaps): SECOND OBSERVER. THE REPAIR "
     "HOLDS, THE TWO ACCOUNTS AGREE, AND THE REFUSAL NOBODY EXECUTED HAD TWO "
     "TESTS THAT NEVER REACHED IT",
     "         5b8dfd108 -> 3c0d9c589 (0232) -> c2883f479 (0234)",
     {"c2883f479": ("05:20:49",
                    "TASK 0234: two tests for the unreadable-brake refusal "
                    "never reached their mock")},
     lr.D_COMMIT, 18.4),
    ("pilotcaps", "06:38:51", "07:18:52",
     "0235-all-nine-at-once.md",
     "# 2026-10-16 ~01:40Z \u2014 TASK 0235 (pilotcaps): all nine at once. "
     "THE ANSWER IS UNKNOWN",
     "    T4  wt-nine-at-once-2026-10-16   5b8dfd108  LF (CR=0)  NEW, "
     "created here",
     {"5b8dfd108": ("03:38:33",
                    "TASK 0235: the positive verification read the wrong "
                    "line and invented a failure")},
     lr.D_COMMIT, 40.0),
)

#: 0235 is the one of the six that TWO rungs convict independently - its
#: `~01:40Z` heading and its own commit - so the entry alone is replayed
#: separately below. Without that, `D_SINGLE` is exercised by nothing in the
#: regression set and the set would go green against a module with that rung
#: deleted.
SINGLE_ONLY = SIX[5]


class C6TheSixRealInstances(Base):
    """All six, replayed. Fewer than six is a result to report, not to tune.

    Each case is its own fixture lane so no case can be carried by another's
    data, and each asserts the RUNG as well as the verdict - a control that
    reads only the verdict credits whichever guard happened to answer.
    """

    def build(self, case):
        lane, began, ended, brief, heading, citing, shas, _rung, _cost = case
        estate = Estate()
        self.addCleanup(estate.close)
        estate.log(lane, [up(lane, "00:00:00"), start(lane, began, brief),
                          done(lane, ended, brief)])
        estate.lane_file(lane, "%s\n\n%s\n" % (heading, citing))
        commits = {sha: {"when": when(clock), "subject": subject}
                   for sha, (clock, subject) in shas.items()}
        data = lr.lane_rework(estate.root, lane, commits=commits,
                              offset_hours=OFFSET,
                              known=("suppression", "pilotcaps"))
        return data["rows"][0], data

    def test_c6_all_six_are_recovered_as_re_dispatches(self):
        found = []
        for case in SIX:
            row, _ = self.build(case)
            if row["verdict"] == lr.REWORK:
                found.append(case[3])
        self.assertEqual(len(found), 6,
                         "recovered %d of 6: %r" % (len(found), found))

    def test_c6_each_is_convicted_by_the_rung_the_record_names(self):
        for case in SIX:
            row, _ = self.build(case)
            self.assertEqual(row["verdict"], lr.REWORK, case[3])
            self.assertEqual(row["field"], case[7], case[3])

    def test_c6_the_cost_of_each_matches_the_watchers_own_clock(self):
        for case in SIX:
            row, data = self.build(case)
            self.assertAlmostEqual(row["minutes"], case[8], places=1,
                                   msg=case[3])
            self.assertAlmostEqual(data["minutes"], case[8], places=1,
                                   msg=case[3])

    def test_c6_more_than_one_rung_is_exercised(self):
        """A regression set that all landed on one rung would go green
        against a module with the other rungs deleted."""
        self.assertEqual({case[7] for case in SIX},
                         {lr.D_COMMIT, lr.D_RANGE})

    def test_c6_0235_is_convicted_a_second_time_by_its_heading_alone(self):
        """The `~01:40Z` reading on its own, with the commit withheld.

        `01:40Z` bounded at the end of its hour is 01:59:59Z, which is
        03:59:59 local - two and a half hours clear of the 06:38:51 START
        it convicts. This is also the only place `D_SINGLE` is exercised
        against real bytes."""
        lane, began, ended, brief, heading = SINGLE_ONLY[:5]
        cost = SINGLE_ONLY[8]
        estate = Estate()
        self.addCleanup(estate.close)
        estate.log(lane, [up(lane, "00:00:00"), start(lane, began, brief),
                          done(lane, ended, brief)])
        estate.lane_file(lane, heading + "\n\nno commit here\n")
        data = lr.lane_rework(estate.root, lane, commits={},
                              offset_hours=OFFSET, known=("pilotcaps",))
        row = data["rows"][0]
        self.assertEqual(row["verdict"], lr.REWORK)
        self.assertEqual(row["field"], lr.D_SINGLE)
        self.assertEqual(row["value"], when("03:59:59"))
        self.assertAlmostEqual(row["minutes"], cost, places=1)


if __name__ == "__main__":
    unittest.main()
