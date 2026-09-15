#!/usr/bin/env python3
"""TASK-116: Generate a fresh sample of 5 em1 drafts to test 'I noticed' rate.

Reads the snapshot, picks 5 records that currently have 'I noticed' in em1,
renders the prompt, generates a fresh draft, and checks whether the new
output still opens 'I noticed'.

Zero writes to the queue. Zero provider writes. Read-only everywhere except
the model call (which is a read of the model, not a write to the estate).
"""
import json
import hashlib
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src import llm, generate, clients, lint


def hash_id(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def main():
    model = llm.from_env()
    if not model.configured():
        print(f"ERROR: no model configured: {model.why_not()}")
        return 1

    snapshot = os.path.join(PROJECT_ROOT, "work", "queue.snapshot.jsonl")
    with open(snapshot, encoding="utf-8") as f:
        recs = [json.loads(line) for line in f if line.strip()]

    # Find records with 'I noticed' in em1
    candidates = []
    for rec in recs:
        cadence = rec.get("cadence", {})
        for ck, steps in cadence.items():
            em1 = steps.get("em1", {})
            body = em1.get("body", "")
            if body.lower().startswith("i noticed") and em1.get("generated"):
                contact_data = None
                for c in rec.get("contacts", []):
                    if lint.contact_key(c) == ck:
                        contact_data = c
                        break
                if contact_data:
                    candidates.append((rec, contact_data, ck))
                    break
        if len(candidates) >= 10:
            break

    # Pick 5 spread across the list
    step = max(1, len(candidates) // 5)
    sample = candidates[::step][:5]

    print("=" * 80)
    print("  TASK-116: FRESH GENERATION SAMPLE (5 em1 drafts)")
    print(f"  Model: {model.model if hasattr(model, 'model') else type(model).__name__}")
    print("=" * 80)
    print()

    i_noticed_count = 0
    results = []

    for i, (rec, contact_data, ck) in enumerate(sample):
        client = clients.load(rec.get("client"))
        prompt = generate.render_prompt("draft", rec, contact_data, client, "em1")

        rec_hash = hash_id(rec["id"])
        print(f"[{i+1}/5] {rec_hash}/{ck} - {rec.get('company')}")

        try:
            data, attempts, errors = llm.ask(model, "draft", prompt)
            body = data.get("body", "")
            subject = data.get("subject", "")
            has_in = bool(re.search(r'\bi noticed\b', body.lower()))
            first_line = ""
            for line in body.strip().split("\n"):
                if line.strip():
                    first_line = line.strip()
                    break

            if has_in:
                i_noticed_count += 1

            print(f"  Subject: {subject}")
            print(f"  First line: {first_line[:120]}")
            print(f"  'I noticed': {has_in}")
            print(f"  Attempts: {attempts}")
            print()

            results.append({
                "rec": rec_hash,
                "contact": ck,
                "company": rec.get("company"),
                "subject": subject,
                "first_line": first_line[:120],
                "i_noticed": has_in,
                "attempts": attempts,
            })
        except Exception as e:
            print(f"  ERROR: {e}")
            print()
            results.append({
                "rec": rec_hash,
                "contact": ck,
                "company": rec.get("company"),
                "error": str(e),
            })

    print("=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print(f"  Fresh 'I noticed' rate: {i_noticed_count} of {len(results)}")
    print()

    if i_noticed_count == 0:
        print("  The model NO LONGER produces 'I noticed' with the current prompt.")
        print("  The 48 in the estate are stale copy from before the quality gate.")
        print("  Regeneration with the current prompt would fix them.")
    elif i_noticed_count == len(results):
        print("  The model STILL produces 'I noticed' on every attempt.")
        print("  A prompt change is needed, not just regeneration.")
    else:
        print(f"  The model SOMETIMES produces 'I noticed' ({i_noticed_count}/{len(results)}).")
        print("  Partial regeneration would help; a prompt nudge would help more.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
