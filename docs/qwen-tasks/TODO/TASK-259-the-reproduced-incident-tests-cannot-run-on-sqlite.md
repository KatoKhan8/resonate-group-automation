PRIORITY: P1
DEPENDS: TASK-253

# TASK-259 — the reproduced-incident tests structurally cannot run on the SQLite backend

**This is the gate on promoting `QUEUE_BACKEND=sqlite`.** Found while
reviewing TASK-253 on branch `infra`, 2026-09-22.

## What was measured

TASK-253's brief named the real acceptance test: *"Parameterise the existing
store tests over both backends; that is the real acceptance test for this
task."* What landed instead is hand-written `_jsonl` / `_sqlite` pairs
covering the happy path. Running the real thing:

    QUEUE_BACKEND=sqlite py -3 -m unittest \
      tests.test_a_batch_does_not_erase_what_arrived_during_it \
      tests.test_a_merge_does_not_unbuy_evidence \
      tests.test_a_checkpoint_costs_what_it_changed

    3 failures:
      test_contacts_bought_mid_batch_are_not_erased
        "two paid decision-makers ... were erased by the batch snapshot"
      test_a_refused_checkpoint_leaves_the_edit_pending    QueueLocked not raised
      test_a_refused_write_leaves_no_stale_handover        QueueLocked not raised

## IT IS NOT DATA LOSS. Read this before investigating.

All three are **test-mechanism artifacts** and the backend is not implicated.
Diagnosed, not assumed:

- `test_contacts_bought_mid_batch_are_not_erased` simulates a second writer
  with `store._write(live)` — the private JSONL writer. Under the sqlite
  backend `save()` calls `_write_sqlite`, so the fixture writes to a JSONL
  file nothing reads, and the "concurrent write" never happened.
- the two `QueueLocked` tests monkeypatch `store._write` to raise. Under
  sqlite that function is not on the path, so the patch never fires.

**Do not "fix" the backend.** There is nothing wrong with it that these
failures demonstrate. Do not weaken or delete these tests either: they encode
the 2026-09-12 incident where a batch checkpoint erased a reply, an
unsubscribe, a drop reason and three purchased decision-makers, and they are
among the most valuable tests in the repository.

## What it actually means, which is worse

**The concurrency semantics that matter most are UNPROVEN on the sqlite
backend, and nothing in the repository can currently prove them.** The
three-way merge, `refuse_evidence_loss`, `refuse_history_loss` and the
checkpoint/rebase ordering are all exercised only on JSONL, because every test
that drives them reaches past the public interface to do so.

Four test files reach `store._write()` directly:

    tests/test_a_batch_does_not_erase_what_arrived_during_it.py
    tests/test_approve.py
    tests/test_double_verification.py
    tests/test_the_provider_acting_alone_is_still_a_touch.py

## The objective

A second writer that writes through **whatever backend is active**, so these
tests can run on both — and then they do.

Falsifiable requirements:

1. A helper in `tests/base.py` — `write_as_another_process(recs)` or similar —
   that persists a record set through the ACTIVE backend without going through
   `save()`'s merge. On jsonl that is today's `store._write`; on sqlite it is
   `_write_sqlite`. **One definition**, because two places that know how to
   write are two places that can disagree, which is the whole hazard
   `_current_records` exists to close.
2. The four files above use it instead of `store._write`. Behaviour on the
   default backend must be **identical** — assert that by running them
   unchanged first and diffing the result.
3. The refusal tests need the same treatment: patching `store._write` to raise
   only fires on one backend. Make the refusal injectable per backend, or
   assert the refusal at a level both share.
4. **Then parameterise for real.** Those tests run under both
   `QUEUE_BACKEND=jsonl` and `QUEUE_BACKEND=sqlite`, and pass under both.
   That is the deliverable; steps 1-3 are how you get there.
5. If any of them FAILS on sqlite once the mechanism is fixed, **stop and
   write the finding**. That is a real defect in the backend and it is
   exactly what this task exists to find. Do not fix it in the same diff —
   a storage defect found by a concurrency test deserves its own reproduction
   and its own review.

## Do not

- Do not edit `refuse_evidence_loss` or `refuse_history_loss`.
- Do not change `QUEUE_BACKEND`'s default. `jsonl` stays canonical.
- Do not promote anything. Promotion is an operator decision against a clean
  shadow ledger, and this task is the evidence that decision will need, not
  the decision.
- Do not touch `config/.env`, `src/providers/*`, `scripts/*_watch_loop.py` or
  anything under `work/`.
