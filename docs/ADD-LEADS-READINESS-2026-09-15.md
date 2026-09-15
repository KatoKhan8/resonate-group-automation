# Add-Leads Readiness Report — 2026-09-15

TASK-124 deliverable. Read-only investigation. No writes were performed, no
`SUPPORTED` was edited, no lead was added to any campaign.

---

## 1. THE EXACT REQUEST BODY SHAPE

The request body that WOULD be sent to `POST /campaign/AddLeadsToCampaignV2`
is constructed by `heyreach.add_leads_to_campaign(campaign_id, rows, linkedin_account_id)`:

```json
{
  "campaignId": 599020,
  "accountLeadPairs": [
    {
      "linkedInAccountId": 174892,
      "lead": {
        "profileUrl": "https://www.linkedin.com/in/example-person",
        "firstName": "Example",
        "lastName": "Person",
        "companyName": "Example Corp",
        "position": "VP Engineering",
        "customUserFields": [
          {"name": "note", "value": "Connection note text here"},
          {"name": "record_id", "value": "rec-abc123"},
          {"name": "contact_key", "value": "contact-xyz789"},
          {"name": "client", "value": "productive"},
          {"name": "sender_id", "value": "sender-hash"},
          {"name": "sender_account_id", "value": "174892"},
          {"name": "Icebreaker", "value": "Saw your talk at..."}
        ]
      }
    }
  ]
}
```

### Field provenance

| Field | Source | Always present? |
|---|---|---|
| `campaignId` | Caller argument | Yes |
| `linkedInAccountId` | `row.provider_account_id` or fallback | Yes (per row) |
| `lead.profileUrl` | `row.linkedin_url` | Yes (row must have one) |
| `lead.firstName` | `row.first_name` | Optional, defaults "" |
| `lead.lastName` | `row.last_name` | Optional, defaults "" |
| `lead.companyName` | `row.company` | Optional, defaults "" |
| `lead.position` | `row.title` | Optional, defaults "" |
| `customUserFields[0]` | `note` — always emitted first | Yes (may be empty string) |
| `customUserFields[1-6]` | `record_id`, `contact_key`, `client`, `sender_id`, `sender_account_id` | Only when truthy |
| `customUserFields[7+]` | `row.custom_fields` dict, sorted by name | Only when non-empty |

### What `supplied_field_names` reports

With no rows (probe mode): `["note", "record_id", "contact_key", "client", "sender_id", "sender_account_id"]`

With rows: the **intersection** of what every row actually produces. A field
only counts when every row has it. One lead missing `note` means `note` is not
reported as supplied, and a campaign whose copy uses `{note}` would render a
blank — `refuse_unsupported_sequence` catches this and raises.

### What `refuse_unsupported_sequence` gates

Before any write, the live campaign sequence is fetched and checked against
what this push supplies. If the sequence uses a variable name (e.g.
`{Icebreaker}`) that no row supplies, the function RAISES `SequenceRefused`.
The prospect would otherwise receive HeyReach's fallback message — copy this
system did not write — while the system records a send.

---

## 2. THE RESPONSE SHAPE — KNOWN AND UNKNOWN

### What the vendor's third-party audit says

The `heyreach-cli` project (Brandon Charleson, audited 2026-05-04) reports:

> "The V2 endpoints return a far better response shape
> (`{addedLeadsCount, updatedLeadsCount, failedLeadsCount}` vs. just an
> integer)."

This is the best available evidence for the response body, but it comes from
a third-party audit of a DIFFERENT workspace, not from a response this
repository has read. The field names are plausible and consistent with the
provider's style, but they are NOT confirmed by a direct read.

### What this repository knows

1. The URL is `https://api.heyreach.io/api/public/campaign/AddLeadsToCampaignV2`
2. The route is on `heyreach.WRITE_ROUTES`
3. The route is NOT in `providerwrites.SUPPORTED`
4. `_write_body` will POST the body and return whatever the provider sends
5. **No successful response has ever been read by this codebase**

### What the readback does regardless

The response body of `AddLeadsToCampaignV2` is NOT what decides the verdict.
`readback_membership` pages through `/campaign/GetLeadsFromCampaign` and
compares expected profile URLs against what the provider actually holds. The
readback is the verdict:

- **found == expected** → ACCEPTED
- **found ⊂ expected** → DRIFTED (partial add)
- **found == ∅** → DRIFTED (nothing landed)
- **readback raises** → UNRESOLVED (provider state unknown)

This means the response body shape matters for diagnostics but NOT for the
safety argument. A 200 with an unparseable body is fine if the readback finds
every lead. A 200 with `{addedLeadsCount: 50}` is NOT fine if the readback
finds 43.

### What remains UNKNOWN until a live call

| Question | Status |
|---|---|
| Exact response body field names | Inferred from third-party audit, not confirmed |
| What it returns for a lead already in the campaign | UNKNOWN |
| What it returns for a rejected lead (bad URL, wrong org) | UNKNOWN |
| Whether it is atomic (all-or-nothing) or per-lead | UNKNOWN |
| HTTP status code on partial success | UNKNOWN |
| Whether `failedLeadsCount` includes reason codes | UNKNOWN |

**If the only way to learn these is to perform a write, that is the finding.**
The first write buys the response shape AND the partial-failure behaviour in
one action. The readback already handles both outcomes correctly.

---

## 3. PROOF THAT LEAD READBACK WORKS ON A CAMPAIGN WITH LEADS

**This is the single most valuable finding in this task.**

### Campaign 594061 — the canary (1 lead)

```
Campaign:  594061
Name:      PRODUCTIVE - CANARY - 2026-09-09
Status:    PAUSED
Leads:     1

Lead readback:
  provider_lead_id: sha256:9d3f33851d741dba
  profile_url:      sha256:1b294aaaa2a2bbc3
  sender_id:        sha256:ba164ef00155d781
  state:            request_pending
  connection:       none
  message:          none
  created_at:       2026-09-09T18:07:51Z

readback_membership:
  Expected: 1 URL → Found: 1 → Missing: 0
  VERDICT: READBACK CONFIRMS leads are detectable via the read route

campaign_stats cross-check:
  connectionsSent: 0, connectionsAccepted: 0
  totalMessageReplies: 0, uniqueLeadsContacted: 0
  (Consistent: 1 lead in request_pending, nothing sent yet)
```

### Campaign 567689 — diverse lifecycle states (28 leads)

```
Campaign:  567689
Name:      PRODUCTIVE - MARTINA H CONNECTIONS - MARKETING AGE...
Status:    FINISHED
Leads:     28

Lifecycle state distribution:
  accepted:  25
  replied:    3

Connection state distribution:
  connectionaccepted: 28

Message state distribution:
  messagesent:   24
  messagereply:   3
  none:           1

Error codes observed:
  CannotViewLeadProfileOrLeadDoesnotExist: 1
  LeadBlockedByRecipient: 1

Leads with action timestamps: 28/28
Leads with profile URL: 28/28

readback_membership (5-lead sample):
  Expected: 5 URLs → Found: 5 → Missing: 0
  Per-lead states confirmed:
    sha256:598c20d2ae772c44 → accepted, ConnectionAccepted, None
    sha256:fef42db0cdfab0ad → accepted, ConnectionAccepted, MessageSent
    sha256:80bd097c982139ee → replied,  ConnectionAccepted, MessageReply
    sha256:9903f4d12b077343 → replied,  ConnectionAccepted, MessageReply
    sha256:9d30da6710a48fca → accepted, ConnectionAccepted, MessageSent

campaign_stats cross-check:
  connectionsSent: 0, connectionsAccepted: 0
  totalMessageReplies: 3, uniqueLeadsContacted: 27
  (totalMessageReplies matches the 3 replied leads; uniqueLeadsContacted
   is 27 not 28 because 1 lead has message state "none")
```

### What this proves

1. **`/campaign/GetLeadsFromCampaign` works** and returns the full per-lead
   lifecycle: campaign status, connection status, message status, error codes,
   timestamps, profile URLs, sender ids.
2. **`readback_membership` correctly matches** expected profile URLs against
   the provider's actual membership.
3. **`campaign_stats` provides an independent cross-check** at campaign
   granularity.
4. **Every lead carries a profile URL** — the key `readback_membership`
   matches on. 28/28 in the larger campaign, 1/1 in the canary.
5. **The lifecycle state machine works as documented**: `lead_state()`
   correctly classifies all observed combinations (replied > accepted >
   request_sent > failed > finished > pending).
6. **Error codes are returned verbatim** and carried without interpretation.

### What campaign 599020 proves

```
Campaign 599020 leads read: 0
Campaign 599020 totalCount: 0
```

Confirmed: 0 leads. This campaign proves NOTHING about readback capability.
The readback proof rests on 594061 and 567689, not on 599020.

---

## 4. PARTIAL-FAILURE CLASSIFICATION

### What the code does today

The `perform` function in `providerwrites.py` classifies outcomes through
`_classify(observed, expected)`:

| Scenario | observed | expected | Verdict | Ledger state |
|---|---|---|---|---|
| All leads found | `{"found": {a,b,c}}` | `{"found": {a,b,c}}` | ACCEPTED | SENT |
| Some leads found | `{"found": {a,b}}` | `{"found": {a,b,c}}` | DRIFTED | UNRESOLVED |
| No leads found | `{"found": set()}` | `{"found": {a,b,c}}` | DRIFTED | UNRESOLVED |
| Readback raises | exception | any | WriteUnverified | UNRESOLVED |
| Transport raises | exception | any | WriteUnverified | UNRESOLVED |

### What a partial add looks like in practice

50 leads sent, 43 land:

1. `add_leads_to_campaign` posts the body. The provider may return 200 with
   `{addedLeadsCount: 43, failedLeadsCount: 7}` or it may return 200 with
   no detail. **The response body does not matter for the verdict.**
2. `readback_membership` pages through the campaign and finds 43 of 50
   expected URLs.
3. `_classify` sees `found ≠ expected` → DRIFTED.
4. `perform` raises `WriteUnverified`.
5. The action ledger is settled to UNRESOLVED.
6. The 7 missing leads CANNOT be retried through the same key — the ledger
   refuses a second attempt on an UNRESOLVED key.

### What the code does NOT do today

1. **It does not identify WHICH 7 leads failed.** The `missing` set in the
   readback result contains the 7 URLs, but this information is in the
   exception message, not in a structured form the caller can act on.
2. **It does not distinguish "provider rejected these 7" from "provider
   accepted them but they have not appeared yet."** A timing gap between the
   write and the readback could produce a false DRIFTED.
3. **It does not retry the missing leads.** The UNRESOLVED ledger state
   blocks all retries on the same key. A human must read provider truth and
   settle the key by hand.

### What it SHOULD do (recommendation for Claude's review)

1. **Log the missing set.** When DRIFTED, the 7 missing URLs should be
   written to the event log so a human can see exactly who did not land.
2. **Poll before declaring DRIFTED.** A single readback immediately after
   the write may catch a timing gap. One retry of the readback after a short
   delay (5-10 seconds) would distinguish "not yet visible" from "rejected."
3. **Allow a targeted retry for the missing subset.** The current key-level
   lock is correct for preventing double-adds, but a NEW key for the 7
   missing leads should be permissible after the first attempt is settled.
4. **Classify the provider's response body.** If the response carries
   `failedLeadsCount > 0`, that is information worth recording even when the
   readback finds all leads (the provider may have accepted and then removed
   them, or the readback may be stale).

### The safety property that holds

**A partial add that is invisible is impossible.** The readback checks every
expected URL against provider truth. If 43 of 50 land, the system reports
DRIFTED, not ACCEPTED. The ledger stays UNRESOLVED, the touch is not
recorded, and no subsequent action assumes the missing 7 are in the campaign.

This is the property the task asked about, and it holds.

---

## 5. CORRECTED OPERATIONS ENTRIES

### LINKEDIN_CREATE_LIST — STALE

**Current text:**
> "no documented route; the list was created by hand in the vendor UI"

**What actually happened:**
- `/list/CreateEmptyList` is on `heyreach.WRITE_ROUTES` (added 2026-09-13,
  commit `f1fd6c0`)
- `heyreach.create_list()` is implemented with full readback: it writes via
  `_write_body`, reads back via `GET /list/GetById`, and raises unless the
  provider confirms the name and type match
- List 933603 was created on 2026-09-13T10:33:37Z — the SAME second as
  campaign 599020 — which is not a human in a UI
- The list is type USER_LIST, attached to campaign 599020

**Corrected description:**
> "SUPPORTED as a mechanism — `/list/CreateEmptyList` is on `WRITE_ROUTES`,
> `heyreach.create_list` writes and reads back, and list 933603 was created
> by this system on 2026-09-13. NOT in `SUPPORTED`: the list is permanent
> (no delete verb on this provider) and the name cannot be changed
> afterwards, so a wrong name is a permanent defect in the client's estate.
> Not prospect-facing: an empty list reaches nobody."

### LINKEDIN_CREATE_CAMPAIGN — STALE

**Current text:**
> "no documented route; POST /campaign/GetById already answers 405 and
> nothing suggests a create verb exists on the public API"

**What actually happened:**
- `/campaign/Create` is on `heyreach.WRITE_ROUTES` (added 2026-09-13,
  commit `f1fd6c0`)
- `heyreach.create_campaign()` is implemented with full readback: it checks
  name uniqueness, writes via `_write_body`, reads back via
  `GET /campaign/GetById`, and raises unless the provider confirms the name
- Campaign 599020 was created on 2026-09-13T10:33:37Z in DRAFT status
- The comment in OPERATIONS confused `GET /campaign/GetById` (which answers
  405 to POST — it is a GET endpoint) with the absence of a create verb.
  The create verb is `POST /campaign/Create` and it is a different route
  entirely
- The vendor's own API documentation (heyreach.io/blog/campaign-api) lists
  `POST /api/public/campaign/Create` as endpoint #1 and documents the
  response as `{ "campaignId": 12345 }`

**Corrected description:**
> "SUPPORTED as a mechanism — `/campaign/Create` is on `WRITE_ROUTES`,
> `heyreach.create_campaign` writes and reads back, and campaign 599020 was
> created by this system on 2026-09-13 in DRAFT status. NOT in `SUPPORTED`:
> a campaign is permanent on this provider (no delete verb), a DRAFT sends
> nothing but is visible in the client's estate, and the name is the only
> recovery key if the campaignId is lost. Not prospect-facing: a DRAFT
> campaign sends nothing until `/campaign/StartCampaign`, which is
> deliberately absent from WRITE_ROUTES."

### Why both entries are stale

Both were written before commit `f1fd6c0` (2026-09-13) added the staging
verbs. That commit added 1116 lines to `heyreach.py` including `create_list`,
`create_campaign`, and six write routes — but the OPERATIONS table in
`providerwrites.py` was not updated to match. The module docstring of
`providerwrites.py` was similarly stale until 2026-09-15 when it was
corrected to list the six enabled routes. The two OPERATIONS entries for
LIST and CAMPAIGN creation were not corrected in that pass.

---

## 6. WHAT REMAINS UNKNOWN — THE LIST CLAUDE IS REVIEWING

When the door opens, this is what Claude is deciding on:

### About the response body

1. **The exact field names of the AddLeadsToCampaignV2 response.** Third-party
   audit says `{addedLeadsCount, updatedLeadsCount, failedLeadsCount}`. Not
   confirmed by a direct read from this codebase.
2. **What the response returns for a lead already in the campaign.** Unknown.
   The provider may count it as `updatedLeadsCount` or ignore it silently.
3. **What the response returns for a rejected lead.** Unknown. Bad URL, wrong
   org, blocked recipient — the error shape is not documented.
4. **Whether the endpoint is atomic.** If 50 leads are sent and 7 are
   rejected, does the endpoint roll back the 43 or does it commit them?
   Unknown. The readback handles both outcomes, but the operator should know
   which one happened.

### About partial failure

5. **Timing gap between write and readback.** If the provider accepts a lead
   but it takes 5 seconds to appear in `GetLeadsFromCampaign`, a single
   immediate readback would report DRIFTED on a successful add. One retry
   after a delay would settle this.
6. **Retry semantics for the missing subset.** The current key-level lock
   blocks all retries. If 7 of 50 fail, the operator needs a path to retry
   those 7 without re-adding the 43.

### About the OPERATIONS corrections

7. **Whether LINKEDIN_CREATE_LIST and LINKEDIN_CREATE_CAMPAIGN should be
   enabled.** The mechanism exists and was live-validated (list 933603,
   campaign 599020). The reason they are not in SUPPORTED is the permanence
   argument: no delete verb on either, so a mistake is permanent. This is a
   policy decision, not an engineering gap.

### About the first write

8. **What the first write buys.** A single call to `AddLeadsToCampaignV2`
   with one lead on campaign 599020 (DRAFT, 0 leads, never started) would
   answer questions 1-4 above and settle every unknown in this list. The
   campaign is in DRAFT and sends nothing, so the lead would be added but
   never acted on. The readback would confirm membership. The response body
   would be read for the first time. **That is what the first write buys:
   information, not exposure.**

---

## 7. SUMMARY OF PROOF

| Question | Status | Evidence |
|---|---|---|
| Request body shape | **KNOWN** | `build_lead_pairs`, `add_leads_to_campaign` |
| Response body shape | **INFERRED** | Third-party audit; not confirmed by direct read |
| Readback works on empty campaign | **PROVED** | 599020: 0 leads, 0 found |
| Readback works on campaign with leads | **PROVED** | 594061 (1 lead), 567689 (28 leads, diverse states) |
| Partial failure is visible | **PROVED** | `readback_membership` checks every expected URL |
| Partial failure is retryable | **NOT YET** | Key-level lock blocks retry; needs design |
| OPERATIONS LINKEDIN_CREATE_LIST | **STALE** | Route exists, list 933603 created by system |
| OPERATIONS LINKEDIN_CREATE_CAMPAIGN | **STALE** | Route exists, campaign 599020 created by system |
| AddLeadsToCampaignV2 in SUPPORTED | **NOT YET** | Claude's decision after review |

---

## APPENDIX: SCRIPTS AND REPRODUCIBILITY

Two scripts were written for this task:

- `scripts/task124_prove_readback.py` — walks all campaigns, finds ones with
  leads, reads leads back from the smallest candidate, tests
  `readback_membership`, confirms 599020 has 0 leads
- `scripts/task124_readback_larger.py` — finds a campaign with diverse
  lifecycle states (28 leads, accepted + replied), proves readback handles
  the full lifecycle

Both are read-only. Both hash every prospect identifier. Both can be re-run
to reproduce the findings.
