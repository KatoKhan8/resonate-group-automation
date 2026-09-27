PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-449 — three order-dependent failures, diagnosed and not dismissed

Off the critical path. Evidence: `docs/SUITE-TRUTH-2026-09-27-NIGHT.md`.

These three fail in the FULL suite run and PASS standalone — confirmed by
`scripts/suite_baseline.py`'s own `order_dependent` set at `0a4c9317` and by
running them directly on master, where they pass:

    test_a_dead_cta_link_is_refused.GuardFailureTests.test_removing_allowlist_check_lets_dead_link_through
    test_a_dead_cta_link_is_refused.ProductionPathTests.test_allowlisted_url_passes_through_check_batch
    test_no_test_leaves_the_environment_changed.NoModuleLeavesTheEnvironmentChanged.test_no_module_left_a_variable_set

## THE STANDING RULE, WHICH IS WHY THIS IS A TASK AND NOT A SHRUG

CLAUDE.md: **"An intermittent failure is diagnosed - alone, as a class, and in an
isolated full run - never dismissed."** All three orderings are required; a pass
in one of them is not an answer.

A test that passes alone and fails in company is the WORSE of the two directions
to shrug at, because the thing it depends on is another module's leftover state —
which means some module is leaking, and **the leak is the defect rather than the
test.** `tests/base.py` documents that `unittest discover` and `tests.offline`
both bind loopback and build demo estates, and that run back to back they still
overlap during teardown.

**Note what the third test says about itself:** "no leaks recorded. If this was
not a full suite run, that is a pass about nothing: the record is populated by
build_suite() in tests/offline.py, so only a discovered run fills it." So its
standalone pass is not evidence in either direction. Do not cite it as one.

A live lead: the integration pass on 2026-09-27 fixed a store-isolation leak that
`TASK-332`'s test shipped — it discarded the restore callable
`store.use_directory` returns, in four places. Check whether these three are
downstream of that same class of leak, and whether any remain.

## SCOPE

1. **Find which module leaves the state these three depend on.** Name it. The
   answer is a specific module and a specific piece of state, not "test
   pollution".
2. **Fix the LEAK, not the symptom.** Do not reorder the suite, do not add a
   sleep, do not mark anything expected-failure, and do not make the affected
   tests defensive against dirty state — that hides the leak for the next test
   that has no such defence.
3. If the real cause is a genuine framework-level overlap that cannot be fixed
   from here, say so explicitly with the evidence, and propose the smallest
   honest containment. "Cannot fix, here is why, here is what it costs" is an
   acceptable outcome; silently reclassifying it is not.

## ACCEPTANCE

1. All three pass **alone, as a class, AND in an isolated full run** — state the
   result of each of the three orderings separately.
2. The leaking module and the leaked state are NAMED in the result.
3. A MUTATION: reintroduce the leak and confirm the failures come back, proving
   you fixed the cause and not a coincidence. Assert the file changed; restore
   byte-identically (this tree is CRLF).
4. No new failing name in the suite, compared by NAME with the same harness on
   both sides.
5. `docs/state/SUITE-BASELINE-2026-09-26.txt` is NOT edited.

Provider writes 0, never call a real provider, freeze in force. Do not touch
`src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`,
`src/generate.py`, `tests/test_generate.py`, `src/packfacts.py`, `src/ingest.py`
or `src/copylint.py`.
