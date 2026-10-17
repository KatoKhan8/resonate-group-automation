#!/usr/bin/env python3
"""Diagnose why TheFatigueHold tests fail — date arithmetic proof."""
import datetime
from src import store, fatigue, eligibility

# Reproduce the test record with count = limit() + 2 = 8 + 2 = 10
rec_count = fatigue.limits({})["account.max_touches_per_week"]["value"] + 2
print(f"limit() = {fatigue.limits({})['account.max_touches_per_week']['value']}")
print(f"rec_count = {rec_count}")

fixture_at = "2026-09-09T10:00:00+00:00"
now_str = store.now()
now_dt = datetime.datetime.fromisoformat(now_str)

print(f"\nFixture events dated: {fixture_at}")
print(f"store.now() returns: {now_str}")
print(f"Now dt: {now_dt}")

gap_hours = (now_dt - datetime.datetime.fromisoformat(fixture_at)).total_seconds() / 3600
gap_days = gap_hours / 24
print(f"\nGap between fixture date and now: {gap_hours:.1f} hours = {gap_days:.1f} days")
print(f"Window threshold: 7 days = 168 hours")
print(f"In window? {gap_hours <= 168}")

# What _within_week returns with now as anchor
events = [{"type": "push_marked", "contact": "a",
           "at": f"2026-09-09T10:00:00+00:00",
           "channel": "email", "step": f"s{i}", "day": i}
          for i in range(rec_count)]
window_origin = fatigue._window_origin(None, [e.get("at") for e in events])
print(f"\n_window_origin(None, events): {window_origin}")
recent = fatigue._within_week(events, window_origin)
print(f"_within_week returned {len(recent)} events out of {len(events)}")

# What the test rec looks like
rec = {"id": "acme", "client": "demo", "state": "ready",
       "contacts": [{"key": "a", "name": "Ada L", "title": "COO",
                     "email": "ada@acme.test", "selected": True}],
       "events": events}
result = eligibility._account_fatigue(rec, rec["contacts"][0], {})
print(f"\n_account_fatigue result: {result}")
print(f"Expected: held:account_fatigue")
print(f"Match? {result == eligibility.HELD_ACCOUNT_FATIGUE}")
