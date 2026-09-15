#!/usr/bin/env python3
"""TASK-158: find real LinkedIn profiles HeyReach already knows about."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers.heyreach import _read, list_leads

# Try the inbox conversations
print("--- Inbox conversations (first page) ---")
try:
    data = _read("/inbox/GetConversationsV2", {
        "filters": {},
        "offset": 0,
        "limit": 5,
    })
    items = data.get("items", [])
    print(f"  total: {data.get('totalCount', '?')}, got {len(items)}")
    for item in items:
        corr = item.get("correspondentProfile", {})
        url = corr.get("profileUrl", "?")
        name = f"{corr.get('firstName', '')} {corr.get('lastName', '')}".strip()
        print(f"  {name} -> {url}")
except Exception as e:
    print(f"  FAILED: {e}")

# Try campaign leads from the production campaign
print("\n--- Campaign leads (campaign 594061, first page) ---")
try:
    data = _read("/campaign/GetLeadsFromCampaign", {
        "campaignId": 594061,
        "offset": 0,
        "limit": 5,
    })
    items = data.get("items", [])
    print(f"  total: {data.get('totalCount', '?')}, got {len(items)}")
    for item in items:
        profile = item.get("linkedInUserProfile", {})
        url = profile.get("profileUrl", "?")
        pid = item.get("linkedInUserProfileId", "?")
        name = f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip()
        print(f"  {name} -> {url}  (id={pid})")
except Exception as e:
    print(f"  FAILED: {e}")

# Try list 940797
print("\n--- List 940797 ---")
try:
    items, total = list_leads(940797)
    print(f"  total: {total}")
    for item in items:
        print(f"  {json.dumps(item)}")
except Exception as e:
    print(f"  FAILED: {e}")

# Try the other list (933603) - READ ONLY
print("\n--- List 933603 (production list, read only) ---")
try:
    items, total = list_leads(933603)
    print(f"  total: {total}")
    for item in items[:5]:
        print(f"  {json.dumps(item)}")
except Exception as e:
    print(f"  FAILED: {e}")

# Try /list/GetAll to see all lists
print("\n--- All lists ---")
try:
    data = _read("/list/GetAll", {"offset": 0, "limit": 20})
    items = data.get("items", [])
    print(f"  total: {data.get('totalCount', '?')}, got {len(items)}")
    for item in items:
        print(f"  list {item.get('id')}: {item.get('name', '?')} "
              f"({item.get('totalItemsCount', 0)} items, "
              f"campaigns={item.get('campaignIds', [])})")
except Exception as e:
    print(f"  FAILED: {e}")
