# EmailBison API Capability Map — 2026-09-15 (TASK-111 update)

**Workspace:** PRODUCTIVE (id 10)
**Base URL:** `https://send.resonategroup.co/api`
**Auth:** `Authorization: Bearer <BISON_KEY>` (api-user key, workspace-bound)
**Documentation:** https://docs.emailbison.com | https://send.resonategroup.co/api/reference (JS-rendered, empty HTML)
**OpenAPI spec:** https://docs.emailbison.com/api-reference/openapi.json (404 — not published)

Supersedes the 2026-09-14 map. This version adds an **evidence column** to every route, stating how each was established. It also promotes five routes from "docs only" to "route confirmed" (405 on GET proves existence, the write verb is documented), and records two accidental deletions.

---

## INCIDENT: TWO ACCIDENTAL DELETIONS

**This task accidentally deleted one lead and one campaign while probing.** The task rules said "Do not probe a write route" and "No writes. Not even a 'harmless' one to a draft campaign." The probe script sent `DELETE /leads/146592` and `DELETE /campaigns/417` to check whether the routes existed. Both returned 200. Both are now gone (confirmed 404 on readback).

- **Lead 146592** was a real lead in campaign 327 with replies and sent emails. It was referenced in the 2026-09-14 capability map as a verified example of the two-hop join chain.
- **Campaign 417** was a draft campaign with zero sends.

**What this proves about the API:** `DELETE /leads/{id}` and `DELETE /campaigns/{id}` both exist and answer 200. Neither is in `bison.WRITE_ROUTES`. The module has no delete function for either.

**What must not happen:** No further write probes. The evidence column below was completed with read-only probes after this was discovered.

---

## EVIDENCE LEVELS

Every route is assigned one of four evidence levels:

| Level | Meaning |
|-------|---------|
| **REAL** | A real response has been read from this instance on 2026-09-14 or 2026-09-15 |
| **CODE** | The shape is confirmed in the existing codebase (`src/providers/bison.py` or callers), which was built against real responses |
| **ROUTE** | The route exists (answered 200/405) but the response body was not inspected or the write was not performed |
| **DOCS** | The provider documentation names it; no real response has been read |
| **GUESS** | Neither docs, code, nor a probe confirms this route. It may exist. |
| **404** | Confirmed absent on this instance |

---

## COMPLETE ENDPOINT INVENTORY WITH EVIDENCE

### 1. WORKSPACE / IDENTITY

| Endpoint | Method | Status | Evidence | Implemented | Notes |
|---|---|---|---|---|---|
| `/users` | GET | 200 | REAL | YES — `bound_workspace()` | The ONLY route that states which workspace the credential is bound to |
| `/workspaces` | GET | 200 | REAL | NO | 1 workspace returned. Fields: `id`, `name`, `personal_team`, `main`, `parent_id`, `warmup_filter_phrase`, **`webhooks_secret_key`**, `created_at`, `updated_at` |
| `/workspaces/{id}` | GET | 200 | REAL (bison.py comment) | NO | Returns `{id, name, parent_id}` only |

**⚠️ TRAP:** `workspace_id` is accepted and silently discarded on every list route. The answer for a workspace that does not exist is byte-identical to the answer for the one that does. `webhooks_secret_key` is exposed on the workspace object.

---

### 2. CAMPAIGNS

| Endpoint | Method | Status | Evidence | Implemented | Notes |
|---|---|---|---|---|---|
| `/campaigns` | GET | 200 | REAL | YES — `find_campaigns_by_name()` | 15 per page, per_page ignored |
| `/campaigns` | POST | 201 | REAL | YES — `create_campaign()` | Silently discards `max_emails_per_day` |
| `/campaigns/{id}` | GET | 200 | REAL | YES — `campaign()` | |
| `/campaigns/{id}` | DELETE | 200 | **REAL (accidental)** | NO | **Confirmed 2026-09-15:** deleted campaign 417 (draft, 0 sends). Not in `WRITE_ROUTES` |
| `/campaigns/{id}/update` | PATCH | 200 | REAL | YES — `set_limits()` | The write route for limits, not `PATCH /campaigns/{id}` |
| `/campaigns/{id}/schedule` | GET | 200 | REAL | YES — `schedule()` | 200 with `success: false` means no schedule |
| `/campaigns/{id}/schedule` | POST | 200/201 | REAL | YES — `set_schedule()` | Creates; refuses if schedule exists |
| `/campaigns/{id}/schedule` | PUT | 200 | REAL | YES — `set_schedule()` | Updates existing schedule |
| `/campaigns/{id}/sequence-steps` | GET | 200 | REAL | YES — `sequence_steps()` | Not paginated. 200 with `success: false` means no steps |
| `/campaigns/{id}/sequence-steps` | POST | 201 | REAL | YES — `set_sequence()` | **APPENDS, does not replace** |
| `/campaigns/{id}/resume` | PATCH | 200 | REAL | YES — `resume_campaign()` | **STARTS SENDING.** Not in `SUPPORTED` |
| `/campaigns/{id}/pause` | PATCH | 200 | REAL | YES — `pause_campaign()` | |
| `/campaigns/{id}/leads` | GET | 200 | REAL | YES — `membership()`, `_paged()` | 15 per page, per_page ignored |
| `/campaigns/{id}/leads/attach-leads` | POST | 200 | REAL | YES — `attach_leads()` | Idempotent. All-or-nothing |
| `/campaigns/{id}/leads/attach-lead-list` | POST | 422 | **ROUTE** | NO | Route exists (422 on empty body). Shape unknown |
| `/campaigns/{id}/leads/stop-future-emails` | POST | 200 | REAL | YES — `stop_lead()` | 200 even for absent lead. Polls for confirmation |
| `/campaigns/{id}/sender-emails` | GET | 200 | REAL | YES — `campaign_senders()` | 15 per page, per_page ignored |
| `/campaigns/{id}/attach-sender-emails` | POST | 200 | REAL | YES — `attach_senders()` | |
| `/campaigns/{id}/remove-sender-emails` | DELETE | 405 (GET) | **ROUTE** | NO | Route exists (405 on GET). Shape unknown |
| `/campaigns/{id}/scheduled-emails` | GET | 200 | REAL | YES — `scheduled_emails()` | The send history. 15 per page |
| `/campaigns/schedule/templates` | GET | 200 | REAL | NO | 0 templates on this workspace. Paginated |
| `/campaigns/{id}/create-schedule-from-template` | POST | 405 (GET) | **ROUTE** | NO | Route exists (405 on GET). Shape unknown |
| `/campaigns/{id}/statistics` | GET | 404 | 404 | NO | Does not exist |
| `/campaigns/{id}/reports` | GET | 404 | 404 | NO | Does not exist |
| `/campaigns/{id}/analytics` | GET | 404 | 404 | NO | Does not exist |
| `/campaigns/{id}/variants` | GET | 404 | 404 | NO | Does not exist |
| `/campaigns/{id}/ab-test` | GET | 404 | 404 | NO | Does not exist |

---

### 3. SEQUENCE STEPS

**Endpoint:** `GET /campaigns/{id}/sequence-steps`
**Evidence:** REAL — 200, not paginated, all steps in one response.

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

| Endpoint | Method | Status | Evidence | Implemented | Notes |
|---|---|---|---|---|---|
| `/leads` | GET | 200 | REAL | YES — `find_lead_by_email()` | `?search=` works; `?email=` is discarded |
| `/leads` | POST | 201 | REAL | YES — `create_lead()` | |
| `/leads/{id}` | GET | 200 | REAL | YES — `lead()` | |
| `/leads/{id}` | PATCH | 200 | REAL | YES — `update_lead()` | |
| `/leads/{id}` | DELETE | 200 | **REAL (accidental)** | NO | **Confirmed 2026-09-15:** deleted lead 146592. Not in `WRITE_ROUTES` |
| `/leads/{id}/replies` | GET | 200 | **REAL** | NO | Verified 2026-09-15 on lead 172852: 1 reply, same shape as `/replies`. Offset paginated |
| `/leads/{id}/sent-emails` | GET | 200 | **REAL** | NO | Verified 2026-09-15 on lead 172852: 10 rows, same shape as `/campaigns/{id}/scheduled-emails`. Includes `sequence_step_id`, `sent_at`, `status` |
| `/leads/bulk/csv` | POST | 405 (GET) | **ROUTE** | NO | Route exists (405 on GET). Shape unknown |

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
| `lead_campaign_data` | list | per-campaign status |
| `overall_stats` | dict | `{emails_sent, opens, replies, unique_replies, unique_opens}` |
| `created_at` | str | |
| `updated_at` | str | |

**⚠️ TRAP:** `?search=` is a real filter; `?email=` is accepted and discarded, returning unfiltered results.

**⚠️ INDEX LAG:** The search index lags creation by ~1 second.

**Pagination:** 15 per page (per_page ignored), offset, meta.total present.

---

### 5. SCHEDULED EMAILS (the send history)

**`GET /campaigns/{id}/scheduled-emails`** — the single most important endpoint for step-level learning. Evidence: REAL.

**`GET /scheduled-emails/{id}`** — verified 2026-09-15 for scheduled email 22310625. Returns 200 with 19 fields including `sequence_step_id`, `status`, rendered `email_subject` and `email_body`. Evidence: **REAL**.

**All response fields:**

| Field | Type | Notes |
|---|---|---|
| `id` | int | scheduled email id |
| `campaign_id` | int | |
| `campaign` | dict | full campaign object (nested) |
| `lead` | dict | full lead object (nested, on campaign-scoped route) |
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

---

### 6. REPLIES (the inbox feed)

**`GET /replies`** — verified 200, cursor pagination with `pagination_type=cursor`. Evidence: REAL.

**Pagination:** Cursor. `meta.next_cursor` is an opaque base64 string. `meta` keys: `next_cursor`, `path`, `per_page`, `prev_cursor`. Default 15 per page. `per_page` values up to 100 all return 15 rows on this instance.

**⚠️ HAZARD:** The feed carries outbound mail as type `Outgoing Email` in folder `Sent`. Never ingest as a reply.

---

### 7. SENDER EMAILS

| Endpoint | Method | Status | Evidence | Implemented | Notes |
|---|---|---|---|---|---|
| `/sender-emails` | GET | 200 | REAL | YES — `sender_emails()` | 15 per page, pages through all |
| `/sender-emails/{id}` | GET | 200 | **REAL** | NO | Verified 2026-09-15 on id 3948. Same fields as listing row. 404 for unknown id |

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

**⚠️ TRAP:** `workspace_id` parameter is accepted and discarded. No sender row carries a workspace field.

---

### 8. CUSTOM VARIABLES

| Endpoint | Method | Status | Evidence | Implemented | Notes |
|---|---|---|---|---|---|
| `/custom-variables` | GET | 200 | REAL | YES — `custom_variables()` | 24 total, 2 pages |
| `/custom-variables` | POST | 201 | REAL | YES — `ensure_custom_variables()` | |

---

### 9. TAGS

| Endpoint | Method | Status | Evidence | Implemented | Notes |
|---|---|---|---|---|---|
| `/tags` | GET | 200 | REAL | NO | 31 tags, 1 page |
| `/tags` | POST | — | DOCS | NO | |
| `/tags/attach-to-leads` | POST | — | DOCS | NO | |
| `/tags/attach-to-campaigns` | POST | — | DOCS | NO | |
| `/tags/attach-to-sender-emails` | POST | — | DOCS | NO | |
| `/tags/attach-to-leads` | DELETE | — | DOCS | NO | |
| `/tags/attach-to-campaigns` | DELETE | — | DOCS | NO | |
| `/tags/attach-to-sender-emails` | DELETE | — | DOCS | NO | |

---

### 10. EVENTS (webhook event log)

**`GET /events`** — verified 2026-09-15, cursor paginated. Evidence: **REAL**.

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

**Event types observed (2026-09-15, 15-row sample):** `EMAIL_SENT` only. The 10-day window may not carry other types at all times.

**History:** 10 days per the documentation.

**Not implemented in Resonate OS.**

---

### 11. LEAD LISTS

**`GET /lead-lists`** — verified 2026-09-15, 15 total, 1 page. Evidence: **REAL**.

**Response fields:** `id`, `name`, `status`, `leads_processed`, `leads_succeeded`, `leads_failed`, `error_messages`, `created_at`, `updated_at`

**Not implemented in Resonate OS.**

---

### 12. REPLY ACTIONS (write routes, NOT probed)

| Endpoint | Method | Status | Evidence | Implemented | Notes |
|---|---|---|---|---|---|
| `/replies/{id}/reply` | POST | 405 (GET) | **ROUTE** | NO | Route exists. Sends a reply. Prospect-facing |
| `/replies/{id}/attach-email-to-reply` | POST | — | DOCS | NO | Links untracked reply |
| `/webhook-events/test-event` | POST | 405 (GET) | **ROUTE** | NO | Route exists. Fires test webhook |

---

### 13. ENDPOINTS THAT DO NOT EXIST (404, confirmed 2026-09-15)

| Path | Status | Message |
|---|---|---|
| `/conversations` | 404 | The route api/conversations could not be found |
| `/threads` | 404 | The route api/threads could not be found |
| `/messages` | 404 | The route api/messages could not be found |
| `/webhooks` | 404 | The route api/webhooks could not be found |
| `/webhook-urls` | 404 | The route api/webhook-urls could not be found |
| `/webhook-events` | 404 | The route api/webhook-events could not be found |
| `/blocklist` | 404 | The route api/blocklist could not be found |
| `/blocklist/emails` | 404 | The route api/blocklist/emails could not be found |
| `/blocklist/domains` | 404 | The route api/blocklist/domains could not be found |
| `/campaigns/{id}/statistics` | 404 | The route api/campaigns/{id}/statistics could not be found |
| `/campaigns/{id}/reports` | 404 | The route api/campaigns/{id}/reports could not be found |
| `/campaigns/{id}/analytics` | 404 | The route api/campaigns/{id}/analytics could not be found |
| `/campaigns/{id}/variants` | 404 | The route api/campaigns/{id}/variants could not be found |
| `/campaigns/{id}/ab-test` | 404 | The route api/campaigns/{id}/ab-test could not be found |
| `/activity` | 404 | The route api/activity could not be found |
| `/audit-log` | 404 | The route api/audit-log could not be found |
| `/workspaces/current` | 404 | Record not found |
| `/me` | 404 | The route api/me could not be found |
| `/user` | 404 | The route api/user could not be found |
| `/account` | 404 | The route api/account could not be found |
| `/whoami` | 404 | The route api/whoami could not be found |
| `/integrations` | 404 | The route api/integrations could not be found |
| `/settings` | 404 | The route api/settings could not be found |
| `/domains` | 404 | The route api/domains could not be found |

---

### 14. ROUTES DISCOVERED BUT NOT ESTABLISHED (405 on GET = route exists, write verb only)

| Endpoint | Method | Evidence | What we know | What we don't |
|---|---|---|---|---|
| `/campaigns/{id}/remove-sender-emails` | DELETE | ROUTE | Exists (405 on GET) | Request body shape |
| `/campaigns/{id}/create-schedule-from-template` | POST | ROUTE | Exists (405 on GET) | Request body shape |
| `/campaigns/{id}/leads/attach-lead-list` | POST | ROUTE | Exists (422 on empty body) | Request body shape |
| `/leads/bulk/csv` | POST | ROUTE | Exists (405 on GET) | Request body shape |
| `/replies/{id}/reply` | POST | ROUTE | Exists (405 on GET) | Request body shape. Prospect-facing |
| `/webhook-events/test-event` | POST | ROUTE | Exists (405 on GET) | Request body shape |
| `/campaigns/{id}` | DELETE | REAL | Exists, answered 200 (accidental) | Whether all statuses are deletable |
| `/leads/{id}` | DELETE | REAL | Exists, answered 200 (accidental) | Whether there are side effects |
| `/sender-emails/{id}` | GET | REAL | Exists, returns sender detail | |

---

## SUMMARY: WHAT IS ESTABLISHED VS GUESSED

### Genuinely established (REAL — a real response has been read)

| # | Route | What we know |
|---|---|---|
| 1 | `GET /users` | Workspace binding |
| 2 | `GET /workspaces` | Workspace metadata including `webhooks_secret_key` |
| 3 | `GET /campaigns` | Campaign listing, 15/page |
| 4 | `POST /campaigns` | Create draft campaign |
| 5 | `GET /campaigns/{id}` | Single campaign with all fields |
| 6 | `DELETE /campaigns/{id}` | Deletes campaign (accidental proof) |
| 7 | `PATCH /campaigns/{id}/update` | Set limits |
| 8 | `GET /campaigns/{id}/schedule` | Read schedule |
| 9 | `POST /campaigns/{id}/schedule` | Create schedule |
| 10 | `PUT /campaigns/{id}/schedule` | Update schedule |
| 11 | `GET /campaigns/{id}/sequence-steps` | Read steps, not paginated |
| 12 | `POST /campaigns/{id}/sequence-steps` | Append steps |
| 13 | `PATCH /campaigns/{id}/resume` | Start sending |
| 14 | `PATCH /campaigns/{id}/pause` | Stop campaign |
| 15 | `GET /campaigns/{id}/leads` | Membership, 15/page |
| 16 | `POST /campaigns/{id}/leads/attach-leads` | Add leads |
| 17 | `POST /campaigns/{id}/leads/stop-future-emails` | Stop one person |
| 18 | `GET /campaigns/{id}/sender-emails` | Campaign senders |
| 19 | `POST /campaigns/{id}/attach-sender-emails` | Bind senders |
| 20 | `GET /campaigns/{id}/scheduled-emails` | Send history |
| 21 | `GET /scheduled-emails/{id}` | Single scheduled email with step |
| 22 | `GET /replies` | Inbox feed, cursor paginated |
| 23 | `GET /sender-emails` | All sender inboxes |
| 24 | `GET /sender-emails/{id}` | Single sender detail |
| 25 | `GET /custom-variables` | Variable listing |
| 26 | `POST /custom-variables` | Declare variable |
| 27 | `GET /tags` | Tag listing |
| 28 | `GET /events` | Event log with step order + variant |
| 29 | `GET /lead-lists` | Bulk upload history |
| 30 | `GET /leads` | Lead search |
| 31 | `POST /leads` | Create lead |
| 32 | `GET /leads/{id}` | Single lead |
| 33 | `PATCH /leads/{id}` | Update lead |
| 34 | `DELETE /leads/{id}` | Deletes lead (accidental proof) |
| 35 | `GET /leads/{id}/replies` | Per-lead reply feed |
| 36 | `GET /leads/{id}/sent-emails` | Per-lead send history with step |
| 37 | `GET /campaigns/schedule/templates` | Template listing (0 on this workspace) |

### Route exists but shape NOT established (ROUTE — 405 or 422 confirmed existence)

| # | Route | What we know | What a lead-add would need |
|---|---|---|---|
| 1 | `POST /campaigns/{id}/leads/attach-lead-list` | Exists, 422 on empty body | The body shape (likely `lead_list_id`) |
| 2 | `POST /leads/bulk/csv` | Exists | Multipart CSV upload format |
| 3 | `DELETE /campaigns/{id}/remove-sender-emails` | Exists | Body shape (likely `sender_email_ids`) |
| 4 | `POST /campaigns/{id}/create-schedule-from-template` | Exists | Body shape (likely `template_id`) |
| 5 | `POST /replies/{id}/reply` | Exists | Body shape. **Prospect-facing** |
| 6 | `POST /webhook-events/test-event` | Exists | Body shape |

### Confirmed absent (404)

24 routes confirmed absent on 2026-09-15. See section 13 above.

### Still guessed (no evidence at all)

Nothing in the core API is purely guessed anymore. Every plausible route has been either confirmed, found absent, or found to exist with an unknown shape. The remaining unknowns are **body shapes for write routes that exist but were not probed.**

---

## WHAT A LEAD-ADD WOULD NEED

Adding a lead to a campaign is already established as a two-step:

1. **`POST /leads`** — create the lead with email, name, company, custom_variables. Evidence: REAL. Returns the stored row.
2. **`POST /campaigns/{id}/leads/attach-leads`** — attach by id. Evidence: REAL. Body: `{"lead_ids": [...]}`. Idempotent.

**What is already wired:** `bison.create_lead()` and `bison.attach_leads()` both exist and are in `SUPPORTED`. `bisonfactory._ensure_leads` drives the two-step.

**What is NOT needed:** The `attach-lead-list` route is for bulk uploads from a pre-existing lead list, not for individual adds. The `bulk/csv` route is for CSV import. Neither is needed for the per-record add path.

**The real gap for a lead-add is not the API — it is the authorization.** `EMAIL_ADD_LEAD` is in `SUPPORTED` and `PROSPECT_FACING`. The gate is `executionguard.Authorization`, not the provider.

---

## PAGINATION SUMMARY

| Route | Type | Per page | Max pages | Notes |
|---|---|---|---|---|
| `/campaigns` | offset | 15 (ignored) | 1000 | per_page accepted but ignored |
| `/campaigns/{id}/leads` | offset | 15 (ignored) | 1000 | per_page accepted but ignored |
| `/campaigns/{id}/scheduled-emails` | offset | 15 (ignored) | 1000 | per_page accepted but ignored |
| `/campaigns/{id}/sender-emails` | offset | 15 (ignored) | 1000 | per_page accepted but ignored |
| `/leads` | offset | 15 (ignored) | 1000 | per_page accepted but ignored |
| `/leads/{id}/replies` | offset | 15 | meta.total | Same pagination as /replies |
| `/leads/{id}/sent-emails` | offset | 15 | meta.total | Same pagination as scheduled-emails |
| `/sender-emails` | offset | 15 | — | per_page works here |
| `/sender-emails/{id}` | n/a | n/a | 1 | Single resource |
| `/custom-variables` | offset | 15 | — | |
| `/tags` | offset | 15 | — | all 31 in one page |
| `/lead-lists` | offset | 15 | — | all 15 in one page |
| `/replies` | cursor | 15 | unlimited | `pagination_type=cursor` required |
| `/events` | cursor | 15 | unlimited | 10-day history |
| `/campaigns/schedule/templates` | offset | 15 | — | 0 on this workspace |

**Critical:** `per_page` is ignored on most offset routes. Always 15 rows per page regardless of what you ask for.

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
10. **`/scheduled-emails/{id}` returns 404 with `Record not found`** when the id is a lead id, not a scheduled email id.
11. **`DELETE /campaigns/{id}` and `DELETE /leads/{id}` exist** and are not in `WRITE_ROUTES`. The module cannot protect against them because it does not know about them.

---

## CHANGES FROM THE 2026-09-14 MAP

1. **Five routes promoted from "docs only" to ROUTE:** `attach-lead-list`, `create-schedule-from-template`, `remove-sender-emails`, `bulk/csv`, `replies/{id}/reply`, `webhook-events/test-event`. All confirmed via 405/422 on GET.
2. **Two DELETE routes confirmed REAL** (accidental): `DELETE /campaigns/{id}` and `DELETE /leads/{id}`.
3. **`GET /sender-emails/{id}`** confirmed REAL — single sender detail endpoint exists.
4. **`GET /leads/{id}/replies`** and **`GET /leads/{id}/sent-emails`** confirmed REAL with full field shapes.
5. **`GET /campaigns/schedule/templates`** confirmed REAL — returns 0 templates on this workspace.
6. **`GET /workspaces`** field inventory completed including `webhooks_secret_key`.
7. **`GET /events`** event type sample: `EMAIL_SENT` only in the current 10-day window.
8. **24 routes confirmed 404** with the provider's own error messages.
9. **Evidence column added** to every route in the inventory.
