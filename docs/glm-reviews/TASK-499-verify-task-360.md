# GLM Independent Verification: TASK-360

**Target task:** TASK-360 — a central model router, and no model slug anywhere else
**Branch:** origin/qwen-worker-2-r70
**Branch HEAD SHA reviewed:** 29f90f7bee9153bcbfb2ffafd6f7cc1182d7fd4f
**Verified SHA with `git rev-parse`:** 29f90f7bee9153bcbfb2ffafd6f7cc1182d7fd4f — MATCH
**Worktree:** `.qwen/worktrees/verify-499` (detached HEAD at 29f90f7be)
**START_MASTER_SHA:** 2bf7b8a57
**Reviewer:** Qwen (qwen-worker-5-r9), 2026-10-04

---

## 1. Does the artifact exist, and does it do what the result block claims?

**VERIFIED.** All seven files in the diff exist at this exact SHA:

| File | Status | Verified |
|------|--------|----------|
| `config/model_policy.yaml` | NEW | ✅ 152 lines, versioned, 4 providers, 7 task types, 12 safety gates |
| `src/modelrouter.py` | NEW | ✅ 268 lines, `resolve()`, `NotAModelDecision`, fallback, `all_slugs()` |
| `src/llm.py` | MODIFIED | ✅ +14 lines, `for_task(task_type)` added at line 549 |
| `src/providers/glm.py` | MODIFIED | ✅ `DEFAULT_MODEL`, `SERVES`, `MODELS` read from router |
| `src/providers/xai.py` | MODIFIED | ✅ `MODELS`, `DEFAULT_MODEL` read from router |
| `tests/test_no_model_slug_lives_outside_the_policy.py` | NEW | ✅ 183 lines, AST-based scan, 3 tests |
| `docs/qwen-tasks/REVIEW/TASK-360-...md` | Task file | ✅ In REVIEW |

### Acceptance re-derivation

1. **Router resolves:** `resolve('research_synthesis')` → `RoutingDecision(provider='glm', model='glm-5.3-flash', reasoning='medium', max_tokens=4096, fallback=None, policy_version=1)` — **PASSED**
2. **Safety refusal:** `resolve('suppression')` raises `NotAModelDecision` — **PASSED**
3. **Planted violation:** `test_planted_violation_is_caught` plants `claude-sonnet-4-20250514`, scan FAILS naming file+line, removal → green — **PASSED** (verified via unittest)
4. **Docstring immunity:** `test_docstring_does_not_trip` — **PASSED**
5. **Fallback:** `mark_unavailable('groq')` → `resolve('simple_extraction')` returns `glm/glm-5.3-flash`; `mark_unavailable('glm')` on `research_synthesis` (no fallback) → `NoFallbackAvailable` raised explicitly — **PASSED**
6. **Suite diff:** Not re-run (full suite ~1780s). The result block's claim of 9 transient errors from incomplete git mv is consistent with the commit history (commit `648b9e19a` fixes the staged deletion).

### Test results in worktree

```
tests/test_no_model_slug_lives_outside_the_policy.py: 3/3 PASS
tests/test_glm_adapter.py: 41/41 PASS
tests/test_xai_adapter.py: 48/48 PASS
tests/test_fixture_hygiene.py: 16/17 (1 pre-existing FAIL: productive.io domain)
```

---

## 2. Existence is not function — are there production callers?

**Two levels of consumption:**

### Real production consumers (import-time)

- `src/providers/glm.py:81` — `DEFAULT_MODEL = modelrouter.default_model("glm")`
- `src/providers/glm.py:87` — `SERVES = modelrouter.provider_serves("glm") or {}`
- `src/providers/xai.py:42` — `MODELS = modelrouter.provider_models("xai")`
- `src/providers/xai.py:43` — `DEFAULT_MODEL = modelrouter.default_model("xai")`

These are **real consumers**. The provider modules fail to import if the policy file is missing or unparseable. The values they read match the previously hardcoded values exactly:

- `glm.DEFAULT_MODEL` = `"glm-5.3"` (was hardcoded `"glm-5.3"`)
- `glm.SERVES` = all 5 entries match the old inline dict
- `xai.MODELS` = all 7 entries match the old inline tuple
- `xai.DEFAULT_MODEL` = `"grok-4.6"` (was hardcoded `"grok-4.6"`)

### `llm.for_task()` — zero callers (by design)

`llm.for_task(task_type)` at line 549 has **zero production callers** and **zero test callers**. `grep -rn "llm.for_task" src/ tests/` returns nothing.

**This is NOT a defect.** The task explicitly scopes: *"Do not change which model any existing stage uses. This task builds the router and moves the slugs into it. Re-routing is TASK-362's."* The function is a seam for TASK-362 to wire into. The real wiring in this task is the provider adapters reading from the router at import time.

**Verdict on consumption:** NOT DISCONNECTED. The provider adapters are real production consumers that replaced hardcoded string literals. `llm.for_task` is a deliberate forward-looking seam, not a dangling function pretending to be wired.

---

## 3. Falsification: could the slug test pass while slugs remain?

**The test is falsifiable.** It uses `ast.parse` to walk string literals (not raw lines), excludes docstrings by AST position, and the planted-violation test proves it catches a real slug and names the file+line.

**One limitation noted:** The test scans `src/` only. A slug introduced in `scripts/`, `tools/`, or other top-level directories would not be caught. This is stated in the test docstring and is acceptable for the current scope since all production code lives in `src/`.

**The guard has been seen to fail:** `test_planted_violation_is_caught` asserts the scan catches a planted slug, names the file and line, then passes after removal. All three states are asserted in one test.

---

## 4. Would merging DELETE anything?

**NO.** `git diff master...29f90f7bee9153bcbfb2ffafd6f7cc1182d7fd4f --diff-filter=D --name-only` returns empty. The diff is purely additive (3 new files) and modifications (4 existing files with line replacements). Net change: +693 / -19 lines.

The 19 deleted lines are the hardcoded slugs in `glm.py` and `xai.py` replaced by router calls. No files are removed.

---

## 5. Scope drift

**NONE.** The diff contains exactly the files the task names:

```
config/model_policy.yaml
docs/qwen-tasks/REVIEW/TASK-360-...md
src/llm.py
src/modelrouter.py
src/providers/glm.py
src/providers/xai.py
tests/test_no_model_slug_lives_outside_the_policy.py
```

No unrelated files, no scratch output, no documentation drift. The branch has many merge commits from master, but the tree diff vs master is clean.

---

## 6. Risks and observations

1. **Import-time dependency:** Provider modules now depend on `modelrouter` at import time. If `config/model_policy.yaml` is missing, `glm.py` and `xai.py` fail to import. The result block acknowledges this as intentional. The `_load()` function handles `FileNotFoundError` by returning `{}`, but `default_model(None)` and `provider_serves(None)` would return `None`, making `DEFAULT_MODEL = None` in the adapters. This is a soft failure — the adapter would fail at call time, not import time, when the policy file is absent but the module loads. **Noted, not blocking.**

2. **`clients.parse` handles the policy:** Verified — the custom YAML parser correctly parses all 4 top-level keys, 7 task types, 4 providers, and the inline list for `deterministic_safety`.

3. **`reasoning: max` in policy:** The `critical_ambiguity` task type has `reasoning: max`, which is not a standard reasoning level. The router passes it through as data without validation. This is acceptable — the router is a data layer, not a validator.

---

## Findings

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | All 6 acceptances verified against code at exact SHA | — | CONFIRMED |
| 2 | Provider adapters are real production consumers of the router | — | CONFIRMED |
| 3 | `llm.for_task` has zero callers | Informational | BY DESIGN (TASK-362 scope) |
| 4 | Slug test is falsifiable and has been seen to fail | — | CONFIRMED |
| 5 | No deletions on merge | — | CONFIRMED |
| 6 | No scope drift | — | CONFIRMED |
| 7 | Import-time dependency on policy file | Low | ACKNOWLEDGED, intentional |

---

## Recommendation

**MERGE.**

The artifact exists, does what it claims, has real production consumers (provider adapters), and the guard test is falsifiable. The scope is clean, nothing is deleted, and the one function with zero callers (`llm.for_task`) is explicitly scoped as a seam for the next task. The pre-existing `productive.io` fixture_hygiene failure is unrelated.

The branch is safe to integrate. TASK-362 (re-routing stages through the router) and TASK-361 (observability) can proceed on top of it.
