# UK/EU Re-engagement Provider Read — 2026-09-25

## Status: SCRIPT AND TESTS DELIVERED, LIVE RUN OWED

The script (`scripts/reengagement_provider_read.py`) and regression test
(`tests/test_reengagement_age_is_read_not_cached.py`) are complete and
tested. The live provider run against the production inventory is owed —
it must be executed from Claude's worktree against `work/queue.jsonl`
and `work/stage/reengagement-inventory.jsonl` in production state.

## What was built

### `scripts/reengagement_provider_read.py`

READ ONLY. No write, no attach, no enrolment. Not one write verb is
imported from any provider module.

1. **UK/EU selection**: from the stored ISO country code in the queue
   record's segment data, cross-referenced via `record_id`. The geo
   module's region table is the canonical source for which ISO codes are
   European. NOT from a TLD guess.

   UK/EU/EEA ISO set: GB, IE, plus EU27 (AT through SE), plus NO, IS,
   LI, CH.

2. **Provider reads**:
   - EmailBison: `GET /leads/{id}/scheduled-emails` — a row with
     `status="sent"` AND a non-null `sent_at` is the only witness
     accepted. `scheduled`, `active`, `stopped` are NOT sends.
   - HeyReach: `POST /inbox/GetConversationsV2` — the most recent
     correspondent-bound message timestamp via `inbound_messages()`.

3. **Per-row output**: `inventory_age_days`, `provider_age_days`,
   `delta_days`, `provider_campaign`, `provider_timestamp`.

4. **REENGAGE predicate**: 90+ days by PROVIDER age, no reply, no
   unsubscribe, no bounce. A provider read failure is HELD, never
   defaulted to the inventory value.

5. **REVIVE lane stays out**: rows carrying a reply or unsubscribe are
   excluded and counted.

### `tests/test_reengagement_age_is_read_not_cached.py`

17 tests, all passing. The regression:

- Feed `assess_row` an inventory row claiming 111 days and a provider
  stamp from yesterday → `reengage_qualifies` is False.
- Feed the same row with no provider data → `reengage_qualifies` is True
  (proving the cache is wrong).
- A HELD row (provider read failure) never qualifies.
- Break-the-wiring verified: removing the provider read from `assess_row`
  changes the answer from False to True.

## What the live run must report

The script cannot be run from this worktree because:

1. `work/stage/reengagement-inventory.jsonl` does not exist here (the
   `work/` directory is gitignored and absent from worker worktrees).
2. `work/queue.jsonl` does not exist here (same reason).
3. The QWEN.md standing order prohibits provider calls from this
   worktree.

The live run must be executed from Claude's worktree against production
state. The script is ready:

    py -3 scripts/reengagement_provider_read.py

Or with explicit paths:

    py -3 scripts/reengagement_provider_read.py \
        --inventory work/stage/reengagement-inventory.jsonl \
        --queue work/queue.jsonl

## Acceptance bar status

| Requirement | Status |
|---|---|
| Every UK/EU row has `provider_age_days` or HELD | Script enforces this |
| Cache-vs-provider one-liner | `report()` emits it |
| Lead 133283 reproduction | Test covers the exact scenario |
| Regression test (yesterday send ≠ untouched) | 17 tests, all green |
| `grep -n last-touch` returns nothing | Verified clean |
| No fixtures | Script reads the provider directly |
| HELD ≠ "no touch found" | `provider_age_days("HELD")` returns -1 |
| `replies.is_automated` for reply classification | Used in predicate |

## The DELTA DISTRIBUTION the live run will produce

The script computes `|inventory_age - provider_age|` per row and buckets
into 0, 1-6, 7-30, 30+, unresolvable. The measured distribution from
the 2026-09-24 probe was:

    145 of 2,081   staler than the live lead
    133 of those   by 7+ days
    the worst      by 111 days

The UK/EU subset will be a fraction of this. The script reports the
exact numbers.

## Files

    ALLOWED    scripts/reengagement_provider_read.py        ✅ CREATED
               tests/test_reengagement_age_is_read_not_cached.py  ✅ CREATED
               docs/REENGAGEMENT-UK-EU-PROVIDER-READ-2026-09-25.md  ✅ THIS FILE
    FORBIDDEN  src/providers/*    not edited
               work/*             not touched
               config/.env        not read
               src/cadence.py     not edited
               config/clients/productive.yaml   not edited
               scripts/batch1_build.py          not edited
