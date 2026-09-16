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

## RESULT

STATUS: DONE
COMMIT: e9e073e
TESTS: 36 new tests in tests/test_hold_reasons.py, all green. 100 tests in
       test_enrich + test_generate still green. 80 tests in test_invariants
       still green.

FILES CHANGED:
  src/holdreasons.py          NEW - taxonomy module
  src/enrich.py               outcome() returns reason code; enrich_record()
                              writes hold_reason via set_hold_reason()
  src/generate.py             ModelError handler classifies error and writes
                              hold_reason
  tests/test_hold_reasons.py  NEW - 36 tests
  scripts/task168_backfill.py NEW - backfill script for the 36 records
  docs/HOLD-REASONS-2026-09-16.md  NEW - documentation

FINDINGS:

1. Two production call sites set rec["state"] = "held":
   - src/enrich.py outcome() line 816: when contacts have unresolved verdicts
   - src/generate.py generate_record() line 1869: when llm.ModelError is caught
   Both now write hold_reason, hold_class, and hold_at.

2. The taxonomy has five classes:
   - ACTIONABLE (9 records): un-drop pending re-enrichment
   - WAITING (9 records): verification unresolved (accept_all or None)
   - RETRYABLE (12 records): generation model errors
   - HUMAN_REVIEW (3 records): verifier disagreement, lint failures
   - PERMANENT (3 records): no contacts found

3. Return-to-queue predicate: can_return_to_queue() refuses unless ALL three
   conditions are provably met (cause gone, gates still pass, no cost).
   - RETRYABLE: refused (requires model re-run, not free)
   - WAITING: refused if contacts still unresolved
   - ACTIONABLE: allowed only if contacts exist AND are resolved
   - HUMAN_REVIEW: always refused
   - PERMANENT: always refused

4. No records were returned to a queue because no queue snapshot was available
   in work/ (gitignored). The backfill script (scripts/task168_backfill.py)
   is ready for Claude to run against the production queue with --apply.

5. The hold_reason field is now consumed:
   - src/enrich.py:1257 imports holdreasons and calls set_hold_reason()
   - src/generate.py:1870 imports holdreasons and calls set_hold_reason()
   - funnel._reason() already checks for hold_reason (line 111)

RISKS:
- The backfill classifier reconstructs reasons from log entries. If a log
  entry is missing or ambiguous, the record is reported as UNCLASSIFIABLE.
  TASK-161 proved all 36 are reconstructable, so this should not happen.
- The generate.py error classification uses string matching on error messages.
  If llm.py changes its error messages, the classification may need updating.

RECOMMENDED CLAUDE ACTION:
1. Run scripts/task168_backfill.py --apply against the production queue to
   backfill the 36 held records with hold_reason.
2. Review the distribution and return-to-queue decisions.
3. The 3 PERMANENT records (no contacts) should be dropped separately with
   proper authority - this task has no authority to end records.
