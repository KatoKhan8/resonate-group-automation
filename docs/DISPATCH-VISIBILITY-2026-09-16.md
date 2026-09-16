# Dispatch visibility: separating "is someone working" from "has work been done"

2026-09-16. TASK-195.

## The problem

`claim_task._claimed_on_a_branch` answered one question - "is this file NOT in
TODO on some branch?" - and used the answer for two different purposes:

1. **Collision prevention**: don't dispatch a task that a worker is actively
   running (TASK-139 through 143, TASK-146, TASK-155, TASK-164).
2. **Availability detection**: don't dispatch a task that looks free but isn't.

The rule "not in TODO = worked on" has two failure modes at once:

- **It hides available work.** Five branches forked from a BLOCKED master all
  inherited BLOCKED. When master moved the task to TODO, the branches still
  said BLOCKED - which the old code read as "not in TODO, therefore worked on"
  - and the task was hidden permanently. (TASK-183.)

- **It was the only thing that noticed finished work.** A branch that moved a
  task to DONE was correctly reported as "not in TODO", preventing
  double-dispatch. Removing the scan would recreate the TASK-139-through-143
  collision.

## The fix

Two separate questions, answered by two separate mechanisms:

### Question 1: Is a worker running on this task?

Answered by **claims** (`work/claims/*.claim`) AND by finding branches that
have moved a task file PAST what master shows, with a NEWER commit timestamp.

A branch whose file is in a different stage than master's, touched more
recently on the branch, has produced real work. The pool must not dispatch it
again. This preserves the TASK-139-through-143 and TASK-146/155 protection.

### Question 2: Has a stale branch hidden an available task?

Answered by finding tasks where master's stage differs from a branch's stage
AND master's commit timestamp is newer. The branch inherited its stage from
an older master and never moved the file. Master moved on; the branch is
stale.

These tasks are **reported out loud** - "TASK-183 is TODO on master; BLOCKED
on 5 branches (stale)" - rather than silently included or excluded. Silence
is what cost a night.

## The comparison: master's stage, not TODO

The old code asked "is this file NOT in TODO on some branch?" The new code
asks "is this file in a DIFFERENT stage on the branch than on master, and who
moved it more recently?"

A branch that has the file in the SAME stage master has it in has done
nothing with it. A branch in a DIFFERENT stage is resolved by commit
timestamp: whoever touched the file more recently moved it.

## The re-queue rule

When master moves a task backwards - BLOCKED to TODO, REVIEW to REWORK -
every existing branch is stale about it. The commit timestamp on master's new
path is newer than any branch's timestamp for the old path, so the branch
loses the comparison and the task becomes available.

A timestamp is the right signal because it is the only ordering that survives
a force-free workflow: branches cannot rewrite master's history, and master's
move is always a new commit with a later timestamp than the branch's
inherited copy. A commit counter or sequence number would require coordination
that does not exist. A branch name convention would break the moment someone
names a branch unexpectedly.

## What was not changed

- `_claimed_on_a_branch` still exists as a backwards-compatible wrapper. It
  returns the active set (tasks with real work on a branch), not the stale
  set.
- The remote-ref scan is preserved. `pool.sh`'s `checkout -B` destroys local
  refs when a worker is reused, and the pushed copy in `refs/remotes/origin/`
  is the only record of finished work (TASK-139 through 143).
- No branch is deleted, no force-push, no history rewrite, no claim release
  as a side effect of a status read.

## Files changed

    scripts/claim_task.py       _classify_branch_tasks, _format_stale_report
    tests/test_claim_task.py    21 regression tests naming every incident
    docs/DISPATCH-VISIBILITY-2026-09-16.md   this file
