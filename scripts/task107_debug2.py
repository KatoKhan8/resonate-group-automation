#!/usr/bin/env python3
"""Debug HeyReach sequence structure."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import heyreach

# Check campaign 599020 which was mentioned in the task
cid = 599020
print(f"Checking HeyReach campaign {cid}\n")

try:
    sequence = heyreach.campaign_sequence(cid)
    print(f"Sequence type: {type(sequence)}")
    print(f"Sequence keys: {list(sequence.keys()) if isinstance(sequence, dict) else 'not a dict'}")
    print(f"\nFull sequence:\n{json.dumps(sequence, indent=2)}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
