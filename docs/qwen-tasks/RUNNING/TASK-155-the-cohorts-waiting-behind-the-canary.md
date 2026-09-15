PRIORITY: P1
DEPENDS:

# TASK-155 - campaign-ready inventory for both channels, cohorted

## WHERE THIS SITS

The HeyReach canary is 3 leads and the email cohort is 17. Both are
deliberately small. The question this task answers is what comes AFTER them,
so the next batch is ready the moment a readback is clean.

Two measured constraints bound it, and neither is negotiable:

    LinkedIn   97 contacts clear every gate including account collision.
               151 of 248 were rejected at the ACCOUNT level.
    Email      17 contacts survive every gate. 16 of 38 domains STOP.

`PRODUCTION-SCALE-POLICY.md` is the contract: a campaign is a COHORT and never
a person, ~50 where inventory supports it, consolidation over proliferation.

## THE QUESTION

Given 97 LinkedIn-eligible and 17 email-eligible contacts, what cohorts should
exist?

Against the snapshot - **quote the STAMP**:

1. The batch ladder: 3 -> 10 -> 25 -> 50. Which specific contacts fill each
   rung on LinkedIn, and does 97 support the whole ladder? Name them by record
   id.
2. TASK-140 found signal 100% null and angle inferred from title rather than
   evidenced. Re-check that at 550 records. If it still holds, the honest
   cohort dimension is persona or ICP segment, not signal - say so.
3. Which contacts are eligible for BOTH channels, and what decides which one
   they get? An account worked on both channels at once is the collision rule
   firing against itself.
4. The leftovers. How many eligible contacts fall into no coherent cohort, and
   what would they need?

## THE TRAP

Do not propose cohorts that need copy nobody has written. The LinkedIn CONTROL
is the operator's fallback copy, which asserts nothing specific - so a
signal-based cohort only matters if the copy SAYS something about the signal,
and that copy must then clear the claims gate against that contact's evidence.
State each cohort's arm: CONTROL or CHALLENGER.

## WHAT YOU MAY NOT DO

- Do not create campaigns or write to `work/`. No provider writes.
- Do not run generation against the real queue.

## FILES ALLOWED

    docs/COHORT-LADDER-2026-09-15.md   (new)
    scripts/task155_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The named contacts per rung of the ladder, the re-checked signal/angle
evidence verdict, the both-channels resolution rule, the leftovers, and each
cohort's arm.
