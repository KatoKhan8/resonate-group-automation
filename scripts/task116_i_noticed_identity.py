#!/usr/bin/env python3
"""TASK-116: Identify every 'I noticed' email opener by step identity.

Establishes whether the 49 openers are stale copy (same 49 steps, never
re-planned) or actively regenerated (set has churned, count held).

Reads work/queue.snapshot.jsonl. Zero writes. Zero provider calls.
"""
import json
import os
import re
import sys
import hashlib

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SNAPSHOT = os.path.join(PROJECT_ROOT, "work", "queue.snapshot.jsonl")


def hash_id(raw):
    """Deterministic hash for record ids - no PII in output."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def load_snapshot():
    with open(SNAPSHOT, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def get_first_line(text):
    """Extract the first non-empty line from a body."""
    for line in text.strip().split("\n"):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def analyze():
    recs = load_snapshot()

    email_steps = ["em1", "em2", "em3", "em4", "em5"]

    # Collect every email step with its identity
    all_email_steps = []
    i_noticed_steps = []
    total_contacts = 0
    contacts_with_generated = 0

    for rec in recs:
        rec_id = rec.get("id", "unknown")
        cadence = rec.get("cadence", {})

        for contact_key, steps in cadence.items():
            total_contacts += 1
            contact_has_generated = False

            for step_key in email_steps:
                step = steps.get(step_key, {})
                body = step.get("body", "")
                generated = step.get("generated", False)
                approved = step.get("approved", False)

                if not body:
                    continue

                if generated:
                    contact_has_generated = True

                first_line = get_first_line(body)
                first_line_lower = first_line.lower()

                # Check if the body CONTAINS "i noticed" anywhere
                has_i_noticed = bool(re.search(r'\bi noticed\b', body.lower()))

                # Check if the first line / opener IS "I noticed"
                opener_is_i_noticed = first_line_lower.startswith("i noticed")

                step_identity = {
                    "rec_hash": hash_id(rec_id),
                    "contact": contact_key,
                    "step": step_key,
                    "generated": generated,
                    "approved": approved,
                    "has_i_noticed": has_i_noticed,
                    "opener_is_i_noticed": opener_is_i_noticed,
                    "first_line": first_line[:120],
                    "body_len": len(body),
                }

                all_email_steps.append(step_identity)

                if has_i_noticed:
                    i_noticed_steps.append(step_identity)

            if contact_has_generated:
                contacts_with_generated += 1

    # Report
    print("=" * 80)
    print("  TASK-116: 'I NOTICED' OPENER IDENTITY ANALYSIS")
    print(f"  Snapshot: work/queue.snapshot.jsonl")
    print(f"  Records: {len(recs)}, Contacts: {total_contacts}")
    print(f"  Contacts with generated copy: {contacts_with_generated}")
    print("=" * 80)
    print()

    # Total email steps
    print(f"  Total email steps with body: {len(all_email_steps)}")
    print(f"  Steps containing 'i noticed': {len(i_noticed_steps)}")
    print()

    # Breakdown: generated vs not
    gen_count = sum(1 for s in i_noticed_steps if s["generated"])
    ungen_count = sum(1 for s in i_noticed_steps if not s["generated"])
    print(f"  Of the {len(i_noticed_steps)} 'i noticed' steps:")
    print(f"    generated=True:  {gen_count}")
    print(f"    generated=False: {ungen_count}")
    print()

    # Breakdown by step position
    by_step = {}
    for s in i_noticed_steps:
        by_step.setdefault(s["step"], []).append(s)
    print("  By step position:")
    for step_key in email_steps:
        steps_list = by_step.get(step_key, [])
        gen = sum(1 for s in steps_list if s["generated"])
        print(f"    {step_key}: {len(steps_list)} total, {gen} generated, "
              f"{len(steps_list) - gen} ungenerated")
    print()

    # Breakdown by record
    by_record = {}
    for s in i_noticed_steps:
        by_record.setdefault(s["rec_hash"], []).append(s)
    print(f"  Records with 'i noticed': {len(by_record)}")
    print(f"  Distribution:")
    dist = {}
    for rh, steps_list in by_record.items():
        n = len(steps_list)
        dist[n] = dist.get(n, 0) + 1
    for n in sorted(dist):
        print(f"    {n} step(s) with 'i noticed': {dist[n]} record(s)")
    print()

    # Opener analysis: how many have "I noticed" as the FIRST LINE vs somewhere in body
    opener_count = sum(1 for s in i_noticed_steps if s["opener_is_i_noticed"])
    body_only_count = sum(1 for s in i_noticed_steps if not s["opener_is_i_noticed"])
    print(f"  'i noticed' as first line (opener): {opener_count}")
    print(f"  'i noticed' in body but not opener: {body_only_count}")
    print()

    # Show the generated ones - these are the key finding
    if gen_count > 0:
        print("-" * 80)
        print("  GENERATED STEPS WITH 'I NOTICED' (the model keeps producing it)")
        print("-" * 80)
        for s in i_noticed_steps:
            if s["generated"]:
                print(f"    {s['rec_hash']}/{s['contact']}/{s['step']}: "
                      f"{s['first_line'][:100]}")
        print()

    # Show a sample of ungenerated ones
    if ungen_count > 0:
        print("-" * 80)
        print(f"  UNGENERATED STEPS WITH 'I NOTICED' (stale copy, first 10)")
        print("-" * 80)
        shown = 0
        for s in i_noticed_steps:
            if not s["generated"] and shown < 10:
                print(f"    {s['rec_hash']}/{s['contact']}/{s['step']}: "
                      f"approved={s['approved']}, {s['first_line'][:100]}")
                shown += 1
        if ungen_count > 10:
            print(f"    ... and {ungen_count - 10} more")
        print()

    # Full identity list for comparison (hash only)
    print("-" * 80)
    print("  FULL IDENTITY LIST (for set comparison)")
    print("-" * 80)
    for s in i_noticed_steps:
        gen_flag = "GEN" if s["generated"] else "old"
        print(f"    {s['rec_hash']}/{s['contact']}/{s['step']} [{gen_flag}]")
    print()

    # Summary verdict
    print("=" * 80)
    print("  VERDICT")
    print("=" * 80)
    if gen_count == 0:
        print("  ALL 49 ARE STALE COPY (generated=False).")
        print("  The model is NOT actively producing 'I noticed'.")
        print("  The fix is regeneration, not prompting.")
    elif ungen_count == 0:
        print("  ALL 'I NOTICED' STEPS ARE GENERATED (generated=True).")
        print("  The model IS actively producing 'I noticed'.")
        print("  A prompt or ladder change is needed.")
    else:
        print(f"  MIXED: {gen_count} generated, {ungen_count} ungenerated.")
        print(f"  The set has PARTIALLY churned.")
        print(f"  Both regeneration AND prompting may be needed.")
    print()

    # Additional: check what fraction of ALL generated email steps use "I noticed"
    all_gen = [s for s in all_email_steps if s["generated"]]
    gen_i_noticed = [s for s in all_gen if s["has_i_noticed"]]
    if all_gen:
        print(f"  Generated email steps overall: {len(all_gen)}")
        print(f"  Generated steps with 'i noticed': {len(gen_i_noticed)} "
              f"({100*len(gen_i_noticed)/len(all_gen):.1f}%)")
    print()

    # Check: what does the opener look like for generated steps that DON'T
    # use "I noticed"?
    gen_no_inoticed = [s for s in all_gen if not s["has_i_noticed"]]
    if gen_no_inoticed:
        opener_words = {}
        for s in gen_no_inoticed:
            first_word = s["first_line"].split()[0].lower() if s["first_line"] else ""
            opener_words[first_word] = opener_words.get(first_word, 0) + 1
        print(f"  First-word distribution in generated steps WITHOUT 'i noticed' "
              f"({len(gen_no_inoticed)} steps):")
        for word, count in sorted(opener_words.items(), key=lambda x: -x[1])[:15]:
            print(f"    '{word}': {count}")


if __name__ == "__main__":
    analyze()
