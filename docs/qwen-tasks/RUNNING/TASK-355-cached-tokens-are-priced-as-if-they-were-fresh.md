PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-355 - cached tokens are priced as if they were fresh

**Operator decision, 2026-09-26: TASK-340's $2 measurement is held until this is
correct.** Then it runs.

TASK-340 built prompt caching and batching and reported the defect itself:

> Cache pricing in `model-prices.yaml` does not yet account for
> `cache_creation_input_tokens` or `cache_read_input_tokens`. The ledger rows
> carry these counts but `cost_micro_usd` treats them as normal input tokens.

So a cached run would be **mispriced in both directions**: a cache read is much
cheaper than a fresh input token and a cache write is more expensive. Measuring
the saving against this pricing would produce a number that is wrong and looks
authoritative - the worst kind.

## Build

    config/model-prices.yaml   MODIFY. Cache rates per model.
    src/modelprices.py         MODIFY. `cost_micro_usd` reads them.
    tests/test_a_cached_token_is_not_priced_as_a_fresh_one.py   NEW

Three input rates per model, not one:

    input                         fresh input tokens
    cache_creation_input_tokens   writing the cache (a premium on input)
    cache_read_input_tokens       reading it (a large discount)

Each entry keeps the `source` (the URL the price was read from) and `as_of` date
that `model-prices.yaml` already requires.

## The rule that governs a missing rate

**Never invent a rate.** This is the standing position and it applies exactly
here: if a model has no published cache rate, **do not derive one from the input
rate by applying a multiplier you chose.** Store the rate as absent, price the
cached tokens as unpriced, and let the row carry `usd_estimate: null` with
`rate_source: "unknown"` rather than a plausible fabrication.

A ledger that says "I do not know" is usable. A ledger carrying a guessed
multiplier is not, and nobody downstream can tell the difference.

## Acceptance - RUN each, paste real output

1. The three rates are read separately, and a cache read costs less than a fresh
   token for the same count:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import modelprices as M;\
    fresh=M.cost_micro_usd('claude-sonnet-4-20250514',{'input_tokens':1000,'output_tokens':0});\
    cached=M.cost_micro_usd('claude-sonnet-4-20250514',{'cache_read_input_tokens':1000,'output_tokens':0});\
    print('1000 fresh:',fresh,' 1000 cache-read:',cached);\
    assert cached < fresh, 'a cache read is not cheaper than a fresh token';\
    print('ratio %.3f'%(cached/fresh if fresh else 0))"

   Name the real signature if it differs - read the module, do not assume.

2. **A cache WRITE costs more than a fresh token**, which is the half people
   forget. Assert it.

3. **An unpriced cache rate returns null, not zero and not a guess:**

    a model with no cache rate in the file must produce `usd_estimate: None` and
    `rate_source: "unknown"` for its cached portion. Assert both.

4. **The total reconciles.** For a usage dict carrying all four token kinds,
   assert the computed cost equals the sum of the four priced components - so a
   kind cannot be silently dropped.

5. **The guard is seen to fail:** revert the cache-rate lookup so cached tokens
   price as fresh, confirm test 1 FAILS, restore, confirm green. Confirm the
   revert landed. Paste both runs.

6. **No existing row repriced.** Historical rows keep their recorded
   `expected_cost`. Count rows before and after and assert equality.

7. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt`.

## Then, and only then

Report in your result block that TASK-340's measurement is unblocked, with the
rates now in place. **Do not run the measurement yourself** - it spends real money
under a $2 cap the operator granted to TASK-340, and running it here would spend
it twice.

## What this task may NOT do

- Do not invent, derive or interpolate a cache rate. No multiplier you chose.
- Do not make a live model call. Do not run TASK-340's measurement.
- Do not reprice or backfill historical rows.
- Nothing sent, nothing activated.
