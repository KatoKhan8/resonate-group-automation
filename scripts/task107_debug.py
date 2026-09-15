#!/usr/bin/env python3
"""Debug script to understand the actual API response structures."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import bison, heyreach


def debug_heyreach():
    print("=== HeyReach Debug ===\n")
    
    # Try different ways to fetch campaigns
    print("1. heyreach.campaigns():")
    try:
        result = heyreach.campaigns()
        print(f"   Type: {type(result)}")
        print(f"   Result: {json.dumps(result, indent=2)[:500]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n2. heyreach.campaigns(offset=0, limit=50):")
    try:
        result = heyreach.campaigns(offset=0, limit=50)
        print(f"   Type: {type(result)}")
        if isinstance(result, list):
            print(f"   Length: {len(result)}")
            if result:
                print(f"   First item keys: {list(result[0].keys())}")
        else:
            print(f"   Result: {json.dumps(result, indent=2)[:500]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n3. heyreach.campaign_by_id(599020):")
    try:
        result = heyreach.campaign_by_id(599020)
        print(f"   Type: {type(result)}")
        if isinstance(result, list) and result:
            print(f"   First item keys: {list(result[0].keys())}")
            print(f"   First item: {json.dumps(result[0], indent=2)[:500]}")
    except Exception as e:
        print(f"   Error: {e}")


def debug_bison_sequence():
    print("\n=== EmailBison Sequence Debug ===\n")
    
    # Fetch first campaign
    status, data = bison.request("GET", f"{bison.base()}/campaigns", bison.headers())
    if not bison.ok(status):
        print(f"Could not fetch campaigns: {status}")
        return
    
    campaigns = data.get('data', [])
    if not campaigns:
        print("No campaigns found")
        return
    
    cid = campaigns[0].get('id')
    cname = campaigns[0].get('name', 'unnamed')
    print(f"Checking campaign {cid} ({cname})\n")
    
    # Try to fetch sequence
    print("1. GET /campaigns/{id}/sequence:")
    try:
        seq_status, seq_data = bison.request(
            "GET",
            f"{bison.base()}/campaigns/{cid}/sequence",
            bison.headers()
        )
        print(f"   Status: {seq_status}")
        if bison.ok(seq_status):
            sequence = seq_data.get('data', {})
            print(f"   Sequence keys: {list(sequence.keys())}")
            print(f"   Sequence: {json.dumps(sequence, indent=2)[:1000]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Try alternative route
    print("\n2. GET /campaigns/{id}/steps:")
    try:
        seq_status, seq_data = bison.request(
            "GET",
            f"{bison.base()}/campaigns/{cid}/steps",
            bison.headers()
        )
        print(f"   Status: {seq_status}")
        if bison.ok(seq_status):
            print(f"   Data: {json.dumps(seq_data, indent=2)[:1000]}")
    except Exception as e:
        print(f"   Error: {e}")


def main():
    debug_heyreach()
    debug_bison_sequence()


if __name__ == "__main__":
    main()
