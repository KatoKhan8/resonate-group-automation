# Grok provider research

2026-09-18T06:58:48.483064+00:00. One call per question, web_search enabled.

**CLASSIFY BEFORE BELIEVING.** Every claim below is the model's, and a confident answer is not a documented one. A point is
DOCUMENTED only where a source URL states it, OBSERVED only where this estate's own provider responses show it, and
HYPOTHESIS or UNKNOWN otherwise. Nothing here is provider truth until a readback against our own estate agrees with it.

---

## bulk

`grok-4.6`, Nones, 55 search URLs, usage {'prompt_tokens': 420528, 'completion_tokens': 5497, 'total_tokens': 426025, 'cached_tokens': 324480, 'reasoning_tokens': 2443, 'cost_in_usd_ticks': 9246360000, 'num_sources_used': 0, 'num_server_side_tools_used': 30}.

**Sources used:** [docs.emailbison.com](https://docs.emailbison.com/llms.txt), [API OpenAPI spec](https://dedi.emailbison.com/api/reference.openapi), [interactive API reference](https://dedi.emailbison.com/api/reference), [pagination](https://docs.emailbison.com/get-started/pagination), [creating leads](https://docs.emailbison.com/leads/creating-a-lead), [leads overview](https://docs.emailbison.com/leads/overview), [attach leads](https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign), [attach senders](https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails), [adding sender emails](https://docs.emailbison.com/email-accounts/adding-accounts), [developers](https://emailbison.com/developers), [unlimited leads](https://emailbison.com/features/unlimited-leads-storage).

---

### 1. Endpoints that accept bulk input

**Creating many leads**
- `POST /api/leads/multiple` — body field `leads` (array of lead objects). Required per item: `first_name`, `email`. Optional: `last_name`, `title`, `company`, `notes`, `custom_variables`. Description: “Create multiple lead records in a single request (limit 500 per request)”. Personal domains skipped unless enabled. https://dedi.emailbison.com/api/reference.openapi
- `POST /api/leads/bulk/csv` — `multipart/form-data`; required `name`, `csv` (file), `columnsToMap`. Optional `existing_lead_behavior`: `put` | `patch` | `skip` (default `put`). Guides: https://docs.emailbison.com/leads/creating-a-lead and https://dedi.emailbison.com/api/reference.openapi
- Single-lead create is `POST /api/leads` (not bulk). https://docs.emailbison.com/leads/creating-a-lead

**Attaching many leads to a campaign**
- `POST /api/campaigns/{campaign_id}/leads/attach-leads` — required `lead_ids` (array of integers). Optional `allow_parallel_sending` (boolean): “Force add leads that are ‘In Sequence’ in other campaigns.” Active-campaign adds are cached and synced every 5 minutes. https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign https://dedi.emailbison.com/api/reference.openapi
- `POST /api/campaigns/{campaign_id}/leads/attach-lead-list` — required `lead_list_id` (integer). Attaches a whole list, not an ID array. https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign

Related (not “attach”, but array of lead IDs): `POST /api/campaigns/{campaign_id}/leads/stop-future-emails` (`lead_ids`); `POST /api/campaigns/{campaign_id}/leads/move-to-another-campaign` (`lead_ids`, `target_campaign_id`). https://dedi.emailbison.com/api/reference.openapi

**Updating many leads**
- `POST /api/leads/create-or-update/multiple` — `leads` array; optional `existing_lead_behavior` `put` | `patch` (default `put`). “Update or create multiple lead records in a single request (limit 500 per request).” https://dedi.emailbison.com/api/reference.openapi
- `PATCH /api/leads/bulk-update-status` — required `lead_ids` (array), `status` enum: `verified`, `unverified`, `unknown`, `unsubscribed`, `risky`, `inactive`. https://dedi.emailbison.com/api/reference.openapi
- CSV re-upload updates in place if email is unchanged. https://docs.emailbison.com/leads/overview Also via `POST /api/leads/bulk/csv` `existing_lead_behavior`.
- There is no documented JSON endpoint that PATCHes arbitrary fields on many lead IDs in one call (only status bulk, create-or-update-by-email, or CSV).

**Adding many senders**
- `POST /api/sender-emails/bulk` — “Add multiple sender email addresses at once.” `multipart/form-data`, required field `csv` (binary). Guides also mention `/api/sender-emails/imap-smtp` for custom SMTP CSV; the OpenAPI bulk path is `/api/sender-emails/bulk`. https://docs.emailbison.com/email-accounts/adding-accounts https://dedi.emailbison.com/api/reference.openapi
- Attach existing senders to a campaign: `POST /api/campaigns/{campaign_id}/attach-sender-emails` — required `sender_email_ids` (array). Remove: `DELETE /api/campaigns/{campaign_id}/remove-sender-emails` with `sender_email_ids`. https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails
- Bulk update existing senders (not create): `PATCH /api/sender-emails/signatures/bulk` (`sender_email_ids`, `email_signature`); `PATCH /api/sender-emails/daily-limits/bulk` (`sender_email_ids`, `daily_limit`); `POST /api/sender-emails/move-to-another-workspace-bulk` (`workspace_id`, `sender_email_ids`). https://dedi.emailbison.com/api/reference.openapi
- Google bulk upload: “currently not first-party supported”. Microsoft: desktop bulk uploader tool, not this REST bulk CSV. https://docs.emailbison.com/email-accounts/adding-accounts

Other documented bulk endpoints (outside the four questions): `DELETE /api/leads/bulk` (`lead_ids`); `DELETE /api/campaigns/bulk` (`campaign_ids`); `POST /api/blacklisted-emails/bulk` and `POST /api/blacklisted-domains/bulk` (CSV); `POST /api/tags/attach-to-leads` (`tag_ids` + `lead_ids`). https://dedi.emailbison.com/api/reference.openapi https://docs.emailbison.com/tags/attaching-tags

---

### 2. Documented per-request limits (max items, page sizes)

| Limit | What docs say |
|---|---|
| JSON bulk create leads | **500 per request** on `POST /api/leads/multiple`. https://dedi.emailbison.com/api/reference.openapi |
| JSON create-or-update leads | **500 per request** on `POST /api/leads/create-or-update/multiple`. https://dedi.emailbison.com/api/reference.openapi |
| CSV lead import | **50,000 leads per CSV**. https://docs.emailbison.com/leads/creating-a-lead Campaigns also “limited to 50,000 leads at once”. https://docs.emailbison.com/leads/overview Same 50k CSV figure on https://emailbison.com/features/unlimited-leads-storage |
| List pagination | **15 entries per page**. Query `page={n}`; optional `pagination_type=cursor` with `cursor`. Cursor `meta.per_page` example is 15. Docs do not document a client-settable `per_page`. https://docs.emailbison.com/get-started/pagination |
| `lead_ids` / `sender_email_ids` array size on attach, remove, status, delete, signatures, daily-limits | **NOT DOCUMENTED** (arrays are required; no maxItems in the spec). https://dedi.emailbison.com/api/reference.openapi |
| Sender CSV (`POST /api/sender-emails/bulk`) max rows | **NOT DOCUMENTED** |
| Blacklist bulk CSV max rows | **NOT DOCUMENTED** |
| Attach-lead-list size | **NOT DOCUMENTED** beyond the campaign 50,000-lead cap. https://docs.emailbison.com/leads/overview |

---

### 3. Rate limits and what is returned when hit

**Numeric global API rate limit:** not stated in the OpenAPI spec or docs.emailbison.com guides.

Documented fragments:
- Developers page: “Standard limits apply per key. Handle 429 and retry after the window indicated by headers.” HTTP **429 Too Many Requests**. Example body: `{"error": "rate_limited", "retry_after": 8}`. https://emailbison.com/developers
- Feature page (uploads, not general API): “Up to 3000 requests per minute via API uploads”. https://emailbison.com/features/unlimited-leads-storage
- OAuth only: `POST /api/oauth-sessions/microsoft` and `POST /api/oauth-sessions/google` each “has a limit of 60 requests per minute.” What is returned if that OAuth limit is hit: **NOT DOCUMENTED** (only the 60/min note). https://dedi.emailbison.com/api/reference.openapi

Exact numeric limit for ordinary REST calls, whether 3000 rpm is global vs upload-only, and whether `retry_after` is seconds vs the header name: **NOT DOCUMENTED** beyond the 429 example and “headers” note above.

Sources the model searched:

- https://docs.emailbison.com/get-started/authentication
- https://docs.emailbison.com/get-started/introduction
- https://docs.emailbison.com/get-started/quickstart/making-http-requests
- https://docs.emailbison.com/llms.txt
- https://emailbison.com/developers
- https://docs.emailbison.com/email-accounts/adding-accounts
- https://docs.withampersand.com/provider-guides/emailBison
- https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails
- https://context7.com/websites/dedi_emailbison_api_reference
- https://docs.emailbison.com/leads/overview
- https://emailbison.com/
- https://outboundsync.com/docs/integrations/engagement/emailbison/authentication/connect-your-emailbison-api-key/
- https://github.com/bcharleson/emailbison-cli
- https://docs.sim.ai/triggers/emailbison
- https://www.linkedin.com/company/emailbison
- https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign
- https://emailbison.com/features/unlimited-leads-storage
- https://docs.emailbison.com/leads/overview
- https://emailbison.com/developers
- https://emailbison.com/features/email-sequencing
- https://docs.emailbison.com/llms.txt
- https://emailbison.com/features/master-inbox
- https://docs.emailbison.com/low-code-tools/clay/enrichments/create-or-update-lead
- https://docs.sim.ai/integrations/emailbison
- https://github.com/bcharleson/emailbison-cli

