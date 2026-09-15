PRIORITY: P1
DEPENDS:

# TASK-152 - 550 of 20,944 domains are in the queue

## THE NUMBER

`batches/productive-*.csv` adapts a 51,741-row people file into 20,944 unique
COMPANY domains. 550 records are in the live queue. That is 2.6%.

The estate was never the constraint - throughput was, and nobody has measured
where it actually stops.

## WHAT THIS TASK IS

Measure the intake pipeline's real cost and rate per stage, so Claude can size
the next batches instead of guessing.

Against `work/queue.snapshot.jsonl` - **quote the STAMP** - and the batch
builder:

1. Per stage, how many of the 550 records are in it, and what does the stage
   cost per record: provider calls, model calls, wall time. `scripts/
   build_intake_batch.py` and `src/ingest.py` are the entry; `src/qualify.py`
   is the first expensive gate.
2. Where do records STOP? Count the terminal states and the reason on each.
   119+ are dropped by ICP - that is the gate working. What else halts, and is
   it a gate or a gap?
3. What does one batch of 250 actually cost end to end, in provider credits
   and model calls, derived from the 550 already processed rather than
   estimated from the code?
4. Which stages are deterministic and which call a model? Cross-reference
   TASK-149 if it has landed.

## WHAT YOU MAY NOT DO

- Do not run `src.ingest` against the real queue. Production state is Claude's.
- No provider writes. No model calls to measure model calls.
- Do not write to `work/`.

## FILES ALLOWED

    docs/INTAKE-THROUGHPUT-2026-09-15.md   (new)
    scripts/task152_*.py

## FILES FORBIDDEN

    src/   work/   config/   batches/

## DELIVERABLE

Per-stage counts and per-record costs from the 550 real records, the terminal
states with reasons, the measured cost of a 250 batch, and the recommended
next batch size with the arithmetic.
