"""TASK-143: Where does junk evidence surface, and does filtering it matter?

Reads work/queue.snapshot.jsonl (read-only, no writes).
Classifies records by what for_prompt() would show the model, then compares
the two groups on rejection rates, draft quality, and vocabulary.

Snapshot: 2026-09-14T21:52:15Z from master 0ac5e60, 300 records.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SNAPSHOT = Path("work/queue.snapshot.jsonl")

# ---------------------------------------------------------------------------
# PRE-STATED THRESHOLDS (before any computation)
# ---------------------------------------------------------------------------
# With 32 JUNK-FED and ~100 FACT-FED (records with usable evidence in first 3),
# the comparison is underpowered. To be worth acting on, the difference must be:
#   - >= 15 percentage points on any rate comparison (rejection, generic, etc.)
#   - OR a qualitative pattern visible in >= 50% of the smaller group
# A difference inside +/- 10pp is noise at this sample size.
# Between 10-15pp is suggestive but not conclusive.
MIN_ACTIONABLE_DIFF_PP = 15

# ---------------------------------------------------------------------------
# Generic phrases that signal "the model had nothing to work with"
# ---------------------------------------------------------------------------
GENERIC_PHRASES = [
    "describes itself as",
    "calls itself",
    "is a leading",
    "is known for",
    "offers a range of",
    "custom-made solutions",
    "ever-changing market",
    "innovative approach",
    "keep pace with",
    "adapts quickly to market",
    "one place where",
    "transform decision-making",
    "maximize returns",
    "streamlining your",
    "simplifying your",
    "improving how",
    "visibility into",
    "clear visibility",
    "without clear",
]

# Phrases that look like navigation/menu text leaked into copy
NAV_LEAK_PATTERNS = [
    r"(?:skip to|back to top|privacy policy|terms & conditions|terms and conditions)",
    r"(?:linkedin|instagram|facebook)\b(?!.*linkedin\.com/company)",
    r"menu\b",
    r"our (?:services|office|team|clients)\b",
    r"\barchive\b",
    r"\bclients\b",
]


def load_records():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def classify_record(rec):
    """What would for_prompt(rec) return? First 3 rows in stored order."""
    research = rec.get("research") or []
    if not research:
        return "no_evidence", []

    first3 = research[:3]
    qualities = [row.get("quality") for row in first3]
    all_unusable = all(q == "unusable" for q in qualities)
    any_usable = any(q in ("medium", "strong") for q in qualities)

    if all_unusable:
        return "junk_fed", first3
    elif any_usable:
        return "fact_fed", first3
    else:
        # weak or missing only - a middle category
        return "weak_fed", first3


def extract_drafts(rec):
    """All generated draft bodies from the cadence."""
    drafts = []
    cadence = rec.get("cadence") or {}
    for contact_key, steps in cadence.items():
        for step_key, step_data in steps.items():
            if not step_data.get("generated"):
                continue
            body = step_data.get("body") or step_data.get("note") or ""
            subject = step_data.get("subject") or ""
            channel = step_data.get("channel", "")
            if body:
                drafts.append({
                    "contact": contact_key,
                    "step": step_key,
                    "channel": channel,
                    "subject": subject,
                    "body": body,
                    "full_text": f"{subject} {body}".strip(),
                })
    return drafts


def categorize_rejections(rec):
    """Categorize all rejection reasons from the log."""
    cats = Counter()
    total = 0
    for entry in rec.get("log", []):
        if "rejected" not in entry:
            continue
        for reason in entry["rejected"]:
            if isinstance(reason, dict):
                reason = json.dumps(reason)
            elif isinstance(reason, list):
                reason = " ".join(str(x) for x in reason)
            total += 1
            rl = reason.lower()
            if "repeats" in rl or "repetition" in rl:
                cats["repetition"] += 1
            elif "unsupported claim" in rl:
                cats["unsupported_claim"] += 1
            elif "banned" in rl or "filler_phrase" in rl:
                cats["banned_or_filler"] += 1
            elif "under 40" in rl or "body_too_short" in rl:
                cats["too_short"] += 1
            elif "em dash" in rl or "curly" in rl or "ascii" in rl or "hard_wrapped" in rl:
                cats["formatting"] += 1
            elif "subject" in rl and "60 characters" in rl:
                cats["subject_too_long"] += 1
            elif "no_angle" in rl or "no angle" in rl:
                cats["no_angle"] += 1
            elif "evidence not traceable" in rl:
                cats["evidence_trace"] += 1
            else:
                cats["other"] += 1
    return cats, total


def count_generic_phrases(text):
    """How many generic filler phrases appear in this text?"""
    text_lower = text.lower()
    return sum(1 for phrase in GENERIC_PHRASES if phrase in text_lower)


def has_nav_leakage(text):
    """Does the text contain navigation/menu fragments?"""
    text_lower = text.lower()
    return any(re.search(pat, text_lower) for pat in NAV_LEAK_PATTERNS)


def word_set(text):
    """Lowercase word set, stripping punctuation."""
    return set(re.findall(r"[a-z']+", text.lower()))


def vocab_overlap(drafts_a, drafts_b):
    """Jaccard similarity of vocabulary between two groups of drafts."""
    words_a = set()
    for d in drafts_a:
        words_a.update(word_set(d["full_text"]))
    words_b = set()
    for d in drafts_b:
        words_b.update(word_set(d["full_text"]))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


def evidence_facts(rec):
    """The usable facts from research rows (medium+strong quality)."""
    facts = []
    for row in rec.get("research") or []:
        if row.get("quality") in ("medium", "strong"):
            fact_text = (row.get("fact") or "")[:200]
            if fact_text.strip():
                facts.append(fact_text)
    return facts


def draft_references_evidence(draft_text, facts):
    """Does the draft contain specific phrases from the evidence facts?"""
    if not facts:
        return False
    draft_lower = draft_text.lower()
    # Look for distinctive phrases from the facts (3+ consecutive words)
    for fact in facts:
        # Extract meaningful phrases (skip very short words)
        words = re.findall(r"[a-z']{3,}", fact.lower())
        # Check for 3-word sequences from the fact appearing in the draft
        for i in range(len(words) - 2):
            phrase = " ".join(words[i:i+3])
            if phrase in draft_lower:
                return True
    return False


def main():
    records = load_records()
    with_research = [r for r in records if r.get("research")]

    # Classify
    groups = {"junk_fed": [], "fact_fed": [], "weak_fed": [], "no_evidence": []}
    for r in with_research:
        cls, _ = classify_record(r)
        groups[cls].append(r)

    print("=" * 72)
    print("TASK-143: JUNK EVIDENCE IMPACT ANALYSIS")
    print(f"Snapshot: 2026-09-14T21:52:15Z from master 0ac5e60, 300 records")
    print("=" * 72)

    print(f"\nRecords with research: {len(with_research)} of {len(records)}")
    print(f"  JUNK-FED  (first 3 all unusable): {len(groups['junk_fed'])}")
    print(f"  FACT-FED  (at least one medium/strong in first 3): {len(groups['fact_fed'])}")
    print(f"  WEAK-FED  (only weak/missing in first 3): {len(groups['weak_fed'])}")

    # Merge weak_fed into analysis as a separate category
    # For the main comparison: JUNK-FED vs FACT-FED
    junk = groups["junk_fed"]
    fact = groups["fact_fed"]

    # -----------------------------------------------------------------------
    # 1. REJECTION RATES BY CLASS
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("1. REJECTION RATES BY CLASS")
    print("=" * 72)

    for label, group in [("JUNK-FED", junk), ("FACT-FED", fact)]:
        total_rejections = 0
        total_records_with_rejections = 0
        all_cats = Counter()
        for r in group:
            cats, n = categorize_rejections(r)
            if n > 0:
                total_records_with_rejections += 1
            total_rejections += n
            all_cats.update(cats)

        print(f"\n  {label} ({len(group)} records):")
        print(f"    Records with any rejection: {total_records_with_rejections} "
              f"({100*total_records_with_rejections/max(len(group),1):.1f}%)")
        print(f"    Total rejection reasons: {total_rejections}")
        if total_rejections > 0:
            print(f"    Avg rejections per record (all): {total_rejections/max(len(group),1):.1f}")
            print(f"    Breakdown:")
            for cat, count in all_cats.most_common():
                print(f"      {cat}: {count} ({100*count/total_rejections:.1f}%)")

    # -----------------------------------------------------------------------
    # 2. DRAFT METRICS
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("2. DRAFT QUALITY METRICS")
    print("=" * 72)

    for label, group in [("JUNK-FED", junk), ("FACT-FED", fact)]:
        all_drafts = []
        generic_counts = []
        nav_leak_count = 0
        references_evidence = 0
        body_lengths = []
        records_with_drafts = 0

        for r in group:
            drafts = extract_drafts(r)
            if drafts:
                records_with_drafts += 1
            all_drafts.extend(drafts)
            for d in drafts:
                gc = count_generic_phrases(d["full_text"])
                generic_counts.append(gc)
                if has_nav_leakage(d["full_text"]):
                    nav_leak_count += 1
                body_lengths.append(len(d["body"].split()))

                # Check if draft references evidence facts
                facts = evidence_facts(r)
                if draft_references_evidence(d["full_text"], facts):
                    references_evidence += 1

        n_drafts = len(all_drafts)
        print(f"\n  {label} ({len(group)} records, {n_drafts} drafts):")
        print(f"    Records with drafts: {records_with_drafts}")
        if n_drafts > 0:
            avg_generic = sum(generic_counts) / n_drafts
            drafts_with_generic = sum(1 for g in generic_counts if g > 0)
            avg_length = sum(body_lengths) / n_drafts
            print(f"    Avg generic phrases per draft: {avg_generic:.2f}")
            print(f"    Drafts with >= 1 generic phrase: {drafts_with_generic} "
                  f"({100*drafts_with_generic/n_drafts:.1f}%)")
            print(f"    Drafts with navigation leakage: {nav_leak_count} "
                  f"({100*nav_leak_count/n_drafts:.1f}%)")
            print(f"    Drafts referencing evidence facts: {references_evidence} "
                  f"({100*references_evidence/n_drafts:.1f}%)")
            print(f"    Avg draft length (words): {avg_length:.1f}")

    # -----------------------------------------------------------------------
    # 3. VOCABULARY OVERLAP
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("3. VOCABULARY ANALYSIS")
    print("=" * 72)

    junk_drafts = []
    fact_drafts = []
    for r in junk:
        junk_drafts.extend(extract_drafts(r))
    for r in fact:
        fact_drafts.extend(extract_drafts(r))

    jaccard = vocab_overlap(junk_drafts, fact_drafts)
    print(f"\n  Jaccard similarity (junk vs fact vocab): {jaccard:.3f}")

    # Internal overlap: how similar are drafts within each group?
    # Measure avg pairwise Jaccard for a sample
    def avg_internal_overlap(drafts, sample_size=50):
        import random
        random.seed(42)
        if len(drafts) < 2:
            return 0.0
        sample = random.sample(drafts, min(sample_size, len(drafts)))
        total = 0.0
        pairs = 0
        for i in range(len(sample)):
            for j in range(i+1, len(sample)):
                wi = word_set(sample[i]["full_text"])
                wj = word_set(sample[j]["full_text"])
                if not wi or not wj:
                    continue
                union = wi | wj
                if union:
                    total += len(wi & wj) / len(union)
                pairs += 1
        return total / pairs if pairs else 0.0

    junk_internal = avg_internal_overlap(junk_drafts)
    fact_internal = avg_internal_overlap(fact_drafts)
    print(f"  Avg internal Jaccard (JUNK-FED, sampled): {junk_internal:.3f}")
    print(f"  Avg internal Jaccard (FACT-FED, sampled): {fact_internal:.3f}")

    # -----------------------------------------------------------------------
    # 4. EXAMPLE-BASED: WHAT DOES JUNK-FED COPY LOOK LIKE?
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("4. EXAMPLES: WHAT JUNK-FED COPY LOOKS LIKE")
    print("=" * 72)

    # Find records where the draft clearly quotes navigation text
    junk_with_nav_in_draft = []
    for r in junk:
        research = r.get("research") or []
        first3_texts = [(row.get("fact") or "")[:200] for row in research[:3]]
        drafts = extract_drafts(r)
        for d in drafts:
            for ft in first3_texts:
                # Check if any 4+ word sequence from the junk evidence appears in the draft
                ft_words = re.findall(r"[a-z']{3,}", ft.lower())
                for i in range(len(ft_words) - 3):
                    phrase = " ".join(ft_words[i:i+4])
                    if phrase in d["full_text"].lower():
                        junk_with_nav_in_draft.append({
                            "record": r["id"],
                            "step": d["step"],
                            "phrase": phrase,
                            "draft_snippet": d["full_text"][:150],
                        })
                        break

    print(f"\n  JUNK-FED drafts that directly quote navigation text: "
          f"{len(junk_with_nav_in_draft)}")
    for ex in junk_with_nav_in_draft[:10]:
        print(f"\n    Record: {ex['record']}, step: {ex['step']}")
        print(f"    Quoted phrase: \"{ex['phrase']}\"")
        print(f"    Draft: {ex['draft_snippet'][:120]}...")

    # -----------------------------------------------------------------------
    # 5. THE USABLE EVIDENCE THAT EXISTS BUT ISN'T SHOWN
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("5. USABLE EVIDENCE ON JUNK-FED RECORDS")
    print("=" * 72)

    junk_with_usable_later = 0
    for r in junk:
        research = r.get("research") or []
        # First 3 are unusable, but are there usable rows after?
        later = research[3:]
        if any(row.get("quality") in ("medium", "strong") for row in later):
            junk_with_usable_later += 1

    print(f"\n  JUNK-FED records with usable evidence in rows 4+: "
          f"{junk_with_usable_later} of {len(junk)}")
    print(f"  These records HAVE facts but for_prompt() never reaches them.")

    # Show what good evidence looks like on these records
    print(f"\n  Examples of usable evidence on JUNK-FED records:")
    shown = 0
    for r in junk:
        research = r.get("research") or []
        later = research[3:]
        usable = [row for row in later if row.get("quality") in ("medium", "strong")]
        if usable and shown < 5:
            print(f"\n    Record: {r['id']}")
            for row in usable[:2]:
                fact = (row.get("fact") or "")[:120]
                print(f"      [{row.get('quality')}] {fact}...")
            shown += 1

    # -----------------------------------------------------------------------
    # 6. STATISTICAL HONESTY CHECK
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("6. STATISTICAL POWER ASSESSMENT")
    print("=" * 72)

    n_junk = len(junk)
    n_fact = len(fact)
    # For a two-proportion z-test at alpha=0.05, power=0.80:
    # The minimum detectable effect (MDE) depends on sample sizes.
    # With n1=32, n2=~100, the MDE is roughly 20-25 percentage points.
    print(f"\n  JUNK-FED: {n_junk} records")
    print(f"  FACT-FED: {n_fact} records")
    print(f"  Minimum detectable difference at ~80% power: ~20-25pp")
    print(f"  Pre-stated actionable threshold: {MIN_ACTIONABLE_DIFF_PP}pp")
    print(f"  VERDICT: This comparison can detect LARGE differences only.")
    print(f"  A null result at this sample size proves nothing.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
