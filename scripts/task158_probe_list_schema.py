#!/usr/bin/env python3
"""TASK-158: find the schema /list/AddLeadsToListV2 actually accepts.

The route returns {addedLeadsCount: 0, updatedLeadsCount: 0, failedLeadsCount: 0}
for every shape tried so far, including populated lead objects. It silently
ignores what it does not recognise.

Hypothesis: the route wants linkedin_id (a numeric internal id) rather than
a URL. /lead/GetLead returns linkedin_id; /list/GetLeadsFromList returns
linkedInUserProfileId. A route that stores profiles by internal id would
ignore a URL exactly the way this one does.

Probes list 940797 ONLY. Attached to no campaign, holds 0 items, nothing
can be sent from it.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers.heyreach import (
    BASE, headers, lead_profile, list_leads, _read, _write_body,
    READ_ROUTES_ALL, WRITE_ROUTES,
)
from src.providers import request, ok

LIST_ID = 940797

# A real LinkedIn profile URL for probing. Willam Barbat is one of the
# HeyReach founders - his profile is public and HeyReach should recognise it.
PROBE_URL = "https://www.linkedin.com/in/william-barbat"


def readback():
    """Read the list and report what is in it."""
    items, total = list_leads(LIST_ID)
    print(f"  list has {total} items")
    for item in items:
        print(f"    {json.dumps(item, ensure_ascii=False)}")
    return items, total


def raw_add(body):
    """Send a raw POST to /list/AddLeadsToListV2 and return (status, data)."""
    url = f"{BASE}/list/AddLeadsToListV2"
    status, data = request("POST", url, headers(), body)
    return status, data


def main():
    print("=" * 70)
    print("TASK-158: probing /list/AddLeadsToListV2 schema")
    print("=" * 70)

    # Step 0: confirm list is empty
    print("\n--- Step 0: readback before any probe ---")
    readback()

    # Step 1: resolve the probe URL via /lead/GetLead
    print(f"\n--- Step 1: resolve {PROBE_URL} via /lead/GetLead ---")
    try:
        profile = lead_profile(PROBE_URL)
        print(f"  resolved: {json.dumps(profile, ensure_ascii=False, indent=2)}")
        linkedin_id = profile.get("linkedin_id")
        print(f"  linkedin_id = {linkedin_id}")
    except Exception as e:
        print(f"  FAILED: {e}")
        linkedin_id = None

    # Step 2: also get the raw response to see ALL fields
    print(f"\n--- Step 2: raw /lead/GetLead response ---")
    try:
        raw = _read("/lead/GetLead", {"profileUrl": PROBE_URL})
        print(f"  keys: {sorted(raw.keys())}")
        for k in ("linkedin_id", "linkedInUserProfileId", "profileUrl",
                   "firstName", "lastName"):
            print(f"  {k} = {raw.get(k)!r}")
    except Exception as e:
        print(f"  FAILED: {e}")
        raw = {}

    # Probe 1: linkedin_id as the sole identifier
    if linkedin_id:
        print(f"\n--- Probe 1: linkedin_id={linkedin_id} ---")
        body = {"listId": LIST_ID, "leads": [{"linkedin_id": str(linkedin_id)}]}
        print(f"  body: {json.dumps(body)}")
        status, data = raw_add(body)
        print(f"  response: {status} {json.dumps(data)}")
        readback()

    # Probe 2: linkedInUserProfileId
    if linkedin_id:
        print(f"\n--- Probe 2: linkedInUserProfileId={linkedin_id} ---")
        body = {"listId": LIST_ID, "leads": [{"linkedInUserProfileId": str(linkedin_id)}]}
        print(f"  body: {json.dumps(body)}")
        status, data = raw_add(body)
        print(f"  response: {status} {json.dumps(data)}")
        readback()

    # Probe 3: linkedInUrl + linkedin_id together
    if linkedin_id:
        print(f"\n--- Probe 3: linkedInUrl + linkedin_id ---")
        body = {"listId": LIST_ID, "leads": [{
            "linkedInUrl": PROBE_URL,
            "linkedin_id": str(linkedin_id),
        }]}
        print(f"  body: {json.dumps(body)}")
        status, data = raw_add(body)
        print(f"  response: {status} {json.dumps(data)}")
        readback()

    # Probe 4: profileUrl (campaign-style) instead of linkedInUrl
    print(f"\n--- Probe 4: profileUrl (campaign-style field name) ---")
    body = {"listId": LIST_ID, "leads": [{"profileUrl": PROBE_URL}]}
    print(f"  body: {json.dumps(body)}")
    status, data = raw_add(body)
    print(f"  response: {status} {json.dumps(data)}")
    readback()

    # Probe 5: linkedInUrl as the only field, no extras
    print(f"\n--- Probe 5: linkedInUrl only, nothing else ---")
    body = {"listId": LIST_ID, "leads": [{"linkedInUrl": PROBE_URL}]}
    print(f"  body: {json.dumps(body)}")
    status, data = raw_add(body)
    print(f"  response: {status} {json.dumps(data)}")
    readback()

    # Probe 6: linkedinId (camelCase, matching campaigns_for_lead's spelling)
    if linkedin_id:
        print(f"\n--- Probe 6: linkedinId (camelCase, campaigns_for_lead spelling) ---")
        body = {"listId": LIST_ID, "leads": [{"linkedinId": str(linkedin_id)}]}
        print(f"  body: {json.dumps(body)}")
        status, data = raw_add(body)
        print(f"  response: {status} {json.dumps(data)}")
        readback()

    # Probe 7: lead object wrapped, with linkedin_id
    if linkedin_id:
        print(f"\n--- Probe 7: wrapped lead with linkedin_id ---")
        body = {"listId": LIST_ID, "leads": [{"lead": {"linkedin_id": str(linkedin_id)}}]}
        print(f"  body: {json.dumps(body)}")
        status, data = raw_add(body)
        print(f"  response: {status} {json.dumps(data)}")
        readback()

    # Probe 8: linkedInUrl + firstName + lastName (the original shape, repeated
    # to confirm the baseline after all the id-based probes)
    print(f"\n--- Probe 8: baseline re-check (linkedInUrl + names) ---")
    body = {"listId": LIST_ID, "leads": [{
        "linkedInUrl": PROBE_URL,
        "firstName": "William",
        "lastName": "Barbat",
    }]}
    print(f"  body: {json.dumps(body)}")
    status, data = raw_add(body)
    print(f"  response: {status} {json.dumps(data)}")
    readback()

    print("\n" + "=" * 70)
    print("DONE. Review which probe (if any) changed the list count.")
    print("=" * 70)


if __name__ == "__main__":
    main()
