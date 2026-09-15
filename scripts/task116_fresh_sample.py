#!/usr/bin/env python3
"""TASK-116: Generate a fresh sample of email em1 steps and measure 'I noticed' rate.

Picks 10 records from the snapshot that have the data needed for email
generation, generates fresh em1 copy using the current prompt and model,
and counts how many open with 'I noticed'.

ZERO provider writes. Read-only at providers. Uses model for generation only.
"""
import json
import os
import re
import sys
import random

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SNAPSHOT = os.path.join(PROJECT_ROOT, "work", "queue.snapshot.jsonl")


def load_snapshot():
    with open(SNAPSHOT, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def has_required_data(rec):
    """Check if a record has the data needed for email generation."""
    cadence = rec.get("cadence", {})
    # Need at least one contact with email steps
    for contact_key, steps in cadence.items():
        em1 = steps.get("em1", {})
        # Need a body (even old) to show the record was once generatable
        if em1.get("body"):
            return True
    return False


def main():
    from src import generate, llm, clients

    recs = load_snapshot()
    eligible = [r for r in recs if has_required_data(r)]
    print(f"Snapshot: {len(recs)} records, {len(eligible)} with email data")

    # Pick a random sample of 10
    random.seed(42)  # Reproducible
    sample = random.sample(eligible, min(10, len(eligible)))

    # Load env from config/.env
    env_path = os.path.join(PROJECT_ROOT, "config", ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    model = llm.from_env()
    model_name = os.environ.get("LLM_MODEL", "?")

    print(f"Model: {model_name}")
    print()

    results = []
    for i, rec in enumerate(sample):
        rec_id = rec.get("id", "?")
        cadence = rec.get("cadence", {})

        # Find first contact with em1
        contact_key = None
        for ck, steps in cadence.items():
            if steps.get("em1", {}).get("body"):
                contact_key = ck
                break

        if not contact_key:
            print(f"  [{i+1}] {rec_id}: no contact with em1, skipping")
            continue

        contact = cadence[contact_key]

        # Load client config
        try:
            client = clients.load(rec.get("client"))
        except Exception as e:
            print(f"  [{i+1}] {rec_id}: cannot load client: {e}")
            continue

        # Render the prompt for em1
        try:
            prompt = generate.render_prompt("draft", rec, contact, client, "em1")
        except Exception as e:
            print(f"  [{i+1}] {rec_id}/{contact_key}: prompt render failed: {e}")
            continue

        # Generate
        try:
            data, raw, schema_errors = llm.ask(model, "draft", prompt)
            if schema_errors:
                print(f"  [{i+1}] {rec_id}/{contact_key}: schema errors: {schema_errors}")
                continue

            body = data.get("body", "")
            subject = data.get("subject", "")
            opens_i_noticed = bool(re.match(r'^I noticed\b', body.strip(), re.IGNORECASE))

            results.append({
                "record_id": rec_id,
                "contact": contact_key,
                "subject": subject,
                "body_preview": body[:120],
                "opens_i_noticed": opens_i_noticed,
            })

            marker = " <-- 'I noticed'" if opens_i_noticed else ""
            print(f"  [{i+1}] {rec_id}/{contact_key}{marker}")
            print(f"       Subject: {subject}")
            print(f"       Body: {body[:120]}...")
            print()

        except Exception as e:
            print(f"  [{i+1}] {rec_id}/{contact_key}: generation failed: {e}")
            continue

    # Summary
    print("=" * 60)
    print(f"  FRESH SAMPLE RESULTS")
    print("=" * 60)
    total = len(results)
    i_noticed = sum(1 for r in results if r["opens_i_noticed"])
    print(f"  Generated: {total}")
    print(f"  Open 'I noticed': {i_noticed} ({100*i_noticed/max(1,total):.0f}%)")
    print()

    # Also show opener distribution
    openers = {}
    for r in results:
        words = " ".join(r["body_preview"].strip().split()[:4]).lower()
        openers[words] = openers.get(words, 0) + 1
    print("  Opener distribution (first 4 words):")
    for opener, count in sorted(openers.items(), key=lambda x: -x[1]):
        marker = " <--" if "i noticed" in opener else ""
        print(f"    {count}  {opener}{marker}")


if __name__ == "__main__":
    main()
