PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-408 — GLM first-pass verification: TASK-319

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly.

## Target

TASK-319, in REVIEW on `qwen-worker-11-r9`. Read the task's own file for its
acceptance criteria — verify against the task's own spec, not a summary.

## What GLM's pass must produce

1. Reproduce the task's own acceptance checks yourself.
2. Confirm any claimed test is falsifiable (fails when the fix is reverted).
3. Any new finding, file:line.

## Result

Use the protocol's own format and eight dispositions. SAFE TO MERGE or
BLOCKED, and why.
