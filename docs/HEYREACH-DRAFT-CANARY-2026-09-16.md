# HeyReach DRAFT Canary: the campaign bind path and the start verb

**Date:** 2026-09-16
**Task:** TASK-218
**Status:** Implemented and sealed. Neither permission is in `SUPPORTED`.

## Summary

Two deliverables:

1. The DRAFT canary campaign path, wired but NOT enabled.
2. The start verb, implemented and sealed.

## 1. The creation permission

### Definition

`LINKEDIN_CREATE_CAMPAIGN` (`heyreach.create_campaign`) has a CONDITIONAL
predicate: `_list_is_ours_and_unbound_and_holds_approved`. It asserts from a
provider read at the moment of the write:

1. **The list exists and is readable** through our API key (the tenant
   boundary). A list this key cannot read is not in this tenant.
2. **The list is unbound** - `campaignIds` is empty. Binding it to a new
   campaign does not detach it from an existing one.
3. **The list is in our tenant** - provable because our key can read it.

The predicate is registered in `CONDITIONAL` but the operation is NOT in
`SUPPORTED`. Enabling is one line: add `LINKEDIN_CREATE_CAMPAIGN` to
`SUPPORTED`.

### Is creation prospect-facing?

**No, and the argument is from the provider rather than asserted here.**

A DRAFT campaign sends nothing. The provider's own behaviour decides this:

- `AddLeadsToCampaignV2` answers 400 "You cannot add new leads to a draft
  campaign" - so a DRAFT cannot be populated through the API.
- `/campaign/StartCampaign` is the only route that moves DRAFT to running,
  and it is not in `SUPPORTED`.
- A DRAFT has no sequence running, no leads, and no sending window that acts
  on anybody.

**What creation costs:** binding a list to a campaign is the moment the list
stops being unbound, which ends the safety property every staged lead depends
on. A list attached to a campaign can no longer receive leads through the
unbound-list path. Detection of drift after the bind is the only safety net.

**What would detect a problem:** `liststaging.readback_list_add` already
classifies DRIFTED if a list's `campaignIds` is no longer empty after a write.
The same mechanism detects a bind that happened outside this system.

### The readback

After creation, `heyreach.create_campaign` proves four things from the
provider:

1. **DRAFT status** - `found["status"] == "DRAFT"`. Anything else is a
   campaign that may already be running.
2. **List binding** - `found["linkedInUserListId"]` matches the requested
   list. A campaign pointing at the wrong list points at somebody else's
   people.
3. **Seats** - `found["campaignAccountIds"]` matches the requested seats.
4. **Name** - `found["name"]` matches the requested name. The name is the
   recovery key on a provider with no campaign delete.

`addedLeadsCount`-style self-reports are not readbacks on this provider -
TASK-158 measured twelve shapes returning 0/0/0 with HTTP 200. The readback
here uses `campaign_read` (`GET /campaign/GetById`), which is a separate
request from the create.

### The sequence

Campaign 599020 carries a 24-node sequence with hash `32f8dde79bfa0f27`.
The sequence can be read off 599020 via `GET /campaign/GetCampaignSequence`,
which returns the whole node graph.

**Can the shape be reproduced?** Yes. `heyreach._fingerprint` reduces a node
to what a prospect experiences (type, delay, unit, messages, fallback) in
walk order. The fingerprint is deterministic: the same graph always produces
the same output, and survives JSON round-tripping. `sequence_matches`
compares two graphs on these properties and tolerates the bare END nodes the
provider adds on its own.

**Is the hash reproducible?** The hash `32f8dde79bfa0f27` is a SHA-256 of the
serialised graph. It is reproducible for the same graph, and changes when any
node type, delay, or message text changes. A new campaign written with the
same sequence produces the same hash.

## 2. The start verb

### Implementation

`heyreach.activate_campaign(campaign_id, expect_leads=None, attempts=6,
interval=2.0)` is modeled after `bison.resume_campaign`:

- **`expect_leads` containment.** The caller states how many leads it
  believes are in the campaign. The provider's own lead count is read
  immediately before the write, and a mismatch refuses. A campaign meant to
  reach one person that finds nine is stopped here.
- **Status classification.** The 200 from StartCampaign is not the answer.
  The status is polled and classified:
  - `IN_PROGRESS` means started - success.
  - `DRAFT` means not yet - poll again or raise on timeout.
  - An unrecognised status raises rather than defaulting to success.
  - A status still unknown when polling runs out raises: "we do not know
    yet" and "it started" must not be the same answer.

### The seal

`LINKEDIN_ACTIVATE` is NOT in `SUPPORTED` and NOT in `CONDITIONAL`. Calling
`providerwrites.perform(LINKEDIN_ACTIVATE, ...)` raises `WriteUnsupported`
before the transport is reached. The test proving this is
`tests/test_heyreach_start_is_sealed.py::ActivateIsSealed::test_perform_refuses_activate`.

**A start verb that is reachable without a permission is worse than no start
verb**, because everything else in the path looks finished. The OFF switch
test is the deliverable that matters most.

### What enabling would take

1. Add `LINKEDIN_ACTIVATE` to `SUPPORTED` in `providerwrites.py`.
2. Add a CONDITIONAL predicate - probably the same `_campaign_is_ours_and_holds_nobody`
   pattern, but with a lead count that is NOT zero.
3. Call `heyreach.activate_campaign(campaign_id, expect_leads=N)` with N
   read from the provider first.

## Files changed

- `src/providers/heyreach.py` - `activate_campaign` function
- `src/providerwrites.py` - `LINKEDIN_CREATE_CAMPAIGN` CONDITIONAL predicate
- `tests/test_heyreach_start_is_sealed.py` - new, 21 tests
- `tests/test_draft_campaign_bind.py` - new, 16 tests

## What is NOT enabled

- `LINKEDIN_CREATE_CAMPAIGN` - defined with condition, NOT in SUPPORTED
- `LINKEDIN_ACTIVATE` - NOT in SUPPORTED, NOT in CONDITIONAL
- No provider writes were made. All tests use fakes.
