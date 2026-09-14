#!/usr/bin/env python3
"""Diagnostic: dump the ACTUAL rendered prompt for two LinkedIn approaches
at li2 (rung 2) and diff them.

Proves whether the ladder brief overpowers the approach descriptions,
causing all variants to collapse to the same structure.

Reads the ogpartner-dk record from the snapshot.
"""
import json
import os
import sys
import difflib
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import generate, variantgen, cadencelibrary


def load_snapshot_record(record_id):
    """Load a record from the snapshot file."""
    snapshot = os.path.join(os.path.dirname(__file__), "..",
                            "work", "queue.snapshot.jsonl")
    with open(snapshot, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("id") == record_id:
                return rec
    return None


def find_contact(rec, contact_name):
    """Find a contact by name."""
    for c in rec.get("contacts", []):
        if contact_name.lower() in (c.get("name") or "").lower():
            return c
    return None


def main():
    rec = load_snapshot_record("ogpartner-dk")
    if not rec:
        print("ERROR: ogpartner-dk not found in snapshot")
        sys.exit(1)

    contact = find_contact(rec, "Jacob Faertz")
    if not contact:
        print("ERROR: Jacob Faertz not found in record")
        sys.exit(1)

    # Get the purpose for li2 (LinkedIn rung 2)
    purpose = generate.purpose_for("linkedin", 2)
    print("=" * 70)
    print("LADDER RUNG 2 PURPOSE (same for ALL variants):")
    print("=" * 70)
    print(purpose)
    print()

    # Build context block
    context_block = generate.context_for(
        "linkedin_note", rec, contact, None, "li2", None)

    # Dump prompts for two approaches
    approaches = ["concise_direct", "conversational"]
    prompts = {}
    for approach in approaches:
        prompt = variantgen.variant_prompt(approach, "linkedin_note",
                                           purpose, context_block)
        prompts[approach] = prompt

    for approach, prompt in prompts.items():
        spec = variantgen.APPROACHES[approach]
        print("=" * 70)
        print(f"APPROACH: {spec['label']} ({approach})")
        print(f"Approach description: {spec['description']}")
        print("=" * 70)
        print(prompt)
        print()

    # Diff the two prompts
    print("=" * 70)
    print("DIFF between concise_direct and conversational prompts:")
    print("=" * 70)
    lines_a = prompts["concise_direct"].splitlines(keepends=True)
    lines_b = prompts["conversational"].splitlines(keepends=True)
    diff = difflib.unified_diff(lines_a, lines_b,
                                fromfile="concise_direct",
                                tofile="conversational",
                                lineterm="")
    diff_text = "".join(diff)
    print(diff_text)
    print()

    # Analysis
    print("=" * 70)
    print("ANALYSIS:")
    print("=" * 70)
    purpose_lower = purpose.lower()
    asks_question = "asks a question" in purpose_lower
    print(f"  Ladder purpose contains 'asks a question': {asks_question}")
    print(f"  concise_direct approach says opening=statement: "
          f"{variantgen.APPROACHES['concise_direct']['opening'] == 'statement'}")
    print(f"  conversational approach says opening=observation: "
          f"{variantgen.APPROACHES['conversational']['opening'] == 'observation'}")
    print()
    if asks_question:
        print("  DEFECT CONFIRMED: The ladder's rung purpose tells the model")
        print("  to 'ask a question', which OVERRIDES the approach's structural")
        print("  instructions. Both approaches get the same form instruction,")
        print("  so both produce questions regardless of their opening type.")
    else:
        print("  Ladder purpose does not contain 'asks a question'.")
        print("  The defect may be elsewhere.")

    # Count lines that differ
    diff_lines = [l for l in diff_text.splitlines()
                  if l.startswith("+") or l.startswith("-")]
    diff_lines = [l for l in diff_lines if not l.startswith("+++")
                  and not l.startswith("---")]
    print(f"\n  Lines that differ between the two prompts: {len(diff_lines)}")
    print("  (Most of the diff should be ONLY the approach section.)")
    print("  If the purpose section is identical, the approach cannot")
    print("  override the form the ladder prescribes.")


if __name__ == "__main__":
    main()
