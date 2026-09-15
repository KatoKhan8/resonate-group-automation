#!/usr/bin/env python3
"""TASK-149: Measure every OpenRouter call site's token cost.

Builds real prompts from real snapshot records and counts tokens with
tiktoken (cl100k_base, the GPT-4/OpenRouter default encoding).

Outputs:
  1. Per-call-site token breakdown (static vs dynamic parts)
  2. Prompt anatomy for one representative 4000-token prompt
  3. Per-company duplication: how many times company evidence travels
     on a multi-contact account
"""
import json
import os
import sys
import hashlib

# Ensure the project root is on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import tiktoken

# Import project modules at top level
from src import generate, clients, lint, cadence, variantgen, research as research_mod

ENC = tiktoken.get_encoding("cl100k_base")


def count_tokens(text):
    return len(ENC.encode(str(text)))


def load_snapshot():
    records = []
    path = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def hash_id(rec):
    """Anonymise a record id for reporting."""
    domain = rec.get("domain", "?")
    return hashlib.sha256(domain.encode()).hexdigest()[:12]


def main():
    records = load_snapshot()
    print(f"Loaded {len(records)} records from snapshot")
    print(f"Snapshot stamp: ", end="")
    try:
        with open(os.path.join(ROOT, "work", "queue.snapshot.STAMP"), encoding="utf-8") as f:
            print(f.read().strip())
    except FileNotFoundError:
        print("(no stamp file)")

    # ------------------------------------------------------------------
    # 1. Find a representative record for prompt anatomy
    # ------------------------------------------------------------------
    # Pick a record with research, company_facts, and at least one contact
    candidates = []
    for rec in records:
        facts = rec.get("company_facts") or {}
        contacts = rec.get("contacts") or []
        research = rec.get("research") or []
        if (facts.get("name") and contacts and research
                and rec.get("lane") in ("cold", "domains", "revive")):
            candidates.append(rec)

    # Sort by richness (most research + facts)
    candidates.sort(key=lambda r: len(r.get("research", []))
                    + len(r.get("company_facts", {})), reverse=True)

    if not candidates:
        print("ERROR: no suitable candidate record found")
        return

    # Pick a cold-lane record for draft anatomy (most common path)
    cold_cands = [r for r in candidates if r.get("lane") == "cold"]
    anatomy_rec = cold_cands[0] if cold_cands else candidates[0]
    anatomy_contact = (anatomy_rec.get("contacts") or [{}])[0]

    print(f"\n{'='*72}")
    print(f"ANATOMY RECORD: domain={anatomy_rec.get('domain')} "
          f"lane={anatomy_rec.get('lane')} "
          f"contacts={len(anatomy_rec.get('contacts', []))} "
          f"research_rows={len(anatomy_rec.get('research', []))}")
    print(f"{'='*72}")

    # Load client config
    client_name = anatomy_rec.get("client")
    try:
        client = clients.load(client_name) if client_name else None
    except Exception:
        client = None

    # ------------------------------------------------------------------
    # 2. Build and measure each prompt type
    # ------------------------------------------------------------------
    prompt_types = {
        "diagnose": {"rec": anatomy_rec, "contact": None, "client": client},
        "hook": {"rec": anatomy_rec, "contact": None, "client": client},
        "persona_angle": {"rec": anatomy_rec, "contact": anatomy_contact,
                          "client": client},
    }

    # For draft and linkedin_note, we need a step_key and sequence
    seq = generate.sequence_for(anatomy_rec, client, anatomy_contact)
    step_keys = [s.get("key") for s in (seq or [])]

    email_steps = [s for s in (seq or []) if s.get("channel") == "email"]
    li_steps = [s for s in (seq or []) if s.get("channel") == "linkedin"]

    results = {}

    # --- diagnose ---
    prompt = generate.render_prompt("diagnose", anatomy_rec)
    results["diagnose"] = measure_prompt("diagnose", prompt, anatomy_rec,
                                         generate.context_for("diagnose", anatomy_rec))

    # --- hook ---
    prompt = generate.render_prompt("hook", anatomy_rec)
    results["hook"] = measure_prompt("hook", prompt, anatomy_rec,
                                     generate.context_for("hook", anatomy_rec))

    # --- persona_angle ---
    prompt = generate.render_prompt("persona_angle", anatomy_rec,
                                    anatomy_contact, client)
    results["persona_angle"] = measure_prompt(
        "persona_angle", prompt, anatomy_rec,
        generate.context_for("persona_angle", anatomy_rec, anatomy_contact, client))

    # --- draft (first email step) ---
    if email_steps:
        sk = email_steps[0]["key"]
        prompt = generate.render_prompt("draft", anatomy_rec, anatomy_contact,
                                        client, sk, seq)
        ctx = generate.context_for("draft", anatomy_rec, anatomy_contact,
                                   client, sk, seq)
        results["draft"] = measure_prompt("draft", prompt, anatomy_rec, ctx,
                                          step_key=sk)
    else:
        # Fallback: use day1
        prompt = generate.render_prompt("draft", anatomy_rec, anatomy_contact,
                                        client, "day1")
        ctx = generate.context_for("draft", anatomy_rec, anatomy_contact,
                                   client, "day1")
        results["draft"] = measure_prompt("draft", prompt, anatomy_rec, ctx,
                                          step_key="day1")

    # --- linkedin_note (first LI step) ---
    if li_steps:
        sk = li_steps[0]["key"]
        prompt = generate.render_prompt("linkedin_note", anatomy_rec,
                                        anatomy_contact, client, sk, seq)
        ctx = generate.context_for("linkedin_note", anatomy_rec, anatomy_contact,
                                   client, sk, seq)
        results["linkedin_note"] = measure_prompt("linkedin_note", prompt,
                                                  anatomy_rec, ctx, step_key=sk)
    else:
        prompt = generate.render_prompt("linkedin_note", anatomy_rec,
                                        anatomy_contact, client, "day3")
        ctx = generate.context_for("linkedin_note", anatomy_rec, anatomy_contact,
                                   client, "day3")
        results["linkedin_note"] = measure_prompt("linkedin_note", prompt,
                                                  anatomy_rec, ctx,
                                                  step_key="day3")

    # ------------------------------------------------------------------
    # 3. Print the call-site inventory
    # ------------------------------------------------------------------
    print(f"\n{'='*72}")
    print("CALL-SITE TOKEN INVENTORY")
    print(f"{'='*72}")
    print(f"{'Step':<18} {'Template':>10} {'Fence':>8} {'Context':>10} "
          f"{'Total':>8} {'Calls/rec':>10}")
    print("-" * 72)
    for step, info in results.items():
        print(f"{step:<18} {info['template']:>10} {info['fence']:>8} "
              f"{info['context']:>10} {info['total']:>8} "
              f"{info['calls_per_record']:>10}")

    # ------------------------------------------------------------------
    # 4. Prompt anatomy for the draft (the biggest one)
    # ------------------------------------------------------------------
    print(f"\n{'='*72}")
    print("PROMPT ANATOMY: draft step")
    print(f"{'='*72}")
    anatomy = results["draft"]
    for part, tokens in anatomy["parts"].items():
        pct = (tokens / anatomy["total"] * 100) if anatomy["total"] else 0
        print(f"  {part:<30} {tokens:>6} tokens  ({pct:.1f}%)")
    print(f"  {'TOTAL':<30} {anatomy['total']:>6} tokens")

    # Also show linkedin_note anatomy
    print(f"\n{'='*72}")
    print("PROMPT ANATOMY: linkedin_note step")
    print(f"{'='*72}")
    anatomy = results["linkedin_note"]
    for part, tokens in anatomy["parts"].items():
        pct = (tokens / anatomy["total"] * 100) if anatomy["total"] else 0
        print(f"  {part:<30} {tokens:>6} tokens  ({pct:.1f}%)")
    print(f"  {'TOTAL':<30} {anatomy['total']:>6} tokens")

    # ------------------------------------------------------------------
    # 5. Company evidence duplication across contacts
    # ------------------------------------------------------------------
    print(f"\n{'='*72}")
    print("COMPANY EVIDENCE DUPLICATION (multi-contact accounts)")
    print(f"{'='*72}")

    # Find the best multi-contact record
    multi_contact_recs = [r for r in records
                          if len(r.get("contacts", [])) >= 3]
    multi_contact_recs.sort(key=lambda r: -len(r.get("contacts", [])))

    for rec in multi_contact_recs[:5]:
        domain = rec.get("domain", "?")
        hid = hash_id(rec)
        contacts = rec.get("contacts") or []
        n = len(contacts)

        # Measure company-level context that is duplicated per contact
        company_facts_tokens = count_tokens(
            json.dumps(generate.facts_block(rec), indent=2))
        research_tokens = count_tokens(
            json.dumps(generate.research_block(rec), indent=2))
        public_ev = generate.research.for_prompt(rec)
        public_tokens = count_tokens(json.dumps(public_ev, indent=2)) \
            if public_ev else 0

        # Measure per-contact context
        per_contact_sizes = []
        for c in contacts[:5]:  # first 5 contacts
            ctx = generate.context_for("draft", rec, c, client, "em1")
            contact_json = json.dumps(ctx, indent=2, ensure_ascii=False)
            per_contact_sizes.append(count_tokens(contact_json))

        company_total = company_facts_tokens + research_tokens + public_tokens
        avg_per_contact = (sum(per_contact_sizes) / len(per_contact_sizes)
                           if per_contact_sizes else 0)

        print(f"\n  Record {hid} ({domain}): {n} contacts")
        print(f"    Company-level evidence (shared): {company_total} tokens")
        print(f"      facts_block:     {company_facts_tokens} tokens")
        print(f"      research_block:  {research_tokens} tokens")
        print(f"      public_evidence: {public_tokens} tokens")
        print(f"    Avg full context per contact: {avg_per_contact:.0f} tokens")
        print(f"    Company evidence sent {n}x = "
              f"{company_total * n} tokens total for shared data")
        print(f"    If deduplicated: {company_total} + "
              f"{n} x ~(avg contact-only) tokens")

        # Measure what portion of the per-contact context is contact-specific
        # vs company-level
        if contacts:
            c0 = contacts[0]
            ctx0 = generate.context_for("draft", rec, c0, client, "em1")
            contact_block_tokens = count_tokens(
                json.dumps(generate.contact_block(c0), indent=2))
            print(f"    Contact-specific block (name/title/persona): "
                  f"{contact_block_tokens} tokens")
            print(f"    Company evidence as % of full prompt: "
                  f"{company_total/avg_per_contact*100:.1f}%"
                  if avg_per_contact > 0 else "")

    # ------------------------------------------------------------------
    # 6. Variant generation cost
    # ------------------------------------------------------------------
    print(f"\n{'='*72}")
    print("VARIANT GENERATION: per-step cost")
    print(f"{'='*72}")
    # The variant prompt is larger than the base draft prompt because it
    # adds the approach description
    if email_steps:
        sk = email_steps[0]["key"]
        channel, ordinal, total = generate.position(seq, sk)
        purpose = generate.purpose_for("email", ordinal, sequence=seq)
        ctx = generate.context_for("draft", anatomy_rec, anatomy_contact,
                                   client, sk, seq)
        for approach in ("concise_direct", "conversational", "problem_led",
                         "observation_led", "value_led"):
            vp = variantgen.variant_prompt(approach, "draft", purpose, ctx)
            t = count_tokens(vp)
            print(f"  variant/{approach:<20} {t:>6} tokens")

    # ------------------------------------------------------------------
    # 7. Calls per record estimate
    # ------------------------------------------------------------------
    print(f"\n{'='*72}")
    print("CALLS PER RECORD (expected, best case)")
    print(f"{'='*72}")
    # Count how many model calls a full generate_record makes
    # diagnose: 1 (revive lane only)
    # hook: 1 (cold lane only)
    # persona_angle: 1 per contact
    # draft: 1 per contact per email step (up to MAX_DRAFT_ATTEMPTS retries)
    # linkedin_note: 1 per contact per LI step
    # variant_set: up to 5 per step

    for rec in candidates[:3]:
        hid = hash_id(rec)
        lane = rec.get("lane")
        contacts = rec.get("contacts") or []
        nc = len(contacts)
        seq_r = generate.sequence_for(rec, client, contacts[0] if contacts else None)
        email_steps_r = [s for s in (seq_r or []) if s.get("channel") == "email"]
        li_steps_r = [s for s in (seq_r or []) if s.get("channel") == "linkedin"]
        ne = len(email_steps_r)
        nl = len(li_steps_r)

        calls = 0
        detail = []
        if lane == "revive":
            calls += 1
            detail.append("diagnose=1")
        if lane == "cold":
            calls += 1
            detail.append("hook=1")
        # persona_angle: 1 per contact
        calls += nc
        detail.append(f"persona_angle={nc}")
        # draft: 1 per contact per email step
        calls += nc * ne
        detail.append(f"draft={nc}x{ne}={nc*ne}")
        # linkedin_note: 1 per contact per LI step
        calls += nc * nl
        detail.append(f"linkedin_note={nc}x{nl}={nc*nl}")

        print(f"  Record {hid} lane={lane} contacts={nc} "
              f"email_steps={ne} li_steps={nl}")
        print(f"    Base calls: {calls} ({', '.join(detail)})")
        print(f"    With retries (up to {generate.MAX_DRAFT_ATTEMPTS}x): "
              f"up to {calls * generate.MAX_DRAFT_ATTEMPTS}")


def measure_prompt(step, full_prompt, rec, context, step_key=None):
    """Break a prompt into parts and count tokens for each."""
    template = generate.prompt_text(step)
    template_tokens = count_tokens(template)

    # The context is JSON-dumped and fenced
    context_json = json.dumps(context, indent=2, ensure_ascii=False)
    context_tokens = count_tokens(context_json)

    # The fence (UNTRUSTED_PREAMBLE + markers)
    fence_text = generate.llm.fence(context_json)
    # fence_text = UNTRUSTED_PREAMBLE + BEGIN + context_json + END
    fence_overhead = count_tokens(fence_text) - context_tokens

    total = count_tokens(full_prompt)

    # Break the context into parts
    parts = {}
    parts["template (static rules)"] = template_tokens
    parts["fence overhead (untrusted preamble)"] = fence_overhead

    # Context sub-parts
    if isinstance(context, dict):
        for key, value in context.items():
            part_json = json.dumps({key: value}, indent=2, ensure_ascii=False)
            parts[f"  ctx.{key}"] = count_tokens(part_json) - 2  # minus {} overhead approx

    # Estimate calls per record
    calls_map = {
        "diagnose": 1,
        "hook": 1,
        "persona_angle": len(rec.get("contacts") or []),
        "draft": len(rec.get("contacts") or []) * max(1, len([
            s for s in (generate.sequence_for(rec) or [])
            if s.get("channel") == "email"
        ])),
        "linkedin_note": len(rec.get("contacts") or []) * max(1, len([
            s for s in (generate.sequence_for(rec) or [])
            if s.get("channel") == "linkedin"
        ])),
    }

    return {
        "template": template_tokens,
        "fence": fence_overhead,
        "context": context_tokens,
        "total": total,
        "parts": parts,
        "calls_per_record": calls_map.get(step, "?"),
    }


if __name__ == "__main__":
    main()
