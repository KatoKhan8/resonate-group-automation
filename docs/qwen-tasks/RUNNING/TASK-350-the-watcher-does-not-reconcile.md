PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-350 - the watcher does not reconcile

**Operator instruction, 2026-09-26:** a reconciliation check in the watcher.

`src/replywatch.py` watches. It does not ask whether what we believe matches what
the provider says. Every drift this project has hit was found by hand, days late:
campaigns believed active that were paused, 44 of 46 blank leads already in a
client campaign, a ledger whose silence was read as absence.

## Build

    src/replywatch.py    MODIFY - add the check to the existing loop.
    tests/test_the_watcher_reports_drift_rather_than_assuming_agreement.py   NEW

Per watched campaign, compare and report:

    our campaign status      vs   the provider's
    our sent count           vs   the provider's
    our reply count          vs   the provider's
    our lead count           vs   the provider's
    our suppression set      vs   what the provider will still send to

**Report drift. Do not correct it.** A watcher that silently reconciles state is
a watcher that can silently destroy it, and which side is right is not always
ours. Emit a finding; let a person decide.

## The failure mode to avoid, which this repo has already paid for

**A zero is not agreement.** `CLAUDE.md`: *"A zero and a wrong lookup look
identical from outside. Prove the field you read is the right one before
reporting a zero."* And: *"READ THE CLOCK - a zero at a weekend or before a
window opens is the calendar rather than a fault."* 487 is Mon-Fri 07:00-15:00Z
and 489 is Mon-Fri 13:00-21:00Z.

So: a check that reports "no drift" because both sides returned nothing is
worthless. Distinguish **agreed**, **drifted**, and **could not be established**,
and never let the third read as the first.

**Order campaigns by provider id, numerically.** `created_at` is null on the
campaigns that actually send, so ordering by it silently drops them.

## Acceptance - RUN each, paste real output

1. Drift is detected: a fixture where our count and the provider's disagree, and
   the check reports it naming the campaign, the field, and both values.

2. Agreement is reported as agreement, not as silence.

3. **An unestablished comparison is its own verdict:** a fixture where the
   provider call fails or returns nothing, asserting the result is
   `COULD_NOT_ESTABLISH` and **not** `AGREED`. This is the assertion that closes
   the task.

4. **The guard is seen to fail:** break the comparison so drift is missed,
   confirm the test fails, restore. Paste both runs.

5. A real read-only run against the live campaign list, reporting the drift table
   as it stands today. Confirm from the code that every call is a read before
   running it; if you cannot, report it as needing authorisation instead.

6. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- **Do not correct drift. Do not write to a provider.** Report only.
- Do not pause, resume, activate or modify any campaign. 493 is live.
- Do not order campaigns by `created_at`.
