# S7 Four-Step Render Verification

**TASK-283. 2026-09-25.**

## What this verifies

When S7 re-renders all rows for the current cadence, every row carries every
variable the provider sequence will ask for, and a row that does not is HELD
rather than sent with a gap in it.

## The five checks

### Check 1: Cadence keys vs config step keys, both directions

The cadence's email step keys (from `scripts/batch1_build.py`'s
`CADENCE_STEPS`) and the client config's `email_sequence.steps` keys must
agree as SETS, both ways. A key on one side the other does not carry is
named.

**Current state:** Both sides declare `['em1', 'em2', 'em3', 'em4', 'em5']`.

### Check 2: thread_reply_pattern, read from config at run time

The pattern must have exactly as many entries as there are email steps.
Position 1 is false (the opener owns the subject); every follow-up is true.

**Current state:** `[False, True, True, True, True]` — 5 entries, correct.

A three-entry pattern on a five-step cadence is the pre-change value and is
refused with the cause named. The pattern is READ FROM THE CONFIG, not
asserted from a table in this document — a table here is the thing that was
wrong in the first place (see the correction below).

### Check 3: Final step wait_in_days >= 1

The provider refused `wait_in_days: 0` on campaign 485 and left it at zero
steps atomically. The last step's declared wait is checked.

**Current state:** `em5.wait_in_days = 1`.

### Check 4: Variable set diff, both directions

The provider sequence templates reference `{SUBJECT_1}`, `{BODY_1}` through
`{BODY_N}`. The journal produces `subject_1`, `body_1` through `body_N`
(lowercase). The two sets are diffed in both directions and the NAMES are
printed.

**Current state:** Provider references `['body_1', 'body_2', 'body_3',
'body_4', 'body_5', 'subject_1']`.

### Check 5: Per-variable table over the journal

For every variable the provider needs: rows present, rows empty, rows
carrying the literal `'None'`, rows with an unrendered `{` surviving. The
verifier exits non-zero when any row would reach the provider with an empty
or unrendered variable.

## How to run

```
py -3 scripts/verify_s7_render.py
py -3 scripts/verify_s7_render.py --journal work/stage/s7-copy.jsonl
py -3 scripts/verify_s7_render.py --journal path/to/copy.jsonl --client productive
```

Without `--journal`, the verifier runs checks 1-3 (config-level) and skips
checks 4-5 (journal-level). With `--journal`, all five checks run.

## The correction (2026-09-25)

The task file originally described a four-step cadence (em1, em2, em4, em5)
with `subject_2`, `body_4` and `body_5` as the new variables. That was wrong
in three ways:

1. **There is no `SUBJECT_2` and no new-thread step.** All steps carry
   `{SUBJECT_1}` and `thread_reply_pattern` is `[false, true, true, true]`
   (now five entries with rung 3).
2. **The step key is NOT the variable number.** Variables are numbered by
   POSITION. em4 at position 3 reads `{BODY_3}`; em5 at position 4 reads
   `{BODY_4}`.
3. **A threaded step STILL CARRIES `email_subject`.** The `thread_reply` flag
   is the mechanism, not subject omission.

The cadence has since been extended to five steps (em1..em5) with rung 3
approved. The verifier reads everything from the config at run time and
asserts against what it finds, not against any table in any document.

## Where this runs in tomorrow's sequence

After the cadence lands and the S7 re-render completes, before the push:

```
py -3 scripts/stage_s7_copy.py --ready work/stage/ready.json
py -3 scripts/verify_s7_render.py --journal work/stage/s7-copy.jsonl
py -3 scripts/verify_s7_cadence_render.py   # the broader verifier
py -3 scripts/batch1_build.py               # only if both verifiers pass
```

## Boundaries

- Does NOT edit `src/cadence.py`, `config/clients/productive.yaml`, or
  `scripts/batch1_build.py`.
- Does NOT push, attach, or re-render production.
- Reads `work/` via a named copy, not directly.
- No prospect data in any committed file.

## Files

- `scripts/verify_s7_render.py` — the verifier
- `tests/test_the_four_step_render_has_every_variable.py` — 49 tests
- This document
