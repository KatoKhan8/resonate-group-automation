# TASK-018 - Classify and repair the remaining suite failures

Operator backlog: QWEN-01.

## GOAL

Take the full-suite failure count from roughly 25 to zero, or to a list where
every remaining entry is a DELIBERATE expected failure with a written reason.

## WHY IT MATTERS

The suite has never been green. The last measured run was 8291 tests, 22 fail,
7 error, 5 skip, 16 expected failures - down from 134 at the start of that
run, which was the first time anybody had seen the number at all. Four of the
22 were fixed after that run, so expect about 25.

A suite nobody can read a verdict from is a suite that stops catching things.
Two real defects were found today in code the suite was green on, because the
functions involved (`heyreachfactory._plan`, `bison`'s write allowlist) had no
tests at all - not failing tests, NO tests. A red suite hides that class of
gap behind noise.

## CURRENT CONTEXT - the known clusters, from the checkpoint

    test_fixture_hygiene          3   real names/domains in fixtures
    test_e2e                      4   seven-step cadence expectations
    test_preproduction            2   same
    test_personalization_e2e      1
    test_the_cadence_reacts...    2   the generic hold-code defect (P1)
    test_mutation_anchors         1
    test_waterfall                1

Two of those are STALE EXPECTATIONS rather than defects - the cadence moved
from seven steps to `productive_li_heavy_v1`'s eleven touches and the tests
were not moved with it. The hold-code cluster is a REAL product defect and is
TASK-022; do not fix it here, and do not let it stop the rest.

## SCOPE

1. Run the suite to a verdict. `py -3 scripts/run_suite.py --timeout 2400`.
   READ THE EXIT CODE FROM UNITTEST, NOT FROM A PIPE - a pipe reports the
   filter's exit code and has reported green over a red run here before.
2. For EVERY failure, write one line classifying it as exactly one of:
   stale fixture / stale expectation / disconnected consumer / wrong canonical
   model / real product defect / flaky.
3. Fix the stale ones. Leave the real defects and file them.
4. `test_fixture_hygiene` failing on real names and domains is a PRIVACY
   finding, not a cosmetic one. Fix by replacing the data, never by widening
   what the hygiene test allows.

## THE RULE THAT DECIDES THIS TASK

Never weaken a check to make it pass. If a test is wrong, say why in the test
and change it deliberately. If a test is right, fix the product. A test
deleted or loosened without a written reason will be reverted on review.

## FILES ALLOWED

`tests/`, `docs/qwen-tasks/`. `src/**` ONLY for a defect you have first
reproduced with a failing test, and name it in FINDINGS.

## FILES FORBIDDEN

`work/**`. `config/.env`. `src/providerwrites.py`, `src/killswitch.py`,
`src/executionguard.py`, `src/approve.py` and both files under
`src/providers/` - those carry the safety seals and Claude changes them.

## PRODUCTION CONSTRAINTS

Zero network. Zero credentials. No provider call of any kind.

## VERIFY IN ISOLATION

`unittest discover` and `tests.offline` both bind loopback and build demo
estates; run back to back they overlap during teardown and one HTTP test
fails intermittently. Leave a gap between them. An intermittent failure is
diagnosed - alone, as a class, and in an isolated full run - never dismissed
as flaky without that.

## TESTS REQUIRED

The suite itself, run to an observed verdict, with the before and after
numbers both recorded in the result block.
