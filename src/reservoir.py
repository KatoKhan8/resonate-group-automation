"""The durable READY reservoir: derived, never latched.

A contact that was READY an hour ago and has since replied, been suppressed,
had its approval invalidated by a copy edit, or had its account collide must
NOT still be READY. The set is recomputed on every call by running the
existing screen (`scripts/next_ready_cohort.py`), not by reading stored
verdicts. Two opinions about who is safe to contact is how they drift.

WHAT THIS IS. A function that returns the current READY set per channel,
with the reason each candidate is READY - not merely that it is. It consumes
the existing screen rather than reimplementing the gates.

WHAT THIS DOES NOT DO. It proposes, it does not send. No provider write,
no activation, no campaign mutation, no credit spend. The allocator that
consumes it is a separate task and consuming from READY is still subject to
every execution-boundary recheck.

WHY DERIVED AND NOT LATCHED. `approve.sync_state` and `approval.is_approved`
already work this way: the approval fingerprint is compared to the current
step on every read, so an edit to the words invalidates the approval without
anybody clearing a cache. A latched boolean that says "this contact was
cleared at time T" is the exact shape of the defect this repository keeps
finding - a stale CLEAR is worse than no CLEAR at all.
"""
import collections
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_screen_module():
    """Import `scripts/next_ready_cohort.py` as a module.

    The script lives in `scripts/` which has no `__init__.py`, so a normal
    import does not reach it. `importlib.util` loads it directly without
    requiring the directory to be a package.
    """
    path = os.path.join(ROOT, "scripts", "next_ready_cohort.py")
    spec = importlib.util.spec_from_file_location("next_ready_cohort", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ready_set(recs, config, campaigns_by_id):
    """The current READY set per channel, derived from the screen.

    Returns a dict: {channel: {"ready": [...], "depth": int,
              "blockers": {gate: count}, "population": int}}

    Each ready entry carries the contact hash, the account hash, and the
    reason it is READY ("every contact-level gate passes").

    DERIVED, NEVER LATCHED. Every call re-runs the screen. A contact that
    was READY on the last call and has since replied, been suppressed, or
    had its approval invalidated will NOT appear in this call's result.
    """
    mod = _load_screen_module()
    screen = mod.Screen(recs, config)
    report = {}
    for channel in ("linkedin", "email"):
        rows = mod.run(channel, recs, config, campaigns_by_id, screen)
        for row in rows:
            row["class"] = mod.classify(row)
        ready_rows = [r for r in rows if r["class"] == "READY_NOW"]
        gates = collections.Counter(r["gate"] or "PASS" for r in rows)
        buckets = collections.Counter(r["class"] for r in rows)
        report[channel] = {
            "ready": [
                {
                    "contact": r["contact"],
                    "account_hash": r["account_hash"],
                    "persona": r.get("persona"),
                    "verified_email": r.get("verified_email"),
                    "reason": r.get("why") or "every contact-level gate passes",
                    "steps_rendered": r.get("steps_rendered", []),
                }
                for r in ready_rows
            ],
            "depth": len(ready_rows),
            "population": len(rows),
            "blockers": dict(gates),
            "buckets": dict(buckets),
        }
    return report


def depth_and_blockers(report):
    """A summary of the reservoir: how many are READY, and what stops the rest.

    Returns a dict with per-channel depth and a ranked blocker list:
    the first gate that stops each contact, and how many it stops.
    """
    summary = {}
    for channel, data in report.items():
        blockers = data["blockers"]
        ranked = sorted(blockers.items(), key=lambda x: -x[1])
        summary[channel] = {
            "depth": data["depth"],
            "population": data["population"],
            "blockers_ranked": ranked,
            "buckets": data["buckets"],
        }
    return summary
