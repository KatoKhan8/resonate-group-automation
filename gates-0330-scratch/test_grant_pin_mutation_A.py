#!/usr/bin/env python3
"""Scratch copy of test_the_live_activation_grant.py — ARM A: TEST-PIN MUTATION.

Replace the pinned expected value with the CURRENT RUNTIME value to verify
that making the test match runtime makes it PASS. If it does, the test side
moved AFTER the test was written → TEST-STALE.
"""
import unittest
from unittest import mock

from src import executionguard, killswitch, providerwrites

from tests.test_no_write_happens_without_every_gate import GuardTest, WS, NOW


LINKEDIN_ACTIVATE = "heyreach.activate"
EMAIL_ACTIVATE = "bison.activate"


class TestTheGrantValueMatchesCurrentRuntime(unittest.TestCase):
    """Mutated pin: expect 3 entries as the runtime produces."""

    def test_grant_holds_exactly_what_runtime_produces(self):
        """ARM A: test-pinned value replaced with runtime value."""
        self.assertEqual(
            executionguard.LIVE_ACTIVATION_GRANTS,
            {
                "productive-linkedin-cohort-v2": frozenset({LINKEDIN_ACTIVATE}),
                "productive-email-control-v3": frozenset({EMAIL_ACTIVATE}),
                "productive-email-us-cohort-v1": frozenset({EMAIL_ACTIVATE}),
            })


if __name__ == "__main__":
    unittest.main()
