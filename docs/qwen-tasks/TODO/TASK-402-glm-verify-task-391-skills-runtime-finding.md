PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-402 — GLM first-pass verification: TASK-391 (skills-at-runtime finding)

**Operator instruction, 2026-09-27 morning.** Do this alongside TASK-401
(364), before the rest. TASK-400 (the critical-path fix) already treats
TASK-391's conclusion as settled and builds on it — this checkpoint exists
to catch it FAST if that trust is misplaced.

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it.

## Target

TASK-391 (`docs/qwen-tasks/REVIEW/` on `qwen-worker-3-r9`) — a FINDING, not a
code change: it concludes the five skills' procedures do not match
`src/generate.py`'s five stages (diagnose/hook/persona_angle/draft/
linkedin_note) in shape, content or job, so wiring them directly would be a
regression.

## What GLM's pass must produce

1. Independently confirm the five-way mismatch table TASK-391 built - read
   each of `generate.py`'s five `render_prompt()` call sites and each
   skill's `.procedure`, and confirm or refute that they genuinely don't
   correspond.
2. Falsify, don't confirm: is there ANY stage where the mismatch claim is
   overstated - i.e., a skill that actually WOULD work if wired in, that
   TASK-391 wrongly dismissed?
3. State plainly whether TASK-400 (the critical-path task, already
   dispatched, built on TASK-391's conclusion) is proceeding on solid
   ground.

## Result

Use the protocol's own format and eight dispositions. This is a
documentation-only task (no code) - the disposition is about whether the
FINDING holds, not whether to merge code.
