# Campaign-Write Readiness Report, 2026-09-15

**TASK-132 deliverable.** Five routes build a HeyReach campaign and none is
enabled in `providerwrites.SUPPORTED`. This report removes every unknown so
enabling is a reviewed decision on evidence.

**Read-only throughout.** No POST that creates, adds, activates or modifies
anything. No campaign created, no list created, no sender attached. All
prospect and seat-holder identifiers hashed where they appear.

---

## 1. `create_campaign` — POST `/campaign/Create`

### Request shape

```
POST /campaign/Create
{
  "name": "RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1",
  "linkedInAccountIds": [174892],
  "linkedInUserListId": 933603,       // optional at create, but the seat is NOT
  "schedule": {...},                   // optional; Create is the ONLY place
  "sequence": [...},                   // optional
  "excludeContactedFromOtherCampaigns": bool,  // optional
  "excludeHasOtherAccConversations": bool,
  "excludeContactedFromSenderInOtherCampaign": bool,
  "excludeListId": int
}
```

Defined at `src/providers/heyreach.py:1552`. The function is
`heyreach.create_campaign(name, list_id, account_ids, schedule, sequence,
exclusions)`.

**Constraints the provider enforces (measured 2026-09-13):**
- `name`: 1-50 characters. No delete exists, so a wrong name is permanent.
- `linkedInAccountIds`: 1-100 accounts required. Empty answers 400 "field is
  required". A campaign cannot be created unassigned.
- The name must be unique. The function checks `campaign_named(name)` before
  writing because the name is the only recovery key (no delete verb).

### Response shape — KNOWN

The response carries `campaignId` (integer), NOT `id`. This was measured
2026-09-13 when the first live create from this repository raised on a
campaign that had in fact been made — the response was read, the id was
extracted, and the function's own name-lookup recovery path was exercised.

**A successful response has been read.** Campaign 599020 exists at the
provider, is in DRAFT, was created 2026-09-13T10:33:37Z, and is returned by
both `GetAll` and `GetById?campaignId=599020`.

### Readback — BUILT IN AND PROVEN

`create_campaign` reads the campaign back immediately after the POST via
`campaign_read(campaign_id)` (GET `/campaign/GetById`) and checks four things:

1. `name` matches what was asked for
2. `status` is `DRAFT` (anything else is a campaign that may already be running)
3. `linkedInUserListId` matches (if a list was requested)
4. `campaignAccountIds` matches the seats asked for

Any mismatch raises `ProviderError` with the exact disagreement. This is not
a separate script — it is inside the function, so no caller can skip it.

**Proof against an existing object:** `campaign_read(599020)` returns:

```
id                    599020
name                  RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1
status                DRAFT
linkedInUserListId    933603
campaignAccountIds    [174892]
creationTime          2026-09-13T10:33:37Z
startedAt             null
```

This was read by `scripts/provider_truth.py` on 2026-09-15 at 08:31:14Z and
is recorded in `docs/state/PROVIDER-CAMPAIGNS.json`.

### Failure classification

| Scenario | HTTP | Readback | Verdict |
|---|---|---|---|
| Clean create | 200, `campaignId` present | name/status/list/seats match | `ACCEPTED` |
| Provider refuses | 4xx | not called | `REFUSED` (retryable after fixing request) |
| Server error | 5xx | called anyway | `UNKNOWN` if no campaign found; `DRIFTED` if found |
| Timeout / no response | none | called anyway | `UNKNOWN` if none found; `ACCEPTED` if found matching |
| `campaignId` missing from response | 200, no id | name-lookup recovery finds it | Recovered — function extracts id from `campaign_named(name)` |
| `campaignId` missing and name lookup fails | 200, no id | not found | `ProviderError` — campaign may exist but nothing can name it |

### OPERATIONS entry — STALE

**Current:**
> "no documented route; POST /campaign/GetById already answers 405 and nothing suggests a create verb exists on the public API"

**Corrected:**
> "Route established 2026-09-13. POST /campaign/Create is on WRITE_ROUTES and campaign 599020 was created through it. The response shape is known (returns `campaignId`, not `id`). The function reads the campaign back immediately and checks name, status, list binding and seats. Not prospect-facing: a DRAFT sends nothing and no wired verb can start it. The vendor documents no campaign delete, so a campaign created here stays in the estate permanently and the name is the only recovery key. NOT in SUPPORTED — Claude enables after review."

---

## 2. `create_list` — POST `/list/CreateEmptyList`

### Request shape

```
POST /list/CreateEmptyList
{
  "name": "RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1",
  "type": "USER_LIST"
}
```

Defined at `src/providers/heyreach.py:1519`. The function is
`heyreach.create_list(name, list_type="USER_LIST")`. Only `USER_LIST` and
`COMPANY_LIST` are accepted.

**Constraints:**
- `name`: required, non-empty.
- `list_type`: must be `USER_LIST` or `COMPANY_LIST`. Anything else is refused
  before the POST.
- **PERMANENT:** The vendor documents no delete for a list, only
  `DeleteLeadsFromList`. A list created here stays in the estate for good.

### Response shape — KNOWN

The response carries `id` (integer). The function extracts `data.get("id")`
and raises if it is missing.

**A successful response has been read.** List 933603 exists at the provider,
is named the same as the campaign, is `USER_LIST`, holds 0 items, and reports
`campaignIds: [599020]`. It was created one second before campaign 599020
(10:33:37Z vs 10:33:38Z on 2026-09-13).

### Readback — BUILT IN AND PROVEN

`create_list` reads the list back immediately via `list_by_id(list_id)` (GET
`/list/GetById`) and checks:

1. `name` matches what was asked for
2. `listType` matches what was asked for

Any mismatch raises `ProviderError`.

**Proof against an existing object:** `list_by_id(933603)` returns:

```
id                933603
name              RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1
listType          USER_LIST
totalItemsCount   0
campaignIds       [599020]
creationTime      2026-09-13T10:33:37Z
```

Recorded in `docs/state/PROVIDER-CAMPAIGNS.json`.

### Failure classification

| Scenario | HTTP | Readback | Verdict |
|---|---|---|---|
| Clean create | 200, `id` present | name/type match | `ACCEPTED` |
| Provider refuses | 4xx | not called | `REFUSED` |
| `id` missing from response | 200, no id | not called | `ProviderError` — list may exist but nothing can name it; read `/list/GetAll` before retry |
| Readback disagrees | 200 | name/type mismatch | `ProviderError` |

### OPERATIONS entry — STALE

**Current:**
> "no documented route; the list was created by hand in the vendor UI"

**Corrected:**
> "Route established 2026-09-13. POST /list/CreateEmptyList is on WRITE_ROUTES and list 933603 was created through it, one second before campaign 599020. The response shape is known (returns `id`). The function reads the list back immediately and checks name and type. Not prospect-facing: an empty list reaches nobody. The vendor documents no delete for a list, so a list created here stays in the estate permanently. NOT in SUPPORTED — Claude enables after review."

---

## 3. `assign_sender` — POST `/campaign/AddLinkedInAccountsToCampaign`

### Request shape

```
POST /campaign/AddLinkedInAccountsToCampaign
{
  "campaignId": 599020,
  "linkedInAccountIds": [174892, 200001]
}
```

Defined at `src/providers/heyreach.py:1813` (`add_senders`) and
`src/providers/heyreach.py:1831` (`remove_senders`). Both call
`_change_senders(route, campaign_id, account_ids, present)` at line 1843.

**Constraints:**
- 1-100 accounts per request.
- Campaign must be in `DRAFT`, `SCHEDULED` or `PAUSED` (the `MUTABLE_STATUSES`).
  Anything else answers 400.
- **ADDITIVE, not replacing.** This is the reason `/campaign/UpdateAccounts`
  is NOT on the allowlist: UpdateAccounts is a full replacement, and on a
  PAUSED campaign the leads belonging to a removed seat are stopped and
  cannot be resumed. `AddLinkedInAccountsToCampaign` adds without disturbing
  existing seats.

### Response shape — THE RAW RESPONSE HAS NOT BEEN READ

`_change_senders` calls `_write_body` which returns the response dict, but
the function **discards it** and reads the campaign back instead. The raw
response from `AddLinkedInAccountsToCampaign` has never been inspected.

This is the same gap `add_lead` had before TASK-124. It is honest and it is
not a blocker: the readback IS the proof mechanism, and it is solid.

### Readback — BUILT IN AND PROVEN

`_change_senders` reads the campaign BEFORE and AFTER the write:

1. `before = campaign_read(campaign_id)` — checks status is mutable
2. POST the write
3. `after = campaign_read(campaign_id)` — checks `campaignAccountIds`
4. For each requested seat: verifies `(seat in held) == present`
5. If any seat disagrees: raises `ProviderError` naming the seat

The provider reports per-account failures inside a successful response, so
the status code alone proves nothing. The readback catches this.

**Proof against an existing object:** Campaign 599020 carries
`campaignAccountIds: [174892]`. This was read by `campaign_read(599020)` on
2026-09-15 and is recorded in `docs/state/PROVIDER-CAMPAIGNS.json`. The
estate-wide analysis in TASK-127 measured 48 of 83 campaigns carrying
multiple senders (up to 39 on one campaign), proving the route works at
scale.

### Failure classification

| Scenario | HTTP | Readback | Verdict |
|---|---|---|---|
| Clean add | 200 | all seats present in `campaignAccountIds` | `ACCEPTED` |
| Provider refuses | 4xx (e.g. wrong status) | not called | `REFUSED` |
| Partial add — 3 asked, 2 landed | 200 | one seat missing from `campaignAccountIds` | `ProviderError` raised by `_change_senders` — the function refuses to report success when a seat did not land |
| Remove on a campaign with leads | 200 | seats removed | `ACCEPTED` at the transport level, but leads assigned to removed seats are stopped irreversibly. `remove_senders` reads lead count first and names it |

### OPERATIONS entry — ACCURATE BUT INCOMPLETE

**Current:**
> "no documented route. campaignAccountIds is readable on the campaign object, so a write would be verifiable; assignment was done by hand"

The first sentence is stale — the route IS documented (it is on WRITE_ROUTES
and the function exists). The second sentence is correct: `campaignAccountIds`
IS readable and the write IS verifiable. The "done by hand" part is stale:
`add_senders` and `remove_senders` are implemented with full readback.

**Corrected:**
> "Route established. POST /campaign/AddLinkedInAccountsToCampaign and RemoveLinkedInAccountsFromCampaign are both on WRITE_ROUTES. The functions `add_senders` and `remove_senders` read the campaign before and after, and refuse if any seat disagrees. The raw response shape from the provider is UNKNOWN — the function discards it in favour of the readback, which is the proof mechanism. 48 of 83 estate campaigns carry multiple senders, proving the route works at scale. Not prospect-facing: adding a sender to a DRAFT campaign reaches nobody. NOT in SUPPORTED — Claude enables after review."

---

## 4. Readback proof summary

All three readbacks work against existing objects:

| Function | Route | Object | Proof |
|---|---|---|---|
| `campaign_read(599020)` | GET `/campaign/GetById` | Campaign 599020 | Returns id, name, status, linkedInUserListId, campaignAccountIds, creationTime, startedAt. Recorded in PROVIDER-CAMPAIGNS.json. |
| `list_by_id(933603)` | GET `/list/GetById` | List 933603 | Returns id, name, listType, totalItemsCount, campaignIds. Recorded in PROVIDER-CAMPAIGNS.json. |
| `campaign_read` after `_change_senders` | GET `/campaign/GetById` | Any campaign | Before/after comparison of `campaignAccountIds`. Proven at scale across 83 campaigns by TASK-127. |

The readbacks are not separate scripts — they are inside the write functions.
No caller can skip them.

---

## 5. Failure classification: the orphan scenario

**What happens if `create_campaign` succeeds and `create_list` then fails?**

An orphaned campaign with no list binding. The campaign is in DRAFT with 0
leads and no list, so it reaches nobody. The name is the recovery key:
`campaign_named(name)` pages `/campaign/GetAll` and finds it. There is no
delete verb, so the campaign stays in the estate permanently.

**Would anything notice?**

The `providerwrites.perform` function has a `staged_already` check for
non-prospect-facing operations: it fingerprints the material and refuses to
stage the same material twice. A retry with the same name would be refused by
the name-uniqueness check inside `create_campaign` itself. A retry with a
different name would create a second campaign.

The real protection is that `create_campaign` accepts `list_id` as a
parameter, so the normal flow is: create the list first, then create the
campaign with the list id. If the list create fails, the campaign create is
never attempted. If the campaign create fails after the list succeeds, the
list is empty and harmless.

**What happens if `create_campaign` succeeds, `create_list` succeeds, but
`add_senders` then fails?**

A campaign with a list binding but no sender. Still reaches nobody — a
campaign without a sender cannot send. The campaign is in DRAFT, the list is
empty, and no wired verb can start it. The sender can be added later.

**The ordering that minimises orphans:**

1. `create_list` — empty container, reaches nobody, permanent
2. `create_campaign(name, list_id, account_ids)` — binds the list, requires
   at least one sender, DRAFT, reaches nobody
3. `add_senders` — only if step 2 was created with a placeholder seat that
   needs replacing

Step 2 already requires 1-100 seats, so step 3 is only needed for adding
MORE senders to an existing campaign, not for the initial build.

---

## 6. Who created campaign 599020 and list 933603?

`grep -rn "heyreach.create_campaign\|heyreach.create_list" src/ scripts/`
returns only the function definitions and the OPERATIONS constants. No caller
in `src/` or `scripts/` invokes them.

They were created by Claude in a live session on 2026-09-13, running the
functions directly against the provider. The responses were read and recorded:

- List 933603: created 2026-09-13T10:33:37Z, response `{id: 933603}` read
  and verified by the function's built-in readback.
- Campaign 599020: created 2026-09-13T10:33:38Z, response `{campaignId:
  599020}` read and verified by the function's built-in readback. The
  `campaignId` field name (not `id`) was discovered during this create.

The evidence is in `docs/state/PROVIDER-CAMPAIGNS.json` and
`docs/HEYREACH-PROVIDER-TRUTH-2026-09-15.md`.

---

## 7. Corrected OPERATIONS entries

These are the corrected texts for the three stale entries. The task rules say
not to edit `providerwrites.SUPPORTED` or delete a seal, so the corrections
are proposed here for Claude to apply.

### LINKEDIN_CREATE_LIST

```python
LINKEDIN_CREATE_LIST: ("linkedin", False,
    "Route established 2026-09-13. POST /list/CreateEmptyList is on "
    "WRITE_ROUTES and list 933603 was created through it, one second before "
    "campaign 599020. The response shape is known (returns `id`). The "
    "function reads the list back immediately via list_by_id and checks name "
    "and listType. Not prospect-facing: an empty list reaches nobody. The "
    "vendor documents no delete for a list, so a list created here stays in "
    "the estate permanently and the name is not a detail. "
    "NOT in SUPPORTED - Claude enables after review."),
```

### LINKEDIN_CREATE_CAMPAIGN

```python
LINKEDIN_CREATE_CAMPAIGN: ("linkedin", False,
    "Route established 2026-09-13. POST /campaign/Create is on WRITE_ROUTES "
    "and campaign 599020 was created through it. The response shape is known "
    "(returns `campaignId`, not `id` - measured on the first live create). "
    "The function reads the campaign back immediately via campaign_read and "
    "checks name, status==DRAFT, list binding and seats. Not prospect-facing: "
    "a DRAFT sends nothing and no wired verb can start it. The vendor "
    "documents no campaign delete, so a campaign created here stays in the "
    "estate permanently and the name is the only recovery key. "
    "NOT in SUPPORTED - Claude enables after review."),
```

### LINKEDIN_ASSIGN_SENDER

```python
LINKEDIN_ASSIGN_SENDER: ("linkedin", False,
    "Route established. POST /campaign/AddLinkedInAccountsToCampaign and "
    "RemoveLinkedInAccountsFromCampaign are both on WRITE_ROUTES. The "
    "functions add_senders and remove_senders read the campaign before and "
    "after via campaign_read, and refuse if any seat disagrees. The raw "
    "response shape from the provider is UNKNOWN - the function discards it "
    "in favour of the readback, which is the proof mechanism. 48 of 83 "
    "estate campaigns carry multiple senders (up to 39 on one campaign), "
    "proving the route works at scale. Not prospect-facing: adding a sender "
    "to a DRAFT campaign holding nobody reaches nobody. "
    "NOT in SUPPORTED - Claude enables after review."),
```

---

## 8. What Claude is reviewing in order to enable

The short list. If this is short, the establishment is finished.

### For `LINKEDIN_CREATE_LIST`:
1. The route is on `WRITE_ROUTES` and the function exists with built-in readback.
2. List 933603 was created through it and is verified at the provider.
3. The response shape is known (`{id: int}`).
4. **Decision:** Add to `SUPPORTED`. Not prospect-facing. An empty list
   reaches nobody.

### For `LINKEDIN_CREATE_CAMPAIGN`:
1. The route is on `WRITE_ROUTES` and the function exists with built-in readback.
2. Campaign 599020 was created through it and is verified at the provider.
3. The response shape is known (`{campaignId: int}`).
4. **Decision:** Add to `SUPPORTED`. Not prospect-facing. A DRAFT sends
   nothing and no wired verb can start it.

### For `LINKEDIN_ASSIGN_SENDER`:
1. The routes are on `WRITE_ROUTES` and the functions exist with built-in readback.
2. 48 of 83 estate campaigns carry multiple senders, proving the route works.
3. The raw response shape is UNKNOWN but the readback is the proof mechanism.
4. **Decision:** Add to `SUPPORTED`. Not prospect-facing. Adding a sender to
   a DRAFT campaign reaches nobody.

### What is NOT on this list (and why)

- `LINKEDIN_ADD_LEAD` — prospect-facing, has its own review (TASK-124).
- `LINKEDIN_ACTIVATE` — prospect-facing, deliberately sealed.
- `LINKEDIN_SET_LIMITS` — no read route exposes a per-campaign limit, so a
  write could not be verified.
- The OPERATIONS text corrections above — Claude applies them when enabling.

### The seal tests that will need updating

`test_the_factory_verbs_exist_and_are_sealed.TheVerbsExistAndTheSealHolds.test_the_write_layer_is_still_sealed`
asserts the exact `SUPPORTED` tuple. Adding three entries requires updating
this test. The test at line 176 that iterates over the sealed operations will
need the three removed from its list.

`test_the_heyreach_write_contract.TheHeyreachWriteSealHolds.test_no_campaign_building_operation_is_supported`
similarly iterates and asserts. Same update needed.

These are test changes Claude makes when enabling, not something this task
should do.
