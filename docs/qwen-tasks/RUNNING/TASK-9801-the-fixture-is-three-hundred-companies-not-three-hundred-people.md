PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-9801 — the sandbox fixture is 300 PEOPLE across 100 companies, and the target is 300 COMPANIES

## The blocker, measured 2026-10-13

`scripts/sandbox_fixture.py` says so in its own docstring:

    WHAT THIS IS. 300 person-level prospect records across 100 companies, EXACTLY
    three decision makers each, partitioned into six HOMOGENEOUS cohorts of exactly 50.

So the previous run was **100 accounts**, not 300. The operator's target is
**exactly 300 synthetic companies/accounts**, with the person count reported
SEPARATELY rather than conflated with it. If the three-per-company rule stands,
that is **900 contacts**.

A run described as "300-account" while the fixture holds 100 companies is a
mislabelled run, which is why this is a blocker and not a tidy-up.

## What to change, and nothing else

ONLY `scripts/sandbox_fixture.py` and its tests. Do not touch the production
ICP or verification validators, and do not route around them.

    FORBIDDEN: src/providers/*  config/  work/*.jsonl  src/eligibility.py
               src/executionguard.py  scripts/sandbox_run.py

## The arithmetic you must redo, not assume

The current file derives its shape and the derivations change:

1. **Cohorts.** Cohorts are HOMOGENEOUS and hold no fewer than 50 records.
   900 records at exactly 50 is 18 cohorts. State the cohort count you chose
   and show it divides 900 exactly.
2. **Geographies.** The existing proof is `300 / 150 = 2`: three decision
   makers in one company have DISTINCT personas, so a company's records land
   in three different cohorts, so a geography cannot carry fewer than three
   cohorts, i.e. not fewer than 150 records. Redo that bound for 900 and state
   the result; do not copy the 2.
3. **Three per company stays an EQUALITY,** asserted as `== 3`, not a range.
   The operator made it an equality on 2026-10-12 and the old 2-3 tolerance let
   a company silently lose a contact.

## Acceptance — RUN each, paste the real output

1. Counts, as two separate numbers:

       py -3 scripts/sandbox_fixture.py --seed 1 --out /tmp/f1.json
       py -3 -c "import json;d=json.load(open('/tmp/f1.json'));\
       c={r['company_domain'] for r in d['records']};\
       print('companies',len(c));print('contacts',len(d['records']))"

   Must print `companies 300` and `contacts 900`.

2. **Three per company as an equality.** A test asserting `== 3` for every one
   of the 300 companies, and that it FAILS when one company is given 2 or 4.
   Paste both the pass and the deliberately-broken run.

3. **Determinism.** The same seed twice gives a byte-identical file:

       py -3 scripts/sandbox_fixture.py --seed 1 --out /tmp/a.json
       py -3 scripts/sandbox_fixture.py --seed 1 --out /tmp/b.json
       py -3 -c "import hashlib;print(hashlib.sha256(open('/tmp/a.json','rb').read()).hexdigest());\
       print(hashlib.sha256(open('/tmp/b.json','rb').read()).hexdigest())"

   Paste both hashes and state that they are equal. Then show seed 2 differs.

4. **Record the fixture hash and counts** in the result block: seed, SHA-256,
   company count, contact count, cohort count, geography count.

5. **No network, asserted.** The file imports no provider and makes no call.
   Show it: `py -3 -c "import ast,sys;t=ast.parse(open('scripts/sandbox_fixture.py').read());
   print([n.module for n in ast.walk(t) if isinstance(n,ast.ImportFrom)])"` and
   state that nothing in that list is a provider or a network module.

6. **Cohort invariants still hold at the new size:** every cohort homogeneous
   in geo, industry, headcount band, signal and persona; no cohort under 50.
   A test per invariant, each shown to fail when violated.

## Report

Companies and contacts as TWO numbers, never one. State explicitly that this
fixture is ENTIRELY INVENTED and that no byte of it was fetched or verified.
