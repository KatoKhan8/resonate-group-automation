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
    """`(input, output, cache_creation, cache_read, source, as_of)` or None.

    `cache_creation` and `cache_read` are None when the model has no published
    cache rate. A missing rate is NOT derived from the input rate - inventing
    a multiplier would make the ledger carry a plausible fabrication that
    nobody downstream can distinguish from a real price.

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
    cc = entry.get("cache_creation_input_per_1m")
    cr = entry.get("cache_read_input_per_1m")
    return (float(inp), float(out),
            float(cc) if cc is not None else None,
            float(cr) if cr is not None else None,
            entry.get("source"), entry.get("as_of"))


def cost_micro_usd(model, usage):
    """The cost of one call in integer micro-USD, or None when unpriceable.

    `usage` is a dict with `prompt_tokens` and `completion_tokens` (the shape
    every adapter in this repository already extracts). Cache tokens carry
    `cache_creation_input_tokens` and `cache_read_input_tokens` - Anthropic
    includes these in the usage object when prompt caching is active.

    Each token kind is priced at its own rate. A cache read is cheaper than
    a fresh input token; a cache write costs more. If a token kind is present
    in the usage but has no published rate, the whole cost is None - the
    caller must ledger the row as unpriced rather than guess.

    Returns 0 when the model itself is unpriced. Returns None when the model
    is priced but a cache token kind is present without a rate. The caller
    MUST still write the row - a missing row and a free call are
    indistinguishable in the ledger.
    """
    priced = price_for(model)
    if priced is None:
        return 0
    inp_per_1m, out_per_1m, cc_per_1m, cr_per_1m, _, _ = priced

    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    cache_write = int(usage.get("cache_creation_input_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)

    if cache_write and cc_per_1m is None:
        return None
    if cache_read and cr_per_1m is None:
        return None

    usd = ((prompt * inp_per_1m
            + completion * out_per_1m
            + cache_write * (cc_per_1m or 0)
            + cache_read * (cr_per_1m or 0))
           / 1_000_000)
    from . import spendledger
    return spendledger.to_micro_usd(usd)
