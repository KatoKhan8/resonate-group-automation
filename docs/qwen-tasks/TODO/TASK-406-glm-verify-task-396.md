PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-406 — GLM first-pass verification: TASK-396 (training-pair capture, finding only)

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly.

## Target

TASK-396, in REVIEW on `qwen-worker-7-r9` — its own commit says "nothing
captures a training pair — finding only." Verify the NEGATIVE finding
itself: is it actually true that no training-pair capture exists, or did
the worker miss one?

## What GLM's pass must produce

1. Your own grep/trace for anything resembling training-pair capture
   (prompt+output+verdict), independent of the worker's search terms.
2. Confirm or refute "nothing exists" as the honest current state.
3. Any new finding, file:line.

## Result

Use the protocol's own format and eight dispositions. Since this is a
finding-only task, the disposition is about whether the finding holds.
