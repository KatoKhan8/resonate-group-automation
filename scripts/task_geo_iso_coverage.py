#!/usr/bin/env python3
"""Measure geo resolution coverage before and after the ISO-code bridge.

Reads live state via store.load(). For each record with a sendable contact:
  - "before" = resolve from company_facts country/city/state only (the old path)
  - "after"  = from_record with the ISO-code bridge (the new path)

Reports:
  - total records with a sendable contact
  - resolved before / after
  - breakdown by timezone_confidence
  - how many are schedulable
  - how many are US and therefore still held
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import geo, store


def _has_sendable_contact(rec):
    """A record that could receive a message if geo and cadence allow it."""
    contacts = (rec or {}).get("contacts") or []
    return any(c.get("email") or c.get("linkedin_url") for c in contacts)


def _resolve_old_way(rec):
    """The resolution before the ISO bridge: country/city/state only."""
    facts = (rec or {}).get("company_facts") or {}
    return geo.resolve(country=facts.get("country"), city=facts.get("city"),
                       state=facts.get("state") or facts.get("region"))


def measure():
    try:
        snapshot = store.load()
    except Exception as e:
        print(f"Cannot load live state: {e}")
        print("This script requires work/queue.jsonl (live state).")
        print("Run it from Claude's worktree, or after copying the queue.")
        return None

    records = list(snapshot)
    sendable = [r for r in records if _has_sendable_contact(r)]

    before_resolved = 0
    after_resolved = 0
    confidence_after = {}
    schedulable_count = 0
    us_held = 0

    for rec in sendable:
        old = _resolve_old_way(rec)
        new = geo.from_record(rec)

        if old.get("timezone"):
            before_resolved += 1
        if new.get("timezone"):
            after_resolved += 1
            conf = new.get("timezone_confidence", "unknown")
            confidence_after[conf] = confidence_after.get(conf, 0) + 1

        ok, _ = geo.schedulable(new)
        if ok:
            schedulable_count += 1

        if new.get("country_code") == "US" and not new.get("timezone"):
            us_held += 1

    result = {
        "records_with_sendable_contact": len(sendable),
        "resolved_before": before_resolved,
        "resolved_after": after_resolved,
        "by_timezone_confidence": confidence_after,
        "schedulable": schedulable_count,
        "us_held": us_held,
    }
    return result


def main():
    result = measure()
    if result is None:
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
