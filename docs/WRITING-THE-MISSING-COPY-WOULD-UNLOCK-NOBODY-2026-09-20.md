# Every record missing copy is also blocked at the account gate

Computed 2026-09-20T12:35-12:40Z from `scripts/next_ready_cohort.py --json`,
which was run fresh. The headline numbers are unchanged from the 09-19
handoff and correct:

    EMAIL     ALREADY_LIVE 15   READY_NOW 0   NEAR_MISS 0   blocked 36
    LINKEDIN  ALREADY_LIVE  3   READY_NOW 0   NEAR_MISS 7   blocked 71

What is new is the cross-tab underneath them, and it retires a piece of work
that looks obviously worth doing.

## The obvious-looking task

Nine LinkedIn records are stopped at the `copy` gate, and the summary says so
in a way that reads like an invitation:

    1 of 5 steps do not render: li4          x5
    2 of 5 steps do not render: li2,li5      x1
    2 of 5 steps do not render: li4,li5      x1
    3 of 5 steps do not render: li2,li4,li5  x1
    4 of 5 steps do not render: li2..li5     x1

Five records are one step short. Generating `li4` for five contacts is a
small, well-defined, cheap piece of work with a measurable result, and it
would move five records from `copy` to `approval`.

## It would move them to a gate they could never pass

    copy-gated LinkedIn records, by account decision
      account = stop      8
      account = hold      1
      account = allow     0

**Not one.** Every record missing copy is at an account where somebody is
already mid-sequence, has already replied, or where a campaign ended in a
state the system will not read as safe. The copy gate is not what is holding
them; it is simply evaluated first. `executionguard.authorize` runs
`copy, tenancy, approval, eligibility, suppression, copy_lint, claims,
fatigue, collision, account_collision` in that order, so the FIRST refusal is
the one reported, and for these nine the first refusal is not the binding
one.

Writing that copy produces nine records that are still blocked, a larger
`approval` bucket that is no more convertible than before, and a number that
looks like progress.

## The whole convertible inventory, by the gate that actually binds

    LINKEDIN  81
      40  account STOP - somebody at this account is mid-sequence right now
      17  account HOLD - a campaign there ended early, the state is ambiguous
       8  account STOP - a person there has already replied or been marked
       3  ALREADY_LIVE (605732)
       2  contact already TOUCHED - 8 and 9 messages, from seats 174822
           and 174748, neither of them ours
       2  account_collision
       1  contact collision
       7  NEAR_MISS - the only records where a human approval is the
                      whole of what is missing

    EMAIL  51
      17  account STOP - mid-sequence
      15  account HOLD - ambiguous stopped campaign
      15  ALREADY_LIVE (487 and 489)
       4  contact already TOUCHED
       0  NEAR_MISS

**Seven people.** That is the entire inventory that an approval converts, on
either channel, and it is the same seven already sitting in
`work/approval/NEAR-MISS-PACKET-2026-09-17.md`.

## Four records that look like hidden email near-misses and are not

Four email records read `gate=approval` with `account=allow`, which is the
exact position the seven LinkedIn NEAR_MISS records are in, and they classify
as SAFETY_BLOCKED instead. That asymmetry is worth being suspicious of - an
email near-miss list that reports zero while four records sit one approval
from ready would be hiding inventory.

It is not hiding anything. All four carry a CONTACT-level collision verdict
of `touched`, and `classify` reads that before it reads the gate:

    contact  10550c1a3e9c   touched   also linkedin, 8 messages, seat 174822
    contact  f2db8143a14f   touched
    contact  bd751f563564   touched
    contact  a79c73dc71b2   touched   also linkedin, 9 messages, seat 174748

`touched` is not `clear`, and somebody who has already been written to is not
a near miss. **EMAIL NEAR_MISS = 0 is the right answer**, which is what the
09-19 handoff said, and this is the check that confirms it rather than
repeating it.

One loose thread, recorded and NOT chased: the email rows read
`{"verdict": "touched", "status": null}` where the LinkedIn rows carry the
message count and the seat. A null status is weaker evidence than a count,
and whether it is the same kind of fact is unmeasured. It does not change the
verdict here - `touched` blocks either way - so it is a question about the
evidence's strength, not about today's decision.

## What this says about where throughput comes from

`THE-ESTATE-IS-SATURATED-NOT-UNAPPROVED` proved the client's own campaigns
hold 65 of the accounts in this estate. This is the same fact counted from
the contact end, and it puts a number on the ceiling: of 132 contact-channel
pairs, **104 are blocked by the account gate alone.**

So the two levers are exactly the two the earlier documents named, and
neither of them is copy:

    one human approval          converts 7 contacts, today
    new accounts, not in the
      client's book             converts everything else, eventually

Generating copy converts nobody, and this document exists so the next session
does not spend an hour discovering that.

## Classification

    9 copy-gated records, 0 with account=allow        MEASURED
    7 NEAR_MISS is the whole convertible inventory    MEASURED
    4 email records are TOUCHED, not hidden           MEASURED
    104 of 132 pairs blocked at the account gate      MEASURED
    the null `status` on an email `touched` row is
      the same kind of evidence as a message count    UNKNOWN, not chased
