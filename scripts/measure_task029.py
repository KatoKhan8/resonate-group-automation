#!/usr/bin/env python3
"""TASK-029: measure the before/after of stripping quoted threads.

Reads the pseudonymised corpus at C:\\Users\\Zvonimir\\Desktop\\resonate-analysis\\
and classifies each body twice:
  1. as-is (the contaminated input the classifier has been seeing)
  2. after extract_prospect_text (the fixed input)

Reports a per-category comparison table and samples the new unknowns
to quantify how much of the rise is real reply being lost.

Zero network. Zero credentials. No corpus content is copied into the
repository - this script reads from the analysis directory and prints
aggregate numbers and invented-label samples.
"""
import json
import os
import sys
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.replies import classify, extract_prospect_text, CATEGORIES

CORPUS_DIR = r"C:\Users\Zvonimir\Desktop\resonate-analysis"
EMAIL_CORPUS = os.path.join(CORPUS_DIR, "replies_email.jsonl")
LINKEDIN_CORPUS = os.path.join(CORPUS_DIR, "replies_linkedin.jsonl")


def load_corpus(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def classify_body(body):
    verdict = classify(body)
    return verdict["classification"]


def measure_channel(path, label):
    rows = load_corpus(path)
    total = len(rows)

    as_is_counts = {}
    stripped_counts = {}
    details = []

    for row in rows:
        body = row["body"]
        rules_say = row.get("rules_say", "")

        as_is = classify_body(body)

        extracted = extract_prospect_text(body)
        stripped = classify_body(extracted["text"]) if extracted["text"] else "unknown"

        as_is_counts[as_is] = as_is_counts.get(as_is, 0) + 1
        stripped_counts[stripped] = stripped_counts.get(stripped, 0) + 1

        details.append({
            "as_is": as_is,
            "stripped": stripped,
            "changed": as_is != stripped,
            "method": extracted["method"],
            "had_quote": extracted["had_quote"],
            "had_signature": extracted["had_signature"],
            "original_length": extracted["original_length"],
            "stripped_length": extracted["stripped_length"],
            "rules_say": rules_say,
        })

    print(f"\n{'=' * 60}")
    print(f"  {label} ({total} replies)")
    print(f"{'=' * 60}")

    all_cats = sorted(set(list(as_is_counts.keys()) + list(stripped_counts.keys())))
    print(f"\n  {'category':<25} {'as-is':>7} {'stripped':>9} {'delta':>7}")
    print(f"  {'-' * 50}")
    for cat in all_cats:
        a = as_is_counts.get(cat, 0)
        s = stripped_counts.get(cat, 0)
        d = s - a
        print(f"  {cat:<25} {a:>7} {s:>9} {d:>+7}")

    changed = sum(1 for d in details if d["changed"])
    print(f"\n  Changed classification: {changed}/{total} "
          f"({100 * changed / total:.1f}%)")

    methods = {}
    for d in details:
        m = d["method"]
        methods[m] = methods.get(m, 0) + 1
    print(f"\n  Extraction methods:")
    for m, c in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"    {m:<15} {c:>5} ({100 * c / total:.1f}%)")

    sig_count = sum(1 for d in details if d["had_signature"])
    quote_count = sum(1 for d in details if d["had_quote"])
    print(f"\n  Had quoted thread: {quote_count}/{total} "
          f"({100 * quote_count / total:.1f}%)")
    print(f"  Had signature stripped: {sig_count}/{total} "
          f"({100 * sig_count / total:.1f}%)")

    return details, total


def sample_unknowns(details, label, max_samples=30):
    """Read the new unknowns: bodies that were classified as something
    as-is but became unknown after stripping. Sample and categorise them
    to quantify how much is real reply being lost."""
    new_unknowns = [d for d in details
                    if d["stripped"] == "unknown" and d["as_is"] != "unknown"]

    print(f"\n  --- New unknowns analysis ({label}) ---")
    print(f"  Total new unknowns: {len(new_unknowns)}")

    if not new_unknowns:
        return

    by_previous = {}
    for d in new_unknowns:
        prev = d["as_is"]
        by_previous[prev] = by_previous.get(prev, 0) + 1
    print(f"  Previously classified as:")
    for cat, count in sorted(by_previous.items(), key=lambda x: -x[1]):
        print(f"    {cat:<25} {count:>5}")

    by_method = {}
    for d in new_unknowns:
        m = d["method"]
        by_method[m] = by_method.get(m, 0) + 1
    print(f"  By extraction method:")
    for m, count in sorted(by_method.items(), key=lambda x: -x[1]):
        print(f"    {m:<15} {count:>5}")

    by_length = {"empty": 0, "short_1_20": 0, "medium_21_100": 0, "long_100+": 0}
    for d in new_unknowns:
        sl = d["stripped_length"]
        if sl == 0:
            by_length["empty"] += 1
        elif sl <= 20:
            by_length["short_1_20"] += 1
        elif sl <= 100:
            by_length["medium_21_100"] += 1
        else:
            by_length["long_100+"] += 1
    print(f"  By stripped text length:")
    for bucket, count in by_length.items():
        print(f"    {bucket:<20} {count:>5}")

    empty_reply = sum(1 for d in new_unknowns if d["stripped_length"] == 0)
    print(f"\n  Real reply LOST (empty after strip): {empty_reply}/{len(new_unknowns)} "
          f"({100 * empty_reply / len(new_unknowns):.1f}%)")
    print(f"  Real reply PRESERVED (non-empty): "
          f"{len(new_unknowns) - empty_reply}/{len(new_unknowns)} "
          f"({100 * (len(new_unknowns) - empty_reply) / len(new_unknowns):.1f}%)")


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    email_details, email_total = measure_channel(EMAIL_CORPUS, "EMAIL")
    sample_unknowns(email_details, "EMAIL")

    li_details, li_total = measure_channel(LINKEDIN_CORPUS, "LINKEDIN")
    sample_unknowns(li_details, "LINKEDIN")

    print(f"\n{'=' * 60}")
    print(f"  COMBINED SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Email:    {email_total} replies")
    print(f"  LinkedIn: {li_total} replies")
    print(f"  Total:    {email_total + li_total} replies")


if __name__ == "__main__":
    main()
