# HeyReach List Staging Rehearsal — 2026-09-16

TASK-186. The LinkedIn staging path rehearsed end to end against a FAKE
transport. No real provider call was made.

## 1. The Entry Point

**The function:** `liststaging.stage_lead(list_id, row, transport, ...)`

This is the low-level primitive. It validates the lead, asserts the list is
safe (unbound), calls the transport, and reads back — the same four-step
shape `providerwrites.perform` uses for every other write.

**What it is NOT:** it does NOT go through `providerwrites.perform`. It takes
a transport callable directly. The verb `heyreach.add_lead_to_list` is NOT in
`SUPPORTED`, so `perform` would refuse it.

**What Claude should call when the verb is enabled:**

A wrapper that goes through `providerwrites.perform(LINKEDIN_ADD_LEAD_TO_LIST,
transport=..., readback=...)`. This wrapper does not exist yet. It belongs in
`liststaging.py` or a new `listfactory.py`, analogous to `bisonfactory.stage`.

**Why the wrapper matters:** `perform` carries the action ledger, the spend
ledger, the authorization check, and the staging-repeat guard. `stage_lead`
does none of these. When the verb is enabled, the wrapper must unify them.

**The gap proved by this rehearsal:**

```python
# stage_lead succeeds with a fake transport:
result = stage_lead(940797, LEAD_OK, fake_transport(), ...)
# → ACCEPTED

# The same write through perform refuses:
providerwrites.perform(LINKEDIN_ADD_LEAD_TO_LIST, transport=..., readback=...)
# → WriteUnsupported: "not supported in this build"
```

Two paths, one write, different gates. The wrapper that unifies them is the
missing piece.

## 2. The Refusal While the Verb is Off

**The most important test in the task.** With `heyreach.add_lead_to_list`
absent from `SUPPORTED`, calling the path through `perform` fails closed,
loudly, naming the missing permission.

```python
providerwrites.perform(
    LINKEDIN_ADD_LEAD_TO_LIST,
    transport=lambda p: None,
    readback=lambda: None)
# → WriteUnsupported: "heyreach.add_lead_to_list is not supported in this
#    build: DEFINED BUT NOT ENABLED. TASK-172. ..."
```

**What is proved:**

- The verb is in `OPERATIONS` (defined).
- The verb is NOT in `SUPPORTED` (not enabled).
- The verb is NOT in `CONDITIONAL` (no predicate wired).
- `perform` raises `WriteUnsupported` before the transport is touched.
- The refusal names the operation and the channel.

**The OFF switch works.** A verb that is defined but not enabled cannot be
called through the write gate. The transport is never reached.

## 3. Idempotency

**Is the write idempotent?** YES, for duplicates.

`AddLeadsToListV2` returns:

```json
{
  "addedLeadsCount": 0,
  "totalLeads": 1,
  "duplicateLeads": 1
}
```

The response shape distinguishes three outcomes:

| addedLeadsCount | duplicateLeads | totalLeads | Meaning                  |
|-----------------|----------------|------------|--------------------------|
| 1               | 0              | 1          | New lead added           |
| 0               | 1              | 1          | Lead was already there   |
| 0               | 0              | 0          | Silent drop (validation) |

**A duplicate is ACCEPTED.** The readback finds the lead present in the list.
The provider is idempotent: adding the same lead twice does not error, does
not double the lead, and returns `duplicateLeads: 1`.

**This is the opposite of EmailBison's sequence write.** `bison.set_sequence`
APPENDS — writing twice doubles the sequence. `heyreach.add_leads_to_list` is
idempotent — writing twice leaves one lead.

### Recovery Procedure for a Half-Failed Write

**Scenario:** The transport times out. Did the provider act? Unknown.

**DO NOT blindly retry.** The provider is idempotent for duplicates, so a
retry is safe — but the readback is the correct path, not a blind retry.

**DO:**

1. **Read provider truth first.**
   ```python
   from src.providers import heyreach
   members, total = heyreach.list_leads(list_id)
   ```

2. **Classify what you found:**
   - **Lead present, list unbound** → write succeeded. The timeout was in the
     response. Do NOT write again.
   - **Lead absent, list unbound** → write did not succeed. Safe to write now.
   - **Lead absent, list bound** → something attached the list to a campaign.
     Do NOT write. Investigate.
   - **Lead present, list bound** → the write succeeded AND the list became
     bound. The activation defect. Do NOT write. Investigate.

3. **The readback function:**
   ```python
   from src.liststaging import readback_list_add, classify_readback
   rb = readback_list_add(list_id, [url], ...)
   verdict = classify_readback(rb)
   # ACCEPTED → done
   # UNKNOWN  → lead missing, safe to retry
   # DRIFTED  → list became bound, investigate
   ```

## 4. The Readback

**`addedLeadsCount: 1` is the provider's claim about its own write.** What
proves the lead is present AND the list is still unbound?

`readback_list_add` performs two reads:

1. **`members_reader`** (default `heyreach.list_leads`) — is the lead there?
2. **`list_reader`** (default `heyreach.list_by_id`) — is the list still
   unbound?

**It fails if either half is false:**

| Lead present | List unbound | Verdict  |
|--------------|--------------|----------|
| Yes          | Yes          | ACCEPTED |
| No           | Yes          | UNKNOWN  |
| Yes          | No           | DRIFTED  |
| No           | No           | DRIFTED  |

**DRIFTED wins over UNKNOWN.** If the list became bound AND the lead is
missing, the activation defect is the more serious finding.

**The readback is the whole safety argument.** A 200 response is not a lead.
A membership read that finds the asked-for profile AND an unbound list is.

## 5. What Happens Between LIST and CAMPAIGN

**The staging path adds a lead to a LIST.** The list is unbound — attached to
no campaign. The payload has `listId` and `leads`. It has no `campaignId`.

**The moment the list is attached to a campaign, adding to it is adding to a
campaign.** The campaign-level gate (`LINKEDIN_ADD_LEAD` with its conditional
permission) is the only path through.

**The attachment step is where the full activation gate belongs.** Nothing in
the staging path can reach it by accident:

- `stage_lead` takes a `list_id`, not a `campaign_id`.
- The payload has no campaign field.
- The readback checks `campaignIds` and classifies DRIFTED if it is non-empty.
- The attachment operation is not in `SUPPORTED` and not wired anywhere.

**The sequence the rehearsal proves:**

```
QUALIFIED → LIST → READBACK → (stop here)
```

The path from LIST to CAMPAIGN is the attachment step (not enabled).
The path from CAMPAIGN to SEND is the activation step (sealed).

## 6. The 0/0/0 Trap

**THE TRAP:** a rehearsal that mocks the provider into agreeing is worthless.

The provider returns `addedLeadsCount: 0` with no error for a lead missing
`firstName` or `lastName`. A 200 response is not a success.

**The test:**

```python
transport = fake_transport(response={
    "addedLeadsCount": 0, "totalLeads": 0, "duplicateLeads": 0})
stage_lead(940797, LEAD_OK, transport, ...)
# → ListStagingUnverified: "UNKNOWN"
```

**The path treats the 0/0/0 response as FAILURE, not success.** The readback
finds the lead absent, the verdict is UNKNOWN, and `stage_lead` raises
`ListStagingUnverified`.

**This single behaviour is the difference between this path being safe and
losing leads invisibly.** It is what made the route look broken for a day.

**Two layers of defence:**

1. **Pre-transport validation:** `validate_lead_row` refuses a lead missing
   `firstName` or `lastName` before the transport is touched.
2. **Post-transport readback:** even if the transport succeeds with a 200,
   the readback finds the lead absent and raises Unverified.

## 7. Summary for Claude

**The function:** `liststaging.stage_lead(list_id, row, transport, ...)`

**The entry point that does not exist yet:** a wrapper that goes through
`providerwrites.perform(LINKEDIN_ADD_LEAD_TO_LIST, ...)`.

**The refusal:** `perform` raises `WriteUnsupported` because the verb is not
in `SUPPORTED`. The transport is never reached.

**Idempotency:** the provider is idempotent for duplicates. A retry is safe,
but the readback is the correct path.

**The readback:** checks presence AND unboundness. Fails if either is false.

**The gap:** nothing in the staging path can attach a list to a campaign.
The attachment step is where the activation gate belongs.

**The trap:** the 0/0/0 response is treated as failure. Two layers of
defence: pre-transport validation and post-transport readback.

**If the write fails halfway:**

1. Read `heyreach.list_leads(list_id)` FIRST.
2. If the lead is present and the list is unbound → done.
3. If the lead is absent and the list is unbound → safe to retry.
4. If the list is bound → investigate. The activation defect.

---

*Rehearsed 2026-09-16 against a fake transport. No real provider call was
made.*
*Tests: `tests/test_list_staging_rehearsal.py` (27 tests),
`tests/test_list_staging.py` (42 tests),
`tests/test_list_staging_permission.py` (31 tests).*
*Total: 100 tests, all passing.*
