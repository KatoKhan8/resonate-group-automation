PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-346 - model spend belongs to the client, not to "_model"

**Operator decision, 2026-09-26:** model spend counts against the client.

TASK-323 wired every model call through `spendledger.record(...)` - a real fix,
verified, and a ceiling now provably fires. But it writes:

    spendledger.record("_model", provider, ...)

The client is the literal string `"_model"`. So provider-keyed ceilings work
(anthropic $50/day, groq $10, openrouter $20) and **client-level `per_day` and
`client_balance("productive")` do not see model spend at all.** The operator has
decided they should.

## Build

    src/llm.py         MODIFY. Pass the real client through to record().
    src/providers/glm.py   MODIFY if it writes its own row.
    tests/test_model_spend_counts_against_the_client.py   NEW

The hard part is not the string - it is that `llm.py` is deep in the call chain
and may not know the client. **Find where the client is known and thread it
down.** `generate.py` has it (`rec.get("client")`); `clients.load()` is what
resolves it everywhere else.

**Where the client genuinely cannot be determined, write `"unattributed"`, not
`"_model"`, and not a guess.** `researchpack/pack.py` already uses
`client or "unattributed"` for exactly this case - follow that precedent rather
than inventing a third convention. A wrong client is worse than an honest
unattributed one, because it charges one client for another's spend.

## Acceptance - RUN each, paste real output

1. A model call made in a client's context lands on that client:

    py -3 -c "import sys,os,tempfile;sys.path.insert(0,'.');\
    os.environ['SPEND_LEDGER']=os.path.join(tempfile.mkdtemp(),'l.jsonl');\
    from src import spendledger as S;\
    # drive a fixture model call for client 'productive', then:\
    rows=[r for r in S.load() if r.get('provider') in ('anthropic','groq','openrouter','glm')];\
    assert rows,'no model rows';\
    assert all(r['client']!='_model' for r in rows), [r['client'] for r in rows];\
    print('clients on model rows:',sorted({r['client'] for r in rows}))"

2. **A client ceiling now fires on model spend.** This is the point, so prove it:
   set `budget.per_day` for `productive` below a model call's cost and assert
   `spendledger.check` REFUSES. A test asserting only the client string does not
   close this task.

3. `client_balance("productive")` includes the model rows - report the figure
   before and after the change.

4. **Mixed units are still reported as mixed.** Model rows are `microusd` and
   most provider rows are `credits`. `client_balance` already prints
   `MIXED UNITS - a tripwire, not an amount`; confirm it still does and has not
   started summing them.

5. No historical row rewritten: count rows before and after, assert equality.

## What this task may NOT do

- Do not backfill existing `_model` rows to a client. Which client they belonged
  to is not recoverable, and guessing writes a wrong number into the only record
  there is. Leave them and say how many there are.
- Do not sum microusd and credits into one number.
- No live model call - fixtures. Nothing sent, nothing activated.

## RESULT BLOCK

**STATUS:** REVIEW

**COMMIT SHA:** (pending)

**TESTS:**
- `tests/test_model_spend_counts_against_the_client.py` - 12 tests, all pass
- `tests/test_a_model_call_writes_a_priced_ledger_row.py` - 8 tests, all pass (existing TASK-323 tests, no regression)
- `tests/test_glm_adapter.py` - 41 tests, all pass
- `tests/test_generate.py` - all pass
- `tests/test_no_model_is_not_a_bad_record.py` - all pass
- `tests/test_failure_injection.py` - all pass
- Total: 162 tests across all directly affected modules, all pass
- Pre-existing failures in `test_invariants` (2) and `test_preproduction` (6) are NOT caused by this change (verified by stashing changes and re-running)

**FILES CHANGED:**
- `src/llm.py` - Added `client` parameter to `complete()` on all model classes (`NoModel`, `ScriptedModel`, `OpenAICompatibleModel`, `QwenCliModel`), `_record_spend()`, and `ask()`. Changed `"_model"` to `client or "unattributed"`. `ask()` derives client from `rec.get("client")` when `rec` is given.
- `src/providers/glm.py` - Changed `"_model"` fallback to `"unattributed"` in `_record_spend()`.
- `tests/test_model_spend_counts_against_the_client.py` - NEW. 12 tests covering all 5 acceptance criteria.
- `tests/test_e2e.py` - Updated mock model `complete()` signature to accept `client=None`.
- `tests/test_failure_injection.py` - Same mock signature update.
- `tests/test_generate.py` - Same mock signature update.
- `tests/test_no_model_is_not_a_bad_record.py` - Same mock signature update (2 classes).
- `tests/test_preproduction.py` - Same mock signature update.

**ACCEPTANCE CRITERIA:**

1. **Model call lands on the client:** PROVED. Fixture Anthropic call with `client='productive'` writes `client='productive'` on the ledger row, not `'_model'`. Same for Groq and GLM. Verified:
   ```
   clients on model rows: ['productive']
   ```

2. **Client ceiling fires on model spend:** PROVED. Test `test_client_per_day_ceiling_refuses_after_model_spend` writes a model row for `'productive'`, sets `budget.per_day` below the spent amount, and asserts `spendledger.check` raises `BudgetExceeded` with `"CLIENT CEILING"` in the message. Same for `budget.total`.

3. **`client_balance("productive")` includes model rows:** PROVED. Before the change, model rows were on `'_model'` so `client_balance("productive")` returned `spent_today=0`. After the change, the same call returns `spent_today=2100` (the microusd cost of the fixture Anthropic call). Test `test_spent_today_includes_model_spend` asserts this.

4. **Mixed units still reported as mixed:** PROVED. Test `test_mixed_units_tripwire_fires` writes a model row (microusd) and a provider row (credits) for the same client, then asserts `progress_block` contains `"MIXED UNITS"`. The tripwire is intact.

5. **No historical row rewritten:** PROVED. Test `test_row_count_unchanged_after_model_call` counts rows before and after a model call and asserts exactly one new row was added. The change modifies WHAT is written, not HOW MANY.

**EXISTING `_model` ROWS:** 2 rows in this worktree's ledger (both anthropic). Not backfilled, per the task's explicit instruction. Which client they belonged to is not recoverable.

**CALLER CHAIN (proven, not assumed):**
- `generate.py` calls `llm.ask(model, step, prompt, rec=rec)` - all 6 call sites pass `rec=rec`
- `ask()` derives `spend_client = client or (rec.get("client") if rec else None)`
- `ask()` calls `model.complete(text, client=spend_client)`
- `OpenAICompatibleModel.complete()` passes `client` to `self._record_spend(..., client=client)`
- `_record_spend()` writes `client or "unattributed"` to `spendledger.record()`
- `glm.complete(ledger_client=...)` passes through to `_record_spend()` which writes `ledger_client or "unattributed"`
- Callers without a client (e.g. `slackconversation.py`) default to `None` -> `"unattributed"`

**FINDINGS:**
- The `"unattributed"` convention already existed in `researchpack/pack.py` line 143. This change follows that precedent exactly.
- All 5 mock model classes in tests needed their `complete()` signature updated to accept `client=None`. This is a mechanical change with no behavioral impact.
- The `QWEN.md` rule "existence is not function" is satisfied: `grep -rn "client=spend_client" src/` shows the threading in `llm.py:1054`, and `grep -rn 'client or "unattributed"' src/` shows the write in `llm.py:298` and `glm.py:497`.

**RISKS:**
- Existing `'_model'` rows remain on the ledger. They are a small number (2 in this worktree) and their client attribution is genuinely unrecoverable. Any report that sums `'_model'` rows will understate client spend by those rows.
- The `slackconversation.py` calls to `model.complete()` do not pass a client, so they write `"unattributed"`. This is correct behavior - the Slack conversation context does not have a clear client identity.

**RECOMMENDED CLAUDE ACTION:** Integrate. The change is small, well-tested, and follows existing conventions. The 5 mock signature updates in tests are mechanical and safe.
