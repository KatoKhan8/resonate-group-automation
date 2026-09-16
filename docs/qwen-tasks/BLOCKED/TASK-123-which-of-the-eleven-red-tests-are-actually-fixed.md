PRIORITY: P3
DEPENDS: 

# TASK-123 - re-diff the failing suite by NAME, not by count

## WHY

The full suite takes about 30 minutes and has been run twice, on 2026-09-15:

    first run   8954 tests, 1937s, 17 red
    final run   9065 tests, 1810s, 12 red

Diffed by NAME, because a count moving 17 -> 12 does not say which five moved.
That discipline caught a real mistake: four failures looked new, a fix was
reverted on the strength of it, and all four turned out to have been in the
first list - the sort order differed and only the head had been read.

Since then TASK-085, TASK-086, TASK-088 and TASK-095 have all touched red
tests, and `tests.test_fixture_hygiene` has gone GREEN (11 tests, verified).

## WHAT TO DO

1. Run the full suite to completion. `scripts/run_suite.py` reports the real
   exit code. It takes ~30 minutes - **commit and push before starting it**,
   so the run is the only thing at risk.
2. Produce the failing list BY NAME.
3. **Diff it by name** against the 11 recorded in TASK-088 and against the 12
   from the final run. Report FIXED, STILL RED, and INTRODUCED as three
   separate lists.
4. For anything INTRODUCED, bisect to the commit. Anything introduced by this
   session's work is a regression and is the most important thing in the task.

## WHAT NOT TO DO

- **Do not eyeball a truncated list and infer.** That exact mistake caused a
  correct fix to be reverted. Sort both lists and diff them mechanically.
- Do not read the verdict through a pipe - a pipe reports the filter's exit
  status. Read it off the process.
- Do not fix anything in this task beyond reporting. A 30-minute measurement
  mixed with fixes cannot be attributed.
- Two module names that DO NOT EXIST and keep being written into tasks:
  `tests/test_accountpolicy.py` (it is `test_account_policy.py`) and
  `tests/test_inbound_classification.py`. Also `tests.test_ladder` and
  `tests.test_claims` and `tests.test_providerwrites` do not exist - loader
  errors from those have been miscounted as failures twice.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from outside.** Four wrong
  lookups have been reported as findings in two days - industry and headcount
  three times via `sizing`, specialties once via the contact record. Prove the
  field you read is the right one before reporting a zero.
- Never weaken, widen or disable a gate, lint rule or sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- **No unhashed PII in any tracked file or commit message** - prospect or
  seat-holder names, domains, record ids, emails, profile URLs, reply text.
  `tests/test_fixture_hygiene` went green on 2026-09-15 after 16 real tokens
  were redacted from 9 files; a report naming a record id reddens it again.
- Do not assert on the text of the source; assert on returned values.
- Do not report a PREDICTED result. You have model access via config/.env.
- Separate OBSERVATIONS (with n), HYPOTHESES and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection.
