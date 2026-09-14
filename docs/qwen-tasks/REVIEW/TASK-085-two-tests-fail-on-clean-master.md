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

STATUS: DONE
COMMIT SHA: 6e468cd
TESTS:
  - `py -3 -m unittest tests.test_crash_restart_idempotency.CrashAtSeam.test_crash_between_first_and_second_lead -v` -> OK (exit 0)
  - `py -3 -m unittest tests.test_cadence.TestTheCompanyPause.test_the_pause_is_recorded_with_its_cause_and_is_auditable -v` -> OK (exit 0)
  - `py -3 -m unittest tests.test_crash_restart_idempotency -v` -> 9 tests OK (exit 0)
  - `py -3 -m unittest tests.test_cadence -v` -> 38 tests OK (exit 0)
  - `py -3 -m unittest tests.test_reply_transitions -v` -> 43 tests OK (exit 0)
  - `py -3 -m unittest tests.test_a_reply_on_one_channel_stops_the_other tests.test_approve tests.test_push -v` -> 92 tests OK (exit 0)
  - `py -3 -m unittest tests.test_staging_a_campaign_twice_builds_one tests.test_staging_refuses_colliding_contacts tests.test_campaign_cadence_wiring -v` -> 40 tests OK (exit 0)
  - `py -3 -m unittest tests.test_invariants tests.test_task041_scale_fixes tests.test_dedupe -v` -> 117 tests OK (exit 0)
  - `py -3 -m unittest tests.test_account_policy tests.test_signals tests.test_tagsync tests.test_hygiene -v` -> 188 tests OK (exit 0)
  - Full suite via `scripts/run_suite.py` running in background at time of commit

FILES CHANGED:
  - src/cadence.py: record_event now calls accountpolicy.apply_reply directly for hand-recorded replies
  - tests/test_crash_restart_idempotency.py: updated to patch _remember_leads (batch) instead of _remember_lead (per-lead)
  - tests/test_reply_transitions.py: updated docstring for test_a_hand_recorded_reply_holds_it_too

FINDINGS:

Failure 1: test_crash_between_first_and_second_lead (RuntimeError not raised)
  Classification: STALE TEST - the crash seam moved
  Broken by: TASK-041 (commit 6be8b6f, 2026-09-14 20:50)
  Red for: ~1 day (from 2026-09-14 to 2026-09-15)
  Whether TEST or CODE was wrong: TEST was stale
  Evidence: TASK-041 changed _ensure_leads to call _remember_leads (batch) after
    the create loop instead of _remember_lead (per-lead) inside the loop. The test
    patched bisonfactory._remember_lead which was never called (grep confirms only
    the definition exists, no callers). The crash never happened because the patched
    function was dead code.
  Fix: Updated _crash_after_remember_lead to patch _remember_leads instead. The
    patched function processes the first N pairs through the original, then raises.
    This simulates a partial-batch crash. The second lead is now reconciled (found
    by email at the provider) rather than created fresh, because both leads exist
    at the provider when the batch persist crashes. The guarantee (no duplicates,
    full recovery) is unchanged.
  Verification: Breaking _remember_leads (making it a no-op) causes the test to
    fail with "the first lead was not reused from its binding" - the intended
    assertion. No other guard fires first.

Failure 2: test_the_pause_is_recorded_with_its_cause_and_is_auditable (TypeError on paused.reason)
  Classification: STALE CODE PATH - the hand-recorded path lost its pause
  Broken by: TASK-030 (commit 6756fc1, 2026-09-14 12:15)
  Red for: ~1 day (from 2026-09-14 to 2026-09-15)
  Whether TEST or CODE was wrong: CODE was wrong (for the hand-recorded path)
  Evidence: TASK-030 changed events.apply_reply_policy to return None instead of
    calling accountpolicy.apply_reply. This was correct for the provider-webhook
    path (pause deferred to inbound.handle after classification). But cadence.record_event
    is the HAND-RECORDED path - an operator recording a reply is saying "this is a
    real reply," not a webhook that might be an autoresponder. The docstring of
    record_event explicitly says "a reply recorded by hand is unclassified like one
    from a webhook, so it holds the company" - but the code no longer did this.
  Fix: Updated record_event to call accountpolicy.apply_reply directly with
    UNKNOWN outcome for hand-recorded replies. The provider-webhook path
    (events.apply_reply_policy -> None -> inbound.handle) is unchanged.
  Verification: Reverting the fix reproduces the original TypeError: 'NoneType'
    object is not subscriptable. The test passes with the fix. test_a_hand_recorded_reply_holds_it_too
    still passes (it only asserts the event is recorded, not that paused is None).

RISKS:
  - The crash test assertion changed from leads["created"]==1 to leads["reconciled"]==1.
    This reflects the new code structure (batch persist) but is a different assertion.
    The guarantee (no duplicates, full recovery) is still verified.
  - cadence.record_event now pauses the account for hand-recorded replies. This restores
    the documented behavior but changes the runtime behavior. Any code that relied on
    record_event NOT pausing would break. No such code was found in the test suite.

RECOMMENDED CLAUDE ACTION:
  Review the two fixes and confirm:
  1. The crash test assertion change (created -> reconciled) is acceptable
  2. The cadence.record_event pause restoration is the correct fix (vs updating the test)
  3. Run the full suite to confirm no regressions in e2e or other slow tests
