# GLM branch verification: TASK-323

Branch: `qwen-worker-2-r59`
Date: 2026-09-26T12:03:33.565132+00:00
Model: glm-5.3
Duration: 74.064s
Usage: {'prompt_tokens': 2275, 'completion_tokens': 5786, 'total_tokens': 8061, 'reasoning_tokens': 4948, 'cached_tokens': 1344}

## Verdict: FAIL

**two of four acceptance commands exit=1 (`spendledger.rows` does not exist), so ledger visibility was never verified end-to-end and the task doc is empty and still in RUNNING.**

## GLM spend

This call: 1 ledger rows, 10168 micro-USD

## Changed files (7)

- `config/model-prices.yaml`
- `docs/qwen-tasks/RUNNING/TASK-323-model-spend-is-invisible-to-the-ledger.md`
- `src/llm.py`
- `src/modelprices.py`
- `src/providers/glm.py`
- `src/spendledger.py`
- `tests/test_a_model_call_writes_a_priced_ledger_row.py`

## Diff stat

```
 config/model-prices.yaml                           |  44 ++++
 ...K-323-model-spend-is-invisible-to-the-ledger.md |   0
 src/llm.py                                         |  49 ++++
 src/modelprices.py                                 |  81 ++++++
 src/providers/glm.py                               |  37 ++-
 src/spendledger.py                                 |   3 +-
 ...test_a_model_call_writes_a_priced_ledger_row.py | 281 +++++++++++++++++++++
 7 files changed, 492 insertions(+), 3 deletions(-)

```

## Acceptance output

```
$ py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as S; n0=len(S.rows()); from src.providers import glm; print('glm rows delta', len(S.rows())-n0)"
exit=1
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import sys;sys.path.insert(0,'.');from src import spendledger as S; n0=len(S.rows()); from src.providers import glm; print('glm rows delta', len(S.rows())-n0)
                                                                               ^^^^^^
AttributeError: module 'src.spendledger' has no attribute 'rows'

$ py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as S; assert S.to_micro_usd(0.00256)==2560, S.to_micro_usd(0.00256); r=[x for x in S.rows() if x.get('provider')in('glm','groq','anthropic')]; assert r, 'no model rows written'; assert all(x.get('unit')=='microusd' for x in r), 'a model row is not microusd'; assert all(isinstance(x['expected_cost'],int) for x in r); assert not any(0 < x['expected_cost'] < 1 for x in r), 'dollars in expected_cost'; print(len(r),'model rows, all microusd')"
exit=1
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import sys;sys.path.insert(0,'.');from src import spendledger as S; assert S.to_micro_usd(0.00256)==2560, S.to_micro_usd(0.00256); r=[x for x in S.rows() if x.get('provider')in('glm','groq','anthropic')]; assert r, 'no model rows written'; assert all(x.get('unit')=='microusd' for x in r), 'a model row is not microusd'; assert all(isinstance(x['expected_cost'],int) for x in r); assert not any(0 < x['expected_cost'] < 1 for x in r), 'dollars in expected_cost'; print(len(r),'model rows, all microusd')
                                                                                                                                                     ^^^^^^
AttributeError: module 'src.spendledger' has no attribute 'rows'

$ py -3 -m unittest tests.test_a_model_call_writes_a_priced_ledger_row -v
exit=0
test_anthropic_call_writes_a_priced_row (tests.test_a_model_call_writes_a_priced_ledger_row.AnthropicWritesALedgerRow.test_anthropic_call_writes_a_priced_row)
OpenAICompatibleModel pointed at Anthropic writes a microusd row. ... ok
test_anthropic_ceiling_refuses_when_exceeded (tests.test_a_model_call_writes_a_priced_ledger_row.CeilingCanFire.test_anthropic_ceiling_refuses_when_exceeded)
Set a $1 ceiling, spend $2 worth, check REFUSES the next call. ... ok
test_all_model_rows_are_microusd_with_int_cost (tests.test_a_model_call_writes_a_priced_ledger_row.DollarsNeverReachExpectedCost.test_all_model_rows_are_microusd_with_int_cost)
No model row carries dollars in expected_cost. ... ok
test_unit_for_glm_is_microusd (tests.test_a_model_call_writes_a_priced_ledger_row.GlmUnitIsMicrousd.test_unit_for_glm_is_microusd) ... ok
test_usd_estimate_for_microusd (tests.test_a_model_call_writes_a_priced_ledger_row.GlmUnitIsMicrousd.test_usd_estimate_for_microusd) ... ok
test_a_priced_row_is_written_after_a_fixture_call (tests.test_a_model_call_writes_a_priced_ledger_row.GlmWritesALedgerRow.test_a_priced_row_is_written_after_a_fixture_call)
glm.complete() with a fixture response writes a microusd row. ... ok
test_an_unpriced_model_still_writes_a_row (tests.test_a_model_call_writes_a_priced_ledger_row.GlmWritesALedgerRow.test_an_unpriced_model_still_writes_a_row)
A model absent from model-prices.yaml gets cost=0, not no row. ... ok
test_groq_call_writes_a_priced_row (tests.test_a_model_call_writes_a_priced_ledger_row.GroqWritesALedgerRow.test_groq_call_writes_a_priced_row)
OpenAICompatibleModel pointed at Groq writes a microusd row. ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.163s

OK

$ py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as S; assert S.unit_for('glm')=='microusd', S.unit_for('glm'); u,rate,src=S.usd_estimate(2560,'microusd'); assert abs(u-0.00256)<1e-9 and src=='unit_definition', (u,src); print('glm microusd, usd_estimate', u, src)"
exit=0
glm microusd, usd_estimate 0.0025599999999999998 unit_definition
```

## GLM response

## 1. Production caller?

SPLIT. The write path has one: `src/providers/glm.py::complete` and `src/llm.py::OpenAICompatibleModel` now emit priced rows — the passing fixture tests (`test_a_priced_row_is_written_after_a_fixture_call`, `test_groq_call_writes_a_priced_row`) invoke the real `glm.complete()`/`OpenAICompatibleModel`, so the pricing code is on a production call path, not test-only. But the bridge looks like a shim: `src/spendledger.py` is only +2/−1, i.e., re-exports (`unit_for`, `usd_estimate`, `to_micro_usd` actually live in the new `src/modelprices.py`, 81 lines). The only demonstrated callers of the spendledger re-exports are tests and acceptance one-liners — NO production caller of the bridge is in evidence, and the one command that would prove end-to-end production wiring (`from src.providers import glm` → rows delta) dies before it measures anything. Diff body not provided, so exact line cites are impossible; going by file/test names only.

## 2. Can the acceptance check fail?

It already did — twice, exit=1: `AttributeError: module 'src.spendledger' has no attribute 'rows'`. This is input-independent: the check fails on 100% of inputs because the API it probes doesn't exist on this branch. The two crashed commands are precisely the ones that verify the task's title claim ("model spend is invisible to the ledger") against the live ledger; the 8 passing tests use fixtures and never touch it. Secondary vacuity: in command 2, `assert not any(0 < x['expected_cost'] < 1)` can never fire once `isinstance(x['expected_cost'], int)` holds — no integer satisfies `0 < x < 1`. Dead guard.

## 3. Do numbers reconcile?

- Diffstat: yes. Per-file changes include deletions: glm 37 = +35/−2, spendledger 3 = +2/−1 → insertions 44+49+81+35+2+281 = 492 ✓, deletions 3 ✓, 7 files ✓.
- 8 tests listed = "Ran 8 tests" ✓ (both runs).
- `to_micro_usd(0.00256)==2560` passed (command 2 reached `S.rows()` past the assert) ✓; `usd_estimate(2560)` → 0.00256 ✓.
- What does NOT reconcile: "task complete" vs. the record. `docs/qwen-tasks/RUNNING/TASK-323-...md` is 0 lines — empty — and still under RUNNING/, not DONE. Nothing documents the run whose completion is claimed.

## Also

- Every changed file plausibly answers to TASK-323 except the task doc, which is empty and un-moved — it answers in name only.
- No scratch files among the changed files (no *.txt/*.err/*.out at root). Untracked files can't be ruled out from a diffstat.
- Latent defeat worth naming: `test_an_unpriced_model_still_writes_a_row` enshrines cost=0 for any model id absent from `config/model-prices.yaml`. A typo'd or newly renamed model id books $0 forever, `usd_estimate` returns 0, and the ceiling tested in `test_anthropic_ceiling_refuses_when_exceeded` can never trip — at 1M calls/day on a $0.0005/call model that's $500/day of spend invisible to the ledger, i.e., the exact bug TASK-323 claims to fix, surviving silently.

VERDICT: FAIL - two of four acceptance commands exit=1 (`spendledger.rows` does not exist), so ledger visibility was never verified end-to-end and the task doc is empty and still in RUNNING.
