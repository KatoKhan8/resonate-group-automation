# Activation order: the second activation at an account is refused

2026-09-17. Tests only - no `src/` change.

## The hazard

This system stages a campaign and leaves it PAUSED. The factory does this on
purpose - a staged campaign must not send. A paused campaign's membership rows
read `sending_paused` or `stopped`, both of which are in
`EXCLUDABLE_MEMBERSHIP`. `staging_artifact_evidence`'s four arms are all
RETROSPECTIVE: "has never sent an email to anybody" is satisfied by a
campaign that is about to.

So while cohort A sits staged and paused, `check_account` on its accounts
reads CLEAR, and cohort B can be built at the same accounts. Both activate,
and two live sequences run at one account.

## What closes it today

ORDER rather than design. The moment A activates, its membership rows read
`in_sequence`, stop being excludable (because `in_sequence` is NOT in
`EXCLUDABLE_MEMBERSHIP`), and B's activation is refused by the account gate.

This is not hypothetical. Campaign 485 is a DRAFT holding the same ten leads
as the live campaign 487, and its membership rows read `stopped`.

## GLM's review and the false positive

GLM's adversarial review of `collision.check_account` on 2026-09-17 claimed
`without_our_staging` could flip an account from IN_SEQUENCE to CLEAR. That
specific claim is a FALSE POSITIVE: `_excludable` refuses any membership
status outside `EXCLUDABLE_MEMBERSHIP = frozenset({'sending_paused',
'stopped'})`, so a row reading `in_sequence` can never be dropped. See
`docs/GLM-REVIEW-COLLISION-2026-09-17.md`, including the CLAUDE VERIFICATION
section.

The ADJACENT hazard - two paused campaigns, both excluded, both later
activated - is real, and that is what these tests pin.

## The tests

`tests/test_the_second_activation_at_an_account_is_refused.py`

Eight tests in one class, covering four assertions:

1. **The exclusion happens.** With both campaigns staged and paused and zero
   sends, `check_account` returns CLEAR and `our_staging_excluded` names both
   campaigns.

2. **The window is real.** In that state, `account_policy` returns ALLOW - a
   second cohort at the same account passes the gate.

3. **The second activation is refused.** Activate A (its membership rows
   change to `in_sequence`); `check_account` now reads IN_SEQUENCE → STOP.
   The mirror: activate B first, A is refused.

4. **The break-proof.** Add `in_sequence` to `EXCLUDABLE_MEMBERSHIP` by hand.
   The test in (3) goes RED: the account reads CLEAR/ALLOW instead of
   IN_SEQUENCE/STOP, and both campaigns' rows are excluded. The constant is
   restored in a `finally` block and a separate test confirms it.

## Break-proof failure text

With `in_sequence` added to `EXCLUDABLE_MEMBERSHIP`, after A's activation:

    verdict=clear              (should be in_sequence)
    anyone_in_sequence=False   (should be True)
    decision=allow             (should be stop)
    excluded=[campaign 600 (in_sequence), campaign 601 (stopped)]

Both campaigns' rows are excluded, including A's `in_sequence` row. The
account reads CLEAR and both cohorts could activate, producing double sends.

## What is NOT asserted

These tests do not assert the full activation path through
`executionguard.authorize()` or `bisonfactory._refuse_colliding_leads`. They
assert the collision module's account-level verdict, which is what those
callers consult. The account gate's refusal is a property of
`check_account` + `account_policy`, not of the activation machinery.

## Files

    tests/test_the_second_activation_at_an_account_is_refused.py   (new)
    docs/ACTIVATION-ORDER-2026-09-17.md                            (this file)
