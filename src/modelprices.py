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


class _Unknown:
    """The cost of a model nobody has priced. NOT a number, on purpose.

    TASK 0073. The defect was not that unpriced models produced 0 - it was
    that the 0 flowed into arithmetic that could not tell it from a free
    call: holds reserved at 0, a guard gated `if cost > 0` skipped, a total
    summed it into a confident figure. So UNKNOWN refuses the arithmetic
    itself. `int(UNKNOWN)` and `UNKNOWN + 0` raise TypeError, which means a
    caller that tries to flatten this back into a number fails LOUDLY in
    its own stack, instead of confidently wrong three ledgers later.

    Truthy on purpose: an unknown is an answer ("this is not known"), not
    a shrug, so `if cost:` does not quietly skip the unpriced branch.
    """

    _refuse = ("UNKNOWN is not a number. A caller that tries arithmetic on "
               "an unknown cost is the 58%-of-the-bill-reads-as-free defect "
               "surviving its fix. Convert at a persistence boundary "
               "(see spendledger.reserve/settle/record) or refuse.")

    def __repr__(self):
        return "UNKNOWN"

    def __bool__(self):
        return True

    def __int__(self):
        raise TypeError(self._refuse)

    def __add__(self, other):
        raise TypeError(self._refuse)

    __radd__ = __add__


UNKNOWN = _Unknown()


def is_unknown(cost):
    """True when `cost` is the unpriced sentinel (`cost is UNKNOWN`)."""
    return cost is UNKNOWN


# Models this repository names that NOBODY has priced, with the reason each
# stays unpriced (TASK 0073 §2: add only entries that can be sourced, and
# name the source; never invent a price). A model here and a model merely
# absent from the yaml are the same state downstream - UNKNOWN - but a name
# here is auditable: the regression test in
# tests/test_an_unknown_price_is_not_a_free_call.py refuses a NEW model id
# that is neither priced nor declared, so this dict is where an honest
# "we know we do not know" gets recorded instead of another silent zero.
DELIBERATELY_UNPRICED = {
    "claude-opus-5":
        "ran 58% of one bill (qwen, 2026-10-15) with no yaml entry; no "
        "in-repo source carries its rates - add a sourced entry to "
        "config/model-prices.yaml when one exists",
    "grok-4.6":
        "named by task166/task182 and tests/test_xai_adapter; x.ai bills in "
        "ticks and no rate table for it exists in this repository",
    "anthropic/claude-3.5-sonnet":
        "the undated slug the openrouter fixture echoes; the dated twin "
        "claude-3-5-sonnet-20241022 is priced, and mapping an undated slug "
        "onto a dated snapshot is the guess the yaml's alias comment "
        "refuses to make",
}


def cost_micro_usd(model, usage):
    """The cost of one call in integer micro-USD.

    `usage` is a dict with `prompt_tokens` and `completion_tokens` (the shape
    every adapter in this repository already extracts). A token count that is
    None or missing is treated as zero for that half - the row is still
    written, and the zero half says "we did not learn the input count" rather
    than "input was free".

    Returns UNKNOWN when the model is unpriced - never 0. A zero that means
    "free" and a zero that means "nobody priced this" were the same number
    here for long enough that 58% of one bill read as free (TASK 0073), so
    the third state is now its own value. The ledger seam
    (`spendledger.reserve`/`settle`/`record`) accepts UNKNOWN and writes the
    row at expected_cost=0 with priced=False: the row is still written,
    visibly unpriced instead of invisibly free.
    """
    priced = price_for(model)
    if priced is None:
        return UNKNOWN
    inp_per_1m, out_per_1m, _, _ = priced
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    usd = (prompt * inp_per_1m + completion * out_per_1m) / 1_000_000
    from . import spendledger
    return spendledger.to_micro_usd(usd)
