PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-323 — model spend is invisible to the ledger

**Operator order, 2026-09-26.** Every model call must write a ledger row
through `spendledger.record(..., unit="microusd")`. Today none of them do.

Measured on master at `4268197a`, not assumed:

    src/providers/glm.py        grep -c spendledger  ->  0
    src/providers/groq.py       does not exist on master at all
    anthropic adapter           TASK-308, MERGE-BLOCKED: hardcodes
                                expected_cost=0 and writes dollars into a new
                                `amount` field, so spent() totals zero and no
                                ceiling can ever fire
    LEDGER_UNITS                has anthropic, groq, openrouter -> microusd.
                                "glm" IS ABSENT, so unit_for("glm") returns
                                DEFAULT_UNIT "credits", and USD_PER_UNIT
                                ["credits"] is None -> usd_estimate None

Consequence, from the handoff §9: **the ledger shows zero rows for a night
that spent ~$3.88.** Ceilings exist (`anthropic $50/day, groq $10,
openrouter $20`) and cannot fire, because nothing writes the rows they read.

## The contract you write through, exactly as it is

    spendledger.record(client, provider, call, expected_cost,
                       run_id=None, at=None, rows=None, unit=None)

- `expected_cost` is stored as `int(expected_cost or 0)`. **Never pass
  dollars.** $0.00256 becomes 0 and a 50-lead cohort ledgers as zero. This is
  the exact defect that merge-blocked TASK-308.
- `spendledger.to_micro_usd(usd)` is the only conversion. $0.00256 -> 2560.
- Pass `unit="microusd"` explicitly on every row. Do not rely on
  `LEDGER_UNITS`; a row that carries its own unit is believed over that table.
- `run_id` defaults to `current_run()`. Do not pass None.

## What to change

    src/providers/glm.py          ADD the record() call. Zero today.
    src/providers/groq.py         DOES NOT EXIST on master. TASK-305's adapter
                                  is on a branch only. Create it here ONLY if
                                  absent; if you find it, wire it and say so.
    src/providers/anthropic.py    Write it correctly the first time, through
                                  record(..., unit="microusd"). Do NOT reuse
                                  TASK-308's `amount` field or its
                                  expected_cost=0.
    src/spendledger.py            Add "glm": "microusd" to LEDGER_UNITS.
    config/model-prices.yaml      NEW. USD per 1M input and output tokens, per
                                  model, each entry carrying `source` (the URL
                                  the price was read from) and `as_of` (date).
    tests/test_a_model_call_writes_a_priced_ledger_row.py   NEW

## The rule about a price nobody has

**Do not invent a rate.** If a model is absent from `config/model-prices.yaml`,
still write the row — `unit="microusd"`, `expected_cost=0`, and the token
counts in `rows` — so the call is VISIBLE and visibly unpriced. A missing row
and a free call are indistinguishable in the ledger, and that is the failure
here. A zero row with token counts is neither.

Each adapter already knows its usage: `glm.py` has `_usage(data)`. Use it.
Do not estimate tokens by counting characters.

## Acceptance — each must be RUN and its real output pasted

1. Every adapter writes a row:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as S;\
    n0=len(S.rows());\
    from src.providers import glm;\
    print('glm rows delta', len(S.rows())-n0)"

   with a fixture response, not a live call. A live call is NOT required and
   NOT authorised for this task.

2. Dollars never reach `expected_cost`:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as S;\
    assert S.to_micro_usd(0.00256)==2560, S.to_micro_usd(0.00256);\
    r=[x for x in S.rows() if x.get('provider')in('glm','groq','anthropic')];\
    assert r, 'no model rows written';\
    assert all(x.get('unit')=='microusd' for x in r), 'a model row is not microusd';\
    assert all(isinstance(x['expected_cost'],int) for x in r);\
    assert not any(0 < x['expected_cost'] < 1 for x in r), 'dollars in expected_cost';\
    print(len(r),'model rows, all microusd')"

3. **A ceiling can now actually fire.** This is the point of the task, so
   prove it rather than asserting the row shape:

    py -3 -m unittest tests.test_a_model_call_writes_a_priced_ledger_row -v

   must contain a test that sets the anthropic ceiling below the next call's
   cost and asserts `spendledger.check` REFUSES. A test that only asserts rows
   exist does not close this task.

4. `glm` unit is no longer `credits`:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as S;\
    assert S.unit_for('glm')=='microusd', S.unit_for('glm');\
    u,rate,src=S.usd_estimate(2560,'microusd');\
    assert abs(u-0.00256)<1e-9 and src=='unit_definition', (u,src);\
    print('glm microusd, usd_estimate', u, src)"

5. The full suite is no worse. Run it, wait for `work/suite_verdict.txt`, and
   report the failing-name SET against the baseline — **not a count.** A count
   that matches while the names differ has passed a broken suite before.
   **Do not grep for `^FAIL:` mid-run: it always returns 0 while the suite is
   still running.**

## What this task may NOT do

- No live model call. No provider write. Nothing sent, nothing activated.
- Do not change `expected_cost` to a float. It would change behaviour for
  every provider to fix three, and every ceiling and all 17,937 existing rows
  depend on it being an int.
- Do not backfill historical rows. The cents-vs-credits backfill rate is an
  open operator decision (handoff §10.4) and guessing it writes a wrong number
  into the only record we have.
- Do not widen or raise a ceiling to make a test pass.

## Completion report

Section 11 of `docs/OPERATOR-DIRECTIVES-2026-09-25.md`, in full, with the
REMOTE SHA verified on GitHub. A local commit is not a completed task.
