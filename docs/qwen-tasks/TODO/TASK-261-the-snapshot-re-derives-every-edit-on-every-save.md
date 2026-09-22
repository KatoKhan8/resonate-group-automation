PRIORITY: P1
DEPENDS: TASK-260

# TASK-261 — `Snapshot` re-serialises every record on every save

**This is why a pass is still O(N²) after TASK-260, and it is not the storage
backend.** Measured 2026-09-22,
`docs/BENCHMARK-PASS-WALL-CLOCK-2026-09-22.md`:

    size    backend   seconds   ratio
    1,000   sqlite      60.53   -
    5,000   sqlite   1,522.58   25.2x   <- 5 squared is 25

Quadratic to two significant figures, with the incremental read in place.

## The cause, exactly

Two full-set JSON serialisations per checkpoint, both in `Snapshot`, both
independent of which backend is active:

    src/store.py:470   Snapshot.merge_onto
        frozen = {row[self.key]: _frozen(row) for row in self}

    src/store.py:604   _incremental_guard_input
        for rec in snapshot:
            if snapshot.baseline.get(rid) != _frozen(rec):

Each walks every record the caller holds and serialises it, to work out which
ones the caller edited. At the measured production mean (19,819 bytes) a
5,000-record pass does 1,000 checkpoints × 2 × ~99 MB ≈ **198 GB of in-memory
JSON serialisation** to change 5,000 records.

**It explains TASK-255 retrospectively too.** That benchmark found jsonl,
journal and sqlite all O(N²) and blamed the O(N) disk read. The read is O(N),
but `Snapshot` is O(N) on every arm — which is why three backends with wildly
different I/O had the same shape.

## The objective

A checkpoint costs what it changed. `Snapshot` should know which rows were
edited without re-deriving it from scratch.

## Read this before designing it

`Snapshot`'s docstring records a REPRODUCED INCIDENT and the design that
followed from it: a batch checkpoints many times, and if the baseline does not
move with each write, every later checkpoint re-asserts every field the caller
has EVER touched. The reproduction is in `rebase`'s docstring — a drop landed
as `state: enriched` with `drop_reason` still set, `validate` returned no
problems, and the record was worked again.

**So whatever replaces the serialisation must preserve:**

1. `rebase()` moving the baseline to what was just written, after a
   successful write and only then. A refused checkpoint must leave the caller
   still holding unpersisted edits.
2. The three-way merge's exact field-level semantics: absent → kept,
   unchanged since read → disk wins, changed by us alone → ours, changed by
   both → field by field.
3. A plain `list` still falling back to whole-file semantics. That is
   deliberate: a caller that built its rows from somewhere other than `load()`
   has no baseline, and inventing one would be a guess.
4. `merge_onto` refusing a row with no key rather than skipping it.

## Approaches, and the trap in the obvious one

**The obvious one is mutation tracking** — have `Snapshot` notice writes. It
cannot, straightforwardly: callers mutate the record dicts in place
(`store.get(rid, recs)["contacts"].append(...)`), and `Snapshot` is a `list`
subclass that never sees those. A `__setitem__` hook catches almost nothing.

**A dirty-set the callers maintain** is a second representation of the same
truth, which CLAUDE.md warns produces drift, and it puts correctness in the
hands of every caller rather than in one place.

**Cheaper identity is the promising direction**: hash each row once at read
time and compare a cheap digest rather than re-serialising. It is still O(N)
walks but with a much smaller constant — and if that is all that is achievable
without weakening the contract, **say so with the measurement rather than
forcing a design**. A 10x constant-factor win on a quadratic is still
quadratic, and the result block should be honest about which was achieved.

## Falsifiable requirements

1. **The existing store suite passes unchanged, on BOTH backends.** 277 tests
   are green at `54619fc1`; that is the floor, not the target.
2. **A randomised property test, at least 200 rounds**, that the new edit
   detection selects exactly the same rows as the current
   `frozen`/`baseline` comparison, over estates where callers touch nested
   structures in place — contacts, events, cadence, log — not just top-level
   fields. In-place nested mutation is the case the obvious designs miss.
3. **The drop-reversion reproduction still fails on a broken baseline.**
   Re-create `rebase`'s scenario: checkpoint `state: enriched`, have another
   process `drop()`, checkpoint again. It must not resurrect the record.
   Break `rebase` deliberately and confirm this test catches it.
4. **Re-run the benchmark** at 1,000 and 5,000 on sqlite and report the
   ratio. The claim to support or refute is that 25.2x moves toward 5x.
   State the shape, not just the seconds.
5. Both loss guards are untouched.

## Do not

- Do not weaken `Snapshot`'s merge contract to make it faster. The incident
  in its docstring cost a reply, an unsubscribe, a drop reason and three
  purchased decision-makers.
- Do not change `run.CHECKPOINT_EVERY`. It is a durability decision and
  `queuejournal.py` says explicitly it must not be reopened as a performance
  one.
- Do not promote anything. Promotion condition 2 depends on this task, and
  the rule is `docs/STORE-SQLITE-DESIGN-2026-09-22.md` §11.
- Do not touch `config/.env`, `src/providers/*`, `scripts/*_watch_loop.py` or
  anything under `work/`.
