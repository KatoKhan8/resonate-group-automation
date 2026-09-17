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
    """A record that could receive a message if geo and cadence allow it.

    DELIBERATELY LOOSER THAN `verification.is_sendable`, and the difference is
    worth naming because the two denominators are both quoted in this
    repository: this counts a contact with an address OR a LinkedIn profile
    (88 records), while the email-sendability question counts only addresses
    two vendors cleared (67). Timezone matters for both channels, so the wider
    one is right here - but a coverage percentage taken from this script and
    compared against one taken from `verification_inventory.py` is comparing
    two populations.
    """
    contacts = (rec or {}).get("contacts") or []
    return any(c.get("email") or c.get("linkedin_url") for c in contacts)


def _resolve_old_way(rec):
    """REMOVED, because it answered a question it could not ask.

    This read `company_facts.country`, `.city` and `.state`. **No record in
    this estate carries any of those keys** - the location evidence lives in
    `company_facts.offices`, which is why the ISO bridge was needed at all. So
    it resolved nothing for every record and the script published
    `resolved_before: 0`, which reads as "the old code placed nobody" when it
    means "this function read three keys that do not exist".

    That is the same defect the queue manifest had the same morning: a count
    nobody could compute, published as a count of none. The honest answer to
    "how many resolved BEFORE" cannot be computed after the change is in the
    working tree, so the script says so instead of guessing.

    Measured by hand across the two trees, on the 67 records with a
    verification-sendable contact: 21 before, 33 after.
    """
    raise NotImplementedError("see the docstring: this cannot be measured here")


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

    after_resolved = 0
    confidence_after = {}
    schedulable_count = 0
    us_held = 0

    for rec in sendable:
        new = geo.from_record(rec)

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
        "resolved_before": "UNKNOWN - cannot be computed from the changed tree; measured by hand at 21 of 67 verification-sendable records, against 33 after",
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
