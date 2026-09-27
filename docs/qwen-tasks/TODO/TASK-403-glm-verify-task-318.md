PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-403 — GLM first-pass verification: TASK-318

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly (isolated
worktree, read-only, falsification over confirmation, eight dispositions).

## Target

TASK-318, in REVIEW on `qwen-worker-2-r9`. Read the task's own file for its
acceptance criteria (`docs/qwen-tasks/DONE/` or the REVIEW copy) — this
task file does not restate them; verify against the task's own spec, not
against a summary.

## What GLM's pass must produce

1. Reproduce the task's own acceptance checks yourself, not by reading the
   worker's report.
2. State whether any test asserting the fix is falsifiable (would it fail if
   the fix were reverted) — reproduce that guard-failure if the task claims
   one, or flag its absence if it does not.
3. Any new finding, file:line.

## Result

Use the protocol's own format and eight dispositions. State plainly: SAFE
TO MERGE or BLOCKED, and why.
