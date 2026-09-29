# S7 Four-Step Render Verification

**Date:** 2026-09-25 (updated for five-step cadence)
**Task:** TASK-283
**Script:** `scripts/verify_s7_render.py`
**Tests:** `tests/test_the_four_step_render_has_every_variable.py`

## Purpose

When S7 re-renders all rows for the cadence, every row must carry every
variable the provider sequence will ask for. A row that does not must be
HELD rather than sent with a gap in it.

`bisonfactory` refuses when the provider sequence keys and the cadence keys
disagree, but it refuses in a place that does not name the cause. This
verifier runs BEFORE the push attempt and names the cause.

## What the verifier checks

### 1. Set diff of cadence keys vs sequence keys (both directions)

The cadence declares email step keys (e.g., `em1, em2, em3, em4, em5`).
The `email_sequence.steps` config declares its own keys. These must be
the same set. A count is not a diff: `{em1, em2, em3, em4}` and
`{em1, em2, em4, em5}` have the same length but differ in two positions.

The diff is printed in BOTH directions:
- Keys in cadence but NOT in sequence (the cadence was lengthened without
  updating the sequence)
- Keys in sequence but NOT in cadence (the sequence was updated without
  matching the cadence)

### 2. Per-variable coverage of the journal

For each variable the provider sequence templates reference (`SUBJECT_1`,
`BODY_1`..`BODY_5`), the verifier counts:
- **present**: the variable has a non-empty, non-placeholder value
- **empty**: the variable is present but blank
- **None**: the variable carries the literal string `'None'`
- **unrendered**: a `{PLACEHOLDER}` survived the render

Empty and `'None'` are both refusals but have different causes. The report
does not merge them.

### 3. Threading invariant

`thread_reply_pattern` must have exactly as many entries as the cadence has
email steps. The first entry must be `false` (the opener owns the subject).
A three-entry pattern against a five-step cadence is the pre-change value
and is refused with a message naming the cause.

### 4. Final step wait_in_days

The final step's `wait_in_days` must be 1, never 0. Campaign 485 was left
at 0 steps by exactly this: the provider rejected the sequence.

### 5. Exit non-zero on any bad row

When any rendered row would reach the provider with an empty, `'None'`, or
unrendered variable, the verifier exits non-zero and names the variable and
row count.

## Running

```bash
py -3 scripts/verify_s7_render.py --copy work/stage/s7-copy.jsonl
py -3 scripts/verify_s7_render.py --copy work/stage/s7-copy.jsonl --client productive
```

## Where this runs in tomorrow's sequence

After the cadence lands and S7 re-renders, BEFORE the push attempt:

1. `scripts/stage_s7_copy.py --ready work/stage/ready.json` (renders)
2. **`scripts/verify_s7_render.py --copy work/stage/s7-copy.jsonl`** (verifies)
3. `scripts/batch1_build.py` (builds the provider payload)

If step 2 exits non-zero, step 3 must not run.

## Current state (productive config)

- **Cadence:** `productive_li_heavy_v1` - 5 email steps (em1..em5)
- **thread_reply_pattern:** `[false, true, true, true, true]` (5 entries)
- **Final wait_in_days:** 1 (em5)
- **Sequence variables:** `{SUBJECT_1}`, `{BODY_1}`..`{BODY_5}`

## Test coverage

35 tests covering:
- Set diff in both directions, including the same-length trap
- Three constructed failures: empty, `'None'`, unrendered `{`
- Thread pattern length mismatch (3 entries vs 5 steps)
- Final wait = 0 refused
- Integration with the real productive config

## Boundaries

This verifier DOES NOT:
- Edit `src/cadence.py`, `config/clients/productive.yaml`, or
  `scripts/batch1_build.py`
- Push, attach, or re-render production
- Write to `work/` in any worktree

Defects found in the cadence or config files are REPORTED, not patched.
