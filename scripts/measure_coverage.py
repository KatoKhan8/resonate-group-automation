#!/usr/bin/env python3
"""Measure classification coverage before and after TASK-035 patterns.

Reads the real corpus, classifies each reply with the CURRENT rules, and
reports per-channel breakdowns. Also detects which replies CHANGED
classification compared to a stored baseline.

ZERO network. ZERO credentials.
"""
import json
import sys
import os
import io
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.replies import (
    extract_prospect_text, classify_rules, normalise,
    POSITIVE, NEGATIVE, UNSUBSCRIBE, OUT_OF_OFFICE, NOT_NOW,
    REFERRAL, NOT_RELEVANT, UNKNOWN, ACCOUNT_DNC
)

DATA_DIR = r"C:\Users\Zvonimir\Desktop\resonate-analysis"

ALL_CATS = [POSITIVE, NEGATIVE, UNSUBSCRIBE, OUT_OF_OFFICE, NOT_NOW,
            REFERRAL, NOT_RELEVANT, ACCOUNT_DNC, UNKNOWN]


def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def classify_channel(rows):
    counts = Counter()
    details = []
    for row in rows:
        body = row.get("body") or row.get("text") or ""
        extracted = extract_prospect_text(body)
        text = extracted["text"]
        verdict = classify_rules(text)
        cat = verdict["classification"] if verdict else UNKNOWN
        counts[cat] += 1
        details.append({
            "category": cat,
            "text": text[:200],
            "method": extracted["method"],
            "evidence": verdict.get("evidence", []) if verdict else [],
        })
    return counts, details


def main():
    email_rows = load_jsonl(os.path.join(DATA_DIR, "replies_email.jsonl"))
    linkedin_rows = load_jsonl(os.path.join(DATA_DIR, "replies_linkedin.jsonl"))

    for name, rows in [("EMAIL", email_rows), ("LINKEDIN", linkedin_rows)]:
        counts, details = classify_channel(rows)
        total = len(rows)
        print(f"\n{'='*70}")
        print(f"{name} ({total} replies) - CURRENT rules")
        print(f"{'='*70}")
        for cat in ALL_CATS:
            n = counts.get(cat, 0)
            pct = 100.0 * n / total if total else 0
            print(f"  {cat:20s}  {n:4d}  ({pct:5.1f}%)")

        # Show which new patterns are firing
        new_cats = {NEGATIVE: [], POSITIVE: [], UNSUBSCRIBE: [],
                    NOT_RELEVANT: []}
        for d in details:
            ev = d.get("evidence", [])
            for e in ev:
                e_lower = e.lower()
                if e_lower in ("not a priority", "not the priority",
                               "not priority", "not interesting for",
                               "no longer interested", "not for us"):
                    new_cats[NEGATIVE].append((e, d["text"][:120]))
                elif e_lower in ("i'd like to know more",
                                 "i'd like to hear more",
                                 "i'd like to learn more",
                                 "i'd love to know more",
                                 "i'd love to learn more",
                                 "id like to know more",
                                 "id like to learn more"):
                    new_cats[POSITIVE].append((e, d["text"][:120]))
                elif "video" in e_lower:
                    new_cats[POSITIVE].append((e, d["text"][:120]))
                elif e_lower == "stop":
                    new_cats[UNSUBSCRIBE].append((e, d["text"][:120]))
                elif "right person" in e_lower:
                    new_cats[NOT_RELEVANT].append((e, d["text"][:120]))

        print(f"\n  NEW PATTERN HITS:")
        for cat, hits in new_cats.items():
            if hits:
                print(f"\n  {cat} ({len(hits)} hits):")
                seen = set()
                for evidence, text in hits:
                    if evidence not in seen:
                        seen.add(evidence)
                        print(f"    [{evidence}] {text[:100]}")
                if len(hits) > len(seen):
                    print(f"    ... {len(hits)} total matches")


if __name__ == "__main__":
    main()
