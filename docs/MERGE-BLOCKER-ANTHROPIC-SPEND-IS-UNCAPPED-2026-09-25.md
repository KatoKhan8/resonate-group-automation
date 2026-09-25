# MERGE BLOCKER — Anthropic spend would ledger as zero and no ceiling could fire

**Verified 2026-09-25 against the three unmerged branches. Do not merge
TASK-308 or TASK-309 until this is fixed.** Nothing is broken on master today;
this is a defect that merging would introduce.

## The finding

`src/spendledger.record()` does `int(expected_cost or 0)`, and the Sonnet
price per lead is $0.00256.

    one lead     $0.00256  -> int() -> 0
    50 leads     $0.128    -> int() -> 0
    1,000 leads  $2.56     -> int() -> 2

**TASK-308** (`resonate-qwen-4`) works around this by hardcoding
`"expected_cost": 0` and putting the real figure in a new `amount` field, with
`unit: "usd"`. Its docstring says dollars and credits "must not be summed",
which is right. But the consequence is not:

- `spent()` sums `expected_cost`, so Anthropic always totals **0**
- `check()` compares that 0 against any ceiling, so it **never refuses**
- `record_spend` calls `spendledger._append_row` directly, bypassing
  `record()` and the production-write barrier it carries

**Anthropic spend would be fully visible in the ledger file and invisible to
every control.** That is the `per_run` defect in new clothes, and the third
instance this week of a check that passes because the thing it checks is
absent.

**TASK-309** (`resonate-qwen-5`) adds `unit` and `usd_estimate` correctly, but
keeps `int(expected_cost or 0)` at line 144. So a `usd` row of $0.00256 stores
`expected_cost: 0` and computes `usd_estimate: 0.0` from it. The unit column
lands and the amount still rounds away.

Neither worker is at fault. Both were dispatched BEFORE the correction naming
micro-dollars was committed, and each read the task text it was given.

## The fix

**Keep `expected_cost` integral** - the ceilings, `spent()` and every existing
row depend on it - and store dollars as **micro-dollars**:

    unit "microusd", expected_cost = round(usd * 1_000_000)
    $0.00256 -> 2560

`usd_estimate` stays a float for reporting. Anthropic's per-provider ceiling is
then denominated in micro-dollars, and the report must say so in words so
nobody reads 5,000,000 as credits.

Do NOT solve it by making `expected_cost` a float. Every ceiling, every
existing row and `spent()`'s accumulator assume an integer, and a float there
changes behaviour for every provider to fix one.

## Merge order, which is not optional

1. **The per-provider-ceilings lane** (`worktree-agent-a5ab2805834c167b3`, 13
   commits) — it holds the `unit=` seam through `record`/`reserve`/`settle` and
   its own `store.lock` restoration. It is the base.
2. **TASK-309** on top — `usd_estimate`, the backfill, reports summing it.
3. **TASK-308** last — rewritten to call `record(..., unit="microusd")` rather
   than `_append_row`.

All three edit `src/spendledger.py`. That lane already deleted its own
cross-process `store.lock` once by rewriting the file from a pre-rebase read,
and only a test on master caught it.

## The acceptance that would have caught it

    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as s;\
    r=[x for x in s.load() if x.get('provider')=='anthropic'];\
    assert r, 'no rows'; assert s.spent(client='productive', provider='anthropic') > 0, \
    'ledger holds rows the ceilings cannot see'"

The second assertion is the one that matters: **rows existing is not the same
as spend being countable**, and only the second protects the client.
