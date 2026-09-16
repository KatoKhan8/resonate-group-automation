# LIST-VERB-PROPOSAL-2026-09-16

## The verb

| Field | Value |
|-------|-------|
| Constant | `LINKEDIN_ADD_LEAD_TO_LIST` |
| String | `heyreach.add_lead_to_list` |
| Channel | linkedin |
| Prospect-facing | No |
| Module | `src/liststaging.py` |
| Defined in | `src/providerwrites.py` (line 108) |
| In OPERATIONS | Yes |
| In SUPPORTED | **No** |
| In CONDITIONAL | **No** |

The verb adds a lead to a HeyReach list, not a campaign. TASK-158 proved the
route works (`/list/AddLeadsToList`), TASK-165 designed the path, and neither
could name the permission because it did not exist. This task defines it.

## Schema enforcement

The provider accepts `profileUrl`, `firstName`, `lastName`, `companyName`,
`position`. Of these, `firstName` and `lastName` are required: the provider
returns `addedLeadsCount: 0` with no error for a lead missing either - a 200
response that is not a success.

Schema enforcement is in `liststaging.validate_lead_row`, which runs BEFORE
the transport is touched. It refuses with every problem named, so a caller
sees all of them rather than one at a time.

## The condition predicate

The predicate is `liststaging.assert_list_safe`. It answers one question from
a provider read taken at the moment of the write:

> Is this list's `campaignIds` empty?

The predicate reads the list from the provider via `heyreach.list_by_id` (or
an injected reader for testing). It refuses unless:

1. A `list_id` is supplied (not None, not empty, not zero).
2. The provider read succeeds (an exception is a refusal, fail-closed).
3. The response contains a row with an `id` field.
4. `campaignIds` is an empty list.

When the predicate is wired into `CONDITIONAL` (an operator decision not made
by this task), it will be called by `providerwrites.perform` before the
transport is touched, the same way `_campaign_is_a_declared_staging_campaign`
guards `LINKEDIN_ADD_LEAD`.

### What the predicate checks

| Check | How |
|-------|-----|
| List is unbound | `campaignIds` is empty, read live from provider |
| List exists | Provider read returns a row with an `id` |
| List is readable | Provider read does not raise |

### What the predicate cannot check

| Question | Why not |
|----------|---------|
| Is this list ours? | The HeyReach list API returns no ownership field. `LIST_FIELDS` is `(id, name, listType, totalItemsCount, campaignIds, creationTime)`. There is no `createdBy`, `ownerId`, or `tenantId`. |
| Is this list in our tenant? | Same reason. The API scopes reads to the tenant of the API key, so a list readable by our key is in our tenant by construction - but this is an assumption about the provider's auth model, not a field we verify. |

The predicate checks what it can (unbound) and refuses everything else
fail-closed. A list that is bound - to any campaign, in any tenant, created
by anyone - is refused. The limitation is that a list we did not create but
that IS unbound would pass the predicate. This is documented and accepted:
the risk is staging a lead into a list that already exists in the tenant, not
into one owned by another tenant (which the API key scoping prevents).

## What the condition cannot promise

A list unbound at the moment of the write can be attached to a campaign a
second later by anyone with provider access. The predicate is a
point-in-time check, not a lock. Between the read and the write, a human can
attach the list to a campaign in the vendor UI, and the write would then add
a lead to a campaign - the prospect-facing path this module deliberately is
not.

**What detects the attachment afterwards:** `liststaging.readback_list_add`
re-reads the list after every write and checks two things:

1. Is the lead present in the list? (via `heyreach.list_leads`)
2. Is the list still unbound? (via `heyreach.list_by_id`)

If the list became bound between the pre-write check and the post-write
readback, the verdict is `DRIFTED` and `stage_lead` raises
`ListStagingUnverified`. The provider may have acted; the ledger is left for
human reconciliation.

This is the same shape as every other write in `providerwrites.perform`:
read back before deciding anything, and classify the result.

## The refusal tests

Every test is in `tests/test_list_staging_permission.py`. Every test uses a
fake transport and fake provider reads. No test reaches a real API.

| # | Scenario | Expected | Test class |
|---|----------|----------|------------|
| 1 | List attached to campaign 599020 | `ListStagingRefused` | `TestRefusalListAttachedToCampaign` |
| 2 | List in another tenant (campaignIds names foreign campaigns) | `ListStagingRefused` | `TestRefusalListInAnotherTenant` |
| 3 | List not ours (client-made, bound to their campaign) | `ListStagingRefused` | `TestRefusalListNotOurs` |
| 4 | Missing firstName | `ListStagingRefused` | `TestRefusalMissingFirstName` |
| 5 | Missing lastName | `ListStagingRefused` | `TestRefusalMissingLastName` |
| 6 | 0/0/0 silent-drop response | `ListStagingUnverified` | `TestSilentDropResponse` |
| 7 | Condition not consulted (validation fails first) | `ListStagingRefused`, safety not called | `TestConditionNotConsulted` |
| 8 | Provider read unavailable (exception) | `ListStagingRefused`, fail-closed | `TestProviderReadUnavailable` |
| 9 | Verb not in SUPPORTED | `WriteUnsupported` from `perform` | `TestPerformRefuses` |

All 31 tests pass. Exit code 0.

## The case for enabling it

**What it buys:** a staging path that reaches nobody. A list attached to no
campaign is a holding area, not an outreach channel. Adding a lead to such a
list is safe in the same way that creating a DRAFT campaign is safe: the
lead sits there until a human attaches the list to a campaign and starts it.

**What becomes possible:** populating a list through the API instead of by
hand in the vendor UI. This is the primitive TASK-165 designed: stage leads
into a list, review them, attach the list to a campaign when ready. The list
is the buffer between "we have a person's URL" and "we are sending to them".

**The safety argument:** the predicate refuses a bound list, the readback
catches a list that became bound during the write, and the verb is not
prospect-facing because an unbound list sends nothing.

## The case against enabling it

**What it risks:** the predicate is a point-in-time check, not a lock.
Between the read and the write, a human can attach the list to a campaign.
The readback catches this after the fact, but the lead is already in the
list - and if that list is now attached to a RUNNING campaign, the sequence
may act on the lead immediately.

**What stays impossible:** enabling this verb does not enable adding a lead
to a campaign. `LINKEDIN_ADD_LEAD` has its own condition
(`_campaign_is_a_declared_staging_campaign`) and its own safety argument.
The two verbs are separate doors with separate keys.

**The operator's question:** is the buffer value (API-driven list
population) worth the race condition (a list bound between check and write)?
The readback catches the race and classifies it DRIFTED, but catching it
after the lead is already in a campaign-bound list is not the same as
preventing it. The campaign-level gate (`LINKEDIN_ADD_LEAD`) refuses the
write up front; the list-level gate refuses up front too, but cannot guarantee
the list stays unbound for the millisecond the write takes.

## The decision

**Not enabled.** The constant is defined, the predicate is written, the
refusals are tested, and the verb is in OPERATIONS. It is NOT in SUPPORTED
and NOT in CONDITIONAL. Enabling is an operator decision that requires:

1. Adding `LINKEDIN_ADD_LEAD_TO_LIST` to `SUPPORTED` in `providerwrites.py`.
2. Adding `CONDITIONAL[LINKEDIN_ADD_LEAD_TO_LIST] = assert_list_safe`.
3. Accepting the race condition as a known risk, documented here.

Until then, the verb fails closed: `providerwrites.perform` raises
`WriteUnsupported` with a message naming the operation and the channel.
