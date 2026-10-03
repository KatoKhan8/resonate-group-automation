PRIORITY: P2
SIZE: M
DEPENDS:

# TASK-549 — regenerate the suite baseline on master

**Filed per the FOCUS RULE. Two independent agents reported this on
2026-09-28, neither prompted by the other.**

## The finding

    CLAIM        `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 named
                 failures) is stale for the TASK-425 work now merged to master
    AUTHORITY    the TASK-425 merge reviewer, and P0-B independently: both
                 found failures absent from the baseline that FAIL ON MASTER
                 WITHOUT their branch
    MEASURED AT  2026-09-28
    STATE        VERIFIED by two independent reverts

The merge reviewer found 4 failures absent from the baseline and confirmed all
four fail at `origin/master` without its branch. P0-B found 6 absent, proved 4
of them were not its own by **swapping its three source files for their
merge-commit versions, re-running the suspects, and restoring byte-identical
against frozen hashes** — those four still failed. They name
`productive-offers.yaml`, `docs/qwen-tasks/DONE/` and `cadencelibrary.py`,
files neither branch touches.

**So the next agent to diff against this baseline will hit the same four and
spend an hour proving they are not its fault. Two already have.**

## Why this is worth doing rather than tolerating

The baseline's whole job is to answer one question: **did this branch add a
failure?** A baseline carrying failures master has since acquired makes every
set diff report false positives, and the rule "a new failure BLOCKS" then
blocks on other people's failures. A guard that cries wolf gets ignored, and
this one gates merges.

Note also that the count is not the measure and never was: P0-B measured 123
failing names against a baseline of 128 — which reads as an improvement while
**6 new failures hid inside it**, offset by 11 that cleared. **Compare the
sets, never the counts.** Any regenerated baseline must be a list of names for
that reason.

## What to do

1. **Run the full suite on `origin/master` with nothing else running.** This
   matters: both agents had to discard runs measured while another process
   touched the tree, and one discarded its own run because its mutation
   harness was rewriting source mid-suite. Wait for the tree to be quiet.
2. **Write the new baseline as NAMED FAILURES**, in the same
   `FAIL `/`ERROR `-prefixed format, dated in the filename.
3. **Record the delta from the 09-26 baseline** — what entered, what cleared,
   and for each entrant, which commit introduced it if it can be established
   cheaply. A regenerated baseline that silently absorbs new failures is worse
   than a stale one, because it launders them into "known debt".
4. **Do not delete the 09-26 file.** Supersede it and leave the old one for
   audit, the way handoffs are superseded here.
5. Note the environment-dependent ones: P0-B reported 11 baseline failures
   that did not reproduce in its worktree (`test_a_resume_leaves_a_ledger_row`
   ×5, `test_e2e` ×4) and explicitly did not claim them fixed. **Establish
   whether those are environmental before recording them either way** — an
   environmental failure recorded as debt and a fixed test recorded as debt
   look identical afterwards.

## Rules

- **Never delete a legitimate test to make the suite green.** A safety test
  failing because production violates the contract is evidence, and the
  baseline exists to keep it visible rather than to retire it.
- The baseline count may never silently increase — if the new list is longer,
  say which entries are new and why.
- Read-only on production `work/`. Provider writes 0. `sending.live` stays
  false.
- Report as CLAIM / AUTHORITY / MEASURED AT / STATE. A test count is never a
  PASS, and that is the entire point of this task.
