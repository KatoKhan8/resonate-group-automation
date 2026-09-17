# Grok provider research

2026-09-17T18:22:11.161301+00:00. One call per question, web_search enabled.

**CLASSIFY BEFORE BELIEVING.** Every claim below is the model's, and a confident answer is not a documented one. A point is
DOCUMENTED only where a source URL states it, OBSERVED only where this estate's own provider responses show it, and
HYPOTHESIS or UNKNOWN otherwise. Nothing here is provider truth until a readback against our own estate agrees with it.

---

## sender_selection

`grok-4.6`, Nones, 88 search URLs, usage {'prompt_tokens': 693729, 'completion_tokens': 6348, 'total_tokens': 700077, 'cached_tokens': 549376, 'reasoning_tokens': 3519, 'cost_in_usd_ticks': 13979640000, 'num_sources_used': 0, 'num_server_side_tools_used': 39}.

I'll look up EmailBison's official API docs and campaign/sender-account pages so every answer is sourced, not inferred.
The campaign overview already states same-sender stickiness after the first send. Next I’ll pull the OpenAPI spec and campaign/scheduled-email pages for how the first sender is chosen and what the API returns.
I’ll inspect campaign-create, scheduled-email, and sender-email OpenAPI fields next, plus the HTML docs for those same endpoints.
OpenAPI JSON wasn’t at the docs URL; I’ll pull the live spec and search it for sender-selection, scheduled-email, and campaign-update fields.
The spec is too large to read whole; I’ll regex-search it for scheduled-email objects, `sender_email_id`, and campaign-update parameters.
Scheduled-email objects already include a nested `sender_email`. I’ll now check campaign-update, lead-attach, and related endpoints for any pin/rotation parameter.
I still need campaign GET, lead scheduled-email, and webhook payload fields so the “which sender” answer is complete.
One last lookup: the sequence-step send-test path, so I can name the only documented `sender_email_id` request field exactly.
Sources: [docs.emailbison.com/campaigns/overview](https://docs.emailbison.com/campaigns/overview), [OpenAPI spec](https://dedi.emailbison.com/api/reference.openapi).

### 1. How is the sender chosen?
**First send across multiple attached inboxes: NOT DOCUMENTED.** Docs never say round-robin, random, weighted, ESP-matched, or any other picker. OpenAPI has no rotation/sticky/selection field.[[1]](https://dedi.emailbison.com/api/reference.openapi)

What *is* documented after the first send: **per-lead sticky.** “Once a lead has been sent an email in a campaign, the same Sender Email will send the remaining steps for that lead, as well as emails sent to the lead from a followup campaign.”[[2]](https://docs.emailbison.com/campaigns/overview)

Related, not sender-selection:
- Multiple inboxes are just attached as a pool via `POST /api/campaigns/{campaign_id}/attach-sender-emails` body `sender_email_ids` (array). No selection mode. https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails
- “Random pattern” in Smart Scheduling is **send time inside the campaign `schedule`**, not which inbox. https://docs.emailbison.com/campaigns/overview
- ESP matching is explicitly **unopinionated**; Bison tags the **lead’s** ESP and leaves matching vs mismatching to you. It does not say it auto-picks a sender by ESP. https://docs.emailbison.com/campaigns/overview

### 2. Multi-step sequence: same inbox or mixed?
**Same inbox for remaining steps** after that lead has already been sent one campaign email. Same inbox also used for later **followup-campaign** emails to that lead. https://docs.emailbison.com/campaigns/overview

Whether two different inboxes could ever send step 1 vs step 2 *before* any email has gone out: **NOT DOCUMENTED** (docs only bind after the first send).

### 3. Setting / field / API param to pin sender per lead or thread?
**No documented campaign/lead/thread pin.**

Checked request bodies:
- `POST /api/campaigns` — `name` (required), optional `type` (`outbound` | `reply_followup`). No sender field. https://dedi.emailbison.com/api/reference.openapi
- `PATCH /api/campaigns/{id}/update` — `name`, `max_emails_per_day`, `max_new_leads_per_day`, `daily_max_sends_per_receiving_domain`, `plain_text`, `open_tracking`, `reputation_building`, `can_unsubscribe`, `include_auto_replies_in_stats`, `sequence_prioritization` (`followups` | `new_leads`). No sender field. https://dedi.emailbison.com/api/reference.openapi
- `POST /api/campaigns/{campaign_id}/attach-sender-emails` — only `sender_email_ids`. https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails
- `POST /api/campaigns/{campaign_id}/leads/attach-leads` — `lead_ids`, optional `allow_parallel_sending`. No `sender_email_id`. https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign
- No `PATCH` on scheduled emails in the spec. https://dedi.emailbison.com/api/reference.openapi

The **only** request field that chooses a sender is a **test send**, not campaign traffic:

`POST /api/campaigns/sequence-steps/{sequence_step_id}/test-email`  
required: `sender_email_id` (“The ID of the sender email to send from.”), `to_email`; optional `use_dedicated_ips`. https://dedi.emailbison.com/api/reference.openapi

`sender_email_id` on `GET /api/campaigns/{campaign_id}/replies` and `GET /api/leads/{lead_id}/replies` is a **filter**, not a pin. https://docs.emailbison.com/master-inbox/fetching-replies.md

### 4. What the API returns for which sender sent / will send
Scheduled-email objects include a nested **`sender_email`** object (`id`, `name`, `email`, plus account fields). Present on both unsent (`status: scheduled` / `sending_paused`, `sent_at: null`) and sent records. https://dedi.emailbison.com/api/reference.openapi

| Endpoint | Sender identity in response |
|---|---|
| `GET /api/scheduled-emails` | nested `sender_email` |
| `GET /api/scheduled-emails/{id}` | nested `sender_email` |
| `GET /api/campaigns/{campaign_id}/scheduled-emails` | nested `sender_email` |
| `GET /api/leads/{lead_id}/scheduled-emails` | top-level `sender_email_id` **and** nested `sender_email` |

Lead scheduled-email example also has `campaign_id`, `lead_id`, `sequence_step_id`, `thread_reply`, `status`, `scheduled_date`, `sent_at`. https://dedi.emailbison.com/api/reference.openapi

Campaign pool listing (not per-email): `GET /api/campaigns/{campaign_id}/sender-emails` returns attached accounts (`id`, `name`, `email`, …). https://dedi.emailbison.com/api/reference.openapi

Reply objects expose `sender_email_id` (inbox that owns the message), not a “will send” assignment. https://dedi.emailbison.com/api/reference.openapi

Sources the model searched:

- https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails
- https://docs.emailbison.com/email-accounts/adding-accounts
- https://docs.emailbison.com/llms.txt
- https://docs.emailbison.com/get-started/introduction
- https://docs.emailbison.com/get-started/authentication
- https://emailbison.com/developers
- https://docs.emailbison.com/campaigns/overview.md
- https://docs.emailbison.com/leads/overview
- https://github.com/bcharleson/emailbison-cli
- https://docs.sim.ai/integrations/emailbison
- https://emailbison.com/
- https://docs.emailbison.com/email-accounts/adding-accounts.md
- https://dedi.emailbison.com/api/reference.openapi
- https://docs.sim.ai/triggers/emailbison
- https://github.com/emailbison-public/n8n-nodes-emailbison-official
- https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails
- https://dedi.emailbison.com/api/reference.openapi
- https://emailbison.com/blogs/cold-email-warmup
- https://emailbison.com/features/master-inbox
- https://docs.emailbison.com/tags/creating-tags
- https://emailbison.com/developers
- https://emailbison.com/features/email-sequencing
- https://emailbison.com/blogs/emailbison-vs-gmass
- https://docs.emailbison.com/llms.txt
- https://dedi.emailbison.com/api/reference.openapi

## timezone

`grok-4.6`, Nones, 105 search URLs, usage {'prompt_tokens': 490801, 'completion_tokens': 4652, 'total_tokens': 495453, 'cached_tokens': 391936, 'reasoning_tokens': 2741, 'cost_in_usd_ticks': 9982200000, 'num_sources_used': 0, 'num_server_side_tools_used': 31}.

**1. Sending window timezone: campaign timezone**

The sending window is the campaign’s `schedule` (`monday`–`sunday`, `start_time`, `end_time`, `timezone`). Docs say emails go out on a random pattern throughout that window.[[1]](https://docs.emailbison.com/campaigns/overview.md)

`timezone` is documented only as **“The timezone of the schedule.”** Create/update: `POST`/`PUT` `/api/campaigns/{campaign_id}/schedule`. Allowed IANA ids come from `GET` `/api/campaigns/schedule/available-timezones` (“use an ID from this list whenever you're working on Campaign Schedules”).[[2]](https://dedi.emailbison.com/api/reference.openapi)

Scheduled-email filter `scheduled_date_local.value`: **“The timezone is the campaign's timezone.”** Format `YYYY-MM-DD`. That is the only documented interpretation of “local” send time.[[2]](https://dedi.emailbison.com/api/reference.openapi)

Workspace timezone and recipient timezone for the window: **NOT DOCUMENTED**.

**2. Recipient-local sending (“timezone-aware” / “prospect local time”)**

**NOT DOCUMENTED** in the API or product docs as a send mode. There is no schedule flag, campaign setting, or lead field for it. The documented send clock is the campaign `schedule.timezone` (above).

Webhook/examples expose `scheduled_date_est`, `scheduled_date_local`, and `local_timezone` on scheduled emails; the API still defines `scheduled_date_local` against **the campaign’s timezone**.[[2]](https://dedi.emailbison.com/api/reference.openapi)

A marketing FAQ claims “timezone-based scheduling, automatically sending emails based on each prospect's local time.” That is not described in the API/docs (no mechanism). Do not build on it.[[3]](https://emailbison.com/blogs/emailbison-vs-woodpecker)

Liquid copy (“Good morning/afternoon/evening based on timezones”) is content variation, not send-time.[[4]](https://emailbison.com/features/email-sequencing)

**3. Per-lead timezone**

**NOT DOCUMENTED.** No lead timezone field; none is inferred.

Create/update lead fields: `first_name`, `last_name`, `email`, `title`, `company`, `notes`, `custom_variables`. Required: `first_name`, `email`. Same in the docs page. Responses add `id`, `uuid`, `status`, `lead_campaign_data`, `overall_stats`, timestamps — still no timezone.[[2]](https://dedi.emailbison.com/api/reference.openapi)

`custom_variables` are arbitrary name/value pairs. They are **not** documented as driving send timezone.[[5]](https://docs.emailbison.com/leads/custom-variables)

**4. Changing schedule/timezone after the campaign is running**

You can update a campaign schedule (including `timezone`, days, `start_time`, `end_time`) with `PUT` `/api/campaigns/{campaign_id}/schedule`. Description: “update the schedule of the campaign.” No documented restriction by campaign status (`Active` / `Paused` / etc.). `GET` `/api/campaigns/{campaign_id}/schedule` reads it. Templates: `GET` `/api/campaigns/schedule/templates`, `POST` `/api/campaigns/{campaign_id}/create-schedule-from-template` (`schedule_id`).[[2]](https://dedi.emailbison.com/api/reference.openapi)

**What happens to already-scheduled emails: NOT DOCUMENTED.** The PUT does not say it reschedules, keeps, or drops existing `scheduled` rows.

Related scheduler behavior only: it schedules on campaign resume and at the end of each sending day; pause then resume can force a scheduler run before end of day. That is not documented as applying to a live schedule/timezone edit.[[1]](https://docs.emailbison.com/campaigns/overview.md)

Sources: [campaigns overview](https://docs.emailbison.com/campaigns/overview.md), [creating campaigns](https://docs.emailbison.com/campaigns/creating-campaigns.md), [creating a lead](https://docs.emailbison.com/leads/creating-a-lead.md), [OpenAPI](https://dedi.emailbison.com/api/reference.openapi).

Sources the model searched:

- https://docs.emailbison.com/campaigns/overview.md
- https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign
- https://docs.emailbison.com/get-started/authentication
- https://docs.emailbison.com/llms.txt
- https://emailbison.com/developers
- https://dedi.emailbison.com/api/reference.openapi
- https://github.com/bcharleson/emailbison-cli
- https://docs.sim.ai/integrations/emailbison
- https://docs.sim.ai/triggers/emailbison
- https://dedi.emailbison.com/api/reference.openapi
- https://emailbison.com/
- https://docs.withampersand.com/provider-guides/emailBison
- https://docs.emailbison.com/email-accounts/adding-accounts
- https://context7.com/websites/dedi_emailbison_api_reference
- https://docs.sim.ai/tools/emailbison
- https://docs.emailbison.com/campaigns/overview.md
- https://docs.sim.ai/triggers/emailbison
- https://github.com/bcharleson/emailbison-cli
- https://academy.optimove.com/hc/en-us/articles/8782199157789-Sending-by-Customer-Local-Time-Zone-in-Email
- https://www.scaledmail.com/alternatives/emailbison
- https://prospeo.io/s/cold-email-time-zone
- https://emailbison.com/
- https://docs.emailbison.com/llms.txt
- https://dedi.emailbison.com/api/reference.openapi
- https://emailbison.com/features/email-warmup

## webhooks

`grok-4.6`, Nones, 75 search URLs, usage {'prompt_tokens': 224402, 'completion_tokens': 3555, 'total_tokens': 227957, 'cached_tokens': 169856, 'reasoning_tokens': 2357, 'cost_in_usd_ticks': 5157000000, 'num_sources_used': 0, 'num_server_side_tools_used': 17}.

**Yes, EmailBison supports webhooks.** Official docs list many events; relevant ones matching your list:

- **Email sent**: "Email Sent" (campaign emails only); also "Manual Email Sent".[[1]](https://docs.emailbison.com/webhooks/when-are-webhooks-triggered)
- **Opened**: "Email Opened" (requires campaign `track opens` enabled).[[1]](https://docs.emailbison.com/webhooks/when-are-webhooks-triggered)
- **Replied**: "Contact Replied" (campaign leads; skips auto-replies if campaign setting `Include auto replies in stats` is off); also "Untracked Reply Received".[[1]](https://docs.emailbison.com/webhooks/when-are-webhooks-triggered)
- **Bounced**: "Email Bounced" (campaign emails).[[1]](https://docs.emailbison.com/webhooks/when-are-webhooks-triggered)
- **Unsubscribed**: "Contact Unsubscribed".[[1]](https://docs.emailbison.com/webhooks/when-are-webhooks-triggered)
- **Lead status change**: NOT DOCUMENTED (no general event). Closest documented: "Contact Interested" (reply marked interested via inbox/API/AI) and "Tag Attached"/"Tag Removed".[[1]](https://docs.emailbison.com/webhooks/when-are-webhooks-triggered)

Full event list and trigger conditions: https://docs.emailbison.com/webhooks/when-are-webhooks-triggered

View events + sample payloads in-app: Settings → Webhooks → New Webhook URL.[[2]](https://docs.emailbison.com/webhooks/overview)

**Configuration**: Primarily in-app (Settings → Webhooks → New Webhook URL: name, URL, select events). Also via API: POST `/api/webhooks` (listed among selected endpoints). Test events: in-app "Send test webhook" or POST `/api/webhook-events/test-event`.[[3]](https://emailbison.com/developers)

Failed deliveries retry up to 5 times over 24 hours. Attempts time out after 15 seconds; can resend via UI (Settings → Events) or API. Past events (last 10 days) via Settings → Events or `/api/events`.[[4]](https://docs.emailbison.com/webhooks/events-deliveries-and-attempts)

**Payload shape** (documented sample for TAG_ATTACHED; other events similar with event-specific `data`):

```json
{
  "event": {
    "type": "TAG_ATTACHED",
    "name": "Tag Attached",
    "instance_url": "https://dedi.emailbison.com",
    "workspace_id": 2,
    "workspace_name": "Red Team"
  },
  "data": {
    "tag_id": 1,
    "tag_name": "Interested",
    "taggable_id": 20,
    "taggable_type": "Campaign"
  }
}
```

Samples also previewed in-app per event.[[3]](https://emailbison.com/developers)

**Signature verification**: NOT DOCUMENTED.

**Push/streaming alternative to polling replies**: Webhooks (Contact Replied / Untracked Reply Received events) are the documented push mechanism. Polling: GET `/api/replies`. No WebSockets, SSE, or other streaming documented.[[1]](https://docs.emailbison.com/webhooks/when-are-webhooks-triggered)

Docs index: https://docs.emailbison.com/llms.txt  
Webhook overview: https://docs.emailbison.com/webhooks/overview  
Events/deliveries: https://docs.emailbison.com/webhooks/events-deliveries-and-attempts  
Developers page: https://emailbison.com/developers

Sources the model searched:

- https://docs.emailbison.com/webhooks/overview
- https://docs.emailbison.com/llms.txt
- https://docs.emailbison.com/get-started/quickstart/making-http-requests
- https://docs.emailbison.com/get-started/authentication
- https://emailbison.com/developers
- https://outboundsync.com/docs/integrations/engagement/emailbison/webhooks/emailbison-webhook-guide/
- https://docs.sim.ai/triggers/emailbison
- https://emailbison.com/
- https://docs.withampersand.com/provider-guides/emailBison
- https://docs.emailbison.com/email-accounts/adding-accounts
- https://github.com/bcharleson/emailbison-cli
- https://docs.sim.ai/integrations/emailbison
- https://context7.com/websites/dedi_emailbison_api_reference
- https://outboundsync.com/docs/integrations/engagement/emailbison/authentication/connect-your-emailbison-api-key/
- https://outboundsync.com/blog/emailbison-tag-attached-events-now-supported/
- https://docs.emailbison.com/get-started/authentication
- https://docs.emailbison.com/get-started/introduction
- https://docs.emailbison.com/get-started/quickstart/making-http-requests
- https://docs.emailbison.com/llms.txt
- https://docs.emailbison.com/workspaces/overview
- https://emailbison.com/developers
- https://docs.emailbison.com/workspaces/creating-users
- https://docs.emailbison.com/webhooks/overview
- https://docs.emailbison.com/email-accounts/adding-accounts
- https://docs.emailbison.com/low-code-tools/clay/workspace-setup

