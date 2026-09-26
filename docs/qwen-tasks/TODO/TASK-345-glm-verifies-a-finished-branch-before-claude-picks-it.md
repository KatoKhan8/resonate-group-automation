PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-345 - GLM verifies a finished branch before Claude cherry-picks it

**Operator decision, 2026-09-26.** GLM does first-pass verification of every
finished worker branch. Claude cherry-picks **only** branches GLM has passed, and
spot-checks one in three. This task builds that gate.

It exists because hand-verification caught three things a green `exit=0` did not:
a fix whose new bridge function had no caller, a tool reporting 56 DISCONNECTED
modules of which most were in use, and four scratch files committed to the repo
root. `exit=0` is not a verdict.

## Build

    scripts/glm_verify_branch.py    NEW
    docs/glm-reviews/branch-<TASK>.md   its output, one per branch

**Extend the existing pattern, do not invent a second one.**
`scripts/glm_review.py` already holds the adapter usage, the prompt discipline
and the report shape. Read it first. Reuse `DEFAULT_MAX_TOKENS = 16000` and
`--timeout 180`: GLM-5.3 spends most of its budget on reasoning tokens, returns
`finish_reason='length'` when starved, and the adapter **refuses rather than
returning an empty string**, which is correct and must not be worked around.

    py -3 scripts/glm_verify_branch.py --branch qwen-worker-2-r59 --task TASK-323

It must do four things and report each separately:

1. **Run the task's own acceptance commands**, from the task file, and capture
   real output. Not a summary - the output.
2. **Run the tests the branch adds or changes**, and diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 names). A failure
   already in that list is NOT this branch's fault.
3. **Read the diff** and answer: does every changed file answer to the task? Name
   any file that does not. Flag scratch output (`*.txt`, `*.err`, `*.out` at the
   repo root) as a hard fail.
4. **Post a verdict**: `PASS`, `FAIL`, or `NEEDS_CLAUDE`, with the reason.

## The three questions GLM must be asked, because they are the ones that caught real defects

Ask for **defeats and concrete mechanisms**, never "is this good code" - that has
an agreeable answer worth nothing. `glm_review.py`'s SYSTEM prompt already says
this; reuse it.

- **Does the new code have a production caller?** Not a test, not `work/`, not a
  re-export nobody calls. If the branch adds a function to bridge two modules,
  ask whether anything calls the BRIDGE. This exact defect shipped on 2026-09-26.
- **Can the acceptance check fail?** Given the change, name an input that makes it
  fail. If GLM cannot name one, the check is vacuous and the verdict is FAIL -
  that is the TASK-317 defect, where an assertion tested that the stamping code
  ran rather than that the provenance was true.
- **Does any number in the result block reconcile?** A count, a cost, a row total.
  If the branch claims a measurement, recompute it.

## Acceptance

1. Run it against a branch already verified BY HAND and confirm it agrees:

    py -3 scripts/glm_verify_branch.py --branch qwen-worker-2-r59 --task TASK-323

   Expected `PASS` - that branch's ceiling test genuinely fires. If GLM says
   FAIL, read why before assuming GLM is wrong; if it is right, that is the most
   valuable output this task can produce.

2. **Run it against a branch known to be DEFECTIVE and confirm it catches it:**

    py -3 scripts/glm_verify_branch.py --branch qwen-worker-3-r59 --task TASK-324

   That branch's tool reports 56 DISCONNECTED components including
   `src/bisonfactory.py`, `src/check.py` and `src/benchmark.py`, all of which are
   in use. A verdict of PASS here means the gate does not work. **This is the test
   that closes the task.**

3. Report the GLM spend for both runs, in micro-dollars, read from the ledger -
   `src/llm.py` now writes model rows, so this is measurable rather than
   estimated.

4. `--dry-run` prints the prompt and calls nothing.

## What this task may NOT do

- **Do not merge, cherry-pick, push to master, or move a task file.** This tool
  reports a verdict. Claude integrates.
- Do not let GLM's verdict override a deterministic test failure. A failing test
  is a failure whatever the model says.
- No provider call, nothing sent, nothing activated.
