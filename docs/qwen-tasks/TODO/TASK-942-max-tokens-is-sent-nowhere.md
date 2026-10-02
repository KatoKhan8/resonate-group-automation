PRIORITY: P1
SIZE: S
DEPENDS: task-step-objectives-convergence

# TASK-942 — `max_tokens` is sent nowhere, so the writer's answers get truncated

Found by the golden-path run on master `eeead37d`, 2026-10-02, and confirmed by grep on both sides.

## The defect

`grep -c max_tokens src/generate.py` returns **0 on master and 0 on
`task-step-objectives-convergence`**. The writer is never told how long its answer may be, so a long
completion is cut mid-JSON.

What happens next was measured in the golden-path run: the truncated completion raises
`JSONDecodeError` inside `_parse_json`, `_process_contact` catches it with a broad `except Exception`
(`src/generate.py:2356`, `:2486`, acknowledged in the comment at `:2730`), and the record ends
`hold_kind="error"` after ONE attempt — spending the whole ten-retry budget that exists for exactly
this case.

## What is already fixed, and what is not

- The retry ACCOUNTING is fixed on `task-step-objectives-convergence`:
  `tests/test_a_truncated_answer_costs_one_attempt_not_the_round.py` is PRESENT on that branch and
  ABSENT on master. A truncated answer there costs one attempt, not the round — measured live during
  a bigfish generation run, which failed on
  `JSONDecodeError: Expecting ',' delimiter: line 1 column 2724` and continued.
- The CAUSE is not fixed anywhere. Nothing sets `max_tokens`, so answers keep getting truncated and
  the fix above only makes the symptom cheaper.

## Acceptance

1. The writer call carries an explicit token budget, chosen from the shape of what is being asked
   for rather than a round number, and the choice is justified in a comment with the measurement
   behind it.
2. Prove by EFFECT that a budget too small for the requested JSON produces a NAMED refusal rather
   than a `JSONDecodeError` swallowed by a broad `except`. The caller must be able to tell "the model
   was cut off" from "the model answered something unusable".
3. The broad `except Exception` at `:2356` and `:2486` must stop hiding a truncation. Narrow it or
   classify before it, but do not widen anything else; this repo's rule is to fail closed and name
   the class.
4. A test that fails before the change: a stubbed model returning a deliberately truncated JSON
   payload must yield the named refusal, and must cost one attempt rather than the round.
5. Do not change any lint threshold, gate or assertion.

## Note on sequencing

Merging `task-step-objectives-convergence` first is what makes this measurable: on master nothing
generates at all, because `step_objective_block` has 0 occurrences there, so every Productive record
is refused at `sequencegate.step_objectives` before truncation can even be observed.
