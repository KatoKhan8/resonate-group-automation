#!/usr/bin/env python3
"""TASK-121: check campaign-level config and the two error campaigns."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers import heyreach


def main():
    # Check a campaign object (from the list) for any rotation/selection config
    print("=== Campaign-level fields (sample campaign 567758) ===")
    items, total = heyreach.campaigns(0, 50)
    for item in items:
        if str(item.get("id")) == "567758":
            # Print all top-level keys and non-huge values
            for k, v in sorted(item.items()):
                if isinstance(v, str) and len(v) > 200:
                    print(f"  {k}: {v[:200]}...")
                elif isinstance(v, (list, dict)):
                    s = json.dumps(v, ensure_ascii=False)
                    if len(s) > 200:
                        print(f"  {k}: ({type(v).__name__}, {len(v)} items) {s[:200]}...")
                    else:
                        print(f"  {k}: {s}")
                else:
                    print(f"  {k}: {v}")
            break

    # Check the two error campaigns
    print("\n=== Error campaigns (canary) ===")
    for cid in [594060, 594057]:
        print(f"\n--- Campaign {cid} ---")
        # Try to get the campaign from the list
        found = None
        offset = 0
        while True:
            page, total = heyreach.campaigns(offset, 50)
            for item in page:
                if str(item.get("id")) == str(cid):
                    found = item
                    break
            offset += len(page)
            if not page or offset >= total:
                break
            if found:
                break

        if found:
            print(f"  Name: {found.get('name')}")
            print(f"  Status: {found.get('status')}")
            # Check if it has a sequence embedded
            seq_keys = [k for k in found.keys() if 'sequence' in k.lower() or 'graph' in k.lower()]
            print(f"  Sequence-related keys: {seq_keys}")
            for k in seq_keys:
                v = found[k]
                if v is None:
                    print(f"    {k}: None")
                elif isinstance(v, dict):
                    print(f"    {k}: dict with keys {sorted(v.keys())}")
                elif isinstance(v, list):
                    print(f"    {k}: list with {len(v)} items")
                else:
                    print(f"    {k}: {v}")

        # Try the direct sequence fetch
        try:
            seq = heyreach.campaign_sequence(cid)
            print(f"  Sequence type: {type(seq).__name__}")
            if isinstance(seq, dict):
                print(f"  Sequence keys: {sorted(seq.keys())}")
            else:
                print(f"  Sequence value: {str(seq)[:500]}")
        except Exception as e:
            print(f"  Sequence error: {e}")


if __name__ == "__main__":
    main()
