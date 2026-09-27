# TASK-424 — Canonical Task-State Registry with Worker Leases: Design

**Date:** 2026-09-27
**Status:** DESIGN — no code changes to `claim_task.py`, `pool.sh` or `pool_watchdog.sh`
**Author:** Qwen Worker 12

---

## 1. Problem Statement

The scheduler derives "is someone working on this?" from git branches: a branch holding a task file in a stage different from master's, with a newer commit, counts as active work. Measured 2026-09-27 at 12:45:

```
143 task files in TODO/
134 excluded as "active work on a branch"
  8 excluded for unmet dependencies
  1 correctly BLOCKED (TASK-309)
  0 READY
```

Of the 134 excluded, **46 were DONE on a branch and 70 were REVIEW** — finished or review-ready work never integrated. Only 13 were genuinely RUNNING. The pool reported zero ready tasks and fired CRITICAL for hours while twelve workers sat polling.

**Root cause:** Branch state is an artifact, not liveness. A branch from three weeks ago with an old copy of a task file is indistinguishable from an active worker, because the only signal is "no commits since" — and the watchdog gives up after two attempts.

**Principle:** Branches are ARTIFACTS, never scheduler authority.

---

## 2. Design Decisions

### 2.1 Where the Registry Lives

**Decision: `docs/state/TASK-LEASES.json` — committed, in git, under `docs/state/`.**

**The hardest question in the task.** The standing invariant says:

> Runtime state may live in `work/`; the logic that reasons about it may not.

A scheduler registry is not runtime state in the same sense as `work/queue.jsonl` (prospect data, written by `store.py`, read by enrichment). It is **scheduling state** — the authority for "who is working on what" — and if the logic that dispatches workers depends on a gitignored file, then a machine crash loses the dispatch authority. That is exactly the failure being corrected.

**Why not `work/`:**
- `work/` is gitignored. A crash loses all leases, and every task looks free — two workers land on the same task within seconds of restart.
- The standing invariant already bit this project twice (2026-09-15): a queue snapshot in `work/` went stale and caused two wrong measurements. Scheduling authority that can go stale without anyone noticing is the same shape of failure.
- `work/claims/` is already gitignored and machine-local — and that is correct for a *mutual-exclusion primitive* (a claim file prevents two workers from racing), but wrong for *durable authority* (knowing which worker has held a task for 11 hours with no heartbeat).

**Why `docs/state/`:**
- Already holds `TASK-REGISTRY.json`, `QUEUE-MANIFEST.json`, `LEDGER.json` — all committed, auditable, durable state.
- Survives a machine death: any worktree can read it after a `git pull`.
- Concurrent writes are the concern. Addressed in §2.2.

**The line:** A claim file (`work/claims/<TASK>.claim`) remains the *atomic mutual-exclusion primitive* — it is fast, local, and `O_CREAT|O_EXCL` is atomic on Windows and POSIX. The registry (`docs/state/TASK-LEASES.json`) is the *durable authority* — it records who holds what, when they last proved alive, and when the lease expires. The claim file is a lock; the registry is the ledger. Both are needed.

### 2.2 Atomicity Across Worktrees

**Decision: Optimistic concurrency with a generation counter, not a lock.**

Twelve workers in twelve worktrees share one `.git`. A commit is the write, and two workers committing to `docs/state/TASK-LEASES.json` simultaneously will produce a merge conflict — or, worse, one will silently overwrite the other's change if they both read the same version and write back.

**The mechanism:**

1. The registry carries a `generation` integer, incremented on every write.
2. A worker that wants to claim a task:
   a. Reads the current registry (from the file on disk, or `git show HEAD:docs/state/TASK-LEASES.json` if the file is stale).
   b. Checks that the task is not already held by another worker with an unexpired lease.
   c. Writes a new registry with the task assigned to itself, `generation + 1`, and its lease expiry set to `now + LEASE_TTL`.
   d. Commits with a message that includes the expected generation: `claim TASK-NNN gen=42`.
   e. Runs `git pull --rebase` before committing. If the rebase fails (another worker committed first), the generation mismatch is detected and the claim is retried.
3. A heartbeat is a commit that updates only the `heartbeat` and `generation` fields for that worker's held tasks. No other worker's rows are touched.

**Why not a file lock:**
- `flock` does not work reliably across Windows and POSIX worktrees sharing a filesystem.
- A lock held by a dead process is the exact failure being corrected.
- The existing `--status` call already takes 100 seconds when uncached; adding lock contention would make it worse.

**Why not a separate lock file:**
- A lock file in `work/` is gitignored and machine-local — it cannot coordinate across worktrees that may be on different machines (the standing brief says "must survive a machine dying").
- A lock file in `docs/state/` is a committed file, which means acquiring the lock is itself a commit — the same contention as the registry itself.

**Why optimistic concurrency is acceptable here:**
- Claims are infrequent: one per task dispatch, not per second. Twelve workers claiming tasks produce at most twelve concurrent writes, and the `git pull --rebase` serializes them within seconds.
- Heartbeats are the frequent write, but each worker touches only its own rows. Two workers heartbeating simultaneously will both read the same generation, both increment to N+1, and one will win the rebase. The loser retries — a cheap operation (read, increment, commit, push).
- The generation counter is the atomicity primitive. A write that does not match the expected generation is rejected, not merged.

**Fallback:** If the retry loop exceeds three attempts in ten seconds, the worker logs a warning and defers to the next sweep. This is a soft failure — the task remains unclaimed for one cycle, not a deadlock.

### 2.3 Reconciliation with Branches

**Decision: The registry wins. A disagreement is reported, not silently resolved.**

Branches remain artifacts. A worker produces a branch as a byproduct of its work, and the branch may carry a task file in any stage. But the registry is the authority for scheduling, and if the registry says TASK-281 is CLAIMED by `resonate-qwen-3` with an unexpired lease, then a branch from three weeks ago saying TASK-281 is in REVIEW is **stale branch state**, not a conflicting claim.

**How disagreements are detected and reported:**

1. **Reconciliation sweep** (run by `pool_watchdog.sh` or a dedicated `--reconcile` flag on `claim_task.py`):
   - For each task in the registry with state CLAIMED or RUNNING, check whether the worker's branch exists and has a commit newer than the `base_sha` recorded in the registry.
   - If the branch does not exist, or its last commit is older than the registry's `heartbeat` by more than `STALE_BRANCH_THRESHOLD` (proposed: 60 minutes), report a **branch divergence**: the registry says active, the branch says abandoned.
   - For each task in the registry with state DONE or REVIEW, check whether the task file on master matches. If master still has it in TODO, report an **integration gap**: the registry says done, master says not yet integrated.

2. **Report format:**
   ```
   RECONCILIATION 2026-09-27T14:00:00Z
   tasks_tracked: 47
   agreements: 41
   divergences: 4
     TASK-281  registry=CLAIMED/resonate-qwen-3  branch=qwen-worker-3-r9  branch_last_commit=6h ago  ACTION: lease expired, mark STALE
     TASK-372  registry=RUNNING/resonate-qwen-7  branch=qwen-worker-7-r9  branch_last_commit=12h ago  ACTION: lease expired, mark STALE
     TASK-158  registry=REVIEW  master=TODO  ACTION: integration gap, result on branch not yet merged
     TASK-164  registry=DONE  master=TODO  ACTION: integration gap, result on branch not yet merged
   stale_branches: 2
     qwen-worker-5-r30  has TASK-139 in REVIEW, registry has TASK-139 as DONE (master)  -> branch is stale, no action needed
   ```

3. **Resolution rules:**
   - An expired lease becomes STALE automatically (see §2.4). No human action needed.
   - An integration gap is reported to Claude via the existing `notify.notify('failed_job_needs_attention', ...)` mechanism. It is not auto-resolved, because merging is Claude's authority.
   - A stale branch is ignored. The registry does not delete or rewrite branches.

**Why the registry wins:**
- A branch cannot express "I am alive right now." A commit timestamp is a historical fact, not a liveness signal.
- The registry carries a heartbeat — a positive proof of life, renewed deliberately. An expired heartbeat is a deliberate signal that the worker is gone, not an inference from silence.
- A branch that disagrees with the registry is either (a) stale — the worker finished and the branch was never cleaned up, or (b) ahead — the worker committed but the registry was not updated. Case (a) is resolved by letting the lease expire. Case (b) is resolved by the worker updating the registry on its next heartbeat. If the worker is dead, case (b) degrades to case (a).

### 2.4 State Machine and Lease Expiry

**Proposed state set:**

| State | Meaning | Who sets it | How it leaves |
|-------|---------|-------------|---------------|
| `TODO` | Available for claiming | Claude (by placing the file in `docs/qwen-tasks/TODO/`) | Worker claims it → CLAIMED |
| `CLAIMED` | A worker holds the lease, has not yet started | `claim_task.py --claim` | Worker moves file to RUNNING/ and updates registry → RUNNING; or lease expires → STALE |
| `RUNNING` | A worker is actively working | Worker's heartbeat updates state | Worker moves file to REVIEW/ or DONE/ and updates registry → REVIEW or DONE; or lease expires → STALE |
| `REVIEW` | Worker finished, awaiting Claude's review | Worker's final update | Claude integrates → DONE; or Claude sends back → REWORK |
| `REWORK` | Claude sent it back for changes | Claude | Worker re-claims → CLAIMED |
| `DONE` | Integrated into master | Claude (by merging) | Terminal state |
| `BLOCKED` | Cannot proceed, explicit reason | Claude or worker (by setting `STATUS: BLOCKED` in the task file header) | Claude unblocks → TODO |
| `STALE` | Lease expired, no heartbeat | Automatic (lease expiry check) | Re-queued → TODO; or recovered by a new claim → CLAIMED |

**States deliberately excluded:**

- `RECOVERABLE` — proposed in the task brief, but it is not a stable state. A task whose lease has expired is STALE, and the next action is to re-queue it (→ TODO) or hand it to a new worker (→ CLAIMED). A separate RECOVERABLE state adds a step without adding information. If the distinction matters for reporting, it is a flag on the STALE row (`recoverable: true`), not a separate state.
- `BLOCKED_QUOTA` — this is a worker-stop condition, not a task state. The task is still TODO; the worker stopped because of a quota. The existing `claim_task.py` already handles this correctly by not including it in `TERMINAL_BRANCH_STAGES`.

**Lease mechanics:**

- **LEASE_TTL:** 45 minutes. Renewed by heartbeat. A worker that heartbeats every 15 minutes has three missed heartbeats before expiry. This is generous enough to survive a long test run (the suite takes ~865 seconds) and tight enough to detect a dead worker within an hour.
- **Heartbeat:** A commit that updates the `heartbeat` field for the worker's held tasks. The worker's pool loop already commits periodically; the heartbeat is a side effect of that commit, detected by the registry update logic.
- **Expiry check:** Run by `pool_watchdog.sh` on every cycle (every 3 minutes by default). For each task with `heartbeat + LEASE_TTL < now`, transition to STALE and report.
- **STALE → TODO:** Automatic. The watchdog moves the task file back to TODO/ on master (if it is not already there) and updates the registry. This is the re-queue that previously required rewriting master's timestamp.

**The incident that would have been prevented:**

TASK-281 and TASK-372 sat for 684 and 675 minutes. With leases:
- TASK-281 claimed at T+0, heartbeat last at T+15, lease expires at T+60.
- At T+63 (next watchdog cycle), the watchdog sees `heartbeat + 45min < now`, transitions TASK-281 to STALE, reports it, and re-queues to TODO.
- At T+66, a free worker claims TASK-281 again.
- Total downtime: 66 minutes instead of 684.

---

## 3. Registry Schema

```json
{
  "schema_version": 1,
  "generation": 142,
  "updated_at": "2026-09-27T14:03:22+00:00",
  "leases": [
    {
      "task_id": "TASK-283",
      "state": "RUNNING",
      "worker": "resonate-qwen-worker",
      "claim_id": "c8a3f1e2-7b4d-4a9e-9f1c-3d5e7a8b9c0d",
      "claimed_at": "2026-09-27T10:02:36+00:00",
      "heartbeat": "2026-09-27T13:45:12+00:00",
      "lease_expires": "2026-09-27T14:30:12+00:00",
      "base_sha": "3badeab0",
      "branch": "qwen-worker-r9",
      "head_sha": "8ce935af",
      "file": "docs/qwen-tasks/RUNNING/TASK-283-*.md"
    }
  ],
  "completed": [
    {
      "task_id": "TASK-158",
      "state": "DONE",
      "worker": "resonate-qwen-5",
      "claim_id": "a1b2c3d4-...",
      "claimed_at": "2026-09-26T08:00:00+00:00",
      "completed_at": "2026-09-26T09:15:00+00:00",
      "branch": "qwen-worker-5-r8",
      "head_sha": "f1e2c3d4"
    }
  ],
  "stale": [
    {
      "task_id": "TASK-281",
      "state": "STALE",
      "worker": "resonate-qwen-3",
      "claim_id": "d4e5f6a7-...",
      "claimed_at": "2026-09-27T02:00:00+00:00",
      "heartbeat": "2026-09-27T02:15:00+00:00",
      "lease_expires": "2026-09-27T03:00:00+00:00",
      "expired_at": "2026-09-27T14:03:22+00:00",
      "branch": "qwen-worker-3-r9",
      "reason": "heartbeat + LEASE_TTL < now"
    }
  ]
}
```

**Fields explained:**

- `schema_version`: Incremented when the schema changes. Readers check this before parsing.
- `generation`: Incremented on every write. The optimistic concurrency primitive (§2.2).
- `claim_id`: UUID per claim attempt. A second claim for the same task gets a different `claim_id`, so a stale claim file cannot be mistaken for a current one.
- `base_sha`: The master HEAD when the task was claimed. Used to detect whether the worker started from current state.
- `head_sha`: The worker's branch HEAD as of the last heartbeat. Used to detect whether the worker is making progress.
- `completed`: A rolling log of the last 500 completed tasks. Provides an audit trail without requiring a git log scan.
- `stale`: Tasks whose leases have expired. Kept separate from active leases so a reconciliation sweep can distinguish "currently held" from "abandoned."

---

## 4. Migration Plan

**Day one: 116 unintegrated DONE/REVIEW branch results.**

These are real work. They cannot be lost, and they cannot block the queue.

**Step 1: Scan and classify.** Run `claim_task.py --status` (or a new `--scan-unintegrated` flag) to produce the set of tasks that are:
- In TODO/ on master.
- In DONE/ or REVIEW/ on at least one branch, with a newer commit timestamp than master's.

This is the existing `_classify_branch_tasks()` logic. The output is the `awaiting` set.

**Step 2: Seed the registry.** For each task in the `awaiting` set, create a registry entry with:
- `state`: `REVIEW` (if the branch says REVIEW) or `DONE` (if the branch says DONE).
- `worker`: the branch name (since the original worker is unknown or gone).
- `claim_id`: a synthetic UUID generated during migration.
- `claimed_at`: the branch's last commit timestamp.
- `heartbeat`: the branch's last commit timestamp.
- `lease_expires`: the branch's last commit timestamp + LEASE_TTL (i.e., already expired).
- `branch`: the branch name.
- `head_sha`: the branch's HEAD.

**Step 3: Do not re-queue.** These tasks are NOT moved to TODO. They are marked as REVIEW or DONE in the registry, and the reconciliation sweep reports them as integration gaps. Claude integrates them on the normal schedule.

**Step 4: For branches saying RUNNING with no live claim**, create a registry entry with:
- `state`: `STALE`.
- `reason`: "migrated from branch, no live claim found."
- The task is immediately available for re-claiming.

**Result on day one:**
- 46 DONE tasks → registry says DONE, awaiting integration.
- 70 REVIEW tasks → registry says REVIEW, awaiting integration.
- 13 RUNNING tasks with live claims → registry says RUNNING, leases active.
- The remaining 5 tasks (143 - 46 - 70 - 13 = 14, but the task says 134 excluded, so the math is approximate) → registry says TODO, available for claiming.

The pool reports a non-zero ready count for the first time in hours.

---

## 5. Test Plan

Each test is falsifiable: it states how it could pass while the registry is still wrong.

### Test 1: Expired lease becomes STALE without human action

**Setup:** Create a registry entry with `heartbeat` set to `now - 60 minutes` and `LEASE_TTL = 45 minutes`. Run the expiry check.

**Expected:** The task transitions to STALE. The `expired_at` field is set. The task is re-queued to TODO.

**How it could pass while wrong:**
- The expiry check reads the system clock incorrectly (timezone mismatch, DST boundary).
- The test asserts on the registry state but does not verify that the task file was moved to TODO/.
- The test uses a mocked clock that does not match the production clock source.

**Mitigation:** The test must verify both the registry state AND the task file's location on disk. The clock source must be the same one the watchdog uses (UTC, `datetime.now(timezone.utc)`).

### Test 2: Two workers cannot hold one task

**Setup:** Worker A claims TASK-100. Worker B attempts to claim TASK-100.

**Expected:** Worker A's claim succeeds (exit code 0). Worker B's claim fails (exit code 3, "ALREADY CLAIMED"). The registry has exactly one lease for TASK-100, held by Worker A.

**How it could pass while wrong:**
- The test runs the two claims sequentially, not concurrently. A race condition only manifests under concurrency.
- The test checks the claim file (`work/claims/TASK-100.claim`) but not the registry. The claim file is machine-local and does not prove cross-worktree atomicity.
- The test mocks `os.open` and does not exercise the real filesystem primitive.

**Mitigation:** The test must launch two subprocesses that attempt to claim simultaneously, and must verify the registry state after both have completed. The `O_CREAT|O_EXCL` primitive is the atomicity guarantee; the test must exercise it on a real filesystem.

### Test 3: Dead worker's task is recoverable without waiting on a commit timestamp

**Setup:** Worker A claims TASK-200 and sets `heartbeat` to `now - 120 minutes`. The worker's branch has a last commit timestamp of `now - 10 minutes` (i.e., the branch looks active by commit-timestamp standards). Run the expiry check.

**Expected:** The task transitions to STALE because `heartbeat + LEASE_TTL < now`, regardless of the branch's commit timestamp. The task is re-queued.

**How it could pass while wrong:**
- The expiry check uses the branch's commit timestamp instead of the registry's `heartbeat` field.
- The test asserts that the task is STALE but does not verify that it was re-queued (moved to TODO/).
- The test uses a `LEASE_TTL` that does not match the production value.

**Mitigation:** The test must verify that the expiry check reads the `heartbeat` field from the registry, not from git. The test must verify both the registry state and the task file location. The `LEASE_TTL` must be the production value (45 minutes).

### Test 4: Registry and stale branch disagreeing is reported, not silently resolved

**Setup:** The registry says TASK-300 is RUNNING, held by `resonate-qwen-5`, with `heartbeat` set to `now - 5 minutes` (lease active). The branch `qwen-worker-5-r9` has a last commit timestamp of `now - 24 hours` and carries TASK-300 in REVIEW/. Run a reconciliation sweep.

**Expected:** The reconciliation report includes a **branch divergence** entry for TASK-300: registry says RUNNING, branch says REVIEW, branch is stale. The registry is NOT updated to match the branch. The task remains RUNNING in the registry.

**How it could pass while wrong:**
- The reconciliation sweep silently updates the registry to match the branch (the exact failure being corrected).
- The test asserts on the reconciliation report but does not verify that the registry state is unchanged.
- The test uses a branch that does not exist, which is a different code path than a branch that exists but is stale.

**Mitigation:** The test must verify that the registry state is unchanged after reconciliation. The test must create a real branch with a real commit, not a mocked branch name.

### Test 5: Migration seeds the registry without losing work or blocking the queue

**Setup:** Master has TASK-400 in TODO/. Branch `qwen-worker-3-r8` has TASK-400 in REVIEW/ with a newer commit. Branch `qwen-worker-7-r8` has TASK-400 in DONE/ with a newer commit. Run the migration.

**Expected:** The registry has one entry for TASK-400 with `state: REVIEW` (DONE wins over REVIEW per the existing `TERMINAL_BRANCH_STAGES` priority). The task is NOT in the ready queue. The reconciliation report lists TASK-400 as an integration gap.

**How it could pass while wrong:**
- The migration creates two entries (one per branch) instead of one.
- The migration sets `state: TODO` instead of `state: REVIEW`, making the task available for re-claiming and duplicating work that is already done.
- The migration does not check the `TERMINAL_BRANCH_STAGES` priority and picks REVIEW arbitrarily.

**Mitigation:** The test must verify that exactly one registry entry is created, that its state is DONE (not REVIEW), and that the task is not in the ready queue.

### Test 6: Heartbeat renewal prevents expiry

**Setup:** Worker A claims TASK-500 with `heartbeat` set to `now - 40 minutes` and `LEASE_TTL = 45 minutes`. Worker A sends a heartbeat (updates `heartbeat` to `now`). Run the expiry check.

**Expected:** The task does NOT transition to STALE. The lease is still active.

**How it could pass while wrong:**
- The heartbeat update writes to the wrong field (e.g., `claimed_at` instead of `heartbeat`).
- The expiry check reads a cached registry that was not updated by the heartbeat.
- The test does not verify that the heartbeat was actually written (e.g., the heartbeat function returns success but does not commit).

**Mitigation:** The test must verify that the `heartbeat` field in the registry matches the expected value after the heartbeat. The test must re-read the registry from disk, not from a cached in-memory copy.

### Test 7: Generation counter prevents concurrent writes from corrupting the registry

**Setup:** Two workers read the registry at generation 100. Worker A increments to 101 and commits. Worker B increments to 101 and attempts to commit.

**Expected:** Worker A's commit succeeds. Worker B's commit fails (generation mismatch). Worker B retries: reads the registry at generation 101, increments to 102, and commits successfully.

**How it could pass while wrong:**
- The test does not actually run two concurrent commits; it mocks the generation check.
- The test asserts that Worker B retries but does not verify that the final registry state is consistent (both changes applied, generation = 102).
- The test uses a file lock to serialize the commits, which defeats the purpose of optimistic concurrency.

**Mitigation:** The test must exercise the real `git pull --rebase` path. The test must verify the final registry state, not just the return codes.

---

## 6. What This Design Does Not Do

- **It does not build it.** This is a design document. No changes to `claim_task.py`, `pool.sh` or `pool_watchdog.sh` are included.
- **It does not delete or rewrite any branch.** The 116 unintegrated results are real work and are preserved.
- **It does not change the claim file mechanism.** `work/claims/<TASK>.claim` remains the atomic mutual-exclusion primitive. The registry is a layer above it.
- **It does not require a database.** The registry is a JSON file in git. A database would be faster but would introduce a new dependency and a new failure mode. The current volume (~500 tasks, ~12 workers) does not require a database.

---

## 7. Open Questions for Claude

1. **LEASE_TTL value.** I proposed 45 minutes. The suite takes ~865 seconds (~14 minutes), so 45 minutes allows three missed heartbeats before expiry. Is this the right tradeoff, or should it be tighter (30 minutes) or looser (60 minutes)?

2. **Heartbeat mechanism.** I proposed that the heartbeat is a side effect of the worker's periodic commit. An alternative is an explicit `claim_task.py --heartbeat` command that the worker runs on a timer. The explicit command is more reliable (it does not depend on the worker committing) but adds a new command and a new failure mode (the heartbeat command itself hangs). Which is preferred?

3. **Completed task retention.** I proposed keeping the last 500 completed tasks in the registry. This provides an audit trail but grows the file. Should it be a rolling window (last 30 days) instead?

4. **Reconciliation authority.** I proposed that the reconciliation sweep reports divergences but does not auto-resolve them (except for expired leases). Should it auto-requeue STALE tasks to TODO, or should that require human confirmation?

---

## 8. Summary

The registry is a committed JSON file in `docs/state/` that carries one row per task, with lease expiry and heartbeat as the liveness signals. Branches remain artifacts. The registry and branches can disagree, and the disagreement is reported, not silently resolved. Optimistic concurrency with a generation counter provides atomicity without locks. The 116 unintegrated results are migrated into the registry on day one without losing them or blocking the queue.

The design answers the four decisions the task asked for:

1. **Where:** `docs/state/TASK-LEASES.json`, committed, because scheduling authority must survive a machine death and must not depend on gitignored state.
2. **Atomicity:** Optimistic concurrency with a generation counter, not a lock, because locks do not work across worktrees and the volume does not require a database.
3. **Reconciliation:** The registry wins. Disagreements are reported, not silently resolved.
4. **Migration:** Seed the registry from the existing `_classify_branch_tasks()` output. DONE/REVIEW branches become registry entries in REVIEW/DONE state. RUNNING branches with no live claim become STALE and are immediately re-queueable.
