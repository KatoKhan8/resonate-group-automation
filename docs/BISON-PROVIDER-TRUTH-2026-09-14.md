# EmailBison Provider Truth — 2026-09-14

Read-only probe of the live instance at `https://send.resonategroup.co/api`.
Every claim below carries the row count behind it. No performance findings —
those belong to TASK-070 and are built on this map.

## Method

Each section names the route, the field, the type, the shape, and how many
rows were checked. All probes are reproducible from `src/providers/bison.py`
with the credential in `config/.env`. No PII is committed — emails, names and
company domains are redacted.

---

## 1. CAMPAIGN

**Route:** `GET /api/campaigns?page=N` (listing), `GET /api/campaigns/{id}` (single)
**Rows checked:** 22 campaigns (the entire estate, 2 pages)

### Fields (29 on the listing row)

| Field | Type | Example | Populated |
|-------|------|---------|-----------|
| `id` | int | `481` | 22/22 |
| `uuid` | str | `"a2bd17a8-..."` | 22/22 |
| `name` | str | `"RESONATE - PRODUCTIVE - EMAIL - ..."` | 22/22 |
| `status` | str | `"paused"`, `"active"`, `"completed"`, `"draft"`, `"archived"` | 22/22 |
| `type` | str | `"outbound"` | 22/22 |
| `created_at` | str (ISO 8601) | `"2026-09-13T20:11:34.000000Z"` | 22/22 |
| `updated_at` | str (ISO 8601) | `"2026-09-13T22:17:13.000000Z"` | 22/22 |
| `emails_sent` | int | `92799` | 22/22 |
| `opened` | int | `0` | 22/22 (always 0 — see below) |
| `unique_opens` | int | `0` | 22/22 (always 0) |
| `replied` | int | `0` | 22/22 |
| `unique_replies` | int | `0` | 22/22 |
| `bounced` | int | `0` | 22/22 |
| `unsubscribed` | int | `0` | 22/22 |
| `interested` | int | `0` | 22/22 |
| `total_leads` | int | `23` | 22/22 |
| `total_leads_contacted` | int | `0` | 22/22 |
| `completion_percentage` | int | `0` | 22/22 |
| **`open_tracking`** | **bool** | **`False`** | **22/22 — ALL FALSE** |
| `can_unsubscribe` | bool | `False` | 22/22 |
| `include_auto_replies_in_stats` | bool | `True` | 22/22 |
| `plain_text` | bool | `False` | 22/22 |
| `sequence_id` | int | `428` | 22/22 |
| `sequence_prioritization` | str | `"followups"` | 22/22 |
| `max_emails_per_day` | int | `20` | 22/22 |
| `max_new_leads_per_day` | int | `20` | 22/22 |
| `daily_max_sends_per_receiving_domain` | int | `25` | 22/22 |
| `tags` | list | `[]` | 22/22 (all empty) |
| `unsubscribe_text` | NoneType | `None` | 0/22 |

### CRITICAL: `open_tracking` IS FALSE ON EVERY CAMPAIGN

All 22 campaigns have `open_tracking: false`. The `opened` and `unique_opens`
fields are 0 on every campaign, including campaign 352 which sent 92,799
emails. **Zero opens across the entire estate is an absent measurement, not
an absent outcome.** Any open-rate analysis that ignores this flag is
fiction. This was suspected for campaign 451; it is now confirmed estate-wide.

### Status values observed

`draft`, `paused`, `active`, `completed`, `archived`, `failed`, `queued`,
`pending deletion`

### Pagination

The listing serves 15 rows per page whatever `per_page` is set to. `meta.total`
carries the true count. The estate has 22 campaigns across 2 pages.

---

## 2. SEQUENCE STEPS

**Route:** `GET /api/campaigns/{id}/sequence-steps`
**Rows checked:** 44 steps (campaign 352), 1 step (campaign 451)

### Fields (12 on the raw row)

| Field | Type | Example | Populated |
|-------|------|---------|-----------|
| `id` | int | `4035` | 44/44 |
| `order` | int | `1` | **5/44** (see below) |
| `active` | bool | `True` | 44/44 |
| `email_subject` | str (HTML template) | `"{me again, {FIRST_NAME}\|..."` | 44/44 |
| `email_body` | str (HTML template) | `"<p>Hey {FIRST_NAME}..."` | 44/44 |
| `wait_in_days` | int | `3` | 44/44 |
| `variant` | bool | `False` | 44/44 |
| `variant_from_step` | NoneType or int | `None` | 44/44 |
| `thread_reply` | bool | `False` | 44/44 |
| `attachments` | NoneType | `None` | 0/44 |
| `created_at` | str (ISO 8601) | `"2026-05-13T11:09:12.000000Z"` | 44/44 |
| `updated_at` | str (ISO 8601) | `"2026-06-12T16:13:00.000000Z"` | 44/44 |

### `order` IS ONLY ON PARENT STEPS, NOT VARIANTS

Campaign 352 has 44 steps but only 5 distinct `order` values (1, 2, 3, 4, 5).
The other 39 steps are variants — they have `variant: true`,
`variant_from_step: <parent_id>`, and `order: null`. A step's position in the
sequence is determined by `order` for parents; variants share their parent's
position.

**Note:** `bison.sequence_steps()` in the existing code trims this to 6 fields
(`id`, `order`, `email_subject`, `email_body`, `wait_in_days`, `active`) and
drops `variant`, `variant_from_step`, `thread_reply`, `created_at`,
`updated_at`, `attachments`. The trimmed form is sufficient for sequence
reproduction but loses variant attribution.

### Not paginated

All 44 steps arrive in one response with no `meta`. `?page=2` returns the same
44 rows.

### A 200 is not an existence proof

A campaign with no sequence answers 200 carrying `{"success": false, "message":
"Sequence steps do not exist for <name>"}`. Absence is read from the body.

---

## 3. LEAD

**Route:** `GET /api/campaigns/{id}/leads?page=N` (listing), `GET /api/leads/{id}` (single)
**Rows checked:** 18 leads across campaigns 352, 451, 335; 1 individual lead (146592)

### Fields (14 on the listing row)

| Field | Type | Example | Populated |
|-------|------|---------|-----------|
| `id` | int | `203752` | 18/18 |
| `uuid` | str | `"a2bf057e-..."` | 18/18 |
| `email` | str | `[REDACTED]` | 18/18 |
| `first_name` | str | `[REDACTED]` | 18/18 |
| `last_name` | str | `[REDACTED]` | 18/18 |
| `company` | str | `"Koval"` | 18/18 |
| `title` | str | `"CEO & Founder"` | 17/18 |
| `status` | str | `"unverified"` | 18/18 |
| `created_at` | str (ISO 8601) | `"2026-09-14T19:12:26.000000Z"` | 18/18 |
| `updated_at` | str (ISO 8601) | same | 18/18 |
| `notes` | NoneType | `None` | 0/18 |
| `custom_variables` | list[{name, value}] | see below | 18/18 (but contents vary) |
| `lead_campaign_data` | list[dict] | see below | 18/18 |
| `overall_stats` | dict | see below | 18/18 |

### `lead_campaign_data` — per-campaign stats (6 fields per entry)

| Field | Type | Example |
|-------|------|---------|
| `campaign_id` | int | `327` |
| `emails_sent` | int | `7` |
| `opens` | int | `0` |
| `replies` | int | `1` |
| `interested` | bool | `False` |
| `status` | str | `"replied"`, `"stopped"`, `"sequence_finished"`, `"in_sequence"`, `"sending_paused"`, `"never_contacted"` |

A lead in three campaigns has three entries. The status is per-campaign, not
global.

### `overall_stats` — cross-campaign totals (5 fields)

| Field | Type |
|-------|------|
| `emails_sent` | int |
| `opens` | int |
| `replies` | int |
| `unique_opens` | int |
| `unique_replies` | int |

### `custom_variables` — list of `{name, value}`

Older campaigns (335, 274, 327, 328, 352): carry provider-defined variables
like `location`, `industry`, `headline`. No `record_id` or `contact_key`.
Checked 37/46 reply leads — none had `record_id` or `contact_key`.

Newer campaigns (451): carry our variables — `record_id`, `contact_key`,
`client`, `subject`, `body`. Checked 1/1 lead — all five present.

### Pagination

15 rows per page whatever `per_page` is set to. `meta.total` carries the true
count. Campaign 352 has 21,159 leads across 1,411 pages.

---

## 4. SEND HISTORY (`scheduled_emails`)

**Route:** `GET /api/campaigns/{id}/scheduled-emails?page=N`
**Rows checked:** 1 (campaign 451), 15 (campaign 335 page 1), 15 (campaign 274 page 1)

### THIS IS THE SINGLE MOST IMPORTANT ROUTE IN THE API

It carries a per-lead per-step record of what was actually sent, with
timestamps, rendered copy, and the `sequence_step_id` that links to the
sequence definition. It is available for historical campaigns, including
archived ones.

### Fields (20 on the row)

| Field | Type | Example | Populated |
|-------|------|---------|-----------|
| `id` | int | `22303717` | yes |
| `campaign_id` | int | `451` | yes |
| **`sequence_step_id`** | **int** | **`4707`** | **yes — THE STEP LINK** |
| `status` | str | `"sent"`, `"stopped"`, `"bounced"` | yes |
| `scheduled_date` | str (ISO 8601) | `"2026-09-14T16:24:00.000000Z"` | yes |
| `scheduled_date_local` | str (ISO 8601) | `"2026-09-14T16:24:00.000000Z"` | yes |
| `sent_at` | str (ISO 8601) | `"2026-09-14T16:24:20.000000Z"` | yes (when sent; null when not yet) |
| `raw_message_id` | str | `"<a2bd2a6e-...@goproductive.online>"` | yes |
| `email_subject` | str (RENDERED) | `"Profitability visible on Monday..."` | yes |
| `email_body` | str (RENDERED HTML) | `"<p>Your website states..."` | yes |
| `opens` | int | `0` | yes |
| `unique_opens` | int | `0` | yes |
| `clicks` | int | `0` | yes |
| `replies` | int | `0` | yes |
| `unique_replies` | int | `0` | yes |
| `interested` | bool | `False` | yes |
| `thread_reply` | bool | `False` | yes |
| `lead` | dict (nested) | full lead object | yes |
| `campaign` | dict (nested) | full campaign object | yes |
| `sender_email` | dict (nested) | sender inbox object | yes |

### Availability for historical campaigns

| Campaign | Status | emails_sent | scheduled_emails total | Available? |
|----------|--------|-------------|----------------------|------------|
| 451 | completed | 1 | 1 | YES |
| 335 | completed | 9,759 | 10,173 | YES |
| 274 | archived | 28,331 | 30,411 | YES |

The `scheduled_emails` total exceeds `emails_sent` because it includes bounced
and stopped rows. Historical data is available for archived campaigns.

### `email_body` and `email_subject` carry RENDERED copy

Merge fields are resolved. The stored template
`{me again, {FIRST_NAME}|following up from LinkedIn}` reads back as
"me again, Matija". This is the only place the rendered copy is visible.

### Pagination

15 rows per page. Campaign 335: 10,173 rows across 679 pages. Campaign 274:
30,411 rows. Large campaigns require many pages.

---

## 5. REPLIES

**Route:** `GET /api/replies?pagination_type=cursor&per_page=N`
**Rows checked:** 750 (50 pages, cursor-paginated, spanning 2026-07-19 to 2026-09-14)

### Fields (30 on the row)

| Field | Type | Example | Populated (of 750) |
|-------|------|---------|-----------|
| `id` | int | `1609175` | 750/750 |
| `uuid` | str | `"a2beed02-..."` | 750/750 |
| `type` | str | `"Tracked Reply"`, `"Outgoing Email"`, `"Bounced"` | 750/750 |
| `folder` | str | `"Inbox"`, `"Sent"`, `"Bounced"` | 750/750 |
| `campaign_id` | int | `327` | **748/750** (2 missing are Outgoing) |
| `lead_id` | int | `146592` | **748/750** (2 missing are Outgoing) |
| **`scheduled_email_id`** | **int** | **`22303789`** | **748/750** (2 missing are Outgoing) |
| `date_received` | str (ISO 8601) | `"2026-09-14T16:12:32.000000Z"` | 750/750 |
| `created_at` | str (ISO 8601) | `"2026-09-14T18:03:58.000000Z"` | 750/750 |
| `from_email_address` | str | `[REDACTED]` | 750/750 |
| `from_name` | str | `"Bernarda Vrbat"` | 750/750 |
| `subject` | str | `"Re: quick question before I stop..."` | 750/750 |
| `text_body` | str | `[1555 chars]` | 750/750 |
| `html_body` | str | `[4026 chars]` | 750/750 |
| `raw_message_id` | str | `"<1e795c8b-...>"` | 750/750 |
| `parent_id` | int or None | `None` | 0/750 (always null in sample) |
| `sender_email_id` | int | `3411` | 750/750 |
| `primary_to_email_address` | str | `[REDACTED]` | 750/750 |
| `to` | list[{address, name}] | `[{...}]` | 750/750 |
| `cc` | NoneType | `None` | 0/750 |
| `bcc` | NoneType | `None` | 0/750 |
| `automated_reply` | bool | `False` | 750/750 |
| `tracked_reply` | bool | `True` | 750/750 |
| `interested` | bool | `False` | 750/750 |
| `read` | bool | `True` | 750/750 |
| `lead` | dict (nested) | full lead object | 748/750 (null on 2 Outgoing) |
| `attachments` | list | `[]` | 750/750 |
| `headers` | NoneType | `None` | 0/750 |
| `raw_body` | NoneType | `None` | 0/750 |
| `updated_at` | str (ISO 8601) | same as created_at | 750/750 |

### Type distribution (750 rows)

| Type | Count | Folder | Classification |
|------|-------|--------|----------------|
| `Tracked Reply` | 46+ | `Inbox` | `reply` |
| `Untracked Reply` | subset | `Inbox` | `reply` |
| `Outgoing Email` | 3+ | `Sent` | `outgoing` — **NOT A REPLY** |
| `Bounced` | 26+ | `Bounced` | `bounce` |

### THE TWO ROWS MISSING JOIN FIELDS ARE OUTGOING

The 2 rows with null `campaign_id`, `lead_id`, and `scheduled_email_id` are
both `type: "Outgoing Email"` in `folder: "Sent"`. They are our own sent mail
and are correctly filtered out by `classify_reply_row`. **100% of actual
inbound replies and bounces carry the full join chain.**

### `custom_variables` ON REPLY LEADS

Of 46 inbound replies sampled: 37/46 leads have `custom_variables` populated,
but **0/46 have `record_id` or `contact_key`**. These are leads from older
campaigns that predate our custom variable scheme. The leads carry
provider-defined variables (`location`, `industry`, `headline`) instead.

### `parent_id` IS ALWAYS NULL

Threading is not tracked through this field in the sample. A reply to a reply
does not carry the parent's id.

### Pagination

Cursor-based. `meta.next_cursor` is an opaque base64 string. `per_page` is
capped at 100. 750 rows fetched across 8 pages in ~65 seconds.

---

## 6. THE JOIN CHAIN

### The question

    campaign -> lead -> exact email step -> exact copy -> send timestamp
             -> reply -> outcome

### The answer: THE FULL CHAIN IS POSSIBLE

Verified end-to-end against a live reply:

```
Reply id=1609175
  campaign_id=327           -> CAMPAIGN ✓
  lead_id=146592            -> LEAD ✓
  scheduled_email_id=22303789 -> SCHEDULED EMAIL ✓
    sequence_step_id=3738     -> STEP ✓ (order=7, active=True, wait=3d)
    sent_at=2026-09-14T16:09:20  -> TIMESTAMP ✓
    email_subject=[41 chars]     -> RENDERED COPY ✓
    email_body=[739 chars]       -> RENDERED COPY ✓
    lead.id=146592               -> LEAD MATCH ✓
```

### How each link is made

| Link | Via | Field | Verified |
|------|-----|-------|----------|
| campaign → lead | `lead_campaign_data[].campaign_id` on the lead | explicit | 18/18 leads |
| lead → scheduled email | `lead.id` matches `scheduled_email.lead.id` | nested object | 1/1 checked |
| scheduled email → step | `scheduled_email.sequence_step_id` matches `step.id` | explicit | 1/1 checked |
| scheduled email → copy | `scheduled_email.email_subject`, `email_body` (rendered) | direct | 1/1 checked |
| scheduled email → timestamp | `scheduled_email.sent_at` | direct | 1/1 checked |
| reply → scheduled email | `reply.scheduled_email_id` matches `scheduled_email.id` | explicit | 748/750 (2 are outgoing) |
| reply → campaign | `reply.campaign_id` | explicit | 748/750 |
| reply → lead | `reply.lead_id` or `reply.lead.id` | explicit + nested | 748/750 |

### What CAN be determined even without step attribution

Even if `scheduled_email_id` were absent on a reply (it is not, but for
robustness): `campaign_id` and `lead_id` together are enough for
cadence-shape learning — you know which campaign and which person replied,
even if you cannot say which exact step triggered the reply.

### What CANNOT be determined

- **Which variant was sent.** `scheduled_email.sequence_step_id` identifies
  the parent step, but the variant selection within that step is not recorded
  on the scheduled email row. If a step has 8 variants, the scheduled email
  carries the rendered copy but not which variant produced it.
- **Opens.** `open_tracking` is false on every campaign. The `opens` and
  `unique_opens` fields exist but are always 0.
- **Threading.** `parent_id` is always null. A reply chain cannot be
  reconstructed from this field.

---

## 7. PAGINATION TRAPS

These are recorded in `bison.py` already but restated here because they
affect any analysis built on this data.

1. **`per_page` is ignored on most routes.** The listing, membership,
   scheduled-emails, and campaign-senders routes all serve 15 rows per page
   whatever is asked for. Only the reply feed honours `per_page` (cursor
   pagination, max 100).

2. **`workspace_id` is accepted and discarded.** Every list route answers
   identically for any workspace id, including ones that do not exist. The
   credential is the scope boundary.

3. **The reply feed carries our own sent mail.** `type: "Outgoing Email"` in
   `folder: "Sent"` must be filtered out before any reply analysis. The
   allowlist in `classify_reply_row` handles this.

---

## 8. SUMMARY TABLE

| Entity | Route | Fields | Row count checked | Key finding |
|--------|-------|--------|-------------------|-------------|
| Campaign | `/campaigns` | 29 | 22 | `open_tracking` false on ALL |
| Sequence step | `/campaigns/{id}/sequence-steps` | 12 (raw) | 44 | `order` only on parents; variants have `order=null` |
| Lead | `/campaigns/{id}/leads`, `/leads/{id}` | 14 | 18 | `lead_campaign_data` is per-campaign; `overall_stats` is cross-campaign |
| Scheduled email | `/campaigns/{id}/scheduled-emails` | 20 | 31 | Available for historical+archived; carries `sequence_step_id` and rendered copy |
| Reply | `/replies` (cursor) | 30 | 750 | `scheduled_email_id` present on 100% of inbound replies; 2 outgoing rows lack it |

---

## 9. WHAT THIS MEANS FOR TASK-070

The data infrastructure for cadence-shape learning exists:

- **Step-level attribution is possible** via `scheduled_email.sequence_step_id`
  joined to `sequence_steps.id`.
- **Per-lead per-step send timestamps** are on `scheduled_email.sent_at`.
- **Rendered copy** is on `scheduled_email.email_subject` and `email_body`.
- **Reply-to-step attribution** works via `reply.scheduled_email_id` →
  `scheduled_email.id` → `scheduled_email.sequence_step_id`.
- **Campaign-level stats** (`replied`, `bounced`, etc.) exist but are
  untrustworthy for opens because `open_tracking` is universally false.

The gaps:

- **Variant-level attribution** is not available — the scheduled email carries
  the rendered copy but not which variant produced it.
- **Open tracking** is absent estate-wide. Any analysis involving opens must
  say so.
- **Large campaign reads are expensive** — 15 rows per page means 1,411 pages
  for campaign 352's membership and 679 pages for its scheduled emails.
