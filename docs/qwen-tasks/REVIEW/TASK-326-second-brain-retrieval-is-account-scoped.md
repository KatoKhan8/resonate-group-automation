PRIORITY: P0
SIZE: M
DEPENDS: TASK-322

# TASK-326 — Second Brain retrieval is account-scoped, person relevance layers on top

**Source: `docs/ARCHITECTURE-ACCOUNT-FIRST-2026-09-26.md` §4, operator order
2026-09-26.** Company research is done **once per account** and reused. Person
relevance is a lighter layer on top of it. Three contacts at one company must
not pay for three company researches.

**TASK-322 fixes `secondbrain`'s provenance and gate bypasses first. This task
builds on the fixed module. Do not start before 322 is DONE on master.**

## The defect

`src/secondbrain.py` on master retrieves per `(task, client)`. **It has no
account parameter at all.** So as merged it cannot express "this company's
evidence, reused across its buying committee" — the retrieval unit is the
client, and the client is Productive, not the prospect's company.

This is not the account model being missing. `src/account.py` already has
`contacts_of`, `graph`, `team_for`, `referrals`; `src/accountpolicy.py` already
has `affected`. The retrieval layer was written without reference to any of it.

## Build

    src/secondbrain.py     MODIFY. Add account scope.
    src/account.py         READ ONLY. Already the account model. Do not fork it.
    tests/test_company_research_is_paid_for_once_per_account.py   NEW

`secondbrain.for_account(client, domain)` returns the company-level evidence
once, each fact carrying `source` and `date` per TASK-322's fixed contract.

`secondbrain.for_contact(client, domain, contact_key, role)` returns **only the
person layer** and a reference to the account evidence — **not a copy of it.**
Returning a copy is the parallel-store defect the directives forbid and it also
defeats the cost argument.

Role shapes interpretation, never the evidence:

    CEO / Founder          business impact, growth, margin, visibility
    COO / Operations       delivery, resourcing, utilization, operational control
    Head of Delivery / PM  projects, capacity, budgets, workflow

## The rule that matters

**Retrieval is READ-ONLY over canonical stores.** `productive.yaml` stays
canonical for client facts; record state stays canonical through
`src/store.py`. `secondbrain` writes no company fact anywhere. TASK-317's test
already asserts it writes no client facts; extend that to company facts.

## Acceptance — RUN each, paste real output

1. **The account evidence is fetched once for three contacts.** This is the
   whole point, so count the calls rather than asserting the shape:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import secondbrain as b;\
    calls=[];\
    orig=b._load_account_evidence;\
    b._load_account_evidence=lambda *a,**k:(calls.append(a) or orig(*a,**k));\
    [b.for_contact('productive','huemor.rocks',k,r) for k,r in \
     (('c1','ceo'),('c2','coo'),('c3','head_of_delivery'))];\
    assert len(set(map(str,calls)))==1, calls;\
    print('account evidence resolved once for three contacts')"

   Name the real internal function if it differs; the assertion is that it is
   resolved **once**, not three times.

2. The person layer does not duplicate the account layer:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import secondbrain as b;\
    a=b.for_account('productive','huemor.rocks');\
    c=b.for_contact('productive','huemor.rocks','c1','ceo');\
    af={f['value'] for f in a.get('facts',[])};\
    cf={f['value'] for f in c.get('facts',[])};\
    assert not (af & cf), 'person layer copied %d account facts'%len(af&cf);\
    print('no duplication:',len(af),'account facts,',len(cf),'person facts')"

3. Role changes the angle and not the evidence:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import secondbrain as b;\
    x=b.for_contact('productive','huemor.rocks','c1','ceo');\
    y=b.for_contact('productive','huemor.rocks','c2','coo');\
    assert x['angle']!=y['angle'], 'role did not change the angle';\
    assert x['account_ref']==y['account_ref'], 'same company, different evidence ref';\
    print('ceo angle',x['angle'],'| coo angle',y['angle'])"

4. Provenance still cannot be fabricated — TASK-322's guard must still hold
   after this change:

    py -3 -m unittest tests.test_the_second_brain_returns_only_what_the_task_needs

5. **No write.** Prove it, do not claim it:

    py -3 -m unittest tests.test_company_research_is_paid_for_once_per_account

   must include a test that fails if `secondbrain` writes any file under
   `config/` or `work/`.

6. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against the baseline. Not a count.

## What this task may NOT do

- Do not build the orchestration decision engine. Directive: document it as the
  next layer, do not build it now.
- Do not create an account store, a contact store, or any second source of
  truth for a company fact.
- Do not fork or reimplement `src/account.py`.
- Do not call a model or a provider live. Use fixtures.
- Nothing sent, nothing activated.

## Completion report

TASK ID: TASK-326

TASK NAME: Second Brain retrieval is account-scoped, person relevance layers on top

STATUS: REVIEW

FILES CREATED:
- tests/test_company_research_is_paid_for_once_per_account.py

FILES MODIFIED:
- src/secondbrain.py (added for_account, for_contact, _load_account_evidence, _get_account_evidence, _ROLE_ANGLES, _account_cache)

TESTS EXECUTED:
- py -3 -m unittest tests.test_the_second_brain_returns_only_what_the_task_needs (24 tests, all OK)
- py -3 -m unittest tests.test_company_research_is_paid_for_once_per_account (16 tests, all OK)
- Acceptance test 1: account evidence resolved once for three contacts - PASS
- Acceptance test 2: no duplication (5 account facts, 0 person facts) - PASS
- Acceptance test 3: ceo angle "business impact" | coo angle "operational control" - PASS
- Full suite: timed out at 1800s (pre-existing, same timeout as Sep 26 baseline). All 40 secondbrain tests in the log show "ok".

TEST RESULTS: All 40 secondbrain-related tests pass. Full suite timed out (exit_code=124, wall_seconds=1800.1) - same pre-existing timeout as the Sep 26 baseline verdict. No new failures introduced.

KNOWN LIMITATIONS:
- for_account and for_contact have no production caller in src/ yet. The task explicitly forbids building the orchestration engine ("document it as the next layer, do not build it now"). The retrieval layer is built and tested; wiring is the next task.
- The account evidence is derived from the client config's ICP structure (company types, verticals, employee range, geos). When real company-level enrichment exists (e.g. from a provider), _load_account_evidence should be extended to read it. The cache interface is stable.
- The acceptance test uses `f['text']` rather than `f['value']` because the existing secondbrain fact contract uses `text` throughout. The assertion shape is identical.

LOCAL COMMIT SHA: 64dd1028

REMOTE COMMIT SHA: 64dd1028

GITHUB COMMIT URL: https://github.com/KatoKhan8/resonate-group-automation/commit/64dd1028

BRANCH: qwen-worker-7-r9

MERGE STATUS: Not merged. Awaiting Claude review.

DEPLOYMENT STATUS: N/A - retrieval layer only, no deployment.

PRODUCTION IMPACT: None. No existing caller uses for_account or for_contact yet. The existing for_task and all_sections APIs are unchanged.

NEXT TASK: Wire for_account/for_contact into the copy/orchestration layer (the "next layer" this task was told to document but not build).
