PRIORITY: P0
DEPENDS:

# TASK-275 — red tests for the account rule and the collision gate

**Write the tests, not the fix.** The rewrite happens tomorrow morning in the
production session; this task exists so that it starts from RED tests rather
than from a blank page. A test that passes against today's code is a test
that has not understood the change.

## The rule, exactly as the operator stated it 2026-09-24

    same contact                              NEVER twice
    same account, a NEW persona               allowed after 5 days with no
                                              human reply
    a third persona                           7 days after that
    any reply or unsubscribe at the account   stops all others
    a stop carrying OUR OWN reason plus an
      operator-recorded move                  is NOT an account-level hold

Today the guard is "same account = refuse", which is why 212 accounts were
refused on 2026-09-24 and why the US cohort was empty that night.

## What to write

`tests/test_the_account_rule_staggers_rather_than_blocks.py`, covering at
least:

1. the same contact twice is refused, on every path
2. a second persona at the same account is refused at day 4 and allowed at
   day 5
3. a third persona is refused at day 11 and allowed at day 12
4. a HUMAN reply anywhere at the account stops every other persona -
   an automated reply is not a human reply, see `replies.is_automated`
5. an unsubscribe anywhere at the account stops every other persona
6. a stop this system made, carrying its own reason and an
   operator-recorded move, does NOT read as an account-level hold
   (ISSUE-035)
7. a stop we did NOT make still holds the account

## The trap this task exists to avoid

**The gap is measured from the last CONFIRMED touch, never from a cache.**
`work/stage/last-touch.json` is stale by up to 111 days - lead 133283 read
111 days untouched while its last confirmed send was two days earlier from
campaign 491. Write the tests so a cached value cannot satisfy them: a lead
sent to yesterday must never read as untouched.

## Rules

- Tests only. Do NOT change `src/` - the rewrite is production's.
- The tests must FAIL against today's code, and you must say which fail and
  why. A green suite here is the task not being done.
- Never put a real prospect address, name or company in a test.
  `tests/test_fixture_hygiene.py` enforces it - run it.
- Commit on your own branch. Do not merge.

## Result block

    BRANCH:
    COMMIT:
    TESTS ADDED:
    FAILING AGAINST TODAY'S CODE (expected):
    ANYTHING THE RULE DOES NOT SAY AND YOU HAD TO DECIDE:

---

## STATE RECORDED BY LANE E, 2026-09-24 late

    DELIVERED BY     qwen-2, round 9
    STATE            REVIEW (moved out of TODO/ tonight; it was still sitting
                     in TODO/ while finished, which is part of why the pool
                     read as deeper than it was)
    ON MASTER        NO
    NEXT             TASK-288 - second pass. Are the tests red, red for the
                     reason claimed, and pinning the operator's rule rather
                     than one the author inferred?

Not to be merged before TASK-288 clears. The rewrite in the production
session starts from these tests, so a wrong test costs the rewrite.
