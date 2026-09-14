#!/usr/bin/env python3
"""TASK-077: Run variantgen against the real model and read what comes out.

Generates five variants for at least three different steps across at least
three records (LinkedIn + email), gates them, and prints the table the task
asks for.

READS ONLY at every provider. No campaign write, no queue write.
"""
import json
import os
import sys
import tempfile

# Ensure the project root is on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Use a temp dir for store so we never touch work/queue.jsonl
os.environ["RESONATE_DATA"] = tempfile.mkdtemp(prefix="task077-")

from src import clients, llm, variantgen, variants, lint, generate, cadence


def make_record(company, domain, contacts, client="productive",
                lane="cold", research=None):
    """A record realistic enough for variant generation."""
    return {
        "id": f"{domain.replace('.', '-')}",
        "company": company,
        "domain": domain,
        "client": client,
        "lane": lane,
        "state": "verified",
        "company_facts": {
            "name": company,
            "employees": 35,
            "industry": "Marketing",
            "email_domain": domain,
            "offices": ["London"],
            "specialties": ["branding", "digital marketing"],
        },
        "contacts": contacts,
        "events": [],
        "evidence": {c["key"]: [] for c in contacts},
        "research": research or [],
    }


def make_contact(key, name, email, title, persona, angle,
                 linkedin_url=None):
    """A contact with enough for both email and LinkedIn."""
    c = {
        "key": key,
        "name": name,
        "email": email,
        "title": title,
        "persona": persona,
        "angle": angle,
    }
    if linkedin_url:
        c["linkedin"] = linkedin_url
    # For email sendability we need verification evidence
    if email:
        c["verification"] = {
            "state": "verified",
            "evidence": [{"source": "reoon", "result": "deliverable"}],
        }
    return c


def print_variant_table(step_label, result):
    """Print the table the task asks for."""
    print(f"\n{'='*78}")
    print(f"  STEP: {step_label}")
    print(f"{'='*78}")

    generated = result.get("generated") or []
    skipped = result.get("skipped") or []
    different = result.get("different")
    problems = result.get("problems") or []
    structural = result.get("structural_summary") or []

    print(f"\n  Different: {different}")
    if problems:
        print(f"  Problems:")
        for p in problems:
            print(f"    - {p.get('a')} vs {p.get('b')}: {p.get('why')}")

    print(f"\n  {'Var':<4} {'Approach':<20} {'Style':<18} "
          f"{'Opening (first 80 chars)':<82} {'Genuinely different?'}")
    print(f"  {'-'*3} {'-'*19} {'-'*17} {'-'*81} {'-'*20}")

    for i, g in enumerate(generated, 1):
        approach = g.get("approach", "?")
        style = g.get("style", "?")
        v = g.get("variant") or {}
        text = v.get("body") or v.get("note") or v.get("subject") or ""
        opening = text.split("\n")[0][:80] if text else "(no text)"

        # Determine if genuinely different from structural summary
        genuinely = "?"
        if structural:
            match = [s for s in structural
                     if s.get("variant_id") == v.get("variant_id")]
            if match:
                s = match[0]
                genuinely = (f"opening={s.get('opening')}, "
                             f"cta={s.get('cta')}, "
                             f"words={s.get('words')}")

        print(f"  {i:<4} {approach:<20} {style:<18} "
              f"{opening:<82} {genuinely}")

    if skipped:
        print(f"\n  Skipped approaches:")
        for s in skipped:
            print(f"    - {s.get('approach')}: {s.get('why')}")

    return generated, skipped, different, problems


def main():
    print("TASK-077: Running variantgen against the real model")
    print("=" * 78)

    # Load the model
    model = llm.from_env()
    if isinstance(model, llm.NoModel):
        print("ERROR: no model configured. Cannot proceed.")
        return 1
    print(f"Model: {model.name}, model_id={model.model}")
    print(f"Base: {model.base}")

    # Load the client config
    client = clients.load("productive")
    print(f"Client: {client.get('name')}")

    # Get the sequence
    sequence = cadence.steps_for(None, client, None, None)
    print(f"Sequence: {len(sequence)} steps")
    email_steps = [s for s in sequence if s.get("channel") == "email"
                   and s.get("generated")]
    li_steps = [s for s in sequence if s.get("channel") == "linkedin"
                and s.get("generated")]
    print(f"  Email steps (generated): {[s['key'] for s in email_steps]}")
    print(f"  LinkedIn steps (generated): {[s['key'] for s in li_steps]}")

    # Check the LinkedIn style mapping - the known limitation
    print(f"\n--- LinkedIn style mapping (APPROACH_TO_STYLE) ---")
    li_map = variantgen.APPROACH_TO_STYLE.get("linkedin_message", {})
    for approach, style in li_map.items():
        print(f"  {approach:<20} -> {style}")

    # Check for shared buckets
    styles_used = list(li_map.values())
    seen = {}
    shared = []
    for approach, style in li_map.items():
        if style in seen:
            shared.append((approach, seen[style], style))
        seen[style] = approach
    if shared:
        print(f"\n  *** SHARED BUCKETS DETECTED ***")
        for a, b, s in shared:
            print(f"    {a} and {b} both map to '{s}'")
    else:
        print(f"\n  No shared buckets - all five LinkedIn approaches map to "
              f"distinct styles")

    # --- Build three records ---
    records = [
        # Record 1: email step, founder persona
        {
            "rec": make_record(
                "Brightwave Digital", "brightwave.test",
                [make_contact("bw:sarah", "Sarah Mitchell",
                              "sarah@brightwave.test", "Founder & CEO",
                              "founder", "founder",
                              "https://linkedin.com/in/sarahbw")],
            ),
            "step_key": email_steps[0]["key"] if email_steps else "em1",
            "label": "Email step 1 (Brightwave, founder)",
        },
        # Record 2: LinkedIn step, operations persona
        {
            "rec": make_record(
                "Cascade Studio", "cascade.test",
                [make_contact("cs:james", "James Porter",
                              "james@cascade.test", "Head of Operations",
                              "champion", "operations",
                              "https://linkedin.com/in/jamescascade")],
            ),
            "step_key": li_steps[0]["key"] if li_steps else "li1",
            "label": "LinkedIn step 1 (Cascade, ops lead)",
        },
        # Record 3: email step 2, finance persona
        {
            "rec": make_record(
                "Northstar Agency", "northstar.test",
                [make_contact("na:emma", "Emma Clarke",
                              "emma@northstar.test", "Finance Director",
                              "champion", "finance",
                              "https://linkedin.com/in/emmanorth")],
            ),
            "step_key": email_steps[1]["key"] if len(email_steps) > 1
                        else email_steps[0]["key"],
            "label": "Email step 2 (Northstar, finance)",
        },
        # Record 4: LinkedIn message step (not connection request)
        {
            "rec": make_record(
                "Pixel & Grain", "pixelgrain.test",
                [make_contact("pg:tom", "Tom Andersen",
                              "tom@pixelgrain.test", "Project Director",
                              "champion", "delivery",
                              "https://linkedin.com/in/tompixel")],
            ),
            "step_key": li_steps[1]["key"] if len(li_steps) > 1
                        else li_steps[0]["key"],
            "label": "LinkedIn step 2 (Pixel&Grain, delivery lead)",
        },
    ]

    all_results = []

    for case in records:
        rec = case["rec"]
        contact = rec["contacts"][0]
        step_key = case["step_key"]
        label = case["label"]

        # Determine node_type from the sequence
        node_type = "email"
        for spec in sequence:
            if spec.get("key") == step_key:
                node_type = spec.get("channel", "email")
                break
        # LinkedIn channels all use the same variant approaches
        if node_type == "linkedin":
            node_type = "linkedin_message"

        print(f"\n\n{'#'*78}")
        print(f"# {label}")
        print(f"# node_type={node_type}, step_key={step_key}")
        print(f"{'#'*78}")

        try:
            result = variantgen.build_variant_set(
                rec, contact, node_type, step_key,
                sequence=sequence, config=client,
                llm_ask=llm.ask, model=model)
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            all_results.append({
                "label": label, "error": str(e),
                "generated": [], "skipped": [],
                "different": None, "problems": [],
            })
            continue

        generated, skipped, different, problems = print_variant_table(
            label, result)

        all_results.append({
            "label": label,
            "node_type": node_type,
            "step_key": step_key,
            "generated": generated,
            "skipped": skipped,
            "different": different,
            "problems": problems,
            "structural_summary": result.get("structural_summary", []),
        })

    # --- Summary ---
    print(f"\n\n{'='*78}")
    print("SUMMARY")
    print(f"{'='*78}")

    for r in all_results:
        if r.get("error"):
            print(f"\n  {r['label']}: ERROR - {r['error']}")
            continue
        n_gen = len(r.get("generated") or [])
        n_skip = len(r.get("skipped") or [])
        diff = r.get("different")
        print(f"\n  {r['label']}")
        print(f"    Generated: {n_gen}, Skipped: {n_skip}, "
              f"Materially different: {diff}")
        if r.get("problems"):
            for p in r["problems"]:
                print(f"    COLLISION: {p.get('a')} vs {p.get('b')}: "
                      f"{p.get('why')}")

    # Model call stats
    if hasattr(model, "calls"):
        print(f"\n  Model calls: {len(model.calls)}")
        total_tokens = sum(c.get("total_tokens", 0) for c in model.calls)
        total_cost = sum(c.get("cost", 0) for c in model.calls)
        print(f"  Total tokens: {total_tokens}")
        if total_cost:
            print(f"  Total cost: ${total_cost:.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
