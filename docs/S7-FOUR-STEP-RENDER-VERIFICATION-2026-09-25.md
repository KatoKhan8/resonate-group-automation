# S7 Four-Step Render Verification — 2026-09-25

TASK-283. Verifier: `scripts/verify_s7_render.py`.
Tests: `tests/test_the_four_step_render_has_every_variable.py`.

## Purpose

When S7 re-renders all rows for the cadence, every row must carry every
variable the provider sequence will ask for. A row that does not must be
HELD rather than sent with a gap in it.

This verifier checks that invariant without changing the cadence, the
config, or the builder. It reads the config at run time and reports what
it finds.

## What it checks

### 1. Set diff: cadence vars vs sequence vars (both directions)

The cadence's step keys determine which `body_N` variables the journal
produces (by key suffix: `em4` -> `body_4`). The provider sequence's
templates reference `{BODY_N}` by position. At five steps these happen to
agree; at four steps they did not (em4 at position 3 reads `{BODY_3}`).

The verifier diffs both sets in BOTH directions and prints the names.
A count is not a diff: "4 keys on both sides" compares equal while the
sets differ.

### 2. Per-variable table over rendered rows

For each variable the sequence references:
- **present**: non-empty, not 'None', no unrendered placeholder
- **empty**: empty string, whitespace, or blankish value (N/A, null, etc.)
- **literal_none**: the string "None" (case-insensitive) — a Python repr
  failure, distinct from empty
- **unrendered**: a surviving `{PLACEHOLDER}` in the value

Three separate counts, three separate causes. A report that merges them
reports one as another.

### 3. Threading invariant

`thread_reply_pattern` is read from the config at run time. The verifier
asserts:
- The pattern has one entry per email step
- Entry 0 is `false` (the opener owns the subject)
- Entries 1..N are `true` (follow-ups are thread replies)

A three-entry pattern on a four-or-five-step sequence is the pre-change
value and is refused with a message naming the cause.

### 4. Final step `wait_in_days`

Must be 1, never 0. Campaign 485 was left at 0 steps by exactly that.
The final step's wait is inert (nothing follows it) but the provider
refuses 0.

### 5. Exit code

Non-zero when:
- The set diff is non-empty in either direction
- The threading invariant is violated
- The final wait is 0
- Any row has empty, 'None', or unrendered variables

## How to run

```bash
python -3 scripts/verify_s7_render.py --copy work/stage/s7-copy.jsonl
python -3 scripts/verify_s7_render.py --copy work/stage/s7-copy.jsonl.bak
python -3 scripts/verify_s7_render.py --copy work/stage/s7-copy.jsonl --client productive
```

## Where this runs in tomorrow's sequence

After the cadence lands (lane B's config change is merged) and S7
re-renders, BEFORE the push to the provider. The verifier is a gate
between the render and the attach. A failure here holds the batch; it
does not push and hope.

## Current state of the config

As of 2026-09-25, the config (`config/clients/productive.yaml`) declares:

    thread_reply_pattern: [false, true, true, true, true]
    steps: em1, em2, em3, em4, em5

Five steps. Rung 3 (`em3`) was approved 2026-09-25 and took the position
the four-step cadence of 2026-09-24 deliberately left empty. The step
keys did not move when it arrived.

The journal variables are `subject_1`, `body_1`..`body_5`. The provider
sequence references `{SUBJECT_1}`, `{BODY_1}`..`{BODY_5}`. At five steps
these agree by coincidence of the cadence's shape.

## The step key is not the variable number

TASK-295 correction. em4 at position 3 reads `{BODY_3}`; em5 at position 4
reads `{BODY_4}`. The verifier reads the mapping from the config at run
time and does not assume the step key suffix equals the variable number.

## What this deliberately does not prove

- The approval gate's other conditions (verification, suppression,
  collision, fatigue) are not exercised. They need `work/` state this
  script does not read.
- Nothing here is evidence that anything reached EmailBison. Only a
  provider readback is.
- The verifier does not re-render or push. It reads a named copy of the
  journal and reports.

## Defects found in lane-B files

None at the time of writing. The config currently declares five steps
with a five-entry threading pattern, and the two agree. If the cadence
changes again, the verifier will catch the mismatch.

## Tests

44 tests in `tests/test_the_four_step_render_has_every_variable.py`:

- `TestDiffSetsBothDirections` — the set diff in both directions
- `TestVariableKeysFromSequence` — provider variable extraction
- `TestVariableKeysFromCadence` — cadence variable extraction
- `TestClassifyValue` — empty/None/unrendered distinction
- `TestCheckRows` — per-variable report
- `TestCheckThreading` — threading invariant
- `TestCheckFinalWait` — final wait_in_days
- `TestLoadAndRender` — JSONL loading
- `TestEndToEndConstructedFailures` — three constructed bad rows
- `TestStepKeyIsNotVariableNumber` — TASK-295 correction
