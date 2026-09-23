"""No test module may leave the environment changed, and this says who did.

THE ALARM, not the repair. `tests/envisolation.py` restores the environment
between modules, so a leak can no longer change what the next module sees.
This is the test that stops the repair from being the end of the story: an
auto-restore with nothing watching it is a leak that merely stopped being
visible, and the next one gets written because nothing objected to the last.

It fails NAMING THE MODULE AND THE VARIABLE, with the value it was left at,
because "test_x leaks" is not something anybody can act on and
"test_x leaves QUEUE set to C:\\...\\tmp3s_6i24q\\queue.jsonl" is.

WHY IT RUNS LAST, AND WHAT THAT COSTS. It can only report modules that have
already run, so `tests/__init__.py` appends it to the end of the assembled
suite explicitly rather than relying on its filename sorting last. Two
consequences, stated rather than discovered later:

  * Run on its own (`python -m unittest tests.test_no_...`) it sees an empty
    record and passes. That is a pass about nothing. `test_the_record_is_only
    _meaningful_after_a_full_run` says so in the output.
  * Run under `python -m unittest tests.test_a tests.test_b`, the package's
    `load_tests` is not used at all, so neither the isolation nor this guard
    is in play.

WHAT IT DOES NOT COVER, said out loud so a green run is not read as more than
it is. TASK-264 names three kinds of leak and this covers the first:

  1. environment variables            - covered, entirely, by snapshot
  2. a module cached at import time   - NOT covered
  3. a shared temp directory          - NOT covered

The 2026-09-23 measurement found three order-dependent failures. One,
`test_slack_agent_cannot_act`, is kind 1 and is fixed. The two in
`test_multi_client_isolation` were NOT reproduced by setting any of the
fourteen leaked values by hand, so they are kind 2 or kind 3 and this guard
will stay green while they stay broken. A guard that is quiet about what it
does not watch is the ISSUE-006 mechanism, and this register has paid for it
twice.
"""
import os
import unittest

from . import envisolation


class NoModuleLeavesTheEnvironmentChanged(unittest.TestCase):

    def test_no_module_left_a_variable_set(self):
        """Every leak, named, with the value it was left at."""
        if not envisolation.LEAKS:
            return

        lines = []
        for leak in envisolation.LEAKS:
            for name, was, now in leak["changed"]:
                lines.append(
                    "%s\n        %s\n        was: %r\n        now: %r" % (
                        leak["module"], name, was, now))

        self.fail(
            "%d module(s) left the environment changed. The harness put it "
            "back, so nothing downstream broke - but each of these is a "
            "module whose own teardown does not undo its own setup, and the "
            "next one will not be caught by luck.\n\n"
            "Fix the module, not this test: save and restore in tearDown, or "
            "`self.addCleanup(store.use_directory(tmp))`, which returns the "
            "restore for exactly this.\n\n    %s"
            % (len({l["module"] for l in envisolation.LEAKS}),
               "\n    ".join(lines)))

    def test_the_record_is_only_meaningful_after_a_full_run(self):
        """A pass here is a pass about nothing unless modules actually ran.

        Without this, running this module alone gives a green
        `test_no_module_left_a_variable_set` - a guard reporting clean because
        it watched nothing, which is the exact defect the guard exists to
        prevent somebody else committing.
        """
        ran = len(envisolation.LEAKS)
        self.assertIsInstance(ran, int)
        if ran == 0:
            print("\n[env guard] no leaks recorded. If this was not a full "
                  "suite run, that is a pass about nothing: the record is "
                  "populated by tests/__init__.py's load_tests, which only "
                  "runs under discovery.")


class TheIsolationItselfWorks(unittest.TestCase):
    """TASK-264 requirement 2: poison a variable, run a test, prove it is put
    back. Proving the mechanism rather than trusting it, because the mechanism
    is the only reason the other test above can be believed."""

    def setUp(self):
        self._saved = dict(os.environ)
        self.addCleanup(envisolation.restore, self._saved)
        self._leaks_before = list(envisolation.LEAKS)
        self.addCleanup(self._put_leaks_back)

    def _put_leaks_back(self):
        envisolation.LEAKS[:] = self._leaks_before

    def _a_module_that_leaks(self, var, value):
        class Leaks(unittest.TestCase):
            def runTest(inner):                      # noqa: N805
                os.environ[var] = value
        return envisolation.Isolated([Leaks()], "tests.fake_leaking_module")

    def test_a_variable_set_by_a_test_is_put_back(self):
        os.environ.pop("RGA_ENV_GUARD_PROBE", None)
        suite = self._a_module_that_leaks("RGA_ENV_GUARD_PROBE", "poisoned")

        result = unittest.TestResult()
        suite.run(result)

        self.assertEqual(result.errors, [])
        self.assertIsNone(
            os.environ.get("RGA_ENV_GUARD_PROBE"),
            "the harness did not put the environment back")

    def test_a_variable_the_test_changed_is_put_back_to_its_old_value(self):
        os.environ["RGA_ENV_GUARD_PROBE"] = "original"
        suite = self._a_module_that_leaks("RGA_ENV_GUARD_PROBE", "poisoned")

        suite.run(unittest.TestResult())

        self.assertEqual(os.environ.get("RGA_ENV_GUARD_PROBE"), "original",
                         "restore set the variable to absent rather than to "
                         "the value it had")

    def test_the_leak_is_recorded_and_names_the_module_and_the_variable(self):
        os.environ.pop("RGA_ENV_GUARD_PROBE", None)
        suite = self._a_module_that_leaks("RGA_ENV_GUARD_PROBE", "poisoned")

        suite.run(unittest.TestResult())

        self.assertTrue(envisolation.LEAKS, "the leak was silently repaired")
        last = envisolation.LEAKS[-1]
        self.assertEqual(last["module"], "tests.fake_leaking_module")
        self.assertIn(("RGA_ENV_GUARD_PROBE", None, "poisoned"),
                      last["changed"])

    def test_a_module_that_leaves_the_environment_alone_records_nothing(self):
        """The recorder must not report every module as a leak."""
        class Clean(unittest.TestCase):
            def runTest(inner):                      # noqa: N805
                pass

        before = len(envisolation.LEAKS)
        envisolation.Isolated([Clean()], "tests.fake_clean_module").run(
            unittest.TestResult())
        self.assertEqual(len(envisolation.LEAKS), before)

    def test_class_teardown_runs_before_the_snapshot_is_compared(self):
        """The defect the first version of the harness shipped.

        `unittest` defers `tearDownClass` to the start of the NEXT module. A
        wrapper that compares and restores without flushing it would record
        this module as clean, and then run its teardown inside the following
        module's window - attributing this module's restore to that one, and
        stopping `webbase`'s live HTTP server a module late.
        """
        os.environ.pop("RGA_ENV_GUARD_PROBE", None)

        class TearsDownLate(unittest.TestCase):
            @classmethod
            def tearDownClass(cls):
                os.environ["RGA_ENV_GUARD_PROBE"] = "set-in-teardown"

            def runTest(inner):                      # noqa: N805
                pass

        suite = envisolation.Isolated([TearsDownLate()],
                                      "tests.fake_late_teardown_module")
        result = unittest.TestResult()
        suite.run(result)

        self.assertEqual(result.errors, [])
        self.assertIsNone(
            os.environ.get("RGA_ENV_GUARD_PROBE"),
            "tearDownClass ran after the restore, so its write survived")
        self.assertEqual(
            envisolation.LEAKS[-1]["module"], "tests.fake_late_teardown_module",
            "the teardown's write was attributed to the wrong module")

    def test_the_environment_is_restored_even_when_the_test_errors(self):
        """The module most likely to leak is the one that blew up."""
        class Explodes(unittest.TestCase):
            def runTest(inner):                      # noqa: N805
                os.environ["RGA_ENV_GUARD_PROBE"] = "poisoned"
                raise RuntimeError("boom")

        os.environ.pop("RGA_ENV_GUARD_PROBE", None)
        result = unittest.TestResult()
        envisolation.Isolated([Explodes()], "tests.fake_exploding_module").run(
            result)

        self.assertEqual(len(result.errors), 1)
        self.assertIsNone(os.environ.get("RGA_ENV_GUARD_PROBE"),
                          "an erroring module kept its leak")


class TheSuiteIsAssembledWithIsolation(unittest.TestCase):
    """If `load_tests` ever stops wrapping, the guard above goes quiet and
    every leak comes back. That would be invisible, so it is asserted."""

    def test_load_tests_wraps_every_module_and_keeps_them_all(self):
        import unittest as ut

        from tests import load_tests

        loader = ut.TestLoader()
        suite = load_tests(loader, ut.TestSuite(), None)

        children = list(suite)
        self.assertTrue(children, "load_tests assembled an empty suite")
        self.assertTrue(
            all(isinstance(c, envisolation.Isolated) for c in children),
            "a module was added to the suite without isolation")

        expected = len([f for f in os.listdir(os.path.dirname(__file__))
                        if f.startswith("test_") and f.endswith(".py")])
        self.assertEqual(
            len(children), expected,
            "load_tests assembled %d module(s) and there are %d on disk - a "
            "suite that silently runs fewer tests than exist is the failure "
            "this file exists to refuse" % (len(children), expected))

    def test_the_guard_module_is_assembled_last(self):
        import unittest as ut

        from tests import load_tests

        suite = load_tests(ut.TestLoader(), ut.TestSuite(), None)
        self.assertEqual(
            list(suite)[-1].module,
            "tests.test_no_test_leaves_the_environment_changed")


if __name__ == "__main__":
    unittest.main()
