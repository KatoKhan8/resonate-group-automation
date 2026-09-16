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

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 4294cd3
- **TESTS:** No test changes. Read-only provider enumeration, no code
  behaviour changed. Script `scripts/task175_enumerate_lists.py` reproduces
  the full data.
- **FILES CHANGED:**
  - `docs/HEYREACH-LIST-ESTATE-2026-09-16.md` (new) — the full deliverable
  - `scripts/task175_enumerate_lists.py` (new) — the enumeration script
- **FINDINGS:**
  1. **99 lists, 83 campaigns.** 42 lists are bound (attached to ≥1 campaign),
     57 are unattached as of 2026-09-16T04:57Z. 2 lists are Resonate's
     (933603, 940797); 97 are the client's.
  2. **Attachment discovery:** `campaignIds` array on the list object
     (from `/list/GetAll` or `GET /list/GetById`). The campaign-side
     counterpart is `linkedInUserListId` (singular integer) on the campaign
     object. Cost: 2 paged reads + 42 individual campaign reads ≈ 44
     requests, all free.
  3. **One-to-many:** A list CAN be attached to multiple campaigns (measured
     up to 8 — list 668409 "PRODUCTIVE - OMEGA"). A campaign holds exactly
     one list or zero (81 of 83 campaigns hold one; 2 DRAFT canary campaigns
     hold none).
  4. **Staging recommendation:** Create a new list (Option B). 940797 is
     usable but holds a probe lead and is named "DO NOT USE". 933603 is
     BOUND and refused by the safety predicate.
  5. **Binding step:** `POST /campaign/Create` with `linkedInUserListId` is
     the ONLY route that attaches a list to a campaign. The verb exists in
     `heyreach.create_campaign` but is NOT in `providerwrites.SUPPORTED`.
     Correctly sealed — creating a campaign with a list is the moment
     staging becomes sending.
  6. **Safety is temporal:** "Unbound as of <timestamp>" is the correct
     statement. `liststaging.assert_list_safe` re-reads the provider
     immediately before every add. The enumeration is a snapshot, not
     permission.
- **RISKS:**
  - The `providerwrites.OPERATIONS` entry for `LINKEDIN_CREATE_CAMPAIGN`
    says "no documented route" — this is stale. `/campaign/Create` is on
    `WRITE_ROUTES` and `heyreach.create_campaign` is implemented. The entry
    should be updated, but that is an operator decision and was not in scope.
  - 940797's probe lead (Brooke Baron) is a real person. This task did not
    remove it and must not — that is a provider write and Claude's call.
- **RECOMMENDED CLAUDE ACTION:**
  1. Decide on the staging list: create new (recommended) or reuse 940797.
  2. Update `LINKEDIN_CREATE_CAMPAIGN`'s OPERATIONS entry to reflect that
     `/campaign/Create` is established.
  3. The list estate document is the factual basis for TASK-172's verb
     specification and any future canary design.
