"""Only the connection REQUEST carries LinkedIn's 300-character limit.

Operator decision "A", Zvonimir, 2026-09-28.

`lint.is_connection_note` compared `requires` against `"connection_accepted"`
alone, while `cadencelibrary` declares `CONNECTED = "connected"` on li2-li5 -
every LinkedIn MESSAGE in the heavy cadence. All four therefore answered TRUE
and were capped at 300 characters as connection requests, producing false
`note_too_long` refusals.

NO CAP IS RAISED BY THE 2026-09-28 FIX. These tests existed to prove that:
the 300 limit still bit on the request, and the 1900 limit still bit on a
message. What changed that day is which steps are which.

WHAT CHANGED ON 2026-10-03, and it is a LOWERING, not a raising. The four flat
character constants are replaced by one measured contract,
`skills.linkedin_writing.LINKEDIN_CHAR_CONTRACT`, and a message\'s ceiling is
now 299, not 1,900: the longest outbound message in 54,647 was 1,097, so 1,900
never bound once, while 100-299 is the band measured to beat every band above
it. The three assertions below that encoded 1,900 are rewritten to the
measured number, and `TheCapsStillBite` is stricter than it was, never looser.

The step list is read from the REAL cadence rather than written out here, so
this test cannot agree with a stale idea of the cadence.
"""
import unittest

from src import cadence, cadencelibrary, clients, lint
from src.skills import linkedin_writing


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

    def test_a_301_character_message_is_not_refused_as_a_NOTE(self):
        """The 2026-09-28 bug, from the other side: this used to be
        `note_too_long`, which is the WRONG CODE for a message. It is now
        `message_too_long`, from the message row of the contract. The
        distinction this file exists to defend is which rule applies, and
        that still holds; what changed is that the message rule now refuses
        301 as well, at 299 rather than 1,900."""
        fails = self._fails("li2", "z" * 301)
        self.assertNotIn("note_too_long", fails)
        self.assertIn("message_too_long", fails)

    def test_a_300_character_message_is_refused_where_a_300_note_is_not(self):
        """299 is the measured ceiling and 300 is LinkedIn\'s own cap on a
        note, so the message ceiling now sits one character BELOW the note
        ceiling. Asserted because it is counter-intuitive and because a
        reader who assumes the old ordering would widen the wrong one."""
        self.assertIn("message_too_long", self._fails("li2", "y" * 300))
        self.assertNotIn("note_too_long", self._fails("li1", "y" * 300))

    def test_a_299_character_message_is_not_too_long(self):
        self.assertNotIn("message_too_long", self._fails("li2", "v" * 299))

    def test_a_1901_character_message_is_still_refused(self):
        """THE CONTROL. Refused under the old 1,900 ceiling and refused
        under the measured 299 one - it passes both ways on purpose, so a
        blanket change cannot be credited to it."""
        self.assertIn("message_too_long", self._fails("li2", "w" * 1901))

    def test_the_limits_are_the_contracts_and_nothing_else_carries_one(self):
        """Nothing was raised. Asserted so a later edit has to say so - and
        now asserted against the ONE authority rather than against a second
        copy in `lint`."""
        contract = linkedin_writing.LINKEDIN_CHAR_CONTRACT
        self.assertEqual(lint.NOTE_MAX_CHARS, 300)
        self.assertIs(lint.LINKEDIN_CHAR_CONTRACT, contract)
        self.assertEqual(contract["li1"][2], 300)
        self.assertEqual(contract["li2"], (100, 125, 299))
        self.assertEqual(contract["li3+"], (100, 173, 299))
        self.assertIs(contract["li1"][0], linkedin_writing.UNKNOWN)
        for gone in ("NOTE_MIN_CHARS", "MESSAGE_MIN_CHARS",
                     "MESSAGE_MAX_CHARS"):
            self.assertFalse(hasattr(lint, gone),
                             "%s is a second authority and is deleted" % gone)


if __name__ == "__main__":
    unittest.main()
