PRIORITY: P0
DEPENDS:

# TASK-147 - the EmailBison cohort, resolved against the LIVE queue rather than a snapshot

## WHY THIS IS P0 AND NOT A LATER PHASE

The operator has made both channels P0. EmailBison is not a thing that starts
when LinkedIn finishes: the two share an estate, a suppression model and an
account-collision rule, and nothing else. Neither blocks the other.

TASK-145 designed the cohort against `work/queue.snapshot.jsonl` and found:

    cold email (verified address, no bison_lead_id)      26
    prior outreach, no reply                             29
    unverified, neither                                 245

That was 300 records. **The live queue is now 550 and the snapshot is stale.**
This task re-resolves those numbers and answers the questions the design left
open, so Claude can build the campaign without re-deriving any of it.

## THE SNAPSHOT PROBLEM, AND WHAT TO DO ABOUT IT

`work/queue.jsonl` is production and you must not write to it. The snapshot in
your worktree is old. So:

**Ask Claude to refresh the snapshot before you start**, by writing a line
under FINDINGS saying you need it and committing that immediately. Then work
against whatever `work/queue.snapshot.STAMP` says, and QUOTE THE STAMP in
every number you report. A measurement against a snapshot is a measurement at
a moment.

If the stamp is older than the numbers above, say so and report both.

## THE FOUR QUESTIONS

### 1. Who is actually cold on email, right now?

Partition the live-ish estate exactly as TASK-145 did, and say what moved:

    verified address AND no bison_lead_id          -> cold cohort
    bison_lead_id present                          -> needs question 2
    no verified address                            -> not eligible, and the
                                                      standing rule is that no
                                                      email is generated for
                                                      an unverified address

### 2. Were the 29 with a `bison_lead_id` ever actually EMAILED?

TASK-145 found the honest answer is probably no, and it matters enormously:

    campaign 481   PAUSED, 23 leads, 0 emails sent
    campaign 451   COMPLETED, 1 email sent

A `bison_lead_id` is assigned at LEAD CREATION. Campaign 481 never sent. So
most of those 29 have a provider-side lead row and have received nothing - they
are effectively cold, and they are currently being held out of BOTH channels
on the assumption that they are not.

**Settle it from the provider.** You hold real EmailBison credentials and the
rule is READS ONLY - no write, no send, no campaign mutation, no resume, no
pause. Per lead, determine whether any email was actually sent, using the
routes `docs/BISON-API-CAPABILITY-MAP-2026-09-14.md` and
`docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md` already establish.

If they were never emailed, say so with the field that proves it. That
potentially returns 29 contacts to BOTH the email and the LinkedIn cohorts,
which is a larger result than the cohort design itself.

### 3. What does the account-collision rule do to the email cohort?

The LinkedIn side measured this and it was brutal: 151 of 248 contacts
rejected at the ACCOUNT level - somebody at that company is mid-sequence, has
already replied, or a campaign there ended ambiguously.
`docs/COHORT-HEADROOM-2026-09-15.md` has the numbers.

The email cohort faces the same rule from the other side. Run
`collision.check_account` over the cold cohort's domains - cached per domain,
it is the account that is the unit - and report how many survive.

**Do not run `check_address` per contact for this.** That is a per-person read
and the account verdict answers the cohort question.

### 4. What cohorts fall out, and are they worth separating?

Group by whatever dimension the evidence ACTUALLY supports - TASK-140 found
signal was 100% null on the LinkedIn side and that angle was inferred from
title rather than evidenced. Do not assume email is richer; check.

For each proposed cohort: size, dimension values, and whether it is a CONTROL
cohort (the validated fallback copy, which asserts nothing specific, so the
cohort is for READING the result) or a CHALLENGER cohort (copy that asserts
something, which needs per-contact evidence and must clear the claims gate).

`PRODUCTION-SCALE-POLICY.md` is the contract: a campaign is a COHORT and never
a person, ~50 where inventory supports it, consolidation over proliferation.

## WHAT YOU MAY NOT DO

- No provider WRITES. No campaign creation, no sequence write, no lead
  creation, no resume, no pause. Reads only.
- Do not write to `work/` in any worktree.
- Do not run `py -3 -m src.generate --live`. Generation against the real queue
  is Claude's; a run here writes to an isolated worktree queue.
- Do not quote an open rate - `open_tracking` is False estate-wide.
- Do not count an UNKNOWN reply as negative.

## FILES ALLOWED

    docs/BISON-COHORT-LIVE-2026-09-15.md   (new)
    scripts/task147_*.py
    the task file itself

## FILES FORBIDDEN

    src/    work/    config/

## DELIVERABLE

The four answers with the snapshot stamp on every number, the per-lead
send-or-not verdict for the 29 with its proving field, the account-collision
survival count, and the cohort proposal with each cohort's arm.
