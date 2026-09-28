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
