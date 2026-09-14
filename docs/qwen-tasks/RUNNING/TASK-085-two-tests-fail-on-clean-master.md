# TASK-085 - two tests fail on clean master and nobody has looked

## THE FACTS

Both verified by Claude by running them on clean master, alone, with the exit
code read off the process rather than through a pipe:

    tests.test_crash_restart_idempotency
      CrashAtSeam.test_crash_between_first_and_second_lead
      FAILED - RuntimeError not raised

    tests.test_cadence
      TestTheCompanyPause.test_the_pause_is_recorded_with_its_cause_and_is_auditable
      ERROR - TypeError on paused.reason

Neither is caused by any change made on 2026-09-14/15. Two separate Qwen
workers reported them independently as "pre-existing", and both were right.

## WHY THIS IS WORTH A TASK RATHER THAN A SHRUG

Look at what the two of them protect.

`test_crash_between_first_and_second_lead` is the test that a run killed
partway through does not half-add a cohort. This repository stages leads to
real providers. A broken crash-seam test is a broken guarantee about what
happens when a staging run dies mid-write - and a staging run HAS died
mid-write here before, which is why `work/queue.jsonl.lock` handling exists.

`test_the_pause_is_recorded_with_its_cause_and_is_auditable` is the test that
a company pause carries its REASON. An unexplained pause is indistinguishable
from a bug, and `ACCOUNT-OUTREACH.md` rests on a pause being auditable.

So these are not cosmetic. They are two of the tests that would tell us a
safety property had broken, and right now they cannot tell us anything.

## WHAT TO DO, IN THIS ORDER

For EACH failure, separately:

1. **Reproduce it alone.** Run just that one test. Confirm it fails the same
   way in isolation as it does in a full run - `CLAUDE.md` warns that
   `unittest discover` and `tests.offline` overlap during teardown and that
   one HTTP test fails intermittently, so establish which kind this is before
   theorising.
2. **Classify it.** Fixture, assumption, disconnected consumer, wrong
   canonical model, stale state, wrong identity, wrong tenancy, swallowed
   exception, or a real bug. Say which, with the evidence.
3. **Decide whether the TEST or the CODE is wrong.** Both are possible and
   the answer is not obvious. `RuntimeError not raised` may mean the crash
   seam moved and the test still points at the old one - in which case the
   guarantee may be intact and the test stale. Or the seam may genuinely no
   longer raise, in which case a real guarantee is gone. **Those two have
   opposite fixes and reporting the wrong one is worse than reporting
   nothing.**
4. **Fix the smallest root cause.** Never weaken a check to make it pass.
5. **Verify** by breaking the thing deliberately and confirming the test now
   fails for the intended reason, and that a different guard did not fire
   first.

## HOW LONG THEY HAVE BEEN BROKEN

Worth knowing and cheap to find: `git log` the two test files and the modules
they exercise, and say which commit most plausibly broke each. If a test has
been red for weeks, that is a finding about how the suite is being read, not
just about the test.

## WHAT YOU MAY NOT DO

- **Do not delete or skip either test.** Not with `@skip`, not with
  `expectedFailure`, not by removing an assertion.
- Do not weaken an assertion to make it pass.
- Do not "fix" it by changing what the code guarantees.
- READS ONLY at every provider.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (exact commands, exact counts, exit codes read off
the process and never through a pipe), FILES CHANGED, FINDINGS - for each
failure: the classification, whether the TEST or the CODE was wrong, and how
long it has been red - RISKS, RECOMMENDED CLAUDE ACTION.
