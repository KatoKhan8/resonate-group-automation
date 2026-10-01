PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-940 — `glm_verify_branch.py` asks GLM to verify a production caller and sends it a diffstat

Found while running the tool for real on 2026-10-01, not by reading it.

## What happened

`py -3 scripts/glm_verify_branch.py --branch task-step-objectives-convergence --task TASK-425
--max-tokens 16000 --timeout 600` returned `NEEDS_CLAUDE`. The reasoning was not a model
failure — it was correct, and it indicts the tool:

> "**Production caller — UNVERIFIABLE from what was provided.** I was given a diffstat, not the
> diff: no function names, no bodies, no line numbers. ... whether a newly added helper inside
> copystages.py or lint.py is called by anything cannot be checked without the line-level diff.
> I will not guess. This alone blocks PASS."

The module docstring states the tool's own purpose as catching "a bridge function with no
caller". It cannot do that from a diffstat. Every `NEEDS_CLAUDE` this script returns for that
reason is vacuous rather than informative, and it costs a full GLM call to produce
(9,035 tokens, 81s, on this run).

Two further holes the same run exposed:

1. **`Extracted 0 acceptance commands`** from the task file, and the script proceeded anyway,
   printing `(no acceptance commands extracted from task file)`. GLM named this correctly: "the
   check is vacuous by absence, not by construction." A verification step that silently runs
   with zero checks should not be able to contribute to a PASS.
2. **The test log reaches GLM truncated with no summary line.** GLM reported it could not
   confirm that a single test from the largest new test file (+319 lines) had run. The script's
   own line said `Failing tests: 0 total, 0 new`, so the script knew more than it forwarded.

## What the answers actually were

All three were settled afterwards by direct measurement, which is the proof that the tool
could have answered them:

- Orphan helpers: NONE. All eight functions added to `src/` by the branch have a caller in
  `src/` on the branch itself: `_selected_offer` (src/generate.py:2404), `countable_words`
  (src/lint.py:683), `reply_steps_for` (src/generate.py:2403), `step_key_of` (src/lint.py:680),
  `step_objective_block` (src/copystages.py:788), `word_range` (src/lint.py:681), plus `check`
  and `check_step` which have 75 and 14 call sites in `src/`. A control search for a nonexistent
  name returned 0, so the search can fail.
- The new tests run and pass: 7, 29 and 17 tests, three `OK` summary lines, `__pycache__` wiped
  first.
- Scratch files at repo root: none.

Note the two wrong turns that produced those numbers, because the fix should make them
unnecessary: a first search used a pattern excluding `module.function(` and reported 0 callers
for six functions; a second searched the master working tree, where the new functions do not
exist. The tool should do this with `git grep <rev>` so a human cannot make either mistake.

## Acceptance

1. GLM receives the line-level diff for `src/` (bounded by a token budget, and when it must be
   truncated, it is told what was cut and how much).
2. A task file yielding zero acceptance commands is a REFUSAL to verify, not a step that passes
   silently. The verdict must say "no acceptance check exists" in the verdict line itself.
3. The test result forwarded to GLM includes the summary lines (`Ran N tests`, `OK`/`FAILED`)
   for every module, or states plainly that it was truncated.
4. The orphan-caller question is answered mechanically by `git grep` against the branch rev
   before GLM is called, and the finding is handed to GLM as a fact rather than a question. A
   model should not be paid to grep.
5. Prove the fix: re-run against this same branch and SHA (`c916d3fd`) and show the verdict
   changes on the strength of better evidence, not a loosened rule.

## Two adjacent facts, measured, not part of this task

- The script diffs failing tests against `docs/state/SUITE-BASELINE-2026-09-26.txt` — master
  `0af11fcb`, 12,737 tests, dated 26.9. Current master is `10a38310`. Its baseline comparison is
  therefore against a different tree and is not authoritative until the named baseline is
  regenerated.
- The run printed `Spend: 0 rows, 0 micro-USD` for a call that consumed 9,035 tokens. The spend
  ledger recorded nothing for a real paid call. Same class as the non-canonical-provider-spelling
  defect: the mechanism, not the figure.
