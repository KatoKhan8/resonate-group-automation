# Grok provider research

2026-09-22T18:53:46.262508+00:00. One call per question, web_search enabled.

**CLASSIFY BEFORE BELIEVING.** Every claim below is the model's, and a confident answer is not a documented one. A point is
DOCUMENTED only where a source URL states it, OBSERVED only where this estate's own provider responses show it, and
HYPOTHESIS or UNKNOWN otherwise. Nothing here is provider truth until a readback against our own estate agrees with it.

---

## contactout_company_search

`grok-4.6`, Nones, 65 search URLs, usage {'prompt_tokens': 305034, 'completion_tokens': 4920, 'total_tokens': 309954, 'cached_tokens': 230784, 'reasoning_tokens': 2933, 'cost_in_usd_ticks': 6668240000, 'num_sources_used': 0, 'num_server_side_tools_used': 16}.

**Docs used:** [https://api.contactout.com/](https://api.contactout.com/) (same content as [https://api.contactout.io/](https://api.contactout.io/)), plus the FAQ the API reference links: [https://docs.google.com/document/d/11tobiUQHho36NtBg2alJ0UyVoS4HIeIz3hehu0EsFjw](https://docs.google.com/document/d/11tobiUQHho36NtBg2alJ0UyVoS4HIeIz3hehu0EsFjw).

### 1. Rate limits on `POST /v1/company/search`

Company Search is **not named** in the rate-limits list. Documented buckets:[[1]](https://api.contactout.com/#rate-limits)

| Bucket | Limit |
|---|---|
| People Search API | 60 requests per minute |
| Contact Checker APIs | 150 requests per minute (FAQ says 100) |
| Other APIs | 1000 requests per minute |

Sources: [https://api.contactout.com/#rate-limits](https://api.contactout.com/#rate-limits), FAQ Q4 [https://docs.google.com/document/d/11tobiUQHho36NtBg2alJ0UyVoS4HIeIz3hehu0EsFjw](https://docs.google.com/document/d/11tobiUQHho36NtBg2alJ0UyVoS4HIeIz3hehu0EsFjw).

- Per second: **NOT DOCUMENTED**
- Per day: **NOT DOCUMENTED**
- Per API key / per account / per endpoint: **NOT DOCUMENTED**
- Shared with `/v1/people/search`: **NOT DOCUMENTED** as shared. People Search is a separate 60/min bucket; Company Search is not listed there.[[2]](https://api.contactout.io/)
- Shared with `/v1/people/count`: **NOT DOCUMENTED** (`/people/count` is not named in the rate-limits list)

429 behaviour (all APIs): `Rate limit reached. Check header retry-after: <time_in_seconds> for when rate limit will reset`. [https://api.contactout.com/#errors](https://api.contactout.com/#errors)[[2]](https://api.contactout.io/)

### 2. Page size / paging ceiling on this endpoint

Company Search query-parameter table does **not** list `page` or `page_size`. Documented body fields are: `linkedin_url`, `name`, `domain`, `size`, `hq_only`, `location`, `industries`, `technologies`, `min_revenue`, `max_revenue`, `year_founded_from`, `year_founded_to`. [https://api.contactout.com/#company-search-api](https://api.contactout.com/#company-search-api)[[2]](https://api.contactout.io/)

What the docs *do* show:

- Example request body includes `"page": 1` (not in the parameter table).
- Example responses include `metadata.page`, `metadata.page_size: 25`, `metadata.total_results`.
- Cost: `Consumes 1 search credit for each company returned.`

- Maximum `page` size: **NOT DOCUMENTED** (do not reuse People Search’s 1–25; that is a different endpoint)
- Default `page` size: **NOT DOCUMENTED** as a request default. Example `metadata.page_size` is 25 only.
- Maximum page number: **NOT DOCUMENTED**
- Total-results ceiling / paging stop: **NOT DOCUMENTED**

### 3. HTTP 402 vs 403 on this endpoint

Documented error table (all ContactOut APIs, not endpoint-specific): [https://api.contactout.com/#errors](https://api.contactout.com/#errors)[[2]](https://api.contactout.io/)

| Code | Documented meaning |
|---|---|
| **402** | **NOT DOCUMENTED** (not in the error table) |
| **403** | Two messages: (1) `You're out of credits, please email your sales manager or book a meeting: https://contactout.com/meeting?utm_source=api-out-of-credits` (2) `No access to endpoint` |

FAQ also: no Search Credits → **403**. [https://docs.google.com/document/d/11tobiUQHho36NtBg2alJ0UyVoS4HIeIz3hehu0EsFjw](https://docs.google.com/document/d/11tobiUQHho36NtBg2alJ0UyVoS4HIeIz3hehu0EsFjw) (Q3)[[3]](https://docs.google.com/document/d/11tobiUQHho36NtBg2alJ0UyVoS4HIeIz3hehu0EsFjw)

What you asked to distinguish:

- Out of credit: documented as **403** with the “You're out of credits…” message (not 402).
- Not entitled to this endpoint: documented as **403** `No access to endpoint`.
- Key revoked: **NOT DOCUMENTED**. Closest listed codes are **400** `Bad credentials or invalid headers` and **401** `Bad request or invalid input` (those labels are as written; they are inverted vs usual HTTP).

The docs do **not** say how to tell the two 403s apart except by **message** text. No separate status for revoked vs unentitled.

### 4. Response headers for remaining credits / quota

On `POST /v1/company/search`: **NOT DOCUMENTED**. No credit/quota response headers are listed for this (or any) search response.[[2]](https://api.contactout.io/)

The only documented response header in Errors is `retry-after` on **429**. [https://api.contactout.com/#errors](https://api.contactout.com/#errors)

Credits are a **separate** `GET https://api.contactout.com/v1/stats?period=YYYY-MM` call. Postpaid body fields include `search_remaining` (`search_quota - search_count`). Prepaid example has `search_quota` = “Prepaid Search credits remaining”, no `search_remaining`. [https://api.contactout.com/#api-usage-stats](https://api.contactout.com/#api-usage-stats)[[2]](https://api.contactout.io/)

FAQ also: web UI [https://contactout.com/api_users/stats](https://contactout.com/api_users/stats).

Sources the model searched:

- https://api.contactout.io/
- https://pipedream.com/apps/http/integrations/contactout/company-search-with-contactout-api-on-new-requests-from-http-webhook-api-int_avs2P5MG
- https://docs.extruct.ai/api-reference/search-post
- https://api.contactout.io/
- https://pipedream.com/apps/contactout/actions/company-search
- https://api.contactout.io/
- https://treg.to/tools/contactout
- https://api.contactout.io/
- https://competitors.explorium.ai/contactout-vs-thecompaniesapi
- https://api.opencorporates.com/documentation/Home
- https://docs.getcargo.ai/integration/contact-out
- https://docs.blitz-api.ai/api-reference/company-search/company-search
- https://docs.kontakto.fi/api/
- https://docs.lusha.com/apis/openapi/search.md
- https://developers.theorg.com/api/endpoints/mcp-api
- https://docs.google.com/document/d/11tobiUQHho36NtBg2alJ0UyVoS4HIeIz3hehu0EsFjw
- https://api.contactout.io/
- https://aeroleads.com/blog/contactout-api-documentation-endpoints-parameters-code-examples/
- https://competitors.explorium.ai/contactout-vs-thecompaniesapi
- https://www.enrich.so/blog/contactout-pricing-breakdown
- https://api.contactout.io/
- https://api.contactout.io/
- https://aeroleads.com/blog/contactout-api-docs-start-developers-sales-engineers/
- https://treg.to/tools/contactout
- https://resources.reachstream.com/contactout-pricing/

## heyreach_seat_limits

`grok-4.6`, Nones, 161 search URLs, usage {'prompt_tokens': 793979, 'completion_tokens': 9237, 'total_tokens': 803216, 'cached_tokens': 662272, 'reasoning_tokens': 6453, 'cost_in_usd_ticks': 14999440000, 'num_sources_used': 0, 'num_server_side_tools_used': 40}.

I'll look up HeyReach's official docs for per-seat limits, usage APIs, multi-campaign sharing, and what happens when a seat hits its cap.
Official API and help-center pages are next: Postman collection, campaign-API writeup, and sending-limits docs.
I'll open the help center, Postman API, and the sending-limits / campaign-API pages next.
Help-center collections, Postman endpoints, and HeyReach blog pages on limits and stats are next.
Found official help articles on sending limits and sender rotation. Opening those plus API/stats docs next.
Help-center pages are JS-rendered. I’ll pull Intercom/JSON copies and the Postman API reference instead.
I'll try archive/JSON copies of the sending-limits article and pull API field lists from Postman, GitHub, and third-party API refs.
Pulling Postman field lists, campaign-lead statuses, and the rest of the limits/analytics docs.
**Official API collection:** https://documenter.getpostman.com/view/23808049/2sA2xb5F75  
**Sending-limits help article (JS-rendered; body not extractable here):** https://help.heyreach.io/en/articles/9892903-how-to-configure-my-sending-limits  
**Sender-rotation help article:** https://help.heyreach.io/en/articles/9897768-multiple-linkedin-senders-on-one-campaign-sender-rotation  

---

### 1. Per-seat daily limits (connection requests / messages)

**Fixed product numbers (max / default for connection requests and for messages):** NOT DOCUMENTED in any extractable vendor page. The help article above exists; its numeric table was not readable in this research.

**Configurable:** Yes, **per LinkedIn account (seat)**, not per campaign. HeyReach’s own workflow says: after connecting a sender, click **Configure Limits**; those values are **hard caps** and “HeyReach won’t exceed them regardless of campaign volume.” Recommended starting points they publish (not stated as product maxima): connection requests **10–15/day** in week one; messages **20–30/day**. Later they recommend ramping connection requests by account age (new 10–15, warming 15–25, established up to 30–40).[[1]](https://www.heyreach.io/blog/linkedin-company-expansion-strategy)

**Per campaign via API:** NOT DOCUMENTED. `POST /api/public/campaign/Create` (`CreateCampaignApiInputDto`) has `name`, `linkedInUserListId`, `linkedInAccountIds`, exclusion flags, `schedule`, `sequence` — **no daily-limit fields**. `UpdateSchedule` only sets `dailyStartTime`, `dailyEndTime`, `timeZoneId`, weekday flags, `startDate`, `endDate`.[[2]](https://www.heyreach.io/blog/campaign-api)

**Adaptive to account age / warmup:** NOT DOCUMENTED as an automatic product behaviour. The same blog gives **manual** warmup guidance by week/age; it does not say HeyReach auto-adjusts the cap from SSI, age, or warmup state.[[1]](https://www.heyreach.io/blog/linkedin-company-expansion-strategy)

---

### 2. Per-seat usage via API (requests/messages sent today; OUR vs THEIR on the same seat)

**Live “sent today vs daily cap” / remaining quota object:** NOT DOCUMENTED.

**Closest documented analytics call:** Postman collection has an **Analytics** folder. Integration maps of the public API name `POST /api/public/stats/GetOverallStats`, with filters `accountIds`, `campaignIds`, and a date range, returning aggregate counts such as `connectionsSent` and `messagesSent` in `byDayStats` / `overallStats` — historical counts, not remaining allowance.[[3]](https://documenter.getpostman.com/view/23808049/2sA2xb5F75)

**Seat vs campaign split:** The stats call can be filtered by `accountIds` (seat totals) and/or `campaignIds` (campaign totals). There is **no** documented field that attributes usage to two tenants sharing one seat. Auth is a workspace `X-API-KEY` mapped to the organization, not to a campaign owner.[[3]](https://documenter.getpostman.com/view/23808049/2sA2xb5F75)

**`GET/POST li_account` returning today’s usage or remaining cap:** NOT DOCUMENTED (folder **LinkedInAccounts** exists in Postman; no usage/quota fields published in extractable docs).

**Campaign list stats** (`POST /api/public/campaign/GetAll` → `progressStats`): `totalUsers`, `totalUsersInProgress`, `totalUsersPending`, `totalUsersFinished`, `totalUsersFailed` only — not sends-today or remaining allowance.[[3]](https://documenter.getpostman.com/view/23808049/2sA2xb5F75)

So: you can **count** sends in a date window per `accountIds` or per `campaignIds`. You cannot, from documented fields, read a seat quota, remaining allowance, or a first-class OUR vs THEIR usage split on the same seat.

---

### 3. Two campaigns on one seat — how the limit is divided; remaining allowance in the API

**Not divided.** Limits are **per LinkedIn account and shared across all campaigns** on that account. HeyReach: “Active senders in other campaigns share daily limits across all campaigns, so actions per day will drop below your set limit if you select LinkedIn senders who are already active in other campaigns.” Same point: “Sending Limits are per LinkedIn account and shared across campaigns”; “All campaigns on the same LinkedIn account share one daily action limit.”[[1]](https://www.heyreach.io/blog/linkedin-company-expansion-strategy)

**API remaining allowance for the seat:** NOT DOCUMENTED.

A 2023 roadmap request asked for per-campaign caps (e.g. 10 CR/day in campaign A, 20 in campaign B); that is a feature request, not current documented behaviour. https://roadmap.heyreach.io/p/campaign-limits-for-accounts-j0JsTp

---

### 4. What happens when a seat hits its limit (queue / skip / fail) and visibility

**Does not fail the campaign.** Vendor text: when send saturation hits, “nothing ‘fails’ outright. Delivery just slows down”; upstream steps consume the shared daily cap and “the rest of the sequence gets blocked.” Campaign can still show as active while leads sit in **Pending** / **In sequence** rather than moving to later steps. Failed is a separate progress bucket (`totalUsersFailed` / “Failed”), not documented as the limit-hit outcome.[[4]](https://www.heyreach.io/blog/why-automation-fails)

**Hard cap:** HeyReach will not exceed the configured per-account limits regardless of campaign volume.[[1]](https://www.heyreach.io/blog/linkedin-company-expansion-strategy)

**Queue vs skip:** NOT DOCUMENTED as those words. Closest documented behaviours:
- Same seat, multiple campaigns: later actions wait / get blocked until cap allows (slowdown, not fail).
- **Multiple senders on one campaign:** when a sender approaches its daily limit, “the next lead in the queue doesn’t wait — it gets routed to the next available sender” (sender rotation). That is **not** documented for two campaigns sharing one seat. https://help.heyreach.io/en/articles/9897768-multiple-linkedin-senders-on-one-campaign-sender-rotation

**Visible in API campaign/lead status as “limit reached”:** NOT DOCUMENTED. Documented visibility is stalled progression (Pending / In sequence) and slower throughput, not a dedicated limit-hit status.

Sources the model searched:

- https://www.heyreach.io/blog/campaign-api
- https://docs.getcargo.ai/integration/heyreach
- https://n8n.io/integrations/heyreach-api/
- https://documenter.getpostman.com/view/23808049/2sA2xb5F75
- https://oxygen-agent.com/integrations/heyreach
- https://docs.alysio.ai/integration-guides/heyreach
- https://www.heyreach.io/blog/how-to-automate-linkedin-outreach
- https://www.heyreach.io
- https://www.heyreach.io/blog/make-integration
- https://www.heyreach.io/blog/automate-linkedin-lead-generation-with-claude-code-and-heyreach
- https://github.com/bcharleson/heyreach-cli
- https://www.heyreach.io/blog/n8n-integration
- https://linkedsdr.com/blog/linkedin-integration-heyreach
- https://github.com/anthroos/heyreach-claude-skill/blob/main/SKILL.md
- https://zapier.com/apps/heyreach/integrations/linkedin
- https://roadmap.heyreach.io/p/configure-activity-days-working-hours-and-daily-limits-XO3QHO
- https://blog.gojiberry.ai/blog/heyreach-review
- https://overloop.com/blog/heyreach-review
- https://www.promiseclick.com/blog/how-to-use-heyreach-guide
- https://overloop.com/blog/heyreach-vs-expandi
- https://www.heyreach.io/blog/linkedin-company-expansion-strategy
- https://www.youtube.com/watch?v=5eJpsKv2Hco
- https://lagrowthmachine.com/heyreach-review/
- https://leadhaste.com/blog/heyreach-review-2026
- https://www.heyreach.io/pricing

## bison_per_mailbox_daily

`grok-4.6`, Nones, 65 search URLs, usage {'prompt_tokens': 591337, 'completion_tokens': 6722, 'total_tokens': 598059, 'cached_tokens': 485632, 'reasoning_tokens': 3092, 'cost_in_usd_ticks': 11641160000, 'num_sources_used': 0, 'num_server_side_tools_used': 35}.

I'll look up EmailBison's official API docs first, then check for mailbox-level send/bounce metrics, bounce type fields, and any sender-health endpoints.
Docs live at docs.emailbison.com plus an OpenAPI spec. Next I’ll pull the index, webhook events, sender-email objects, and stats endpoints.
The OpenAPI spec and webhook/sender-email pages are the source of truth. I’ll extract bounce/send fields, time windows, and event types from those.
`/api/campaign-events/stats` can drill by date and sender email ID. I’ll pull its params, campaign/workspace stats, sender-email fields, and bounce webhook payload next.
**Sources used:** official OpenAPI at `https://dedi.emailbison.com/api/reference.openapi`, plus `docs.emailbison.com` webhook pages. No other bounce-rate report exists in those docs.[[1]](https://dedi.emailbison.com/api/reference.openapi)

---

### 1. Sends/bounces per mailbox per day?

**No documented endpoint returns a mailbox × day matrix of sends and bounces in one response.**

Closest documented report:

- **`GET /api/campaign-events/stats`** — “Breakdown of events by date”. Query params: required `start_date`, `end_date`; optional `sender_email_ids` (“List of sender email IDs to include”), optional `campaign_ids`. Events returned include **`Sent`** and **`Bounced`**. Response is series objects `{ label, color, dates: [[YYYY-MM-DD, count], ...] }`, not rows keyed by mailbox. Passing several `sender_email_ids` still yields one combined series. To isolate one mailbox you would pass a single ID; the spec does not document a multi-mailbox breakdown. Time-window max is **NOT DOCUMENTED**.  
  URL: https://dedi.emailbison.com/api/reference.openapi (`/api/campaign-events/stats`)[[1]](https://dedi.emailbison.com/api/reference.openapi)

Webhooks are **per event**, not daily totals:

- `email_sent` — “Triggered only when a campaign email is sent.”
- `email_bounced` — “Triggered when a campaign email bounces.”  
  URL: https://docs.emailbison.com/webhooks/when-are-webhooks-triggered.md[[2]](https://docs.emailbison.com/webhooks/when-are-webhooks-triggered.md)

`GET /api/webhook-events/sample-payload` (body `event_type`) can return a sample; the only payload example in the spec is `EMAIL_SENT`, which includes nested `scheduled_email`, `campaign_event.type: "sent"`, `lead`, `campaign`, `sender_email` (lifetime `emails_sent` / `bounced` on the sender object). No daily counts.  
  URL: https://dedi.emailbison.com/api/reference.openapi (`/api/webhook-events/sample-payload`)[[1]](https://dedi.emailbison.com/api/reference.openapi)

`GET /api/events` lists the same event types (including `email_sent`, `email_bounced`) for **the last 10 days only**, with `type`, `start_date`, `end_date`. Still individual events, not per-day aggregates.  
  URLs: https://docs.emailbison.com/webhooks/events-deliveries-and-attempts.md · OpenAPI `/api/events` (“Get all events (up to 10 days)”)[[3]](https://docs.emailbison.com/webhooks/events-deliveries-and-attempts.md)

Lifetime (no day bucket) on the mailbox object:

- **`GET /api/sender-emails`** / **`GET /api/sender-emails/{senderEmailId}`** — fields `emails_sent_count`, `bounced_count` (examples are integers; no date params on list).  
  URL: https://dedi.emailbison.com/api/reference.openapi (`/api/sender-emails`)[[1]](https://dedi.emailbison.com/api/reference.openapi)

Row-level (what you already walk):

- **`GET /api/scheduled-emails`** — filter `status` (`sent` | `bounced` | …), `sender_email_ids`, `scheduled_date_local.value` (`YYYY-MM-DD`) + `scheduled_date_local.criteria`. Nested `sender_email.emails_sent_count` / `bounced_count` are mailbox lifetime, not that day’s totals.  
  URL: https://dedi.emailbison.com/api/reference.openapi (`/api/scheduled-emails`)[[1]](https://dedi.emailbison.com/api/reference.openapi)

---

### 2. Finest documented granularity and window

| Granularity | Endpoint | Window | Metrics |
|---|---|---|---|
| **Sender email IDs + calendar day** (finest stats report) | `GET /api/campaign-events/stats` | `start_date` + `end_date` (max **NOT DOCUMENTED**) | daily `Sent`, `Bounced` (plus Replied, opens, Unsubscribed, Interested) |
| **One campaign + calendar day** | `GET /api/campaigns/{campaign_id}/line-area-chart-stats` | same | same labels |
| **One campaign, range summary (not daily)** | `POST /api/campaigns/{campaign_id}/stats` body `start_date`, `end_date` | same | `emails_sent`, `bounced`, `bounced_percentage`, plus `sequence_step_stats[].sent` / `.bounced` |
| **Workspace + calendar day** | `GET /api/workspaces/v1.1/line-area-chart-stats` | same | daily Sent / Bounced |
| **Workspace range summary** | `GET /api/workspaces/v1.1/stats` | same | `emails_sent`, `bounced`, `bounced_percentage` |
| **Mailbox lifetime totals** | `GET /api/sender-emails` | no window | `emails_sent_count`, `bounced_count` |
| **Raw events** | `GET /api/events` | **last 10 days** | `email_sent` / `email_bounced` events |

OpenAPI: `/api/campaigns/{campaign_id}/stats`, `/api/campaigns/{campaign_id}/line-area-chart-stats`, `/api/workspaces/v1.1/stats`, `/api/workspaces/v1.1/line-area-chart-stats`.[[1]](https://dedi.emailbison.com/api/reference.openapi)

A rolling 7-day bounce **rate** field is **NOT DOCUMENTED**. You would have to sum the daily `Sent`/`Bounced` series yourself.

---

### 3. Hard vs soft bounces?

**NOT DOCUMENTED.** OpenAPI has no `hard_bounce`, `soft_bounce`, `bounce_type`, or similar field.[[1]](https://dedi.emailbison.com/api/reference.openapi)

Documented bounce representations are a single bucket:

- Webhook/event id `email_bounced` — “You sent an email that bounced.” / “Triggered when a campaign email bounces.”  
  URLs: https://docs.emailbison.com/webhooks/when-are-webhooks-triggered.md · OpenAPI webhook `events` enum  
- Scheduled-email `status` enum: `sent`, `scheduled`, `failed`, `paused`, `stopped`, **`bounced`**, `unsubscribed` — one `bounced` value.  
- Lead `status` example includes `bounced`.  
- Stats labels: `Bounced` / field `bounced` / `bounced_count` / `bounced_percentage`.

Warmup events are **not** hard/soft:

- `warmup_disabled_causing_bounces` — “warmup for a sender email was disabled for causing too many bounces”
- `warmup_disabled_receiving_bounces` — “disabled for receiving too many bounces”  
  URL: https://docs.emailbison.com/webhooks/when-are-webhooks-triggered.md

Whether bounce type is available per mailbox: **NOT DOCUMENTED** (no type field at any grain).

---

### 4. Sender health / reputation / deliverability field that already aggregates this?

**No documented field is a campaign bounce rate per mailbox over rolling 7 days.**

What the API *does* expose on a sender:

- **`GET /api/sender-emails`**: `emails_sent_count`, `bounced_count` (lifetime counts, not a rate, no 7-day window). `status` enum is connection state: `connected`, `not_connected`, `pending_move`, `pending_deletion`. Filter `warmup_score_filter` with periods `warmup_score_last_3_days` … `warmup_score_last_7_days` … `warmup_score_last_30_days` — that is **warmup score**, not bounce rate. Spec says use the Warmup resource for exact scores.  
  URL: OpenAPI `/api/sender-emails`[[1]](https://dedi.emailbison.com/api/reference.openapi)

- **`GET /api/warmup/sender-emails`** and **`GET /api/warmup/sender-emails/{senderEmailId}`** (`start_date`/`end_date` required on the single-account GET): `warmup_emails_sent`, `warmup_replies_received`, `warmup_emails_saved_from_spam`, **`warmup_score`**, `warmup_bounces_received_count`, `warmup_bounces_caused_count`, `warmup_disabled_for_bouncing_count`. These are warmup stats, not campaign send/bounce rate.  
  URL: OpenAPI `/api/warmup/sender-emails` · marketing list of warmup routes also at https://emailbison.com/features/email-warmup[[1]](https://dedi.emailbison.com/api/reference.openapi)

- Campaign create body **`reputation_building`**: boolean, described as “Spam protection” — a setting, not a health score.  
  URL: OpenAPI campaign create schema

- Team object has `has_access_to_healthcheck: boolean`. A healthcheck **stats** endpoint is **NOT DOCUMENTED**.

- Workspace/campaign `bounced_percentage` is over the requested date range at **campaign or workspace** grain, not per mailbox.

**Practical substitute the docs actually specify:** call `GET /api/campaign-events/stats` once per mailbox (`sender_email_ids` = that id, `start_date`/`end_date` covering 7 days), read the `Sent` and `Bounced` date series, and compute the rate. Lifetime `bounced_count`/`emails_sent_count` on `GET /api/sender-emails` cannot enforce a rolling 7-day stop.

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
- https://emailbison.com/blogs/email-warmup-tools
- https://dedi.emailbison.com/api/reference.openapi
- https://emailbison.com/blogs/cold-email-open-rates
- https://emailbison.com/blogs/emailbison-vs-smartlead
- https://emailbison.com/blogs/dedicated-ip-clusters
- https://emailbison.com/pricing
- https://emailbison.com/blogs/cold-email-warmup
- https://emailbison.com/blogs/emailbison-vs-reply.io
- https://docs.emailbison.com/master-inbox/fetching-replies.md
- https://emailbison.com/blogs/emailbison-vs-instantly

## hosting_hetzner_vs_railway

`grok-4.6`, Nones, 106 search URLs, usage {'prompt_tokens': 466477, 'completion_tokens': 8155, 'total_tokens': 474632, 'cached_tokens': 340864, 'reasoning_tokens': 4500, 'cost_in_usd_ticks': 11111760000, 'num_sources_used': 0, 'num_server_side_tools_used': 34}.

I'll pull current Hetzner and Railway docs/pricing, plus SQLite's documented live-backup method, and only report what those pages actually say.
Official pricing and backup pages next: Hetzner’s current cloud list, Railway restart/volume backup docs, and SQLite’s live-copy APIs.
Fetching official pricing, backup-consistency, and Railway volume/backup pages so every number and caveat is from a cited URL.
Pulling SQLite’s Python backup API, Railway’s always-on/volume limits, and Hetzner’s backup-enable + snapshot-rate pages.
Prices below are **as published on the cited vendor pages**. Where a vendor page does not specify a step or guarantee, this says **NOT DOCUMENTED** rather than filling the gap.

## 1. Hetzner Cloud

**Instance type.** Hetzner does **not** document which type fits “15 background loops + a small HTTP server”. Documented smallest Cost-Optimized type: **CX23** — 2 vCPU (Intel/AMD), 4 GB RAM, 40 GB NVMe, EU traffic included 20 TB. Positioned as cost-effective, low-to-medium CPU, “perfect for test environments”. Next Cost-Optimized: **CX33** — 4 vCPU, 8 GB, 80 GB. Regular Performance **CPX22** — 2 AMD vCPU, 4 GB, 80 GB.[[1]](https://www.hetzner.com/cloud/cost-optimized/)

**Monthly EUR (EU FSN/NBG/HEL, new orders from 15 Jun 2026).** Price-adjustment table (header: prices include 19% MwSt; column is excl. IPv4): **CX23 €6.53/month** (hourly €0.0105); CX33 €10.10; CPX22 €23.19.[[2]](https://docs.hetzner.com/de/general/infrastructure-and-availability/price-adjustment/)

Add-ons billed separately:
- **Primary IPv4:** €0.50/month excl. VAT (English IP page) / **€0.60/month incl. 19% USt** (German IP page). Primary IPv6 free.[[3]](https://docs.hetzner.com/general/infrastructure-and-availability/ipv4-pricing/)
- **Automatic Backups:** flat **20% of the server price**, 7 slots. Example in the FAQ uses an old €3.29 server → €0.658/month; the 20% rule is what is documented, not a current CX23 line item.[[4]](https://docs.hetzner.com/cloud/billing/faq/)
- **Snapshots:** billed **per GB/month of compressed size**; **€/GB rate: NOT DOCUMENTED** on the billing FAQ (it only says “per gigabyte per month”).[[4]](https://docs.hetzner.com/cloud/billing/faq/)

Bill never exceeds the monthly cap; hourly rounding up; billed until the server is **deleted**, including while powered off.[[4]](https://docs.hetzner.com/cloud/billing/faq/)

**systemd units.** **NOT DOCUMENTED** in Hetzner Cloud docs (they do not publish unit files, `Restart=`, or an app-supervision guide). You get a normal Linux VM; supervision is OS-level, not a Hetzner product.

**TLS (certbot / Caddy) for a custom Python HTTP server.** **NOT DOCUMENTED** for this shape. Hetzner documents `certbot --apache` only on **LAMP/Nextcloud app images**, not a stdlib Python server. Caddy appears only as a **community DNS plugin** for Hetzner DNS (`caddy-dns/hetzner`), not as a reverse-proxy recipe.[[5]](https://docs.hetzner.com/de/cloud/apps/list/lamp-stack/)

**Nightly backups — Hetzner’s own feature.**
- **Backups:** automatic **daily** copy of the **server disk**; 7 slots; oldest deleted; **you cannot pick the time** (that UI was removed). Attach **Volumes are not included**. Enable via Console: Backups → add/enable (paid). Manual backup also consumes one of the 7 slots. Snapshots are customer-triggered and not auto-rotated (default max 30 across projects).[[6]](https://docs.hetzner.com/cloud/servers/backups-snapshots/faq/)
- **Live SQLite safety:** Hetzner **does not** claim a live SQLite file is consistent. Quote: “When creating Backups or Snapshots, we recommend that you power off your server to ensure data consistency on the disk. You can also create them from a running system. However, in this case, **we cannot guarantee data consistency**.” So **no** — the product does not document a safe live-SQLite snapshot.[[6]](https://docs.hetzner.com/cloud/servers/backups-snapshots/faq/)
- **Nightly copy of one directory + SQLite via cron/restic/etc.:** **NOT DOCUMENTED** by Hetzner.

---

## 2. Railway

**Long-lived background workers.** Yes, as an **always-on service** (“Background worker … Always consumes resources, even when idle”). Persistent services are “always running” (web apps, APIs, queues, DBs). Fifteen loops inside **one process** is **NOT DOCUMENTED** as a special case; it is just a process that must not exit. Cron services are the opposite: they must **exit**; cron is **not** for long-running processes. Minimum cron interval 5 minutes, UTC.[[7]](https://docs.railway.com/guides/cron-workers-queues)

**systemd.** **NOT DOCUMENTED** (no systemd, no unit files). Equivalent is **restart policy**: default **`On Failure`**, max **10** restarts; values `Always` / `On Failure` / `Never`. Paid plans: any policy and any retry count. Config field: `deploy.restartPolicyType` (`ON_FAILURE` | `ALWAYS` | `NEVER`), `restartPolicyMaxRetries`. Crash after the retry limit → status `Crashed`. `Always` is unavailable on Free/trial.[[8]](https://docs.railway.com/guides/restart-policy)

**Cost per month (USD as published; EUR conversion NOT DOCUMENTED).**
- Floor: **Hobby $5/mo** (includes $5 usage) or **Pro $20/mo**. Usage ≤ credit → you pay only the subscription. Excess is billed. Credits **do not roll over**.[[9]](https://docs.railway.com/pricing)
- Rates: **RAM $10/GB/month**, **CPU $20/vCPU/month**, **egress $0.05/GB**, **volume $0.15/GB/month**. Billed by the minute. **You pay allocated resources, not traffic** — an idle always-on worker still bills RAM/CPU. Serverless sleep is documented as the way to cut idle cost; it conflicts with 15 always-on loops. **Exact monthly $ for this app: NOT DOCUMENTED** (depends on measured RAM/CPU). Volume default cap: Hobby **5 GB**.[[10]](https://docs.railway.com/pricing/understanding-your-bill)

**TLS / custom domain.** Automatic. Add **Custom Domain** in service Settings → Public Networking; put **both** the given **CNAME** and **TXT** in DNS (TXT missing → 404). Railway issues a **Let’s Encrypt** cert (ECDSA, 90 days, renew at 30 days left). Expected issuance within an hour, tries up to 72 hours. Hobby: **2 custom domains per service**. Public ingress is **HTTP/HTTP2**; plain HTTP GET → **301 HTTPS**. TLS 1.2/1.3. **NOT DOCUMENTED:** terminating TLS yourself with certbot/Caddy on the container.[[11]](https://docs.railway.com/networking/domains/working-with-domains)

**Persistent volume backups.** Volume mount path is a directory the app can read/write. One volume per service. **Replicas cannot be used with volumes.** Redeploy of a volume-backed service has **downtime** (two deployments must not mount the same volume). Backups: manual + scheduled **Daily** (every 24h, kept **6 days**) / **Weekly** (7d, kept **27 days**) / **Monthly** (30d, kept **89 days**). Docs explicitly include “any other data stored within a volume, **such as an SQLite database**.” Incremental copy-on-write; billed at volume rates for exclusive data. Manual backups limited to **50% of volume size**. Restore: new volume mounted at the same path, old volume unmounted but kept; restore **only same project + environment**. **Wiping a volume deletes all backups.** **SQLite crash-consistency of a live writer during a volume snapshot: NOT DOCUMENTED.**[[12]](https://docs.railway.com/volumes/backups)

---

## 3. Honest trade (only what the docs support)

**Cheaper at this size.** Hetzner **CX23** has a documented **monthly cap (~€6.53 + 20% backups + IPv4)**. Railway’s always-on worker is **usage-priced** (RAM $10/GB-mo, CPU $20/vCPU-mo) with a **$5 Hobby floor**; docs state you pay while the process is up even with no HTTP traffic. A **fixed Hetzner cap vs unbounded Railway always-on** is the documented difference; a single Railway EUR total for *this* process is **NOT DOCUMENTED**.[[2]](https://docs.hetzner.com/de/general/infrastructure-and-availability/price-adjustment/)

**Less operational work.** Railway: TLS issued/renewed, restart policy, scheduled volume backups, no VM OS. Hetzner: you run Linux yourself; Hetzner does **not** document systemd/TLS/app backup steps for this stack.

**What each does *not* do that the other does**

| | Hetzner has / Railway does not | Railway has / Hetzner does not |
|---|---|---|
| OS / supervision | Full VM; systemd is yours (undocumented by Hetzner) | **No systemd.** Restart policy only. |
| TLS | You terminate TLS (not documented for this app) | Automatic Let’s Encrypt on custom domain |
| Backups | Daily **whole-disk** backups (7 slots, 20%); time **not** choosable; **consistency not guaranteed while running** | Scheduled **volume** backups with restore UI; **not** a full VM image |
| SQLite | Disk snapshot ≠ documented-safe live DB | Volume backup of the file; **live consistency NOT DOCUMENTED** |
| Networking | Arbitrary ports/protocols on the VM | Public: **HTTP(S) only** |
| Volumes | Attached volumes **excluded** from server backups | One volume/service; **no replicas** with a volume |
| Cost model | Monthly cap | Pay-for-use always-on |

---

## 4. Live SQLite — method that docs say does **not** corrupt a writer

**Do not** `cp`/`rsync` the `.db` (and hoping the WAL comes along) as the primary method. SQLite documents that a lock + file copy can block writers, and a crash mid-copy can leave a **corrupt** backup.[[13]](https://www.sqlite.org/backup.html)

Documented live methods:

**A. Online Backup API** (original live method). Copies pages; source need not stay locked for the whole copy. Completed destination is a **bitwise snapshot** of the source as of copy start. Python stdlib (3.7+): `Connection.backup(target, *, pages=-1, progress=None, name='main', sleep=0.250)` — “Works even if the database is being accessed by other clients or concurrently by the same connection.” Example: `src.backup(dst, pages=1, progress=...)`. Incremental `pages` + `sleep` matches SQLite’s “copy N pages, unlock, sleep” pattern.[[14]](https://docs.python.org/3/library/sqlite3.html)

**B. `VACUUM INTO 'file'`.** Documented as “an alternative to the backup API for generating backup copies of a **live** database.” Original file unchanged; output is a consistent, fully vacuumed copy. Destination must not exist (or be empty). Transactional snapshot, but **if interrupted by power loss the output can be incomplete/corrupt**; with `PRAGMA synchronous` NORMAL/FULL, SQLite fsyncs the output after completion. Uses more I/O than the backup API; backup API uses fewer CPU cycles and can run incrementally. Also: `sqlite3_rsync` for a live copy over SSH.[[15]](https://www.sqlite.org/lang_vacuum.html)

**Neither Hetzner disk backups nor Railway volume snapshots are documented as substituting for A or B while SQLite is writing.** Use A or B **into a file**, then copy that file (and the rest of the directory) off-box. Nightly scheduling of that job: **NOT DOCUMENTED** by either host (Railway cron can run a job that **exits**; Hetzner would be OS cron, undocumented).

Sources the model searched:

- https://docs.hetzner.com/de/general/infrastructure-and-availability/price-adjustment/
- https://docs.cost-pilot.com/cloud-providers/hetzner/
- https://costgoat.com/pricing/hetzner
- https://northflank.com/blog/hetzner-cloud-server-price-increases
- https://cloudpricecheck.com/hetzner/cloud-servers-pricing
- https://www.eucloudcost.com/providers/hetzner/
- https://cloudfleet.ai/blog/partner-news/2025-10-hetzner-cloud-introduces-new-shared-vcpu-server-families-cx-gen3-and-cpx-gen2/
- https://kuberns.com/blogs/hetzner-cloud-pricing/
- https://www.vpsbenchmarks.com/instance_types/hetzner
- https://www.vpsbenchmarks.com/hosters/hetzner
- https://docs.hetzner.com/cloud/servers/backups-snapshots/overview/
- https://docs.hetzner.com/cloud/servers/backups-snapshots/faq/
- https://docs.hetzner.com/storage/storage-box/snapshots/
- https://docs.hetzner.com/storage/storage-box/getting-started/creating-snapshots/
- https://docs.hetzner.com/de/cloud/servers/backups-snapshots/overview/
- https://docs.hetzner.com/de/storage/storage-box/snapshots/
- https://docs.hetzner.com/de/storage/storage-share/faq/backup-snapshot/
- https://docs.hetzner.com/de/cloud/servers/backups-snapshots/faq/
- https://github.com/fbrettnich/hcloud-snapshot-as-backup
- https://docs.sqlitecloud.io/docs/backup-commands
- https://docs.railway.com/pricing
- https://docs.railway.com/volumes
- https://docs.railway.com/volumes/reference
- https://docs.railway.com/pricing/plans
- https://docs.railway.com/pricing/understanding-your-bill

