#!/usr/bin/env python3
"""TASK-089: Diagnose why LinkedIn variants collapse to the same structure.

Dumps the actual rendered prompts for two approaches at li3, diffs them,
then runs real generation and measures diversity.
"""
import json
import sys
from pathlib import Path

# Add src to path
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


def dump_prompts(rec, contact, step_key, sequence):
    """Generate and dump prompts for two approaches at li3."""
    print(f"\n{'='*70}")
    print(f"DIAGNOSING: {step_key} for {rec.get('company')}")
    print(f"{'='*70}\n")
    
    # Get the purpose for this step
    channel = "linkedin"
    _, ordinal, _ = generate.position(sequence, step_key)
    purpose = generate.purpose_for(channel, ordinal, sequence=sequence)
    
    print(f"Step: {step_key} (ordinal {ordinal})")
    print(f"Rung purpose: {purpose}\n")
    
    # Build context block
    context_block = generate.context_for(
        "linkedin_note", rec, contact, None, step_key, sequence)
    
    # Generate prompts for two approaches
    approaches = ["concise_direct", "problem_led"]
    prompts = {}
    
    for approach in approaches:
        prompt = variantgen.variant_prompt(
            approach, "linkedin_note", purpose, context_block)
        prompts[approach] = prompt
        
        # Write to file
        filename = f"work/task089_prompt_{step_key}_{approach}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"Written: {filename}")
    
    print(f"\n{'='*70}")
    print("PROMPT DIFF")
    print(f"{'='*70}\n")
    
    # Show the key sections side by side
    for approach in approaches:
        print(f"\n--- {approach} ---")
        prompt = prompts[approach]
        # Extract the approach description
        lines = prompt.split("\n")
        in_approach = False
        in_job = False
        for line in lines:
            if "## Approach:" in line:
                in_approach = True
                in_job = False
                print(line)
            elif "## This step's job" in line:
                in_approach = False
                in_job = True
                print(line)
            elif in_approach or in_job:
                if line.startswith("## "):
                    in_approach = False
                    in_job = False
                else:
                    print(line)


def run_generation(rec, contact, step_key, sequence, config):
    """Run real generation and measure diversity."""
    print(f"\n{'='*70}")
    print(f"RUNNING GENERATION: {step_key}")
    print(f"{'='*70}\n")
    
    node_type = "linkedin_message"
    
    # Get model from environment
    model = llm.from_env()
    if isinstance(model, llm.NoModel):
        print("ERROR: No model configured in config/.env")
        print("Set LLM_API_KEY, LLM_BASE_URL and LLM_MODEL")
        return None
    print(f"Using model: {model}\n")
    
    result = variantgen.build_variant_set(
        rec, contact, node_type, step_key, sequence=sequence,
        config=config, model=model, llm_ask=llm.ask)
    
    print(f"\nGenerated {len(result['variants'])} variants")
    print(f"Different: {result['different']}")
    
    if result['problems']:
        print("\nProblems:")
        for p in result['problems']:
            print(f"  - {p['a']} vs {p['b']}: {p['why']}")
    
    print("\nStructural summary:")
    for s in result['structural_summary']:
        print(f"  {s['variant_id']:30s}  opening={s['opening']:10s}  "
              f"cta={s['cta']:10s}  words={s['words']:3d}  "
              f"approach={s['approach']}")
    
    # Write full variants to file
    filename = f"work/task089_variants_{step_key}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({
            "variants": result['variants'],
            "structural_summary": result['structural_summary'],
            "different": result['different'],
            "problems": result['problems'],
        }, f, indent=2)
    print(f"\nWritten: {filename}")
    
    return result


def main():
    print("TASK-089: LinkedIn variant diagnosis\n")
    
    # Load a test record first to get the client name
    rec = load_test_record()
    if not rec:
        print("ERROR: No suitable record found in snapshot")
        sys.exit(1)
    
    print(f"Using record: {rec.get('company')} ({rec.get('id')})")
    
    # Load config for this client
    client_name = rec.get("client", "productive")
    config = clients.load(client_name)
    
    contact = rec["contacts"][0]
    print(f"Contact: {contact.get('name')} ({contact.get('title')})")
    
    # Get the LinkedIn sequence - hardcode for now since the record's cadence
    # field is the generated copy, not the sequence name
    seq_name = "productive_li_heavy_v1"
    sequence = cadencelibrary.named(seq_name)
    if not sequence:
        print(f"ERROR: Sequence {seq_name} not found")
        sys.exit(1)
    
    print(f"Sequence: {seq_name}")
    
    # Find LinkedIn message steps
    li_steps = []
    for step in sequence:
        if step.get("channel") == "linkedin_message" or step.get("linkedin_action") == "message":
            li_steps.append(step.get("key"))
    
    print(f"LinkedIn message steps: {li_steps}\n")
    
    # Diagnose the first three LinkedIn steps
    for step_key in li_steps[:3]:
        dump_prompts(rec, contact, step_key, sequence)
        run_generation(rec, contact, step_key, sequence, config)
    
    print(f"\n{'='*70}")
    print("DIAGNOSIS COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
