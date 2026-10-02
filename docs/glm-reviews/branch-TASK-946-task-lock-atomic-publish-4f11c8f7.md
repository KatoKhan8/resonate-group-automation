# GLM branch verification: TASK-946

Branch: `task-lock-atomic-publish`
Date: 2026-10-02T18:31:37.253733+00:00
Model: glm-5.3
Duration: 102.94s
Usage: {'prompt_tokens': 14599, 'completion_tokens': 7680, 'total_tokens': 22279, 'reasoning_tokens': 6943, 'cached_tokens': 14592}

## Verdict: PASS

## GLM spend

This call: 1 ledger rows, 18128 micro-USD

## Changed files (5)

- `CLAUDE.md`
- `docs/qwen-tasks/REVIEW/TASK-946-the-suite-lock-three-defects-from-its-first-production-use.md`
- `scripts/run_suite.py`
- `src/suitelock.py`
- `tests/test_one_full_suite_at_a_time.py`

## Diff stat

```
 CLAUDE.md                                          |  16 +-
 ...-three-defects-from-its-first-production-use.md |  89 +++++
 scripts/run_suite.py                               |  14 +-
 src/suitelock.py                                   | 384 ++++++++++++++++++---
 tests/test_one_full_suite_at_a_time.py             | 381 ++++++++++++++++++++
 5 files changed, 835 insertions(+), 49 deletions(-)

```

## Acceptance output

```
$ python -m unittest tests.test_one_full_suite_at_a_time
exit=0
.....................................
----------------------------------------------------------------------
Ran 37 tests in 12.431s

OK

$ python -c "import sys, os; sys.path.insert(0,'.'); from src import suitelock, store; p = suitelock.path(); assert os.path.isabs(p), p; assert os.path.abspath(p) != os.path.abspath(os.path.join(store.PRODUCTION_WORK, 'suite.lock')), p; print('OK the lock is outside this worktree:', p)"
exit=0
OK the lock is outside this worktree: C:\Users\Zvonimir\Desktop\resonate-group-automation\work\suite.lock

$ python -c "import sys, os, json, tempfile, itertools; sys.path.insert(0,'.'); from src import suitelock; c = itertools.count(1); suitelock.time.strftime = (lambda f: 'T%02d' % next(c)); p = os.path.join(tempfile.mkdtemp(), 'work', 'suite.lock'); os.makedirs(os.path.dirname(p)); json.dump({'pid': 999999999, 'branch': 'dead'}, open(p, 'w')); m = suitelock.acquire(branch='x', timeout=5, file_path=p, poll=0.01, say=(lambda *a: None)); assert m['started_at'] > m['queued_at'], m; print('OK started_at is the acquisition, queued_at the launch:', m['queued_at'], '->', m['started_at'])"
exit=0
OK started_at is the acquisition, queued_at the launch: T01 -> T03

$ python -c "import sys, os, tempfile; sys.path.insert(0,'.'); from src import suitelock; p = os.path.join(tempfile.mkdtemp(), 'work', 'suite.lock'); calls = []; suitelock._write_in_place = (lambda *a, **k: calls.append(1)); suitelock.acquire(branch='atomic', file_path=p, timeout=1, say=(lambda *a: None)); assert calls == [], 'the one-step fallback was used: %r' % calls; assert os.path.isfile(p), 'nothing was published at all'; print('OK published by hard link; the one-step fallback was never used')"
exit=0
OK published by hard link; the one-step fallback was never used

$ python -c "import sys; sys.path.insert(0,'.'); from src import suitelock; assert suitelock.DEFAULT_TIMEOUT >= 2767.0 * 6, suitelock.DEFAULT_TIMEOUT; print('OK the wait default outlasts a realistic queue:', suitelock.DEFAULT_TIMEOUT, 'vs six suites at the slowest measured 2767s')"
exit=0
OK the wait default outlasts a realistic queue: 21600.0 vs six suites at the slowest measured 2767s
```

## GLM response

**1. Production caller: YES.** `scripts/run_suite.py:main` (diff hunk at `@@ -305,7 +309,9 @@`) calls `suitelock.acquire(branch=_current_branch(), timeout=wait)` and now reads `suitelock.DEFAULT_TIMEOUT` instead of its private 4200.0. Every new helper (`_label`, `_take_ticket`, `_my_turn`, `_write`) is reached through `acquire`. This is the suite runner the standing rule mandates — not a test, not `work/`, not a dead re-export.

**2. Can the acceptance fail: YES, all five.** Not vacuous:
- Cmd 1: `_my_turn := True` makes `test_a_later_arrival_waits_even_when_the_lock_is_free` go red ("SuiteBusy not raised").
- Cmd 2: fails if `path()` is derived from this tree's ROOT.
- Cmd 3: if `started_at` were stamped pre-wait, both read "T01" and `T01 > T01` is False.
- Cmd 4: concrete input — any FS where `os.link` raises non-`FileExistsError`; `_write` then calls the patched `_write_in_place`, `calls == [1]`, assert fires.
- Cmd 5: fails the moment `DEFAULT_TIMEOUT < 16602.0`.

**3. Arithmetic: reconciles.** 2767.0×6 = 16602 ≤ 21600 (slack 4998s); "six hours" = 21600s ✓; "4200 cannot survive even two runs ahead": 2×2281.5 = 4563 > 4200 ✓; "70 minutes" = 4200s ✓; "four overtakes at 46min starve a 3h wait": 184 > 180 ✓. "Ran 37 tests": 36 visible + the results block itself truncates mid-name (`test_an_omitted_flag_reaches_acquire_as_the_mo`), consistent with 37; no falsification.

**Files vs task:** all five answer to TASK-946 (CLAUDE.md = standing rule; docs = review doc; run_suite = single timeout authority; suitelock = the fixes; tests = proof). No `*.txt`/`*.err`/`*.out` at root in the changed list.

**Findings (minor, bounded):**
- `src/suitelock.py`, `_write`: if `os.write` on the staged tmp raises (e.g. ENOSPC), control returns via the staging `except` to `_write_in_place`, and the `finally: os.unlink(tmp)` is attached to the *`os.link`* try, which is never entered — so `<lock>.<pid>.<ns>.tmp` is orphaned in the shared main-checkout `work/`. Cost: one stray file per failed publish; the mutex itself is intact (`FileExistsError` re-raise precedes the fallback). `test_no_temp_file_is_left_behind...` only covers the held-lock path.
- Ticket-name pid reuse: a dead waiter's pid recycled by an unrelated process wedges queue order until that process exits. At ~6 runs/day, not a measurable cost.

Truncation note: the hidden 7071 chars are the tail of the test file only; both production files are fully shown, so nothing hidden can change Q1–Q3.

VERDICT: PASS
