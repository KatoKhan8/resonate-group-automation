# Grok provider research

2026-09-21T09:40:43.594962+00:00. One call per question, web_search enabled.

**CLASSIFY BEFORE BELIEVING.** Every claim below is the model's, and a confident answer is not a documented one. A point is
DOCUMENTED only where a source URL states it, OBSERVED only where this estate's own provider responses show it, and
HYPOTHESIS or UNKNOWN otherwise. Nothing here is provider truth until a readback against our own estate agrees with it.

---

## sender_selection

`grok-4.6`, Nones, 85 search URLs, usage {'prompt_tokens': 556017, 'completion_tokens': 5082, 'total_tokens': 561099, 'cached_tokens': 447744, 'reasoning_tokens': 2929, 'cost_in_usd_ticks': 11118200000, 'num_sources_used': 0, 'num_server_side_tools_used': 34}.

**1. How the sender is chosen**

**NOT DOCUMENTED** for the first email (no round-robin / random / configurable algorithm in the API docs or OpenAPI).

After the first send, selection is **per-lead sticky**: once a lead has been sent an email in a campaign, **the same Sender Email sends the remaining steps**, and also emails to that lead from a **followup campaign**.[[1]](https://docs.emailbison.com/campaigns/overview)

https://docs.emailbison.com/campaigns/overview

Multiple senders are attached at **campaign** level only (`POST /api/campaigns/{campaign_id}/attach-sender-emails`, body `sender_email_ids`). No selection mode is documented on that endpoint.[[2]](https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails)

https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails

Campaign `PATCH /api/campaigns/{id}/update` fields are `name`, `max_emails_per_day`, `max_new_leads_per_day`, `daily_max_sends_per_receiving_domain`, `plain_text`, `open_tracking`, `reputation_building`, `can_unsubscribe`, `include_auto_replies_in_stats`, `sequence_prioritization` (`followups` | `new_leads`). None control sender rotation.[[3]](https://docs.emailbison.com/campaigns/creating-campaigns)

https://docs.emailbison.com/campaigns/creating-campaigns  
OpenAPI: https://dedi.emailbison.com/api/reference.openapi

---

**2. Multi-step sequence: same inbox or different?**

Documented: **same sender inbox** for remaining steps after the first campaign email to that lead (and for followup-campaign emails to that lead).[[1]](https://docs.emailbison.com/campaigns/overview)

https://docs.emailbison.com/campaigns/overview

Whether different steps *can* come from different inboxes before that first send, or if the first sender is later swapped: **NOT DOCUMENTED**.

Sequence-step create (`POST /api/campaigns/{campaign_id}/sequence-steps`) fields are `title`, `email_subject`, `email_body`, `wait_in_days`, `variant`, `variant_from_step`, `thread_reply`, `order`. No per-step sender field.[[3]](https://docs.emailbison.com/campaigns/creating-campaigns)

https://docs.emailbison.com/campaigns/creating-campaigns

---

**3. Setting / field / API param to pin sender per lead or thread?**

**NOT DOCUMENTED** for campaign sequence sends.

Checked and absent:
- Attach senders: campaign-level `sender_email_ids` only. https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails
- Attach leads: `lead_ids` + optional `allow_parallel_sending` only. No `sender_email_id`. https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign  
  OpenAPI: https://dedi.emailbison.com/api/reference.openapi (`POST /api/campaigns/{campaign_id}/leads/attach-leads`)
- Campaign update / sequence steps: no pin field (see above).

The only documented sender-pick parameter is **test send**, not production sequencing: body requires `sender_email_id` and `to_email` (`use_dedicated_ips` optional). Path is a sequence-step id; marketing lists `POST /api/campaigns/sequence-steps/{id}/send-test`. https://emailbison.com/developers  
OpenAPI: https://dedi.emailbison.com/api/reference.openapi

---

**4. What the API returns that identifies the sender**

Scheduled/sent campaign emails expose the sender as a nested **`sender_email`** object (`id`, `name`, `email`, plus account fields). Present in examples even when `status` is `scheduled` and `sent_at` is null.

| Endpoint | Sender identifier |
|---|---|
| `GET /api/campaigns/{campaign_id}/scheduled-emails` | nested `sender_email` (`id`, `name`, `email`, …) |
| `GET /api/scheduled-emails` | nested `sender_email`; filter query `sender_email_ids` |
| `GET /api/scheduled-emails/{id}` | nested `sender_email` |
| `GET /api/leads/{lead_id}/sent-emails` | field `sender_email_id` |
| Replies (`GET /api/replies`, campaign/lead replies) | field `sender_email_id` |

OpenAPI: https://dedi.emailbison.com/api/reference.openapi  
Lead sent-emails also: https://docs.emailbison.com/master-inbox/fetching-replies (`GET /api/leads/{lead_id_or_email}/sent-emails`)

There is **no documented PATCH** to set/change the sender on a scheduled email.

Sources the model searched:

- https://docs.emailbison.com/campaigns/adding-and-removing-sender-emails
- https://docs.emailbison.com/email-accounts/adding-accounts
- https://docs.emailbison.com/llms.txt
- https://emailbison.com/developers
- https://docs.emailbison.com/get-started/introduction
- https://docs.emailbison.com/get-started/authentication
- https://docs.emailbison.com/leads/overview
- https://docs.sim.ai/integrations/emailbison
- https://github.com/bcharleson/emailbison-cli
- https://docs.emailbison.com/tags/creating-tags
- https://dedi.emailbison.com/api/reference.openapi
- https://emailbison.com/
- https://docs.sim.ai/tools/emailbison
- https://github.com/emailbison-public/n8n-nodes-emailbison-official
- https://outboundsync.com/docs/integrations/engagement/emailbison/authentication/connect-your-emailbison-api-key/
- https://docs.emailbison.com/get-started/authentication
- https://emailbison.com/resources/podcast-email
- https://emailbison.com/blogs/google-workspace-vs-microsoft-365
- https://dedi.emailbison.com/api/reference.openapi
- https://docs.emailbison.com/get-started/quickstart/making-http-requests
- https://emailbison.com/blogs/cold-email-secondary-domains
- https://emailbison.com/blogs/cold-email-open-rates
- https://emailbison.com/blogs/emailbison-vs-quickmail
- https://emailbison.com/blogs/shared-ip-address-vs-dedicated-ip-address
- https://emailbison.com/blogs/emailbison-vs-woodpecker

