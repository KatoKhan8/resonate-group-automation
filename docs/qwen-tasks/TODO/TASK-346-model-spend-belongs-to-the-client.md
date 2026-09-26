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
