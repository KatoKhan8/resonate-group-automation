PRIORITY: P0
DEPENDS:

# TASK-221 - the exact-match safety gate still pins yesterday's shape

## WHERE THIS SITS

`tests/test_no_activation_without_an_exact_match.py` is the module that proves
activation is refused on anything less than an exact provider match. It is a
SAFETY module and it is currently RED, which means the guarantee it encodes is
unverified. That is the only reason this is P0.

Every failure is one of two known, expected categories. Nothing here is a
newly discovered defect.

**1. It pins the pre-authorization permission state.** Line ~720 asserts
`providerwrites.is_supported(EMAIL_ACTIVATE)` is False. The operator authorized
EmailBison campaign 485 activation on 2026-09-16, so `EMAIL_ACTIVATE` is now in
`SUPPORTED` **and** in `CONDITIONAL`, scoped by
`_is_the_authorized_email_campaign` to provider id 485 and canonical row
`productive-email-control-v2`.

**2. It pins the pre-threading sequence shape.** TASK-219 implemented the
production invariant that only the opener owns a subject: every step references
`{SUBJECT_1}`, follow-ups are `thread_reply: true`, and `subject_2..N` are
written EMPTY. This module's fixtures still build distinct `{SUBJECT_2}` /
`{SUBJECT_3}` and a non-threaded final step, so `_sequence_steps` now refuses
them.

Claude has already made the same two corrections in
`tests/test_compare_bison.py` and in `config/clients/demo.yaml` (which now
declares `providers.emailbison.workspace: 99` - it declared none, so the
tenancy comparison could never match and `configdiff` derived an empty
workspace).

## THE QUESTION

1. **Move every fixture to the threaded shape.** All steps reference
   `{SUBJECT_1}`; `thread_reply_pattern` is `[False, True, True]`; the final
   step's `wait_in_days` is 1, not 0 - the provider rejects 0, measured on
   campaign 485 today. Lead custom variables carry `subject_1` plus a body per
   step, with `subject_2..N` empty.
2. **Replace the two permission assertions with SCOPE assertions.** This is
   the important half. Do not simply delete them. The guarantee that replaced
   "activation is impossible" is "activation is possible for exactly one named
   campaign", and it is the stronger statement. Assert:
     - `EMAIL_ACTIVATE` is in `SUPPORTED` and in `CONDITIONAL`
     - `require_conditional_permission(EMAIL_ACTIVATE, "481", ...)` RAISES -
       481 holds 23 people with 6 to 40 historical touches each
     - `require_conditional_permission(EMAIL_ACTIVATE, "485", "wrong-row")`
       RAISES
     - `require_conditional_permission(EMAIL_ACTIVATE, "485",
       "productive-email-control-v2")` passes
3. **Every other assertion in the module stays.** The one-mutation-at-a-time
   tests - wrong subject, wrong body, wrong delay, missing lead, wrong address,
   already-activated campaign, the two channels disagreeing about expected
   status - are the reason the module exists. Each must still FAIL the
   comparison. If any of them now passes when it should fail, STOP and report
   it: that is a real regression and it outranks every fixture repair here.
4. **Run the module and report the count**, with the exit code read off the
   process.

## THE TRAP

This module's whole job is to refuse. The cheap way to make it green is to
weaken a mutation test until the comparison stops caring, and that would
convert a safety module into decoration. **Every mutation must still be
caught.** If a fixture change makes a mutation undetectable, the fixture is
wrong, not the assertion.

Second trap: do not touch `src/`. The production code is correct - TASK-219's
18 tests and TASK-215's comparator tests both pass. This is a fixture and
assertion update.

## WHAT YOU MAY NOT DO

- No provider writes. No activation. No campaign or lead changes.
- Do not modify anything under `src/`.
- Do not add to `SUPPORTED` or `CONDITIONAL`.
- Do not delete, skip or `expectedFailure` a mutation test.
- Never commit an email address, a contact name, a company name or a domain.

## FILES ALLOWED

    tests/test_no_activation_without_an_exact_match.py

## FILES FORBIDDEN

    src/   work/   config/   docs/

## DELIVERABLE

The module green, with every mutation still caught; the two permission
assertions replaced by the four scope assertions; confirmation that no
mutation test now passes when it should fail; and the test count with the exit
code read off the process.
