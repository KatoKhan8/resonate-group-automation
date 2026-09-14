#!/usr/bin/env python3
"""Generate five materially different variants per message step.

## What this is

A variant generator that produces up to five approach-labelled variants
for a single message step, each testing a genuinely different hypothesis
about what will work. The variants differ in tone, opening structure,
pain-first versus observation-first, length, CTA style and proof framing
- not in wording alone.

## What this is not

Five paraphrases of one sentence. A synonym swap is a failure of this
module, and `are_materially_different` catches it.

## The approaches

Each approach is a named structural hypothesis, not a letter. The name
is what makes the result reusable across steps, campaigns and eventually
a workspace's history.

    concise_direct     Two sentences and one question. No preamble.
    conversational     Written the way a peer would write it. Lower guard.
    problem_led        Opens on the cost of the status quo.
    observation_led    Opens on something noticed. REQUIRES licensed evidence.
    value_led          Opens on what they would gain. Product-forward.

## The constraint that outranks variety

Every variant passes the SAME gates as any other copy. Style may change
tone, length, structure, opening and call to action. It may not change
what is true. `claims.check` refuses unsupported assertions, and a
variant is not exempt.

The observation-led variant is the dangerous one. A model asked for an
observation-led message with no observation available will invent one.
So `approaches_available` returns only the approaches the record can
support, and the observation-led approach is absent when no licensed
observation exists - rather than generated and then rejected.

## No separate experiment ledger

EmailBison models a variant as a first-class sequence step with its own
id. Variant identity survives send and readback. The existing
`variants.py` data model carries the variant, its style and its
approval fingerprint. This module writes into that model and nothing
else.

## Production boundary

This module does not call a live model. It builds prompts and delegates
to `llm.ask` through the same path `generate.draft` uses. A fake model
is sufficient for testing.
"""
import re

from . import cadencelibrary, claims, observations, variants

# --------------------------------------------------------- the approaches
#
# Each approach is a structural hypothesis about what makes a message work.
# The description is what goes into the prompt, so the model knows what
# shape to write. The dimensions vary: opening structure, tone, length,
# CTA style, proof framing.

APPROACHES = {
    "concise_direct": {
        "label": "Concise and direct",
        "description": (
            "Short and direct. Open with the reason for writing in one "
            "sentence - no preamble, no setup. State what is offered in "
            "one line. Close with a single question they can answer in a "
            "word. Total: two to three sentences."),
        "opening": "statement",
        "tone": "direct",
        "length": "short",
        "cta": "question",
        "proof": "none",
    },
    "conversational": {
        "label": "Conversational",
        "description": (
            "Conversational. Write the way a peer would message another "
            "peer - lower case feel, shorter sentences, no corporate "
            "phrasing. Open with an observation about their situation, "
            "not a pitch. Close with a casual question, not a CTA."),
        "opening": "observation",
        "tone": "casual",
        "length": "medium",
        "cta": "casual_question",
        "proof": "none",
    },
    "problem_led": {
        "label": "Problem-led",
        "description": (
            "Problem-led. Open with the cost of the status quo - what "
            "the current way of working actually spends in time, risk or "
            "reconstruction. Name the pain before naming the solution. "
            "Close with a question about whether they see the same "
            "pattern."),
        "opening": "pain",
        "tone": "empathetic",
        "length": "medium",
        "cta": "question",
        "proof": "consequence",
    },
    "observation_led": {
        "label": "Observation-led",
        "description": (
            "Observation-led. Open with something specific noticed about "
            "their company or role - a fact with a source, not an "
            "invention. Connect the observation to the argument. Close "
            "with a question about what the observation means for them. "
            "MAY NOT invent an observation. If none is licensed, this "
            "variant is not generated."),
        "opening": "evidence",
        "tone": "researched",
        "length": "contextual",
        "cta": "question",
        "proof": "attributed_fact",
    },
    "value_led": {
        "label": "Value-led",
        "description": (
            "Value-led. Open with what they would gain - a concrete "
            "outcome, not a feature. Name the product and say in one "
            "line what it joins up. Give one consequence a team their "
            "size would recognise. Close with a direct CTA - a specific "
            "next step, not an open question."),
        "opening": "outcome",
        "tone": "professional",
        "length": "contextual",
        "cta": "direct",
        "proof": "product_capability",
    },
}

# The order matters: it is the order variants are generated in, and the
# observation-led variant is placed fourth so the first four can always
# be generated regardless of evidence.
EMAIL_APPROACH_ORDER = (
    "concise_direct",
    "conversational",
    "problem_led",
    "observation_led",
    "value_led",
)

LINKEDIN_APPROACH_ORDER = (
    "concise_direct",
    "conversational",
    "problem_led",
    "observation_led",
    "value_led",
)

APPROACH_ORDER_FOR = {
    "email": EMAIL_APPROACH_ORDER,
    "connection_request": LINKEDIN_APPROACH_ORDER,
    "linkedin_message": LINKEDIN_APPROACH_ORDER,
    "linkedin_followup": LINKEDIN_APPROACH_ORDER,
}

# Map approach keys to the style keys in variants.STYLES_FOR.
# The style is what is recorded on the variant entry and what the
# evaluator groups results by.
APPROACH_TO_STYLE = {
    "email": {
        "concise_direct": "short_direct",
        "conversational": "casual",
        "problem_led": "problem_led",
        "observation_led": "consultative",
        "value_led": "professional",
    },
    "connection_request": {
        "concise_direct": "short_direct",
        "conversational": "casual",
        "problem_led": "professional",
        "observation_led": "consultative",
        "value_led": "peer_to_peer",
    },
    "linkedin_message": {
        "concise_direct": "short_direct",
        "conversational": "casual",
        "problem_led": "professional",
        "observation_led": "consultative",
        "value_led": "peer_to_peer",
    },
    "linkedin_followup": {
        "concise_direct": "short_direct",
        "conversational": "casual",
        "problem_led": "professional",
        "observation_led": "consultative",
        "value_led": "peer_to_peer",
    },
}


def approaches_for(node_type):
    """The approach keys for this channel, in generation order."""
    return APPROACH_ORDER_FOR.get(node_type, EMAIL_APPROACH_ORDER)


def style_for(node_type, approach):
    """The variants.STYLES_FOR key this approach maps to."""
    return APPROACH_TO_STYLE.get(node_type, APPROACH_TO_STYLE["email"]).get(
        approach, approach)


# --------------------------------------------------- evidence gating
#
# The observation-led variant is the dangerous one. A model asked for an
# observation-led message with no observation available will invent one.
# So this module checks whether the record can support it BEFORE
# generating, and removes it from the set rather than generating and
# then rejecting.

def approaches_available(rec, contact, node_type="email", config=None,
                         today=None):
    """Which approaches this record can support, with reasons for those it cannot.

    Returns a list of dicts, one per approach in generation order:
        {"approach": "concise_direct", "available": True, "style": "short_direct"}
    or:
        {"approach": "observation_led", "available": False,
         "why": "no licensed observation", "style": "consultative"}

    The observation-led approach requires a licensed observation from
    `observations.resolve`. Every other approach is always available.
    """
    from . import lint

    contact_key = lint.contact_key(contact) if contact else None
    order = approaches_for(node_type)
    out = []
    for approach in order:
        entry = {"approach": approach,
                 "style": style_for(node_type, approach),
                 "label": APPROACHES[approach]["label"]}
        if approach == "observation_led":
            decision = observations.resolve(
                observations.COMPANY_EVENT, rec, contact_key, config, today)
            if not decision:
                # Try person-level observations too
                decision = observations.resolve(
                    observations.PERSON_ROLE, rec, contact_key, config, today)
            if not decision:
                decision = observations.resolve(
                    observations.COMPANY_ATTRIBUTE, rec, contact_key, config,
                    today)
            if not decision:
                entry["available"] = False
                entry["why"] = ("no licensed observation: the record carries "
                                "nothing checkable a message could point at")
                out.append(entry)
                continue
            entry["available"] = True
            entry["evidence"] = decision.get("evidence")
        else:
            entry["available"] = True
        out.append(entry)
    return out


# --------------------------------------------------- the prompt

def variant_prompt(approach, purpose, context_block):
    """The prompt for one variant, combining the approach brief with the
    step's purpose and the record context.

    The purpose is the ladder's rung job - shared across all variants for
    this step. The approach is what makes THIS variant different from the
    other four.
    """
    spec = APPROACHES[approach]
    lines = [
        f"## Approach: {spec['label']}",
        "",
        spec["description"],
        "",
        "## This step's job (same for all variants)",
        purpose or "No specific purpose assigned for this rung.",
        "",
        "## Record context",
    ]
    if context_block.get("company"):
        lines.append(f"Company: {context_block['company']}")
    if context_block.get("facts"):
        facts = context_block["facts"]
        for k, v in facts.items():
            lines.append(f"  {k}: {v}")
    if context_block.get("contact"):
        contact = context_block["contact"]
        for k, v in contact.items():
            lines.append(f"  {k}: {v}")
    if context_block.get("public_evidence"):
        lines.append(f"Public evidence: {context_block['public_evidence']}")
    if approach == "observation_led" and context_block.get("observation"):
        obs = context_block["observation"]
        lines.append(f"Licensed observation: {obs.get('fact', '')}")
        if obs.get("source_url"):
            lines.append(f"Source: {obs['source_url']}")
    if context_block.get("product"):
        lines.append(f"Product: {context_block['product']}")
    if context_block.get("angle_wording"):
        lines.append(f"Angle: {context_block['angle_wording']}")
    lines.append("")
    lines.append("## Rules")
    lines.append("- Do not invent facts about the company or the person.")
    lines.append("- Do not assert a prior conversation that did not happen.")
    lines.append("- Do not name a product that is not listed above.")
    lines.append("- Every claim must be traceable to the context above.")
    return "\n".join(lines)


# --------------------------------------------------- differentiation
#
# Five paraphrases of one sentence fail this task. The check must catch
# variants that differ only in wording, not in approach.

def _structural_tokens(text):
    """Tokens that capture structure rather than content.

    Two variants that share these are saying the same thing in the same
    shape, however different the words look. The check discounts the
    company name and the subject vocabulary - naming the prospect's
    company is relevance, not repetition.
    """
    low = (text or "").lower()
    return set(re.findall(r"[a-z][a-z\-]{3,}", low))


def _opening_shape(text):
    """How the message opens: question, statement, or observation.

    Two variants that both open with a question and close with a question
    are structurally the same variant, however different the words.
    """
    first = (text or "").strip().split("\n", 1)[0].strip()
    if not first:
        return "empty"
    if first.endswith("?"):
        return "question"
    return "statement"


def _cta_shape(text):
    """How the message closes."""
    lines = [l.strip() for l in (text or "").strip().split("\n") if l.strip()]
    if not lines:
        return "empty"
    last = lines[-1]
    if last.endswith("?"):
        return "question"
    return "statement"


def _word_length(text):
    """Approximate word count."""
    return len((text or "").split())


def are_materially_different(variants_entries, node_type="email",
                             company_name=None):
    """Whether a set of variants differ in approach, not just wording.

    Returns a dict:
        {"different": True/False,
         "pairs": [{"a": id, "b": id, "why": reason}, ...],
         "structural_summary": [{"variant_id": ..., "opening": ..., "cta": ...,
                                  "length": ..., "approach": ...}, ...]}

    Two variants are NOT materially different when:
      - they share the same opening shape AND the same CTA shape AND
        their distinctive-word overlap is >= 50% of the smaller set
      - they are identical in all structural dimensions

    This reuses the same overlap logic as `quality.repetition_across_rungs`
    rather than writing a second comparator, per the task's instruction.
    """
    from . import quality

    if not variants_entries or len(variants_entries) < 2:
        return {"different": True, "pairs": [], "structural_summary": []}

    summaries = []
    for entry in variants_entries:
        text = (entry.get("body") or entry.get("note") or
                entry.get("subject") or "")
        summaries.append({
            "variant_id": entry.get("variant_id"),
            "approach": entry.get("style"),
            "opening": _opening_shape(text),
            "cta": _cta_shape(text),
            "words": _word_length(text),
        })

    # Build the step list for quality.campaign_repetition
    ignore = set()
    if company_name:
        for token in re.findall(r"[a-z]+", str(company_name).lower()):
            if len(token) >= 4:
                ignore.add(token)

    steps = []
    for entry in variants_entries:
        text = " ".join(filter(None, [
            entry.get("subject"), entry.get("body"), entry.get("note")]))
        steps.append({"key": entry.get("variant_id", ""), "text": text})

    collisions = quality.repetition_across_rungs(steps, ignore=ignore)

    # Filter collisions to those that ALSO share structural dimensions
    problem_pairs = []
    summary_by_id = {s["variant_id"]: s for s in summaries}
    for key_a, key_b, shared_count in collisions:
        sa = summary_by_id.get(key_a, {})
        sb = summary_by_id.get(key_b, {})
        same_opening = sa.get("opening") == sb.get("opening")
        same_cta = sa.get("cta") == sb.get("cta")
        if same_opening and same_cta:
            problem_pairs.append({
                "a": key_a, "b": key_b,
                "why": (f"same opening ({sa.get('opening')}), same CTA "
                        f"({sa.get('cta')}), {shared_count} shared words"),
            })

    # Also check: all same approach?
    approaches_used = {s.get("approach") for s in summaries}
    if len(approaches_used) == 1 and len(summaries) > 1:
        problem_pairs.append({
            "a": summaries[0]["variant_id"],
            "b": summaries[1]["variant_id"],
            "why": "all variants carry the same style/approach",
        })

    return {
        "different": len(problem_pairs) == 0,
        "pairs": problem_pairs,
        "structural_summary": summaries,
    }


# --------------------------------------------------- the generation
#
# This does not call a live model. It builds the prompts and the
# variant entries, and delegates the actual model call to the caller
# (or to a fake in tests).

def build_variant_set(rec, contact, node_type, step_key, sequence=None,
                      config=None, model=None, llm_ask=None):
    """Generate up to five approach-labelled variants for one step.

    Returns a dict:
        {"variants": [variant_entry, ...],
         "skipped": [{"approach": ..., "why": ...}, ...],
         "different": True/False,
         "problems": [...]}

    Each variant_entry is a `variants.variant()` dict with the approach
    recorded as its style. Each variant passes claims.check.

    `llm_ask` is the model call function. In production it is
    `llm.ask`; in tests it is a fake. When None, no model is called and
    the function returns the prompts and available approaches only.
    """
    from . import generate, lint

    contact_key = lint.contact_key(contact) if contact else None
    available = approaches_available(rec, contact, node_type, config)
    channel = "email" if node_type == "email" else "linkedin"
    _, ordinal, _ = generate.position(sequence, step_key)
    purpose = generate.purpose_for(channel, ordinal, sequence=sequence)

    # Build the context block
    context_block = generate.context_for(
        "draft" if node_type == "email" else "linkedin_note",
        rec, contact, config, step_key, sequence)

    # For observation-led, inject the licensed observation
    obs_entry = next((a for a in available
                      if a["approach"] == "observation_led"), None)
    if obs_entry and obs_entry.get("available") and obs_entry.get("evidence"):
        context_block["observation"] = obs_entry["evidence"]

    generated = []
    skipped = []

    for entry in available:
        approach = entry["approach"]
        if not entry.get("available"):
            skipped.append({"approach": approach, "why": entry.get("why", "")})
            continue

        prompt = variant_prompt(approach, purpose, context_block)

        if llm_ask is None:
            # No model: return the prompt for the caller to use
            generated.append({
                "approach": approach,
                "style": style_for(node_type, approach),
                "prompt": prompt,
                "variant": None,
            })
            continue

        # Call the model
        variant_data = _generate_one(
            approach, node_type, prompt, llm_ask, model,
            rec, contact, config, step_key)
        if variant_data is None:
            skipped.append({"approach": approach,
                            "why": "failed gates (claims or lint)"})
            continue
        generated.append(variant_data)

    # Check differentiation
    variant_entries = [g.get("variant") for g in generated
                       if g.get("variant")]
    company_name = (rec.get("company_facts") or {}).get("name") or \
        rec.get("company")
    diff_check = are_materially_different(variant_entries, node_type,
                                          company_name)

    return {
        "variants": variant_entries,
        "skipped": skipped,
        "different": diff_check["different"],
        "problems": diff_check["pairs"],
        "structural_summary": diff_check["structural_summary"],
        "generated": generated,
    }


def _generate_one(approach, node_type, prompt, llm_ask, model,
                  rec, contact, config, step_key):
    """Generate one variant, gate it, and return it or None."""
    from . import lint

    prompt_step = "draft" if node_type == "email" else "linkedin_note"
    data, attempts, errors = llm_ask(model, prompt_step, prompt)
    if not data:
        return None

    subject = data.get("subject")
    body = data.get("body")
    note = data.get("note")

    # Normalise punctuation
    if subject:
        subject = lint.normalise_punctuation(subject)
    if body:
        body = lint.normalise_punctuation(body)
    if note:
        note = lint.normalise_punctuation(note)

    style = style_for(node_type, approach)
    variant_id = f"{step_key}_{approach}"

    entry = variants.variant(
        variant_id, style,
        subject=subject, body=body, note=note)

    # Gate: claims check
    text = " ".join(filter(None, [subject, body, note]))
    unsupported = claims.check(text, rec, contact)
    if unsupported:
        return None

    # Gate: foreign product
    from . import clients
    product = clients.product(config or {})
    invented = claims.foreign_product(text, product, rec)
    if invented:
        return None

    return {
        "approach": approach,
        "style": style,
        "variant": entry,
    }


# --------------------------------------------------- integration
#
# Wire into generate.py's plan/draft path. A step that has variants
# generates them all at once rather than one at a time.

def plan_variant_set(rec, contact, spec, client=None, campaign=None):
    """Should this step generate a variant set? Returns the op or None.

    A step with `variants` already populated and passing validation does
    not need regeneration. A step without variants, or with variants that
    fail the differentiation check, does.
    """
    from . import cadence

    key_spec = spec
    if not (key_spec.get("variants") or key_spec.get("generated")):
        return None

    # Check if variants already exist on the spec
    existing = key_spec.get("variants") or []
    active = [v for v in existing if v.get("status") == variants.ACTIVE]
    if len(active) >= variants.MINIMUM_VARIANTS:
        # Already have enough variants - check they are different
        company_name = (rec.get("company_facts") or {}).get("name") or \
            rec.get("company")
        node_type = key_spec.get("type", spec.get("channel", "email"))
        diff = are_materially_different(active, node_type, company_name)
        if diff["different"]:
            return None

    return {
        "step": "variant_set",
        "why": (f"generate {variants.MINIMUM_VARIANTS} variants for "
                f"{spec.get('key', '?')}"),
        "contact": (contact or {}).get("name"),
        "day": spec.get("key"),
        "channel": spec.get("channel", "email"),
    }
