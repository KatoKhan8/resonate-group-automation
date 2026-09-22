"""A dispatch that exits 127 must never read as a completed run.

This suite exists because one did. On 2026-09-22 a background task reported
"completed" while its inner command exited 127, and the reply walk it was meant
to finish had not advanced a page. The tests below are written against that
failure rather than against the happy path.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import dispatch  # noqa: E402


class TestTheInterpreterIsCarriedNotLookedUp(unittest.TestCase):

    def test_interpreter_is_the_running_binary(self):
        """The only answer that cannot be stale is the one executing this."""
        self.assertEqual(dispatch.interpreter(), sys.executable)
        self.assertTrue(os.path.exists(dispatch.interpreter()))

    def test_every_forbidden_spelling_is_refused(self):
        """`py -3`, `python` and friends are PATH lookups, and one returned 127."""
        for spelling in ("python", "python3", "py", "PYTHON", "python.exe"):
            with self.subTest(spelling=spelling):
                with self.assertRaises(dispatch.DispatchFailed) as caught:
                    dispatch.argv_for([spelling, "-c", "pass"])
                self.assertIn("PATH lookup", str(caught.exception))

    def test_a_plain_script_is_led_by_the_resolved_interpreter(self):
        argv = dispatch.argv_for("scripts/whatever.py")
        self.assertEqual(argv[0], sys.executable)
        self.assertEqual(argv[1], "scripts/whatever.py")

    def test_an_empty_command_is_refused(self):
        with self.assertRaises(dispatch.DispatchFailed):
            dispatch.argv_for([])


class TestExit127IsAFaultNotAResult(unittest.TestCase):

    def test_127_raises_with_the_command_echoed(self):
        """The defining case. 127 means nothing ran, so it cannot be a result."""
        with self.assertRaises(dispatch.DispatchFailed) as caught:
            dispatch.run(["-c", "import sys; sys.exit(127)"], echo=False)
        message = str(caught.exception)
        self.assertIn("EXIT 127", message)
        self.assertIn("NOTHING RAN", message)
        self.assertIn("-c", message, "the command must be echoed to be reproducible")

    def test_127_raises_even_when_check_is_off(self):
        """`check=False` licenses a meaningful non-zero, never a missing command."""
        with self.assertRaises(dispatch.DispatchFailed):
            dispatch.run(["-c", "import sys; sys.exit(127)"],
                         check=False, echo=False)

    def test_an_ordinary_non_zero_is_returned_not_raised_when_unchecked(self):
        """A red suite is a result. It must stay distinguishable from 127."""
        proc = dispatch.run(["-c", "import sys; sys.exit(3)"],
                            check=False, echo=False)
        self.assertEqual(proc.returncode, 3)

    def test_a_successful_dispatch_returns_its_output(self):
        proc = dispatch.run(["-c", "print('ran')"], echo=False)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("ran", proc.stdout)


class TestTheInterpreterIsRecordedForTheHandoff(unittest.TestCase):

    def test_record_writes_the_resolved_interpreter(self):
        data = dispatch.record_interpreter()
        self.assertEqual(data["interpreter"], sys.executable)
        self.assertTrue(os.path.exists(dispatch.RECORD))

    def test_the_handoff_line_names_the_interpreter_and_the_suite(self):
        line = dispatch.handoff_line()
        self.assertIn(sys.executable, line)
        self.assertIn("unittest", line)
        self.assertNotIn("py -3", line)


if __name__ == "__main__":
    unittest.main()
