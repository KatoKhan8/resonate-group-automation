PRIORITY: P0
DEPENDS:
TIMEBOX: 90 minutes. If you are not green at 90, write what you measured
under FINDINGS, commit, move the file to REVIEW/ and stop.

# TASK-1013 - never attach a lead whose copy is not already on it

## WHERE THIS SITS

The second of the four Tier 1/2 controls that no test names.
`resonate-ops/control-inventory-2026-10-14/TIER-1-2.json`:

    control:        bisonfactory._refuse_unvariabled_leads
    where:          src/bisonfactory.py:2589
    tier:           1
    callers_src:    1
    hops_to_sink:   3
    raises:         FactoryRefused
    claims:         "NEVER ATTACH A LEAD WHOSE COPY IS NOT ALREADY ON IT."
    test_asserts_it_fires: "NEVER - no test names it"

Verified today: `grep -rn "_refuse_unvariabled_leads" tests/` returns **0 hits**.

**This is the structural half of the 2026-09-23 blank-email incident fix**
(operator decision, same date). 77 emails with an empty subject and a `<p></p>`
body reached real prospects. The mechanism: a lead was attached to a campaign
before its `custom_variables` were on it, the sequence template rendered
against nothing, and the provider sent the empty result. The fix is an ordering
invariant - **set the variables, READ THE LEAD BACK FROM THE PROVIDER, and only
then attach.**

It is called once, from `_ensure_leads` at src/bisonfactory.py:2534, immediately
after `_remember_leads` and immediately before the fresh re-read of campaign
status that precedes the attach.

### What already has coverage, and what does not

`tests/test_a_blank_email_can_never_be_sent_again.py` is a large module about
the same incident. **It does not cover this control.** It covers
`emptyrender.classify_body` - the four blank shapes, the threaded exemption -
and the scan that splits what can still send from what cannot. Read it, reuse
its vocabulary, and do not duplicate it.

The uncovered property is different and is about ORDER and about READING THE
PROVIDER: that no lead reaches an attach unless a provider readback has
confirmed its copy is on it.

## THE QUESTION

Write `tests/test_a_lead_is_never_attached_without_its_copy.py` proving all six
of the following. Each must go RED under a stated mutation.

1. **A variable that did not take refuses the push.** The provider readback
   returns variables that disagree with what `_variables_for` wants for that
   lead. `FactoryRefused` must be raised. This is the exact failure the
   docstring names: *"the write we are guarding against is one where our PATCH
   was accepted and did not take, and our own copy of what we sent cannot see
   that."*

2. **THE PROVIDER WAS ACTUALLY READ.** Assert `bison.lead` /
   `bison.variables_of` were called, and called with the lead ids staged by
   this run. A test that passes without the readback happening proves the
   opposite of the invariant. Assert this before you read the outcome.

3. **An empty body refuses, by the queue's own predicate.** The function does
   not use a truthiness check - it calls `emptyrender.classify_body`, because
   truthiness is what let the literal string `'None'` through. Prove at least
   the empty body and the literal `'None'` are each refused, and that the
   refusal names `body_1 is <fault>`. The faults themselves belong to
   `emptyrender` and are already tested; what you are proving is that THIS
   function consults that predicate rather than a truthiness test.

4. **A lead not staged by this run is named, not passed.** When `lead_id` is
   absent from `wanted_by_id` the function appends
   `(lead_id, "not staged by this run")` rather than skipping it, on the stated
   principle that *"we did not look" is not "it is fine"*. Prove that such a
   lead causes a refusal and is named in it. **This is the single most
   valuable requirement in the file**: it is the one a future "optimisation"
   would delete, because skipping it looks harmless.

5. **The count on the report is the verified count, not the staged count.**
   `report["provider"]["leads_variable_verified"]` must equal
   `len(ids) - len(unverified)`. Prove it on a clean batch (equals `len(ids)`)
   and on a mixed batch (strictly less). A report that always says "all
   verified" is how a blind spot is read as health.

6. **The clean batch does not raise, and the invariant holds over ALL ids.**
   The docstring states that `ids` is assembled from three paths - remembered,
   created, adopted - and that the property is about what goes on the wire, not
   about which branch put it there. Build a batch containing ids from more than
   one of those origins and prove one consistent verdict over all of them.

## THE TRAP

**The refusal leaves leads created and unattached, and that is correct.** The
docstring says so explicitly, "stated so nobody 'fixes' it": an unattached lead
sends nothing to anybody, while an attached one is in a campaign's queue within
the minute. Do not write a test that asserts cleanup, and do not add cleanup.

Second trap, and it is the one that will cost you time: **`emptyrender` is
imported INSIDE the function** (`from . import emptyrender`, first line of the
body). Patching `bisonfactory.emptyrender` at module level will not work the
way you expect. Patch `src.emptyrender.classify_body` at its own module, or
drive it with real values and let the real predicate run - the latter is better
here, because requirement 3 is about which predicate is consulted, and a real
`classify_body` over a real empty body proves it without a mock.

Third trap: the per-lead comparison `break`s on the FIRST disagreeing variable
and the body check sits in the loop's `else` clause - so a lead whose variables
disagree is never body-checked. Do not write a test expecting both faults
reported for one lead. Read the control flow before you write the assertion.

Fourth trap: the read is per lead TOUCHED this run, not per lead in the
campaign - *"a 300-lead re-stage does not pay 300 GETs"*. Do not assert a GET
per campaign member, and do not "fix" the function to read them all.

Fifth trap: when you break the guard to prove red, confirm the intended test
failed for the intended reason. `_ensure_leads` has several refusals around
this call; if your red run fails on the campaign-status re-read that follows at
line 2535ff, you have measured nothing about this control.

## WHAT YOU MAY NOT DO

- **No provider calls of any kind.** No EmailBison, HeyReach, Apify, Slack.
  Reads included - assume you have no credentials. `unittest.mock.patch.object`
  against `bison` is the convention; see
  `tests/test_attach_leads_confirms_absence_before_raising.py`.
- Do not change the order of operations in `_ensure_leads`. The ordering IS the
  control.
- Do not change `src/emptyrender.py`.
- Do not weaken the refusal, narrow the "not staged by this run" case, or make
  any check conditional on a flag.
- Never commit copy text, an email address, a contact name, a domain or a
  profile URL. Fixtures use synthetic values.

## FILES ALLOWED

    tests/test_a_lead_is_never_attached_without_its_copy.py   (new)

Touching `src/bisonfactory.py` is NOT expected. If you believe a source change
is required to make the control testable, do not make it: write the specific
change and its justification under FINDINGS and stop.

## FILES FORBIDDEN

    src/providers/*          config/            work/*.jsonl
    src/bisonfactory.py      src/emptyrender.py
    scripts/                 docs/state/

## ACCEPTANCE

**The command that proves it** - run it, read the exit code off the process,
never through a pipe:

    py -3 -m unittest tests.test_a_lead_is_never_attached_without_its_copy -v

Green, with every test running - a skip is not a pass. Then prove you broke
nothing adjacent:

    py -3 -m unittest tests.test_a_blank_email_can_never_be_sent_again tests.test_attach_leads_confirms_absence_before_raising -v

Record both exit codes and the name counts in your result block.

**The mutations that must go red.** Apply each to a scratch copy, run the
command, record which test names failed, then RESTORE the source and confirm
`git status` is clean:

    M1  Delete the `_refuse_unvariabled_leads(...)` call at
        src/bisonfactory.py:2534.
        -> requirements 1, 2, 4 and 5 must fail.
    M2  In the per-lead loop, replace the `unverified.append(...)` for a
        disagreeing variable with `pass`.
        -> requirement 1 must fail.
    M3  Replace the `lead is None` branch's append with `continue`
        - the "optimisation" requirement 4 exists to catch.
        -> requirement 4 must fail, and ONLY requirement 4.
    M4  Replace the `emptyrender.classify_body(body)` call with a truthiness
        check `fault = None if body else "empty"` - the pre-incident
        behaviour that let `'None'` through.
        -> requirement 3 must fail on the literal `'None'` case and pass on
           the empty case. Record both; the split is the measurement.
    M5  Set `leads_variable_verified` to `len(ids)` unconditionally.
        -> requirement 5 must fail on the mixed batch.

M3 failing ONLY requirement 4 is itself a result worth recording: it shows the
other requirements do not accidentally cover it, which is why that case needs
its own test.

A mutation that leaves every test green means the test does not test the
control, and the correct result block says so rather than reporting green.

## DELIVERABLE

One new test module; six proven requirements; five mutations each recorded with
the test names that went red and the reason each failed; both acceptance
commands' exit codes read off the process; the source tree restored and
`git status` clean. Append the result block, `git mv` the file to DONE/, commit
locally. Do not push.
