PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-404 — GLM first-pass verification: TASK-397 (HeyReach seat-cap check)

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly.

## Target

TASK-397, in REVIEW on `qwen-worker-4-r9`. This task involved a READ-ONLY
provider check — verify no write occurred (grep the branch's diff for any
POST/PATCH/PUT/DELETE to HeyReach) before trusting any other claim.

## What GLM's pass must produce

1. **Confirm READ-ONLY was honored** - no provider write in this branch's
   diff. This is the first thing to check, not the last.
2. Reproduce the seat-cap read's own acceptance criteria against the task's
   own spec file.
3. Any new finding, file:line.

## Result

Use the protocol's own format and eight dispositions. SAFE TO MERGE or
BLOCKED, and why.
