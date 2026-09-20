# Grok provider research

2026-09-20T15:41:32.015395+00:00. One call per question, web_search enabled.

**CLASSIFY BEFORE BELIEVING.** Every claim below is the model's, and a confident answer is not a documented one. A point is
DOCUMENTED only where a source URL states it, OBSERVED only where this estate's own provider responses show it, and
HYPOTHESIS or UNKNOWN otherwise. Nothing here is provider truth until a readback against our own estate agrees with it.

---

## heyreach_sender

`grok-4.6`, Nones, 120 search URLs, usage {'prompt_tokens': 521359, 'completion_tokens': 4390, 'total_tokens': 525749, 'cached_tokens': 416000, 'reasoning_tokens': 3097, 'cost_in_usd_ticks': 10551160000, 'num_sources_used': 0, 'num_server_side_tools_used': 33}.

The official Postman collection and campaign API blog look like the primary sources. I'll open those next and pull the exact field names.
Postman rendered poorly. I’ll pull the rest of the official campaign-api blog and the help-center/API pages next.
Make.com points at official Postman and Notion webhook docs. I’ll open those and search the Postman collection for the three endpoints.
Official docs are at docs.heyreach.io. Fetching the campaign, add-leads, GetById, schedule, and webhook pages now.
GetById has no schedule fields. I’ll confirm GetLeadsFromCampaign, UpdateSchedule, and the OpenAPI spec so we don’t miss a read endpoint.
**1. Sender selection / `accountLeadPairs`**

Default algorithm when a campaign has multiple senders and you do **not** pin one: **NOT DOCUMENTED**.

Yes. `accountLeadPairs` on `POST /api/public/campaign/AddLeadsToCampaignV2` is the documented pin. Docs: if a LinkedIn account ID is specified in `accountLeadPairs`, that lead is mapped to that account in the campaign. Same wording on `AddLeadsToCampaign`. Fields: `campaignId`, `accountLeadPairs[].linkedInAccountId`, `accountLeadPairs[].lead`. The generated schema lists `linkedInAccountId` as required; the prose only describes behaviour when it *is* specified. What happens if it is omitted is **NOT DOCUMENTED**.

Sources the model searched:

- https://documenter.getpostman.com/view/23808049/2sA2xb5F75
- https://www.heyreach.io/blog/linkedin-login-via-api
- https://docs.withampersand.com/provider-guides/heyreach
- https://oxygen-agent.com/integrations/heyreach
- https://docs.jungler.ai/integrations/heyreach
- https://www.heyreach.io/blog/campaign-api
- https://n8n.io/integrations/heyreach-api/
- https://github.com/bcharleson/heyreach-cli
- https://www.postman.com/chad-999/highlevel/collection/5ud7ues/heyreach-api
- https://apps.make.com/heyreach
- https://help.heyreach.io/en/
- https://docs.alysio.ai/integration-guides/heyreach
- https://cotera.co/docs/reference/tools/individual-tools/hey-reach
- https://docs.composio.dev/toolkits/heyreach.md
- https://outboundsync.com/docs/integrations/engagement/heyreach/authentication/connect-your-heyreach-api-key/
- https://cotera.co/docs/reference/tools/individual-tools/hey-reach
- https://oxygen-agent.com/integrations/heyreach
- https://raw.githubusercontent.com/bcharleson/cold-outbound-dream-team/main/src/tools/heyreach/tools.py
- https://pkg.go.dev/github.com/amp-labs/connectors/providers/heyreach
- https://www.heyreach.io/blog/campaign-api
- https://docs.alysio.ai/integration-guides/heyreach
- https://ncnodes.com/package/n8n-nodes-heyreach/heyReach/Campaign:Add%20Leads
- https://docs.getcargo.ai/integration/heyreach
- https://github.com/bcharleson/heyreach-cli/blob/main/AGENTS.md
- https://www.make.com/en/integrations/heyreach/linkedin

## bulk

`grok-4.6`, Nones, 68 search URLs, usage {'prompt_tokens': 647434, 'completion_tokens': 6944, 'total_tokens': 654378, 'cached_tokens': 469888, 'reasoning_tokens': 3198, 'cost_in_usd_ticks': 14434000000, 'num_sources_used': 0, 'num_server_side_tools_used': 36}.

Sources used: [OpenAPI spec](https://dedi.emailbison.com/api/reference.openapi), [interactive API reference](https://dedi.emailbison.com/api/reference), [docs.emailbison.com](https://docs.emailbison.com/), [developers page](https://emailbison.com/developers).

## 1. Endpoints that accept bulk input

### Creating many leads at once

**`POST /api/leads/multiple`** — “Bulk create leads”. Body: required `leads` array of objects (`first_name`, `email` required; optional `last_name`, `title`, `company`, `notes`, `custom_variables`). Documented limit: **500 per request**. Personal domains skipped unless enabled. 201. Spec: https://dedi.emailbison.com/api/reference.openapi (operationId `bulkCreateLeads`).[[1]](https://dedi.emailbison.com/api/reference.openapi)

**`POST /api/leads/bulk/csv`** — “Bulk create leads using CSV”. `multipart/form-data`: required `name`, `csv` (file), `columnsToMap`; optional `existing_lead_behavior` (`put` | `patch` | `skip`, default `put`). 201. Spec + workflow docs: https://dedi.emailbison.com/api/reference.openapi, https://docs.emailbison.com/leads/creating-a-lead.[[1]](https://dedi.emailbison.com/api/reference.openapi)

Single create is **`POST /api/leads`** (one lead), not bulk. https://docs.emailbison.com/leads/creating-a-lead.[[2]](https://docs.emailbison.com/leads/creating-a-lead)

### Attaching many leads to a campaign

**`POST /api/campaigns/{campaign_id}/leads/attach-leads`** — “Import leads by IDs”. Body: required `lead_ids` (array of integers); optional `allow_parallel_sending` (boolean: force-add leads already “In Sequence” in other campaigns). Active-campaign adds are cached locally and synced every 5 minutes. Spec + docs: https://dedi.emailbison.com/api/reference.openapi, https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign.[[1]](https://dedi.emailbison.com/api/reference.openapi)

**`POST /api/campaigns/{campaign_id}/leads/attach-lead-list`** — attach an existing list. Body: required `lead_list_id` (integer). Same docs.[[3]](https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign)

Related array-of-IDs (not attach): `POST .../leads/stop-future-emails` (`lead_ids`); `POST .../leads/move-to-another-campaign` (`lead_ids` + `target_campaign_id`); `DELETE` remove-leads-from-campaign (`lead_ids`). Spec: https://dedi.emailbison.com/api/reference.openapi.[[1]](https://dedi.emailbison.com/api/reference.openapi)

### Updating many leads

**`POST /api/leads/create-or-update/multiple`** — “Update or create multiple leads”. Body: required `leads` array (same shape as bulk create); optional `existing_lead_behavior` (`put` | `patch`, default `put`). **Limit 500 per request**. Spec: https://dedi.emailbison.com/api/reference.openapi.[[1]](https://dedi.emailbison.com/api/reference.openapi)

**`PATCH /api/leads/bulk-update-status`** — status only. Body: required `lead_ids` (integer array), `status` enum: `verified` | `unverified` | `unknown` | `unsubscribed` | `risky` | `inactive`. Same spec.[[1]](https://dedi.emailbison.com/api/reference.openapi)

CSV re-upload also updates existing leads when email is unchanged (`existing_lead_behavior` on `/api/leads/bulk/csv`). Overview: https://docs.emailbison.com/leads/overview.[[4]](https://docs.emailbison.com/leads/overview)

Single-lead update is **`PUT /api/leads/{lead_id}`** / **`POST /api/leads/create-or-update/{lead_id}`**, not bulk. A docs curl showing `PUT /api/leads` (no id) is not an OpenAPI bulk-update path. https://docs.emailbison.com/leads/custom-variables, OpenAPI.[[5]](https://docs.emailbison.com/leads/custom-variables)

### Adding many senders

**`POST /api/sender-emails/bulk`** — “Bulk add sender emails”. `multipart/form-data`, required field `csv` (file). 201. Spec: https://dedi.emailbison.com/api/reference.openapi. Docs page names `/api/sender-emails/imap-smtp` in prose but the curl uses `/api/sender-emails/bulk`. https://docs.emailbison.com/email-accounts/adding-accounts.[[1]](https://dedi.emailbison.com/api/reference.openapi)

**`POST /api/sender-emails/imap-smtp`** is **single** account create (JSON: `name`, `email`, `password`, `imap_server`, `imap_port`, `smtp_server`, `smtp_port`, …), not bulk. Spec: https://dedi.emailbison.com/api/reference.openapi.[[1]](https://dedi.emailbison.com/api/reference.openapi)

Attach many existing senders to a campaign: **`POST /api/campaigns/{campaign_id}/attach-sender-emails`**, body required `sender_email_ids` (array). Remove: **`DELETE /api/campaigns/{campaign_id}/remove-sender-emails`**, same field. https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails, OpenAPI.[[1]](https://dedi.emailbison.com/api/reference.openapi)

Other sender bulk (not “add senders”): `PATCH /api/sender-emails/signatures/bulk` (`sender_email_ids` + `email_signature`); `PATCH /api/sender-emails/daily-limits/bulk` (`sender_email_ids` + `daily_limit`); `POST /api/sender-emails/move-to-another-workspace-bulk` (`workspace_id` + `sender_email_ids`). Spec: https://dedi.emailbison.com/api/reference.openapi.[[1]](https://dedi.emailbison.com/api/reference.openapi)

### Other bulk (for completeness)

- `POST /api/tags/attach-to-leads` (and sender-emails / campaigns): `tag_ids` + `lead_ids` / `sender_email_ids` / `campaign_ids`. https://docs.emailbison.com/tags/attaching-tags.[[6]](https://docs.emailbison.com/tags/attaching-tags)
- `DELETE /api/leads/bulk` — bulk delete by ID. `DELETE /api/campaigns/bulk` — bulk delete campaigns. `POST /api/blacklisted-emails/bulk` and `POST /api/blacklisted-domains/bulk` — CSV. Spec: https://dedi.emailbison.com/api/reference.openapi.[[1]](https://dedi.emailbison.com/api/reference.openapi)

---

## 2. Documented per-request limits (max items, page sizes)

| Limit | What docs actually say | URL |
|---|---|---|
| JSON bulk create/upsert | **500 leads per request** on `POST /api/leads/multiple` and `POST /api/leads/create-or-update/multiple` | https://dedi.emailbison.com/api/reference.openapi |
| CSV lead import | **50,000 leads per CSV**; “There is a 50,000 lead limit per CSV file” | https://docs.emailbison.com/leads/creating-a-lead, https://docs.emailbison.com/leads/overview |
| Campaign size | “CSVs and campaigns are limited to 50,000 leads at once” | https://docs.emailbison.com/leads/overview |
| `attach-leads` / `lead_ids` arrays | Array documented; **max length NOT DOCUMENTED** (examples are `[1,2,3]`) | OpenAPI + https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign |
| `sender_email_ids` arrays (attach/remove/signatures/daily-limits) | Array documented; **max length NOT DOCUMENTED** | OpenAPI + https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails |
| Sender CSV `/api/sender-emails/bulk` | CSV file; **max rows NOT DOCUMENTED** | OpenAPI |
| `bulk-update-status` `lead_ids` | Array; **max length NOT DOCUMENTED** | OpenAPI |
| Page size | Paginated responses are **15 entries per page**. Cursor `meta.per_page` example is **15**. OpenAPI examples use `per_page: 15`. | https://docs.emailbison.com/get-started/pagination, OpenAPI |
| Change page size (`per_page` query) | **NOT DOCUMENTED** as a request parameter. `GET /api/leads` query params in OpenAPI: `search`, `filters.*`, `pagination_type` (`cursor` \| `length_aware`). No `per_page`. | OpenAPI; https://docs.emailbison.com/get-started/pagination |
| Page index | `?page={page_number}`. Length-aware pagination **limited to 1000 pages** on index routes (e.g. `/api/leads`, `/api/replies`). Beyond that, use `pagination_type=cursor` + `cursor`. | https://docs.emailbison.com/get-started/pagination |

---

## 3. Rate limits and 429 response

**Numeric rate in OpenAPI / docs.emailbison.com: NOT DOCUMENTED.** No `429` responses, retry headers, or RPM/RPS appear in https://dedi.emailbison.com/api/reference.openapi or the docs index pages (auth, pagination, quickstart).

What vendor pages *do* say:

- https://emailbison.com/developers — “Standard limits apply per key. Handle 429 and retry after the window indicated by headers.” HTTP **429 Too Many Requests**, example body: `{"error": "rate_limited", "retry_after": 8}`. Units of `retry_after` and which headers: **NOT DOCUMENTED** beyond that sentence. Exact RPM/RPS: **NOT DOCUMENTED** on this page.[[7]](https://emailbison.com/developers)
- https://emailbison.com/features/unlimited-leads-storage — marketing copy: “Up to **3000 requests per minute** via API uploads.” Not in the API reference/OpenAPI. Scope (which endpoints, per key vs workspace) **NOT DOCUMENTED**.[[8]](https://emailbison.com/features/unlimited-leads-storage)

**What the API returns when a rate limit is hit (only documented on the developers page):** status **429**, JSON `error: "rate_limited"` plus `retry_after` (example value `8`). https://emailbison.com/developers.

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
- https://docs.emailbison.com/leads/overview
- https://emailbison.com/features/unlimited-leads-storage
- https://emailbison.com/pricing
- https://emailbison.com/developers
- https://docs.emailbison.com/email-accounts/adding-accounts
- https://docs.emailbison.com/llms.txt
- https://docs.sim.ai/integrations/emailbison
- https://scrapercity.com/integrations/emailbison
- https://emailbison.com/
- https://emailbison.com/features/email-warmup

