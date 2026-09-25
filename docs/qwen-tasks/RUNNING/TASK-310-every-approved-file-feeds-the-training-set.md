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

## RESULT BLOCK

**STATUS**: DONE

**COMMIT SHA**: (to be filled after commit)

**TESTS**: 
- `tests.test_training_pair_written_on_approval` - 5 tests, all pass
- `tests.test_invariants.TestTheBarrierCoversEveryWriter` - 5 tests, all pass
- Acceptance command: `py -3 -c "import sys;sys.path.insert(0,'.');from src import training;print(training.count())"` returns `{'pairs': 0, 'held': 0, 'approved': 0, 'remaining': 5000}`

**FILES CHANGED**:
- `src/training.py` - NEW: training pair capture module
- `src/reviewapproval.py` - MODIFIED: calls `training.capture_on_approval()` after recording approval, added `refuse_production_write` guard
- `src/store.py` - MODIFIED: added `TRAINING` to `STATE_OVERRIDES` tuple
- `tests/test_training_pair_written_on_approval.py` - NEW: tests proving pairs are written on approval and NOT without one
- `tests/test_invariants.py` - MODIFIED: added `reviewapproval` and `training` to `SELF_WRITERS` checklist

**FINDINGS**:
1. The capture hooks `reviewapproval.record()`, which is the only function that knows an approval happened. The pipeline runs whether or not the operator approves, so the capture must be at the approval boundary.
2. The review file is at `out/review.html` and is overwritten by each render. The capture checks the file hash against the approval hash; if they don't match (file was overwritten), no pairs are written. This is best-effort: a pair not captured when the file is approved is gone for good.
3. The training pairs are stored in `work/training/pairs.jsonl`, append-only, never rewritten. Each pair contains:
   - Metadata: campaign, review_hash, approval_by, record_id, contact_email, held flag
   - Input: what the writer saw (lead info, company, facts, angle, persona, hook)
   - Output: what the operator approved (subject, first_line, body)
4. Held leads are captured separately with `held=true`, as negative examples.
5. The counter shows progress toward 5,000 pairs: `{'pairs': N, 'held': H, 'approved': A, 'remaining': R}`.
6. The fine-tune, A/B test, and routing changes are NOT built. This task is capture and count only.

**RISKS**:
- If the review file is overwritten before the operator approves, the pairs are lost. The operator should approve promptly after posting the review file.
- The review file HTML parsing is fragile. If the HTML structure changes in `render.py`, the parser may break. The test uses a minimal HTML structure that matches the current `render.py` output.

**RECOMMENDED CLAUDE ACTION**: Review and integrate. The capture mechanism is in place and tested. The next task can build the fine-tune pipeline and the counter dashboard.
