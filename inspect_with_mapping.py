#!/usr/bin/env python3
"""Generate LinkedIn variants and map styles back to approaches."""
import json
import sys
from src import variantgen, llm, cadencelibrary

FIXTURE_RECORD = {
    "id": "test-linkedin-inspection",
    "lane": "domains",
    "client": "productive",
    "company": "Acme Agency",
    "domain": "acme.test",
    "context": "",
    "signal": "",
    "company_facts": {
        "name": "Acme Agency",
        "industry": "Marketing & Advertising",
        "employees": 25,
        "employee_range": "11-50 employees",
        "research_outcome": "HTTP_SUCCESS",
    },
    "contacts": [{
        "name": "Anna Smith",
        "title": "Founder",
        "linkedin": "annasmith",
        "email": "anna@acme.test",
        "email_source": "provider",
        "persona": "economic_buyer",
        "angle": "founder",
        "verdict": "valid",
        "sendable": True,
        "primary": True,
        "key": "anna-smith",
    }],
    "diagnosis": {
        "died_on": None,
        "died_because": None,
        "failure_mode": None,
        "last_position": None,
    },
    "hook": "Agencies your size rebuild utilisation reports by hand every Monday morning.",
    "sizing": {"employees": 25},
    "excluded": [],
    "cadence": {},
    "log": [],
    "events": [],
}

# Reverse mapping: style -> approach for linkedin_message
STYLE_TO_APPROACH = {v: k for k, v in variantgen.APPROACH_TO_STYLE.get("linkedin_message", {}).items()}

def judge_opening_semantic(body):
    """Hand-judge the semantic opening type."""
    if not body:
        return "empty"

    first_sentence = body.split('.')[0] + '.' if '.' in body else body
    first_lower = first_sentence.lower()

    # Check for question first
    if '?' in first_sentence:
        return "question"

    # Check for pain/cost
    pain_words = ['cost', 'spend', 'waste', 'break', 'problem', 'hard', 'difficult',
                  'hours', 'slow', 'risk', 'delay', 'rebuild', 'manual', 'hand',
                  'separately', 'without clear', 'often end up', 'leads to']
    if any(w in first_lower for w in pain_words):
        return "pain"

    # Check for outcome/gain
    outcome_words = ['gain', 'save', 'join', 'connect', 'view', 'drop', 'minute',
                     'improve', 'visibility', 'track', 'planning', 'capacity',
                     'reaching out from a team that helps', 'our product']
    if any(w in first_lower for w in outcome_words):
        return "outcome"

    # Check for evidence/observation
    evidence_words = ['saw', 'noticed', 'reviewing', 'growing', 'hiring', 'raised',
                      'congrats', 'announced']
    if any(w in first_lower for w in evidence_words):
        return "evidence"

    # Default to statement
    return "statement"

def main():
    model = llm.from_env()
    if not model:
        print("ERROR: No model configured", file=sys.stderr)
        return 1

    contact = FIXTURE_RECORD["contacts"][0]
    node_type = "linkedin_message"  # Use the specific type, not just "linkedin"
    sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1

    print(f"Model: {getattr(model, 'model', 'unknown')}")
    print("=" * 80)

    all_results = {}

    for step_key in ["li2", "li3", "li4"]:
        print(f"\n{'='*80}")
        print(f"STEP: {step_key}")
        print(f"{'='*80}")

        result = variantgen.build_variant_set(
            FIXTURE_RECORD, contact, node_type, step_key,
            sequence=sequence, config=None,
            llm_ask=llm.ask, model=model)

        variants = result.get("variants", [])
        skipped = result.get("skipped", [])

        print(f"\nGenerated {len(variants)} variants, skipped {len(skipped)}")

        step_results = []
        for v in variants:
            style = v.get("style", "unknown")
            approach = STYLE_TO_APPROACH.get(style, style)
            body = v.get("body") or v.get("note") or v.get("subject") or ""
            declared = variantgen.APPROACHES.get(approach, {}).get("opening", "unknown")
            detected_punct = variantgen._opening_shape(body)
            judged_semantic = judge_opening_semantic(body)

            print(f"\n--- {style} (approach: {approach}) ---")
            print(f"Declared opening: {declared}")
            print(f"Detected (punctuation): {detected_punct}")
            print(f"Judged (semantic): {judged_semantic}")
            print(f"Match: {'YES' if declared == judged_semantic or (declared in ['pain', 'outcome', 'evidence'] and judged_semantic == declared) else 'NO'}")
            print(f"Body: {body[:200]}")

            step_results.append({
                "style": style,
                "approach": approach,
                "declared": declared,
                "detected_punct": detected_punct,
                "judged_semantic": judged_semantic,
            })

        all_results[step_key] = step_results

        if skipped:
            print(f"\nSkipped: {[s.get('approach') for s in skipped]}")

    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY: ARE DECLARED OPENINGS HONORED?")
    print(f"{'='*80}")

    total_match = 0
    total_count = 0

    for step_key, results in all_results.items():
        print(f"\n{step_key}:")
        for r in results:
            declared = r["declared"]
            judged = r["judged_semantic"]
            # Consider it a match if:
            # - declared == judged (exact match for question/statement)
            # - declared is pain/outcome/evidence and judged matches
            match = (declared == judged) or \
                    (declared in ["pain", "outcome", "evidence"] and judged == declared)
            total_match += int(match)
            total_count += 1
            print(f"  {r['approach']:20s} declared={declared:10s} judged={judged:10s} {'YES' if match else 'NO'}")

    print(f"\n\nOverall: {total_match}/{total_count} declared openings honored ({100*total_match/total_count:.0f}%)")

    # Now measure collisions with semantic openings
    print(f"\n\n{'='*80}")
    print("COLLISION ANALYSIS: PUNCTUATION vs SEMANTIC")
    print(f"{'='*80}")

    for step_key, results in all_results.items():
        print(f"\n{step_key}:")

        # By punctuation
        punct_openings = [r["detected_punct"] for r in results]
        unique_punct = len(set(punct_openings))

        # By semantic
        semantic_openings = [r["judged_semantic"] for r in results]
        unique_semantic = len(set(semantic_openings))

        print(f"  Punctuation: {punct_openings}")
        print(f"  Unique (punctuation): {unique_punct}")
        print(f"  Semantic: {semantic_openings}")
        print(f"  Unique (semantic): {unique_semantic}")
        print(f"  Improvement: {unique_semantic - unique_punct} more unique openings")

    return 0

if __name__ == "__main__":
    sys.exit(main())
