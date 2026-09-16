#!/usr/bin/env python3
"""TASK-158: probe with real profiles HeyReach already knows about.

Uses <name_hash_1> (in campaign 594061) and <name_hash_2> (in inbox) to
resolve linkedin_id and probe the list add schema.

List 940797 ONLY. 0 items, no campaign, nothing can be sent.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers.heyreach import (
    BASE, headers, lead_profile, list_leads, _read, _write_body,
)
from src.providers import request, ok

LIST_ID = 940797

# Real profiles from the HeyReach system (PII hashed)
PROFILES = [
    # From campaign 594061 - we know the linkedInUserProfileId
    {"url": "https://www.linkedin.com/in/<profile_hash_1>",
     "known_id": "<id_hash_1>",
     "name": "<name_hash_1>"},
    # From inbox conversations
    {"url": "https://www.linkedin.com/in/<profile_hash_2>",
     "known_id": None,
     "name": "<name_hash_2>"},
]


def raw_add(body):
    """Send a raw POST to /list/AddLeadsToListV2."""
    url = f"{BASE}/list/AddLeadsToListV2"
    status, data = request("POST", url, headers(), body)
    return status, data


def readback():
    items, total = list_leads(LIST_ID)
    print(f"  readback: {total} items")
    for item in items:
        print(f"    {json.dumps(item, ensure_ascii=False)}")
    return items, total


def main():
    print("=" * 70)
    print("TASK-158: probe with real profiles")
    print("=" * 70)

    # Step 0: confirm list is empty
    print("\n--- Step 0: readback ---")
    readback()

    probe_count = 0

    for prof in PROFILES:
        url = prof["url"]
        name = prof["name"]
        known_id = prof.get("known_id")

        print(f"\n{'='*50}")
        print(f"Profile: {name} ({url})")
        print(f"{'='*50}")

        # Resolve via /lead/GetLead
        print(f"\n  /lead/GetLead...")
        try:
            raw = _read("/lead/GetLead", {"profileUrl": url})
            print(f"  keys: {sorted(raw.keys())}")
            linkedin_id = raw.get("linkedin_id")
            profile_id = raw.get("linkedInUserProfileId")
            print(f"  linkedin_id = {linkedin_id!r}")
            print(f"  linkedInUserProfileId = {profile_id!r}")
            print(f"  firstName = {raw.get('firstName')!r}")
            print(f"  lastName = {raw.get('lastName')!r}")
            print(f"  profileUrl = {raw.get('profileUrl')!r}")
        except Exception as e:
            print(f"  FAILED: {e}")
            linkedin_id = None
            profile_id = None

        # Use whichever id we got
        the_id = linkedin_id or profile_id or known_id
        print(f"\n  Using id: {the_id!r}")

        if not the_id:
            print("  No id available, skipping id-based probes")
            # Still try URL-based probes
            probe_count += 1
            print(f"\n  Probe {probe_count}: linkedInUrl only ---")
            body = {"listId": LIST_ID, "leads": [{"linkedInUrl": url}]}
            status, data = raw_add(body)
            print(f"  {status} {json.dumps(data)}")
            readback()
            continue

        # Probe A: linkedin_id as string
        probe_count += 1
        print(f"\n  Probe {probe_count}: linkedin_id={the_id} ---")
        body = {"listId": LIST_ID, "leads": [{"linkedin_id": str(the_id)}]}
        status, data = raw_add(body)
        print(f"  {status} {json.dumps(data)}")
        readback()

        # Probe B: linkedInUserProfileId
        probe_count += 1
        print(f"\n  Probe {probe_count}: linkedInUserProfileId={the_id} ---")
        body = {"listId": LIST_ID, "leads": [{"linkedInUserProfileId": str(the_id)}]}
        status, data = raw_add(body)
        print(f"  {status} {json.dumps(data)}")
        readback()

        # Probe C: linkedinId (camelCase)
        probe_count += 1
        print(f"\n  Probe {probe_count}: linkedinId={the_id} ---")
        body = {"listId": LIST_ID, "leads": [{"linkedinId": str(the_id)}]}
        status, data = raw_add(body)
        print(f"  {status} {json.dumps(data)}")
        readback()

        # Probe D: profileUrl (campaign-style)
        probe_count += 1
        print(f"\n  Probe {probe_count}: profileUrl={url} ---")
        body = {"listId": LIST_ID, "leads": [{"profileUrl": url}]}
        status, data = raw_add(body)
        print(f"  {status} {json.dumps(data)}")
        readback()

        if probe_count >= 12:
            print("\n  PROBE LIMIT REACHED (12)")
            break

    print(f"\n{'='*70}")
    print(f"Total probes used: {probe_count}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
