# Grok provider research

2026-09-21T09:53:47.801464+00:00. One call per question, web_search enabled.

**CLASSIFY BEFORE BELIEVING.** Every claim below is the model's, and a confident answer is not a documented one. A point is
DOCUMENTED only where a source URL states it, OBSERVED only where this estate's own provider responses show it, and
HYPOTHESIS or UNKNOWN otherwise. Nothing here is provider truth until a readback against our own estate agrees with it.

---

## empty_queue

`grok-4.6`, Nones, 80 search URLs, usage {'prompt_tokens': 760287, 'completion_tokens': 9089, 'total_tokens': 769376, 'cached_tokens': 643968, 'reasoning_tokens': 4769, 'cost_in_usd_ticks': 14083120000, 'num_sources_used': 0, 'num_server_side_tools_used': 38}.

I'll look up EmailBison's official API docs first, then pull the campaign, schedule, and sender-capacity pages so every answer is cited or marked NOT DOCUMENTED.
The campaign overview already mentions the scheduler and pause/resume. Next I’ll pull that page, the OpenAPI spec, and scheduled-email / sender endpoints so the five questions can be answered from primary docs only.
The markdown overview is truncated at the scheduler sentence. I’ll open the HTML docs, OpenAPI, and pages that name scheduled emails, sending-schedule, and resume.
Resume is documented as a scheduler trigger, not as a queue-clear. I’ll pull pause/resume, scheduled-emails, sender-capacity, and campaign-create pages next.
I’ll extract the OpenAPI definitions for pause/resume, scheduled-emails, sending-schedule, and sender-email limits next.
Pause/resume OpenAPI text is thin. I’ll pull scheduled-email, sender-email, and sending-schedule schemas, plus any help-center pages on queue rebuild.
I’ll scan the OpenAPI for queue-clear / rebuild language, then pull the remaining read-only schedule and sender-email endpoints.
Sources used: EmailBison docs (`docs.emailbison.com`) and the instance OpenAPI (`dedi.emailbison.com/api/reference.openapi`). Anything not stated there is **NOT DOCUMENTED**.

### 1. Does resume CLEAR existing scheduled emails? Does pause/resume invalidate already-scheduled messages?

**NOT DOCUMENTED** that resume clears scheduled rows. **NOT DOCUMENTED** that pause/resume invalidates already-scheduled messages.

What *is* documented:

- Scheduler **runs** (creates schedule rows) on **resume**, and at **end of every sending day**. Manual rerun = pause then resume. `https://docs.emailbison.com/campaigns/overview`[[1]](https://docs.emailbison.com/campaigns/overview)
- `PATCH /api/campaigns/{campaign_id}/resume` — “resume a paused campaign.” Example `status` after resume: `"Queued"`. No mention of deleting/rebuilding scheduled emails. `https://dedi.emailbison.com/api/reference.openapi` (`resumeCampaign`)[[2]](https://dedi.emailbison.com/api/reference.openapi)
- `PATCH /api/campaigns/{campaign_id}/pause` — “pause a campaign.” Example `status`: `"Paused"`. No mention of scheduled-email rows. Same OpenAPI.[[2]](https://dedi.emailbison.com/api/reference.openapi)
- Launch is the same resume call: `PATCH /api/campaigns/{campaign_id}/resume`. `https://docs.emailbison.com/campaigns/creating-campaigns`[[3]](https://docs.emailbison.com/campaigns/creating-campaigns.md)

Scheduled-email **status values** exist (`scheduled`, `paused`, `stopped`, plus example `"sending_paused"`), but docs never say pause/resume writes those or deletes rows. `GET /api/leads/{lead_id}/scheduled-emails` lists possible statuses including `` `scheduled`, `sending paused`, `stopped` ``. `https://dedi.emailbison.com/api/reference.openapi`
Sources: EmailBison docs and the instance OpenAPI. If the docs do not state it, the answer is **NOT DOCUMENTED**.

### 1. Does resume CLEAR existing scheduled emails? Does pause/resume invalidate already-scheduled messages?

**NOT DOCUMENTED** that resume clears scheduled rows. **NOT DOCUMENTED** that pause/resume invalidates already-scheduled messages.

Documented behaviour:

- Scheduler **runs and schedules emails** every time the campaign is **resumed**, and at the **end of every sending day**. To run it early: pause then resume. `https://docs.emailbison.com/campaigns/overview`[[1]](https://docs.emailbison.com/campaigns/overview)
- `PATCH /api/campaigns/{campaign_id}/resume` — “resume a paused campaign.” Example response `status`: `"Queued"`. No mention of deleting or rebuilding scheduled emails. `https://dedi.emailbison.com/api/reference.openapi` (`resumeCampaign`)[[2]](https://dedi.emailbison.com/api/reference.openapi)
- `PATCH /api/campaigns/{campaign_id}/pause` — “pause a campaign.” Example `status`: `"Paused"`. No mention of scheduled-email rows. Same OpenAPI.[[2]](https://dedi.emailbison.com/api/reference.openapi)
- Launch uses the same resume call. `https://docs.emailbison.com/campaigns/creating-campaigns`[[3]](https://docs.emailbison.com/campaigns/creating-campaigns.md)

Related status names exist (`scheduled`, `paused`, `stopped`; example payload `"sending_paused"`; lead endpoint text includes `` `sending paused` ``) but docs never say pause/resume writes those or deletes rows. `https://dedi.emailbison.com/api/reference.openapi` (`GET /api/leads/{lead_id}/scheduled-emails`, `GET /api/scheduled-emails`)[[2]](https://dedi.emailbison.com/api/reference.openapi)

### 2. What documented operations trigger queue regeneration, other than resume and end-of-sending-day?

**NOT DOCUMENTED.** The only documented scheduler triggers are resume and end of sending day. `https://docs.emailbison.com/campaigns/overview`[[1]](https://docs.emailbison.com/campaigns/overview)

Not documented as scheduler triggers: attaching leads, attaching/removing senders, `PUT /api/campaigns/{campaign_id}/schedule`, sequence updates, `PATCH /api/campaigns/{id}/update`.

Adjacent (not regeneration): adding leads to an **active** campaign “will take up to 5 minutes for the leads to get synced” so sending is not interrupted. `https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign`[[4]](https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign)

Removing leads: “All future scheduled emails in this campaign will be stopped (for these leads).” That is stop-on-remove, not a rebuild. OpenAPI `removeLeadsFromACampaign`. `https://dedi.emailbison.com/api/reference.openapi`[[2]](https://dedi.emailbison.com/api/reference.openapi)

### 3. Can an ACTIVE campaign hold an empty queue indefinitely? What makes the scheduler produce nothing?

**NOT DOCUMENTED** that an Active campaign may keep an empty queue indefinitely. **NOT DOCUMENTED** any conditions under which the scheduler produces zero rows.

Documented facts that do **not** answer this:

- Resume example status is `"Queued"`, not `"Active"`. List examples also show `"Active"` and `"Launching"`. List filter enum includes `queued`, `paused`, `stopped`, `completed`, `failed`, `archived`. Meaning of Active-with-empty-queue vs Queued is **NOT DOCUMENTED**. `https://dedi.emailbison.com/api/reference.openapi` (`listCampaigns`, `resumeCampaign`)[[2]](https://dedi.emailbison.com/api/reference.openapi)
- Sends are a “random pattern throughout your sending window” from campaign `schedule` (days, `start_time`, `end_time`, `timezone`). Empty window / off-day effect on the queue is **NOT DOCUMENTED**. `https://docs.emailbison.com/campaigns/overview` · `GET /api/campaigns/{campaign_id}/schedule` `https://dedi.emailbison.com/api/reference.openapi` (`viewCampaignSchedule`)[[1]](https://docs.emailbison.com/campaigns/overview)
- Caps exist as fields only: campaign `max_emails_per_day`, `max_new_leads_per_day`, `daily_max_sends_per_receiving_domain`, `sequence_prioritization` (`followups` | `new_leads`). Effect on empty rebuild is **NOT DOCUMENTED**. `https://docs.emailbison.com/campaigns/creating-campaigns` · OpenAPI campaign update.[[5]](https://docs.emailbison.com/campaigns/creating-campaigns)
- `GET .../sending-schedule` only accepts `day`: `today` | `tomorrow` | `day_after_tomorrow`. Nothing on those three days is **not** documented as “no future queue.” Field returned: `emails_being_sent`. `https://dedi.emailbison.com/api/reference.openapi` (`showSendingScheduleForCampaign`)[[2]](https://dedi.emailbison.com/api/reference.openapi)

### 4. Sender “forward commitment” to other campaigns — empty queue vs later date?

**NOT DOCUMENTED.** The phrase/concept “forward commitment” does not appear. **NOT DOCUMENTED** that a fully booked mailbox yields an empty queue rather than a later `scheduled_date`.

Documented nearby:

- Sender `daily_limit`: “The daily limit of emails that can be sent from this sender email.” No remaining-today / committed-future field. `PATCH /api/sender-emails/{senderEmailId}` body `daily_limit`. `https://dedi.emailbison.com/api/reference.openapi`[[2]](https://dedi.emailbison.com/api/reference.openapi)
- Product FAQ (not API): same senders on multiple campaigns — “sender email limits may deplete first.” Does not say empty rebuild vs later date. `https://emailbison.com/features/email-sequencing`[[6]](https://emailbison.com/features/email-sequencing)
- After a lead is sent once in a campaign, the **same sender** sends remaining steps (and followup-campaign mail to that lead). `https://docs.emailbison.com/campaigns/overview`[[1]](https://docs.emailbison.com/campaigns/overview)

### 5. Read-only endpoints for scheduling state and sender capacity

All GET. None document remaining daily capacity or cross-campaign booking.

**Queue / schedule**

| Endpoint | Documented behaviour |
|---|---|
| `GET /api/campaigns/{campaign_id}/scheduled-emails` | All scheduled emails for the campaign. Filters: `status` (`scheduled`,`sent`,`failed`,`paused`,`stopped`,`bounced`,`unsubscribed`), `scheduled_date`, `scheduled_date_local`. Fields: `id`, `status`, `scheduled_date`, `scheduled_date_local`, `sent_at`, nested `lead`, `sender_email` (`daily_limit`, `emails_sent_count`). `https://dedi.emailbison.com/api/reference.openapi` |
| `GET /api/scheduled-emails` | All scheduled campaign emails. Query: `status`, `campaign_ids`, `lead_ids`, `sender_email_ids`, `scheduled_date_local.value` (`YYYY-MM-DD`, campaign timezone) + `scheduled_date_local.criteria` (`<`,`<=`,`=`,`>`,`>=`). `https://dedi.emailbison.com/api/reference.openapi` |
| `GET /api/scheduled-emails/{id}` | One scheduled email. Same OpenAPI. |
| `GET /api/leads/{lead_id}/scheduled-emails` | Lead’s scheduled emails; statuses include `scheduled`, `sending paused`, `stopped`, `bounced`, `unsubscribed`, `replied`. Same OpenAPI. |
| `GET /api/campaigns/{campaign_id}/sending-schedule` | Body/query `day`: `today`\|`tomorrow`\|`day_after_tomorrow`. Returns `emails_being_sent`, `campaign_id`, nested `campaign`. Same OpenAPI. |
| `GET /api/campaigns/sending-schedules` | Same `day` param, all campaigns. Same OpenAPI. |
| `GET /api/campaigns/{campaign_id}/schedule` | Sending window: `monday`…`sunday`, `start_time`, `end_time`, `timezone`. `https://docs.emailbison.com/campaigns/creating-campaigns` |
| `GET /api/campaigns/{id}` | `status`, `max_emails_per_day`, `max_new_leads_per_day`, `sequence_prioritization`, `daily_max_sends_per_receiving_domain`. Same creating-campaigns page + OpenAPI. |
| `GET /api/campaigns/{campaign_id}/leads` | Campaign leads. Query `filters.lead_campaign_status`: `in_sequence`, `sequence_finished`, `sequence_stopped`, `never_contacted`, `replied`. OpenAPI `getAllLeadsForCampaign`. |

**Senders / capacity (lifetime counts, not remaining today)**

| Endpoint | Documented behaviour |
|---|---|
| `GET /api/sender-emails` | Accounts: `daily_limit`, `status`, `emails_sent_count` (not documented as today). OpenAPI `listEmailAccounts`. |
| `GET /api/sender-emails/{senderEmailId}` | Same fields. OpenAPI `showEmailAccountDetails`. |
| `GET /api/sender-emails/{senderEmailId}/campaigns` | Campaigns using that mailbox (`status`, `max_emails_per_day`, …). OpenAPI `showEmailAccountCampaigns`. |
| `GET /api/campaigns/{campaign_id}/sender-emails` | Senders on this campaign, including `daily_limit`, `emails_sent_count`, `status`. OpenAPI `getAllCampaignSenderEmails`. |

**NOT DOCUMENTED** as a read-only capacity view: remaining sends today, future booked slots, or per-mailbox commitment across campaigns. `GET .../sending-schedule` only exposes `emails_being_sent` for a 3-day horizon.

Sources the model searched:

- https://emailbison.com/features/email-sequencing
- https://docs.emailbison.com/llms.txt
- https://emailbison.com/developers
- https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign
- https://docs.sim.ai/integrations/emailbison
- https://github.com/bcharleson/emailbison-cli
- https://docs.sim.ai/tools/emailbison
- https://dedi.emailbison.com/api/reference.openapi
- https://emailbison.com/features/email-warmup
- https://github.com/emailbison-public/n8n-nodes-emailbison-official
- https://emailbison.com/
- https://www.linkedin.com/company/emailbison
- https://docs.sim.ai/triggers/emailbison
- https://context7.com/websites/dedi_emailbison_api_reference
- https://help.everlytic.com/knowledgebase/email-action-call-resume/
- https://docs.emailbison.com/campaigns/overview
- https://docs.emailbison.com/get-started/authentication
- https://docs.emailbison.com/get-started/introduction
- https://docs.emailbison.com/get-started/quickstart/making-http-requests
- https://docs.emailbison.com/llms.txt
- https://docs.emailbison.com/workspaces/overview
- https://emailbison.com/developers
- https://docs.emailbison.com/workspaces/creating-users
- https://docs.emailbison.com/webhooks/overview
- https://docs.emailbison.com/email-accounts/adding-accounts

