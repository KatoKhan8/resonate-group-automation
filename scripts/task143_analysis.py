"""TASK-143: Where does junk evidence actually surface?

Snapshot: 2026-09-14T21:52:15Z from master 0ac5e60, 300 records.

Splits the 203 records with research into JUNK-FED (first 3 rows all
unusable/missing quality) and FACT-FED (first 3 rows all usable), then
compares rejection reasons, draft quality, and vocabulary.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SNAPSHOT = Path("C:/Users/Zvonimir/Desktop/resonate-qwen-6/work/queue.snapshot.jsonl")

# --- Generic product language that signals "the model had nothing to work with"
GENERIC_PHRASES = [
    "streamline your operations", "optimise your workflow", "optimize your workflow",
    "improve your efficiency", "boost your productivity", "enhance your",
    "take your business to the next level", "scale your business",
    "help you grow", "help you succeed", "comprehensive solution",
    "end-to-end solution", "all-in-one platform", "one platform",
    "powerful tool", "cutting-edge", "industry-leading", "best-in-class",
    "world-class", "game-changer", "transform your", "revolutionise",
    "revolutionize", "innovative solution", "tailored to your needs",
    "designed for", "built for professionals", "trusted by",
    "thousands of companies", "leading providers", "resource planning",
    "project management software", "professional services",
    "clear visibility", "real-time insights", "data-driven",
    "make better decisions", "informed decisions", "stay ahead",
    "competitive edge", "peace of mind", "focus on what matters",
    "what matters most", "let us help", "we can help",
    "get in touch", "learn more", "find out more",
]

# --- Repetition/angle-wording leakage patterns
REPETITION_PATTERNS = [
    "angle_wording_leakage",
    "repeats another",
    "repetition",
    "same angle",
    "same wording",
    "too similar",
]

# --- Claims gate patterns
CLAIMS_PATTERNS = [
    "unsupported claim",
    "claims_gate",
    "asserts we have",
    "no confirmed touch",
]

# --- Other lint failures (not repetition, not claims)
LINT_PATTERNS = [
    "filler_phrase",
    "em_dash",
    "em dash",
    "too long",
    "too short",
    "missing personalisation",
    "generic opener",
    "generic closing",
]


def is_junk(item):
    """A research row is junk if its quality is unusable or missing."""
    q = item.get("quality", "unusable")
    return q == "unusable"


def classify_record(rec):
    """JUNK-FED if first 3 rows are all junk, FACT-FED if all usable, else MIXED."""
    research = rec.get("research") or []
    if not research:
        return None
    first3 = research[:3]
    junk_count = sum(1 for item in first3 if is_junk(item))
    if junk_count == len(first3):
        return "junk_fed"
    elif junk_count == 0:
        return "fact_fed"
    return "mixed"


def get_drafts(rec):
    """Extract all draft texts from cadence."""
    drafts = []
    cadence = rec.get("cadence") or {}
    for contact_key, steps in cadence.items():
        if not isinstance(steps, dict):
            continue
        for step_id, step_data in steps.items():
            if isinstance(step_data, dict) and step_data.get("note"):
                drafts.append({
                    "contact": contact_key,
                    "step": step_id,
                    "channel": step_data.get("channel", ""),
                    "text": step_data["note"],
                })
    return drafts


def get_rejections(rec):
    """Extract lint_failed events and classify the failure reasons."""
    rejections = []
    for e in rec.get("events") or []:
        if e.get("type") != "lint_failed":
            continue
        failures = e.get("failures") or []
        classes = set()
        for f in failures:
            f_lower = f.lower()
            if any(p in f_lower for p in REPETITION_PATTERNS):
                classes.add("repetition")
            if any(p in f_lower for p in CLAIMS_PATTERNS):
                classes.add("claims")
            if any(p in f_lower for p in LINT_PATTERNS):
                classes.add("lint")
        if not classes:
            classes.add("other_lint")
        rejections.append({
            "contact": e.get("contact", ""),
            "step": e.get("step", ""),
            "channel": e.get("channel", ""),
            "failures": failures,
            "classes": sorted(classes),
            "attempt": e.get("attempt", 1),
        })
    return rejections


def count_generic_phrases(text):
    """How many generic product phrases appear in the text."""
    text_lower = text.lower()
    return sum(1 for phrase in GENERIC_PHRASES if phrase in text_lower)


def has_specific_fact(text, research_items):
    """Does the draft text reference a specific fact from the research?

    Checks whether any non-trivial content word from a research fact appears
    in the draft. A content word is 5+ chars, alphabetic, not a common stopword.
    """
    stopwords = {
        "about", "their", "there", "would", "could", "should", "this",
        "that", "with", "from", "have", "been", "will", "your", "what",
        "which", "when", "where", "how", "all", "each", "every", "both",
        "few", "more", "most", "other", "some", "such", "than", "them",
        "very", "just", "also", "into", "over", "after", "before",
    }
    text_lower = text.lower()
    text_words = set(re.findall(r"[a-z]{5,}", text_lower)) - stopwords

    for item in research_items:
        fact = (item.get("fact") or "").lower()
        fact_words = set(re.findall(r"[a-z]{5,}", fact)) - stopwords
        # If 2+ content words from a fact appear in the draft, it references it
        overlap = text_words & fact_words
        if len(overlap) >= 2:
            return True
    return False


def word_count(text):
    return len(text.split())


def vocabulary_words(text):
    """Lowercase alphabetic words of 4+ chars."""
    return set(re.findall(r"[a-z]{4,}", text.lower()))


def jaccard(set_a, set_b):
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def main():
    records = [json.loads(line) for line in open(SNAPSHOT, encoding="utf-8")]
    with_research = [r for r in records if r.get("research")]

    # --- Classify records
    groups = {"junk_fed": [], "fact_fed": [], "mixed": []}
    for r in with_research:
        cls = classify_record(r)
        if cls:
            groups[cls].append(r)

    print("=" * 70)
    print("TASK-143: Junk evidence impact analysis")
    print(f"Snapshot: 2026-09-14T21:52:15Z from master 0ac5e60, 300 records")
    print("=" * 70)

    print(f"\nTotal records: {len(records)}")
    print(f"Records with research: {len(with_research)}")
    print(f"  JUNK-FED (first 3 all unusable): {len(groups['junk_fed'])}")
    print(f"  FACT-FED (first 3 all usable):    {len(groups['fact_fed'])}")
    print(f"  MIXED:                            {len(groups['mixed'])}")

    # --- Overall research row stats
    total_rows = sum(len(r.get("research", [])) for r in with_research)
    junk_rows = sum(1 for r in with_research for item in r["research"] if is_junk(item))
    print(f"\nTotal research rows: {total_rows}")
    print(f"  Junk (unusable/missing quality): {junk_rows} ({100*junk_rows/total_rows:.1f}%)")
    print(f"  Fact (usable quality):           {total_rows - junk_rows} ({100*(total_rows-junk_rows)/total_rows:.1f}%)")

    # --- Compare the two main groups
    for label in ["junk_fed", "fact_fed"]:
        recs = groups[label]
        print(f"\n{'=' * 70}")
        print(f"Group: {label.upper()} ({len(recs)} records)")
        print(f"{'=' * 70}")

        # Drafts
        all_drafts = []
        for r in recs:
            all_drafts.extend(get_drafts(r))

        print(f"\nDrafts: {len(all_drafts)} total across {sum(1 for r in recs if get_drafts(r))} records")

        if not all_drafts:
            print("  (no drafts to analyse)")
            continue

        # Draft lengths
        lengths = [word_count(d["text"]) for d in all_drafts]
        avg_len = sum(lengths) / len(lengths) if lengths else 0
        print(f"  Avg draft length: {avg_len:.1f} words (min={min(lengths)}, max={max(lengths)})")

        # Rejections
        all_rejections = []
        for r in recs:
            all_rejections.extend(get_rejections(r))

        print(f"\nRejections (lint_failed events): {len(all_rejections)}")

        # Classify rejection reasons
        reason_counts = Counter()
        for rej in all_rejections:
            for cls in rej["classes"]:
                reason_counts[cls] += 1

        # Also count individual failure strings
        failure_strings = Counter()
        for rej in all_rejections:
            for f in rej["failures"]:
                # Truncate long failure strings
                key = f[:80] if len(f) > 80 else f
                failure_strings[key] += 1

        records_with_rejections = sum(1 for r in recs if get_rejections(r))
        print(f"  Records with rejections: {records_with_rejections} of {len(recs)}")
        print(f"  Rejection classes:")
        for cls, count in reason_counts.most_common():
            print(f"    {cls}: {count}")

        if failure_strings:
            print(f"\n  Top failure reasons:")
            for reason, count in failure_strings.most_common(10):
                print(f"    [{count}x] {reason}")

        # Generic language
        generic_counts = [count_generic_phrases(d["text"]) for d in all_drafts]
        avg_generic = sum(generic_counts) / len(generic_counts) if generic_counts else 0
        drafts_with_generic = sum(1 for c in generic_counts if c > 0)
        print(f"\nGeneric product language:")
        print(f"  Avg generic phrases per draft: {avg_generic:.2f}")
        print(f"  Drafts with 1+ generic phrase: {drafts_with_generic} of {len(all_drafts)} ({100*drafts_with_generic/len(all_drafts):.1f}%)")

        # Fact referencing
        fact_ref_counts = []
        for d in all_drafts:
            # Find the record this draft belongs to
            for r in recs:
                cad = r.get("cadence") or {}
                if d["contact"] in cad:
                    steps = cad[d["contact"]]
                    if isinstance(steps, dict) and d["step"] in steps:
                        research_items = r.get("research") or []
                        refs_fact = has_specific_fact(d["text"], research_items)
                        fact_ref_counts.append(refs_fact)
                        break

        if fact_ref_counts:
            refs = sum(1 for x in fact_ref_counts if x)
            print(f"\nFact referencing:")
            print(f"  Drafts referencing a research fact: {refs} of {len(fact_ref_counts)} ({100*refs/len(fact_ref_counts):.1f}%)")

        # Vocabulary overlap (average pairwise Jaccard)
        draft_vocabs = [vocabulary_words(d["text"]) for d in all_drafts]
        if len(draft_vocabs) >= 2:
            # Sample up to 100 pairs to keep it fast
            import random
            random.seed(42)
            pairs = []
            n = len(draft_vocabs)
            max_pairs = min(200, n * (n - 1) // 2)
            indices = list(range(n))
            for _ in range(max_pairs):
                i, j = random.sample(indices, 2)
                pairs.append(jaccard(draft_vocabs[i], draft_vocabs[j]))
            avg_jaccard = sum(pairs) / len(pairs) if pairs else 0
            print(f"\nVocabulary overlap (avg pairwise Jaccard, {len(pairs)} samples): {avg_jaccard:.3f}")

        # Show sample drafts
        print(f"\nSample drafts (first 3):")
        for d in all_drafts[:3]:
            text = d["text"][:200].replace("\n", " ")
            print(f"  [{d['channel']}/{d['step']}] {text}...")

    # --- Direct comparison table
    print(f"\n{'=' * 70}")
    print("COMPARISON SUMMARY")
    print(f"{'=' * 70}")

    for label in ["junk_fed", "fact_fed"]:
        recs = groups[label]
        all_drafts = []
        for r in recs:
            all_drafts.extend(get_drafts(r))
        all_rejections = []
        for r in recs:
            all_rejections.extend(get_rejections(r))

        n_recs = len(recs)
        n_drafts = len(all_drafts)
        n_recs_with_drafts = sum(1 for r in recs if get_drafts(r))
        n_rejections = len(all_rejections)
        n_recs_with_rejections = sum(1 for r in recs if get_rejections(r))

        repetition_count = sum(1 for rej in all_rejections if "repetition" in rej["classes"])
        claims_count = sum(1 for rej in all_rejections if "claims" in rej["classes"])
        lint_count = sum(1 for rej in all_rejections if "lint" in rej["classes"])

        lengths = [word_count(d["text"]) for d in all_drafts]
        avg_len = sum(lengths) / len(lengths) if lengths else 0

        generic_counts = [count_generic_phrases(d["text"]) for d in all_drafts]
        avg_generic = sum(generic_counts) / len(generic_counts) if generic_counts else 0
        pct_generic = 100 * sum(1 for c in generic_counts if c > 0) / len(generic_counts) if generic_counts else 0

        print(f"\n{label.upper()} ({n_recs} records):")
        print(f"  Records with drafts: {n_recs_with_drafts} ({100*n_recs_with_drafts/n_recs:.0f}%)")
        print(f"  Total drafts: {n_drafts}")
        print(f"  Avg draft length: {avg_len:.1f} words")
        print(f"  Records with rejections: {n_recs_with_rejections} ({100*n_recs_with_rejections/n_recs:.0f}%)")
        print(f"  Total rejections: {n_rejections}")
        print(f"    repetition: {repetition_count}")
        print(f"    claims: {claims_count}")
        print(f"    lint: {lint_count}")
        print(f"  Avg generic phrases/draft: {avg_generic:.2f}")
        print(f"  Drafts with generic language: {pct_generic:.0f}%")


if __name__ == "__main__":
    main()
