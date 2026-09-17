"""A variant's copy must come out of `_step_copy`, not a second extractor.

## The drift this pins

TASK-126 taught the factory to collect all variants into `payload.messages`
instead of resolving one. The first version extracted the text itself, because
`_step_copy` refuses a step with no `approval` and a variant carries its
approval on the VARIANT rather than on the step.

That obstacle is real. Duplicating the extractor was the wrong answer to it,
and the copy had already drifted from the original **in the same commit that
created it**:

    dropped   the `effective_channel != "linkedin"` check, so a non-LinkedIn
              variant could reach a LinkedIn payload
    reversed  the InMail field precedence, from `message or note` to
              `note or message`, so a variant carrying both would send
              different words depending on which path read it

Neither is visible from outside: both produce plausible text.

The fix lifts the variant's own verified approval onto the stepped copy and
calls the one extractor. These tests assert on RETURNED VALUES, so they
survive a rewording, and they fail if somebody reintroduces a second
extraction path that does not carry these guards.
"""

import unittest

from src import approval, heyreachfactory


def _stamped(step):
    """The step, approved over ITS OWN words.

    This was a shared module-level approval constant recording the fingerprint
    string "whatever", which certified nothing: `_step_copy` now compares the
    recorded fingerprint to `approval.fingerprint(step)`, so a stamp taken over
    no words at all is exactly the stale stamp the gate exists to refuse.
    Stamping here, after the step is complete, is what lets these tests keep
    asking their real question - which FIELD the extractor reads - rather than
    accidentally asking whether an approval matches.
    """
    step["approval"] = {"by": "fixture", "at": "2026-09-17T00:00:00",
                        "fingerprint": approval.fingerprint(step)}
    return step


class TheExtractorGuardsEveryPath(unittest.TestCase):

    def test_a_non_linkedin_step_yields_no_linkedin_copy(self):
        """The check the duplicated extractor dropped.

        `assemble_linkedin_copy` builds a LinkedIn payload. A step whose
        channel is email must contribute nothing to it, however approved and
        however well-formed its text.
        """
        email_step = _stamped({"channel": "email",
                               "linkedin_action": "message",
                               "note": "this is email copy"})
        self.assertIsNone(heyreachfactory._step_copy(email_step))

    def test_a_linkedin_step_yields_its_copy(self):
        """The other half: the guard must not refuse everything."""
        li_step = _stamped({"channel": "linkedin",
                            "linkedin_action": "message",
                            "note": "this is linkedin copy"})
        self.assertEqual(heyreachfactory._step_copy(li_step),
                         "this is linkedin copy")

    def test_inmail_prefers_message_over_note(self):
        """The precedence the duplicated extractor reversed.

        A variant carrying BOTH fields is where the two paths diverged. The
        canonical order is `message` first.
        """
        step = _stamped({"channel": "linkedin", "linkedin_action": "inmail",
                         "subject": "S", "message": "FROM-message",
                         "note": "FROM-note"})
        self.assertEqual(heyreachfactory._step_copy(step),
                         {"subject": "S", "message": "FROM-message"})

    def test_inmail_falls_back_to_note_when_message_is_absent(self):
        step = _stamped({"channel": "linkedin", "linkedin_action": "inmail",
                         "subject": "S", "note": "FROM-note"})
        self.assertEqual(heyreachfactory._step_copy(step),
                         {"subject": "S", "message": "FROM-note"})

    def test_an_unapproved_step_yields_nothing(self):
        """The guard that makes lifting the variant's approval meaningful.

        The variant path sets `stepped["approval"]` to the variant's own
        approval, which has just been verified by fingerprint. If that lift
        ever stops happening, this is what refuses the copy.
        """
        step = {"channel": "linkedin", "linkedin_action": "message",
                "note": "unapproved copy"}
        self.assertIsNone(heyreachfactory._step_copy(step))

    def test_an_inmail_missing_its_subject_yields_nothing(self):
        # Half an InMail is not an InMail, and the provider rejects it.
        step = _stamped({"channel": "linkedin", "linkedin_action": "inmail",
                         "message": "body with no subject"})
        self.assertIsNone(heyreachfactory._step_copy(step))


if __name__ == "__main__":
    unittest.main()
