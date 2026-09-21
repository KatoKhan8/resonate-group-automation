#!/usr/bin/env python3
"""TASK-238: Measure whether HeyReach conversation items carry campaign/seat ids.

READ-ONLY. One call to POST /inbox/GetConversationsV2 with limit=1.
Prints the exact key set of one conversation object so the attribution
design can be decided from fact rather than documentation.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers import load_env
load_env()

from src.providers.heyreach import conversations

ATTRIBUTION_KEYS = ("campaignId", "linkedInAccountId", "campaign_id",
                    "linkedInAccountId", "accountId", "linkedinAccountId",
                    "campaignIds", "linkedInAccountIds",
                    "campaign", "account", "sender", "senderAccount")


def main():
    print("=" * 78)
    print("TASK-238 ATTRIBUTION PROBE")
    print("=" * 78)
    print()
    print("Calling POST /inbox/GetConversationsV2 with limit=3...")
    print()

    items, total = conversations(offset=0, limit=3)
    print(f"Total conversations in inbox: {total}")
    print(f"Returned: {len(items)}")
    print()

    if not items:
        print("NO ITEMS RETURNED. Cannot measure keys.")
        return

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            print(f"Item {i}: not a dict ({type(item).__name__})")
            continue
        print(f"--- Item {i} ---")
        print(f"  ALL KEYS: {sorted(item.keys())}")
        print()

        # Check for attribution keys specifically
        found = {k: item.get(k) for k in ATTRIBUTION_KEYS if k in item}
        missing = [k for k in ATTRIBUTION_KEYS if k not in item]
        print(f"  ATTRIBUTION KEYS FOUND: {found}")
        print(f"  ATTRIBUTION KEYS MISSING: {missing}")
        print()

        # Print values of known interesting keys (no PII)
        for key in ("id", "campaignId", "linkedInAccountId",
                     "lastMessageSender", "lastMessageAt"):
            if key in item:
                val = item[key]
                if key == "id":
                    # Hash conversation ids - they are PII-adjacent
                    import hashlib
                    hashed = hashlib.sha256(str(val).encode()).hexdigest()[:12]
                    print(f"  {key}: <hash:{hashed}>")
                else:
                    print(f"  {key}: {val}")
        print()

    print("=" * 78)
    print("DONE. READ-ONLY - no write route was called.")


if __name__ == "__main__":
    main()
