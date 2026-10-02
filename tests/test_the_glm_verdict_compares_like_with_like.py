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


if __name__ == "__main__":
    unittest.main()
