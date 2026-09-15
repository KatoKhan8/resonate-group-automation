#!/usr/bin/env python3
"""TASK-115: Is the declared opening honoured in the generated text?

For each approach, generate the text and judge whether it actually opens
on pain, on outcome, on evidence, on a question, or on a plain statement.

This is the single most important question: if the declared opening is NOT
honoured, then comparing declared values would compare LABELS rather than
copy - and a check that compares labels passes five identical messages that
merely carry five different tags.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import (store, variantgen, generate, cadencelibrary, llm,
                 clients)


def load_test_record():
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


def generate_and_capture(rec, contact, step_key, sequence, config, model):
    """Generate a full variant set and capture everything."""
    node_type = "linkedin_message"
    result = variantgen.build_variant_set(
        rec, contact, node_type, step_key, sequence=sequence,
        config=config, model=model, llm_ask=llm.ask)
    return result


def classify_opening_by_hand(text, approach, approach_spec):
    """Print the text and the declared opening for human judgement."""
    declared = approach_spec.get("opening", "?")
    desc = approach_spec.get("description", "")
    # Extract first sentence
    import re
    match = re.search(r'[.?!]\s', text)
    if match:
        first_sentence = text[:match.end()].strip()
    else:
        first_sentence = text
    return {
        "approach": approach,
        "declared_opening": declared,
        "first_sentence": first_sentence,
        "full_text": text,
        "description": desc,
    }


def main():
    print("TASK-115: Is the declared opening honoured?\n")

    rec = load_test_record()
    if not rec:
        print("ERROR: No suitable record found")
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

    model = llm.from_env()
    if isinstance(model, llm.NoModel):
        print("ERROR: No model configured")
        sys.exit(1)

    # Find LinkedIn message steps
    li_steps = []
    for step in sequence:
        ch = step.get("channel", "")
        action = step.get("linkedin_action", "")
        if ch == "linkedin_message" or action == "message":
            li_steps.append(step.get("key"))

    print(f"Sequence: {seq_name}")
    print(f"LinkedIn message steps: {li_steps}\n")

    # Show the APPROACHES declarations first
    print("=" * 70)
    print("APPROACH DECLARATIONS")
    print("=" * 70)
    for name, spec in variantgen.APPROACHES.items():
        print(f"\n  {name}:")
        print(f"    declared opening: {spec['opening']}")
        print(f"    description: {spec['description'][:100]}...")

    # Generate variants for each LinkedIn step
    all_results = {}
    for step_key in li_steps[:4]:  # li1 through li4
        print(f"\n{'=' * 70}")
        print(f"GENERATING: {step_key}")
        print(f"{'=' * 70}\n")

        result = generate_and_capture(
            rec, contact, step_key, sequence, config, model)

        n_variants = len(result.get("variants", []))
        different = result.get("different")
        problems = result.get("problems", [])
        summary = result.get("structural_summary", [])

        print(f"Generated: {n_variants} variants")
        print(f"Different: {different}")
        if problems:
            print(f"Problems: {len(problems)}")
            for p in problems:
                print(f"  - {p['a']} vs {p['b']}: {p['why']}")

        print(f"\nStructural summary (detector view):")
        for s in summary:
            print(f"  {s['variant_id']:30s}  opening={s['opening']:10s}  "
                  f"cta={s['cta']:10s}  words={s['words']:3d}  "
                  f"approach={s['approach']}")

        # Now show the ACTUAL TEXT for hand-judgement
        print(f"\n--- FULL TEXT FOR HAND JUDGEMENT ---\n")
        generated = result.get("generated", [])
        entries = []
        for g in generated:
            approach = g.get("approach")
            variant = g.get("variant")
            if variant:
                text = (variant.get("note") or variant.get("body") or
                        variant.get("subject") or "")
                spec = variantgen.APPROACHES.get(approach, {})
                entry = classify_opening_by_hand(text, approach, spec)
                entries.append(entry)

                print(f"  Approach: {approach}")
                print(f"  Declared opening: {spec.get('opening', '?')}")
                print(f"  First sentence: {entry['first_sentence']}")
                print(f"  Full text: {text}")
                print()

        all_results[step_key] = {
            "different": different,
            "problems": problems,
            "summary": summary,
            "entries": entries,
        }

    # Write full results to file for analysis
    out_path = Path(".qwen/tmp/task115_openings.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Convert entries to serialisable form
    serialisable = {}
    for step_key, data in all_results.items():
        serialisable[step_key] = {
            "different": data["different"],
            "problems": data["problems"],
            "summary": data["summary"],
            "entries": [
                {
                    "approach": e["approach"],
                    "declared_opening": e["declared_opening"],
                    "first_sentence": e["first_sentence"],
                    "full_text": e["full_text"],
                }
                for e in data["entries"]
            ],
        }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serialisable, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
