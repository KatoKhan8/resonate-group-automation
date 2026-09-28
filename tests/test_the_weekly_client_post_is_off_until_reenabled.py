#!/usr/bin/env python3
"""The weekly report may not reach a CLIENT channel until it is switched on.

## WHAT HAPPENED

Monday 2026-09-28, 08:03. The weekly client post fired into
`#productive-resonate-outbound` - a Slack Connect channel the client is in - and
what the client saw was exactly this:

    *Weekly report - week of 2026-09-28*
    PDF: `C:\\Users\\<operator>\\...\\work\\reports\\weekly-productive-2026-09-28.pdf` (5027 bytes)

An absolute path on a laptop the client cannot reach, carrying the operator's own
username, plus a promise of a file Slack has no upload route for. The 07:30
preview into `#resonate-os` had a half-hour stop window; nobody was awake to use
it, and **late is not the same as approved is a rule this loop already enforces in
the other direction** - it refuses to post if it first ticks after 08:00 - so the
gap was the unattended window, not the schedule.

The part that went right, and it is worth stating because it is the part a reader
will assume went wrong: the preview's real content stayed internal. The warning
that the ledger is not recording this workspace's sends, and the 1,504 accounts
that cannot be placed, were in `#resonate-os` only. The client saw a path, not a
number.

## WHAT THIS MODULE HOLDS

Operator instruction, Zvonimir, 2026-09-28: the automatic client post is disabled
until the content is reviewed. Held as a SWITCH rather than by killing the loop,
because a killed process restarts and a killed process is not a decision - the
same reason `sending.live` is a policy key and not somebody remembering.

Three properties, and the second is the one that makes the first safe to trust:

  1. absence of the switch means NO client post (fail closed);
  2. the PREVIEW still goes out (a review pause must not become a blind spot);
  3. the hold is recorded as a STOP, so it does not retry every tick inside the
     window and the journal says who held it and why.
"""
import unittest

from src import weeklyreportwatch as watch


class TheSwitchFailsClosed(unittest.TestCase):

    def test_absence_is_not_permission(self):
        """A missing variable is not a setting of on.

        The same contract as `sending.live`: a fresh clone, a new host or a lost
        `.env` must all fail toward NOT posting to a client.
        """
        self.assertFalse(watch.client_post_enabled(env={}))

    def test_an_empty_value_is_not_permission_either(self):
        self.assertFalse(watch.client_post_enabled(env={watch.CLIENT_POST_VAR: ""}))
        self.assertFalse(watch.client_post_enabled(
            env={watch.CLIENT_POST_VAR: "   "}))

    def test_a_word_that_is_not_yes_is_not_permission(self):
        for value in ("0", "off", "false", "no", "later", "maybe", "disabled"):
            self.assertFalse(
                watch.client_post_enabled(env={watch.CLIENT_POST_VAR: value}),
                f"{value!r} must not enable the client post")

    def test_it_can_be_turned_back_on_deliberately(self):
        """The control. Without it this module would pass just as happily if the
        switch were welded shut, and a switch that cannot be turned on is not a
        switch - the operator would find that out next Monday instead of now."""
        for value in ("1", "true", "yes", "on", "ON", " True "):
            self.assertTrue(
                watch.client_post_enabled(env={watch.CLIENT_POST_VAR: value}),
                f"{value!r} should enable the client post")


class TheRefusalIsNamedAndActionable(unittest.TestCase):

    def test_the_reason_says_what_to_do_about_it(self):
        """A log line an operator cannot act on costs a support round trip.

        It has to name the variable, so reading the refusal is enough to know
        how to reverse it without finding the source comment.
        """
        why = watch.CLIENT_POST_OFF_WHY
        self.assertIn(watch.CLIENT_POST_VAR, why)
        self.assertIn("2026-09-28", why)

    def test_stop_is_in_the_outcome_vocabulary(self):
        """The hold reuses STOPPED rather than inventing an outcome.

        It matters because the loop's state machine and its readback both
        enumerate `OUTCOMES`; a new word there would be a second vocabulary for
        the same fact, and FAILED would be wrong - FAILED retries inside the
        window, which is exactly what a hold must not do.
        """
        self.assertIn(watch.STOPPED, watch.OUTCOMES)
        self.assertNotEqual(watch.STOPPED, watch.FAILED)


class ThePreviewIsNotSilenced(unittest.TestCase):
    """The review pause must not become a blind spot.

    If holding the client post also stopped the preview, the operator would lose
    the only view of what the report says each Monday - trading a known problem
    for an invisible one.
    """

    def test_the_preview_channel_is_not_a_client_channel(self):
        self.assertEqual("#resonate-os", watch.PREVIEW_CHANNEL)

    def test_the_switch_governs_only_the_client_half(self):
        """`client_post_enabled` takes no view of the preview at all.

        Asserted on the function's behaviour rather than on the loop's source:
        it answers the same way whatever the preview constants are, so it cannot
        grow an opinion about the preview without this test noticing.
        """
        self.assertFalse(watch.client_post_enabled(env={}))
        self.assertTrue(watch.client_post_enabled(
            env={watch.CLIENT_POST_VAR: "1"}))


if __name__ == "__main__":
    unittest.main()
