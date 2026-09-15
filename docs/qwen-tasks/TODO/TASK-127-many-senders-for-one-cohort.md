PRIORITY: P1
DEPENDS: 

# TASK-127 - assign several healthy senders to one cohort

## THE POLICY AND THE MEASURED ESTATE

`docs/PRODUCTION-SCALE-POLICY.md`: use MULTIPLE appropriate healthy senders
per campaign where the provider supports it, optimising aggregate throughput
rather than pushing individual accounts harder.

Measured, and in `docs/state/SENDER-CAPACITY.json`:

    seats                             41
    healthy (isActive + authIsValid)  33
    active but auth INVALID            1   accepts work, then fails
    inactive                           7
    daily ceiling, healthy          1054 connection requests, 1143 messages
    healthy seats with NO active campaign   ZERO

Campaign 599020 carries ONE sender.

## THE QUESTION THIS ANSWERS

**Can a campaign hold several senders, and what actually decides how work is
split between them?**

1. `campaignAccountIds` is a LIST on the campaign object, which suggests yes.
   Confirm it from the estate: how many campaigns carry more than one, and
   what is the largest number of seats on one campaign?
2. `/campaign/AddLinkedInAccountsToCampaign` and
   `RemoveLinkedInAccountsFromCampaign` are on `heyreach.WRITE_ROUTES`.
   `LINKEDIN_ASSIGN_SENDER` is NOT in `providerwrites.SUPPORTED` and you may
   NOT enable it. Establish the request shape and what a readback would need
   to confirm the assignment landed.
3. **How does HeyReach distribute leads across seats?** Round-robin, per-lead
   assignment at add time, or something else? `build_lead_pairs` pairs each
   lead with a `linkedInAccountId`, which suggests WE choose. If we choose,
   the distribution policy is ours to design and it needs stating.
4. **What is actually free?** Zero healthy seats are uncommitted, so adding
   senders means reassigning seats already attached to campaigns. Per healthy
   seat, report which campaigns it is on and the status of each - a seat on
   six FINISHED and two PAUSED campaigns is effectively idle; one on an
   IN_PROGRESS campaign is not.

## HARD RULES

- **Reads only.** Do not attach, detach or modify any seat or campaign.
- **Never propose raising a per-seat limit.** Add senders or add days. A
  raised limit changes the risk taken with a client's real LinkedIn account
  and is not an engineering decision.
- **The `authIsValid: false` seat is not capacity.** It reports `isActive:
  true`, accepts an assignment and then fails, which is worse than absent
  because leads queue behind it looking scheduled. Find out whether it is
  recoverable or must be excluded from every plan.
- A seat is a REAL PERSON. Hash names, emails and profile URLs. Seat ids and
  numeric limits are fine.

## DELIVERABLE

A distribution design for a ~50-lead cohort across N healthy seats, with the
arithmetic shown: how many seats, how many days, and what that rests on.
Separate what you MEASURED from what you ASSUMED. If the honest answer is
that one seat could carry the cohort in two days, say so - then multi-sender
is not urgent and the finding is worth more than a plan nobody needs.
