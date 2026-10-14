PRIORITY: P0
DEPENDS:
TIMEBOX: 60 minutes - the smallest of the three control tasks. If you are not
green at 60, write what you measured under FINDINGS, commit, move the file to
REVIEW/ and stop.

# TASK-1014 - the entry point that "every entry point" missed

## WHERE THIS SITS

The third of the four Tier 1/2 controls that no test names.
`resonate-ops/control-inventory-2026-10-14/TIER-1-2.json`:

    control:        run.stage_push
    where:          src/run.py:359
    tier:           1
    callers_src:    1
    hops_to_sink:   1
    claims:         "Preparation only. `live` is refused by push.py, deliberately."
    raises_or_returns: propagates a refusal from a control it calls
    test_asserts_it_fires: "NEVER - no test names it"

Verified today: `grep -rn "stage_push" tests/` returns **0 hits**.

### The anchor, and it is a good one

`tests/test_invariants.py:463` is named

    test_live_push_is_refused_at_every_entry_point

and it asserts exactly two:

    push.run(day=1, live=True)   -> LiveSendNotEnabled
    run.run(live=True)           -> LiveSendNotEnabled

**There are three, and the one it omits is this Tier 1 control.** The name
claims a completeness the body does not have. That is the finding this task
closes.

The three independent refusals of `live`, measured:

    src/push.py:495    push.run(live=True)        the innermost
    src/run.py:362     run.stage_push(live=True)  THIS ONE - untested
    src/run.py:387     run.run(live=True)         the outermost

## STATE THE PROPERTY HONESTLY - READ THIS BEFORE YOU WRITE AN ASSERTION

The inventory row says this control `sits_in_front_of` "push.run - the send
path - sends when live=True". **That label comes from a reverse call graph and
it overstates what this build can do.** `src/push.py` says, and
`test_invariants.test_the_push_module_cannot_reach_the_transport` proves, that
there is no HTTP call to EmailBison or HeyReach anywhere in it. Worse for the
scary reading: `stage_push` calls `push.run(day=day)` and **does not pass
`live` through at all**, so even with this guard deleted, `push.run` would run
with its default `live=False`.

So do **not** write a test, a docstring or a result block claiming this guard
prevents a send. It does not; three separate things prevent that.

**The property that is real, and worth a Tier 1 test:** a caller who asks for
`live=True` must receive a loud refusal, and must never receive a silently
successful dry run reported as a push. The danger here is not a send - it is a
**false success**: `live` requested, dry run performed, counts returned, and
the report read as "the push stage ran". That is the defect class `CLAUDE.md`
names as a silent fallback on a safety path.

## THE QUESTION

Write `tests/test_the_runner_refuses_live_at_the_third_entry_point.py` proving
all six of the following. Each must go RED under a stated mutation.

1. **It raises, and it raises the exact class.** `stage_push(recs, day, live=True,
   notes)` must raise `push.LiveSendNotEnabled`. Assert the class exactly, not
   `Exception` and not `RuntimeError` - `LiveSendNotEnabled` subclasses
   `RuntimeError`, so a loose assertion cannot tell the designed refusal from an
   incidental crash.

2. **The refusal PROPAGATES and is not converted into a return value.** This is
   the most important requirement in the file; see THE TRAP. Assert that the
   call raises - and additionally assert that `notes` is still **empty** and
   that no value was returned. The guard sits ABOVE the `try` deliberately;
   inside it, the function's own `except Exception` would swallow the refusal,
   append a note and return `{"error": ...}`.

3. **`push.run` was never called - a measured zero, not an assumed one.** Patch
   `push.run` with a counter. Assert it is 0 after the live refusal. Then, in
   the same test, call `stage_push(..., live=False)` and assert the counter
   becomes 1. *A zero and a wrong lookup look identical from outside* - the
   increment is what proves your counter was watching the right function.

4. **Nothing was written.** Assert `store.transaction` and
   `push.record_prepared` were not reached on the live path. A refusal that
   still opened a write transaction is not a refusal.

5. **All three entry points refuse, and they are independent.** Assert the
   refusal at each of `push.run(live=True)`, `run.stage_push(live=True)` and
   `run.run(live=True)`. Do not delete or edit
   `test_invariants.test_live_push_is_refused_at_every_entry_point`; your
   module is where the complete claim now lives. Mutation M4 proves the three
   are genuinely independent rather than one guard observed three times.

6. **The dry-run path still works.** `live=False` must return a dict carrying
   `email`, `linkedin` and `skipped`. Without this, a guard that refused
   everything would pass requirements 1-5 and you would have proved nothing
   about the control's precision.

## THE TRAP

**`except Exception` on line 371 catches `LiveSendNotEnabled`.** It is a
`RuntimeError`. The guard is correct only because it sits above the `try`. So:

    a test asserting `result["error"]` contains "LiveSendNotEnabled"
    PASSES on the broken version and PASSES on the correct version
    -> it measures nothing

Assert that the call **raises**. If your test can pass against a `stage_push`
that returns an error dict instead of raising, your test is the defect.

Second trap: `run.run(live=True)` refuses at src/run.py:387, before `stage_push`
is ever reached - the lambda at src/run.py:490 is downstream of that guard. So
driving this control through `run.run` proves the OUTER barrier and nothing
about this one. **Call `stage_push` directly.** It is a module-level function;
import it and call it.

Third trap: on the real path `stage_push` never sees `live=True`, because
`run.run` refused first. That makes this defence in depth, not dead code - the
value is that a future caller, or a future removal of the outer guard, cannot
turn a live request into a silent dry run. Do not report it as unreachable and
skip it.

Fourth trap: `store.transaction()` writes to `work/*.jsonl`. Use this
repository's test isolation - see `tests/base.py` and
`tests/envisolation.py` - and do not let a test touch the production queue. If
your test writes a row into `work/`, that is a defect in the test, not a pass.

Fifth trap: do not assert on the text of `src/run.py`. `test_invariants` has
one deliberate source-text check with a stated reason; this is not one.
Assert on raised classes, call counters and returned values.

## WHAT YOU MAY NOT DO

- **No provider calls of any kind.** Assume you have no credentials.
- Do not move, reorder or soften any of the three `live` guards. If you believe
  the docstring at src/run.py:360 misdescribes the refusal - it says `live` is
  "refused by push.py", while `stage_push` in fact refuses it itself before
  push.py is reached - that is a **documentation finding**. Write it under
  FINDINGS with the file:line. Do not edit the docstring.
- Do not edit `tests/test_invariants.py`.
- Do not add anything to `work/`.
- Never commit copy text, an email address, a contact name or a domain.

## FILES ALLOWED

    tests/test_the_runner_refuses_live_at_the_third_entry_point.py   (new)

## FILES FORBIDDEN

    src/providers/*          config/            work/*.jsonl
    src/run.py               src/push.py        src/store.py
    tests/test_invariants.py
    scripts/                 docs/state/

## ACCEPTANCE

**The command that proves it** - run it, read the exit code off the process,
never through a pipe:

    py -3 -m unittest tests.test_the_runner_refuses_live_at_the_third_entry_point -v

Green, with every test running - a skip is not a pass. Then prove you broke
nothing adjacent:

    py -3 -m unittest tests.test_invariants tests.test_push tests.test_orchestration -v

Record both exit codes and the name counts in your result block.

**The mutations that must go red.** Apply each to a scratch copy, run the
command, record which test names failed, then RESTORE the source and confirm
`git status` is clean:

    M1  Delete the `if live: raise ...` block at src/run.py:361-363.
        -> requirements 1, 2, 3 and 4 must fail. ALSO RECORD what
           `stage_push(live=True)` returns instead: a live request answered
           with dry-run counts is the false success this control prevents,
           and naming it in your result block is part of the deliverable.
    M2  Move that same block INSIDE the `try`, as its first statement.
        -> requirements 1 and 2 must fail, because the refusal becomes
           `{"error": ...}` plus a note. If your tests stay green here,
           your tests assert the wrong thing - say so and fix them.
    M3  Change the raise to a bare `RuntimeError` with the same message.
        -> requirement 1 must fail. Record whether anything else did; if a
           loose assertion let it through, tighten it.
    M4  Delete `run.run`'s own guard at src/run.py:386-388, leaving
        `stage_push`'s intact.
        -> requirement 5's `run.run` assertion must fail while requirements
           1-4 stay GREEN. That split is the proof the barriers are
           independent, and it is the measurement this mutation exists for.

A mutation that leaves every test green means the test does not test the
control, and the correct result block says so rather than reporting green.

## DELIVERABLE

One new test module; six proven requirements; four mutations each recorded with
the test names that went red and the reason each failed; the M1 false-success
return value written down verbatim; both acceptance commands' exit codes read
off the process; the source tree restored and `git status` clean. Append the
result block, `git mv` the file to DONE/, commit locally. Do not push.
