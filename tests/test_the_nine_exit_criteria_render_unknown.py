"""The nine exit criteria, and the one direction this page may never fail in.

WHAT THIS FILE IS FOR. `CANARY-01.md` lists nine exit criteria and says the
canary activates "only when all of these are true". Four of them were recorded
NOT MET on 2026-10-15 and one was MET only on a branch that collides with
another branch. Whether the canary may go is therefore a question about nine
recorded verdicts, and until now reading them meant opening a 395 KB lane file
and trusting the last table in it.

THE INVARIANT UNDER TEST IS DIRECTIONAL, and that is the whole point. A page
that reads UNKNOWN when the answer is MET wastes somebody's afternoon. A page
that reads MET when the answer is unknown sends mail to real people. So every
test here that matters asserts the second thing cannot happen:

    an absent source renders UNKNOWN, never MET;
    an unparseable source renders UNKNOWN, never MET;
    `NOT MET` is never read as `MET` - the substring is inside the phrase;
    `MET-WITH-CAVEAT` is not rounded up to MET;
    two verdicts on one criterion is UNKNOWN, not whichever came first;
    a failed self-control poisons EVERY verdict on the page.

AND THE CONTROL THAT STOPS THAT BEING FREE. A reader that answers UNKNOWN to
everything satisfies all six of those and is worthless - it is the shape of
this lane's own B7 finding, an instrument that reports clean because it sees
nothing. So a planted MET must come back MET, and that is asserted here as
well as being one of the three controls the page runs on every render.

NOTHING HERE REACHES A PROVIDER, A NETWORK, A REAL LANE OR THE REAL OPS
ESTATE. Every source in this file is a file this test writes into a temporary
directory, or a string handed straight to the parser. One test patches
`socket.socket` to raise and then calls the reader, so "it opens no socket" is
a measurement rather than a claim.
"""
import datetime
import os
import shutil
import socket
import tempfile
import unittest

from src import exitcriteria, lanes
from src.web import api, pages
from src.web.app import permission_for
from tests.webbase import WebTest

PATH = "/admin/exit-criteria"
SUPER = "root@resonate.test"
ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"

NOW = datetime.datetime(2026, 10, 16, 2, 0, 0)

#: TASK 0160's answer block, verbatim in shape and in verdicts, including the
#: two it recorded as `MET-WITH-CAVEAT` and criterion 4's two answers at two
#: SHAs. Written out here rather than imported, so that a change to the
#: audit's layout shows up as a failure in this file instead of as a page that
#: reads every criterion UNKNOWN and looks merely cautious.
BLOCK_AS_RECORDED = """# CANARY-01 exit criteria

## THE ANSWER - 2026-10-15

    1  suppressed address cannot reach transport by any path  MET-WITH-CAVEAT
    2  a removal request writes a suppression row             MET
    3  li1 renders a real note, RED on empty                  NOT MET
    4  every template inside ceiling AND floor                MET on 32cb420f7
                                                              NOT MET on 93162471d
    5  zero bypassing write paths, real denominator           NOT MET  26 of 58
    6  mailbox health from the estate export                  MET
    7  one owner across the pool, bodies signed by them       NOT MET
    8  the review file approved by the owner                  MET-WITH-CAVEAT
    9  a kill switch the owner can operate alone              NOT MET
"""


def block(**verdicts):
    """A nine-row verdict block in that same shape, verdicts supplied.

    Anything not named renders `NOT MET`, because a fixture whose unspecified
    rows defaulted to MET would make a test pass for the one reason this file
    exists to rule out.
    """
    lines = ["# EXIT CRITERIA", "", "## THE ANSWER - 2026-10-16", ""]
    for number in range(1, 10):
        lines.append("    %d  criterion number %d   %s"
                     % (number, number,
                        verdicts.get("c%d" % number, "NOT MET")))
    return "\n".join(lines) + "\n"


#: All nine decided, no caveats and nothing contested. The fixture most of
#: these tests want, because it isolates whatever one thing they are varying.
BLOCK_CLEAN = block(c1="MET", c2="MET", c4="MET", c6="MET", c8="MET")


class ASource:
    """A temporary ops estate and repository root, thrown away per test."""

    def setUp(self):
        super().setUp()
        self.repo = tempfile.mkdtemp(prefix="rga-nine-repo-")
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.ops = tempfile.mkdtemp(prefix="rga-nine-ops-")
        self.addCleanup(shutil.rmtree, self.ops, ignore_errors=True)
        previous = os.environ.get(lanes.OPS_DIR)
        os.environ[lanes.OPS_DIR] = self.ops
        self.addCleanup(self._restore_ops, previous)

    @staticmethod
    def _restore_ops(previous):
        if previous is None:
            os.environ.pop(lanes.OPS_DIR, None)
        else:
            os.environ[lanes.OPS_DIR] = previous

    def write(self, name, text, where="ops"):
        root = self.ops if where == "ops" else self.repo
        path = os.path.join(root, name)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def report(self, now=None):
        return exitcriteria.report(root=self.repo, now=now or NOW)

    def rows(self, now=None):
        return {row["number"]: row for row in self.report(now)["rows"]}


# --------------------------------------------------------------------------
# The reader is not blind. Without this class every assertion below is
# satisfied by a function that returns UNKNOWN unconditionally.
# --------------------------------------------------------------------------

class TheReaderIsNotBlind(ASource, unittest.TestCase):

    def test_a_planted_met_comes_back_met(self):
        """The anti-B7 assertion, on the real reading path.

        `EXIT-CRITERIA-2026-10-16.md` is the designated authority, so this is
        the same code the page runs - not a parser called in a corner.
        """
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        rows = self.rows()
        for number in (1, 2, 4, 6, 8):
            self.assertEqual(rows[number]["verdict"], exitcriteria.MET,
                             "criterion %d" % number)

    def test_a_planted_not_met_comes_back_not_met(self):
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        rows = self.rows()
        for number in (3, 5, 7, 9):
            self.assertEqual(rows[number]["verdict"], exitcriteria.NOT_MET,
                             "criterion %d" % number)

    def test_the_three_controls_all_pass(self):
        """They run on every render, and each prints PASS or FAIL."""
        results = exitcriteria.controls(now=NOW)
        self.assertEqual(len(results), 3)
        for control in results:
            self.assertTrue(control["ok"],
                            "%s FAILED: %s" % (control["name"],
                                               control["detail"]))

    def test_the_controls_cover_absent_unparseable_and_planted(self):
        names = {control["name"] for control in exitcriteria.controls(now=NOW)}
        self.assertEqual(names, {"absent_renders_unknown",
                                 "unparseable_renders_unknown",
                                 "a_planted_met_renders_met"})

    def test_the_absent_control_uses_a_path_that_is_really_absent(self):
        """If somebody creates the fixture path, the control must FAIL.

        A control pointed at a path that has quietly come into existence is
        measuring nothing, which is the defect it exists to catch.
        """
        path = os.path.join(exitcriteria.REPO_ROOT, exitcriteria.ABSENT_FIXTURE)
        self.assertFalse(os.path.exists(path),
                         "%s exists, so the absence control is vacuous"
                         % exitcriteria.ABSENT_FIXTURE)

    def test_the_planted_control_checks_both_directions(self):
        """A control that only planted MET would pass on a reader that
        answers MET to everything - the opposite blindness."""
        planted = set(exitcriteria.PLANTED.values())
        self.assertEqual(planted, {exitcriteria.MET, exitcriteria.NOT_MET})


# --------------------------------------------------------------------------
# UNKNOWN never becomes MET. Each way measured rather than argued.
# --------------------------------------------------------------------------

class UnknownNeverBecomesMet(ASource, unittest.TestCase):

    def test_an_absent_source_renders_unknown(self):
        """Nothing is written at all, so every source is absent."""
        for row in self.report()["rows"]:
            self.assertEqual(row["verdict"], exitcriteria.UNKNOWN,
                             "criterion %d" % row["number"])

    def test_an_absent_source_names_the_reason_in_the_row(self):
        row = self.rows()[1]
        self.assertTrue(row["reason"])
        self.assertIn(exitcriteria.DESIGNATED, row["reason"])

    def test_an_unparseable_source_renders_unknown(self):
        """Present, readable, and holding no verdict block at all."""
        self.write(exitcriteria.DESIGNATED,
                   "# Notes\n\nThe audit is still in flight. Nothing here is\n"
                   "a verdict and nothing here is a table.\n")
        for row in self.report()["rows"]:
            self.assertEqual(row["verdict"], exitcriteria.UNKNOWN)

    def test_an_unparseable_source_says_it_was_read_and_not_understood(self):
        self.write(exitcriteria.DESIGNATED, "# Notes\n\nstill in flight\n")
        source = {s["key"]: s for s in self.report()["sources"]}
        self.assertEqual(source[exitcriteria.DESIGNATED]["state"],
                         exitcriteria.NO_BLOCK)

    def test_not_met_is_never_read_as_met(self):
        """`MET` is a substring of `NOT MET`, and that is the whole trap.

        A reader searching for the shorter phrase first reads every refusal
        as a pass - in the one direction that puts mail in front of people.
        """
        self.write(exitcriteria.DESIGNATED, block(c1="NOT MET"))
        self.assertEqual(self.rows()[1]["verdict"], exitcriteria.NOT_MET)

    def test_met_with_caveat_is_not_rounded_up_to_met(self):
        """Two of the nine were recorded exactly this way on 2026-10-15.

        It is not one of the three verdicts this page can render, so it is
        UNKNOWN and the recorded words are shown. Rounding it to MET is a
        guess in the unsafe direction; rounding it to NOT MET would be this
        page inventing a verdict the authority did not write.
        """
        self.write(exitcriteria.DESIGNATED, block(c1="MET-WITH-CAVEAT"))
        row = self.rows()[1]
        self.assertEqual(row["verdict"], exitcriteria.UNKNOWN)
        self.assertEqual(row["recorded"], "MET-WITH-CAVEAT")
        self.assertIn("MET-WITH-CAVEAT", row["reason"])

    def test_met_with_caveat_spelled_with_spaces_is_also_unknown(self):
        self.write(exitcriteria.DESIGNATED, block(c1="MET WITH CAVEAT"))
        self.assertEqual(self.rows()[1]["verdict"], exitcriteria.UNKNOWN)

    def test_a_lowercase_met_in_prose_is_not_a_verdict(self):
        """`is met` appears in prose constantly. Only the recorded token
        counts, and a shape this reader does not know is UNKNOWN."""
        self.write(exitcriteria.DESIGNATED, block(c1="this one is met"))
        self.assertEqual(self.rows()[1]["verdict"], exitcriteria.UNKNOWN)

    def test_two_verdicts_on_one_criterion_is_unknown(self):
        """Criterion 4's real shape on 2026-10-15, and why it matters.

        It was recorded `MET on 32cb420f7` and `NOT MET on 93162471d` - two
        SHAs, two answers. A reader taking the first token reads MET.
        """
        self.write(exitcriteria.DESIGNATED, BLOCK_AS_RECORDED)
        row = self.rows()[4]
        self.assertEqual(row["verdict"], exitcriteria.UNKNOWN)
        self.assertIn("NOT MET", row["reason"])
        self.assertIn("contested", row["reason"].lower())

    def test_a_contested_criterion_does_not_poison_its_neighbours(self):
        """Fail-closed on one row, not a page-wide shrug."""
        self.write(exitcriteria.DESIGNATED, BLOCK_AS_RECORDED)
        rows = self.rows()
        self.assertEqual(rows[4]["verdict"], exitcriteria.UNKNOWN)
        self.assertEqual(rows[2]["verdict"], exitcriteria.MET)
        self.assertEqual(rows[3]["verdict"], exitcriteria.NOT_MET)

    def test_a_verdict_word_this_page_does_not_know_is_unknown(self):
        self.write(exitcriteria.DESIGNATED, block(c1="PROBABLY FINE"))
        row = self.rows()[1]
        self.assertEqual(row["verdict"], exitcriteria.UNKNOWN)
        self.assertTrue(row["reason"])

    def test_a_criterion_missing_from_the_block_is_unknown(self):
        text = "\n".join(line for line in BLOCK_CLEAN.splitlines()
                         if "criterion number 7" not in line) + "\n"
        self.write(exitcriteria.DESIGNATED, text)
        rows = self.rows()
        self.assertEqual(rows[1]["verdict"], exitcriteria.MET)
        self.assertEqual(rows[7]["verdict"], exitcriteria.UNKNOWN)

    def test_no_row_is_ever_met_when_nothing_was_read(self):
        """The aggregate form of this whole class, stated as a tally."""
        tally = self.report()["tally"]
        self.assertEqual(tally[exitcriteria.MET], 0)
        self.assertEqual(tally[exitcriteria.UNKNOWN], 9)

    def test_the_recorded_unknown_of_an_authority_is_passed_through(self):
        """An authority that wrote UNKNOWN is agreed with, not overruled."""
        self.write(exitcriteria.DESIGNATED, block(c1="UNKNOWN"))
        row = self.rows()[1]
        self.assertEqual(row["verdict"], exitcriteria.UNKNOWN)
        self.assertEqual(row["recorded"], "UNKNOWN")


# --------------------------------------------------------------------------
# A failed control is not a footnote.
# --------------------------------------------------------------------------

class AFailedControlPoisonsEveryVerdict(ASource, unittest.TestCase):
    """If the reader cannot prove it works, nothing it says may be believed.

    This is the rule that makes the three controls load-bearing rather than
    decorative. A control that fails beside a page still showing MET is a
    page whose reader is unproven and whose verdicts look exactly as
    authoritative as they did before.
    """

    def _break_a_control(self, name):
        real = exitcriteria.controls

        def broken(now=None):
            results = real(now=now)
            for control in results:
                if control["name"] == name:
                    control["ok"] = False
                    control["detail"] = "forced by a test"
            return results

        exitcriteria.controls = broken
        self.addCleanup(setattr, exitcriteria, "controls", real)

    def test_a_failing_control_forces_every_row_to_unknown(self):
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        self.assertEqual(self.rows()[1]["verdict"], exitcriteria.MET)
        self._break_a_control("a_planted_met_renders_met")
        for row in self.report()["rows"]:
            self.assertEqual(row["verdict"], exitcriteria.UNKNOWN,
                             "criterion %d survived a failed control"
                             % row["number"])

    def test_the_poisoned_rows_name_the_control_that_failed(self):
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        self._break_a_control("absent_renders_unknown")
        self.assertIn("absent_renders_unknown", self.rows()[1]["reason"])

    def test_the_recorded_verdict_is_still_shown_verbatim(self):
        """Poisoned is not hidden. The reader is untrusted, not the artifact.

        An operator has to be able to see what the file said, or a failed
        control destroys information instead of flagging it.
        """
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        self._break_a_control("absent_renders_unknown")
        self.assertEqual(self.rows()[1]["recorded"], "MET")

    def test_the_report_says_the_controls_did_not_pass(self):
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        self._break_a_control("absent_renders_unknown")
        self.assertFalse(self.report()["controls_ok"])
        self.assertEqual(self.report()["tally"][exitcriteria.MET], 0)


# --------------------------------------------------------------------------
# The block parser, and the things in a 395 KB append-only log that look
# like a verdict table and are not.
# --------------------------------------------------------------------------

class TheBlockParser(unittest.TestCase):

    def parse(self, text):
        return exitcriteria.verdicts_from_text(text)

    def test_a_block_needs_a_majority_of_the_nine(self):
        """A stray numbered line in prose is not a verdict table.

        The lane files discuss criteria by number constantly. Accepting any
        run of numbered lines would let a sentence become the authority.
        """
        found = self.parse("# Notes\n\n    3  li1 still renders nothing\n"
                           "    5  still 26 of 58  NOT MET\n")
        self.assertEqual(found["blocks"], 0)
        self.assertEqual(found["rows"], {})

    def test_the_majority_threshold_is_named_and_is_a_majority(self):
        self.assertGreaterEqual(exitcriteria.MIN_BLOCK, 5)
        self.assertLessEqual(exitcriteria.MIN_BLOCK, 9)

    def test_a_numbered_roster_is_not_a_verdict_block(self):
        """Verbatim from `LANE-pilotcaps.md` line 3753.

        Nine numbered lines in aligned columns, carrying word counts. Under
        a row-count-only threshold this was an accepted verdict block.
        """
        found = self.parse(
            "## the roster - 2026-09-28\n\n"
            "    1   austin-ball               79                83\n"
            "    2   anthony-andreatos         80                84\n"
            "    3   jonathan-moisan           79                83\n"
            "    4   andreas-alex              85                89\n"
            "    5   gianna-mohammed           81                85\n"
            "    6   michael-watts             76                80\n"
            "    7   andrew-kilness            78                82\n"
            "    8   john-mctigue              77                81\n"
            "    9   judy-crawford             79                83\n")
        self.assertEqual(found["blocks"], 0)

    def test_a_numbered_decision_list_is_not_a_verdict_block(self):
        """Verbatim from `LANE-pilotcaps.md` line 6076, and the shape that
        actually won: six numbered open decisions, 272 lines BELOW the real
        verdict table, so last-block-wins handed the page this."""
        found = self.parse(
            "## open decisions - 2026-10-15\n\n"
            "    1  approve ONE read: GET /sender-emails, fully walked\n"
            "    2  does the opt-out sentence count toward the ceiling?\n"
            "    3  authorise the attach despite add_lead being sealed\n"
            "    4  order P1 and P2 - the two resume_campaign sites\n"
            "    5  is the note-less connection request global?\n"
            "    6  criterion 5 wording: literal zero can only be reached\n")
        self.assertEqual(found["blocks"], 0)

    def test_a_majority_of_the_rows_must_record_a_verdict(self):
        """Nine numbered rows, four verdicts. Not a verdict table."""
        rows = "".join("    %d  criterion %d  %s\n"
                       % (n, n, "MET" if n <= 4 else "")
                       for n in range(1, 10))
        self.assertEqual(self.parse("## x - 2026-10-16\n\n" + rows)["blocks"],
                         0)

    def test_the_last_block_that_records_verdicts_wins(self):
        """A roster AFTER the verdict table does not displace it, which is
        the real file's layout and the bug this pair of rules fixes."""
        text = (BLOCK_AS_RECORDED + "\n## the roster - 2026-09-28\n\n"
                + "".join("    %d  somebody-%d   79   83\n" % (n, n)
                          for n in range(1, 10)))
        found = self.parse(text)
        self.assertEqual(found["blocks"], 1)
        self.assertEqual(found["rows"][6]["verdict"], exitcriteria.MET)
        self.assertEqual(found["stamp"], "2026-10-15")

    def test_a_heading_ends_a_block(self):
        """Two runs of four, split by a heading, are not one block of eight.

        Without the heading rule these eight lines merge into an accepted
        block, so this fixture discriminates rather than merely passing.
        """
        text = ("## first\n"
                + "".join("    %d  x  MET\n" % n for n in range(1, 5))
                + "## second\n"
                + "".join("    %d  x  NOT MET\n" % n for n in range(6, 10)))
        self.assertEqual(self.parse(text)["blocks"], 0)

    def test_without_the_heading_those_same_eight_lines_would_be_a_block(self):
        """The control on the test above: the fixture is near the boundary,
        and this proves it is the heading doing the work."""
        text = ("".join("    %d  x  MET\n" % n for n in range(1, 5))
                + "".join("    %d  x  NOT MET\n" % n for n in range(6, 10)))
        self.assertEqual(self.parse(text)["blocks"], 1)

    def test_the_last_block_wins(self):
        text = block(c1="MET") + "\n## a later entry\n\n" + block(c1="NOT MET")
        found = self.parse(text)
        self.assertEqual(found["blocks"], 2)
        self.assertEqual(found["rows"][1]["verdict"], exitcriteria.NOT_MET)

    def test_an_earlier_block_is_counted_not_silently_dropped(self):
        found = self.parse(block(c1="MET") + "\n## later\n\n"
                           + block(c1="NOT MET"))
        self.assertEqual(found["superseded"], 1)

    def test_a_two_digit_number_is_not_criterion_one(self):
        """`10 companies / 30 contacts` appears throughout CANARY-01."""
        self.assertIsNone(exitcriteria.number_on("    10 companies  MET"))

    def test_a_number_followed_by_a_comma_is_not_a_criterion(self):
        """`1,147 campaign-slot claims` is in the same document."""
        self.assertIsNone(
            exitcriteria.number_on("    1,147 campaign-slot claims  MET"))

    def test_zero_is_not_a_criterion(self):
        self.assertIsNone(exitcriteria.number_on("    0  nothing  MET"))

    def test_a_digit_inside_an_identifier_is_not_a_criterion(self):
        self.assertIsNone(exitcriteria.number_on("    em1  body  MET"))

    def test_a_criterion_number_is_recognised_in_a_markdown_table_row(self):
        """pilotcaps 0210's deliverable is described as a table, not a block.

        The format is not known in advance, so both shapes are read and a
        shape that is neither makes the rows UNKNOWN rather than MET.
        """
        self.assertEqual(exitcriteria.number_on("| 4 | ceiling | MET |"), 4)

    def test_a_markdown_table_parses_to_nine_rows(self):
        text = ("# Exit criteria\n\n"
                "| # | criterion | verdict |\n"
                "|---|-----------|---------|\n"
                + "".join("| %d | criterion %d | MET |\n" % (n, n)
                          for n in range(1, 10)))
        found = self.parse(text)
        self.assertEqual(found["blocks"], 1)
        self.assertEqual(len(found["rows"]), 9)
        self.assertEqual(found["rows"][9]["verdict"], exitcriteria.MET)

    def test_a_table_separator_row_is_not_a_criterion(self):
        self.assertIsNone(exitcriteria.number_on("|---|---|---|"))

    def test_prose_at_column_zero_does_not_attach_as_a_continuation(self):
        """A continuation must be indented. Otherwise the paragraph after a
        table contributes a second verdict to its last row."""
        text = block(c9="MET") + "Criterion 9 is NOT MET in my view.\n"
        self.assertEqual(self.parse(text)["rows"][9]["verdict"],
                         exitcriteria.MET)

    def test_an_indented_continuation_does_attach(self):
        text = block(c9="MET") + "        NOT MET on another ref\n"
        self.assertEqual(self.parse(text)["rows"][9]["verdict"],
                         exitcriteria.UNKNOWN)

    def test_the_verbatim_line_is_kept_for_every_row(self):
        found = self.parse(BLOCK_CLEAN)
        self.assertIn("criterion number 1", found["rows"][1]["line"])

    def test_the_recorded_answer_block_parses_to_nine(self):
        """The one fixture taken verbatim from a real recorded artifact."""
        found = self.parse(BLOCK_AS_RECORDED)
        self.assertEqual(len(found["rows"]), 9)
        self.assertEqual(found["rows"][4]["verdict"], exitcriteria.UNKNOWN)
        self.assertEqual(found["rows"][6]["verdict"], exitcriteria.MET)


# --------------------------------------------------------------------------
# The source chain.
# --------------------------------------------------------------------------

class TheSourceChain(ASource, unittest.TestCase):

    def test_the_designated_authority_outranks_the_lane_report(self):
        self.write(exitcriteria.DESIGNATED, block(c1="MET"))
        self.write(exitcriteria.LANE_REPORT, block(c1="NOT MET"))
        row = self.rows()[1]
        self.assertEqual(row["verdict"], exitcriteria.MET)
        self.assertEqual(row["source_name"], exitcriteria.DESIGNATED)

    def test_a_source_that_answers_nothing_falls_through_to_the_next(self):
        self.write(exitcriteria.DESIGNATED, "# nothing here yet\n")
        self.write(exitcriteria.LANE_REPORT, block(c1="MET"))
        row = self.rows()[1]
        self.assertEqual(row["verdict"], exitcriteria.MET)
        self.assertEqual(row["source_name"], exitcriteria.LANE_REPORT)

    def test_a_source_silent_on_one_criterion_falls_through_per_criterion(self):
        text = "\n".join(line for line in block(c1="MET").splitlines()
                         if "criterion number 7" not in line) + "\n"
        self.write(exitcriteria.DESIGNATED, text)
        self.write(exitcriteria.LANE_REPORT, block(c7="MET"))
        rows = self.rows()
        self.assertEqual(rows[1]["source_name"], exitcriteria.DESIGNATED)
        self.assertEqual(rows[7]["source_name"], exitcriteria.LANE_REPORT)
        self.assertEqual(rows[7]["verdict"], exitcriteria.MET)

    def test_a_higher_ranked_unknown_is_not_overruled_by_a_lower_source(self):
        """The authority answered. A weaker source disagreeing does not get
        to resolve it - that would be the page choosing a verdict."""
        self.write(exitcriteria.DESIGNATED, block(c1="MET-WITH-CAVEAT"))
        self.write(exitcriteria.LANE_REPORT, block(c1="MET"))
        row = self.rows()[1]
        self.assertEqual(row["verdict"], exitcriteria.UNKNOWN)
        self.assertEqual(row["source_name"], exitcriteria.DESIGNATED)

    def test_every_row_names_the_source_that_answered_it(self):
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        for row in self.report()["rows"]:
            self.assertEqual(row["source_name"], exitcriteria.DESIGNATED)

    def test_a_lane_report_is_labelled_as_a_claim_not_an_audit(self):
        """A lane's claim about its own work is a claim. 2026-10-15 produced
        four corrections to exactly that kind of claim."""
        self.write(exitcriteria.LANE_REPORT, block(c1="MET"))
        self.assertIn("not the audit", self.rows()[1]["source_kind"].lower())

    def test_the_repository_sourced_audit_is_read_from_the_repository(self):
        self.write(exitcriteria.IN_REPO_AUDIT, block(c1="MET"), where="repo")
        row = self.rows()[1]
        self.assertEqual(row["verdict"], exitcriteria.MET)
        self.assertEqual(row["source_where"], exitcriteria.LOC_REPO)

    def test_the_sources_are_ranked_and_the_ranks_are_distinct(self):
        ranks = [s["rank"] for s in exitcriteria.SOURCES]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(len(set(ranks)), len(ranks))

    def test_every_source_is_reported_even_when_it_answered_nothing(self):
        """A reader has to be able to see which authorities were consulted
        and what each one was, or an absence looks like a choice."""
        keys = {s["key"] for s in self.report()["sources"]}
        self.assertEqual(keys, {s["key"] for s in exitcriteria.SOURCES})


# --------------------------------------------------------------------------
# `as of` is the artifact's age, never the render's.
# --------------------------------------------------------------------------

class AsOfIsTheArtifactsAge(ASource, unittest.TestCase):

    def test_as_of_is_the_documents_own_stamp_when_it_has_one(self):
        self.write(exitcriteria.DESIGNATED, BLOCK_AS_RECORDED)
        row = self.rows()[2]
        self.assertEqual(row["as_of"], "2026-10-15")
        self.assertEqual(row["as_of_kind"], exitcriteria.AS_OF_STAMP)

    def test_a_date_inside_a_branch_name_is_not_the_entrys_stamp(self):
        """Measured on the real `LANE-pilotcaps.md`, not imagined.

        The first read of it dated TASK 0160's verdict block 2026-10-14, by
        harvesting the date out of `task-pilotcaps-enforcer-2026-10-14` two
        lines above the table, when the entry's own heading says 2026-10-15.
        `\\b` matches inside a hyphenated identifier, so both boundaries have
        to be spelled out.
        """
        self.write(exitcriteria.DESIGNATED,
                   "## THE ANSWER - 2026-10-15\n\n"
                   "    branch  task-pilotcaps-enforcer-2026-10-14\n\n"
                   + "".join("    %d  x  MET\n" % n for n in range(1, 10)))
        self.assertEqual(self.rows()[1]["as_of"], "2026-10-15")

    def test_a_date_in_a_filename_is_not_a_stamp_either(self):
        self.write(exitcriteria.DESIGNATED,
                   "## THE ANSWER\n\n"
                   "    see FINDING-the-24-names-2026-10-16.md\n\n"
                   + "".join("    %d  x  MET\n" % n for n in range(1, 10)))
        self.assertEqual(self.rows()[1]["as_of_kind"], exitcriteria.AS_OF_MTIME)

    def test_a_document_with_no_stamp_falls_back_to_mtime_and_says_so(self):
        self.write(exitcriteria.DESIGNATED,
                   "## THE ANSWER\n\n"
                   + "".join("    %d  x  NOT MET\n" % n for n in range(1, 10)))
        row = self.rows()[1]
        self.assertEqual(row["as_of_kind"], exitcriteria.AS_OF_MTIME)
        self.assertTrue(row["as_of"])

    def test_the_as_of_does_not_move_when_the_render_does(self):
        """The defect this whole lane exists to avoid, as an assertion.

        A stale verdict shown with its real age is useful. The same verdict
        shown as current is the one that gets believed.
        """
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        first = self.rows(NOW)[1]
        later = self.rows(NOW + datetime.timedelta(days=3))[1]
        self.assertEqual(first["as_of"], later["as_of"])
        self.assertGreater(later["age_seconds"], first["age_seconds"])

    def test_the_age_is_computed_from_the_stamp(self):
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        row = self.rows(datetime.datetime(2026, 10, 17, 0, 0, 0))[1]
        self.assertEqual(row["age_seconds"], 86400)

    def test_a_stamp_in_the_future_is_flagged_rather_than_a_negative_age(self):
        self.write(exitcriteria.DESIGNATED,
                   BLOCK_CLEAN.replace("2026-10-16", "2026-11-20"))
        row = self.rows()[1]
        self.assertTrue(row["as_of_in_future"])
        self.assertIsNone(row["age_seconds"])

    def test_a_verdict_older_than_the_horizon_is_marked_stale(self):
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        self.assertFalse(self.rows(NOW)[1]["stale"])
        old = self.rows(NOW + datetime.timedelta(
            seconds=exitcriteria.STALE_SECONDS + 60))[1]
        self.assertTrue(old["stale"])

    def test_stale_is_not_a_verdict_and_does_not_change_one(self):
        """Age is shown beside the verdict, never substituted for it."""
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        old = self.rows(NOW + datetime.timedelta(days=30))[1]
        self.assertEqual(old["verdict"], exitcriteria.MET)
        self.assertTrue(old["stale"])


# --------------------------------------------------------------------------
# Nine rows, always, each naming its own authority.
# --------------------------------------------------------------------------

class NineRowsWhateverHappens(ASource, unittest.TestCase):

    def test_there_are_nine_criteria(self):
        self.assertEqual(len(exitcriteria.CRITERIA), 9)
        self.assertEqual([c["number"] for c in exitcriteria.CRITERIA],
                         list(range(1, 10)))

    def test_nine_rows_render_when_every_source_is_absent(self):
        self.assertEqual(len(self.report()["rows"]), 9)

    def test_nine_rows_render_when_a_source_holds_only_some(self):
        self.write(exitcriteria.DESIGNATED, block(c1="MET"))
        self.assertEqual(len(self.report()["rows"]), 9)

    def test_every_criterion_names_an_authority_and_where_it_lives(self):
        for row in self.report()["rows"]:
            self.assertTrue(row["authority"], row["number"])
            self.assertIn(row["location"], exitcriteria.LOCATION_TEXT)
            self.assertTrue(row["statement"])

    def test_the_locations_include_authorities_outside_the_repository(self):
        """TASK 0020 measured that six of eleven operator questions have an
        authority outside `src/web/`. Some of the nine are outside it too,
        and a page implying otherwise would be the same defect."""
        used = {c["location"] for c in exitcriteria.CRITERIA}
        self.assertIn(exitcriteria.LOC_OPERATOR, used)
        self.assertIn(exitcriteria.LOC_PROVIDER, used)

    def test_the_registry_notices_canary_01_growing_a_tenth_criterion(self):
        """The page's own copy of the nine going stale is a real risk.

        `CANARY-01.md` is the authority for WHICH criteria exist. If it ever
        lists a different number, this page must say so rather than show
        nine of ten and look complete.
        """
        self.write(exitcriteria.DEFINITION,
                   "## Exit criteria\n\n"
                   + "".join("%d. criterion %d\n" % (n, n)
                             for n in range(1, 11)))
        self.assertTrue(self.report()["registry_drift"])

    def test_no_drift_is_reported_when_the_definition_still_lists_nine(self):
        self.write(exitcriteria.DEFINITION,
                   "## Exit criteria\n\n"
                   + "".join("%d. criterion %d\n" % (n, n)
                             for n in range(1, 10)))
        self.assertIsNone(self.report()["registry_drift"])

    def test_an_absent_definition_is_not_reported_as_agreement(self):
        data = self.report()
        self.assertEqual(data["registry_state"], exitcriteria.ABSENT)
        self.assertIsNone(data["registry_drift"])
        self.assertTrue(data["registry_unchecked"])


# --------------------------------------------------------------------------
# What it refuses to do.
# --------------------------------------------------------------------------

class ItReadsAndWritesNothingElse(ASource, unittest.TestCase):

    def test_it_writes_no_file(self):
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        before = sorted(os.listdir(self.ops))
        self.report()
        self.report()
        self.assertEqual(sorted(os.listdir(self.ops)), before)
        self.assertEqual(sorted(os.listdir(self.repo)), [])

    def test_it_opens_no_socket(self):
        """Patched to raise, then called. A measurement, not a claim."""
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        real = socket.socket

        def refuse(*a, **k):
            raise AssertionError("the exit-criteria reader opened a socket")

        socket.socket = refuse
        self.addCleanup(setattr, socket, "socket", real)
        self.assertEqual(self.rows()[1]["verdict"], exitcriteria.MET)

    def test_an_unset_ops_dir_is_unconfigured_rather_than_no_answer(self):
        os.environ.pop(lanes.OPS_DIR, None)
        data = exitcriteria.report(root=self.repo, now=NOW)
        self.assertEqual(data["ops_state"], exitcriteria.UNCONFIGURED)
        for row in data["rows"]:
            self.assertEqual(row["verdict"], exitcriteria.UNKNOWN)

    def test_an_ops_sourced_row_says_unconfigured_rather_than_absent(self):
        os.environ.pop(lanes.OPS_DIR, None)
        data = exitcriteria.report(root=self.repo, now=NOW)
        source = {s["key"]: s for s in data["sources"]}
        self.assertEqual(source[exitcriteria.DESIGNATED]["state"],
                         exitcriteria.UNCONFIGURED)

    def test_a_directory_where_a_source_file_should_be_is_unreadable(self):
        """Fail closed on a shape nobody planned for, rather than crash."""
        os.makedirs(os.path.join(self.ops, exitcriteria.DESIGNATED))
        data = self.report()
        source = {s["key"]: s for s in data["sources"]}
        self.assertEqual(source[exitcriteria.DESIGNATED]["state"],
                         exitcriteria.UNREADABLE)
        self.assertEqual(data["tally"][exitcriteria.MET], 0)

    def test_describe_runs_and_names_the_controls(self):
        self.write(exitcriteria.DESIGNATED, BLOCK_CLEAN)
        text = exitcriteria.describe(self.report())
        for control in exitcriteria.controls(now=NOW):
            self.assertIn(control["name"], text)
        self.assertIn("PASS", text)


# --------------------------------------------------------------------------
# The page.
# --------------------------------------------------------------------------

class ThePage(WebTest):
    """Served over real HTTP, by the real handler, through the real gate.

    The fixture is TASK 0160's answer verbatim, so the page under test shows
    all three verdicts at once - two UNKNOWN from a caveat, one UNKNOWN from
    a contest, and the rest decided.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ops = tempfile.mkdtemp(prefix="rga-nine-web-")
        with open(os.path.join(cls.ops, exitcriteria.DESIGNATED), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write(BLOCK_AS_RECORDED)
        cls._previous_ops = os.environ.get(lanes.OPS_DIR)
        os.environ[lanes.OPS_DIR] = cls.ops

    @classmethod
    def tearDownClass(cls):
        if cls._previous_ops is None:
            os.environ.pop(lanes.OPS_DIR, None)
        else:
            os.environ[lanes.OPS_DIR] = cls._previous_ops
        shutil.rmtree(cls.ops, ignore_errors=True)
        super().tearDownClass()

    def test_a_super_admin_gets_the_page(self):
        status, body, _ = self.signin(SUPER).get(PATH)
        self.assertEqual(status, 200)
        self.assertIn("Exit criteria", body)

    def test_a_workspace_admin_is_refused(self):
        status, body, _ = self.signin(ADMIN).get(PATH)
        self.assertEqual(status, 404, "404 rather than 403, as /admin does")
        self.assertNotIn("Exit criteria", body)

    def test_an_operator_is_refused(self):
        status, _body, _ = self.signin(OPERATOR).get(PATH)
        self.assertEqual(status, 404)

    def test_an_anonymous_caller_is_never_served_the_page(self):
        status, body, _ = self.anonymous().get(PATH)
        self.assertIn(status, (200, 303))
        self.assertNotIn("Exit criteria", body)
        self.assertIn("Sign in", body)

    def test_the_route_is_not_gated_by_a_workspace_permission(self):
        self.assertIsNone(permission_for(PATH))

    def test_the_navigation_entry_is_super_admin_only(self):
        found = [entry for _k, _t, _h, items in pages.SECTIONS
                 for entry in items if entry[0] == PATH]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][2], "__super_admin__")

    def test_a_POST_is_not_accepted(self):
        session = self.signin(SUPER)
        status, _body, _ = session.post(PATH, {"csrf": session.csrf()})
        self.assertNotEqual(status, 200)

    def test_the_three_controls_are_on_the_page_with_pass_or_fail(self):
        _status, body, _ = self.signin(SUPER).get(PATH)
        for control in exitcriteria.controls():
            self.assertIn(control["name"], body)
        self.assertIn("PASS", body)

    def test_the_reason_is_in_the_row_and_not_only_in_a_tooltip(self):
        """The brief's words: visible in the row, not hidden in a tooltip.

        So the reason text appears as content, and is not carried only by a
        `title=` attribute a reader has to hover to find.
        """
        _status, body, _ = self.signin(SUPER).get(PATH)
        reasons = [row["reason"] for row in api.exit_criteria()["rows"]
                   if row["reason"]]
        self.assertTrue(reasons, "this fixture must leave reasons to show")
        for reason in reasons:
            fragment = pages.esc(reason[:60])
            self.assertIn(fragment, body)
            self.assertNotIn('title="' + fragment, body)

    def test_every_verdict_label_the_reader_can_produce_is_rendered(self):
        _status, body, _ = self.signin(SUPER).get(PATH)
        for label, _why in exitcriteria.VERDICT_TEXT.values():
            self.assertIn(label, body)

    def test_the_page_prints_no_absolute_path(self):
        """The ops estate is somebody's home directory. A path on a screen
        is that person's name in a screenshot."""
        _status, body, _ = self.signin(SUPER).get(PATH)
        self.assertNotIn(self.ops, body)
        self.assertNotIn(self.ops.replace("\\", "\\\\"), body)

    def test_the_page_shows_the_as_of_of_its_rows(self):
        _status, body, _ = self.signin(SUPER).get(PATH)
        self.assertIn("2026-10-15", body)

    def test_the_page_names_where_each_authority_lives(self):
        _status, body, _ = self.signin(SUPER).get(PATH)
        for label, _why in exitcriteria.LOCATION_TEXT.values():
            self.assertIn(pages.esc(label), body)


class TheVariableIsTheOneTheLaneBoardAlreadyUses(unittest.TestCase):
    """One estate, one variable. A second name for the same directory is how
    two readers come to disagree about where the lanes are."""

    def test_it_reuses_the_lane_boards_variable(self):
        self.assertEqual(exitcriteria.OPS_DIR, lanes.OPS_DIR)

    def test_that_variable_is_in_the_registry(self):
        from src import config
        self.assertIn(exitcriteria.OPS_DIR, config.BY_NAME)


if __name__ == "__main__":
    unittest.main()
