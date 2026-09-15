#!/usr/bin/env python3
"""TASK-109: Collect UNKNOWN reply texts for fresh hand-labelling.

Draws a random sample from the UNKNOWN pool in the cached conversation
data, blind to the classifier's output. The sample is written to a file
for hand-labelling.
"""
import json
import os
import sys
import hashlib
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

temp = os.environ.get("TEMP", os.environ.get("TMP", ""))
if not temp:
    temp = os.path.expanduser("~") + os.sep + "AppData" + os.sep + "Local" + os.sep + "Temp"

dataset_path = os.path.join(temp, "task058_dataset.json")
cache_dir = os.path.join(temp, "task058_cache")
output_path = os.path.join(temp, "task109_unknown_sample.json")

# Load dataset
print("Loading dataset...")
with open(dataset_path) as f:
    data = json.load(f)

# Get all UNKNOWN replies with their hashes
unknown_replies = [r for r in data
                   if r.get("replied") and r.get("reply_classification") == "unknown"]
print(f"Total UNKNOWN replies in dataset: {len(unknown_replies)}")

# Build hash -> reply mapping for unknowns
unknown_hashes = {}
for r in unknown_replies:
    h = r.get("reply_text_hash")
    if h:
        unknown_hashes[h] = r

# Collect all CORRESPONDENT messages from cache
print("Loading cache...")
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
                    sha_hash = hashlib.sha256(body.encode()).hexdigest()[:12]
                    correspondent_messages.append({
                        "body": body,
                        "hash": sha_hash,
                        "conv_id": conv["id"],
                    })

print(f"Total conversations: {total_convs}")
print(f"Total CORRESPONDENT messages: {len(correspondent_messages)}")

# Match to UNKNOWN replies
unknown_with_text = []
for msg in correspondent_messages:
    if msg["hash"] in unknown_hashes:
        unknown_with_text.append(msg)

print(f"UNKNOWN replies with text: {len(unknown_with_text)}")

# Draw a fresh random sample - seed different from the original (42)
# Using seed=109 for TASK-109
SAMPLE_SIZE = 200
random.seed(109)
sample = random.sample(unknown_with_text, min(SAMPLE_SIZE, len(unknown_with_text)))

print(f"\nSample size: {len(sample)}")

# Save the sample - WITHOUT classifier output, for blind labelling
sample_output = []
for i, msg in enumerate(sample, 1):
    text = msg["body"]
    sample_output.append({
        "index": i,
        "hash": msg["hash"],
        "conv_id": msg["conv_id"],
        "text": text,
    })

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(sample_output, f, indent=2, ensure_ascii=False)

print(f"Sample written to: {output_path}")

# Also write a readable version for hand-labelling
readable_path = os.path.join(temp, "task109_sample_readable.txt")
with open(readable_path, "w", encoding="utf-8") as f:
    f.write(f"TASK-109: Fresh UNKNOWN sample for hand-labelling\n")
    f.write(f"Sample size: {len(sample_output)}\n")
    f.write(f"Seed: 109\n")
    f.write(f"Pool size: {len(unknown_with_text)}\n\n")
    for item in sample_output:
        text = item["text"][:500].replace("\n", " ").strip()
        f.write(f"#{item['index']:3d} [{item['hash']}]\n")
        f.write(f"  {text}\n\n")

print(f"Readable version written to: {readable_path}")
