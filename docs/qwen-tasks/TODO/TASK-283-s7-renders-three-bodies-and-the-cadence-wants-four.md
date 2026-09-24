PRIORITY: P0
DEPENDS:

# TASK-283 — S7 renders three bodies and the cadence now wants four

## The question this answers

**When S7 re-renders all 927 rows for the four-step cadence, will every row
carry every variable the provider sequence will ask for — and will a row that
does not be HELD rather than sent with a gap in it?**

State, 2026-09-24 night. The cadence moves to **em1, em2, em4, em5** —
`breakup` is retired. em4 opens a NEW thread (`thread_reply` false,
`SUBJECT_2`); em5 replies into it (true). `work/stage/s7-copy.jsonl` carries
**`subject_1` and `body_1..3` only**. em4 and em5 need **`subject_2`, `body_4`
and `body_5`**, and on 40 live leads checked tonight those variables are
**empty — not the literal string `'None'`** the morning handoff warned about.
Empty is exactly what the blank gate refuses.

`bisonfactory` REFUSES when the provider sequence keys and the cadence keys
disagree, and it refuses in a place that does not name the cause. So a push
attempted before this verification passes fails obscurely.

**This task VERIFIES. It does not change the cadence, the config, or the
builder** — another lane is landing those tonight and two hands on those three
files is how a half-applied cadence happens twice.

## What to build

`scripts/verify_s7_render.py` plus its tests.

1. Read the cadence's step keys and the provider sequence's variable keys, and
   **diff them as SETS, both directions**. Report keys the cadence declares
   that the sequence does not carry, AND keys the sequence carries that the
   cadence does not declare. One direction is how a half-applied change reads
   as complete.
2. Read `work/stage/s7-copy.jsonl` (via a copy — see boundaries) and report,
   per variable in the four-step set: rows present, rows empty, rows carrying
   the literal `'None'`, rows with an unrendered `{` surviving.
3. Assert the threading invariant for the four steps **as data**:

       em1   SUBJECT_1, thread_reply false
       em2   no subject, thread_reply true
       em4   SUBJECT_2, thread_reply false     <- a NEW thread
       em5   no subject, thread_reply true

   `thread_reply_pattern` must have **four** entries. Three is the current
   value and it is the bug.
4. Assert the **final step's `wait_in_days` is 1, never 0.** Campaign 485 was
   left at 0 steps by exactly that.
5. Exit non-zero, naming the variable and the row count, when any row would
   reach the provider with an empty or unrendered variable.

Write `docs/S7-FOUR-STEP-RENDER-VERIFICATION-2026-09-25.md`.

## The acceptance bar

- The verifier is run against the **real** `s7-copy.jsonl` for all 927 rows
  and reports a number per variable. "All good" with no denominator is not a
  result.
- The set diff is printed in **both directions** and both are named in the
  output. A one-directional diff is rejected on sight.
- A row with `subject_2` empty causes a non-zero exit and is named. Construct
  such a row and show the failure.
- A row carrying the literal `'None'` is caught and distinguished from empty.
  Both are refusals; they have different causes and the report must not merge
  them.
- The verifier refuses when `thread_reply_pattern` has three entries, and its
  message **names the cause** — the thing `bisonfactory`'s refusal does not do.

## What evidence counts

- The per-variable table over 927 real rows, with the run timestamp and the
  path of the copy read.
- The two-direction key diff, pasted.
- The failure output for the three constructed bad rows (empty, `'None'`,
  unrendered `{`).
- The current `thread_reply_pattern` value read from the config at run time,
  quoted — not from memory and not from this task file.

## WHAT WOULD MAKE THIS A FALSE PASS

- **A count instead of a list.** "4 keys on both sides" compares equal while
  the sets differ. Diff the SETS, print the names, both directions. This is
  the same defect the suite baselines carried.
- **A green suite over invented rows.** Fixtures will carry whatever variables
  you put in them. The 927 rows are the test; the fixtures are the regression.
- **Verifying against `src/cadence.py`'s templates while the config still
  declares em1..em3.** The whole point is that the two disagree right now.
  Read BOTH and diff them. If they currently agree, say so and check you read
  the file the builder reads.
- **Treating an empty variable as "the provider will fill it".** It will not;
  the blank gate refuses, and 76 blank emails have already gone out once
  (ISSUE-025).
- **Asserting on the source text.** `grep "SUBJECT_2" src/cadence.py` proves a
  string exists. Assert on the rendered variable set a lead actually gets.
- A verifier with no caller and no runbook line. Say where in tomorrow's
  sequence it runs (after the cadence lands, before the push).

## Boundaries

- **DO NOT EDIT** `src/cadence.py`, `config/clients/productive.yaml`, or
  `scripts/batch1_build.py`. Another lane is landing the cadence tonight.
  If you find a defect in one of them, **write it into FINDINGS** — that is
  the deliverable, not a patch.
- **Do not push, attach, or re-render production.** The re-render is
  production's to run. Verify the artefact; do not replace it.
- Production `work/` is not yours; read a named copy.
- No prospect data in any committed file.

## Files

    ALLOWED    scripts/verify_s7_render.py,
               tests/test_the_four_step_render_has_every_variable.py,
               docs/S7-FOUR-STEP-RENDER-VERIFICATION-2026-09-25.md
    FORBIDDEN  src/cadence.py, config/clients/productive.yaml,
               scripts/batch1_build.py, scripts/stage_s7_copy.py,
               src/providers/*, src/push.py, work/*, config/.env

## Result block

    BRANCH:
    COMMIT:
    CADENCE KEYS / SEQUENCE KEYS, BOTH DIFF DIRECTIONS:
    thread_reply_pattern AS READ AT RUN TIME:
    FINAL STEP wait_in_days:
    PER-VARIABLE TABLE OVER 927 ROWS (present / empty / 'None' / unrendered):
    THE THREE CONSTRUCTED FAILURES AND THEIR MESSAGES:
    DEFECTS FOUND IN THE LANE-B FILES (reported, NOT patched):
    WHERE THIS RUNS IN TOMORROW'S SEQUENCE:
    WORKSPACES COPY USED (path, taken at):
