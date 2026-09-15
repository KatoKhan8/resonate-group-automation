#!/usr/bin/env python3
"""TASK-116: Identify the 49 'I noticed' email openers by step identity.

Reads work/queue.snapshot.jsonl (read-only, NOT live queue).
For each email step (em1-em5) whose body begins with 'I noticed',
records the step identity (record_id, contact, step_key) and the
last generation timestamp from events.

ZERO provider calls. ZERO writes. Read-only everywhere.
"""
import json
import os
import re
import sys
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(PROJECT_ROOT, "work", "queue.snapshot.jsonl")


def load_snapshot():
    with open(SNAPSHOT, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def get_last_generation_event(rec, contact, step_key):
    """Find the most recent draft_generated event for this step."""
    events = rec.get("events", [])
    candidates = []
    for ev in events:
        if (ev.get("type") == "draft_generated"
                and ev.get("contact") == contact
                and ev.get("step") == step_key
                and ev.get("channel") == "email"):
            candidates.append(ev.get("at", ""))
    candidates.sort()
    return candidates[-1] if candidates else None


def get_all_generation_events(rec, contact, step_key):
    """Find all draft_generated events for this step."""
    events = rec.get("events", [])
    candidates = []
    for ev in events:
        if (ev.get("type") == "draft_generated"
                and ev.get("contact") == contact
                and ev.get("step") == step_key
                and ev.get("channel") == "email"):
            candidates.append(ev.get("at", ""))
    candidates.sort()
    return candidates


def opener_is_i_noticed(body):
    """Check if the email body opens with 'I noticed'."""
    if not body:
        return False
    stripped = body.strip()
    return bool(re.match(r'^I noticed\b', stripped, re.IGNORECASE))


def main():
    recs = load_snapshot()
    print(f"Snapshot: {len(recs)} records")

    # Collect all email steps with body
    total_email_steps = 0
    i_noticed_steps = []
    all_openers = defaultdict(int)

    for rec in recs:
        rec_id = rec.get("id", "?")
        cadence = rec.get("cadence", {})

        for contact_key, steps in cadence.items():
            for step_key in ["em1", "em2", "em3", "em4", "em5"]:
                step = steps.get(step_key, {})
                body = step.get("body", "")
                if not body:
                    continue
                total_email_steps += 1

                if opener_is_i_noticed(body):
                    last_gen = get_last_generation_event(rec, contact_key, step_key)
                    all_gens = get_all_generation_events(rec, contact_key, step_key)
                    generated = step.get("generated", False)
                    approved = step.get("approval", {}).get("approved", False) if step.get("approval") else False

                    # Extract first 80 chars of body for context
                    first_line = body.strip()[:100]

                    i_noticed_steps.append({
                        "record_id": rec_id,
                        "contact": contact_key,
                        "step": step_key,
                        "last_generated": last_gen,
                        "generation_count": len(all_gens),
                        "all_generations": all_gens,
                        "generated_flag": generated,
                        "approved": approved,
                        "body_preview": first_line,
                    })

                # Track first few words for opener distribution
                words = body.strip().split()[:4]
                opener_key = " ".join(words).lower()
                all_openers[opener_key] += 1

    print(f"Total email steps with body: {total_email_steps}")
    print(f"Steps opening 'I noticed': {len(i_noticed_steps)}")
    print()

    # Distribution by step position
    by_step = defaultdict(list)
    for s in i_noticed_steps:
        by_step[s["step"]].append(s)

    print("=== DISTRIBUTION BY STEP POSITION ===")
    for step_key in ["em1", "em2", "em3", "em4", "em5"]:
        steps = by_step.get(step_key, [])
        print(f"  {step_key}: {len(steps)} steps")
    print()

    # Distribution by generation timestamp
    print("=== GENERATION TIMESTAMPS ===")
    by_date = defaultdict(int)
    for s in i_noticed_steps:
        if s["last_generated"]:
            date = s["last_generated"][:10]
            by_date[date] += 1
        else:
            by_date["NO_EVENT"] += 1
    for date in sorted(by_date.keys()):
        print(f"  {date}: {by_date[date]} steps")
    print()

    # Distribution by generation count
    print("=== GENERATION COUNT PER STEP ===")
    by_gen_count = defaultdict(int)
    for s in i_noticed_steps:
        by_gen_count[s["generation_count"]] += 1
    for count in sorted(by_gen_count.keys()):
        print(f"  {count} generation(s): {by_gen_count[count]} steps")
    print()

    # Generated flag
    gen_flag_true = sum(1 for s in i_noticed_steps if s["generated_flag"])
    gen_flag_false = len(i_noticed_steps) - gen_flag_true
    print(f"=== GENERATED FLAG ===")
    print(f"  generated=True:  {gen_flag_true}")
    print(f"  generated=False: {gen_flag_false}")
    print()

    # Approved flag
    approved_true = sum(1 for s in i_noticed_steps if s["approved"])
    approved_false = len(i_noticed_steps) - approved_true
    print(f"=== APPROVED FLAG ===")
    print(f"  approved=True:   {approved_true}")
    print(f"  approved=False:  {approved_false}")
    print()

    # Steps with multiple generations - did they get 'I noticed' twice?
    multi_gen = [s for s in i_noticed_steps if s["generation_count"] > 1]
    print(f"=== MULTI-GENERATION STEPS (re-generated, still 'I noticed') ===")
    print(f"  Count: {len(multi_gen)}")
    for s in multi_gen[:5]:
        print(f"    {s['record_id']}/{s['contact']}/{s['step']}: "
              f"generated {s['generation_count']}x, "
              f"timestamps: {s['all_generations']}")
    if len(multi_gen) > 5:
        print(f"    ... and {len(multi_gen) - 5} more")
    print()

    # Print the full set identity (hashed record IDs for PII safety)
    print("=== FULL SET IDENTITY (record_id hashed) ===")
    import hashlib
    step_ids = []
    for s in sorted(i_noticed_steps, key=lambda x: (x["record_id"], x["contact"], x["step"])):
        hashed = hashlib.sha256(s["record_id"].encode()).hexdigest()[:12]
        step_id = f"{hashed}/{s['contact']}/{s['step']}"
        step_ids.append(step_id)
        gen_info = s['last_generated'] or 'NO_EVENT'
        print(f"  {step_id}  gen={s['generation_count']}  last={gen_info}  approved={s['approved']}")
    print()

    # Top 15 openers for context
    print("=== TOP 15 OPENERS (first 4 words) ===")
    for opener, count in sorted(all_openers.items(), key=lambda x: -x[1])[:15]:
        marker = " <--" if "i noticed" in opener else ""
        print(f"  {count:3d}  {opener}{marker}")

    # Write the set identity to a file for comparison
    identity_file = os.path.join(PROJECT_ROOT, ".qwen", "tmp", "task116_step_ids.json")
    os.makedirs(os.path.dirname(identity_file), exist_ok=True)
    identity_data = []
    for s in sorted(i_noticed_steps, key=lambda x: (x["record_id"], x["contact"], x["step"])):
        identity_data.append({
            "record_id": s["record_id"],
            "contact": s["contact"],
            "step": s["step"],
            "last_generated": s["last_generated"],
            "generation_count": s["generation_count"],
            "generated_flag": s["generated_flag"],
            "approved": s["approved"],
        })
    with open(identity_file, "w", encoding="utf-8") as f:
        json.dump(identity_data, f, indent=2)
    print(f"\nStep identities written to {identity_file}")


if __name__ == "__main__":
    main()
