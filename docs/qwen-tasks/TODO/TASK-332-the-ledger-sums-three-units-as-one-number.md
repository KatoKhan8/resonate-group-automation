PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-332 — the ledger sums three units as one number

**SEVERITY: MEDIUM** (findings M1/M2/M3 in `docs/BUGGIE-FINDINGS-2026-09-26.md`).
Related to TASK-323 but distinct: 323 makes model spend VISIBLE, this makes the
existing totals HONEST.

## M1 — report() mixes units and prints one total

`spendledger.report()` accumulates `int(row["expected_cost"])` into `by_provider`
and `by_day` with no unit filter, and `main()` prints
`expected total {out['expected_total']}` unguarded.

Rows on disk are in **cents** (apify), **credits** (most providers) and
**microusd** (anthropic/groq/openrouter). The module's own comment records that
this already happened once: *"a report summed 18,809 / 14,365 / 31,191 as though
they were one thing."*

`client_balance()` and `progress_block()` already detect mixed units and print
`MIXED UNITS - a tripwire, not an amount`. **`report()` has no equivalent.** Give
it the same guard — reuse the existing shape, do not invent a second one.

## M2 — Apify writes cents and declares nothing

`researchpack/pack.py:run_actor` documents *"THE COST HERE IS INTEGER CENTS, NOT
CREDITS"* and then calls `spendledger.reserve(...)` **without** `unit="cents"`.
Because `record` stamps the unit only `if unit:`, every Apify row lands with no
unit and no `usd_estimate` — even though the writer knows the unit exactly at
call time. Pass it.

## M3 — a dormant two-billion-credit landmine

`enrich.COSTS['xai-research'] = 2_000_000_000` (xAI ticks, ~$0.20) sits in a dict
whose other values are single-digit credits, and `enrich`'s `spend()` calls
`record(...)` with **no** `unit=`. There is no live call site today, so this is
dormant — but the first caller added will ledger two billion "credits" and blow
through or silently miscompare every ceiling. Give `xai` a unit in `LEDGER_UNITS`
and pass it at the `record` call, or refuse the call until it has one. **Do not
delete the entry** — it records a real price.

## The rule that governs all three

**Never invent a rate.** `USD_PER_UNIT["credits"]` is `None` on purpose: nobody
has priced a credit, and `usd_estimate` must come back `None` with
`rate_source: "unknown"` rather than carrying a fabricated conversion.

**Do not backfill historical rows.** The cents-vs-credits backfill rate is an open
operator decision (handoff §10.4). Guessing it writes a wrong number into the
only record that exists.

## Acceptance — RUN each, paste real output

1. A mixed-unit client no longer gets one number — a test asserting `report()`
   over rows of two different units returns the mixed-unit tripwire rather than a
   single summed integer.

2. Apify rows carry their unit:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as S;\
    u,rate,src=S.usd_estimate(1500,'cents');\
    assert abs(u-15.0)<1e-9 and src=='unit_definition',(u,src);print('cents ->',u)"

   plus a test that a `run_actor` reserve writes `unit == "cents"`.

3. `unit_for('xai')` is no longer `credits`, and a `record` for xai carries its
   unit.

4. **No invented rate:** a test asserting a provider with no established rate
   returns `usd_estimate is None` and `rate_source == "unknown"`.

5. **No historical row changed.** Count rows before and after and assert
   equality, and assert no existing row's `expected_cost` differs.

6. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not change `expected_cost` to a float. Every ceiling and all 17,937 existing
  rows depend on it being an int.
- Do not backfill. Do not invent a credit rate.
- Nothing sent, nothing activated, no model call, no provider call.
