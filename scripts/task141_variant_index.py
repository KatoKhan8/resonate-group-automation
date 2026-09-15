#!/usr/bin/env python3
"""TASK-141: Verify what sequence_step_variant actually is.

The earlier docs said it was the step id of the variant. The first run
showed values like 2, 5, 3 which are too small to be step ids (step ids
are in the 4000s). This script checks whether it is a variant INDEX
(1=A, 2=B, 3=C...) within a parent step.
"""
import json
import os
import urllib.request
import urllib.error

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "config", ".env")
def load_env():
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

BASE = os.environ.get("BISON_BASE", "https://send.resonategroup.co/api").rstrip("/")
KEY = os.environ.get("BISON_KEY", "")

def api_get(path):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    # Get campaign 352 steps and build the variant map
    print("=== Campaign 352 step structure ===")
    status, data = api_get("/campaigns/352/sequence-steps")
    steps = data.get("data", [])

    # Build parent -> variants map
    parent_variants = {}
    step_map = {}
    for s in steps:
        step_map[s["id"]] = s
        if s.get("variant"):
            parent_id = s.get("variant_from_step")
            parent_variants.setdefault(parent_id, []).append(s)

    # Sort each parent's variants by id to determine index
    for parent_id, variants in parent_variants.items():
        variants.sort(key=lambda x: x["id"])
        print(f"\nParent step {parent_id} (order={step_map[parent_id].get('order')}):")
        for i, v in enumerate(variants, 1):
            print(f"  Variant index {i}: step_id={v['id']}, subject={v.get('email_subject', '')[:60]}")

    # Now get events and cross-reference
    print("\n=== Events cross-reference ===")
    status, data = api_get("/events?pagination_type=cursor&per_page=15")
    events = data.get("data", [])

    for ev in events:
        payload = ev.get("payload", {})
        event_type = payload.get("event", {}).get("type", "?")
        if event_type != "EMAIL_SENT":
            continue
        sched = payload.get("data", {}).get("scheduled_email", {})
        step_id = sched.get("sequence_step_id")
        step_order = sched.get("sequence_step_order")
        step_variant = sched.get("sequence_step_variant")

        if step_variant is not None and step_id in step_map:
            step = step_map[step_id]
            is_variant = step.get("variant", False)
            parent_id = step.get("variant_from_step")
            if is_variant and parent_id in parent_variants:
                # Find the index of this step among its siblings
                siblings = parent_variants[parent_id]
                idx = next((i for i, s in enumerate(siblings, 1) if s["id"] == step_id), "?")
                print(f"  step_id={step_id}, variant_index_in_event={step_variant}, computed_index={idx}, parent={parent_id}")
            elif not is_variant:
                print(f"  step_id={step_id}, variant_index_in_event={step_variant}, is_parent_step (not variant)")
        elif step_variant is not None:
            print(f"  step_id={step_id} NOT in campaign 352 steps, variant={step_variant}")


if __name__ == "__main__":
    main()
