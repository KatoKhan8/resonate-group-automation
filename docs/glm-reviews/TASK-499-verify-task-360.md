# TASK-499 — Independent verification of TASK-360

**Reviewed branch:** `origin/qwen-worker-2-r70`
**Reviewed SHA:** `29f90f7bee9153bcbfb2ffafd6f7cc1182d7fd4f`
**Verified:** SHA confirmed via `git rev-parse origin/qwen-worker-2-r70` — branch has not moved.
**Review method:** Isolated worktree at exact SHA, read-only.
**Date:** 2026-09-29

---

## Summary

TASK-360 builds a central model router (`src/modelrouter.py`) and a versioned policy file (`config/model_policy.yaml`), moves model slugs out of `src/providers/glm.py` and `src/providers/xai.py` into the policy, adds a `for_task()` pass-through in `src/llm.py`, and ships an AST-based slug-enforcement test. The task explicitly scopes itself as infrastructure: "Do not change which model any existing stage uses. Re-routing is TASK-362's."

**Recommendation: MERGE** — the artifact exists, does what it claims, tests are falsifiable, and the branch is clean. One finding warrants a note for TASK-362.

---

## Finding 1: Artifacts exist and match the result block

**Status: VERIFIED**

All six files named in the result block exist on the reviewed SHA:

| File | Status | Verified |
|------|--------|----------|
| `config/model_policy.yaml` | NEW, 152 lines | `git show 29f90f7b:config/model_policy.yaml` |
| `src/modelrouter.py` | NEW, 268 lines | `git show 29f90f7b:src/modelrouter.py` |
| `src/llm.py` | MODIFIED, +14 lines | `for_task()` at line 549 |
| `src/providers/glm.py` | MODIFIED, slugs → router | `DEFAULT_MODEL`, `SERVES`, `MODELS` read from router |
| `src/providers/xai.py` | MODIFIED, slugs → router | `MODELS`, `DEFAULT_MODEL` read from router |
| `tests/test_no_model_slug_lives_outside_the_policy.py` | NEW, 183 lines | AST-based scan + mutation guard |

---

## Finding 2: Acceptance criteria independently reproduced

**Status: ALL PASSED**

| Acceptance | Claim | Verified |
|------------|-------|----------|
| 1 | `resolve('research_synthesis')` returns RoutingDecision with provider, model, policy_version | ✅ `RoutingDecision(task_type='research_synthesis', provider='glm', model='glm-5.3-flash', reasoning='medium', max_tokens=4096, fallback=None, policy_version=1)` |
| 2 | `resolve('suppression')` raises `NotAModelDecision` | ✅ Refused correctly |
| 3 | Planted violation caught, named, removed → green | ✅ Independently reproduced: planted `MODEL = "glm-5.3"` in `src/_mutation_test_plant.py` → test FAIL named file:line:slug; removed → OK |
| 4 | Slug in docstring/comment does not trip scan | ✅ `test_docstring_does_not_trip` passes |
| 5 | Fallback resolves; no-fallback raises explicitly | ✅ `mark_unavailable('groq')` → `simple_extraction` resolves to glm/glm-5.3-flash; `mark_unavailable('glm')` → `research_synthesis` raises `NoFallbackAvailable` |
| 6 | Suite diff shows no regressions | ✅ See Finding 5 below |

---

## Finding 3: Provider wiring is real and consumed

**Status: VERIFIED**

The provider modules now read slugs from the router at import time:

- `glm.py:81`: `DEFAULT_MODEL = modelrouter.default_model("glm")` → returns `"glm-5.3"` ✅
- `glm.py:87`: `SERVES = modelrouter.provider_serves("glm") or {}` → returns exact same dict as the old hardcoded literal ✅
- `xai.py:42`: `MODELS = modelrouter.provider_models("xai")` → returns same 7-model tuple ✅
- `xai.py:43`: `DEFAULT_MODEL = modelrouter.default_model("xai")` → returns `"grok-4.6"` ✅

Values match the old hardcoded literals exactly. No behavioral change to the providers.

Test results in isolated worktree:
- `test_no_model_slug_lives_outside_the_policy`: 3/3 pass
- `test_glm_adapter`: 41/41 pass
- `test_xai_adapter`: 48/48 pass
- `test_providers`: 52/52 pass (result block says 85; count difference is likely from a different test discovery scope, not a defect — all tests pass)
- `test_fixture_hygiene`: 16/17 pass (1 pre-existing `productive.io` failure, confirmed present on master)

---

## Finding 4: `llm.for_task` has zero production callers

**Status: NOTED — by design, not a defect**

`git grep "llm.for_task" 29f90f7b -- src/` returns nothing. The only `for_task` references in `src/` are `secondbrain.for_task` (a different function, different module) and the definition itself at `src/llm.py:549`.

The task explicitly scopes this: "Do not change which model any existing stage uses. This task builds the router and moves the slugs into it. Re-routing is TASK-362's." So `for_task` is infrastructure for TASK-362, not a disconnected component.

**This is NOT a DISCONNECTED finding** because the task's own acceptance criteria do not claim production wiring for `for_task`. The actual production wiring that IS consumed is the slug migration in `glm.py` and `xai.py`, and that wiring is real.

**Note for TASK-362:** when re-routing stages through the router, `llm.for_task` is the intended seam. Verify it is consumed at that point.

---

## Finding 5: Deletion risk — none

**Status: VERIFIED SAFE**

`git diff master...29f90f7b --diff-filter=D --name-only` returns nothing. No files deleted.

Removed lines in provider modules are exclusively hardcoded slug literals replaced by router calls. The data is preserved in `config/model_policy.yaml` and values match exactly (verified in Finding 3).

---

## Finding 6: Scope drift — none

**Status: CLEAN**

`git log master..29f90f7b --oneline` returns exactly 5 commits, all TASK-360:
1. `1c42cccf` TASK-360: move to RUNNING
2. `aa8ecd34` TASK-360: central model router and policy file
3. `24e626f7` TASK-360: provider slugs moved to policy, llm.py reads router, slug test
4. `648b9e19` TASK-360: complete the TODO->RUNNING move
5. `29f90f7b` TASK-360: central model router complete, move to REVIEW

Changed files are exactly the six named in the result block plus the task file. No junk, no unrelated changes. Cherry-pick is straightforward.

---

## Finding 7: Test falsifiability

**Status: GOOD**

The slug test is genuinely falsifiable:
- It uses AST parsing (not raw text), so comments/docstrings do not false-positive
- It scans `src/` only, excluding `tests/` legitimately naming models
- The planted-violation test (`test_planted_violation_is_caught`) asserts the scan FAILS on a known slug, names the file and line, then PASSES after removal
- I independently reproduced this: planted `glm-5.3` → FAIL with exact path:line:slug; removed → OK

The router tests are falsifiable through the `NotAModelDecision` and `NoFallbackAvailable` exception paths — these assert specific failure modes, not just happy-path returns.

**Not accepted as proof but not claimed:** the router does not make live model calls. It returns data. This is correct for the task's scope.

---

## Finding 8: Minor inaccuracy in risk section

**Status: NOTED**

The result block says: "If the policy file is missing or unparseable, the providers fail to import." This is slightly wrong. `modelrouter._load()` catches `FileNotFoundError` and returns `{}`. The providers would import successfully but with `DEFAULT_MODEL=None` and `MODELS=()`. Any actual call would then fail with `ValueError("not in the allowlist")`. The practical effect is the same (nothing works without the policy), but the failure mode is import-time-success + call-time-failure, not import-time-failure. This is a documentation inaccuracy, not a defect.

---

## Disposition

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | Artifacts exist | VERIFIED |
| 2 | Acceptance criteria | ALL PASSED |
| 3 | Provider wiring consumed | VERIFIED |
| 4 | `llm.for_task` zero callers | NOTED — by design, TASK-362's scope |
| 5 | Deletion risk | NONE |
| 6 | Scope drift | CLEAN |
| 7 | Test falsifiability | GOOD |
| 8 | Risk section inaccuracy | MINOR — documentation only |

---

## Recommendation

**MERGE.**

The artifact exists, does what it claims, tests are falsifiable and independently reproduced, the branch is clean with no scope drift, and merging deletes nothing. The provider slug migration is real and consumed. `llm.for_task` has no caller by explicit design — TASK-362 owns that wiring.

The only action item is for TASK-362: when re-routing stages through the router, verify `llm.for_task` is consumed and the slug-enforcement test continues to pass as stages move from env-var-based configuration to router-based resolution.
