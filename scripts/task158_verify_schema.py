#!/usr/bin/env python3
"""TASK-158: verify the n8n-documented schema.

The n8n HeyReach node source code shows the list route wants:
  {profileUrl, firstName, lastName} per lead

Previous probes tried profileUrl ALONE and linkedInUrl WITH names,
but never profileUrl WITH names. This is the gap.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers.heyreach import (
    BASE, headers, list_leads,
)
from src.providers import request

LIST_ID = 940797


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
    print("TASK-158: verify n8n-documented schema")
    print("=" * 70)

    # Confirm still empty
    print("\n--- baseline ---")
    readback()

    # The exact shape the n8n node sends:
    # profileUrl + firstName + lastName
    print("\n--- Probe: profileUrl + firstName + lastName (n8n shape) ---")
    body = {
        "listId": LIST_ID,
        "leads": [{
            "profileUrl": "https://www.linkedin.com/in/brookebaron",
            "firstName": "Brooke",
            "lastName": "Baron",
        }]
    }
    print(f"  body: {json.dumps(body)}")
    status, data = raw_add(body)
    print(f"  response: {status} {json.dumps(data)}")
    items, total = readback()

    if total == 0:
        # Try with additional optional fields too
        print("\n--- Probe: full n8n shape with optional fields ---")
        body = {
            "listId": LIST_ID,
            "leads": [{
                "profileUrl": "https://www.linkedin.com/in/pavanmarisetti",
                "firstName": "Pavan",
                "lastName": "Marisetti",
                "companyName": "Test",
                "position": "Test",
            }]
        }
        print(f"  body: {json.dumps(body)}")
        status, data = raw_add(body)
        print(f"  response: {status} {json.dumps(data)}")
        readback()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
