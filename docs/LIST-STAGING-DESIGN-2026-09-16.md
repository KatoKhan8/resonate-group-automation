# List staging design — 2026-09-16

TASK-165. A staging primitive exists at the list level, proven against the
provider on 2026-09-15 (TASK-158). This document places it under the correct
gates without weakening any existing one.

## The path

    QUALIFIED -> LIST -> READBACK -> FINAL ELIGIBILITY -> CAMPAIGN -> SEND

Each arrow is a gate. The list step is not send-capable; the campaign step is.

## 1. Where the gates go

### List add: NOT prospect-facing, conditionally safe

A list add is safe BECAUSE the list is unbound — attached to no campaign.
Adding a lead to an unbound list reaches nobody. It does NOT need the
activation gate (`executionguard.authorize`), because no prospect is reached.

It DOES need a condition: the list must be proven unbound immediately before
every add. This is `liststaging.assert_list_safe`, and it reads the provider
via `heyreach.list_by_id`. It is a new operation in the staging layer, not an
entry in `providerwrites.SUPPORTED` — that is an operator decision.

**Function:** `liststaging.stage_lead(list_id, row, transport, readback_fn)`

**Gate sequence at the list step:**

1. `validate_lead_row(row)` — firstName and lastName required, provider
   silently drops leads missing either
2. `assert_list_safe(list_id)` — reads provider, refuses if `campaignIds`
   is non-empty
3. `transport(payload)` — POST `/list/AddLeadsToListV2`
4. `readback_fn(list_id, expected_urls)` — reads list members AND re-reads
   list binding; both must pass

### Campaign add: prospect-facing, full gate stack

Adding a lead to a campaign IS the activation step. It needs the COMPLETE
`executionguard.authorize` gate stack, with `require_conditional_permission`
for `LINKEDIN_ADD_LEAD` immediately before the POST — not earlier, with no
state read between the gate and the transport.

**Function:** `providerwrites.perform(LINKEDIN_ADD_LEAD, ...)` (existing)

**Gate sequence at the campaign step:**

1. `executionguard.authorize(operation=LINKEDIN_ADD_LEAD, ...)` — full stack
2. `providerwrites.require_conditional_permission(LINKEDIN_ADD_LEAD, ...)` —
   re-reads campaign, proves it cannot send
3. `authorization.spend()`
4. `transport(payload)` — POST `/campaign/AddLeadsToCampaignV2`
5. `readback()` — reads campaign members

**The gap between list readback and campaign gate must contain no provider
state read that could stale.** The list readback proves the lead is staged.
The campaign gate re-reads the campaign at the moment of the write. Between
those two, nothing must read the list's binding state and then reuse it —
the campaign gate reads the CAMPAIGN, not the list.

## 2. The safe-list predicate

**Function:** `liststaging.list_is_unbound(list_row)`

**Input:** A list row as returned by `heyreach.list_by_id(list_id)`.

**Predicate:** `campaignIds` is empty (zero-length list or absent).

```python
def list_is_unbound(list_row):
    """True only when the list is attached to no campaign.

    `campaignIds` is a provider fact that can change without us — a human can
    attach a list to a campaign in the vendor UI. The predicate reads the
    provider row, not a remembered state.
    """
    ids = list_row.get("campaignIds") or []
    return len(ids) == 0
```

**What must be asserted immediately before every add:**

`assert_list_safe(list_id)` calls `heyreach.list_by_id(list_id)`, checks
`list_is_unbound`, and raises `ListStagingRefused` otherwise. This is the
same shape as `_campaign_is_a_declared_staging_campaign` — a provider read
at the moment of the write, not a remembered state.

**Why "our list" is not the same as "a safe list":** Campaign 599020 has list
933603 ATTACHED. A list belonging to our tenant can still be bound to a
campaign. The safety property is `campaignIds == []`, not ownership.

**Tenant check:** The list must belong to our org_unit. `heyreach.list_by_id`
returns the list row, which carries `organizationUnitId` implicitly through
the credential scope. An explicit check: the list's org_unit must match the
campaign's org_unit. This is a secondary check after the binding check.

## 3. Readback

After an add, two things must be proven:

1. **The lead is present.** `heyreach.list_leads(list_id)` returns members.
   The lead's `profile_url` must appear in the returned set. `addedLeadsCount: 1`
   from the write response is the provider's claim about its own write — it
   is NOT a readback. The readback is a SEPARATE read.

2. **The list is still unbound.** `heyreach.list_by_id(list_id)` is called
   again after the write. `campaignIds` must still be empty. A list that was
   unbound before the add and bound after it means the add triggered a
   binding — the same activation defect the gate exists to prevent.

**Sufficient identification:** `profile_url` identifies the lead. The provider
returns `linkedInUserProfile.profileUrl` per member, which is the same field
sent in the write payload. `totalCount` alone is NOT sufficient — it proves a
count, not a specific lead. But `totalCount` is a useful secondary check: it
must be >= the expected count.

**Function:** `liststaging.readback_list_add(list_id, expected_urls)`

Returns:
```python
{
    "found": set,          # profile URLs found in the list
    "missing": set,        # profile URLs asked for but not found
    "total": int,          # totalCount from the provider
    "still_unbound": bool, # campaignIds is still empty
    "list_row": dict,      # the post-write list row
}
```

Classification:
- `ACCEPTED` iff `found == expected` AND `still_unbound` is True
- `DRIFTED` if the list became bound
- `UNKNOWN` if the lead is missing

## 4. The firstName/lastName trap

The provider SILENTLY DROPS a lead missing either field, returning
`addedLeadsCount: 0` with no error. A 200 response is not a success.

`validate_lead_row(row)` refuses BEFORE the transport:

```python
def validate_lead_row(row):
    """Refuse a lead that the provider would silently drop.

    firstName and lastName are required. The provider returns 0/0/0 with
    no error for a lead missing either — a 200 is not a success.
    """
    problems = []
    if not str(row.get("first_name") or "").strip():
        problems.append("firstName is required")
    if not str(row.get("last_name") or "").strip():
        problems.append("lastName is required")
    if not str(row.get("linkedin_url") or "").strip():
        problems.append("linkedin_url is required")
    if problems:
        raise ListStagingRefused(
            f"lead would be silently dropped: {'; '.join(problems)}")
    return True
```

## 5. Module placement

The code lives in `src/liststaging.py`, NOT in `src/linkedinstate.py`.
`linkedinstate.py` owns connection-axis state (pending, accepted, replied)
and has no concept of lists or staging. The list staging primitive is a
write-layer concern — it belongs alongside the other staging operations
(create-list, set-sequence) that `providerwrites` orchestrates.

`src/liststaging.py` is a new module because:
- It is not a provider adapter (that is `heyreach.py`)
- It is not the write gate (that is `providerwrites.py`, which this task
  may not modify)
- It is the orchestration between the two: validating, gating, transporting,
  and reading back a list add

When an operator decides to wire this into `providerwrites.SUPPORTED`, the
operation name is `LINKEDIN_ADD_LEAD_TO_LIST = "heyreach.add_lead_to_list"`
and it is NOT prospect-facing, with a `CONDITIONAL` entry pointing at
`assert_list_safe`.

## 6. What this does NOT do

- Does not add to `providerwrites.SUPPORTED` — operator decision
- Does not weaken or relocate an existing gate
- Does not execute a provider write
- Does not commit PII
