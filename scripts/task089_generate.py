#!/usr/bin/env python3
"""TASK-089: Generate actual LinkedIn messages at li1, li2, li3 for all
approaches and measure their structure (opening type, CTA type, word count).
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import cadencelibrary, generate, variantgen, llm, clients, store

# Load config
config = clients.load("productive")

# Connect to model
model = llm.from_env()
if isinstance(model, llm.NoModel):
    print("ERROR: No model configured. Set LLM_API_KEY, LLM_BASE_URL, LLM_MODEL in config/.env")
    sys.exit(1)
print(f"Model connected: {type(model).__name__}")

# Create a test record
rec = {
    "company": "Test Agency",
    "domain": "testagency.com",
    "company_facts": {
        "name": "Test Agency",
        "employees": "50",
        "industry": "Marketing",
        "revenue": "$5M",
        "founded": "2015",
        "offices": ["London"],
        "specialties": ["Digital Marketing", "Branding"],
    },
    "lane": "cold",
    "events": [],
    "cadence": {},
}

contact = {
    "name": "Jane Doe",
    "title": "CEO",
    "persona": "founder",
    "angle": "profitability",
}

# Get the sequence
sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1

# Test steps
test_steps = [
    ("li1", "linkedin", 1),
    ("li2", "linkedin", 2),
    ("li3", "linkedin", 3),
]

results = {}

for step_key, channel, ordinal in test_steps:
    print(f"\n{'=' * 70}")
    print(f"Generating variants for {step_key} (LinkedIn step {ordinal})")
    print(f"{'=' * 70}")

    # Get the purpose
    purpose = generate.purpose_for(channel, ordinal, sequence=sequence)
    print(f"\nPurpose (rung {ordinal}):")
    print(f"  {purpose}")

    # Get available approaches
    available = variantgen.approaches_available(rec, contact, "linkedin_message", config)

    # Build context
    context_block = generate.context_for(
        "linkedin_note", rec, contact, config, step_key, sequence)

    # Generate for each approach
    step_results = []
    for entry in available:
        approach = entry["approach"]
        if not entry.get("available"):
            print(f"\n  {approach}: SKIPPED - {entry.get('why')}")
            continue

        spec = variantgen.APPROACHES[approach]
        prompt = variantgen.variant_prompt(approach, "linkedin_note", purpose, context_block)

        print(f"\n  Generating {approach}...")
        print(f"    Approach spec: opening={spec['opening']}, cta={spec['cta']}, tone={spec['tone']}")

        # Call the model
        try:
            data, attempts, errors = llm.ask(model, "linkedin_note", prompt)

            if data and data.get("note"):
                note = data["note"]
                word_count = len(note.split())
                char_count = len(note)

                # Analyze structure
                first_line = note.strip().split("\n", 1)[0].strip()
                last_line = [l.strip() for l in note.strip().split("\n") if l.strip()][-1] if note.strip() else ""

                opening_is_question = first_line.endswith("?")
                cta_is_question = last_line.endswith("?")

                opening_type = "question" if opening_is_question else "statement"
                cta_type = "question" if cta_is_question else "statement"

                print(f"    Generated: {word_count} words, {char_count} chars")
                print(f"    Opening: {opening_type} - {first_line[:80]}")
                print(f"    CTA: {cta_type} - {last_line[:80]}")
                print(f"    Full note: {note[:200]}")

                step_results.append({
                    "approach": approach,
                    "spec_opening": spec["opening"],
                    "spec_cta": spec["cta"],
                    "actual_opening": opening_type,
                    "actual_cta": cta_type,
                    "words": word_count,
                    "chars": char_count,
                    "note": note,
                })
            else:
                print(f"    FAILED: {errors}")
        except Exception as e:
            print(f"    ERROR: {e}")

    results[step_key] = step_results

# Summary table
print("\n\n")
print("=" * 70)
print("SUMMARY TABLE: Opening type / CTA type / Word count per approach")
print("=" * 70)

for step_key in ["li1", "li2", "li3"]:
    step_data = results.get(step_key, [])
    print(f"\n{step_key}:")
    print(f"{'Approach':<20} {'Spec Open':<12} {'Spec CTA':<15} {'Actual Open':<12} {'Actual CTA':<12} {'Words':<8} {'Chars':<8}")
    print("-" * 90)
    for r in step_data:
        print(f"{r['approach']:<20} {r['spec_opening']:<12} {r['spec_cta']:<15} {r['actual_opening']:<12} {r['actual_cta']:<12} {r['words']:<8} {r['chars']:<8}")

# Diversity collisions
print("\n\n")
print("=" * 70)
print("DIVERSITY COLLISIONS: Pairs with same opening AND same CTA")
print("=" * 70)

for step_key in ["li1", "li2", "li3"]:
    step_data = results.get(step_key, [])
    collisions = []
    for i, a in enumerate(step_data):
        for b in step_data[i+1:]:
            if a["actual_opening"] == b["actual_opening"] and a["actual_cta"] == b["actual_cta"]:
                collisions.append((a["approach"], b["approach"], a["actual_opening"], a["actual_cta"]))

    print(f"\n{step_key}: {len(collisions)} collisions")
    for a, b, open_type, cta_type in collisions:
        print(f"  - {a} vs {b}: both {open_type}/{cta_type}")
