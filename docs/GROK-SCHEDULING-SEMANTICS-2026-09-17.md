# EmailBison scheduling semantics, asked because 487 queued six days out

2026-09-17T19:51:26.408836+00:00. Grok with web_search, 50 sources.

Classify before believing: DOCUMENTED only where a source URL states it. Provider readback stays authoritative over any claim here.

---

I'll pull EmailBison's OpenAPI spec and docs and search those sources only for scheduled_date, wait_in_days, sender attach/detach, and capacity.
The spec is large; I’ll search it and the campaign docs for `scheduled_date`, `wait_in_days`, `daily_limit`, and sender attach/detach behavior.
I have the scheduler overview and field names; next I’ll pull the OpenAPI descriptions for attach/remove senders, `wait_in_days`, `daily_limit`, and any capacity fields.
I’ll pull the remaining OpenAPI paths (`sending-schedules`, scheduled-emails, sender campaigns) and any help-center text on how first-step wait and daily limits work.
I’ll grab sender-email and campaign-limit field descriptions plus the HTML campaign overview, which looked truncated.
I have the spec and docs coverage; remaining points that aren’t in those sources will be marked `NOT DOCUMENTED`.

**1. How `scheduled_date` is computed for the FIRST sequence step / does `daily_limit` push leads to a later day**

**How `scheduled_date` is computed: NOT DOCUMENTED.** The OpenAPI spec exposes `scheduled_date` / `scheduled_date_local` on scheduled-email objects and does not describe the algorithm that sets them.[[1]](https://dedi.emailbison.com/api/reference.openapi)

What *is* documented about scheduling:

- The campaign scheduler runs and schedules emails **every time the campaign is resumed**, and **at the end of every sending day**. Pause+resume is documented as the way to run the scheduler early.[[2]](https://docs.emailbison.com/campaigns/overview)
- “Smart scheduling”: campaign emails are sent on a **random pattern throughout the sending window** from the campaign’s `schedule`.[[2]](https://docs.emailbison.com/campaigns/overview)
- Sender `daily_limit` is documented only as: **“The daily limit of emails that can be sent from this sender email.”** (`PATCH /api/sender-emails/{senderEmailId}`, body field `daily_limit`). It does not say how that limit is applied when computing `scheduled_date`.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- Campaign-level caps that exist as settings (not a scheduler formula): `max_emails_per_day` = “The maximum number of emails that can be sent per day”; `max_new_leads_per_day` = “The maximum number of new leads that can be added per day”; `sequence_prioritization` = “How the campaign sequence should be prioritized. By default, followups are prioritized.” (`followups` | `new_leads`). (`PATCH /api/campaigns/{campaign_id}/update`)[[1]](https://dedi.emailbison.com/api/reference.openapi)

**Does a sender’s `daily_limit`, shared across campaigns, push first-step leads to a later day when nearer days are fully booked? NOT DOCUMENTED.**

**Is the daily limit enforced per mailbox per day across campaigns?** The OpenAPI wording is mailbox-scoped (“from this sender email”), not campaign-scoped. A marketing FAQ says if the same sender emails are used across multiple campaigns, “sender email limits may deplete first.” It does **not** document overflow-to-later-day scheduling.[[3]](https://emailbison.com/features/email-sequencing)

---

**2. What `wait_in_days` on the FIRST sequence step means**

OpenAPI field description is only: **“The days to wait.”** Type integer; required on sequence-step create (`email_subject`, `email_body`, `wait_in_days`). Same text on deprecated `/api/campaigns/{campaign_id}/sequence-steps` and Campaigns v1.1 create. Examples put `wait_in_days: 1` on the `order: 1` step.[[1]](https://dedi.emailbison.com/api/reference.openapi)

**Whether that is a delay before the first email, or the gap until the next step: NOT DOCUMENTED.**

---

**3. Existing `/campaigns/{id}/scheduled-emails` rows when senders are attached/removed**

**Fate of already-scheduled rows (rescheduled / reassigned / dropped / left pointing at a detached sender): NOT DOCUMENTED.**

What *is* documented:

- `POST /api/campaigns/{campaign_id}/attach-sender-emails` — “attach sender emails to a campaign.” Body: `sender_email_ids`. Success example: `"Sender emails successfully added to Campaign One."` No mention of scheduled emails or reschedule.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- `DELETE /api/campaigns/{campaign_id}/remove-sender-emails` — **“remove sender emails from a draft or paused campaign.”** Success example: `"Sender emails sent for deletion. This may take a moment."` No mention of scheduled-email rows. The documented scope is **draft or paused**, not an active/running campaign.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- The docs page for these endpoints only documents the request body (`sender_email_ids`); it does not describe scheduler side effects. Note: that page’s remove example uses `--request POST` while the OpenAPI method is `DELETE`.[[4]](https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails.md)
- Stickiness **after a send has already happened**: “Once a lead has been **sent** an email in a campaign, the same Sender Email will send the remaining steps for that lead, as well as emails sent to the lead from a followup campaign.” That is about remaining steps after a send, not about queued/`scheduled` rows when the mailbox set changes.[[2]](https://docs.emailbison.com/campaigns/overview)

**Documented warning about changing senders on a running campaign: NOT DOCUMENTED** (beyond remove being specified only for draft/paused).

---

**4. Endpoint/field for a sender email’s remaining capacity or forward schedule across all campaigns**

**Remaining capacity field (e.g. remaining daily slots): NOT DOCUMENTED.**  
`GET /api/sender-emails/{senderEmailId}` returns `daily_limit` and `emails_sent_count` (example `100`); there is no remaining-today / remaining-capacity field and `emails_sent_count` is not described as remaining or as today’s count.[[1]](https://dedi.emailbison.com/api/reference.openapi)

Closest documented surfaces (none of these are “remaining capacity”):

- `GET /api/campaigns/sending-schedules` — “view the sending schedules for campaigns.” Required body `day`: `today` | `tomorrow` | `day_after_tomorrow`. Response field `emails_being_sent` is **per campaign**, not per sender. Same for `GET /api/campaigns/{campaign_id}/sending-schedule`.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- `GET /api/scheduled-emails` — “retrieves all scheduled (campaign) emails.” Query filters include `sender_email_ids`, `campaign_ids`, `status` (`sent` | `scheduled` | `failed` | `paused` | `stopped` | `bounced` | `unsubscribed`), and `scheduled_date_local` (`YYYY-MM-DD` in the campaign timezone, with `criteria` `<` `<=` `=` `>` `>=`). Each row includes `scheduled_date` and nested `sender_email`. That lists queued/sent rows, not remaining capacity. Campaign-scoped twin: `GET /api/campaigns/{campaign_id}/scheduled-emails`.[[1]](https://dedi.emailbison.com/api/reference.openapi)
- `GET /api/sender-emails/{senderEmailId}/campaigns` — “Retrieves a collection of campaigns where this email account is being used.” No capacity or schedule.[[1]](https://dedi.emailbison.com/api/reference.openapi)

---

**5. Does attaching an additional sender to a running campaign reschedule already-queued emails?**

**NOT DOCUMENTED.** `POST /api/campaigns/{campaign_id}/attach-sender-emails` only documents attaching IDs; it does not mention queued emails, `scheduled_date`, or reschedule. Scheduler runs on resume and at end of sending day; attach is not listed as a scheduler trigger.[[1]](https://dedi.emailbison.com/api/reference.openapi)

---

Sources used: [OpenAPI spec](https://dedi.emailbison.com/api/reference.openapi), [campaigns overview](https://docs.emailbison.com/campaigns/overview), [attach/remove senders](https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails), [creating campaigns](https://docs.emailbison.com/campaigns/creating-campaigns), [sequencing FAQ](https://emailbison.com/features/email-sequencing).

## Sources searched

- https://docs.emailbison.com/email-accounts/adding-accounts.md
- https://docs.emailbison.com/get-started/quickstart/making-http-requests
- https://docs.emailbison.com/workspaces/overview
- https://docs.emailbison.com/get-started/authentication
- https://docs.emailbison.com/leads/custom-variables
- https://docs.emailbison.com/llms.txt
- https://docs.emailbison.com/tags/removing-tags
- https://docs.emailbison.com/master-inbox/fetching-replies.md
- https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign
- https://docs.emailbison.com/workspaces/creating-users
- https://docs.emailbison.com/webhooks/overview
- https://docs.emailbison.com/leads/overview
- https://docs.emailbison.com/get-started/introduction
- https://docs.emailbison.com/low-code-tools/clay/workspace-setup
- https://docs.emailbison.com/low-code-tools/clay/enrichments/create-or-update-lead
- https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails
- https://docs.emailbison.com/llms.txt
- https://docs.emailbison.com/email-accounts/adding-accounts
- https://docs.emailbison.com/tags/removing-tags
- https://docs.emailbison.com/campaigns/overview.md
- https://docs.emailbison.com/workspaces/overview
- https://docs.emailbison.com/master-inbox/fetching-replies.md
- https://docs.emailbison.com/tags/creating-tags
- https://docs.emailbison.com/webhooks/overview
- https://docs.emailbison.com/email-accounts/adding-accounts.md
- https://emailbison.com/features/email-sequencing
- https://docs.sim.ai/integrations/emailbison
- https://github.com/bcharleson/emailbison-cli
- https://docs.sim.ai/triggers/emailbison
- https://docs.emailbison.com/get-started/authentication
