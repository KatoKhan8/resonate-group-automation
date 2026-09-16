#!/usr/bin/env python3
"""TASK-158: final probes - structural variations.

8 probes used, 4 remaining. Trying structural differences:
- linkedInAccountId + lead wrapper (like campaign route)
- integer linkedin_id vs string
- different array item structures
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers.heyreach import (
    BASE, headers, list_leads, _read,
)
from src.providers import request

LIST_ID = 940797
PROBE_URL = "https://www.linkedin.com/in/brookebaron"
PROBE_ID = "389277834"


def raw_add(body):
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
    print("TASK-158: final structural probes (4 remaining)")
    print("=" * 70)

    # First confirm still empty
    print("\n--- baseline ---")
    readback()

    # Probe 9: accountLeadPairs-style with linkedInAccountId + lead wrapper
    # The campaign route uses this shape. Maybe the list route wants it too,
    # despite using `leads` as the array name.
    print(f"\n--- Probe 9: leads with linkedInAccountId + lead wrapper ---")
    body = {"listId": LIST_ID, "leads": [{
        "linkedInAccountId": 0,
        "lead": {"profileUrl": PROBE_URL}
    }]}
    print(f"  body: {json.dumps(body)}")
    status, data = raw_add(body)
    print(f"  {status} {json.dumps(data)}")
    readback()

    # Probe 10: linkedInUrl as integer linkedin_id (not string)
    print(f"\n--- Probe 10: linkedInUrl as the numeric id (integer) ---")
    body = {"listId": LIST_ID, "leads": [{
        "linkedInUrl": int(PROBE_ID),
    }]}
    print(f"  body: {json.dumps(body)}")
    status, data = raw_add(body)
    print(f"  {status} {json.dumps(data)}")
    readback()

    # Probe 11: linkedInUserProfile object with profileUrl inside
    print(f"\n--- Probe 11: linkedInUserProfile nested object ---")
    body = {"listId": LIST_ID, "leads": [{
        "linkedInUserProfile": {"profileUrl": PROBE_URL}
    }]}
    print(f"  body: {json.dumps(body)}")
    status, data = raw_add(body)
    print(f"  {status} {json.dumps(data)}")
    readback()

    # Probe 12: linkedInUserProfile with linkedin_id inside
    print(f"\n--- Probe 12: linkedInUserProfile with linkedin_id ---")
    body = {"listId": LIST_ID, "leads": [{
        "linkedInUserProfile": {"linkedin_id": PROBE_ID}
    }]}
    print(f"  body: {json.dumps(body)}")
    status, data = raw_add(body)
    print(f"  {status} {json.dumps(data)}")
    readback()

    print(f"\n{'='*70}")
    print("ALL 12 PROBES USED")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
