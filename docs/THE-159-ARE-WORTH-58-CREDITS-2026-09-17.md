# The 159 unverified contacts are worth 58 credits, not 318, and not today

2026-09-17. Computed live from `store.load()` by
`scripts/verification_inventory.py`. Every number TASK-194 and TASK-203 argued
about came from `work/queue.snapshot.jsonl`, which was retired the same day.

## The estate, live

    277 contacts on 550 records

     68  SENDABLE        policy says the address may be written to
     13  HELD            a provider answered; policy is not satisfied
    159  NEVER_OFFERED   nothing ever asked a provider
     37  NO_ADDRESS

TASK-203's 159 survives contact with live state exactly. Its explanation does
too: 157 of the 159 sit on records whose `persona_plan.cap_reason` reads
`tier C allows up to 1 contact(s)`, and 151 are on a record holding more
contacts than its own cap. Nineteen are different - their record has no
`email_verification` row in its waterfall at all, so the stage never ran over
them rather than passing them over.

## The number that changes the decision

The 159 contacts sit on **32 records**. Not 159 accounts - thirty-two.

    32   records hold at least one NEVER_OFFERED contact
    19   of those ALREADY have a sendable contact
    13   have none

Verifying all 159 costs an expected **318 credits** and can add **at most 13
accounts** to the addressable pool, because the other 19 records are already
addressable and the account gate lets one person at an account be worked at a
time regardless.

The 29 never-offered contacts on those 13 account-less records cost an
expected **58 credits** and carry **the entire account-level upside**. 18% of
the spend, 100% of the new accounts. Twenty-seven of the twenty-nine are on
records in state `held`, so 13 is an upper bound and the realistic figure is
lower.

## And none of it converts today, for a reason the code states out loud

`required_confirmations: 2` with `primary: contactout`, `secondary:
deliverable`, `catch_all: reoon`. **The Deliverable leg is closed**, and not
by accident:

    deliverable.result_shape_confirmed()
    "ONLY the operator's environment variable answers this ... Opening it
     admits the whole verification waterfall for 159 contacts with no
     evidence, at up to three credits each - which is the spend the gate
     exists to make somebody choose."

TASK-196 once changed that function to return True whenever a constant in the
same file was populated - which is always. That was the gate opening itself,
and it was reverted on 2026-09-16.

So with Deliverable refused before any network call, ContactOut can supply at
most ONE of the two required confirmations for any address that is not a
catch-all. Spending 159 ContactOut credits today would move 159 contacts from
NEVER_OFFERED to HELD and produce **zero** newly sendable addresses. That is
not a reason to relax `required_confirmations`; it is the rule that keeps this
system from mailing an address nobody confirmed, and TASK-196 measured that
relaxing it to 1 would admit three more contacts. Three.

## So verification is not the bottleneck, and the arithmetic says so plainly

    91  records hold any contact at all
    67  already have a SENDABLE contact - one each, bar a single record with two
    13  of those 67 are LIVE right now
    17  contacts pass every gate except approval

**Sixty-seven accounts are already verified and addressable. Seventeen are
approvable. Thirteen are live.** The estate's ceiling is not the verified
pool; the verified pool is nearly five times what the approval queue can pass.
Buying thirteen more accounts - the best case, for 58 credits, behind a vendor
decision - would change nothing about what can be made live this week.

See `docs/SEVENTEEN-AND-ONE-SIGNATURE-2026-09-17.md`.

## What an operator is actually being asked, when they are asked

Not "should we spend 318 credits". Three separate questions, and only the
first is urgent:

1. **Approve some of the seventeen.** Costs nothing, converts people this
   week, and is the only thing that does.
2. **Open the Deliverable leg** (`DELIVERABLE_RESULT_SHAPE=confirmed`) or
   name a different secondary vendor. Reoon is the obvious candidate and is
   demonstrably answering today - four of the thirteen HELD contacts carry a
   live Reoon verdict - but it is also the `catch_all` adjudicator, so making
   it the secondary would have one vendor both supplying the second
   confirmation and clearing the catch-all. That is a smaller independence
   than the policy was designed around and it should be chosen deliberately
   rather than discovered later.
3. **Then spend 58 credits, not 318**, on the 29 contacts at the 13 records
   that have no verified contact at all. The other 130 buy nothing that the
   account gate will let us use.

## The tool

`scripts/verification_inventory.py`, read-only, no provider call. It reports
what a run would cost and never runs one. It keeps HELD and NEVER_OFFERED
apart because every summary that counts "unverified" merges them, and they are
different problems: one is a policy question, the other is inventory already
paid for once and abandoned before the cheap step that would license using it.
