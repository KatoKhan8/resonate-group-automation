#!/usr/bin/env python3
"""TASK-116: Check approval structure and count discrepancy."""
import json
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(PROJECT_ROOT, "work", "queue.snapshot.jsonl")


def load_snapshot():
    with open(SNAPSHOT, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    recs = load_snapshot()

    # Check approval structure for a known approved step
    for rec in recs:
        if rec.get("id") == "1gslab-com":
            cadence = rec.get("cadence", {})
            steps = cadence.get("claudia-papa", {})
            em2 = steps.get("em2", {})
            print("=== 1gslab-com/claudia-papa/em2 ===")
            print(f"  Keys: {list(em2.keys())}")
            print(f"  approval: {em2.get('approval')}")
            print(f"  approval type: {type(em2.get('approval'))}")
            print(f"  generated: {em2.get('generated')}")
            print()

            # Check all email steps for this contact
            for sk in ["em1", "em2", "em3", "em4", "em5"]:
                step = steps.get(sk, {})
                if step:
                    appr = step.get("approval")
                    print(f"  {sk}: approval={appr}")
            break

    # Count total email steps and "I noticed" more carefully
    total_with_body = 0
    i_noticed_count = 0
    i_noticed_steps = []

    for rec in recs:
        rec_id = rec.get("id", "?")
        cadence = rec.get("cadence", {})
        for contact_key, steps in cadence.items():
            for step_key in ["em1", "em2", "em3", "em4", "em5"]:
                step = steps.get(step_key, {})
                body = step.get("body", "")
                if not body:
                    continue
                total_with_body += 1
                if re.match(r'^I noticed\b', body.strip(), re.IGNORECASE):
                    i_noticed_count += 1
                    i_noticed_steps.append(f"{rec_id}/{contact_key}/{step_key}")

    print(f"\n=== COUNTS ===")
    print(f"Total email steps with body: {total_with_body}")
    print(f"Steps opening 'I noticed': {i_noticed_count}")
    print(f"\nStep IDs:")
    for s in sorted(i_noticed_steps):
        print(f"  {s}")

    # Check if any records have contacts with 5 email steps
    full_contacts = 0
    for rec in recs:
        cadence = rec.get("cadence", {})
        for contact_key, steps in cadence.items():
            email_steps = [sk for sk in ["em1", "em2", "em3", "em4", "em5"]
                           if steps.get(sk, {}).get("body")]
            if len(email_steps) == 5:
                full_contacts += 1
    print(f"\nContacts with all 5 email steps: {full_contacts}")


if __name__ == "__main__":
    main()
