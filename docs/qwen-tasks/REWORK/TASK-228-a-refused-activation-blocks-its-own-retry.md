# TASK-228 - REJECTED, because the task itself named the wrong defect

Branch `staged-paused-activation-order-2026-09-17`, tip `e577b9e8`.
**NOT INTEGRATED.** The work is careful and the reasoning in it is good. It
fixes something that was not broken, because I briefed it wrongly.

## What I told the worker, and why it was false

The task said `executionguard.authorize` reserves a ledger key while its gates
run, so a killswitch refusal at gate 7 leaves a reservation behind, and that
the comment claiming otherwise was wrong.

**The comment was right.** On master, `actionledger.reserve` is reached only
after `gates.append("killswitch")`. Gate 6 is `require_clear`, a CHECK that
writes nothing. A killswitch refusal raises before any ledger write.

The worker's own diff shows this: it relabels gate 6 and adds documentation,
and the reservation is in the same place afterwards as before. The change is a
behavioural no-op that asserts a false history in its comments - which is
worse than no change, because the next reader would believe it.

## The measurement I should have made first

The session's own record disproves the brief without reading any code:

    run A   5 contacts REFUSED at gate 7 (killswitch)
    run B   5 contacts AUTHORIZED
    run C   0 contacts authorized, REFUSED at gate 3 (collision)

If run A had left reservations, run B could not have authorized anybody - gate
6 refuses an unsettled retry, which is exactly what run C hit. Run B
succeeding is the proof, and it was in front of me when I wrote the task.

I inferred the mechanism from the symptom and briefed the inference as fact.
The worker then had no reason to question it, and its explorer agent
"confirmed my findings independently" - confirming the brief rather than the
code.

## What the real defect is

**An authorization that is minted and never used leaves a reservation, and
nothing settles it automatically.** Run B authorized all five and each
correctly reserved; then `providerwrites.perform` raised `no transport
supplied` - a caller bug - so nothing reached the provider and nothing settled
the keys. PRODUCT-GAPS.md 44 carries the corrected account.

The all-or-nothing activation shape makes it routine rather than rare: one
authorization per contact, abort if any refuses, and every one minted before
the refusal has already reserved. HeyReach 605487 hit exactly that, which is
why `settle_abandoned_linkedin_attempts.py` already existed.

## What is worth keeping

The reserve-late versus reserve-then-release analysis in the worker's module
docstring is genuinely useful and its conclusion is correct - reserve-late is
what the code already does, for the reason the worker gives. If a future task
touches this ordering, read `e577b9e8` first rather than re-deriving it.

## The re-scoped task

Not "move the reservation". The reservation is where it belongs. The question
is how a caller says "I am not going to use this", and who says it:

- an authorization context manager that settles ABANDONED on the exception
  path, so a caller cannot forget
- a sweep settling any `attempted` key older than N minutes whose campaign
  provider truth proves silent - the settlement scripts generalised
- `perform` settling the key it was handed when it refuses before reaching the
  transport, which covers the measured case but not the all-or-nothing one

An eager release is NOT acceptable on its own: an authorization is a claim on
`new_accounts_per_day`, so releasing it the moment a caller wanders off would
let two callers authorize the same last slot.
