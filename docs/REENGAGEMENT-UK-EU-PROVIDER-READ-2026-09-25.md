# UK/EU Re-engagement Provider Read

**Date:** 2026-09-25  
**Script:** `scripts/reengagement_provider_read.py`  
**Test:** `tests/test_reengagement_age_is_read_not_cached.py`  
**Status:** Code and tests built; live provider run is owed (see below).

## What was built

A read-only script that re-derives the re-engagement age from the provider's
own scheduled-emails endpoint at read time, replacing the cached age that was
never refreshed. The script:

1. Reads the UK/EU rows from `work/stage/reengagement-inventory.jsonl`.
2. Determines UK/EU by the stored ISO country code on the queue record
   (`record.segment.country_code`), mapped through `src/geo.COUNTRIES` to
   regions UK, DACH, Nordics, Benelux, CEE and Southern Europe.
3. For each row, calls `GET /leads/{id}/scheduled-emails` at EmailBison and
   derives the last confirmed touch (status=`sent` WITH a dated `sent_at`).
4. Produces per row: `inventory_age_days`, `provider_age_days`, `delta_days`,
   the campaign id of the last confirmed touch, and its timestamp.
5. Re-applies the REENGAGE predicate against the provider figures.
6. The REVIVE lane stays out. A row carrying a reply or an unsubscribe is
   never in the output set.

## How UK/EU was decided

Geo comes from the stored ISO country code on the queue record
(`record.segment.country_code`), populated by `src/geo` from the company's
country. The UK/EU set is the union of ISO2 codes mapped to regions UK, DACH,
Nordics, Benelux, CEE and Southern Europe in `src/geo.COUNTRIES` - the same
set `src/campaignseg.REGION_FAMILIES["EUROPE"]` uses.

This is NOT a TLD guess. The ISO code was stored during record enrichment
from the company's country field.

## What the live run will produce

The script was built in worktree `qwen-worker-8-r9`, which has no
`work/stage/reengagement-inventory.jsonl` and no `work/queue.jsonl` (both are
gitignored and live only in Claude's worktree). The live provider run is
**owed** from Claude's worktree against production state.

Expected output when run:

- A per-row table (hashed contact ids only) with the run's timestamp.
- The delta distribution: how many rows differ by 0, 1-6, 7-30, 30+ days.
- The named campaign id behind the worst deltas.
- The count of rows the cache would have wrongly admitted.
- The count of rows the cache would have wrongly excluded.

## The regression test

21 tests, all passing. The core assertion:

> A lead with a provider-confirmed send yesterday can never read as untouched.
> Feed the checker an inventory row claiming 111 days and a provider row from
> yesterday; the answer must be "touched yesterday", and deleting the provider
> read must make that test fail.

The test verifies:
- `assess_row` calls `last_provider_touch` (the wiring is real).
- A provider-confirmed send yesterday is never REENGAGE.
- The inventory age alone would have wrongly admitted the row.
- A provider read failure is HELD, never "no touch found".
- UK/EU geo filtering works by ISO code, not TLD.
- The REENGAGE predicate is correct against provider figures.
- `replies.is_automated` classifies out-of-office correctly.

## What would make this a false pass

- **Reading the cached age file.** `grep -n last-touch` over both new files
  returns nothing. The script does not import, open, or transitively read it.
- **Fixtures.** The regression test uses fixture data with a fixed clock
  (2026-09-25T12:00:00Z) and hashed identifiers. The LIVE provider run is
  owed separately.
- **Counting a read failure as "no touch".** The script returns HELD for any
  provider read failure, and the test asserts this explicitly.

## Boundaries respected

- **READ ONLY.** No write verb is imported from any provider module.
- **No PII.** All lead ids are hashed with SHA-256 (first 12 hex chars).
- **No forbidden files edited.** `src/cadence.py`,
  `config/clients/productive.yaml`, `scripts/batch1_build.py` untouched.
- **No prospect data in committed files.** The report uses hashed ids only.

## What is owed

1. **The live provider run.** The script must be run from Claude's worktree
   against `work/stage/reengagement-inventory.jsonl` and `work/queue.jsonl`
   with live EmailBison credentials. The run will produce the per-row table,
   the delta distribution, and the wrongly-admitted count.
2. **Lead 133283 verification.** The live run should reproduce the known-wrong
   row: 111-day inventory age, 2-day provider age, campaign 491.
3. **HeyReach cross-check.** The current script reads EmailBison only. A
   HeyReach touch (conversation, message, connection acceptance) could make a
   row even more recent. The HeyReach inbox walk is expensive (full inbox
   pagination) and was not included in this build. It should be a follow-up.
