# GLM Verdict: TASK-281 — UK/EU re-engagement provider age read

**Review target:** TASK-281  
**Branch:** qwen-worker-2-r9  
**Branch HEAD SHA:** f03c74fc01a40df45419742e122268d11c8395a1  
**Verified SHA:** f03c74fc01a40df45419742e122268d11c8395a1 (confirmed via `git rev-parse`)  
**Review date:** 2026-09-28  
**Reviewer:** GLM independent verification (TASK-440)

---

## Executive summary

**DISPOSITION: REWORK**  
**Recommendation: CHERRY-PICK only the three TASK-281 artifacts, do not merge the branch**

The three TASK-281 artifacts exist, are well-tested, and the core claim (provider age is load-bearing, cache is not read) is proven. However:

1. **Zero production callers.** The script is DISCONNECTED — it exists but nothing in `src/` or `scripts/` imports or invokes it. This is the recurring defect: a thing computed correctly that nothing downstream reads.
2. **Massive scope drift.** The branch carries 46 commits and 93 file changes; TASK-281 is 3 files. Merging the branch wholesale would introduce unrelated work.
3. **One deleted file.** `docs/qwen-tasks/TODO/TASK-372-the-suite-baseline-is-73-failures-short.md` is deleted; this must be reviewed separately.
4. **One code quality bug.** `compare_row` calls `assess_reengage(sends, sends, now=now)` instead of `assess_reengage(row, sends, now=now)`. The bug is harmless (the first parameter is never read) but the signature is misleading.

The artifacts are correct in isolation but not integrated. This is a REWORK, not a merge.

---

## 1. Artifact existence — VERIFIED

All three artifacts exist on the target ref `f03c74fc01a40df45419742e122268d11c8395a1`:

```
scripts/reengagement_provider_read.py          583 lines (claimed 584)
tests/test_reengagement_age_is_read_not_cached.py  365 lines (claimed 366)
docs/REENGAGEMENT-UK-EU-PROVIDER-READ-2026-09-25.md  161 lines
```

**Verification command:**
```bash
git show f03c74fc:scripts/reengagement_provider_read.py | wc -l
git show f03c74fc:tests/test_reengagement_age_is_read_not_cached.py | wc -l
git show f03c74fc:docs/REENGAGEMENT-UK-EU-PROVIDER-READ-2026-09-25.md | wc -l
```

**Added in commit:** 99795a3e18f04fa1925bfeb05d8211464c409a4d (TASK-281: UK/EU re-engagement provider age read)

---

## 2. Existence is not function — DISCONNECTED

**Zero production callers.** The script is not imported or invoked anywhere in the production codebase.

**Verification command:**
```bash
git grep -n "reengagement_provider_read" f03c74fc -- 'src/' 'scripts/' | grep -v "reengagement_provider_read.py:"
```

**Result:** (empty)

The script is a standalone tool that must be invoked manually. It is not wired into any pipeline, batch job, or entrypoint. This is the recurring defect documented in CLAUDE.md: "Existence is not function... trace the whole chain and prove every link is consumed."

**Impact:** The script can measure the UK/EU re-engagement age from the provider, but nothing in the production system uses that measurement. The live run is owed (the task acknowledges this), but even after the run, the script remains a dead end unless something consumes its output.

**This is a REWORK criterion:** zero production callers means DISCONNECTED.

---

## 3. Falsification of core claims — VERIFIED

### Claim 1: The script does not read the cached `last-touch.json`

**Verification command:**
```bash
git show f03c74fc:scripts/reengagement_provider_read.py | grep -n "last-touch"
```

**Result:** (empty)

**Test verification:**
```bash
cd .qwen/worktrees/task440-review
python -m unittest tests.test_reengagement_age_is_read_not_cached.TestNoLastTouchFileRead -v
```

**Result:** `test_source_does_not_reference_last_touch ... ok`

**Verdict:** PROVEN. The script does not read the cached file.

### Claim 2: Provider age is load-bearing, not the cache

**Mutation test performed:**

```python
# With provider data (send yesterday)
result_with = compare_row(inv_row, sends, 'GB', now=now)
# verdict: TOO_RECENT, provider_age_days: 1

# Without provider data (sends=None)
result_without = compare_row(inv_row, None, 'GB', now=now)
# verdict: HELD, provider_age_days: None
```

**Verdict:** PROVEN. Removing the provider read changes the verdict from TOO_RECENT to HELD, not to a silent fallback on the cache. The dependency is real.

### Claim 3: 30 tests, all green

**Verification command:**
```bash
cd .qwen/worktrees/task440-review
python -m unittest tests.test_reengagement_age_is_read_not_cached -v
```

**Result:** `Ran 30 tests in 0.002s ... OK`

**Verdict:** PROVEN. All 30 tests pass.

---

## 4. Test falsifiability — ADEQUATE

The tests are falsifiable:

1. **`test_yesterday_send_reads_as_touched_yesterday`** — asserts that a provider send yesterday reads as `provider_age_days == 1` and `verdict == TOO_RECENT`, even when the inventory claims 111 days. This would fail if the script read the cache instead of the provider.

2. **`test_deleting_provider_read_makes_the_test_fail`** — asserts that when `sends=None`, the verdict is HELD, not TOO_RECENT. This proves the function does not silently fall back to the inventory age.

3. **`test_source_does_not_reference_last_touch`** — asserts that the source code does not contain the string "last-touch". This would fail if someone added a cache read.

**Not accepted as proof:** The tests use synthetic provider data, not live provider responses. The task acknowledges this ("The live run is owed"). The tests prove the logic is correct given the input shape, but do not prove the script can actually read from a real provider or staged files.

**Verdict:** ADEQUATE for the logic, but the live run is needed to prove the I/O path.

---

## 5. Would merging delete anything? — ONE DELETION

**Verification command:**
```bash
git diff master...f03c74fc --name-status | grep "^D"
```

**Result:**
```
D  docs/qwen-tasks/TODO/TASK-372-the-suite-baseline-is-73-failures-short.md
```

**Analysis:** One file is deleted. This file is a task file for TASK-372 (suite baseline measurement). The deletion appears to be a task state transition (TODO → REVIEW or DONE), not a content deletion. However, the file is deleted from TODO/ without a corresponding addition in REVIEW/ or DONE/ on this branch.

**Verdict:** The deletion must be reviewed separately. It is not part of TASK-281's scope.

---

## 6. Scope drift — SIGNIFICANT

**Verification command:**
```bash
git diff master...f03c74fc --stat | tail -1
```

**Result:** `93 files changed, 10615 insertions(+), 315 deletions(-)`

**Breakdown:**
- 66 files added
- 19 files modified
- 1 file deleted
- 7 files renamed (task state transitions)

**TASK-281's contribution:** 3 files (the script, the test, the report)

**Other work on the branch:** 46 commits covering TASK-293, TASK-318, TASK-364, TASK-372, TASK-387, TASK-397, TASK-400, TASK-410, TASK-423/424/425, offer approvals, status reports, GLM verdicts, and more.

**Verdict:** SIGNIFICANT scope drift. The branch is a multi-task integration branch, not a single-task feature branch. Merging it wholesale would introduce unrelated work. **Cherry-pick only the three TASK-281 files.**

---

## 7. Code quality finding — HARMLESS BUG

**Location:** `scripts/reengagement_provider_read.py:333`

**Code:**
```python
verdict, reason = assess_reengage(sends, sends, now=now)
```

**Expected:**
```python
verdict, reason = assess_reengage(row, sends, now=now)
```

**Analysis:** The function `assess_reengage(inventory_row, sends, now=None)` takes `inventory_row` as its first parameter but never uses it. The function body only references `sends` and `now`. So passing `sends` as the first argument is a bug but it does not affect correctness.

**Impact:** None. The bug is harmless because the first parameter is dead. However, the signature is misleading and the call site is wrong.

**Recommendation:** Fix the call to `assess_reengage(row, sends, now=now)` for clarity, or remove the `inventory_row` parameter from `assess_reengage` if it is truly unused.

---

## 8. What the task claims vs. what it delivers

| Claim | Delivered | Verified |
|-------|-----------|----------|
| Script reads provider, not cache | Yes | PROVEN |
| 30 tests, all green | Yes | PROVEN |
| Mutation test proves dependency | Yes | PROVEN |
| No reference to `last-touch.json` | Yes | PROVEN |
| Live run produces per-row table | No (owed) | NOT VERIFIED |
| Script is consumed by production | No | DISCONNECTED |

---

## 9. Disposition

**DISPOSITION: REWORK**

**Reasons:**

1. **Zero production callers (DISCONNECTED).** The script exists but nothing uses it. This is the recurring defect and is a rework criterion per CLAUDE.md.

2. **Significant scope drift.** The branch carries 93 file changes across 46 commits. TASK-281 is 3 files. Merging the branch wholesale would introduce unrelated work.

3. **One deleted file.** TASK-372's task file is deleted without a clear state transition on this branch.

4. **One code quality bug.** The `assess_reengage` call passes the wrong first argument. Harmless but misleading.

**What is correct:**

- The three artifacts exist and are well-tested.
- The core claim (provider age is load-bearing, cache is not read) is proven.
- The mutation test proves the dependency.
- The tests are falsifiable and adequate for the logic.

**What is owed:**

1. **Wire the script into a production caller.** A batch job, a pipeline step, or an entrypoint must invoke it. Until then, it is a dead end.
2. **Run the live measurement.** The per-row table with real provider ages is owed. The task acknowledges this.
3. **Fix the `assess_reengage` call.** Change `assess_reengage(sends, sends, now=now)` to `assess_reengage(row, sends, now=now)`, or remove the unused parameter.
4. **Cherry-pick, do not merge.** Extract only the three TASK-281 files. Do not merge the branch.

---

## 10. Cherry-pick instructions

To extract only TASK-281's work:

```bash
git checkout -b task-281-cherry-pick master
git cherry-pick 99795a3e18f04fa1925bfeb05d8211464c409a4d
# Resolve any conflicts
# Run tests
python -m unittest tests.test_reengagement_age_is_read_not_cached -v
# Commit and push
```

This extracts the single commit that added the three TASK-281 artifacts, without the other 45 commits on the branch.

---

## 11. Reproducible verification commands

All commands were run in an isolated worktree at the target SHA:

```bash
# Create worktree
git worktree add .qwen/worktrees/task440-review f03c74fc01a40df45419742e122268d11c8395a1 --detach

# Verify SHA
git rev-parse qwen-worker-2-r9
# f03c74fc01a40df45419742e122268d11c8395a1

# Check artifacts exist
ls -la .qwen/worktrees/task440-review/scripts/reengagement_provider_read.py
ls -la .qwen/worktrees/task440-review/tests/test_reengagement_age_is_read_not_cached.py
ls -la .qwen/worktrees/task440-review/docs/REENGAGEMENT-UK-EU-PROVIDER-READ-2026-09-25.md

# Check for production callers
cd .qwen/worktrees/task440-review
grep -rn "reengagement_provider_read" src/ scripts/ | grep -v "reengagement_provider_read.py:"

# Check for last-touch reference
grep -n "last-touch" scripts/reengagement_provider_read.py

# Run tests
python -m unittest tests.test_reengagement_age_is_read_not_cached -v

# Check scope drift
git diff master...f03c74fc --stat | tail -1
git diff master...f03c74fc --name-status | grep "^D"
```

---

## 12. Findings summary

| # | Finding | Severity | Category |
|---|---------|----------|----------|
| 1 | Zero production callers (DISCONNECTED) | Critical | wiring |
| 2 | Significant scope drift (93 files, 46 commits) | High | scope |
| 3 | One deleted file (TASK-372 task file) | Medium | state |
| 4 | Harmless bug in `assess_reengage` call | Low | code-quality |
| 5 | Live run not executed (acknowledged) | Medium | incomplete |

---

**Verdict written:** 2026-09-28  
**Reviewer:** GLM independent verification (TASK-440)  
**Target SHA:** f03c74fc01a40df45419742e122268d11c8395a1  
**Disposition:** REWORK  
**Recommendation:** CHERRY-PICK the three TASK-281 artifacts, wire into a production caller, run the live measurement, fix the `assess_reengage` call.
