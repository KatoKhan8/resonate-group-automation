PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-424 — canonical task-state registry with worker leases: DESIGN ONLY

**Operator instruction, 2026-09-27, Qwen lane C. DESIGN NOW, BUILD AFTER THE
ONE-ACCOUNT SLICE.** This task produces a design document and a test plan. It
does **not** change `scripts/claim_task.py`, `scripts/pool.sh` or
`scripts/pool_watchdog.sh`. Until the registry is built, the existing
`claim_task.py` stale-branch behaviour stands.

## WHY, MEASURED TODAY RATHER THAN ARGUED

`claim_task.py` derives "is someone working on this" from git branches: a branch
holding a task file in a stage different from master's, with a newer commit, counts
as active work. Measured on 2026-09-27 at 12:45, that produced:

    143 task files in TODO/
    134 excluded as "active work on a branch"
      8 excluded for unmet dependencies
      1 correctly BLOCKED (TASK-309)
      0 READY

Of the 134, **46 were DONE on a branch and 70 were REVIEW** — finished or
review-ready work that was never integrated. Only 13 were RUNNING. So the pool
reported zero ready tasks and fired CRITICAL for hours while twelve workers sat
polling, because nothing distinguishes "a worker is working on this right now"
from "a branch from three weeks ago still has an old copy of this file".

Requeueing works only by rewriting master's copy so its timestamp beats every
branch's. That is a real mechanism and it is documented, but it means the scheduler's
authority is a commit timestamp comparison across ~270 refs, which cannot express
"this worker died at 23:08".

**The principle the operator states: branches are ARTIFACTS, never scheduler
authority.**

## WHAT TO DESIGN

One canonical registry, one row per task, as the single authority for scheduling:

    task_id       the task
    state         TODO / CLAIMED / RUNNING / REVIEW / DONE / BLOCKED /
                  STALE / RECOVERABLE  (propose the exact set and defend it)
    worker        which worker holds it
    claim_id      unique per claim attempt, so a second claim cannot be mistaken
                  for the first
    claimed_at    when
    heartbeat     last proof of life from the worker
    base_sha      what it started from
    branch        the artifact it is producing
    head_sha      where that artifact is now

**Worker leases.** A claim is a lease with an expiry, renewed by heartbeat. An
expired lease becomes **STALE / RECOVERABLE** automatically, with no human and no
watchdog special case. This is the part that would have prevented today's incident:
TASK-281 and TASK-372 sat for 684 and 675 minutes because the only signal was
"no commits since", and the watchdog's response was to give up after two attempts.

Design decisions to make and justify:

1. **Where the registry lives.** It is scheduling state, not prospect state, and
   it must survive a machine dying. `docs/state/` in git is durable and auditable
   but every write is a commit and concurrent workers will conflict. `work/` is
   fast but gitignored, and the standing invariant says business logic may not
   depend on gitignored `work/` (runtime state may live there; the logic that
   reasons about it may not). Say which side of that line a scheduler registry
   falls on, and why. This is the hardest question in the task; do not skip it.
2. **Atomicity across worktrees.** Twelve workers in twelve worktrees sharing one
   `.git`. How does a claim become atomic without the lock contention that made
   `--status` take 100 seconds before the two-git-calls optimisation?
3. **Reconciliation with branches.** Branches remain artifacts, so the registry
   and the branches can disagree. Define which wins (the registry) and how a
   disagreement is reported rather than silently resolved.
4. **Migration.** How the 116 unintegrated DONE/REVIEW branch results are
   represented on day one, without either losing them or blocking the queue.

## DELIVERABLES

A design document under `docs/`, plus a test plan listing the falsifiable tests
the build will have to pass. At minimum the test plan must cover: an expired lease
becomes RECOVERABLE without human action; two workers cannot hold one task; a dead
worker's task is recoverable without waiting on a commit timestamp; the registry
and a stale branch disagreeing is reported rather than silently resolved.

## WHAT THIS TASK MAY NOT DO

- **Do not build it.** No changes to `claim_task.py`, `pool.sh` or
  `pool_watchdog.sh`. A design that quietly starts editing the scheduler while
  twelve workers depend on it is how the pool stops.
- No send, activate, resume, enrol or attach. Provider writes zero.
- Do not delete or rewrite any branch. The 116 unintegrated results are real work.

## ACCEPTANCE

The document answers all four design decisions above with a defended choice rather
than a list of options, and the test plan's tests are falsifiable: each one states
how it could pass while the registry is still wrong.
