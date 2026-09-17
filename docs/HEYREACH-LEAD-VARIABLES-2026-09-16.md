# HeyReach lead variables: can list 944355 be personalised without activating?

**Date:** 2026-09-16
**Scope:** READ-ONLY. No provider write of any kind was made. No campaign, list,
sequence or lead was created, modified, started, resumed or activated. No script
was run with `--live`. Nothing was committed.
**Subject:** campaign 605732 (DRAFT), bound list 944355 (3 leads), seat 174892.

---

## HEADLINE

**The blocker dissolves.** There IS a documented, already-permitted, non-activating
route to set per-lead custom variables on the three leads already in list 944355:
re-POST `/list/AddLeadsToListV2` with the same `profileUrl`/`firstName`/`lastName`
plus a `customUserFields` array. The vendor documents this route as accepting
personalisation variables AND as an update path for leads already in a list. The
readback field exists and was read live from this estate today.

The repo belief that `/list/AddLeadsToListV2` "takes only profileUrl/firstName/
lastName" is **an artifact of never having sent `customUserFields`**, not a proof
that it rejects them. `add_leads_to_list` in `src/providers/heyreach.py` does not
build that key at all, and `list_leads` discards the field the provider returns.

The sealed campaign route (`/campaign/AddLeadsToCampaignV2`) is **not needed and
would not work anyway** — a DRAFT campaign refuses leads outright.

---

## 1. FALLBACK BEHAVIOUR — CONFIRMED (confidence: HIGH)

**Answer: HeyReach sends `fallbackMessage`.** It does not send a blank, does not
skip the step, and does not error.

**Vendor documentation**, HeyReach Help Center, *"How to import and use custom
variables?"*, https://help.heyreach.io/en/articles/9879182-how-to-import-and-use-custom-variables
(article header read 2026-09-16 as "Updated today"):

> "The custom variable will be replaced with the value specified for each lead
> for the custom variable. **If the value is null, the fallback message will be
> used.**"

This is the vendor's own words, on the vendor's own domain, on the current
article. `src/heyreachfactory.py:393` is **CONFIRMED**.

**Consequence for 605732 as it stands today:** the three leads in list 944355
carry no custom fields (measured — see §2). Every MESSAGE node in the sequence
references `{connected_1}`..`{connected_4}` / `{connection_note}`. Activating
today would send the generic `fallbackMessage` to all three, not the approved
per-contact copy. **The premise of the question is correct.**

Two supporting facts from this repo, both still valid:

- `docs/HEYREACH-VARIABLES.md` — 3,295 single-brace variable occurrences across
  81 campaigns in this estate, zero double-brace. Syntax is `{VAR}`.
- The same doc: HeyReach does not error on an unknown variable either; it
  substitutes the fallback. Same failure mode, different cause.

---

## 2. SETTING VARIABLES ON LEADS ALREADY IN A LIST — YES (confidence: HIGH)

### 2a. Does `/list/AddLeadsToListV2` accept custom fields? YES.

**Vendor documentation**, same article, "Option 2: Mapping custom variables from
an API request":

> "If you wish to take the API route, you can use two specific endpoints. The
> first is **AddLeadstoCampaignV2**, while the second is **AddLeadstoListV2**."
>
> "The personalization variables can be added using the **`customUserFields`
> array in the API requests.**"
>
> "🚨 The name field in the customUserFields array of the leads you are importing
> must contain only alpha-numeric characters or underscores `_`. An error will be
> returned if the name field does not follow this format."

The vendor names the LIST route explicitly and in the same breath as the campaign
route. `customUserFields` is not campaign-only.

**Naming constraint is load-bearing:** `connected_1`..`connected_4` and
`connection_note` are alphanumeric-plus-underscore and pass. Any field name with
a hyphen, space or dot would be rejected with an error.

### 2b. Is there an upsert semantic? YES.

**Vendor documentation**, same article, same section:

> "The API requests will return the number of **imported, updated, or failed**
> leads."
>
> "🧑‍💻 **This method allows you to update leads' custom variables in a lead list**
> (e.g., lead X had company Y. You can update it to Z)."

That is an explicit vendor statement of update-in-place for custom variables on a
lead ALREADY in a list. It also explains the `updatedLeadsCount` field the repo
already observed in the response — `{addedLeadsCount, updatedLeadsCount,
failedLeadsCount}` (docs/HEYREACH-LIST-SCHEMA-2026-09-15.md). `updatedLeadsCount`
was always the upsert counter; the repo had the evidence and read it as noise.

### 2c. The readback channel exists — MEASURED LIVE TODAY

`/list/GetLeadsFromList` returns a first-class `customFields` key per lead row.
The repo's `list_leads()` wrapper (src/providers/heyreach.py ~line 2389) maps only
four keys and **throws `customFields` away**, which is why nobody in this repo has
ever seen it.

Raw row shape, read from list 944355 today (values elided, no PII):

```
['about', 'autoTags', 'companyName', 'companyUrl', 'connections',
 'customEmailAddress', 'customFields', 'emailAddress', 'enrichedEmailAddress',
 'firstName', 'followers', 'headline', 'id', 'imageUrl', 'lastName',
 'linkedin_id', 'location', 'position', 'profileUrl', 'tags']
```

For all three leads in list 944355: `"customFields": []`. **Empty. Confirms the
premise.**

**Proof the field is populated when variables exist** — a different list in this
same client estate, list `906686` (USER_LIST, 1000 leads, bound to campaign
565765), returns:

```json
"customFields": [{"name": "Icebreaker", "value": "<icebreaker_text_hash>"}]
```

So: custom variables live on the LEAD IN THE LIST, are named/valued exactly as
`{name, value}`, and are readable back on a free read route. This is the missing
link. The write is verifiable.

Note the asymmetry in field naming, which has bitten this repo before:
**request key is `customUserFields`; response key is `customFields`.**

### 2d. Why the 2026-09-15 probe "proved" otherwise — it did not

`docs/HEYREACH-LIST-SCHEMA-2026-09-15.md` lists twelve failing shapes. **None of
the twelve carried `customUserFields`.** The probe established which fields are
REQUIRED (profileUrl, firstName, lastName) and that unrecognised shapes silently
drop. It never tested `customUserFields` at all. The repo's summary line — "takes
only profileUrl/firstName/lastName" — over-reads its own evidence.

The `extras=True` caution in `add_leads_to_list` (companyName/position coinciding
with silent drops) is about DIFFERENT keys and does not transfer. But it is a real
warning about this route's silent-drop behaviour: **a `0/0/0` response means
nothing landed, and only the `/list/GetLeadsFromList` readback settles it.** Any
first attempt must be one lead, then read back `customFields`.

### 2e. Is there a dedicated lead-update endpoint this repo does not know? PARTLY — and it does not help.

- **`/lead/AddTags`, `/lead/ReplaceTags`, `/lead/GetTags`** — real, keyed by
  `leadProfileUrl` or `leadLinkedInId`. Tags are NOT personalisation variables and
  are not readable as `{VAR}` in a sequence. Not useful here.
- **`PATCH /campaign/UpdateLeadCustomFields/.../campaigns/{campaignId}/leads/custom-fields`**
  — appears in a third-party endpoint listing (swarmhit.com/blog/heyreach-api) as
  "Personalization variables per lead". **Confidence: LOW.** Not found in HeyReach's
  own help centre or blog. It is CAMPAIGN-scoped, and campaign 605732 in DRAFT has
  zero enrolled leads, so even if real it has nothing to address today. Recorded as
  a lead to chase, not a route to use.
- **`/lead/UpdateStatus`** — probed 404 by a third party (bcharleson/heyreach-mcp
  `API_ENDPOINT_STATUS.md`). Does not exist.
- No official vendor documentation describes any other lead-update or
  personalisation endpoint. The vendor's own answer to "how do I update a lead's
  custom variables" is `AddLeadsToListV2`.

**Confidence summary for Q2: HIGH that the list route accepts `customUserFields`
and upserts. It is vendor-documented in plain language and the readback field is
live-proven. It is UNPROVEN on this account by an actual write — that write has
not been made and is not mine to make.**

---

## 3. THE SEALED ROUTE AND DRAFT — DRAFT REFUSES LEADS ENTIRELY (confidence: HIGH)

**Answer: neither. Adding leads to a DRAFT campaign does not activate it and does
not leave it DRAFT-with-leads — the call FAILS. The provider refuses.**

**Vendor documentation**, HeyReach Help Center, *"How to add Leads to campaigns?"*,
https://help.heyreach.io/en/articles/11657798-how-to-add-leads-to-campaigns:

> "Only the campaigns with **ongoing, paused, or finished** status are eligible
> for adding new leads. **Draft**, canceled, and failed status campaigns **are
> not.**"

The docs **do** address DRAFT explicitly, and they exclude it. This is not an
inference.

**This repo has already measured it.** `docs/DRAFT-CANNOT-TAKE-LEADS-2026-09-15.md`,
against campaign 599020:

```
POST /campaign/AddLeadsToCampaignV2
HTTP 400
{"errorMessage": "You cannot add new leads to a draft campaign."}
```

Provider state immediately after: **DRAFT, 0 leads. Nothing was written.**

Vendor documentation and a live measurement agree. DRAFT stays DRAFT because the
request never takes effect.

**The activation hazard the seal was built for is real but is about OTHER
statuses.** Same vendor article:

> "**Finished campaigns** - as soon as new leads are added campaign **will get
> activated.**"

and for PAUSED, the vendor instructs the operator to "pause and resume the
campaign, once the leads are added" — i.e. leads sit in a PAUSED campaign until
somebody resumes. So the seal's reasoning holds for FINISHED (auto-activates) and
the PAUSED risk is a human-hand risk, not an auto-send. Neither applies to DRAFT,
because DRAFT cannot be reached at all.

**Net: the sealed route is not the door. It is a wall, in this status. Q2's list
route is the door, and it is already on `WRITE_ROUTES`.**

Corollary worth recording: the repo's `providerwrites.CONDITIONAL[LINKEDIN_ADD_LEAD]`
gate — admit a write only when `campaign_cannot_send(campaign)` is True, with
`_STATUSES_THAT_CANNOT_SEND = (DRAFT,)` — is **unsatisfiable by construction**.
The one status the gate permits is the one status the provider refuses. That is
already written up in `DRAFT-CANNOT-TAKE-LEADS-2026-09-15.md` and is confirmed
here by vendor documentation.

---

## 4. PROVING A FIRST REAL SEND (confidence: HIGH)

**Endpoint:** `POST /campaign/GetLeadsFromCampaign` (already in `READ_ROUTES_ALL`,
already wired as `heyreach.campaign_leads`).

**The field:** `leadMessageStatus` — and for the connection request,
`leadConnectionStatus`.

**Values** (allowlists established in this repo over 851 real leads across 11
campaigns, `src/providers/heyreach.py` `MESSAGE_STATES` / `CONNECTION_STATES`):

| Field | Value | Means |
|---|---|---|
| `leadMessageStatus` | `None` | no message sent |
| | **`MessageSent`** | **a message was actually sent to this person** |
| | `MessageReply` | they replied |
| `leadConnectionStatus` | `None` | no invitation sent |
| | **`ConnectionSent`** | **the invitation actually went out** |
| | `ConnectionAccepted` | they accepted |

**The corroborating field:** `lastActionTime` — an ISO timestamp. A lead with
`MessageSent` carries a real `lastActionTime`; a merely-enrolled lead carries
`lastActionTime: null`. **A status word plus a non-null timestamp is the proof.**

**Verified live today** against campaign 565765 (IN_PROGRESS, bound to list
906686). Example row, identifiers elided:

```
{'leadCampaignStatus': 'Failed',
 'leadConnectionStatus': 'ConnectionAccepted',
 'leadMessageStatus': 'MessageSent',
 'lastActionTime': '2026-09-03T18:43:24.969124Z',
 'errorCode': 'LeadBlockedByRecipient'}
```

**Three traps, all already known to this repo and all worth restating:**

1. **`progressStats` CANNOT answer this.** `totalUsersInProgress` counts a lead
   before anything is sent, and returns NEGATIVE numbers on some campaigns
   (-7, -5, -6 on campaigns 470039/470038/470010). It is a residual, not a count.
2. **`Failed` does not mean nothing reached the prospect.** 27 of 851 observed
   leads read `(Failed, ConnectionAccepted, MessageSent)`. The three fields are
   independent, not a state machine. Read `leadMessageStatus` directly; never
   infer from `leadCampaignStatus`.
3. **`/inbox/GetConversationsV2` is a weaker proof, not a stronger one.** A
   conversation exists only after somebody has been written to, so it is
   *sufficient* evidence of a send — but it carries no invitation state at all
   (`CONNECTION_STATUS_AVAILABLE = False`), so it cannot prove a connection
   request went out. Use it as corroboration, not as the primary.

**A repo belief CORRECTED here.** `docs/DOES-A-BOUND-LIST-SEND-2026-09-16.md`
states that `GetLeadsFromCampaign` "returns leads explicitly added via
AddLeadsToCampaignV2" and "does NOT return leads from the bound list". **That is
wrong.** Measured today: campaign 565765 is bound to list 906686 (1000 leads) and
`GetLeadsFromCampaign` returns `totalCount: 1000`. List-bound leads ARE returned.

The correct explanation for a DRAFT campaign reporting 0 leads is simpler:
**leads are enrolled into a campaign's roster when the campaign STARTS, not when
the list is bound.** A DRAFT has enrolled nobody yet. This matters because
`activate_campaign(expect_leads=N)` reads `campaign_leads` BEFORE starting — and
on a DRAFT that will read 0, not 3. Passing `expect_leads=3` on a DRAFT would
raise. **Read this before wiring the containment argument.**

---

## 5. `/campaign/StartCampaign` SEMANTICS (confidence: HIGH for the transition, MEDIUM for reversibility)

**What it does to a DRAFT:** moves it to running. `StartCampaign` is the verb for
a campaign that has never run; `Resume` is not, and answers HTTP 400 *"The
campaign you are trying to resume is not paused, finished or failed"* on a DRAFT
(repo-measured, `src/providers/heyreach.py` `resume_campaign` docstring).

**Resulting status string:** **`IN_PROGRESS`**. This is what
`_STARTED_STATUSES = ("IN_PROGRESS",)` encodes and what `activate_campaign` polls
for. Confidence HIGH — `IN_PROGRESS` is the status string observed live on
campaign 565765 today and across this estate.

**The 200 is not the answer.** The transition is not instant; the campaign can
still read `DRAFT` for some seconds after a 200. `activate_campaign` polls
(6 attempts / 2.0s) and raises rather than defaulting to success if the status is
still unknown when polling runs out. That is correct and should not be relaxed.

**Is it reversible via `/campaign/Pause`?** **Yes, as a status transition** —
`IN_PROGRESS -> PAUSED`, `heyreach.pause` is live-validated and in `SUPPORTED`.

**But it is NOT reversible as an outreach event, and that is the only sense that
matters here.** A started campaign begins acting on its leads; any message or
invitation already dispatched cannot be recalled by pausing. Pause stops the
NEXT step, not the last one. Treat `StartCampaign` on a campaign holding people as
irreversible with respect to the people.

---

## WHAT THIS MEANS FOR 605732 — the shortest correct path

Stated as findings, not as authorisation. Nothing below has been done.

1. **Do not touch `/campaign/AddLeadsToCampaignV2`.** DRAFT refuses it (§3), by
   vendor doc and by measurement.
2. **The variables go onto the LIST, not the campaign.** Re-POST
   `/list/AddLeadsToListV2` with `{listId: 944355, leads: [{profileUrl, firstName,
   lastName, customUserFields: [{name, value}, ...]}]}` — the same three required
   fields the 2026-09-15 probe proved, plus the array the vendor documents. This
   route is ALREADY on `WRITE_ROUTES`. It touches no campaign and cannot start
   anything.
3. **Names must be alphanumeric/underscore.** `connected_1`..`connected_4` and
   `connection_note` qualify.
4. **Prove it before trusting it.** One lead first. `0/0/0` means nothing landed.
   Then read `/list/GetLeadsFromList` and assert `customFields` is non-empty and
   exact. `list_leads()` currently DISCARDS `customFields` and must be widened, or
   the raw read used, or the verification is impossible.
5. **`refuse_unsupported_sequence` should then pass** against the live sequence,
   because every variable it names would be supplied for every lead.
6. **Only then is activation a question at all** — and it is a separate decision
   with its own evidence, reaching 3 real people with up to 4 messages each.

## WHAT WAS NOT ESTABLISHED

- **No write was made.** That `/list/AddLeadsToListV2` accepts `customUserFields`
  **on this account** is vendor-documented and structurally corroborated by a live
  readback of a populated `customFields` on list 906686 — but it has not been
  demonstrated by a write from this system. That is the one remaining unknown, and
  it costs one lead to remove.
- How list 906686's `Icebreaker` values were originally written (API, CSV or Clay)
  is UNKNOWN. All three vendor paths write the same field, so this does not change
  the conclusion, but it is not direct proof of the API path.
- `PATCH /campaign/UpdateLeadCustomFields/...` — existence UNVERIFIED (§2e).
- Whether `AddLeadsToListV2` MERGES custom fields into an existing lead or
  REPLACES the whole array is **UNKNOWN**. The vendor says "update"; it does not
  say which. For 944355 the leads hold `customFields: []`, so the distinction is
  moot today — but it matters for any later correction, and EmailBison's merge
  semantics (see `docs/LEAD-VARIABLES-2026-09-16.md`) must not be assumed here.

## SOURCES

**Vendor (official):**
- https://help.heyreach.io/en/articles/9879182-how-to-import-and-use-custom-variables — fallback behaviour, `customUserFields` on both routes, list-update semantics, naming constraint
- https://help.heyreach.io/en/articles/11657798-how-to-add-leads-to-campaigns — DRAFT excluded from lead-addition; FINISHED auto-activates
- https://www.heyreach.io/blog/campaign-api — campaign/list binding, status vocabulary

**Third-party (corroborating, lower weight):**
- https://github.com/bcharleson/heyreach-mcp/blob/main/API_ENDPOINT_STATUS.md — endpoint probe status; `/lead/UpdateStatus` 404
- https://github.com/bcharleson/heyreach-cli — CLI behaviour
- https://www.swarmhit.com/blog/heyreach-api — endpoint inventory; the unverified `UpdateLeadCustomFields` path

**Live reads, this estate, 2026-09-16 (no writes):**
- `/campaign/GetById` 605732 — DRAFT, bound list 944355
- `/list/GetLeadsFromList` 944355 — 3 leads, `customFields: []`
- `/list/GetAll` + `/list/GetLeadsFromList` 906686 — `customFields: [{name: "Icebreaker", value: ...}]`
- `/campaign/GetById` + `/campaign/GetLeadsFromCampaign` 565765 — IN_PROGRESS, list-bound, 1000 leads returned, `MessageSent` / `ConnectionAccepted` / `lastActionTime` observed

**Repo documents distinguished as BELIEF and assessed:**
- `docs/HEYREACH-LIST-SCHEMA-2026-09-15.md` — sound on required fields; **over-reads its evidence** on custom fields (never tested)
- `docs/DRAFT-CANNOT-TAKE-LEADS-2026-09-15.md` — **CONFIRMED by vendor documentation**
- `docs/DOES-A-BOUND-LIST-SEND-2026-09-16.md` — conclusion (a) correct; its claim that `GetLeadsFromCampaign` excludes list-bound leads is **REFUTED by live read**
- `docs/HEYREACH-VARIABLES.md` — single-brace syntax and fallback-on-unknown: consistent with vendor docs
