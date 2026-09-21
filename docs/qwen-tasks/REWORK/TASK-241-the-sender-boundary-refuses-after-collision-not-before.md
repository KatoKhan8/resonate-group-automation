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

---

## RESULT OF RUN r56 — READ BY CLAUDE 2026-09-21T17:45Z — REWORK, NOT MERGED

Qwen's commit `fae90efc` on `qwen-worker`. Suite `work/suite-r56.err`,
started 17:18:59Z, finished ~17:44Z, 1514.5s.

    baseline r53   10,671 tests   50 failures   33 errors
    r56            10,707 tests   51 failures   35 errors

**THE FEATURE'S OWN ACCEPTANCE TEST PASSED.**
`test_ATTACK_client_a_record_with_client_b_seat_is_refused` failed in r55 and
is GREEN in r56. The spec file is untouched. That is the thing this task was
sent back for and Qwen got it right.

Diffed by test name, both directions. Nothing that passed in r53 fails in r56.
Three names are new, and **none of the three is attributable to this branch**:

    ERROR test_xai_has_no_caller_in_src
          test_waterfall_order.TestXaiOffByDefault
          CAUSE: environmental. The test shells out to `grep` via
          subprocess and CreateProcess failed - grep was not on PATH for
          the shell that launched r56. Carved out by this brief already.

    FAIL  test_no_linkedin_url_with_real_vanity_name
          test_fixture_hygiene.TestNoRealDataAnywhereInGit
          hit: docs/GROK-CONVERSATION-ATTRIBUTION-2026-09-21.md
          CAUSE: worktree staleness, not a leak. Master redacted that
          placeholder and wrote the reasoning into the doc itself; the
          worktree still holds the 13:47 copy. A rebase clears it.
          Carved out by this brief already.

    ERROR test_the_demo_form_cannot_consume_an_invitation
          test_production_auth.AnInvitationBecomesAccessOnlyThroughGoogle
          NEW in r56, not present in r55. urllib transport error against
          the test's own loopback server.
          CAUSE: order-dependent, not a regression. Claude re-ran the
          whole class in the same worktree at 17:5xZ: **7 tests, OK,
          2.326s.** A `python -m src.web --demo` server (pid 108672) is
          live on this machine and the suite runs the web tests against
          real ephemeral ports.

**SO WHY IS THIS NOT MERGED.** The acceptance is a number and the number is
not zero. The rule in the handoff is mechanical on purpose - this register
records six separate occasions where a value that "obviously" did not matter
did. A diagnosis is not a green suite, and the merge is worth twenty-five
minutes.

## REWORK — one action, no code changes expected

1. `git fetch origin && git rebase origin/master` on `qwen-worker`. That
   picks up the redacted doc.
2. Re-run from a shell where `grep` resolves (Git Bash on PATH, or run the
   suite from `C:\Program Files\Git\bin` prepended), so the xai test can
   shell out.
3. `py -3 -m tests.offline`, read the exit code off the process.
4. Report the diff by test name, both directions, against 10,671 / 50 / 33.

**DO NOT EDIT ANY TEST TO GO GREEN**, including the three above, and do not
touch `src/executionguard.py` again unless the rebase conflicts. If a name
still appears after the rebase, say so and stop - it is then a real finding
and Claude will triage it.

Batch 1 runs tonight on the single-mailbox branch - 8 campaigns, one mailbox
each, 120 first-step sends a day - because this did not merge in time.
Wave 2 re-points to all attested mailboxes the moment it does.
