"""A LinkedIn step that does not say what it IS must fail closed.

THE DEFECT, measured on master 2bf7b8a5.

`lint.is_connection_note` decided "note or message" with

    return (step or {}).get("requires") not in CONNECTED_STATES

so ABSENCE of `requires` answered "this is a connection request". Absence is
not a declaration. It is the state of every step the campaign writer emits:
`generate_campaign` builds `result["sequences"]["li1".."li5"]` as BARE
STRINGS (see `src/generate_campaign.py`, the `for key in
LINKEDIN_WRITER_KEYS` loop), and whoever turns those strings into a step for
linting has no `requires` to put on them. So all five lint as connection
requests.

WHY THAT IS NOT A COSMETIC MISCLASSIFICATION. Lint-for-a-note and
lint-for-a-message are different doors with different numbers. Against the
measured contract in `docs/second-brain/linkedin.md` S14.3:

    li1  connection request   floor UNKNOWN (no measured floor)  ceiling 300
    li2  first message        floor 100  target 125  ceiling 299
    li3+ follow-up            floor 100  target 173  ceiling 299

A message that is misread as a connection request is therefore let through
with NO CONTRACT FLOOR and a 300 ceiling, where the cadence intends 100-299.
The wrong door does not merely mislabel the step; it applies the wrong
numbers, in the looser direction, to the half of the cadence that does the
persuading.

THE FIX IS NOT "GUESS BETTER". It is that the step must DECLARE its operation
- `connection_request` or `message` - and an undeclared step is refused.
`cadencelibrary` already gives three ways to declare it (`linkedin_action`,
`capability`, `requires`); what was missing is that absence of all three is an
answer in itself, and the answer is no.
"""
import unittest

from src import cadencelibrary, lint
from tests.campaignbase import CampaignTest


# 150 characters: inside the message band (100-299) and inside the note band
# (40-300), so every assertion below turns on CLASSIFICATION and never on
# length. A test that used a length only one door accepts would pass for the
# wrong reason.
BOTH_BANDS = ("hi Ann, i work with operations leads at agencies on how they "
              "see utilisation before a month closes. curious how you handle "
              "that at your size.")


class DeclarationTest(CampaignTest):
    def rec(self):
        return {"id": "acme", "state": "drafted", "client": "demo",
                "contacts": [{"key": "c0", "name": "Ann", "email": "a@b.test",
                              "linkedin": "https://www.linkedin.com/in/ann"}]}

    def step(self, **extra):
        step = {"channel": "linkedin", "note": BOTH_BANDS}
        step.update(extra)
        return step


class TestTheLengthsAreInsideBothBands(DeclarationTest):
    """The control. Without this the tests below could pass on length."""

    def test_the_fixture_is_inside_the_note_band(self):
        self.assertTrue(lint.NOTE_MIN_CHARS <= len(BOTH_BANDS)
                        <= lint.NOTE_MAX_CHARS, len(BOTH_BANDS))

    def test_the_fixture_is_inside_the_message_band(self):
        self.assertTrue(lint.MESSAGE_MIN_CHARS <= len(BOTH_BANDS)
                        <= lint.MESSAGE_MAX_CHARS, len(BOTH_BANDS))


class TestAnUndeclaredStepFailsClosed(DeclarationTest):
    def test_a_step_with_no_operation_is_refused(self):
        """THE PRECONDITION. Absence is not a declaration."""
        self.assertIn("operation_type_undeclared",
                      lint.check_linkedin(self.rec(), "c0", self.step()))

    def test_it_does_not_validate_as_a_note(self):
        """It must not merely be flagged - it must not pass the note door.

        The failure the operator named is a step sliding through the note
        door. Asserting the code is present is not enough: a code that
        appears alongside a `clean` verdict changes nothing.
        """
        self.assertEqual(
            lint.classify_linkedin(
                lint.check_linkedin(self.rec(), "c0", self.step())),
            "failed")

    def test_the_note_rules_are_not_applied_to_an_undeclared_step(self):
        """Fail closed means STOP, not 'carry on with the note numbers'.

        A 320-character undeclared step must not come back saying
        `note_too_long`, because that answer asserts it is a note.
        """
        failures = lint.check_linkedin(self.rec(), "c0",
                                       self.step(note="x" * 320))
        self.assertIn("operation_type_undeclared", failures)
        self.assertNotIn("note_too_long", failures)
        self.assertNotIn("message_too_long", failures)

    def test_operation_of_says_undeclared_rather_than_guessing(self):
        self.assertIsNone(lint.operation_of(self.step()))

    def test_is_connection_note_is_false_for_an_undeclared_step(self):
        """The regression in one line.

        On master this returned True, which is how an undeclared message got
        the connection-request numbers.
        """
        self.assertFalse(lint.is_connection_note(self.step()))


class TestEveryDeclarationTheCadenceActuallyUses(DeclarationTest):
    """`cadencelibrary` already declares the operation three ways."""

    def test_linkedin_action_connect_is_a_connection_request(self):
        self.assertEqual(lint.operation_of(self.step(linkedin_action="connect")),
                         lint.CONNECTION_REQUEST)

    def test_linkedin_action_message_is_a_message(self):
        self.assertEqual(lint.operation_of(self.step(linkedin_action="message")),
                         lint.MESSAGE)

    def test_inmail_is_a_message_not_a_request(self):
        self.assertEqual(lint.operation_of(self.step(linkedin_action="inmail")),
                         lint.MESSAGE)

    def test_open_profile_message_is_a_message(self):
        self.assertEqual(
            lint.operation_of(self.step(linkedin_action="open_profile_message")),
            lint.MESSAGE)

    def test_the_connect_capability_is_a_connection_request(self):
        self.assertEqual(
            lint.operation_of(self.step(capability=cadencelibrary.CAP_CONNECT)),
            lint.CONNECTION_REQUEST)

    def test_the_message_capability_is_a_message(self):
        self.assertEqual(
            lint.operation_of(self.step(capability=cadencelibrary.CAP_MESSAGE)),
            lint.MESSAGE)

    def test_requires_connected_is_still_a_message(self):
        """Both names for the one state, as before. Nothing is lost."""
        for state in (cadencelibrary.CONNECTED,
                      cadencelibrary.CONNECTION_ACCEPTED):
            self.assertEqual(lint.operation_of(self.step(requires=state)),
                             lint.MESSAGE, state)

    def test_an_explicit_operation_field_is_honoured(self):
        self.assertEqual(
            lint.operation_of(self.step(operation=lint.CONNECTION_REQUEST)),
            lint.CONNECTION_REQUEST)
        self.assertEqual(lint.operation_of(self.step(operation=lint.MESSAGE)),
                         lint.MESSAGE)

    def test_an_unrecognised_declaration_is_undeclared_not_a_note(self):
        """A typo must fail closed too, not fall through to the note door."""
        self.assertIsNone(lint.operation_of(self.step(linkedin_action="conect")))
        self.assertIn("operation_type_undeclared",
                      lint.check_linkedin(self.rec(), "c0",
                                          self.step(linkedin_action="conect")))


class TestTheCadenceLibrarysOwnStepsAllDeclare(DeclarationTest):
    """The shipped cadence must not trip its own new gate.

    A fail-closed rule that refuses the cadence we actually run is not a
    safety gate, it is an outage. Asserted against the library rather than
    against a copy of it.
    """

    def test_every_linkedin_step_in_every_sequence_declares_itself(self):
        checked = 0
        for name in dir(cadencelibrary):
            seq = getattr(cadencelibrary, name)
            if not isinstance(seq, (list, tuple)):
                continue
            for step in seq:
                if not isinstance(step, dict):
                    continue
                if step.get("channel") != "linkedin":
                    continue
                checked += 1
                self.assertIsNotNone(
                    lint.operation_of(step),
                    f"{name}:{step.get('key')} declares no operation")
                alt = step.get("alternative")
                if isinstance(alt, dict):
                    checked += 1
                    merged = dict(step)
                    merged.update(alt)
                    self.assertIsNotNone(
                        lint.operation_of(merged),
                        f"{name}:{step.get('key')}:alternative declares none")
        # POSITIVE CONTROL. If the walk found nothing, every assertion above
        # was vacuous and this test would be green having checked zero steps.
        self.assertGreater(checked, 5, "the walk found no LinkedIn steps")


class TestTheTwoDoorsCarryDifferentNumbers(DeclarationTest):
    """The reason misclassification matters, asserted rather than asserted of.

    Measured contract, `docs/second-brain/linkedin.md` S14.3:
    li2/li3+ are 100-299. A connection request is capped at 300 and has no
    measured floor; the operator's standing instruction keeps a 40-character
    floor on it so a note still says something.
    """

    def test_the_message_floor_is_the_measured_one(self):
        self.assertEqual(lint.MESSAGE_MIN_CHARS, 100)

    def test_the_message_ceiling_is_the_measured_one(self):
        self.assertEqual(lint.MESSAGE_MAX_CHARS, 299)

    def test_the_note_band_is_the_operators(self):
        self.assertEqual(lint.NOTE_MIN_CHARS, 40)
        self.assertEqual(lint.NOTE_MAX_CHARS, 300)

    def test_a_ninety_character_message_is_refused_but_would_pass_as_a_note(self):
        """The exact gap the misclassification opened.

        90 characters is above the note floor (40) and below the message
        floor (100). Declared as a message it is refused; the defect made
        every writer step take the note door, where it passed.
        """
        text = "x" * 90
        self.assertIn("message_too_short",
                      lint.check_linkedin(self.rec(), "c0",
                                          self.step(note=text,
                                                    linkedin_action="message")))
        self.assertNotIn("note_too_short",
                         lint.check_linkedin(self.rec(), "c0",
                                             self.step(note=text,
                                                       linkedin_action="connect")))

    def test_a_300_character_message_is_refused_but_passes_as_a_request(self):
        """The other end of the same gap: 300 vs 299."""
        text = "y" * 300
        self.assertIn("message_too_long",
                      lint.check_linkedin(self.rec(), "c0",
                                          self.step(note=text,
                                                    linkedin_action="message")))
        self.assertNotIn("note_too_long",
                         lint.check_linkedin(self.rec(), "c0",
                                             self.step(note=text,
                                                       linkedin_action="connect")))


if __name__ == "__main__":
    unittest.main()
