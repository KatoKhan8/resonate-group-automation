"""Only the connection REQUEST carries LinkedIn's 300-character limit.

Operator decision "A", Zvonimir, 2026-09-28.

`lint.is_connection_note` compared `requires` against `"connection_accepted"`
alone, while `cadencelibrary` declares `CONNECTED = "connected"` on li2-li5 -
every LinkedIn MESSAGE in the heavy cadence. All four therefore answered TRUE
and were capped at 300 characters as connection requests, producing false
`note_too_long` refusals.

NO CAP IS RAISED. These tests exist to prove that: the 300 limit still bites on
the request, and the 1900 limit still bites on a message. What changed is which
steps are which.

The step list is read from the REAL cadence rather than written out here, so
this test cannot agree with a stale idea of the cadence.
"""
import unittest

from src import cadence, cadencelibrary, clients, lint


def _li_steps():
    config = clients.load("productive")
    return {s["key"]: s for s in cadence.steps_for(None, config=config)
            if str(s.get("key", "")).startswith("li")}


class OnlyTheRequestIsCappedAt300(unittest.TestCase):

    def setUp(self):
        self.steps = _li_steps()
        self.assertTrue(self.steps, "the cadence declares no LinkedIn steps")

    def test_the_cadence_really_declares_connected_on_the_messages(self):
        """The premise. If this changes, the rest of this file is about
        nothing, so it is asserted rather than assumed."""
        self.assertEqual(cadencelibrary.CONNECTED, "connected")
        for key in ("li2", "li3", "li4", "li5"):
            self.assertEqual(self.steps[key].get("requires"),
                             cadencelibrary.CONNECTED,
                             "%s should require an established connection" % key)

    def test_li1_is_the_connection_request(self):
        self.assertEqual(self.steps["li1"].get("linkedin_action"), "connect")
        self.assertTrue(lint.is_connection_note(self.steps["li1"]))

    def test_li2_is_a_message_not_a_request(self):
        self.assertFalse(lint.is_connection_note(self.steps["li2"]))

    def test_li3_is_a_message_not_a_request(self):
        self.assertFalse(lint.is_connection_note(self.steps["li3"]))

    def test_li4_is_a_message_not_a_request(self):
        self.assertFalse(lint.is_connection_note(self.steps["li4"]))

    def test_li5_is_a_message_not_a_request(self):
        self.assertFalse(lint.is_connection_note(self.steps["li5"]))

    def test_every_message_step_reports_the_message_action(self):
        for key in ("li2", "li3", "li4", "li5"):
            self.assertEqual(self.steps[key].get("linkedin_action"), "message",
                             "%s is not a message step" % key)


class TheCapsStillBite(unittest.TestCase):
    """THE NEGATIVE CONTROLS. A classification fix that quietly stopped
    enforcing a length would be worse than the bug it replaced."""

    def setUp(self):
        self.steps = _li_steps()

    def _fails(self, key, text):
        step = dict(self.steps[key])
        step["note" if lint.is_connection_note(step) else "body"] = text
        rec = {"id": "cap-probe", "state": "ready",
               "contacts": [{"key": "c1", "name": "A Person",
                             "linkedin": "https://www.linkedin.com/in/x"}]}
        return lint.check_linkedin(rec, "c1", step)

    def test_a_301_character_connection_request_is_still_refused(self):
        self.assertIn("note_too_long", self._fails("li1", "x" * 301))

    def test_a_300_character_connection_request_is_not_too_long(self):
        self.assertNotIn("note_too_long", self._fails("li1", "y" * 300))

    def test_a_301_character_message_is_no_longer_refused_for_length(self):
        """The bug, from the other side: this used to be `note_too_long`."""
        fails = self._fails("li2", "z" * 301)
        self.assertNotIn("note_too_long", fails)
        self.assertNotIn("message_too_long", fails)

    def test_a_1901_character_message_is_still_refused(self):
        self.assertIn("message_too_long", self._fails("li2", "w" * 1901))

    def test_a_1900_character_message_is_not_too_long(self):
        self.assertNotIn("message_too_long", self._fails("li2", "v" * 1900))

    def test_the_two_limits_are_unchanged(self):
        """Nothing was raised. Asserted so a later edit has to say so."""
        self.assertEqual(lint.NOTE_MAX_CHARS, 300)
        self.assertEqual(lint.MESSAGE_MAX_CHARS, 1900)


if __name__ == "__main__":
    unittest.main()
