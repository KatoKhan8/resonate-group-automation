PRIORITY: P0
DEPENDS:

# TASK-288 — second pass: do the account-rule tests actually fail, and for the right reason?

## The question this answers

**TASK-275 was asked for RED tests. Are they red, are they red for the reason
claimed, and do they pin the rule the operator stated — or a rule the author
inferred?**

`docs/qwen-tasks/REVIEW/TASK-275-account-rule-red-tests.md` carries the
delivery. The rewrite happens in the production session tomorrow and starts
from these tests, so a test that is wrong costs the rewrite, not the review.

**A red test is not proof by itself.** When a guard is broken deliberately to
check a test, three things have to hold: the intended test failed, it failed
for the intended reason, and **a different guard did not fire first.** That
third one is how a test can be red all week and still be testing nothing.

## The rule under test, as the operator stated it 2026-09-24

    same contact                            NEVER twice
    same account, a NEW persona             allowed after 5 days with no
                                            human reply
    a third persona                         7 days after that
    any reply or unsubscribe at the account stops all others
    a stop carrying OUR OWN reason plus an
      operator-recorded move                is NOT an account-level hold

## What to check, one at a time

1. **Run each new test and record its failure message verbatim.** Not "7
   fail". Which seven, and what each says.
2. For each: is the failure the ASSERTION the test was written for, or an
   `ImportError`, a missing fixture, a `TypeError`, or a different guard
   refusing earlier? Classify every one. A test failing on a typo is green
   dressed as red.
3. **Day boundaries.** Refused at day 4 / allowed at day 5; refused at day 11
   / allowed at day 12. Check the arithmetic is 5 then 7-more (=12), not 5
   then 7 (=7). An off-by-one here becomes a live policy.
4. **Human vs automated reply.** Does the test use `replies.is_automated`, or
   does it hand-roll a check? An out-of-office must not stop the account.
5. **The ISSUE-035 carve-out.** Does the test distinguish a stop WE made
   carrying our own reason plus an operator-recorded move, from a stop we did
   not make? Both cases must be present and they must behave differently. If
   only one is tested, the carve-out is untested.
6. **The cache trap.** The gap is measured from the last CONFIRMED touch,
   never from a cache. Does a test exist in which a lead sent to YESTERDAY is
   offered to the rule with a cached value claiming 111 days, and the rule
   still refuses? If the cached value can satisfy the test, the test will pass
   against the broken code tomorrow.
7. **Fixture hygiene.** Run `tests/test_fixture_hygiene.py`. No real address,
   name or company anywhere in the new tests.
8. **The other direction.** Name at least one behaviour the operator's rule
   implies that these tests do NOT cover, and write the missing case as a
   further red test.

## The acceptance bar

- A per-test table: name, red/green, failure class (ASSERTION / IMPORT /
  FIXTURE / WRONG-GUARD / OTHER), and the verbatim message.
- Every ASSERTION failure is traced to the specific production behaviour that
  will change tomorrow, named by file and function.
- At least one test is proved to fail for the WRONG reason, or you state
  explicitly that you checked all of them and none did — with the evidence.
- The cache-trap test exists and is red, or you write it.
- The set of rule clauses (5 above) is diffed against the set of tests, **both
  directions**: clauses with no test, and tests asserting something the rule
  does not say.

## What evidence counts

- Raw test output, per module, run alone. Not the full suite, not a filtered
  pipe. **Never read a filter's exit code** — three "green" runs meant nothing
  here for exactly that reason.
- For the "wrong guard fired first" check: the traceback showing which guard
  raised.
- For the cache trap: the actual values fed in and the verdict returned.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Counting reds.** "7 of 7 red, approved" is the review not happening. The
  failure REASON is the review.
- **Accepting a red that is an ImportError.** That test will go green the
  moment somebody adds the import, and will assert nothing thereafter.
- **A test that passes because the fixture mocks the function under test.**
  Fixtures get invented and then mock the buggy function. If the rule's input
  is hand-constructed, the seam is being tested and the seam was never the
  risk.
- **Approving tests that read `work/stage/last-touch.json`.** That cache is
  the defect the rewrite exists to remove.
- **Reviewing the task file instead of the code.** Read the diff.
- Treating "the operator did not say" as "the author may decide silently".
  Anything the rule does not state and the tests assume is a DECISION and goes
  in the result block by name.

## Boundaries

- **Review only. Do not fix `src/`.** The rewrite is production's tomorrow.
  A missing TEST you may add; a production change you may not.
- No provider calls.
- Do not merge, do not push to master.

## Files

    ALLOWED    tests/test_the_account_rule_staggers_rather_than_blocks.py
               (additional red cases only),
               docs/qwen-tasks/REVIEW/TASK-275-account-rule-red-tests.md
               (append a REVIEW block)
    FORBIDDEN  src/*, work/*, config/.env

## Result block

    BRANCH:
    COMMIT:
    PER-TEST TABLE (name / red / failure class / verbatim message):
    TESTS RED FOR THE WRONG REASON:
    DAY ARITHMETIC: 5 and 12, or 5 and 7?
    is_automated USED, YES/NO:
    ISSUE-035 CARVE-OUT: both cases present, YES/NO:
    CACHE-TRAP TEST: existed / written by me / still missing:
    CLAUSES WITH NO TEST:
    TESTS ASSERTING WHAT THE RULE DOES NOT SAY:
    test_fixture_hygiene RESULT:
    VERDICT: ACCEPT / ACCEPT WITH THE ADDITIONS NAMED / REWORK
