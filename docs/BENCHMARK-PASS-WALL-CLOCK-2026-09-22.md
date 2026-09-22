# Wall clock per pass, both backends — measured 2026-09-22

Operator asked for 1k / 5k / 20k on both backends, run detached with no
timeout wrapper. Here are the numbers, and they say TASK-260 did not achieve
its goal.

A **pass** is what `run.py` does: N/5 checkpoints, five records changed each,
every one going through `store.save()` with the full guard path. Records are
generated at the measured production distribution (mean 19,819 bytes).

---

## The numbers

    size    backend   seconds   ratio vs 5x records
    1,000   sqlite      60.53   -
    5,000   sqlite   1,522.58   25.2x
    1,000   jsonl       88.36   -
    5,000   jsonl        n/a    PROJECTED — ~99.5 GB written, refused
    20,000  either       n/a    NOT RUN — see below

**5² = 25. The measured ratio is 25.2.** That is not "close to quadratic", it
is quadratic to two significant figures. **The incremental checkpoint read did
not change the shape at all.**

The 20,000 arm was stopped before it began. At this shape it is 16x the 5,000
figure — **about 6.8 hours for one pass** — and running it would have told us
nothing the ratio above has not already established. That is a projection, and
it is labelled as one.

For context, the jsonl arm is *slower* than sqlite at 1,000 (88s vs 61s) and
becomes unrunnable above it: TASK-255's disk check refuses ~99.5 GB at 5,000
and ~1.59 TB at 20,000.

---

## Why it is still quadratic, and it is not the storage backend

TASK-260 narrowed the DISK read. It left **two full-set JSON serialisations
per checkpoint, both in `Snapshot`, both independent of which backend is
active**:

    src/store.py:470   Snapshot.merge_onto
        frozen = {row[self.key]: _frozen(row) for row in self}

    src/store.py:604   _incremental_guard_input
        for rec in snapshot:
            if snapshot.baseline.get(rid) != _frozen(rec):

Each walks **every record the caller holds** and serialises it to JSON, to
work out which ones the caller edited. At the measured mean that is ~20 MB of
serialisation per record set, twice, on every checkpoint.

At 5,000 records: 1,000 checkpoints × 2 × ~99 MB ≈ **198 GB of in-memory JSON
serialisation** for a pass that changes 5,000 records. The disk did not do
that work — the CPU did, and no storage backend can help.

**This also explains TASK-255's result retrospectively.** That benchmark found
all three arms — jsonl, journal and sqlite — were O(N²), and attributed it to
the O(N) read per checkpoint. The read is O(N) as well, but `Snapshot` is
O(N) on every arm, which is why all three had the same shape despite wildly
different I/O. The storage layer was never the whole story.

---

## What this means for promotion

**Condition 2 of the promotion rule (`docs/STORE-SQLITE-DESIGN-2026-09-22.md`
§11) is NOT met.** TASK-260 is merged and its tests are green, but the goal it
was set — "a checkpoint reads O(changed), not O(N)" — is achieved for the
guard input and not for the pass. A pass is still O(N²).

`QUEUE_BACKEND=sqlite` stays blocked, as recorded. Nothing here changes
conditions 1, 3 or 4.

**What SQLite has actually bought, stated honestly:** write volume, which is
not nothing. TASK-255 measured 1.59 TB projected for jsonl at 20k against
188 KB for sqlite — a difference in write endurance of four orders of
magnitude, and the reason `work/queue.jsonl` will not survive 20k records
whatever else is true. It has not yet bought wall clock.

---

## Next: TASK-261

`Snapshot` re-derives its edit set from scratch on every save. It should track
edits as they are made, so a checkpoint costs what it changed. That is a
change to a class whose docstring records a reproduced drop-reversion
incident, so it is a task with a property test, not a drive-by optimisation.

## How to reproduce

    py -3 <scratch>/bench/run.py > out.txt 2> err.txt

Detached, no `timeout` wrapper. The 5,000-record sqlite arm takes ~25 minutes;
the 20,000 arm is not worth running until TASK-261 lands.

---

# RE-MEASURED AFTER TASK-261 — 2026-09-22, later the same day

`Snapshot` now tracks dirty ids instead of re-serialising every record twice
per checkpoint. Same benchmark, same machine, detached, no `timeout` wrapper.

    size     backend   BEFORE 261    AFTER 261    speedup
    1,000    sqlite        60.53 s       5.04 s     12.0x
    5,000    sqlite     1,522.58 s      55.24 s     27.6x
    20,000   sqlite     ~6.8 h (proj)  707.73 s     ~35x
    1,000    jsonl         88.36 s      32.81 s      2.7x

    20,000 sqlite = 11 minutes 48 seconds, MEASURED, not projected.

**A 20,000-record pass now completes in under twelve minutes.** It was
projected at nearly seven hours this morning. That is the number the promotion
decision wanted and it now exists.

## THE ACCEPTANCE CRITERION IS STILL NOT MET, AND I AM NOT ROUNDING IT

The operator set it precisely: *the 5k/1k ratio must be near 5x, not 25x.*

    before 261   1,522.58 / 60.53  =  25.2x
    after  261      55.24 /  5.04  =  11.0x
    target                            ~5x

**11.0x is not near 5x.** The shape improved from ~N² to ~N^1.65 and it is
still superlinear. By the criterion as written, **TASK-261 does not pass**,
and the worker said so itself: its own STATUS line reads PARTIAL PASS.

### Where the remaining superlinearity is

TASK-261's own isolating measurement, holding checkpoints constant at 200:

    1,000  8.07 s     2,000  9.48 s     3,000  11.06 s     5,000  12.20 s
                                                            -> 1.51x for 5x

**The per-checkpoint save path is sub-linear.** What remains is that a pass
over 5x the records performs 5x more checkpoints, because
`run.CHECKPOINT_EVERY` is 5 — so even a perfectly O(changed) checkpoint gives
a pass that grows with N. The residual above linear is whatever per-pass work
still touches all N.

`CHECKPOINT_EVERY` is not available as a lever: it is a durability decision
with a reproduced incident behind it and `queuejournal.py` says explicitly it
must not be reopened as a performance one.

## What this changes for promotion

**Nothing automatically.** Condition 2 in
`docs/STORE-SQLITE-DESIGN-2026-09-22.md` §11 says "TASK-260 green", and the
substance of it — a checkpoint that reads O(changed) — is now delivered for
the save path and not for the pass.

**That is an operator call, not mine**, and it is the only one outstanding:
whether 11.8 minutes at 20,000 records satisfies the intent of a criterion
written as a ratio. The numbers are above; the verdict is not mine to record.

If the answer is "not yet", the next lever is the residual per-pass O(N) work
rather than anything in the storage layer — and it should be found by
profiling a pass rather than by guessing, because two guesses about this have
already been wrong.


---

# THE HOTSPOT, PROFILED AND FIXED — 2026-09-22, third measurement

The operator's rule was: above 10x, **name the next hotspot from a profile, do
not guess.** Profiled a pass at 1,000 and 3,000 records, two sizes so that a
function which GROWS with N is distinguishable from one that is merely
expensive.

    cumulative seconds        1,000     3,000    scaling (3x records)
    save                       4.375    27.675     6.3x
      _incremental_guard_input 2.270    17.335     7.6x
        read_changed_since     1.506    12.388     8.2x   <-- HOTSPOT
      _write_sqlite            1.266     7.744     6.1x
      merge_onto               0.205     0.622     3.0x   <-- exactly linear

`merge_onto` scaling 3.0x for 3x records is TASK-261's dirty tracking working
perfectly. `read_changed_since` at 8.2x, and 45% of the whole pass, is what
was left.

## The cause, from EXPLAIN QUERY PLAN rather than from reasoning

    SELECT doc FROM records WHERE rev > ? ORDER BY seq  ->  SCAN records
    SELECT doc FROM records WHERE rev > ?               ->  SEARCH records
                                                            USING INDEX
                                                            records_rev (rev>?)

**`ORDER BY seq` defeated the `records_rev` index.** `seq` is the primary key,
so ordering by it is free IF the table is walked in primary-key order — and
SQLite took that trade, walking all N rows and filtering, rather than seeking
the index and sorting a handful.

It did this **even when nothing matched**. 50 calls against 5,000 rows with
zero matching rows: 0.009s ordered, 0.000s unordered.

O(N) per checkpoint x N/5 checkpoints = O(N²), sitting inside the function
written to remove exactly that.

**Fix:** drop the `ORDER BY` from the SQL and sort the result in Python. The
result set is O(changed) and therefore small; the order is still preserved,
just not by making the database prove it over every row it did not select.

## THE ACCEPTANCE CRITERION IS NOW MET

    size     backend   this morning   after 261    after the index fix
    1,000    sqlite         60.53 s      5.04 s              3.74 s
    5,000    sqlite      1,522.58 s     55.24 s             20.77 s
    20,000   sqlite     ~6.8 h proj    707.73 s            126.91 s

    5k/1k ratio    25.2x    ->    11.0x    ->    5.55x     TARGET ~5x  PASS
    20k/5k ratio                                 6.11x

**5.55x for 5x the records.** The operator's criterion was "near 5x, not 25x".

**A 20,000-record pass now takes 2 minutes 7 seconds**, measured, against a
projection of nearly seven hours this morning — about 193x.

Per the operator's instruction, this goes into the promotion evidence.
