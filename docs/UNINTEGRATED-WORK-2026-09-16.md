# Unintegrated Work — 2026-09-16

## What happened

On 2026-09-15, TASK-146 (finished on `qwen-worker-r19`) and TASK-155
(finished on `qwen-worker-7-r18`) sat invisible for a day. Both were pushed.
Neither was integrated. `claim_task.py` correctly reported them unavailable,
because `_claimed_on_a_branch` sees a branch that has moved the file out of
TODO. The result was a queue that reported `ready: 0` with nine files in TODO.
The pool logged "no ready task" eight times and stopped.

Three artefacts disagreed: TODO said available, the claim detector said taken,
and the registry said queued. All three were right about different things.

This document is the scan that makes the disagreement visible.

## How to reproduce

    py -3 scripts/task173_scan.py                  # full three-way report
    py -3 scripts/task173_scan.py --unintegrated    # only the disagreeing set
    py -3 scripts/task173_scan.py --prune           # safe-to-prune branches

## Unintegrated tasks as of 2026-09-16 morning

Master HEAD: `73b8988` (at time of scan)

Five tasks are finished on remote branches but master still shows them as
available. All five have result blocks with STATUS: DONE.

| Task     | Master stage | Finished on branch              | Branch stage | Result status |
|----------|-------------|---------------------------------|-------------|---------------|
| TASK-067 | ABSENT      | origin/qwen-worker-7            | REVIEW      | DONE          |
| TASK-169 | TODO        | origin/qwen-worker-r24          | REVIEW      | DONE          |
| TASK-170 | TODO        | origin/qwen-worker-3-r24        | REVIEW      | DONE          |
| TASK-172 | TODO        | origin/qwen-worker-5-r25        | DONE        | DONE          |
| TASK-174 | TODO        | origin/qwen-worker-7-r25        | DONE        | DONE          |

TASK-067 is absent from master entirely — it does not exist in any master
stage directory. It exists only on `origin/qwen-worker-7` in REVIEW.

TASK-172 and TASK-174 are in DONE on their branches, meaning the workers
considered them fully complete. They are in TODO on master, meaning Claude
has not yet moved them.

TASK-169 and TASK-170 are in REVIEW on their branches, meaning the workers
submitted them for review but Claude has not yet accepted or rejected them.

### What this means for the pool

The pool's `claim_task.py --next` correctly excludes these five tasks because
`_claimed_on_a_branch` sees them on remote branches. The pool will not
double-assign them. But the registry reports them as QUEUED, which inflates
the ready count and masks the true state of the backlog.

## Registry honesty

`scripts/task_registry.py` and `scripts/durable_state.py` have been updated
to include a `branch_blindness` field in their output JSON. This field states
plainly that they read master only and that unintegrated work is invisible to
them. The field points at `scripts/task173_scan.py --unintegrated` as the
command that shows the cross-branch view.

## Safe-to-prune branches

14 remote branches have every commit reachable from master. Proof:
`git merge-base --is-ancestor <branch> master` returns true for each.

| Branch                                | Commits ahead |
|---------------------------------------|---------------|
| origin                                | 0             |
| origin/qwen-worker-2-r22              | 0             |
| origin/qwen-worker-2-r23              | 0             |
| origin/qwen-worker-3-r22              | 0             |
| origin/qwen-worker-3-r23              | 0             |
| origin/qwen-worker-3-r24              | 0             |
| origin/qwen-worker-5-r24              | 0             |
| origin/qwen-worker-5-r25              | 0             |
| origin/qwen-worker-6-r24              | 0             |
| origin/qwen-worker-7-r18              | 0             |
| origin/qwen-worker-r19                | 0             |
| origin/qwen-worker-r22                | 0             |
| origin/qwen-worker-r23                | 0             |
| origin/qwen-worker-r24                | 0             |

**Note:** `origin/qwen-worker-7-r18` and `origin/qwen-worker-r19` are the
branches that carried TASK-155 and TASK-146 respectively — the two tasks that
sat invisible the night before. Their work has been integrated into master,
so they are now safe to prune.

## Not safe to prune

93 remote branches carry commits NOT reachable from master. The full list is
produced by `py -3 scripts/task173_scan.py --prune`. Each entry in that output
shows:

- The branch name
- How many commits it is ahead of master
- Whether it carries unmerged work in non-TODO stages (REVIEW, DONE, RUNNING,
  REWORK)
- Which tasks it carries in those stages

**No branch has been deleted.** Deletion is Claude's decision after reading
this list. The task forbids deletion by the worker.

## The pool.sh dispatch hazard

`pool.sh dispatch` runs `git checkout -B "$br" master`, which destroys the
local ref. A worker's second push to the same branch can only fast-forward if
the first result is already in master. This means a remote branch is sometimes
the ONLY copy of finished work.

The ancestry proof uses `git merge-base --is-ancestor` per commit, not per
branch, as the task requires. A branch with `ahead=0` and `ancestor=yes` has
nothing that master lacks, so deleting its remote ref loses nothing.

## What Claude should do

1. **Integrate the five unintegrated tasks.** Move their files from the
   branch versions into master's appropriate stage directories.
2. **Prune the 14 safe branches.** They carry nothing master lacks.
3. **Read the 93 unsafe branches.** Each one's unmerged task list is in the
   scan output. Some carry early-round work that has been superseded; others
   carry the only copy of a result.
4. **Re-run the registry** after integration to get an honest ready count.
