#!/usr/bin/env python3
"""Generate LinkedIn variants and inspect their openings.

This script generates real LinkedIn variants using the configured model
and inspects whether the declared semantic opening (pain, outcome, evidence,
question, statement) is actually honored in the generated text.
"""
import json
import sys
from src import variantgen, llm, store, cadencelibrary

# Use a fixture record for testing
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

def main():
    # Load model config
    model = llm.from_env()
    if not model:
        print("ERROR: No model configured", file=sys.stderr)
        return 1

    contact = FIXTURE_RECORD["contacts"][0]
    node_type = "linkedin"
    step_key = "li2"
    sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1

    print(f"Generating LinkedIn variants for {FIXTURE_RECORD['company']}")
    print(f"Model: {getattr(model, 'model', 'unknown')}")
    print(f"Step: {step_key}")
    print("=" * 80)

    # Build the variant set
    result = variantgen.build_variant_set(
        FIXTURE_RECORD, contact, node_type, step_key,
        sequence=sequence, config=None,
        llm_ask=llm.ask, model=model)

    variants = result.get("variants", [])
    skipped = result.get("skipped", [])

    print(f"\nGenerated {len(variants)} variants, skipped {len(skipped)}")
    print("=" * 80)

    # Inspect each variant
    for i, v in enumerate(variants, 1):
        approach = v.get("style", "unknown")
        body = v.get("body") or v.get("note") or v.get("subject") or ""
        declared = variantgen.APPROACHES.get(approach, {}).get("opening", "unknown")

        print(f"\n--- Variant {i}: {approach} ---")
        print(f"Declared opening: {declared}")
        print(f"Detected opening: {variantgen._opening_shape(body)}")
        print(f"Detected CTA: {variantgen._cta_shape(body)}")
        print(f"\nFull text:")
        print(body if body else "(empty)")
        print("-" * 80)

        if not body:
            print("\n(NO BODY - skipping hand judgment)")
            continue

        # Hand-judge the opening
        first_sentence = body.split('.')[0] + '.' if '.' in body else body
        print(f"\nFirst sentence: {first_sentence}")
        print(f"Does it open on pain/cost? {'YES' if any(w in first_sentence.lower() for w in ['cost', 'spend', 'waste', 'break', 'problem', 'hard', 'difficult']) else 'NO'}")
        print(f"Does it open on outcome/gain? {'YES' if any(w in first_sentence.lower() for w in ['gain', 'save', 'join', 'connect', 'view', 'drop', 'minute']) else 'NO'}")
        print(f"Does it open on evidence/observation? {'YES' if any(w in first_sentence.lower() for w in ['saw', 'noticed', 'reviewing', 'growing', 'hiring', 'raised']) else 'NO'}")
        print(f"Does it open with a question? {'YES' if '?' in first_sentence else 'NO'}")

    if skipped:
        print("\n\n=== SKIPPED APPROACHES ===")
        for s in skipped:
            print(f"  {s.get('approach')}: {s.get('why')}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
