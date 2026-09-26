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

## AMENDMENT 2026-09-26 — the ceiling does not refuse a model call at all

GLM finding **P1-1** and **T-1**, `docs/glm-reviews/canary-readiness-b333697.md`.
**Claude reproduced every claim against `origin/master` before this amendment.**
This task already owns `src/llm.py`'s ledger row, so it also owns this. **No
duplicate task exists or is to be created.**

`grep -n "spendledger" src/llm.py` returns exactly two hits, both inside
`_record_spend`, and both are `record`. **No model call in this system is
checked against any ceiling.** Three separate defects on one path:

1. **`_record_spend(self, model, usage)` takes `usage`** — it therefore runs
   *after* the model has answered. A ceiling checked there could not prevent
   the spend even if it raised.
2. **It never calls `spendledger.check`.** `src/spendledger.py:591` `check` is
   the only function that raises `BudgetExceeded`, and its only callers are
   `src/enrich.py:925` and the verification path. The LLM path is not one.
3. **`except Exception: pass` (`src/llm.py:296-297`)** would swallow
   `BudgetExceeded` / `MissingCeiling` if `record` ever raised one.

And `if provider is None: return` (`:286-287`) means any base URL that is not
groq / anthropic / openrouter — **GLM, xAI, a local server, the next provider
added** — writes **no ledger row at all**. That spend is not merely unrefused,
it is invisible. Given the model policy routes extraction, synthesis, QA,
grounding and reply classification to **GLM**, that is most of our model
traffic.

**`tests/test_a_model_call_writes_a_priced_ledger_row.py:184`
`test_anthropic_ceiling_refuses_when_exceeded` is a green test that cannot
fail.** It makes one real `model.complete()`, then calls `spendledger.check`
**by hand** and asserts that raises. It never makes a second `complete()`.
Delete `_record_spend` entirely and it still passes. It proves a property of
`check`, not of the model path — and acceptance 2 of this task as originally
written asks for the same weak shape. **Acceptance 2 is superseded by
acceptance 6 and 7 below.**

## Build, added

    src/llm.py    MODIFY. Wrap `complete()` in `spendledger.holding(...)` the
                  way `src/enrich.py:927` already does. Let `BudgetExceeded`
                  propagate — it is a refusal, not an error to log. Narrow the
                  `except` to the ledger's own I/O errors. An unrecognised
                  provider becomes a **named row or a refusal**, never a silent
                  return.

**One authoritative spend gate.** `holding(...)` is the existing shape, already
used by two callers and already concurrency-proven at K=8 in
`tests/test_a_provider_ceiling_refuses_before_the_call.py`. Do not write a
second gate, do not add a check in a caller of `llm.py`, and do not introduce a
new config key.

## Acceptance, added — RUN each, paste real output

6. **A model call is REFUSED before the provider is reached.** Set a ceiling
   below the next call's cost, call `model.complete("second call")`, assert it
   raises `BudgetExceeded`, **and assert `providers.request` was never
   invoked** — the surrounding tests already stub it, so the spy is free. This
   is the T-1 negative control and it is what closes the finding.

7. **The guard is seen to fail.** Revert your `holding(...)` change, re-run
   acceptance 6, confirm it FAILS on the old code, restore, confirm it passes.
   Paste both runs. Without the red run, acceptance 6 proves nothing.

8. **GLM writes a row.** Drive a fixture call against a GLM base URL and assert
   a ledger row exists naming a provider — not nothing. Then assert an
   unpriced or unknown provider's cost is recorded as **UNKNOWN, not zero**, and
   that `client_balance` still prints `MIXED UNITS` rather than summing.

9. **Retry and fallback paths are gated too.** `src/providers/glm.py` and any
   fallback in TASK-305's shape must not be a second unchecked door. Name
   every code path that reaches a paid model and state, per path, whether it
   now passes through `holding(...)`. A path you did not check is reported as
   unchecked, not as fine.
