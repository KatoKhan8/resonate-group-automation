"""Campaign strategy: decided ONCE PER SEGMENT, not once per lead.

Stage E of the v2 copy engine. The strategy for a segment is invariant across
all leads in that segment - the same segment+persona combination gets the same
target ICP, primary problem, primary offer, approved angles, objective, CTA
strategy and disqualification criteria. Per-lead work ADAPTS the strategy
(account research, signal relevance, personalisation, validation); it does not
re-decide it.

At 50 leads in one segment the previous design made 50 model calls for the
same answer. This module makes one and caches it.

Offers come from `src/offers.py` as DATA. A strategy may not invent an offer,
a capability, a discount, a pilot, a guarantee or a customer result.

The model call is injectable so tests never spend. Production passes a real
model; tests pass `llm.ScriptedModel`.
"""
import hashlib
import json

from . import copystages, offers as offers_mod

# ---------------------------------------------------------------- cache
#
# Keyed by (segment_key, persona). Lives for the process lifetime. A strategy
# that changes within a process would make every comparison across leads
# meaningless, so the cache is deliberately not time-bounded.

_strategy_cache = {}
_model_call_count = 0


def clear_cache():
    """Reset the strategy cache and call counter. Call in tests."""
    global _model_call_count
    _strategy_cache.clear()
    _model_call_count = 0


def model_call_count():
    """How many model calls have been made since the last clear_cache()."""
    return _model_call_count


# --------------------------------------------------------- the strategy call

def _strategy_fingerprint(segment_key, persona, offers_block):
    """Stable hash of the inputs that decide a strategy.

    Two calls with the same segment, persona and offer set produce the same
    fingerprint, so the strategy_id is reproducible across processes.
    """
    material = json.dumps({
        "segment_key": segment_key,
        "persona": persona,
        "offers": offers_block,
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _offers_for_segment(segment_key, persona):
    """The offers that apply to this segment+persona, as a plain dict.

    TASK-367: offers are persona-to-offer records. Each names a persona and
    a list of capability ids. The angle order within an offer comes from
    `capability_by_persona` in productive.yaml, not from the offer itself.

    An offer whose approval_status is not 'approved' is excluded - a strategy
    may not plan around an offer that cannot ship.
    """
    all_offers = offers_mod.load()
    matched = {}
    for oid, offer in all_offers.items():
        if offer.get("approval_status") != offers_mod.APPROVED:
            continue
        offer_persona = offer.get("persona", "")
        if offer_persona and offer_persona != persona:
            continue
        matched[oid] = {
            "persona": offer_persona,
            "capabilities": offer.get("capabilities", []),
            "problem": offer.get("problem"),
            "mechanism": offer.get("mechanism"),
            "cta_link": offer.get("cta_link"),
        }
    return matched


def _build_strategy_prompt(segment_key, persona, offers_block):
    """Assemble the user prompt for the strategy model call.

    The system prompt is `copystages.STRATEGY_SYSTEM`. The user prompt
    provides the segment context and the offers the strategy may draw on.
    """
    return (
        f"Segment: {segment_key}\n"
        f"Persona: {persona}\n\n"
        f"Available offers (data, not to be invented):\n"
        + json.dumps(offers_block, indent=2)
        + "\n\nDecide the strategy for this segment+persona combination."
    )


def _call_model(segment_key, persona, offers_block, model):
    """Make the ONE model call for this segment+persona.

    Returns the parsed strategy dict. Increments the module call counter
    exactly once per call - this is the counter the acceptance test reads.
    """
    global _model_call_count
    user_prompt = _build_strategy_prompt(segment_key, persona, offers_block)
    full_prompt = copystages.STRATEGY_SYSTEM + "\n\n" + user_prompt
    raw = model.complete(full_prompt)
    _model_call_count += 1
    data = json.loads(raw) if isinstance(raw, str) else raw
    return data


def for_segment(segment_key, persona, model=None):
    """Return the strategy for this segment+persona, calling the model at most
    once per unique combination.

    `model` is injectable. When None, a `NoModel` is used, which refuses -
    production must pass a real model. Tests pass `ScriptedModel`.

    The returned dict always includes `strategy_id`, a stable fingerprint of
    the inputs. Two calls with the same segment_key, persona and offer set
    return the same strategy_id without making a second model call.
    """
    from . import llm as llm_mod

    cache_key = (segment_key, persona)
    if cache_key in _strategy_cache:
        return _strategy_cache[cache_key]

    if model is None:
        model = llm_mod.NoModel()

    offers_block = _offers_for_segment(segment_key, persona)
    strategy_data = _call_model(segment_key, persona, offers_block, model)

    strategy_data["strategy_id"] = _strategy_fingerprint(
        segment_key, persona, offers_block)
    strategy_data["segment_key"] = segment_key
    strategy_data["persona"] = persona

    _strategy_cache[cache_key] = strategy_data
    return strategy_data
