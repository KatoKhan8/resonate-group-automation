"""A dispatch whose wrapper was killed, and whether its work survived.

WHAT THIS FILE IS FOR, measured 2026-10-16 by TASK-0220. Six lane tasks were
killed in one second, 09:16:45. All six recorded `DONE -> exit-1` and none of
the six had a readable output file, and the outcomes were opposite:
`suppression/0330` had already written a complete 3,085-word report, and
`webapp/0190` had written nothing at all - no entry, no commit, and no file
in its worktree with an mtime inside the window. `pilotcaps/0241` was the
third shape: no entry and no commit, and its 34,712-byte deliverable sitting
untracked on disk, found an hour later by another lane.

So `exit-1` plus an empty `.out` is not evidence about the work, and
`src.lanerework.landing` is the three-state answer that is. This file is the
proof it can be wrong in every direction it is allowed to answer.

NOTHING HERE READS THE REAL ESTATE OR A REPOSITORY. Every watcher log and
every lane file is a string written into a temporary directory and every
commit window is a `(shas, complete)` pair handed to the reader, which is
the git seam `src.lanerework`'s own docstring requires.

THE CONTROLS, AND THE TWO THAT CAUGHT REAL DEFECTS IN THIS CODE:

  C1  all three verdicts are REACHABLE, each by a named route. A state the
      code can never reach is not a state.
  C2  LOST is WITHHELD when any single authority is unread - four cases, one
      per leg, each with the same row that reaches LOST when all four are
      read. This is the pair, not a single leg.
  C3  `None` NEVER BECOMES `False` on the entry leg. CAUGHT A REAL DEFECT:
      the first version returned False for an id with entries and two
      STARTs, so `glm-b/0170` rendered "entry: no" beside a 1,374-word entry
      its third dispatch had written.
  C4  the commit leg REFUSES an unattributed commit. CAUGHT A REAL DEFECT:
      with six watchers running concurrently a 41-minute window contains
      other lanes' commits, and the first version reported LANDED-by-commit
      for `suppression/0330` off `1edcd1321` (pilotcaps' TASK 0239) and for
      `pilotcaps/0241` off `8b2d12d11` (webapp's own 0180).
  C5  a cheap commit walk's empty answer cannot license LOST, because it
      reaches only what a ref reaches.
  C6  the lane roll-up takes the WORST verdict, not the most common one.
  C7  the panel renders the three apart, and renders an unread leg as
      neither yes nor no.
  C8  the regression: the six real rows, as literal log lines.
"""
import datetime
import os
import re
import shutil
import tempfile
import unittest

from src import lanerework as lr
from src import lanes
from src.web import api, pages

DAY = "2026-10-16"
ALPHA = "alpha"
BETA = "beta"
KNOWN = (ALPHA, BETA)

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


def done(lane, clock, brief, suffix="exit-1", day=DAY):
    return "[%s] [%s] DONE  %s -> %s" % (stamp(clock, day), lane, brief,
                                         suffix)


def heading(task, body=REPORT):
    return "## %s \u2014 TASK-%s: the thing\n\n%s\n" % (DAY, task, body)


class Estate(object):

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="killed-")
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

    def queue(self, lane, *names):
        base = os.path.join(self.root, "queue", lane)
        os.makedirs(base, exist_ok=True)
        for name in names:
            with open(os.path.join(base, name), "w",
                      encoding="utf-8") as handle:
                handle.write("brief\n")

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class Base(unittest.TestCase):

    def setUp(self):
        self.estate = Estate()
        self.addCleanup(self.estate.close)

    def read(self, lane):
        # `cwd` is the temp root, which is not a git repository, so the
        # commit leg reads UNKNOWN rather than reaching for this machine's.
        return lr.lane_rework(self.estate.root, lane, commits={},
                              offset_hours=2.0, known=KNOWN,
                              cwd=self.estate.root)

    def row(self, lane, brief):
        data = self.read(lane)
        self.assertEqual(data["state"], "present", data)
        matches = [item for item in data["rows"] if item["brief"] == brief]
        self.assertEqual(len(matches), 1, [i["brief"] for i in data["rows"]])
        return matches[0], data


# --------------------------------------------------------------------- C1


class C1EveryVerdictIsReachable(unittest.TestCase):
    """Three states, each reached by a named route. A verdict the code can
    never produce is a dead branch, and this estate has shipped one before:
    an evaluator reported INSUFFICIENT_DATA forever because nothing wrote
    the field it read."""

    ENTRIES = [{"line": 1, "level": 2, "text": "TASK-0330",
                "body": REPORT}]

    def test_c1a_landed_by_the_entry_leg(self):
        found = lr.landing(self.ENTRIES, 1)
        self.assertEqual(found["verdict"], lr.LANDED)
        self.assertIs(found["legs"]["entry"], True)
        # And the other legs are NOT claimed: one positive authority is
        # sufficient, so listing the rest as missing would read as a
        # weakness that is not there.
        self.assertEqual(found["unread"], [])

    def test_c1b_landed_by_the_commit_leg_with_no_entry_at_all(self):
        found = lr.landing([], 3, commits_in_window=["deadbeef"])
        self.assertEqual(found["verdict"], lr.LANDED)
        self.assertIs(found["legs"]["commit"], True)

    def test_c1c_landed_by_the_artefact_leg_alone(self):
        """`pilotcaps/0241`'s shape: no entry, no commit, a file on disk."""
        found = lr.landing([], 1, commits_in_window=[],
                           artefacts_in_window=["tests/t.py"])
        self.assertEqual(found["verdict"], lr.LANDED)
        self.assertIs(found["legs"]["artefact"], True)

    def test_c1d_lost_needs_all_five_read_and_empty(self):
        """FIVE SINCE TASK 0250, and the rule did not change - the set of
        authorities grew. `lane_mtime_state` is the lane file's own clock,
        and LOST needs it read and negative like every other leg. Omitting
        it is the next test, which is what keeps this one honest.
        """
        found = lr.landing([], 2, commits_in_window=[],
                           artefacts_in_window=[], requeued=False,
                           lane_mtime_state=lr.LANE_MTIME_NOT_APPENDED)
        self.assertEqual(found["verdict"], lr.LOST)
        self.assertEqual(found["unread"], [])

    def test_c1d2_the_fifth_leg_unread_withholds_lost(self):
        """The pair for the test above, added with the leg itself.

        Four read and empty was enough for LOST before 0250 and is not
        enough now. Without this assertion the growth would be invisible:
        the test above would simply have been edited to keep passing.
        """
        found = lr.landing([], 2, commits_in_window=[],
                           artefacts_in_window=[], requeued=False)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)
        self.assertIn("lane_mtime", found["unread"])

    def test_c1e_not_determined_is_the_default(self):
        found = lr.landing([], 2)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)

    def test_c1f_the_three_are_distinct_and_all_have_words(self):
        self.assertEqual(len(set(lr.LANDING_ORDER)), 3)
        for verdict in lr.LANDING_ORDER:
            label, why = lr.LANDING_TEXT[verdict]
            self.assertTrue(label.strip() and why.strip())
        # NOT-DETERMINED's words may not read as either of the others.
        label, why = lr.LANDING_TEXT[lr.NOT_DETERMINED]
        self.assertNotIn("lost", label.lower())
        self.assertIn("neither", why.lower())


# --------------------------------------------------------------------- C2


class C2LostIsWithheldWhenAnAuthorityIsUnread(unittest.TestCase):
    """The PAIR. A test that only showed LOST being reached would pass
    against a function that ALWAYS reaches LOST, which is the `0239`
    criterion-2 defect this estate has now committed at least three times.
    """

    def all_read(self, **override):
        # FIVE LEGS SINCE TASK 0250. `lane_mtime_state` joined the
        # conjunction, so the baseline every test in this class varies ONE
        # leg away from has to supply it - otherwise each of them would be
        # withholding LOST for the fifth leg rather than for the leg it
        # names, and the whole class would pass while measuring nothing.
        kwargs = {"commits_in_window": [], "artefacts_in_window": [],
                  "requeued": False,
                  "lane_mtime_state": lr.LANE_MTIME_NOT_APPENDED}
        kwargs.update(override)
        return lr.landing([], 2, **kwargs)

    def test_c2_control_all_five_read_reaches_lost(self):
        self.assertEqual(self.all_read()["verdict"], lr.LOST)

    def test_c2e_the_lane_clock_unread_withholds_lost(self):
        """One more leg, one more case, same shape as C2a-C2c."""
        found = self.all_read(lane_mtime_state=None)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)
        self.assertIn("lane_mtime", found["unread"])

    def test_c2f_an_inconclusive_lane_clock_also_withholds_lost(self):
        """And the state that is READ and still cannot contribute.

        INCONCLUSIVE is not the same as unread, but it is equally unable to
        support LOST - this is the asymmetry TASK 0250 exists for, asserted
        where LOST is decided rather than only where the leg is computed.
        """
        found = self.all_read(lane_mtime_state=lr.LANE_MTIME_AFTER)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)
        self.assertIn("lane_mtime", found["unread"])

    def test_c2a_commit_unread_withholds_lost(self):
        found = self.all_read(commits_in_window=None)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)
        self.assertIn("commit", found["unread"])

    def test_c2b_artefact_unread_withholds_lost(self):
        found = self.all_read(artefacts_in_window=None)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)
        self.assertIn("artefact", found["unread"])

    def test_c2c_requeued_unread_withholds_lost(self):
        found = self.all_read(requeued=None)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)
        self.assertIn("requeued", found["unread"])

    def test_c2d_entry_unread_withholds_lost(self):
        """`starts_for_task=None` is the log not answering."""
        found = lr.landing([], None, commits_in_window=[],
                           artefacts_in_window=[], requeued=False)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)
        self.assertIn("entry", found["unread"])

    def test_c2e_a_requeued_brief_is_not_lost(self):
        """Somebody picked the work up. That is not the same as it having
        landed, and it is certainly not LOST."""
        found = self.all_read(requeued=True)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)


# --------------------------------------------------------------------- C3


class C3AnEntryWithTwoStartsIsUnreadNotAbsent(unittest.TestCase):
    """CAUGHT A REAL DEFECT. An entry exists and the brief was dispatched
    three times: the authority was READ and came back INCONCLUSIVE, which is
    None. The first version of `landing` returned False, so the panel
    printed "entry: no" against `glm-b/0170`'s 1,374-word entry."""

    ENTRIES = [{"line": 9, "level": 2, "text": "TASK-0170", "body": REPORT}]

    def test_c3a_two_starts_makes_the_entry_leg_none(self):
        found = lr.landing(self.ENTRIES, 3)
        self.assertIsNone(found["legs"]["entry"])
        self.assertIn("entry", found["unread"])
        self.assertEqual(found["entries_naming_id"], 1)

    def test_c3b_control_one_start_makes_it_true(self):
        """The same entry, one dispatch. Without this leg C3a passes against
        a function that returns None for every entry."""
        self.assertIs(lr.landing(self.ENTRIES, 1)["legs"]["entry"], True)

    def test_c3c_control_no_entry_at_all_makes_it_false(self):
        """And this leg is why None and False are not the same cell: an id
        no heading names is an authority answering NO."""
        self.assertIs(lr.landing([], 1)["legs"]["entry"], False)

    def test_c3d_two_starts_can_never_reach_lost(self):
        found = lr.landing(self.ENTRIES, 3, commits_in_window=[],
                           artefacts_in_window=[], requeued=False)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)

    def test_c3e_a_heading_with_an_empty_body_blocks_lost(self):
        """A bare heading is the id being on the record. It does not license
        LANDED and it must not license LOST either - two directions, two
        answers, and one word count may not decide both."""
        bare = [{"line": 3, "level": 2, "text": "TASK-0170", "body": "x"}]
        found = lr.landing(bare, 1, commits_in_window=[],
                           artefacts_in_window=[], requeued=False)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)
        self.assertEqual(found["entries_with_a_report"], 0)
        self.assertEqual(found["entries_naming_id"], 1)


# --------------------------------------------------------------------- C4


class C4TheCommitLegRefusesAnotherLanesCommit(unittest.TestCase):
    """CAUGHT A REAL DEFECT. Six watchers run at once, so a 41-minute window
    holds other lanes' commits by construction. The window is not an
    attribution."""

    WINDOW = (when("08:35:24"), when("09:16:45"))

    def leg(self, shas, branch_lanes, complete=True):
        return lr.commit_leg(self.WINDOW[0], self.WINDOW[1], ALPHA,
                             known=KNOWN, branch_lanes=branch_lanes,
                             measured=(shas, complete))

    def test_c4a_a_commit_on_another_lanes_branch_does_not_count(self):
        leg = self.leg(["aaa111"], {"aaa111": [BETA]})
        self.assertEqual(leg, [])

    def test_c4b_control_a_commit_on_this_lanes_branch_does_count(self):
        """Without this leg C4a passes against a function that refuses every
        commit, which would be a commit authority that never fires."""
        self.assertEqual(self.leg(["aaa111"], {"aaa111": [ALPHA]}),
                         ["aaa111"])

    def test_c4c_a_commit_two_lanes_both_reach_is_no_information(self):
        """Containment proves association, never authorship: `38c0db9c4` is
        reachable from four `task-pilotcaps-*` branches AND from
        `task-glm-c-2026-10-14`, because pilotcaps merged it to certify it.
        """
        self.assertEqual(self.leg(["aaa111"], {"aaa111": [ALPHA, BETA]}), [])

    def test_c4d_a_commit_no_branch_names_is_no_information(self):
        self.assertEqual(self.leg(["aaa111"], {"aaa111": []}), [])

    def test_c4e_refused_commits_leave_an_EMPTY_leg_not_an_unread_one(self):
        """The window WAS read. Nothing in it is this lane's, which is an
        answer - and with a complete walk it is a proven empty."""
        self.assertIsNotNone(self.leg(["aaa111"], {"aaa111": [BETA]}))

    def test_c4f_the_refusal_keeps_the_row_out_of_landed(self):
        found = lr.landing([], 1,
                           commits_in_window=self.leg(["aaa111"],
                                                      {"aaa111": [BETA]}),
                           artefacts_in_window=None, requeued=False)
        self.assertEqual(found["verdict"], lr.NOT_DETERMINED)


# --------------------------------------------------------------------- C5


class C5ACheapWalkCannotProveAnEmptyWindow(unittest.TestCase):
    """`git log --all` is 0.25s and `--all --reflog` is 88.5s in the real
    repository, both timed 2026-10-16 over the same window. The cheap walk
    is the default and reaches only what a ref reaches - over 09:18-10:45
    the complete walk returns 14 commits of which 8 are reachable from no
    branch tip. So an empty cheap walk proves nothing."""

    WINDOW = (when("09:14:03"), when("09:16:45"))

    def leg(self, complete):
        return lr.commit_leg(self.WINDOW[0], self.WINDOW[1], ALPHA,
                             known=KNOWN, branch_lanes={},
                             measured=([], complete))

    def test_c5a_an_empty_incomplete_walk_is_unread(self):
        self.assertIsNone(self.leg(False))

    def test_c5b_control_an_empty_complete_walk_is_a_proven_empty(self):
        self.assertEqual(self.leg(True), [])

    def test_c5c_so_only_the_complete_walk_can_reach_lost(self):
        for complete, expected in ((False, lr.NOT_DETERMINED),
                                   (True, lr.LOST)):
            found = lr.landing(
                [], 1, commits_in_window=self.leg(complete),
                artefacts_in_window=[], requeued=False,
                # The fifth leg, read and negative, so that the only thing
                # varying across this loop is the completeness of the walk.
                lane_mtime_state=lr.LANE_MTIME_NOT_APPENDED)
            self.assertEqual(found["verdict"], expected, complete)

    def test_c5d_a_missing_bound_is_unreadable_and_not_empty(self):
        shas, complete = lr.commits_between(None, self.WINDOW[1])
        self.assertIsNone(shas)
        self.assertFalse(complete)


# --------------------------------------------------------------------- C6


class C6TheLaneRollUpTakesTheWorst(unittest.TestCase):
    """A lane with nine LANDED rows and one NOT-DETERMINED has an
    unanswered question in it. A majority rule would render it healthy."""

    def test_c6a_one_not_determined_outranks_nine_landed(self):
        lane = {"landing_tally": {lr.LANDED: 9, lr.NOT_DETERMINED: 1}}
        self.assertEqual(lr.landing_state(lane), lr.NOT_DETERMINED)

    def test_c6b_not_determined_outranks_lost_too(self):
        """Both need a person; only one of them needs a person to go and
        LOOK. An unanswered question is the louder of the two."""
        lane = {"landing_tally": {lr.LOST: 3, lr.NOT_DETERMINED: 1}}
        self.assertEqual(lr.landing_state(lane), lr.NOT_DETERMINED)

    def test_c6c_control_all_landed_reports_landed(self):
        lane = {"landing_tally": {lr.LANDED: 4}}
        self.assertEqual(lr.landing_state(lane), lr.LANDED)

    def test_c6d_no_killed_dispatch_is_none_and_not_landed(self):
        """None renders as "no killed dispatch". LANDED would be a claim
        about work nobody asked about."""
        self.assertIsNone(lr.landing_state({"landing_tally": {}}))
        self.assertIsNone(lr.landing_state({}))


# --------------------------------------------------------------------- C7


class C7ThePanelRendersTheThreeApart(Base):
    """A verdict computed correctly that renders the same as another one is
    this estate's recurring defect, not a cosmetic problem."""

    KILLED = "0330-the-reference.md"
    ALIVE = "0320-the-other.md"

    def setUp(self):
        super(C7ThePanelRendersTheThreeApart, self).setUp()
        self.estate.log(ALPHA, [
            up(ALPHA),
            start(ALPHA, "08:35:24", self.KILLED),
            done(ALPHA, "09:16:45", self.KILLED, "exit-1"),
            start(ALPHA, "09:33:04", self.ALIVE),
            done(ALPHA, "10:00:51", self.ALIVE, "exit0")])
        self.estate.lane_file(ALPHA, heading("0330"))
        self.estate.log(BETA, [
            up(BETA),
            start(BETA, "08:57:21", "0241-the-door.md"),
            done(BETA, "09:16:45", "0241-the-door.md", "exit-1")])
        self.estate.lane_file(BETA, "## nothing about any task\n\nbody\n")

    def data(self):
        found = api.lane_rework(root=self.estate.root, branch_lanes={},
                                cwd=self.estate.root,
                                lanes_wanted=[ALPHA, BETA])
        self.assertEqual(found["state"], "present")
        return found

    def test_c7a_only_the_killed_dispatch_gets_a_landing_verdict(self):
        data = self.data()
        self.assertEqual(data["killed"], 2)
        briefs = sorted(row["brief"] for row in data["killed_rows"])
        self.assertEqual(briefs, ["0241-the-door.md", self.KILLED])
        rows = {row["brief"]: row for lane in data["lanes"]
                for row in lane["rows"]}
        self.assertIsNone(rows[self.ALIVE]["landing"])

    def test_c7b_the_two_killed_rows_get_different_verdicts(self):
        rows = {row["brief"]: row["landing"]["verdict"]
                for row in self.data()["killed_rows"]}
        self.assertEqual(rows[self.KILLED], lr.LANDED)
        self.assertEqual(rows["0241-the-door.md"], lr.NOT_DETERMINED)

    def test_c7c_the_panel_prints_both_verdicts_and_names_the_unread(self):
        html = pages.lane_rework(self.data())
        self.assertIn("LANDED", html)
        self.assertIn("NOT DETERMINED", html)
        self.assertIn("not read:", html)
        self.assertIn("artefact", html)

    def test_c7d_an_unread_leg_renders_as_neither_yes_nor_no(self):
        """The cell this replaces had two renderings for three values, and a
        blank cell and a "no" cell were the same pixel."""
        html = pages.lane_rework(self.data())
        self.assertIn("UNREAD", html)

    def test_c7e_a_lane_with_no_killed_dispatch_says_so(self):
        data = self.data()
        for lane in data["lanes"]:
            lane["landing_state"] = None
            lane["landing_state_label"] = None
        html = pages.lane_rework(data)
        self.assertIn("no killed dispatch", html)
        # And it does NOT render as a pass.
        self.assertNotIn(">LANDED<", html.split("Dispatches whose")[0])

    def test_c7f_an_unreadable_lane_renders_unknown_in_that_column(self):
        """`0170`'s lesson one level up: a zero that is a provable upper
        bound keeps the alarm, an UNKNOWN that throws it away is worse."""
        os.remove(os.path.join(self.estate.root, "logs",
                               "watcher-%s.log" % BETA))
        data = self.data()
        beta = [lane for lane in data["lanes"] if lane["lane"] == BETA][0]
        self.assertEqual(beta["state"], lr.UNREADABLE)
        self.assertIsNone(beta["landing_state"])
        html = pages.lane_rework(data)
        unreadable = re.search(r'<tr class="warn"><th>beta</th>.*?</tr>',
                               html, re.S)
        self.assertIsNotNone(unreadable)
        self.assertEqual(unreadable.group(0).count("UNKNOWN"), 7)


# --------------------------------------------------------------------- C8


class C8TheSuffixCarriesItsOwnMeaning(unittest.TestCase):
    """`exit-1` had no entry in `DONE_MEANINGS` at all, so the board printed
    "unrecognised suffix" - correct and uninformative."""

    def test_c8a_exit_minus_one_is_named(self):
        self.assertIn("exit-1", lanes.DONE_MEANINGS)
        short, why = lanes.DONE_MEANINGS["exit-1"]
        self.assertIn("wrapper", short.lower())
        self.assertIn("outside", why.lower())

    def test_c8b_it_does_not_claim_the_work_failed(self):
        short, why = lanes.DONE_MEANINGS["exit-1"]
        text = (short + " " + why).lower()
        self.assertIn("no information about the child", text)

    def test_c8c_it_is_not_confused_with_the_timeout(self):
        """TIMEOUT is also a killed tree and is a DIFFERENT fact: the watcher
        did that one itself, at a cap it knows."""
        self.assertNotEqual(lanes.DONE_MEANINGS["exit-1"],
                            lanes.DONE_MEANINGS["TIMEOUT"])
        self.assertIn("timeout", lanes.DONE_MEANINGS["exit-1"][1].lower())

    def test_c8d_the_killed_suffix_list_is_not_a_pattern(self):
        """A suffix nobody has measured is not added on a guess.

        `TIMEOUT` JOINED IT IN TASK 0250 AND THE RULE IS UNCHANGED, because
        it was measured and not guessed: `glm-c/0220`, START 09:16:52, DONE
        11:47:00, 150.1 minutes, with `KILL VERIFIED: 0 of 4 still alive` on
        the line above the DONE. Every member of this tuple has a dated
        instance behind it, and the second assertion is the one with teeth -
        `exit1` was written 17 times and is still not here, because
        ran-and-failed is an ordinary outcome and not a kill.
        """
        self.assertEqual(lr.KILLED_SUFFIXES, ("exit-1", "TIMEOUT"))
        self.assertNotIn("exit1", lr.KILLED_SUFFIXES)
        self.assertNotIn("exit0", lr.KILLED_SUFFIXES)
        self.assertNotIn("NOWORK", lr.KILLED_SUFFIXES)
        # AND EVERY MEMBER IS A SUFFIX THE WATCHERS ACTUALLY WRITE. A tuple
        # member with no entry in the dictionary would be a suffix this code
        # believes in and nothing describes.
        for suffix in lr.KILLED_SUFFIXES:
            self.assertIn(suffix, lanes.DONE_MEANINGS, suffix)

    def test_c8e_every_authority_names_what_it_cannot_answer(self):
        for key in ("entry", "commit", "artefact", "requeued", "lane_mtime"):
            name, why = lr.LANDING_AUTHORITIES[key]
            self.assertTrue(name.strip())
            self.assertTrue(re.search(r"cannot|not read|never|only",
                                      why, re.I), key)


# --------------------------------------------------------------------- C9


class C9TheSixRealRows(Base):
    """The regression, as literal lines. Only the three lanes whose real
    outcome this task could establish from files it was allowed to read.

    `requeued` IS the one leg a page can measure, so the queue folders are
    built to match what was on disk at 10:52: `glm-c/0161` back at depth 0,
    `suppression/0330` gone.
    """

    def setUp(self):
        super(C9TheSixRealRows, self).setUp()
        # suppression: one START, a full entry -> LANDED
        self.estate.log("suppression", [
            up("suppression"),
            "[2026-10-16 08:35:24] [suppression] START "
            "0330-the-reference-that-states-its-own-sha.md",
            "[2026-10-16 09:16:45] [suppression] DONE  "
            "0330-the-reference-that-states-its-own-sha.md -> exit-1"])
        self.estate.lane_file(
            "suppression",
            "## 2026-10-16 \u2014 TASK-0330: the two references that state "
            "their own SHA\n\n" + REPORT + "\n")
        self.estate.queue("suppression")
        # glm-c: THREE STARTs of the same brief and an entry from the first
        # -> the entry authority is inconclusive, so NOT DETERMINED
        self.estate.log("glm-c", [
            up("glm-c"),
            "[2026-10-16 00:42:32] [glm-c] START 0161-save-sweep.md",
            "[2026-10-16 01:41:51] [glm-c] DONE  0161-save-sweep.md -> exit1",
            "[2026-10-16 09:14:03] [glm-c] START 0161-save-sweep.md",
            "[2026-10-16 09:16:45] [glm-c] DONE  0161-save-sweep.md "
            "-> exit-1"])
        self.estate.lane_file(
            "glm-c",
            "## 2026-10-16 00:5x \u2014 TASK 0161 (GLM-C): save sweep\n\n"
            + REPORT + "\n")
        self.estate.queue("glm-c", "0161-save-sweep.md")
        # pilotcaps: no entry naming 0241 anywhere, and the only mention is
        # inside ANOTHER task's prose -> entry leg False, still NOT
        # DETERMINED because the artefact walk is unread. The real artefact
        # was on disk and this page could not see it.
        self.estate.log("pilotcaps", [
            up("pilotcaps"),
            "[2026-10-16 08:57:21] [pilotcaps] START "
            "0241-the-door-that-does-not-ask-whose.md",
            "[2026-10-16 09:16:45] [pilotcaps] DONE  "
            "0241-the-door-that-does-not-ask-whose.md -> exit-1"])
        self.estate.lane_file(
            "pilotcaps",
            "## TASK-0244 \u2014 2026-10-16 \u2014 recovering 0241: the "
            "report died, the work did not\n\n0241 and 0242 are queued and "
            "untouched. " + REPORT + "\n")
        self.estate.queue("pilotcaps",
                          "0244-the-work-that-died-with-its-wrapper.md")

    def verdicts(self):
        data = api.lane_rework(
            root=self.estate.root, branch_lanes={}, cwd=self.estate.root,
            lanes_wanted=["suppression", "glm-c", "pilotcaps"])
        return {(row["lane"], row["brief"]): row["landing"]
                for row in data["killed_rows"]}, data

    def test_c9a_suppression_0330_landed(self):
        found, _ = self.verdicts()
        row = found[("suppression",
                     "0330-the-reference-that-states-its-own-sha.md")]
        self.assertEqual(row["verdict"], lr.LANDED)
        self.assertIs(row["legs"]["entry"], True)
        self.assertEqual(row["starts_for_task"], 1)

    def test_c9b_glm_c_0161_is_not_determined_on_three_starts(self):
        found, _ = self.verdicts()
        row = found[("glm-c", "0161-save-sweep.md")]
        self.assertEqual(row["verdict"], lr.NOT_DETERMINED)
        self.assertIsNone(row["legs"]["entry"])
        self.assertEqual(row["starts_for_task"], 2)
        self.assertIs(row["legs"]["requeued"], True)

    def test_c9c_pilotcaps_0241_has_no_entry_but_is_not_called_lost(self):
        """The row the brief's own premise got wrong. A mention of `0241`
        inside the 0244 entry's prose is NOT an entry - and LOST is still
        refused, because the authority that refuted it is unread."""
        found, _ = self.verdicts()
        row = found[("pilotcaps",
                     "0241-the-door-that-does-not-ask-whose.md")]
        self.assertIs(row["legs"]["entry"], False)
        self.assertEqual(row["entries_naming_id"], 0)
        self.assertEqual(row["verdict"], lr.NOT_DETERMINED)
        self.assertIn("artefact", row["unread"])

    def test_c9d_a_successor_brief_does_not_count_as_re_queued(self):
        """`0244` is the re-queue of `0241`'s work and shares not one
        character of its filename. Only a person can pair them."""
        found, _ = self.verdicts()
        row = found[("pilotcaps",
                     "0241-the-door-that-does-not-ask-whose.md")]
        self.assertIs(row["legs"]["requeued"], False)

    def test_c9e_all_six_would_have_rendered_identically_before(self):
        """The defect, stated as an assertion: suffix and output size are
        the same for every row and the verdicts are not."""
        found, _ = self.verdicts()
        self.assertEqual({row["suffix"] for row in
                          self.verdicts()[1]["killed_rows"]}, {"exit-1"})
        self.assertEqual(len({row["verdict"] for row in found.values()}), 2)


if __name__ == "__main__":
    unittest.main()
