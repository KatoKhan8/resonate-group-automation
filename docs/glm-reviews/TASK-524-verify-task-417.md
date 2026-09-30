# TASK-524 — GLM Independent Verification: TASK-417

**Review target**: TASK-417, campaign cadence drift check  
**Branch reviewed**: `origin/qwen-worker-12-r9-sync`  
**Branch HEAD SHA**: `3da4a246ee2536760d04dfc4d1d94b649160c2fa` (verified with `git rev-parse`)  
**Review date**: 2026-09-29  
**Reviewer**: GLM (independent verification)  
**Worktree**: `.qwen/worktrees/task524-review` (isolated, detached HEAD at exact SHA)

---

## Verdict: **MERGE**

TASK-417 is a finding/investigation task. The artifact is the result block in the task file itself - a read-only audit of campaign cadence drift. No code was changed. The finding is valid, the code analysis is correct, and the artifact exists on the reviewed ref.

---

## Verification Results

### 1. Artifact Existence — ✓ VERIFIED

**Claim**: TASK-417 produced a result block documenting cadence drift.  
**Evidence**: `docs/qwen-tasks/DONE/TASK-417-campaign-cadence-drift-check.md` exists at SHA `3da4a246`.  
**Verification command**:
```bash
git ls-tree -r 3da4a246 | grep TASK-417
```
Output confirms the file is present in `docs/qwen-tasks/DONE/`.

**Finding**: The artifact exists. This is a finding-only task (ARTIFACT KIND: finding), so the deliverable is the result block, not code. This is correct for an audit task.

---

### 2. Code Claims — ✓ VERIFIED

**Claim 1**: `linkedin_sequence()` has two branches with different delay compensation.

**Evidence** (at SHA `3da4a246`):
- `src/providers/heyreach.py:1222` — function definition
- Lines 1258-1266 — cold branch `chain()`:
  ```python
  def chain(copy_block):
      """message_2 -> view -> message_3 -> message_4 -> END."""
      return _node("MESSAGE", 3, "HOUR", _copy("message_2", copy_block),
              nxt=_node("VIEW_PROFILE", d1, "DAY",
                   nxt=_node("MESSAGE", d2, "DAY", _copy("message_3", copy_block),
                        nxt=_node("MESSAGE", d3, "DAY",
                                  _copy("message_4", copy_block),
                                  nxt=end()))))
  ```
- Lines 1292-1299 — already-connected branch:
  ```python
  already = _node("MESSAGE", 3, "HOUR", _copy("connected_1", copy),
             nxt=_node("MESSAGE", d1, "DAY", _copy("connected_2", copy),
                  nxt=_node("VIEW_PROFILE", 2, "DAY",
                       nxt=_node("MESSAGE", max(d2 - 2, 1), "DAY",
                                 _copy("connected_3", copy),
                            nxt=_node("MESSAGE", d3, "DAY",
                                      _copy("connected_4", copy),
                                      nxt=end())))))
  ```

**Verification**: The already-connected branch uses `max(d2 - 2, 1)` to compensate for the 2-day VIEW_PROFILE delay. The cold branch does NOT compensate - it adds d1 (VIEW_PROFILE delay) and d2 (message delay) sequentially.

**Finding**: ✓ CORRECT. The code matches the claim.

---

**Claim 2**: Canonical cadence declares li2→li3 gap as 3 days, li3→li4 as 4 days.

**Evidence** (`src/cadencelibrary.py:327-365`):
```python
PRODUCTIVE_LI_HEAVY_V1 = (
    {"key": "li2", "day": 3, ...},   # First message after connect
    {"key": "li3", "day": 6, ...},   # Second message
    {"key": "li4", "day": 10, ...},  # Third message
    {"key": "li5", "day": 15, ...},  # Fourth message
)
```

**Verification**:
- li2→li3 gap: day 6 - day 3 = 3 days ✓
- li3→li4 gap: day 10 - day 6 = 4 days ✓
- li4→li5 gap: day 15 - day 10 = 5 days ✓

**Finding**: ✓ CORRECT.

---

**Claim 3**: `li_message_delays_from_cadence()` derives (d1, d2, d3) = (3, 4, 5).

**Evidence** (`src/providers/heyreach.py:1198-1220`):
```python
def li_message_delays_from_cadence():
    li_steps = sorted(
        [s for s in cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
         if s.get("channel") == "linkedin"],
        key=lambda s: s["day"])
    days = [s["day"] for s in li_steps]
    return tuple(days[i + 1] - days[i] for i in range(1, len(days) - 1))
```

**Verification**: 
- li_steps (starting from index 1, skipping li1): days = [3, 6, 10, 15]
- d1 = 6 - 3 = 3
- d2 = 10 - 6 = 4
- d3 = 15 - 10 = 5
- Result: (3, 4, 5) ✓

**Finding**: ✓ CORRECT.

---

**Claim 4**: Cold branch delivers (7d, 5d) instead of canonical (3d, 4d), producing +4d and +1d drift.

**Evidence** (cold branch `chain()` at lines 1258-1266):
- message_2 fires at 3h (immediate)
- VIEW_PROFILE fires at d1=3 days after message_2
- message_3 fires at d2=4 days after VIEW_PROFILE
- message_4 fires at d3=5 days after message_3

**Verification**:
- message_2 → message_3 gap: 3d (VIEW_PROFILE) + 4d = 7d total
  - Canonical: 3d (li2→li3)
  - Drift: +4d ✓
- message_3 → message_4 gap: 5d
  - Canonical: 4d (li3→li4)
  - Drift: +1d ✓

**Finding**: ✓ CORRECT. The cold branch does NOT compensate for the VIEW_PROFILE delay, producing additive delays.

---

**Claim 5**: Already-connected branch compensates and delivers (3d, 4d, 5d) with no drift.

**Evidence** (already-connected branch at lines 1292-1299):
- connected_1 at 3h
- connected_2 at d1=3 days
- VIEW_PROFILE at 2 days
- connected_3 at max(d2-2, 1) = max(4-2, 1) = 2 days
- connected_4 at d3=5 days

**Verification**:
- connected_1 → connected_2: 3d (canonical: 3d) → no drift ✓
- connected_2 → connected_3: 2d (VIEW_PROFILE) + 2d (max(d2-2,1)) = 4d (canonical: 4d) → no drift ✓
- connected_3 → connected_4: 5d (canonical: 5d) → no drift ✓

**Finding**: ✓ CORRECT. The compensation works as claimed.

---

### 3. Production Callers — N/A (Finding Task)

**Claim**: This is a finding task with no code changes.  
**Evidence**: The result block states "ARTIFACT KIND: finding (read-only audit, no code changed)" and "FILES CHANGED: this task file only".  
**Verification**: `git diff master...3da4a246 --stat` shows TASK-417 added only the task file to `docs/qwen-tasks/DONE/` and removed it from `docs/qwen-tasks/TODO/`. No source files were modified.

**Finding**: This is correct for a finding task. There are no production callers because no code was changed. The finding itself is the artifact, and it is intended for Claude/operator review and decision, not for automatic consumption.

---

### 4. Test Falsifiability — N/A (Finding Task)

**Claim**: "TESTS: read-only; no tests applicable".  
**Evidence**: This is an audit task that analyzes existing code and provider state. No new code was written, so no tests are applicable.

**Finding**: Correct. A finding task's "test" is the verification of its claims against the code, which this verdict performs.

---

### 5. Deletion Check — ✓ NO DELETIONS

**Command**: `git diff master...3da4a246 --stat`  
**Evidence**: The diff shows TASK-417 added 160 lines (the result block) and removed 13 lines (the TODO version). No other files were deleted.

**Finding**: ✓ CORRECT. The task file was moved from TODO to DONE, which is the correct lifecycle. No unintended deletions.

---

### 6. Scope Drift — ✓ ISOLATED

**Evidence**: The branch `origin/qwen-worker-12-r9-sync` carries work from multiple tasks (TASK-245, TASK-355, TASK-272, TASK-424, etc.), but TASK-417's artifact is isolated to:
- `docs/qwen-tasks/DONE/TASK-417-campaign-cadence-drift-check.md` (added)
- `docs/qwen-tasks/TODO/TASK-417-campaign-cadence-drift-check.md` (removed)

**Finding**: ✓ CORRECT. TASK-417's work is cleanly isolated. The branch carries other tasks' work, but that is expected for a sync branch. TASK-417 can be cherry-picked cleanly if needed.

---

## Summary of Findings

| # | Claim | Status | Evidence |
|---|-------|--------|----------|
| 1 | Artifact exists on reviewed ref | ✓ VERIFIED | File present at SHA `3da4a246` |
| 2 | Cold branch does NOT compensate for VIEW_PROFILE | ✓ VERIFIED | Code at lines 1258-1266 |
| 3 | Already-connected branch DOES compensate | ✓ VERIFIED | Code at lines 1292-1299, uses `max(d2-2, 1)` |
| 4 | Canonical cadence declares (3, 4, 5) gaps | ✓ VERIFIED | `cadencelibrary.py:327-365` |
| 5 | Cold branch delivers (7d, 5d) with +4d, +1d drift | ✓ VERIFIED | Math verified against code |
| 6 | Already-connected branch delivers (3d, 4d, 5d) with no drift | ✓ VERIFIED | Math verified against code |
| 7 | This is a finding task with no code changes | ✓ VERIFIED | Only task file changed |
| 8 | No unintended deletions | ✓ VERIFIED | Only TODO→DONE move |
| 9 | Scope is isolated | ✓ VERIFIED | Task file only |

---

## Critical Finding: Cold-Branch Expansion

The task correctly identified a **structural drift** in `linkedin_sequence()`:

**Cold branch** (prospects who were NOT already LinkedIn connections):
- Delivers messages at day 1, day 8, day 13 from connection request
- Gaps: 7d, 5d
- Canonical intent: 3d, 4d
- **Drift: +4d, +1d**

**Already-connected branch** (prospects who WERE already connections):
- Delivers messages at day 1, day 4, day 8, day 13 from detection
- Gaps: 3d, 4d, 5d
- Canonical intent: 3d, 4d, 5d
- **Drift: none**

**Impact**: The majority of cold outreach prospects (who were not already connections) receive LinkedIn messages at roughly double the intended spacing. This confounds the cadence experiment if the cold branch's actual spacing is wider than declared.

**Root cause**: The cold branch's `chain()` function adds VIEW_PROFILE delay (d1=3d) and message delay (d2=4d) sequentially, producing a 7-day gap. The already-connected branch compensates by subtracting the VIEW_PROFILE delay from the next message delay (`max(d2-2, 1)`).

**Recommendation from TASK-417**: Claude must decide whether this is intentional (update canonical cadence to match reality) or a defect (fix `chain()` to compensate like the already-connected branch).

---

## Disposition

**MERGE**

**Reason**: TASK-417 is a valid finding task. The artifact exists, the code analysis is correct, the math is verified, and the finding is actionable. The cold-branch expansion is a real structural drift that affects the majority of cold outreach prospects. The task correctly identified the root cause and provided a clear recommendation for Claude's decision.

This is a finding-only task with no code changes, so there is no risk of introducing defects. The finding itself is valuable operational intelligence that informs the cadence experiment design.

**Recommended Claude action**:
1. Decide whether the cold-branch expansion is intentional or a defect.
2. If intentional: update `PRODUCTIVE_LI_HEAVY_V1` to declare the actual day positions (day 1, day 8, day 13 for cold branch).
3. If a defect: fix `chain()` to compensate for VIEW_PROFILE delay like the already-connected branch does.
4. For EmailBison cadence verification: run a live read from Claude's worktree with access to `work/queue.jsonl` or a direct EmailBison API call.

---

## Verification Commands

All claims can be independently verified with:

```bash
# Check out the exact SHA
git worktree add .qwen/worktrees/verify-task524 3da4a246ee2536760d04dfc4d1d94b649160c2fa --detach

# Verify artifact exists
git ls-tree -r 3da4a246 | grep TASK-417

# Read the code
cd .qwen/worktrees/verify-task524
cat src/providers/heyreach.py | sed -n '1258,1299p'
cat src/cadencelibrary.py | sed -n '327,365p'

# Verify no code changes
git diff master...3da4a246 -- src/ scripts/
```

---

**Verdict authored**: 2026-09-29  
**Branch HEAD SHA reviewed**: `3da4a246ee2536760d04dfc4d1d94b649160c2fa`  
**Disposition**: MERGE
