#!/usr/bin/env python3
"""Arm 2 — CODE-REGRESSED proof: mutate _within_week to ALWAYS drop all events.

With FRESH dates and a broken window that drops everything, the code path
returns None (no events in window -> count < limit -> no block). The test
stays red but for REASON #2 (proceeds past fatigue gate, fails later on verification).

This contrasts with TEST-STALE where fresh dates fix everything because the code
itself works. Two different failures under two different mechanisms.
"""
from datetime import datetime, timezone
import src.store as store_module
import src.fatigue as fatigue_module
import importlib
import src.eligibility as eligibility_module

TODAY = datetime(2026, 10, 17, tzinfo=timezone.utc).replace(microsecond=0)
store_module.now = lambda: TODAY.isoformat()

# MUTATION: _within_week always returns empty — no event ever survives
original_within_week = fatigue_module._within_week

def broken_within_week(touches, of):
    """Mutated: drops ALL events, even fresh ones."""
    return []

fatigue_module._within_week = broken_within_week

# Reload eligibility to pick up mutation
importlib.reload(eligibility_module)

from src import fatigue

# REC WITH FRESH DATES (same fixture date as arm 1)
def make_rec(count, key="a"):
    return {"id": "acme", "client": "demo", "state": "ready",
            "contacts": [{"key": key, "name": "Ada L", "title": "COO",
                          "email": "ada@acme.test", "selected": True}],
            "events": [{"type": "push_marked", "contact": key,
                        "at": f"2026-10-15T10:00:00+00:00",  # Yesterday — fresh!
                        "channel": "email", "step": f"s{i}", "day": i}
                       for i in range(count)]}

limit = fatigue.limits({})["account.max_touches_per_week"]["value"]
print(f"Limit: {limit}, count: {limit + 2}")
print(f"Mutation: _within_week -> ALWAYS returns []")
print(f"Dates: FRESH (Oct 15), same as arm 1\n")

rec = make_rec(limit + 2)

# Verify plant was applied
plant_check = fatigue_module._within_week([{"at": "now"}], "2026-10-17T13:00:00+00:00")
print(f"Plant check: _within_week(anything) returned {len(plant_check)} items")
assert len(plant_check) == 0, "PLANT NOT APPLIED — dead row"
print("PLANT CONFIRMED: mutation active\n")

result1 = eligibility_module._account_fatigue(rec, rec["contacts"][0], {})
print(f"test_a_second_contact_does_not_reset_the_company_count:")
print(f"  Result: {result1}")
print(f"  With BROKEN guard + FRESH dates -> None (window empty, count=0 < limit)")
print(f"  Test FAILS (None != HELD_ACCOUNT_FATIGUE)")

result3 = eligibility_module.decide(
    rec, rec["contacts"][0], "s99",
    timeline={"a": {"s99": {"channel": "email", "day": 30,
                            "subject": "x", "body": "y"}}}, config={})
print(f"\ntest_it_is_asked_before_content_and_cannot_be_out_ranked:")
print(f"  Reasons: {result3.get('reasons')}")
print(f"  Fatigue passes (none in window) -> hits verification_next -> held:verification_unknown")
print(f"  Test FAILS (wrong reason code)")

# Restore original for clean exit
fatigue_module._within_week = original_within_week

print(f"\n{'='*60}")
print(f"ARM 2 VERDICT: Fresh dates + mutated guard -> still red, but for reason #2")
print(f"The mechanism: TEST-STALE fixes the code; CODE-REGRESSED does not.")
print(f"Different symptoms under identical date conditions.")
