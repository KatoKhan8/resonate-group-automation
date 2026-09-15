#!/usr/bin/env python3
"""TASK-115: Measure whether declared openings are honoured in generated text.

For each approach, generate a LinkedIn variant and hand-judge whether the
text actually opens on pain, outcome, evidence, question, or plain statement
as declared.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import store, variantgen, generate, cadencelibrary, llm, clients


def load_test_record():
    """Load a real record from the snapshot."""
    snapshot = Path("work/queue.snapshot.jsonl")
    if not snapshot.exists():
        print("ERROR: work/queue.snapshot.jsonl not found")
        sys.exit(1)
    with open(snapshot, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("state") == "verified" and rec.get("contacts"):
                return rec
    return None


def generate_one_approach(rec, contact, approach, step_key, sequence, config):
    """Generate a single variant for one approach and return the text."""
    model = llm.from_env()
    if isinstance(model, llm.NoModel):
        print("ERROR: No model configured")
        sys.exit(1)

    channel = "linkedin"
    _, ordinal, _ = generate.position(sequence, step_key)
    purpose = generate.purpose_for(channel, ordinal, sequence=sequence)

    context_block = generate.context_for(
        "linkedin_note", rec, contact, None, step_key, sequence)

    # For observation_led, inject the licensed observation
    if approach == "observation_led":
        available = variantgen.approaches_available(rec, contact, "linkedin_message", config)
        obs_entry = next((a for a in available if a["approach"] == "observation_led"), None)
        if obs_entry and obs_entry.get("available") and obs_entry.get("evidence"):
            context_block["observation"] = obs_entry["evidence"]

    prompt = variantgen.variant_prompt(approach, "linkedin_note", purpose, context_block)

    # Call the model
    prompt_step = "linkedin_note"
    data, attempts, errors = llm.ask(model, prompt_step, prompt)
    if not data:
        return None

    note = data.get("note") or data.get("body") or ""
    from src import lint
    if note:
        note = lint.normalise_punctuation(note)

    return note


def main():
    print("TASK-115: Are declared openings honoured in generated text?\n")

    rec = load_test_record()
    if not rec:
        print("ERROR: No suitable record found in snapshot")
        sys.exit(1)

    print(f"Record: {rec.get('company')} ({rec.get('id')})")
    client_name = rec.get("client", "productive")
    config = clients.load(client_name)
    contact = rec["contacts"][0]
    print(f"Contact: {contact.get('name')} ({contact.get('title')})")

    seq_name = "productive_li_heavy_v1"
    sequence = cadencelibrary.named(seq_name)
    if not sequence:
        print(f"ERROR: Sequence {seq_name} not found")
        sys.exit(1)

    # Find LinkedIn message steps
    li_steps = []
    for step in sequence:
        if step.get("channel") == "linkedin_message" or step.get("linkedin_action") == "message":
            li_steps.append(step.get("key"))
    print(f"LinkedIn steps: {li_steps}\n")

    # Run on the first three LinkedIn steps
    target_steps = li_steps[:3]
    if not target_steps:
        print("ERROR: No LinkedIn message steps found")
        sys.exit(1)

    model = llm.from_env()

    for step_key in target_steps:
        print(f"{'='*70}")
        print(f"GENERATING FOR: {step_key}")
        print(f"{'='*70}\n")

        approaches = ["concise_direct", "conversational", "problem_led",
                       "observation_led", "value_led"]

        for approach in approaches:
            spec = variantgen.APPROACHES[approach]
            print(f"--- {approach} ---")
            print(f"  Declared opening: {spec['opening']}")

            # Check availability
            available = variantgen.approaches_available(
                rec, contact, "linkedin_message", config)
            avail_entry = next((a for a in available if a["approach"] == approach), None)
            if avail_entry and not avail_entry.get("available"):
                print(f"  SKIPPED: {avail_entry.get('why', 'not available')}")
                print()
                continue

            text = generate_one_approach(
                rec, contact, approach, step_key, sequence, config)
            if text is None:
                print(f"  GENERATION FAILED (model returned no data)")
                print()
                continue

            print(f"\n  GENERATED TEXT:")
            for line in text.split("\n"):
                print(f"    | {line}")

            # Analyze the opening
            opening = variantgen._opening_shape(text)
            cta = variantgen._cta_shape(text)
            print(f"\n  _opening_shape: {opening}")
            print(f"  _cta_shape:     {cta}")
            print()

        # Now run the full build_variant_set to get the diversity check result
        print(f"\n{'='*70}")
        print(f"FULL DIVERSITY CHECK for {step_key}")
        print(f"{'='*70}\n")

        result = variantgen.build_variant_set(
            rec, contact, "linkedin_message", step_key, sequence=sequence,
            config=config, model=model, llm_ask=llm.ask)

        print(f"Different: {result['different']}")
        print(f"Problems: {len(result['problems'])}")
        for p in result['problems']:
            print(f"  - {p['a']} vs {p['b']}: {p['why']}")

        print(f"\nStructural summary:")
        for s in result['structural_summary']:
            print(f"  {s['variant_id']:30s}  opening={s['opening']:10s}  "
                  f"cta={s['cta']:10s}  words={s['words']:3d}  "
                  f"approach={s['approach']}")

        # Dump the full texts for hand-judgment
        print(f"\n--- FULL TEXTS for {step_key} ---\n")
        for v in result['variants']:
            vid = v.get("variant_id", "?")
            text = v.get("note") or v.get("body") or v.get("subject") or ""
            style = v.get("style", "?")
            print(f"--- {vid} (style={style}) ---")
            print(text)
            print()


if __name__ == "__main__":
    main()
