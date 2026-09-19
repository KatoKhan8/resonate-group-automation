# 210 mailboxes are free on Monday and none of them may be used

Read 2026-09-19T11:40Z, `scripts/sender_pool_census.py` against the COMPLETE
forward-book walk. This is the end of the chain the day's earlier documents
started, and it moves the answer.

## The chain, in order

1. `THE-SEND-DATE-IS-THE-MAILBOX` - 487 and 489 send on the 23rd and 24th
   because their mailboxes are booked.
2. `THE-SCHEDULER-PLACES-THE-WHOLE-COHORT` - specifically, because those
   mailboxes have no day with room for the whole cohort until then.
3. Both documents concluded the fix is "a mailbox the client cannot book".
   **That conclusion was right about the shape and wrong about the
   obstacle.**

## The estate has the capacity already

    TOTAL_BISON_INBOXES      225
    CONNECTED                210
    HEALTHY                  207
    proven free on some day  210      <- every connected mailbox
    could NOT be proven free   0

    walk complete=True  fresh=True  covers_active=True

Most of those 210 read `0 or 1 of 15 booked on 2026-09-21, 14-15 free` -
roughly three thousand free slots on Monday, on healthy connected inboxes, in
the correct workspace and the correct tenant. The estate is not saturated.
**Two specific mailboxes are.**

## And not one of them may be used

    HUMAN_IDENTITY_ATTESTED   0
    SAFE_FOR_PRODUCTIVE       0

    PER HUMAN        inboxes   attested   headroom
      (hashed)            66          0        634
      (hashed)            58          0        462

**Zero attested owners, across every human and all 225 inboxes.**
`assignment.eligible_senders` walks HUMANS and asks which accounts they own,
and `senderownership.resolve_owner` answers from the canonical roster rather
than guessing from a display name. With no attestations the eligible pool is
empty however healthy the estate is - which is what `SAFE_FOR_PRODUCTIVE = 0`
says.

`sender_pool_census` has reported this since it was written. What is new is
that the forward book now sits beside it, so the two halves can be read
together: **the capacity is real, measured, and entirely unreachable.**

## So the latency is not a capacity problem

It is an ATTESTATION problem, and that is a much more actionable statement
than "get a dedicated mailbox".

    is there free capacity on Monday          YES - 210 mailboxes, ~3,000 slots
    is any of it eligible                     NO  - 0 attested owners
    would attestation alone make a pool        NO  - the arity rule still caps
                                                     a campaign at ONE sender
    what the campaign holds today              2736, one mailbox, booked

Two independent things have to move, and `sender_pool_census` already says so
in its own words: `SAFE_FOR_PRODUCTIVE` (how many inboxes are eligible at
all) and `MAX_SENDERS_ONE_CAMPAIGN_MAY_NAME` (how many one campaign may name,
which is 1, by `executionguard._sender_for`: "a guarded action is attributed
to exactly one"). **The maximum safe pool is the MINIMUM of the two, and it
is currently zero.**

## The narrow version, which is the useful one

A cohort does not need a pool. It needs ONE eligible mailbox with room, and
the arity rule permits exactly that.

So the smallest change that would have let 487 send on Monday instead of
Wednesday is **one human sender identity attested to one healthy uncommitted
mailbox.** Not a pool, not the arity rule, not a new provider, not a
dedicated domain.

That is a bounded piece of work with a named module
(`senderownership.resolve_owner`, the canonical roster) and it is the highest
-leverage item this analysis produced.

## What must not be done with it

- **Do not attest a human to a mailbox to gain capacity.** The rule stands:
  a prospect belongs to a HumanSenderIdentity and the copy is signed by a
  person. Attestation records who genuinely operates an inbox; inventing one
  to unlock a send is fabricating the thing the gate exists to check.
- **Do not read "210 free" as 210 usable.** It is the measured forward book
  and nothing else. Deliverability, tenancy, ownership and the arity rule all
  still apply, and `senderheadroom.rank` says so in its own docstring:
  it ranks on LATENCY ONLY and must never be the only filter.
- **The three UNCOMMITTED inboxes (3941, 3930, 3919) are still the wrong
  answer.** Their books are empty because they have NEVER SENT AN EMAIL,
  which this system calls DEGRADED. Free and unproven are not the same.

## Classification

    210 connected mailboxes proven free on a day    MEASURED, complete walk
    0 attested human owners                         MEASURED
    SAFE_FOR_PRODUCTIVE = 0                         MEASURED
    arity rule caps a campaign at one sender        DOCUMENTED (executionguard)
    150 connected mailboxes have room for TEN on
      Monday 2026-09-21, and the same 150 for FIVE  MEASURED
    one attestation would have moved 487 to Monday  INFERRED - the capacity
                                                    side is measured; whether
                                                    the scheduler would then
                                                    replan a LIVE campaign
                                                    onto a newly attached
                                                    sender is UNKNOWN and is
                                                    NOT a reason to try it on
                                                    487 or 489
