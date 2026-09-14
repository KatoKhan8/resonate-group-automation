#!/usr/bin/env python3
"""Check for false positives in TASK-035 pattern changes.

For each new pattern, show a sample of what it matched so we can verify
the classification is correct.

ZERO network. ZERO credentials.
"""
import json
import sys
import os
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.replies import (
    extract_prospect_text, classify_rules, normalise,
    POSITIVE, NEGATIVE, UNSUBSCRIBE, NOT_RELEVANT, UNKNOWN
)

DATA_DIR = r"C:\Users\Zvonimir\Desktop\resonate-analysis"

# The new patterns, isolated for testing
NEW_NEG = [
    r"\bnot (?:a |the )?priority\b",
    r"\bnot interesting for\b",
    r"\bno longer interested\b",
    r"\bnot for us\b",
]
NEW_POS = [
    r"\bi'?d (?:like|love) to (?:know|hear|learn|see) more\b",
    r"\bsend (?:me )?(?:a )?video\b",
]
NEW_UNSUB = [
    r"\bstop\b(?! (?:by|the|it|this|that|your?|my|our|a |an ))",
]
NEW_NR = [
    r"\bnot (?:be )?(?:the )?right person\b",
]


def safe(text):
    return "".join(c if ord(c) < 128 else "?" for c in text)


def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def check_pattern(pattern, rows, channel, category):
    """Find all replies where this pattern fires and show them."""
    hits = []
    for row in rows:
        body = row.get("body") or row.get("text") or ""
        extracted = extract_prospect_text(body)
        text = normalise(extracted["text"])
        if re.search(pattern, text, re.I):
            hits.append(text[:200])
    print(f"\n  Pattern: {pattern}")
    print(f"  Channel: {channel}, Category: {category}, Hits: {len(hits)}")
    for i, h in enumerate(hits[:10]):
        print(f"    [{i+1}] {safe(h[:150])}")
    if len(hits) > 10:
        print(f"    ... and {len(hits) - 10} more")
    return hits


def main():
    email_rows = load_jsonl(os.path.join(DATA_DIR, "replies_email.jsonl"))
    linkedin_rows = load_jsonl(os.path.join(DATA_DIR, "replies_linkedin.jsonl"))

    print("=" * 70)
    print("FALSE POSITIVE CHECK - sample each new pattern's matches")
    print("=" * 70)

    all_patterns = (
        [(p, NEGATIVE) for p in NEW_NEG] +
        [(p, POSITIVE) for p in NEW_POS] +
        [(p, UNSUBSCRIBE) for p in NEW_UNSUB] +
        [(p, NOT_RELEVANT) for p in NEW_NR]
    )

    total_hits = 0
    for pattern, category in all_patterns:
        for channel, rows in [("EMAIL", email_rows),
                              ("LINKEDIN", linkedin_rows)]:
            hits = check_pattern(pattern, rows, channel, category)
            total_hits += len(hits)

    print(f"\n{'='*70}")
    print(f"TOTAL new pattern hits across both channels: {total_hits}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
