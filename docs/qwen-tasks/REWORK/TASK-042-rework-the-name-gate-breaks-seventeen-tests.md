# TASK-042 REWORK - the gate is right, the wiring breaks seventeen tests

## THE VERDICT

REJECTED for integration, not for design. `cohort_names_from` is a good idea
and its reasoning is right - matching the COHORT rather than the whole estate,
and excluding tokens under three characters because the false-positive rate on
two-letter words makes a gate unusable. Keep both. The branch is not lost.

## WHAT HAPPENS WHEN IT IS APPLIED TO MASTER

    tests.test_the_sequence_belongs_to_nobody        12 ERRORS
    tests.test_campaign_repetition_integration        1 ERROR, 4 FAILURES
    ----------------------------------------------------------------
                                                     17 broken

Reverted on master; master is green at 26/26 on those two modules.

## WHY THIS MATTERS MORE THAN AN ORDINARY TEST FAILURE

`test_the_sequence_belongs_to_nobody` is the module that protects the exact
defect TASK-042 exists to prevent: campaign 599020 held "hi jacob" for a
canonical row naming fourteen records. Those twelve tests are the reason that
can never silently return.

**A name gate that breaks the name-tenancy tests has to be wrong somewhere.**
Either the wiring changed a signature those tests call, or the gate refuses
fixtures that are legitimately clean. Both are fixable; neither is fixed by
updating the tests.

## WHAT TO DO

1. Run `py -3 -m unittest tests.test_the_sequence_belongs_to_nobody
   tests.test_campaign_repetition_integration` FIRST, before anything else,
   and read the actual errors. Twelve ERRORS rather than FAILURES usually
   means a signature or an exception, not an assertion.

2. Classify each one in writing: is it the wiring, or is it the gate
   refusing something clean? `CLAUDE.md`: "A failing test is a question about
   the system, not an obstacle."

3. Fix the smallest root cause. **Do not weaken a sequence-tenancy
   assertion to make the gate pass.** If you conclude a test encodes an
   assumption the gate legitimately invalidates, say precisely which
   assumption and why the change is safe - and expect that argument to be
   read closely.

4. Re-run the full affected surface before moving to REVIEW:

       tests.test_the_sequence_belongs_to_nobody
       tests.test_campaign_repetition_integration
       tests.test_a_person_can_enter_a_heyreach_campaign
       tests.test_heyreach_readback
       tests.test_heyreachfactory_name_gate

   Report the real exit code. Never pipe a test run into a filter and read
   the filter's status.

## THE PROCESS NOTE

The result block said REVIEW with tests passing. The tests that pass are your
own new ones; the surface the change sits on was not run. That is the single
most common way a green result reaches Claude and has to be sent back - it
happened four times on 2026-09-14. Run the neighbours, not just the new file.

## WHAT YOU MAY NOT DO

- Do not weaken `test_the_sequence_belongs_to_nobody`.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- No provider write.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (with the real exit code), FILES CHANGED, FINDINGS,
RISKS, RECOMMENDED CLAUDE ACTION.
