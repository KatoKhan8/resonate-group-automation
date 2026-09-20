# TASK-233 - the published benchmark command overwrites the live queue

## The defect, and it is a data-loss defect

`src/scalesim.py::measure` does:

    recs = synthetic.dataset(size, config)
    store.save(recs)

`store.save` with a plain list takes the whole-file branch - `_write(recs)`
then `os.replace(tmp, queue_path())`. The real `work/queue.jsonl` is
replaced by synthetic records.

`PRE-PRODUCTION.md` publishes the command:

    python -m src.scalesim --sizes 100,1000,5000

`SIZES = (100, 1000, 5000)` means **three successive overwrites** of the
production queue by anybody who runs the documented benchmark.

## Three guards were checked and all three let it through

    store.refuse_production_write   arms only when `unittest` is in
                                    sys.modules. From a normal shell
                                    `under_test()` is False and the target
                                    resolves to the real work/queue.jsonl.
    refuse_evidence_loss            skips ABSENT records by design
                                    (`if rid not in present: continue`)
    refuse_history_loss             likewise - "removal is a different rule"

5,000 synthetic ids share nothing with the 550 real ids, so every real record
is "absent" and both loss guards pass in silence. They are not broken; they
answer a different question.

## What is at stake

550 companies, 277 contacts, verification evidence, and the event history for
three live campaigns. **`work/` is gitignored, so there is no git recovery.**
The only artefact is a stale snapshot.

## The repository already contains the right pattern

`src/synthetic.py` makes the identical write an explicit `--write` opt-in.
`scalesim` does it with no flag and no warning. Read `synthetic.py` first and
follow what it already does rather than inventing a third convention.

## The objective

A synthetic scale benchmark must not be able to touch production storage,
and that must be true of the PUBLISHED command with no extra flag.

Falsifiable requirements:

1. `python -m src.scalesim --sizes 100,1000,5000` leaves `work/queue.jsonl`
   BYTE-IDENTICAL. Prove it by digest before and after, in a test, with the
   store pointed at a temp directory that stands in for production - do NOT
   prove it by running it against the real file.
2. The synthetic records are written somewhere real enough for the benchmark
   to measure honestly. `store.use_directory(tempfile.mkdtemp())` with a
   `finally` restore is the intended shape; a measurement that skips the
   write entirely is measuring the wrong thing and is NOT acceptable.
3. The restore happens even when `measure()` raises. Test it by making the
   body raise and asserting the store is pointed back.
4. Nested or repeated `measure()` calls do not leave the store pointed at a
   deleted temp directory. `SIZES` has three entries, so this runs three
   times in a row in the published command.
5. If you add an opt-in flag for writing to a named directory, it must not
   accept the production path. State how you enforce that.

## Explicitly NOT in scope

- Do not change `store.refuse_production_write`'s `unittest` trigger. It is
  load-bearing for the whole suite and widening it is a separate decision
  that Claude owns. Several other findings touch it; leave it alone.
- Do not change `refuse_evidence_loss` or `refuse_history_loss`. They are
  correct for the question they answer.
- Do not touch `src/synthetic.py`'s existing `--write` behaviour. Read it,
  match it, leave it.
- No provider calls of any kind. This task needs none, and
  `providers.refuse_unauthorized_write` will refuse a prospect-facing
  mutation anyway.

## Files you own

    src/scalesim.py
    tests/test_a_benchmark_cannot_overwrite_the_live_queue.py   (new)

Nothing else. If the work appears to need another file, stop and write why
under FINDINGS.

## Invariants

- `work/` is production state and is never written by a test. The barrier is
  `store.refuse_production_write`; a test that needs a store calls
  `store.use_directory(tempfile.mkdtemp())`.
- Test behaviour, not the text of the source.
- A red test is not proof by itself: when you break the fix deliberately to
  check the test, confirm the INTENDED test failed for the intended reason
  and that a different guard did not fire first.

## Result block, required

    STATUS
    COMMIT SHA
    TESTS              named modules, with the actual pass/fail counts
    FILES CHANGED
    FINDINGS
    RISKS
    RECOMMENDED CLAUDE ACTION

## Provenance

Found by the Buggie audit, 2026-09-20, finding #2, graded CRITICAL. The
reproduction in that report was read-only - the three guards were inspected,
not defeated against the real file. Reproduce it yourself against a temp
store before you fix it: a fix for a defect nobody reproduced is a guess.

## Result

    STATUS             DONE
    COMMIT SHA        8d1a6cf3
    TESTS             tests.test_a_benchmark_cannot_overwrite_the_live_queue:
                      10 passed, 0 failed
                      tests.test_scalesim: 17 passed, 0 failed (pre-existing,
                      all still green)
                      tests.test_explorer.TestTheScaleSimulation: 7 passed,
                      0 failed
                      tests.test_invariants: 82 passed, 1 failed (pre-existing
                      failure in test_emailbison_posts_only_to_routes_it_declares,
                      unrelated - confirmed by running against stashed changes)
    FILES CHANGED     src/scalesim.py
                      tests/test_a_benchmark_cannot_overwrite_the_live_queue.py (new)
                      docs/qwen-tasks/DONE/TASK-233-the-benchmark-overwrites-the-live-queue.md (moved from TODO/)
    FINDINGS          1. The defect is real and reproducible. Removing the
                         isolation wrapper causes the digest tests to fail
                         with different SHA-256 hashes before/after, proving
                         the queue was overwritten.
                      2. store.refuse_production_write only fires when
                         `unittest` is in sys.modules. From a normal shell,
                         the benchmark writes freely to work/queue.jsonl.
                      3. refuse_evidence_loss and refuse_history_loss are
                         correct for their question (known records losing
                         evidence/history) but structurally cannot catch a
                         total replacement with unknown ids.
                      4. The write_to parameter enforces production path
                         rejection by comparing the resolved absolute path
                         against store.PRODUCTION_WORK with both exact match
                         and prefix match (for subdirectories).
    RISKS             1. The _isolated_store context manager saves and
                         restores environment variables. If a new state
                         override is added to STATE_OVERRIDES but a caller
                         bypasses use_directory, it could still leak. The
                         save/restore covers the full tuple, so this is
                         defensive.
                      2. shutil.rmtree in the finally block uses
                         ignore_errors=True. On Windows, a held file handle
                         could leave temp files behind. This is the same
                         pattern used elsewhere in the codebase.
    RECOMMENDED       Integrate. The fix is minimal, the tests prove the
    CLAUDE ACTION     defect and its cure, and no existing behaviour changes
                      beyond isolating the benchmark's writes.
