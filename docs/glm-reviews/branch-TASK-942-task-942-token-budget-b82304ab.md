# GLM branch verification: TASK-942

Branch: `task-942-token-budget`
Date: 2026-10-03T02:07:53.602620+00:00
Model: glm-5.3
Duration: 132.615s
Usage: {'prompt_tokens': 13605, 'completion_tokens': 8792, 'total_tokens': 22397, 'reasoning_tokens': 7757, 'cached_tokens': 11328}

Parts: 3 (part 1=PASS, part 2=PASS, part 3=PASS)

## Verdict: PASS

**all 3 part(s) PASS**

## GLM spend

This call: 3 ledger rows, 56027 micro-USD

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
 ...he-writer-is-told-how-long-its-answer-may-be.md |  62 ++
 scripts/task425_one_account_dry_run.py             |  11 +-
 src/generate.py                                    |  14 +-
 src/generate_campaign.py                           | 287 ++++++++-
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
 ...he_writer_is_told_how_long_its_answer_may_be.py | 693 +++++++++++++++++++++
 28 files changed, 1266 insertions(+), 64 deletions(-)

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
......................................
----------------------------------------------------------------------
Ran 38 tests in 1.194s

OK
```

## GLM response

### Part 1 — PASS



## 1. Production caller?

YES. `src/generate_campaign.py` `_process_contact` writer loop calls `_call_model(..., max_tokens=WRITER_MAX_TOKENS)`; `_call_model` builds `extra={"max_tokens": ...}` and passes it to `model.complete`; `src/llm.py` `OpenAICompatibleModel.complete` puts it in the HTTP `body`. The wrapper on the real production path, `_CountedModel` in `src/generate.py`, forwards it (`**extra`). `_unreadable_refusal` is called from two sites in `_process_contact` (writer loop and the new outer `except llm.UnreadableAnswer`). Not test-only.

## 2. Can the acceptance check fail?

YES — check 1 (`== 1759`) fails on any change to the lint constants; acceptance command 2 demonstrates the failure input itself (`lint.MAX_WORDS *= 2` → 2884 ≠ 1759). Not vacuous. Caveat: the command verifies the constant's *value*, not its *delivery* — an accepts-and-drops seam (exactly the defect fixed in `scripts/task425_one_account_dry_run.py` `RecordingModel`) would still print OK. Delivery is only exercised by the 38-test module in part 3.

## 3. Do the numbers reconcile?

YES. From the two printed values alone: 2884 − 1759 = 1125 = the email term delta, and 5·MAX_WORDS·1.25 = 1125 ⟹ `lint.MAX_WORDS = 180`, exactly. Back-solving the total: 1125 + 5·NOTE_MAX_CHARS·0.25 + 3·MAX_SUBJECT·0.25 + 100 (P.S.) + 98 + 16 = 1759 ⟹ NOTE/subject terms = 420; one consistent solution is NOTE_MAX_CHARS=300, MAX_SUBJECT=60, 5 LinkedIn keys — matching the "five LinkedIn notes" comment and li1–li5 in the dry-run output. Also 1759/795 ≈ 2.2× as claimed. 38 tests, exit 0. Nothing unreconciled.

## Findings

**F1 (bounded, constructible).** `_json_unterminated` + the span fix misclassify prose containing an unmatched `{` before a complete object. Input: `Sure { here: {"em1": "hi"}` → depth ends at 1 → `TruncatedAnswer` (src/generate_campaign.py, `_parse_json`/`_json_unterminated`). The writer is then told "WAS CUT OFF… make it SHORTER" for an answer that finished, up to `MAX_WRITER_ATTEMPTS = 10` calls × 1759-token budget ≈ 17.6k completion tokens worst case per affected contact, ending in a `copy_refused` hold. Fail-closed, wrong diagnosis; frequency unmeasured.

**F2 (conditional, outside every part).** `OpenAICompatibleModel.complete` now raises `TruncatedAnswer` at the transport whenever `finish_reason == "length"` — including for callers that pass `max_tokens=None` and consume free text. Inside `_process_contact` this is handled (writer loop / new outer clause). Callers of `complete()` elsewhere in `src/generate.py` (Slack/assistant paths — only a 14-line hunk of that file is in any part) previously received truncated-but-deliverable text; whether they catch `ValueError` is not settleable from any part.

**Scope note:** `generate_campaign.py` (+287) implements truncation *classification* and a `_parse_json` rewrite — beyond the task title's "told how long," but load-bearing for the budget's retry semantics; the doc in part 3 presumably scopes it.

**Files not answering to the task:** none — every signature-only test change is forced by the seam change.

**Scratch files:** none; all 28 changed files are source/tests/docs.

VERDICT: PASS

### Part 2 — PASS



## 1. Does the new code have a production caller?

**PART 1.** Part 2 contains zero production lines — it is 12 test files, 60 changed lines, every one a mechanical widening of a fake's `complete()` signature to accept `max_tokens=None` (e.g. `tests/test_preproduction.py:52-53`, `tests/test_task400_rework2.py:37-38`). But part 2 is *evidence* the caller exists: if production never passed `max_tokens` as a keyword, none of these 12 fakes would need the parameter — an unwidened fake raises `TypeError` the moment part 1's plumbing calls it. The actual call site (`model.complete(..., max_tokens=...)` in `src/llm.py` / `src/generate_campaign.py`) is in part 1.

One flag to carry into part 1: the widening reaches **non-writer paths** — `test_slack_agent_conversation.py`, `test_slack_agent_numbers.py`, `test_slack_agent_scope.py`, `test_the_gag_stops_the_answer_not_the_request.py`, `test_the_readback_cache...`. The kwarg crosses the Slack-agent path, not just the campaign writer. If part 1 passes `WRITER_MAX_TOKENS` (1759) there instead of `None`, every conversational answer is capped at 1759 tokens on a path that has one retry for numbers and none for scope — a truncation there burns the retry or kills the turn. Whether that's uniform plumbing (fine) or an accidental cap is decided by part 1. No part-2 fake asserts on the value, so no test here would catch it.

## 2. Can the acceptance check fail?

Yes, all three are falsifiable — not vacuous:
- Check 2 fails on the obvious cheat: a literal `1759` reloads to `1759`, failing `> before`. It also fails if `generate_campaign` caches the value at import in a way `importlib.reload` doesn't refresh.
- Check 1 fails the moment upstream `lint.MAX_WORDS` changes (1759 → anything else) — a canary, not a tautology.
- Check 3 fails if `TruncatedAnswer` and `UnusableAnswer` collapse into one class or leave `ValueError`.

**Residual hole in the acceptance commands, not in part 2:** none of the three commands proves `max_tokens=WRITER_MAX_TOKENS` actually reaches the writer call — all three pass even if the kwarg is never passed to any model (and every part-2 widening would then be dead code). The binding proof must live in **PART 3** (`test_the_writer_is_told_how_long_its_answer_may_be.py`, the 38-test run); part 2's fakes all *accept and ignore* the value, so `max_tokens=0` would pass every part-2 test and truncate 100% of real answers.

## 3. Do the numbers reconcile?

Two reconciliations, one pointer:
- **Diffstat reconciles exactly.** Part 1 column: 515. Part 2: 3+6+3+15+3+3+6+3+3+6+3+6 = 60. Part 3: 693+62 = 755. Total 1330 = 1266 insertions + 64 deletions. No file hidden, none double-counted.
- **1759 → 2884 under doubled `MAX_WORDS` is arithmetically coherent** but only as an *affine* map: the variable part is 2884−1759 = 1125 and the fixed part is 1759−1125 = 634. (Fits exactly as `W+634` with MAX_WORDS=1125, or `1.25·W+634` with W=900.) Note 2×1759 = 3518 ≠ 2884 — so a fixed 634-token overhead term **must** exist in part 1's derivation; if part 1's formula is purely multiplicative, these two printed numbers cannot both be true. The formula itself is in **PART 1**; `lint.MAX_WORDS`'s value is in no part (lint.py unchanged).
- "Ran 38 tests" is countable only in **PART 3**.

## Also checked

- **Files answering to the task:** all 12 part-2 files do — they're the contract's test side. The seven Slack/conversation-file widenings are the scope question flagged in Q1; resolve in part 1 before calling them in-scope.
- **Scratch files:** none. No `*.txt`/`*.err`/`*.out` in the changed list. The stray `DRY RUN ... states {}` / `LIVE ENRICHMENT` lines in the test output are stdout prints from the dry-run script (part 1), not files.
- Minor: `tests/test_the_research_pack_has_one_shape.py` `UnparseableModel.complete` forwards `temperature=`, `client=`, and the trailing context cuts off before showing whether `max_tokens` reaches `super()` — harmless either way (parent defaults to `None`), but the fake loses budget visibility there.

**NO FINDING** constructible from part 2 alone — its 60 lines are mechanical and sum correctly. The two open risks (kwarg value on non-writer paths; the 634-token fixed term in the derivation) live in part 1, and the binding value-on-the-wire test lives in part 3.

VERDICT: PASS

### Part 3 — PASS



## 1. Production caller?

**YES — named.** The new code in *this* part is a test file and a doc; the production symbols it verifies live in part 1. The caller chain, confirmed by effect here: `tests/test_the_writer_is_told_how_long_its_answer_may_be.py::run_contact` (new file, ~lines 172–195) invokes the real `gc._process_contact`, and `RecordingStub` records the writer's `complete` receiving `max_tokens == gc.WRITER_MAX_TOKENS` (1759) on every one of `MAX_WRITER_ATTEMPTS` calls (`test_the_writer_call_carries_the_budget`, `test_every_retry_carries_it_too`). Upstream callers: `src/generate.py::_CountedModel` (forwarding pinned at `test_the_counting_wrapper_forwards_the_budget`) and `scripts/task425_one_account_dry_run.py::RecordingModel` (pinned in `TestTheDryRunSeamForwardsTheBudget` — this test exists precisely because that seam accepted-and-dropped the kwarg). The entrypoint→campaign wiring itself is asserted in part 2 (`tests/test_the_entrypoint_is_the_only_generation_path.py`); the literal `max_tokens=WRITER_MAX_TOKENS` call site is in part 1 (`src/generate_campaign.py`).

## 2. Can the acceptance check fail?

**Yes, all four — named inputs:**
- Cmd 2: replace the derivation with a literal 1759 → `1759 > 1759` is False → AssertionError. The doc records the measured passing pair 1759→2884, proving it moves.
- Cmd 4: delete `max_tokens=WRITER_MAX_TOKENS` from the writer call → `test_the_writer_call_carries_the_budget` red (`None != 1759`); delete `_parse_json`'s `_json_unterminated` branch → classification tests red. Both documented with the exact red test names.
- Cmd 3: alias the two classes → `is not` check fails.
- Cmd 1: change the derivation inputs → `== 1759` fails.

Not vacuous. One inherent limit: `test_every_term_comes_from_a_contract` recomputes with the same formula it polices, so it can't catch a *jointly* edited formula — but the reload command catches literal-ness, and the two ceiling-bound tests catch a number that drifts from `lint`.

## 3. Do the numbers reconcile?

**Mostly yes; one stale claim.**
- 38 tests run = I count 38 test methods in the new file (4+5+5+7+5+4+6+2). ✓
- 1759↔2884: doubling `lint.MAX_WORDS` gives `2·(1759−C)+C = 2884` ⟹ non-MAX_WORDS terms C = 634, MAX_WORDS term = 1125 — arithmetically consistent with a single linear derivation and `int()`. (The constants themselves are in part 1/`src/lint.py`, not recomputable here, but the equality test ran green.)
- 2724 chars ≈ 680 tokens (2724/4 = 681 ✓); 3942/795 = 4.96 ✓; `test_the_refusal_counts_the_object_not_the_prose`'s "6 characters" matches `'{"a":1'` ✓.
- **STALE:** the file header (~lines 57–75) and the REVIEW doc's Mutation section both claim "2 of 30 red" / "8 of 30 go red". The suite is 38 tests. Under the classification mutation, `TestProseAfterTheObjectIsNotATruncation::test_a_genuine_prefix_is_still_a_truncation` and `test_the_refusal_counts_the_object_not_the_prose` would also go red (both require `TruncatedAnswer`), so both denominator and numerator predate the 6-test regression class that class's own docstring says was added later. Cost: none in production — the guarantee is *stronger* than claimed (≥10/38 red) — but the REVIEW doc records a measurement that no longer describes the file it certifies. Update "of 30" → "of 38" and re-measure.

## Also

- Every changed file answers to the task: the ~20 test files with +3/−3 are forced mechanical updates (stub `complete` signatures must accept `max_tokens` now that production passes it); `tests/base.py`, `src/generate.py`, `scripts/task425_one_account_dry_run.py` are the seams the new tests pin. No stray file.
- No scratch files (*.txt / *.err / *.out) at repo root in this diff.

VERDICT: PASS
