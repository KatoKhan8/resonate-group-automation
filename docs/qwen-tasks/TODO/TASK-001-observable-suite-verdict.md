# TASK-001 - Make the full test suite's verdict observable

## GOAL

A full-suite run whose PASS/FAIL verdict and exit code are actually observed,
without a 900-second watchdog killing it and without a pipe swallowing the
exit code.

## WHY IT MATTERS

This is P1-0 in `docs/CLAUDE-HANDOFF.md` and it invalidates every other
claim. Three earlier runs "exited 0"; that was the exit code of `tail` at the
end of the pipeline, not of `unittest`. One honest run exited 124 - killed at
the watchdog. Right now nobody in this project knows whether the suite is
green. Every statement of the form "safety tests pass" rests on a subset.

## CURRENT CONTEXT

- 342 files under `tests/`.
- `python -m unittest discover` and `python -m tests.offline` both bind
  loopback and build demo estates. Run back to back they overlap during
  teardown and one HTTP test fails intermittently. CLAUDE.md requires a gap
  between them.
- A prior MemoryExhaustion on this machine was caused by a runaway unittest
  process, so unbounded concurrency is not the answer.

## SCOPE

1. Measure where the time actually goes. Per-test-module wall clock, written
   to a file, slowest 30 reported.
2. Decide between (a) shards that each finish inside a sane watchdog and whose
   verdicts are aggregated, and (b) one run with a raised watchdog. Prefer
   whichever produces an observed verdict with the least new machinery.
3. Whatever you build must report the unittest exit code itself. Never pipe
   unittest into a filter and read the filter's status.
4. Run it. Record the real verdict and the real failing test names.

## FILES ALLOWED

`tests/` (new runner/shard helper only), `docs/qwen-tasks/`, a new script
under `scripts/` if one is genuinely needed.

## FILES FORBIDDEN

`src/**` - do NOT fix failing tests in this task. Report them.
`work/**`, `config/clients/**`, anything under `.github/`.

## PRODUCTION CONSTRAINTS

Offline only. No provider network calls. If a test reaches for a provider
credential, that is a finding, not something to satisfy.

## TESTS REQUIRED

The deliverable IS a test run. Also: whatever you add must itself be
exercised once with a deliberately failing test injected, to prove a red
result is reported red and not swallowed. Remove the injected failure
afterwards and say in the result that you did.

## EXPECTED OUTPUT

- The measurement file (slowest modules).
- The runner, if one was needed.
- A written verdict: total tests, failures, errors, skips, wall clock, and
  the exact names of anything not green.

## DONE CONDITION

Someone can run one documented command and see a true verdict for the whole
suite, and this file records what that verdict was on the day it ran.

## RESULT

STATUS: TODO
COMMIT SHA:
TESTS:
FILES CHANGED:
FINDINGS:
RISKS:
RECOMMENDED CLAUDE ACTION:
