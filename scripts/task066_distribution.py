#!/usr/bin/env python3
"""TASK-066: Current classification distribution + explore cache."""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

temp = os.environ.get("TEMP", os.environ.get("TMP", ""))
if not temp:
    temp = os.path.expanduser("~") + os.sep + "AppData" + os.sep + "Local" + os.sep + "Temp"
dataset_path = os.path.join(temp, "task058_dataset.json")
cache_dir = os.path.join(temp, "task058_cache")

# Load dataset
with open(dataset_path) as f:
    data = json.load(f)

# Filter to replies only
replies = [r for r in data if r.get("replied")]
print(f"Total touches: {len(data)}")
print(f"Total replies: {len(replies)}")

# Current classification distribution
classifications = Counter()
for r in replies:
    c = r.get("reply_classification") or "NONE"
    classifications[c] += 1

print("\n=== CURRENT CLASSIFICATION DISTRIBUTION ===")
for cat, count in classifications.most_common():
    pct = count / len(replies) * 100
    print(f"  {cat:25s}  {count:5d}  {pct:5.1f}%")

# Check reply_unreadable field
unreadable_counts = Counter(r.get("reply_unreadable") for r in replies)
print(f"\nreply_unreadable field: {dict(unreadable_counts)}")

# Check cache
print(f"\nCache dir exists: {os.path.exists(cache_dir)}")
if os.path.exists(cache_dir):
    cache_files = os.listdir(cache_dir)
    print(f"Cache files: {len(cache_files)}")
    if cache_files:
        print(f"First few: {cache_files[:5]}")
        # Read one cache file to understand structure
        sample_path = os.path.join(cache_dir, cache_files[0])
        with open(sample_path) as f:
            sample = json.load(f)
        if isinstance(sample, dict):
            print(f"Sample cache keys: {list(sample.keys())[:15]}")
            # Check if it has reply text
            for k in list(sample.keys())[:15]:
                v = sample[k]
                if isinstance(v, str) and len(v) > 10:
                    print(f"  {k}: {v[:100]}...")
                elif isinstance(v, (list, dict)):
                    print(f"  {k}: {type(v).__name__} len={len(v)}")
                else:
                    print(f"  {k}: {v}")
        elif isinstance(sample, list):
            print(f"Sample cache: list of {len(sample)}")
            if sample:
                print(f"First item keys: {list(sample[0].keys()) if isinstance(sample[0], dict) else type(sample[0])}")
