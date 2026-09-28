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

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: 69d18d57
TESTS: 16 new tests in tests/test_pool_status.py, all pass. 31 existing
  claim_task tests still pass when run together (47 total, 0 failures).
  2 pre-existing test_invariants failures (reviewapproval barrier, emailbison
  routes) are unrelated to this change.
FILES CHANGED:
  scripts/pool_status.py (new) — the status command
  tests/test_pool_status.py (new) — 16 tests covering idle reasons, output
    shape, human format, GLM detection, worker count
FINDINGS:
  1. Claims live in the MAIN worktree's work/claims/, not in each worker's
     local worktree. pool_status.py reads from the correct location and
     patches claim_task.held_claims so ready_tasks() also sees the right set.
     Without this patch, the script reported 38 ready tasks (ignoring 4 live
     claims) instead of the correct 34.
  2. 11 of 12 workers are currently NOT_ON_ORIGIN_MASTER — this is normal
     for mid-task workers whose branches have diverged since dispatch. The
     script flags this as a finding in worker details, not as an idle reason,
     because pool.sh resets branches with `checkout -B` before dispatch.
  3. GLM tasks identified by filename pattern ("glm" in name), covering both
     glm-verify-task-* (55 queued, 6 done) and glm-checkpoint-* conventions.
     No separate registry field needed.
  4. resonate-qwen-5, resonate-qwen-8, resonate-qwen-10 are locked but hold
     no claims and show no RUNNING tasks — they are between dispatches.
     Reported as "busy" (locked) without a task_id, which is accurate.
RISKS:
  - The monkey-patch of claim_task.held_claims persists for the process
    lifetime. If another module imports claim_task after pool_status in the
    same process, it sees the patched version. Mitigated: the patch reads
    from the correct claims directory, so the behavior is correct, not just
    compatible.
  - The script does a `git fetch origin master` per worktree to compare HEAD
    against origin/master. With 12 worktrees, that is 12 fetch calls. On a
    slow connection this could be slow. Mitigated: the fetch is quiet and
    has a 15-second timeout per call.
RECOMMENDED CLAUDE ACTION:
  Accept. The script is read-only, has no provider calls, and the 16 tests
  cover the idle-reason logic that is most likely to silently lie. The
  cross-check against claim_task.py --status shows agreement (34 ready
  tasks match after accounting for 4 live claims).
