# GLM branch verification: TASK-903

Branch: `task-step-objectives-convergence`
Date: 2026-10-02T15:16:26.279496+00:00
Model: glm-5.3
Duration: 78.902s
Usage: {'prompt_tokens': 14892, 'completion_tokens': 5895, 'total_tokens': 20787, 'reasoning_tokens': 5043, 'cached_tokens': 0}

## Verdict: NEEDS_CLAUDE

**criteria 1–4 are testable only via `test_em3_and_em5_can_satisfy_the_ladder_at_all.py`, which is entirely inside the 39,184 unshown characters, and no acceptance commands were run.**

## GLM spend

This call: 1 ledger rows, 15389 micro-USD

## Changed files (7)

- `src/copystages.py`
- `src/generate.py`
- `src/generate_campaign.py`
- `src/lint.py`
- `tests/test_a_thread_reply_has_its_own_word_range.py`
- `tests/test_a_truncated_answer_costs_one_attempt_not_the_round.py`
- `tests/test_em3_and_em5_can_satisfy_the_ladder_at_all.py`

## Diff stat

```
 src/copystages.py                                  | 169 +++++++++--
 src/generate.py                                    |  44 ++-
 src/generate_campaign.py                           | 103 ++++++-
 src/lint.py                                        | 244 +++++++++++++++-
 .../test_a_thread_reply_has_its_own_word_range.py  | 295 +++++++++++++++++++
 ...cated_answer_costs_one_attempt_not_the_round.py | 275 ++++++++++++++++++
 ...st_em3_and_em5_can_satisfy_the_ladder_at_all.py | 319 +++++++++++++++++++++
 7 files changed, 1410 insertions(+), 39 deletions(-)

```

## Acceptance output

```
NOTHING WAS RUN. This task declares no runnable acceptance commands, so there is no evidence here that the branch does what it claims. Treat question 2 as unanswerable and do not return PASS on the strength of the diff alone.

The task's acceptance criteria, stated as prose rather than as commands, are below. Judge the diff AGAINST THESE - that is what the branch promised:

1. For Offer A rungs 1 and 3 and every Offer B rung with the same shape: a
   question form and a capability form both **pass** the claims gate with a
   pack containing no margin/resource fact.
2. **NEGATIVE CONTROL:** the assertion form of the same rung is still
   **REFUSED** on that pack. The corridor must close for assertions and only
   for assertions.
3. **`sequencegate` still refuses a step that does not pursue its rung's
   topic** — prove with a step that covers the wrong rung.
4. Mutation: revert one rung's objective to its assertion form; control 2 must
   go red.

(no acceptance commands extracted from task file)
```

## GLM response

## 1. Does the new code have a production caller?

YES, for every bridge in the visible portion:

- `copystages.step_objective_block` (copystages.py @@ -652,8 +670,108) ← `copystages.writer_user` ← `generate_campaign._process_contact` (@@ -800,10 +834,27: `writer_base = copystages.writer_user(..., step_objectives=..., ai_capabilities=..., thread_reply_rungs=...)`).
- `generate._selected_offer` (@@ -2325,6 +2325,38) ← `generate._step_refusals` (@@ -2359: `lint.check(trial, key, step, step_key=step_key, reply_steps=lint.reply_steps_for(_selected_offer(rec, contact)))`).
- `lint.reply_steps_for`, `word_range`, `countable_words`, `step_key_of` ← `lint.check`; `check_record` now passes `step_key=day`.

Caveat, not a finding: `_step_refusals` references `step_key`, but the loop header that would bind it is above the hunk context and not shown. If it is unbound, every non-LinkedIn step raises `NameError`, which is in `PIPELINE_DEFECTS` and stops the run — the first generated refusal would expose it, but I cannot confirm either way from this diff.

## 2. Can the acceptance check fail?

UNANSWERABLE AS SHOWN. Criteria 1–4 test the claims-gate corridor and `sequencegate`. Neither `claims.py` nor `sequencegate.py` is in the diff — the mechanism is prompt-only (`step_objective_block` tells the writer to put rung words in question form) — and the only file plausibly containing the corridor tests, `tests/test_em3_and_em5_can_satisfy_the_ladder_at_all.py` (319 lines), lies entirely in the 39,184 hidden characters. No acceptance commands were run. I cannot name an input that fails a check I cannot see, and I cannot prove the check vacuous either.

## 3. Does any number reconcile?

- Diffstat reconciles exactly: 169+44+103+244+295+275+319 = 1449 = 1410 insertions + 39 deletions. ✓
- Production measurements (1323 stored em2 / 1317 over 60; 33 of 54 em4; 4082 bodies with zero sign-offs) reference queue data outside the diff — self-consistent but not recomputable.
- The test-results block is cut off mid-test-name (`test_it_carries_a_real_level_and_not_an_empty_string (`) and the visible portion contains **zero tests from `test_em3_and_em5_can_satisfy_the_ladder_at_all.py`**. I cannot confirm the acceptance-criteria tests exist, ran, or passed.

## Also checked

- File-to-task: copystages/generate/generate_campaign plausibly answer TASK-903. `lint.py`'s 244 lines implement an operator ruling (reply word range) that the four stated criteria never mention — in scope only if TASK-903's full text includes the canary's em4 under-length refusals, which I can't see. The `account=` NameError fix and truncated-JSON retry in generate_campaign.py are real bugfixes but not named by the criteria.
- No scratch files; changed list is all `.py` under `src/` and `tests/`.

## Verdict

The hidden 39k characters contain the only evidence that acceptance criteria 1–4 are met, nothing was executed, and the visible results omit the ladder test file entirely.

VERDICT: NEEDS_CLAUDE - criteria 1–4 are testable only via `test_em3_and_em5_can_satisfy_the_ladder_at_all.py`, which is entirely inside the 39,184 unshown characters, and no acceptance commands were run.
