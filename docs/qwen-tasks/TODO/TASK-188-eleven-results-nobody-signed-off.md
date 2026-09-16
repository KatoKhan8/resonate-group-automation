PRIORITY: P2
DEPENDS:

# TASK-188 - eleven results are merged and still say AWAITING_REVIEW

## WHERE THIS SITS

The registry reads:

    DONE 165   AWAITING_REVIEW 11   QUEUED 2   CLAIMED 4   BLOCKED 1

Those eleven are results whose code and documents are merged into master and
whose task files sit in `REVIEW/`. Nothing is waiting on them - they are
landed. But `AWAITING_REVIEW` is also the state a result sits in when its
finding has NOT been checked, and the registry cannot tell those two apart.

That matters for one specific reason. A finished-and-unchecked result and a
finished-and-verified result look identical in the state file a fresh session
reads first, and this repository has already had a morning where three
artefacts disagreed about what was done.

## THE QUESTION

1. **List the eleven.** For each: the task, where its files are, whether its
   code is in master, and whether its result block says COMPLETE.
2. **Check each result against what landed.** Not a re-run of the analysis -
   a check that the result block's claims match the repository. Specifically,
   for each: do the files it says it changed exist and contain what it says,
   do the tests it claims green actually run green now, and does the commit SHA
   in the result block exist in master. A result block claiming tests that no
   longer pass is the finding this task exists to catch.
3. **Move the ones that check out to DONE.** Leave any that do not, and say
   exactly which claim failed. Do not fix the underlying work - report it.
4. **Then make the distinction durable.** `AWAITING_REVIEW` currently means
   two things. Either split it - MERGED_UNVERIFIED versus VERIFIED - or make
   `task_registry.py` report the check in item 2 so the state means something
   a reader can act on. Say which you chose and why.

## THE TRAP

The cheap version of this task moves eleven files to `DONE/` and reports
eleven verified. That is bookkeeping dressed as verification and it makes the
registry confidently wrong, which is worse than the ambiguity it replaces.
The check in item 2 is the task. If a result block claims 42 tests pass,
RUN them, read the exit code off the process, and report the number you got.

Several of these results are from rounds where workers reported SHAs before
the commit existed and then amended - so a missing SHA is a real finding and
not necessarily a lie. Say which of the two it is.

## WHAT YOU MAY NOT DO

- No provider writes, no provider calls.
- Do not edit a worker's recorded RESULT block. If it is wrong, report it in
  your own deliverable.
- Do not move a task to DONE whose claims you could not check.
- Do not merge into master, and do not delete a branch.
- Do not weaken or skip a test to make a result block's claim come true.

## FILES ALLOWED

    docs/qwen-tasks/REVIEW -> DONE moves (verified ones only)
    scripts/task_registry.py
    scripts/task188_*.py
    docs/REVIEW-BACKLOG-2026-09-16.md   (new)

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The eleven enumerated with their three checks each, the ones moved to DONE,
the ones left with the failing claim named, and the state distinction made
durable in the registry.
