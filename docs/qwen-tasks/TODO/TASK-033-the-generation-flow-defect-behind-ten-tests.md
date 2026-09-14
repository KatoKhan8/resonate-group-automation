# TASK-033 - The generation-flow defect behind ten tests

The largest remaining cluster in the suite. TASK-018 fixed five of seven
clusters and named this one as the reason it stopped: `test_e2e` and
`test_preproduction` fail for the same root cause, and it is a product defect
rather than a stale expectation.

## WHAT IS KNOWN

    test_e2e          8 failures
    test_preproduction  2 failures + 2 errors

TASK-018's note: "NOT FIXED - generation flow defect", and it changed
`test_preproduction.py`'s `FakeModel` to produce distinct drafts per step,
which moved the symptom without settling the cause.

Several of these tests were written against the SEVEN-step email-led cadence
and the client now runs `productive_li_heavy_v1` - five emails and six
LinkedIn steps over 21 days. So some of the ten are stale expectations and
some are real. **Separating those two is most of this task**, and getting it
wrong in either direction is expensive: a stale test "fixed" by weakening it
hides a defect, and a real defect "fixed" by editing the test is worse.

## SCOPE

1. Run the ten and classify EACH one, in one line, as exactly one of: stale
   cadence expectation / stale fixture / real product defect / disconnected
   consumer. Put the table in the result block before you change anything.
2. Fix the stale ones by updating them to the current cadence, saying in each
   docstring what changed and when - not by deleting an assertion.
3. For each real defect: reproduce it with the smallest test that fails,
   fix the root cause, and confirm the original test passes for the right
   reason rather than incidentally.
4. If a test cannot be classified, say so and leave it. An honest "I could not
   tell" is worth more than a guess that closes the ticket.

## THE RULE THAT DECIDES THIS TASK

Never weaken a check to make it pass. If the cadence moved, the test moves
with it and says so. If the product is wrong, the product changes.

## FILES ALLOWED

`tests/`, `docs/qwen-tasks/`. `src/**` only for a defect you have first
reproduced with a failing test, and name it in FINDINGS.

## FILES FORBIDDEN

`src/providerwrites.py`, `src/executionguard.py`, `src/killswitch.py`,
`src/approve.py`, `src/providers/**`, `work/**`.

## TESTS REQUIRED

The ten, passing for stated reasons. Plus, for every product defect you fix,
a test that fails without the fix - and confirm it fails for the intended
reason and that no other guard fired first.
