"""The write-bypass guard's own comparison, measured against a planted tree.

WHY THIS MODULE EXISTS, AND IT IS NOT ORDINARY COVERAGE. TASK 0233 (2026-10-16)
mutated `tests/test_no_new_write_bypasses_the_door.py:132` - the
`set(self.counts) - set(self.known)` that decides whether a new ungated
provider write has appeared - to always-match, and measured the kill-set
against the committed suite as **0 of 10**. No test planted a bypass, so the
one comparison the merge gate rests on was watched by nothing: anyone could
neuter it and every gate in this estate would stay green.

That is this repository's own signature defect - an instrument that reports
PASS because it is looking at nothing - sitting on the guard whose whole job is
to catch it.

HOW IT IS CLOSED, AND WHY IT IS NOT CLOSED BY RE-DERIVING THE COMPARISON HERE.
A copy of `set(a) - set(b)` written in this file would be green in both worlds:
mutate the guard's line and this module would never notice, because it would be
comparing with its own arithmetic. So this module does not reimplement the
comparison - it CALLS the guard's own test methods, with `counts` and `known`
injected from a synthetic tree, and records whether each one raised. The code
under test is literally the guard's line, which is the only arrangement in
which the C4 mutation can be seen.

WHY A TEMP TREE RATHER THAN A PLANT IN THE REPOSITORY. The analyzer is already
root-parameterised - `mutating_functions(root)` and `call_sites(root, writers)`
both take a tree - so a plant can live in `tempfile.mkdtemp()`, outside the
repository entirely. Nothing in `src/` or `tests/` is touched, no plant has to
be reverted, and `test_fixture_hygiene`'s corpus (which includes untracked
files) never sees it.

THE THREE VERDICTS, because one of them is not the one a reader expects. The
baseline is keyed `file::function::call` and deliberately not by line, so:
  * a NEW key              -> `test_no_bypassing_call_site_is_new` raises, and
                              its message names the full key;
  * an ACCEPTED key MOVED
    within its own function -> green, at a different line number;
  * an ACCEPTED key gaining
    a SECOND occurrence     -> `test_no_existing_site_gained_occurrences`
                              raises. An accepted key does not buy unlimited
                              occurrences at it.
The first and third both take BYPASS from one to two - the SAME total - and
produce DIFFERENT names. That is the property a counting guard cannot have, and
it is why 0233's note that `97fec582d` moved a key while the count stayed 26 on
both sides matters: totals are not the assertion here, keys are.

WHAT THIS MODULE DOES NOT DO. It takes no view on whether any real site in
`scripts/known_write_bypasses.json` should be gated - that is the operator's B
decision - and it does not read the real baseline at all. Its baseline is
derived from its own unplanted fixture, so it cannot drift with the repository
and cannot be made green by regenerating anything.
"""
import collections
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYZER = os.path.join(ROOT, "scripts", "write_path_denominator.py")
GUARD = os.path.join(ROOT, "tests", "test_no_new_write_bypasses_the_door.py")

#: The fixture's own file name inside the temp tree. Keys below are built from
#: it, so the assertions name a full `file::function::call` key and not a
#: fragment of one.
FIXTURE = "scripts/planted_write.py"

#: Two verbs the guard's OWN positive control already pins
#: (`test_known_write_verbs_are_found`), so this fixture cannot be the reason a
#: verb stops being recognised.
ACCEPTED_KEY = FIXTURE + "::accepted_bypass::bison.resume_campaign"
PLANTED_KEY = FIXTURE + "::freshly_planted::bison.create_campaign"

_PREAMBLE = '''"""Synthetic fixture for the write-bypass guard's self-test.

Written into a temp tree by tests/test_the_write_bypass_guard_can_see_a_plant.
NEVER imported and NEVER executed - the analyzer only `ast.parse`s it.
"""
import bison
import providerwrites
'''

#: One ungated write (so the fixture has a bypass the synthetic baseline can
#: accept) and one gated write (so the fixture is not degenerate in the one
#: direction that would make every assertion below vacuous - a tree with no
#: gated writes at all would mean the classifier had stopped classifying).
_BASE = '''

def accepted_bypass(campaign):
    bison.resume_campaign(campaign)


def already_gated(campaign, token):
    providerwrites.perform(token, transport=lambda: bison.pause_campaign(campaign))
'''

#: A new enclosing function with no `perform` anywhere in it. This is the shape
#: the guard exists to catch.
_NEW_KEY = '''

def freshly_planted(payload):
    bison.create_campaign(payload)
'''

#: The accepted write, same function, further down it. The key is unchanged and
#: the line number is not.
_MOVED = '''

def accepted_bypass(campaign):
    note = "this write moved down inside its own function"
    del note
    bison.resume_campaign(campaign)


def already_gated(campaign, token):
    providerwrites.perform(token, transport=lambda: bison.pause_campaign(campaign))
'''

#: A second ungated write at a key the baseline already accepts at one.
_SECOND_OCCURRENCE = '''

def accepted_bypass(campaign):
    bison.resume_campaign(campaign)
    bison.resume_campaign(campaign + 1)


def already_gated(campaign, token):
    providerwrites.perform(token, transport=lambda: bison.pause_campaign(campaign))
'''


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TheWriteBypassGuardCanSeeAPlant(unittest.TestCase):
    """The guard's comparison, run against trees this module builds."""

    @classmethod
    def setUpClass(cls):
        cls.analyzer = _load(ANALYZER, "write_path_denominator_for_the_plant")
        cls.guard = _load(GUARD, "write_bypass_guard_under_test")

    def setUp(self):
        self.tree = tempfile.mkdtemp(prefix="write_bypass_plant_")
        self.addCleanup(shutil.rmtree, self.tree, True)
        providers = os.path.join(self.tree, "src", "providers")
        os.makedirs(providers)
        os.makedirs(os.path.join(self.tree, "scripts"))
        for module in ("bison", "heyreach"):
            shutil.copyfile(
                os.path.join(ROOT, "src", "providers", module + ".py"),
                os.path.join(providers, module + ".py"))

    def _write_fixture(self, body):
        path = os.path.join(self.tree, *FIXTURE.split("/"))
        with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(_PREAMBLE + body)

    def _measure(self, body):
        """`(counts, rows)` for the temp tree, exactly as the guard measures."""
        self._write_fixture(body)
        writers = self.analyzer.mutating_functions(self.tree)
        rows = self.analyzer.call_sites(self.tree, writers)
        counts = collections.Counter(
            "%s::%s::%s" % (rel, where, call)
            for verdict, rel, _line, call, where in rows if verdict == "BYPASS")
        return counts, rows

    def _verdict(self, method, counts, known):
        """Run ONE of the guard's own test methods against injected state.

        Returns its assertion message when it fails and `None` when it passes.
        Calling the guard's method is the whole point: a comparison re-derived
        in this file would not move when the guard's own line was mutated.
        """
        case = self.guard.NoNewWriteBypassesTheDoor(method)
        case.counts = counts
        case.known = known
        case.baseline = {"sites": dict(known),
                         "total_bypassing_call_sites": sum(known.values())}
        try:
            getattr(case, method)()
        except AssertionError as failure:
            return str(failure)
        return None

    def test_the_fixture_tree_is_what_this_module_claims_it_is(self):
        """Signs of life, before any verdict below is believed.

        A fixture that produced no bypass, or that leaked the real repository
        into the measurement, would make every assertion here vacuous in a way
        that looks exactly like a passing test.
        """
        counts, rows = self._measure(_BASE)
        verdicts = collections.Counter(verdict for verdict, *_ in rows)
        self.assertEqual({ACCEPTED_KEY: 1}, dict(counts),
                         "the unplanted fixture is not the one tree this "
                         "module reasons about")
        self.assertGreater(verdicts["gated"], 0,
                           "the fixture has no gated write, so the classifier "
                           "is answering one way for everything")
        for key in counts:
            self.assertTrue(
                key.startswith(FIXTURE),
                "%s came from outside the temp tree, so the analyzer is not "
                "root-parameterised and this module is measuring the "
                "repository" % key)

    def test_a_new_bypassing_key_is_caught_and_named(self):
        """THE ONE THAT WATCHES THE GUARD'S COMPARISON."""
        known = self._measure(_BASE)[0]
        counts = self._measure(_BASE + _NEW_KEY)[0]
        self.assertEqual({ACCEPTED_KEY: 1, PLANTED_KEY: 1}, dict(counts),
                         "the planted tree is not the one this test reasons "
                         "about")
        message = self._verdict("test_no_bypassing_call_site_is_new",
                                counts, known)
        self.assertIsNotNone(
            message,
            "a NEW ungated provider write at %s did not move the guard's "
            "comparison. The guard cannot see a 27th bypass, and the merge "
            "gate reads this guard." % PLANTED_KEY)
        self.assertIn(
            PLANTED_KEY, message,
            "the guard went red without naming the plant, so a reader cannot "
            "tell which write appeared. Message was:\n%s" % message)
        self.assertNotIn(
            ACCEPTED_KEY, message,
            "the guard named an ALREADY-ACCEPTED key as new, so it is "
            "reporting the whole set rather than the difference. Message "
            "was:\n%s" % message)

    def test_an_accepted_write_moved_within_its_function_stays_green(self):
        """Keyed by function, not by line - so an unrelated edit cannot churn.

        Without this, the test above proves a guard that fires, not a guard
        that discriminates.
        """
        known, base_rows = self._measure(_BASE)
        counts, moved_rows = self._measure(_MOVED)
        self.assertEqual(dict(known), dict(counts),
                         "moving an accepted write inside its own function "
                         "changed the key set")
        before = [line for verdict, rel, line, call, where in base_rows
                  if verdict == "BYPASS"]
        after = [line for verdict, rel, line, call, where in moved_rows
                 if verdict == "BYPASS"]
        self.assertNotEqual(
            before, after,
            "the write did not actually move, so this test would pass for a "
            "guard that WAS keyed by line")
        for method in ("test_no_bypassing_call_site_is_new",
                       "test_no_existing_site_gained_occurrences",
                       "test_the_baseline_has_not_fallen_behind_the_code"):
            self.assertIsNone(
                self._verdict(method, counts, known),
                "%s went red for an accepted write that only changed line "
                "number" % method)

    def test_a_second_occurrence_at_an_accepted_key_is_caught(self):
        """An accepted key does not buy unlimited occurrences at it.

        This and `test_a_new_bypassing_key_is_caught_and_named` both take
        BYPASS from one to two - the same total - and are caught by DIFFERENT
        tests. A guard comparing totals could not tell them apart.
        """
        known = self._measure(_BASE)[0]
        counts = self._measure(_SECOND_OCCURRENCE)[0]
        self.assertEqual({ACCEPTED_KEY: 2}, dict(counts),
                         "the fixture did not gain a second occurrence at the "
                         "accepted key")
        self.assertIsNone(
            self._verdict("test_no_bypassing_call_site_is_new",
                          counts, known),
            "a second occurrence at an accepted key is not a NEW key, so it "
            "must not be reported as one")
        message = self._verdict("test_no_existing_site_gained_occurrences",
                                counts, known)
        self.assertIsNotNone(
            message,
            "%s gained a second ungated write and the guard stayed green"
            % ACCEPTED_KEY)
        self.assertIn(ACCEPTED_KEY, message, message)

    def test_a_bypass_that_disappears_is_caught_in_the_other_direction(self):
        """The baseline cannot silently become a list of things that are gone."""
        known = self._measure(_BASE + _NEW_KEY)[0]
        counts = self._measure(_BASE)[0]
        message = self._verdict(
            "test_the_baseline_has_not_fallen_behind_the_code", counts, known)
        self.assertIsNotNone(
            message,
            "a recorded bypass vanished from the tree and the guard stayed "
            "green, so the baseline can drift into naming absent keys")
        self.assertIn(PLANTED_KEY, message, message)


if __name__ == "__main__":
    unittest.main()
