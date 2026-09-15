#!/usr/bin/env python3
"""Generate LinkedIn variants for li2, li3, li4 and inspect their openings."""
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

def judge_opening(body, declared):
    """Hand-judge whether the opening matches the declared semantic type."""
    if not body:
        return "EMPTY"

    first_sentence = body.split('.')[0] + '.' if '.' in body else body
    first_lower = first_sentence.lower()

    # Check for question
    if '?' in first_sentence:
        return "question"

    # Check for pain/cost
    pain_words = ['cost', 'spend', 'waste', 'break', 'problem', 'hard', 'difficult',
                  'hours', 'slow', 'risk', 'delay', 'rebuild', 'manual', 'hand']
    if any(w in first_lower for w in pain_words):
        return "pain"

    # Check for outcome/gain
    outcome_words = ['gain', 'save', 'join', 'connect', 'view', 'drop', 'minute',
                     'improve', 'visibility', 'track', 'planning', 'capacity']
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
    node_type = "linkedin"
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
            approach = v.get("style", "unknown")
            body = v.get("body") or v.get("note") or v.get("subject") or ""
            declared = variantgen.APPROACHES.get(approach, {}).get("opening", "unknown")
            detected_punct = variantgen._opening_shape(body)
            judged_semantic = judge_opening(body, declared)

            print(f"\n--- {approach} ---")
            print(f"Declared: {declared}")
            print(f"Detected (punctuation): {detected_punct}")
            print(f"Judged (semantic): {judged_semantic}")
            print(f"Body: {body[:150]}...")

            step_results.append({
                "approach": approach,
                "declared": declared,
                "detected_punct": detected_punct,
                "judged_semantic": judged_semantic,
                "body_preview": body[:100] if body else "",
            })

        all_results[step_key] = step_results

        if skipped:
            print(f"\nSkipped: {[s.get('approach') for s in skipped]}")

    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    for step_key, results in all_results.items():
        print(f"\n{step_key}:")
        print(f"  Total variants: {len(results)}")

        # Count by detected punctuation
        punct_counts = {}
        for r in results:
            p = r["detected_punct"]
            punct_counts[p] = punct_counts.get(p, 0) + 1
        print(f"  By punctuation: {punct_counts}")

        # Count by judged semantic
        semantic_counts = {}
        for r in results:
            s = r["judged_semantic"]
            semantic_counts[s] = semantic_counts.get(s, 0) + 1
        print(f"  By semantic: {semantic_counts}")

        # Count unique (opening, cta) pairs by punctuation
        pairs = set()
        for r in results:
            pairs.add(r["detected_punct"])
        print(f"  Unique opening shapes (punctuation): {len(pairs)}")

        # Count unique by semantic
        semantic_pairs = set()
        for r in results:
            semantic_pairs.add(r["judged_semantic"])
        print(f"  Unique opening shapes (semantic): {len(semantic_pairs)}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
