# TASK-435 — GLM Independent Verification: TASK-246

## Target

    task            TASK-246
    branch          qwen-worker-7-r9
    branch HEAD SHA 8db9271503ac965bcaa48ee4cca55356c0582d9d

**Note:** The branch has moved past the target SHA (current head: `de9161f6`).
Per protocol, this review targets `8db9271503ac965bcaa48ee4cca55356c0582d9d` specifically,
which is the artifact TASK-246's result block claims.

**Review worktree:** `.qwen/worktrees/task435-review` (detached at `8db92715`, now removed)

**START_MASTER_SHA:** `37c12335` (current master at review time)

---

## Summary

**DISPOSITION: REWORK**

The wiring is real and the code is correct. `push.py` genuinely imports
`enrollmenttags` and calls `enrollmenttags.preflight()` in `push.run()`. The
core module (validation, backfill, nightly report, under-30 refusal) is
well-designed and all 38 tests pass.

**However, the two wiring tests are the exact pattern QWEN.md says is "NOT
accepted as proof."** They use `hasattr` and `assertIs` — proving the import
exists, not that the function is called. If `enrollmenttags.preflight()` were
deleted from `push.run()` but the import remained, both wiring tests would
still pass. This is the third face of the defect that cost three tasks on
2026-09-14.

The fix is small: replace the two `PushReportsTagCoverage` tests with one that
calls `push.run()` and asserts the result contains `tag_coverage` with the
preflight shape.

---

## Findings

### Finding 1: Artifact exists and does what the result block claims ✅

**Verified.** At SHA `8db92715`:

- `src/enrollmenttags.py` (587 lines) contains:
  - `preflight()` function (lines 384-432) — checks tag coverage on records
  - `_cli_main()` function (lines 438-533) — CLI entry point
  - `__main__` guard (lines 536-537)
  - `import json` and `from . import store` (lines 36-38)

- `src/push.py` contains:
  - `from . import (..., enrollmenttags, ...)` (line 26)
  - `tag_coverage = enrollmenttags.preflight(enrolling_recs)` (line 531)
  - `"tag_coverage": tag_coverage` in the return dict (line 540)
  - CLI output of tag coverage (lines 576-580)

- `tests/test_enrollment_tags.py` has 38 tests, all passing

The result block's claims about files changed and what was added are accurate.

### Finding 2: Production caller exists ✅

**Verified.** `grep -rn enrollmenttags src/` returns:

```
src/push.py:26:  from . import (cadence, clients, enrollmenttags, events, killswitch, lint,
src/push.py:531: tag_coverage = enrollmenttags.preflight(enrolling_recs)
```

Two hits outside the module itself: the import and the call. This is NOT
disconnected. The chain is: `push.run()` → `enrollmenttags.preflight()` →
result dict → CLI output.

### Finding 3: Wiring tests are NOT falsifiable ❌

**This is the defect.** The two `PushReportsTagCoverage` tests:

```python
def test_push_result_contains_tag_coverage(self):
    from src import push as push_module
    self.assertTrue(
        hasattr(push_module, "enrollmenttags"),
        "push.py does not import enrollmenttags; the wiring is absent")

def test_push_result_tag_coverage_shape(self):
    from src import push as push_module
    self.assertIs(push_module.enrollmenttags.preflight,
                  enrollmenttags.preflight)
```

**What these prove:** The import exists and the function reference is correct.

**What they do NOT prove:** That `push.run()` calls `enrollmenttags.preflight()`.

**Mutation test performed:** I verified that if line 531
(`tag_coverage = enrollmenttags.preflight(enrolling_recs)`) and line 540
(`"tag_coverage": tag_coverage`) were deleted from `push.py`, both tests would
still pass. The import would remain, the function reference would remain, and
the tests check only those two things.

**QWEN.md explicitly prohibits this:**

> "Not accepted as proof: hasattr, assertions on source text, a token appearing
> in a file, proving a function exists, a JSON shape, or a fake cassette
> returning fake data."

Both tests use `hasattr` (test 1) and "proving a function exists" via `assertIs`
(test 2). These are the exact patterns the rule names.

**The docstring claims "Driven through push.run()" but neither test calls
push.run().** This is the second face of the defect from TASK-029, TASK-028,
and TASK-019 on 2026-09-14: the test describes what it should prove but
actually proves something weaker.

**What would fix it:**

```python
def test_push_run_result_contains_tag_coverage(self):
    """push.run() calls enrollmenttags.preflight and includes it in the result.
    
    If the call is removed from push.run(), this test fails because the
    result will not contain tag_coverage. This is the point.
    """
    from src import push as push_module
    result = push_module.run(day=21, live=False)
    self.assertIn("tag_coverage", result)
    self.assertIn("total", result["tag_coverage"])
    self.assertIn("tagged", result["tag_coverage"])
    self.assertIn("untagged", result["tag_coverage"])
```

This calls the real entry point and asserts on the real output. If the call is
removed, the test fails.

### Finding 4: CLI tests are also weak ⚠️

The two `CLIReportsNightlyRates` tests:

```python
def test_cli_main_is_callable(self):
    self.assertTrue(callable(enrollmenttags._cli_main))

def test_module_has_main_guard(self):
    import importlib
    spec = importlib.util.find_spec("src.enrollmenttags")
    self.assertIsNotNone(spec, "src.enrollmenttags is not importable")
```

**What these prove:** The function exists and the module is importable.

**What they do NOT prove:** That the CLI actually works, that `--preflight`
produces output, or that the `__main__` guard exists (the test checks
importability, not the guard).

These are less critical than the wiring tests because the CLI is not the
production path (push.run() is), but they are still not falsifiable for the
claims they make.

### Finding 5: Core module is solid ✅

The 29 original tests (not added by TASK-246) are well-designed and falsifiable:

- Unknown values are refused (not coerced) ✅
- Backfill from enrollment artifact works ✅
- Under-30 sends refuses the percentage ✅
- Rates name their denominator ✅
- Reply rate uses SENT not ENROLLED as denominator ✅

These tests drive through the actual functions (`validate`, `backfill`,
`nightly_report`) and assert on their output. They are the kind of test this
repository needs.

### Finding 6: Scope drift is significant ⚠️

The branch has **78 commits not in master**, changing **121 files** with
**+13,485 / -541 lines**. TASK-246's specific contribution is **4 files / 320
lines** (3 commits: `5c3e3f30`, `49d44051`, `19fb39a7`).

The rest is work from TASK-272, TASK-355, TASK-283, TASK-364, TASK-395,
TASK-328, TASK-427, TASK-426, and many others. This is not pollution — the
other tasks are legitimate work — but it means the branch cannot be merged as
a whole without reviewing all 78 commits.

**Cherry-pick scope:** The three TASK-246 commits (`5c3e3f30`, `49d44051`,
`19fb39a7`) are clean and self-contained. They can be cherry-picked without
the rest of the branch.

### Finding 7: No deletion risk ✅

The branch "deletes" three TODO task files:

```
docs/qwen-tasks/TODO/TASK-310-every-approved-file-feeds-the-training-set.md
docs/qwen-tasks/TODO/TASK-364-one-canonical-sequence-plan.md
docs/qwen-tasks/TODO/TASK-388-reconciliation-check-in-the-watcher-cycle.md
```

These do NOT exist on master (they were created on the branch and moved to
DONE/REVIEW). No master content would be lost by merging.

### Finding 8: The preflight is a report, not a gate ✅

The result block acknowledges this: "A lead without tags can still be enrolled.
This is deliberate." This is a design choice, not a defect. The preflight
result is in the push return value, so enforcement can be added later without
changing the preflight function.

---

## What is consumed and by whom

| Function | Caller | Location |
|----------|--------|----------|
| `enrollmenttags.preflight()` | `push.run()` | `src/push.py:531` |
| `enrollmenttags._cli_main()` | `__main__` guard | `src/enrollmenttags.py:537` |
| `push.run()` | `push.main()`, `run.stage_push()`, tests | multiple |

The chain is connected end-to-end.

---

## Reproducible verification commands

```bash
# Check out the exact SHA
git worktree add .qwen/worktrees/task435-review 8db9271503ac965bcaa48ee4cca55356c0582d9d --detach

# Verify production callers
cd .qwen/worktrees/task435-review
grep -rn "enrollmenttags" src/ --include="*.py"

# Run the tests
python -m unittest tests.test_enrollment_tags -v

# Mutation test: remove the call, see if tests catch it
# (Edit src/push.py: delete lines 531 and 540, re-run tests)
```

---

## Recommendation

**REWORK** — small, specific fix required.

The wiring is real and the code is correct. The defect is in the tests: the two
`PushReportsTagCoverage` tests use `hasattr` and `assertIs`, which are
explicitly prohibited by QWEN.md as proof. They prove the import exists, not
that the function is called.

**Required fix:** Replace the two `PushReportsTagCoverage` tests with one test
that calls `push.run()` and asserts the result contains `tag_coverage` with the
preflight shape. This is a 10-line change.

**Optional fix:** Strengthen the `CLIReportsNightlyRates` tests to actually
invoke `_cli_main()` with `--preflight` and check the output.

**Cherry-pick scope:** The three TASK-246 commits are clean and can be
cherry-picked from the branch without the other 75 commits.

**Risk if merged as-is:** The wiring tests would pass even if the call were
removed from `push.run()`. A future refactor could silently disconnect the
preflight from the push path, and the tests would not catch it. This is the
exact defect that cost three tasks on 2026-09-14.

---

## Disposition summary

| Aspect | Status | Evidence |
|--------|--------|----------|
| Artifact exists | ✅ VERIFIED | `src/enrollmenttags.py:384-537`, `src/push.py:26,531` |
| Production caller | ✅ VERIFIED | `push.py:531` calls `enrollmenttags.preflight()` |
| Wiring tests falsifiable | ❌ FAILED | `hasattr` and `assertIs` do not prove the call |
| Core module correct | ✅ VERIFIED | 29 original tests, all falsifiable |
| Scope drift | ⚠️ SIGNIFICANT | 78 commits, 121 files, TASK-246 is 4 files |
| Deletion risk | ✅ NONE | Deleted files don't exist on master |
| Tests pass | ✅ VERIFIED | 38/38 tests pass at target SHA |

**RECOMMENDATION: REWORK** — fix the wiring tests, then merge.
