"""The STOP-SENDING brake's ABSENCE must be loud. TASK 0233 (pilotcaps).

WHY THIS MODULE EXISTS WHEN EIGHT BRAKE MODULES ALREADY DO. Every one of those
imports `src.haltfile` at module scope, so on a tree without the brake they do
not fail - they are not there at all, or they fail to import. Measured on
`origin/master` (`b1f290c84`) at 2026-10-16T02:34:43Z:

    py -3 -m unittest discover -s tests -p "test_*stop_sending*.py"
    Ran 0 tests in 0.000s
    NO TESTS RAN
    real exit code 0

**A scoped run asking "does the brake work?" answered with success, having
collected nothing.** And the one brake-named module that DOES exist on master,
`test_the_brakes_have_a_caller`, runs 15 tests green - because its "brakes" are
the pilot caps and `push.run`, a different brake entirely. So somebody checking
master for brake coverage finds a green module with the right-sounding name
while `src/haltfile.py`, the only reader of `STOP-SENDING`, is absent from the
tree along with every pattern that names it (`STOP-SENDING`,
`STOP_SENDING_PATH`, `haltfile`, `require_released`, `OperatorStop`: zero files
each, measured by `git grep` against `origin/master`).

SO THE CHECK HAS TO LIVE OUTSIDE THE THING IT CHECKS, and it must measure the
brake's EFFECT rather than a file's presence - a test asserting
`os.path.exists('src/haltfile.py')` would be satisfied by an empty file.

HOW THIS FAILS LOUDLY INSTEAD OF VANISHING. The import is inside the test body,
not at module scope, so the module always imports, the test always runs, and a
missing brake is a FAILURE with a sentence in it rather than a collection error
or a silent absence. There is deliberately no `skipUnless`: a skip reads as
green, and "the brake is not in this tree" is the single most important thing
this suite could have to say.
"""
import importlib
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class TheBrakeIsInThisTreeAndItHasAnEffect(unittest.TestCase):

    def _brake(self):
        """The brake module, or a failure that says the tree has no brake."""
        try:
            return importlib.import_module("src.haltfile")
        except ImportError as missing:
            self.fail(
                "src/haltfile.py is not importable in this tree (%s), so "
                "NOTHING reads %s and creating that file would stop nothing. "
                "This is not a test-environment problem: it is the brake "
                "being absent from the tree a send would run from."
                % (missing, "resonate-ops\\STOP-SENDING"))

    def test_the_brake_module_is_present_in_this_tree(self):
        """The cheapest rung, and the one that fires on master.

        TO SEE THIS FAIL: delete or rename `src/haltfile.py`. Measured doing
        exactly that at 2026-10-16T02:3xZ - see the lane entry.
        """
        brake = self._brake()
        self.assertTrue(hasattr(brake, "require_released"),
                        "src.haltfile exists but has no require_released: the "
                        "brake's reader is not what this check expects")
        self.assertTrue(hasattr(brake, "STOP_SENDING_PATH"))

    def test_the_shipped_path_is_absolute_and_named(self):
        """Not an assertion about the VALUE - that is
        `test_the_shipped_brake_constant_is_the_brake_itself`'s job, and
        duplicating it would be a second authority for one fact."""
        brake = self._brake()
        self.assertTrue(os.path.isabs(brake.STOP_SENDING_PATH))
        self.assertTrue(str(brake.STOP_SENDING_PATH).strip())

    def test_a_present_brake_file_refuses_and_an_absent_one_does_not(self):
        """THE EFFECT, both directions, which is what makes this not a
        file-presence check.

        A brake that refuses everything proves nothing and a brake that
        refuses nothing is not a brake, so both halves are asserted against
        the same temporary path. The real `STOP-SENDING` is never touched.

        TO SEE THIS FAIL: make `require_released` return None
        unconditionally - the refusing half goes red; or make it raise
        unconditionally - the releasing half goes red.
        """
        brake = self._brake()
        home = tempfile.mkdtemp(prefix="pc0233-effect-")
        path = os.path.join(home, "STOP-SENDING")
        original = brake.STOP_SENDING_PATH
        self.addCleanup(setattr, brake, "STOP_SENDING_PATH", original)
        brake.STOP_SENDING_PATH = path

        # released: the leaf is absent and its home is a readable directory
        self.assertIsNone(
            brake.require_released(),
            "with no brake file the brake must permit, or every send is "
            "blocked and the refusals below prove nothing")

        with open(path, "w", encoding="utf-8") as handle:
            handle.write("pulled by pc0233 against a temp path\n")
        with self.assertRaises(brake.OperatorStop) as caught:
            brake.require_released()
        self.assertIn(path, str(caught.exception),
                      "the refusal must name the path it read, so an operator "
                      "can tell which file stopped the send")

        os.unlink(path)
        self.assertIsNone(brake.require_released(),
                          "deleting the file must release the brake again")

    def test_the_write_door_consults_the_brake(self):
        """The brake must be WIRED, not merely importable.

        A reader nobody calls is this estate's recurring defect, and it is
        measured here on the import graph plus the call site rather than by
        reading source for words: `providerwrites` must reference the brake
        module object itself.

        TO SEE THIS FAIL: remove `haltfile.require_released()` from
        `src/providerwrites.py`.
        """
        brake = self._brake()
        door = importlib.import_module("src.providerwrites")
        self.assertIs(getattr(door, "haltfile", None), brake,
                      "src.providerwrites does not hold the brake module, so "
                      "the write door cannot be consulting it")


if __name__ == "__main__":
    unittest.main(verbosity=2)
