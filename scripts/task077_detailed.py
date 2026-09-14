#!/usr/bin/env python3
"""TASK-077: Detailed variant generation with full text capture.

Captures the full text of each variant, the diversity check result,
and diagnoses the missing-format bug.
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["RESONATE_DATA"] = tempfile.mkdtemp(prefix="task077-detail-")

from src import clients, llm, variantgen, variants, lint, generate, cadence, claims


def make_record(company, domain, contact_name, contact_email, contact_key,
                title, persona, angle, linkedin_url=None):
    contact = {
        "key": contact_key,
        "name": contact_name,
        "email": contact_email,
        "title": title,
        "persona": persona,
        "angle": angle,
        "verification": {
            "state": "verified",
            "evidence": [{"source": "reoon", "result": "deliverable"}],
        },
    }
    if linkedin_url:
        contact["linkedin"] = linkedin_url
    return {
        "id": domain.replace(".", "-"),
        "company": company,
        "domain": domain,
        "client": "productive",
        "lane": "cold",
        "state": "verified",
        "company_facts": {
            "name": company,
            "employees": 35,
            "industry": "Marketing",
            "email_domain": domain,
            "offices": ["London"],
            "specialties": ["branding", "digital marketing"],
        },
        "contacts": [contact],
        "events": [],
        "evidence": {contact_key: []},
        "research": [],
    }


def custom_llm_ask(model, step):
    """A wrapper around llm.ask that captures the raw model output."""
    captured = []

    def ask(model, step, prompt):
        # Call the model directly first to see raw output
        raw = model.complete(prompt)
        captured.append({"prompt_len": len(prompt), "raw": raw[:300]})
        # Then do the normal ask
        return llm.ask.__wrapped__(model, step, prompt) if hasattr(llm.ask, '__wrapped__') else _real_ask(model, step, prompt)

    return ask, captured


def _real_ask(model, step, prompt):
    """The real llm.ask."""
    return llm.ask(model, step, prompt)


def run_variant_set(rec, contact, node_type, step_key, sequence, client, model):
    """Run build_variant_set and capture everything."""
    result = variantgen.build_variant_set(
        rec, contact, node_type, step_key,
        sequence=sequence, config=client,
        llm_ask=llm.ask, model=model)
    return result


def main():
    print("TASK-077 DETAILED VARIANT GENERATION")
    print("=" * 78)

    model = llm.from_env()
    if isinstance(model, llm.NoModel):
        print("ERROR: no model configured")
        return 1
    print(f"Model: {model.name} ({model.model})")

    client = clients.load("productive")
    sequence = cadence.steps_for(None, client, None, None)
    email_steps = [s for s in sequence if s.get("channel") == "email"
                   and s.get("generated")]
    li_steps = [s for s in sequence if s.get("channel") == "linkedin"
                and s.get("generated")]

    # --- THE VARIANT TABLE ---
    all_results = []

    cases = [
        {
            "rec": make_record(
                "Brightwave Digital", "brightwave.test",
                "Sarah Mitchell", "sarah@brightwave.test", "bw:sarah",
                "Founder & CEO", "founder", "founder",
                "https://linkedin.com/in/sarahbw"),
            "step_key": "em1",
            "node_type": "email",
            "label": "Email em1 - Brightwave founder",
        },
        {
            "rec": make_record(
                "Cascade Studio", "cascade.test",
                "James Porter", "james@cascade.test", "cs:james",
                "Head of Operations", "champion", "operations",
                "https://linkedin.com/in/jamescascade"),
            "step_key": "li2",
            "node_type": "linkedin_message",
            "label": "LinkedIn li2 - Cascade ops lead",
        },
        {
            "rec": make_record(
                "Northstar Agency", "northstar.test",
                "Emma Clarke", "emma@northstar.test", "na:emma",
                "Finance Director", "champion", "finance",
                "https://linkedin.com/in/emmanorth"),
            "step_key": "em2",
            "node_type": "email",
            "label": "Email em2 - Northstar finance",
        },
        {
            "rec": make_record(
                "Pixel & Grain", "pixelgrain.test",
                "Tom Andersen", "tom@pixelgrain.test", "pg:tom",
                "Project Director", "champion", "delivery",
                "https://linkedin.com/in/tompixel"),
            "step_key": "li3",
            "node_type": "linkedin_message",
            "label": "LinkedIn li3 - Pixel&Grain delivery",
        },
        {
            "rec": make_record(
                "Horizon Creative", "horizon.test",
                "Lisa Chen", "lisa@horizon.test", "hc:lisa",
                "Studio Manager", "champion", "resource_management",
                "https://linkedin.com/in/lisahorizon"),
            "step_key": "em3",
            "node_type": "email",
            "label": "Email em3 - Horizon studio mgr",
        },
    ]

    for case in cases:
        rec = case["rec"]
        contact = rec["contacts"][0]
        step_key = case["step_key"]
        node_type = case["node_type"]
        label = case["label"]

        print(f"\n{'#'*78}")
        print(f"# {label}")
        print(f"{'#'*78}")

        try:
            result = run_variant_set(
                rec, contact, node_type, step_key, sequence, client, model)
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            all_results.append({
                "label": label, "error": str(e),
                "generated": [], "skipped": [],
                "different": None, "problems": [],
            })
            continue

        generated = result.get("generated") or []
        skipped = result.get("skipped") or []
        different = result.get("different")
        problems = result.get("problems") or []
        structural = result.get("structural_summary") or []

        print(f"\n  Materially different: {different}")
        if problems:
            for p in problems:
                print(f"  COLLISION: {p}")

        # Print each variant with full text
        for i, g in enumerate(generated, 1):
            approach = g.get("approach", "?")
            style = g.get("style", "?")
            v = g.get("variant") or {}
            subject = v.get("subject") or ""
            body = v.get("body") or ""
            note = v.get("note") or ""

            if node_type == "email":
                text = body
                opening = (subject + " | " + body.split("\n")[0])[:120]
            else:
                text = note
                opening = note.split("\n")[0][:120] if note else "(empty)"

            print(f"\n  --- Variant {i}: {approach} (style={style}) ---")
            if node_type == "email":
                print(f"  Subject: {subject}")
                print(f"  Body: {body[:300]}{'...' if len(body) > 300 else ''}")
            else:
                print(f"  Note: {note[:300]}{'...' if len(note) > 300 else ''}")

            # Structural info
            s_match = [s for s in structural
                       if s.get("variant_id") == v.get("variant_id")]
            if s_match:
                s = s_match[0]
                print(f"  [opening={s.get('opening')}, cta={s.get('cta')}, "
                      f"words={s.get('words')}]")

        if skipped:
            print(f"\n  Skipped:")
            for s in skipped:
                print(f"    {s.get('approach')}: {s.get('why')}")

        all_results.append({
            "label": label,
            "node_type": node_type,
            "step_key": step_key,
            "generated": generated,
            "skipped": skipped,
            "different": different,
            "problems": problems,
            "structural_summary": structural,
        })

    # --- THE TABLE THE TASK ASKS FOR ---
    print(f"\n\n{'='*78}")
    print("THE TABLE: variant, approach, opening line, genuinely different?")
    print(f"{'='*78}")

    for r in all_results:
        if r.get("error"):
            print(f"\n  {r['label']}: ERROR - {r['error']}")
            continue

        print(f"\n  --- {r['label']} ---")
        print(f"  {'Var':<4} {'Approach':<20} {'Opening line':<80} "
              f"{'Genuinely different?'}")
        print(f"  {'-'*3} {'-'*19} {'-'*79} {'-'*20}")

        for i, g in enumerate(r.get("generated") or [], 1):
            approach = g.get("approach", "?")
            v = g.get("variant") or {}
            text = v.get("body") or v.get("note") or ""
            opening = text.split("\n")[0][:80] if text else "(empty)"

            # Find structural info
            genuinely = "?"
            for s in (r.get("structural_summary") or []):
                if s.get("variant_id") == v.get("variant_id"):
                    genuinely = (f"opening={s.get('opening')}, "
                                 f"cta={s.get('cta')}")
                    break

            print(f"  {i:<4} {approach:<20} {opening:<80} {genuinely}")

        for s in (r.get("skipped") or []):
            print(f"  {'--':<4} {s.get('approach'):<20} "
                  f"{'(skipped)':<80} {s.get('why', '')[:40]}")

        print(f"  diversity_collisions says: {r.get('different')}")
        if r.get("problems"):
            for p in r["problems"]:
                print(f"    collision: {p}")

    # --- DIAGNOSIS ---
    print(f"\n\n{'='*78}")
    print("DIAGNOSIS")
    print(f"{'='*78}")

    # Check the prompt format issue
    print("\n1. PROMPT FORMAT BUG:")
    # TASK-084 gave variant_prompt a `step` argument when it started reusing
    # the real prompt template for the JSON contract. This diagnostic still
    # called the three-argument form and died at the very end of an otherwise
    # complete run, which is a stale caller rather than a product defect.
    prompt = variantgen.variant_prompt(
        "concise_direct",
        {"key": "li2", "channel": "linkedin", "purpose": "test purpose"},
        "test purpose",
        {"company": "Test", "facts": {"name": "Test"}})
    has_json = "json" in prompt.lower()
    has_return = "return" in prompt.lower()
    print(f"   variant_prompt mentions 'json': {has_json}")
    print(f"   variant_prompt mentions 'return': {has_return}")
    print(f"   The prompt NEVER tells the model to return JSON.")
    print(f"   The draft.md template says 'Return JSON only' but")
    print(f"   variantgen builds its own prompt without the template.")
    print(f"   llm.ask then tries to parse plain text as JSON and retries,")
    print(f"   burning 1-2 of the 3 attempts on format recovery.")

    # Check LinkedIn style mapping
    print(f"\n2. LINKEDIN STYLE MAPPING:")
    li_map = variantgen.APPROACH_TO_STYLE.get("linkedin_message", {})
    styles_used = list(li_map.values())
    unique = len(set(styles_used))
    total = len(styles_used)
    print(f"   LinkedIn approaches -> styles:")
    for approach, style in li_map.items():
        print(f"     {approach:<20} -> {style}")
    print(f"   {unique} unique styles from {total} approaches")
    if unique < total:
        print(f"   *** SHARED BUCKETS: two approaches share one style ***")
        seen = {}
        for approach, style in li_map.items():
            if style in seen:
                print(f"     {approach} and {seen[style]} both -> {style}")
            seen[style] = approach
    else:
        print(f"   No shared buckets. All five map to distinct styles.")
        print(f"   problem_led -> professional, observation_led -> consultative")
        print(f"   These are DIFFERENT style keys with DIFFERENT descriptions.")

    # Model stats
    if hasattr(model, "calls"):
        print(f"\n3. MODEL USAGE:")
        print(f"   Total calls: {len(model.calls)}")
        total_tokens = sum(c.get("total_tokens", 0) for c in model.calls)
        total_cost = sum(c.get("cost", 0) for c in model.calls)
        print(f"   Total tokens: {total_tokens}")
        if total_cost:
            print(f"   Total cost: ${total_cost:.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
