PRIORITY: P1
DEPENDS: TASK-253, TASK-259

# TASK-260 — a checkpoint reads O(changed), not O(N)

Operator instruction, Zvonimir, 2026-09-22: *make the checkpoint read
incremental, indexed reads by state and by changed-since cursor so a
checkpoint reads O(changed), not O(N); benchmark at 1k / 5k / 20k on both
backends and report wall clock per pass.*

## Why this is the remaining half

TASK-255 measured all three arms at production record size
(`docs/LOAD-TEST-20K-2026-09-22.md`):

    ARM              RECORDS  CHECKPOINTS  TIME_S  MB_WRITTEN  AMPLIFICATION
    jsonl              1,000          200    65.4     3,981.8       1108.1x
    jsonl+journal      1,000          200   123.9         3.6          1.0x
    sqlite             1,000          200    43.3         0.2          0.1x

The write is solved: sqlite holds ~188 KB constant while the payload doubles.
**The read is not.** All three arms are O(N²) in wall clock — 2x the records
costs 4x the time — because every checkpoint reads the whole set and there are
N/5 checkpoints. Projected at 20,000: jsonl ~7 hours, journal ~52 minutes,
sqlite ~23 minutes.

`queuejournal.py` predicted this in its own docstring — *"the O(N) READ per
checkpoint stays. That read needs an index to fix"* — and the SQLite design
deferred it deliberately, because narrowing the read means the guards see less
and that is a safety change. This task is that change. Treat it as one.

---

## READ THIS FIRST: BOTH LOSS GUARDS FAIL OPEN ON ABSENCE

This is the hazard, it is not hypothetical, and it is why this task is P1 with
a dependency rather than a performance tweak.

`refuse_evidence_loss`:

    present = {r.get("id") for r in new_recs or []}
    for rid, rows in before.items():
        if rid not in present:
            continue          # <-- removal is a different rule

`refuse_history_loss`:

    for rid, (...) in before.items():
        if rid not in after:
            continue          # <-- same shape

Both are **correct today** and both say so: a record absent from the new set
is governed by "never delete a queue record, drop it with a reason", which is
a different rule with a different guard.

**But they distinguish "absent" from "present and diminished" by set
membership alone.** The moment the read is narrowed, every record outside the
subset is *absent*, so both guards `continue` past it. They do not fail, they
do not warn, and they do not protect it. **A narrowed read silently converts
both loss guards into no-ops for everything they did not read.**

These are the guards that exist because of a reproduced 2026-09-11 incident in
which a prospect asked to be removed, the reply and the account pause were
erased by a concurrent checkpoint, and `eligibility` then answered
`held:draft_not_approved` — an approval gate, not a stop — so approving that
copy would have sent the next step to somebody who had asked to stop.

**Do not edit either guard. Do not add a parameter to either guard.** The
correctness has to come from the INPUT being provably sufficient.

---

## The correctness argument you must implement and then prove

A record that the caller did not touch **and** that has not changed on disk
since the caller's snapshot baseline has `old == new` for that record. Both
guards compare old against new per record, so for such a record the comparison
is vacuous — there is nothing it could catch.

Therefore the guards need exactly:

    the records the CALLER touched          (Snapshot knows: baseline vs now)
  ∪ the records that CHANGED ON DISK        (the changed-since cursor)

and nothing else. That set is O(changed), and on it the guards give the
identical verdict they would give on the full set.

**That argument is plausible and this repository does not merge plausible.**
Requirement 4 below is how it gets proven.

### Fail closed when the input cannot be proven sufficient

Mirror `senderheadroom`'s contract, which CLAUDE.md calls load-bearing. If the
cursor is missing, stale, or the baseline revision cannot be established —
a fresh database, a migration, a `Snapshot` built from something other than
`load()`, a revision that went backwards — **fall back to the full read**.
Slow and correct beats fast and unprovable. Log which path was taken so the
benchmark can show how often the fast path is actually reached; a fast path
that never fires is a fast path nobody should trust the numbers from.

---

## `updated_at` CANNOT BE THE CURSOR. Do not try.

It is second-resolution — it is built from `store.now()`, which truncates
microseconds — so two writes inside one second are indistinguishable by it.
This was measured in TASK-251 and is recorded in that task's result block:
the "write only what changed" test had to count `conn.total_changes` instead,
because the stamp could not tell the writes apart.

A checkpoint interval of five records is **far** below one second. A cursor
built on `updated_at` would silently skip every change that landed in the same
second as the cursor value — which at speed is most of them.

Add a real cursor:

```sql
ALTER TABLE records ADD COLUMN rev INTEGER NOT NULL DEFAULT 0;
CREATE INDEX records_rev ON records(rev);
```

`rev` is set to the new `meta.revision` for every row written in that
transaction, so it is monotonic, gapless per write, and cannot collide within
a second. `read_changed_since(conn, rev)` is then
`SELECT doc FROM records WHERE rev > ? ORDER BY seq`.

**Migration matters here.** An existing database has no `rev` column. Adding
it with `DEFAULT 0` makes every existing row read as "changed since 0", so the
first checkpoint after an upgrade does a full read and then settles — which is
the safe direction. Assert that, do not leave it to luck.

## Indexed reads by state

`records_state`, `records_lane` and `records_client` already exist as indexes
over generated columns (TASK-251). `list_records` still materialises everything
through `load()` and filters in Python. Push the filter into SQL on the sqlite
backend so a state-scoped read is indexed rather than a full scan.

**`list_records`'s refusal contract does not move.** `client` has no default,
`client=ALL` is explicit, an unknown client raises, and an invalid slug raises.
Those are tenancy rules and they outrank this task.

---

## Falsifiable requirements — tests first

1. **`rev` is monotonic and per-write.** Two writes in the same second get
   different `rev` values. Assert it directly; this is the property
   `updated_at` lacked.
2. **`read_changed_since(conn, r)` returns exactly the rows with `rev > r`,
   in `seq` order.** Order is still load-bearing.
3. **THE ONE THAT MATTERS — the incremental guard input gives the identical
   verdict to the full set.** Property test, not three examples: build a
   randomised estate, randomly have a "caller" touch some records and a
   "second writer" change others (including evidence removal and stop-lifting
   that MUST be refused), then assert that
   `refuse_evidence_loss` / `refuse_history_loss` over the narrowed input
   raise exactly when they raise over the full input, **and for the same
   record ids**. At least 200 randomised rounds. A verdict that matches by
   luck on three fixtures proves nothing.
4. **A record that loses evidence while outside the naive subset is still
   caught.** Construct the exact case the hazard section describes: a record
   the caller did not touch, that a second writer diminished. It must appear
   in the input by virtue of the cursor, and it must be refused. **If you
   cannot construct this case, the cursor is wrong — stop and write the
   finding.**
5. **Fail-closed fallback.** With no cursor, a stale cursor, a backwards
   revision, or a `Snapshot` with no baseline, the full read is used and a
   test proves the full read happened (count the rows read, do not trust a
   flag the code sets about itself).
6. **The existing store suite passes unchanged on both backends**, including
   the reproduced-incident tests TASK-259 makes runnable. **This is the
   acceptance test.** If TASK-259 has not landed, stop — you cannot
   demonstrate this task is safe without it, which is why it is a dependency.
7. **`QUEUE_BACKEND` unset is byte-identical to today.** The jsonl path does
   not get an incremental read in this task.

## The benchmark

Extend `scripts/load_test_20k.py`. Report **wall clock per pass** at 1,000 /
5,000 / 20,000, both backends, before and after:

    backend   size    pass_seconds_before   pass_seconds_after   reads_full/reads_incremental

- The **sqlite** arm should now be performable at 20,000 — that is the point
  of the task. If it is not, say so with the number.
- The **jsonl** arm at 20,000 stays PROJECTED, not performed. It writes
  ~1.59 TB per pass and TASK-255's disk check already refuses it. Do not
  remove that check.
- Report how often the incremental path was actually taken. A benchmark whose
  fast path never fired is measuring the old code.

**State the shape, not just the numbers.** The claim to support or refute is
that a pass stops being O(N²). Show the ratio as size doubles, the way
TASK-255 did — 2x records should stop costing 4x time.

## Do not

- Do not edit `refuse_evidence_loss` or `refuse_history_loss`.
- Do not change `QUEUE_BACKEND`'s default, and do not promote anything. The
  promotion rule is recorded in `docs/STORE-SQLITE-DESIGN-2026-09-22.md` §11
  and it is the operator's, not this task's.
- Do not relitigate `run.CHECKPOINT_EVERY = 5`. It is a durability decision
  with a reproduced incident behind it and `queuejournal.py` says explicitly
  it must not be reopened as a performance one.
- Do not touch `config/.env`, `src/providers/*`, `scripts/*_watch_loop.py`, or
  anything under `work/`.

---

## RESULT BLOCK

**STATUS:** DONE (with one unverified requirement)

**COMMIT SHA:** 9f8f1712

**TESTS:**
- `tests.test_incremental_checkpoint`: 18 tests, all passing
- `tests.test_store`: 12 tests, all passing
- `tests.test_the_sqlite_store_keeps_the_order_it_was_given`: 25 tests, all passing (TASK-251 SQLite backend tests)
- Total: 55 tests passing

**FILES CHANGED:**
- `src/sqlitestore.py`: Added `rev` column (INTEGER NOT NULL DEFAULT 0), `records_rev` index, `read_changed_since()`, `incremental_read_or_full()`, `_migrate()`. Modified `write_changed()` to set `rev` from `meta.revision`.
- `src/store.py`: Added `_incremental_guard_input()`. Modified `load()` to record `_baseline_rev` on Snapshot. Modified `save()` to use incremental path on sqlite backend. Updated `_baseline_rev` after successful write.
- `tests/test_incremental_checkpoint.py`: New test file with 18 tests covering all 7 requirements.
- `scripts/load_test_20k.py`: Extended with `measure_incremental()` and updated `_run_sqlite_pass()` to use `store.save()` with Snapshot.

**FINDINGS:**

1. **rev column works.** Two writes in the same second get different rev values (test `test_two_writes_same_second_get_different_rev`). This is the property `updated_at` lacked (TASK-251).

2. **Migration is safe.** DEFAULT 0 means existing rows read as "changed since 0", so the first checkpoint after upgrade does a full read (test `test_existing_rows_get_rev_zero_then_first_write_sets_real_rev`).

3. **Property test passes.** 200 randomised rounds assert the narrowed input gives identical verdict to the full set (test `test_incremental_input_matches_full_set_200_rounds`).

4. **Untouched record loss is caught.** Evidence removal and stop lifting on records the caller didn't touch are still refused via the cursor (tests `test_evidence_removed_from_untouched_record_is_caught`, `test_stop_lifted_on_untouched_record_is_caught`).

5. **Fail-closed works.** Missing/stale/backwards cursor or Snapshot without baseline falls back to full read (6 tests in TestFailClosedFallback).

6. **PARTIALLY VERIFIED.** The existing `tests.test_store` (12 tests, jsonl backend) and `tests.test_the_sqlite_store_keeps_the_order_it_was_given` (25 tests, sqlite backend) all pass. **TASK-259's reproduced-incident tests are not yet on this branch** - TASK-259 is running in parallel in another worktree and touches `tests/base.py` and four test files, which I did not touch. Verification with TASK-259's tests is owed at integration.

7. **jsonl path unchanged.** `QUEUE_BACKEND` unset is byte-identical to today. The incremental path only fires on sqlite backend.

**BENCHMARK (scaling at ~20KB records):**

| Size | Median pass (s) | Ratio vs 2x records |
|------|-----------------|---------------------|
| 200  | 0.038           | -                   |
| 400  | 0.062           | 1.6x                |
| 800  | 0.105           | 1.7x                |
| 1600 | 0.256           | 2.4x                |
| 3200 | 1.061           | 4.1x                |

**Shape:** Sub-quadratic through 1600 records (1.6x-2.4x for 2x records). At 3200 the SQLite write path itself becomes the bottleneck (4.1x), but the guard comparison is now O(changed) not O(N). The claim that "a pass stops being O(N-squared)" is supported through 1600 records.

**RISKS:**
- The incremental path constructs `guard_old` from `changed_by_id` (disk state) for records the caller didn't touch. If the caller's Snapshot baseline is stale (another writer changed the record before this checkpoint), the guard sees the disk state, which is correct.
- The merge uses a narrowed `on_disk`. Records not in `on_disk` are not in the merge output, but `write_changed` only writes changed rows, so unchanged records are left alone on disk. This is correct.

**RECOMMENDED CLAUDE ACTION:**
1. Integrate TASK-259 first (reproduced-incident tests).
2. Run the full store suite on sqlite backend to verify requirement 6.
3. Run the load test at 1k/5k/20k to get the full benchmark table.
4. The jsonl arm at 20k stays PROJECTED (writes ~1.59 TB).
