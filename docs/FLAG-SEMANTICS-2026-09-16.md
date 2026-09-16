# Flag semantics: --limit, --lane, --cap

**Date:** 2026-09-16  
**Task:** TASK-181  
**Files changed:** `src/run.py`, `tests/test_run_flags.py` (new)

## Summary

Three CLI flags that an operator reads as bounding the run had two bugs and
one that needed proof. `--limit` bounded the scan window, not the work done.
`--lane` scoped only ingest, not the processing stages. `--cap` was correct
but had no test proving it.

## What each flag does today (after the fix)

### `--limit N`

**Bounds the number of records that have work done on them.**

The runner filters the queue to records that need work in at least one active
per-record stage, then takes the first N of those. Records already finished
for every active stage are not counted against the limit.

**Before:** `targets = targets[:limit]` sliced the first N records from the
queue, then each stage skipped the ones already done. An operator passing
`--limit 20` over a queue where 11 of the first 20 were already enriched got
9 records processed - the scan window, not the work done.

**Code path:** `run()` calls `record_has_work(rec, stages)` for each record,
which checks `needs(rec, stage)` for every per-record stage in the active
set, plus the second predicates (`qualify.needs_work` for changed facts,
`unkeyed(rec)` for contacts without keys).

**Why this over the alternative:** "Records processed" is the reading an
operator has. "Records scanned" is what the implementation did. Nothing in
the codebase depends on the scan-window semantics - the stages themselves
already skip done records, so the limit was double-counting the skip. The
fix makes the limit agree with what the stages decide.

**Impact on recorded runs:** Any previous run that reported "N records with
`--limit M`" described the scan window, not the processing count. If M >
active records, the actual processing count was lower. TASK-163 measured
five records with `--limit 5`; if any of the first 5 were already done, the
real processing count was lower than 5.

### `--lane <lane>`

**Scopes every stage to records in that lane.**

The runner filters `targets` to records whose `lane` field matches, before
passing them to any stage. This applies to enrich, qualify, personas,
generate, render and push - not just ingest.

**Before:** `lane` was only passed to `ingest.run()`. The processing stages
received the full target list and worked on every record regardless of lane.
An operator passing `--lane domains` expected only domains-lane records to
be processed; instead, records in `drafted` and `verified` from other lanes
were moved forward.

**Code path:** `run()` filters `targets` with `r.get("lane") == lane` after
loading and before any stage runs.

### `--cap N`

**Bounds the credit spend for this run. Required with `--spend`.**

`enrich.require_cap(spend, cap)` refuses a live run with no cap.
`enrich.Budget(cap)` refuses any call that would exceed the cap. `--cap 0`
plans without spending and also refuses unpriced calls (Apify research) that
burn compute units despite costing 0 credits.

**Proof:** `tests/test_run_flags.py::CapBoundsSpend` drives the real
`Budget` class and the real `stage_enrich` entry point. The budget refuses
calls over the cap, accepts calls within it, and the stage stops spending
when the cap is reached.

## The `record_has_work` predicate

This function decides which records count against `--limit`. It must agree
with what the stages themselves decide, or the limit and the stages will
disagree about how many records were processed.

It checks:
1. `needs(rec, stage)` for every per-record stage in the active set
2. `qualify.needs_work(rec)` when qualify is done but facts changed
3. `unkeyed(rec)` when personas is done but contacts lack keys

Terminal records (`dropped`, `pushed`) are never active.

## Tests

30 tests in `tests/test_run_flags.py`:
- `LimitBoundsProcessing` (5 tests): limit skips done records, bounds when
  more active than limit, returns zero when all done, processes all without
  limit, counts qualify rework
- `LaneScopesEveryStage` (4 tests): lane filters enrich, lane filters
  qualify, no lane processes all, lane combines with limit
- `CapBoundsSpend` (11 tests): require_cap refuses/accepts, budget
  refuses/allows/exact/zero/refund, stage stops at cap
- `RecordHasWork` (10 tests): unit tests for the predicate covering fresh,
  done, terminal, partial, failed, batch-only, multi-stage, qualify rework,
  personas unkeyed

## Help text

Updated in `src/run.py::main()`:

- `--lane`: "scope every stage (not just ingest) to records in this lane;
  records in other lanes are not processed"
- `--cap`: "credit ceiling for this run; required with --spend. The
  enrichment budget refuses any call that would exceed it. --cap 0 plans
  without spending"
- `--limit`: "maximum number of records that have work done on them. Records
  already finished for every active stage are not counted; the limit bounds
  processing, not scanning"
