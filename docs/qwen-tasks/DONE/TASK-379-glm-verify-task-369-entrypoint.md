PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-379 — GLM first-pass verification: TASK-369, the production entrypoint

**Operator instruction, 2026-09-26 evening.** Dispatch GLM as an independent
first-pass verifier of work Claude already merged tonight, per
`docs/GLM-REVIEW-PROTOCOL.md` — the standing contract for review triggers,
checkpoints, the isolated-worktree rule, falsification over confirmation, and
the eight dispositions every finding must carry. **Read that file yourself and
follow it exactly; this task file only names the target, not the procedure.**

## Target

TASK-369, "one versioned production entrypoint for generation" — merged to
`origin/master` at `6ca3b94c`, verified by Claude before merge (byte-identical
file check against `qwen-worker-r78`, all three new test files present and
green). Files: `src/generate_campaign.py`, `src/sequenceplan.py`,
`src/skills/*.py`, `tests/test_a_skill_is_loaded_by_the_stage_that_uses_it.py`,
`tests/test_changing_an_approved_fact_changes_the_output.py`,
`tests/test_the_entrypoint_is_the_only_generation_path.py`.

**Known open finding, not yours to re-discover — verify it independently
instead:** Claude found tonight (docs/qwen-tasks/TODO/TASK-375) that
`generate_campaign.generate()` itself has zero production callers anywhere in
`src/` or `scripts/`, and that the five `src/skills/*` modules are never
called by `_process_contact` (which calls the raw `copyprompts`/`copystages`
constants directly instead). **Falsify this, don't confirm it**: grep it
yourself, on current master, and either confirm the finding stands or show
Claude's grep was wrong.

## What GLM's pass must produce

Per the protocol's own disposition set. At minimum, for each of TASK-369's
own claims (mutation-tested provenance, the entrypoint's single-source-of-
truth claim, the skill-loading test):

1. Reproduce the mutation test yourself (change an approved fact, confirm the
   output changes) — do not accept "the test is green" as the finding.
2. State plainly whether the "zero production callers" finding above is
   CONFIRMED CURRENT or refuted, with the exact grep you ran.
3. Any NEW finding GLM makes on this code that Claude's merge review did not
   catch, with file:line.

## Result

Follow the protocol's own result format. Do not create a new disposition
vocabulary — use the eight the protocol already defines.

## CLAUDE CLOSE-OUT NOTE, 2026-09-26/27

Full report: see docs/glm-reviews/ (this task's own artifact). Disposition
recorded, task closed. See the disposition tables (TRIAGE-CANARY, or this
task's own artifact) for detail.
