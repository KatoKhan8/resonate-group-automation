# TASK-250 — 27 tests assert verification roles this client no longer uses

**This is a real backlog item found by measuring, not a guess.** Master has
carried it since 2026-09-21 afternoon and nobody noticed, because the suite
baseline everyone was diffing against was taken that morning.

    r53  2026-09-21 12:14Z   master   10,671 tests   50 failures   33 errors
    r58  2026-09-21 19:10Z   master   10,769 tests   76 failures   44 errors

The 27 new ones are enrichment, e2e and preproduction tests, and they all
have the same cause: Productive's verification roles changed that afternoon -
primary moved from ContactOut to Deliverable, ContactOut removed from
verification entirely - and these fixtures still build their evidence from
`(contactout, reoon)`. `verification.is_sendable` recomputes from the
evidence against the CLIENT's policy, so on a `productive` record that pair
is no longer a verified address, and the record lands `held` where the test
expects `approved`.

Proven, not inferred: check out `b9823c6f` - tonight's starting commit,
before any of this evening's work - and run
`tests.test_e2e.TestEnrichmentOutcomes.test_the_clean_domain_verifies`. It
fails there identically.

## WHAT TO DO

**Update the fixtures, not the policy.** The roles are an operator decision
recorded in `config/clients/productive.yaml` and asserted by
`tests/test_productive_verification_roles.py`. A test that goes green by
weakening them is worth less than the failure.

Two shapes of fix, and which one applies is per test:

  - the test is ABOUT verification -> give it the client's current pair,
    `(deliverable, reoon)`, and keep what it was asserting
  - the test is about something else and merely needs a sendable contact ->
    same change, one line, no ceremony. `tests/test_the_opener_asserts_nothing.py`
    was fixed this way on 2026-09-21 and its comment explains the rule.

A handful may be genuinely about ContactOut-as-verifier. Those move to a
client WITHOUT a verification block, where `policy_for` returns the
conservative default and ContactOut is still primary - which is the honest
place for them, because that is the only kind of workspace where that pair
still verifies.

## THE ONE THAT IS NOT A FIXTURE

`test_e2e.TestPushPreparationAndIdempotency.test_the_payloads_are_the_documented_shapes`
and the two `test_preproduction.TestApprovalIsRequired` errors are ERRORS
rather than failures. Read them before assuming they are the same cause;
an error is usually a different bug wearing the same coat.

## ACCEPTANCE

Full offline suite, and the number to beat is r58's: **10,769 / 76 / 44.**
Every one of the 27 named below should be gone and NOTHING new may appear.
Report the diff by test name in both directions.

Do not touch `src/verification.py`, `src/lint.py`, `src/approve.py` or
`config/clients/productive.yaml`. If a test cannot be fixed without one of
them, that is a finding: write it in the result block and stop.

## FILES FORBIDDEN

    src/verification.py   src/lint.py   src/approve.py
    config/clients/*.yaml   src/providers/*   work/*.jsonl

---

# ATTEMPT 1 FAILED AND WAS REVERTED. READ THIS BEFORE ATTEMPT 2.

`qwen-worker-r57` claimed this task (`61a2bc60`) and did the fixture work
(`126dcfa1`), then stopped: the file stayed in `RUNNING/` with no result
block and the worker exited. The infra session merged it on 2026-09-22,
measured, and **reverted it**.

**Measured, whole suite, before and after by name:**

    before r57   11,226 tests    82 distinct failures
    after  r57   11,346 tests   123 distinct failures

    gone:   6   test_e2e 2, test_invariants 1, PII guard 3 (the guard was
                master's fix, not r57's)
    new:   47   test_approve 14, test_push 13, test_cadence 5,
                test_generate 4, and 11 more across 8 modules

**IT MADE THE BASELINE 41 WORSE.**

## Why, exactly — and this is the trap for attempt 2

r57 changed the evidence in the SHARED phase fixtures from contactout to
deliverable:

    tests/fixtures/phase2.jsonl   read by test_audit, test_render
    tests/fixtures/phase5.jsonl   read by test_audit, test_generate,
                                  test_company_evidence_cache, test_siblings_block
    tests/fixtures/phase6.jsonl   read by test_personas
    tests/fixtures/phase7.jsonl   read by test_approve, test_cadence,
                                  test_double_verification, test_events

That fixed `test_e2e`, which was the target, and broke every OTHER consumer of
those files. The failures are `'blocked' != 'eligible'` — records that no
longer verify, so the gates below them refuse.

**The fixtures are shared and the task brief did not say so.** A change to
`phase7.jsonl` is a change to four test modules at once. That is the whole
difficulty of this task and it is why "27 tests" understates it.

## What attempt 2 has to do differently

1. **Enumerate every consumer of every fixture you touch, first.**
   `grep -rl phase7.jsonl tests/` before editing `phase7.jsonl`, not after.
2. **Run the FULL suite before and after and diff by name in both
   directions.** The brief already asked for this and attempt 1 did not do
   it — which is precisely how 47 new failures reached a merge. The baseline
   artifact is `docs/state/SUITE-BASELINE-2026-09-22.json`; regenerate it and
   `comm` the two.
3. Consider whether the shared fixture should be SPLIT instead: a
   verification-specific fixture for the tests that are about verification,
   leaving the shared ones alone. Four modules sharing one evidence blob is
   what makes a one-line change cost 47 failures.
4. r57's approach was otherwise RIGHT and is worth recovering rather than
   re-inventing — evidence to deliverable, a deliverable cassette,
   `confirm_deliverable_contract()` in the e2e setup. The commit is
   `126dcfa1` on `qwen-worker-r57`, unmerged and preserved.
