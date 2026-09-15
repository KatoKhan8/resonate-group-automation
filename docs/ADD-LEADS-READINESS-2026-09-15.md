# Add-Leads Readiness Report, 2026-09-15

**TASK-124 deliverable.** The add-leads door is shut because one line is missing
from `providerwrites.SUPPORTED`. This report removes every unknown from the
review so Claude can open that door with full information.

**Read-only throughout.** No POST that creates, adds, activates or modifies
anything. No lead added to any campaign. All prospect identifiers hashed.

---

## 1. THE REQUEST SHAPE, ESTABLISHED COMPLETELY

The endpoint is `POST https://api.heyreach.io/api/public/campaign/AddLeadsToCampaignV2`.

The request body is `{campaignId, accountLeadPairs}`. The structure comes from
`heyreach.build_lead_pairs` and `heyreach.add_leads_to_campaign`, both in
`src/providers/heyreach.py`.

### Exact body structure

```json
{
  "campaignId": 599020,
  "accountLeadPairs": [
    {
      "linkedInAccountId": 174892,
      "lead": {
        "profileUrl": "https://www.linkedin.com/in/example",
        "firstName": "John",
        "lastName": "Doe",
        "companyName": "Acme Corp",
        "position": "CEO",
        "customUserFields": [
          {"name": "note", "value": "Hi John, interested in connecting"},
          {"name": "record_id", "value": "rec_12345"},
          {"name": "contact_key", "value": "contact_abc"},
          {"name": "client", "value": "productive"},
          {"name": "sender_id", "value": "sender_xyz"},
          {"name": "sender_account_id", "value": "174892"},
          {"name": "Icebreaker", "value": "Saw your post about marketing agencies"},
          {"name": "Company_Size", "value": "50-100"}
        ]
      }
    }
  ]
}
```

### Field semantics

- **`campaignId`**: integer, the HeyReach campaign to populate.
- **`accountLeadPairs`**: array, one entry per lead.
- **`linkedInAccountId`**: integer, which HeyReach sender account sends to this
  lead. Per-lead, not per-batch: a single push can carry leads from multiple
  senders. Falls back to the caller-supplied default when the row has no
  `provider_account_id`.
- **`lead.profileUrl`**: string, the LinkedIn profile URL. Required.
- **`lead.firstName`**, **`lead.lastName`**, **`lead.companyName`**,
  **`lead.position`**: strings, optional but sent when present.
- **`lead.customUserFields`**: array of `{name, value}` pairs. Always carries:
  - `note` (unconditional, even if empty)
  - `record_id`, `contact_key`, `client`, `sender_id`, `sender_account_id`
    (when present in the row)
  - Any keys from the row's `custom_fields` dict (campaign-specific variables
    like `Icebreaker`)

### What `supplied_field_names` reports

With no rows (a probe): `['note', 'record_id', 'contact_key', 'client',
'sender_id', 'sender_account_id']`

With rows: the **intersection** of what each row actually produces. A field
only counts when every row has it - one lead missing it is one prospect
receiving the fallback, and `refuse_unsupported_sequence` checks the live
sequence against what this actually produces.

### The caller chain

1. `heyreach.add_leads_to_campaign(campaign_id, rows, linkedin_account_id)`
   builds the pairs and posts them.
2. The caller goes through `providerwrites.perform`, which owns the
   authorization, the readback and the classification.
3. `providerwrites.SUPPORTED` does NOT contain `LINKEDIN_ADD_LEAD`, so
   `perform` raises `WriteUnsupported` before the transport is called.

---

## 2. THE RESPONSE SHAPE, WHAT IS KNOWN AND UNKNOWN

**The response body of `AddLeadsToCampaignV2` itself has never been read.**
This is the stated unknown, and it is the reason the route is not in
`SUPPORTED`.

### What is known

- The endpoint is on `WRITE_ROUTES`, so the transport can call it.
- The request shape is established from `build_lead_pairs`.
- The readback uses `/campaign/GetLeadsFromCampaign`, which is already wired
  and returns per-lead membership with lifecycle state.

### What is unknown until a live call

1. **What the response body contains on success.** Does it return per-lead
   status? A count? A simple `{success: true}`?
2. **What it returns for a lead already in the campaign.** Does it skip,
   error, or return a per-lead "already exists" status?
3. **What it returns for a lead it rejects** (bad URL, wrong org, etc.).
   Per-lead error, or batch failure?
4. **Whether it is atomic (all-or-nothing) or per-lead.** If 50 leads are
   sent and 43 land, what does the response say, and what does the readback
   show?

### What the readback buys

The readback is what decides the verdict - not the status code or the response
body. A 200 with no membership confirmation is not a success; a membership
read that finds every asked-for lead is.

`heyreach.readback_membership(campaign_id, expected_urls)` pages through the
whole campaign (bounded at 50 pages / 5000 leads) and returns:
- `found`: set of profile URLs found in the campaign
- `missing`: set of profile URLs asked for but not found
- `total`: the campaign's reported total lead count
- `per_lead`: list of per-lead state dicts from `campaign_leads`

**This is the proof mechanism.** A write whose readback finds every lead is
`ACCEPTED`. A write whose readback finds none is `REFUSED` or `UNKNOWN`
depending on the HTTP status. A write whose readback finds some is `DRIFTED`
and needs a human.

---

## 3. PROOF THAT LEAD READBACK WORKS ON A CAMPAIGN WITH LEADS

Campaign 565765 (`PRODUCTIVE - SOFTWARE DEVELOPMENT - JELENA - AUGUST 24`) has
1000 leads. The readback was tested on this campaign.

### Readback results

```
Campaign name: PRODUCTIVE - SOFTWARE DEVELOPMENT - JELENA - AUGUST 24
Campaign status: IN_PROGRESS

Total leads read: 1000
Provider reported total: 1000

Lead state distribution:
  request_sent: 831
  accepted: 100
  failed: 48
  replied: 21
```

### Sample leads (URLs hashed)

```
1. hash=9500ffa44929cac0 state=accepted
   campaign=Failed connection=ConnectionAccepted message=MessageSent
2. hash=e40c0d0c1c818b32 state=failed
   campaign=Failed connection=None message=None
3. hash=773bf6fcea0ff778 state=failed
   campaign=Failed connection=None message=None
```

### readback_membership test

Five sample URLs were passed to `readback_membership`:
- Found: 5
- Missing: 0
- Total in campaign: 1000

**The readback works.** It pages through the whole campaign, matches profile
URLs case-insensitively, and returns per-lead lifecycle state. A write to
`AddLeadsToCampaignV2` can be verified by reading back the leads after.

### What this proves

- `/campaign/GetLeadsFromCampaign` is wired and returns per-lead membership.
- The lifecycle state (`leadCampaignStatus`, `leadConnectionStatus`,
  `leadMessageStatus`) is readable for each lead.
- The readback can confirm whether a write landed.

### What this does not prove

- The response shape of `AddLeadsToCampaignV2` itself.
- Whether the write is atomic or per-lead.
- What happens on partial failure.

Those require a live write, and that is Claude's decision.

---

## 4. FAILURE CLASSIFICATION: WHAT DOES A PARTIAL ADD LOOK LIKE?

The failure classes are defined in `providerwrites`:
- **`ACCEPTED`**: provider confirmed and read-back agreed.
- **`REFUSED`**: provider declined before acting. Retryable.
- **`UNKNOWN`**: we cannot say whether it acted. NEVER retryable.
- **`DRIFTED`**: it acted, and read-back disagrees with what we asked for.
  Never retryable; needs a human.

### What the code does today

`heyreach.add_leads_to_campaign` returns the raw provider response. The caller
(`providerwrites.perform`) would need to:
1. Read the response (shape unknown).
2. Call `readback_membership` with the expected URLs.
3. Compare `found` vs `missing` and classify.

The classification logic is not yet written because the response shape is
unknown. The readback is wired and works, so the classification can be written
once the first live write is read.

### What it should do

**Scenario 1: All leads land.**
- Response: 200, body unknown.
- Readback: `found` == `expected`, `missing` == empty.
- Verdict: `ACCEPTED`.

**Scenario 2: Provider refuses the batch.**
- Response: 4xx or 5xx.
- Readback: not called (no point).
- Verdict: `REFUSED` if 4xx (retryable after fixing the request), `UNKNOWN`
  if 5xx (cannot say whether it acted).

**Scenario 3: Partial add - 50 sent, 43 land.**
- Response: 200, body may say "43 added, 7 failed" or may say nothing.
- Readback: `found` == 43, `missing` == 7.
- Verdict: `DRIFTED`. The provider acted, but not fully. Needs a human to
  decide: retry the 7? Investigate why they failed? Accept the 43?

**Scenario 4: Timeout or network error.**
- Response: none.
- Readback: called anyway, because the provider may have acted.
- If readback finds all leads: `ACCEPTED` (it acted, we just didn't get the
  response).
- If readback finds none: `UNKNOWN` (cannot say whether it acted).
- If readback finds some: `DRIFTED` (it acted partially).

### The one rule that matters most

After a write, READ BACK BEFORE DECIDING ANYTHING. Never retry because the
client did not receive a response: a timeout says nothing about whether the
provider acted, and `actionledger` refuses a retry until provider truth
settles the reservation.

### What is not yet wired

The classification logic for partial adds. The readback is wired; the
decision tree that reads the response and the readback together is not. It
can be written after the first live write, because that is when the response
shape becomes known.

---

## 5. THE STALE OPERATIONS ENTRIES, CORRECTED

### LINKEDIN_CREATE_LIST

**Current entry in `providerwrites.OPERATIONS`:**
> "no documented route; the list was created by hand in the vendor UI"

**What actually happened:**
List 933603 was created on 2026-09-13 at 10:33:37Z by
`heyreach.create_list`, which POSTs to `/list/CreateEmptyList`. That route is
on `WRITE_ROUTES`. The list was created one second before campaign 599020, as
part of the same factory run that built the campaign.

**Evidence:**
- `src/providers/heyreach.py:1459` defines `create_list`, which calls
  `_write_body("/list/CreateEmptyList", ...)`.
- `docs/HEYREACH-PROVIDER-2026-09-15.md` confirms list 933603 exists, is
  named the same as the campaign, and is bound to campaign 599020.
- The list was created by the system, not by hand in the vendor UI.

**Corrected entry:**
> "SUPPORTED as of 2026-09-13. POST /list/CreateEmptyList is on WRITE_ROUTES
> and list 933603 was created through it, one second before campaign 599020.
> The list is empty (0 leads) and reaches nobody, which is what makes this
> safe: an empty list is a container with no prospects. Not prospect-facing.
> The vendor documents no delete for a list, only DeleteLeadsFromList, so a
> list created here stays in the client's estate for good and the name is not
> a detail."

### LINKEDIN_CREATE_CAMPAIGN

**Current entry in `providerwrites.OPERATIONS`:**
> "no documented route; POST /campaign/GetById already answers 405 and nothing
> suggests a create verb exists on the public API"

**What actually happened:**
Campaign 599020 was created on 2026-09-13 at 10:33:38Z by
`heyreach.create_campaign`, which POSTs to `/campaign/Create`. That route is
on `WRITE_ROUTES`. The campaign is in DRAFT status with 0 leads and
`startedAt` null.

**Evidence:**
- `src/providers/heyreach.py:1492` defines `create_campaign`, which calls
  `_write_body("/campaign/Create", ...)`.
- `docs/HEYREACH-PROVIDER-TRUTH-2026-09-15.md` confirms campaign 599020
  exists, is in DRAFT, was created 2026-09-13, and has never started.
- The campaign was created by the system, not by hand.

**Corrected entry:**
> "SUPPORTED as of 2026-09-13. POST /campaign/Create is on WRITE_ROUTES and
> campaign 599020 was created through it. The campaign is in DRAFT with 0
> leads and startedAt null, which is what makes this safe: a DRAFT sends
> nothing until it is resumed, and Resume is deliberately absent from
> WRITE_ROUTES. Not prospect-facing. The vendor documents no campaign delete,
> so a campaign created here stays in the client's estate for good and the
> name is the only recovery key."

### Why these entries were stale

The module docstring in `providerwrites.py` said "`SUPPORTED` is empty. Every
attempt refuses." for long enough that it was quoted as current on 2026-09-15
while six routes were enabled. The same happened to these two entries: they
were written before the routes were established, and nobody updated them when
the routes were added to `WRITE_ROUTES` and used.

A document about the environment that is believed without checking is how
somebody reasons correctly to a wrong conclusion.

---

## 6. WHAT REMAINS UNKNOWN

This is the list Claude is reviewing when the door opens.

1. **The response shape of `AddLeadsToCampaignV2`.** Unknown until a live
   call. The readback is the proof mechanism, not the response body.

2. **Whether the write is atomic or per-lead.** Unknown until a live call.
   The readback will show whether all, some, or none of the leads landed.

3. **What happens on partial failure.** Unknown until a live call. The
   readback will show which leads landed; the response body (once read) will
   say what the provider thinks happened.

4. **The classification logic for partial adds.** Not yet written. The
   readback is wired; the decision tree that reads the response and the
   readback together can be written after the first live write.

5. **Whether `providerwrites.SUPPORTED` should contain `LINKEDIN_ADD_LEAD`.**
   Claude's decision. The mechanism exists; the door is shut by one line.

---

## 7. WHAT THE FIRST WRITE BUYS

A single live write to `AddLeadsToCampaignV2`, on campaign 599020 (which has
0 leads and is in DRAFT), with a canary lead or a small cohort:

1. **The response shape becomes known.** The transport returns whatever the
   provider sends, and that response is recorded.

2. **The readback confirms whether it landed.** `readback_membership` pages
   through the campaign and reports which leads are present.

3. **The failure classification can be written.** With the response shape
   known, the decision tree that classifies ACCEPTED / REFUSED / UNKNOWN /
   DRIFTED can be implemented and tested.

4. **The door can be opened with full information.** Claude can enable
   `LINKEDIN_ADD_LEAD` in `SUPPORTED` knowing exactly what the request shape
   is, what the response shape is, and how partial failures are handled.

**The readback is already wired and proven.** The only missing piece is the
write itself, and that is Claude's decision.

---

## 8. RECOMMENDED CLAUDE ACTION

1. **Review this report.** Confirm the request shape, the readback proof, and
   the failure classification.

2. **Decide whether to enable `LINKEDIN_ADD_LEAD` in `SUPPORTED`.** This is
   the door. The mechanism exists; the permission is the missing piece.

3. **If enabling, perform a canary write.** Campaign 599020 has 0 leads and
   is in DRAFT. Add one lead or a small cohort, read the response, read back
   the membership, and record the response shape.

4. **Write the classification logic.** With the response shape known,
   implement the decision tree that classifies the write result.

5. **Correct the stale OPERATIONS entries.** Update `LINKEDIN_CREATE_LIST`
   and `LINKEDIN_CREATE_CAMPAIGN` to reflect what actually happened.

---

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** (to be filled after commit)

**TESTS:** Read-only throughout. No tests run; no writes performed. The
readback proof was performed against live provider truth (campaign 565765,
1000 leads) and confirmed that `/campaign/GetLeadsFromCampaign` returns
per-lead membership with lifecycle state.

**FILES CHANGED:**
- `docs/ADD-LEADS-READINESS-2026-09-15.md` (this file)

**FINDINGS:**
1. The request shape for `AddLeadsToCampaignV2` is fully established from
   `build_lead_pairs` and `add_leads_to_campaign`.
2. The response shape is unknown until a live call. The readback is the proof
   mechanism, not the response body.
3. Lead readback works on campaign 565765 (1000 leads). The readback pages
   through the whole campaign and returns per-lead lifecycle state.
4. The failure classification for partial adds is not yet written. The
   readback is wired; the decision tree can be written after the first live
   write.
5. The OPERATIONS entries for `LINKEDIN_CREATE_LIST` and
   `LINKEDIN_CREATE_CAMPAIGN` are stale. Both routes are on `WRITE_ROUTES`
   and were used to create list 933603 and campaign 599020 on 2026-09-13.

**RISKS:**
- The response shape of `AddLeadsToCampaignV2` is unknown. The first write
   will reveal it.
- Partial failure handling is not yet implemented. The readback will show
   what landed; the classification logic can be written after.
- The OPERATIONS entries are stale and may mislead future readers.

**RECOMMENDED CLAUDE ACTION:**
Review this report, decide whether to enable `LINKEDIN_ADD_LEAD` in
`SUPPORTED`, and if enabling, perform a canary write to establish the response
shape.
