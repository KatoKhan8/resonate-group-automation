PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-385 — a machine-derived status command, per OPERATING-MODE §30

`docs/OPERATING-MODE.md`: *"§30 requires a machine-derived status command so
state stops living in prose. Until it exists, `scripts/task_registry.py` and
`scripts/claim_task.py --status` are the authorities for task and worker
state, and the provider is the authority for campaign state."*

**Operator instruction, 2026-09-26/27 overnight:** every status report must
show workers running, GLM tasks running, tasks queued, and the reason for
any idle worker. Tonight this was assembled by hand from three separate
sources (`claim_task.py --status`, `git log`/`git status` across twelve
worktrees, and reading pool-logs by eye) — slow, and only as accurate as the
person doing it remembered to check.

## Build

    scripts/pool_status.py   NEW

One command, one JSON (or a `--human` flag for the readable form), that
answers exactly what a status report needs:

    workers: for each of the 12 known worktrees - idle or busy, current
             task id (if busy), current branch, whether its last checkout
             verified against origin/master (reuse the check TASK-... added
             to pool.sh - a worker whose branch is NOT cleanly based on
             origin/master is a finding, not silence)
    glm_tasks: which currently-running or recently-completed tasks are GLM
             verification/checkpoint tasks (by task id prefix or a registry
             field - decide which and say so), and their disposition
             (PASS/FAIL/pending) if finished
    queue: ready count, ready task ids with priority, and the count of
             genuinely idle workers vs ready tasks (the exact number the
             standing order's "refill before the queue drops below one
             ready task per idle worker" rule needs)
    idle_reasons: for each idle worker, WHY - no ready task, worktree
             locked, or a stuck/stale state the watchdog would flag
    stale_branches: reuse `claim_task.py`'s existing stale-branch detector,
             summarised as a count, not the full 100+ line dump

## Acceptance

1. Run it against the current live pool state and paste the output next to
   what `claim_task.py --status` + a manual worktree walk shows for the same
   moment - they must agree.
2. Deliberately make one worker idle with a genuinely empty ready queue;
   confirm `idle_reasons` reports "no ready task," not silence or a guess.
3. Deliberately leave one worktree on a stale branch (not reset to
   origin/master); confirm it is flagged, not silently reported as "busy."
4. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not invent a new task-status vocabulary — read from the existing
  TODO/RUNNING/REVIEW/DONE/REWORK/BLOCKED states and the registry.
- Read-only. No writes to any task file, no claims taken, no provider calls.
- Nothing sent, nothing activated.
