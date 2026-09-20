PRIORITY: P0
DEPENDS:

# TASK-235 - a DNC or unsubscribe cannot stop a running HeyReach sequence

Priority P0. PROBLEM-REGISTER ISSUE-002. Found by Buggie 2026-09-20 and
re-verified open the same evening.

## The defect

`heyreach.stop_lead_in_campaign` is fully implemented, is on `WRITE_ROUTES`,
and refuses on an unconfirmed readback. **It has no caller anywhere in the
repository.**

    grep -rn "LINKEDIN_STOP_LEAD" src/          -> nothing
    grep -rn "stop_lead_in_campaign" src/       -> only its own module

`EMAIL_STOP_LEAD` exists as a verb. There is no LinkedIn equivalent. So a
DNC, an unsubscribe, or an email reply cannot stop a LinkedIn sequence that
is already running. HeyReach's own structural reply-stop closes
LinkedIn-reply -> LinkedIn-step natively and **only** that.

## And the sweep reports clean because it counts nobody

`leadstop.sweep` `continue`s past every LinkedIn-staged contact **without
incrementing `report['checked']`**. That is why this never surfaced: the
sweep succeeds, reports zero problems, and has examined none of them.

**Fix that first and separately.** A counter that skips silently is the
reason a missing capability looked like a working one, and it is the smaller
half of this task.

## A third thing is missing underneath both

`heyreach_lead_id` is **read** by two modules and **written** by none. No
record carries the id the stop route needs. Establish where that id comes
from on the staging path and persist it, or the verb cannot be called even
once it exists.

## Blast radius today

    HeyReach-bound records   4
    Bison-bound records     16
    overlap                  0

So the email-reply half is LATENT. **The DNC and unsubscribe half is live
now**, against the three real people enrolled in campaign 605732.

## The objective

A suppression that applies to a person stops them on EVERY channel they are
live on, and a sweep that cannot check a channel says so loudly.

Falsifiable requirements:

1. `leadstop.sweep` counts every contact it examines, including
   LinkedIn-staged ones. A test that stages a LinkedIn contact and asserts
   `report['checked']` includes it FAILS today.
2. A `LINKEDIN_STOP_LEAD` verb exists with the same shape as
   `EMAIL_STOP_LEAD`: reserved on the ledger, gated by `executionguard`,
   performed through `providerwrites`, and refusing unless the provider
   readback confirms the lead actually stopped.
3. `heyreach_lead_id` is WRITTEN on the staging path, and a test proves a
   staged LinkedIn contact carries it.
4. A DNC on a contact live on both channels produces a stop attempt on both.
   Prove it with a fake transport, asserting BOTH calls.
5. A LinkedIn stop whose readback does not confirm is reported as FAILED and
   never as stopped.

## The seal, and do not break it

**`LINKEDIN_STOP_LEAD` goes on `WRITE_ROUTES` and NOT into
`providerwrites.SUPPORTED`.** A route the module CAN call and a route this
build WILL call are different lists, and enabling the second is Claude's
decision after review - the same treatment `heyreach.add_lead` got. Build the
mechanism and the tests; leave the door shut.

## Hard limits

- **NO PROVIDER WRITE. No live call of any kind.** Campaign 605732 is LIVE
  with three real people in it. Every test uses a fake transport.
- Do not weaken the unconfirmed-readback refusal to make a test pass.
- Do not touch the email stop path except where a shared helper genuinely
  serves both.

## Where to read first

`src/leadstop.py`, `src/providerwrites.py` (`EMAIL_STOP_LEAD` and
`SUPPORTED`), `src/providers/heyreach.py::stop_lead_in_campaign`,
`src/executionguard.py`, and `work/BUGGIE-FINDINGS-2026-09-20.md` finding 3.

## Acceptance

Every requirement above has a test; the five listed fail before the change
and pass after; `SUPPORTED` is unchanged; no live call was made.
