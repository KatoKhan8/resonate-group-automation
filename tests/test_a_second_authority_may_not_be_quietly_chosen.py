#!/usr/bin/env python3
"""The exit-criteria page's rule for an authority set that has GROWN.

WHY THIS MODULE EXISTS. TASK 0090 proved the page is a live read: `report()`
calls `_read_chain()` calls `read_source()`, every authority reopened on every
render, no verdict cached anywhere. Fifteen minutes after that task closed,
`EXIT-NINE-AT-ONCE-2026-10-16.md` was written - the first artifact in the
estate answering all nine criteria in one tree, at one SHA, in one run.

Measured at `c6ac4b88c`, the page opened three files on a render and that was
not one of them. **A live read of a stale authority SET is still stale**, and
the page's silence about the new authority was ignorance rather than
agreement. Those are not the same fact and the difference is the whole task.

WHAT IS ASSERTED HERE, AND WHAT IS NOT. Every test below is about what the
page DOES with two authorities. Not one of them asserts that a criterion is
met: the page reads verdicts out of recorded artifacts and measures nothing,
so a test that pinned a verdict would pin an artifact that moves every few
minutes - `LANE-pilotcaps.md`'s modification time moved twice while this
module was being written.

THE DIRECTION, FOR EACH RULE. Four rules were added and three of them push
towards UNKNOWN, which is the safe direction and therefore the one that can
hide a broken reader. `agreeing_authorities_can_still_render_met` is the
counterweight and it is asserted here as well as run as a control: an
instrument that only ever answers UNKNOWN is not cautious, it is broken.
"""

import datetime
import os
import shutil
import tempfile
import unittest

from src import exitcriteria
from src.web import api, pages
#: THE TEMPORARY-ESTATE MIXIN IS IMPORTED, NOT COPIED. A second copy of
#: 'point LANE_OPS_DIR at a scratch directory and tear it down' is a
#: second representation of one fixture, and the two drift - which is the
#: module under test's own first principle.
from tests.test_the_nine_exit_criteria_render_unknown import ASource


#: A fixed clock. The fixtures carry this date, so an age is establishable
#: and nothing here renders STALE for want of one.
NOW = datetime.datetime(2026, 10, 16, 12, 0, 0)

ALL_NINE = tuple(criterion["number"] for criterion in exitcriteria.CRITERIA)


def _table(verdicts, title="A FIXTURE AUTHORITY", date="2026-10-16"):
    """A dated nine-row pipe table, the shape both ops authorities use."""
    lines = ["## %s - %s" % (title, date), "",
             "| # | criterion | verdict |", "|---|---|---|"]
    for number in ALL_NINE:
        lines.append("| %d | fixture criterion %d | **%s** |"
                     % (number, number,
                        exitcriteria.VERDICT_TEXT[verdicts[number]][0]))
    return "\n".join(lines) + "\n"


def _source(name, verdicts, rank, title="A FIXTURE AUTHORITY"):
    return {"key": name, "name": name, "rank": rank,
            "where": exitcriteria.LOC_REPO, "kind": "a fixture authority",
            "text": _table(verdicts, title)}


def _rows(sources):
    """The assembled rows for a list of inline fixture sources."""
    chain = exitcriteria._read_chain(
        sources, exitcriteria.REPO_ROOT, exitcriteria.REPO_ROOT,
        exitcriteria.PRESENT, NOW)
    return {row["number"]: row
            for row in exitcriteria._assemble(chain, NOW)}


MIXED = {1: exitcriteria.MET, 2: exitcriteria.NOT_MET,
         3: exitcriteria.MET, 4: exitcriteria.NOT_MET,
         5: exitcriteria.MET, 6: exitcriteria.NOT_MET,
         7: exitcriteria.MET, 8: exitcriteria.NOT_MET,
         9: exitcriteria.MET}
ALL_MET = {number: exitcriteria.MET for number in ALL_NINE}


# ---------------------------------------------------------------------------
# The two parser repairs that reading the new authority at all depended on.


class TheParserReadsTheRightTable(unittest.TestCase):
    """A document's own verdict block, and not its report about another's."""

    def test_a_block_headed_with_another_authoritys_name_is_not_this_ones(self):
        """The defect, reproduced on the real shape.

        `EXIT-NINE-AT-ONCE-2026-10-16.md` holds its nine under `## 0. THE
        NINE` and a five-row comparison under `## 4. WHERE I DISAGREE WITH
        EXIT-CRITERIA-2026-10-16.md ...`. "The last live block wins" took the
        COMPARISON, so criteria 3, 4, 5 and 8 disappeared and every surviving
        row carried a composite of two documents' verdicts.
        """
        text = (_table(ALL_MET, "0. THE NINE")
                + "\n## 4. WHERE I DISAGREE WITH OTHER-AUTHORITY.md\n\n"
                + "| # | theirs | mine |\n|---|---|---|\n"
                + "| 1 | NOT MET | **NOT MET** |\n"
                + "| 2 | NOT MET | **NOT MET** |\n"
                + "| 6 | NOT MET | **NOT MET** |\n"
                + "| 7 | NOT MET | **NOT MET** |\n"
                + "| 9 | NOT MET | **NOT MET** |\n")
        parsed = exitcriteria.verdicts_from_text(text, self_name="MINE.md")
        self.assertEqual(sorted(parsed["rows"]), list(ALL_NINE))
        self.assertEqual(parsed["foreign_blocks"], 1)
        for number in ALL_NINE:
            self.assertEqual(parsed["rows"][number]["verdict"],
                             exitcriteria.MET, "criterion %d" % number)

    def test_the_foreign_block_is_what_would_have_been_read(self):
        """The control on the test above, and it is not decoration.

        Without it the first test passes on a parser that rejected the
        comparison for ANY reason - a count threshold, a stray character -
        and the measurement being claimed is that a FOREIGN HEADING did it.
        So the same bytes with the filename removed from the heading must
        come back the other way.
        """
        text = (_table(ALL_MET, "0. THE NINE")
                + "\n## 4. WHERE I DISAGREE WITH ANOTHER TASK\n\n"
                + "| # | theirs | mine |\n|---|---|---|\n"
                + "| 1 | NOT MET | **NOT MET** |\n"
                + "| 2 | NOT MET | **NOT MET** |\n"
                + "| 6 | NOT MET | **NOT MET** |\n"
                + "| 7 | NOT MET | **NOT MET** |\n"
                + "| 9 | NOT MET | **NOT MET** |\n")
        parsed = exitcriteria.verdicts_from_text(text, self_name="MINE.md")
        self.assertEqual(parsed["foreign_blocks"], 0)
        self.assertEqual(sorted(parsed["rows"]), [1, 2, 6, 7, 9])

    def test_a_heading_naming_this_file_itself_is_not_foreign(self):
        """A document is allowed to title itself with its own name."""
        text = "# THE STATE OF MINE.md - 2026-10-16\n\n" + _table(ALL_MET)
        parsed = exitcriteria.verdicts_from_text(text, self_name="MINE.md")
        self.assertEqual(parsed["foreign_blocks"], 0)
        self.assertEqual(sorted(parsed["rows"]), list(ALL_NINE))

    def test_a_tally_line_after_a_table_is_not_part_of_its_last_row(self):
        """The live defect: a summary line belongs to no row.

        The real artifact writes `    tally   MET 3   NOT MET 3   UNKNOWN 3`
        under its table. Indented, three verdict tokens, so all three were
        appended to criterion 9 and a cell stating **NOT MET** contested to
        UNKNOWN.
        """
        verdicts = dict(ALL_MET)
        verdicts[9] = exitcriteria.NOT_MET
        text = (_table(verdicts)
                + "\n    tally   MET 8   NOT MET 1   UNKNOWN 0\n")
        parsed = exitcriteria.verdicts_from_text(text, self_name="MINE.md")
        self.assertEqual(parsed["rows"][9]["verdict"], exitcriteria.NOT_MET)
        self.assertEqual(parsed["rows"][9]["recorded"], "NOT MET")

    def test_an_indented_block_still_takes_its_continuation(self):
        """The control on that one: the rule it narrows must still work.

        TASK 0160's authority writes an indented run, not a table, and its
        verdict may sit on the line below the number. Narrowing the
        continuation to the indented shape is only correct if the indented
        shape keeps it.
        """
        lines = ["## AN INDENTED FIXTURE - 2026-10-16", ""]
        for number in ALL_NINE:
            lines.append("    %d  indented criterion %d" % (number, number))
            lines.append("        MET")
        parsed = exitcriteria.verdicts_from_text(
            "\n".join(lines) + "\n", self_name="MINE.md")
        self.assertEqual(sorted(parsed["rows"]), list(ALL_NINE))
        for number in ALL_NINE:
            self.assertEqual(parsed["rows"][number]["verdict"],
                             exitcriteria.MET, "criterion %d" % number)

    def test_a_verdict_cell_outranks_the_prose_in_its_own_row(self):
        """Criterion 9's real row, which argues about its own history.

        `| 9 | ... | **NOT MET** | ... | Measured from the SHIPPED default
        ... the whole reason 9 once read MET while the default was never
        exercised. |` - the whole-line reader harvested NOT MET and MET,
        contested them, and reported an authority that could not be clearer
        as unanswered.
        """
        row = ("| 9 | a kill switch | **NOT MET** | measured from the "
               "SHIPPED default - the whole reason 9 once read MET while "
               "the default was never exercised |")
        self.assertEqual(exitcriteria._cell_tokens_on(row), ["NOT MET"])
        self.assertEqual(exitcriteria._tokens_on(row), ["NOT MET", "MET"])

    def test_a_row_writing_its_verdict_inline_still_reads(self):
        """The fallback, and `EXIT-CRITERIA-2026-10-16.md` depends on it.

        Its criterion 9 cell is `**NOT MET - the two trees disagree.** The
        Q2 plant is CLOSED at T3 ...` - a prose cell with the verdict inside
        it. No cell there is NOTHING BUT a verdict, so cell-reading must
        return nothing and the whole line must still be read, or the
        designated authority stops answering at all.
        """
        row = ("| 5 | zero write paths bypass the gate | **NOT MET - 26 of "
               "58 bypass**, and the analyzer errs in both directions |")
        self.assertEqual(exitcriteria._cell_tokens_on(row), [])
        self.assertEqual(exitcriteria._tokens_on(row), ["NOT MET"])

    def test_a_table_cell_with_two_verdicts_contests(self):
        """Preferring the cell may not switch the contest rule off.

        This is the guard named in `_cell_tokens_on`'s own docstring. Two
        whole-cell verdicts that differ are a comparison row, and a
        comparison row has no single answer.
        """
        row = "| 3 | fixture | **MET** | **NOT MET** |"
        self.assertEqual(
            {exitcriteria._normalise(token)
             for token in exitcriteria._cell_tokens_on(row)},
            {"MET", "NOT MET"})
        parsed = exitcriteria.verdicts_from_text(
            "## A FIXTURE - 2026-10-16\n\n| # | a | b | c |\n|---|---|---|---|\n"
            + row + "\n| 4 | fixture | **MET** | **MET** |\n",
            self_name="MINE.md")
        self.assertEqual(parsed["rows"][3]["verdict"], exitcriteria.UNKNOWN)
        self.assertEqual(parsed["rows"][4]["verdict"], exitcriteria.MET)


# ---------------------------------------------------------------------------
# The cross-file rule itself.


class TwoAuthoritiesForOneCriterion(unittest.TestCase):
    """Agreement is named; disagreement refuses; neither is resolved."""

    def test_the_new_authority_is_in_the_configured_set(self):
        """It has to be IN the set for any rule below to reach it.

        The whole defect was a file that existed, answered all nine, and was
        never opened - so the one assertion that catches a regression to that
        state is that the configuration names it.
        """
        names = [source["name"] for source in exitcriteria.SOURCES]
        self.assertIn(exitcriteria.AT_ONCE, names)
        self.assertEqual(exitcriteria.AT_ONCE,
                         "EXIT-NINE-AT-ONCE-2026-10-16.md")

    def test_the_ranks_are_distinct_and_cover_every_source(self):
        """A duplicate rank makes `min(chain, key=rank)` arbitrary, and the
        designated authority would then be whichever one sorted first."""
        ranks = [source["rank"] for source in exitcriteria.SOURCES]
        self.assertEqual(sorted(ranks), list(range(1, len(ranks) + 1)))

    def test_two_agreeing_authorities_render_the_verdict_and_name_both(self):
        rows = _rows([_source("a.md", MIXED, 1), _source("b.md", MIXED, 2)])
        for number in ALL_NINE:
            row = rows[number]
            self.assertEqual(row["verdict"], MIXED[number],
                             "criterion %d" % number)
            self.assertFalse(row["contested"], "criterion %d" % number)
            self.assertEqual({item["source_name"]
                              for item in row["agreement"]},
                             {"a.md", "b.md"}, "criterion %d" % number)

    def test_one_authority_alone_is_not_corroborated(self):
        """`agreement` is empty for a single source. A row naming one file as
        "1 authority agrees" would read as corroboration of itself."""
        rows = _rows([_source("a.md", MIXED, 1)])
        for number in ALL_NINE:
            self.assertEqual(rows[number]["agreement"], [],
                             "criterion %d" % number)

    def test_two_disagreeing_authorities_render_contested(self):
        flipped = dict(MIXED)
        flipped[3] = exitcriteria.NOT_MET
        rows = _rows([_source("a.md", MIXED, 1),
                      _source("b.md", flipped, 2)])
        three = rows[3]
        self.assertEqual(three["verdict"], exitcriteria.UNKNOWN)
        self.assertTrue(three["contested"])
        self.assertIn("CONTESTED", three["verdict_label"])
        self.assertEqual({item["verdict"] for item in three["disagreement"]},
                         {exitcriteria.MET, exitcriteria.NOT_MET})
        self.assertEqual({item["source_name"]
                          for item in three["disagreement"]},
                         {"a.md", "b.md"})
        self.assertIn("a.md", three["reason"])
        self.assertIn("b.md", three["reason"])

    def test_the_eight_they_agree_on_are_left_alone(self):
        """The control on the test above. A reader that answered CONTESTED to
        everything would satisfy it, and would be worthless."""
        flipped = dict(MIXED)
        flipped[3] = exitcriteria.NOT_MET
        rows = _rows([_source("a.md", MIXED, 1),
                      _source("b.md", flipped, 2)])
        for number in ALL_NINE:
            if number == 3:
                continue
            self.assertFalse(rows[number]["contested"],
                             "criterion %d" % number)
            self.assertEqual(rows[number]["verdict"], MIXED[number],
                             "criterion %d" % number)

    def test_a_contest_is_unknown_even_when_neither_reading_is_met(self):
        """Criterion 9's real shape on 2026-10-16, and the reason the rule
        was widened.

        `EXIT-CRITERIA-2026-10-16.md` records WITHDRAWN and
        `EXIT-NINE-AT-ONCE-2026-10-16.md` records NOT MET. Neither is a pass,
        so TASK 0090's rule - which downgraded a disputed MET only - left it
        alone, and the page reported WITHDRAWN as though one authority had
        answered. The authorities disagree about what KIND of failure this
        is, and a reader who has to act needs to know that.
        """
        withdrawn = ("## A WITHDRAWING AUTHORITY - 2026-10-16\n\n"
                     "| # | criterion | verdict |\n|---|---|---|\n"
                     "| 9 | a kill switch | ~~MET at e84108f5d~~ SUPERSEDED |\n")
        refusing = dict(MIXED)
        refusing[9] = exitcriteria.NOT_MET
        rows = _rows([
            {"key": "w.md", "name": "w.md", "rank": 1,
             "where": exitcriteria.LOC_REPO, "kind": "a fixture authority",
             "text": withdrawn},
            _source("b.md", refusing, 2)])
        nine = rows[9]
        self.assertEqual(nine["verdict"], exitcriteria.UNKNOWN)
        self.assertTrue(nine["contested"])
        self.assertEqual({item["verdict"] for item in nine["disagreement"]},
                         {exitcriteria.WITHDRAWN, exitcriteria.NOT_MET})

    def test_a_contested_row_names_both_measuring_tasks_or_says_it_cannot(self):
        """Both tasks, by name - and an authority naming none says so.

        `EXIT-NINE-AT-ONCE-2026-10-16.md` carries its tree, its branch, its
        SHA and its run clock and NO task id. A page required to name the
        measuring task must then say it was not named, never supply one.
        """
        flipped = dict(MIXED)
        flipped[3] = exitcriteria.NOT_MET
        rows = _rows([
            {"key": "a.md", "name": "a.md", "rank": 1,
             "where": exitcriteria.LOC_REPO, "kind": "a fixture authority",
             "text": "# TASK 0210 MEASURED THIS - 2026-10-16\n\n"
                     + _table(MIXED)},
            _source("b.md", flipped, 2)])
        three = rows[3]
        tasks = {item["source_name"]: item["task"]
                 for item in three["disagreement"]}
        self.assertEqual(tasks["a.md"], "TASK 0210")
        self.assertIsNone(tasks["b.md"])
        self.assertIn("TASK 0210", three["reason"])
        self.assertIn("no measuring task named in the file", three["reason"])

    def test_the_page_does_not_resolve_a_contest_by_rank(self):
        """Either order of the same two readings gives the same cell.

        Rank decides which reading is QUOTED first and nothing else. If
        swapping the ranks changed the verdict, rank would be resolving the
        dispute, which is the one thing the rule forbids.
        """
        flipped = dict(MIXED)
        flipped[3] = exitcriteria.NOT_MET
        first = _rows([_source("a.md", MIXED, 1),
                       _source("b.md", flipped, 2)])[3]
        second = _rows([_source("b.md", flipped, 1),
                        _source("a.md", MIXED, 2)])[3]
        self.assertEqual(first["verdict"], second["verdict"])
        self.assertEqual(first["verdict"], exitcriteria.UNKNOWN)
        self.assertTrue(first["contested"] and second["contested"])

    def test_a_silent_designated_authority_does_not_veto(self):
        """Criteria 4 and 8 are the live instance.

        `EXIT-CRITERIA-2026-10-16.md` re-audited criteria 3, 5 and 9 only, so
        it was never going to answer either - and nothing else in the page's
        old set answered them, so both read UNKNOWN while an authority on
        disk said MET. The answer stands, MARKED.
        """
        partial = ("## A PARTIAL RE-AUDIT - 2026-10-16\n\n"
                   "| # | criterion | verdict |\n|---|---|---|\n"
                   "| 3 | three | **NOT MET** |\n"
                   "| 5 | five | **NOT MET** |\n")
        rows = _rows([
            {"key": "p.md", "name": "p.md", "rank": 1,
             "where": exitcriteria.LOC_REPO, "kind": "a fixture authority",
             "text": partial},
            _source("b.md", ALL_MET, 2)])
        self.assertEqual(rows[4]["verdict"], exitcriteria.MET)
        self.assertTrue(rows[4]["off_designated"])
        self.assertEqual(rows[4]["source_name"], "b.md")
        # And a criterion the designated authority DID answer is not marked.
        self.assertEqual(rows[3]["source_name"], "p.md")
        self.assertFalse(rows[3]["off_designated"])

    def test_agreeing_authorities_can_still_render_met(self):
        """The counterweight. Three of the four rules push towards UNKNOWN,
        and an instrument that only ever says UNKNOWN is broken, not
        cautious."""
        rows = _rows([_source("a.md", ALL_MET, 1),
                      _source("b.md", ALL_MET, 2)])
        self.assertEqual({row["verdict"] for row in rows.values()},
                         {exitcriteria.MET})
        verdict, _why = exitcriteria.conjunction_of(
            list(rows.values()), complete=True)
        self.assertEqual(verdict, exitcriteria.MET)


# ---------------------------------------------------------------------------
# The blind spot, announced.


class TheSetMayBeIncomplete(unittest.TestCase):
    """A file the configuration does not name, found on a real disk."""

    def setUp(self):
        super().setUp()
        self.scratch = tempfile.mkdtemp(prefix="exitcriteria-discovery-")
        self.addCleanup(shutil.rmtree, self.scratch, True)

    def _write(self, name, text):
        with open(os.path.join(self.scratch, name), "w",
                  encoding="utf-8") as handle:
            handle.write(text)

    def test_an_unregistered_authority_is_announced(self):
        """THE REAL `os.listdir` PATH, with a real directory on a real disk.

        The per-render control injects its listing, because `report()`
        promises to write no file and the directory it scans is the ops
        estate, which this lane may not write to. An injected listing cannot
        show that the scan looks in the right PLACE, so that half is proven
        here instead - in a temporary directory outside the repository, so
        the hygiene corpus never sees it.
        """
        self._write("CONFIGURED.md", _table(MIXED))
        self._write("STRANGER.md", _table(MIXED))
        self._write("SILENT.md", "# A FILE THAT ANSWERS NOTHING\n\nprose.\n")
        self._write("NOT-MARKDOWN.txt", _table(MIXED))
        seen = exitcriteria._discover(
            self.scratch, exitcriteria.PRESENT, ["CONFIGURED.md"])
        self.assertFalse(seen["blind"])
        self.assertFalse(seen["injected"])
        self.assertEqual([item["name"] for item in seen["found"]],
                         ["STRANGER.md"])
        self.assertEqual(seen["found"][0]["answered"], list(ALL_NINE))
        # Three `.md` files were opened and the `.txt` was not: a scan that
        # counted every file would report a denominator it had not read.
        self.assertEqual(seen["scanned"], 3)

    def test_a_configured_authority_is_not_announced_as_a_stranger(self):
        """The control on the test above. A scanner that announced
        everything would satisfy it while saying nothing."""
        self._write("CONFIGURED.md", _table(MIXED))
        seen = exitcriteria._discover(
            self.scratch, exitcriteria.PRESENT, ["CONFIGURED.md"])
        self.assertEqual(seen["found"], [])
        self.assertEqual(seen["scanned"], 1)

    def test_a_configured_repository_source_is_matched_by_basename(self):
        """`docs/CANARY-01-EXIT-CRITERIA-AUDIT-2026-10-15.md` is configured
        with a path, and a file of that name beside the ops authorities is
        the same document rather than a stranger."""
        self._write("CANARY-01-EXIT-CRITERIA-AUDIT-2026-10-15.md",
                    _table(MIXED))
        seen = exitcriteria._discover(
            self.scratch, exitcriteria.PRESENT,
            ["docs/CANARY-01-EXIT-CRITERIA-AUDIT-2026-10-15.md"])
        self.assertEqual(seen["found"], [])

    def test_a_scan_that_could_not_run_says_the_set_may_be_incomplete(self):
        """UNKNOWN, not zero. "The page could not look" and "nothing is
        there" are different sentences and only one of them is a reassurance.
        """
        for state in (exitcriteria.UNCONFIGURED, exitcriteria.ABSENT):
            seen = exitcriteria._discover(None, state, ["CONFIGURED.md"])
            self.assertTrue(seen["blind"], state)
            self.assertEqual(seen["found"], [], state)
            self.assertEqual(seen["state"], state)

    def test_discovery_changes_no_verdict(self):
        """ANNOUNCE, NEVER REGISTER.

        The same scan that finds the new authority finds `LANE-webapp.md`,
        whose prose about these criteria parses as a verdict block. A page
        that promoted what it found would become an authority on itself,
        which is what section 6 of this task forbids. So the rows assembled
        from the configured chain must be identical whether or not a stranger
        is sitting on disk beside it.
        """
        sources = [_source("a.md", MIXED, 1)]
        before = {number: row["verdict"]
                  for number, row in _rows(sources).items()}
        self._write("STRANGER.md", _table(ALL_MET))
        seen = exitcriteria._discover(
            self.scratch, exitcriteria.PRESENT, ["a.md"])
        self.assertEqual([item["name"] for item in seen["found"]],
                         ["STRANGER.md"])
        after = {number: row["verdict"]
                 for number, row in _rows(sources).items()}
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# The conjunction.


class TheConjunctionIsNotAScore(unittest.TestCase):
    """One answer over all nine, with UNKNOWN dominating.

    The five branches below are the same five
    `EXIT-NINE-AT-ONCE-2026-10-16.md`'s own C3 control pins, reproduced
    because that document's run exits **2** and `exit 2` means the
    conjunction was not established - which must not render as nine
    independent rows with no overall verdict.
    """

    def _rows_of(self, verdicts):
        return [{"number": number, "verdict": verdicts[number]}
                for number in ALL_NINE]

    def test_nine_met_is_met(self):
        verdict, _why = exitcriteria.conjunction_of(self._rows_of(ALL_MET))
        self.assertEqual(verdict, exitcriteria.MET)

    def test_eight_met_and_one_not_met_is_not_met(self):
        verdicts = dict(ALL_MET)
        verdicts[4] = exitcriteria.NOT_MET
        verdict, why = exitcriteria.conjunction_of(self._rows_of(verdicts))
        self.assertEqual(verdict, exitcriteria.NOT_MET)
        self.assertIn("4", why)

    def test_eight_met_and_one_unknown_is_unknown(self):
        verdicts = dict(ALL_MET)
        verdicts[4] = exitcriteria.UNKNOWN
        verdict, why = exitcriteria.conjunction_of(self._rows_of(verdicts))
        self.assertEqual(verdict, exitcriteria.UNKNOWN)
        self.assertIn("UNKNOWN never becomes PASS", why)

    def test_one_unknown_dominates_one_not_met(self):
        """Not outvoted and not averaged. An UNKNOWN beside a NOT MET is
        still UNKNOWN, because the estate does not know whether the rest is
        true."""
        verdicts = dict(ALL_MET)
        verdicts[4] = exitcriteria.UNKNOWN
        verdicts[5] = exitcriteria.NOT_MET
        verdict, why = exitcriteria.conjunction_of(self._rows_of(verdicts))
        self.assertEqual(verdict, exitcriteria.UNKNOWN)
        self.assertIn("NOT MET as well", why)

    def test_a_withdrawn_or_stale_row_is_not_established_either(self):
        for state in (exitcriteria.WITHDRAWN, exitcriteria.STALE):
            verdicts = dict(ALL_MET)
            verdicts[9] = state
            verdict, _why = exitcriteria.conjunction_of(
                self._rows_of(verdicts))
            self.assertEqual(verdict, exitcriteria.UNKNOWN, state)

    def test_a_partial_set_has_no_conjunction(self):
        verdict, why = exitcriteria.conjunction_of(
            self._rows_of(ALL_MET)[:8])
        self.assertEqual(verdict, exitcriteria.UNKNOWN)
        self.assertIn("the SET is wrong", why)

    def test_an_incomplete_authority_set_cannot_assert_met(self):
        """The one direction incompleteness moves the conjunction.

        A page that has just said it may not have opened every authority has
        no standing to settle what those authorities would settle. It can
        still report a NOT MET - one refusal it DID read is enough to say the
        canary does not go, and a file nobody read cannot undo it.
        """
        verdict, why = exitcriteria.conjunction_of(
            self._rows_of(ALL_MET), complete=False)
        self.assertEqual(verdict, exitcriteria.UNKNOWN)
        self.assertIn("may be incomplete", why)
        verdicts = dict(ALL_MET)
        verdicts[4] = exitcriteria.NOT_MET
        verdict, _why = exitcriteria.conjunction_of(
            self._rows_of(verdicts), complete=False)
        self.assertEqual(verdict, exitcriteria.NOT_MET)


# ---------------------------------------------------------------------------
# What the rendered page says.


class TheRenderedPageSaysIt(ASource, unittest.TestCase):
    """Computed correctly is not rendered. This repository's named defect.

    AGAINST A TEMPORARY ESTATE, NOT THE REAL ONE. Both real authorities are
    appended to while this suite runs - `LANE-pilotcaps.md`'s modification
    time moved twice during one task - so a render test bound to them asserts
    on a file another lane is writing. The fixtures below reproduce the SHAPE
    of 2026-10-16 instead: a designated authority that answers three
    criteria, a second one that answers all nine and disagrees on criterion
    9, and a stranger the configuration does not name.
    """

    def setUp(self):
        super().setUp()
        self.write(exitcriteria.DESIGNATED,
                   "## A PARTIAL RE-AUDIT BY TASK 0210 - 2026-10-16" + chr(10)
                   + chr(10)
                   + "| # | criterion | verdict |" + chr(10)
                   + "|---|---|---|" + chr(10)
                   + "| 3 | three | **NOT MET** |" + chr(10)
                   + "| 5 | five | **NOT MET** |" + chr(10)
                   + "| 9 | nine | ~~MET at e84108f5d~~ SUPERSEDED |" + chr(10))
        nine = dict(MIXED)
        nine[3] = exitcriteria.NOT_MET
        nine[5] = exitcriteria.NOT_MET
        nine[9] = exitcriteria.NOT_MET
        self.write(exitcriteria.AT_ONCE, _table(nine, "0. THE NINE"))
        self.write("A-STRANGER-2026-10-16.md", _table(MIXED))
        self.data = api.exit_criteria(now=NOW)
        self.html = pages.exit_criteria(self.data)

    def test_the_contested_criterion_names_both_files_in_the_html(self):
        """The rule, end to end, in the bytes a reader sees.

        Criterion 9: the designated authority struck a MET and recorded
        SUPERSEDED, the second authority records NOT MET. Two authorities,
        two verdicts, so the cell is UNKNOWN / CONTESTED and the page names
        both files rather than quoting the higher-ranked one.
        """
        nine = {row["number"]: row for row in self.data["rows"]}[9]
        self.assertEqual(nine["verdict"], exitcriteria.UNKNOWN)
        self.assertTrue(nine["contested"])
        self.assertIn("UNKNOWN / CONTESTED", self.html)
        self.assertIn("TWO AUTHORITIES DISAGREE", self.html)
        self.assertIn(exitcriteria.DESIGNATED, self.html)
        self.assertIn(exitcriteria.AT_ONCE, self.html)

    def test_the_stranger_makes_the_page_say_its_set_may_be_incomplete(self):
        self.assertTrue(self.data["set_may_be_incomplete"])
        self.assertEqual([item["name"] for item in self.data["discovered"]],
                         ["A-STRANGER-2026-10-16.md"])
        self.assertIn("authority set may be incomplete", self.html)
        self.assertIn("A-STRANGER-2026-10-16.md", self.html)

    def test_a_criterion_only_the_second_authority_answers_is_marked(self):
        rows = {row["number"]: row for row in self.data["rows"]}
        self.assertEqual(rows[4]["verdict"], exitcriteria.NOT_MET)
        self.assertTrue(rows[4]["off_designated"])
        self.assertIn("not the designated authority", self.html)

    def test_the_conjunction_is_unknown_on_this_shape(self):
        """Nine rows with no overall verdict is the rendering that loses the
        `exit 2`, so the page carries one - and on a contested criterion the
        only honest one is UNKNOWN."""
        self.assertEqual(self.data["conjunction"], exitcriteria.UNKNOWN)
        self.assertIn("UNKNOWN", self.data["headline"])

    def test_the_headline_is_the_conjunction_and_not_a_fraction(self):
        self.assertIn(self.data["conjunction_label"], self.data["headline"])
        self.assertIn("conjunction", self.data["headline"])
        self.assertNotIn("of 9 are MET", self.data["headline"])

    def test_the_authority_set_is_printed_by_path(self):
        self.assertEqual(len(self.data["authority_set"]),
                         len(exitcriteria.SOURCES))
        for item in self.data["authority_set"]:
            if item["located"]:
                self.assertIn(os.path.basename(item["name"]),
                              item["located"])
                self.assertIn(item["located"], self.html)

    def test_no_absolute_path_is_printed_for_an_authority_it_could_read(self):
        """TASK 0090's rule, kept. An absolute path on a screen is somebody's
        home directory in a screenshot, so the set is printed root-relative
        and only a FAILED read names the full path."""
        for item in self.data["authority_set"]:
            if item["state"] == exitcriteria.PRESENT and item["located"]:
                self.assertFalse(os.path.isabs(item["located"]),
                                 item["located"])

    def test_the_set_notice_appears_above_the_criteria_table(self):
        """"Above the table" is the requirement, and a notice rendered below
        it is read after the totals it qualifies."""
        notice = "The authority set this render used, by path"
        self.assertIn(notice, self.html)
        self.assertLess(self.html.index(notice),
                        self.html.index("Authority - what would prove it"))

    def test_the_page_says_what_it_refuses_to_do(self):
        refusals = " ".join(item["what"] for item in self.data["refused"])
        for claim in ("resolve a disagreement between two authorities",
                      "let a silent designated authority veto another one's "
                      "answer",
                      "register an authority it found on disk",
                      "assert the conjunction over a set it may not have "
                      "read in full"):
            self.assertIn(claim, refusals)

    def test_every_control_runs_on_the_render(self):
        names = {check["name"] for check in self.data["controls"]}
        for control in ("two_agreeing_authorities_render_and_name_both",
                        "two_disagreeing_authorities_render_contested",
                        "an_unregistered_authority_is_announced",
                        "agreeing_authorities_can_still_render_met"):
            self.assertIn(control, names)

    def test_a_failed_control_poisons_every_row(self):
        """The page has no standing to report a pass it cannot demonstrate.

        Broken through the module attribute `report` looks `controls` up on,
        so this exercises the real poisoning path rather than a parallel one.
        """
        real = exitcriteria.controls

        def broken(now=None):
            results = real(now=now)
            for check in results:
                if check["name"] == "two_disagreeing_authorities_render_" \
                                    "contested":
                    check["ok"] = False
            return results

        exitcriteria.controls = broken
        try:
            data = exitcriteria.report(now=NOW)
        finally:
            exitcriteria.controls = real
        self.assertFalse(data["controls_ok"])
        self.assertEqual({row["verdict"] for row in data["rows"]},
                         {exitcriteria.UNKNOWN})
        self.assertEqual(data["conjunction"], exitcriteria.UNKNOWN)


if __name__ == "__main__":                                  # pragma: no cover
    unittest.main()
