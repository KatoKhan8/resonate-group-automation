# TASK-530 — GLM Independent Verification of TASK-424

**Review target:** TASK-424, canonical task-state registry with worker leases  
**Branch reviewed:** `origin/qwen-worker-12-r9-sync`  
**Branch HEAD SHA reviewed:** `3da4a246ee2536760d04dfc4d1d94b649160c2fa`  
**Review date:** 2026-09-29  
**Reviewer:** GLM (Qwen Worker 7)  
**Protocol:** `docs/GLM-REVIEW-PROTOCOL.md`

---

## Executive Summary

**DISPOSITION: MERGE (cherry-pick)**

TASK-424 is a design-only task that produced a 389-line design document answering four defended design decisions and a 7-test falsifiable test plan. The artifact exists on the exact ref reviewed, does what the result block claims, and does not violate the task's explicit prohibitions. The branch carries 34 commits from multiple tasks, but TASK-424's own three commits are clean and isolated. Cherry-picking `55fb4664` (design doc) and `b063f188` (result block) is safe.

---

## Verification Steps

### 1. Artifact Existence on the Exact Ref

**Claim:** Design document exists at `docs/TASK-STATE-REGISTRY-DESIGN.md`  
**Verified:** ✓

```bash
$ git log --diff-filter=A --all -- docs/TASK-STATE-REGISTRY-DESIGN.md
commit 55fb4664dd3e93e3a0de81e21157e091000fe1e0
    TASK-424: canonical task-state registry design with worker leases

$ wc -l docs/TASK-STATE-REGISTRY-DESIGN.md
389 docs/TASK-STATE-REGISTRY-DESIGN.md
```

The file exists at SHA `3da4a246`, was added in commit `55fb4664`, and is 389 lines as claimed. It does not exist on master.

### 2. Result Block Accuracy

**Claim:** "STATUS: DONE, COMMIT SHA: 55fb4664, TESTS: N/A — design-only task, no code changes, FILES CHANGED: docs/TASK-STATE-REGISTRY-DESIGN.md (new, 389 lines)"  
**Verified:** ✓

TASK-424's own commits:
- `fe832a8a` — Move task file from TODO/ to RUNNING/ (0 lines changed)
- `55fb4664` — Add design document (389 lines, 1 file)
- `b063f188` — Add result block to task file (41 lines, 1 file)

The result block is accurate. No code changes in TASK-424's own commits.

### 3. Task Prohibitions Respected

**Claim:** "Do not build it. No changes to `scripts/claim_task.py`, `pool.sh` or `pool_watchdog.sh`."  
**Verified:** ✓

```bash
$ git diff master...HEAD --stat -- scripts/claim_task.py scripts/pool.sh scripts/pool_watchdog.sh
 scripts/claim_task.py | 177 +++++++++++++++++++++++++++++++++++++++++++-------
```

The branch DOES change `claim_task.py`, but those changes belong to commit `e111d611` ("Branch state is an artifact: a held claim is the only liveness authority"), which is an interim fix that references TASK-424 as the permanent solution. TASK-424's own commits do not touch any forbidden file.

### 4. Design Quality — Four Decisions Answered

**Acceptance criterion:** "The document answers all four design decisions above with a defended choice rather than a list of options."  
**Verified:** ✓

| Decision | Section | Choice | Defense |
|----------|---------|--------|---------|
| Where the registry lives | §2.1 | `docs/state/TASK-LEASES.json` (committed, in git) | Survives machine death; `work/` is gitignored and went stale twice (2026-09-15); claim file remains the atomic primitive, registry is the durable ledger |
| Atomicity across worktrees | §2.2 | Optimistic concurrency with generation counter | `flock` unreliable across Windows/POSIX; lock held by dead process is the failure being corrected; volume (~12 workers, ~500 tasks) does not require a database |
| Reconciliation with branches | §2.3 | Registry wins; disagreements reported, not silently resolved | Branch cannot express liveness; commit timestamp is historical fact, not proof of life; expired heartbeat is deliberate signal |
| Migration | §4 | Seed 116 unintegrated results; DONE/REVIEW branches become registry entries, not re-queued | Preserves real work; does not block the queue; reconciliation reports integration gaps |

Each decision is stated as a choice, not a list of options, and is defended against alternatives.

### 5. Test Plan Falsifiability

**Acceptance criterion:** "The test plan's tests are falsifiable: each one states how it could pass while the registry is still wrong."  
**Verified:** ✓

Seven tests, each with a "How it could pass while wrong" section:

1. Expired lease becomes STALE without human action
2. Two workers cannot hold one task
3. Dead worker's task is recoverable without waiting on a commit timestamp
4. Registry and stale branch disagreeing is reported, not silently resolved
5. Migration seeds the registry without losing work or blocking the queue
6. Heartbeat renewal prevents expiry
7. Generation counter prevents concurrent writes from corrupting the registry

Each test states concrete failure modes (timezone mismatch, mocked clock, sequential not concurrent execution, asserts on wrong field, cached registry, etc.) and mitigations.

### 6. Existence Is Not Function

**Concern:** Is the design document consumed by anything?  
**Assessment:** This is a design-only task. The task instruction says "DESIGN NOW, BUILD AFTER THE ONE-ACCOUNT SLICE." The deliverable is a document meant to inform future work, not code with production callers. "Consumed" in this context means "reviewed by Claude and used as a basis for the build" — a human action, not a code action. The design document is the artifact, and it exists.

### 7. Merge Safety — Would Merging Delete Anything?

**Check:** `git diff master...HEAD --diff-filter=D --name-only`  
**Result:** 6 task files deleted from TODO/

```
docs/qwen-tasks/TODO/TASK-335-recover-the-audit-and-the-two-provider-artifacts-from-branches.md
docs/qwen-tasks/TODO/TASK-405-glm-verify-task-394.md
docs/qwen-tasks/TODO/TASK-409-glm-verify-task-294.md
docs/qwen-tasks/TODO/TASK-415-sender-inventory-drift-check.md
docs/qwen-tasks/TODO/TASK-417-campaign-cadence-drift-check.md
docs/qwen-tasks/TODO/TASK-418-offer-config-consistency-check.md
```

**Assessment:** These are legitimate task lifecycle moves (TODO → RUNNING/REVIEW/DONE/BLOCKED) by other tasks on this branch. TASK-424's own commits do not delete anything. Cherry-picking TASK-424's commits (`55fb4664`, `b063f188`) would not delete any files.

### 8. Scope Drift

**Check:** How many commits on the branch, and which belong to TASK-424?  
**Result:** 34 commits ahead of master. TASK-424's own commits: 3 (`fe832a8a`, `55fb4664`, `b063f188`).

The branch carries work from TASK-245, TASK-272, TASK-311, TASK-335, TASK-355, TASK-364, TASK-397, TASK-405, TASK-409, TASK-415, TASK-417, TASK-418, TASK-426, TASK-427, TASK-434, and others. Two commits (`e111d611`, `53a28c06`) mention TASK-424 in their messages but are not part of TASK-424 — they are related work (interim fix and offers regression fix) that reference TASK-424 as context.

**Cherry-pick scope:** To merge TASK-424 alone, cherry-pick `55fb4664` (design doc) and `b063f188` (result block). The task file move (`fe832a8a`) is optional and may conflict with master's task file state.

---

## Findings

### Finding 1: Design Document Quality — PASS

The design document is comprehensive, answers all four decisions with defended choices, and provides a falsifiable test plan. The writing is clear, the reasoning is explicit, and the alternatives are considered and rejected with reasons.

**Evidence:**
- §2.1–2.3 each state a decision and defend it against alternatives
- §4 provides a 4-step migration plan
- §5 provides 7 tests, each with "How it could pass while wrong" and "Mitigation"
- §7 lists 4 open questions for Claude, showing the design is not complete but is ready for review

**Disposition:** No defect. The design is a legitimate deliverable for a design-only task.

### Finding 2: Result Block Accuracy — PASS

The result block accurately describes the artifact: 389 lines, design-only, no code changes in TASK-424's own commits.

**Evidence:**
- `wc -l docs/TASK-STATE-REGISTRY-DESIGN.md` → 389
- `git show --stat 55fb4664` → 1 file, 389 insertions
- `git show --stat b063f188` → 1 file, 41 insertions (result block)

**Disposition:** No defect. The result block is accurate.

### Finding 3: Task Prohibitions Respected — PASS

TASK-424's own commits do not change `claim_task.py`, `pool.sh`, or `pool_watchdog.sh`. The branch does change `claim_task.py`, but that belongs to a different commit (`e111d611`) that is an interim fix referencing TASK-424 as the permanent solution.

**Evidence:**
- `git show --stat fe832a8a 55fb4664 b063f188` → only `docs/TASK-STATE-REGISTRY-DESIGN.md` and the task file
- `git show --stat e111d611` → `scripts/claim_task.py` and `tests/test_claim_task_readiness_is_not_inferred.py` (interim fix, not TASK-424)

**Disposition:** No defect. TASK-424 respected the prohibitions.

### Finding 4: Branch Scope Drift — INFORMATIONAL

The branch carries 34 commits from multiple tasks. This is expected for a sync branch but means merging the branch would bring in other work. TASK-424's contribution is clean and can be cherry-picked in isolation.

**Evidence:**
- `git log --oneline master..HEAD | wc -l` → 34
- `git log --oneline master..HEAD --grep="TASK-424"` → 5 commits, but only 3 are TASK-424's own work
- `git diff master...HEAD --stat` → 46 files changed, but TASK-424's commits touch only 2 files

**Disposition:** No defect in TASK-424. The branch scope drift is a merge logistics concern, not a quality concern. Cherry-pick TASK-424's commits to avoid bringing in other work.

### Finding 5: Design Not Yet Consumed — EXPECTED

The design document is not consumed by any production code. This is expected: the task says "DESIGN NOW, BUILD AFTER THE ONE-ACCOUNT SLICE." The design is meant to inform future work, not to be built immediately.

**Evidence:**
- Task instruction: "DESIGN NOW, BUILD AFTER THE ONE-ACCOUNT SLICE"
- Design document §6: "It does not build it. This is a design document."
- Result block: "RECOMMENDED CLAUDE ACTION: Review the design document... Once the design is approved, the build can proceed."

**Disposition:** Not a defect. The design is the deliverable, and it exists. Consumption is a future task.

---

## Risks

1. **Design may become stale.** The design was written on 2026-09-27. If the one-account slice takes months, the design may need revision. Mitigation: The design is version-controlled and can be updated.

2. **Open questions unresolved.** The design lists 4 open questions for Claude (§7): LEASE_TTL value, heartbeat mechanism, completed task retention, reconciliation authority. These need answers before the build. Mitigation: The result block explicitly calls these out.

3. **Interim fix may diverge from design.** Commit `e111d611` implements an interim fix to `claim_task.py` that differs from the design's lease-based registry. If the interim fix accumulates complexity, the permanent design may need to account for it. Mitigation: The interim fix is explicitly labeled as interim, and TASK-424's design is the permanent solution.

---

## Recommendation

**MERGE (cherry-pick)**

Cherry-pick commits `55fb4664` (design document) and `b063f188` (result block) from `origin/qwen-worker-12-r9-sync` at SHA `3da4a246ee2536760d04dfc4d1d94b649160c2fa`.

The design document is a legitimate deliverable for a design-only task. It answers the questions asked, provides defended choices, and has a falsifiable test plan. The result block is accurate. The task prohibitions were respected. The branch carries other work, but TASK-424's contribution is clean and isolated.

After merging, Claude should:
1. Review the 4 open questions in §7 and answer them
2. Decide when the one-account slice is complete and the build can proceed
3. Update the design if the interim fix (`e111d611`) has accumulated complexity

---

## Verification Commands

```bash
# Check out the exact ref reviewed
git worktree add ../resonate-glm-530 3da4a246ee2536760d04dfc4d1d94b649160c2fa --detach

# Verify the design document exists
cd ../resonate-glm-530
git log --diff-filter=A --all -- docs/TASK-STATE-REGISTRY-DESIGN.md
wc -l docs/TASK-STATE-REGISTRY-DESIGN.md

# Verify TASK-424's commits
git show --stat fe832a8a  # Take TASK-424
git show --stat 55fb4664  # Design document
git show --stat b063f188  # Result block

# Verify no forbidden changes in TASK-424's commits
git diff fe832a8a^..b063f188 -- scripts/claim_task.py scripts/pool.sh scripts/pool_watchdog.sh

# Verify branch scope drift
git log --oneline master..HEAD | wc -l
git diff master...HEAD --stat
```

---

## Appendix: TASK-424 Result Block

```
STATUS: DONE
COMMIT SHA: 55fb4664
TESTS: N/A — design-only task, no code changes
FILES CHANGED:
- docs/TASK-STATE-REGISTRY-DESIGN.md (new, 389 lines)

FINDINGS:
The design answers all four decisions with defended choices:
1. Where the registry lives: docs/state/TASK-LEASES.json
2. Atomicity across worktrees: Optimistic concurrency with generation counter
3. Reconciliation with branches: Registry wins; disagreements reported
4. Migration: Seeds 116 unintegrated results without losing them

RISKS:
- Generation counter contention under heavy load
- Heartbeat reliability (side effect of commit vs. explicit command)
- Migration correctness (TERMINAL_BRANCH_STAGES priority)

RECOMMENDED CLAUDE ACTION:
Review the design document and answer the four open questions in §7.
```

---

**End of verdict.**
