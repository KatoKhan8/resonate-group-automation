PRIORITY: P1
DEPENDS:

# TASK-195 - a branch that did no work can hide a task forever

## WHERE THIS SITS

`claim_task._claimed_on_a_branch` exists for a good measured reason and its
docstring records it: five tasks were each run twice because a finished
worker's local ref was destroyed by `checkout -B`, and scanning remote refs
closed that window. It is not belt-and-braces and it should not be removed.

But its rule is "the file is not in TODO on some branch", and that is not the
same question as "somebody is working on it".

Measured this morning, twice:

    TASK-183   blocked itself correctly, was moved to BLOCKED on master, and
               then FIVE live worktree branches were forked from that master.
               Each inherited the file in BLOCKED without doing any work. When
               the blocker cleared and Claude moved the file back to TODO, the
               task was invisible - permanently, because those branches are
               active. It had to be re-issued as TASK-192 under a new id.

    TASK-164   its own claim commit moved the file to RUNNING on a branch that
               then died. The task was invisible until Claude released the
               claim AND reset the worktree.

And the same detector was right about TASK-146 and TASK-155, which really were
finished on branches and really were invisible for a day.

So it has both failure modes at once: it hides work that is available, and it
was the only thing that noticed work that was done.

## THE QUESTION

1. **Separate the two questions.** "Is a worker running on this task" is
   answered by a claim and a worktree lock. "Has a worker produced a result for
   this task" is answered by a branch. The current code answers the second and
   is used for the first. Make the distinction explicit in the code.
2. **Compare against master, not against TODO.** A branch that has the file in
   the SAME stage master has it in has done nothing with it. A branch that
   moved it PAST master's stage has produced something. That single change
   fixes the TASK-183 case, because a branch forked from a BLOCKED master and a
   master that now says TODO differ in a direction that means "master moved on",
   not "the branch did work".
3. **Handle the re-queue case explicitly.** When master deliberately moves a
   task backwards - BLOCKED to TODO, REVIEW to REWORK - every existing branch is
   stale about it. Decide how the detector knows master's move is newer than
   the branch's, and say why your answer is right. A commit timestamp is one
   option and it is not obviously the right one.
4. **Keep every existing protection.** The TASK-139-through-143 double-dispatch
   must still be prevented, and TASK-146 and TASK-155 must still be reported as
   unintegrated. Write a test for each of those historical cases, by name, so a
   future change cannot quietly undo them.
5. **Report, do not reap.** If a task is hidden by a stale branch, the tool
   should SAY so - "TASK-nnn is in TODO on master and in BLOCKED on 5 branches,
   which are stale" - rather than silently include or exclude it. Silence is
   what cost a night.

## THE TRAP

The easy fix is to stop scanning branches. Do not. That scan is the only thing
that noticed two finished results nobody had integrated, and removing it
recreates a defect that wasted five workers in one round. The docstring records
both incidents; read it before changing a line.

Second trap: this module is used by `pool.sh` while eight workers are running
against it. A change that throws on an unexpected ref shape takes the whole
pool down. Handle a missing ref, a detached HEAD, a branch with no commits and
a worktree that has been reset - all four have happened today.

## WHAT YOU MAY NOT DO

- Do not remove or weaken `_claimed_on_a_branch`.
- Do not delete a branch, do not force-push, do not rewrite history.
- Do not reap or release a claim as a side effect of a status read.
- Do not merge into master.
- Test against real refs in a throwaway clone or with fixtures, not by
  mutating the live worktrees - eight of them are in use.

## FILES ALLOWED

    scripts/claim_task.py
    tests/test_claim_task.py   (new)
    docs/DISPATCH-VISIBILITY-2026-09-16.md   (new)

## FILES FORBIDDEN

    src/   work/   config/   scripts/pool.sh

## DELIVERABLE

The two questions separated in code, the comparison made against master's
stage, the re-queue rule with its justification, named regression tests for the
139-143 double dispatch and for the 146/155 unintegrated case, and the tool
reporting stale-branch hiding out loud instead of silently.
