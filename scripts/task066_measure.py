#!/usr/bin/env python3
"""TASK-066: Measure classifier against hand-labels and full dataset."""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import replies

temp = os.environ.get("TEMP", os.environ.get("TMP", ""))
if not temp:
    temp = os.path.expanduser("~") + os.sep + "AppData" + os.sep + "Local" + os.sep + "Temp"
dataset_path = os.path.join(temp, "task058_dataset.json")

# Load hand labels
with open(os.path.join(temp, "task066_hand_labels.json"), encoding="utf-8") as f:
    raw_labels = json.load(f)
hand_labels = {int(k): v[0] for k, v in raw_labels.items()}

# Load sample
with open(os.path.join(temp, "task066_unknown_sample.json"), encoding="utf-8") as f:
    sample = json.load(f)

print("=" * 70)
print("PRECISION ON 100 HAND-LABELLED UNKNOWN REPLIES")
print("=" * 70)

# Run classifier on each and compare to hand labels
correct = 0
wrong = 0
still_unknown = 0
conflicts = []

for i, msg in enumerate(sample):
    idx = i + 1
    text = msg["body"]
    hand_label = hand_labels[idx]
    verdict = replies.classify(text, model=None)
    classifier_label = verdict["classification"]

    if classifier_label == hand_label:
        correct += 1
    elif classifier_label == "unknown" and hand_label == "unknown":
        correct += 1
        still_unknown += 1
    elif classifier_label == "unknown" and hand_label != "unknown":
        # Classifier says unknown, hand says something else - missed but safe
        still_unknown += 1
        wrong += 1
        conflicts.append((idx, hand_label, classifier_label, text[:80]))
    else:
        # Classifier says something different from hand label
        wrong += 1
        conflicts.append((idx, hand_label, classifier_label, text[:80]))

# More precise: check for UNSAFE errors (wrong positive, wrong negative)
unsafe_errors = []
for i, msg in enumerate(sample):
    idx = i + 1
    text = msg["body"]
    hand_label = hand_labels[idx]
    verdict = replies.classify(text, model=None)
    classifier_label = verdict["classification"]

    if hand_label == "unknown" and classifier_label in ("positive", "negative"):
        unsafe_errors.append((idx, hand_label, classifier_label, text[:80]))
    elif hand_label in ("positive", "negative") and classifier_label not in (hand_label, "unknown"):
        unsafe_errors.append((idx, hand_label, classifier_label, text[:80]))

print(f"\nTotal: {len(sample)}")
print(f"Correct (classifier matches hand label): {correct}")
print(f"Wrong: {wrong}")
print(f"Still unknown (both say unknown): {still_unknown}")
print(f"\nPrecision: {correct}/{len(sample)} = {correct/len(sample)*100:.1f}%")

if conflicts:
    print(f"\n=== MISCLASSIFIED ({len(conflicts)}) ===")
    for idx, hand, got, text in conflicts[:20]:
        safe_text = text.encode("ascii", errors="replace").decode()
        print(f"  #{idx}: hand={hand:15s} got={got:15s} | {safe_text}")

if unsafe_errors:
    print(f"\n=== UNSAFE ERRORS ({len(unsafe_errors)}) ===")
    for idx, hand, got, text in unsafe_errors:
        safe_text = text.encode("ascii", errors="replace").decode()
        print(f"  #{idx}: hand={hand:15s} got={got:15s} | {safe_text}")
else:
    print("\n*** NO UNSAFE ERRORS (no wrong positives or wrong negatives) ***")

# Now measure on full dataset
print("\n" + "=" * 70)
print("FULL DATASET: 5,291 REPLIES")
print("=" * 70)

with open(dataset_path, encoding="utf-8") as f:
    data = json.load(f)

replies_list = [r for r in data if r.get("replied")]
print(f"Total replies: {len(replies_list)}")

# We need to re-classify each reply using the text from cache
# But we don't have all texts in memory. Let's use the dataset's stored
# classification as the BEFORE, and re-derive the AFTER from cache.

# Build hash -> reply mapping
hash_to_reply = {}
for r in replies_list:
    h = r.get("reply_text_hash")
    if h:
        hash_to_reply[h] = r

# Scan cache for all CORRESPONDENT messages
import hashlib
cache_dir = os.path.join(temp, "task058_cache")
all_classified = {}  # hash -> new classification

for cache_file_name in sorted(os.listdir(cache_dir)):
    cache_path = os.path.join(cache_dir, cache_file_name)
    with open(cache_path, encoding="utf-8") as f:
        cache_data = json.load(f)
    for conv in cache_data["items"]:
        for msg in conv.get("messages", []):
            if msg.get("sender") == "CORRESPONDENT":
                body = str(msg.get("body") or "").strip()
                if body:
                    sha_hash = hashlib.sha256(body.encode()).hexdigest()[:12]
                    if sha_hash in hash_to_reply:
                        verdict = replies.classify(body, model=None)
                        all_classified[sha_hash] = verdict["classification"]

# Count new distribution
new_dist = Counter()
old_dist = Counter()
changed = Counter()  # (old, new) -> count

for r in replies_list:
    h = r.get("reply_text_hash")
    old_cat = r.get("reply_classification") or "unknown"
    old_dist[old_cat] += 1
    if h and h in all_classified:
        new_cat = all_classified[h]
        new_dist[new_cat] += 1
        if old_cat != new_cat:
            changed[(old_cat, new_cat)] += 1
    else:
        new_dist[old_cat] += 1  # no text available, keep old

print("\n--- BEFORE (old classification) ---")
for cat, count in sorted(old_dist.items(), key=lambda x: -x[1]):
    pct = count / len(replies_list) * 100
    print(f"  {cat:20s}  {count:5d}  {pct:5.1f}%")

print(f"\n--- AFTER (new classification) ---")
for cat, count in sorted(new_dist.items(), key=lambda x: -x[1]):
    pct = count / len(replies_list) * 100
    print(f"  {cat:20s}  {count:5d}  {pct:5.1f}%")

print(f"\n--- CHANGES ---")
for (old, new), count in sorted(changed.items(), key=lambda x: -x[1]):
    print(f"  {old:15s} -> {new:15s}  {count:5d}")

unknown_before = old_dist.get("unknown", 0)
unknown_after = new_dist.get("unknown", 0)
reduction = unknown_before - unknown_after
print(f"\nUnknown reduction: {unknown_before} -> {unknown_after} ({reduction} fewer, {reduction/unknown_before*100:.1f}% reduction)")
print(f"Unreadable before: {unknown_before/len(replies_list)*100:.1f}%")
print(f"Unreadable after:  {unknown_after/len(replies_list)*100:.1f}%")
