# Grok provider research

2026-09-17T18:29:45.160239+00:00. One call per question, web_search enabled.

**CLASSIFY BEFORE BELIEVING.** Every claim below is the model's, and a confident answer is not a documented one. A point is
DOCUMENTED only where a source URL states it, OBSERVED only where this estate's own provider responses show it, and
HYPOTHESIS or UNKNOWN otherwise. Nothing here is provider truth until a readback against our own estate agrees with it.

---

## bulk

`grok-4.6`, Nones, 68 search URLs, usage {'prompt_tokens': 482772, 'completion_tokens': 5367, 'total_tokens': 488139, 'cached_tokens': 388352, 'reasoning_tokens': 2251, 'cost_in_usd_ticks': 9854360000, 'num_sources_used': 0, 'num_server_side_tools_used': 31}.

## 1. Endpoints that accept bulk input

### Creating many leads
- **`POST /api/leads/multiple`** — body field `leads` (array of lead objects). Required per item: `first_name`, `email`. Optional: `last_name`, `title`, `company`, `notes`, `custom_variables`. Documented as bulk create.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- **`POST /api/leads/bulk/csv`** — `multipart/form-data`. Required: `name` (lead list name), `csv` (file), `columnsToMap`. Optional: `existing_lead_behavior` (`put` | `patch` | `skip`; default `put`). Returns a list-processing job (`status`, `leads_processed`, `leads_succeeded`, `leads_failed`).[[1]](https://dedi.emailbison.com/api/reference.openapi)
- Single-lead create is **`POST /api/leads`** (one object, not an array).[[2]](https://docs.emailbison.com/leads/creating-a-lead.md)

### Attaching many leads to a campaign
- **`POST /api/campaigns/{campaign_id}/leads/attach-leads`** — required `lead_ids` (array of integers). Optional `allow_parallel_sending` (boolean). Active-campaign adds are cached and synced every 5 minutes.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- **`POST /api/campaigns/{campaign_id}/leads/attach-lead-list`** — required `lead_list_id` (one list ID, not an array of leads).[[3]](https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign.md)

Related array-of-IDs (not “create”, but bulk attach/remove on a campaign):
- **`POST /api/campaigns/{campaign_id}/leads/stop-future-emails`** — `lead_ids` array.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- **`POST /api/campaigns/{campaign_id}/leads/move-to-another-campaign`** — `lead_ids` array + `target_campaign_id`.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- **`POST /api/tags/attach-to-leads`** — `tag_ids` array + `lead_ids` array.[[4]](https://docs.emailbison.com/tags/attaching-tags.md)

### Updating many leads
- **`POST /api/leads/create-or-update/multiple`** — body `leads` array (same fields as bulk create) plus optional `existing_lead_behavior` (`put` | `patch`; default `put`). Documented as update-or-create in one request.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- **`PATCH /api/leads/bulk-update-status`** — required `lead_ids` (array) and `status` (`verified` | `unverified` | `unknown` | `unsubscribed` | `risky` | `inactive`). Status only, not field updates.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- CSV re-upload: docs say leads are updated by uploading the same CSV with new values if the email does not change (`POST /api/leads/bulk/csv` with `existing_lead_behavior`).[[5]](https://docs.emailbison.com/leads/overview.md)
- Single-lead field update is **`PUT /api/leads/{lead_id}`** / **`POST /api/leads/create-or-update/{lead_id}`**. There is **no** documented JSON “bulk PATCH fields” endpoint besides create-or-update/multiple and CSV.[[1]](https://dedi.emailbison.com/api/reference.openapi)

### Adding many senders
- **`POST /api/sender-emails/bulk`** — `multipart/form-data`, required `csv`. Summary: “Add multiple sender email addresses at once.” OpenAPI example response is an array of sender objects. Docs also show this as bulk custom SMTP/IMAP upload.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- **`POST /api/campaigns/{campaign_id}/attach-sender-emails`** — required `sender_email_ids` (array). Attaches existing senders to a campaign; does not create accounts.[[1]](https://dedi.emailbison.com/api/reference.openapi)

Related sender bulk (not create):
- **`PATCH /api/sender-emails/signatures/bulk`** — `sender_email_ids` + `email_signature`.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- **`PATCH /api/sender-emails/daily-limits/bulk`** — `sender_email_ids` + daily limit.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- **`POST /api/sender-emails/move-to-another-workspace-bulk`** — `workspace_id` + `sender_email_ids`. Requires `super-admin` token.[[1]](https://dedi.emailbison.com/api/reference.openapi)

JSON array create of sender objects (not CSV): **NOT DOCUMENTED** in the OpenAPI/docs (only CSV bulk create).

---

## 2. Documented per-request limits

| Limit | What docs say |
|---|---|
| **500 leads per request** | `POST /api/leads/multiple`: “limit 500 per request”. Same for `POST /api/leads/create-or-update/multiple`. No `maxItems` in the schema beyond that description.[[1]](https://dedi.emailbison.com/api/reference.openapi) |
| **50,000 leads per CSV** | “There is a 50,000 lead limit per CSV file.” Also: “CSVs and campaigns are limited to 50,000 leads at once.” Marketing FAQ: “Each CSV lets you upload up to 50,000 leads at a time.” OpenAPI for `/api/leads/bulk/csv` does **not** restate 50,000.[[2]](https://docs.emailbison.com/leads/creating-a-lead.md) |
| **50,000 leads per campaign** | “CSVs and campaigns are limited to 50,000 leads at once.” No separate attach-leads max.[[5]](https://docs.emailbison.com/leads/overview.md) |
| **Page size 15** | Paginated responses: “pages of 15 data entries per page.” Cursor `meta.per_page` example is `15`. OpenAPI examples use `per_page: 15`. `GET /api/leads` query params document `search`, `filters.*`, `pagination_type` (`cursor` \| `length_aware`) — **not** a client-settable `per_page`. Changing page size: **NOT DOCUMENTED**.[[6]](https://docs.emailbison.com/get-started/pagination.md) |
| **Array max on attach/update/delete** | Max length of `lead_ids`, `sender_email_ids`, `tag_ids` on attach/stop/move/delete/tag/status endpoints: **NOT DOCUMENTED**. |
| **CSV sender bulk max rows** | `POST /api/sender-emails/bulk`: **NOT DOCUMENTED**. |
| **OAuth session create** | `POST /api/oauth-sessions/microsoft` and `POST /api/oauth-sessions/google`: “limit of 60 requests per minute.” (This is a rate limit, not an items-per-body limit.)[[1]](https://dedi.emailbison.com/api/reference.openapi) |

---

## 3. Rate limits and 429 behaviour

**Numeric general API rate limit in the API reference / OpenAPI:** **NOT DOCUMENTED** (no rpm/rph except the OAuth 60/min note above).

What *is* documented:

- **Developers page:** “Standard limits apply per key. Handle 429 and retry after the window indicated by headers.” HTTP **429 Too Many Requests**. Example body: `{"error": "rate_limited", "retry_after": 8}`. Header names are **NOT DOCUMENTED** (only “headers”).[[7]](https://emailbison.com/developers)
- **Marketing feature page (not API reference):** “Up to 3000 requests per minute via API uploads.” Scope (all endpoints vs uploads only) is not specified beyond that phrase.[[8]](https://emailbison.com/features/unlimited-leads-storage)
- OpenAPI does not define a 429 response schema for the lead/campaign/sender bulk routes.[[1]](https://dedi.emailbison.com/api/reference.openapi)

---

**Primary sources:** [OpenAPI](https://dedi.emailbison.com/api/reference.openapi), [API reference UI](https://dedi.emailbison.com/api/reference), [creating leads](https://docs.emailbison.com/leads/creating-a-lead), [leads overview](https://docs.emailbison.com/leads/overview), [add leads to campaign](https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign), [attach/remove senders](https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails), [adding sender accounts](https://docs.emailbison.com/email-accounts/adding-accounts), [pagination](https://docs.emailbison.com/get-started/pagination), [developers / 429](https://emailbison.com/developers).

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
- https://docs.emailbison.com/email-accounts/bulk-uploader-tool/overview
- https://outboundsync.com/docs/integrations/engagement/emailbison/authentication/connect-your-emailbison-api-key/
- https://github.com/bcharleson/emailbison-cli
- https://docs.sim.ai/triggers/emailbison
- https://www.linkedin.com/company/emailbison
- https://emailbison.com/features/unlimited-leads-storage
- https://docs.emailbison.com/email-accounts/adding-accounts
- https://docs.emailbison.com/email-accounts/bulk-uploader-tool/overview
- https://emailbison.com/pricing
- https://docs.emailbison.com/llms.txt
- https://emailbison.com/developers
- https://docs.emailbison.com/leads/overview
- https://github.com/bcharleson/emailbison-cli
- https://docs.emailbison.com/email-accounts/adding-accounts.md
- https://emailbison.com/blogs/emailbison-vs-mailshake

## scheduling

`grok-4.6`, Nones, 63 search URLs, usage {'prompt_tokens': 487932, 'completion_tokens': 5701, 'total_tokens': 493633, 'cached_tokens': 370432, 'reasoning_tokens': 3291, 'cost_in_usd_ticks': 10338440000, 'num_sources_used': 0, 'num_server_side_tools_used': 25}.

I have the docs index and campaign overview snippet. Next I’ll pull the scheduler, sender-email, warmup, and OpenAPI pages so answers stay source-only.
Campaign scheduler and field names are in the docs. Next I’ll search the OpenAPI spec for sender capacity, scheduled emails, and warmup.
Sources used: [https://docs.emailbison.com/campaigns/overview](https://docs.emailbison.com/campaigns/overview), [https://docs.emailbison.com/campaigns/creating-campaigns](https://docs.emailbison.com/campaigns/creating-campaigns), [https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign](https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign), OpenAPI at [https://dedi.emailbison.com/api/reference.openapi](https://dedi.emailbison.com/api/reference.openapi), [https://emailbison.com/features/email-sequencing](https://emailbison.com/features/email-sequencing), [https://emailbison.com/features/email-warmup](https://emailbison.com/features/email-warmup).

## 1. When campaign leads are scheduled

Documented scheduler cycle: the campaign scheduler “will run and schedule emails to be sent out every time the campaign is **resumed**, as well as **at the end of every sending day** for the campaign.” To force a run before end of day: **pause then resume**.[[1]](https://docs.emailbison.com/campaigns/overview)

Send times inside that day: “Campaign emails are sent on a **random pattern throughout your sending window** — decided by the campaign’s `schedule`.”[[1]](https://docs.emailbison.com/campaigns/overview)

`schedule` fields (POST `/api/campaigns/{campaign_id}/schedule`): `monday`…`sunday` (boolean), `start_time` / `end_time` (`HH:MM`), `timezone`.[[2]](https://docs.emailbison.com/campaigns/creating-campaigns)

Related caps (not a clock): campaign `max_emails_per_day` (“The maximum number of emails that can be sent per day”, default 1000), `max_new_leads_per_day` (“The maximum number of new leads that can be added per day”, default 1000).[[2]](https://docs.emailbison.com/campaigns/creating-campaigns)

`sequence_prioritization` (PATCH campaign update): `followups` or `new_leads`; “By default, followups are prioritized.”[[3]](https://dedi.emailbison.com/api/reference.openapi)

Adding leads to an **active** campaign: “will take **up to 5 minutes** for the leads to get synced.” That is sync delay, not the daily assignment time.[[4]](https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign)

Exact clock for “end of every sending day”, and **when / how new leads for a day are assigned** (which sender, order, leftover capacity): **NOT DOCUMENTED**.

## 2. Sender-level forward schedule / remaining capacity (all campaigns)

No documented endpoint returns remaining daily capacity for a sender.

Closest documented pieces:

- **GET `/api/scheduled-emails`** — “retrieves all scheduled (campaign) emails.” Query filters: `sender_email_ids`, `campaign_ids`, `lead_ids`, `status` (`sent` | `scheduled` | `failed` | `paused` | `stopped` | `bounced` | `unsubscribed`), `scheduled_date_local.value` (`YYYY-MM-DD`, “timezone is the campaign’s timezone”), `scheduled_date_local.criteria` (`<` `<=` `=` `>` `>=`). Response items include `scheduled_date`, `scheduled_date_local`, `status`, nested `campaign` and `sender_email`. This is a list of emails, not a capacity remaining field.[[3]](https://dedi.emailbison.com/api/reference.openapi)
- **GET `/api/campaigns/sending-schedules`** — “view the sending schedules for campaigns.” Body field `day`: `today` | `tomorrow` | `day_after_tomorrow`. Each row: `emails_being_sent`, `campaign_id`, nested `campaign`. Campaign-level, not sender-level. Same shape on **GET `/api/campaigns/{campaign_id}/sending-schedule`**.[[3]](https://dedi.emailbison.com/api/reference.openapi)
- **GET `/api/sender-emails/{senderEmailId}`** — `daily_limit`, `emails_sent_count`. No remaining-today / remaining-capacity field is documented. `emails_sent_count` is not described as today’s usage.[[3]](https://dedi.emailbison.com/api/reference.openapi)
- **GET `/api/sender-emails/{senderEmailId}/campaigns`** — “campaigns where this email account is being used.” Campaign stats only, not a send schedule.[[3]](https://dedi.emailbison.com/api/reference.openapi)

A dedicated sender “forward schedule” or remaining-capacity object: **NOT DOCUMENTED**.

## 3. `max_emails_per_day` vs sender `daily_limit` across campaigns

Documented separately:

- Campaign `max_emails_per_day`: “The maximum number of emails that can be sent per day.” PATCH `/api/campaigns/{id}/update`.[[2]](https://docs.emailbison.com/campaigns/creating-campaigns)
- Sender `daily_limit`: “The daily limit of emails that can be sent from this sender email.” PATCH `/api/sender-emails/{senderEmailId}`; bulk PATCH `/api/sender-emails/daily-limits/bulk` (“The daily sending limit to set”).[[3]](https://dedi.emailbison.com/api/reference.openapi)

Product FAQ (not API semantics): “If you use the same sender emails across multiple campaigns, **sender email limits may deplete first**.” Also: “You can run as many campaigns as you want.”[[5]](https://emailbison.com/features/email-sequencing)

How the two caps combine, share, or preempt each other when one sender is on several campaigns: **NOT DOCUMENTED**.

## 4. Does warmup consume sender `daily_limit`?

Warmup uses a **separate** limit. PATCH `/api/warmup/sender-emails/update-daily-warmup-limits` body: `sender_email_ids`, `daily_limit` (“The daily limit of **warmup** emails to send”), optional `daily_reply_limit`. Product FAQ: “You only need to set your **max daily warmup limit**.” Ramp: “gradually increase it everyday until we reach your max daily warmup limit.”[[3]](https://dedi.emailbison.com/api/reference.openapi)

Whether those warmup sends count against the sender account `daily_limit`: **NOT DOCUMENTED**.

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
- https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign
- https://docs.emailbison.com/campaigns/overview.md
- https://docs.sim.ai/integrations/emailbison
- https://emailbison.com/features/unlimited-leads-storage
- https://docs.sim.ai/tools/emailbison
- https://docs.emailbison.com/llms.txt
- https://emailbison.com/features/email-sequencing
- https://github.com/bcharleson/emailbison-cli
- https://emailbison.com/

## heyreach_sender

`grok-4.6`, Nones, 206 search URLs, usage {'prompt_tokens': 657004, 'completion_tokens': 6732, 'total_tokens': 663736, 'cached_tokens': 507392, 'reasoning_tokens': 4140, 'cost_in_usd_ticks': 13966240000, 'num_sources_used': 0, 'num_server_side_tools_used': 42}.

I'll look up HeyReach's official API docs and pull the specific campaign, sender, schedule, and webhook details from those pages.
Official Postman docs and the Campaign API page look like the primary sources. I’ll open those next and search for sender pairing, schedule reads, and webhooks.
The Postman page truncated after GetAll. I’ll search that collection plus the Campaign API and Help Center pages for AddLeadsToCampaignV2, schedule fields, and webhook events.
The Postman HTML is truncated, so I’ll look for the collection JSON, OpenAPI/Swagger, Help Center API articles, and the rest of the Campaign API page.
I’ll pull the n8n node and CLI source next — they usually copy the official request fields — and look for Help Center API/webhook articles.
**1. Sender choice with multiple LinkedIn accounts**

How HeyReach picks a sender per lead when a campaign has several accounts (round-robin, random, load, etc.): **NOT DOCUMENTED**. The official Campaign API only assigns senders at **campaign** level: `POST /api/public/campaign/Create` takes required `linkedInAccountIds` (`int[]`, 1–100 items: “LinkedIn sender account IDs; must exist and have valid auth”). That is not a per-lead pin. https://www.heyreach.io/blog/campaign-api

Is `accountLeadPairs` on `AddLeadsToCampaignV2` the documented way to pin a sender to a lead?

Vendor Campaign API page does **not** document `AddLeadsToCampaignV2` or `accountLeadPairs`. Official Postman docs list `PublicCampaigns` but the published HTML does not include that endpoint’s field text in what is retrievable. https://documenter.getpostman.com/view/23808049/2sA2xb5F75

Integration docs that wrap the same public API **do** document this payload:

- `POST /campaign/AddLeadsToCampaignV2` body: `campaignId`, `accountLeadPairs[]` with `linkedInAccountId` + `lead`. Scalekit: each pair “binds a lead to the LinkedIn sender account that will reach out”; max 100 pairs; lead minimum `profileUrl`. https://www.scalekit.com/connectors/heyreach
- Cotera: `linkedInAccountId` is **nullable** (“LinkedIn account ID of the sender”). https://cotera.co/docs/reference/tools/individual-tools/hey-reach
- n8n HeyReach node (HeyReach-partnered): “Account Lead Pairs” = LinkedIn Account ID **associated with** the lead. https://ncnodes.com/package/n8n-nodes-heyreach/heyReach/Campaign:Add%20Leads

What happens if `linkedInAccountId` is omitted/null, and whether the pin is honored for the whole sequence: **NOT DOCUMENTED**.

**2. Reading a campaign’s sending schedule after creation**

Write is documented. Read is not.

- Set on create: optional `schedule` (`CampaignScheduleApiDto`). If omitted, default is Mon–Fri 09:00–17:00 UTC. https://www.heyreach.io/blog/campaign-api
- Replace later: `POST /api/public/campaign/UpdateSchedule` with `campaignId` + `schedule` (`dailyStartTime`, `dailyEndTime`, `timeZoneId`, `enabledMonday`…`enabledSunday`, optional `startDate`/`endDate`). Response is empty `200`. https://www.heyreach.io/blog/campaign-api

A read endpoint for that schedule: **NOT DOCUMENTED**. Same page’s documented GET is `GET /api/public/campaign/GetCampaignSequence` (sequence tree only). `POST /api/public/campaign/GetAll` sample items have `id`, `name`, `creationTime`, list fields, `campaignAccountIds`, `status`, `progressStats`, exclusion flags — **no** `schedule`. https://documenter.getpostman.com/view/23808049/2sA2xb5F75

Whether `GET /campaign/GetById` returns `schedule`: **NOT DOCUMENTED**.

**3. Webhooks for accept / reply / lead status**

Yes for accept and reply. Generic “lead status change”: **NOT DOCUMENTED**.

Official Postman collection has a **PublicWebhooks** section. https://documenter.getpostman.com/view/23808049/2sA2xb5F75

Create-webhook `eventType` values in API wrappers:

| Event | Documented? |
|---|---|
| Connection accepted | Yes: `CONNECTION_REQUEST_ACCEPTED` |
| Message reply | Yes: `MESSAGE_REPLY_RECEIVED` (also `EVERY_MESSAGE_REPLY_RECEIVED` / “Every Message/InMail Reply Received”) |
| Lead status change | **NOT DOCUMENTED**. Closest is `LEAD_TAG_UPDATED` |

Sources: https://docs.composio.dev/toolkits/heyreach.md · https://ncnodes.com/package/n8n-nodes-heyreach/heyReach/Webhook:Create · https://github.com/bcharleson/heyreach-cli/blob/main/AGENTS.md

n8n Create Webhook: name 3–25 chars, URL, `eventType`, optional `campaignIds` (empty = all campaigns; **not** available for Lead Tag Updated and Every Message/InMail Reply Received). https://ncnodes.com/package/n8n-nodes-heyreach/heyReach/Webhook:Create

Sources the model searched:

- https://documenter.getpostman.com/view/23808049/2sA2xb5F75
- https://www.heyreach.io/blog/linkedin-login-via-api
- https://www.heyreach.io/blog/campaign-api
- https://n8n.io/integrations/heyreach-api/
- https://www.postman.com/chad-999/highlevel/collection/5ud7ues/heyreach-api
- https://apps.make.com/heyreach
- https://github.com/bcharleson/heyreach-cli
- https://docs.alysio.ai/integration-guides/heyreach
- https://help.heyreach.io/en/
- https://cotera.co/docs/reference/tools/individual-tools/hey-reach
- https://docs.composio.dev/toolkits/heyreach.md
- https://outboundsync.com/docs/integrations/engagement/heyreach/authentication/connect-your-heyreach-api-key/
- https://github.com/bcharleson/heyreach-cli/blob/main/AGENTS.md
- https://roadmap.heyreach.io/p/heyreach-api-JZah9z
- https://pkg.go.dev/github.com/amp-labs/connectors/providers/heyreach
- https://cotera.co/docs/reference/tools/individual-tools/hey-reach
- https://pkg.go.dev/github.com/amp-labs/connectors/providers/heyreach
- https://raw.githubusercontent.com/bcharleson/cold-outbound-dream-team/main/src/tools/heyreach/tools.py
- https://ncnodes.com/package/n8n-nodes-heyreach/heyReach/Campaign:Add%20Leads
- https://github.com/bcharleson/heyreach-mcp/blob/main/API_ENDPOINT_STATUS.md
- https://docs.alysio.ai/integration-guides/heyreach
- https://github.com/bcharleson/heyreach-cli/blob/main/AGENTS.md
- https://www.scalekit.com/connectors/heyreach
- https://docs.getcargo.ai/integration/heyreach
- https://github.com/bcharleson/heyreach-cli/blob/main/HEYREACH_API_AUDIT.md

