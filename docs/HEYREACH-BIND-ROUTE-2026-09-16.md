# HeyReach Bind Route Investigation — 2026-09-16

## TASK-216 Result

**STATUS:** DONE
**ANSWER:** (a) with constraints — a supported bind route EXISTS, but cannot be used on FINISHED campaigns

---

## 1. What Was Searched

### In-Codebase Routes

**READ_ROUTES_ALL** (`src/providers/heyreach.py` line ~192):
- `/campaign/GetAll`, `/inbox/GetConversationsV2`, `/lead/GetLead`, `/li_account/GetAll`, `/campaign/GetLeadsFromCampaign`, `/stats/GetOverallStats`, `/list/GetAll`, `/list/GetLeadsFromList`, `/campaign/GetCampaignsForLead`

**READ_GET_ROUTES** (line ~240):
- `/campaign/GetCampaignSequence`, `/campaign/GetById`, `/list/GetById`

**WRITE_ROUTES** (line ~1421):
- `/campaign/Pause`, `/list/CreateEmptyList`, `/campaign/Create`, `/campaign/UpdateSequence`, `/campaign/AddLinkedInAccountsToCampaign`, `/campaign/RemoveLinkedInAccountsFromCampaign`, `/campaign/StopLeadInCampaign`, `/campaign/AddLeadsToCampaignV2`, `/campaign/Resume`, `/campaign/StartCampaign`, `/list/AddLeadsToListV2`

**Result:** No route named `attach_list`, `bind_list`, `set_list`, `AddListToCampaign`, or `UpdateSettings` appears in any of these tuples.

### External Sources

1. **HeyReach official blog** (`https://www.heyreach.io/blog/campaign-api`): Documents `POST /api/public/campaign/UpdateSettings` with full schema
2. **HeyReach CLI** (`github.com/bcharleson/heyreach-cli`): Implements `heyreach campaigns update-settings --campaign-id <id> --list-id <id>`
3. **HeyReach CLI API Audit** (`HEYREACH_API_AUDIT.md`): Confirms `UpdateSettings` exists but does not document list-change constraints
4. **n8n HeyReach nodes** (`github.com/bcharleson/n8n-nodes-heyreach`): Does not expose `UpdateSettings` in its 15 operations

---

## 2. The Answer: (a) A Supported Bind Route EXISTS

### The Endpoint

**`POST /api/public/campaign/UpdateSettings`**

### Request Body (`UpdateCampaignSettingsApiDto`)

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `campaignId` | long | Yes | Campaign must exist |
| `name` | string | Yes | 1–50 chars |
| `linkedInUserListId` | long | Yes | Must exist, must be type `USER_LIST` |
| `excludeContactedFromOtherCampaigns` | bool | No | default false |
| `excludeHasOtherAccConversations` | bool | No | default false |
| `excludeContactedFromSenderInOtherCampaign` | bool | No | default false |
| `excludeListId` | long? | No | Must not equal `linkedInUserListId` |

### What It Does

Updates a campaign's general settings: name, lead list, and exclusion options. The `linkedInUserListId` field is the replacement lead list.

### Critical Constraints

1. **Status restriction:** Can ONLY be called on campaigns in **DRAFT**, **SCHEDULED**, or **PAUSED** status. **CANNOT** be called on **ACTIVE** (IN_PROGRESS) or **COMPLETED** (FINISHED) campaigns.

2. **List locking:** The `linkedInUserListId` **cannot be changed after the campaign has started at least once**. Attempting to do so returns HTTP 400 with error "List changed after campaign has started".

3. **Side effect:** If the campaign is in SCHEDULED status, updating settings causes it to revert to DRAFT status.

4. **Does NOT activate:** Updating settings does NOT activate the campaign. Activation requires a separate `StartCampaign` or `Resume` call.

---

## 3. What Binding Does to Campaign State

### The Safety Question

**Does attaching a list to a FINISHED or PAUSED campaign start it sending?**

**Answer: NO.** The documentation explicitly states:
- `UpdateSettings` only modifies configuration
- Activation requires a separate `StartCampaign` or `Resume` call
- The `Create` endpoint documentation states you "must call `StartCampaign` separately to activate it"

**However**, for campaign 599020 (FINISHED status), `UpdateSettings` **cannot be called at all** due to the status restriction. The path for 599020 is answer **(b)**: create a NEW campaign around list 940797.

### For DRAFT/PAUSED Campaigns

If a campaign is DRAFT or PAUSED and has never started:
- Binding a list via `UpdateSettings` does NOT activate it
- The campaign remains in its current status (DRAFT or PAUSED)
- Activation is a separate, deliberate act

This is the same safety property as `Create`: the bind is configuration, not activation.

---

## 4. The Readback Requirement

### What "200 OK" Does NOT Prove

TASK-158 measured twelve body shapes that returned `addedLeadsCount: 0` with HTTP 200 — the silent drop. A 200 on this provider is not evidence that anything was bound.

### What the Readback MUST Prove

After calling `UpdateSettings`, the readback must:

1. **Read the campaign back** via `GET /campaign/GetById?campaignId={id}`
2. **Verify `linkedInUserListId`** matches the requested list id
3. **Verify `status`** is unchanged (DRAFT or PAUSED, not IN_PROGRESS)
4. **Verify the list's `campaignIds`** now includes this campaign id (via `GET /list/GetById?listId={id}`)

If any of these fail, the bind did not succeed regardless of the 200 response.

---

## 5. The Shortest Safe Sequence: Staged Lead to First Send

### Current State

- List 940797: UNBOUND, holds 1 staged lead (operator-approved, li1-li5 approved)
- Campaign 599020: FINISHED, 0 leads, cannot have its list changed

### Path: New Campaign Around List 940797

Since 599020 is FINISHED and cannot use `UpdateSettings`, the path is a new campaign.

#### Step 1: Create Campaign with List Binding

**Route:** `POST /campaign/Create`
**Body:**
```json
{
  "name": "<unique name>",
  "linkedInAccountIds": [174892],
  "linkedInUserListId": 940797,
  "sequence": <reproduced 24-node sequence from 599020>
}
```

**Verb in `providerwrites`:** `LINKEDIN_CREATE_CAMPAIGN`
**Exists in `SUPPORTED`:** **NO** — sealed
**Prospect-facing:** **NO** — creates in DRAFT, sends nothing

**What this does:** Creates a campaign in DRAFT status, bound to list 940797. The campaign holds ZERO leads (leads enroll when a campaign STARTS, not when it is created).

**Readback:** Verify `status == DRAFT`, `linkedInUserListId == 940797`, `campaignAccountIds == [174892]`.

#### Step 2: Start the Empty Campaign

**Route:** `POST /campaign/StartCampaign?campaignId={id}`
**Verb in `providerwrites`:** `LINKEDIN_ACTIVATE` (via `heyreach.start_empty_for_staging`)
**Exists in `SUPPORTED`:** **YES** — but only for campaigns with ZERO leads
**Prospect-facing:** **NO** — starts a campaign that holds nobody

**What this does:** Moves the campaign from DRAFT to IN_PROGRESS. Since the campaign holds zero leads, the sequence has nobody to act on.

**Safety gate:** `providerwrites` refuses this for any campaign the provider says holds a lead, read immediately before.

**Readback:** Verify `status == IN_PROGRESS`, `campaign_leads` returns `totalCount == 0`.

#### Step 3: Add Leads to the Campaign

**Route:** `POST /campaign/AddLeadsToCampaignV2`
**Verb in `providerwrites`:** `LINKEDIN_ADD_LEAD`
**Exists in `SUPPORTED`:** **YES** — but `CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False` reseals it
**Prospect-facing:** **YES** — adds a lead to an active campaign, the sequence acts on them

**What this does:** Adds the staged lead from list 940797 to the campaign. The lead enrolls and the sequence begins.

**Safety gate:** `LINKEDIN_ADD_LEAD` is CONDITIONAL on `CAMPAIGN_LEVEL_STAGING_IS_PROVEN`. The first line of its condition refuses while this is False.

**Readback:** Verify `campaign_leads` returns the lead, `GetCampaignsForLead` shows the campaign.

#### Step 4: The Lead Is Now in the Campaign

The lead is enrolled. The sequence will act on them according to the configured node graph. This is the first real send.

---

## 6. Why the Previous Completion Was Wrong

The previous TASK-216 completion (commit 24de8de5) stated:

> "The bind itself — attaching a list to a campaign — happens ONLY at campaign creation time via `POST /campaign/Create` with `linkedInUserListId`. There is no separate attach/detach verb."

This is **incorrect**. `POST /campaign/UpdateSettings` exists and can change the `linkedInUserListId` on an existing campaign, subject to the constraints documented above.

The previous completion searched only the in-codebase routes and did not check the vendor documentation or community sources as the task required. The vendor's own blog post (`https://www.heyreach.io/blog/campaign-api`) documents `UpdateSettings` with full schema.

### What This Changes

For a DRAFT or PAUSED campaign that has never started, the list binding can be changed without creating a new campaign. This is a different path than "create a new campaign" and may be relevant for future tasks.

For campaign 599020 (FINISHED), the answer is still effectively "create a new campaign" because `UpdateSettings` cannot be called on FINISHED campaigns. But the reason is different: not "there is no route" but "the route exists but cannot be used on this campaign's status".

---

## 7. Summary

| Question | Answer |
|----------|--------|
| Does a bind route exist? | **YES** — `POST /campaign/UpdateSettings` |
| Can it be used on campaign 599020? | **NO** — 599020 is FINISHED, route requires DRAFT/SCHEDULED/PAUSED |
| Does binding activate the campaign? | **NO** — activation requires separate `StartCampaign` or `Resume` |
| Can the list be changed after the campaign starts? | **NO** — returns 400 "List changed after campaign has started" |
| What is the path for 599020? | Create a NEW campaign around list 940797 |
| What must the readback prove? | `linkedInUserListId` matches, `status` unchanged, list's `campaignIds` includes the campaign |

---

## 8. Files Allowed

- `docs/HEYREACH-BIND-ROUTE-2026-09-16.md` (this file)
- `scripts/task216_*.py` (read-only probes against READ routes only) — not created, not needed

## 9. Files Forbidden

- `src/`, `work/`, `config/` — not touched

## 10. What Was Not Done

- No provider writes (no bind, no campaign creation, no activation, no lead add)
- No changes to `SUPPORTED` or `CONDITIONAL`
- No changes to `CAMPAIGN_LEVEL_STAGING_IS_PROVEN`
- No changes to list 940797, list 933603, or campaign 599020
- No profile URLs, prospect names, or domains committed
