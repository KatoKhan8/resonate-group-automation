#!/usr/bin/env python3
"""Five materially different variants per step, not five paraphrases.

## What this is

A generator that produces N variants for a single message step, each with a
named approach (style) drawn from `variants.STYLES_FOR`. The approach is
RECORDED on the variant so a result can later be attributed to an approach
rather than to a string.

## What this is not

It is not five drafts for an operator to pick from. Each variant is a
complete message that passes the SAME quality gates as any other copy:
lint, claims, and - for the research-led approach - an observation licence.

## The approaches

Email:
  short_direct   - Two sentences and one question.
  casual         - Written the way a peer would write it.
  professional   - Complete sentences, measured tone.
  consultative   - Names the pattern before the ask. REQUIRES an observation.
  problem_led    - Opens on the cost of the status quo.

LinkedIn:
  casual         - Lower case, short, conversational.
  short_direct   - One line and a question.
  professional   - Full sentences, no abbreviation.
  consultative   - A short observation, then the ask. REQUIRES an observation.
  peer_to_peer   - One operator writing to another.

## The research-led variant is gated on observations

A model asked for an observation-led message with no observation available
will invent one. The consultative/observation-led variant is UNAVAILABLE
when the record carries no licensed observation, rather than generated and
then rejected. `observations.resolve()` is the authority.

## The diversity check

After generation, `quality.campaign_repetition()` checks whether any pair
of variants is a synonym swap. Two variants that share 50%+ of their
content words (discounting subject vocabulary and the company name) are
not materially different, and the set is rejected.

## Each variant carries its own approval requirement

`variants.fingerprint()` hashes the style, subject, body and note into a
16-character digest. Editing a variant invalidates its approval by the
same rule that has always applied.
"""
from . import claims, lint, observations, quality, variants

# The consultative/observation-led style requires a licensed observation.
# These are the style keys that assert something the system noticed.
OBSERVATION_REQUIRING_STYLES = ("consultative",)

# Maximum regeneration attempts per variant before giving up.
MAX_ATTEMPTS_PER_VARIANT = 3


def approaches_for(channel, rec=None, contact_key=None, config=None,
                   today=None):
    """The available approaches for this channel, with gating.

    Returns a list of (style_key, description, gated, gate_reason) tuples.
    `gated` is True when the style is available, False when it is refused.
    An observation-requiring style with no licensed observation is refused
    rather than generated and then rejected.
    """
    styles = variants.STYLES_FOR.get(channel, {})
    out = []
    for style_key, description in styles.items():
        if style_key in OBSERVATION_REQUIRING_STYLES:
            decision = observations.resolve(
                observations.PERSON_CONTENT
                if channel != "email"
                else observations.COMPANY_EVENT,
                rec or {}, contact_key, config, today)
            if not decision:
                out.append((style_key, description, False,
                            decision.get("why", "no licensed observation")))
                continue
        out.append((style_key, description, True, None))
    return out


def variant_prompt_context(step_context, style_key, style_description):
    """Extend a step's prompt context with the approach instruction.

    Returns a dict that can be merged into the context passed to the model.
    The approach instruction tells the model HOW to write, not WHAT to say -
    the ladder's purpose for this rung is the shared brief, and the style
    is the angle on it.
    """
    return {
        "approach": style_key,
        "approach_description": style_description,
        "approach_instruction": (
            f"Write in the '{style_key}' style: {style_description}. "
            f"This is one of five approaches being tested. The step's "
            f"purpose is: {step_context.get('purpose', 'not specified')}. "
            f"Vary the opening structure, tone, CTA style and proof "
            f"framing to match this approach. Do NOT vary what is true."
        ),
    }


def check_diversity(variants_list, company_name=None):
    """Are these variants materially different, or synonym swaps?

    Uses `quality.campaign_repetition()` from TASK-043. Returns a list of
    collision dicts, each naming a pair of variants that are too similar.
    An empty list means the variants are genuinely different approaches.

    Each variant is represented as a dict with `variant_id` and either
    `body` (email) or `note` (linkedin).
    """
    if len(variants_list) < 2:
        return []
    steps = []
    for v in variants_list:
        text = v.get("body") or v.get("note") or ""
        steps.append({"key": v["variant_id"], "text": text})
    return quality.campaign_repetition(steps, company_name=company_name)


def generate_variants(step_context, rec, contact, model, channel="email",
                      client=None, campaign=None, config=None, n=5):
    """Generate N materially different variants for one step.

    Returns a dict with:
      - `variants`: list of variant dicts (from `variants.variant()`)
      - `skipped`: list of (style, reason) for approaches that could not be
        generated
      - `diversity_collisions`: list of collision dicts from the diversity
        check (empty if all variants are materially different)

    Each variant:
      - carries its approach recorded as `style`
      - passes lint and claims gates
      - has its own approval fingerprint

    A variant that cannot be supported is NOT generated. The research-led
    variant is absent rather than invented when no observation is licensed.
    """
    contact_key = lint.contact_key(contact or {})
    available = approaches_for(channel, rec, contact_key, config)

    generated = []
    skipped = []

    for style_key, description, is_available, gate_reason in available:
        if not is_available:
            skipped.append((style_key, gate_reason or "not available"))
            continue

        variant_result = _generate_one_variant(
            step_context, rec, contact, model, channel, style_key,
            description, client, campaign)
        if variant_result is None:
            skipped.append((style_key,
                            "failed quality gates after "
                            f"{MAX_ATTEMPTS_PER_VARIANT} attempts"))
            continue
        generated.append(variant_result)

    # Diversity check: are the generated variants materially different?
    collisions = check_diversity(generated,
                                 company_name=rec.get("company"))

    return {
        "variants": generated,
        "skipped": skipped,
        "diversity_collisions": collisions,
        "approaches_recorded": [v["style"] for v in generated],
    }


def _generate_one_variant(step_context, rec, contact, model, channel,
                          style_key, style_description, client=None,
                          campaign=None):
    """Generate one variant for one approach, passing all gates.

    Returns a variant dict or None if the variant could not be produced.
    """
    contact_key = lint.contact_key(contact or {})
    approach_ctx = variant_prompt_context(step_context, style_key,
                                          style_description)

    for attempt in range(MAX_ATTEMPTS_PER_VARIANT):
        draft = _call_model_for_variant(model, step_context, approach_ctx,
                                        channel, rec, contact, client)
        if draft is None:
            continue

        subject = draft.get("subject")
        body = draft.get("body")
        note = draft.get("note")

        # Build a step dict for lint
        step = {"channel": channel}
        if subject:
            step["subject"] = subject
        if body:
            step["body"] = body
        if note:
            step["note"] = note

        # Lint gate
        failures = lint.check(rec, contact_key, step)
        if failures:
            continue

        # Claims gate
        text = body or note or ""
        unsupported = claims.check(text, rec, contact)
        if unsupported:
            continue

        # Build the variant with recorded approach
        variant_id = f"{step_context.get('key', 'step')}-{style_key}"
        entry = variants.variant(
            variant_id, style_key,
            subject=subject, body=body, note=note)
        return entry

    return None


def _call_model_for_variant(model, step_context, approach_ctx, channel,
                            rec, contact, client):
    """Call the model for one variant draft. Returns a dict or None."""
    from . import generate, llm

    context = generate.context_for(
        "draft" if channel == "email" else "linkedin_note",
        rec, contact, client,
        step_key=step_context.get("key"),
    )
    context.update(approach_ctx)

    import json
    prompt = (
        f"Write a {'email' if channel == 'email' else 'LinkedIn message'} "
        f"in the '{approach_ctx['approach']}' style.\n\n"
        f"Style instruction: {approach_ctx['approach_description']}\n\n"
        f"Step purpose: {step_context.get('purpose', 'not specified')}\n\n"
        f"Context:\n{json.dumps(context, indent=2, ensure_ascii=False)}\n\n"
        f"Return JSON with fields: "
        f"{'subject, body' if channel == 'email' else 'note'}."
    )

    try:
        data, _attempt, _errors = llm.ask(model, "draft", prompt, rec=rec)
        if isinstance(data, dict):
            return data
        return None
    except Exception:
        return None


def approval_requirements(variants_list):
    """Each variant's approval fingerprint.

    Returns a list of dicts, each with variant_id, style and fingerprint.
    A variant that is edited invalidates its approval by the same rule
    that has always applied.
    """
    out = []
    for entry in variants_list:
        out.append({
            "variant_id": entry["variant_id"],
            "style": entry.get("style"),
            "fingerprint": variants.fingerprint(entry),
        })
    return out
