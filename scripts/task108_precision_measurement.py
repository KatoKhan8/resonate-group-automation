#!/usr/bin/env python3
"""TASK-108: Propose patterns and measure precision on held-out sample.

The 821 still-unknown replies (after TASK-066/067 patterns) are split:
  - 200 hand-labelled (the training/sample set)
  - 621 held-out (for precision measurement)

For each proposed pattern:
  1. Run on the 621 held-out
  2. Sample up to 30 matches
  3. Hand-verify each match (is it actually the claimed category?)
  4. Report precision = correct / total_matches_sampled
"""
import json
import os
import re
import sys
import tempfile
import random
from collections import Counter

sys.path.insert(0, r'C:\Users\Zvonimir\Desktop\resonate-qwen-7')
from src import replies

random.seed(108)

# Load the full still-unknown set
p = os.path.join(tempfile.gettempdir(), 'task108_still_unknown.json')
with open(p, 'r', encoding='utf-8') as f:
    still_unknown = json.load(f)

# Load the hand-labelled sample indices
# The 200 were sampled with seed=108 from the 821
# We need to identify which 200 are the labelled ones
# Re-run the same sampling to get the indices
all_other = []
p2 = os.path.join(tempfile.gettempdir(), 'task066_categorized.json')
with open(p2, 'r', encoding='utf-8') as f:
    data = json.load(f)
for r in data:
    if r['failure_mode'] == 'other':
        verdict = replies.classify(r['reply_text'], model=None)
        if verdict['classification'] == 'unknown':
            all_other.append(r)

# The first 200 with seed=108 are the labelled ones
random.seed(108)
shuffled = list(all_other)
random.shuffle(shuffled)
labelled_texts = set()
for r in shuffled[:200]:
    labelled_texts.add(r['reply_text'])

held_out = [r for r in all_other if r['reply_text'] not in labelled_texts]
labelled = [r for r in all_other if r['reply_text'] in labelled_texts]

print(f"Total still-unknown: {len(all_other)}")
print(f"Hand-labelled sample: {len(labelled)}")
print(f"Held-out set: {len(held_out)}")

# -----------------------------------------------------------------------
# PROPOSED PATTERNS
# Each pattern is an ACT: stating a fact, naming a time, drawing a boundary.
# No MANNERS (adjectives like "interesting", "curious" without a verb).
# -----------------------------------------------------------------------

PROPOSED_PATTERNS = {
    # --- NOT_RELEVANT: stating employment/role facts ---
    "not_relevant_left_company": {
        "patterns": [
            # "I don't work X anymore" - stating they left
            r"\bi (?:don'?t|do not) work .{2,30} anymore\b",
            # "haven't worked at X" - past tense, stating they left
            r"\b(?:haven'?t|have not) worked (?:at|for) \S+",
            # "I'm not with X" without requiring "anymore" - but requires
            # a capitalized proper noun to avoid matching "I'm not with you"
            r"\bi'?m not with [A-Z]\w+",
            # "no longer at/with X" - variant without "work"
            r"\bno longer (?:at|with) [A-Z]\w+",
        ],
        "category": "not_relevant",
        "description": "Person states they left the company",
    },
    "not_relevant_wrong_role": {
        "patterns": [
            # "not on my radar" / "off my radar" - stating irrelevance
            r"\b(?:not |off )my radar\b",
            # "not in a position to" - stating lack of authority
            r"\bnot in a position to\b",
            # "I don't have anything to do with" - disclaiming involvement
            r"\bi (?:don'?t|do not) have anything to do with\b",
            # "not my position or insight" - disclaiming expertise
            r"\bnot my (?:position|area|remit|decision|call)\b",
        ],
        "category": "not_relevant",
        "description": "Person states it's not their area/role",
    },
    "not_relevant_retired_seeking": {
        "patterns": [
            # "I am retired" - stating retirement
            r"\bi(?:'m| am) retired\b",
            # "seeking employment" / "looking for a role" - job seeker
            r"\b(?:seeking (?:employment|a (?:new )?role)|looking for (?:a |an )?(?:opportunity|role|job))\b",
            # "being made redundant" - losing job
            r"\b(?:being )?(?:made|being) redundant\b",
        ],
        "category": "not_relevant",
        "description": "Person states retirement or job-seeking status",
    },

    # --- NEGATIVE: stating current solution or satisfaction ---
    "negative_own_solution": {
        "patterns": [
            # "custom built/made" - stating they built their own
            r"\bcustom[- ]?(?:built|made)\b",
            # "own software/tool/solution/system/application" - own solution
            r"\bown (?:software|tool|solution|system|application)\b",
            # "we developed our own" - built internally
            r"\b(?:we|they) (?:developed|built|created) (?:a |our )?(?:own |custom )?(?:tool|solution|system|software)\b",
        ],
        "category": "negative",
        "description": "Person states they have their own/custom solution",
    },
    "negative_happy_current": {
        "patterns": [
            # "works well" / "working well" - stating satisfaction
            r"\b(?:works?|working) well\b",
            # "all good" in response to outreach - stating satisfaction
            # Anchored: "all good" at start or after punctuation, not inside
            # a sentence where it could mean something else.
            r"(?:^|[,;:.!] )all good\b",
            # "we good" (informal) - stating satisfaction
            r"\bwe good\b",
            # "happy with the setup/setup we have" - stating satisfaction
            r"\bhappy with (?:the |our |what we have)\b",
        ],
        "category": "negative",
        "description": "Person states satisfaction with current setup",
    },
    "negative_boundary": {
        "patterns": [
            # "do not pitch me" - drawing a boundary
            r"\b(?:do not|don'?t) pitch me\b",
            # "not interesting" with exclamation or period (not "sounds interesting")
            # The "for" gate from TASK-035 keeps "not interesting for" separate.
            # This catches "Not interesting!" / "Non interesting!" as standalone.
            r"\bnot interesting[!.]\b",
            # "they would not agree" - stating an organizational constraint
            r"\b(?:they|we) would not agree\b",
        ],
        "category": "negative",
        "description": "Person draws a boundary or states organizational refusal",
    },

    # --- UNSUBSCRIBE: spam complaints and removal requests ---
    "unsubscribe_spam_complaint": {
        "patterns": [
            # "stop spamming" / "you are spamming" - spam complaint
            r"\b(?:stop |you (?:are|guys) |enjoy )?spam(?:ming|s)?\b",
            # "delete me" - removal request
            r"\b(?:please )?(?:delete|remove) me\b",
            # "I'll report you" / "going to report" - threat to report
            r"\b(?:i'?ll|going to|will) report\b",
            # "block you" - threat to block
            r"\b(?:i'?ll|going to|will) block\b",
        ],
        "category": "unsubscribe",
        "description": "Spam complaint or threat to report/block",
    },

    # --- NOT_NOW: deferral signals ---
    "not_now_deferral": {
        "patterns": [
            # "will reach out (to you) soon" - deferring contact
            r"\b(?:will|shall) reach out(?: to you)? soon\b",
            # "let's reconnect in" - deferring to a later time
            r"\blet'?s reconnect in\b",
            # "not conducting business" - temporary closure
            r"\bnot conducting business\b",
            # "not ready yet" - not ready
            r"\bnot ready yet\b",
        ],
        "category": "not_now",
        "description": "Person defers to a later time",
    },

    # --- MEETING_INTENT: concrete meeting steps ---
    "meeting_intent_proposal": {
        "patterns": [
            # "we can meet online this week" - proposing a meeting
            r"\bwe can meet\b",
            # "catch up around" - proposing a meeting time
            r"\bcatch up (?:around|in|next|on|at)\b",
            # "April/May/... would be good" - naming a time
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December) would be good\b",
        ],
        "category": "meeting_intent",
        "description": "Person proposes a concrete meeting step",
    },
}


def measure_pattern_on_held_out(patterns, held_out_data, max_sample=30):
    """Run patterns on held-out data and sample matches for verification."""
    matches = []
    for r in held_out_data:
        text = replies.normalise(r['reply_text'])
        for pat in patterns:
            if re.search(pat, text, re.I):
                matches.append(r)
                break  # one match per reply is enough

    if not matches:
        return {"matches": 0, "sample": [], "total_in_held_out": 0}

    # Sample up to max_sample
    sample_size = min(max_sample, len(matches))
    sample = random.sample(matches, sample_size)
    return {
        "matches": len(matches),
        "total_in_held_out": len(held_out_data),
        "match_rate": round(len(matches) / len(held_out_data) * 100, 2),
        "sample": sample,
        "sample_size": sample_size,
    }


def main():
    print(f"\n{'='*70}")
    print("PATTERN PROPOSALS AND PRECISION MEASUREMENT")
    print(f"{'='*70}")

    # Also measure on the labelled set for recall
    # Load hand labels
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from task108_hand_labels import LABELS

    # Build a map from reply_text to label for the labelled set
    # Re-run the same sampling to get the ordered list
    random.seed(108)
    shuffled2 = list(all_other)
    random.shuffle(shuffled2)
    labelled_ordered = shuffled2[:200]

    label_map = {}
    for i, r in enumerate(labelled_ordered):
        idx = i + 1
        if idx in LABELS:
            label, _ = LABELS[idx]
            label_map[r['reply_text']] = label

    results = {}
    for name, spec in PROPOSED_PATTERNS.items():
        print(f"\n{'-'*70}")
        print(f"PATTERN: {name}")
        print(f"  Category: {spec['category']}")
        print(f"  Description: {spec['description']}")
        print(f"  Patterns:")
        for p in spec['patterns']:
            print(f"    {p}")

        # Measure on held-out
        ho_result = measure_pattern_on_held_out(spec['patterns'], held_out)
        print(f"\n  Held-out matches: {ho_result['matches']} / {ho_result['total_in_held_out']} "
              f"({ho_result.get('match_rate', 0)}%)")

        # Print sample matches for hand-verification
        if ho_result['sample']:
            print(f"\n  Sample matches (up to 30, for hand-verification):")
            for j, r in enumerate(ho_result['sample']):
                text = r['reply_text'][:150].replace('\n', ' ')
                try:
                    print(f"    [{j+1:2d}] {text}")
                except UnicodeEncodeError:
                    safe = text.encode('ascii', 'replace').decode('ascii')
                    print(f"    [{j+1:2d}] {safe}")

        # Measure on labelled set for recall
        labelled_matches = []
        for r in labelled_ordered:
            text = replies.normalise(r['reply_text'])
            for pat in spec['patterns']:
                if re.search(pat, text, re.I):
                    labelled_matches.append(r)
                    break

        # Check how many of the labelled matches are correct
        correct = 0
        total_with_label = 0
        for r in labelled_matches:
            if r['reply_text'] in label_map:
                total_with_label += 1
                if label_map[r['reply_text']] == spec['category']:
                    correct += 1

        # Also check recall: of the labelled items in this category, how many matched?
        category_count = sum(1 for l in label_map.values() if l == spec['category'])
        recall = round(correct / category_count * 100, 1) if category_count > 0 else 0

        print(f"\n  Labelled set: {len(labelled_matches)} matches")
        if total_with_label > 0:
            precision_labelled = round(correct / total_with_label * 100, 1)
            print(f"  Precision on labelled: {correct}/{total_with_label} = {precision_labelled}%")
        else:
            precision_labelled = None
            print(f"  Precision on labelled: no labelled matches to verify")
        print(f"  Recall on labelled: {correct}/{category_count} = {recall}%")

        results[name] = {
            "held_out_matches": ho_result['matches'],
            "held_out_match_rate": ho_result.get('match_rate', 0),
            "labelled_precision": precision_labelled,
            "recall": recall,
            "sample": ho_result.get('sample', []),
        }

    # Summary
    print(f"\n\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    total_ho_matches = sum(r['held_out_matches'] for r in results.values())
    print(f"Total held-out matches across all patterns: {total_ho_matches} / {len(held_out)}")
    print(f"  ({round(total_ho_matches/len(held_out)*100,1)}% of held-out would be reclassified)")
    print(f"\nPer-pattern summary:")
    for name, r in results.items():
        print(f"  {name:40s}  HO={r['held_out_matches']:3d}  "
              f"prec={r['labelled_precision'] or 'N/A'}%  "
              f"recall={r['recall']}%")


if __name__ == "__main__":
    main()
