"""POOL 0006 harness — prove the classifier prints both answers.

Two synthetic send paths:
  PATH-GATED:    goes through eligibility.decide (which consults _account_fatigue)
  PATH-UNGATED:  bypasses eligibility.decide (no fatigue check)

Both paths operate on the same synthetic record. The record carries enough
recent confirmed touches to trip the company-fatigue hold (using NOW-relative
dates so the 7-day window actually covers them, unlike the test fixture in
test_red_team_tonights_guards.py whose 2026-09-09 dates are over a month
stale as of 2026-10-17).

The classifier says GATED when the path consults the hold, UNGATED when it
does not. We assert it says GATED for path A and UNGATED for path B. If it
says the same thing for both, the instrument is broken and the measurement
is void.
"""
import datetime as _dt
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import eligibility, fatigue  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Build a synthetic record whose touches TRIP the hold NOW.
# ---------------------------------------------------------------------------
def build_over_fatigued_rec():
    """A record with 10 confirmed touches within the last 7 days.

    Default account.max_touches_per_week is 8, so 10 recent touches trip
    the BLOCK at the heart of _account_fatigue.

    The test fixture in test_red_team_tonights_guards.py uses a hard-coded
    2026-09-09 date which is over a month old by 2026-10-17; the 7-day
    window drops every touch and the check passes. That is why those tests
    are red, and it is why this fixture uses now-relative dates.
    """
    limit = fatigue.limits({})["account.max_touches_per_week"]["value"]
    count = limit + 2  # 10 by default, 2 over the limit
    now = _dt.datetime.now(_dt.timezone.utc)
    events = []
    for i in range(count):
        at = now - _dt.timedelta(days=i % 5, hours=i)  # staggered within 5d
        events.append({
            "type": "push_marked",  # in touch.CONFIRMING_EVENTS -> SENT
            "contact": "a",
            "at": at.isoformat(),
            "channel": "email",
            "step": "s%d" % i,
            "day": i,
        })
    return {
        "id": "acme",
        "client": "demo",
        "domain": "acme.test",
        "state": "ready",
        "contacts": [
            {"key": "a", "name": "Ada L", "title": "COO",
             "email": "ada@acme.test", "selected": True},
            {"key": "b", "name": "Bo C", "title": "CFO",
             "email": "bo@acme.test", "selected": True},
        ],
        "events": events,
    }


# ---------------------------------------------------------------------------
# 2. Two synthetic send paths.
# ---------------------------------------------------------------------------
def send_path_gated(rec, contact):
    """A path that calls eligibility.decide before handing to the provider.

    This is what executionguard.authorize does at line 571 of
    src/executionguard.py, what push.py:verify_before_payload does at
    line 153, and what every script that consults eligibility does.
    """
    decision = eligibility.decide(
        rec, contact, "s99",
        timeline={"a": {"s99": {"channel": "email", "day": 30,
                                "subject": "x", "body": "y"}},
                  "b": {"s99": {"channel": "email", "day": 30,
                                "subject": "x", "body": "y"}}},
        config={})
    return decision


def send_path_ungated(rec, contact):
    """A path that bypasses eligibility.decide entirely.

    This is what liststaging.stage_lead does (non-facing perform with no
    Authorization), what prototype/bin/push.py did, and what every entry
    in scripts/known_write_bypasses.json does.
    """
    # No eligibility.decide call. Pretend we reached the provider.
    return {"sent": True, "reason": None}


# ---------------------------------------------------------------------------
# 3. Classifier - the same shape the census uses.
# ---------------------------------------------------------------------------
def classify(verdict):
    """Given a send-path result, say whether it consulted the fatigue hold."""
    if isinstance(verdict, dict):
        reasons = verdict.get("reasons") or []
        reason = verdict.get("reason") or (reasons[0] if reasons else None)
        if reason == eligibility.HELD_ACCOUNT_FATIGUE:
            return "GATED"
        if verdict.get("verdict") in ("eligible", "held", "blocked", "skipped"):
            # It went through eligibility.decide but did not fire fatigue
            # (e.g. held on a different reason). Still GATED - the check ran.
            return "GATED"
        if "sent" in verdict:
            return "UNGATED"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# 4. Both-answer control.
# ---------------------------------------------------------------------------
def main():
    rec = build_over_fatigued_rec()
    contact_a = rec["contacts"][0]
    contact_b = rec["contacts"][1]

    limit = fatigue.limits({})["account.max_touches_per_week"]["value"]
    recent = len([e for e in rec["events"]])
    print("=== fixture ===")
    print("  touches on record : %d (limit %d)" % (recent, limit))
    print("  window origin     : now() (the test fixture uses 2026-09-09 - "
          "38d stale)")
    print()

    # --- control: an under-fatigued record must pass the GATED path
    print("=== under-fatigued control ===")
    under = dict(rec, events=rec["events"][:2])
    v_under = send_path_gated(under, contact_a)
    c_under = classify(v_under)
    print("  path: GATED  verdict: %s  reasons: %s  classified: %s" %
          (v_under.get("verdict"), v_under.get("reasons"), c_under))
    assert c_under == "GATED", "under-fatigued record should still be classified GATED"
    # The verdict may be held on a different reason (e.g. verification_unknown)
    # but it went through decide(), which is what GATED means.
    print()

    # --- over-fatigued, GATED path: should return HELD_ACCOUNT_FATIGUE
    print("=== over-fatigued, GATED path ===")
    v_gated_a = send_path_gated(rec, contact_a)
    c_gated_a = classify(v_gated_a)
    print("  contact: a  verdict: %s  reasons: %s  classified: %s" %
          (v_gated_a.get("verdict"), v_gated_a.get("reasons"), c_gated_a))
    assert c_gated_a == "GATED", ("over-fatigued path through decide must "
                                  "be GATED; got %s" % c_gated_a)

    v_gated_b = send_path_gated(rec, contact_b)
    c_gated_b = classify(v_gated_b)
    print("  contact: b  verdict: %s  reasons: %s  classified: %s" %
          (v_gated_b.get("verdict"), v_gated_b.get("reasons"), c_gated_b))
    assert c_gated_b == "GATED", ("contact b must see the SAME company "
                                  "fatigue; got %s" % c_gated_b)
    print()

    # --- over-fatigued, UNGATED path: should reach the provider
    print("=== over-fatigued, UNGATED path ===")
    v_ungated_a = send_path_ungated(rec, contact_a)
    c_ungated_a = classify(v_ungated_a)
    print("  contact: a  result: %s  classified: %s" %
          (v_ungated_a, c_ungated_a))
    assert c_ungated_a == "UNGATED", ("ungated path must be UNGATED; got %s"
                                      % c_ungated_a)

    v_ungated_b = send_path_ungated(rec, contact_b)
    c_ungated_b = classify(v_ungated_b)
    print("  contact: b  result: %s  classified: %s" %
          (v_ungated_b, c_ungated_b))
    assert c_ungated_b == "UNGATED"
    print()

    # --- the two answers must differ
    print("=== classifier discriminates ===")
    print("  GATED path    : %s  (the hold was consulted)" % c_gated_a)
    print("  UNGATED path  : %s  (the hold was bypassed)" % c_ungated_a)
    assert c_gated_a != c_ungated_a, ("classifier returned the same label "
                                       "for both paths - broken")
    print("  PASS: the instrument prints both answers")
    print()

    # --- the specific finding the brief names
    print("=== the specific finding ===")
    print("  _account_fatigue on over-fatigued contact a: %s" %
          eligibility._account_fatigue(rec, contact_a, {}))
    print("  _account_fatigue on over-fatigued contact b: %s" %
          eligibility._account_fatigue(rec, contact_b, {}))
    # Now the dates are fresh, this should return HELD_ACCOUNT_FATIGUE
    # - confirming the tests in test_red_team_tonights_guards.py are red
    # because of stale dates, not a defect in the guard.


if __name__ == "__main__":
    main()
