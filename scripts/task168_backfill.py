#!/usr/bin/env python3
"""TASK-168: backfill hold_reason on the 36 held records.

Reads the queue, classifies each held record using its log entries and
contact verdicts, writes hold_reason, hold_class and hold_at.

Classification is reconstructable from the data because TASK-161 proved
all 36 are reconstructable. This script does NOT call any provider.

Usage:
    python scripts/task168_backfill.py              dry run, prints plan
    python scripts/task168_backfill.py --apply      writes to the queue

The --apply path uses store.transaction() for atomic write.
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src import store, holdreasons


def classify_from_log(rec):
    """Reconstruct the hold reason from log entries and contact verdicts.

    Returns (reason_code, detail_string) or (None, None) if unclassifiable.
    """
    log = rec.get("log") or []
    contacts = rec.get("contacts") or []

    # Check for un-drop: log contains step "un-dropped"
    for entry in log:
        if entry.get("step") == "un-dropped":
            return (holdreasons.UNDROP_PENDING_REENRICHMENT,
                    entry.get("note", "un-dropped"))

    # Check for generation model errors: log contains "held:" in note
    # on a persona_angle or draft step
    for entry in reversed(log):
        note = entry.get("note", "")
        step = entry.get("step", "")
        if step in ("persona_angle", "draft", "hook", "diagnose",
                     "linkedin_note", "linkedin_set", "variant_set"):
            if note.startswith("held:"):
                msg = note[5:].strip()
                if "not traceable" in msg:
                    return (holdreasons.GENERATION_EVIDENCE_TRACE, msg)
                if ("non-empty list" in msg
                        or ("evidence" in msg and "empty" in msg)):
                    return (holdreasons.GENERATION_EVIDENCE_EMPTY, msg)
                if "not JSON" in msg or "JSON" in msg:
                    return (holdreasons.GENERATION_JSON_PARSE, msg)
                if "lint" in msg.lower():
                    return (holdreasons.GENERATION_LINT_FAILURE, msg)
                return (f"generation:{step}:{msg[:60]}", msg)

    # Check for enrichment holds: contacts with unresolved verdicts
    verdicts = [c.get("verdict") for c in contacts]
    unresolved = [v for v in verdicts
                  if v in (None, "unknown", "accept_all")]
    if unresolved:
        if all(v == "accept_all" for v in unresolved):
            return (holdreasons.ENRICH_ACCEPT_ALL_UNCLEARED,
                    f"{len(unresolved)} contact(s) accept_all")
        return (holdreasons.ENRICH_UNRESOLVED_VERDICT,
                f"{len(unresolved)} contact(s) unresolved")

    # No contacts at all - enrichment found nobody
    if not contacts:
        # Check if this was an enrichment hold vs a no-contacts drop
        for entry in log:
            if entry.get("step") == "held":
                return (holdreasons.ENRICH_NO_CONTACTS,
                        entry.get("note", "no contacts"))
        return (holdreasons.ENRICH_NO_CONTACTS, "no contacts on record")

    # Verifier disagreement
    for entry in log:
        note = entry.get("note", "")
        if "verifiers disagree" in note.lower():
            return (holdreasons.ENRICH_VERIFIERS_DISAGREE, note)

    return None, None


def assess_return_safety(rec):
    """Can this record safely return to its queue?

    Returns (safe: bool, target_state: str|None, reason: str).
    """
    reason_code = rec.get("hold_reason", "")
    cls = holdreasons.classify(reason_code)

    if cls == holdreasons.ACTIONABLE:
        contacts = rec.get("contacts") or []
        unresolved = [c for c in contacts
                      if c.get("verdict") in (None, "unknown", "accept_all")]
        if not contacts:
            return False, None, "no contacts to re-enrich"
        if unresolved:
            return False, None, ("%d contact(s) still need enrichment"
                                 % len(unresolved))
        return True, "queued", "contacts present and resolved"

    if cls == holdreasons.RETRYABLE:
        return False, None, "requires model re-run (not free)"

    if cls == holdreasons.WAITING:
        contacts = rec.get("contacts") or []
        unresolved = [c for c in contacts
                      if c.get("verdict") in (None, "unknown", "accept_all")]
        if unresolved:
            return False, None, ("%d contact(s) still unresolved"
                                 % len(unresolved))
        return True, "queued", "all contacts resolved"

    return False, None, "%s: cannot return safely" % cls


def main(argv=None):
    p = argparse.ArgumentParser(description="TASK-168 hold_reason backfill")
    p.add_argument("--apply", action="store_true",
                   help="write changes to the queue (default: dry run)")
    a = p.parse_args(argv)

    recs = store.load()
    held = [r for r in recs if r.get("state") == "held"]

    print(f"Found {len(held)} held records")
    print()

    distribution = {}
    returned = 0
    kept = 0
    unclassifiable = 0

    for rec in held:
        rid = rec.get("id", "?")
        code, detail = classify_from_log(rec)
        if code is None:
            unclassifiable += 1
            print(f"  UNCLASSIFIABLE  {rid}")
            continue

        cls = holdreasons.classify(code)
        distribution[cls] = distribution.get(cls, 0) + 1

        safe, target, why = assess_return_safety(rec)

        if a.apply:
            holdreasons.set_hold_reason(rec, code, detail=detail)
            if safe and target:
                rec["state"] = target
                rec["returned_from_hold"] = {
                    "at": datetime.datetime.now(datetime.timezone.utc)
                        .replace(microsecond=0).isoformat(),
                    "reason": why,
                    "previous_hold_reason": code,
                }
                returned += 1
                print(f"  {cls:<14} {rid:<40} -> {target} ({why})")
            else:
                kept += 1
                print(f"  {cls:<14} {rid:<40} stays held ({why})")
        else:
            if safe and target:
                returned += 1
                print(f"  {cls:<14} {rid:<40} -> {target} ({why})")
            else:
                kept += 1
                print(f"  {cls:<14} {rid:<40} stays held ({why})")

    print()
    print("Distribution:")
    for cls in holdreasons.CLASSES:
        n = distribution.get(cls, 0)
        print(f"  {cls:<14} {n}")
    if unclassifiable:
        print(f"  {'UNCLASSIFIABLE':<14} {unclassifiable}")
    print()
    print(f"Return to queue: {returned}")
    print(f"Stay held:       {kept}")

    if a.apply:
        with store.transaction():
            pass
        print("\nChanges written to queue.")
    else:
        print("\nDry run. Pass --apply to write.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
