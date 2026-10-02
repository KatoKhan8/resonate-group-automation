# GLM branch verification: TASK-942

Branch: `task-942-token-budget`
Date: 2026-10-02T17:46:07.530897+00:00
Model: glm-5.3
Duration: 134.598s
Usage: {'prompt_tokens': 14579, 'completion_tokens': 10029, 'total_tokens': 24608, 'reasoning_tokens': 9005, 'cached_tokens': 0}

## Verdict: FAIL

**the dry-run seam (`RecordingModel`) accepts and drops the very budget this task adds, and `_parse_json` now refuses trailing-quote inputs it previously parsed.**

## GLM spend

This call: 1 ledger rows, 21878 micro-USD

## Changed files (28)

- `docs/qwen-tasks/REVIEW/TASK-942-the-writer-is-told-how-long-its-answer-may-be.md`
- `scripts/task425_one_account_dry_run.py`
- `src/generate.py`
- `src/generate_campaign.py`
- `src/llm.py`
- `tests/base.py`
- `tests/test_a_broad_question_plans_one_tool.py`
- `tests/test_a_truncated_answer_costs_one_attempt_not_the_round.py`
- `tests/test_changing_an_approved_fact_changes_the_output.py`
- `tests/test_e2e.py`
- `tests/test_failure_injection.py`
- `tests/test_generate.py`
- `tests/test_internal_assistant_mode.py`
- `tests/test_measurement_truth.py`
- `tests/test_no_model_is_not_a_bad_record.py`
- `tests/test_preproduction.py`
- `tests/test_slack_agent_conversation.py`
- `tests/test_slack_agent_language_and_relay.py`
- `tests/test_slack_agent_numbers.py`
- `tests/test_slack_agent_scope.py`
- `tests/test_task400_rework2.py`
- `tests/test_task400_rework3.py`
- `tests/test_the_entrypoint_actually_loads_its_skills.py`
- `tests/test_the_entrypoint_is_the_only_generation_path.py`
- `tests/test_the_gag_stops_the_answer_not_the_request.py`
- `tests/test_the_readback_cache_cannot_lie_about_its_age.py`
- `tests/test_the_research_pack_has_one_shape.py`
- `tests/test_the_writer_is_told_how_long_its_answer_may_be.py`

## Diff stat

```
 ...he-writer-is-told-how-long-its-answer-may-be.md |  62 +++
 scripts/task425_one_account_dry_run.py             |   3 +-
 src/generate.py                                    |  14 +-
 src/generate_campaign.py                           | 267 +++++++++-
 src/llm.py                                         | 141 ++++-
 tests/base.py                                      |   3 +-
 tests/test_a_broad_question_plans_one_tool.py      |   6 +-
 ...cated_answer_costs_one_attempt_not_the_round.py |  20 +-
 ...changing_an_approved_fact_changes_the_output.py |   3 +-
 tests/test_e2e.py                                  |   3 +-
 tests/test_failure_injection.py                    |   3 +-
 tests/test_generate.py                             |   3 +-
 tests/test_internal_assistant_mode.py              |   3 +-
 tests/test_measurement_truth.py                    |  12 +-
 tests/test_no_model_is_not_a_bad_record.py         |   6 +-
 tests/test_preproduction.py                        |   3 +-
 tests/test_slack_agent_conversation.py             |   6 +-
 tests/test_slack_agent_language_and_relay.py       |   3 +-
 tests/test_slack_agent_numbers.py                  |  15 +-
 tests/test_slack_agent_scope.py                    |   3 +-
 tests/test_task400_rework2.py                      |   3 +-
 tests/test_task400_rework3.py                      |   6 +-
 ...est_the_entrypoint_actually_loads_its_skills.py |   3 +-
 ...t_the_entrypoint_is_the_only_generation_path.py |   3 +-
 ...est_the_gag_stops_the_answer_not_the_request.py |   6 +-
 ..._the_readback_cache_cannot_lie_about_its_age.py |   3 +-
 tests/test_the_research_pack_has_one_shape.py      |   6 +-
 ...he_writer_is_told_how_long_its_answer_may_be.py | 586 +++++++++++++++++++++
 28 files changed, 1132 insertions(+), 63 deletions(-)

```

## Acceptance output

```
$ python -c "import sys; sys.path.insert(0,'.'); from src import generate_campaign as g; assert isinstance(g.WRITER_MAX_TOKENS, int), type(g.WRITER_MAX_TOKENS); assert g.WRITER_MAX_TOKENS == 1759, g.WRITER_MAX_TOKENS; print('OK the writer carries a budget:', g.WRITER_MAX_TOKENS, 'tokens')"
exit=0
OK the writer carries a budget: 1759 tokens

$ python -c "import sys; sys.path.insert(0,'.'); import importlib; from src import lint; import src.generate_campaign as g; before = g.WRITER_MAX_TOKENS; lint.MAX_WORDS = lint.MAX_WORDS * 2; importlib.reload(g); assert g.WRITER_MAX_TOKENS > before, (before, g.WRITER_MAX_TOKENS); print('OK the budget is DERIVED from lint, not a literal:', before, '->', g.WRITER_MAX_TOKENS)"
exit=0
OK the budget is DERIVED from lint, not a literal: 1759 -> 2884

$ python -c "import sys; sys.path.insert(0,'.'); from src import llm; assert issubclass(llm.TruncatedAnswer, ValueError); assert issubclass(llm.UnusableAnswer, ValueError); assert issubclass(llm.TruncatedAnswer, llm.UnreadableAnswer); assert llm.TruncatedAnswer is not llm.UnusableAnswer; print('OK two named refusals, and an existing except ValueError still catches both')"
exit=0
OK two named refusals, and an existing except ValueError still catches both

$ python -m unittest tests.test_the_writer_is_told_how_long_its_answer_may_be
exit=0
..............................
----------------------------------------------------------------------
Ran 30 tests in 0.478s

OK
```

## GLM response

## Q1 — Production caller?

YES. `_process_contact`'s writer retry loop in `src/generate_campaign.py` (hunk at old line 918) now calls `_call_model(..., max_tokens=WRITER_MAX_TOKENS)`; `_call_model` forwards it via `**extra`; `_CountedModel.complete` (`src/generate.py`, @@ -2804) forwards to the inner model; `OpenAICompatibleModel.complete` (`src/llm.py`, @@ -424) writes `body["max_tokens"]`. Chain is complete on the production path. `QwenCliModel` accepts and drops, but with a stated reason (no CLI flag exists) and a second witness (`_parse_json` structure).

## Q2 — Can the acceptance fail?

Not vacuous. Cmd 1 fails on any legitimate lint change (e.g. `MAX_WORDS` 180→200 ⇒ 5·200·1.25=1250, total 1884 ≠ 1759). Cmd 2 fails iff the figure is a literal (doubling `MAX_WORDS` + reload yields no increase). Cmd 3 fails iff the classes collapse or leave `ValueError`. Cmd 4's 30 tests are claimed mutation-sensitive, but the entire 586-line test file is in the unseen 33k — the "8 of 30 go red" mutation claim is unverifiable from the diff.

## Q3 — Do the numbers reconcile?

Yes, from the acceptance output alone: 2884 − 1759 = 1125 = 6.25·W ⇒ `lint.MAX_WORDS` = 180. Then 1759 − 1125 − (2·200·0.25 + 98 + 16 = 214) = 420 = 0.25·K·N + 0.75·S; with K=5 LinkedIn keys (docstring says five), N=300, S=60 gives 375+45 ⇒ exactly 1759. 1759/795 = 2.21 ✓ "about 2.2x the richest answer". 2724 chars / 680 tokens = 4.0 chars/token, consistent with `_TOKENS_PER_CHAR = 0.25` ✓. All reconciles; `lint`'s constants are not in the diff but are pinned by the acceptance output.

## Findings

1. **Dry-run seam drops the budget.** `scripts/task425_one_account_dry_run.py:341` — `RecordingModel.complete` accepts `max_tokens` and calls `self.inner.complete(...)` WITHOUT it. Call order: `_process_contact` → `_call_model(max_tokens=1759)` → RecordingModel (drops) → inner. Cost: every writer call in that dry run sends no cap, so the dry run can neither reproduce nor validate the TASK-942 fix — the exact "accepted and dropped" pattern `_CountedModel`'s own docstring calls the reintroduced defect.

2. **`_parse_json` regression on trailing junk.** `_json_unterminated` scans `t[i:]`, past `j`. Concrete inputs: `{"a":1} She said "maybe` (unmatched quote → `in_string` at end) and `{"a":1} {"b":2` — both previously parsed via `t[i:rfind("}")+1]` and proceeded to lint; both now raise `TruncatedAnswer`, costing one writer attempt or, on ICP/extract stages, a full `hold_kind="model_answer_truncated"` hold. The docstring's "trailing prose… is correctly not a truncation" is false for any prose containing `"`, `{`, or `[`.

3. **Measurement contamination.** The outer `except llm.UnreadableAnswer` appends `kind` to `result["writer_parse_refusals"]` for NON-writer stages (ICP, extract, hypothesis, match). Input: contact whose ICP verdict is cut at `finish_reason="length"` ⇒ `writer_parse_refusals == ["truncated"]` with the writer never called — the TASK-942 signal overcounts writer budget failures. Also introduces hold_kind values `model_answer_truncated`/`model_answer_unusable`; any downstream consumer bucketing `hold_kind == "error"` is not shown in the diff.

## Also

- Test signature widenings in `test_slack_agent_*`, `test_internal_assistant_mode`, `test_a_broad_question_plans_one_tool` are never reached by `max_tokens` (those models are called outside `_call_model`) — harmless noise.
- No scratch files (*.txt/*.err/*.out) in the changed list.

VERDICT: FAIL - the dry-run seam (`RecordingModel`) accepts and drops the very budget this task adds, and `_parse_json` now refuses trailing-quote inputs it previously parsed.
