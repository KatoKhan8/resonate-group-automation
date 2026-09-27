PRIORITY: P3
SIZE: S
DEPENDS:

# TASK-407 — GLM first-pass verification: TASK-399 (docs hygiene, report only)

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly.

## Target

TASK-399, in REVIEW on `qwen-worker-9-r9` — a report-only task (no file
edits; Claude applies any correction). Verify its list of FALSE claims is
actually false, each one, before Claude spends time acting on any of them.

## What GLM's pass must produce

1. For each claim TASK-399 reports as FALSE: independently verify against
   current master or a read-only provider check.
2. Flag any claim TASK-399 marked FALSE that is actually still true (a
   false positive would waste Claude's correction pass).
3. Confirm TASK-399 did not edit any of its scoped files (report-only, per
   its own rule).

## Result

Use the protocol's own format and eight dispositions.
