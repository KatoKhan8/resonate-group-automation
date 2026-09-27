#!/usr/bin/env python3
"""Model token prices, loaded from config/model-prices.yaml.

TASK-323: every model call must write a ledger row through
`spendledger.record(..., unit="microusd")`. The cost comes from this file.
A model absent from the file still gets a row - at expected_cost=0 with
token counts - so the call is visible and visibly unpriced.

## Why micro-USD

`spendledger.record` stores `expected_cost` as `int`. Dollars would truncate
to zero for any single call ($0.00256 -> 0). Micro-dollars keep the column
integral: $0.00256 -> 2560. See `spendledger.to_micro_usd`.
"""
import os

from . import clients

_PRICES = None
_PRICES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "model-prices.yaml")


def _load():
    """Parse config/model-prices.yaml. Cached after first call."""
    global _PRICES
    if _PRICES is not None:
        return _PRICES
    try:
        with open(_PRICES_PATH, encoding="utf-8") as fh:
            _PRICES = clients.parse(fh.read())
    except FileNotFoundError:
        _PRICES = {}
    return _PRICES


def reload():
    """Force a re-read. Tests call this after swapping the config."""
    global _PRICES
    _PRICES = None
    return _load()


def price_for(model):
    """`(input_per_1m, output_per_1m, source, as_of)` or None if absent.

    A missing model is NOT an error and NOT zero. It means nobody has priced
    it, and the caller should ledger the call at expected_cost=0 with token
    counts so the absence is visible.
    """
    entry = _load().get(model)
    if not isinstance(entry, dict):
        return None
    inp = entry.get("input_per_1m")
    out = entry.get("output_per_1m")
    if inp is None or out is None:
        return None
    return float(inp), float(out), entry.get("source"), entry.get("as_of")


def cache_rates_for(model):
    """`(cache_creation_per_1m, cache_read_per_1m)` or `(None, None)`.

    TASK-355: cache tokens price at their own rates. A model with no published
    cache rate returns `(None, None)` - the caller must NOT derive a rate from
    the input rate by applying a multiplier. An absent rate means the cached
    portion is unpriced, not that it is free.
    """
    entry = _load().get(model)
    if not isinstance(entry, dict):
        return None, None
    creation = entry.get("cache_creation_input_per_1m")
    read = entry.get("cache_read_input_per_1m")
    if creation is None or read is None:
        return None, None
    return float(creation), float(read)


def cost_micro_usd(model, usage):
    """The cost of one call in integer micro-USD.

    `usage` is a dict with any of:
      - `prompt_tokens` or `input_tokens` (fresh input)
      - `completion_tokens` or `output_tokens`
      - `cache_creation_input_tokens` (cache write, priced at a premium)
      - `cache_read_input_tokens` (cache read, priced at a discount)

    A token count that is None or missing is treated as zero for that kind.
    A model with no base rate returns 0. A model with base rates but no cache
    rates prices the cached portion at 0 (unpriced, not free) - the caller
    MUST still write the row so the absence is visible.

    Returns 0 when the model is unpriced. The caller MUST still write the row
    - a missing row and a free call are indistinguishable in the ledger.
    """
    priced = price_for(model)
    if priced is None:
        return 0
    inp_per_1m, out_per_1m, _, _ = priced
    cache_creation_per_1m, cache_read_per_1m = cache_rates_for(model)

    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    cache_creation = int(usage.get("cache_creation_input_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)

    usd = (prompt * inp_per_1m + completion * out_per_1m) / 1_000_000
    if cache_creation_per_1m is not None:
        usd += (cache_creation * cache_creation_per_1m) / 1_000_000
    if cache_read_per_1m is not None:
        usd += (cache_read * cache_read_per_1m) / 1_000_000

    from . import spendledger
    return spendledger.to_micro_usd(usd)


def cost_details(model, usage):
    """Per-kind breakdown with pricing metadata. TASK-355.

    Returns a dict:
      - `cost_micro_usd`: total integer micro-USD (0 if unpriced)
      - `components`: dict per token kind with `tokens`, `rate_per_1m`, `cost_micro_usd`
      - `usd_estimate`: float dollars or None if any priced portion has no rate
      - `rate_source`: "model_prices" or "unknown"

    A model with no cache rate prices the cached portion at 0 and sets
    `usd_estimate: None` with `rate_source: "unknown"` for that portion.
    """
    priced = price_for(model)
    if priced is None:
        return {
            "cost_micro_usd": 0,
            "components": {},
            "usd_estimate": None,
            "rate_source": "unknown",
        }
    inp_per_1m, out_per_1m, _, _ = priced
    cache_creation_per_1m, cache_read_per_1m = cache_rates_for(model)

    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    cache_creation = int(usage.get("cache_creation_input_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)

    components = {}
    total_usd = 0.0
    has_unknown = False

    if prompt:
        cost = (prompt * inp_per_1m) / 1_000_000
        components["input"] = {"tokens": prompt, "rate_per_1m": inp_per_1m,
                               "cost_micro_usd": int(round(cost * 1_000_000))}
        total_usd += cost
    if completion:
        cost = (completion * out_per_1m) / 1_000_000
        components["output"] = {"tokens": completion, "rate_per_1m": out_per_1m,
                                "cost_micro_usd": int(round(cost * 1_000_000))}
        total_usd += cost
    if cache_creation:
        if cache_creation_per_1m is not None:
            cost = (cache_creation * cache_creation_per_1m) / 1_000_000
            components["cache_creation"] = {"tokens": cache_creation,
                                            "rate_per_1m": cache_creation_per_1m,
                                            "cost_micro_usd": int(round(cost * 1_000_000))}
            total_usd += cost
        else:
            has_unknown = True
            components["cache_creation"] = {"tokens": cache_creation,
                                            "rate_per_1m": None,
                                            "cost_micro_usd": 0}
    if cache_read:
        if cache_read_per_1m is not None:
            cost = (cache_read * cache_read_per_1m) / 1_000_000
            components["cache_read"] = {"tokens": cache_read,
                                        "rate_per_1m": cache_read_per_1m,
                                        "cost_micro_usd": int(round(cost * 1_000_000))}
            total_usd += cost
        else:
            has_unknown = True
            components["cache_read"] = {"tokens": cache_read,
                                        "rate_per_1m": None,
                                        "cost_micro_usd": 0}

    from . import spendledger
    total_micro = spendledger.to_micro_usd(total_usd)
    return {
        "cost_micro_usd": total_micro,
        "components": components,
        "usd_estimate": None if has_unknown else total_usd,
        "rate_source": "unknown" if has_unknown else "model_prices",
    }
