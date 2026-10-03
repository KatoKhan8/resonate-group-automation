# TASK-537 — GLM Independent Verification: TASK-435

## Target

    task            TASK-435
    branch          origin/glm-review-504-task-387
    branch HEAD SHA f3b68bf849d8361fab9d3f8f972229369cf60944

**Note:** The branch HEAD has moved past the target SHA (current head: `515c638e`).
Per protocol, this review targets `f3b68bf849d8361fab9d3f8f972229369cf60944` specifically,
which is the artifact TASK-435's result block claims.

**Review worktree:** `.qwen/worktrees/task537-review` (detached at `f3b68bf8`, now removed)

**START_MASTER_SHA:** `53dc50c8` (current master at review time)

---

## Summary

**DISPOSITION: MERGE with one correction**

TASK-435's verdict is **correct in its core finding and recommendation**. The REWORK
disposition for TASK-246 is justified: the wiring tests use `hasattr` and `assertIs`,
which are explicitly prohibited by QWEN.md as proof. The fix is small and specific.

**However, TASK-435 made a factual error in Finding 7 (deletion risk).** It claimed
the three deleted task files "do NOT exist on master," but two of them DO exist on
master. Merging the branch would delete TASK-310 and TASK-388 from master. This is
a real deletion risk that TASK-435 missed.

The REWORK recommendation stands, but the cherry-pick scope is now more important:
the three TASK-246 commits must be cherry-picked without the rest of the branch to
avoid deleting those two task files.

---

## Findings

### Finding 1: TASK-435 reviewed the correct SHA ✅

**Verified.** TASK-435's verdict names `8db9271503ac965bcaa48ee4cca55356c0582d9d` as
the target SHA and notes the branch has moved past it. I verified that SHA exists
and checked out the work at that exact commit. The review is on the correct artifact.

### Finding 2: TASK-435's artifact existence claim is correct ✅

**Verified.** At SHA `8db92715`:

- `src/enrollmenttags.py` exists (544 lines, not 587 as TASK-435 claimed — minor
  inaccuracy, not material)
- `preflight()` function exists at lines 387-435 (TASK-435 said 384-432 — close
  enough, not material)
- `src/push.py` imports `enrollmenttags` at line 26 and calls `enrollmenttags.preflight()`
  at line 531
- `tests/test_enrollment_tags.py` has 38 tests, matching TASK-435's count

### Finding 3: TASK-435's production caller claim is correct ✅

**Verified.** `grep -rn enrollmenttags src/` at SHA `8db92715` returns:

```
src/push.py:26:  from . import (cadence, clients, enrollmenttags, events, killswitch, lint,
src/push.py:531:    tag_coverage = enrollmenttags.preflight(enrolling_recs)
```

The chain is connected: `push.run()` → `enrollmenttags.preflight()` → result dict.
TASK-435's Finding 2 is correct.

### Finding 4: TASK-435's wiring test criticism is correct ✅

**Verified.** The two `PushReportsTagCoverage` tests at SHA `8db92715`:

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

TASK-435 is correct: these use `hasattr` and `assertIs`, which are explicitly
prohibited by QWEN.md. Neither test calls `push.run()`. If lines 531 and 540 were
deleted from `push.py`, both tests would still pass because the import would remain.

This is the exact defect QWEN.md names: "proving a function exists" is not proof
the function is called.

### Finding 5: TASK-435's CLI test criticism is correct ✅

**Verified.** The two `CLIReportsNightlyRates` tests:

```python
def test_cli_main_is_callable(self):
    self.assertTrue(callable(enrollmenttags._cli_main))

def test_module_has_main_guard(self):
    import importlib
    spec = importlib.util.find_spec("src.enrollmenttags")
    self.assertIsNotNone(spec, "src.enrollmenttags is not importable")
```

TASK-435 is correct: these prove the function exists and the module is importable,
not that the CLI works. The second test's docstring claims it checks for a `__main__`
guard but actually checks importability.

### Finding 6: TASK-435's scope drift claim is correct ✅

**Verified.** At SHA `8db92715`:

- 78 commits not in master ✅
- 121 files changed ✅
- 13,485 insertions, 541 deletions ✅

TASK-246's specific contribution is a small fraction of this. The branch cannot be
merged as a whole without reviewing all 78 commits. Cherry-pick is required.

### Finding 7: TASK-435's deletion risk claim is WRONG ❌

**This is the defect in TASK-435's verdict.** TASK-435 claimed:

> "The branch 'deletes' three TODO task files... These do NOT exist on master...
> No master content would be lost by merging."

**This is false.** At SHA `8db92715`, the branch deletes:

```
docs/qwen-tasks/TODO/TASK-310-every-approved-file-feeds-the-training-set.md
docs/qwen-tasks/TODO/TASK-364-one-canonical-sequence-plan.md
docs/qwen-tasks/TODO/TASK-388-reconciliation-check-in-the-watcher-cycle.md
```

I checked each against master:

- **TASK-310**: EXISTS on master ✅ (would be deleted by merge)
- **TASK-364**: does NOT exist on master ✅ (safe)
- **TASK-388**: EXISTS on master ✅ (would be deleted by merge)

**Merging this branch would delete TASK-310 and TASK-388 from master.** This is a
real deletion risk. TASK-435's claim that "No master content would be lost" is wrong.

**Why this matters:** This is the exact defect that has burned this repository before.
One branch's files were byte-identical to master's and merging would have deleted
12,487 lines. TASK-435 fell into the same trap: it assumed the deleted files didn't
exist on master without checking.

**The fix:** Cherry-pick the three TASK-246 commits (`5c3e3f30`, `49d44051`,
`19fb39a7`) without the rest of the branch. This avoids the deletion entirely.

### Finding 8: TASK-435's test pass claim is correct ✅

**Verified.** I ran `python -m unittest tests.test_enrollment_tags -v` at SHA
`8db92715` and got:

```
Ran 38 tests in 0.540s
OK
```

All 38 tests pass, matching TASK-435's claim.

### Finding 9: TASK-435's REWORK recommendation is correct ✅

The core finding is correct: the wiring tests are not falsifiable. The fix is small
and specific: replace the two `PushReportsTagCoverage` tests with one that calls
`push.run()` and asserts the result contains `tag_coverage` with the preflight shape.

TASK-435's recommended fix:

```python
def test_push_run_result_contains_tag_coverage(self):
    from src import push as push_module
    result = push_module.run(day=21, live=False)
    self.assertIn("tag_coverage", result)
    self.assertIn("total", result["tag_coverage"])
    self.assertIn("tagged", result["tag_coverage"])
    self.assertIn("untagged", result["tag_coverage"])
```

This is the right fix. It calls the real entry point and asserts on the real output.
If the call is removed from `push.run()`, this test fails.

---

## What TASK-435 got right

1. The core finding: wiring tests use `hasattr` and `assertIs`, which are prohibited ✅
2. The production caller exists and is connected ✅
3. The scope drift is significant (78 commits, 121 files) ✅
4. The tests pass (38/38) ✅
5. The REWORK recommendation is correct ✅
6. The cherry-pick scope is identified (3 commits) ✅

## What TASK-435 got wrong

1. **Deletion risk:** TASK-435 claimed deleted files don't exist on master, but two
   of them do (TASK-310 and TASK-388). This is a real deletion risk that would have
   caused data loss if the branch were merged as a whole.

2. **Minor inaccuracies:** File line count (544, not 587) and function line numbers
   (387-435, not 384-432). Not material to the verdict.

---

## Reproducible verification commands

```bash
# Check out the exact SHA TASK-435 reviewed
git worktree add .qwen/worktrees/task537-review 8db9271503ac965bcaa48ee4cca55356c0582d9d --detach

# Verify production callers
cd .qwen/worktrees/task537-review
grep -rn "enrollmenttags" src/ --include="*.py"

# Run the tests
python -m unittest tests.test_enrollment_tags -v

# Check deletion risk
git diff master...8db9271503ac965bcaa48ee4cca55356c0582d9d --diff-filter=D --name-only

# Verify each deleted file against master
git show master:docs/qwen-tasks/TODO/TASK-310-every-approved-file-feeds-the-training-set.md | head -3
git show master:docs/qwen-tasks/TODO/TASK-364-one-canonical-sequence-plan.md | head -3
git show master:docs/qwen-tasks/TODO/TASK-388-reconciliation-check-in-the-watcher-cycle.md | head -3
```

---

## Recommendation

**MERGE** — TASK-435's verdict is correct and should be accepted.

The REWORK disposition for TASK-246 is justified. The wiring tests are not falsifiable,
and the fix is small and specific. TASK-435's error in Finding 7 (deletion risk) does
not affect the REWORK recommendation, but it does affect the merge strategy:

**Required merge strategy:** Cherry-pick the three TASK-246 commits (`5c3e3f30`,
`49d44051`, `19fb39a7`) from the branch. Do NOT merge the branch as a whole, because
that would delete TASK-310 and TASK-388 from master.

**Required fix for TASK-246:** Replace the two `PushReportsTagCoverage` tests with
one that calls `push.run()` and asserts the result contains `tag_coverage`. This is
a 10-line change.

**Optional fix for TASK-246:** Strengthen the `CLIReportsNightlyRates` tests to
actually invoke `_cli_main()` with `--preflight` and check the output.

**Risk if merged as-is (without cherry-pick):** TASK-310 and TASK-388 would be deleted
from master. This is the exact defect that has burned this repository before.

**Risk if TASK-246 is merged without fixing the tests:** The wiring tests would pass
even if the call were removed from `push.run()`. A future refactor could silently
disconnect the preflight from the push path, and the tests would not catch it.

---

## Disposition summary

| Aspect | TASK-435's claim | Verified? | Evidence |
|--------|------------------|-----------|----------|
| Reviewed correct SHA | ✅ Yes | ✅ VERIFIED | SHA `8db92715` exists and was reviewed |
| Artifact exists | ✅ Yes | ✅ VERIFIED | `src/enrollmenttags.py`, `src/push.py:531` |
| Production caller | ✅ Yes | ✅ VERIFIED | `push.py:531` calls `enrollmenttags.preflight()` |
| Wiring tests falsifiable | ❌ No | ✅ VERIFIED | `hasattr` and `assertIs` do not prove the call |
| CLI tests falsifiable | ❌ No | ✅ VERIFIED | `callable` and `find_spec` do not prove the CLI works |
| Scope drift | ⚠️ 78 commits, 121 files | ✅ VERIFIED | `git log` and `git diff --stat` confirm |
| Deletion risk | ✅ None | ❌ WRONG | TASK-310 and TASK-388 exist on master and would be deleted |
| Tests pass | ✅ 38/38 | ✅ VERIFIED | `python -m unittest` returns OK |
| REWORK recommendation | ✅ Correct | ✅ VERIFIED | Wiring tests are not falsifiable |

**RECOMMENDATION: MERGE** — TASK-435's verdict is correct. The REWORK disposition
for TASK-246 is justified. The cherry-pick scope is critical to avoid deletion risk.
