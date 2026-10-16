"""A verdict the authority took back, and three states it may not collapse.

WHAT THIS FILE IS FOR. TASK 0090 asked one question about the exit-criteria
page - is it showing a verdict that was withdrawn - and the answer was no by
luck rather than by design. `pilotcaps/0210` moved criterion 9 from MET to
UNKNOWN and recorded it as

    | 9 | ... | ~~**MET at `e84108f5d`**~~ **SUPERSEDED -> UNKNOWN** / ... |

and the reader had no notion of `~~`, so the `MET` inside the strike-through
was harvested as a live verdict. The cell came out UNKNOWN only because three
different verdict words on one row trip the CONTESTED refusal. Remove any two
of them and the same reader returns MET.

THE FOUR DEFECTS MEASURED, each with its own class below:

    D1  the page read the RETAINED FIRST PASS. `EXIT-CRITERIA-2026-10-16.md`
        keeps its second-pass table at line 22 and its first pass at line 456
        under `# APPENDIX - FIRST PASS, RETAINED VERBATIM`, and "the last
        block wins" takes the appendix. The two passes agreeing on all three
        verdicts is the only reason no cell was wrong.
    D2  a struck-through or SUPERSEDED verdict was read as a live one.
    D3  the `as of` was harvested from prose in ANOTHER section - a TASK 0220
        correction dated 2026-10-15 - which put a red STALE badge on the
        freshest authority in the estate.
    D4  no cell said WHICH TASK measured it; there was no STALE state and no
        WITHDRAWN state; a cross-source disagreement was resolved silently by
        rank; and a failed authority read named no path.

THE THREE CONTROLS FROM THE BRIEF, and C3 is the one the others cannot stand
in for:

    C1  a verdict change in the authority MOVES the page - and the proof that
        C1 can fail is here too: with the read frozen, the page serves its
        first answer and `test_a_frozen_read_does_not_move` measures that the
        assertion in C1 would have gone red.
    C2  an undated verdict renders STALE, not the value it carried.
    C3  an authority that parses to zero criteria renders nine UNKNOWN and
        names the path it tried. Without C3 a page that renders whatever it
        happens to find passes C1 and C2 both.

FIXTURES ONLY. Every authority in this file is written into a temporary
directory. Nothing here reads `EXIT-CRITERIA-2026-10-16.md`, `CONTINUITY.md`
or any real lane file, nothing writes into the ops estate, and the one address
that appears anywhere is `.invalid`.
"""
import datetime
import os
import shutil
import tempfile
import unittest

from src import exitcriteria, lanes
from src.web import api, pages

NOW = datetime.datetime(2026, 10, 16, 3, 0, 0)

#: Criterion 9's row as `pilotcaps/0210` actually wrote it, verbatim in shape.
#: Three verdict words, one of them struck through, one withdrawal marker.
THE_REAL_ROW = (
    "| 9 | a kill switch the operator can operate alone, named and tested "
    "| `src/haltfile.py` + seven test modules "
    "| ~~**MET at `e84108f5d`**~~ **SUPERSEDED -> UNKNOWN** "
    "/ **NOT MET at T1** |")


def table(rows, heading="## 0. THE TABLE - SECOND PASS", stamp="2026-10-16",
          task="TASK 0210"):
    """A pipe table of verdicts, with a document that frames it.

    Shaped like the real authority: a title carrying the task, a heading over
    the table, and pipe rows. `rows` maps a criterion number to whatever the
    verdict cell says, verbatim, so a test can plant a strike-through or
    nothing at all.
    """
    out = ["# CANARY-01 - RE-AUDITED"]
    if task:
        out.append("")
        out.append("%s (pilotcaps) ran and recorded the table below." % task)
    out += ["", heading, ""]
    if stamp:
        # INSIDE the table's own section, which is where a block's `as of`
        # may be read from. A date in the front matter is a date about the
        # document and the reader does not take it - that is D3.
        out.append("Measured %s." % stamp)
        out.append("")
    out += ["| # | criterion | verdict |", "|---|---|---|"]
    for number in sorted(rows):
        out.append("| %d | criterion %d | %s |" % (number, number,
                                                   rows[number]))
    return "\n".join(out) + "\n"


def nine(verdict="NOT MET", **override):
    rows = {number: verdict for number in range(1, 10)}
    for key, value in override.items():
        rows[int(key.lstrip("c"))] = value
    return rows


class AnEstate:
    """A temporary ops estate and repository root, thrown away per test."""

    def setUp(self):
        super().setUp()
        self.repo = tempfile.mkdtemp(prefix="rga-0090-repo-")
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.ops = tempfile.mkdtemp(prefix="rga-0090-ops-")
        self.addCleanup(shutil.rmtree, self.ops, ignore_errors=True)
        previous = os.environ.get(lanes.OPS_DIR)
        os.environ[lanes.OPS_DIR] = self.ops
        self.addCleanup(self._restore, previous)

    @staticmethod
    def _restore(previous):
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

    def authority(self, text):
        return self.write(exitcriteria.DESIGNATED, text)

    def report(self, now=None):
        return exitcriteria.report(root=self.repo, now=now or NOW)

    def rows(self, now=None):
        return {row["number"]: row for row in self.report(now)["rows"]}

    def page(self, now=None):
        data = api.exit_criteria(now=now or NOW)
        return pages.exit_criteria(data), data


# --------------------------------------------------------------------------
# D2 and the WITHDRAWN state. The defect the brief was actually about.
# --------------------------------------------------------------------------

class AWithdrawnVerdictIsNotTheValueItHeld(AnEstate, unittest.TestCase):

    def test_a_struck_through_met_renders_withdrawn(self):
        self.authority(table(nine(c9="~~MET~~")))
        self.assertEqual(self.rows()[9]["verdict"], exitcriteria.WITHDRAWN)

    def test_a_struck_through_met_is_never_met(self):
        """The whole point, stated as the thing that must not happen."""
        self.authority(table(nine(c9="~~MET~~")))
        self.assertNotEqual(self.rows()[9]["verdict"], exitcriteria.MET)

    def test_the_word_superseded_withdraws_a_verdict_too(self):
        self.authority(table(nine(c9="MET - SUPERSEDED")))
        self.assertEqual(self.rows()[9]["verdict"], exitcriteria.WITHDRAWN)

    def test_withdrawn_void_and_revoked_are_withdrawals_as_well(self):
        for word in ("WITHDRAWN", "VOID", "REVOKED"):
            with self.subTest(word=word):
                self.authority(table(nine(c9="MET - %s" % word)))
                self.assertEqual(self.rows()[9]["verdict"],
                                 exitcriteria.WITHDRAWN, word)

    def test_the_value_it_held_is_reported_as_history(self):
        self.authority(table(nine(c9="~~MET~~ SUPERSEDED")))
        row = self.rows()[9]
        self.assertEqual(row["recorded"], "MET")
        self.assertEqual(row["struck"], ["MET"])
        self.assertEqual(row["withdrawn"], ["SUPERSEDED"])

    def test_the_real_criterion_nine_row_renders_withdrawn(self):
        """`pilotcaps/0210`'s row verbatim, as a fixture.

        Three verdict words and a strike-through. It came out UNKNOWN before
        TASK 0090 - the right colour for the wrong reason, which reads to an
        operator as "nobody measured this" when the document says somebody
        measured it, wrote MET, and took it back.
        """
        self.authority(table({3: "NOT MET", 5: "NOT MET"})
                       + THE_REAL_ROW + "\n")
        row = self.rows()[9]
        self.assertEqual(row["verdict"], exitcriteria.WITHDRAWN)
        self.assertEqual(row["recorded"], "MET")
        self.assertIn("SUPERSEDED", row["withdrawn"])

    def test_a_struck_value_beside_one_live_verdict_is_a_replacement(self):
        """`~~MET~~ SUPERSEDED -> NOT MET` renders NOT MET, with MET history.

        FOUND BY THE AUTHORITY MOVING MID-TASK. At 03:13:49 on 2026-10-16
        pilotcaps' TASK 0225 rewrote criterion 9 to
        `**NOT MET - the two trees disagree** ... ~~UNKNOWN at e84108f5d~~`.
        The verdict there is NOT MET and what is struck is the UNKNOWN that
        came before, so rendering the row WITHDRAWN replaced a CURRENT
        refusal with a statement about a dead one. The struck value still
        travels with the row, so nothing is resurrected either way.
        """
        self.authority(table(nine(c9="~~MET~~ SUPERSEDED -> NOT MET")))
        row = self.rows()[9]
        self.assertEqual(row["verdict"], exitcriteria.NOT_MET)
        self.assertEqual(row["struck"], ["MET"])
        self.assertIn("replaced an earlier verdict", row["reason"])

    def test_the_real_row_after_task_0225_renders_its_live_verdict(self):
        """That row's shape, as a fixture, with the live verdict first."""
        self.authority(table({3: "NOT MET", 5: "NOT MET"})
                       + "| 9 | criterion 9 | **NOT MET - the two trees "
                         "disagree** ~~UNKNOWN at `e84108f5d`~~ |\n")
        row = self.rows()[9]
        self.assertEqual(row["verdict"], exitcriteria.NOT_MET)
        self.assertEqual(row["struck"], ["UNKNOWN"])

    def test_a_withdrawal_word_with_no_strike_through_withdraws_the_row(self):
        """`MET - SUPERSEDED` names no second value, so the thing superseded
        is the MET on the row. A reader that treated the MET as the live
        verdict because a withdrawal word sat beside it would be the exact
        failure this state exists to prevent - and that was the first
        version of this code."""
        self.authority(table(nine(c9="MET - SUPERSEDED")))
        row = self.rows()[9]
        self.assertEqual(row["verdict"], exitcriteria.WITHDRAWN)
        self.assertEqual(row["recorded"], "MET")

    def test_two_live_verdicts_beside_a_strike_through_is_withdrawn(self):
        """The appendix row's real shape: `~~MET~~ SUPERSEDED -> UNKNOWN /
        NOT MET at T1`. Two replacements, so none is promoted."""
        self.authority(table(nine(
            c9="~~MET~~ SUPERSEDED -> UNKNOWN / NOT MET at T1")))
        row = self.rows()[9]
        self.assertEqual(row["verdict"], exitcriteria.WITHDRAWN)
        self.assertEqual(row["recorded"], "MET")

    def test_a_struck_value_equal_to_the_live_one_is_withdrawn(self):
        """`~~MET~~ MET` is incoherent and fails closed rather than being
        read as a confirmation."""
        self.authority(table(nine(c9="~~MET~~ MET")))
        self.assertEqual(self.rows()[9]["verdict"], exitcriteria.WITHDRAWN)

    def test_a_replacement_that_reads_met_still_shows_what_it_replaced(self):
        """The one path where a strike-through yields MET - the authority
        deliberately upgrading. It is allowed, because refusing it would mean
        this page can never read a correction; and the withdrawal stays on
        the row, so the change is never invisible."""
        self.authority(table(nine(c9="~~NOT MET~~ SUPERSEDED -> MET")))
        row = self.rows()[9]
        self.assertEqual(row["verdict"], exitcriteria.MET)
        self.assertEqual(row["struck"], ["NOT MET"])
        body, _data = self.page()
        self.assertIn("it used to say", body)

    def test_a_withdrawal_does_not_touch_its_neighbours(self):
        self.authority(table(nine("MET", c9="~~MET~~ SUPERSEDED")))
        rows = self.rows()
        self.assertEqual(rows[9]["verdict"], exitcriteria.WITHDRAWN)
        for number in range(1, 9):
            self.assertEqual(rows[number]["verdict"], exitcriteria.MET,
                             "criterion %d" % number)

    def test_a_table_of_nothing_but_withdrawals_still_parses(self):
        """Nine rows with no LIVE verdict on any of them.

        This was rejected as prose before TASK 0090 - `carrying` counted only
        live tokens, so the block failed the threshold and nine rows came back
        UNKNOWN-because-unparseable. That reads as "nobody wrote this down"
        when the document says the opposite.
        """
        self.authority(table(nine(**{"c%d" % n: "~~MET~~ SUPERSEDED"
                                     for n in range(1, 10)})))
        for row in self.report()["rows"]:
            self.assertEqual(row["verdict"], exitcriteria.WITHDRAWN,
                             "criterion %d" % row["number"])

    def test_a_block_admitted_on_withdrawals_alone_can_never_say_met(self):
        """The direction that makes the looser threshold safe."""
        self.authority(table(nine(**{"c%d" % n: "~~MET~~" for n in
                                     range(1, 10)})))
        verdicts = {row["verdict"] for row in self.report()["rows"]}
        self.assertNotIn(exitcriteria.MET, verdicts)

    def test_withdrawn_is_not_counted_as_met_in_the_tally(self):
        self.authority(table(nine(**{"c%d" % n: "~~MET~~" for n in
                                     range(1, 10)})))
        data = self.report()
        self.assertEqual(data["tally"][exitcriteria.MET], 0)
        self.assertEqual(data["tally"][exitcriteria.WITHDRAWN], 9)
        self.assertFalse(data["all_nine_met"])

    def test_blanking_a_struck_span_cannot_splice_a_new_phrase(self):
        """Deleting `~~` spans instead of blanking them would join the halves
        either side and manufacture a phrase nobody wrote."""
        line = "    9  MET~~ x ~~WITH CAVEAT"
        self.assertEqual(exitcriteria._tokens_on(line), ["MET"])

    def test_a_lowercase_withdrawal_in_prose_is_not_a_withdrawal(self):
        """These documents argue about withdrawals in prose constantly."""
        self.authority(table(nine(
            c9="MET (the earlier reading was withdrawn, see above)")))
        self.assertEqual(self.rows()[9]["verdict"], exitcriteria.MET)


class ThePageSaysWithdrawnAndSaysWhatItWas(AnEstate, unittest.TestCase):

    def test_the_page_renders_the_withdrawn_label(self):
        self.authority(table(nine(c9="~~MET~~ SUPERSEDED")))
        body, _data = self.page()
        self.assertIn("WITHDRAWN", body)

    def test_the_page_says_the_old_value_is_history(self):
        self.authority(table(nine(c9="~~MET~~ SUPERSEDED")))
        body, _data = self.page()
        self.assertIn("it used to say", body)
        self.assertIn("that is history, not the verdict", body)

    def test_every_verdict_the_reader_can_produce_has_a_glossary_entry(self):
        """A label the renderer can show and the glossary cannot explain is a
        word on a safety page with no definition behind it."""
        for verdict in (exitcriteria.MET, exitcriteria.NOT_MET,
                        exitcriteria.UNKNOWN, exitcriteria.WITHDRAWN,
                        exitcriteria.STALE):
            self.assertIn(verdict, exitcriteria.VERDICT_TEXT)
            self.assertIn(verdict, pages.EXIT_VERDICT_KIND)


# --------------------------------------------------------------------------
# C2 - an undated verdict renders STALE.
# --------------------------------------------------------------------------

class AnUndatedVerdictIsAMemoryNotAVerdict(AnEstate, unittest.TestCase):

    def undated(self, verdict="MET"):
        """An authority with no date anywhere, read inline.

        Inline because a file on disk always has a modification time, and
        `AS_OF_MTIME` is a weaker answer than a stamp but it IS an answer.
        The state under test is the one where neither exists.
        """
        source = {"key": "fixture", "name": "undated.md", "rank": 1,
                  "where": exitcriteria.LOC_OPS, "kind": "a fixture",
                  "text": table(nine(verdict), stamp=None, task=None)}
        return exitcriteria.report(root=self.repo, now=NOW,
                                   sources=(source,))

    def test_an_undated_met_renders_stale(self):
        rows = {row["number"]: row for row in self.undated("MET")["rows"]}
        self.assertEqual(rows[9]["verdict"], exitcriteria.STALE)

    def test_an_undated_met_is_never_met(self):
        for row in self.undated("MET")["rows"]:
            self.assertNotEqual(row["verdict"], exitcriteria.MET,
                                "criterion %d" % row["number"])

    def test_an_undated_not_met_is_also_stale(self):
        """Both directions, so STALE is about the DATE and not about the
        verdict being inconvenient."""
        rows = {row["number"]: row for row in self.undated("NOT MET")["rows"]}
        self.assertEqual(rows[9]["verdict"], exitcriteria.STALE)

    def test_the_undated_row_still_reports_what_was_recorded(self):
        rows = {row["number"]: row for row in self.undated("MET")["rows"]}
        self.assertEqual(rows[9]["recorded"], "MET")
        self.assertIn("no measurement date", rows[9]["reason"].lower())

    def test_a_dated_verdict_is_not_stale_merely_for_being_old(self):
        """STALE-the-state and `stale`-the-age-flag are different questions.

        A verdict dated and 26 hours old still HAS a verdict; an undated one
        does not. Collapsing the two would turn every verdict in this estate
        STALE within a day and the page would stop meaning anything.
        """
        self.authority(table(nine("MET"), stamp="2026-10-14"))
        row = self.rows()[9]
        self.assertEqual(row["verdict"], exitcriteria.MET)
        self.assertTrue(row["stale"])

    def test_an_undated_verdict_is_stale_however_recent_the_file_is(self):
        """And the control on the page measures the same thing."""
        check = {control["name"]: control
                 for control in exitcriteria.controls(now=NOW)}
        self.assertIn("an_undated_verdict_renders_stale", check)
        self.assertTrue(check["an_undated_verdict_renders_stale"]["ok"])

    def test_the_undated_control_fixture_says_met_nine_times(self):
        """A control whose fixture said NOT MET would pass on a reader that
        answers NOT MET to everything, which is the wrong blindness to rule
        out here."""
        self.assertEqual(exitcriteria.UNDATED_FIXTURE.count("MET"), 9)
        self.assertNotIn("NOT MET", exitcriteria.UNDATED_FIXTURE)
        self.assertIsNone(exitcriteria._DATE.search(
            exitcriteria.UNDATED_FIXTURE))


# --------------------------------------------------------------------------
# C3 - an authority that parses to nothing is nine UNKNOWN, named.
# --------------------------------------------------------------------------

class ZeroParsedCriteriaIsNotNinePassingCriteria(AnEstate, unittest.TestCase):

    #: Valid markdown, prose about the nine, and no criteria table. The
    #: shape the brief names: a page that renders whatever it finds passes
    #: C1 and C2 and fails only this.
    NO_TABLE = """# EXIT CRITERIA - 2026-10-16

The re-audit did not finish. There is no table in this file yet, and nothing
below is a verdict.

## What was attempted

The three criteria were to be re-measured at two SHAs. That work is not done.
"""

    def test_an_authority_with_no_table_renders_nine_unknown(self):
        self.authority(self.NO_TABLE)
        rows = self.report()["rows"]
        self.assertEqual(len(rows), 9)
        for row in rows:
            self.assertEqual(row["verdict"], exitcriteria.UNKNOWN,
                             "criterion %d" % row["number"])

    def test_it_is_not_an_empty_green_page(self):
        self.authority(self.NO_TABLE)
        data = self.report()
        self.assertEqual(data["tally"][exitcriteria.MET], 0)
        self.assertFalse(data["all_nine_met"])

    def test_the_state_is_no_block_and_not_absent(self):
        """Read in full and understood as holding no verdict. A different
        answer from "the file is not there", and the one most easily mistaken
        for a page with nothing to say."""
        self.authority(self.NO_TABLE)
        source = {item["name"]: item for item in self.report()["sources"]}
        self.assertEqual(source[exitcriteria.DESIGNATED]["state"],
                         exitcriteria.NO_BLOCK)

    def test_the_page_names_the_absolute_path_it_tried(self):
        self.authority(self.NO_TABLE)
        body, data = self.page()
        unread = {item["name"]: item for item in data["unread"]}
        self.assertIn(exitcriteria.DESIGNATED, unread)
        self.assertEqual(unread[exitcriteria.DESIGNATED]["path"],
                         os.path.join(self.ops, exitcriteria.DESIGNATED))
        self.assertIn(pages.esc(os.path.join(self.ops,
                                             exitcriteria.DESIGNATED)), body)
        self.assertIn("authority not read", body)

    def test_an_absent_authority_is_named_by_path_as_well(self):
        body, data = self.page()
        paths = [item["path"] for item in data["unread"]]
        self.assertIn(os.path.join(self.ops, exitcriteria.DESIGNATED), paths)
        for path in paths:
            self.assertIn(pages.esc(path), body)

    def test_an_unreadable_authority_is_named_by_path_as_well(self):
        """A directory where a file belongs: not absent, not empty."""
        os.makedirs(os.path.join(self.ops, exitcriteria.DESIGNATED))
        _body, data = self.page()
        unread = {item["name"]: item for item in data["unread"]}
        self.assertEqual(unread[exitcriteria.DESIGNATED]["state"],
                         exitcriteria.UNREADABLE)
        self.assertTrue(unread[exitcriteria.DESIGNATED]["path"])

    def test_zero_parsed_criteria_reports_zero_rather_than_silence(self):
        self.authority(self.NO_TABLE)
        source = {item["name"]: item for item in self.report()["sources"]}
        self.assertEqual(source[exitcriteria.DESIGNATED]["answered"], [])


# --------------------------------------------------------------------------
# C1 - the cells are derived at render time, not a snapshot.
# --------------------------------------------------------------------------

class TheCellsAreDerivedAndNotASnapshot(AnEstate, unittest.TestCase):

    def test_a_verdict_change_in_the_authority_moves_the_page(self):
        """C1. Flip one criterion and the cell must follow."""
        self.authority(table(nine(c9="MET")))
        self.assertEqual(self.rows()[9]["verdict"], exitcriteria.MET)
        self.authority(table(nine(c9="UNKNOWN")))
        self.assertEqual(self.rows()[9]["verdict"], exitcriteria.UNKNOWN)

    def test_a_frozen_read_does_not_move(self):
        """C1 CAN FAIL, and this is the measurement of it.

        The read is frozen - every `read_source` call after the first returns
        the first answer - which is exactly what a page serving a snapshot
        does. The assertion C1 makes then goes red, which is what proves C1
        is watching the read and not the fixture.
        """
        self.authority(table(nine(c9="MET")))
        real = exitcriteria.read_source
        cache = {}

        def frozen(path):
            if path not in cache:
                cache[path] = real(path)
            return cache[path]

        exitcriteria.read_source = frozen
        self.addCleanup(setattr, exitcriteria, "read_source", real)
        self.assertEqual(self.rows()[9]["verdict"], exitcriteria.MET)
        self.authority(table(nine(c9="UNKNOWN")))
        self.assertEqual(self.rows()[9]["verdict"], exitcriteria.MET,
                         "the frozen read should serve its snapshot, or this "
                         "control is not measuring what it claims")

    def test_the_change_moves_the_rendered_html_too(self):
        """Derived in the reader is not the same claim as derived on the
        page - the page could cache its own markup."""
        self.authority(table(nine(c9="~~MET~~ SUPERSEDED")))
        before, _ = self.page()
        self.assertIn("WITHDRAWN", before)
        self.authority(table(nine(c9="NOT MET")))
        after, _ = self.page()
        # "it used to say" and not the word WITHDRAWN: the glossary and the
        # refusals name every state on every render, so the label alone is
        # always present and would make this assertion vacuous.
        self.assertIn("it used to say", before)
        self.assertNotIn("it used to say", after)

    def test_an_authority_that_did_not_exist_at_build_time_is_read(self):
        """The designated authority was written AFTER the page was. A
        snapshot could not answer with it at all."""
        rows = self.rows()
        self.assertTrue(all(row["source_name"] is None
                            for row in rows.values()))
        self.authority(table(nine(c9="NOT MET")))
        self.assertEqual(self.rows()[9]["source_name"],
                         exitcriteria.DESIGNATED)

    def test_no_verdict_is_stored_in_the_module(self):
        """A constant holding one of the nine verdicts is a snapshot however
        the page reads it."""
        for criterion in exitcriteria.CRITERIA:
            self.assertNotIn("verdict", criterion)


# --------------------------------------------------------------------------
# D1 - a block a heading calls history is not the current entry.
# --------------------------------------------------------------------------

class ARetainedAppendixIsNotTheNewestEntry(AnEstate, unittest.TestCase):

    def both_passes(self, second, first):
        """The real file's shape: the live table first, the appendix after."""
        return (table(nine(c9=second))
                + "\n# APPENDIX - FIRST PASS, 01:11, RETAINED VERBATIM\n"
                + "\n## 0. THE TABLE (FIRST PASS)\n\n"
                + "| # | criterion | verdict |\n|---|---|---|\n"
                + "| 9 | criterion 9 | %s |\n" % first)

    def test_the_second_pass_answers_and_not_the_appendix(self):
        self.authority(self.both_passes(second="NOT MET", first="MET"))
        self.assertEqual(self.rows()[9]["verdict"], exitcriteria.NOT_MET)

    def test_the_appendix_is_not_allowed_to_resurrect_a_met(self):
        """The failure this is actually guarding. On the real file the two
        passes agree, so nothing was visibly wrong - the appendix exists
        BECAUSE a verdict moved, and reading it reads the old side."""
        self.authority(self.both_passes(second="UNKNOWN", first="MET"))
        self.assertNotEqual(self.rows()[9]["verdict"], exitcriteria.MET)

    def test_the_skipped_block_is_counted_and_not_dropped(self):
        self.authority(self.both_passes(second="NOT MET", first="MET"))
        self.assertEqual(self.report()["retained_blocks"], 1)

    def test_the_page_says_a_block_was_skipped_as_history(self):
        self.authority(self.both_passes(second="NOT MET", first="MET"))
        body, _data = self.page()
        self.assertIn("calls them history", body)

    def test_every_retained_word_is_recognised(self):
        for word in ("APPENDIX", "FIRST PASS", "SUPERSEDED", "RETAINED",
                     "HISTORICAL", "ARCHIVED", "OBSOLETE"):
            with self.subTest(word=word):
                self.assertTrue(
                    exitcriteria._retained_by([(1, "# %s" % word, 0)]), word)

    def test_an_ordinary_heading_is_not_retained(self):
        self.assertIsNone(
            exitcriteria._retained_by([(1, "# THE NINE, RE-MEASURED", 0)]))

    def test_a_lowercase_appendix_in_a_heading_is_not_a_marker(self):
        """Headings in these files are uppercase by convention, and a
        case-insensitive marker would file live sections as history - which
        fails in the direction of hiding a verdict."""
        self.assertIsNone(
            exitcriteria._retained_by([(1, "# the appendix question", 0)]))

    def test_a_document_with_nothing_but_an_appendix_is_still_read(self):
        """Refusing it outright would turn a readable authority into nine
        UNKNOWNs. It is read, and the page says it is reading an appendix."""
        self.authority("# KEPT FOR THE RECORD\n\n"
                       + "| # | criterion | verdict |\n|---|---|---|\n"
                       + "| 9 | criterion 9 | NOT MET |\n")
        data = self.report()
        rows = {row["number"]: row for row in data["rows"]}
        self.assertEqual(rows[9]["verdict"], exitcriteria.NOT_MET)
        self.assertIn(exitcriteria.DESIGNATED, data["retained_used"])
        body = pages.exit_criteria(api.exit_criteria(now=NOW))
        self.assertIn("reading an appendix", body)

    def test_an_outer_appendix_governs_a_subheading_beneath_it(self):
        trail = [(1, "# APPENDIX - FIRST PASS", 10),
                 (2, "## 0. THE TABLE", 20)]
        self.assertEqual(exitcriteria._retained_by(trail),
                         "# APPENDIX - FIRST PASS")

    def test_a_later_top_level_heading_ends_the_appendix(self):
        """A `#` heading after the appendix is not inside it, so its blocks
        are live again. Without this the rest of a file would be history."""
        text = ("# KEPT FOR THE RECORD\n\n"
                "| # | criterion | verdict |\n|---|---|---|\n"
                "| 9 | criterion 9 | MET |\n"
                "\n# THE CURRENT TABLE - 2026-10-16\n\n"
                "| # | criterion | verdict |\n|---|---|---|\n"
                "| 9 | criterion 9 | NOT MET |\n")
        self.authority(text)
        self.assertEqual(self.rows()[9]["verdict"], exitcriteria.NOT_MET)
        self.assertEqual(self.report()["retained_blocks"], 1)


# --------------------------------------------------------------------------
# D3 and D4 - when it was measured, and by which task.
# --------------------------------------------------------------------------

class EveryCellSaysWhenAndByWhom(AnEstate, unittest.TestCase):

    def test_a_date_in_another_section_is_not_this_blocks_as_of(self):
        """D3, as a fixture of the real shape.

        The prose under the appendix heading carries a 2026-10-15 correction.
        Walking up without a limit harvested it, and that is what put a red
        STALE badge on the newest authority in the estate.
        """
        text = (table(nine(c9="NOT MET"), stamp=None, task=None)
                + "\n# APPENDIX - RETAINED\n\n"
                + "A correction dated 2026-10-15 about another document.\n")
        path = self.authority(text)
        row = self.rows()[9]
        self.assertNotEqual(row["as_of"], "2026-10-15")
        # Nothing in its own section dates it, so the file's own clock is the
        # weaker answer it falls back to - labelled as such.
        self.assertEqual(row["as_of_kind"], exitcriteria.AS_OF_MTIME)
        self.assertTrue(os.path.exists(path))

    def test_a_stamp_in_the_blocks_own_section_is_used(self):
        self.authority(table(nine(c9="NOT MET"),
                             heading="## THE TABLE - 2026-10-16"))
        self.assertEqual(self.rows()[9]["as_of"], "2026-10-16")
        self.assertEqual(self.rows()[9]["as_of_kind"],
                         exitcriteria.AS_OF_STAMP)

    def test_an_enclosing_headings_date_is_used_when_the_section_has_none(self):
        """The lane-file shape, and the reason the scope is not just the
        nearest heading: `LANE-pilotcaps.md`'s verdict table sits seven
        subheadings below the entry heading that carries the date.
        """
        text = ("# 2026-10-16 - TASK 0200 (pilotcaps): the entry\n\n"
                "## A SUBHEADING WITH NO DATE\n\n"
                "## THE NINE, RE-MEASURED\n\n"
                "| # | criterion | verdict |\n|---|---|---|\n"
                "| 9 | criterion 9 | NOT MET |\n")
        self.authority(text)
        row = self.rows()[9]
        self.assertEqual(row["as_of"], "2026-10-16")
        self.assertEqual(row["task"], "TASK 0200")
        self.assertEqual(row["task_kind"], exitcriteria.TASK_SECTION)

    def test_prose_under_a_sibling_heading_is_not_in_scope(self):
        """A heading is a statement about everything beneath it. The
        paragraphs under a SIBLING heading are not."""
        text = ("# THE ENTRY\n\n"
                "## AN EARLIER SECTION\n\n"
                "Measured 2026-10-11, and that date belongs to this section.\n"
                "\n## THE NINE\n\n"
                "| # | criterion | verdict |\n|---|---|---|\n"
                "| 9 | criterion 9 | NOT MET |\n")
        self.authority(text)
        self.assertNotEqual(self.rows()[9]["as_of"], "2026-10-11")

    def test_the_task_is_read_from_the_section_when_it_names_one(self):
        self.authority(table(nine(c9="NOT MET"),
                             heading="## TASK 0210 RE-MEASURED - 2026-10-16"))
        row = self.rows()[9]
        self.assertEqual(row["task"], "TASK 0210")
        self.assertEqual(row["task_kind"], exitcriteria.TASK_SECTION)

    def test_a_task_named_only_in_the_front_matter_is_a_weaker_claim(self):
        self.authority(table(nine(c9="NOT MET"), task="TASK 0210"))
        row = self.rows()[9]
        self.assertEqual(row["task"], "TASK 0210")
        self.assertEqual(row["task_kind"], exitcriteria.TASK_DOCUMENT)

    def test_the_page_says_which_claim_it_is(self):
        self.authority(table(nine(c9="NOT MET"), task="TASK 0210"))
        body, _data = self.page()
        self.assertIn("TASK 0210", body)
        self.assertIn("named by the document as a whole", body)

    def test_an_authority_naming_no_task_says_so_rather_than_guessing(self):
        self.authority(table(nine(c9="NOT MET"), task=None,
                             heading="## THE TABLE - 2026-10-16"))
        row = self.rows()[9]
        self.assertIsNone(row["task"])
        self.assertEqual(row["task_kind"], exitcriteria.TASK_NONE)
        body, _data = self.page()
        self.assertIn("the authority names no task for this verdict", body)

    def test_a_two_digit_number_is_not_a_task_id(self):
        """`TASK 90` would be harvested out of a time or a count."""
        self.assertIsNone(exitcriteria._TASK.search("TASK 90"))
        self.assertTrue(exitcriteria._TASK.search("TASK 0090"))

    def test_every_rendered_cell_carries_a_date_and_an_author_or_says_not(self):
        """The brief's requirement, as one assertion over all nine rows."""
        self.authority(table(nine("NOT MET"), task="TASK 0210"))
        for row in self.report()["rows"]:
            with self.subTest(criterion=row["number"]):
                self.assertIn("as_of", row)
                self.assertIn("task", row)
                self.assertIn(row["as_of_kind"],
                              (exitcriteria.AS_OF_STAMP,
                               exitcriteria.AS_OF_MTIME,
                               exitcriteria.AS_OF_NONE))


# --------------------------------------------------------------------------
# D4 - two authorities disagreeing are shown, not resolved.
# --------------------------------------------------------------------------

class TwoAuthoritiesDisagreeingAreBothShown(AnEstate, unittest.TestCase):

    def disagree(self, designated, lane):
        """Two authorities, DIFFERENT dates, so "which is newer" has an
        answer that is not a tie."""
        self.authority(table(nine(c9=designated), stamp="2026-10-15"))
        self.write(exitcriteria.LANE_REPORT,
                   table(nine(c9=lane), heading="## THE NINE",
                         stamp="2026-10-16", task="TASK 0200"))
        return self.rows()[9]

    def test_both_readings_are_reported(self):
        row = self.disagree(designated="UNKNOWN", lane="NOT MET")
        self.assertEqual([item["verdict_label"]
                          for item in row["disagreement"]],
                         ["UNKNOWN", "NOT MET"])

    def test_the_authority_by_rank_is_marked_as_such(self):
        row = self.disagree(designated="UNKNOWN", lane="NOT MET")
        self.assertTrue(row["disagreement"][0]["authoritative"])
        self.assertFalse(row["disagreement"][1]["authoritative"])

    def test_which_is_newer_is_shown_and_is_a_separate_question(self):
        row = self.disagree(designated="UNKNOWN", lane="NOT MET")
        newer = [item for item in row["disagreement"] if item["newer"]]
        self.assertEqual(len(newer), 1)
        self.assertEqual(newer[0]["source_name"], exitcriteria.LANE_REPORT)
        self.assertTrue(newer[0]["as_of"])

    def test_a_disputed_met_does_not_render_met(self):
        """"Do not pick" cannot mean "take the top-ranked MET and mention the
        dispute underneath". MET is the one value here that licenses a send.
        """
        row = self.disagree(designated="MET", lane="NOT MET")
        self.assertEqual(row["verdict"], exitcriteria.UNKNOWN)
        self.assertIn("CONTESTED ACROSS AUTHORITIES", row["reason"])

    def test_agreement_leaves_no_disagreement_to_show(self):
        row = self.disagree(designated="NOT MET", lane="NOT MET")
        self.assertEqual(row["disagreement"], [])

    def test_the_page_shows_both_and_says_it_is_not_choosing(self):
        self.disagree(designated="UNKNOWN", lane="NOT MET")
        body, data = self.page()
        self.assertEqual(data["disagreements"], [9])
        self.assertIn("TWO AUTHORITIES DISAGREE", body)
        self.assertIn("does not choose between", body)

    def test_an_undated_source_is_neither_newer_nor_older(self):
        """Said explicitly rather than sorted to the bottom."""
        found = [({"name": "a", "rank": 1, "as_of": "2026-10-16",
                   "as_of_kind": exitcriteria.AS_OF_STAMP, "task": None},
                  {"verdict": exitcriteria.MET, "recorded": "MET"}),
                 ({"name": "b", "rank": 2, "as_of": None,
                   "as_of_kind": exitcriteria.AS_OF_NONE, "task": None},
                  {"verdict": exitcriteria.NOT_MET, "recorded": "NOT MET"})]
        out = exitcriteria._disagreement(found)
        self.assertTrue(out[0]["newer"])
        self.assertFalse(out[1]["newer"])
        self.assertTrue(out[1]["undated"])


# --------------------------------------------------------------------------
# The refusals the page publishes have to be true of the code.
# --------------------------------------------------------------------------

class ThePageDoesWhatItSaysItRefusesToDo(AnEstate, unittest.TestCase):

    def test_the_refusals_name_the_three_new_ones(self):
        said = " ".join(what for what, _why
                        in api.EXIT_CRITERIA_REFUSALS).lower()
        self.assertIn("took back", said)
        self.assertIn("measurement date", said)
        self.assertIn("history", said)

    def test_a_failing_control_still_poisons_every_row(self):
        """Including the two new states. A reader that cannot demonstrate it
        works has no standing to report anything."""
        self.authority(table(nine(c9="~~MET~~ SUPERSEDED")))
        real = exitcriteria.controls

        def broken(now=None):
            out = real(now=now)
            out[0] = dict(out[0], ok=False)
            return out

        exitcriteria.controls = broken
        self.addCleanup(setattr, exitcriteria, "controls", real)
        data = self.report()
        self.assertFalse(data["controls_ok"])
        for row in data["rows"]:
            self.assertEqual(row["verdict"], exitcriteria.UNKNOWN,
                             "criterion %d" % row["number"])

    def test_it_writes_nothing_into_the_estate(self):
        self.authority(table(nine(c9="NOT MET")))
        before = sorted(os.listdir(self.ops))
        self.report()
        self.page()
        self.assertEqual(sorted(os.listdir(self.ops)), before)

    def test_every_fixture_this_module_builds_is_synthetic(self):
        """This module's own boundary, measured on the fixtures rather than
        promised in prose - and on the fixtures rather than on this file's
        own source text, which is the trap the first version of this test
        fell into: a test that greps itself for a forbidden string contains
        that string, so it can never pass.
        """
        built = (table(nine("MET")) + THE_REAL_ROW
                 + exitcriteria.UNDATED_FIXTURE
                 + exitcriteria.WITHDRAWN_FIXTURE
                 + exitcriteria.UNPARSEABLE_FIXTURE
                 + exitcriteria._planted_fixture())
        for at in [part for part in built.split() if "@" in part]:
            self.assertTrue(at.endswith(".invalid"),
                            "%s is not a synthetic address" % at)
        self.assertNotIn("resonategroup.co", built)


if __name__ == "__main__":
    unittest.main()
