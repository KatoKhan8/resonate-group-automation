#!/usr/bin/env python3
"""TASK-116: Check the two multi-generation steps.

For the two steps that were generated more than once, check if the
'I noticed' opener survived regeneration. Also check if any lint
events exist for these steps.
"""
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(PROJECT_ROOT, "work", "queue.snapshot.jsonl")


def load_snapshot():
    with open(SNAPSHOT, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    recs = load_snapshot()

    # The two multi-gen steps
    targets = [
        ("1gslab-com", "claudia-papa", "em2"),
        ("<client-abb4a2>-com", "janie-karas", "em1"),
    ]

    for rec in recs:
        rec_id = rec.get("id")
        if rec_id not in [t[0] for t in targets]:
            continue

        for target_id, target_contact, target_step in targets:
            if rec_id != target_id:
                continue

            cadence = rec.get("cadence", {})
            steps = cadence.get(target_contact, {})
            step = steps.get(target_step, {})

            print(f"=== {rec_id}/{target_contact}/{target_step} ===")
            print(f"  Body (first 200 chars): {step.get('body', '')[:200]}")
            print(f"  Generated: {step.get('generated')}")
            print(f"  Approval: {step.get('approval')}")
            print()

            # Show ALL events for this contact/step
            events = rec.get("events", [])
            relevant = [e for e in events
                        if e.get("contact") == target_contact
                        and e.get("step") == target_step]
            relevant.sort(key=lambda e: e.get("at", ""))

            print(f"  Events ({len(relevant)}):")
            for ev in relevant:
                ev_type = ev.get("type")
                at = ev.get("at", "")
                extra = ""
                if ev_type == "lint_failed":
                    extra = f" failures={ev.get('failures')}"
                    extra += f" attempt={ev.get('attempt')}"
                elif ev_type == "draft_generated":
                    extra = f" generated={ev.get('generated')}"
                print(f"    {at}  {ev_type}{extra}")
            print()

            # Show ALL events for this contact (all steps) to see sequence
            all_contact_events = [e for e in events
                                  if e.get("contact") == target_contact]
            all_contact_events.sort(key=lambda e: e.get("at", ""))
            print(f"  All events for {target_contact} ({len(all_contact_events)}):")
            for ev in all_contact_events:
                ev_type = ev.get("type")
                at = ev.get("at", "")
                step_key = ev.get("step", "")
                extra = ""
                if ev_type == "lint_failed":
                    extra = f" failures={ev.get('failures')}"
                print(f"    {at}  {step_key}  {ev_type}{extra}")
            print()


if __name__ == "__main__":
    main()
