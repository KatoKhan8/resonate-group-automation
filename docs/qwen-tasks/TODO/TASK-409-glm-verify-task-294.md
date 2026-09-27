PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-409 — GLM first-pass verification: TASK-294 (research-pack QA, identity not presence)

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly.

## Target

TASK-294, in REVIEW on `qwen-worker-12-r9` — per-lead research-pack QA with
identity, not presence (matches the same class of bug the 50-of-71
mismatched-company incident named in `src/packfacts.py`'s own docstring).

## What GLM's pass must produce

1. Confirm the QA check actually verifies IDENTITY (exact company/domain
   match), not just presence of a research pack.
2. Reproduce with a deliberately mismatched pack (right shape, wrong
   company) and confirm it is caught, not passed.
3. Any new finding, file:line.

## Result

Use the protocol's own format and eight dispositions. SAFE TO MERGE or
BLOCKED, and why.
