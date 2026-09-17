# Grok provider research

2026-09-17T20:43:35.106111+00:00. One call per question, web_search enabled.

**CLASSIFY BEFORE BELIEVING.** Every claim below is the model's, and a confident answer is not a documented one. A point is
DOCUMENTED only where a source URL states it, OBSERVED only where this estate's own provider responses show it, and
HYPOTHESIS or UNKNOWN otherwise. Nothing here is provider truth until a readback against our own estate agrees with it.

---

## bulk

`grok-4.6`, Nones, 68 search URLs, usage {'prompt_tokens': 416634, 'completion_tokens': 5996, 'total_tokens': 422630, 'cached_tokens': 321408, 'reasoning_tokens': 2521, 'cost_in_usd_ticks': 9242640000, 'num_sources_used': 0, 'num_server_side_tools_used': 30}.

I'll look up EmailBison's official API docs first, then pull the bulk endpoints, per-request limits, and rate-limit behavior only from those pages.
Official docs and OpenAPI are at docs.emailbison.com. Next I’ll pull the index, pagination, lead/campaign/sender pages, and the OpenAPI spec for bulk endpoints and limits.
I’ll open the pagination, lead-create, campaign-attach, sender, tags, and OpenAPI pages next and search them for bulk fields and numeric limits.
Pagination and bulk CSV/create are documented. I’ll search the OpenAPI spec next for maxItems, rate limits, and other bulk array endpoints.
The live OpenAPI is at dedi.emailbison.com. I’ll search that spec for bulk, attach, rate-limit, and max-item fields.
OpenAPI lists several bulk lead/sender endpoints. I’ll pull their request bodies and any documented item/rate limits next.
Sources: [docs.emailbison.com](https://docs.emailbison.com/llms.txt), [OpenAPI](https://dedi.emailbison.com/api/reference.openapi), [emailbison.com/developers](https://emailbison.com/developers).

## 1. Endpoints that accept bulk input

**Create many leads**
- `POST /api/leads/multiple` — body field `leads` (array of lead objects). Required per item: `first_name`, `email`. Optional: `last_name`, `title`, `company`, `notes`, `custom_variables`. Returns `201`. Description: “Create multiple lead records in a single request (limit 500 per request)”. Personal domains are skipped unless enabled. [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="83"}`
- `POST /api/leads/bulk/csv` — `multipart/form-data`. Required: `name` (lead list name), `csv` (file), `columnsToMap`. Optional: `existing_lead_behavior` (`put` | `patch` | `skip`, default `put`). [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="88"}` Same path in the docs guide. [Adding Leads](https://docs.emailbison.com/leads/creating-a-lead.md) `{render_inline_citation citation_id="57"}`
- Single create is `POST /api/leads` (one lead, not bulk). [Adding Leads](https://docs.emailbison.com/leads/creating-a-lead.md) `{render_inline_citation citation_id="57"}`

**Attach many leads to a campaign**
- `POST /api/campaigns/{campaign_id}/leads/attach-leads` — required `lead_ids` (array of integers). Optional `allow_parallel_sending` (boolean: force-add leads already “In Sequence” in other campaigns). Active-campaign adds are cached and synced every 5 minutes. [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="86"}` [Adding Leads to a Campaign](https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign.md) `{render_inline_citation citation_id="58"}`
- `POST /api/campaigns/{campaign_id}/leads/attach-lead-list` — required `lead_list_id` (integer). Attaches an existing list, not a raw ID array. [Adding Leads to a Campaign](https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign.md) `{render_inline_citation citation_id="58"}`

**Update many leads**
- `POST /api/leads/create-or-update/multiple` — body `leads` (array). Optional `existing_lead_behavior`: `put` (replace all fields including custom variables; omitted fields cleared) or `patch` (only update passed fields; default `put`). Description: “limit 500 per request”. [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="83"}`
- `PATCH /api/leads/bulk-update-status` — required `lead_ids` (array of integers) and `status` (`verified` | `unverified` | `unknown` | `unsubscribed` | `risky` | `inactive`). [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="83"}`
- CSV re-upload: docs say leads can be updated by uploading the same CSV with new values if the email does not change (`POST /api/leads/bulk/csv` + `existing_lead_behavior`). [Leads overview](https://docs.emailbison.com/leads/overview.md) `{render_inline_citation citation_id="61"}`
- Single-lead update is `PUT /api/leads/{lead_id}` / `POST /api/leads/create-or-update/{lead_id}` — not bulk. [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="80"}`

**Add many senders**
- `POST /api/sender-emails/bulk` — “Bulk add sender emails”. `multipart/form-data`, required field `csv` (binary). [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="84"}`
- Docs page also names `POST /api/sender-emails/imap-smtp` with `csv` and `multipart/form-data`, but the curl example hits `/api/sender-emails/bulk`. OpenAPI defines `POST /api/sender-emails/imap-smtp` as **Create IMAP/SMTP Email Account** (single). [Adding Sender Emails](https://docs.emailbison.com/email-accounts/adding-accounts.md) `{render_inline_citation citation_id="59"}` [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="90"}`
- Attach existing senders to a campaign: `POST /api/campaigns/{campaign_id}/attach-sender-emails` — required `sender_email_ids` (array). [Adding and Removing Sender Emails](https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails.md) `{render_inline_citation citation_id="63"}` [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="87"}`

Related array endpoints (not in your four cases): `POST /api/tags/attach-to-leads` (`tag_ids`, `lead_ids`); `PATCH /api/sender-emails/signatures/bulk` and `PATCH /api/sender-emails/daily-limits/bulk` (`sender_email_ids`). [Attaching Tags](https://docs.emailbison.com/tags/attaching-tags.md) `{render_inline_citation citation_id="60"}` [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="81"}`

## 2. Documented per-request limits

| Limit | Documented value | Where |
|---|---|---|
| JSON bulk create `POST /api/leads/multiple` | **500 leads per request** | [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="83"}` |
| JSON bulk upsert `POST /api/leads/create-or-update/multiple` | **500 leads per request** | [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="83"}` |
| CSV upload `POST /api/leads/bulk/csv` | **50,000 leads per CSV** | [Adding Leads](https://docs.emailbison.com/leads/creating-a-lead.md) `{render_inline_citation citation_id="57"}` |
| Campaign / CSV capacity | **CSVs and campaigns limited to 50,000 leads at once** | [Leads overview](https://docs.emailbison.com/leads/overview.md) `{render_inline_citation citation_id="61"}` |
| List page size | **15 entries per page** (`meta.per_page`: 15). Query `page`. Cursor: `pagination_type=cursor` + `cursor`. Docs do **not** document a `per_page` request parameter you can raise. | [Pagination](https://docs.emailbison.com/get-started/pagination.md) `{render_inline_citation citation_id="56"}` |
| `lead_ids` on attach-leads / bulk-update-status | **NOT DOCUMENTED** (array, no maxItems) | [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="86"}` |
| `sender_email_ids` on attach-sender-emails | **NOT DOCUMENTED** (array, no maxItems) | [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="87"}` |
| Rows in sender CSV `POST /api/sender-emails/bulk` | **NOT DOCUMENTED** | [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="84"}` |

## 3. Rate limits and 429 behaviour

**Numeric rate in API docs / OpenAPI:** NOT DOCUMENTED. No rate-limit, 429, or retry-after schema in [OpenAPI](https://dedi.emailbison.com/api/reference.openapi) `{render_inline_citation citation_id="82"}` or in [docs.emailbison.com pagination/auth](https://docs.emailbison.com/get-started/pagination.md).

**Vendor marketing / developers pages (not the API reference):**
- “Standard limits apply per key. Handle 429 and retry after the window indicated by headers.” `{render_inline_citation citation_id="65"}`
- On 429 Too Many Requests, documented JSON: `{"error": "rate_limited", "retry_after": 8}` — [Developers](https://emailbison.com/developers) `{render_inline_citation citation_id="65"}`
- “Up to 3000 requests per minute via API uploads” — [Unlimited Lead Storage](https://emailbison.com/features/unlimited-leads-storage) `{render_inline_citation citation_id="71"}`

Whether `retry_after` is seconds, whether 8 is an example vs a fixed window, and whether 3000 rpm is global vs uploads-only: **NOT DOCUMENTED**.

Sources the model searched:

- https://docs.emailbison.com/get-started/authentication
- https://docs.emailbison.com/get-started/quickstart/making-http-requests
- https://docs.emailbison.com/llms.txt
- https://emailbison.com/developers
- https://docs.emailbison.com/email-accounts/adding-accounts
- https://docs.withampersand.com/provider-guides/emailBison
- https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails
- https://docs.emailbison.com/leads/overview
- https://context7.com/websites/dedi_emailbison_api_reference
- https://emailbison.com/
- https://outboundsync.com/docs/integrations/engagement/emailbison/authentication/connect-your-emailbison-api-key/
- https://docs.emailbison.com/email-accounts/bulk-uploader-tool/overview
- https://github.com/bcharleson/emailbison-cli
- https://docs.sim.ai/triggers/emailbison
- https://www.linkedin.com/company/emailbison
- https://docs.emailbison.com/leads/overview
- https://emailbison.com/features/unlimited-leads-storage
- https://emailbison.com/developers
- https://docs.emailbison.com/email-accounts/adding-accounts
- https://docs.emailbison.com/llms.txt
- https://docs.sim.ai/integrations/emailbison
- https://github.com/emailbison-public/n8n-nodes-emailbison-official
- https://scrapercity.com/integrations/emailbison
- https://emailbison.com/
- https://emailbison.com/features/email-warmup

## scheduling

`grok-4.6`, Nones, 55 search URLs, usage {'prompt_tokens': 494749, 'completion_tokens': 4602, 'total_tokens': 499351, 'cached_tokens': 405632, 'reasoning_tokens': 3318, 'cost_in_usd_ticks': 9623240000, 'num_sources_used': 0, 'num_server_side_tools_used': 29}.

I'll look up EmailBison's official API docs first, then drill into scheduling, sender capacity, daily limits, and warmup.
Official docs and OpenAPI are live. Next I’ll pull the campaigns, sender, warmup, and scheduled-email pages plus the spec.
I’ll search the OpenAPI spec for scheduler, sender capacity, daily limits, and warmup fields.
I have the scheduler and endpoint names. Next I’ll pull sender-email, campaign-update, and warmup field definitions from the spec.
Sources used: [docs.emailbison.com](https://docs.emailbison.com/), OpenAPI at [dedi.emailbison.com/api/reference.openapi](https://dedi.emailbison.com/api/reference.openapi), product page [emailbison.com/features/email-warmup](https://emailbison.com/features/email-warmup).

---

### 1. When campaign leads are scheduled

Documented scheduler cycle:

- The campaign scheduler “will run and schedule emails to be sent out every time the campaign is **resumed**, as well as **at the end of every sending day** for the campaign.”
- To run it **before** end of day: “pause and resume the campaign.”
- URL: https://docs.emailbison.com/campaigns/overview 

Sources the model searched:

- https://docs.emailbison.com/get-started/authentication
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
- https://docs.emailbison.com/email-accounts/bulk-uploader-tool/overview
- https://github.com/bcharleson/emailbison-cli
- https://docs.sim.ai/triggers/emailbison
- https://www.linkedin.com/company/emailbison
- https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign
- https://docs.emailbison.com/leads/overview
- https://docs.emailbison.com/campaigns/overview.md
- https://docs.sim.ai/integrations/emailbison
- https://emailbison.com/features/unlimited-leads-storage
- https://docs.emailbison.com/llms.txt
- https://docs.emailbison.com/low-code-tools/clay/enrichments/import-leads-to-campaign
- https://dedi.emailbison.com/api/reference.openapi
- https://github.com/bcharleson/emailbison-cli
- https://emailbison.com/developers

## heyreach_sender

`grok-4.6`, Nones, 183 search URLs, usage {'prompt_tokens': 999235, 'completion_tokens': 8016, 'total_tokens': 1007251, 'cached_tokens': 813568, 'reasoning_tokens': 5200, 'cost_in_usd_ticks': 18624280000, 'num_sources_used': 0, 'num_server_side_tools_used': 42}.

I'll look up HeyReach's official API docs first, then check the specific endpoints and fields you asked about.
Official Postman docs and the campaign-API blog look like the primary sources. I’ll open those next and pull the exact fields.
The Postman page truncated before the endpoints I need. I’ll search that collection and the campaign-API / webhook docs for the exact fields.
Postman still isn’t giving the full endpoint text. I’ll pull the rest of the campaign-API blog and HeyReach’s help/webhook pages next.
I’ll pull the official Postman collection, help-center API articles, and any OpenAPI/webhook docs so we only cite documented behavior.
I’ll open the n8n node, CLI source, and Make.com webhook links next — those often copy the official request/response shapes.
Make.com points at HeyReach’s Notion webhook docs and a Postman fragment. Opening those now.
**Official API docs:** [Postman collection](https://documenter.getpostman.com/view/23808049/2sA2xb5F75) · [Campaign API](https://www.heyreach.io/blog/campaign-api). The Postman HTML extract only includes `GetAll` in full; `AddLeadsToCampaignV2` / `GetById` request-response text was not in that extract.

### 1. Sender choice with multiple LinkedIn accounts

**How the sender is chosen per lead (rotation, round-robin, load, etc.): NOT DOCUMENTED.**  
Campaign create takes a sender list `linkedInAccountIds` (1–100). That is assignment of accounts *to the campaign*, not per-lead selection.[[1]](https://www.heyreach.io/blog/campaign-api)

**Is `accountLeadPairs` on `AddLeadsToCampaignV2` the documented way to pin a sender?**  
Vendor Postman/Campaign API pages retrieved here **do not** state that. Closest published API-client descriptions:

- **Endpoint:** `POST /campaign/AddLeadsToCampaignV2` (base `https://api.heyreach.io/api/public/`). Body: `campaignId`, `accountLeadPairs`, optional `resumePausedCampaign` / `resumeFinishedCampaign`. Up to 100 pairs.[[2]](https://raw.githubusercontent.com/bcharleson/heyreach-cli/main/src/commands/campaigns/add-leads.ts)
- Each pair: `linkedInAccountId` + `lead` (`profileUrl` required). Scalekit: each pair **binds** the lead to that sender (`linkedInAccountId`). Cotera: `linkedInAccountId` is **nullable** “LinkedIn account ID of the sender.”[[3]](https://www.scalekit.com/connectors/heyreach)

**What happens if `linkedInAccountId` is omitted/null on a multi-sender campaign: NOT DOCUMENTED.** Do not treat omit-as-auto-assign as specified.

---

### 2. Reading sending schedule after creation

**Readable schedule after create: NOT DOCUMENTED.** No `GetSchedule` (or equivalent) in the Campaign API reference.

Documented related endpoints:

| Endpoint | Behaviour |
|---|---|
| `POST /api/public/campaign/GetAll` | Documented item fields: `id`, `name`, `creationTime`, `linkedInUserListName`, `linkedInUserListId`, `campaignAccountIds`, `status`, `progressStats`, exclusion flags, `excludeListId`. **No schedule fields.**[[4]](https://documenter.getpostman.com/view/23808049/2sA2xb5F75) |
| `GET /campaign/GetById?campaignId=` | Exists as a get-by-id call. **Response schema including schedule: NOT DOCUMENTED** in retrieved vendor text.[[5]](https://raw.githubusercontent.com/bcharleson/heyreach-cli/main/src/commands/campaigns/get.ts) |
| `GET /api/public/campaign/GetCampaignSequence?campaignId=` | Returns sequence tree only, not schedule.[[1]](https://www.heyreach.io/blog/campaign-api) |
| `POST /api/public/campaign/UpdateSchedule` | **Write only.** Replaces `CampaignScheduleApiDto` (`dailyStartTime`, `dailyEndTime`, `timeZoneId`, `enabledMonday`…`enabledSunday`, `startDate`, `endDate`). `200` empty body. DRAFT/SCHEDULED/PAUSED only.[[1]](https://www.heyreach.io/blog/campaign-api) |

Schedule is set on `Create` (`schedule` optional; default Mon–Fri 09:00–17:00 UTC if omitted) and replaced via `UpdateSchedule`. A documented **read** of that object after creation is **NOT DOCUMENTED**.[[1]](https://www.heyreach.io/blog/campaign-api)

---

### 3. Webhooks: connection accepted / message reply / lead status change

**Yes for connection accepted and message reply. Generic “lead status change”: NOT DOCUMENTED** (tag update is documented instead).

Official Postman has **PublicWebhooks**. Create used by API clients: `POST /webhooks/CreateWebhook` with `webhookName`, `webhookUrl`, `eventType`, optional `campaignIds`.[[6]](https://raw.githubusercontent.com/bcharleson/heyreach-cli/main/src/commands/webhooks/create.ts)

| Event you asked | Documented `eventType` | Notes |
|---|---|---|
| Connection accepted | `CONNECTION_REQUEST_ACCEPTED` | In create-webhook enums; Zapier trigger “Connection Request Accepted”.[[7]](https://docs.composio.dev/toolkits/heyreach.md) |
| Message reply | `MESSAGE_REPLY_RECEIVED` (first reply) and `EVERY_MESSAGE_REPLY_RECEIVED` / UI “every message/inmail reply received” | Vendor n8n guide: first-reply only fires once; every-reply fires on later replies. Payload includes latest message, conversation ID, campaign, sender, lead — **not** full thread.[[8]](https://www.heyreach.io/blog/handle-heyreach-replies-with-n8n) |
| Lead status change | **NOT DOCUMENTED** under that name | Documented nearby event: `LEAD_TAG_UPDATED`. Campaign-lead `status` transitions are not listed as a webhook type.[[9]](https://ncnodes.com/package/n8n-nodes-heyreach/heyReach/Webhook:Create) |

Other documented types: `CONNECTION_REQUEST_SENT`, `MESSAGE_SENT`, `INMAIL_SENT`, `INMAIL_REPLY_RECEIVED`, `FOLLOW_SENT`, `LIKED_POST`, `VIEWED_PROFILE`, `CAMPAIGN_COMPLETED`. `campaignIds` empty = all campaigns; n8n notes campaign filter is **not** available for Lead Tag Updated and Every Message/InMail Reply Received.[[7]](https://docs.composio.dev/toolkits/heyreach.md)

Vendor webhook payload reference (Notion) is linked from Make but did not render without JS: https://heyreach.notion.site/heyreach-webhooks-documentation-400c53b3aa8743d085937419bccfe276

Sources the model searched:

- https://cotera.co/docs/reference/tools/individual-tools/hey-reach
- https://raw.githubusercontent.com/bcharleson/cold-outbound-dream-team/main/src/tools/heyreach/tools.py
- https://pkg.go.dev/github.com/amp-labs/connectors/providers/heyreach
- https://github.com/bcharleson/heyreach-mcp/blob/main/API_ENDPOINT_STATUS.md
- https://ncnodes.com/package/n8n-nodes-heyreach/heyReach/Campaign:Add%20Leads
- https://github.com/bcharleson/heyreach-cli/blob/main/AGENTS.md
- https://docs.alysio.ai/integration-guides/heyreach
- https://apps.make.com/heyreach
- https://docs.getcargo.ai/integration/heyreach
- https://www.pkgstats.com/pkg:heyreach-cli
- https://github.com/bcharleson/heyreach-cli/blob/main/HEYREACH_API_AUDIT.md
- https://docs.composio.dev/toolkits/heyreach.md
- https://www.scalekit.com/connectors/heyreach
- https://www.heyreach.io/blog/campaign-api
- https://github.com/anthroos/heyreach-claude-skill/blob/main/SKILL.md
- https://outboundsync.com/docs/integrations/engagement/heyreach/webhooks/heyreach-webhook-guide/
- https://github.com/bcharleson/heyreach-cli
- https://cotera.co/docs/reference/tools/individual-tools/hey-reach
- https://docs.getcargo.ai/integration/hey-reach
- https://docs.composio.dev/toolkits/heyreach.md
- https://ncnodes.com/package/n8n-nodes-heyreach/heyReach/Webhook:Create
- https://documenter.getpostman.com/view/23808049/2sA2xb5F75
- https://github.com/bcharleson/heyreach-cli/blob/main/AGENTS.md
- https://www.heyreach.io/blog/zapier-integration
- https://ncnodes.com/package/n8n-nodes-heyreach/heyReach/Webhook:Update

