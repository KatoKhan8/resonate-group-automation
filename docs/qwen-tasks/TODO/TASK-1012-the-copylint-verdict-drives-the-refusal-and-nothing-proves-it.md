PRIORITY: P0
DEPENDS:
TIMEBOX: 90 minutes. If you are not green at 90, write what you measured
under FINDINGS, commit, move the file to REVIEW/ and stop.

# TASK-1012 - the copylint verdict drives the refusal, and nothing proves it

## WHERE THIS SITS

`docs/../resonate-ops/control-inventory-2026-10-14/TIER-1-2.json` enumerated
45 Tier 1/2 controls by reverse call graph and found **four** whose row reads
`"test_asserts_it_fires": "NEVER - no test names it"`. This is one of them:

    control:        bisonfactory._copylint_report
    where:          src/bisonfactory.py:645
    tier:           1
    callers_src:    2
    hops_to_sink:   2
    sits_in_front_of: optout.append_opt_out - opt-out appended to a body
    raises_or_returns: CONTROL INPUT - computes a value a refusal depends on;
                       cannot refuse itself

**Read that last line twice, because it decides the whole shape of this task.**
`_copylint_report` never raises. It computes the verdict that
`_refuse_copylint` raises on. So "test that the control fires" cannot mean
"assert this function raises" - it means **prove that the refusal is driven by
THIS function's return value, and prove this function actually ran.**

### What already has coverage, and what does not

Do not rediscover these. Measured today:

    _refuse_copylint       NAMED by tests/test_a_dry_run_runs_the_sequence_gate.py
                           and discussed in tests/test_a_dead_cta_link_is_refused.py
    _copylint_batch        NAMED by tests/test_a_described_capability_traces_to_its_licensed_text.py:1112
    _copylint_report       NAMED BY NOTHING. Verified:
                           grep -rn "_copylint_report" tests/   ->  0 hits

So the gap is specific. There are tests that drive `_refuse_copylint` with real
copy and watch it refuse. There is **no** test that proves the refusal reads
`_copylint_report`'s verdict, and none that proves `_copylint_report` is
reached on both of its two call paths.

### The two call paths, both of which matter

    src/bisonfactory.py:123   _refuse_copylint(plan, recs, report)
                              -> _copylint_report at line 700, LIVE path,
                                 before the first provider call of any kind
    src/bisonfactory.py:177   report["copylint"] = _copylint_report(plan, recs)
                              -> the DRY RUN fill-in

The comment at lines 115-122 records why the dry-run path is load-bearing: the
dry-run return once sat **above** the refusal, so `live=False` skipped the
refusal while the lint still ran and wrote a verdict onto the report that
stopped nothing. A dry run could report `refused: true` and be read as a pass
by anything that only checked whether it raised. That defect is fixed in the
code and **unprotected by any test**.

## THE QUESTION

Write `tests/test_the_copylint_verdict_is_what_refuses_the_push.py` proving all
five of the following. Each must go RED under a stated mutation.

1. **The verdict drives the refusal.** Stub `_copylint_report` to return a
   refusing report. `_refuse_copylint` must raise `FactoryRefused`. Stub it to
   return a passing report over the SAME plan and recs, and it must not raise.
   One fixture, two stubbed verdicts, opposite outcomes - that is what proves
   the dependency rather than a coincidence of the fixture's copy.

2. **THE STUB WAS ACTUALLY CALLED.** Assert the call count is >= 1 before you
   conclude anything from the outcome. See THE TRAP - this is the single most
   important assertion in the file and the reason the task exists.

3. **The structured verdict travels with the refusal.** `_refuse_copylint`
   passes `report=report` to `FactoryRefused` precisely so that which rule
   fired against which lead is answerable from the report and not from the
   message text. Assert on the exception's `report["copylint"]`, which must be
   the object `_copylint_report` returned. Do not assert on the message string.

4. **The dry run makes the same call with the same verdict.** Drive
   `bisonfactory` with `live=False` and prove `_copylint_report` was called and
   that a refusing verdict refuses the dry run too. `tests/test_a_dry_run_runs_the_sequence_gate.py`
   already covers the sequence gate on a dry run - read it first and do not
   duplicate it. Your addition is that the COPYLINT verdict, specifically,
   cannot be withheld because `live` is false.

5. **`steps_expected` is the plan's sequence length, not the module constant.**
   The docstring states this and gives the reason: checking a four-step push
   against a five-step target refuses every lead for a reason about the cadence
   rollout rather than about the copy. Build a plan whose `provider_sequence`
   is shorter than `copylint.STEPS_EXPECTED` and assert the returned
   `steps_expected` equals the plan's length. Then assert the fallback: an
   empty/absent `provider_sequence` falls back to `copylint.STEPS_EXPECTED`.

## THE TRAP

**`_refuse_copylint` returns `None` before it ever calls `_copylint_report`
if any lead in the plan carries `missing_copy`:**

    short = [lead for lead in plan.get("leads") or []
             if lead.get("missing_copy")]
    if short:
        return None

An incomplete batch is deliberately not asked - the docstring explains that the
refusal is better one gate down in `_ensure_leads`, which knows WHICH steps are
missing. The consequence for you: **a fixture whose leads are short of copy
makes `_refuse_copylint` a no-op, your stub never runs, nothing raises, and a
test that asserts "no refusal" passes while proving absolutely nothing.** That
is the exact failure this repository calls a correct guard nothing can call.
Hence requirement 2. Assert the call count, and assert it before you read the
outcome.

Second trap: do not assert on the text of `src/bisonfactory.py`. A test that
greps source for `_copylint_report` fails the day somebody writes a comment and
proves nothing about execution. Assert on the call count and on returned
values.

Third trap: `copylint.STEPS_EXPECTED` is a module constant. Read it, do not
hardcode its current number into an assertion - if the operator's target
cadence changes, a hardcoded 5 makes this test fail for a reason that has
nothing to do with the control.

Fourth trap: when you break the guard to prove the test goes red, **confirm the
intended test failed for the intended reason, and that a different guard did
not fire first.** `_refuse_sequence_gate` and `_refuse_missing_cta` sit
immediately below this one and will happily refuse your fixture for their own
reasons. If your red run fails on a sequence-gate refusal, you have measured
nothing about copylint.

## WHAT YOU MAY NOT DO

- **No provider calls of any kind.** No EmailBison, HeyReach, Apify, Slack.
  Reads included - assume you have no credentials. Use
  `unittest.mock.patch.object`, which is this repository's convention; see
  `tests/test_attach_leads_confirms_absence_before_raising.py` for the pattern.
- Do not change `src/copylint.py`'s rules, thresholds or constants.
- Do not widen, soften or reorder any gate to make a fixture pass. If your
  fixture cannot get past a gate, fix the fixture.
- Do not change the dry-run return position or either call site. If you believe
  one is wrong, write it under FINDINGS; do not edit it.
- Never commit copy text, an email address, a contact name, a domain or a
  profile URL. Fixtures use synthetic values.

## FILES ALLOWED

    tests/test_the_copylint_verdict_is_what_refuses_the_push.py   (new)

Touching `src/bisonfactory.py` is NOT expected. If you believe a source change
is required to make the control testable, do not make it: write the specific
change and its justification under FINDINGS and stop. An untestable control is
a finding worth more than a guess.

## FILES FORBIDDEN

    src/providers/*          config/            work/*.jsonl
    src/copylint.py          src/bisonfactory.py
    scripts/                 docs/state/

## ACCEPTANCE

**The command that proves it** - run it, read the exit code off the process,
never through a pipe:

    py -3 -m unittest tests.test_the_copylint_verdict_is_what_refuses_the_push -v

Green, with every test in the file running - a skip is not a pass. Then run the
two adjacent modules to prove you broke nothing:

    py -3 -m unittest tests.test_a_dry_run_runs_the_sequence_gate tests.test_a_dead_cta_link_is_refused -v

Record both exit codes and the name counts in your result block.

**The mutations that must go red.** Apply each to a scratch copy, run the
command, record which test names failed, then RESTORE the source and confirm
`git status` is clean:

    M1  In `_refuse_copylint`, replace the `found = _copylint_report(...)`
        verdict with a hardcoded `{"refused": False, "steps_expected": 0}`.
        -> requirement 1 and 3 must fail.
    M2  Delete the `_refuse_copylint(plan, recs, report)` call at
        src/bisonfactory.py:123.
        -> requirement 1 and 2 must fail on the live path.
    M3  Move the `if not live:` dry-run return to ABOVE the
        `_refuse_copylint` call - the historical defect, restored.
        -> requirement 4 must fail.
    M4  In `_copylint_report`, replace `expected` with
        `copylint.STEPS_EXPECTED` unconditionally.
        -> requirement 5 must fail.

A mutation that leaves every test green means the test does not test the
control, and the correct result block says so rather than reporting green.

## DELIVERABLE

One new test module; five proven requirements; four mutations each recorded
with the test names that went red and the reason each failed; both acceptance
commands' exit codes read off the process; the source tree restored and
`git status` clean. Append the result block, `git mv` the file to DONE/, commit
locally. Do not push.
