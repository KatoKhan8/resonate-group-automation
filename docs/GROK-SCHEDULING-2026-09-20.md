# Grok provider research

2026-09-20T15:08:11.586859+00:00. One call per question, web_search enabled.

**CLASSIFY BEFORE BELIEVING.** Every claim below is the model's, and a confident answer is not a documented one. A point is
DOCUMENTED only where a source URL states it, OBSERVED only where this estate's own provider responses show it, and
HYPOTHESIS or UNKNOWN otherwise. Nothing here is provider truth until a readback against our own estate agrees with it.

---

## scheduling

`grok-4.6`, Nones, 63 search URLs, usage {'prompt_tokens': 475326, 'completion_tokens': 6001, 'total_tokens': 481327, 'cached_tokens': 356992, 'reasoning_tokens': 3031, 'cost_in_usd_ticks': 10473400000, 'num_sources_used': 0, 'num_server_side_tools_used': 29}.

I'll look up EmailBison's official API docs first, then pull the pages that cover campaign scheduling, sender capacity, daily limits, and warmup.
I have the docs index. Next I’ll open the campaign, sender, warmup, and OpenAPI pages that actually describe scheduling and limits.
The campaign overview is useful but incomplete. I’ll pull the OpenAPI spec and the remaining campaign, sender, and warmup pages next.
I’ll search the OpenAPI spec for scheduler, daily limits, sender capacity, and warmup fields so we only report what the spec actually defines.
I found campaign scheduler and sending-schedule endpoints. Next I’ll inspect sender-email, scheduled-email, and warmup sections of the OpenAPI spec.
I have the endpoint list. I’ll now read the sending-schedule, sender-update, and warmup-limit schemas for field names and documented behavior.
Answers are from EmailBison docs and the published OpenAPI spec only. Where those sources do not state the behaviour, the answer is **NOT DOCUMENTED**.

## 1. When campaign leads are scheduled

**What is documented**

The campaign scheduler runs in two cases: every time the campaign is **resumed**, and **at the end of every sending day**. To force a scheduler run before the end of the sending day, pause then resume.[[1]](https://docs.emailbison.com/campaigns/overview)

Sends are placed on a **random pattern** inside the campaign sending window, which is the campaign’s `schedule`.[[1]](https://docs.emailbison.com/campaigns/overview)

`POST/GET/PUT /api/campaigns/{campaign_id}/schedule` defines that window with: `monday`–`sunday` (booleans), `start_time` (`HH:MM`), `end_time` (`HH:MM`), `timezone`. Resume is `PATCH /api/campaigns/{campaign_id}/resume`. Pause is `PATCH /api/campaigns/{campaign_id}/pause`.[[2]](https://docs.emailbison.com/campaigns/creating-campaigns.md)

Adding leads to an **active** campaign: “will take up to 5 minutes for the leads to get synced.” Endpoints: `POST /api/campaigns/{campaign_id}/leads/attach-lead-list` (`lead_list_id`), `POST /api/campaigns/{campaign_id}/leads/attach-leads` (`lead_ids`).[[3]](https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign.md)

Related campaign fields on `PATCH /api/campaigns/{id}/update`:
- `max_emails_per_day` — “The maximum number of emails that can be sent per day.”
- `max_new_leads_per_day` — “The maximum number of new leads that can be added per day.”
- `sequence_prioritization` — `followups` or `new_leads`; “By default, followups are prioritized.”
- `daily_max_sends_per_receiving_domain` — “The maximum number of emails that can be sent per day to a single receiving domain.”[[4]](https://dedi.emailbison.com/api/reference.openapi)

You can **view** already-built sending volume (not the assignment algorithm) with:
- `GET /api/campaigns/sending-schedules`
- `GET /api/campaigns/{campaign_id}/sending-schedule`

Both take required body field `day`: `today` | `tomorrow` | `day_after_tomorrow`. Example response field: `emails_being_sent` (campaign-level count). The spec does not define how that count is computed.[[4]](https://dedi.emailbison.com/api/reference.openapi)

Once a lead has been sent one campaign email, “the same Sender Email will send the remaining steps for that lead, as well as emails sent to the lead from a followup campaign.”[[1]](https://docs.emailbison.com/campaigns/overview)

**NOT DOCUMENTED**
- Clock time of “end of every sending day” (end of `end_time`? midnight in `timezone`? UTC?).
- Whether new leads attached mid-day are scheduled for **today** or only after the next end-of-day/resume run (docs only say 5-minute sync + scheduler on resume / end of day).
- How leads are chosen or split across senders for a given day.
- How far ahead the scheduler assigns (the view API exposes 3 days; the scheduler text only says resume + end of sending day).
- Exact interaction of `max_emails_per_day`, `max_new_leads_per_day`, and `sequence_prioritization` on **which** leads get a slot.

## 2. Sender-level forward schedule or remaining capacity (all campaigns)

**No documented endpoint returns remaining sender capacity.** `GET /api/sender-emails/{senderEmailId}` returns `daily_limit` and `emails_sent_count`. The spec does not say `emails_sent_count` is today, remaining, or lifetime. There is no remaining-capacity field.[[4]](https://dedi.emailbison.com/api/reference.openapi)

Closest documented pieces (not a remaining-capacity API):
- `GET /api/scheduled-emails` — “retrieves all scheduled (campaign) emails.” Filters: `sender_email_ids`, `campaign_ids`, `status` (`sent|scheduled|failed|paused|stopped|bounced|unsubscribed`), `scheduled_date_local.value` (`YYYY-MM-DD`, campaign timezone), `scheduled_date_local.criteria`. Each row has `scheduled_date` / `scheduled_date_local` and nested `sender_email`. That is per-email campaign schedule, not remaining capacity.[[4]](https://dedi.emailbison.com/api/reference.openapi)
- `GET /api/sender-emails/{senderEmailId}/campaigns` — campaigns that sender is on; campaign stats only, no remaining capacity.[[4]](https://dedi.emailbison.com/api/reference.openapi)
- `GET /api/campaigns/sending-schedules` — **campaign** `emails_being_sent`, not per sender.[[4]](https://dedi.emailbison.com/api/reference.openapi)

**NOT DOCUMENTED:** an endpoint that shows one sender’s remaining daily capacity across all attached campaigns.

## 3. `max_emails_per_day` (campaign) vs `daily_limit` (sender) when one sender is on several campaigns

Documented meanings only:
- Campaign `max_emails_per_day`: “The maximum number of emails that can be sent per day.” (`PATCH /api/campaigns/{id}/update`)[[4]](https://dedi.emailbison.com/api/reference.openapi)
- Sender `daily_limit`: “The daily limit of emails that can be sent from this sender email.” (`PATCH /api/sender-emails/{senderEmailId}`; bulk `PATCH /api/sender-emails/daily-limits/bulk` with `sender_email_ids` + `daily_limit`)[[4]](https://dedi.emailbison.com/api/reference.openapi)

A sender can be attached to multiple campaigns (`POST /api/campaigns/{campaign_id}/attach-sender-emails`, `GET /api/sender-emails/{senderEmailId}/campaigns`). The docs do not say how those two caps combine.[[4]](https://dedi.emailbison.com/api/reference.openapi)

**NOT DOCUMENTED:** whether the sender `daily_limit` is shared across campaigns, whether campaign `max_emails_per_day` is applied first, min(), or independently; no allocation rule when one sender serves several campaigns.

## 4. Does mailbox warmup consume the sender `daily_limit`?

Warmup uses a **separate** setting, also named `daily_limit`, on `PATCH /api/warmup/sender-emails/update-daily-warmup-limits`: “The daily limit of warmup emails to send” (required with `sender_email_ids`). Optional `daily_reply_limit`. Other warmup routes: `GET /api/warmup/sender-emails`, `GET /api/warmup/sender-emails/{senderEmailId}`, `PATCH .../enable`, `PATCH .../disable`. List/detail examples expose `warmup_emails_sent`, not campaign `daily_limit`.[[4]](https://dedi.emailbison.com/api/reference.openapi)

Marketing copy: you set a “max daily warmup limit”; Bison ramps until that warmup max. It does not mention the sender campaign `daily_limit`.[[5]](https://emailbison.com/features/email-warmup)

**NOT DOCUMENTED:** whether warmup volume counts against the sender’s campaign `daily_limit`.

---

Primary sources: [Campaigns overview](https://docs.emailbison.com/campaigns/overview), [Creating campaigns](https://docs.emailbison.com/campaigns/creating-campaigns.md), [Adding leads](https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign.md), [OpenAPI](https://dedi.emailbison.com/api/reference.openapi), [Warmup product page](https://emailbison.com/features/email-warmup).

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
- https://docs.emailbison.com/leads/overview
- https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign
- https://docs.emailbison.com/campaigns/overview.md
- https://docs.sim.ai/integrations/emailbison
- https://docs.sim.ai/tools/emailbison
- https://docs.emailbison.com/llms.txt
- https://docs.emailbison.com/low-code-tools/clay/enrichments/import-leads-to-campaign
- https://github.com/bcharleson/emailbison-cli
- https://emailbison.com/
- https://emailbison.com/developers

