# TASK-216: Find the supported list-to-campaign bind

## Status: DONE

## Objective

Find and document the supported mechanism by which a HeyReach list is bound
to a campaign — what the provider primitive is, what the codebase wraps
around it, what gates it, and what the current state of enablement is.

## RESULT

**STATUS:** DONE
**COMMIT:** (see below)
**TESTS:** Not a code-change task; investigation only. Existing tests in
  `tests/test_list_staging.py`, `tests/test_list_staging_permission.py`,
  and `tests/test_list_staging_rehearsal.py` cover the path.
**FILES CHANGED:** This task file only.
**FINDINGS:** Below.
**RISKS:** None — read-only investigation.
**RECOMMENDED CLAUDE ACTION:** Review findings. The bind is fully traced.

---

## FINDINGS

### 1. The provider primitive

The list-to-campaign bind is a field on the campaign object, not a separate
attach/detach verb. HeyReach's `POST /campaign/Create` accepts
`linkedInUserListId` in the body, and that is the ONLY route that attaches a
list to a campaign. There is no separate "bind list to campaign" endpoint.

**Code:** `src/providers/heyreach.py`, `create_campaign()` (line ~1670):
```python
body = {"name": name, "linkedInAccountIds": seats}
if list_id is not None:
    body["linkedInUserListId"] = int(list_id)
```

The campaign object carries `linkedInUserListId` (singular integer or null).
A campaign holds exactly one list or zero. The list object carries
`campaignIds` (array), and a list can be attached to many campaigns
simultaneously — measured up to 8 in the live estate.

### 2. The cardinality

- **Campaign → List:** One-to-zero-or-one. `linkedInUserListId` is singular.
- **List → Campaign:** One-to-many. `campaignIds` is an array. Measured:
  list 668409 (33,710 leads) is attached to 8 campaigns simultaneously.

### 3. The two sides of the bind

**From the campaign side** (read via `GET /campaign/GetById`):
- Field: `linkedInUserListId` — integer or null
- Read by: `heyreach.campaign_read()`, projected via `CAMPAIGN_FIELDS`
- Stored canonically as: `campaign["heyreach_list_id"]`

**From the list side** (read via `GET /list/GetById`):
- Field: `campaignIds` — array of campaign ids
- Read by: `heyreach.list_by_id()`, projected via `LIST_FIELDS`
- The safety predicate: `liststaging.list_is_unbound()` checks this is empty

### 4. The canonical row

`src/campaigns.py`, `material()` (line 301):
```python
"heyreach_list_id": campaign.get("heyreach_list_id"),
```
This is part of the campaign fingerprint. Changing the list id moves the
fingerprint, which invalidates any prior approval. The list id is
launch-sensitive.

### 5. The configdiff comparison

`src/configdiff.py` compares both sides:
- Canonical side (line 382): `"list_id": str(campaign.get("heyreach_list_id") or "")`
- Provider side (line 535): `"list_id": str(row.get("linkedInUserListId") or "")`

A mismatch fails the diff. The list id is one of the fields that
`scripts/declare_campaign_shape.py` adopts from a provider readback.

### 6. The safety predicate (list-level staging)

`src/liststaging.py`, `assert_list_safe(list_id)`:
- Reads the list from the provider via `heyreach.list_by_id()`
- Checks `campaignIds` is empty
- Refuses if the list is bound to ANY campaign
- This is a live provider read at the moment of the write, not a remembered state

The predicate is wired into `CONDITIONAL`:
```python
CONDITIONAL[LINKEDIN_ADD_LEAD_TO_LIST] = _list_is_unbound_right_now
```
(`src/providerwrites.py` line 784)

### 7. The operation and its enablement state

| Property | Value |
|----------|-------|
| Constant | `LINKEDIN_ADD_LEAD_TO_LIST` |
| String | `"heyreach.add_lead_to_list"` |
| In `OPERATIONS` | Yes (line 183) |
| In `SUPPORTED` | **Yes** (line 447, enabled 2026-09-16) |
| In `CONDITIONAL` | **Yes** (line 784, predicate: `_list_is_unbound_right_now`) |
| Prospect-facing | **No** |
| Module | `src/liststaging.py` |
| Transport | `heyreach.add_leads_to_list()` → `POST /list/AddLeadsToListV2` |

### 8. The full staging path

```
liststaging.stage_lead(list_id, row, transport)
  ├── validate_lead_row(row)          # firstName, lastName, profileUrl
  ├── assert_list_safe(list_id)       # live provider read, campaignIds == []
  ├── providerwrites.perform(         # the gate layer
  │     LINKEDIN_ADD_LEAD_TO_LIST,
  │     provider_campaign_id=list_id, # NOTE: list id, not campaign id
  │     transport=_transport,
  │     readback=_readback,
  │     expected={"class": "ACCEPTED"},
  │   )
  │   ├── _list_is_unbound_right_now()  # CONDITIONAL predicate, re-reads
  │   ├── action ledger
  │   ├── spend ledger
  │   ├── killswitch
  │   └── idempotency check
  └── readback_list_add()             # prove lead present AND list still unbound
```

### 9. The bind step (list → campaign attachment)

The bind itself — attaching a list to a campaign — happens ONLY at campaign
creation time via `POST /campaign/Create` with `linkedInUserListId`. This
operation (`LINKEDIN_CREATE_CAMPAIGN`) is **NOT in SUPPORTED**. There is no
separate attach/detach verb.

This means:
- A list can be filled safely (unbound, via `LINKEDIN_ADD_LEAD_TO_LIST`)
- But attaching that list to a campaign requires creating a new campaign
  with the list id in the body — and campaign creation is sealed
- Once attached, adding to the list is adding to a campaign, and the
  campaign-level gate (`LINKEDIN_ADD_LEAD`) is the only path through

### 10. What is supported end-to-end

The supported path is:

1. **Create a list** — `LINKEDIN_CREATE_LIST` is NOT in SUPPORTED (no
   documented route was the old reason; `/list/CreateEmptyList` IS on
   `WRITE_ROUTES` and `heyreach.create_list` IS implemented)
2. **Add leads to the list** — `LINKEDIN_ADD_LEAD_TO_LIST` IS in SUPPORTED
   and CONDITIONAL (enabled 2026-09-16 by operator authorization)
3. **Attach list to campaign** — `LINKEDIN_CREATE_CAMPAIGN` is NOT in
   SUPPORTED. The bind is a campaign-create-time parameter
4. **Add leads to the campaign** — `LINKEDIN_ADD_LEAD` IS in SUPPORTED and
   CONDITIONAL, but `CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False` reseals it

So the list-to-campaign BIND is not itself a supported operation. What IS
supported is adding leads to an unbound list (step 2), and the bind (step 3)
remains sealed because it requires campaign creation.

### 11. The two Resonate-owned lists

| List ID | Name | Bound? | Campaign | Notes |
|---------|------|--------|----------|-------|
| 933603 | RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1 | **BOUND** | 599020 (FINISHED) | NOT safe to stage into |
| 940797 | RESONATE - STAGING PROBE - DO NOT USE | **UNBOUND** | none | Safe by predicate, holds 1 probe lead |

### 12. Key files

| File | Role |
|------|------|
| `src/providers/heyreach.py` | Transport: `create_campaign`, `create_list`, `add_leads_to_list`, `list_by_id`, `list_leads` |
| `src/liststaging.py` | Safety layer: validate, gate, transport, readback |
| `src/providerwrites.py` | Write gate: `SUPPORTED`, `CONDITIONAL`, `perform()` |
| `src/campaigns.py` | Canonical state: `heyreach_list_id` in `material()` and fingerprint |
| `src/configdiff.py` | Diff: compares canonical `heyreach_list_id` vs provider `linkedInUserListId` |
| `scripts/declare_campaign_shape.py` | Adopts provider shape into canonical row |
| `scripts/probe_list_staging.py` | Live probe: does adding to a list activate a campaign? |
| `docs/LIST-STAGING-DESIGN-2026-09-16.md` | Design document |
| `docs/HEYREACH-LIST-ESTATE-2026-09-16.md` | Live estate enumeration |
| `docs/LIST-VERB-PROPOSAL-2026-09-16.md` | Verb proposal and safety argument |
| `docs/HEYREACH-LIST-SCHEMA-2026-09-15.md` | Provider schema |
