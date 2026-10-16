#!/usr/bin/env python3
"""TASK-0210. A `path:line` citation is a claim, and claims get checked.

## THE DEFECT, THREE TIMES IN ONE NIGHT, IN ONE LANE

1. `CANARY-01-PREFLIGHT-2026-10-16.md` named a SHA for a run made from a tree
   where the instrument was uncommitted. Fixed by `preflight.provenance()`
   and its ABSENT / MODIFIED / CONFIRMED verdict.
2. `assessment["at"]` had a reader and no producer, so every report said
   *"Measured see the lane entry on SHA ..."*.
3. `docs/NINE-HUNDRED-SENDS-ONE-CONFIRMED-TOUCH-2026-10-16.md` cited
   `scripts/bison_watch_loop.py` line 643 where the symbol is at 641, and
   `src/leadobserve.py` line 789 where it is at 790 - on the four citations
   carrying that document's one load-bearing claim.

`provenance()` verifies the SHA. **Nothing verified a line number**, and the
line number is what a reader opens the file to.

## WHAT IS PINNED HERE

* the six states, each observed with WHICH GUARD answered - because three
  different facts come out as `BROKEN` and a control that watched only the
  verdict could not tell them apart. Measured: it could not, and the
  "missing file read as empty" blinding reddened nothing until the `because`
  codes existed
* four blindings, each reddening exactly the control it should and no other
* `UNVERIFIABLE` is not a pass and is counted out loud
* an empty result is a FAILURE, because a checker that finds nothing always
  reports clean
* the line-ending trap: a CRLF working tree and an LF blob must number lines
  identically, and that is asserted rather than assumed
"""
import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SCRIPT = os.path.join(ROOT, "scripts", "citecheck.py")


def load_checker():
    spec = importlib.util.spec_from_file_location("_citecheck", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cc = load_checker()


class TheSixControlsHold(unittest.TestCase):

    def test_every_planted_control_holds(self):
        rows = cc._fixture_states()
        self.assertEqual(6, len(rows))
        for row in rows:
            with self.subTest(control=row["control"]):
                self.assertTrue(row["ok"], "%s: expected %r observed %r"
                                % (row["control"], row["expected"],
                                   row["observed"]))

    def test_each_control_observes_which_guard_answered(self):
        """NOT JUST THE VERDICT. Three facts come out as BROKEN - no file, a
        line past end-of-file, and a symbol absent from the file - and the
        `because` code is what keeps them apart. Without it the "missing file
        read as empty" blinding reddened NOTHING, measured."""
        rows = cc._fixture_states()
        for row in rows:
            with self.subTest(control=row["control"]):
                self.assertEqual(2, len(row["expected"]))
                self.assertIn(row["expected"][0], cc.STATES)
                self.assertTrue(row["expected"][1])
        broken = [r for r in rows if r["expected"][0] == cc.BROKEN]
        self.assertEqual(2, len(broken))
        self.assertNotEqual(broken[0]["expected"][1], broken[1]["expected"][1])

    def test_the_self_test_exits_zero_while_the_controls_hold(self):
        lines = []
        self.assertEqual(0, cc.self_test(out=lines.append))
        self.assertTrue(any("6 of 6 controls hold" in line for line in lines))


class EachBlindingReddensExactlyItsOwnControl(unittest.TestCase):
    """The only proof a control can fail is watching it fail."""

    def test_four_blindings_each_redden_what_they_should(self):
        for row in cc.blindings():
            with self.subTest(blinding=row["blinding"]):
                self.assertEqual(row["expected_red"], row["observed_red"],
                                 row["blinding"])

    def test_the_symbol_blinding_cannot_redden_the_other_three(self):
        """THE BRIEF ASKED FOR ONE BLINDING AND FOR IT TO REDDEN THREE
        FIXTURES. It cannot, and this is the measurement: a missing file is
        still missing however the comparison answers, and a citation with no
        symbol never reaches a comparison. Pinned so the claim in
        `blindings()`' comment is checked rather than argued."""
        rows = [r for r in cc.blindings()
                if r["blinding"] == "the symbol comparison always succeeds"]
        self.assertEqual(1, len(rows))
        self.assertEqual((cc.MOVED,), rows[0]["observed_red"])

    def test_an_extractor_that_finds_nothing_reddens_everything(self):
        rows = [r for r in cc.blindings()
                if r["blinding"] == "the extractor finds nothing"]
        self.assertEqual(1, len(rows))
        self.assertEqual(6, len(rows[0]["observed_red"]))


class TheExtractorKnowsAClaimFromProse(unittest.TestCase):
    """Each shape measured, including the four that are NOT claims."""

    SHAPES = (
        ("`src/x.py:4` `THE_SYMBOL`", "THE_SYMBOL", "backticked"),
        ("    src/x.py:4   THE_SYMBOL = 1", "THE_SYMBOL", "code block"),
        ("| `src/x.py:4` |", None, None),
        ("see `src/x.py:4`, as stated above", None, None),
        ("`src/x.py:4`, in `record_bounces`' own docstring", None, None),
        ("`src/x.py:4` `,`", None, None),
        ("`src/x.py:4` `docs/other.md`", None, None),
    )

    def test_every_shape_is_read_the_way_it_is_written(self):
        for text, symbol, how in self.SHAPES:
            found = cc.citations_in(text)
            with self.subTest(shape=text):
                self.assertEqual(1, len(found), text)
                self.assertEqual(symbol, found[0]["symbol"])
                if how:
                    self.assertEqual(how, found[0]["symbol_from"])

    def test_two_citations_on_one_line_are_two_claims(self):
        """And neither is the other's symbol. Before this was fixed, the
        first citation's "symbol" was the second CITATION, and `_on_line`
        then looked for the identifier `docs` and found it on five lines of
        a markdown file - a MOVED out of nothing."""
        found = cc.citations_in("`src/x.py:4` and `src/y.py:9`")
        self.assertEqual(2, len(found))
        self.assertEqual([None, None], [c["symbol"] for c in found])

    def test_a_range_and_a_list_are_different_claims(self):
        span = cc.citations_in("`src/x.py:100-104` `S`")
        self.assertEqual([(100, 104)],
                         [(c["start"], c["end"]) for c in span])
        listed = cc.citations_in("`src/x.py:100,104,110` `S`")
        self.assertEqual([(100, 100), (104, 104), (110, 110)],
                         [(c["start"], c["end"]) for c in listed])

    def test_prose_numbers_are_not_citations(self):
        """A pattern that matched `3:14` in prose would fill every document
        with findings nobody wrote."""
        for text in ("at 10:30 UTC", "a ratio of 3:14", "page 2:1",
                     "version 1.2:3"):
            with self.subTest(text=text):
                self.assertEqual([], cc.citations_in(text))


class TheVerdictIsNeverATick(unittest.TestCase):

    def rows(self, *states):
        return [{"state": s, "path": "p", "start": 1, "end": 1}
                for s in states]

    def test_a_moved_or_broken_citation_fails_the_run(self):
        for state in (cc.MOVED, cc.BROKEN, cc.REFUSED, cc.ERROR):
            with self.subTest(state=state):
                code, sentence = cc.verdict(self.rows(cc.OK, state))
                self.assertEqual(1, code)
                self.assertIn("NOT VERIFIED", sentence)

    def test_a_failing_headline_names_the_verified_count_too(self):
        """THE HEADLINE NAMED THE SMALLEST NUMBER. Measured 2026-10-16 on
        this lane's own two documents at `2a623b506`: one read "NOT
        VERIFIED: 3 of 20 citations cannot be trusted", counting only the
        REFUSED three, while exactly ONE of the twenty was OK and the
        UNVERIFIABLE sentence was suppressed by the early return. A reader
        who skims a headline takes the number in it, so the failing count
        and the verified count - two different questions - are both in it."""
        rows = self.rows(cc.OK, cc.REFUSED, *([cc.UNVERIFIABLE] * 8))
        code, sentence = cc.verdict(rows)
        self.assertEqual(1, code)
        self.assertIn("1 of 10 citations FAIL", sentence)
        self.assertIn("only 1 of 10 is OK", sentence)
        self.assertIn("other 9 were not verified", sentence)

    def test_the_failing_headline_agrees_with_its_own_totals(self):
        """The three numbers are arithmetic, not prose: fail + ok + the
        unchecked remainder must account for every citation, at any mix."""
        for extra in (0, 1, 5):
            rows = self.rows(cc.OK, cc.OK, cc.MOVED,
                             *([cc.UNVERIFIABLE] * extra))
            counts = cc.totals(rows)
            code, sentence = cc.verdict(rows)
            with self.subTest(unverifiable=extra):
                self.assertEqual(1, code)
                self.assertIn("only %d of %d" % (counts[cc.OK], len(rows)),
                              sentence)
                self.assertIn("other %d" % (len(rows) - counts[cc.OK],),
                              sentence)

    def test_unverifiable_does_not_fail_but_is_never_called_verified(self):
        code, sentence = cc.verdict(self.rows(cc.OK, cc.UNVERIFIABLE))
        self.assertEqual(0, code)
        self.assertIn("NOT verified", sentence)
        self.assertIn("1 of 2", sentence)

    def test_an_all_ok_document_says_so_with_its_denominator(self):
        code, sentence = cc.verdict(self.rows(cc.OK, cc.OK))
        self.assertEqual(0, code)
        self.assertIn("every one of 2 citations is OK", sentence)

    def test_no_citation_at_all_is_a_failure(self):
        """A CHECKER THAT FINDS NOTHING REPORTS CLEAN, so finding nothing is
        itself the finding. Measured against the real
        `CANARY-01-PREFLIGHT-2026-10-16.md`, which carries zero `path:line`
        citations - the extractor was not broken, the document cites no
        lines."""
        code, sentence = cc.verdict([])
        self.assertEqual(2, code)
        self.assertIn("NO CITATION WAS FOUND AT ALL", sentence)

    def test_the_summary_names_all_six_counts(self):
        code, sentence = cc.verdict(self.rows(cc.OK))
        for state in cc.STATES:
            with self.subTest(state=state):
                self.assertIn(state.lower(), sentence)


class TheBoundaryIsARefusalAndNotAPass(unittest.TestCase):

    def test_a_forbidden_path_is_refused_before_it_is_opened(self):
        for path in ("src/providers/bison.py",
                     "scripts/bison_watch_loop.py",
                     "scripts/heyreach_watch_loop.py",
                     "work/queue.jsonl", "config/.env"):
            with self.subTest(path=path):
                bad, why = cc.forbidden(path)
                self.assertTrue(bad, path)
                self.assertTrue(why)
                with self.assertRaises(cc.Refused):
                    cc.read_at_head(path)

    def test_a_refusal_is_its_own_state_and_fails_the_run(self):
        self.assertIn(cc.REFUSED, cc.FAILING)
        self.assertNotIn(cc.UNVERIFIABLE, cc.FAILING)

    def test_an_ordinary_path_is_not_refused(self):
        """The control: the boundary refuses the five above and nothing
        else, so REFUSED above is about those paths and not about a check
        that refuses everything."""
        for path in ("src/preflight.py", "scripts/citecheck.py", "CLAUDE.md"):
            with self.subTest(path=path):
                self.assertEqual((False, None), cc.forbidden(path))


class TheLineEndingTrapIsAssertedNotAssumed(unittest.TestCase):

    #: A file that is ALREADY TRACKED. `scripts/citecheck.py` is added by
    #: the very commit these tests arrive in, so resolving it at HEAD fails
    #: until that commit exists - and a test that can only run after its own
    #: commit cannot be run while it is being written.
    TRACKED = "src/preflight.py"

    def test_the_head_blob_and_the_working_tree_agree_on_this_tree(self):
        """Five lane worktrees are CRLF and the main checkout is LF. A
        terminator is not a line, so these counts must agree - and `cannot
        differ` is an argument, which is why this measures."""
        lines, note = cc.read_at_head(self.TRACKED)
        self.assertGreater(len(lines), 100)
        self.assertIn("working tree agrees", note)

    def test_a_tree_that_disagrees_with_head_makes_the_citation_error(self):
        """Planted by handing the reader a blob that is NOT this file, so
        the counts differ. The direction is ERROR - never OK - because line
        numbers that mean two things cannot answer a citation."""
        real_git = cc._git

        def short_blob(args):
            if args[:1] == ["show"]:
                return 0, b"one\ntwo\nthree\n", ""
            return real_git(args)

        with mock.patch.object(cc, "_git", short_blob):
            with self.assertRaises(RuntimeError) as caught:
                cc.read_at_head(self.TRACKED)
            # AND IT IS AN ERROR CELL, not an OK and not a BROKEN: the check
            # itself could not be made.
            row = cc.check_one(
                cc.citations_in("`%s:4` `PASS`" % self.TRACKED)[0])
        self.assertIn("not comparable", str(caught.exception))
        self.assertEqual(cc.ERROR, row["state"])
        self.assertEqual(cc.BECAUSE_CHECK_FAILED, row["because"])

    def test_the_ending_is_named_in_the_note(self):
        for path in (self.TRACKED, "CLAUDE.md"):
            lines, note = cc.read_at_head(path)
            with self.subTest(path=path):
                self.assertTrue(any(e in note for e in ("LF", "CRLF")), note)


class ItWritesNothingAndCallsNoProvider(unittest.TestCase):

    def source(self):
        return io.open(SCRIPT, encoding="utf-8").read()

    def test_the_checker_opens_no_file_for_writing(self):
        """BY AST, NOT BY TEXT. The first version of this searched the source
        for the literal `"a"` - which `NOT_A_SYMBOL` contains as an English
        word, so a read-only module failed its own read-only check. A
        one-character lexical ban is the false-positive class this
        repository has replaced with an AST walk everywhere else."""
        import ast
        tree = ast.parse(self.source())
        writers = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # THE DOTTED NAME, NOT THE BARE ATTRIBUTE. `path.replace("/",
            # ".")` is a string method and was being reported as a file
            # operation - a name matched without its receiver, which is the
            # same false positive as the lexical `"a"` this replaced.
            if isinstance(node.func, ast.Attribute) and isinstance(
                    node.func.value, ast.Name):
                dotted = "%s.%s" % (node.func.value.id, node.func.attr)
            else:
                dotted = getattr(node.func, "id", "") or ""
            if dotted == "open" and len(node.args) > 1:
                mode = node.args[1]
                if isinstance(mode, ast.Constant) and any(
                        ch in str(mode.value) for ch in "wax+"):
                    writers.append((node.lineno, mode.value))
            if dotted in ("os.replace", "os.rename", "os.unlink",
                          "os.remove", "os.mkdir", "os.makedirs",
                          "shutil.rmtree", "shutil.move", "shutil.copy"):
                writers.append((node.lineno, dotted))
        self.assertEqual([], writers)

    def test_the_only_subprocess_it_runs_is_git(self):
        import ast
        tree = ast.parse(self.source())
        runs = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "run"):
                first = node.args[0] if node.args else None
                runs.append(ast.dump(first) if first else "")
        self.assertTrue(runs, "no subprocess call found at all")
        for dumped in runs:
            with self.subTest(call=dumped[:60]):
                self.assertIn("'git'", dumped)

    def test_it_imports_no_provider(self):
        import ast
        tree = ast.parse(self.source())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
        self.assertEqual([], sorted(n for n in imported
                                    if "provider" in n or "bison" in n
                                    or "heyreach" in n or "requests" in n
                                    or "urllib" in n))

    def test_no_real_address_in_the_checker_or_this_file(self):
        pattern = re.compile(
            r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
        reserved = ("example.test", "example.invalid", "other.invalid",
                    "example.com", "test", "invalid", "localhost")
        for path in (SCRIPT, os.path.abspath(__file__)):
            text = io.open(path, encoding="utf-8").read()
            found = [m.group(0) for m in pattern.finditer(text)
                     if not any(m.group(1).lower() == r
                                or m.group(1).lower().endswith("." + r)
                                for r in reserved)]
            with self.subTest(file=os.path.basename(path)):
                self.assertEqual([], found)


class TheTwoDocumentsItWasBuiltFor(unittest.TestCase):
    """Measured on the real files, because a checker proven only on its own
    fixtures is a checker proven on nothing a reader will ever open."""

    A = os.path.join(ROOT, "docs",
                     "NINE-HUNDRED-SENDS-ONE-CONFIRMED-TOUCH-2026-10-16.md")
    B = os.path.join(
        ROOT, "docs",
        "NINE-HUNDRED-SENDS-ONE-CONFIRMED-TOUCH-REDISPATCH-2026-10-16.md")

    def counts(self, path):
        text = io.open(path, encoding="utf-8").read()
        return cc.totals(cc.check_text(text))

    def test_neither_document_still_carries_a_moved_or_broken_citation(self):
        """The TASK-0210 deliverable, as a test rather than a claim. If a
        future edit reintroduces one, this fails."""
        for path in (self.A, self.B):
            counts = self.counts(path)
            with self.subTest(document=os.path.basename(path)):
                self.assertEqual(0, counts[cc.MOVED])
                self.assertEqual(0, counts[cc.BROKEN])
                self.assertEqual(0, counts[cc.ERROR])

    def test_the_corrected_chain_is_the_one_in_the_file(self):
        """The two numbers themselves, measured against `src/leadobserve.py`
        rather than quoted. `scripts/bison_watch_loop.py` is NOT asserted
        here: it is outside this lane's boundary, the checker refuses it, and
        a test that read it would be the boundary breach the refusal
        exists to prevent."""
        lines, _ = cc.read_at_head("src/leadobserve.py")
        self.assertIn("confirm_email_touches", lines[789])      # line 790
        self.assertIn("scheduled_rows", lines[788])             # line 789
        text = io.open(self.A, encoding="utf-8").read()
        self.assertIn("src/leadobserve.py:790", text)
        self.assertNotIn("src/leadobserve.py:789", text)

    def test_both_documents_still_carry_citations_to_check(self):
        """Without this, deleting every citation would pass the test above."""
        for path in (self.A, self.B):
            counts = self.counts(path)
            with self.subTest(document=os.path.basename(path)):
                self.assertGreater(sum(counts.values()), 10)
                self.assertGreater(counts[cc.OK], 0)


class TheMainIsAThinWrapper(unittest.TestCase):

    def test_a_missing_argument_is_refused_rather_than_defaulted(self):
        with self.assertRaises(SystemExit):
            cc.main([])

    def test_self_test_runs_from_the_command_line(self):
        self.assertEqual(0, cc.main(["--self-test"]))

    def test_an_unreadable_markdown_file_is_not_a_pass(self):
        tmp = tempfile.mkdtemp(prefix="rga-0210-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.assertEqual(2, cc.main([os.path.join(tmp, "nope.md")]))


if __name__ == "__main__":
    unittest.main()
