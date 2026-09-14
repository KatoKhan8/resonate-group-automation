#!/usr/bin/env python3
"""Analyze unmatched reply bodies from the real corpus.

Reads replies_email.jsonl and replies_linkedin.jsonl, runs the classifier
rules on the extracted prospect text, and outputs the unmatched bodies
grouped by rough theme for pattern development.

ZERO network. ZERO credentials. Real data read, never copied into the repo.
"""
import json
import sys
import os
import re
import io
from collections import Counter, defaultdict

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.replies import (
    extract_prospect_text, classify_rules, normalise,
    POSITIVE, NEGATIVE, UNSUBSCRIBE, OUT_OF_OFFICE, NOT_NOW,
    REFERRAL, NOT_RELEVANT, UNKNOWN, ACCOUNT_DNC
)

DATA_DIR = r"C:\Users\Zvonimir\Desktop\resonate-analysis"


def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def analyze_channel(rows, channel):
    counts = Counter()
    unmatched = []
    changed = []

    for row in rows:
        body = row.get("body") or row.get("text") or ""
        extracted = extract_prospect_text(body)
        text = extracted["text"]
        verdict = classify_rules(text)

        if verdict is None:
            cat = UNKNOWN
        else:
            cat = verdict["classification"]

        counts[cat] += 1
        if cat == UNKNOWN:
            unmatched.append({
                "text": text,
                "original_length": extracted["original_length"],
                "stripped_length": extracted["stripped_length"],
                "method": extracted["method"],
                "excerpt": text[:300] if text else "(empty)",
            })

    total = len(rows)
    print(f"\n{'='*70}")
    print(f"CHANNEL: {channel} ({total} replies)")
    print(f"{'='*70}")
    for cat in [POSITIVE, NEGATIVE, UNSUBSCRIBE, OUT_OF_OFFICE, NOT_NOW,
                REFERRAL, NOT_RELEVANT, ACCOUNT_DNC, UNKNOWN]:
        n = counts.get(cat, 0)
        pct = 100.0 * n / total if total else 0
        print(f"  {cat:20s}  {n:4d}  ({pct:5.1f}%)")

    print(f"\n  UNMATCHED: {len(unmatched)} of {total} "
          f"({100.0*len(unmatched)/total:.1f}%)")
    return unmatched


def group_unmatched(unmatched):
    """Rough grouping by surface features of the text."""
    groups = defaultdict(list)

    for item in unmatched:
        text = item["text"].lower()
        excerpt = item["excerpt"]

        if not text.strip():
            groups["empty_or_greeting_only"].append(item)
            continue

        # Very short replies (< 20 chars)
        if len(text) < 20:
            groups["very_short_under_20"].append(item)
            continue

        # Short replies (20-50 chars)
        if len(text) < 50:
            groups["short_20_50"].append(item)
            continue

        # Contains question marks - asking something
        if "?" in text:
            groups["contains_question"].append(item)
            continue

        # Thanks/acknowledgment without commitment
        if re.search(r"\b(thank|thanks|thx|appreciate)\b", text):
            groups["thanks_acknowledgment"].append(item)
            continue

        # Asking for more info / curious but not committing
        if re.search(r"\b(what|how|where|when|which|who|why)\b", text):
            groups["question_word"].append(item)
            continue

        # Scheduling / time references
        if re.search(r"\b(monday|tuesday|wednesday|thursday|friday|"
                     r"january|february|march|april|may|june|july|"
                     r"august|september|october|november|december|"
                     r"week|month|quarter|calendar|schedule|time|busy)\b", text):
            groups["time_reference"].append(item)
            continue

        # Company / team references
        if re.search(r"\b(company|team|organisation|organization|we|our)\b", text):
            groups["company_reference"].append(item)
            continue

        # Medium length (50-150 chars)
        if len(text) < 150:
            groups["medium_50_150"].append(item)
            continue

        # Longer replies
        groups["longer_150_plus"].append(item)

    return groups


def safe(text):
    """Strip non-ASCII for safe terminal output."""
    return "".join(c if ord(c) < 128 else "?" for c in text)


def print_groups(groups, channel, top_n=10):
    print(f"\n{'='*70}")
    print(f"UNMATCHED GROUPS: {channel}")
    print(f"{'='*70}")

    sorted_groups = sorted(groups.items(), key=lambda x: -len(x[1]))
    for name, items in sorted_groups:
        print(f"\n--- {name}: {len(items)} replies ---")
        for i, item in enumerate(items[:top_n]):
            excerpt = safe(item["excerpt"][:200].replace("\n", " "))
            print(f"  [{i+1}] (len={item['stripped_length']}, "
                  f"method={item['method']}) {excerpt}")
        if len(items) > top_n:
            print(f"  ... and {len(items) - top_n} more")


def deep_analysis(unmatched, channel):
    """Look deeper at the unmatched to find classifiable patterns."""
    print(f"\n{'='*70}")
    print(f"DEEP PATTERN ANALYSIS: {channel} ({len(unmatched)} unmatched)")
    print(f"{'='*70}")

    # Look for specific semantic clusters
    clusters = {
        "asking_for_info": [],        # "what does this do?", "tell me about"
        "sceptical_but_engaged": [],   # "how is this different from"
        "internal_forward": [],        # "let me check with", "i'll get back"
        "already_has_solution": [],    # "we use X already"
        "too_expensive": [],           # "too expensive", "no budget"
        "wrong_timing_soft": [],       # "busy right now", "swamped"
        "acknowledged_no_action": [],  # "got it", "noted", "will keep in mind"
        "company_info": [],            # "what company is this", "who are you"
        "automated_reply": [],         # mailer-daemon, delivery failure
        "non_english": [],             # non-English replies
        "link_attachment": [],         # "see attached", "here's the link"
        "call_me": [],                 # "give me a call", "phone me"
        "positive_soft": [],           # "sounds interesting but", " intriguing"
        "negative_soft": [],           # "not sure about", "doubt"
        "delegation": [],              # "my colleague handles", "ask X"
    }

    for item in unmatched:
        text = item["text"].lower()
        if not text.strip():
            continue

        # Asking for information
        if re.search(r"\b(?:what|how|where|when|can you|could you)"
                     r".*\b(?:work|do|help|offer|provide|cost|price)\b", text):
            clusters["asking_for_info"].append(item)
            continue

        # Already has a solution
        if re.search(r"\b(?:we (?:already|currently)|we'?re (?:using|on)|"
                     r"already (?:have|use|signed))\b", text):
            clusters["already_has_solution"].append(item)
            continue

        # Budget/price objection
        if re.search(r"\b(?:too expensive|no budget|cost(?:ly|s)|"
                     r"not in (?:the |our )?budget|pricing is|"
                     r"can'?t afford|price is)\b", text):
            clusters["too_expensive"].append(item)
            continue

        # Soft timing
        if re.search(r"\b(?:busy (?:right )?now|swamped|under pressure|"
                     r"this week is|loaded|flat out|snowed|"
                     r"deadline|crunch time)\b", text):
            clusters["wrong_timing_soft"].append(item)
            continue

        # Acknowledged but no action
        if re.search(r"\b(?:got it|noted|will keep|thanks for (?:sharing|sending|"
                     r"reaching|the info)|appreciate (?:you|the|this|that)|"
                     r"good to know|thanks for (?:the )?(?:offer|info|details))\b", text):
            clusters["acknowledged_no_action"].append(item)
            continue

        # Automated / delivery failure
        if re.search(r"\b(?:mailer[- ]?daemon|delivery (?:failed|failure)|"
                     r"undeliverable|bounce|no such user|"
                     r"address not found|does not exist)\b", text):
            clusters["automated_reply"].append(item)
            continue

        # Non-English detection (rough: high proportion of non-ASCII)
        non_ascii = sum(1 for c in text if ord(c) > 127)
        if len(text) > 10 and non_ascii / len(text) > 0.15:
            clusters["non_english"].append(item)
            continue

        # Call me / phone
        if re.search(r"\b(?:call me|give me a call|phone me|ring me|"
                     r"my number|reach me at)\b", text):
            clusters["call_me"].append(item)
            continue

        # Internal check / delegation
        if re.search(r"\b(?:let me (?:check|ask|see|find out)|"
                     r"i'?ll (?:get back|check|ask|find out)|"
                     r"need to (?:check|ask|discuss)|"
                     r"my (?:colleague|team|boss|manager)|"
                     r"will (?:check|ask|discuss|see))\b", text):
            clusters["internal_forward"].append(item)
            continue

        # Sceptical but engaged
        if re.search(r"\b(?:how is (?:this|that) different|"
                     r"what makes|how does (?:this|that) compare|"
                     r"sounds (?:interesting|intriguing) but|"
                     r"not sure (?:about|if)|I doubt)\b", text):
            clusters["sceptical_but_engaged"].append(item)
            continue

        # Link/attachment
        if re.search(r"\b(?:see attached|attached is|here'?s (?:the |a )?link|"
                     r"sending (?:you )?(?:the |a )?link|check (?:out )?(?:the )?link)\b", text):
            clusters["link_attachment"].append(item)
            continue

        # Soft positive
        if re.search(r"\b(?:sounds (?:interesting|good|great|intriguing)|"
                     r"(?:that'?s |that )?(?:interesting|intriguing|fascinating)|"
                     r"i'?d (?:like|love) to (?:hear|know|learn)|"
                     r"tell me more|can you (?:send|share|elaborate))\b", text):
            clusters["positive_soft"].append(item)
            continue

        # Soft negative
        if re.search(r"\b(?:not sure (?:about|if)|don'?t think (?:this|it|we)|"
                     r"doesn'?t (?:seem|look) (?:like|right)|"
                     r"not (?:quite|really) (?:what|for)|"
                     r"(?:we|I) (?:probably|might) (?:pass|decline))\b", text):
            clusters["negative_soft"].append(item)
            continue

        # Delegation without naming (different from referral)
        if re.search(r"\b(?:the (?:right|best) (?:person|contact)|"
                     r"(?:please|try) (?:contacting|reaching|asking)|"
                     r"you (?:may|might) want to (?:contact|reach|speak))\b", text):
            clusters["delegation"].append(item)
            continue

    for name, items in sorted(clusters.items(), key=lambda x: -len(x[1])):
        if items:
            print(f"\n--- {name}: {len(items)} replies ---")
            for i, item in enumerate(items[:8]):
                excerpt = safe(item["excerpt"][:200].replace("\n", " "))
                print(f"  [{i+1}] (len={item['stripped_length']}) {excerpt}")
            if len(items) > 8:
                print(f"  ... and {len(items) - 8} more")

    return clusters


def main():
    email_rows = load_jsonl(os.path.join(DATA_DIR, "replies_email.jsonl"))
    linkedin_rows = load_jsonl(os.path.join(DATA_DIR, "replies_linkedin.jsonl"))

    # Analyze each channel
    email_unmatched = analyze_channel(email_rows, "EMAIL")
    linkedin_unmatched = analyze_channel(linkedin_rows, "LINKEDIN")

    # Group and print
    email_groups = group_unmatched(email_unmatched)
    linkedin_groups = group_unmatched(linkedin_unmatched)

    print_groups(email_groups, "EMAIL", top_n=15)
    print_groups(linkedin_groups, "LINKEDIN", top_n=15)

    # Deep analysis
    email_clusters = deep_analysis(email_unmatched, "EMAIL")
    linkedin_clusters = deep_analysis(linkedin_unmatched, "LINKEDIN")

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Email:    {len(email_rows)} total, "
          f"{len(email_unmatched)} unmatched "
          f"({100.0*len(email_unmatched)/len(email_rows):.1f}%)")
    print(f"LinkedIn: {len(linkedin_rows)} total, "
          f"{len(linkedin_unmatched)} unmatched "
          f"({100.0*len(linkedin_unmatched)/len(linkedin_rows):.1f}%)")


if __name__ == "__main__":
    main()
