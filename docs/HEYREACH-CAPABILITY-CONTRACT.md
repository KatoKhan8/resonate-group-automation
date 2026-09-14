# HeyReach Capability Contract

Which HeyReach routes could answer "is this profile an Open Profile?" and
"can this seat send an InMail?" - and which cannot. Derived from the adapter
and its fixtures without a live call.

Written for TASK-002. Extends TASK-025's funnel enumeration.

## The two capabilities

| Capability | Constant | Verdict |
|---|---|---|
| Open Profile detection | `CAP_OPEN_PROFILE` = `linkedin.open_profile_message` | **UNSUPPORTED** |
| InMail eligibility | `CAP_INMAIL` = `linkedin.inmail` | **UNSUPPORTED** |

Neither can be answered from any wired read route. The adapter already
records this: `OPEN_PROFILE_DETECTABLE = False` and
`INMAIL_ELIGIBILITY_DETECTABLE = False`. This document states what was
looked for, where, and what each absence means.

## CAP_OPEN_PROFILE - UNSUPPORTED

**Question:** Is this prospect an Open Profile member who can receive a
direct message without a connection?

**What was looked for:**

A field named `openProfile`, `isOpenProfile`, `isOpen`, `premium`,
`connectionDegree`, or any boolean/enum indicating Open Profile status.

**Where it was looked for:**

1. `POST /lead/GetLead` - 23 keys returned. None indicate Open Profile
   status. The adapter's `PROFILE_FIELDS` tuple lists them: `headline`,
   `position`, `companyName`, `about`, `summary`, `location`, `industry`,
   `profileUrl`, `linkedin_id`, `firstName`, `lastName`. No premium flag,
   no connection degree, no open-profile indicator.

2. `POST /campaign/GetLeadsFromCampaign` - `linkedInUserProfile` sub-object
   carries 16 keys. None indicate Open Profile status.

3. `POST /inbox/GetConversationsV2` - `correspondentProfile` carries
   profile metadata. `correspondentProfile.connections` is an integer
   follower/connection count, not a status. No open-profile field.

4. `POST /li_account/GetAll` - seat-level data. No prospect attributes.

5. `GET /campaign/GetCampaignSequence` - the node graph.
   `CHECK_IS_OPEN_PROFILE` is a documented branching node type. It can
   branch on Open Profile status INSIDE a running sequence. But it is a
   branch node, not a query: no external caller can read its answer. It was
   NOT observed in any of the 82 campaigns read on 2026-09-13 (1194 nodes:
   END 396, LIKE_POST 300, MESSAGE 227, VIEW_PROFILE 135,
   CONNECTION_REQUEST 39, CHECK_IS_CONNECTION 35, SEND_LEAD_TO_BISON 24,
   FOLLOW 23, INMAIL 15 - zero CHECK_IS_OPEN_PROFILE).

**What the absence means:**

Open Profile status is decidable INSIDE a running HeyReach graph (via
`CHECK_IS_OPEN_PROFILE`) and nowhere else. A planner cannot know it in
advance. A report cannot state it afterwards. The strongest supported
design is to branch rather than predict, which is what `linkedin_sequence`
does when it builds a graph with the open-profile alternative.

**Cheapest live read to settle it:**

None. The provider does not expose this as a queryable field on any read
route. `CHECK_IS_OPEN_PROFILE` works inside a sequence graph, but its
answer is not readable from outside the graph. A live call would not change
this verdict.

**What would change the verdict:**

The vendor adds a field to `/lead/GetLead` or `/campaign/GetLeadsFromCampaign`
that indicates Open Profile status, and a wired read route reads it back.

## CAP_INMAIL - UNSUPPORTED

**Question:** Can this specific prospect receive an InMail from this seat?

**What was looked for:**

A lead-level field indicating InMail eligibility, reachability, or
acceptance likelihood.

**Where it was looked for:**

1. `POST /lead/GetLead` - 23 keys. No InMail eligibility field.

2. `POST /campaign/GetLeadsFromCampaign` - per-lead fields are
   `leadCampaignStatus`, `leadConnectionStatus`, `leadMessageStatus`,
   `lastActionTime`, `failedTime`, `errorCode`, `linkedInUserProfileId`.
   No InMail eligibility field.

3. `POST /li_account/GetAll` - seat-level `accountLimits` carries
   `inMailLimit`, `inMailLimitMax`, `inMailCooldown`. These describe OUR
   seat's capacity (how many InMails we can send, how long until we can
   send more), not whether a specific prospect can receive one. A seat with
   InMail credit says nothing about whether this person will accept an
   InMail.

4. `POST /inbox/GetConversationsV2` - conversation metadata. No InMail
   eligibility field.

5. `POST /campaign/GetLeadsFromCampaign` - `linkedInUserProfile` (16 keys).
   No InMail eligibility field.

**What the adapter already says:**

`INMAIL` is a real node type. It appears 15 times across the 82 sequences
in this workspace. The payload shape is `messages: [{subject, message}]`
and `fallbackMessage: {subject, message}` - objects, not strings, because
an InMail has a subject line. The adapter handles this correctly:
`INMAIL_MESSAGE_FIELDS = ("subject", "message")`.

What cannot be read is whether a given prospect can receive one. The
capacity fields (`inMailLimit`, `inMailLimitMax`, `inMailCooldown`) are
readable at seat level but answer a different question: "can WE send"
rather than "can THEY receive."

**What the absence means:**

An InMail is attempted rather than targeted. A seat out of InMail credit
fails that step. A prospect who cannot receive InMails fails silently or
with a provider error the sequence must handle. The planner cannot
pre-filter for InMail reachability.

**Cheapest live read to settle it:**

None. The provider does not expose prospect-level InMail eligibility on
any read route. The vendor documents no such endpoint.

**What would change the verdict:**

The vendor adds a lead-level InMail eligibility field to
`/lead/GetLead` or `/campaign/GetLeadsFromCampaign`, and a wired read
route reads it back. Alternatively, a `CONNECTION_REQUEST_ACCEPTED` webhook
or `POST /MyNetwork/IsConnection` could be wired into the allowlist and
used to infer reachability - but neither is on any allowlist and neither
has ever been called from this repository.

## What IS readable

For completeness, the response fields every wired read route returns:

### POST /campaign/GetAll (READ_ROUTES)

14 fields per campaign row:
`campaignAccountIds`, `creationTime`,
`excludeContactedFromSenderInOtherCampaign`,
`excludeHasOtherAccConversations`, `excludeInOtherCampaigns`,
`excludeListId`, `id`, `linkedInUserListId`, `linkedInUserListName`,
`name`, `organizationUnitId`, `progressStats`, `startedAt`, `status`.

`progressStats` sub-object (7 fields):
`totalUsers`, `totalUsersExcluded`, `totalUsersFailed`,
`totalUsersFinished`, `totalUsersInProgress`, `totalUsersManuallyStopped`,
`totalUsersPending`.

### POST /inbox/GetConversationsV2 (READ_ROUTES)

Per conversation: `lastMessageSender`, `correspondentProfile`, `messages`,
`campaignIds`, `searchString`, `leadProfileUrl`, `linkedInAccountIds`.
`correspondentProfile.connections` is an integer count, not a status.
`CONNECTION_STATUS_AVAILABLE = False` for this route: no invitation state,
no acceptedAt, no connectionStatus.

### POST /lead/GetLead (READ_ROUTES_ALL)

23 keys including: `headline`, `position`, `companyName`, `about`,
`summary`, `location`, `industry`, `profileUrl`, `linkedin_id`,
`firstName`, `lastName`, `experiences`, `education`, `emailEnrichments`.
No open-profile flag. No InMail eligibility.

### POST /li_account/GetAll (READ_ROUTES_ALL)

Seat-level fields: `accountLimits`, `activeCampaigns`, `authIsValid`,
`connectionNoteCooldown`, `connectionRequestCooldown`, `emailAddress`,
`firstName`, `id`, `inMailCooldown`, `isActive`, `isValidNavigator`,
`isValidRecruiter`, `lastName`, `profileUrl`, `searchCooldown`.

`accountLimits` sub-object (12 fields): `followLimit`, `followLimitMax`,
`messageLimit`, `messageLimitMax`, `inMailLimit`, `inMailLimitMax`,
`profileViewLimit`, `profileViewLimitMax`, `postLikeLimit`,
`postLikeLimitMax`, `connectioRequestLimit` (vendor typo, load-bearing),
`connectioRequestMax`.

### POST /campaign/GetLeadsFromCampaign (READ_ROUTES_ALL)

Per lead: `id`, `leadCampaignStatus`, `leadConnectionStatus`,
`leadMessageStatus`, `lastActionTime`, `failedTime`, `errorCode`,
`linkedInUserProfileId`, `linkedInSenderId`, `creationTime`,
`linkedInUserProfile` (16-key sub-object including `profileUrl`).

### POST /stats/GetOverallStats (READ_ROUTES_ALL)

`overallStats` sub-object with four counters per campaign.

### POST /list/GetAll (READ_ROUTES_ALL)

List metadata.

### POST /campaign/GetCampaignsForLead (READ_ROUTES_ALL)

Per-campaign, per-lead status. Collision detection.

### GET /campaign/GetCampaignSequence (READ_GET_ROUTES)

Full node graph: every step, delay, message variant, fallback. Node types
observed across 82 campaigns (1194 nodes): END 396, LIKE_POST 300,
MESSAGE 227, VIEW_PROFILE 135, CONNECTION_REQUEST 39, CHECK_IS_CONNECTION
35, SEND_LEAD_TO_BISON 24, FOLLOW 23, INMAIL 15.

### GET /campaign/GetById (READ_GET_ROUTES)

Same 14 fields as `/campaign/GetAll`.

### GET /list/GetById (READ_GET_ROUTES)

List details.

## The capability table in this build

`src/linkedinstate.py` CAPABILITIES:

| Capability | Proven | Reason |
|---|---|---|
| `linkedin.connection_request` | True | CONNECTION_REQUEST observed in real sequences |
| `linkedin.message` | True | MESSAGE observed in real sequences |
| `linkedin.open_profile_message` | False | Nothing reads whether a profile is open |
| `linkedin.inmail` | False | No InMail eligibility field at lead level |

A step naming an unproven capability is HELD by `plan_step` with
`HELD_CAPABILITY_UNPROVEN` as the code. This is asserted by 17 behavioural
tests in `tests/test_task002_capability_contract.py`.

## What TASK-025 already settled

TASK-025 enumerated the full LinkedIn funnel (targeted through meeting) and
classified each stage. Its findings on the two capabilities here:

- CAP_OPEN_PROFILE: classified as unproven. TASK-025 found that
  `leadobserve.observe()` has no caller in `src/`, so even if the provider
  could answer, nothing asks. The acceptance verdict was UNDETERMINED.
- CAP_INMAIL: classified as unproven. TASK-025 found that the only InMail
  fields are seat-level cooldowns, not prospect eligibility.
- Both capabilities are False in the CAPABILITIES table, and steps naming
  them are HELD.

TASK-025 wrote 9 behavioural tests asserting the hold path. This task
extends that with 17 tests that additionally assert:
- The capability table's shape (proven vs unproven, unknown refused)
- The counterfactual (flipping the table entry is the ONLY change needed)
- The ordering (capability gate fires before prospect-state checks)
- Every shipped sequence's capabilities are classified

## The one live call this document recommends

None. Both capabilities are UNSUPPORTED from the available surface, and no
single live call would change either verdict. What would change them is a
vendor change (a new field on an existing route) or a new route being added
to the allowlist. Neither is an engineering task for this repository today.

If the vendor adds an Open Profile field or an InMail eligibility field,
the verdicts change by adding a read route and flipping a CAPABILITIES
entry. Until then, the planner correctly holds every step that depends on
either, and the cadence runs its proven touches without silently dropping
the unproven ones.
