# CANARY/0180 - the fail-closed branch of `_alive` now has a closing test

Date: 2026-10-17. Lane: canary. Branch:
`task-canary-0180-failclosed-closing-test-2026-10-17` (parent
`7fbf1078c5f6eb417255ec8d84c6f3967bda8eaf`). Status: COMPLETE, measured,
pushed (readback in the lane log). No other lane's blob was modified; the
main checkout was never opened; no suite lock was taken; no network call
beyond this branch's own authorised push and ls-remote.

## The gap, in the measuring task's own words

canary/0150: "Across every ref: 100/100 traced tests, 0 executions of the
fail-closed branch - it has zero tests anywhere, and the closing test (a
one-line raising-fake monkeypatch) is recorded as a gap, not written, since
both blobs belong to other lanes."

The branch: `_alive(pid)`'s Windows seam runs `tasklist` through
`subprocess.run` inside `try/except Exception: return True`. The contract,
from `_alive`'s own docstring in both blobs: "Unknown counts as ALIVE, so a
lock is never stolen on a guess - waiting costs time, stealing costs a
corrupted run." If this branch ever answers False, one failed probe makes a
live suite holder's lock stealable - two suites running at once against one
evidence path, which is the exact incident the lock exists to prevent.

## The one question, and the answer

Does a one-line raising-fake monkeypatch test execute the fail-closed
`return True` branch and make `_alive()` return True, on scratch copies of
BOTH suitelock blobs - and does that test FAIL, naming itself, when the
branch is mutated to `return False`?

**YES and YES, on both blobs, measured with a `sys.settrace` line tracer:**

| blob (denominator = 2) | oid | fail-closed lines | BEFORE (corpus, no closing test) | AFTER (corpus + closing test) | mutation `return True` -> `return False` |
|---|---|---|---|---|---|
| identity (`task-suppression-0399-lock-identity-2026-10-16` @ `c85724df0ef4d3f477bcc283a79a208f9d40466a`) | `ea0dbdd872bd3a02732ade7fd5f89ba9064b486c` | L373 (except) / L374 (return True) | L373=0, L374=0 - 0150's zero reproduced | L373=1, L374=1 | test FAILS by name on the fail-closed assertion, 1 failure 0 errors; mutated oid `78103d43ae2f3ad03fe8483ebe8fe75e7728b74e`; restored green, 1/1 |
| master (`origin/master` @ `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`) | `12de2433e6555a92a7def2cf5d2b5da7c2547c8c` | L154 (except) / L155 (return True) | L154=0, L155=0 | L154=1, L155=1 | test FAILS by name, 1 failure 0 errors; mutated oid `fec53987252d8344c1128eb0ce23ee011cecb31b`; restored green, 1/1 |

The tracer prints both answers (0 and 1/1) per blob; the twelve committed
transcripts are under
`tests/fixtures/suitelock_failclosed_canary0180/arms/`. Harness summary:
10/10 arms PASS, "ARMS: ALL-PASS", exit 0 - and the exit code is not the
result, the transcripts are.

## What was built

- `tests/test_a_liveness_probe_that_raises_counts_as_alive.py` - the closing
  test. Stdlib only, standalone: it loads each pinned blob copy as a fresh
  module from its bytes (never a `sys.modules` hit, so a mutated file on
  disk is what it loads), installs a raising fake as the module's
  `subprocess` attribute, asserts the fake fired exactly once, and asserts
  `_alive(424248) is True` - identity, not truthiness. The pid is
  synthetic; no real process is ever queried. A separate provenance method
  re-verifies both fixture copies against `MANIFEST.json` (oid =
  sha1(header+content), byte count, sha256, and the two target lines'
  shape) so a drifted fixture fails as a drifted fixture and can never
  mask or replace the behaviour assertion's red.
- `tests/fixtures/suitelock_failclosed_canary0180/` - the pinned blob
  copies, `MANIFEST.json` (every SHA computed from live refs at build
  time, never retyped), `tracer_arm.py` (the harness), `README.md`, and
  `arms/` (the transcripts).

Reviewer mode, no environment and no harness:
`py -3 tests/test_a_liveness_probe_that_raises_counts_as_alive.py -v` -
measured `Ran 3 tests ... OK`, zero skips, exit 0.

## Method: five arms per label, calibration first

1. **calibration** - canary/0150's own passing control re-run FIRST: the
   fake-raise through the tracer gives 1/1 on the target lines. If the
   instrument cannot print 1/1, nothing after it means anything.
2. **before** - the pre-existing corpus WITHOUT the closing test; the
   module is provably not imported (`sys.modules` checked). Target lines
   0/0. The witness tables show the corpus really executed `_alive`'s body
   (720 traced executions inside identity's L345-L384; 350 inside master's
   L132-L165 - real `tasklist` calls from the collateral test's child-wait
   and dead-pid search), so the zero is a branch never taken, not a
   function never run.
3. **after** - corpus plus the closing test: exactly 1/1 per blob. The
   red-name set is compared to the before arm by SET EQUALITY on
   arm-suffix-stripped ids, never by count: identity 0 red names in both
   arms; master 26 red names in both arms (24 errors + 2 failures - the
   collateral test targets the identity-era API and the L323 test is
   born-red on the master blob; both states were recorded by canary/0170
   and neither changed).
4. **mutation** - line-targeted flip of the fail-closed `return True` to
   `return False` on the scratch copy. The whole-file line diff is printed
   and is exactly one line ([374] identity, [155] master). The intended
   test failed for the intended reason: the failure message is the
   fail-closed assertion ("fail-closed contract broken"), the fake-fired
   witness did NOT fail (no other guard fired first), errors = 0, and the
   branch still traces 1/1 - the flip changed the value, not the coverage.
5. **restore** - pinned bytes written back, oid re-verified equal to the
   pin, test green again, 1/1 again. The red was the flip and nothing else.

Corpus per label (BEFORE-arm denominator, census at run time):
`test_a_holder_that_dies_mid_check_is_stale_not_held.py`
`486b9b3398e30448b5b34dc6be44fe38a6fb551c` (2 tests) +
`test_the_suite_lock_holder_is_a_process_not_a_number.py`
`2ac8a9217475edba9d967ba51a74fe0ca0551587` (26 tests) = 28, matching
canary/0170's recorded counts; AFTER arms ran 31.

**Named exclusion (NOT-RUN):** `test_one_full_suite_at_a_time.py` - it
calls `suitelock.path()`, the live machine-lock resolver, and needs
`src.store`, which the hermetic package does not carry; the brief forbids
taking the suite lock. Named NOT-RUN per the canary/0170 precedent;
recorded in `MANIFEST.json`.

## Honest run history

The first full harness run finished 9/10: `master/after` failed its own
name-set gate. The gate was defective, not the code - it compared raw
`test.id()` strings, which embed the per-arm unique module name
(`...__master__before` vs `...__master__after`), so equality was
impossible by construction even though the underlying name sets were
identical (24 errors + 2 failures on both sides). Fixed by normalising
the arm suffix before comparison, and the WHOLE sequence was re-run for
both labels so the committed transcripts are one consistent run: 10/10
PASS. The first run's console log stays in the task scratch dir
(`arms-run-1.log`) and is not committed; its master/after transcript was
overwritten by the re-run. (identity/after had passed the defective gate
only trivially - empty set equals empty set - so the re-run matters for
both labels' evidence, not just master's.)

## What this does NOT claim

- Neither pinned blob was modified anywhere. The copies under
  `tests/fixtures/` are oid-pinned measurements of other lanes' bytes as
  they stood at the named tips; if those refs move, the fixtures stay at
  the measured versions by design (the provenance guard fails loudly if
  anyone edits a copy).
- The closing test guards the CONTRACT on the pinned copies. Making it
  guard a future merged `src/suitelock.py` in place is the merging lane's
  step, not this branch's - this branch touches no other lane's blob.
- The mutation arm proves teeth on scratch copies inside the harness's
  hermetic package; nothing mutated ever existed outside the system temp
  dir, and each mutation was reverted with an oid readback in the same arm
  sequence.

## Discipline ledger

- pyc (qwen/0176's rule): sweeps after every `.py` write (direction
  "write": package build, mutation write - 4 sweeps in the committed run)
  and after every revert (direction "revert": restore write - 4), plus a
  pre-arm sweep before every interpreter run (12). BOTH directions
  applied; per-sweep removed counts are printed in every transcript.
  Reviewer-mode run's caches were swept too (1 dir).
- Hygiene: every staged byte was scanned against
  `tests/test_fixture_hygiene.py`'s own imported constants (forbidden
  names/domains/figures as plain substrings - a 40-hex oid CAN contain a
  forbidden figure by accident, so this was checked, not assumed - plus
  email domains, phone shapes, CRM phrases) BEFORE commit: ALL-PASS. All
  committed files ASCII, LF, CR=0.
- Transcripts are scrubbed of machine paths (`<PKG>`, `<TMP>`,
  `<SOURCE_ROOT>`, `<REPO>`) and verified by readback after writing.
- Synthetic fixtures only; no real process queried (synthetic pid, raising
  fake fires before any spawn); no network in any test or arm; no key or
  credential value read or printed.
- Commit is plumbing-only (temp index + `hash-object -w` + `commit-tree` +
  `update-ref`): the worktree never moves off
  `task-canary-0140-l323-test-2026-10-17` and no lane's checkout is
  touched. Push verification (ls-remote readback + empty-answer control)
  is in the lane log, `LANE-canary.md`, canary/0180 entry.

Lineage: canary/0150 measured the zero; canary/0170 built the hermetic
scratch-package pattern, the blob census and the plumbing-commit precedent
this task reuses; canary/0180 closes the gap.
