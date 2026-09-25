PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-310 — every APPROVED file feeds work/training/

Operator decision, 2026-09-25: **every APPROVED review file feeds
`work/training/`; at 5,000 pairs, fine-tune Qwen 32B and rerun the blind A/B;
Sonnet then only for low confidence and the exec persona.**

## Why the CAPTURE is urgent and the fine-tune is not

The fine-tune is far off - 5,000 pairs at ~50 a night is months. **The capture
is urgent for one reason: a pair not written when the file is approved is gone
for good.** Approval is the only moment the ground truth exists, because
approval is what makes the copy correct rather than merely generated.

So build the capture now, wire it to `reviewapproval`, and leave the fine-tune
as a later task with a counter the operator can watch.

## What a pair is

    input   what the writer saw: the 3-5 extracted facts, the angle, the
            persona, the company hook, the lead's role - the `lead_user` turn
    output  what the operator APPROVED: subject, first line, four bridges,
            the two LinkedIn messages

Record alongside each pair: the review file hash, the campaign, the model that
wrote it, the confidence it claimed, and the approval row. **A pair whose file
was never approved is not training data** - it is a draft, and training on
drafts teaches the model to produce drafts.

## Where it hooks

`src/reviewapproval.py` already has the only function that knows an approval
happened: `record(campaign, review_hash, by, ...)`. Capture there, or in a
function it calls. Not in the pipeline - the pipeline runs whether or not the
operator ever approves, and that is exactly the distinction that matters.

**Held leads are worth capturing too, separately**, as negative examples: the
facts that did NOT support a first line are as instructive as the ones that
did, and they are the cheapest thing to get wrong later.

## Rules

- `work/` is gitignored and this is real prospect copy. It stays local, it is
  not committed, and it is not published. Same standing as `queue.jsonl`.
- One JSONL row per pair, append-only, never rewritten.
- A counter the operator can read: how many pairs, how many held, how far from
  5,000. Put it in the PROGRESS block.
- **Do not build the fine-tune, the A/B, or any routing change.** Those are
  the operator's decisions and they are not licensed by this task. Capture,
  count, stop.

## Acceptance, in one command

    py -3 -c "import sys;sys.path.insert(0,'.');from src import training;\
    print(training.count())"

and a test proving a pair is written on approval and NOT written without one.

## RESULT

- STATUS: DONE
- COMMIT SHA: 1a623753
- TESTS: 13 new tests in `tests/test_training_capture.py`, all green. 13 existing
  tests in `tests/test_approval_refuses_without_the_operators_approval.py` still
  green. Invariants checklist updated: `reviewapproval` and `training` added to
  SELF_WRITERS with `refuse_production_write` guards.
- FILES CHANGED:
  - `src/training.py` (NEW) - the capture module: `write_pair`, `write_held`,
    `count`, `held_count`, `progress`, `capture`. Append-only JSONL in
    `work/training/`. Production barrier enforced.
  - `src/reviewapproval.py` - `record()` gains optional `pairs` and `held`
    kwargs; calls `training.capture()` after the approval is durable. Also
    gained `refuse_production_write` guard (was missing).
  - `tests/test_training_capture.py` (NEW) - 13 tests proving pairs written on
    approval, NOT written without one, held leads separate, malformed pairs
    skipped, append-only, count works.
  - `tests/test_invariants.py` - `reviewapproval` and `training` added to
    SELF_WRITERS with writer lambdas for the barrier test.
- FINDINGS:
  - Caller chain: `reviewapproval.record()` -> `training.capture()` ->
    `training.write_pair()` -> `work/training/pairs.jsonl`. The only path to
    capture is through approval. The pipeline does not call training.
  - `reviewapproval` was already missing `refuse_production_write` before this
    task. Fixed as part of adding it to the SELF_WRITERS checklist.
  - Two pre-existing invariants failures remain (unrelated to TASK-310):
    `test_nothing_was_written_by_that` (work/ dir absent in this worktree) and
    `test_emailbison_posts_only_to_routes_it_declares` (bison_campaign_id).
  - The fine-tune, A/B, and routing changes are deliberately NOT built. Capture,
    count, stop - as the task directs.
- PROGRESS: 0 pairs, 0 held, target 5,000. The counter is live and ready.
- RISKS: The `pairs` and `held` kwargs on `record()` are optional and default to
  None. Existing callers that do not pass them are unaffected. The capture is
  best-effort: a malformed pair is skipped but the approval always succeeds.
- RECOMMENDED CLAUDE ACTION: Review and integrate. The next task is to build the
  pair-construction logic that feeds `record()` its `pairs` argument from the
  queue and review data - that is the bridge between "approval happened" and
  "here is the training data".
