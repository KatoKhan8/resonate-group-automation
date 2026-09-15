#!/usr/bin/env python3
"""TASK-109: Score the NEW INTERESTED pattern set against fresh hand-labels.

Loads the hand-labelled sample, runs the current classifier (with the NEW
patterns - bare adjectives removed), and computes precision and recall for
INTERESTED, MEETING_INTENT, and OBJECTION.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import replies

temp = os.environ.get("TEMP", os.environ.get("TMP", ""))
if not temp:
    temp = os.path.expanduser("~") + os.sep + "AppData" + os.sep + "Local" + os.sep + "Temp"

sample_path = os.path.join(temp, "task109_unknown_sample.json")
labels_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "scripts", "task109_labels.json")

# Load sample
with open(sample_path, encoding="utf-8") as f:
    sample = json.load(f)

# Load labels
with open(labels_path, encoding="utf-8") as f:
    labels_data = json.load(f)

labels = labels_data["labels"]

# Run classifier on each reply and compare
results = []
for item in sample:
    idx = str(item["index"])
    text = item["text"]
    hand_label = labels.get(idx, "none")

    # Run the full classify pipeline
    verdict = replies.classify(text)
    classifier_label = verdict["classification"]

    # The taxonomy categories map to UNKNOWN in production, but classify()
    # returns the taxonomy label directly when it fires
    if classifier_label in (replies.INTERESTED, replies.MEETING_INTENT, replies.OBJECTION):
        pred = classifier_label
    else:
        pred = "none"

    results.append({
        "index": idx,
        "text": text[:200],
        "hand_label": hand_label,
        "pred": pred,
        "correct": hand_label == pred,
        "evidence": verdict.get("evidence", []),
    })

# Compute precision and recall for each category
def compute_metrics(results, category):
    tp = sum(1 for r in results if r["hand_label"] == category and r["pred"] == category)
    fp = sum(1 for r in results if r["hand_label"] != category and r["pred"] == category)
    fn = sum(1 for r in results if r["hand_label"] == category and r["pred"] != category)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    return {
        "category": category,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "total_actual": tp + fn,
        "total_predicted": tp + fp,
    }

print("=" * 70)
print("TASK-109: INTERESTED Re-measure — NEW pattern set")
print("=" * 70)
print(f"\nSample size: {len(results)}")
print(f"Pool size: 3,893 UNKNOWN replies with text")
print(f"Seed: 109")
print()

# Per-category metrics
for cat in ["interested", "meeting_intent", "objection"]:
    m = compute_metrics(results, cat)
    print(f"\n{cat.upper()}:")
    print(f"  Precision: {m['precision']:.2f}  (TP={m['tp']}, FP={m['fp']}, predicted={m['total_predicted']})")
    print(f"  Recall:    {m['recall']:.2f}  (TP={m['tp']}, FN={m['fn']}, actual={m['total_actual']})")

# Detail: show all predictions for each category
print("\n" + "=" * 70)
print("DETAIL: INTERESTED predictions vs hand-labels")
print("=" * 70)

interested_preds = [r for r in results if r["pred"] == "interested"]
print(f"\nClassifier predicted INTERESTED: {len(interested_preds)} replies")
for r in interested_preds:
    status = "CORRECT" if r["correct"] else "WRONG"
    print(f"  #{r['index']:3d} [{status}] hand={r['hand_label']}")
    print(f"         text: {r['text'][:150]}")
    print(f"         evidence: {r['evidence']}")
    print()

print("\n" + "=" * 70)
print("DETAIL: INTERESTED missed (hand-labelled interested, classifier said none)")
print("=" * 70)

interested_missed = [r for r in results if r["hand_label"] == "interested" and r["pred"] != "interested"]
print(f"\nMissed: {len(interested_missed)} replies")
for r in interested_missed:
    print(f"  #{r['index']:3d} pred={r['pred']}")
    print(f"         text: {r['text'][:150]}")
    print()

print("\n" + "=" * 70)
print("DETAIL: MEETING_INTENT predictions")
print("=" * 70)

mi_preds = [r for r in results if r["pred"] == "meeting_intent"]
print(f"\nClassifier predicted MEETING_INTENT: {len(mi_preds)} replies")
for r in mi_preds:
    status = "CORRECT" if r["correct"] else "WRONG"
    print(f"  #{r['index']:3d} [{status}] hand={r['hand_label']}")
    print(f"         text: {r['text'][:150]}")
    print()

print("\n" + "=" * 70)
print("DETAIL: OBJECTION predictions")
print("=" * 70)

obj_preds = [r for r in results if r["pred"] == "objection"]
print(f"\nClassifier predicted OBJECTION: {len(obj_preds)} replies")
for r in obj_preds:
    status = "CORRECT" if r["correct"] else "WRONG"
    print(f"  #{r['index']:3d} [{status}] hand={r['hand_label']}")
    print(f"         text: {r['text'][:150]}")
    print()

# Summary comparison with old measurement
print("\n" + "=" * 70)
print("COMPARISON: OLD vs NEW pattern set")
print("=" * 70)
print("""
OLD (docs/TAXONOMY-PRECISION-2026-09-14.md, n=263):
  INTERESTED     precision 0.44   recall 0.62
  MEETING_INTENT precision 1.00   recall 1.00
  OBJECTION      precision 1.00   recall 0.67

NEW (this measurement, n=200):
""")
for cat in ["interested", "meeting_intent", "objection"]:
    m = compute_metrics(results, cat)
    print(f"  {cat.upper():15s} precision {m['precision']:.2f}   recall {m['recall']:.2f}")

# Save full results
results_path = os.path.join(temp, "task109_results.json")
with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nFull results saved to: {results_path}")
