PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-401 — GLM first-pass verification: TASK-364 (SequencePlan consumed by both provider factories)

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with GLM first-pass verdicts. Claude cherry-picks only what GLM confirms
passes. Do this one first, alongside TASK-402 (391).**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself, follow it exactly (isolated
worktree, read-only, falsification over confirmation, eight dispositions).

## Target

TASK-364, "one canonical SequencePlan" — in REVIEW on `qwen-worker-worker-r9`
(the primary worktree branch). Read its own acceptance criteria from
`docs/qwen-tasks/DONE/` or the REVIEW copy first.

## What GLM's pass must produce

1. Reproduce whatever the task claims: does `bisonfactory.py` and
   `heyreachfactory.py` now build their provider payloads FROM a SequencePlan
   object (`sequenceplan.derive_*`), or do they still build their own
   payload independently and the plan is decorative? This is the exact
   "existence is not function" question - prove consumption, not presence.
2. If a prior WIP existed on this branch (commit `59f8647f`,
   `derive_xlsx_data`/`qa_validate`), confirm whether the final result
   actually uses those functions or superseded them.
3. Run whatever tests the task claims; reproduce at least one with a
   deliberately broken plan field to confirm the factory's output changes.
4. Any new finding, file:line.

## Result

Use the protocol's own format and eight dispositions. State plainly: SAFE
TO MERGE or BLOCKED, and why.
