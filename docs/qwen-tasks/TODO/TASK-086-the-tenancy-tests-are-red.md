# TASK-086 - the tenancy and send-safety tests are red, and have been

## THE FACTS, AND THEY ARE NOT NEW

The full suite was run to completion on 2026-09-15:

    8954 tests, 1937s
    10 failures, 7 errors, 5 skipped, 16 expected failures

Seven of those were then run at commit `a519954` - the commit the overnight
session started from - in a detached worktree. **They fail there identically,
same names, same count.** Nothing in the 2026-09-14/15 work caused any of
them. They were red before, and nobody had run the full suite to find out.

## WHAT IS RED, AND WHY EACH ONE MATTERS

    tests.test_workspace_isolation_attacks
      ARecordWithNoClient.test_LEAK_the_sanctioned_write_path_accepts_a_null_client
      ConsumingAnApprovalGrantedElsewhere.test_the_unscoped_default_reads_the_whole_estate

    tests.test_the_second_client_runs_on_the_same_engine
      NoClientContextIsNoAccess.test_an_unowned_record_belongs_to_nobody_rather_than_to_everybody

**These three are TENANCY.** The first has LEAK in its name. The second is
about an unscoped read reaching the whole estate. The third is about a record
with no client belonging to everybody instead of nobody. `CLAUDE.md` lists
tenancy first among the things that outrank every preference, and
`MULTI-CLIENT-AUDIT.md` exists because this system holds more than one
client's prospects.

    tests.test_no_write_happens_without_every_gate
      TheAccountIsAskedToo.test_a_finished_campaign_with_no_reply_still_authorizes

**This is the write door.** The module name is the guarantee.

    tests.test_a_bounced_address_stops_being_sendable
      TheSENDPathReadsIt.test_decide_blocks_a_bounced_address

**This is send safety.** A bounced address that stays sendable is how a
domain reputation dies, and note the class name - `TheSENDPathReadsIt` is
precisely the "is it actually consumed" question this repository keeps
getting wrong.

    tests.test_ingest
      TestPhase1Csv.test_every_dropped_record_carries_its_reason
      TestPhase1Csv.test_queue_has_a_record_for_every_row

Ingest integrity. "Never delete a queue record. Drop it with a reason" is a
rule in `CLAUDE.md` and this is its test.

## THE QUESTION THIS TASK ANSWERS

For each: **is the TEST stale, or is the GUARANTEE gone?**

Those have opposite fixes and opposite consequences. A stale test that points
at a moved seam is housekeeping. A real tenancy leak is a stop-everything.
**Reporting the wrong one is worse than reporting nothing**, so show the
evidence either way.

Six of the seven are ERRORS rather than failures, which often means a
fixture or import broke rather than an assertion - check that first, because
it is the cheap explanation and it may cover most of them at once.

## HOW TO WORK

For each failure, in this order:

1. Run it ALONE. `CLAUDE.md` warns that `unittest discover` and
   `tests.offline` overlap during teardown and one HTTP test fails
   intermittently - establish which kind you have before theorising. These
   seven reproduce in isolation, so they are NOT that, but confirm it.
2. Read the traceback properly. An ERROR names a line; start there.
3. Classify: fixture, assumption, disconnected consumer, wrong canonical
   model, stale state, wrong identity, wrong tenancy, swallowed exception,
   or a real bug.
4. Say whether the TEST or the CODE is wrong, with evidence.
5. Fix the smallest root cause.
6. Verify by breaking the thing deliberately and confirming the test fails
   for the intended reason, and that a different guard did not fire first.

**Start with the three tenancy ones.** If any is a real leak, stop and report
it immediately rather than continuing down the list - that is a finding the
operator needs before anything else happens.

## HOW LONG HAVE THEY BEEN RED

`git log` each test file and the module it exercises, and name the commit
that most plausibly broke each. A guarantee that has been untested for weeks
is a different problem from one that broke yesterday.

## WHAT YOU MAY NOT DO

- **Do not delete, skip, `@expectedFailure` or weaken any of these tests.**
  They are the tests that would tell us a safety property had broken.
- Do not "fix" one by changing what the code guarantees.
- Do not fold TASK-085's two failures into this - they are separately queued.
- READS ONLY at every provider.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (exact commands, exact counts, exit codes read off
the process and never through a pipe), FILES CHANGED, FINDINGS - per failure:
classification, TEST-wrong or CODE-wrong, how long red - RISKS, RECOMMENDED
CLAUDE ACTION. If any tenancy failure is a real leak, say so in the first
line of the result block.
