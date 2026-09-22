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

## THE ACCEPTANCE CRITERION IS THE BENCHMARK, NOT THE TEST SUITE

Operator, Zvonimir, 2026-09-22:

> *Acceptance is the benchmark itself: re-run 1k and 5k on sqlite after it
> lands; the ratio must be near 5x, not 25x. Only then run 20k.*

So:

    1,000 sqlite   measured today   60.53 s
    5,000 sqlite   measured today   1,522.58 s   = 25.2x

    PASS  the 5k/1k ratio is near 5x
    FAIL  it is still near 25x

**A green test suite is necessary and not sufficient.** TASK-260 shipped 18
green tests and did not move this ratio at all; that is exactly the outcome
this criterion exists to prevent. Report the two seconds figures and the
ratio, and if the ratio has not moved, say so plainly rather than reporting
the tests.

**Do not run 20,000 until the ratio passes.** At 25x it is ~6.8 hours for one
pass and it proves nothing the ratio has not already settled. Once the ratio
is near 5x, run it — that is the number the promotion decision actually wants.

Run it detached, to a file, with no `timeout` wrapper. The 5,000 arm takes
~25 minutes at today's shape.

## The direction, and the trap in the obvious version of it

Operator's direction: **track dirty ids at write time, or diff only the ids
the caller touched.** Both are right and the second reduces to the first —
"the ids the caller touched" is not knowable without either tracking them or
re-deriving them, and re-deriving them is the O(N) this task exists to remove.

So: **track them.** And here is the trap, which is why this is a task and not
a patch.

`Snapshot` is a `list` subclass, so a `__setitem__` hook on the LIST catches
almost nothing — callers do not replace rows, they mutate them:

    store.get(rid, recs)["state"] = "enriched"          # dict __setitem__
    store.get(rid, recs)["contacts"].append(person)     # nested LIST mutation
    rec["cadence"]["day1"]["body"] = "..."              # nested, two deep

The first is catchable with a tracking dict. **The second and third are not,
unless the nested containers are tracked too.** A design that catches only
top-level assignment will pass a casual test, show a beautiful benchmark, and
**silently stop detecting the edits that carry contacts, events and cadence** —
which is to say, it will silently stop feeding the loss guards the records
that matter most. That failure is invisible until somebody loses a reply.

So a tracking container has to propagate: the dict marks its record dirty, and
so does every list and dict reached through it. Requirement 2 below is written
to catch exactly this and it is the requirement to write first.

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
