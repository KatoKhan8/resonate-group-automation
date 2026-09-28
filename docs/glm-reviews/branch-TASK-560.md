# GLM branch verification: TASK-560

Branch: `qwen-worker-3-r10`
Date: 2026-09-28T17:57:43.818555+00:00
Model: glm-5.3
Duration: 73.496s
Usage: {'prompt_tokens': 1192, 'completion_tokens': 5263, 'total_tokens': 6455, 'reasoning_tokens': 4571, 'cached_tokens': 896}

## Verdict: NEEDS_CLAUDE

**41 changed lines in src/bisonfactory.py have zero test references and no demonstrable production caller; diff body must be read to rule out dead code or double-append of the P.S.**

## GLM spend

This call: 0 ledger rows, 0 micro-USD

## Changed files (5)

- `docs/qwen-tasks/REVIEW/TASK-560-the-ps-must-reach-the-person.md`
- `src/approval.py`
- `src/bisonfactory.py`
- `src/render.py`
- `tests/test_task560_ps_reaches_the_person.py`

## Diff stat

```
 .../TASK-560-the-ps-must-reach-the-person.md       |  44 +++
 src/approval.py                                    |  10 +-
 src/bisonfactory.py                                |  41 ++-
 src/render.py                                      |  21 +-
 tests/test_task560_ps_reaches_the_person.py        | 344 +++++++++++++++++++++
 5 files changed, 453 insertions(+), 7 deletions(-)

```

## Acceptance output

```
(no acceptance commands extracted from task file)
```

## GLM response

## 1. Does the new code have a production caller?

**NO CALLER DEMONSTRATED for src/bisonfactory.py.** The 12 tests exercise render.py (`variables_for`, `emailbison_rows`, card HTML) and approval.py (certified-copy forbidden set, fingerprint) directly, but **zero of the 12 tests reference bisonfactory.py, which carries the largest src change (+41 lines)**. If the P.S.-append logic lives there and render.py calls it, the summary does not show it; if it's a new bridge function, nothing shown calls it. The render.py/approval.py changes look like in-place edits of existing functions (they keep whatever callers they had), but I only have per-file line counts, not the diff body, so I cannot name a call order. Honest answer: unverified; bisonfactory.py is the blind spot.

## 2. Can the acceptance check fail?

**There is no acceptance check** — "(no acceptance commands extracted from task file)". Vacuous by absence. The 12 tests are non-vacuous (revert render.py's append and 4 fail), but two concrete inputs they cannot catch:

- **Substring assertions can't catch glue or duplication.** Every render test is an inclusion check. `body + ps` with no separator, or the P.S. appended twice (plausible if bisonfactory.py and render.py *both* append — the exact file pair changed), passes all 12. At 10k sends/week with P.S. on 30% of steps, that's 3,000 malformed or duplicated-P.S. emails/week with a green suite.
- **Key-deletion bypass.** The suite itself blesses it: `{"steps":[{"body":"x","ps":""}]}` blocks, but `{"steps":[{"body":"x"}]}` passes (`test_step_without_ps_field_is_fine`). The only refused representation — explicit empty string — is exactly what proto3/omit-empty serializers elide, so any copy crossing such a boundary converts the blocking case into the silently-passing case and sends P.S.-less mail. Conditional on the pipeline, but the input is nameable.

## 3. Does any number reconcile?

Yes. Per-file changes 44+10+41+21+344 = 460 = 453 insertions + 7 deletions ✓. 12 tests listed = 12 run ✓. 0.038s for 12 unit tests is plausible. No cost/row-total claims exist to recompute.

## Also-check

- **src/bisonfactory.py does not demonstrably answer to the task**: 41 changed lines, no coverage in the 344-line test file, no shown caller. The other four files answer to TASK-560.
- No scratch files (*.txt/*.err/*.out) appear in the changed set.

## Caveat

I was given the diff *summary*, not the diff body — I cannot cite interior line numbers, only file names and per-file counts. That is itself why this cannot close here.

VERDICT: NEEDS_CLAUDE - 41 changed lines in src/bisonfactory.py have zero test references and no demonstrable production caller; diff body must be read to rule out dead code or double-append of the P.S.
