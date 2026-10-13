"""A control counts as existing only if its SCOPE cannot exempt its subject.

Earned 2026-10-13. `test_invariants.TestNothingCanSend
.test_no_module_issues_an_http_post_outside_the_named_ones` filtered its
offenders with `not any(a in p for a in allowed)` where `p` is the
ABSOLUTE path from `source_files()`. `slack` is one of the allowed
provider tokens, the worktree was `.../scratchpad/wt-slack-24h`, and so:

    exempt from a path containing "slack"   258 of 258  (100%)
    exempt from a neutral path               25 of 258  ( 10%)

The guard reported green while guarding nothing, and a completed 1,879
second suite run had to be discarded as void. `test_audit` carried the
same filter.

So this file tests the SCOPE rather than the subject. It asks one
question: can any directory name a person, a worktree tool or a CI runner
might choose change which files the guard covers? The answer must be no,
for every allowed token, and the proof is a measurement rather than an
argument about `os.path`.

It is deliberately cheap and hermetic - synthetic path prefixes, no
worktrees created - because a control that costs nine checkouts to run is
a control nobody runs. The end-to-end proof with a real worktree is
recorded in the branch's report; this is the part that runs on every
suite.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from tests import guardscope
except ImportError:                                 # pragma: no cover
    import guardscope

#: The allowlists the two guards actually use. Copied as DATA rather than
#: imported from the test modules, because importing a `test_`-prefixed
#: sibling registers it twice in the assembled suite - measured at 697
#: children against 696 files on disk.
PROVIDER_TOKENS = ("aiark", "apify", "blitz", "bison", "contactout", "glm",
                   "heyreach", "slack", "xai")

#: Directory names a person might plausibly choose. Each contains an
#: allowed token, which is the entire hazard.
HOSTILE_PREFIXES = tuple(
    os.path.join("C:\\", "work", "wt-%s-review" % token)
    for token in PROVIDER_TOKENS
) + (
    os.path.join("C:\\", "Users", "someone", "slack-agent", "repo"),
    os.path.join("/home", "ci", "builds", "bison-nightly", "src"),
    os.path.join("/tmp", "glm-940", "checkout"),
)

NEUTRAL_PREFIX = os.path.join("C:\\", "neutral", "checkout")

#: A representative file list: the real repository's own source files.
def source_paths():
    src = os.path.join(ROOT, "src")
    out = []
    for base, dirs, names in os.walk(src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        out.extend(os.path.join(base, n) for n in names
                   if n.endswith(".py"))
    return sorted(out)


def rerooted(paths, prefix):
    """The same files as if the checkout lived under `prefix`."""
    return [os.path.join(prefix, os.path.relpath(p, ROOT)) for p in paths]


class TheScopeIsIndependentOfWhereTheCheckoutLives(unittest.TestCase):

    def setUp(self):
        self.paths = source_paths()
        self.assertGreater(len(self.paths), 100,
                           "the file list is too small to be meaningful")

    def test_every_hostile_prefix_exempts_exactly_what_neutral_does(self):
        """THE CONTROL FOR THE CONTROL.

        One number per prefix, and they must all be the same number.
        """
        neutral = guardscope.exempt_count(
            rerooted(self.paths, NEUTRAL_PREFIX), PROVIDER_TOKENS)
        for prefix in HOSTILE_PREFIXES:
            got = guardscope.exempt_count(
                rerooted(self.paths, prefix), PROVIDER_TOKENS)
            self.assertEqual(
                got, neutral,
                "a checkout at %r exempts %d files where a neutral path "
                "exempts %d - the guard's scope moved with its own location"
                % (prefix, got, neutral))

    def test_the_exempt_SET_is_identical_not_merely_the_count(self):
        """A count can match while the membership differs.

        This repository has already been caught by that once: three
        finished suites each reported exactly 231 failing names and one of
        them was a different 231.
        """
        def names(prefix):
            moved = rerooted(self.paths, prefix)
            return {os.path.basename(p) for p in moved
                    if guardscope.is_exempt(p, PROVIDER_TOKENS)}

        neutral = names(NEUTRAL_PREFIX)
        for prefix in HOSTILE_PREFIXES:
            self.assertEqual(names(prefix), neutral,
                             "the exempt SET changed under %r" % (prefix,))

    def test_the_old_absolute_filter_really_was_broken(self):
        """THE POSITIVE CONTROL, and the whole justification.

        If the absolute-path filter had been harmless, the two tests above
        would pass under it too and this change would be noise. It is not
        harmless: under the old rule a hostile prefix exempts EVERYTHING.
        """
        neutral_old = sum(
            1 for p in rerooted(self.paths, NEUTRAL_PREFIX)
            if any(t in p for t in PROVIDER_TOKENS))
        worst = 0
        for prefix in HOSTILE_PREFIXES:
            moved = rerooted(self.paths, prefix)
            old = sum(1 for p in moved
                      if any(t in p for t in PROVIDER_TOKENS))
            worst = max(worst, old)
        self.assertEqual(
            worst, len(self.paths),
            "the old absolute filter did NOT exempt everything under a "
            "hostile prefix (%d of %d), so this file's premise is wrong - "
            "reread it" % (worst, len(self.paths)))
        self.assertLess(
            neutral_old, len(self.paths),
            "even a neutral path exempted everything under the old rule, "
            "which would mean the guard never worked at all")

    def test_no_directory_component_can_widen_it(self):
        """Not just the prefix: a directory INSIDE the repo cannot either.

        `src/slack/thing.py` must not become exempt because of its folder.
        """
        for token in PROVIDER_TOKENS:
            inside = os.path.join(ROOT, "src", token, "thing.py")
            self.assertFalse(
                guardscope.is_exempt(inside, PROVIDER_TOKENS),
                "a directory named %r exempted %r" % (token, inside))
            named = os.path.join(ROOT, "src", "providers",
                                 "%s.py" % token)
            self.assertTrue(
                guardscope.is_exempt(named, PROVIDER_TOKENS),
                "the real provider module %r is no longer exempt - the fix "
                "went too far" % (named,))


class EveryMeasurementRecordsWhereItRan(unittest.TestCase):
    """The process half of the rule: a run whose path could have altered
    the measurement must be identifiable afterwards.

    This asserts the helper exists and reports a usable absolute path, so
    a report can carry it. It does not assert any particular runner writes
    it - that is a reporting convention, not a code property, and claiming
    otherwise would be the "existence is not function" defect.
    """

    def test_the_running_worktree_path_is_discoverable(self):
        self.assertTrue(os.path.isabs(ROOT))
        self.assertTrue(os.path.isdir(os.path.join(ROOT, "src")))

    def test_and_this_run_declares_whether_its_path_was_hazardous(self):
        hazard = [t for t in PROVIDER_TOKENS if t in ROOT.lower()]
        # NOT an assertion that the path is clean - a suite may legitimately
        # run from anywhere now that the scope is basename-only. It records
        # the fact so a reader can tell, which is the point of the rule.
        self.assertIsInstance(hazard, list)
        if hazard:
            print("\nNOTE: this run's worktree path contains %r. Under the "
                  "basename rule that no longer changes the measurement, "
                  "which is what the tests above prove." % (hazard,))


if __name__ == "__main__":
    unittest.main()
