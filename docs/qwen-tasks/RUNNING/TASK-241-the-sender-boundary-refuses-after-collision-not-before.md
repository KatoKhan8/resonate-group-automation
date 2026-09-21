# TASK-241 · The sender boundary must refuse AFTER collision, not before

PRIORITY: P0
DEPENDS:
OWNER: qwen
CHANNEL: both

## THIS IS REWORK OF YOUR OWN TASK-240, AND THE SECURITY PROPERTY IS INTACT

TASK-240 (`8f4406e1`) moved the arity rule from the campaign to the action and
did it well: 89 tests green, the design's own acceptance measure satisfied -
`test_a_seat_with_no_human_owner_still_passes` is gone and
`..._is_refused` replaces it. **It is not merged, and the reason is one test
in a file your brief never named.** That is a gap in the brief, not
carelessness on your part.

    tests/test_the_second_client_runs_on_the_same_engine.py:595
    test_ATTACK_client_a_record_with_client_b_seat_is_refused

    AssertionError: 'collision' not found in ()

## WHAT IS AND IS NOT BROKEN - checked, not assumed

**The cross-tenant attack is still REFUSED.** `refused_at("sender", ...)`
succeeds, the refusal still names seat 800 and client A, the other 51 tests in
that file pass, and the whole 78-test gate suite is green, so collision still
runs. Nothing is weaker in outcome.

What changed is ORDER. The new predicate refuses EARLIER in the gate
sequence, so `why.passed` is empty where it used to contain `collision`. The
test's own comment says why that matters:

    # And the gates that ran before it did pass, so this is the sender
    # boundary refusing rather than an earlier accident.

With `passed` empty, that distinction is no longer observable. An operator
reading a refusal cannot tell the sender boundary caught it from an earlier
gate accidentally catching it first - and on a CROSS-TENANT refusal that is
exactly the distinction worth having.

## WHAT TO DO

Restore the ordering so the sender-boundary refusal happens **after** collision
has passed, exactly as the test asserts.

**THE TEST IS THE SPEC. DO NOT EDIT IT.** Not the assertion, not the name, not
the fixture. If you believe the test is wrong, stop and write why in your
result block instead of changing it - a cross-tenant security test edited to
go green is the single worst outcome available here, and it is worth more to
this project than the feature is.

Keep everything TASK-240 got right: the predicate itself, the two changed
tests in `test_no_write_happens_without_every_gate.py`, and all four
preserved protections (uninventoried, deactivated, unhealthy, another
client's seat).

## ACCEPTANCE - a number, not an opinion

Run the FULL offline suite and diff the failure set against the current
master baseline:

    baseline   10,671 tests   50 failures   33 errors
    yours      must add ZERO new failures and ZERO new errors

Report the diff explicitly, by test name, both directions. `py -3 -m
tests.offline`, and read the exit code off the process rather than through a
pipe. The suite takes about 25 minutes; start it before you start writing
your result block.

Three tests were new in the last arity run. One is this one. The other two -
`test_xai_has_no_caller_in_src` and `test_no_linkedin_url_with_real_vanity_name`
- are being triaged separately and are NOT yours to fix; if they still appear,
say so and leave them.

## FILES ALLOWED

    src/executionguard.py
    tests/test_task240_*.py      only to add coverage of the ORDER
    tests/test_task241_*.py      new

## FILES FORBIDDEN

    tests/test_the_second_client_runs_on_the_same_engine.py   ← THE SPEC
    src/providerwrites.py   src/providers/*   config/

## WHY THE CLOCK MATTERS

Until this merges, batch 1 runs on the single-mailbox branch of the
authorization: 8 campaigns, one mailbox each, 15 first-step sends per mailbox
per day - **120 a day.** Merged, each campaign names all of its human's
attested connected mailboxes and the same 8 campaigns carry thousands.
Target is merged before 09:00 Zagreb tomorrow so wave 2 runs multi-mailbox.
That is a reason to be quick, and not a reason to be loose.
