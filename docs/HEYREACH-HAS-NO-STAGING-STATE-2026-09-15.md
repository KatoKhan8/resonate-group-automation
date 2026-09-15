# Adding a lead IS activation, and HeyReach has no staging state

Established 2026-09-15 from the vendor's own documentation, after three
measured provider refusals narrowed the space to nothing.

## What the vendor says

> "Even if the campaign is paused, adding leads via API or integration
> directly into that campaign will activate the campaign."

> "Finished campaigns - as soon as new leads are added campaign will get
> activated."

https://help.heyreach.io/en/articles/11657798-how-to-add-leads-to-campaigns

## What was measured getting here

    DRAFT + AddLeadsToCampaignV2   400  "You cannot add new leads to a draft
                                         campaign."
    DRAFT + /campaign/Pause        400  "You cannot pause an inactive
                                         campaign."
    DRAFT + /campaign/Resume       400  "The campaign you are trying to resume
                                         is not paused, finished or failed."
    DRAFT + /campaign/StartCampaign      SUCCEEDED -> STARTING -> IN_PROGRESS
    IN_PROGRESS + /campaign/Pause        SUCCEEDED -> PAUSED
    PAUSED, zero leads, left alone       -> IN_PROGRESS -> FINISHED

Every state transition works. The one thing that does not exist is a state in
which a campaign holds leads and does not send to them.

## Why this matters more than a failed call

The operator's model, and the whole design built for it, is:

    stage leads -> provider readback -> verify -> SEPARATELY GATED activation

That model assumes adding a lead and starting outreach are two actions.
**On HeyReach they are one action.** `LINKEDIN_ADD_LEAD` and
`LINKEDIN_ACTIVATE` are separate operations in this codebase, separately
sealed, with separate conditions - and the provider does not honour the
distinction. Adding the first lead to campaign 599020 sends that person a
connection request.

So the canary is not a staging step. It is a real first touch.

## What is NOT affected

Nothing has been sent. Campaign 599020 is FINISHED, holds ZERO leads, and its
own counters read `connectionsSent: 0`, `uniqueLeadsContacted: 0`. It was
started empty, had nobody to act on, and finished. The action ledger is
settled from provider truth.

Every gate built for this remains correct and is what stopped it: the cohort
is collision-cleared at account and person level, the copy is the operator's
own CONTROL text approved by fingerprint, the campaign approval is current,
and the write door refused an IN_PROGRESS campaign twice without reaching the
transport.

## The options, and neither is an engineering decision

**A. Treat add-lead as the activation moment.** Apply the activation gates -
not the staging ones - to the first lead, and accept that the canary is a real
send to one approved prospect. The cohort is already cleared for exactly that.
This is what "live" means on this provider.

**B. Find out whether a LIST behaves differently.** Campaign 599020 has list
933603 attached, holding 0 items. `/list/AddLeadsToListV2` exists (probed 405).
Adding a lead to a LIST is not adding it to a campaign, and the vendor's
sentence is about campaigns. If a list can be filled without activating, the
stage-then-activate model survives on this provider after all. Unproven, and
worth one probe before choosing A.

## What must not happen

Neither option is a reason to weaken a gate. If A is chosen, the add-lead path
must require the activation evidence rather than the staging evidence -
`LINKEDIN_START_EMPTY_FOR_STAGING`'s zero-lead condition does not apply to it,
and `CONDITIONAL[LINKEDIN_ADD_LEAD]` currently admits PAUSED on the premise
that a paused campaign does not send. That premise is now known to be false,
and the condition should say so before it is used again.
