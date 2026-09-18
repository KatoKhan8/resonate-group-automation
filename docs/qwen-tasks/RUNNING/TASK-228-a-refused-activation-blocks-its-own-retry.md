# TASK-228 - a refused activation blocks its own retry

PRODUCT-GAPS.md gap 44. Measured 2026-09-18 on EmailBison campaign 489, and
previously on HeyReach campaign 605487. Two channels, same defect.

## The defect

`executionguard.authorize` RESERVES a ledger key while its gates run. The
killswitch is gate 7 and its own comment says it is last "so that a killswitch
refusal does not leave a reservation behind". It is last, and a reservation is
left behind anyway, because the reservation is taken DURING the run rather
than after all seven gates pass.

The second-order effect is what makes it serious:

    run 1   5 authorized, refused at gate 7 (killswitch), 0 emails sent,
            5 ledger keys left at `attempted`
    run 2   0 authorized, refused at gate 3 (collision), on run 1's own rows

`collision.staging_artifact_evidence` proves a campaign is our own silent
staging on four arms. The fourth is "the action ledger records no unrefuted
prospect-facing action against this canonical campaign". Five unrefuted
`attempted` rows is not silence, so the campaign stopped qualifying, its leads
stopped being excluded from their own collision history, and every contact
read TOUCHED - "loaded as a lead, nothing sent yet" - against the campaign
that had just loaded them.

**So the first refused activation of any campaign makes the second attempt
refuse for a different and more alarming reason.**

## The objective

A refusal must not leave a reservation behind. Either reserve after every gate
passes, or release the reservation when a later gate refuses.

Falsifiable requirements:

1. `executionguard.authorize` that raises `NotAuthorized` at ANY gate leaves
   the action ledger exactly as it found it. Prove it by asserting the
   ledger's unsettled set is byte-identical before and after a refusal at
   gate 7 specifically, and at one earlier gate.
2. A SUCCESSFUL authorize still reserves exactly as it does today. The
   reservation is what stops two concurrent authorizations spending the same
   `new_accounts_per_day` slot, so this must not become "reserve nothing".
3. **The race must be considered explicitly and the choice documented.**
   Reserving only after all gates pass widens the window in which two callers
   can both pass gate 6 and both reserve. Say in a comment which of the two
   shapes you chose - reserve-late, or reserve-then-release - and why, and
   what the remaining window is. Do not leave it implied.
4. The existing settlement scripts keep working and keep their meaning:
   `settle_abandoned_email_attempts.py` and
   `settle_abandoned_linkedin_attempts.py` settle ABANDONED against provider
   truth. They become a recovery path for history rather than a routine step;
   do not delete them.
5. `reserve=False` callers are unchanged.

## Tests required

A refusal at gate 7 leaves no ledger row. A refusal at an earlier gate leaves
no ledger row. A success reserves one. Two sequential authorizations for the
same contact behave as they do today. Break-proof it: reintroduce the early
reservation and confirm the gate-7 test fails, and fails for that reason
rather than another.

## Boundaries

NO PROVIDER WRITE. NO CREDIT SPEND. Tests use fakes and fixtures.

This is a change to the LAST-WORD GATE. Do not relax any gate, do not reorder
the gates themselves, and do not change what any of them checks. The only
thing moving is WHEN the reservation is taken. If you find yourself editing a
gate's condition, stop and report instead.
