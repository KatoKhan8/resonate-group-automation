r"""TASK 0225 - the one thing 36 green tests could not see.

`pilotcaps/0210` planted `STOP_SENDING_PATH` at a SIBLING file in the brake's
own directory - `...resonate-ops\STOP-SENDING-ELSEWHERE`, parent intact - and
all 36 brake tests stayed green. TASK 0225 reproduced that before writing this
module: plant P1 SURVIVED, invisible.

WHY NO CODE RULE CAN CATCH IT, which is why this is a test module and not more
of `haltfile`. "The home is readable and the leaf is absent" is the brake's one
RELEASED state. A sibling path in a readable directory produces exactly that
state, byte for byte. Nothing inside `require_released` can distinguish "the
operator has not pulled the brake" from "I am not looking at the brake",
because both are the same `lstat` outcome. Refusing on absence would make the
brake always-on, which is the same defect facing the other way. So the question
"is this constant the brake?" is answerable only by an independent statement of
what the brake is - and that is this file.

HOW THIS AVOIDS BEING THE 37TH TEST THAT PATCHES THE CONSTANT. It never assigns
to `haltfile.STOP_SENDING_PATH`, never decorates with `mock.patch`, and never
passes a path in. It READS the shipped value and compares it to a literal
written here, independently. That property is evidenced BEHAVIOURALLY rather
than by grepping this file - see
`test_the_value_under_test_is_the_module_attribute_itself` and the measured
denominator in TASK 0225's lane entry.

WHY A SECOND LITERAL IS NOT CIRCULAR. The two literals are in different files
with different reasons to change: `src/haltfile.py` is edited when the brake's
behaviour changes, this file when the brake's LOCATION is deliberately moved.
A rename, a typo or a refactor touches one and not the other, and that is
exactly the drift `0210` measured surviving. Agreement between two independent
statements is the evidence; one statement compared with itself is not.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import haltfile  # noqa: E402

#: What the brake IS, stated here independently of the module under test.
THE_BRAKE = r"C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING"

#: Values that are NOT the brake, every one of which satisfies the properties
#: the old path test asserted (`isabs`, not under ROOT, no
#: "resonate-group-automation") and all but the last of which live in the
#: brake's own directory with the parent intact.
NOT_THE_BRAKE = (
    r"C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING-ELSEWHERE",
    r"C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING.txt",
    r"C:\Users\Zvonimir\Desktop\resonate-ops\STOP_SENDING",
    r"C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING-2026-10-16",
    r"C:\Users\Zvonimir\Desktop\resonate-ops\queue\STOP-SENDING",
    r"C:\Temp\nowhere\BRAKE",
)


def is_the_brake(path):
    """The identity predicate: whole path, case-sensitively, exactly."""
    return path == THE_BRAKE


class TheShippedConstantIsTheBrakeItself(unittest.TestCase):
    """Identity, not shape. The default value, unpatched."""

    def test_the_shipped_constant_is_the_brake_and_not_a_sibling(self):
        self.assertTrue(
            is_the_brake(haltfile.STOP_SENDING_PATH),
            f"the shipped brake constant is {haltfile.STOP_SENDING_PATH!r}, "
            f"which is not the brake {THE_BRAKE!r}. If the brake has been "
            f"deliberately moved, this literal is the second place to change "
            f"and that is the point of it")

    def test_the_predicate_rejects_every_sibling(self):
        """The other half: the assertion above must be able to FAIL.

        Without this, a predicate that returned True for everything would
        pass the test above and prove nothing - which is `B7`, the
        instrument that sees nothing, and this lane audited it.
        """
        for other in NOT_THE_BRAKE:
            with self.subTest(other=other):
                self.assertFalse(
                    is_the_brake(other),
                    f"{other!r} is not the brake but the predicate accepted "
                    f"it, so the identity assertion cannot fail")

    def test_every_sibling_satisfies_the_OLD_assertions(self):
        """Why `isabs` and not-under-ROOT were never enough.

        This is the measured form of 0225's second defect: the properties the
        previous path test asserted are true of paths that are not the brake.
        """
        for other in NOT_THE_BRAKE:
            with self.subTest(other=other):
                self.assertTrue(os.path.isabs(other))
                self.assertFalse(
                    os.path.abspath(other).startswith(
                        os.path.abspath(ROOT) + os.sep))
                self.assertNotIn("resonate-group-automation", other)

    def test_the_value_under_test_is_the_module_attribute_itself(self):
        """Behavioural, not textual. The identity test above is only about
        the DEFAULT if the thing it read is the module's live attribute, so
        that is asserted directly: same object, read through the module.

        An earlier draft of this test grepped this file's own source for
        `patch` and failed on its own forbidden-string list - the exact
        defect CLAUDE.md names, a test that breaks when somebody writes a
        comment. The evidence that no test here patches the constant is
        behavioural and external: the runtime denominator instrument
        (`pilotcaps-0225-denominator.py`) counts how many tests reach
        `require_released` with the shipped value in place, and TASK 0225
        measured that count rising from 4 to 5 when this module landed - plus
        two tests that assert on the constant's VALUE, which no test did
        before. An earlier draft of this docstring said 8; it was a guess and
        the instrument corrected it.
        """
        import src.haltfile as reimported
        self.assertIs(reimported, haltfile)
        self.assertEqual(reimported.STOP_SENDING_PATH, THE_BRAKE)
        self.assertEqual(vars(haltfile)["STOP_SENDING_PATH"], THE_BRAKE)


class TheBrakeIsStillReleasedWhenNothingIsWrong(unittest.TestCase):
    """The control, and it must be able to fail.

    Shipped constant, real home, no brake file: the brake must say GO. A rule
    that refuses here is a brake that is always on - the same bug facing the
    other way, and 0225 names it as NOT MET.
    """

    def test_the_real_brake_file_is_absent_right_now(self):
        """A premise, pinned. If the operator has pulled the brake, the next
        test's expectation is the opposite and the failure below would be
        correct behaviour reported as a fault."""
        self.assertFalse(
            os.path.lexists(THE_BRAKE),
            f"{THE_BRAKE} exists - the operator has pulled the brake. This "
            f"module's control expects it absent; no test may create or "
            f"delete it")

    def test_the_shipped_constant_resolves_to_a_released_brake(self):
        self.assertIsNone(
            haltfile.require_released(),
            "with the shipped constant, a readable home and no brake file, "
            "the brake must release. If this refuses, the home rule has "
            "made the brake always-on")

    def test_the_shipped_home_exists_and_is_a_directory(self):
        """What the home rule depends on, measured rather than assumed."""
        home = os.path.dirname(haltfile.STOP_SENDING_PATH)
        self.assertTrue(os.path.isdir(home),
                        f"the brake's home {home} is not a directory, so the "
                        f"brake could never be determined on this machine")


class AnUndeterminableHomeRefusesByTheRule(unittest.TestCase):
    """0225's fail-closed clause, and WHICH rule fires matters.

    `C:\\Temp\\nowhere\\BRAKE` was already caught before this task - but by the
    winerror-3 leg, an errno accident. These assert the refusal comes from the
    home rule, by reading the reason it gives.
    """

    def setUp(self):
        self.real = haltfile.STOP_SENDING_PATH
        self.addCleanup(setattr, haltfile, "STOP_SENDING_PATH", self.real)

    def test_a_missing_home_refuses_and_names_the_home_rule(self):
        haltfile.STOP_SENDING_PATH = os.path.join(
            ROOT, "no", "such", "home", "STOP-SENDING")
        with self.assertRaises(haltfile.OperatorStop) as caught:
            haltfile.require_released()
        text = str(caught.exception)
        self.assertIn("home rule", text,
                      "the refusal must say it came from the home rule, not "
                      "leave the operator to infer it from an errno")
        self.assertIn("UNKNOWN refuses", text)

    def test_a_home_that_is_a_file_refuses(self):
        haltfile.STOP_SENDING_PATH = os.path.join(
            os.path.abspath(__file__), "STOP-SENDING")
        with self.assertRaises(haltfile.OperatorStop):
            haltfile.require_released()

    def test_a_relative_brake_path_refuses(self):
        """It would resolve against the working directory, which this module's
        own docstring forbids the brake from depending on."""
        haltfile.STOP_SENDING_PATH = os.path.join("resonate-ops",
                                                  "STOP-SENDING")
        with self.assertRaises(haltfile.OperatorStop) as caught:
            haltfile.require_released()
        self.assertIn("not absolute", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
