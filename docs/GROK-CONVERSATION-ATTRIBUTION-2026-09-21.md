# Grok provider research

2026-09-21T11:46:12.742621+00:00. One call per question, web_search enabled.

**CLASSIFY BEFORE BELIEVING.** Every claim below is the model's, and a confident answer is not a documented one. A point is
DOCUMENTED only where a source URL states it, OBSERVED only where this estate's own provider responses show it, and
HYPOTHESIS or UNKNOWN otherwise. Nothing here is provider truth until a readback against our own estate agrees with it.

---

## conversation_attribution

`grok-4.6`, Nones, 208 search URLs, usage {'prompt_tokens': 1183950, 'completion_tokens': 7473, 'total_tokens': 1191423, 'cached_tokens': 1036672, 'reasoning_tokens': 4444, 'cost_in_usd_ticks': 19354600000, 'num_sources_used': 0, 'num_server_side_tools_used': 44}.

I'll look up HeyReach's public API docs and map conversation IDs to campaigns, sender seats, list/inbox endpoints, rate limits, and webhooks.
The Postman collection looks like the public API source of record. I'll open that plus webhook docs and the inbox endpoints next.
I'll pull the official Postman Inbox/Webhooks pages and the reply-webhook payload docs so we can answer from cited sources only.
Postman is JS-rendered, so I’ll pull the CLI/MCP type definitions and any webhook payload docs that list conversation, campaign, and sender fields.
I’ll fetch the CLI/n8n request schemas and any Inbox V3 or webhook payload field lists so we can stay with documented field names.
Make.com points at official webhook docs on Notion and a Postman Inbox section. I'll open those plus the CLI inbox command sources.
Official public API surface is the Postman collection. Inbox/webhook **field-level schemas** (conversation object, lookup-by-conversation-id) are largely unpublished; where they are unpublished the answer is **NOT DOCUMENTED**.[[1]](https://documenter.getpostman.com/view/23808049/2sA2xb5F75)

---

### 1. Endpoint that resolves a conversation id → campaign + LinkedIn sender seat

**NOT DOCUMENTED.** No public method takes **only** a conversation id and returns `campaignId` / LinkedIn account (seat) id.

Documented conversation **get** is:

- **Method / path:** `GET https://api.heyreach.io/api/public/inbox/GetChatroom/{accountId}/{conversationId}`
- **Request:** path params `accountId` (LinkedIn sender account id) **and** `conversationId`. You already need the seat id. Header `X-API-KEY`.
- **Response fields (campaign, sender, lead):** **NOT DOCUMENTED** in any retrieved schema. Vendor blog only says the response “describes the complete conversation” and “returns all messages in the thread.”[[2]](https://oxygen-agent.com/integrations/heyreach)

There is also **no** documented filter on the list endpoint for `conversationId`.

---

### 2. Inbox / conversation LIST endpoint, filters, pagination, `campaignId` / `linkedInAccountId` on each item

**Yes, a list endpoint exists:** `POST https://api.heyreach.io/api/public/inbox/GetConversationsV2`  
(“Get a paginated collection of LinkedIn conversations.”) Header `X-API-KEY`.[[2]](https://oxygen-agent.com/integrations/heyreach)

**Body (as used by the HeyReach-partnered CLI against that path):**

```json
{
  "offset": 0,
  "limit": 100,
  "filters": {
    "linkedInAccountIds": [123],
    "campaignIds": [456],
    "searchString": "…",
    "leadLinkedInId": "…",
    "leadProfileUrl": "https://www.linkedin.com/in/username/",
    "tags": ["…"],
    "seen": false
  }
}
```

`limit` 1–100. Filter keys are optional. n8n’s Inbox → Get Many maps the same filters (`Campaign IDs`, `Lead LinkedIn ID`, `Lead Profile URL`, `LinkedIn Account IDs`, `Search String`, `Seen`) plus `offset`/`limit`.[[3]](https://raw.githubusercontent.com/bcharleson/heyreach-cli/main/src/commands/inbox/list.ts)

**Pagination shape (workspace-wide pattern in the public API intro / list endpoints):** request `{ offset, limit }` → response `{ totalCount, items: [...] }`. Max 100 items per request. Whether Inbox V2 uses that exact envelope is **not restated on an Inbox page we could fetch**; the CLI still posts `{ offset, limit, filters }` to this path.[[1]](https://documenter.getpostman.com/view/23808049/2sA2xb5F75)

**Does each conversation return `campaignId` and `linkedInAccountId`?** **NOT DOCUMENTED.** Official Postman example body for this endpoint did not load. The only published item sketch (unofficial) is `id`, `lastMessageText`, `lastMessageSender`, `correspondentProfile.{firstName,lastName}` — no campaign or account id. n8n’s “typically includes … campaign associations” is not a vendor schema.[[4]](https://raw.githubusercontent.com/bcharleson/cold-outbound-dream-team/main/src/tools/heyreach/tools.py)

`GetConversations` (non-V2) is named in connector inventories; contract **NOT DOCUMENTED**. CLI notes **Inbox V3** exists on Postman and is unpublished in that client; V3 contract **NOT DOCUMENTED**.

---

### 3. What `2-` on a conversation id means; is the format documented?

**NOT DOCUMENTED.** No HeyReach API/help/webhook page retrieved describes `2-<base64>`, a decoded `<uuid>_100`, or any conversation-id prefix.

---

### 4. Rate limits on those endpoints; payload of a single conversation object

**Rate limits (global, not per-endpoint):** maximum **300 requests per minute**. All requests share that bucket. Over limit → **HTTP 429** and an error. Organization API is documented elsewhere as a **separate** 300/min bucket; Inbox is under the workspace public API. Per-Inbox-endpoint limits: **NOT DOCUMENTED**.[[1]](https://documenter.getpostman.com/view/23808049/2sA2xb5F75)

**Single conversation object (list item or GetChatroom):** **NOT DOCUMENTED** in vendor OpenAPI/Postman text we could retrieve. Unofficial list-item sketch above is not a vendor contract. GetChatroom: messages present (blog); other fields **NOT DOCUMENTED**.

---

### 5. Webhook that already includes campaign + sender (no lookup)

**Yes, at the prose level — not a field schema.**

HeyReach documents a reply webhook. Preferred event in their own n8n guide: **“every message/inmail reply received”** (`EVERY_MESSAGE_REPLY_RECEIVED` in partner enums; also `MESSAGE_REPLY_RECEIVED` / `INMAIL_REPLY_RECEIVED` for first-reply). Create via UI or `POST /api/public/webhooks/CreateWebhook`. Partner docs: `campaignIds` filter is **not** available for “Lead Tag Updated” and “Every Message/InMail Reply Received”.[[5]](https://www.heyreach.io/blog/handle-heyreach-replies-with-n8n)

Vendor blog states the **every-reply** payload includes:

- message text, timestamp, whether it is a reply  
- **conversation ID**  
- **campaign information**  
- **sender details (your LinkedIn account)** — blog also says GetChatroom’s **Account ID** is taken from this webhook  
- lead information, list membership, event type  

It also states the payload has **only the latest message**, not the full thread. Exact JSON names (`campaign.id` vs `campaignId`, `sender.id` vs `linkedInAccountId`, etc.): **NOT DOCUMENTED** on that page. A third-party mapper describes nested `lead`, `campaign`, `sender` plus `conversation_id` / `recent_messages`; that is not HeyReach’s schema.[[6]](https://docs.getcargo.ai/integration/hey-reach)

Official webhook write-up URL (JS Notion page; body not fetchable here): https://heyreach.notion.site/heyreach-webhooks-documentation-400c53b3aa8743d085937419bccfe276  
Public API: https://documenter.getpostman.com/view/23808049/2sA2xb5F75  

**Bottom line for inbox events that only carry `2-…`:** public REST does **not** document a conversation-id → campaign/seat resolver. GetChatroom needs `accountId` already. The documented way to get campaign + sender **without** that lookup is the **every-reply webhook**, with field names still **NOT DOCUMENTED** beyond the blog’s prose.

Sources the model searched:

- https://documenter.getpostman.com/view/23808049/2sA2xb5F75
- https://www.heyreach.io/blog/campaign-api
- https://oxygen-agent.com/integrations/heyreach
- https://apps.make.com/heyreach
- https://docs.alysio.ai/integration-guides/heyreach
- https://cotera.co/docs/reference/tools/individual-tools/hey-reach
- https://n8n.io/integrations/heyreach-api/
- https://www.pkgstats.com/pkg:heyreach-cli
- https://docs.getcargo.ai/integration/hey-reach
- https://docs.composio.dev/toolkits/heyreach.md
- https://github.com/bcharleson/heyreach-mcp/blob/main/API_ENDPOINT_STATUS.md
- https://raw.githubusercontent.com/bcharleson/cold-outbound-dream-team/main/src/tools/heyreach/tools.py
- https://github.com/bcharleson/heyreach-cli/blob/main/AGENTS.md
- https://www.scalekit.com/connectors/heyreach
- https://pkg.go.dev/github.com/amp-labs/connectors/providers/heyreach
- https://oxygen-agent.com/integrations/heyreach
- https://www.heyreach.io/blog/linkedin-login-via-api
- https://cotera.co/docs/reference/tools/individual-tools/hey-reach
- https://github.com/bcharleson/heyreach-cli
- https://docs.composio.dev/toolkits/heyreach.md
- https://raw.githubusercontent.com/bcharleson/cold-outbound-dream-team/main/src/tools/heyreach/tools.py
- https://ncnodes.com/package/n8n-nodes-heyreach/heyreach/Inbox:Get%20Chatroom
- https://github.com/bcharleson/heyreach-mcp/blob/main/API_ENDPOINT_STATUS.md
- https://ncnodes.com/package/n8n-nodes-heyreach/heyReach/Inbox:Send%20Message
- https://www.heyreach.io/blog/campaign-api

