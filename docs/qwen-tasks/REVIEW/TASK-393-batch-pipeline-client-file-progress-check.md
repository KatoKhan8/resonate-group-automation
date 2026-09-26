PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-393 — batch pipeline on the client file: verify TASK-347's progress

TASK-347 (client file through qualification/MX/CheapVerifier/research/facts,
in batches of 1,000, stop before copy) is already queued/possibly in flight.
This task's job: read TASK-347's CURRENT state (TODO/RUNNING/REVIEW/DONE,
across all worker branches, not just master) and report exactly how far it
has gotten — batches completed, qualification rate measured so far, any
blocker it hit — rather than waiting for a final result that may not land
before this session's handoff.

## Acceptance

1. Name TASK-347's real current state with evidence (branch, last commit,
   batches processed if any).
2. If it is stalled or blocked: name the blocker plainly, do not guess.
3. If genuinely not started: this task becomes "start it," following
   TASK-347's own spec exactly — do not restate or fork it.
4. No new code unless TASK-347 is confirmed not started and this task picks
   it up directly.

## What this task may NOT do

- Do not commit anything from work/ (client PII).
- No provider write, nothing sent.

## RESULT BLOCK

**STATUS:** DONE
**ARTIFACT KIND:** finding (read-only investigation, no code changed)
**COMMIT SHA:** 5f2c0436 (branch qwen-worker-2-r93)
**TESTS:** N/A — no code changed

### TASK-347 current state: NOT STARTED, zero batches processed

**Evidence across all branches:**

| Location | State | Detail |
|---|---|---|
| master | TODO/ | Task file present, never moved |
| qwen-worker-4-r68 | REVIEW/ | Commit `9f5a720a` — "five structural blockers prevent pipeline execution" |
| 7 other branches | BLOCKED/ | Commit pattern `bb51482e` etc. — "TASK-347 came back BLOCKED with real blockers" |
| No branch | DONE/ | Does not exist |

**Batches processed:** 0. No credits spent. No code was changed by any TASK-347 attempt.

### Five blockers reported (commit 9f5a720a, verified against master)

1. **CheapVerifier not in waterfall.** `src/providers/cheapverifier.py` exists only on `qwen-worker-5-r69` (commit `efa5edd6`, TASK-358). On master, `src/waterfall.py` declares email_verification as ContactOut, Deliverable and Reoon — CheapVerifier absent, so `record_step` raises WaterfallViolation on first paid call. **NOT resolved on master.**

2. **No person-centric import.** `ingest.py` dedupes by domain, dropping ~12,432 of the 33,887 CSV rows. No person-centric import path exists.

3. **No `work/queue.jsonl`.** The queue file does not exist in this worktree (gitignored, lives in Claude's worktree only per QWEN.md).

4. **No `work/stage/` intermediate files.** Absent.

5. **Pipeline order contradiction.** The requested qualification→MX→CheapVerifier→research→facts order contradicts the existing enrich→qualify fixed-point orchestration.

### Blocker resolution status

- **Blocker 1:** TASK-358 cherry-picked CheapVerifier into the email_verification waterfall, but that commit (`efa5edd6`) is on `qwen-worker-5-r69` only — **not merged to master**. Partial progress, not resolved.
- **Blockers 2-5:** No commits found addressing any of them on any branch.

### FILES CHANGED

- `docs/qwen-tasks/REVIEW/TASK-393-batch-pipeline-client-file-progress-check.md` (moved from TODO/, result block added)

### FINDINGS

TASK-347 is genuinely not started and remains blocked on master. The task spec says "if genuinely not started: this task becomes 'start it,'" but starting it requires resolving blockers 1-5 first, which are architectural (waterfall config, ingest pipeline, queue bootstrap) — not work this task can do without provider credentials and Claude's worktree access. No new code was written.

### RISKS

- TASK-347 has been picked up by at least 8 workers across branches, all of which returned BLOCKED or REVIEW without progress. The repeated collision suggests it needs explicit unblocking by Claude before another worker attempt.

### RECOMMENDED CLAUDE ACTION

1. Merge TASK-358 (CheapVerifier waterfall cherry-pick) from `qwen-worker-5-r69` to master — resolves blocker 1.
2. Decide on person-centric import (blocker 2) — this is an architectural decision.
3. Bootstrap `work/queue.jsonl` from the client CSV in Claude's worktree (blocker 3).
4. Resolve pipeline order contradiction (blocker 5) — architectural.
5. Only then re-queue TASK-347 for execution.
