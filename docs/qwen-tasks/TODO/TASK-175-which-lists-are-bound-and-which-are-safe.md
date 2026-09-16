PRIORITY: P0
DEPENDS:

# TASK-175 - the list estate, and which list the canary may stage into

## WHERE THIS SITS

TASK-158 proved list staging works and TASK-172 is specifying the verb. Both
rest on one safety property, and it is a property of a LIST, not of a campaign
and not of us:

    a list attached to NO campaign cannot send, whatever is added to it

Which makes the next question unavoidable, and it has never been measured. We
know of exactly three lists and two of them already contradict each other:

    933603   ATTACHED to campaign 599020 (DRAFT, 0 leads, 24 nodes, 1 sender)
    940797   attached to nothing, holds 1 lead from TASK-158's schema probe

So "a list Resonate created" is not the safety condition - 933603 is ours and
staging into it is staging into a campaign. Nobody has enumerated the rest.

## THE QUESTION

Read-only against the provider.

1. **Enumerate every list the account can see.** Id, name, lead count,
   created date, and whether it is attached to a campaign - and if so, which
   campaign and that campaign's state. The account holds 83 campaigns of which
   exactly one is ours, so expect lists that are the client's and say which are
   which.
2. **How is attachment discovered?** Name the endpoint and field that answers
   "is this list attached to a campaign". If it can only be answered by walking
   campaigns and reading their lists, say so, and say what that costs - a
   readback that paged 83 campaigns to find one has already timed out once in
   this repository's history.
3. **Can a list be attached to more than one campaign?** And can a campaign
   hold more than one list? The answer changes the predicate TASK-172 is
   writing, so answer it from the provider or from its documentation, and say
   which.
4. **What should the canary's staging list be?** Given the 3-lead rung of
   TASK-155's ladder, recommend one of: reuse 940797, create a new list, or
   something else. 940797 currently holds one real lead from a schema probe,
   which is a fact a canary readback would have to account for.
5. **The binding step.** The path is `QUALIFIED -> LIST -> READBACK -> FINAL
   ELIGIBILITY -> CAMPAIGN -> SEND`. Between LIST and CAMPAIGN a list must
   become attached, and that attachment is the moment staging becomes sending.
   Which provider operation performs it, does a verb for it exist in
   `providerwrites.py`, and is it in `SUPPORTED`? Report, do not enable.

## THE TRAP

An unbound list is safe now. Nothing in the provider prevents a person with
account access from attaching it a minute later, at which point every lead in
it is a lead in a campaign. So do not report a list as "safe" - report it as
"unattached as of <timestamp>", and say what would detect a later attachment.
The distinction is the whole safety argument and a summary that loses it is
worse than no summary.

Second trap: 940797's single lead is a real person added by a probe. Do not
remove it - that is a provider write and it is Claude's call, not this task's.

## WHAT YOU MAY NOT DO

- **No provider writes.** Do not create, delete, attach or detach a list, do
  not add or remove a lead, do not touch campaign 599020.
- Do not add anything to `SUPPORTED` or `CONDITIONAL`.
- Never commit a profile URL, a prospect name, or a seat-holder's real name -
  a sender's name has leaked into a committed state file in this repository
  once already. Hash identifiers; list ids and campaign ids are not PII.

## FILES ALLOWED

    docs/HEYREACH-LIST-ESTATE-2026-09-16.md   (new)
    scripts/task175_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The full list enumeration with attachment state and ownership, the endpoint
that answers attachment and what it costs, the one-to-many answers in both
directions, the recommended staging list with its reason, and the binding
operation with its verb and permission status.
