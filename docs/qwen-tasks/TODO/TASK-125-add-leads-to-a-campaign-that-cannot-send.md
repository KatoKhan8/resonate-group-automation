PRIORITY: P0
DEPENDS: 

# TASK-125 - the permission the codebase needs: add leads to a campaign that CANNOT send

## WHERE THIS CAME FROM, INCLUDING A MISTAKE

Claude tried to enable `LINKEDIN_ADD_LEAD` in `providerwrites.SUPPORTED` on
2026-09-15, under the operator's production authorisation, reasoning that a
lead added to a DRAFT campaign reaches nobody and campaign 599020 is DRAFT.

**Eight tests across three modules refused it**, in classes named
`TheSealStillHolds` and `TheWriteSurfaceIsSmallAndEveryRouteIsDeliberate`.
They were right and the reasoning was wrong: "599020 is DRAFT" is a property
of ONE CAMPAIGN AT ONE MOMENT, not of the permission. `OPERATIONS` flags
`add_lead` prospect-facing UNCONDITIONALLY, so adding it to `SUPPORTED` would
equally permit adding leads to an IN_PROGRESS campaign, where the sequence
acts immediately and nothing downstream would stop it.

The reverted attempt is on branch `write-gate-add-lead-UNVERIFIED`.

## THE DESIGN THIS TASK PRODUCES

The codebase does not currently have the distinction it needs. Build it.

**A lead may be added to a campaign that cannot send. A lead may not be added
to a campaign that can.**

That is a property of the CAMPAIGN, checked at the moment of the write, not a
property of the operation. It needs:

1. **A verifiable "cannot send" predicate**, read from the PROVIDER and not
   from local state. Campaign 599020 reports `status: DRAFT` and
   `startedAt: null`. Establish which fields actually prove a campaign cannot
   send, and what the provider returns for each status in the estate - there
   are 8 DRAFT, 32 PAUSED, 31 FINISHED and 12 IN_PROGRESS to look at.
   **PAUSED is the interesting one**: a paused campaign can be resumed, so
   leads added to it sit waiting for somebody to press a button. Decide
   whether PAUSED counts as "cannot send" and argue it either way - that
   argument is a deliverable.
2. **The check must be UNSKIPPABLE and must fail closed.** If the campaign
   status cannot be read, the answer is refuse, not proceed. A timeout is not
   a DRAFT.
3. **Re-check immediately before the write**, not once at planning time. A
   campaign can be started by a human in the vendor UI between the two, and
   the whole point is that the window is small and checked.
4. **The seals get NARROWED, not deleted.** The eight tests currently assert
   `add_lead` is never supported. They should end up asserting that it is
   refused for a campaign that can send, and permitted only for one proven
   not to - including a test that the refusal fires when the status read
   FAILS. Deleting a seal to make a route pass is the move this task exists to
   avoid.

## WHAT YOU MAY AND MAY NOT DO

- **You may NOT edit `providerwrites.SUPPORTED`.** Design, implement the
  predicate, write the tests, and leave the tuple alone. Claude enables it.
- **NO WRITES to any provider.** Reads only. Do not add a lead to anything,
  including 599020, including one.
- Do not weaken or delete any existing seal. If a seal must change shape, the
  replacement must assert something STRONGER and must be proven non-inert -
  break the guard, confirm the intended test fails for the intended reason.
- Hash prospect identifiers in anything tracked.
- Read every test exit code OFF THE PROCESS, never through a pipe.

## WHAT IS ALREADY ESTABLISHED - BUILD ON IT, DO NOT REDO IT

`docs/ADD-LEADS-READINESS-2026-09-15.md` (TASK-124) and Claude's independent
verification:

    request shape        established from build_lead_pairs:
                         {campaignId, accountLeadPairs[{linkedInAccountId, lead}]}
    response body        UNKNOWN, and it no longer decides anything
    READBACK             VERIFIED on campaign 565765: 1000 leads paged, each
                         carrying leadCampaignStatus, leadConnectionStatus,
                         leadMessageStatus, errorCode and
                         leadCampaignStatusMessage

Per-lead error codes are what a partial add needs: send 50, read back, and the
ones that did not land say why.

## DELIVERABLE

The predicate, its tests, the narrowed seals with counterfactual evidence for
each, and a written argument on PAUSED. End with exactly what Claude has to
review in order to enable the route - a short list, because a long one means
the design is not finished.
