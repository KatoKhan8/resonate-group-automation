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

## THE LEAKING MODULE IS ALREADY NAMED — START HERE

**Added 2026-09-28 from a full-suite run that was measuring something else.** You
do not have to search for the leaker for the third failure:

    test_no_module_left_a_variable_set  names ONE leaking module:
        tests/test_the_readback_cache_cannot_lie_about_its_age
    and the variable it leaks:
        QUEUE

That is a direct answer to scope item 1 for that failure. **Verify it rather than
trusting it** — the env guard's own output is the authority, and it only populates
during a discovered run, so reproduce it in a full run before acting. Then fix
the leak in that module (it should restore `QUEUE` rather than leave it set), and
confirm the failure goes away for the RIGHT reason: the guard reports no leaks
because none happened, not because the guard stopped looking.

**A second independent lead for the other two.** `scripts/glm_verify_branch.py`'s
`_load_baseline` was leaking a file handle on every call — a bare `open()` with no
`with` — fixed on master 2026-09-28, and the TASK-400 verdict independently found
the same shape at `tests/test_e2e.py:194`, where
`io.open(self.mx_cache, "w").write(...)` never closes. **On Windows an unclosed
handle can fail a later reopen or unlink of the same path**, which is exactly how
`test_a_dead_cta_link_is_refused` could pass alone and fail in company. Search for
that pattern rather than assuming those two share the `QUEUE` cause: three
order-dependent failures do not have to have one explanation, and deciding they
do is how the second cause survives the fix.

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
