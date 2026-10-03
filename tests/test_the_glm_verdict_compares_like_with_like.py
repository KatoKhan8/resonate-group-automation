#!/usr/bin/env python3
"""A GLM verdict's "new failures" must be a real set difference.

## WHY THIS EXISTS

`scripts/glm_verify_branch.py` decides a branch's verdict partly by subtracting
the standing suite baseline from the branch's failing tests. The two sides were
shaped differently and nobody reconciled them:

    unittest -v writes      FAIL: test_x (tests.mod.Class.test_x)
    the baseline holds      FAIL tests.mod.Class.test_x

The extractor stored the whole `"test_x (tests.mod.Class.test_x)"` string and
subtracted bare dotted names from it. **The two sets could never intersect**, so
every failing test was reported as "new (not in baseline)" and every verdict was
FAIL - including for branches whose failures were entirely baseline names.

Measured on 2026-09-28, which is what this module pins: the TASK-364 verdict
named two "new" failures and BOTH are in the baseline file; the TASK-400 verdict
named seventeen and every one sampled was in the baseline too.

The reason this is worth a test rather than a fix and a shrug: the operator's
standing merge rule is **"a valid GLM PASS means merge"**. A verifier that can
never emit PASS does not make merging slower - it teaches everyone to discount
the verifier, and then a real finding gets waved through months later. A broken
check that always cries wolf is more dangerous than no check, because it spends
the credibility the check needs.

It is the same class of defect as the one this repository already names: two
numbers compared without being shaped the same way. The suite baseline is a LIST
for exactly that reason, and a diff is only evidence once both sides are
normalised.
"""
import io
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

from scripts import glm_verify_branch as verifier
from scripts.glm_verify_branch import (
    BASELINE_PATH, normalise_test_name, _load_baseline)


#: The two names the TASK-364 verdict called "new". Both are baseline entries -
#: lines 62 and 63 of docs/state/SUITE-BASELINE-2026-09-26.txt.
MISREPORTED_AS_NEW = (
    "test_add_lead_is_refused_for_finished "
    "(tests.test_campaign_cannot_send.TheNarrowedSeals."
    "test_add_lead_is_refused_for_finished)",
    "test_finished_is_not_proven_safe "
    "(tests.test_campaign_cannot_send.ThePredicateReadsProviderTruth."
    "test_finished_is_not_proven_safe)",
)


class TheTwoSidesAreShapedTheSame(unittest.TestCase):

    def test_unittest_output_reduces_to_the_baselines_spelling(self):
        """`test_x (tests.mod.Class.test_x)` becomes `mod.Class.test_x`."""
        self.assertEqual(
            "test_campaign_cannot_send.TheNarrowedSeals."
            "test_add_lead_is_refused_for_finished",
            normalise_test_name(MISREPORTED_AS_NEW[0]))

    def test_it_is_idempotent_so_either_side_may_be_normalised(self):
        """A name already in baseline shape survives unchanged.

        The comparison has to be symmetric: normalising the baseline as well
        must not corrupt it, or fixing one side breaks the other.
        """
        bare = "test_campaign_cannot_send.TheNarrowedSeals.test_a"
        self.assertEqual(bare, normalise_test_name(bare))
        self.assertEqual(bare, normalise_test_name(normalise_test_name(bare)))

    def test_the_leading_tests_package_is_dropped(self):
        """The baseline does not carry the `tests.` prefix, so neither may we."""
        self.assertEqual(
            "mod.Class.test_a",
            normalise_test_name("test_a (tests.mod.Class.test_a)"))

    def test_nothing_useful_becomes_none(self):
        self.assertIsNone(normalise_test_name(""))
        self.assertIsNone(normalise_test_name(None))


class TheRegressionItself(unittest.TestCase):
    """The two names GLM called new are found IN the baseline after normalising.

    This is the test that would have caught the defect, and it asserts on the
    real baseline file rather than a fixture - because the defect was a
    disagreement between the parser and that exact file, and a fixture of my own
    shaping could have agreed with the parser while the file did not.
    """

    def setUp(self):
        self.baseline = _load_baseline()
        if not self.baseline:
            self.skipTest("baseline file absent")

    def test_the_baseline_is_a_list_of_names_and_it_loaded(self):
        self.assertGreater(len(self.baseline), 200,
                           "the baseline should hold ~231 named failures")

    def test_both_misreported_names_are_baseline_members(self):
        for raw in MISREPORTED_AS_NEW:
            name = normalise_test_name(raw)
            self.assertIn(
                name, self.baseline,
                f"{name} was reported as a NEW failure by a GLM verdict, but it "
                f"is in the standing baseline. That verdict was void on this "
                f"ground and the branch it failed was merged after independent "
                f"verification")

    def test_a_genuinely_new_name_is_still_reported_as_new(self):
        """The control. Without it, a normaliser that mapped everything onto an
        existing baseline entry would pass every test above and silence every
        real regression - which is the opposite failure and the worse one."""
        invented = normalise_test_name(
            "test_nothing (tests.test_module_that_does_not_exist."
            "Class.test_nothing)")
        self.assertNotIn(invented, self.baseline)


class TheBaselineIsJSON(unittest.TestCase):
    """The baseline moved from a text file to JSON on 2026-10-02.

    The old text baseline held 128 entries; the new JSON baseline holds 231.
    A verifier that still reads the old file compares against a stale set and
    reports every new master failure as 'new on the branch' - the same class
    of defect as the original spelling mismatch this module pins.
    """

    def test_the_baseline_path_points_at_a_json_file(self):
        self.assertTrue(BASELINE_PATH.endswith(".json"),
                        f"baseline should be JSON, got {BASELINE_PATH}")

    def test_the_json_baseline_holds_231_named_failures(self):
        baseline = _load_baseline()
        self.assertEqual(231, len(baseline),
                         "the 2026-10-02 full baseline measures 231 named "
                         "failures; a different count means the parser is "
                         "reading the wrong file or the wrong key")


class ThePatchSurvivesBeingRead(unittest.TestCase):
    """A byte the machine's locale codec cannot map must not erase the patch.

    MEASURED 2026-10-02, by this branch's own verification run. `_git` captured
    with `text=True` and no `encoding`, so Python decoded git's bytes with the
    LOCALE codec - cp1250 on this machine. `git diff --name-only` and
    `git diff --stat` are ASCII and survived; the PATCH carried byte 0x90 at
    offset 3065, the reader thread raised `UnicodeDecodeError`, and
    `CompletedProcess.stdout` came back `None`. `_diff_against_master` then
    returned `None` for the diff and the prompt's patch slot became
    "(could not generate a diff - answer NEEDS_CLAUDE)".

    That is this task's own defect reached by a second route: the verifier
    reviewing a summary instead of the code, except this time it reviews
    NOTHING and looks healthy doing it, because the file list and the stat are
    still there. The verdict it produced was NEEDS_CLAUDE, which is the only
    thing that kept it honest.

    The decode policy is one dict (`CAPTURE`) used by every capture in the
    script, so there is nowhere for a second copy of it to drift.
    """

    #: U+0410 CYRILLIC CAPITAL A. Its UTF-8 bytes are D0 90, and 0x90 is
    #: undefined in cp1250 - the exact byte that blinded the real run.
    #: CHOSEN BY MEASUREMENT, not by looking non-ASCII: a black diamond
    #: (E2 99 A6) and an em dash (E2 80 94) are both decoded happily by cp1250,
    #: so either one as the control would have proved nothing. An emoji
    #: (F0 9F 98 80) works for the same reason this does.
    OUTSIDE_CP1250 = "\u0410"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="glmpatch-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.a = os.path.join(self.tmp, "a.txt")
        self.b = os.path.join(self.tmp, "b.txt")
        for target, text in ((self.a, "plain\n"),
                             (self.b, "plain " + self.OUTSIDE_CP1250 + "\n")):
            with io.open(target, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)

    def test_the_diff_is_text_and_still_carries_the_character(self):
        result = verifier._git("diff", "--no-index", self.a, self.b)
        self.assertIsNotNone(
            result.stdout,
            "git produced a patch and the capture lost it: that is the blind "
            "reviewer, not a cosmetic problem")
        self.assertIsInstance(result.stdout, str)
        self.assertIn(self.OUTSIDE_CP1250, result.stdout)

    def test_the_control_a_strict_locale_capture_loses_the_whole_patch(self):
        """The negative control, and the reason this test can fail.

        Without it, a capture that happened to work for an ASCII-only patch
        would pass the test above, and the defect would return the first time a
        branch touched a file with an em dash in it.
        """
        died = []
        previous = threading.excepthook
        # The reader thread's traceback goes to the process's stderr, where in a
        # full-suite log it reads as a crash in whatever ran next. It is
        # CAPTURED instead of printed, and capturing it is the stronger
        # assertion: the control proves the thread actually died, not merely
        # that stdout came back empty.
        threading.excepthook = lambda args: died.append(args.exc_type)
        try:
            strict = subprocess.run(
                ["git", "diff", "--no-index", self.a, self.b],
                capture_output=True, text=True,
                encoding="cp1250", errors="strict", timeout=120)
        finally:
            threading.excepthook = previous
        self.assertIsNone(
            strict.stdout,
            "cp1250 decoded bytes it cannot map, so this control proves "
            "nothing - pick a character outside the codec")
        self.assertIn(UnicodeDecodeError, died)

    def test_the_decode_policy_replaces_rather_than_refuses(self):
        """`errors="replace"`, never `"strict"`: git emits patch bytes verbatim,
        and a mangled character costs a reviewer nothing while a dead reader
        costs it the entire diff."""
        self.assertEqual({"encoding": "utf-8", "errors": "replace"},
                         verifier.CAPTURE)


class TheCodeIsShownBeforeTheProse(unittest.TestCase):
    """When the patch does not fit the prompt, the PROSE is what gets cut.

    MEASURED on this branch: 68,102 characters of patch, of which 35,326 are
    five markdown files and 32,912 are the code, against about 57,000
    characters of room. `git diff` emits paths alphabetically, so `docs/` came
    first and the truncation banner cut the code - leaving a reviewer asked
    "does this function have a production caller" holding review prose.

    A reviewer cannot check prose for a caller, a constructible failing input or
    an arithmetic slip, so prose is the only part whose loss is affordable.
    """

    def _git(self, *args):
        return subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t"] + list(args),
            cwd=self.repo, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120)

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="glmorder-")
        self.addCleanup(shutil.rmtree, self.repo, True)
        self._git("init", "-q", "-b", "main")
        os.makedirs(os.path.join(self.repo, "docs"))
        os.makedirs(os.path.join(self.repo, "scripts"))
        for rel, text in (("docs/note.md", "prose one\n"),
                          ("scripts/tool.py", "x = 1\n")):
            with io.open(os.path.join(self.repo, rel), "w",
                         encoding="utf-8", newline="") as handle:
                handle.write(text)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "base")
        self.base = self._git("rev-parse", "HEAD").stdout.strip()
        for rel, text in (("docs/note.md", "prose one\nprose two\n"),
                          ("scripts/tool.py", "x = 1\ny = 2\n")):
            with io.open(os.path.join(self.repo, rel), "w",
                         encoding="utf-8", newline="") as handle:
                handle.write(text)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "change both")
        self.head = self._git("rev-parse", "HEAD").stdout.strip()
        if not self.base or not self.head:
            self.skipTest("git could not build the fixture repository")

    def _patch(self):
        with mock.patch.object(verifier, "ROOT", self.repo), \
             mock.patch.object(
                 verifier, "review_range",
                 lambda branch: (self.base, self.head, "fixture")):
            return verifier._diff_against_master("fixture-branch")

    def test_the_code_hunk_comes_before_the_docs_hunk(self):
        _stat, patch = self._patch()
        self.assertIsNotNone(patch)
        starts = [line for line in patch.splitlines()
                  if line.startswith("diff --git")]
        self.assertEqual(2, len(starts), starts)
        self.assertIn("scripts/tool.py", starts[0])
        self.assertIn("docs/note.md", starts[1])

    def test_the_control_both_files_are_really_in_the_patch(self):
        """Without this, dropping the prose altogether would pass the test above
        while hiding half the branch from the reviewer."""
        _stat, patch = self._patch()
        self.assertIn("prose two", patch)
        self.assertIn("y = 2", patch)


class TheSpendLedgerIsTheMainCheckoutsOne(unittest.TestCase):
    """A verification run from a worktree must bill and audit the ONE ledger.

    MEASURED 2026-10-02, and found by GLM once the patch reached it:
    `spendledger.path()` resolves against `store.queue_path()`, which is the
    CALLING TREE's `work/`, and `work/` is gitignored - so every worktree has
    its own. The main checkout held **39** glm rows while the worktree this
    verifier had been running from held **2**: its own calls, 30,688 micro-USD
    of real money that the production spend audit could not see. The standing
    rule is that model spend is attributed to a client or a task.

    It also made the branch's own acceptance command 4 unfailable - a fresh
    acceptance worktree has no ledger, so `0 rows, 0 clients` satisfied an
    `isinstance(..., dict)` assertion that no ledger content could break. This
    is the same per-worktree trap as `config/.env` and the suite lock, and it
    gets the same one escape: `--path-format=absolute --git-common-dir`.
    """

    def test_the_ledger_sits_under_the_main_checkout_not_under_this_tree(self):
        fake_main = os.path.join(tempfile.gettempdir(), "glmmain-fixture")
        git_dir = os.path.join(fake_main, ".git")

        def fake_git(*args, **kwargs):
            if args[:1] == ("rev-parse",):
                return subprocess.CompletedProcess(args, 0, git_dir + "\n", "")
            raise AssertionError(f"unexpected git call: {args}")

        with mock.patch.object(verifier, "_git", fake_git):
            resolved = verifier.ledger_path()
        self.assertEqual(
            os.path.join(fake_main, "work", "spend-ledger.jsonl"), resolved,
            "the ledger must be the main checkout's, whatever tree we run in")
        self.assertFalse(
            resolved.startswith(os.path.abspath(verifier.ROOT) + os.sep),
            "the ledger resolved inside the calling tree, which is the defect: "
            "a worktree then bills a throwaway file")

    def test_a_relative_answer_from_git_is_refused_rather_than_resolved(self):
        """The control on the escape itself.

        Without `--path-format=absolute` git answers RELATIVE from a worktree,
        and `abspath` would resolve it against the caller - putting the ledger
        back inside the tree while looking like it had escaped. Refusing is the
        only safe reading, and `None` is then visible in the output line.
        """
        def relative_git(*args, **kwargs):
            return subprocess.CompletedProcess(args, 0, ".git\n", "")

        with mock.patch.object(verifier, "_git", relative_git):
            self.assertIsNone(verifier.ledger_path())
            self.assertIsNone(verifier.main_checkout_root())

    def test_binding_moves_the_write_and_the_read_together(self):
        """One environment variable, so billing and auditing cannot diverge."""
        fake_main = os.path.join(tempfile.gettempdir(), "glmmain-fixture2")
        git_dir = os.path.join(fake_main, ".git")

        def fake_git(*args, **kwargs):
            return subprocess.CompletedProcess(args, 0, git_dir + "\n", "")

        previous = os.environ.pop("SPEND_LEDGER", None)
        self.addCleanup(lambda: os.environ.__setitem__("SPEND_LEDGER", previous)
                        if previous is not None
                        else os.environ.pop("SPEND_LEDGER", None))
        with mock.patch.object(verifier, "_git", fake_git):
            bound = verifier.bind_spend_to_the_main_ledger()
        self.assertEqual(os.path.join(fake_main, "work", "spend-ledger.jsonl"),
                         bound)
        from src import spendledger
        self.assertEqual(bound, spendledger.path(),
                         "the ledger the adapter WRITES must be the one the "
                         "verifier READS")

    def test_an_operators_own_override_still_wins(self):
        """`setdefault`, not assignment: `SPEND_LEDGER` is a documented override
        and a tool that overwrote it would silently redirect somebody's audit."""
        chosen = os.path.join(tempfile.gettempdir(), "operator-chosen.jsonl")
        previous = os.environ.get("SPEND_LEDGER")
        os.environ["SPEND_LEDGER"] = chosen
        self.addCleanup(lambda: os.environ.__setitem__("SPEND_LEDGER", previous)
                        if previous is not None
                        else os.environ.pop("SPEND_LEDGER", None))
        self.assertEqual(chosen, verifier.bind_spend_to_the_main_ledger())


def _patch_for(*files):
    """A minimal multi-file patch, shaped the way git emits one."""
    out = []
    for name, body in files:
        out.append(f"diff --git a/{name} b/{name}\n")
        out.append("index 0000000..1111111 100644\n")
        out.append(f"--- a/{name}\n+++ b/{name}\n")
        out.append("@@ -1 +1 @@\n")
        out.append(f"+{body}\n")
    return "".join(out)


class WhatIsWithheldIsAWholeFileAndItIsNamed(unittest.TestCase):
    """A patch that does not fit loses WHOLE FILES, never half of one.

    MEASURED 2026-10-02, the third form of this task's own defect. The patch is
    ordered code-first, but the bound then cut the tail at a character count:
    on this branch that left 30,596 characters unseen INCLUDING the end of
    `main()`, and GLM - correctly - answered NEEDS_CLAUDE, because the question
    it is asked is whether the new code has a production caller and the caller
    could have been in the part it could not see.

    Two thirds of a function is not two thirds of a review. Whole files, and the
    withheld ones named, so the reviewer can judge whether what is missing
    matters instead of being handed a character count.
    """

    def test_every_line_survives_the_split_exactly_once(self):
        """The structural control. A split that loses or duplicates a line would
        make every assertion below meaningless."""
        patch = _patch_for(("src/a.py", "one"), ("docs/b.md", "two"))
        sections = verifier.split_patch_by_file(patch)
        self.assertEqual(["src/a.py", "docs/b.md"], [n for n, _ in sections])
        self.assertEqual(patch, "".join(text for _, text in sections))

    def test_the_files_that_fit_are_whole_and_the_rest_are_named(self):
        patch = _patch_for(("src/a.py", "A" * 50),
                           ("tests/b.py", "B" * 50),
                           ("docs/c.md", "C" * 50))
        sections = verifier.split_patch_by_file(patch)
        room = len(sections[0][1]) + len(sections[1][1])

        fitted, withheld = verifier.fit_patch(patch, room)

        self.assertEqual(["docs/c.md"], withheld)
        self.assertEqual(sections[0][1] + sections[1][1], fitted,
                         "the kept files must be byte-for-byte whole")
        self.assertNotIn("C" * 50, fitted)

    def test_a_file_larger_than_the_budget_is_declared_a_mid_file_cut(self):
        """The honest answer when no whole file fits.

        `fit_patch` returns nothing kept, and the prompt must then say the cut is
        MID-FILE rather than implying a tidy split - a half-read file is exactly
        the state this bound exists to avoid, so the reviewer has to know it is
        in it.
        """
        # Larger than the REAL budget, not just larger than a toy room:
        # `_build_prompt` computes its own room from `glm.MAX_PROMPT_CHARS`, and
        # a 5,000-character patch sails through it. The first version of this
        # test used one and asserted a banner that correctly never appeared.
        patch = _patch_for(("src/huge.py", "X" * 70_000))
        fitted, withheld = verifier.fit_patch(patch, 100)
        self.assertEqual(["src/huge.py"], withheld,
                         "a file that does not fit IS withheld; the prompt is "
                         "what decides to show part of it anyway")
        self.assertEqual("", fitted)

        prompt = verifier._build_prompt("b", "T", ["src/huge.py"], "stat",
                                        patch, "ran", "tests")
        self.assertIn("CUT PATCH:", prompt)
        self.assertIn("the cut is MID-FILE", prompt)
        self.assertNotIn("PARTIAL PATCH:", prompt)
        self.assertIn("XXXX", prompt,
                      "a declared mid-file cut is worth more than an empty "
                      "patch under a banner that says 'partial'")

    def test_the_control_nothing_is_withheld_when_it_all_fits(self):
        """Without this, a `fit_patch` that always withheld everything would
        satisfy every assertion above."""
        patch = _patch_for(("src/a.py", "small"))
        fitted, withheld = verifier.fit_patch(patch, 10_000)
        self.assertEqual([], withheld)
        self.assertEqual(patch, fitted)

        prompt = verifier._build_prompt("b", "T", ["src/a.py"], "stat", patch,
                                        "ran", "tests")
        self.assertNotIn("PARTIAL PATCH:", prompt)
        self.assertNotIn("CUT PATCH:", prompt)
        self.assertIn("+small", prompt)


class ThePromptNeverExceedsTheAdaptersBound(unittest.TestCase):
    """The banner that names withheld files must not break the prompt it labels.

    FOUND BY GLM, 2026-10-02, reviewing the commit that added that banner -
    mine, one commit old. `BANNER_RESERVE` was 400 characters and the banner
    NAMES the withheld files, so thirty docs paths at this repository's typical
    ~85 characters is 2,550 characters of names alone. `banner + fitted` then
    exceeds `MAX_PROMPT_CHARS`, `glm.complete` REFUSES the prompt rather than
    truncating it, and the verifier reports "GLM call failed" - NEEDS_CLAUDE
    with no review at all, which is the precise failure this task exists to end.

    A reserve that depends on how many files a branch happens to touch is not a
    reserve. The bound is now arithmetic: names capped at `NAME_BUDGET`, prose
    capped at `BANNER_RESERVE`, patch fitted to what is left.
    """

    def _patch_of(self, count, name_length):
        files = []
        for index in range(count):
            stem = "docs/glm-reviews/" + ("x" * max(1, name_length - 20))
            files.append((f"{stem}-{index:03d}.md", "Z" * 400))
        return _patch_for(*files)

    def test_the_prompt_never_exceeds_the_adapters_bound(self):
        """The property that matters: the adapter refuses above its own bound,
        so a prompt over it is not a long prompt, it is no review."""
        from src.providers import glm
        patch = self._patch_of(300, 200)
        self.assertGreater(len(patch), glm.MAX_PROMPT_CHARS)

        prompt = verifier._build_prompt(
            "branch", "TASK", ["a"], "stat", patch, "ran", "tests")

        self.assertLessEqual(
            len(prompt) + len(verifier.SYSTEM), glm.MAX_PROMPT_CHARS,
            "the prompt plus the system turn must fit the adapter's bound, "
            "which counts both")
        self.assertIn("PARTIAL PATCH:", prompt)
        self.assertIn("more", prompt, "past the name budget the banner counts")

    def test_the_whole_banner_fits_the_two_budgets_that_reserve_for_it(self):
        """The arithmetic the bound above rests on, asserted directly.

        An earlier version of this test measured the banner's fixed prose and
        SKIPPED when its fixture happened to fit whole - a test that cannot fail
        is the defect this repository keeps paying for, so it now uses a patch
        that certainly does not fit and asserts the claim the two constants
        actually make: prose plus names stay inside what was reserved for them.
        """
        patch = self._patch_of(300, 200)
        prompt = verifier._build_prompt(
            "branch", "TASK", ["a"], "stat", patch, "ran", "tests")
        marker = "PARTIAL PATCH:"
        self.assertIn(marker, prompt)
        banner = marker + prompt.split(marker, 1)[1].split("diff --git", 1)[0]
        self.assertLessEqual(
            len(banner), verifier.BANNER_RESERVE + verifier.NAME_BUDGET,
            "the banner outgrew the room reserved for it, which is how it "
            "pushed the prompt past the adapter's bound in the first place")

    def test_the_name_list_is_bounded_and_says_how_many_it_dropped(self):
        names = [f"docs/{'n' * 80}-{i}.md" for i in range(100)]
        text = verifier.name_list(names)
        self.assertLessEqual(len(text), verifier.NAME_BUDGET)
        self.assertRegex(text, r"\+\d+ more$")

    def test_the_control_a_short_list_is_printed_in_full(self):
        """Without it, a name_list that always returned '+N more' would satisfy
        the bound above while telling the reviewer nothing."""
        text = verifier.name_list(["docs/a.md", "docs/b.md"])
        self.assertEqual("docs/a.md, docs/b.md", text)
        self.assertNotIn("more", text)
        self.assertEqual("(none)", verifier.name_list([]))


class ABranchTooBigForOnePromptIsReviewedInParts(unittest.TestCase):
    """Operator's decision, 2026-10-02: parts, not a truncated single call.

    A branch can be correct, carry its own tests, pass its acceptance and show
    zero new failing names, and still be unmergeable because the gate cannot
    see it. TASK-940's own last verdict said so: "the production call path and
    the acceptance file's provenance are both inside the 8 withheld files and
    either could flip this to FAIL." Under a multi-part review nothing is
    withheld - it is in another part, and the reviewer is told which.

    The rule the operator set, and the one these tests are really about: the
    branch is PASS only if EVERY part is PASS.
    """

    def _patch(self, *sizes):
        files = []
        for index, size in enumerate(sizes):
            folder = "src" if index % 2 == 0 else "docs"
            files.append((f"{folder}/f{index}.py", "Q" * size))
        return _patch_for(*files)

    def test_every_file_appears_in_exactly_one_part(self):
        """The structural control. A split that dropped or duplicated a file
        would make a part count meaningless and every assertion below with it."""
        patch = self._patch(300, 300, 300, 300)
        parts = verifier.patch_parts(patch, 800)

        names = [name for part in parts for name, _ in part]
        self.assertEqual(sorted(names), sorted(set(names)), "a file repeated")
        self.assertEqual(4, len(names), names)
        rebuilt = "".join(text for part in parts for _, text in part)
        self.assertEqual(patch, rebuilt,
                         "the parts must rebuild the patch byte for byte")

    def test_each_part_fits_the_room_it_was_given(self):
        patch = self._patch(300, 300, 300, 300)
        room = 800
        parts = verifier.patch_parts(patch, room)
        for number, part in enumerate(parts, 1):
            size = sum(len(text) for _, text in part)
            self.assertLessEqual(size, room, f"part {number} is {size}")
        self.assertGreater(len(parts), 1, "this fixture must actually split")

    def test_a_file_larger_than_the_room_becomes_its_own_part(self):
        """Dropping it would hide a whole file while reporting a part count
        that looks complete; its own part is declared a mid-file cut instead."""
        patch = self._patch(50, 5_000, 50)
        parts = verifier.patch_parts(patch, 500)
        big = [part for part in parts if any("f1" in n for n, _ in part)]
        self.assertEqual(1, len(big))
        self.assertEqual(1, len(big[0]), "the oversized file shares no part")

    def test_the_order_is_preserved_so_code_comes_before_prose(self):
        """`_diff_against_master` hands over a patch already ordered code-first;
        the splitter must not reorder it, or part 1 stops being the code."""
        patch = _patch_for(("src/a.py", "A" * 200), ("tests/b.py", "B" * 200),
                           ("docs/c.md", "C" * 200))
        parts = verifier.patch_parts(patch, 400)
        flat = [name for part in parts for name, _ in part]
        self.assertEqual(["src/a.py", "tests/b.py", "docs/c.md"], flat)

    def test_the_control_one_part_when_it_all_fits(self):
        patch = self._patch(100)
        parts = verifier.patch_parts(patch, 10_000)
        self.assertEqual(1, len(parts))
        self.assertEqual("", verifier.part_sentence(1, parts),
                         "a single-part review has no other parts to describe, "
                         "and a sentence about none of them would be noise")


class TheBranchIsPassOnlyIfEveryPartIs(unittest.TestCase):
    """The conjunction, which is the operator's rule and the whole point.

    Stricter than one call over a truncated patch on purpose: a part that
    passed says something about that part only.
    """

    def test_all_pass_is_pass(self):
        verdict, reason = verifier.combine_verdicts(
            [("PASS", "a"), ("PASS", "b"), ("PASS", "c")])
        self.assertEqual("PASS", verdict)
        self.assertIn("3", reason)

    def test_one_needs_claude_is_the_branchs_verdict(self):
        verdict, reason = verifier.combine_verdicts(
            [("PASS", "a"), ("NEEDS_CLAUDE", "cannot see the caller")])
        self.assertEqual("NEEDS_CLAUDE", verdict)
        self.assertIn("part 2", reason)
        self.assertIn("cannot see the caller", reason)

    def test_a_fail_outranks_a_needs_claude_wherever_it_sits(self):
        """Both block the merge, but the REASON a reader sees should be the
        defect rather than the abstention."""
        verdict, reason = verifier.combine_verdicts(
            [("NEEDS_CLAUDE", "abstained"), ("FAIL", "no production caller")])
        self.assertEqual("FAIL", verdict)
        self.assertIn("part 2", reason)
        self.assertIn("no production caller", reason)

    def test_no_parts_is_not_a_pass(self):
        """A review of nothing is the defect this tool exists to end, and an
        empty list is the easiest way to get one."""
        verdict, reason = verifier.combine_verdicts([])
        self.assertEqual("NEEDS_CLAUDE", verdict)
        self.assertIn("nothing", reason)


class EveryCallIsToldWhatTheOtherPartsHold(unittest.TestCase):
    """Operator's condition: part, full file list, and ONE sentence on the rest.

    Without it a reviewer cannot tell a missing caller from a caller in another
    part, and the honest answer to that uncertainty is NEEDS_CLAUDE - which
    would make a multi-part review WORSE than a truncated single one, because
    there would be more chances to abstain. So the sentence also says what to do
    instead.
    """

    def setUp(self):
        patch = _patch_for(("src/a.py", "A" * 200), ("src/b.py", "B" * 200),
                           ("docs/c.md", "C" * 200))
        self.parts = verifier.patch_parts(patch, 400)
        self.assertGreater(len(self.parts), 1)

    def test_it_names_the_other_parts_and_their_files(self):
        sentence = verifier.part_sentence(1, self.parts)
        self.assertIn(f"PART 1 OF {len(self.parts)}", sentence)
        self.assertIn("docs/c.md", sentence)
        self.assertNotIn("part 1 holds", sentence,
                         "a part does not describe itself twice")

    def test_it_forbids_abstaining_over_another_parts_code(self):
        sentence = verifier.part_sentence(2, self.parts)
        self.assertIn("NAMING THAT PART", sentence)
        self.assertIn("not by NEEDS_CLAUDE", sentence)

    def test_every_part_prompt_stays_inside_the_adapters_bound(self):
        """The property that matters: the adapter REFUSES above its bound, so a
        prompt over it is not a long prompt, it is no review."""
        from src.providers import glm
        patch = _patch_for(*[(f"src/f{i}.py", "Z" * 9000) for i in range(12)])
        room = verifier.patch_room("b", "T", ["src/f0.py"], "stat", "ran", "t")
        parts = verifier.patch_parts(patch, room)
        self.assertGreater(len(parts), 1, "this fixture must split")
        for number, part in enumerate(parts, 1):
            prompt = verifier._build_prompt(
                "b", "T", ["src/f0.py"], "stat",
                "".join(text for _, text in part), "ran", "t",
                part_note=verifier.part_sentence(number, parts))
            self.assertLessEqual(
                len(prompt) + len(verifier.SYSTEM), glm.MAX_PROMPT_CHARS,
                f"part {number} renders a prompt the adapter would refuse")


class TheReviewerIsToldWhetherTheBranchsOwnTestsRan(unittest.TestCase):
    """The fifth defect in this gate rather than in a branch, 2026-10-03.

    The prompt carried `test_output[:8000]` - the HEAD of a verbose run across
    every changed module - and on `task-word-contract-enforced` that cut before
    both of the branch's controlling test files. GLM named them and FAILED the
    branch for having no evidence its own tests ran. They had run and passed:
    53 OK and 15 OK, measured directly afterwards.

    Truncating the head was the worst available choice, because unittest prints
    the failures and the verdict at the END.
    """

    #: A real verbose run's shape, including the case that defeats a naive
    #: parser: unittest prints a test's docstring BETWEEN the name and the
    #: verdict, so the verdict is not always on the name's line.
    OUTPUT = (
        "test_a (tests.test_alpha.A.test_a) ... ok\n"
        "test_b (tests.test_alpha.A.test_b)\n"
        "The docstring unittest prints. ... ok\n"
        "test_c (tests.test_beta.B.test_c) ... FAIL\n"
        "test_d (tests.test_beta.B.test_d) ... ok\n"
        "test_e (tests.test_beta.B.test_e) ... skipped 'why'\n"
        "\nRan 5 tests in 0.01s\n\nFAILED (failures=1)\n")

    MODULES = ["tests.test_alpha", "tests.test_beta"]

    def test_every_module_gets_a_line_with_its_count(self):
        summary = verifier.summarise_tests(self.OUTPUT, self.MODULES)
        for module in self.MODULES:
            self.assertIn(module, summary)
        self.assertIn("2 ran", summary)
        self.assertIn("3 ran", summary)

    def test_a_verdict_on_the_line_after_the_name_is_still_counted(self):
        """`test_b`'s "ok" is on the docstring's line, not on its own."""
        summary = verifier.summarise_tests(self.OUTPUT, self.MODULES)
        self.assertIn("tests.test_alpha", summary)
        self.assertRegex(summary, r"tests\.test_alpha\s+2 ran, all ok")

    def test_failures_and_skips_are_not_reported_as_ok(self):
        summary = verifier.summarise_tests(self.OUTPUT, self.MODULES)
        self.assertRegex(summary, r"tests\.test_beta\s+3 ran, 1 ok, "
                                  r"1 FAILED/ERRORED, 1 skipped")

    def test_a_module_that_never_ran_says_so(self):
        """The one outcome the old 8,000-character head could not express."""
        summary = verifier.summarise_tests(
            self.OUTPUT, ["tests.test_alpha", "tests.test_missing"])
        self.assertIn("NOTHING RAN", summary)

    def test_the_control_fires_when_the_summary_misses_a_test(self):
        """A parser that under-counts would hide a module while looking tidy."""
        summary = verifier.summarise_tests(
            self.OUTPUT.replace("Ran 5 tests", "Ran 9 tests"), self.MODULES)
        self.assertIn("CONTROL FAILED", summary)
        self.assertIn("9", summary)

    def test_a_run_that_never_said_it_ran_proves_nothing(self):
        summary = verifier.summarise_tests(
            "test_a (tests.test_alpha.A.test_a) ... ok", ["tests.test_alpha"])
        self.assertIn("NOTHING is proven to have run", summary)

    def test_the_control_passes_on_an_honest_run(self):
        """The opposite control: a clean run must NOT raise an alarm."""
        summary = verifier.summarise_tests(self.OUTPUT, self.MODULES)
        self.assertNotIn("CONTROL FAILED", summary)
        self.assertIn("matching the run's own count", summary)

    def test_the_summary_is_short_enough_that_it_cannot_be_truncated_away(self):
        """200 modules must still fit in a fraction of the prompt budget."""
        many = ["tests.test_module_%03d" % i for i in range(200)]
        summary = verifier.summarise_tests(self.OUTPUT, many)
        self.assertLess(len(summary), 20_000)
        self.assertEqual(summary.count("NOTHING RAN"), 200)

    #: What unittest ACTUALLY prints: the verbose list, then a failure block
    #: that repeats every failing name in a `FAIL: `/`ERROR: ` header.
    WITH_FAILURE_BLOCK = (
        "test_a (tests.test_alpha.A.test_a) ... ok\n"
        "test_c (tests.test_beta.B.test_c) ... FAIL\n"
        "test_d (tests.test_beta.B.test_d) ... ERROR\n"
        "\n"
        "======================================================================\n"
        "FAIL: test_c (tests.test_beta.B.test_c)\n"
        "----------------------------------------------------------------------\n"
        "Traceback (most recent call last):\n"
        "  AssertionError: no\n"
        "\n"
        "======================================================================\n"
        "ERROR: test_d (tests.test_beta.B.test_d)\n"
        "----------------------------------------------------------------------\n"
        "KeyError: 'x'\n"
        "\n"
        "Ran 3 tests in 0.01s\n\nFAILED (failures=1, errors=1)\n")

    def test_the_failure_block_does_not_count_a_test_twice(self):
        """MEASURED 2026-10-03, by GLM, using this function's own control.

        The first version counted any line naming the module, so each failing
        test was counted twice - once in the verbose list and once in its
        `FAIL:` header. The summary claimed 237 where the run said 232, the gap
        was exactly 5, and the run had 4 failures and 1 error. `test_generate`
        read "59 ran, 53 ok, 3 FAILED/ERRORED" - 56 accounted, 3 missing, which
        is its three failures counted twice.

        The control is what found it, which is the argument for the control.
        """
        summary = glm_verify_branch_summary = verifier.summarise_tests(
            self.WITH_FAILURE_BLOCK, self.MODULES)
        self.assertNotIn("CONTROL FAILED", summary)
        self.assertIn("matching the run's own count", summary)
        self.assertRegex(summary, r"tests\.test_beta\s+2 ran")
        self.assertRegex(summary, r"tests\.test_alpha\s+1 ran, all ok")

    def test_failures_are_still_seen_as_failures(self):
        """The opposite control: skipping the block must not hide the failure."""
        summary = verifier.summarise_tests(self.WITH_FAILURE_BLOCK,
                                           self.MODULES)
        self.assertIn("FAILED/ERRORED", summary)
        self.assertNotIn("tests.test_beta                                 "
                         "                                2 ran, all ok",
                         summary)

    #: Two failures, with their failure-block headers, so they can be named
    #: and matched against a baseline.
    TWO_FAILURES = (
        "test_a (tests.test_alpha.A.test_a) ... ok\n"
        "test_c (tests.test_beta.B.test_c) ... FAIL\n"
        "test_d (tests.test_beta.B.test_d) ... FAIL\n"
        "\nFAIL: test_c (tests.test_beta.B.test_c)\n"
        "\nFAIL: test_d (tests.test_beta.B.test_d)\n"
        "\nRan 3 tests in 0.01s\n\nFAILED (failures=2)\n")

    BOTH_IN_BASELINE = {"test_beta.B.test_c", "test_beta.B.test_d"}

    def test_baseline_failures_are_not_charged_to_the_branch(self):
        """The sixth gate defect, and mine, 2026-10-03.

        The first version of this summary reported "3 FAILED/ERRORED" with no
        baseline context. GLM read five of master's standing failures as the
        branch's own regressions and FAILED `task-word-contract-enforced`,
        whose full suite then measured 228 names against the reference's 228 -
        0 new and 0 gone, a perfect set match. A neutral worktree detached at
        master gave the same five names with nothing from the branch present.

        The gate already loaded the baseline and already computed the set
        difference. It simply was not telling the reviewer.
        """
        summary = verifier.summarise_tests(self.TWO_FAILURES, self.MODULES,
                                           self.BOTH_IN_BASELINE)
        self.assertIn("ALL 2 ARE IN THE STANDING BASELINE", summary)
        self.assertIn("0 NEW failing name(s)", summary)
        self.assertNotIn("NEW: test_beta", summary)

    def test_a_genuinely_new_failure_is_named(self):
        """The control. A summary that calls everything baseline is worse than
        one that calls everything new, because it reads as a clean branch."""
        summary = verifier.summarise_tests(self.TWO_FAILURES, self.MODULES,
                                           {"test_beta.B.test_c"})
        self.assertIn("1 NEW on this branch", summary)
        self.assertIn("NEW: test_beta.B.test_d", summary)
        self.assertIn("1 NEW failing name(s)", summary)

    def test_an_absent_baseline_refuses_to_attribute_anything(self):
        """UNKNOWN is not a pass and it is not a failure either.

        With no baseline there is no way to tell master's failures from the
        branch's, so the summary says exactly that rather than defaulting to
        either reading.
        """
        summary = verifier.summarise_tests(self.TWO_FAILURES, self.MODULES,
                                           set())
        self.assertIn("NO BASELINE", summary)
        self.assertIn("not attributable", summary)

    def test_modules_of_is_one_definition_for_runner_and_summary(self):
        """Two spellings would count a module that ran under another name."""
        self.assertEqual(
            verifier.modules_of(["tests/test_a.py", "src/x.py",
                                          "tests/sub/test_b.py"]),
            ["tests.test_a", "tests.sub.test_b"])


if __name__ == "__main__":
    unittest.main()
