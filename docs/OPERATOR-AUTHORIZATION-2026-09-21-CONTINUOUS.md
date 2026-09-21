# Operator authorization — 2026-09-21 — continuous cohorts

Recorded verbatim. **This supersedes the "NOT AUTHORIZED: a second batch"
clause of `OPERATOR-AUTHORIZATION-2026-09-21-BATCH-1.md`.** Every other
condition of that grant stands unchanged.

---

CONTINUOUS COHORTS. Batch 1's authorization extends to batches 2..N
under identical conditions 1 to 8, each with its stats posted and a
15-minute veto window before push. "NOT AUTHORIZED: a second batch" is
replaced by this grant. Any hard stop halts all further batches until I
clear it in writing.

PACING RULE. Enrolled-but-not-yet-sent backlog per campaign stays at or
below 3 days of that campaign's first-step capacity (15 x named
mailboxes). Tonight that is 45 per campaign, 360 total; after arity
merges it scales with the mailboxes named. Batches are sized to that
rule, not to 500. READY leads above the rule wait in the reservoir.

WAVE 2. When TASK-241 merges at zero new failures, re-run eligibility,
re-point the 8 campaigns to ALL attested mailboxes of their human at 15
per mailbox per day, and resume pacing at the new capacity. Report the
new first-step capacity per campaign.

LINKEDIN. Enroll leads with a LinkedIn URL onto fresh unbound lists,
one campaign per attested seat, 10 connection requests per seat per day
until per-seat usage on shared seats can be measured from our own
ledger; raise only on measured room.

SUPPLY. Start the next inputs now, in parallel, no approval needed for
enrichment: (a) re-qualify the 3,540 FLAGGED domains with the missing
company fields via ContactOut then free sources then Blitz then AI Ark;
(b) TASK-239 for the 459 contactless store accounts; (c) schedule the
weekly AI-ARK company search on the Productive ICP with headcount >= 20
applied at the source, diffed against the estate, never deleting.
Report READY reservoir daily.

REPLIES. Every classified reply posts to #replies-productive with a
drafted answer from prompts/reply_handling.md attached, three variants,
for a human to send. No auto-reply.

REPORT daily at 07:00 Zagreb in the digest: READY, enrolled, first-step
capacity, provider-confirmed SENT, replied, bounced, hard stops, credits.

---

## What the pacing rule replaces, and why it is the tighter number

Batch 1 was sized at 500 READY. **It is now sized at three days of first-step
capacity instead, and tonight that is 45 per campaign and 360 in total.** The
500 floor for the FIRST batch still stands as the operator's separate gate;
the pacing rule governs how much may be enrolled at once thereafter.

The rule exists because enrolled is not sent. A campaign holding 500 enrolled
leads against 15 first-step sends a day carries a 33-day backlog, and every
one of those leads ages, changes job, or unsubscribes while it waits. Three
days is the stated ceiling.

    tonight, single-mailbox branch   8 campaigns x 15/day x 3 = 360
    after TASK-241 merges            8 campaigns x 15 x (mailboxes named) x 3

## Current blocker on all of it

**S5 cannot produce READY leads right now**, so there is nothing to pace.
Deliverable became the verification primary today and has never made a live
call in this estate: `DELIVERABLE_RESULT_SHAPE` is unset and
`require_contract` refuses before the network. Until the operator opens that
gate, every verification refuses locally and READY stays at 609 - the rows
verified earlier under the previous policy with pair `(contactout, reoon)`.

That gate is deliberately an operator decision. TASK-196 made it open itself
and the change was reverted on 2026-09-16 for exactly that reason, so this
session will not set it.
