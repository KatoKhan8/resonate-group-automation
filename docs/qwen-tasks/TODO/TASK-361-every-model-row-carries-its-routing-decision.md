PRIORITY: P0
SIZE: M
DEPENDS: TASK-360

# TASK-361 - every model row carries its routing decision

**Operator scope 2, 2026-09-26**, from the model-routing directive section 17.

TASK-323 made model spend visible; TASK-346 moves it onto the client. This makes
each row say **what decision produced it**, so cost attribution is possible later
without re-deriving anything.

## Fields, on every model row through `spendledger.record`

    task_type          client            campaign
    account            contact           model
    policy_version     reasoning_level   input_tokens
    cached_input_tokens               output_tokens
    latency            retries           fallback_used
    gate_result

`cached_input_tokens` matters specifically: TASK-355 is adding cache-aware pricing
and the rows must carry the counts for it to price. Where the provider does not
report a cached count, write **absent, not zero** - zero is a claim that nothing
was cached, and that is a different statement from "the provider did not say".

## The rule that governs the shape

**Do not add a second ledger.** `spendledger` is the one, `actionledger` is the
other and they have different jobs. Extend the row.

`record()` stores `expected_cost` as `int()`, so **nothing here may change that
column's meaning** - all 17,937 existing rows and every ceiling depend on it.
These are additional fields alongside it.

**An old row without the new fields must still read correctly.** Most rows on disk
predate this. Follow `row_unit`'s existing precedent: a row that carries its own
value is believed, and absence is read as the convention, never back-filled with
an invented default.

## Acceptance - RUN each, paste real output

1. A fixture model call writes every field:

    py -3 -c "import sys,os,tempfile;sys.path.insert(0,'.');\
    os.environ['SPEND_LEDGER']=os.path.join(tempfile.mkdtemp(),'l.jsonl');\
    from src import spendledger as S;\
    # drive a fixture call, then:\
    r=[x for x in S.load() if x.get('task_type')][-1];\
    need={'task_type','client','model','policy_version','reasoning_level',\
          'input_tokens','output_tokens','latency','retries','fallback_used'};\
    missing=need-set(r);\
    assert not missing, missing;\
    print('all fields present:',sorted(need))"

2. **A missing cached count is ABSENT, not zero.** Assert the key is absent when
   the provider reports nothing, and present when it reports a number.

3. **Old rows still load.** Read a row written before this change and assert no
   exception and no fabricated field.

4. **The ceiling still fires.** TASK-323's `CeilingCanFire` test must still pass -
   adding observability may not break the control. Paste it.

5. **`policy_version` comes from the policy file**, not a literal. Change the
   version in `config/model_policy.yaml`, make a fixture call, assert the row
   carries the new value.

6. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not create a second ledger. Do not change `expected_cost`'s unit or type.
- Do not backfill historical rows with invented values.
- Do not make a live model call.
- Nothing sent, nothing activated.
