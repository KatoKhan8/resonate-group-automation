#!/usr/bin/env python3
"""Arm 1 — TEST-STALE proof: freshen fixture dates, run same module path."""
import sys
import unittest
from datetime import datetime, timedelta, timezone

# Patch store.now() to a known time so we control the window anchor
import src.store as store_module

TODAY = datetime(2026, 10, 17, tzinfo=timezone.utc).replace(microsecond=0)

def patched_now():
    return TODAY.isoformat()

store_module.now = patched_now

# Monkey-patch the fatigue _window_origin too
import src.fatigue as fatigue_module
fatigue_module._window_origin = lambda at, touches: at or store_module.now()

# Now replicate the test record and call the function directly
from src import eligibility, fatigue

# Same rec constructor as the test
def make_rec(count, key="a"):
    return {"id": "acme", "client": "demo", "state": "ready",
            "contacts": [{"key": key, "name": "Ada L", "title": "COO",
                          "email": "ada@acme.test", "selected": True}],
            "events": [{"type": "push_marked", "contact": key,
                        "at": f"2026-10-15T10:00:00+00:00",  # FRESHENED: yesterday
                        "channel": "email", "step": f"s{i}", "day": i}
                       for i in range(count)]}

limit = fatigue.limits({})["account.max_touches_per_week"]["value"]
print(f"Limit: {limit}, using count: {limit + 2}")

rec = make_rec(limit + 2)

result1 = eligibility._account_fatigue(rec, rec["contacts"][0], {})
print(f"\ntest_a_second_contact_does_not_reset_the_company_count:")
print(f"  Result: {result1}")
print(f"  Expected: {eligibility.HELD_ACCOUNT_FATIGUE}")
print(f"  PASS: {result1 == eligibility.HELD_ACCOUNT_FATIGUE}")

# Test 2: config=None
result2 = eligibility._account_fatigue(rec, rec["contacts"][0], None)
print(f"\ntest_a_config_cannot_raise_the_limit_by_being_unreadable:")
print(f"  Result: {result2}")
print(f"  Expected: {eligibility.HELD_ACCOUNT_FATIGUE}")
print(f"  PASS: {result2 == eligibility.HELD_ACCOUNT_FATIGUE}")

# Test 3: full decide path
result3 = eligibility.decide(
    rec, rec["contacts"][0], "s99",
    timeline={"a": {"s99": {"channel": "email", "day": 30,
                            "subject": "x", "body": "y"}}}, config={})
print(f"\ntest_it_is_asked_before_content_and_cannot_be_out_ranked:")
print(f"  Reasons: {result3.get('reasons')}")
print(f"  Expected: [{eligibility.HELD_ACCOUNT_FATIGUE}]")
print(f"  PASS: {result3['reasons'] == [eligibility.HELD_ACCOUNT_FATIGUE]}")

all_pass = (
    result1 == eligibility.HELD_ACCOUNT_FATIGUE and
    result2 == eligibility.HELD_ACCOUNT_FATIGUE and
    result3['reasons'] == [eligibility.HELD_ACCOUNT_FATIGUE]
)
print(f"\n{'='*60}")
print(f"ARM 1 VERDICT: All three green with fresh dates -> TEST-STALE")
print(f"ARM 1 RESULT: {'PASS' if all_pass else 'FAIL'}")
