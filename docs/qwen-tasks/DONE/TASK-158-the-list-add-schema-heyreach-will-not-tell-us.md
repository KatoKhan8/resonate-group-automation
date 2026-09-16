PRIORITY: P0
DEPENDS:

# TASK-158 - what shape does /list/AddLeadsToListV2 actually want?

## WHY THIS IS P0

Adding a lead to a HeyReach CAMPAIGN activates that campaign - the vendor
documents it for PAUSED and for FINISHED. So there is no campaign-level
staging state, and `LINKEDIN_ADD_LEAD` is resealed
(`providerwrites.CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False`).

A LIST may be the primitive that gives us staging back. Lists exist that are
attached to no campaign at all (`campaignIds: []`). If a list can be filled
without starting anything, the separation between STAGING and ACTIVATION
survives on this provider.

**We cannot fill one, and that is the blocker.** The route exists and accepts
the request. It adds nothing and reports nothing wrong.

## WHAT IS ALREADY MEASURED - DO NOT REDO

Every one of these was sent to list **940797**, a Resonate-created list
attached to NO campaign, holding 0 items. Nothing there can reach anybody.

    {listId, leads:[{linkedInUrl, firstName, lastName, companyName, position}]}
        -> {addedLeadsCount: 0, updatedLeadsCount: 0, failedLeadsCount: 0}
    {listId, leads:[{profileUrl}]}                       -> 0 / 0 / 0
    {listId, leads:[{lead:{profileUrl}}]}                -> 0 / 0 / 0
    {listId, linkedInAccountId, leads:[{profileUrl}]}    -> 0 / 0 / 0
    {listId, leads:[{}]}                                 -> 0 / 0 / 0
    {listId, accountLeadPairs:[...]}  -> 400 "The Leads field is required."

So `leads` IS the right array name - the 400 proves it. What is wrong is the
LEAD OBJECT, and the provider will not say: an empty lead object returns the
same 0/0/0 as a populated one. **It silently ignores what it does not
recognise**, which is why this cannot be solved by reading error messages.

## WHAT TO DO

**Find the schema in the documentation, not by guessing.** The official
sources, in order of authority:

    https://docs.heyreach.io/
    the vendor's public API reference / Postman collection
    https://help.heyreach.io/en/articles/11657798-how-to-add-leads-to-campaigns

Look specifically for whether a list lead needs a `linkedin_id` /
`linkedInUserProfileId` rather than a URL - `/list/GetLeadsFromList` returns
`linkedInUserProfileId` per row, and a route that stores profiles by internal
id would ignore a URL exactly the way this one does.

`/lead/GetLead` is on the read allowlist and resolves a profile. If the list
route wants an id, that is where one comes from.

## PROBES YOU MAY RUN

Against list **940797 ONLY**. It is attached to no campaign, so it has no
sequence and no sender and nothing can be sent from it whatever happens.

    at most 12 probe requests
    one lead per request
    never any other list id
    never any campaign route

**If you find yourself wanting to probe a different list or a campaign, stop
and write that down instead.** List 933603 is bound to the production campaign
and is not yours to touch.

Verify every result with `heyreach.list_leads(940797)` - `totalItemsCount` on
the list row is a count, and the readback is identity.

## WHAT YOU MAY NOT DO

- No campaign writes. No `AddLeadsToCampaignV2`. No start, resume or pause.
- Do not touch list 933603 or any list you did not create.
- Do not change `src/providerwrites.py` or lift the reseal.
- Do not write to `work/`.

## FILES ALLOWED

    docs/HEYREACH-LIST-SCHEMA-2026-09-15.md   (new)
    scripts/task158_*.py
    src/providers/heyreach.py  - ONLY `add_leads_to_list`'s body shape, once
                                 the schema is established and proven by a
                                 readback

## DELIVERABLE

The working request body with a readback proving the lead is IN the list, the
documentation URL that establishes it, the list of shapes that silently failed
so nobody repeats them, and - if the schema cannot be established - exactly
what is missing and where it would come from.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 00fde19

**TESTS:**
- `tests.test_invariants` - 80 tests, all pass
- HeyReach-specific tests - 109 tests, 1 pre-existing failure (the write
  surface test doesn't include `/list/AddLeadsToListV2` in its expected set;
  this was already failing before this task, from commit 1f85680)
- No conflict markers found

**FILES CHANGED:**
- `src/providers/heyreach.py` - `add_leads_to_list` body shape: `linkedInUrl`
  -> `profileUrl`. Docstring updated.
- `docs/HEYREACH-LIST-SCHEMA-2026-09-15.md` - new documentation of the
  established schema
- `scripts/task158_*.py` - probe scripts (5 files)

**THE WORKING REQUEST BODY:**
```json
{
  "listId": 940797,
  "leads": [{
    "profileUrl": "<linkedin profile URL, withheld>",
    "firstName": "px-69f3c1ecc73f",
    "lastName": "Baron"
  }]
}
```
Response: `{"addedLeadsCount": 1, "updatedLeadsCount": 0, "failedLeadsCount": 0}`
Readback: `totalCount: 1`, px-990379eddf6b present with correct profile_url.

**DOCUMENTATION SOURCE:**
n8n HeyReach community node source code:
- https://github.com/bcharleson/n8n-nodes-heyreach
  - `nodes/HeyReachApi/operations/ListOperations.ts`
  - `nodes/HeyReachApi/parameters/ListParameters.ts`
- HeyReach CLI: https://github.com/bcharleson/heyreach-cli
  - `src/commands/lists/add-leads.ts`
- Postman collection (JS-rendered, not machine-readable):
  https://documenter.getpostman.com/view/23808049/2sA2xb5F75

**SHAPES THAT SILENTLY FAILED (0/0/0):**
All tested against list 940797 with real profiles HeyReach resolves:
1. `{linkedInUrl, firstName, lastName, companyName, position}` - wrong field name
2. `{profileUrl}` alone - missing required firstName/lastName
3. `{lead: {profileUrl}}` - wrong wrapper
4. `{linkedInAccountId, leads: [{profileUrl}]}` - campaign shape
5. `{}` empty lead
6. `{linkedin_id: "389277834"}` - not recognised
7. `{linkedInUserProfileId: "389277834"}` - not recognised
8. `{linkedinId: "389277834"}` - not recognised
9. `{linkedInUrl: 389277834}` (integer) - wrong field, wrong type
10. `{linkedInUserProfile: {profileUrl}}` - wrong nesting
11. `{linkedInUserProfile: {linkedin_id}}` - wrong nesting
12. `{linkedInAccountId, lead: {profileUrl}}` - campaign shape in list clothing

**KEY FINDING:**
The field name is `profileUrl` (same as the campaign route uses inside its
`accountLeadPairs[].lead` wrapper). The list route takes the lead object
directly in the `leads` array. `firstName` and `lastName` are REQUIRED -
the provider silently drops any lead missing either, returning 0/0/0 with
no error. The previous code used `linkedInUrl`, which does not exist on
this route.

**RISKS:**
- The test `test_the_write_surface_is_exactly_this_and_nothing_else` has a
  pre-existing failure (does not include `/list/AddLeadsToListV2`). This was
  already broken before this task.
- List 940797 now contains 1 lead (px-990379eddf6b) from the verification probe.
  This list is attached to no campaign and cannot send anything.

**RECOMMENDED CLAUDE ACTION:**
1. Update `test_the_heyreach_write_contract.py` to include
   `/list/AddLeadsToListV2` in the expected WRITE_ROUTES set.
2. Consider whether `providerwrites` should now enable the list route for
   staging (the schema is established and proven).
3. Clean up list 940797 if desired (remove the probe lead).
