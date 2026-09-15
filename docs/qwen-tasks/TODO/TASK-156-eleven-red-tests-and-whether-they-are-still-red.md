PRIORITY: P2
DEPENDS:

# TASK-156 - the eleven pre-existing failures, and what each one means

## THE FACT

The full suite reports failures that are NOT from the current work. Eleven
were reproduced at commit 270de5e, in a clean worktree, before any of today's
changes:

    test_ingest                                   2 errors
    test_a_bounced_address_stops_being_sendable   1
    test_mutation_anchors                         1  (events.py, assignment.py)
    test_nothing_writes_to_a_provider             1  (two scripts POST)
    test_referral                                 1
    test_replaysim                                2
    test_the_account_is_the_unit_of_outreach      3

Checkpoint E does not mention them, so a fresh session reads a red suite as
damage it just did. TASK-123 is already about eleven red tests and the count
is not a coincidence - reconcile the two.

## WHAT THIS TASK IS

For each failure, exactly one of three verdicts, with evidence:

    STALE TEST      the system changed deliberately and the test was not
                    updated. Say which commit changed it and why.
    REAL DEFECT     the test is right and the code is wrong. Say what breaks
                    in production, concretely.
    BROKEN FIXTURE  neither - the test cannot run for an environmental reason.

**A "real defect" verdict must name the production consequence.** "The
assertion fails" is not one. Two of today's fixture bugs turned out to be
exactly this: `test_heyreachfactory_ensure_leads` records had no company name,
so eight tests passed while never expanding any copy - a fixture that cannot
survive the path it tests hides the first real defect it meets.

`test_nothing_writes_to_a_provider` names `scripts/provider_truth.py` and
`scripts/sender_capacity.py`. Both are read-only scripts that POST because
this vendor spells reads as POST. Check whether the right fix is the ALLOWED
list the test's own message describes.

## WHAT YOU MAY NOT DO

- **Do not fix them.** Diagnose, verdict, evidence. Claude decides what to fix
  and when - several touch production safety paths.
- Never weaken a check to make it pass.
- One test process at a time. This machine died once from a runaway unittest.
- Read exit codes OFF THE PROCESS, never through a pipe.

## FILES ALLOWED

    docs/RED-TESTS-2026-09-15.md   (new)
    the task file itself

## FILES FORBIDDEN

    src/   tests/   work/

## DELIVERABLE

Eleven verdicts with evidence, the production consequence named for every REAL
DEFECT, the reconciliation with TASK-123, and a recommended fix order.
