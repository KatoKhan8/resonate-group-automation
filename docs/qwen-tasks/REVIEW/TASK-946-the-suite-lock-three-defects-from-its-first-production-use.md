# TASK-946 — the suite lock's three defects, all from its first production use

Covers TASK-946 (the lock stole itself from a live holder), TASK-950 (the wait
default starved the one run that mattered) and TASK-951 (`started_at` was the
launch time), plus the FIFO queue and the detached-HEAD label.

## Why

The machine-wide suite lock merged at `6f3aeda2` and its first day in production
found three defects in one function, every one of them measured rather than
reasoned about:

1. **It stole itself from a live holder.** `_write` created the file with
   `O_CREAT|O_EXCL` and wrote the payload in a SEPARATE call, so the lock existed
   EMPTY for a moment. `read` turns an unreadable lock into `{"pid": None,
   "damaged": True}`, `_alive(None)` is False, and `acquire` unlinked it as stale.
   A holder's payload (pid 117216, 13:19:00Z) was found replaced by another
   branch's while that pid was still running, and two suites then ran at once —
   the one thing this module exists to prevent.
2. **Grants were unordered, and it starved the run that mattered.** `acquire`
   raced on `O_EXCL`, so arrival order bought a waiter nothing. The frozen master
   reference, launched with the 4200s default while every track had asked for
   10800 or more, was overtaken twice and raised `SuiteBusy` after 70 minutes
   with ZERO tests run. Six suites finished that day in 2281–2767s, so 4200s
   cannot survive even two runs ahead.
3. **`started_at` was the launch time, not the acquisition time.** A lock
   advertised `started_at=15:20:52` while its suite actually ran 15:59:58 →
   16:39:12 — a 39-minute overstatement equal to its queue wait, and another
   holder briefly advertised ~77 minutes. The figure is printed in all three
   operator-facing messages, so a reader asking "is this hung?" saw a 40-minute
   suite apparently 77 minutes in, and the obvious response to that is to kill a
   healthy run.

Every refinement fails SAFE: no hard links, or no queue directory, and `acquire`
falls back to the behaviour it had and says so out loud. Fairness and atomicity
are refinements; serialisation is the rule.

## Scope

`src/suitelock.py`, `scripts/run_suite.py`, `CLAUDE.md`'s standing rule, and
`tests/test_one_full_suite_at_a_time.py`. Nothing on the send path: the closure
walked from `executionguard`, `providerwrites`, `eligibility`, `generate` and
`lint` contains none of these files.

## Acceptance

```
python -m unittest tests.test_one_full_suite_at_a_time
python -c "import sys, os; sys.path.insert(0,'.'); from src import suitelock, store; p = suitelock.path(); assert os.path.isabs(p), p; assert os.path.abspath(p) != os.path.abspath(os.path.join(store.PRODUCTION_WORK, 'suite.lock')), p; print('OK the lock is outside this worktree:', p)"
python -c "import sys, os, json, tempfile, itertools; sys.path.insert(0,'.'); from src import suitelock; c = itertools.count(1); suitelock.time.strftime = (lambda f: 'T%02d' % next(c)); p = os.path.join(tempfile.mkdtemp(), 'work', 'suite.lock'); os.makedirs(os.path.dirname(p)); json.dump({'pid': 999999999, 'branch': 'dead'}, open(p, 'w')); m = suitelock.acquire(branch='x', timeout=5, file_path=p, poll=0.01, say=(lambda *a: None)); assert m['started_at'] > m['queued_at'], m; print('OK started_at is the acquisition, queued_at the launch:', m['queued_at'], '->', m['started_at'])"
python -c "import sys, os, tempfile; sys.path.insert(0,'.'); from src import suitelock; p = os.path.join(tempfile.mkdtemp(), 'work', 'suite.lock'); calls = []; suitelock._write_in_place = (lambda *a, **k: calls.append(1)); suitelock.acquire(branch='atomic', file_path=p, timeout=1, say=(lambda *a: None)); assert calls == [], 'the one-step fallback was used: %r' % calls; assert os.path.isfile(p), 'nothing was published at all'; print('OK published by hard link; the one-step fallback was never used')"
python -c "import sys; sys.path.insert(0,'.'); from src import suitelock; assert suitelock.DEFAULT_TIMEOUT >= 2767.0 * 6, suitelock.DEFAULT_TIMEOUT; print('OK the wait default outlasts a realistic queue:', suitelock.DEFAULT_TIMEOUT, 'vs six suites at the slowest measured 2767s')"
```

### Why each command can fail

- **Command 1** is the 37-test module, and five mutations have been run against
  it: `_my_turn` always true gives "SuiteBusy not raised"; `_label` returning its
  input gives "'detached abc1234' != 'HEAD'"; keeping the ticket in the `finally`
  leaves two tickets where one belongs; a one-step publish gives "Expected
  `_write_in_place` to not have been called"; no grace for a damaged lock gives
  "SuiteBusy not raised". Each was proved applied by its token and restored with
  `__pycache__` wiped, because two of them are equal-length.
- **Command 2** fails the moment the path is derived from this tree's own ROOT,
  which is the original defect: `work/` is gitignored, so every worktree has its
  own and six concurrent runs serialised nothing.
- **Command 3** fails if `started_at` is stamped before the wait loop again. The
  clock counts rather than sleeps, so the ORDER is asserted, not a duration.
- **Command 4** fails if the publish stops being atomic, and it is an effect
  assertion on a call that must NOT happen — the shape that cannot be satisfied
  by writing the word "link" in a comment.
- **Command 5** fails if the default drops back below a realistic queue. The
  figure is checked against the slowest suite actually measured that day, so it
  cannot drift away from reality silently.

### Mutation

Set `_my_turn` to `return True` unconditionally and
`test_a_later_arrival_waits_even_when_the_lock_is_free` must go red with
"SuiteBusy not raised" — the FIFO property, asserted with no lock file present at
all, which the old implementation would have taken instantly.

## Files

`src/suitelock.py`, `scripts/run_suite.py`, `CLAUDE.md`,
`tests/test_one_full_suite_at_a_time.py`. `--lock-wait` must READ
`suitelock.DEFAULT_TIMEOUT` rather than carry a copy of it; the two figures had
already drifted once and that is how the reference came to be launched with a
timeout shorter than the queue ahead of it.
