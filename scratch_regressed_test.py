#!/usr/bin/env python3
"""Arm 2 — mutate _within_week, run as unittest module to capture FAIL names."""
import sys
from datetime import datetime, timezone
import unittest

# Apply mutations BEFORE any imports of src modules that use them
import src.store as store_module
store_module.now = lambda: datetime(2026, 10, 17, tzinfo=timezone.utc).replace(microsecond=0).isoformat()

import src.fatigue as fatigue_module
def broken_within_week(touches, of):
    return []
fatigue_module._within_week = broken_within_week

# Must reload eligibility AFTER mutating fatigue because it uses local import
import importlib
import src.eligibility as eligibility_module
importlib.reload(eligibility_module)

from src import fatigue

class TheFatigueHoldCannotBeSidestepped(unittest.TestCase):
    """Mutated-fatigue version of the same tests."""

    def rec(self, count, key="a"):
        return {"id": "acme", "client": "demo", "state": "ready",
                "contacts": [{"key": key, "name": "Ada L", "title": "COO",
                              "email": "ada@acme.test", "selected": True}],
                "events": [{"type": "push_marked", "contact": key,
                            "at": f"2026-10-15T10:00:00+00:00",
                            "channel": "email", "step": f"s{i}", "day": i}
                           for i in range(count)]}

    def limit(self):
        return fatigue.limits({})["account.max_touches_per_week"]["value"]

    def test_a_second_contact_does_not_reset_the_company_count(self):
        rec = self.rec(self.limit() + 2)
        rec["contacts"].append({"key": "b", "name": "Bo C", "title": "CFO",
                                "email": "bo@acme.test", "selected": True})
        self.assertEqual(
            eligibility_module._account_fatigue(rec, rec["contacts"][1], {}),
            eligibility_module.HELD_ACCOUNT_FATIGUE)

    def test_a_config_cannot_raise_the_limit_by_being_unreadable(self):
        rec = self.rec(self.limit() + 2)
        self.assertEqual(eligibility_module._account_fatigue(rec, rec["contacts"][0], None),
                         eligibility_module.HELD_ACCOUNT_FATIGUE)

    def test_it_is_asked_before_content_and_cannot_be_out_ranked(self):
        rec = self.rec(self.limit() + 2)
        verdict = eligibility_module.decide(
            rec, rec["contacts"][0], "s99",
            timeline={"a": {"s99": {"channel": "email", "day": 30,
                                    "subject": "x", "body": "y"}}}, config={})
        self.assertEqual(verdict["reasons"], [eligibility_module.HELD_ACCOUNT_FATIGUE])


if __name__ == "__main__":
    unittest.main(verbosity=2)
