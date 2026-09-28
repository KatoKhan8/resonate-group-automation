# GLM independent verification: TASK-302

**Target task:** TASK-302 — re-render 504 from productive.yaml and build the operator's review file
**Target branch:** `origin/qwen-worker-r9`
**Target HEAD SHA (named in task):** `e456c6128774cfd00960ac50d7b39c6e99a3f8cd`
**Current branch HEAD (at review time):** `ff754e5de41a636de7e14e02f35de551b8eab6c0`
**Branch has moved:** YES — the branch advanced by 100+ commits after the target SHA. Per task instructions, this verdict reviews `e456c6128774cfd00960ac50d7b39c6e99a3f8cd` exactly.
**Review worktree:** `.qwen/worktrees/glm-455` (detached at `e456c612`)
**Date:** 2026-09-28
**Reviewer:** GLM (independent, Qwen worktree)

---

## Verdict: REWORK

**The script exists, imports cleanly, and uses the correct rendering chain. But the task is half-complete (Stage 1 of 3), the output files are not in git (gitignored `work/review/`), the claimed numbers are unreproducible from the branch, and the script has zero production callers. The artifact is a one-shot rendering tool with no consumer — correct for its stated purpose, but the review file the operator asked for does not exist on any ref.**

---

## Finding 1: Artifact exists but output files do not

**Claim:** "work/review/504-rerender-2026-09-27.html — NEW: review file" and ".json — NEW: summary JSON"

**Evidence:**
- `scripts/task302_render_504.py` EXISTS at commit `4b404b5a` (579 lines, imports cleanly)
- `git ls-tree -r e456c612 | findstr "work/review"` returns NOTHING
- The `work/` directory is gitignored — the HTML and JSON outputs were never committed

**Conclusion:** The rendering script exists. The review file it produces does NOT exist on any ref. The result block claims artifacts that are invisible to version control.

---

## Finding 2: Zero production callers — DISCONNECTED

**Evidence:**
- `grep -rn "task302" src/` returns zero matches
- `grep -rn "task302_render_504" src/` returns zero matches
- The script is in `scripts/`, not `src/`, and no module imports it
- The task itself says "No unit tests added — the script is a one-shot rendering tool, not a library"

**Conclusion:** The script is a dead end. It computes correctly but nothing downstream reads it. Per the standing rule: "Zero production callers means DISCONNECTED, which is a rework and not a merge."

**Mitigating context:** The task is explicitly a one-shot rendering tool for operator review, not a pipeline component. The "disconnected" rule is designed for library modules that should be consumed but aren't. A rendering script that produces a human-readable file is architecturally different — its "consumer" is the operator reading the output. But the output file is not in git (Finding 1), so even that indirect consumption cannot be verified.

---

## Finding 3: Claims are unreproducible from the branch

**Claim:** "87 leads rendered", "44 HELD", "100% LinkedIn coverage", "21 clean, 2 warned, 64 refused"

**Evidence:**
- The script requires `work/queue.jsonl` to run (via `store.load()`)
- `work/queue.jsonl` is gitignored and does not exist in the worktree
- The script cannot be executed from the branch alone
- The numbers in the result block came from a run against local state that is not recoverable

**Conclusion:** The result block's numbers are ASSERTED, not VERIFIED from the branch. A future session checking out this SHA cannot reproduce them. This is the exact failure mode the protocol warns against: "a confident wrong verdict is the expensive outcome."

---

## Finding 4: Task is half-complete by design

**Evidence from task file:**
- Stage 1 (render locally): COMPLETE
- Stage 1b (LinkedIn coverage): COMPLETE
- Stage 2 (provider write): "CLAUDE'S, NOT YOURS. Stop and hand back."
- Stage 3 (review file from provider readback): BLOCKED on Stage 2

**Conclusion:** The task was correctly scoped and the boundary was correctly identified. Stage 2 requires provider writes, which are Claude's scope. The result block honestly states what is owed and what is blocked. This is NOT a defect — it is the correct behavior of a task that hit its permission boundary.

---

## Finding 5: Code quality — the rendering chain is correct

**Evidence:**
- Uses `cadence.TEMPLATES` for em3/em4/em5 (persona-specific: `rung3_`, `angle_shift_`, `close_`)
- Uses `cadence.template_vars(rec, contact, config)` which reads `productive.yaml`'s `product.name`, `product.capabilities`, `capability_by_persona`, `angle_labels`, `sender.name`
- Uses `cadence.render(template, tv)` which does `text.format(**values)` on each template field
- Carries `template_id` on every rendered step (the provenance gate the task requires)
- Sender name from `config.sender.name` (Ivan), not the operator's name
- Pack fact gate checks for verb indicators and nav indicators — reasonable heuristic
- Copylint integration via `copylint.check_batch` is correct
- `reviewapproval.file_hash` is called on the output

**Conclusion:** The script uses the proper rendering path. It does NOT invent its own copy (which was the incident this task was responding to). The rendering chain is: `productive.yaml` → `clients.load` → `cadence.template_vars` → `cadence.render` → output. This is the correct path.

---

## Finding 6: Scope drift — minimal for TASK-302, massive for the branch

**TASK-302's own commits (3):**
- `a071f5b7` — task file move TODO → RUNNING (0 lines)
- `4b404b5a` — rendering script (579 lines, 1 file)
- `3912c8f7` — result block (93 lines, 1 file)

**Total TASK-302 footprint:** 1 new file (`scripts/task302_render_504.py`), 1 task file movement.

**Branch total:** 75 files changed, 17,680 insertions, 3,150 deletions across 100+ commits from TASK-264, TASK-271, TASK-273, TASK-294, TASK-298, TASK-325, TASK-326, TASK-364, TASK-389, TASK-394, TASK-400, TASK-418, TASK-420, TASK-426, TASK-427, TASK-429, TASK-430, TASK-436, TASK-449, and integration passes.

**Cherry-pick scope:** TASK-302's own work is cleanly isolable — the single script file and the task file. No src/ changes, no test changes, no config changes. A cherry-pick of `4b404b5a` would be clean.

---

## Finding 7: Deletion check — no deletions

**Evidence:**
- `git diff --diff-filter=D origin/master...e456c612 -- src/ tests/` returns nothing
- The branch deletes only task files in `docs/qwen-tasks/TODO/` (lifecycle movements: TODO → REVIEW/DONE)
- No source, test, or config files are deleted

**Conclusion:** Merging would not delete anything.

---

## Finding 8: Test falsifiability — NOT APPLICABLE

**Evidence:** No tests were added. The task explicitly says "No unit tests added — the script is a one-shot rendering tool."

**Conclusion:** There is nothing to falsify. The script's correctness rests on code review of the rendering chain (Finding 5), not on test assertions. This is acceptable for a one-shot tool but means the claimed output numbers (Finding 3) have no automated verification either.

---

## Disposition summary

| Finding | Status | Severity |
|---------|--------|----------|
| 1. Output files not in git | CONFIRMED | HIGH — the operator's deliverable is invisible |
| 2. Zero production callers | CONFIRMED | MEDIUM — expected for a one-shot tool, but no consumer verified |
| 3. Claims unreproducible | CONFIRMED | HIGH — numbers asserted, not verified from branch |
| 4. Task half-complete | CONFIRMED | LOW — correct boundary identification, not a defect |
| 5. Rendering chain correct | CONFIRMED | POSITIVE — uses the proper path |
| 6. Scope drift minimal | CONFIRMED | POSITIVE — cleanly cherry-pickable |
| 7. No deletions | CONFIRMED | POSITIVE — safe to merge |
| 8. No tests | CONFIRMED | LOW — acceptable for one-shot, but limits verification |

---

## Recommendation: REWORK

**Reason:** The script is correct code that uses the right rendering chain, but the task's deliverable (the review file) does not exist on any ref, the claimed numbers are unreproducible, and the script has no consumer. The task is honestly half-complete with correct boundary identification — Stage 2 requires Claude's provider write scope.

**What rework means here:**
1. The script itself is merge-ready as a tool. It can be cherry-picked (`4b404b5a`) without risk.
2. The review file cannot be produced without Stage 2 (provider readback), which is Claude's scope.
3. The result block's numbers should be marked "measured on 2026-09-27, not reproducible from branch" rather than presented as verifiable facts.
4. If the operator still needs the 504 review file, Stage 2 and Stage 3 must be completed by Claude from Claude's worktree with access to the live queue and provider.

**What is NOT a defect:**
- The task correctly identified its own permission boundary
- The rendering chain is the proper one (not the incident's `work/gencopy.py` path)
- The pack fact gate and copylint integration are sound
- The branch carries no deletions and TASK-302's footprint is cleanly isolable
