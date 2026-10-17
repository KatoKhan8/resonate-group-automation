# suitelock_failclosed_canary0180 - pinned fixture copies and tracer evidence

canary/0180, 2026-10-17. This directory makes the fail-closed branch of
`_alive` in `src/suitelock.py` TESTED, closing the gap canary/0150 measured
("Across every ref: 100/100 traced tests, 0 executions of the fail-closed
branch"). It belongs to no other lane: the two blobs under test live on refs
owned by other lanes, so they are pinned here as byte-faithful COPIES and
every measurement runs on scratch copies. No original was modified.

## The contract under test

`_alive(pid)` probes the process table (`tasklist` on Windows) inside
`try/except Exception: return True`. Unknown counts as ALIVE, so a suite
lock is never stolen on a guess. If that branch ever returns False, one
failed probe makes a live holder's lock stealable: two suites, one evidence
path, destroyed names.

## The two pinned blobs (denominator = 2, by SHA)

| label    | blob oid (sha1)                                | bytes  | fail-closed lines | resolved from |
|----------|------------------------------------------------|--------|-------------------|---------------|
| identity | `ea0dbdd872bd3a02732ade7fd5f89ba9064b486c`     | 34,353 | L373 / L374       | `refs/heads/task-suppression-0399-lock-identity-2026-10-16` tip `c85724df0ef4d3f477bcc283a79a208f9d40466a`, path `src/suitelock.py` |
| master   | `12de2433e6555a92a7def2cf5d2b5da7c2547c8c`     | 22,013 | L154 / L155       | `origin/master` tip `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`, path `src/suitelock.py` |

Both are LF (CR = 0). Every oid, byte count, sha256 and line number is also
in `MANIFEST.json`, computed from live refs at build time (never retyped),
and re-verified against the bytes by the closing test's own provenance
guard and by the harness before every arm.

## Files

- `suitelock_identity.py`, `suitelock_master.py` - the pinned blob copies.
- `MANIFEST.json` - oids, sizes, sha256, source refs and tips, computed
  `_alive` ranges and target lines, corpus oids, and the named exclusion.
- `tracer_arm.py` - the line-tracer harness (five arms per label). Run it
  from a checkout holding the pinned objects:
  `py -3 tracer_arm.py --repo <checkout>`. It builds hermetic packages
  under the system temp dir, never touches this tree's `src/`, and writes
  its transcripts to `arms/`.
- `arms/*.txt` - the twelve committed transcripts of the measured run
  (build + calibration + before + after + mutation + restore, per label),
  scrubbed of machine paths, ASCII, LF.

## The closing test

`tests/test_a_liveness_probe_that_raises_counts_as_alive.py` (one level up
from this directory). Reviewer mode - no environment, no harness:

    py -3 tests/test_a_liveness_probe_that_raises_counts_as_alive.py -v

Expected: `Ran 3 tests ... OK` on Windows (both behaviour methods plus the
provenance guard; the behaviour methods skip on non-Windows because the
seam under test is the Windows `tasklist` branch). The test installs a
raising fake as the loaded blob module's `subprocess` attribute, asserts
the fake fired exactly once (a plant that lands nowhere reads as a dead
row), and asserts `_alive(424248) is True` - identity, not truthiness. No
real process is queried; the pid is synthetic.

## The measured answers (transcripts in arms/, run 2026-10-17)

Per label, in arm order:

1. calibration - canary/0150's own passing control re-run FIRST: the
   fake-raise through the tracer gives except-line = 1, return-line = 1
   (identity L373=1 L374=1; master L154=1 L155=1). An instrument that
   cannot print 1/1 proves nothing else.
2. before - the pre-existing corpus WITHOUT the closing test (module not
   imported, asserted): L373=0 L374=0 (identity) and L154=0 L155=0
   (master). 0150's zero reproduced. The witness tables show the corpus
   really executed `_alive`'s body (720 traced line executions inside
   L345-L384 on identity; 350 inside L132-L165 on master), so the zero is
   a branch never taken, not a function never run.
3. after - corpus PLUS the closing test: L373=1 L374=1 and L154=1 L155=1.
   Exactly one execution of the branch, added by the closing test. The
   red-name set is unchanged versus before (set equality on
   arm-suffix-stripped ids): identity 0 red names both arms; master 26
   red names both arms (24 errors + 2 failures - the collateral test is
   written against the identity-era API and the L323 test is born-red on
   the master blob, both expected and recorded by canary/0170).
4. mutation - the pinned copy's fail-closed `return True` flipped to
   `return False`: exactly one differing line (identity L374, whole-file
   diff `[374]`, oid moves to `78103d43ae2f3ad03fe8483ebe8fe75e7728b74e`;
   master L155, diff `[155]`, oid moves to
   `fec53987252d8344c1128eb0ce23ee011cecb31b`). The closing behaviour
   test FAILS, naming itself, on the fail-closed assertion ("fail-closed
   contract broken"), with 1 failure and 0 errors, the fake-fired witness
   still green (no other guard fired first), and the branch still traced
   1/1 (the flip changed the value, not the coverage).
5. restore - pinned bytes written back (oid re-verified equal), the test
   is green again and 1/1 again: the red was the flip and nothing else.

Harness summary for that run: 10/10 arms PASS, "ARMS: ALL-PASS". pyc
discipline, printed counts per sweep in every transcript: direction
"write" after the package build and after the mutation write, direction
"revert" after the restore write, plus a pre-arm sweep before every
interpreter run (Python invalidates bytecode on mtime AND size with
whole-second granularity, so a same-second revert could otherwise import
stale bytes). Both directions applied.

## Named exclusion (NOT-RUN)

`tests/test_one_full_suite_at_a_time.py` is not in the corpus: it calls
`suitelock.path()`, the live machine-lock resolver, and needs `src.store`,
which the hermetic package does not carry; the task brief forbids taking
the suite lock. Named NOT-RUN per the canary/0170 precedent. Recorded in
`MANIFEST.json` under `excluded_corpus`.

## Corpus (the BEFORE arm's denominator, by SHA)

- `test_a_holder_that_dies_mid_check_is_stale_not_held.py`
  `486b9b3398e30448b5b34dc6be44fe38a6fb551c` (2 tests; from
  `7fbf1078c5f6eb417255ec8d84c6f3967bda8eaf`, this branch's parent)
- `test_the_suite_lock_holder_is_a_process_not_a_number.py`
  `2ac8a9217475edba9d967ba51a74fe0ca0551587` (26 tests; from
  `c85724df0ef4d3f477bcc283a79a208f9d40466a`)

Census at run time: 28 corpus tests per label (matching canary/0170's
recorded 26 collateral + 2), AFTER arms ran 31 (corpus + the closing
test's 3).
