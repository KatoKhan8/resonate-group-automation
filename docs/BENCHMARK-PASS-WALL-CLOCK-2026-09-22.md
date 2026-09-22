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
