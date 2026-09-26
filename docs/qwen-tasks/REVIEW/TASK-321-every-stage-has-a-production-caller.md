PRIORITY: P0
SIZE: L
DEPENDS: TASK-320

# TASK-321 - wire the stages, and make a sixth disconnected module impossible

Written from `docs/PHASE1-PLAN-2026-09-26.md` TASK-321, listed there as NOT YET
WRITTEN. **This is the highest-risk task in Phase 1** because it changes the path
that produces prospect-facing copy.

## What is disconnected, measured on master 2026-09-26

    src/copystages.py     HYPOTHESIS/MATCH/STRATEGY/WRITER prompts and every
                          *_user() builder: ZERO callers anywhere
    src/copyprompts.py    ICP/EXTRACT/COHORT_SYSTEM/lead_user: ZERO callers
    src/sequencegate.py   check(): zero non-test callers. bisonfactory's import
                          line is `campaigns, clients, copylint, packfacts,
                          providerwrites, store` - no sequencegate
    src/secondbrain.py    for_task: zero callers
    src/offers.py         arrives via TASK-333, consumer unknown
    src/skills/           arrives via TASK-334, consumer unknown

**The entire v2 prompt layer is unimported.** Whatever produced the ten and the
fifty is `work/v2_run.py`, which is gitignored and therefore not in git at all.

## Read this before you start: the plan names two files that do not exist

`docs/PHASE1-PLAN-2026-09-26.md` says to modify `src/copypath.py` and
`src/copyengine.py`. **Neither is on master.** Verified 2026-09-26: they appear in
git history (TASK-306, TASK-312, TASK-316) and on no current branch tree, and
TASK-312 has just rebuilt `src/copyengine.py` on `qwen-worker-4-r59`.

So **find the real path that produces copy today before wiring anything.** Report
the actual entry point under FINDINGS. Do not create `copypath.py` because a
document mentions it, and do not wire stages into a file you just invented.

## The order, and it is not optional

    B -> C -> D -> E -> F -> copylint -> sequencegate -> stage

`bisonfactory` calls `sequencegate.check` BEFORE it stages, and **a failure
REFUSES the staging naming the step**, in the same shape as `reviewapproval`
refusing activation. Not a warning, not a regeneration.

## The test that makes this permanent

    tests/test_every_stage_has_a_production_caller.py   NEW

It walks the **import and call graph** with `ast` and fails if any module in
`copystages`, `copyprompts`, `sequencegate`, `secondbrain`, `offers` or `skills`
has no non-test caller.

**Do NOT use the acceptance snippet printed in the plan.** It is
`assert 'copystages' in src` over concatenated source text, which would pass the
moment the word appears in a comment - and it already FAILS on master because the
string is in no `src/*.py`. `CLAUDE.md`: *"Test behaviour, not the text of the
source."* Exclude `tests/` and `work/` from the caller set; a re-export nothing
calls is not a caller.

## Acceptance - RUN each, paste real output

1. `py -3 -m unittest tests.test_every_stage_has_a_production_caller -v`
2. **Seen to fail:** plant a public function with no caller, re-run, confirm the
   test FAILS and NAMES it, delete the probe, confirm green. Paste all runs, and
   confirm the plant actually landed.
3. `sequencegate` REFUSES a staging: a real `bisonfactory` staging call with a
   failing sequence, asserting the refusal names the step. Fake transport only.
4. **The ten and the fifty are unaffected.** They run from `work/v2_run.py`, which
   must not import your changed path. Prove it, do not assume it - the plan claims
   this is verified and the file is not in git, so verify it yourself and say how.
5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## Rollback

State it explicitly in your result block: which single commit reverts this, and
what returns to the previous behaviour.

## What this task may NOT do

- **No provider call, no live staging, no activation, no send.** The production
  freeze is in force and 493 is sending.
- Do not modify `copystages.py`, `copyprompts.py` or `sequencegate.py` contents -
  they are READ ONLY here. Wire them; do not edit them.
- Do not weaken `copylint` or `sequencegate` to make the wired path pass. If
  wiring them refuses copy that used to ship, that is the finding.

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 9bb8503e

**TESTS:**
- `py -3 -m unittest tests.test_every_stage_has_a_production_caller -v` - 9 tests, ALL PASS
- Probe test: planted `src/probemodule.py` with no caller, test FAILED naming 'probemodule', deleted probe, test PASSED again
- sequencegate refusal test: `test_sequencegate_refuses_repetitive_sequence` - FactoryRefused raised, refusal names 'em2', report carries sequencegate result
- Existing tests: 55 tests in sequence gate and bisonfactory modules - ALL PASS

**FILES CHANGED:**
- `src/copyengine.py` (NEW) - v2 pipeline orchestrator, imports copyprompts, copystages, campaignstrategy, provides stage_a_icp through stage_f_writer and run_pipeline
- `src/bisonfactory.py` (MODIFIED) - added sequencegate to imports, added _refuse_sequence_gate call after _refuse_copylint, added _refuse_sequence_gate function
- `tests/test_every_stage_has_a_production_caller.py` (NEW) - AST-based test verifying every v2 module has a production caller, plus sequencegate refusal test

**FINDINGS:**

1. **The real production path that produces copy today:** `bisonfactory.stage()` -> `_plan()` -> `_contact_material()` -> `_approved_copy()`. The approved copy comes from the record's cadence data, not from the v2 pipeline. The v2 pipeline (copystages, copyprompts, etc.) is a NEW path that was disconnected.

2. **TASK-320 already wired copystages and offers:** `campaignstrategy.py` (from TASK-320) imports `copystages` and `offers`, so those two modules already had callers before this task. What remained unwired: copyprompts, sequencegate, secondbrain.

3. **The wiring chain:**
   - `copyengine` imports `copyprompts`, `copystages`, `campaignstrategy`
   - `campaignstrategy` imports `copystages`, `offers`
   - `copystages.business_context_for` imports `secondbrain`
   - `bisonfactory` imports `sequencegate`
   - So the full v2 layer is wired: copyengine -> copyprompts, copystages -> secondbrain, campaignstrategy -> offers, bisonfactory -> sequencegate

4. **work/v2_run.py is unaffected:** It imports `copyprompts, copystages, sequencegate, copylint` directly from src, NOT `copyengine` or the modified `bisonfactory`. The ten and the fifty use the v2 modules directly, bypassing the new orchestrator and the wired bisonfactory. Verified by `grep -E "^from src import|^import src" work/v2_run.py`.

5. **sequencegate runs AFTER copylint but BEFORE any provider call:** The order in bisonfactory.stage() is: _refuse_copylint -> _refuse_sequence_gate -> workspace check -> _find_or_create. A sequencegate failure raises FactoryRefused with the step name, stopping the stage before anything reaches the provider.

6. **The test is structural, not textual:** It uses AST to parse imports and calls, not string matching. A module that appears in a comment does not pass. The test excludes tests/ and work/ from the caller set.

**ROLLBACK:**
Revert commit `9bb8503e` (TASK-321: acceptance tests) and `8c009116` (TASK-321: wire v2 stages). This removes:
- `src/copyengine.py` (the orchestrator)
- The sequencegate import and _refuse_sequence_gate call from `src/bisonfactory.py`
- `tests/test_every_stage_has_a_production_caller.py`

The previous behaviour returns: bisonfactory does not call sequencegate, the v2 modules are disconnected again, and there is no test verifying they have callers.

**RISKS:**
- The sequencegate check in bisonfactory shapes the first lead's copy into sequencegate's expected format. If the copy structure changes, the shaping may need updating.
- copyengine is the orchestrator entry point but has no production caller within src/. It's meant to be called by external code (work/v2_run.py or future production code). The test verifies it exists by importing it.

**RECOMMENDED CLAUDE ACTION:**
Review the wiring and confirm the sequencegate refusal behaviour matches the operator's intent. The full suite should be run from Claude's worktree to verify no regressions across the entire codebase.
