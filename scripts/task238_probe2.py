#!/usr/bin/env python3
"""TASK-238 follow-up: check the linkedInAccount sub-object for campaign info."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers import load_env
load_env()

from src.providers.heyreach import conversations

def main():
    # Filter to our seat to see if the sub-object carries more
    items, total = conversations(offset=0, limit=10,
                                  filters={"linkedInAccountIds": [174892]})
    print(f"Conversations on seat 174892: {len(items)} (of {total} total)")
    for i, item in enumerate(items[:3]):
        if not isinstance(item, dict):
            continue
        lia = item.get("linkedInAccount")
        print(f"\n--- Item {i} ---")
        print(f"  linkedInAccountId: {item.get('linkedInAccountId')}")
        print(f"  linkedInAccount type: {type(lia).__name__}")
        if isinstance(lia, dict):
            print(f"  linkedInAccount keys: {sorted(lia.keys())}")
            print(f"  linkedInAccount: {json.dumps(lia, indent=4, default=str)[:500]}")
        cp = item.get("correspondentProfile")
        if isinstance(cp, dict):
            print(f"  correspondentProfile keys: {sorted(cp.keys())}")

    # Also check a few from other seats
    print("\n\n--- Other seats ---")
    items2, _ = conversations(offset=0, limit=5)
    for item in items2[:5]:
        aid = item.get("linkedInAccountId")
        if aid != 174892:
            print(f"  Seat {aid}: keys = {sorted(item.keys())}")
            lia = item.get("linkedInAccount")
            if isinstance(lia, dict):
                print(f"    linkedInAccount keys: {sorted(lia.keys())}")
            break

if __name__ == "__main__":
    main()
