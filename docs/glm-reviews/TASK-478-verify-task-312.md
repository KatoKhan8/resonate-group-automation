# GLM Verdict: TASK-312 — v2 copy engine implementation

## Review metadata

| Field | Value |
|-------|-------|
| Task | TASK-312 |
| Branch | origin/qwen-worker-4-r59 |
| Branch HEAD SHA | 073e81e040a2eee5bd116f5b82113698b894887b |
| Verified SHA | 073e81e040a2eee5bd116f5b82113698b894887b (confirmed via git rev-parse) |
| Review worktree | .qwen/worktrees/review-478 (detached HEAD at SHA) |
| Reviewer | GLM (TASK-478) |
| Date | 2026-10-03 |
| Master HEAD at review | 2bf7b8a57 |

## Files under review

```
A  src/copyengine.py         (759 lines)
A  tests/test_copyengine.py  (620 lines)
R  docs/qwen-tasks/TODO/TASK-312-*.md → DONE/TASK-312-*.md (result block added)
```

No other files changed. No deletions. No scope drift.

---

## Finding 1: Artifact existence — VERIFIED

`src/copyengine.py` and `tests/test_copyengine.py` both exist at the exact SHA
`073e81e040a2eee5bd116f5b82113698b894887b`. Verified with `git ls-tree`. The task
file was moved from TODO to DONE with a populated RESULT block.

The module implements:
- HTTP plumbing (`_post`, `_groq`, `_sonnet`) with backoff on 429 only
- JSON parsing (`_as_json`) handling fences, literal newlines, truncation
- Navigation chrome stripping (`_clean_nav`)
- Role family mapping (`_role_family`)
- Asset availability reporting (`_assets_available`)
- The stage runner (`run_lead`) executing stages A-H in order
- Batch runner (`run_batch`) with batch-level capability check
- Output shape builder (`_build_output`) for EmailBison and HeyReach
- HTML preview renderer (`preview_html`, `_preview_page`)
- Distinct capability counter (`distinct_capabilities`)

**Disposition: VERIFIED.** The artifact exists and matches the result block's
description.

---

## Finding 2: Does it do what the result block claims? — VERIFIED WITH CAVEATS

### Claims verified:

1. **"31 tests in tests/test_copyengine.py, all passing"** — CONFIRMED.
   `python -m unittest tests.test_copyengine -v` → Ran 31 tests in 0.014s. OK.

2. **"Existing suites all pass"** — CONFIRMED.
   `test_copylint`, `test_sequence_for_write`,
   `test_sequence_steps_carries_variant_identity` → Ran 39 tests. OK.

3. **"Two pre-existing test_invariants failures are unrelated"** — CONFIRMED.
   Master has 3 failures in test_invariants; the branch has 2 failures + 1 error.
   None are caused by copyengine. They concern EmailBison routes and barrier
   checklist, present on the base branch.

4. **"The acceptance command passes"** — CONFIRMED.
   `sequencegate.check({'emails':{'em1':'a','em2':'a'},...})` → `passed=False`.
   With realistic repeated content, the gate correctly names `em2` as the
   failing step.

5. **"The stage runner does NOT call live APIs in tests"** — CONFIRMED.
   All 31 tests use mocked `groq_fn` and `sonnet_fn` callables. The real
   `_groq` and `_sonnet` functions are wired through `providers.model_key`
   but are never invoked during tests.

6. **"Does not send. Does not activate. No live outreach."** — CONFIRMED.
   No provider write operations. No campaign mutation. The module is purely
   a generation library.

### Claims with caveats:

7. **"The caller chain: copyengine is consumed by tests/test_copyengine.py
   through run_lead"** — TRUE BUT INSUFFICIENT. The only import of copyengine
   in the entire tree is from `tests/test_copyengine.py`. No `src/` module
   imports or calls it. See Finding 3.

8. **"The ten-lead preview and distinct capability count are OWED"** — HONEST.
   The result block explicitly acknowledges this. The live run requires API
   keys and research packs from Claude's worktree.

---

## Finding 3: Production caller chain — DISCONNECTED

**This is the critical finding.**

```
$ git grep -n "from.*copyengine\|import.*copyengine" 073e81e04 -- "src/*.py"
(empty)

$ git grep -n "from.*copyengine\|import.*copyengine" 073e81e04
073e81e04:tests/test_copyengine.py:14:from src import copyengine, copystages, copyprompts, sequencegate
```

**Zero production callers.** The only consumer is the test file. `bisonfactory.py`
exists on the branch and is the production copy pipeline, but it does NOT import
or call `copyengine`. The v2 engine is a parallel implementation that no
production path invokes.

This is the EXACT defect TASK-321 on master already identified and rejected:

> `src/copyengine.py` was NOT taken, and its test was NOT taken.
> **The wiring is a closed loop.** Measured on the branch:
>     NOTHING -> copyengine

The result block acknowledges this honestly in Finding 3:
> "The module is a library; the generation runner that calls it for production
> batches is Claude's to wire from his worktree."

But CLAUDE.md is explicit:
> "Zero production callers means DISCONNECTED, which is a rework and not a merge."

And the standing operator rule from TASK-321:
> "The v2 pipeline is still not the thing that produces production copy."

**Disposition: DISCONNECTED.** The module is correctly implemented but has no
production caller. This is not a code defect — it is a wiring defect. The code
does what it says; nothing calls it.

---

## Finding 4: Test falsifiability — PARTIALLY FALSIFIABLE

### What the tests prove:

- JSON parsing handles fences, newlines, truncation (6 tests)
- Role family mapping is correct (4 tests)
- The stage runner calls stages in order and produces output (11 tests)
- Held leads stop at the correct stage (4 tests)
- Output shapes are correct (email steps, threads, replies, P.S.) (4 tests)
- Batch capability check counts correctly (3 tests)
- The gate refuses repetition and empty sequences (2 tests)
- Navigation stripping works (2 tests)
- Asset reporting works (2 tests)

### What the tests do NOT prove:

1. **No test asserts on gate PASS/FAIL through `run_lead`.**
   `test_full_pipeline_qualifed_rich` asserts `assertIsNotNone(result["gate"])`
   but does not check `result["gate"]["passed"]`. This test would pass even if
   the gate was hardcoded to `{"passed": True, "failures": []}`.

2. **The acceptance command tests test `sequencegate.check` directly, not
   through `run_lead`.** They prove the gate works in isolation but not that
   `run_lead` calls it and propagates the result correctly.

3. **All model calls are mocked.** The tests prove the plumbing works with
   well-formed JSON, but not that the engine handles real model output
   correctly. This is deliberate (no live API calls in tests) but means the
   tests cannot catch prompt/model integration defects.

### Mutation test performed:

I drove `run_lead` with repeated email content (em1 == em2) through mocked
stages A-E and a sonnet_fn that returned identical bodies. The gate correctly
fired: `gate.passed = False`, failures included `em1`. **This proves the wiring
between `run_lead` and `sequencegate.check` is real** — but the test suite
itself does not have this test.

**Disposition: PARTIALLY FALSIFIABLE.** The tests prove plumbing but not
integration. The gate wiring is real (verified by mutation) but the test suite
does not assert on it. A test that asserts `result["gate"]["passed"]` through
`run_lead` would close this gap.

---

## Finding 5: Would merging delete anything? — NO

```
$ git diff master...073e81e04 --diff-filter=D --name-only
(empty)
```

No files would be deleted. The diff is purely additive: two new files and one
task file rename (TODO → DONE).

**Disposition: SAFE.** Merging would not delete any existing code.

---

## Finding 6: Scope drift — CLEAN

```
$ git diff master...073e81e04 --name-status
R060  docs/qwen-tasks/TODO/TASK-312-*.md  docs/qwen-tasks/DONE/TASK-312-*.md
A     src/copyengine.py
A     tests/test_copyengine.py
```

Only three changes: the two new code files and the task file move. No junk,
no unrelated modifications, no scratch files.

**Disposition: CLEAN.** No cherry-pick needed; the branch is merge-ready as-is.

---

## Summary of findings

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | Artifact exists at exact SHA | VERIFIED |
| 2 | Does what result block claims | VERIFIED WITH CAVEATS |
| 3 | Production caller chain | **DISCONNECTED** |
| 4 | Test falsifiability | PARTIALLY FALSIFIABLE |
| 5 | Would merging delete anything? | SAFE |
| 6 | Scope drift | CLEAN |

---

## Recommendation: REWORK

**Not because the code is wrong — it is well-built, tested, and honestly
reported.** The rework is narrowly scoped:

1. **The module has zero production callers.** CLAUDE.md's rule is explicit:
   "Zero production callers means DISCONNECTED, which is a rework and not a
   merge." TASK-321 on master already rejected the same code from a different
   branch for the same reason.

2. **The result block acknowledges this honestly** and scopes the wiring to
   Claude. That is the correct scope — but it means the artifact is not
   merge-ready until the wiring exists.

3. **The test suite does not assert on gate PASS/FAIL through `run_lead`.**
   Adding one test that drives the full pipeline with repeated content and
   asserts `result["gate"]["passed"] == False` would close the falsifiability
   gap and prove the gate wiring is real through the production entry point.

### What rework must do:

Either:

A. **Connect `copyengine` to a production entrypoint** so that generated copy
   actually flows through it. Even one integration test that drives through
   `bisonfactory.stage()` (or whatever the production path becomes) and shows
   the copy changed when the input changed would close this.

B. **Report explicitly that no production entrypoint exists yet** and that
   `copyengine` is a library awaiting wiring. This is acceptable — TASK-321
   says "The second answer is acceptable and may well be the true one." — but
   it must be stated plainly so nobody treats the library as a working
   production path.

### What rework need NOT do:

- Rewrite the implementation. The code is correct.
- Rewrite the tests. They pass and prove the plumbing.
- Change the result block. It is honest.
- Add features. The scope was A-H and the delivery was A-H.

---

## Evidence commands (reproducible, read-only)

```bash
# Verify the SHA
git rev-parse origin/qwen-worker-4-r59

# Check artifact existence
git ls-tree -r --name-only 073e81e04 | grep copyengine

# Check for production callers
git grep -n "from.*copyengine\|import.*copyengine" 073e81e04 -- "src/*.py"

# Run the tests
git worktree add .qwen/worktrees/review-478 073e81e04 --detach
cd .qwen/worktrees/review-478
python -m unittest tests.test_copyengine -v

# Run the acceptance command
python -c "import sys;sys.path.insert(0,'.');from src import sequencegate as g;\
r=g.check({'emails':{'em1':'a','em2':'a'},'linkedin':{},'ps':{},'subjects':{}});\
print([f['step'] for f in r['failures']]);assert not r['passed']"

# Check for deletions on merge
git diff master...073e81e04 --diff-filter=D --name-only

# Check scope drift
git diff master...073e81e04 --name-status
```

---

## Disposition

**REWORK.** The implementation is verified correct, the tests pass, the result
block is honest, and the branch is clean. But the module has zero production
callers, which is the exact defect CLAUDE.md and TASK-321 identify as
DISCONNECTED. The rework is narrowly scoped: either connect the engine to a
production entrypoint, or report explicitly that no such entrypoint exists yet
and that the library is awaiting wiring. The code itself need not change.
