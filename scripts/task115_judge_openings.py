#!/usr/bin/env python3
"""TASK-115: Hand-judge whether declared openings are honoured in generated text.

For each LinkedIn step (li2, li3, li4), generate five variants and output:
1. The approach key and its declared opening type
2. The full generated text
3. The first sentence extracted (what _opening_shape would see)
4. A hand-judgement column for the investigator to fill in

Reads only. No writes, sends, or campaign changes.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import store, variantgen, generate, cadencelibrary, llm, clients


def load_test_record():
    """Load a verified record with contacts from the snapshot."""
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


def first_sentence(text):
    """Extract the first sentence - mirrors _opening_shape logic."""
    full = (text or "").strip()
    if not full:
        return ""
    match = re.search(r'[.?!]\s', full)
    if match:
        return full[:match.end()].strip()
    return full


def main():
    print("TASK-115: Hand-judge declared openings vs actual text\n")

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

    model = llm.from_env()
    if isinstance(model, llm.NoModel):
        print("ERROR: No model configured")
        sys.exit(1)
    print(f"Model: {model}\n")

    li_steps = []
    for step in sequence:
        ch = step.get("channel", "")
        action = step.get("linkedin_action", "")
        if ch == "linkedin_message" or action == "message":
            li_steps.append(step.get("key"))

    print(f"LinkedIn message steps: {li_steps}\n")

    node_type = "linkedin_message"

    for step_key in li_steps:
        print(f"\n{'#'*78}")
        print(f"# STEP: {step_key}")
        print(f"{'#'*78}\n")

        result = variantgen.build_variant_set(
            rec, contact, node_type, step_key, sequence=sequence,
            config=config, model=model, llm_ask=llm.ask)

        print(f"Generated: {len(result['variants'])} variants")
        print(f"Different: {result['different']}")
        if result['problems']:
            print(f"Problems:")
            for p in result['problems']:
                print(f"  {p['a']} vs {p['b']}: {p['why']}")
        print()

        for g in result.get('generated', []):
            approach = g.get('approach', '?')
            variant = g.get('variant')
            declared = variantgen.APPROACHES.get(approach, {}).get('opening', '?')

            if variant is None:
                print(f"  [{approach}] SKIPPED (failed gates)")
                print(f"    declared opening: {declared}")
                print()
                continue

            body = variant.get("note") or variant.get("body") or ""
            first_sent = first_sentence(body)
            detected = variantgen._opening_shape(body)

            print(f"  [{approach}] declared_opening={declared}  "
                  f"detected_opening={detected}")
            print(f"    First sentence: {first_sent}")
            print(f"    Full text: {body}")
            print()

        print(f"\n{'='*78}\n")


if __name__ == "__main__":
    main()
