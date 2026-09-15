#!/usr/bin/env python3
"""Find records with LinkedIn variants for inspection."""
import json

with open('work/queue.snapshot.jsonl', encoding='utf-8') as f:
    for i, line in enumerate(f):
        rec = json.loads(line)
        cadence = rec.get('cadence', {})
        steps = cadence.get('steps', [])
        for step in steps:
            if step.get('key') in ['li2', 'li3', 'li4']:
                variants = step.get('variants', [])
                if variants:
                    print(f"\n=== Record {i}: {rec.get('id')} - Step {step.get('key')} ===")
                    print(f"Company: {rec.get('company')}")
                    print(f"Contact: {step.get('contact')}")
                    for v in variants:
                        print(f"\n--- Approach: {v.get('style')} ---")
                        print(f"Body: {v.get('body', '')[:200]}")
                    # Just show first 3 records with variants
                    if i > 10:
                        break
