#!/usr/bin/env python3
"""Dry-run impact analysis: which stored steps does the ladder change affect?

TASK-075 rewrote LINKEDIN_DEFAULT_LADDER (all 6 rungs) and EMAIL_FIVE_LADDER
(rungs 1, 3, 4). This script reads the queue and reports:

  1. How many stored steps use changed ladder rungs
  2. How many of those carry a current approval
  3. Per-record breakdown

Nothing is modified. No regeneration, no deletion, no provider calls.

  python -m scripts.ladder_impact
  python -m scripts.ladder_impact --json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import cadencelibrary, store, approval, lint


# TASK-075 changed these rungs (1-indexed ordinals within their channel).
# Email rung 5 was explicitly NOT changed (TASK-047 invariant).
# Email rung 2 was NOT changed (same text as before).
EMAIL_CHANGED_RUNGS = frozenset({1, 3, 4})

# All 6 LinkedIn rungs were rewritten.
LINKEDIN_CHANGED_RUNGS = frozenset({1, 2, 3, 4, 5, 6})


def _sequence_for_record(rec):
    """Resolve the sequence this record runs, matching cadencelibrary.

    Returns the sequence tuple or None.
    """
    from src import cadence, clients

    config = None
    try:
        config = clients.load(rec.get("client"))
    except Exception:
        config = None
    return cadence.steps_for(campaign=None, config=config, rec=rec)


def _position_in_channel(sequence, step_key):
    """Return (channel, ordinal_1based) for a step key, or (None, None)."""
    for spec in sequence or ():
        if spec.get("key") != step_key:
            continue
        channel = spec.get("channel")
        same = [s for s in sequence if s.get("channel") == channel]
        keys = [s.get("key") for s in same]
        return channel, keys.index(step_key) + 1
    return None, None


def _ladder_changed(channel, ordinal):
    """Did this ladder rung change in TASK-075?"""
    if channel == "email":
        return ordinal in EMAIL_CHANGED_RUNGS
    elif channel == "linkedin":
        return ordinal in LINKEDIN_CHANGED_RUNGS
    return False


def analyze_record(rec):
    """Analyze one record. Returns a dict with impact details."""
    sequence = _sequence_for_record(rec)
    cadence_rows = rec.get("cadence") or {}

    affected_steps = []
    unaffected_steps = []
    non_generated_steps = []

    for contact_key, steps in cadence_rows.items():
        for step_key, stored in steps.items():
            if not isinstance(stored, dict):
                continue
            channel = stored.get("channel")
            if not channel:
                continue

            # Check if this step has stored copy (generated, not template)
            has_copy = bool(stored.get("body") or stored.get("note")
                            or stored.get("subject"))
            if not has_copy:
                non_generated_steps.append({
                    "contact": contact_key,
                    "step": step_key,
                    "channel": channel,
                })
                continue

            # Resolve position in sequence
            seq_channel, ordinal = _position_in_channel(sequence, step_key)
            if seq_channel is None:
                # Step not in current sequence - orphaned or from old cadence
                unaffected_steps.append({
                    "contact": contact_key,
                    "step": step_key,
                    "channel": channel,
                    "reason": "not_in_sequence",
                })
                continue

            changed = _ladder_changed(seq_channel, ordinal)
            has_approval = bool(
                (stored.get("approval") or {}).get("fingerprint"))
            approval_current = False
            if has_approval:
                approval_current = approval.is_approved(
                    rec, contact_key, step_key, stored)

            entry = {
                "contact": contact_key,
                "step": step_key,
                "channel": channel,
                "ordinal": ordinal,
                "has_approval": has_approval,
                "approval_current": approval_current,
            }

            if changed:
                affected_steps.append(entry)
            else:
                unaffected_steps.append(entry)

    return {
        "record_id": rec.get("id"),
        "state": rec.get("state"),
        "client": rec.get("client"),
        "sequence_keys": [s.get("key") for s in (sequence or ())],
        "affected": affected_steps,
        "unaffected": unaffected_steps,
        "non_generated": non_generated_steps,
    }


def analyze_queue(recs):
    """Analyze every record. Returns summary and per-record details."""
    results = []
    total_affected = 0
    total_affected_with_approval = 0
    total_unaffected = 0
    total_non_generated = 0

    for rec in recs:
        result = analyze_record(rec)
        results.append(result)
        n_affected = len(result["affected"])
        n_approved = sum(1 for s in result["affected"]
                         if s["has_approval"] and s["approval_current"])
        total_affected += n_affected
        total_affected_with_approval += n_approved
        total_unaffected += len(result["unaffected"])
        total_non_generated += len(result["non_generated"])

    return {
        "summary": {
            "total_records": len(recs),
            "records_with_affected_steps": sum(
                1 for r in results if r["affected"]),
            "total_affected_steps": total_affected,
            "total_affected_with_current_approval":
                total_affected_with_approval,
            "total_unaffected_steps": total_unaffected,
            "total_non_generated": total_non_generated,
        },
        "records": results,
    }


def format_report(result):
    """Human-readable report."""
    s = result["summary"]
    lines = [
        "=" * 70,
        "LADDER IMPACT ANALYSIS - TASK-075 DRY RUN",
        "=" * 70,
        "",
        f"Records analysed:              {s['total_records']}",
        f"Records with affected steps:   {s['records_with_affected_steps']}",
        f"Total affected steps:          {s['total_affected_steps']}",
        f"  with current approval:       "
        f"{s['total_affected_with_current_approval']}",
        f"Total unaffected steps:        {s['total_unaffected_steps']}",
        f"Total non-generated/template:  {s['total_non_generated']}",
        "",
        "Changed rungs:",
        f"  Email:    positions {sorted(EMAIL_CHANGED_RUNGS)} "
        f"(of 5; rung 5 unchanged per TASK-047)",
        f"  LinkedIn: positions {sorted(LINKEDIN_CHANGED_RUNGS)} "
        f"(all 6 rungs rewritten)",
        "",
    ]

    for rec_result in result["records"]:
        if not rec_result["affected"] and not rec_result["unaffected"]:
            continue
        rid = rec_result["record_id"]
        lines.append(f"--- {rid} ({rec_result['state']}) ---")
        if rec_result["affected"]:
            lines.append(f"  AFFECTED ({len(rec_result['affected'])} steps):")
            for step in rec_result["affected"]:
                appr = ("APPROVED" if step["approval_current"]
                        else "stale" if step["has_approval"]
                        else "no approval")
                lines.append(
                    f"    {step['contact']}:{step['step']:<6} "
                    f"{step['channel']:<9} rung {step['ordinal']}  "
                    f"[{appr}]")
        if rec_result["unaffected"]:
            lines.append(
                f"  UNAFFECTED ({len(rec_result['unaffected'])} steps):")
            for step in rec_result["unaffected"]:
                reason = step.get("reason", "unchanged_rung")
                lines.append(
                    f"    {step['contact']}:{step['step']:<6} "
                    f"{step['channel']:<9} [{reason}]")
        lines.append("")

    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Ladder impact dry-run analysis (TASK-075)")
    p.add_argument("--json", action="store_true",
                   help="Output JSON instead of text")
    args = p.parse_args(argv)

    if not os.path.exists(store.queue_path()):
        print(f"ERROR: queue not found at {store.queue_path()}",
              file=sys.stderr)
        print("This script must be run from a worktree with work/ present.",
              file=sys.stderr)
        return 1

    with store.transaction() as recs:
        result = analyze_queue(recs)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(format_report(result))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
