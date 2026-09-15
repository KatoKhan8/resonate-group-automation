#!/usr/bin/env python3
"""Find records with LinkedIn steps."""
import json

count = 0
with open('work/queue.snapshot.jsonl', encoding='utf-8') as f:
    for i, line in enumerate(f):
        rec = json.loads(line)
        cadence = rec.get('cadence', {})
        steps = cadence.get('steps', [])
        for step in steps:
            if step.get('key') in ['li2', 'li3', 'li4']:
                count += 1
                if count <= 5:
                    print(f"\nRecord {i}: {rec.get('id')} - Step {step.get('key')}")
                    print(f"  Company: {rec.get('company')}")
                    print(f"  Contact: {step.get('contact')}")
                    print(f"  Has variants: {bool(step.get('variants'))}")
                    if step.get('variants'):
                        print(f"  Variant count: {len(step.get('variants'))}")

print(f"\n\nTotal LinkedIn steps found: {count}")
