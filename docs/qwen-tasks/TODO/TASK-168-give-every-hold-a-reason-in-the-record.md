PRIORITY: P1
DEPENDS:

# TASK-168 - write the hold reason into the record

## WHERE THIS SITS

TASK-161 classified all 36 held records and found the thing that matters:

    zero of the 36 carry a hold_reason

The classification exists in `docs/HELD-RECORDS-2026-09-15.md`. It exists in a
document. It does not exist in the data, which means nothing downstream can act
on it, and the next session re-derives it by hand.

A hold with no machine-readable reason is a record that leaves the pipeline
silently.

## THE QUESTION

1. Read `docs/HELD-RECORDS-2026-09-15.md` and the code that PUTS a record into
   `held`. Every call site. A reason written by a backfill and a reason written
   at the moment of the hold are different things, and only the second one
   survives the next hold.
2. Add `hold_reason` at the point of the hold, with the taxonomy TASK-161
   established, mapped onto these five classes:

       ACTIONABLE     something we can do now moves it
       WAITING        a dependency outside us, time will move it
       RETRYABLE      transient, retrying is correct
       HUMAN_REVIEW   a person must decide
       PERMANENT      it is never moving

   Also record WHAT was being attempted and WHEN. A reason without a timestamp
   cannot be aged.
3. Backfill the 36 from TASK-161's classification. Report the distribution
   across the five classes.
4. Return the ACTIONABLE and RETRYABLE records to the correct queue - **only
   where it is provably safe**. Safe means: the condition that caused the hold
   is measurably gone, the record still passes every gate it passed before, and
   returning it costs nothing. Where that is not provable, leave it held and
   say which of the three conditions failed.

## THE TRAP

Returning a record to a queue is a state transition, and `held` exists because
something refused. Do not clear a hold because its class sounds recoverable -
clear it because you measured that the cause is gone. A record that cycles
held -> queued -> held is worse than one that stays held: it burns the stage
that holds it, every pass, forever.

TASK-161 also found that a hold's cause and the field a summary reads are not
the same thing. Prove the field you read is the field that holds the record.

## WHAT YOU MAY NOT DO

- No provider writes, no paid provider calls, no model calls that cost money.
- Do not clear a hold whose cause you have not measured as gone.
- Do not delete a held record, and do not move one to `dropped` - `dropped` is
  terminal and this task has no authority to end a record.
- Never commit PII. Hash record identifiers in the deliverable.
- Tests: add them for the taxonomy and for the return-to-queue predicate. Read
  the exit code off the process.

## FILES ALLOWED

    src/   (the hold call sites and the taxonomy - read before writing)
    tests/test_hold_reasons.py   (new)
    docs/HOLD-REASONS-2026-09-16.md   (new)
    scripts/task168_*.py

## FILES FORBIDDEN

    config/   src/providerwrites.py

## DELIVERABLE

The hold call sites enumerated, `hold_reason` written at each, the 36
backfilled with their class distribution, the records returned to a queue with
the measurement that justified each, and the ones left held with the reason.
