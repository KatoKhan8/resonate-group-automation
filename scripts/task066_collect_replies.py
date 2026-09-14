#!/usr/bin/env python3
"""TASK-066: Collect all CORRESPONDENT messages and match to unknowns."""
import json
import os
import sys
import hashlib
import random
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

# Get all replies with their hashes
replies = [r for r in data if r.get("replied")]
print(f"Total replies: {len(replies)}")

# Build hash -> reply mapping
hash_to_reply = {}
for r in replies:
    h = r.get("reply_text_hash")
    if h:
        hash_to_reply[h] = r

# Collect all CORRESPONDENT messages from cache
print("\n=== COLLECTING ALL CORRESPONDENT MESSAGES ===")
correspondent_messages = []
total_convs = 0

for cache_file_name in sorted(os.listdir(cache_dir)):
    cache_path = os.path.join(cache_dir, cache_file_name)
    with open(cache_path) as f:
        cache_data = json.load(f)

    for conv in cache_data["items"]:
        total_convs += 1
        for msg in conv.get("messages", []):
            if msg.get("sender") == "CORRESPONDENT":
                body = str(msg.get("body") or "").strip()
                if body:
                    # Compute hash - SHA256, first 12 hex chars, of stripped body
                    sha_hash = hashlib.sha256(body.encode()).hexdigest()[:12]
                    correspondent_messages.append({
                        "body": body,
                        "hash": sha_hash,
                        "conv_id": conv["id"],
                    })

print(f"Total conversations: {total_convs}")
print(f"Total CORRESPONDENT messages: {len(correspondent_messages)}")

# Match to dataset
matched = 0
unmatched_hashes = set()
for msg in correspondent_messages:
    if msg["hash"] in hash_to_reply:
        matched += 1
        msg["reply_data"] = hash_to_reply[msg["hash"]]
    else:
        unmatched_hashes.add(msg["hash"])

print(f"Matched to dataset: {matched}")
print(f"Unmatched hashes: {len(unmatched_hashes)}")

# Now get the unknown replies with their text
unknown_with_text = [m for m in correspondent_messages
                     if m.get("reply_data", {}).get("reply_classification") == "unknown"]
print(f"\nUnknown replies with text: {len(unknown_with_text)}")

# Sample and display
if unknown_with_text:
    random.seed(42)
    sample = random.sample(unknown_with_text, min(100, len(unknown_with_text)))

    print("\n=== HAND-CLASSIFICATION SAMPLE: 100 UNKNOWN REPLIES ===")
    print("(Showing first 100 of unknowns for manual classification)\n")

    # Save to file instead of printing to avoid encoding issues
    sample_output = []
    for i, msg in enumerate(sample, 1):
        text = msg["body"][:300].replace("\n", " ")
        sample_output.append(f"{i:3d}. {text}")

    # Write to file
    with open(os.path.join(temp, "task066_sample_output.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(sample_output))
    print(f"Sample written to task066_sample_output.txt")

    # Save full sample for analysis
    with open(os.path.join(temp, "task066_unknown_sample.json"), "w") as f:
        json.dump(sample, f, indent=2)
    print(f"\nSaved full sample to task066_unknown_sample.json")

# Also check length distribution of unknown replies
lengths = [len(m["body"]) for m in unknown_with_text]
print(f"\n=== LENGTH DISTRIBUTION OF UNKNOWN REPLIES ===")
print(f"Count: {len(lengths)}")
if lengths:
    print(f"Min: {min(lengths)}, Max: {max(lengths)}, Avg: {sum(lengths)/len(lengths):.1f}")
    # Buckets
    buckets = Counter()
    for l in lengths:
        if l <= 10:
            buckets["very_short (<=10)"] += 1
        elif l <= 30:
            buckets["short (11-30)"] += 1
        elif l <= 100:
            buckets["medium (31-100)"] += 1
        elif l <= 300:
            buckets["long (101-300)"] += 1
        else:
            buckets["very_long (>300)"] += 1
    for bucket, count in sorted(buckets.items()):
        print(f"  {bucket}: {count}")
