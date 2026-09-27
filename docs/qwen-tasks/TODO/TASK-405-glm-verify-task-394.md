PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-405 — GLM first-pass verification: TASK-394 (contact-key guard)

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly.

## Target

TASK-394, in REVIEW on `qwen-worker-6-r9`. Note: TASK-389 covers the same
scope (contact-key guard clean-up) — check whether TASK-389 or TASK-394
actually did the work, and whether they duplicate or complement each other.
Do not verify both as if independent if one is a no-op citing the other.

## What GLM's pass must produce

1. State which of TASK-389/394 has the real content, or whether both do
   (and whether they agree).
2. Reproduce the acceptance criteria against the task's own spec.
3. Any new finding, file:line.

## Result

Use the protocol's own format and eight dispositions. SAFE TO MERGE or
BLOCKED, and why.
