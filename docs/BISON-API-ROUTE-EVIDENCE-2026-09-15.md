---
title: "EmailBison API Route Evidence Map"
task: "TASK-111"
date: "2026-09-15"
supersedes: "docs/BISON-API-CAPABILITY-MAP-2026-09-14.md (route inventory sections)"
---

# EmailBison API Route Evidence Map — 2026-09-15

**TASK-111 deliverable.** Every EmailBison route the codebase references or
calls, classified by evidence level, with the evidence cited.

**Workspace:** PRODUCTIVE (id 10), the only workspace on this instance.
**Base URL:** `https://send.resonategroup.co/api`
**Auth:** `Authorization: Bearer <BISON_KEY>` (api-user key, workspace-bound)

**Probed on 2026-09-15** unless an earlier date is cited. All probes are
read-only (GET). No write route was probed.

---

## Evidence levels

Each route carries one of four evidence levels:

| Level | Meaning |
|---|---|
| **LIVE** | A real GET returned 200 with a parseable response. Shape recorded. |
| **CODE** | The codebase calls this route and handles its response. Shape confirmed in code but not re-probed live. |
| **DOCS** | The vendor documentation names this route. No live probe and no code caller. |
| **GUESSED** | Neither documented, nor called, nor probed. Inferred from naming patterns. |

A route with CODE evidence has a function in `src/providers/bison.py` (or
another `src/` module) that constructs the URL and reads the response. That
is stronger than DOCS but weaker than LIVE — the code may handle an error
shape rather than the success shape, or the provider may have changed since
the code was written.

A 404 is a LIVE result. "This route does not exist" is a finding, not a gap.

---

## COMPLETE ROUTE INVENTORY

### 1. WORKSPACE / IDENTITY

| Route | Method | Evidence | Status | In code | In WRITE_ROUTES |
|---|---|---|---|---|---|
| `/users` | GET | **LIVE** 2026-09-15 | 200 | `bound_workspace()` | No |
| `/workspaces` | GET | **LIVE** 2026-09-15 | 200 | No | No |
| `/workspaces/{id}` | GET | **LIVE** 2026-09-15 | 200 | No | No |
| `/workspaces/current` | GET | **LIVE** 2026-09-15 | 404 | No | No |
| `/me` | GET | **LIVE** 2026-09-15 | 404 | No | No |
| `/user` | GET | **LIVE** 2026-09-15 | 404 | No | No |
| `/account` | GET | **LIVE** 2026-09-15 | 404 | No | No |
| `/whoami` | GET | **LIVE** 2026-09-15 | 404 | No | No |

**`/users` response shape (LIVE):**
```
data.id: int (user id)
data.name: str
data.email: str
data.workspace.id: int         ← THE BINDING
data.workspace.name: str       ← "PRODUCTIVE"
data.workspace.personal_team: bool
data.workspace.main: bool
data.workspace.parent_id: int
data.workspace.warmup_filter_phrase: str
data.workspace.webhooks_secret_key: str   ← ⚠️ secret exposed
data.profile_photo_path: null
data.profile_photo_url: str
data.created_at: str
data.updated_at: str
```

**`/workspaces` response shape (LIVE):**
```
data: list[1]     ← ONLY ONE WORKSPACE NOW (was 13 on 2026-09-07)
  id: int
  name: str
  personal_team: bool
  main: bool
  parent_id: int
  warmup_filter_phrase: str
  webhooks_secret_key: str    ← ⚠️ secret exposed
  created_at: str
  updated_at: str
```

**`/workspaces/10` response shape (LIVE):** Same as one workspace row above.

**⚠️ TRAP:** `workspace_id` is accepted and silently discarded on every list
route. The credential IS the boundary. `/users` is the only route that states
which workspace the credential is bound to.

**⚠️ CHANGE:** The bison.py comment from 2026-09-07 says "thirteen
workspaces." On 2026-09-15, `/workspaces` returns exactly one: PRODUCTIVE
(id 10). Workspaces have been removed or the credential was rebound.

---

### 2. CAMPAIGNS

| Route | Method | Evidence | Status | In code | In WRITE_ROUTES |
|---|---|---|---|---|---|
| `/campaigns` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `find_campaigns_by_name()`, `check()` | No |
| `/campaigns` | POST | **CODE** | 201 (code) | `create_campaign()` | YES |
| `/campaigns/{id}` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `campaign()` | No |
| `/campaigns/{id}` | DELETE | **DOCS** | not probed | No | No |
| `/campaigns/{id}/update` | PATCH | **CODE** | 200 (code) | `set_limits()` | YES |
| `/campaigns/{id}/schedule` | GET | **CODE** | 200 (code) | `schedule()` | No |
| `/campaigns/{id}/schedule` | POST | **CODE** | 200/201 (code) | `set_schedule()` | YES |
| `/campaigns/{id}/schedule` | PUT | **CODE** | 200 (code) | `set_schedule()` | YES |
| `/campaigns/{id}/sequence-steps` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `sequence_steps()` | No |
| `/campaigns/{id}/sequence-steps` | POST | **CODE** | 201 (code) | `set_sequence()` | YES |
| `/campaigns/{id}/resume` | PATCH | **CODE** | 200 (code) | `resume_campaign()` | YES |
| `/campaigns/{id}/pause` | PATCH | **CODE** | 200 (code) | `pause_campaign()` | YES |
| `/campaigns/{id}/leads` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `membership()`, `_paged()` | No |
| `/campaigns/{id}/leads/attach-leads` | POST | **CODE** | 200 (code) | `attach_leads()` | YES |
| `/campaigns/{id}/leads/attach-lead-list` | POST | **DOCS** | not probed | No | No |
| `/campaigns/{id}/leads/stop-future-emails` | POST | **CODE** | 200 (code) | `stop_lead()` | YES |
| `/campaigns/{id}/sender-emails` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `campaign_senders()` | No |
| `/campaigns/{id}/attach-sender-emails` | POST | **CODE** | 200 (code) | `attach_senders()` | YES |
| `/campaigns/{id}/remove-sender-emails` | DELETE | **DOCS** | not probed | No | No |
| `/campaigns/{id}/scheduled-emails` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `scheduled_emails()` | No |
| `/campaigns/schedule/templates` | GET | **LIVE** 2026-09-15 | 200 | No | No |
| `/campaigns/{id}/create-schedule-from-template` | POST | **DOCS** | not probed | No | No |
| `/campaigns/{id}/statistics` | GET | **LIVE** 2026-09-15 | **404** | No | No |
| `/campaigns/{id}/reports` | GET | **LIVE** 2026-09-15 | **404** | No | No |
| `/campaigns/{id}/analytics` | GET | **LIVE** 2026-09-15 | **404** | No | No |
| `/campaigns/{id}/variants` | GET | **LIVE** 2026-09-15 | **404** | No | No |
| `/campaigns/{id}/ab-test` | GET | **LIVE** 2026-09-15 | **404** | No | No |

**Campaign listing response shape (LIVE, 29 fields):**

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
| `opened` | int | Always 0 — `open_tracking` is false estate-wide |
| `unique_opens` | int | Always 0 |
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
| `open_tracking` | bool | **ALL FALSE estate-wide** |
| `can_unsubscribe` | bool | |
| `unsubscribe_text` | null | |
| `include_auto_replies_in_stats` | bool | |
| `sequence_prioritization` | str | `followups` |
| `daily_max_sends_per_receiving_domain` | int | |
| `created_at` | str | |
| `updated_at` | str | |
| `tags` | list | All empty |

**⚠️ TRAP:** `POST /campaigns` silently discards `max_emails_per_day`. Must
use `/campaigns/{id}/update` after creation.

**⚠️ TRAP:** `?search=` on `/campaigns/{id}/leads` is accepted and DISCARDED.
A search for a nonexistent term returns the full unfiltered listing
(meta.total=21,249 for campaign 352). This is different from `/leads` where
`?search=` IS a real filter.

---

### 3. SEQUENCE STEPS

| Route | Method | Evidence | Status | In code | In WRITE_ROUTES |
|---|---|---|---|---|---|
| `/campaigns/{id}/sequence-steps` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `sequence_steps()` | No |
| `/campaigns/{id}/sequence-steps` | POST | **CODE** | 201 (code) | `set_sequence()` | YES |

**Response shape (LIVE, 12 fields per step):**

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
| `thread_reply` | bool | |
| `attachments` | null | |
| `created_at` | str | |
| `updated_at` | str | |

**Not paginated.** All steps arrive in one response with no `meta`.

**⚠️ A 200 IS NOT AN EXISTENCE PROOF:** A campaign with no sequence answers
200 carrying `{"success": false, "message": "Sequence steps do not exist for
<name>"}`. (Campaign 481 now has 5 steps as of 2026-09-15.)

**⚠️ APPEND ONLY:** `POST` appends; there is no replace and no per-step
delete. Writing twice doubles the sequence.

---

### 4. LEADS

| Route | Method | Evidence | Status | In code | In WRITE_ROUTES |
|---|---|---|---|---|---|
| `/leads` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `find_lead_by_email()` | No |
| `/leads` | POST | **CODE** | 201 (code) | `create_lead()` | YES |
| `/leads/{id}` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `lead()` | No |
| `/leads/{id}` | PATCH | **CODE** | 200 (code) | `update_lead()` | YES |
| `/leads/{id}` | DELETE | **DOCS** | not probed | No | No |
| `/leads/{id}/replies` | GET | **LIVE** 2026-09-15 | 200 | No | No |
| `/leads/{id}/sent-emails` | GET | **LIVE** 2026-09-15 | 200 | No | No |
| `/leads/bulk/csv` | POST | **DOCS** | not probed | No | No |

**Lead response shape (CODE + LIVE, 14+ fields):**

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
| `lead_campaign_data` | list | per-campaign status |
| `overall_stats` | dict | `{emails_sent, opens, replies, unique_replies, unique_opens}` |
| `created_at` | str | |
| `updated_at` | str | |

**⚠️ TRAP:** `?search=` is a real filter on `/leads`; `?email=` is accepted
and discarded.

**⚠️ INDEX LAG:** The search index lags creation by ~1 second.

**Pagination:** 15 per page (per_page ignored), offset, meta.total present.

---

### 5. PER-LEAD REPLIES AND SENT-EMAILS

**NEWLY CONFIRMED LIVE on 2026-09-15.** These routes were listed in the
earlier capability map from documentation only. They are now LIVE-verified.

#### `GET /leads/{id}/replies`

**Evidence: LIVE** — 200, offset paginated, lead 172105 returns 1 reply.

**Response shape:** Same reply fields as `GET /replies` (30 fields). Offset
pagination with `meta.current_page`, `meta.last_page`, `meta.total`.

**First reply keys (LIVE):** `attachments`, `automated_reply`, `bcc`,
`campaign_id`, `cc`, `created_at`, `date_received`, `folder`,
`from_email_address`, `from_name`, `headers`, `html_body`, `id`,
`interested`, `lead`, `lead_id`, `parent_id`, `primary_to_email_address`,
`raw_body`, `raw_message_id`, `read`, `scheduled_email_id`,
`sender_email_id`, `subject`, `text_body`, `to`, `tracked_reply`, `type`,
`updated_at`, `uuid`

**Not implemented in Resonate OS.**

#### `GET /leads/{id}/sent-emails`

**Evidence: LIVE** — 200, offset paginated, lead 172105 returns 12 sent
emails.

**Response shape:** Same scheduled-email fields as
`GET /campaigns/{id}/scheduled-emails`, **including the `lead` nested
object**. This is DIFFERENT from `GET /scheduled-emails/{id}` which does NOT
carry the lead field (see section 6).

**First sent-email keys (LIVE):** `campaign`, `campaign_id`, `clicks`,
`email_body`, `email_subject`, `id`, `interested`, `lead`, `opens`,
`raw_message_id`, `replies`, `scheduled_date`, `scheduled_date_local`,
`sender_email`, `sent_at`, `sequence_step_id`, `status`, `thread_reply`,
`unique_opens`, `unique_replies`

**Not implemented in Resonate OS.**

---

### 6. SCHEDULED EMAILS (the send history)

| Route | Method | Evidence | Status | In code | In WRITE_ROUTES |
|---|---|---|---|---|---|
| `/campaigns/{id}/scheduled-emails` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `scheduled_emails()` | No |
| `/scheduled-emails/{id}` | GET | **LIVE** 2026-09-15 | 200 | No | No |

#### Listing form: `GET /campaigns/{id}/scheduled-emails`

**Response shape (LIVE, 21 fields):**

| Field | Type | Notes |
|---|---|---|
| `id` | int | scheduled email id |
| `campaign_id` | int | |
| `campaign` | dict (nested) | full campaign object (28 keys) |
| `lead` | dict (nested) | **PRESENT** — full lead object (13 keys) |
| `sender_email` | dict (nested) | full sender object (23 keys) |
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

**Lead nested object keys (LIVE):** `company`, `created_at`,
`custom_variables`, `email`, `first_name`, `id`, `last_name`, `notes`,
`overall_stats`, `status`, `title`, `updated_at`, `uuid`

#### Individual form: `GET /scheduled-emails/{id}`

**Evidence: LIVE** — 200 for id 22290485.

**Response shape (LIVE, 19 fields):**

| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `campaign_id` | int | |
| `campaign` | dict (nested) | full campaign object |
| `sender_email` | dict (nested) | full sender object |
| `sequence_step_id` | int | **THE STEP JOIN** |
| `status` | str | |
| `sent_at` | str/null | |
| `scheduled_date` | str | |
| `scheduled_date_local` | str | |
| `email_subject` | str | rendered |
| `email_body` | str | rendered |
| `opens` | int | |
| `replies` | int | |
| `unique_opens` | int | |
| `unique_replies` | int | |
| `clicks` | int | |
| `interested` | bool | |
| `thread_reply` | bool | |
| `raw_message_id` | str | |

**⚠️ DIFFERENCE FROM LISTING FORM:** The individual form does NOT carry a
`lead` nested object. The listing form does. This is a real asymmetry in the
provider's API — the same scheduled email returns different field sets
depending on whether it is fetched by listing or by id. The earlier
capability map listed `lead` on the individual form; that was wrong.

**⚠️ TRAP:** `/scheduled-emails/{id}` where `{id}` is a LEAD id returns 404
"Record not found" — the path parameter is a scheduled email id, not a lead
id.

**Pagination (listing):** 15 per page (per_page ignored), offset, meta.total
present. Campaign 352 has 95,439+ rows.

---

### 7. REPLIES (the inbox feed)

| Route | Method | Evidence | Status | In code | In WRITE_ROUTES |
|---|---|---|---|---|---|
| `/replies` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `fetch_replies()` | No |
| `/replies/{id}` | GET | **LIVE** 2026-09-15 | 200 | No | No |
| `/replies/{id}/reply` | POST | **DOCS** | not probed | No | No |
| `/replies/{id}/attach-email-to-reply` | POST | **DOCS** | not probed | No | No |

**Reply row shape (LIVE, 31 fields):**

| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `uuid` | str | |
| `type` | str | `Tracked Reply` / `Untracked Reply` / `Outgoing Email` / `Bounced` |
| `folder` | str | `Inbox` / `Sent` / `Bounced` |
| `campaign_id` | int | |
| `lead_id` | int | |
| `scheduled_email_id` | int | **the join to step** |
| `sender_email_id` | int | |
| `parent_id` | null | always null in sample |
| `subject` | str | |
| `text_body` | str | |
| `html_body` | str | |
| `raw_body` | null | |
| `headers` | null | |
| `date_received` | str (ISO 8601) | |
| `created_at` | str (ISO 8601) | |
| `updated_at` | str (ISO 8601) | |
| `from_email_address` | str | |
| `from_name` | str | |
| `primary_to_email_address` | str | |
| `to` | list | `[{name, address}]` |
| `cc` | null | |
| `bcc` | null | |
| `automated_reply` | bool | |
| `tracked_reply` | bool | |
| `interested` | bool | |
| `read` | bool | |
| `lead` | dict (nested) | full lead object (13 keys) |
| `raw_message_id` | str | |
| `attachments` | list | |

**`GET /replies/{id}` (LIVE):** Returns the same shape as a listing row,
wrapped in `{"data": {...}}`.

**Pagination:** Cursor. `meta.next_cursor` is an opaque base64 string.
Default 15 per page. `per_page` is IGNORED (5, 15, 50, 100 all return 15).

**⚠️ HAZARD:** The feed carries outbound mail as type `Outgoing Email` in
folder `Sent`. Never ingest as a reply.

---

### 8. SENDER EMAILS

| Route | Method | Evidence | Status | In code | In WRITE_ROUTES |
|---|---|---|---|---|---|
| `/sender-emails` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `sender_emails()` | No |

**Response shape (LIVE, 24 fields):**

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

**Pagination:** 15 per page, offset, meta.total present. Total: 225 senders
across 15 pages.

**⚠️ TRAP:** `workspace_id` parameter is accepted and discarded.

---

### 9. CUSTOM VARIABLES

| Route | Method | Evidence | Status | In code | In WRITE_ROUTES |
|---|---|---|---|---|---|
| `/custom-variables` | GET | **CODE** + **LIVE** 2026-09-15 | 200 | `custom_variables()` | No |
| `/custom-variables` | POST | **CODE** | 201 (code) | `ensure_custom_variables()` | YES |

**Response shape (LIVE, 4 fields):** `id`, `name`, `created_at`, `updated_at`

**Pagination:** 15 per page (per_page ignored), offset, meta.total present.
24 total variables, 2 pages.

---

### 10. TAGS

| Route | Method | Evidence | Status | In code | In WRITE_ROUTES |
|---|---|---|---|---|---|
| `/tags` | GET | **LIVE** 2026-09-15 | 200 | No | No |
| `/tags` | POST | **DOCS** | not probed | No | No |
| `/tags/attach-to-leads` | POST | **DOCS** | not probed | No | No |
| `/tags/attach-to-campaigns` | POST | **DOCS** | not probed | No | No |
| `/tags/attach-to-sender-emails` | POST | **DOCS** | not probed | No | No |
| `/tags/attach-to-leads` | DELETE | **DOCS** | not probed | No | No |
| `/tags/attach-to-campaigns` | DELETE | **DOCS** | not probed | No | No |
| `/tags/attach-to-sender-emails` | DELETE | **DOCS** | not probed | No | No |

**Response shape (LIVE, 5 fields):** `id`, `name`, `default`, `created_at`,
`updated_at`. 31 tags, all in one page.

**Not implemented in Resonate OS.**

---

### 11. EVENTS (webhook event log)

| Route | Method | Evidence | Status | In code | In WRITE_ROUTES |
|---|---|---|---|---|---|
| `/events` | GET | **LIVE** 2026-09-15 | 200 | No | No |
| `/webhook-events/test-event` | POST | **DOCS** | not probed | No | No |

**Evidence: LIVE** — 200, cursor paginated, 15 per page (per_page=5
ignored).

**Response shape (LIVE):**

```
data: list[15]
  id: int
  uuid: str
  payload.event.type: str          ← "EMAIL_SENT", "CONTACT_REPLIED", etc.
  payload.event.name: str
  payload.event.instance_url: str
  payload.event.workspace_id: int
  payload.event.workspace_name: str
  payload.data.campaign: dict
  payload.data.campaign_event: dict
  payload.data.lead: dict
  payload.data.scheduled_email: dict  ← SEE BELOW
  payload.data.sender_email: dict
  webhook_deliveries: list[0]
  created_at: str
  updated_at: str
meta:
  path: str
  per_page: int
  next_cursor: str                 ← cursor pagination
  prev_cursor: null
```

**`payload.data.scheduled_email` keys (LIVE):** `email_body`,
`email_subject`, `id`, `interested`, `lead_id`, `local_timezone`, `opens`,
`raw_message_id`, `replies`, `scheduled_date_est`, `scheduled_date_local`,
`sent_at`, `sequence_step_id`, **`sequence_step_order`**,
**`sequence_step_variant`**, `status`, `unique_opens`, `unique_replies`

**This endpoint carries the richest step-level data in the API** —
`sequence_step_order` and `sequence_step_variant` appear ONLY here, not on
the scheduled-email or reply objects.

**History:** 10 days per the documentation. First page (2026-09-15): all 15
events were `EMAIL_SENT`.

**Not implemented in Resonate OS.**

---

### 12. LEAD LISTS

| Route | Method | Evidence | Status | In code | In WRITE_ROUTES |
|---|---|---|---|---|---|
| `/lead-lists` | GET | **LIVE** 2026-09-15 | 200 | No | No |

**Evidence: LIVE** — 200, offset paginated, 15 total, 1 page.

**Response shape (LIVE, 9 fields):**

| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `name` | str | |
| `status` | str | `Processed` etc. |
| `leads_processed` | int | |
| `leads_succeeded` | int | |
| `leads_failed` | int | |
| `error_messages` | list | |
| `created_at` | str | |
| `updated_at` | str | |

**Not implemented in Resonate OS.**

---

### 13. SCHEDULE TEMPLATES

| Route | Method | Evidence | Status | In code | In WRITE_ROUTES |
|---|---|---|---|---|---|
| `/campaigns/schedule/templates` | GET | **LIVE** 2026-09-15 | 200 | No | No |
| `/campaigns/{id}/create-schedule-from-template` | POST | **DOCS** | not probed | No | No |

**Evidence: LIVE** — 200, empty list (0 templates), offset paginated.

**Not implemented in Resonate OS.**

---

### 14. ENDPOINTS THAT DO NOT EXIST (404)

All confirmed **LIVE** on 2026-09-15:

| Path | Status | Notes |
|---|---|---|
| `/conversations` | 404 | |
| `/threads` | 404 | |
| `/messages` | 404 | |
| `/webhooks` | 404 | |
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
| `/workspaces/current` | 404 | |
| `/me` | 404 | |
| `/user` | 404 | |
| `/account` | 404 | |
| `/whoami` | 404 | |

---

## SUMMARY: WHAT IS ESTABLISHED VS WHAT IS GUESSED

### Fully established (LIVE evidence, shape confirmed)

1. `GET /users` — workspace binding
2. `GET /workspaces` — workspace listing (1 workspace)
3. `GET /workspaces/{id}` — single workspace
4. `GET /campaigns` — campaign listing
5. `GET /campaigns/{id}` — single campaign
6. `GET /campaigns/{id}/sequence-steps` — step listing
7. `GET /campaigns/{id}/leads` — membership listing
8. `GET /campaigns/{id}/sender-emails` — campaign senders
9. `GET /campaigns/{id}/scheduled-emails` — send history (with lead field)
10. `GET /scheduled-emails/{id}` — single scheduled email (**without** lead field)
11. `GET /replies` — reply feed (cursor)
12. `GET /replies/{id}` — single reply
13. `GET /sender-emails` — sender listing
14. `GET /custom-variables` — variable listing
15. `GET /tags` — tag listing
16. `GET /events` — event log (cursor, 10-day history)
17. `GET /lead-lists` — bulk upload listing
18. `GET /leads/{id}/replies` — per-lead replies
19. `GET /leads/{id}/sent-emails` — per-lead send history (with lead field)
20. `GET /campaigns/schedule/templates` — schedule templates (empty)
21. 19 routes confirmed as 404

### Established in code only (CODE evidence, not re-probed live)

22. `POST /campaigns` — create campaign (draft)
23. `POST /campaigns/{id}/update` — set limits
24. `POST /campaigns/{id}/schedule` — create schedule
25. `PUT /campaigns/{id}/schedule` — update schedule
26. `POST /campaigns/{id}/sequence-steps` — append steps
27. `PATCH /campaigns/{id}/resume` — start sending
28. `PATCH /campaigns/{id}/pause` — stop campaign
29. `POST /campaigns/{id}/leads/attach-leads` — add leads
30. `POST /campaigns/{id}/leads/stop-future-emails` — stop one person
31. `POST /campaigns/{id}/attach-sender-emails` — bind inboxes
32. `POST /leads` — create lead
33. `PATCH /leads/{id}` — update lead
34. `POST /custom-variables` — declare variable

### Documentation only (DOCS evidence, not probed, not in code)

35. `DELETE /campaigns/{id}` — delete campaign
36. `POST /campaigns/{id}/leads/attach-lead-list` — add leads from list
37. `DELETE /campaigns/{id}/remove-sender-emails` — remove inboxes
38. `POST /campaigns/{id}/create-schedule-from-template` — apply template
39. `DELETE /leads/{id}` — delete lead
40. `POST /leads/bulk/csv` — bulk CSV upload
41. `POST /tags` — create tag
42. `POST /tags/attach-to-leads` — tag leads
43. `POST /tags/attach-to-campaigns` — tag campaigns
44. `POST /tags/attach-to-sender-emails` — tag senders
45. `DELETE /tags/attach-to-leads` — untag leads
46. `DELETE /tags/attach-to-campaigns` — untag campaigns
47. `DELETE /tags/attach-to-sender-emails` — untag senders
48. `POST /replies/{id}/reply` — send a reply
49. `POST /replies/{id}/attach-email-to-reply` — link untracked reply
50. `POST /webhook-events/test-event` — fire test webhook

### GUESSED

**None.** Every route the codebase references has at least DOCS evidence.
No route is inferred from naming patterns alone.

---

## WHAT A LEAD-ADD WOULD NEED

A lead-add to a campaign requires this chain, all of which is established:

1. **Create the lead** — `POST /leads` with email, first_name,
   custom_variables. CODE evidence. Returns the stored lead row with id.

2. **Attach the lead to the campaign** — `POST /campaigns/{id}/leads/attach-leads`
   with `{"lead_ids": [...]}`. CODE evidence. All-or-nothing: one held person
   in a batch attaches nobody.

3. **Pre-conditions that must be true:**
   - The lead must NOT be `in_sequence` in any other campaign (the provider
     refuses with "no leads were added").
   - The lead must NOT have previously bounced or unsubscribed (same refusal).
   - The campaign must exist and not be `completed` or `archived`.
   - Custom variable names must be declared first via `POST /custom-variables`
     if they don't already exist.

4. **What is NOT needed but might be assumed:**
   - No `workspace_id` parameter (it is ignored).
   - No separate "add to sequence" step — attaching is enough.
   - The lead's `status` field on creation is `unverified`; the provider does
     not require verification before attach.

5. **What is still a gap:**
   - `POST /campaigns/{id}/leads/attach-lead-list` (DOCS only) could add
     leads from a pre-uploaded list, but its shape is not confirmed.
   - `POST /leads/bulk/csv` (DOCS only) could create many leads at once,
     but its shape is not confirmed.
   - The per-lead rate of attach failures is unknown — the provider refuses
     the entire batch on one collision, so a 200-lead batch with 1 held
     person attaches 0 and names none.

---

## CORRECTIONS TO THE EARLIER CAPABILITY MAP

The 2026-09-14 capability map contained these inaccuracies, now corrected:

1. **`GET /scheduled-emails/{id}` does NOT carry a `lead` field.** The
   earlier map listed it. The listing form (`/campaigns/{id}/scheduled-emails`)
   DOES carry it. This is a real asymmetry.

2. **Lead 146592 no longer exists** (404). The earlier map used it for
   examples. It has been removed from the estate.

3. **`/workspaces` returns 1 workspace, not 13.** The bison.py comment from
   2026-09-07 said "thirteen workspaces." On 2026-09-15, only PRODUCTIVE
   (id 10) remains.

4. **`/leads/{id}/replies` and `/leads/{id}/sent-emails` are LIVE-confirmed**,
   not just documented. The earlier map listed them from documentation.

5. **`/campaigns/{id}/leads?search=` is NOT a real filter.** It is accepted
   and discarded, returning the full unfiltered listing. This is different
   from `/leads?search=` which IS a real filter.

6. **Campaign 481 now has 5 sequence steps.** The earlier map described it
   as having no sends and all `thread_reply=False`. It now has a sequence.

---

## PAGINATION SUMMARY (re-confirmed 2026-09-15)

| Route | Type | Per page | Notes |
|---|---|---|---|
| `/campaigns` | offset | 15 (ignored) | per_page accepted but ignored |
| `/campaigns/{id}/leads` | offset | 15 (ignored) | per_page AND search ignored |
| `/campaigns/{id}/scheduled-emails` | offset | 15 (ignored) | per_page ignored |
| `/campaigns/{id}/sender-emails` | offset | 15 (ignored) | per_page ignored |
| `/leads` | offset | 15 (ignored) | per_page ignored |
| `/leads/{id}/replies` | offset | 15 | standard pagination |
| `/leads/{id}/sent-emails` | offset | 15 | standard pagination |
| `/sender-emails` | offset | 15 | per_page works here |
| `/custom-variables` | offset | 15 (ignored) | |
| `/tags` | offset | 15 | all 31 in one page |
| `/lead-lists` | offset | 15 | all 15 in one page |
| `/campaigns/schedule/templates` | offset | 15 | empty |
| `/replies` | cursor | 15 (ignored) | `pagination_type=cursor` required |
| `/events` | cursor | 15 (ignored) | 10-day history |

**Critical:** `per_page` is ignored on almost every route. Always 15 rows
per page regardless of what you ask for.

---

## SCRIPTS

The probe scripts are at:
- `scripts/task111_probe_routes.py` — main route inventory probe
- `scripts/task111_probe_routes2.py` — follow-up probes (lead existence, events shape)
- `scripts/task111_probe_routes3.py` — per-lead routes, individual reply, search trap

All are GET-only. No write was made.
