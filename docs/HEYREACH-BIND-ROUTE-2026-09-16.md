# HEYREACH-BIND-ROUTE-2026-09-16

TASK-216 deliverable. The supported route from an unbound list to a campaign.

## ANSWER: (b) - a list can only be attached at campaign creation or via UpdateSettings on a campaign that has never been started

The route `POST /campaign/UpdateSettings` exists and can change a campaign's
list binding (`linkedInUserListId`). It does NOT help for campaign 599020 or
list 940797, for two independent reasons.

## WHAT WAS SEARCHED

1. **`src/providers/heyreach.py`** - every route on `READ_ROUTES`,
   `READ_ROUTES_ALL`, `READ_GET_ROUTES`, `WRITE_ROUTES`. No route named
   `AddListToCampaign`, `BindList`, `AttachList`, or `UpdateSettings` appears.
   `UpdateSettings` is mentioned in a comment (line 1254) as documented by the
   vendor but never probed or added to any allowlist.
2. **Vendor official documentation** - `heyreach.io/blog/campaign-api` and the
   Postman collection at `documenter.getpostman.com/view/23808049/2sA2xb5F75`.
3. **Community sources TASK-158 used** -
   `github.com/bcharleson/n8n-nodes-heyreach` and
   `github.com/bcharleson/heyreach-cli`.
4. **Web search** for HeyReach API endpoint lists and documentation.

## THE ROUTE THAT EXISTS

### `POST /campaign/UpdateSettings`

**Source:** heyreach-cli source code
(`src/commands/campaigns/update-settings.ts`), confirmed by the vendor's
official blog post and Postman collection.

**Endpoint:**
```
POST https://api.heyreach.io/api/public/campaign/UpdateSettings
```

**Body:**
```json
{
  "campaignId": 123,
  "name": "New Name",
  "linkedInUserListId": 789,
  "excludeContactedFromOtherCampaigns": false,
  "excludeHasOtherAccConversations": false,
  "excludeContactedFromSenderInOtherCampaign": false,
  "excludeListId": 456
}
```

All three fields (`campaignId`, `name`, `linkedInUserListId`) are required.
The exclusion flags are optional.

**Allowed statuses:** DRAFT, SCHEDULED, PAUSED.

**Effect on campaign state:**
- If the campaign is SCHEDULED, it reverts to DRAFT.
- If the campaign is DRAFT or PAUSED, the status does not change.
- **Binding a list does NOT activate the campaign.** `StartCampaign` is a
  separate, explicit call.

**Two critical restrictions:**

1. **Not allowed on ACTIVE (IN_PROGRESS) or COMPLETED (FINISHED) campaigns.**
   Returns 400. Campaign 599020 is FINISHED, so this route refuses it.

2. **The list cannot be changed if the campaign has been started at least
   once.** Returns 400: "List changed after campaign has started". The field
   is `linkedInUserListId` and the CLI describes it as "locked after campaign
   has started". This means even a campaign in DRAFT that was previously
   started (if such a state is reachable) cannot have its list rebound.

## WHY THIS DOES NOT HELP FOR 599020

Campaign 599020 is FINISHED and has already run. Both restrictions apply:
- FINISHED is not in {DRAFT, SCHEDULED, PAUSED} - the route refuses.
- The campaign has been started - the list field is locked.

The path is a **new campaign** created around list 940797, with campaign
599020's 24-node sequence reproduced on it.

## THE READBACK A BIND MUST PROVE

If `UpdateSettings` were used on an eligible campaign, a 200 response is not
sufficient evidence. Based on the silent-drop pattern TASK-158 measured
(twelve body shapes returning `addedLeadsCount 0` with HTTP 200), the readback
must prove:

1. **`GET /campaign/GetById`** (or `campaign_read`) returns the campaign with
   `linkedInUserListId` matching the list that was bound.
2. **`POST /list/GetById`** returns the list with `campaignIds` containing the
   campaign's id.
3. **The campaign status** has not changed unexpectedly (SCHEDULED reverts to
   DRAFT, which is documented; anything else is not).
4. **`POST /list/GetLeadsFromList`** returns the same lead count as before the
   bind - binding a list does not add or remove leads from it.

## THE SHORTEST SAFE SEQUENCE: STAGED LEAD TO FIRST SEND

From the staged lead (on list 940797, unbound) to a first send:

### Step 1: Create a new campaign bound to list 940797

- **Route:** `POST /campaign/Create`
- **Body:** `{name, linkedInAccountIds: [sender], linkedInUserListId: 940797}`
- **Verb in providerwrites:** `LINKEDIN_CREATE_CAMPAIGN`
  (`heyreach.create_campaign`)
- **Exists?** Yes, in `SUPPORTED` since 2026-09-14.
- **Prospect-facing?** No. Creates in DRAFT, sends nothing.
- **Readback:** `campaign_read` confirms name, status=DRAFT,
  `linkedInUserListId=940797`, correct sender accounts.

### Step 2: Write the sequence onto the new campaign

- **Route:** `POST /campaign/UpdateSequence`
- **Body:** `{campaignId, sequence}` - the 24-node graph from campaign 599020
- **Verb in providerwrites:** No dedicated verb exists. `set_sequence` in
  `heyreach.py` implements the transport. Not in `SUPPORTED` or
  `CONDITIONAL` as a named verb.
- **Exists in transport?** Yes, on `WRITE_ROUTES`.
- **Prospect-facing?** No. Configuration only; the campaign is DRAFT.
- **Readback:** `GET /campaign/GetCampaignSequence` returns the graph,
  compared field-for-field with what was sent (node shape, not raw equality).

### Step 3: Start the empty campaign for staging

- **Route:** `POST /campaign/StartCampaign`
- **Verb in providerwrites:** `LINKEDIN_START_EMPTY_FOR_STAGING`
  (`heyreach.start_empty_for_staging`)
- **Exists?** Yes, in `SUPPORTED` since 2026-09-15, CONDITIONALLY.
- **Prospect-facing?** No. The campaign holds ZERO leads at this point
  (the list is bound but no leads have been added to the campaign). Starting
  a campaign with zero leads sends nothing.
- **Condition:** `providerwrites` refuses unless the provider says the
  campaign holds ZERO leads, read immediately before.
- **Readback:** `campaign_read` confirms status is IN_PROGRESS; lead count
  from `GetLeadsFromCampaign` confirms zero.

### Step 4: Add the staged lead to the campaign

- **Route:** `POST /campaign/AddLeadsToCampaignV2`
- **Verb in providerwrites:** `LINKEDIN_ADD_LEAD` (`heyreach.add_lead`)
- **Exists?** Yes, in `SUPPORTED` since 2026-09-15, CONDITIONALLY.
- **Prospect-facing?** **YES.** This is the first prospect-facing step. The
  lead enters the sequence and begins receiving messages.
- **Condition:** `CAMPAIGN_LEVEL_STAGING_IS_PROVEN` is currently False, so
  `LINKEDIN_ADD_LEAD` is RESEALED - refused on the first line of its own
  condition. The condition `_campaign_is_a_declared_staging_campaign` checks
  that the campaign is a declared staging destination.
- **This is the reseal the task names.** Adding a lead to a campaign
  ACTIVATES it for that lead - the vendor documents it for PAUSED and
  FINISHED. The lead enters the sequence immediately.
- **Readback:** `GetCampaignsForLead` confirms the lead is in the campaign
  with a non-terminal `leadStatus`; `GetLeadsFromCampaign` confirms the lead
  count increased by one.

### Step 5: (If needed) Pause the campaign

- **Route:** `POST /campaign/Pause`
- **Verb in providerwrites:** `LINKEDIN_PAUSE` (`heyreach.pause`)
- **Exists?** Yes, in `SUPPORTED`.
- **Prospect-facing?** No. Stops outreach.
- **Readback:** `campaign_read` confirms status is PAUSED.

## THE SAFETY BOUNDARY

The bind (step 1) is NOT the activation boundary. The activation boundary is
step 4 - `AddLeadsToCampaignV2`. Before step 4, the campaign holds zero leads
and sends nothing regardless of its status. After step 4, the lead is in the
sequence and the sequence acts on them.

This is exactly the same boundary `LINKEDIN_ADD_LEAD` already guards. The
list-to-campaign bind at creation time is bookkeeping; the lead add is the
prospect-facing act. The activation gate stays on `LINKEDIN_ADD_LEAD`, where
it already is.

## WHAT IS NOT IN `providerwrites` AND WOULD BE NEEDED

| Step | Route | Verb | In SUPPORTED? | In CONDITIONAL? | Prospect-facing? |
|------|-------|------|---------------|-----------------|------------------|
| 1 | `/campaign/Create` | `LINKEDIN_CREATE_CAMPAIGN` | Yes | No | No |
| 2 | `/campaign/UpdateSequence` | (no named verb) | No | No | No |
| 3 | `/campaign/StartCampaign` | `LINKEDIN_START_EMPTY_FOR_STAGING` | Yes | Yes | No |
| 4 | `/campaign/AddLeadsToCampaignV2` | `LINKEDIN_ADD_LEAD` | Yes | Yes | **Yes** |
| 5 | `/campaign/Pause` | `LINKEDIN_PAUSE` | Yes | No | No |

Step 2 has no named verb in `providerwrites`. The transport exists in
`heyreach.set_sequence` but no `LINKEDIN_SET_SEQUENCE` or equivalent is in
`SUPPORTED` or `CONDITIONAL`. It would need to be added, or the sequence
would need to be passed as part of `create_campaign` (which accepts a
`sequence` parameter).

If the sequence is passed at creation (step 1), step 2 is folded into step 1
and needs no separate verb. `create_campaign` already accepts `sequence=` and
validates it before writing. This is the shorter path.

## WHAT `UpdateSettings` WOULD BE USEFUL FOR

`UpdateSettings` is useful for rebinding a DRAFT campaign to a different list
before it has been started. For example:

- A campaign was created with list A, but the wrong list was chosen.
- The campaign is still DRAFT and has never been started.
- `UpdateSettings` can rebind it to list B without creating a new campaign.

It is NOT useful for:
- A campaign that has already run (FINISHED, or was started and paused).
- A campaign that is currently running (IN_PROGRESS).
- Adding a list to a campaign that was created without one (if it has been
  started).

## SUMMARY

The answer is **(b)**: a list can only be attached at campaign creation or via
`UpdateSettings` on a campaign in DRAFT/SCHEDULED/PAUSED that has never been
started. Campaign 599020 is FINISHED and has been started, so neither path
works for it. The path forward is a new campaign created around list 940797,
with campaign 599020's sequence reproduced on it.

The bind at creation is bookkeeping. The activation boundary is
`AddLeadsToCampaignV2`, which is already guarded by `LINKEDIN_ADD_LEAD` with
its conditional seal. No new activation gate is needed for the bind itself.
