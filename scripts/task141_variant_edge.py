#!/usr/bin/env python3
"""TASK-141: Verify whether parent-step sends coexist with variant sends.

The question: when a scheduled email's sequence_step_id points to a PARENT
step that HAS variants, does that mean (a) no variant was used, or (b) the
variant information is lost?

We check by looking at the events for the same lead+step combination and
seeing whether sequence_step_variant is None or an integer.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.providers import load_env
load_env()

import urllib.request
import urllib.parse

BASE = os.environ.get("BISON_BASE", "https://send.resonategroup.co/api").rstrip("/")
KEY = os.environ["BISON_KEY"]


def _get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main():
    print("=== VARIANT EDGE CASE PROBE ===\n")

    # Campaign 352, step 4035 is a parent with variants [4036, 4192, 4193, 4194, 4195, 4196]
    # Reply 1609203 → scheduled_email 22310389 → step 4035 (parent)
    # Reply 1609200 → scheduled_email 22310733 → step 4036 (variant)

    # Check: do scheduled emails to step 4035 and step 4036 coexist for the same campaign?
    print("1. Scheduled emails for campaign 352, sampling step ids:")
    data = _get("/campaigns/352/scheduled-emails", {"per_page": 15, "page": 1})
    rows = data.get("data", [])
    step_counts = {}
    for r in rows:
        sid = r.get("sequence_step_id")
        step_counts[sid] = step_counts.get(sid, 0) + 1
    print(f"   First 15 rows - step id distribution: {step_counts}")

    # Check a few more pages
    for page in [2, 5, 10]:
        data = _get("/campaigns/352/scheduled-emails", {"per_page": 15, "page": page})
        rows = data.get("data", [])
        step_counts = {}
        variant_count = 0
        parent_count = 0
        for r in rows:
            sid = r.get("sequence_step_id")
            step_counts[sid] = step_counts.get(sid, 0) + 1
        print(f"   Page {page} - step ids: {step_counts}")

    # Now check events for step 4035 specifically
    print("\n2. Events for step 4035 (parent) vs step 4036 (variant):")
    events_data = _get("/events", {"per_page": 15, "pagination_type": "cursor"})
    events = events_data.get("data", [])
    for ev in events:
        se = ev.get("payload", {}).get("data", {}).get("scheduled_email", {})
        step_id = se.get("sequence_step_id")
        variant = se.get("sequence_step_variant")
        etype = ev.get("payload", {}).get("event", {}).get("type", "?")
        if step_id in (4035, 4036, 4040, 4041, 4042):
            print(f"   Event {ev['id']}: {etype}, step={step_id}, "
                  f"variant_idx={variant}, lead={se.get('lead_id')}")

    # Check: does the scheduled email for a VARIANT step carry any extra field?
    print("\n3. Comparing scheduled email fields: parent vs variant step")
    # Parent step send
    se_parent = _get("/scheduled-emails/22310389")  # reply 1609203's send
    if isinstance(se_parent.get("data"), dict):
        se_parent = se_parent["data"]
    # Variant step send
    se_variant = _get("/scheduled-emails/22310733")  # reply 1609200's send
    if isinstance(se_variant.get("data"), dict):
        se_variant = se_variant["data"]

    parent_keys = set(se_parent.keys())
    variant_keys = set(se_variant.keys())
    print(f"   Parent step send keys: {sorted(parent_keys)}")
    print(f"   Variant step send keys: {sorted(variant_keys)}")
    print(f"   Keys only in parent: {parent_keys - variant_keys}")
    print(f"   Keys only in variant: {variant_keys - parent_keys}")
    print(f"   Parent: step_id={se_parent.get('sequence_step_id')}, "
          f"subject='{se_parent.get('email_subject', '')[:60]}'")
    print(f"   Variant: step_id={se_variant.get('sequence_step_id')}, "
          f"subject='{se_variant.get('email_subject', '')[:60]}'")

    # Check: sequence steps for campaign 328 (no variants)
    print("\n4. Campaign 328 step structure (no variants expected):")
    steps_data = _get("/campaigns/328/sequence-steps")
    steps = steps_data.get("data", [])
    for s in steps:
        vflag = "VARIANT" if s.get("variant") else "parent"
        print(f"   step {s['id']}: order={s.get('order')}, {vflag}, "
              f"variant_from_step={s.get('variant_from_step')}")

    print("\nDone.")


if __name__ == "__main__":
    main()
