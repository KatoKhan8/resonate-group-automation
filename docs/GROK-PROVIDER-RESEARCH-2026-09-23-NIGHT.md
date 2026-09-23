# Grok provider research

2026-09-23T19:47:16.665966+00:00. One call per question, web_search enabled.

**CLASSIFY BEFORE BELIEVING.** Every claim below is the model's, and a confident answer is not a documented one. A point is
DOCUMENTED only where a source URL states it, OBSERVED only where this estate's own provider responses show it, and
HYPOTHESIS or UNKNOWN otherwise. Nothing here is provider truth until a readback against our own estate agrees with it.

---

## bison_variable_rendering

`grok-4.6`, Nones, 113 search URLs, usage {'prompt_tokens': 976585, 'completion_tokens': 6549, 'total_tokens': 983134, 'cached_tokens': 843264, 'reasoning_tokens': 4396, 'cost_in_usd_ticks': 17251360000, 'num_sources_used': 0, 'num_server_side_tools_used': 54}.

I'll look up EmailBison's official API docs and specifically the sequence-step / scheduled-email rendering path.
Found the official docs and OpenAPI spec. Next I’ll pull the index, custom-variables, sequence-step, and scheduled-email pages.
Pulling the OpenAPI spec and campaign/sequence pages next — those should name the scheduled-email and render endpoints.
OpenAPI JSON 404’d. Trying the live API reference and searching it for scheduled-emails and sequence-step fields.
There's a BisonSphere help article on Liquid/spintax. I'll open that and the OpenAPI scheduled-email paths next.
Liquid docs confirm `{VAR}` replacement before Liquid parse. Next I’ll extract scheduled-email endpoints and any empty-render / fallback rules.
Need the scheduled-email schema, test-email route, and help-center sequence/lead articles.
Help-center sequence articles look useful. Opening preview, test-email, custom-variables, and failed-send pages, plus remaining OpenAPI routes.
Official sources: [EmailBison API docs](https://docs.emailbison.com/llms.txt), [OpenAPI spec](https://dedi.emailbison.com/api/reference.openapi), [Liquid/Spintax help](https://help.bisonsphere.com/en/articles/184-liquid-syntax-spintax-how-to-use-and-templates). Behaviours not in those sources are marked **NOT DOCUMENTED**.

---

### 1. When are per-lead custom variables injected, and what is the syntax?

**Injection timing (enrollment vs queue build vs send): NOT DOCUMENTED.** Docs never name those three stages.

What is documented:

- Custom variables live on the lead as `{name, value}` pairs, created first via `POST /api/custom-variables` (`name` only), then attached on `POST`/`PUT` `/api/leads`. They are workspace-scoped.

Sources the model searched:

- https://emailbison.com/features/email-sequencing
- https://docs.emailbison.com/get-started/quickstart/making-http-requests
- https://docs.emailbison.com/get-started/introduction
- https://docs.emailbison.com/get-started/authentication
- https://docs.emailbison.com/llms.txt
- https://github.com/bcharleson/emailbison-cli
- https://emailbison.com/developers
- https://docs.emailbison.com/email-accounts/adding-accounts
- https://docs.emailbison.com/campaigns/adding-leads-to-a-campaign
- https://dedi.emailbison.com/api/reference.openapi
- https://emailbison.com/
- https://docs.withampersand.com/provider-guides/emailBison
- https://outboundsync.com/docs/integrations/engagement/emailbison/authentication/connect-your-emailbison-api-key/
- https://github.com/emailbison-public/n8n-nodes-emailbison-official
- https://context7.com/websites/dedi_emailbison_api_reference
- https://docs.emailbison.com/leads/custom-variables
- https://emailbison.com/
- https://dedi.emailbison.com/api/reference.openapi
- https://emailbison.com/resources/podcast-email
- https://docs.emailbison.com/low-code-tools/clay/enrichments/create-or-update-lead
- https://emailbison.com/blogs/dedicated-email-infrastructure
- https://docs.emailbison.com/llms.txt
- https://emailbison.com/features/unlimited-leads-storage
- https://emailbison.com/blogs/emailbison-vs-woodpecker
- https://emailbison.com/blogs/email-warmup-tools

## heyreach_ai_replies

`grok-4.6`, Nones, 200 search URLs, usage {'prompt_tokens': 713034, 'completion_tokens': 6957, 'total_tokens': 719991, 'cached_tokens': 576384, 'reasoning_tokens': 3723, 'cost_in_usd_ticks': 13864680000, 'num_sources_used': 0, 'num_server_side_tools_used': 36}.

**Bottom line:** HeyReach’s own docs do **not** describe a native “auto-send AI replies” switch (per seat, campaign, or workspace). What they document is (a) campaign sequence messages that **end on a prospect reply**, (b) **AI auto-tags** on inbound replies, and (c) MCP/n8n/Make agents that **draft** replies and only send after approval or via `inbox/SendMessage`. Whether a **STOPPED** lead can still get an AI/inbox send is **NOT DOCUMENTED**. That gap is the risk you described.[[1]](https://www.heyreach.io/blog/beginners-guide-heyreach-mcp)

---

### 1. Where AI / automatic replies are configured, and at what scope

**Native auto-send AI replies (product toggle): NOT DOCUMENTED.**  
Public API collections and campaign create/update DTOs have no AI-reply / auto-reply setting. Official API surface is Campaigns, Inbox, LinkedInAccounts, Lists, Analytics, Leads, LeadTags, Webhooks, MyNetwork, Organization, Enrichment, Blacklist.  
https://documenter.getpostman.com/view/23808049/2sA2xb5F75

**What *is* documented, and its scope:**

| Capability | Where configured | Scope | What docs actually say |
|---|---|---|---|
| **HeyReach MCP (draft replies)** | Workspace **Integrations** → copy MCP key | **Per workspace** (“Each workspace… dedicated MCP endpoints”) | Unibox “can now suggest responses automatically.” Agent “drafts a short reply… presents it for approval before sending. **Nothing goes out without human review.**” https://www.heyreach.io/blog/beginners-guide-heyreach-mcp |
| **MCP Inbox Manager** | Prompted in Claude via MCP, not a HeyReach UI toggle | Tied to a named LinkedIn account in the prompt | “Claude **always requires user confirmation before sending.**” https://www.youtube.com/watch?v=YRJ0QFa4tK8 |
| **Positive Reply Rate** | “No setup required. Just open your dashboard” | Product-wide (not documented as per-seat) | **Auto-tags** inbound replies Interested / Generic / Negative. Does **not** send replies. Auto-tag is locked. Webhooks: Auto-tag Positive / Generic / Negative. https://www.heyreach.io/blog/positive-reply-rate-auto-detect-warm-leads |
| **Campaign sequence messages** | Campaign sequence builder / `UpdateSequence` | **Per campaign** | `MESSAGE` / `INMAIL` nodes: “conditional (when there is a reply must be an END node)”. Follow-ups in the sequence stop when the lead replies. Not AI generation. https://www.heyreach.io/blog/campaign-api |
| **Inbox privacy** | When **connecting a LinkedIn account** | **Per seat (LinkedIn account)** | “Configure your Inbox privacy.” Not an AI-reply setting. https://help.heyreach.io/en/articles/10665739-how-to-activate-the-infinite-login-on-heyreach |
| **Make “REPLY AGENT” on autopilot** | Make scenario (HeyReach-hosted template) | External to HeyReach | Custom Make agent “analyzes sentiment… then generates contextual replies.” Not a HeyReach seat/campaign flag. https://www.heyreach.io/make-automation-template/identify-positive-replies-respond-to-leads-on-autopilot |

MCP setup steps in vendor docs: **Integrations** in the HeyReach workspace → copy MCP key. That is workspace-scoped, not per campaign.  
https://www.heyreach.io/blog/beginners-guide-heyreach-mcp

**Per-seat vs per-campaign AI auto-reply setting: NOT DOCUMENTED.**

---

### 2. Does the API expose AI/auto-reply enabled? Can you read it or turn it off?

**NOT DOCUMENTED** — no endpoint or field for “AI reply enabled” / “auto-reply enabled” on a seat or campaign.

Documented campaign fields on `POST /api/public/campaign/GetAll` include `id`, `name`, `creationTime`, `linkedInUserListName`, `linkedInUserListId`, `campaignAccountIds`, `status`, `progressStats`, `excludeAlreadyMessagedGlobal`, `excludeAlreadyMessagedCampaignAccounts`, `excludeFirstConnectionCampaignAccounts`, `excludeFirstConnectionGlobal`, `excludeNoProfilePicture`, `excludeListId`. None are AI/auto-reply.  
https://documenter.getpostman.com/view/23808049/2sA2xb5F75

`POST /api/public/campaign/Create` and `UpdateSettings` fields: `name`, `linkedInUserListId`, `linkedInAccountIds`, exclusion flags, `schedule`, `sequence`. No AI-reply flag. No documented update that disables AI replies.  
https://www.heyreach.io/blog/campaign-api

Inbox write path that *would* send a reply (human, MCP, or third-party AI):

- `POST /api/public/inbox/SendMessage`  
https://documenter.getpostman.com/view/23808049/2sA2xb5F75

There is **no documented API to turn off AI/auto-reply**, because there is no documented AI/auto-reply resource.

Closest related APIs (not AI-reply toggles):

- `POST /api/public/campaign/StopLeadInCampaign` — stop a lead **in a campaign**  
- `POST /api/public/campaign/Pause` — pause the whole campaign  
https://documenter.getpostman.com/view/23808049/2sA2xb5F75

---

### 3. If AI replies are on: visible in inbox/conversations API? Distinguishable?

**Visible:** Vendor docs say `GetChatroom` returns the **full thread** (“all messages in the thread”) for `accountId` + `conversationId`. Webhook payload is only the latest inbound message.  
`GET /api/public/inbox/GetChatroom/{accountId}/{conversationId}`  
https://www.heyreach.io/blog/handle-heyreach-replies-with-n8n

List conversations: `POST /api/public/inbox/GetConversationsV2`.  
https://documenter.getpostman.com/view/23808049/2sA2xb5F75

**Distinguish AI vs human vs campaign step: NOT DOCUMENTED.** No field such as `isAi`, `source`, `generatedBy`, or `campaignStepId` is named in vendor docs.

The only sender distinction the vendor blog documents when walking GetChatroom JSON:

- if `sender` equals `"me"` → your LinkedIn account  
- otherwise → the correspondent  

https://www.heyreach.io/blog/handle-heyreach-replies-with-n8n

A message sent after MCP approval or via `SendMessage` would therefore look like a normal outbound (`"me"`) message. **NOT DOCUMENTED** that you can tell AI, human Unibox send, and campaign `MESSAGE` step apart.

---

### 4. Can an AI reply fire after the lead is STOPPED? (highest-priority)

**NOT DOCUMENTED** that stopping a lead also stops AI / automatic *inbox* replies.

What **is** documented:

**Stopping a lead stops campaign progression, not “all messaging” in so many words.**

- Endpoint: `POST /api/public/campaign/StopLeadInCampaign`  
  Documented purpose: “Stop a lead in a campaign.” CLI wording: “Stop lead progression.”  
  https://documenter.getpostman.com/view/23808049/2sA2xb5F75  
  https://github.com/bcharleson/heyreach-cli/blob/main/AGENTS.md

- Sequence follow-ups **on reply**: `MESSAGE` / `INMAIL` “when there is a reply must be an END node.” That is campaign-sequence behaviour, not an inbox AI agent.  
  https://www.heyreach.io/blog/campaign-api

- Cross-channel: “Leads now auto-pause across Smartlead, Instantly, and EmailBison the moment they reply in HeyReach.” That is **reply → pause email**, not **stop lead → pause AI LinkedIn replies**.  
  https://www.heyreach.io/blog/sequence-sharing-auto-save-auto-pause

**Inbox send is independent of campaign lead status in the documented contract.**

`SendMessage` documented inputs are conversation + LinkedIn account + message (optional subject). No campaign ID, no lead-status check, no “skip if stopped” rule.  
https://documenter.getpostman.com/view/23808049/2sA2xb5F75

MCP / n8n / Make AI replies, when they send, use that inbox send path (or Unibox). Vendor MCP copy is explicit that sending is a separate, approval-gated action, not a campaign step.  
https://www.heyreach.io/blog/beginners-guide-heyreach-mcp

**So, from documentation alone:**

- Stopped lead → **should not** get further **campaign sequence** steps (progression stopped).  
- Stopped lead → **whether an MCP/Make/n8n/Unibox AI reply can still send on that conversation: NOT DOCUMENTED.**  
- Because `SendMessage` is not documented as gated on campaign lead status, **you cannot treat Stop Lead as a guarantee** that nothing will be sent on that seat’s conversation.

For shared seats with a client: if anything is auto-sending via webhook → `SendMessage` (or an MCP agent allowed to send), **stopping the lead in the campaign is not documented to block that send.** Confirm with HeyReach support; the public docs do not close this.

Sources the model searched:

- https://www.heyreach.io/blog/handle-heyreach-replies-with-n8n
- https://www.heyreach.io/blog/how-to-automate-linkedin-outreach
- https://www.promiseclick.com/blog/how-to-use-heyreach-guide
- https://docs.getcargo.ai/integration/heyreach
- https://www.heyreach.io/blog/positive-reply-rate-auto-detect-warm-leads
- https://www.fluents.ai/integrations/heyreach
- https://www.builtforb2b.com/blog/heyreach-review-linkedin-automation-for-b2b-outreach
- https://www.underfive.ai/heyreach-ai-reply-agent
- https://www.heyreach.io/blog/campaign-api
- https://www.heyreach.io/blog/linkedin-message-automation
- https://www.wonda.sh/blog/linkedin-automation-safety-heyreach-ban
- https://www.heyreach.io/blog/generate-qualified-linkedin-meetings
- https://zapier.com/apps/heyreach/integrations/linkedin
- https://www.heyreach.io/blog/linkedin-automation-n8n
- https://www.heyreach.io/blog/smartreach-ai-integration
- https://documenter.getpostman.com/view/23808049/2sA2xb5F75
- https://www.pkgstats.com/pkg:heyreach-cli
- https://n8n.io/integrations/heyreach-api/
- https://oxygen-agent.com/integrations/heyreach
- https://www.youtube.com/watch?v=YRJ0QFa4tK8
- https://www.heyreach.io/blog/handle-heyreach-replies-with-n8n
- https://www.heyreach.io/blog/linkedin-login-via-api
- https://www.underfive.ai/heyreach-ai-reply-agent
- https://github.com/bcharleson/heyreach-cli/blob/main/AGENTS.md
- https://docs.alysio.ai/integration-guides/heyreach

## oss_outbound_comparables

`grok-4.6`, Nones, 75 search URLs, usage {'prompt_tokens': 453403, 'completion_tokens': 6321, 'total_tokens': 459724, 'cached_tokens': 327040, 'reasoning_tokens': 5382, 'cost_in_usd_ticks': 10683440000, 'num_sources_used': 0, 'num_server_side_tools_used': 32}.

## Coverage note

At least six open-source projects exist across the two groups. What is *scarce* is the two “especially” features: documented **account-based orchestration** (multiple contacts at one company, shared hook, ordered persona plan) appears in **one** repo; a Slack **client-facing assistant over a business system with a reply engine** that classifies inbound replies and decides stop vs escalate is **not documented** as a complete OSS product. That implies those two capabilities are still mostly commercial or in-house.

Sources the model searched:

- https://github.com/eracle/OpenOutreach
- https://github.com/mukul-07/opensource-sales-ops
- https://github.com/janskuba/outbound-agents
- https://github.com/siddartha19/OpenSales
- https://github.com/swatv3nub/LeadSync
- https://github.com/vedangvatsa/b2b-outreach
- https://github.com/Dumebii/free_outbound_email_agent
- https://www.happyrobot.ai/hub/outbound-sales-automation-tools
- https://www.navgood.com/en/tool-details/qrev-dynamic-salesforce-2-0-043dc
- https://github.com/OmateLabs/speed-to-lead-agent
- https://news.ycombinator.com/item?id=49760135
- https://github.com/eracle/OpenOutFind
- https://github.com/sodiray/agent-outbound
- https://github.com/Varun-Kumar-3105/Outbound-Sales-Agent/blob/main/PLAN.md
- https://github.com/mcvalosborne/lead-research-agent
- https://github.com/personizeai/revenue-os
- https://slashdot.org/software/account-based-orchestration/for-github/
- https://www.horilla.com/crm/
- https://github.com/personizeai/revenue-os
- https://github.com/aadiieee/multi-agent-revenue-orchestrator
- https://github.com/Mrgig7/Multi-Agent-Enterprise-CRM
- https://github.com/dealbot/dealbot
- https://github.com/nash-md/meow
- https://github.com/sidmohan0/kanbun
- https://openalternative.co/atomic-crm

