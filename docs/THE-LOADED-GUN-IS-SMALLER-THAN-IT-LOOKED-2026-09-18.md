# 481 and 485: the exposure is 9 people, not 33, and archiving is the wrong verb

Read 2026-09-18 from EmailBison, per lead, per campaign membership. This
supersedes `docs/TWO-DRAFT-CAMPAIGNS-HOLD-THE-LIVE-COHORT-2026-09-17.md` on
the numbers and agrees with it on the direction.

## What the previous handoff said

> 487  active   10 leads  [2736]   the live one
> 485  DRAFT    10 leads  [2736]   10 of 10 are 487's leads
> 481  PAUSED   23 leads  [2736,2737]  9 of them are 487's leads
>
> **Starting 485 sends a second opener to every person 487 is already queued
> to email.** Recommendation: archive 485 and 481.

The lead COUNTS are right. The exposure they imply is not, because nobody had
read the per-campaign membership STATUS.

## What the provider actually says

    campaign 485   10 leads   stopped 10
    campaign 481   23 leads   stopped 14,  sending_paused 9
    campaign 487   10 leads   in_sequence 10
    campaign 489    5 leads   in_sequence 5

**485 is already inert.** All ten of its memberships read `stopped`, and a
stopped lead is not sent to. "Starting 485 sends a second opener to every
person 487 is queued to email" is not supported by provider truth today.
Whether resuming a campaign RESETS a stopped membership is **UNKNOWN** - not
probed, and not worth probing on a campaign holding live 487's ten people.

**481's exposure is the 9 `sending_paused` rows**, and those 9 are 487's own
leads. `sending_paused` is the state a lead sits in while its campaign is
paused; it is the one that would resume.

The remaining 14 in 481 are `stopped`, and four of them are the US cohort now
live in 489. They were `stopped` with `emails_sent: 0` before 489 was staged,
which is what let them attach at all.

## Per-campaign membership is independent, and that is now proven twice

A person can be `sending_paused` in 481 and `in_sequence` in 487 at the same
moment. Four more are `stopped` in 481 and `in_sequence` in 489. So a stop
applied in one campaign does not reach another, in either direction.

That matters because it is the premise of every option below.

## Why NOT archive, which is what was recommended

**There is no archive route in this system at all.** `bison.WRITE_ROUTES` is
the allowlist and it admits two kinds only - staging, which cannot send, and
stopping, which can only ever mean somebody receives less. Archiving is
neither, is not in the tuple, and the vendor's route for it has never been
probed here. Adding it would take a transport route, a `providerwrites`
operation, a CONDITIONAL predicate and an operator grant: four new things, to
reach a state the leads are mostly already in.

**And archiving is not neutral for the LIVE cohorts.**
`collision.staging_artifact_evidence` proves a campaign is our own silent
staging on four arms, and the first one READS THE CAMPAIGN FROM THE PROVIDER
and fails closed when it cannot:

    481  proven = True    ours / zero_send / queue / ledger  all pass
    485  proven = True    ours / zero_send / queue / ledger  all pass

That proof is what removes 481's and 485's membership rows from the collision
history of the people in them. Remove the campaigns and the proof may go with
them - and if an archived campaign still appears in a lead's
`lead_campaign_data` while being unreadable, every one of those people starts
reading TOUCHED. That includes the four US-cohort contacts whose pre-send
recheck for step 2 lands in three days, and 487's ten on the 23rd.

This is not hypothetical. The same mechanism fired today from a smaller cause:
five unsettled ledger rows made campaign 489 stop proving itself and refused
its own five contacts at the collision gate. The arms are load-bearing.

## What was done instead, today

`providerwrites._NEVER_ACTIVATE` now refuses 481 and 485 **whatever canonical
row names them**, resolved after the row supplies a provider id and before any
write is admitted. The allowlist alone was only ever as safe as a row's
`bison_campaign_id`; this holds when that number is wrong.

So the exposure from THIS system is zero, and was already zero. What remains
is a human in the vendor UI.

## The recommendation, and it is an operator decision

**Stop the 9 `sending_paused` leads in campaign 481.** Not archive it.

    POST /api/campaigns/481/leads/stop-future-emails   {"lead_ids": [...]}

`EMAIL_STOP_LEAD` is already SUPPORTED, already unconditional, already
classified not prospect-facing, and its route is already in `WRITE_ROUTES`
under the category whose guarantee is that it can only ever mean somebody
receives less. It needs no new permission. It leaves every membership row,
counter and history intact - it deletes no evidence - and it moves 481 to the
state 485 is already in: 23 of 23 stopped, resumable by a human to no effect.
`stopped` is in `EXCLUDABLE_MEMBERSHIP` alongside `sending_paused`, so the
collision exclusion is unchanged by it.

**Why it was not simply done.** The only existing caller,
`leadstop.stop_contact`, writes the stop into the CONTACT's history through
`_record`. Those 9 contacts are live in campaign 487 with openers queued for
the 23rd, and a stop stamped on a live contact is exactly the shape a
suppression takes. Writing "stopped" onto nine people we are about to email is
a worse failure than the one being prevented, and reaching for the raw
`providerwrites.perform` path instead means building a second stop path
against live production data to close a hole that requires somebody to
deliberately resume a campaign the documentation tells them not to.

So: the verb is available, the target is exact, the risk is in the plumbing
rather than the provider, and the fix is a small one - a campaign-scoped stop
that does not touch contact history. It is queued rather than improvised.

## Classification

    485 all-stopped                          OBSERVED  2026-09-18, per lead
    481 nine sending_paused                  OBSERVED  2026-09-18, per lead
    per-campaign membership is independent   OBSERVED  both directions
    resume resets a stopped membership       UNKNOWN   not probed, not worth
                                                       probing on these
    no archive route exists here             DOCUMENTED  bison.WRITE_ROUTES
    archiving could break collision proof    INFERRED  from the four arms and
                                                       today's 489 incident
