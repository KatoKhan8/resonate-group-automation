# TASK-040 - What gets slow first, and at what size

Operator backlog: QWEN-23 and QWEN-24. Read TASK-004's result first if it is
DONE - do not repeat its measurements.

## GOAL

Find the first thing that breaks as the estate grows, by measuring rather than
by reading code.

## WHY IT MATTERS

The estate is 300 records. The operator's target is a large TAM processed as a
stream, and `STREAMING-ARCHITECTURE.md` describes that phase. Before designing
for it, somebody has to know which operation actually falls over first - a
speedup applied to something that was never the bottleneck is churn, and the
repository has explicit guidance against exactly that.

## CURRENT FACTS

- `work/queue.jsonl` is 9.6MB for 300 records, so roughly 32KB each.
- `store.load()` reads the whole file and `store.save()` writes it whole. The
  handoff records that two concurrent generation runs cannot overlap because
  of it, and that a crashed run left a 9.6MB `.tmp` file behind.
- `store.refuse_history_loss` compares event logs on every write.

## SCOPE

1. Synthetic estates at 300, 1K, 5K and 30K records. Generated, never copied
   from the real estate.
2. Time the operations that run per batch: `store.load`, `store.save`,
   `refuse_history_loss`, the funnel computation, `cadence.steps_for` across
   an estate, and the planner.
3. Report the SHAPE, not just the number: which are linear, which are
   quadratic, and where memory goes. A quadratic at 300 records is invisible
   and at 30K is fatal.
4. Name the FIRST operation to become unusable and at what size. One answer,
   with the measurement behind it.
5. Do not optimise anything in this task. Measuring and fixing in one pass is
   how a benchmark gets written to flatter a fix.

## PRODUCTION BOUNDARY

ZERO network. ZERO credentials - `config/.env` does not exist in this
worktree and a task that tries to obtain one has misunderstood its job. No
provider call. No write to `work/**`. Nothing is staged, activated or sent.

## HANDOFF FORMAT

Return ONLY this, concisely:

    STATUS / COMMIT SHA / FILES CHANGED / TESTS RUN / TEST RESULTS /
    BUGS FOUND / BUGS FIXED / RISKS / OPEN QUESTIONS /
    RECOMMENDED CLAUDE ACTION

Plus, required of every task since 2026-09-14: the output of
`grep -rn "<each new name you added>" src/` proving it is CONSUMED, and
confirmation that deleting the CALL to your new code makes a test fail.

## TESTS REQUIRED

- the synthetic generator produces records the real code paths accept - prove
  it by running the funnel over a synthetic estate;
- the timing harness is deterministic enough to compare runs, and says how it
  handles variance.

## DONE CONDITION

A table of operation against estate size, the complexity shape of each, and a
single named answer to "what breaks first".
