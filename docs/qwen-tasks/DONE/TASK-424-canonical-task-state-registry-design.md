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

---

## RESULT BLOCK

**STATUS:** DONE
**COMMIT SHA:** 55fb4664
**TESTS:** N/A — design-only task, no code changes
**FILES CHANGED:**
- `docs/TASK-STATE-REGISTRY-DESIGN.md` (new, 389 lines)

**FINDINGS:**

The design answers all four decisions with defended choices:

1. **Where the registry lives:** `docs/state/TASK-LEASES.json`, committed in git. The standing invariant says runtime state may live in `work/` but the logic that reasons about it may not. A scheduler registry is scheduling authority, not runtime state — it must survive a machine death and must not depend on gitignored state. The claim file (`work/claims/`) remains the atomic mutual-exclusion primitive; the registry is the durable ledger above it.

2. **Atomicity across worktrees:** Optimistic concurrency with a generation counter, not a lock. Each write increments the generation; a write that does not match the expected generation is rejected. `git pull --rebase` serializes concurrent commits. Locks do not work reliably across Windows/POSIX worktrees, and the volume (~12 workers, ~500 tasks) does not require a database.

3. **Reconciliation with branches:** The registry wins. A reconciliation sweep detects divergences (registry says RUNNING, branch says REVIEW) and reports them without silently resolving. Expired leases become STALE automatically. Integration gaps (registry says DONE, master says TODO) are reported to Claude via the existing notification mechanism.

4. **Migration:** The 116 unintegrated DONE/REVIEW branch results are seeded into the registry on day one. DONE/REVIEW branches become registry entries in those states (not re-queued). RUNNING branches with no live claim become STALE and are immediately re-queueable. The pool reports a non-zero ready count for the first time.

The test plan covers seven falsifiable tests: lease expiry, mutual exclusion, dead-worker recovery, branch divergence reporting, migration correctness, heartbeat renewal, and generation-counter concurrency. Each test states how it could pass while the registry is still wrong.

**RISKS:**

- **Generation counter contention:** Under heavy load (12 workers claiming simultaneously), the retry loop may exceed three attempts. The design defers to the next sweep rather than deadlocking.
- **Heartbeat reliability:** If the heartbeat is a side effect of the worker's commit, a worker that stops committing (but is still alive) will have its lease expire. An explicit `--heartbeat` command is more reliable but adds a new failure mode.
- **Migration correctness:** The migration must check the `TERMINAL_BRANCH_STAGES` priority (DONE wins over REVIEW) to avoid creating duplicate entries or re-queuing finished work.

**RECOMMENDED CLAUDE ACTION:**

Review the design document (`docs/TASK-STATE-REGISTRY-DESIGN.md`) and answer the four open questions in §7:

1. LEASE_TTL value (proposed: 45 minutes)
2. Heartbeat mechanism (side effect of commit vs. explicit command)
3. Completed task retention (proposed: last 500)
4. Reconciliation authority (auto-requeue STALE vs. human confirmation)

Once the design is approved, the build can proceed. The build should not change `claim_task.py`, `pool.sh` or `pool_watchdog.sh` until the one-account slice is complete (per the operator instruction in the task file).
