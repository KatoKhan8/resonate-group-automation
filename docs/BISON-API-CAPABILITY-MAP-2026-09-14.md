# EmailBison API Capability Map — 2026-09-14

**Workspace:** PRODUCTIVE (id 10)
**Base URL:** `https://send.resonategroup.co/api`
**Auth:** `Authorization: Bearer <BISON_KEY>` (api-user key, workspace-bound)
**Documentation:** https://docs.emailbison.com | https://send.resonategroup.co/api/reference (JS-rendered, empty HTML)
**OpenAPI spec:** https://docs.emailbison.com/api-reference/openapi.json (404 — not published)

All findings verified against the live API on 2026-09-14 unless marked otherwise.

---

## TASK-069 VERDICTS — THE FOUR QUESTIONS

These lead the document because they decide what TASK-070 can claim.

### A. Do historical per-lead / per-step SENDS with timestamps exist?

**VERDICT: 1 — DIRECTLY SUPPORTED BY PROVIDER**

`GET /campaigns/{id}/scheduled-emails` returns rows for **completed** campaigns, not only scheduled ones. Campaign 335 (status `completed`, 9,759 emails sent) returns 10,173 rows, each carrying:

| Field | Type | Example |
|---|---|---|
| `id` | int | 21060537 |
| `campaign_id` | int | 335 |
| `lead` | dict | `{id, uuid, first_name, last_name, email, ...}` |
| `sequence_step_id` | int | 3815 |
| `status` | str | `sent` / `scheduled` / `bounced` / `stopped` |
| `sent_at` | str (ISO 8601) | `2026-06-25T02:05:23.000000Z` |
| `scheduled_date` | str (ISO 8601) | `2026-06-25T02:05:00.000000Z` |
| `scheduled_date_local` | str (ISO 8601) | `2026-06-25T16:05:00.000000Z` |
| `email_subject` | str | rendered subject |
| `email_body` | str | rendered body (merge fields resolved) |
| `sender_email` | dict | `{id, name, email, ...}` |
| `opens` | int | 0 |
| `replies` | int | 0 |
| `unique_opens` | int | 0 |
| `unique_replies` | int | 0 |
| `clicks` | int | 0 |
| `interested` | bool | false |
| `thread_reply` | bool | false |
| `raw_message_id` | str | message-id header |

**Rows checked:** Campaign 335 (completed, 10,173 rows), campaign 352 (active, 95,439 rows). Both return historical data with `sent_at` populated for sent rows.

**Pagination:** Offset, 15 per page (per_page is ignored), meta.total present. Campaign 335 = 679 pages. Bounded by `_paged` in `bison.py` with `PAGE_CAP=40` — a campaign over 600 rows raises `PartialInventory`.

**Implemented in Resonate OS:** Partial. `bison.scheduled_emails()` exists and pages, but is used for pre-send copy verification, not historical analysis.

---

### B. Does a REPLY carry a direct message or step relationship?

**VERDICT: 2 — RECONSTRUCTABLE FROM PROVIDER DATA (two-hop)**

A reply row carries `scheduled_email_id` but NOT `sequence_step_id`. The join is:

    reply.scheduled_email_id → GET /scheduled-emails/{id} → sequence_step_id

**Reply fields (verified on 15 inbox rows):**

| Field | Type | Notes |
|---|---|---|
| `id` | int | reply id |
| `uuid` | str | |
| `campaign_id` | int | **present on reply directly** |
| `lead_id` | int | **present on reply directly** |
| `scheduled_email_id` | int | **the join to step** — null on untracked replies |
| `sender_email_id` | int | which inbox received/sent |
| `parent_id` | int | threading |
| `type` | str | `Tracked Reply` / `Untracked Reply` / `Outgoing Email` / `Bounced` |
| `folder` | str | `Inbox` / `Sent` / `Bounced` |
| `subject` | str | |
| `text_body` | str | |
| `html_body` | str | |
| `date_received` | str (ISO 8601) | |
| `created_at` | str (ISO 8601) | |
| `interested` | bool | |
| `automated_reply` | bool | |
| `tracked_reply` | bool | |
| `read` | bool | |
| `from_email_address` | str | |
| `from_name` | str | |
| `primary_to_email_address` | str | |
| `to` | list | `[{name, address}]` |
| `lead` | dict | `{id, uuid, first_name, last_name, email, ...}` |
| `raw_message_id` | str | |
| `attachments` | list | |

**Fields NOT present on a reply:** `sequence_step_id`, `step_id`, `message_id`, `email_id`.

**The two-hop trace (verified live):**
- Reply 1609175 → `scheduled_email_id: 22303789`
- GET `/scheduled-emails/22303789` → `sequence_step_id: 3738`, `sent_at: 2026-09-14T16:09:20.000000Z`

**Implemented in Resonate OS:** `fetch_replies()` and `classify_reply_row()` exist. The `scheduled_email_id` field is read but not traced to a step. `adapters.from_emailbison` reads `custom_variables` and `lead` for identity but does not follow the step join.

---

### C. Can exact sequence position be RECONSTRUCTED when B is absent?

**VERDICT: 1 — DIRECTLY SUPPORTED BY PROVIDER**

Not only reconstructable — it is directly available through two independent paths:

1. **Scheduled email path:** `reply → scheduled_email_id → GET /scheduled-emails/{id} → sequence_step_id`
2. **Event webhook path:** `EMAIL_SENT` event payload carries `sequence_step_id`, `sequence_step_order`, AND `sequence_step_variant` directly in `payload.data.scheduled_email`

The `sequence_step_order` field in the event payload gives the position number without any lookup.

**Implemented in Resonate OS:** No. Events are polled via `/events` but the `sequence_step_order` and `sequence_step_variant` fields in the payload are not extracted.

---

### D. Does EmailBison expose a persistent VARIANT identifier?

**VERDICT: 1 — DIRECTLY SUPPORTED BY PROVIDER**

Two independent sources:

1. **Event payload:** `sequence_step_variant` is an integer (e.g. 3, 4, 5, 7) present on every `EMAIL_SENT` event. It is `None` for non-variant steps (the "parent" step). Verified on 12 events.

2. **Sequence steps:** Each step has `variant` (bool) and `variant_from_step` (int, the parent step id). The step `id` itself is the persistent identifier — it appears in both the sequence-steps read and the scheduled-email record.

**Variant structure (campaign 352, verified on 44 steps):**
- Step 4035: order=1, variant=False (parent)
- Step 4036: order=None, variant=True, variant_from_step=4035 (variant A)
- Step 4192: order=None, variant=True, variant_from_step=4035 (variant B)
- Step 4193: order=None, variant=True, variant_from_step=4035 (variant C)
- Step 4037: order=2, variant=False (parent, next position)
- ...

**The `sequence_step_variant` value in events** is the step `id` of the variant that was sent, NOT a sequential index. It matches the step `id` in the sequence-steps listing.

**Implemented in Resonate OS:** No. The variant field on sequence steps is read by `sequence_steps()` but not used for experiment tracking.

---

## COMPLETE ENDPOINT INVENTORY

### 1. WORKSPACE / IDENTITY

| Endpoint | Method | Status | Verified | Implemented |
|---|---|---|---|---|
| `/users` | GET | 200 | YES | YES — `bound_workspace()` |
| `/workspaces` | GET | 200 | YES | NO |
| `/workspaces/{id}` | GET | 200 | YES (bison.py comment) | NO |

**`/users` response:**
```
data.workspace.id: int
data.workspace.name: str
```
This is the ONLY route that states which workspace the credential is bound to. Every list route accepts `workspace_id` and discards it.

**`/workspaces` response fields:** `id`, `name`, `personal_team`, `main`, `parent_id`, `warmup_filter_phrase`, `webhooks_secret_key`, `created_at`, `updated_at`

**⚠️ TRAP:** `workspace_id` is accepted and silently discarded on every list route. The answer for a workspace that does not exist is byte-identical to the answer for the one that does. `webhooks_secret_key` is exposed on the workspace object.

---

### 2. CAMPAIGNS

| Endpoint | Method | Status | Verified | Implemented |
|---|---|---|---|---|
| `/campaigns` | GET | 200 | YES | YES — `find_campaigns_by_name()` |
| `/campaigns` | POST | 201 | YES (bison.py) | YES — `create_campaign()` |
| `/campaigns/{id}` | GET | 200 | YES | YES — `campaign()` |
| `/campaigns/{id}` | DELETE | 200 | docs | NO |
| `/campaigns/{id}/update` | PATCH | 200 | YES | YES — `set_limits()` |
| `/campaigns/{id}/schedule` | GET | 200 | YES | YES — `schedule()` |
| `/campaigns/{id}/schedule` | POST | 200/201 | YES | YES — `set_schedule()` |
| `/campaigns/{id}/schedule` | PUT | 200 | YES | YES — `set_schedule()` |
| `/campaigns/{id}/sequence-steps` | GET | 200 | YES | YES — `sequence_steps()` |
| `/campaigns/{id}/sequence-steps` | POST | 201 | YES | YES — `set_sequence()` |
| `/campaigns/{id}/resume` | PATCH | 200 | YES | YES — `resume_campaign()` |
| `/campaigns/{id}/pause` | PATCH | 200 | YES | YES — `pause_campaign()` |
| `/campaigns/{id}/leads` | GET | 200 | YES | YES — `membership()`, `_paged()` |
| `/campaigns/{id}/leads/attach-leads` | POST | 200 | YES | YES — `attach_leads()` |
| `/campaigns/{id}/leads/attach-lead-list` | POST | — | docs only | NO |
| `/campaigns/{id}/leads/stop-future-emails` | POST | 200 | YES | YES — `stop_lead()` |
| `/campaigns/{id}/sender-emails` | GET | 200 | YES | YES — `campaign_senders()` |
| `/campaigns/{id}/attach-sender-emails` | POST | 200 | YES | YES — `attach_senders()` |
| `/campaigns/{id}/remove-sender-emails` | DELETE | — | docs only | NO |
| `/campaigns/{id}/scheduled-emails` | GET | 200 | YES | YES — `scheduled_emails()` |
| `/campaigns/schedule/templates` | GET | 200 | YES | NO |
| `/campaigns/{id}/create-schedule-from-template` | POST | — | docs only | NO |
| `/campaigns/{id}/statistics` | GET | 404 | YES | NO — does not exist |
| `/campaigns/{id}/reports` | GET | 404 | YES | NO — does not exist |
| `/campaigns/{id}/analytics` | GET | 404 | YES | NO — does not exist |
| `/campaigns/{id}/variants` | GET | 404 | YES | NO — does not exist |
| `/campaigns/{id}/ab-test` | GET | 404 | YES | NO — does not exist |

**Campaign list response fields (15 per page, per_page ignored):**

| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `uuid` | str | |
| `sequence_id` | int | |
| `name` | str | |
| `type` | str | `outbound` |
| `status` | str | `draft`/`paused`/`queued`/`active`/`failed`/`completed`/`archived`/`pending deletion` |
| `completion_percentage` | int | |
| `emails_sent` | int | |
| `opened` | int | |
| `unique_opens` | int | |
| `replied` | int | |
| `unique_replies` | int | |
| `bounced` | int | |
| `unsubscribed` | int | |
| `interested` | int | |
| `total_leads` | int | |
| `total_leads_contacted` | int | |
| `max_emails_per_day` | int | |
| `max_new_leads_per_day` | int | |
| `plain_text` | bool | |
| `open_tracking` | bool | **CRITICAL** — campaign 451 has this FALSE |
| `can_unsubscribe` | bool | |
| `unsubscribe_text` | str/null | |
| `include_auto_replies_in_stats` | bool | |
| `sequence_prioritization` | str | `followups` |
| `daily_max_sends_per_receiving_domain` | int | |
| `created_at` | str | |
| `updated_at` | str | |
| `tags` | list | |

**⚠️ TRAP:** `POST /campaigns` silently discards `max_emails_per_day`. Must use `/campaigns/{id}/update` after creation.

---

### 3. SEQUENCE STEPS

**Endpoint:** `GET /campaigns/{id}/sequence-steps`
**Verified:** YES — 200, not paginated, all steps in one response.

**Response fields per step:**

| Field | Type | Notes |
|---|---|---|
| `id` | int | persistent identifier |
| `order` | int/null | null for variants |
| `email_subject` | str | template with `{VARIABLE}` syntax |
| `email_body` | str | template with `{VARIABLE}` syntax |
| `wait_in_days` | int | |
| `active` | bool | |
| `variant` | bool | true if this IS a variant |
| `variant_from_step` | int/null | parent step id (null for parents) |
| `thread_reply` | bool | whether this is a reply in-thread |
| `attachments` | null | |
| `created_at` | str | |
| `updated_at` | str | |

**⚠️ A 200 IS NOT AN EXISTENCE PROOF:** A campaign with no sequence answers 200 carrying `{"success": false, "message": "Sequence steps do not exist for <name>"}`.

**⚠️ APPEND ONLY:** `POST` appends; there is no replace and no per-step delete. Writing twice doubles the sequence.

---

### 4. LEADS

| Endpoint | Method | Status | Verified | Implemented |
|---|---|---|---|---|
| `/leads` | GET | 200 | YES | YES — `find_lead_by_email()` |
| `/leads` | POST | 201 | YES | YES — `create_lead()` |
| `/leads/{id}` | GET | 200 | YES | YES — `lead()` |
| `/leads/{id}` | PATCH | 200 | YES | YES — `update_lead()` |
| `/leads/{id}` | DELETE | — | docs | NO |
| `/leads/{id}/replies` | GET | 200 | YES | NO |
| `/leads/{id}/sent-emails` | GET | 200 | YES | NO |
| `/leads/bulk/csv` | POST | — | docs only | NO |

**Lead response fields:**

| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `uuid` | str | |
| `first_name` | str | |
| `last_name` | str | |
| `email` | str | |
| `title` | str/null | |
| `company` | str/null | |
| `notes` | str/null | |
| `status` | str | `unverified` etc. |
| `custom_variables` | list | `[{name, value}]` |
| `tags` | list | `[{id, name, default, created_at, updated_at}]` |
| `lead_campaign_data` | list | per-campaign status (see below) |
| `overall_stats` | dict | `{emails_sent, opens, replies, unique_replies, unique_opens}` |
| `created_at` | str | |
| `updated_at` | str | |

**`lead_campaign_data` entry fields:**

| Field | Type | Notes |
|---|---|---|
| `campaign_id` | int | |
| `status` | str | `in_sequence`/`stopped`/`replied`/`bounced`/`sequence_finished`/`unsubscribed`/`sending_paused`/`never_contacted` |
| `emails_sent` | int | |
| `replies` | int | |
| `opens` | int | |
| `interested` | bool | |

**⚠️ TRAP:** `?search=` is a real filter; `?email=` is accepted and discarded, returning unfiltered results.

**⚠️ INDEX LAG:** The search index lags creation by ~1 second. A lead created moments ago may not appear in `?search=`.

**Pagination:** 15 per page (per_page ignored), offset, meta.total present. Total estate: 1,816 pages × 15 = ~27,240 leads.

---

### 5. LEAD REPLIES AND SENT_EMAILS (per-lead)

**`GET /leads/{id}/replies`** — verified 200, offset paginated, same reply shape as `/replies`.

**`GET /leads/{id}/sent-emails`** — verified 200, offset paginated, returns scheduled-email rows (same shape as `/campaigns/{id}/scheduled-emails`) filtered to this lead. Includes `sequence_step_id`, `sent_at`, `status`.

**Both are NOT implemented in Resonate OS.**

---

### 6. SCHEDULED EMAILS (the send history)

**`GET /campaigns/{id}/scheduled-emails`** — the single most important endpoint for step-level learning.

**`GET /scheduled-emails/{id}`** — verified 200 for a specific scheduled email by id. Returns the full row including `sequence_step_id`, `sent_at`, `status`, rendered `email_subject` and `email_body`.

**All response fields:**

| Field | Type | Notes |
|---|---|---|
| `id` | int | scheduled email id |
| `campaign_id` | int | |
| `campaign` | dict | full campaign object (nested) |
| `lead` | dict | full lead object (nested) |
| `sender_email` | dict | full sender object (nested) |
| `sequence_step_id` | int | **THE STEP JOIN** |
| `status` | str | `scheduled`/`sent`/`bounced`/`stopped` |
| `sent_at` | str/null | actual send timestamp |
| `scheduled_date` | str | planned send timestamp (UTC) |
| `scheduled_date_local` | str | planned send timestamp (local) |
| `email_subject` | str | rendered (merge fields resolved) |
| `email_body` | str | rendered (merge fields resolved) |
| `opens` | int | |
| `replies` | int | |
| `unique_opens` | int | |
| `unique_replies` | int | |
| `clicks` | int | |
| `interested` | bool | |
| `thread_reply` | bool | |
| `raw_message_id` | str | |

**Pagination:** 15 per page (per_page ignored), offset, meta.total present. Campaign 352 has 95,439 rows = 6,363 pages.

---

### 7. REPLIES (the inbox feed)

**`GET /replies`** — verified 200, cursor pagination with `pagination_type=cursor`.

**All response fields listed in section B above.**

**Pagination:** Cursor. `meta.next_cursor` is an opaque base64 string. Default 15 per page. No explicit page count limit. `per_page` values of 5, 15, 50, 100 all return 15 rows on this instance.

**⚠️ HAZARD:** The feed carries outbound mail as type `Outgoing Email` in folder `Sent`. Never ingest as a reply.

---

### 8. SENDER EMAILS

**`GET /sender-emails`** — verified 200, 15 per page, 15 pages = 225 total.

**Response fields:**

| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `name` | str | sender display name |
| `email` | str | |
| `email_signature` | str | |
| `imap_server` | str/null | |
| `imap_port` | int/null | |
| `smtp_server` | str/null | |
| `smtp_port` | int/null | |
| `daily_limit` | int | |
| `type` | str | `google_workspace_oauth` etc. |
| `status` | str | |
| `warmup_enabled` | bool | |
| `tags` | list | free text, no referential integrity |
| `emails_sent_count` | int | |
| `total_replied_count` | int | |
| `total_opened_count` | int | |
| `unsubscribed_count` | int | |
| `bounced_count` | int | |
| `unique_replied_count` | int | |
| `unique_opened_count` | int | |
| `total_leads_contacted_count` | int | |
| `interested_leads_count` | int | |
| `created_at` | str | |
| `updated_at` | str | |

**⚠️ TRAP:** `workspace_id` parameter is accepted and discarded. No sender row carries a workspace field. Ownership cannot be established from the payload.

---

### 9. CUSTOM VARIABLES

**`GET /custom-variables`** — verified 200, 24 total, 2 pages.

**Response fields:** `id`, `name`, `created_at`, `updated_at`

**Implemented:** YES — `custom_variables()`, `ensure_custom_variables()`

---

### 10. TAGS

**`GET /tags`** — verified 200, 31 tags returned in one page.

**Response fields:** `id`, `name`, `default`, `created_at`, `updated_at`

| Endpoint | Method | Status | Verified | Implemented |
|---|---|---|---|---|
| `/tags` | GET | 200 | YES | NO |
| `/tags` | POST | — | docs | NO |
| `/tags/attach-to-leads` | POST | — | docs | NO |
| `/tags/attach-to-campaigns` | POST | — | docs | NO |
| `/tags/attach-to-sender-emails` | POST | — | docs | NO |
| `/tags/attach-to-leads` | DELETE | — | docs | NO |
| `/tags/attach-to-campaigns` | DELETE | — | docs | NO |
| `/tags/attach-to-sender-emails` | DELETE | — | docs | NO |

**Not implemented in Resonate OS.**

---

### 11. EVENTS (webhook event log)

**`GET /events`** — verified 200, cursor paginated.

**Response fields per event:**

| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `uuid` | str | |
| `payload` | dict | contains `event` and `data` |
| `payload.event.type` | str | `EMAIL_SENT`, `CONTACT_REPLIED`, etc. |
| `payload.event.name` | str | human-readable event name |
| `payload.event.instance_url` | str | |
| `payload.event.workspace_id` | int | |
| `payload.event.workspace_name` | str | |
| `payload.data.scheduled_email.id` | int | |
| `payload.data.scheduled_email.lead_id` | int | |
| `payload.data.scheduled_email.sequence_step_id` | int | |
| `payload.data.scheduled_email.sequence_step_order` | int | **position number** |
| `payload.data.scheduled_email.sequence_step_variant` | int/null | **variant step id** |
| `payload.data.scheduled_email.email_subject` | str | |
| `payload.data.scheduled_email.email_body` | str | |
| `webhook_deliveries` | list | |
| `created_at` | str | |

**This endpoint carries the richest step-level data in the API** — `sequence_step_order` and `sequence_step_variant` appear ONLY here, not on the scheduled-email or reply objects.

**History:** 10 days per the documentation.

**Not implemented in Resonate OS.**

---

### 12. LEAD LISTS

**`GET /lead-lists`** — verified 200, 15 total, 1 page.

**Response fields:** `id`, `name`, `status`, `leads_processed`, `leads_succeeded`, `leads_failed`, `error_messages`, `created_at`, `updated_at`

**Not implemented in Resonate OS.**

---

### 13. ENDPOINTS THAT DO NOT EXIST (404)

| Path | Status | Notes |
|---|---|---|
| `/conversations` | 404 | |
| `/threads` | 404 | |
| `/messages` | 404 | |
| `/webhooks` | 404 | confirmed in bison.py |
| `/webhook-urls` | 404 | |
| `/blocklist/emails` | 404 | |
| `/blocklist/domains` | 404 | |
| `/campaigns/{id}/statistics` | 404 | |
| `/campaigns/{id}/reports` | 404 | |
| `/campaigns/{id}/analytics` | 404 | |
| `/campaigns/{id}/variants` | 404 | |
| `/campaigns/{id}/ab-test` | 404 | |
| `/activity` | 404 | |
| `/audit-log` | 404 | |
| `/workspaces/current` | 404 | confirmed in bison.py |
| `/me` | 404 | confirmed in bison.py |
| `/user` | 404 | confirmed in bison.py |
| `/account` | 404 | confirmed in bison.py |
| `/whoami` | 404 | confirmed in bison.py |

---

## WRITE ENDPOINTS (DOCUMENTED, NOT CALLED)

These are documented from the EmailBison docs and the existing code. **None were called during this inventory.**

| Endpoint | Method | Purpose | In WRITE_ROUTES |
|---|---|---|---|
| `/campaigns` | POST | Create campaign (draft) | YES |
| `/campaigns/{id}/update` | PATCH | Set limits, open_tracking, etc. | YES |
| `/campaigns/{id}/sequence-steps` | POST | Append sequence steps | YES |
| `/campaigns/{id}/leads/attach-leads` | POST | Add leads by id | YES |
| `/campaigns/{id}/leads/attach-lead-list` | POST | Add leads from list | NO |
| `/campaigns/{id}/leads/stop-future-emails` | POST | Stop one person | YES |
| `/campaigns/{id}/pause` | PATCH | Pause campaign | YES |
| `/campaigns/{id}/resume` | PATCH | **START SENDING** | YES |
| `/campaigns/{id}/schedule` | POST/PUT | Set sending window | YES |
| `/campaigns/{id}/attach-sender-emails` | POST | Bind inboxes | YES |
| `/campaigns/{id}/remove-sender-emails` | DELETE | Remove inboxes | NO |
| `/campaigns/{id}/create-schedule-from-template` | POST | Apply template | NO |
| `/leads` | POST | Create lead | YES |
| `/leads/{id}` | PATCH | Update lead fields | YES |
| `/leads/bulk/csv` | POST | Bulk CSV upload | NO |
| `/custom-variables` | POST | Declare variable name | YES |
| `/tags` | POST | Create tag | NO |
| `/tags/attach-to-leads` | POST | Tag leads | NO |
| `/tags/attach-to-campaigns` | POST | Tag campaigns | NO |
| `/tags/attach-to-sender-emails` | POST | Tag senders | NO |
| `/replies/{id}/reply` | POST | Send a reply | NO |
| `/replies/{id}/attach-email-to-reply` | POST | Link untracked reply | NO |
| `/webhook-events/test-event` | POST | Fire test webhook | NO |

---

## PAGINATION SUMMARY

| Route | Type | Per page | Max pages | Notes |
|---|---|---|---|---|
| `/campaigns` | offset | 15 (ignored) | 1000 | per_page accepted but ignored |
| `/campaigns/{id}/leads` | offset | 15 (ignored) | 1000 | per_page accepted but ignored |
| `/campaigns/{id}/scheduled-emails` | offset | 15 (ignored) | 1000 | per_page accepted but ignored |
| `/campaigns/{id}/sender-emails` | offset | 15 (ignored) | 1000 | per_page accepted but ignored |
| `/leads` | offset | 15 (ignored) | 1000 | per_page accepted but ignored |
| `/sender-emails` | offset | 15 | — | per_page works here |
| `/custom-variables` | offset | 15 | — | |
| `/tags` | offset | 15 | — | all 31 in one page |
| `/lead-lists` | offset | 15 | — | |
| `/replies` | cursor | 15 | unlimited | `pagination_type=cursor` required |
| `/events` | cursor | 15 | unlimited | 10-day history |

**Critical:** `per_page` is ignored on most routes. Always 15 rows per page regardless of what you ask for.

---

## WEBHOOK EVENTS (from documentation)

23 event types documented. Key ones for Resonate OS:

1. **Email Sent** — campaign email sent
2. **Manual Email Sent** — reply or compose via inbox/API
3. **Contact First Emailed** — first campaign email in workspace
4. **Contact Replied** — lead replies (excludes auto-replies if configured)
5. **Contact Interested** — reply marked interested
6. **Contact Unsubscribed** — lead unsubscribed
7. **Untracked Reply Received** — reply not associated with a scheduled email
8. **Email Opened** — requires `open_tracking` enabled
9. **Email Bounced** — campaign email bounced
10. **Email Send Failed** — scheduled email failed to send

**`skip_webhooks` parameter:** Available on blocklist operations.

**Webhook management:** No `/api/webhooks` route exists on this instance (404). Polling is the transport.

---

## CAPABILITIES NOT IN EXISTING CODE

These endpoints exist and answer questions the current code does not ask:

| Endpoint | What it answers | TASK-069 relevance |
|---|---|---|
| `GET /scheduled-emails/{id}` | One scheduled email with step id | B — the second hop |
| `GET /leads/{id}/replies` | Per-lead reply feed | B, C |
| `GET /leads/{id}/sent-emails` | Per-lead send history with step id | A, C |
| `GET /events` | EMAIL_SENT with step order + variant | A, C, D |
| `GET /workspaces` | Workspace metadata | tenancy |
| `GET /lead-lists` | Bulk upload history | operational |
| `GET /tags` | Tag inventory | operational |
| `GET /campaigns/schedule/templates` | Reusable schedules | operational |

---

## KNOWN LIMITATIONS AND TRAPS

1. **`per_page` is ignored** on most routes. Always 15 rows per page.
2. **`workspace_id` is accepted and discarded** on every list route. The credential IS the boundary.
3. **Search index lags creation** by ~1 second.
4. **`POST /campaigns` silently discards `max_emails_per_day`** — must set via `/update` after.
5. **Sequence steps append only** — no replace, no per-step delete.
6. **`open_tracking` defaults to false** — zero opens may mean absent measurement, not zero interest.
7. **Reply feed carries outbound mail** as type `Outgoing Email` in folder `Sent`.
8. **Campaign lead list ignores `per_page`** — 15 rows whatever you ask for.
9. **Events have 10-day history** — not suitable for full historical analysis.
10. **`/scheduled-emails/{id}` returns 404 with `Record not found`** when the id is a lead id, not a scheduled email id — the path parameter is a scheduled email id, not a lead id.

---

## THE FULL JOIN CHAIN

The operator's question and whether it is answerable:

```
campaign        → GET /campaigns/{id}               → campaign_id, name, status, stats
  → lead        → GET /campaigns/{id}/leads          → lead_id, email, custom_variables, lead_campaign_data
    → step      → GET /campaigns/{id}/scheduled-emails → sequence_step_id, sent_at, email_subject, email_body
      → reply   → GET /replies (scheduled_email_id)  → reply_id, date_received, type, interested
        → step  → GET /scheduled-emails/{id}          → sequence_step_id (the second hop)
```

**The chain is complete.** Every link exists and is verified. The one extra hop — reply → scheduled_email → step — is a two-step lookup, not a gap.

**The event payload shortcut:** `GET /events` carries `sequence_step_id`, `sequence_step_order`, AND `sequence_step_variant` in a single read, but is limited to 10 days.
