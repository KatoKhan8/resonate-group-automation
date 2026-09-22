#!/usr/bin/env python3
"""A status the provider returns on the happy path is a state, not an anomaly.

Measured 2026-09-22 while activating both channels:

    EmailBison   491, 492 and 495 answered `launching`
    HeyReach     all 33 batch campaigns answered `STARTING`

Every one was reported as unclassifiable, and every one was running moments
later. Both modules already had a tuple for exactly this - `STARTING_STATES`
on one and `_STARTING_STATUSES` on the other - and HeyReach's was EMPTY while
EmailBison's did not carry `launching`.

The failure mode is worse than a confusing message. The refusal tells the
caller to read provider truth before starting again, which a less careful
caller turns into a blind retry of the one verb that makes a campaign send.

These tests pin the two statuses and, more importantly, pin that neither
module reports success without seeing the started state itself.
"""
import unittest

from src.providers import bison, heyreach


class TheTransitionalStatesAreCarried(unittest.TestCase):

    def test_emailbison_polls_launching(self):
        self.assertIn("launching", bison.STARTING_STATES)

    def test_emailbison_still_polls_queued(self):
        self.assertIn("queued", bison.STARTING_STATES)

    def test_heyreach_polls_starting(self):
        self.assertIn("STARTING", heyreach._STARTING_STATUSES)


class SuccESSIsStillOnlyTheStartedState(unittest.TestCase):

    def test_emailbison_does_not_treat_a_transitional_state_as_started(self):
        for state in bison.STARTING_STATES:
            self.assertNotIn(state, bison.NOT_STARTED_STATES)
            self.assertNotEqual(state, "active")

    def test_heyreach_does_not_treat_starting_as_started(self):
        for state in heyreach._STARTING_STATUSES:
            self.assertNotIn(state, heyreach._STARTED_STATUSES)
            self.assertNotIn(state, heyreach._NOT_STARTED_STATUSES)

    def test_heyreach_started_is_only_in_progress(self):
        self.assertEqual(tuple(heyreach._STARTED_STATUSES), ("IN_PROGRESS",))


if __name__ == "__main__":
    unittest.main()
