# heyreach-step-limits

_Asked of Grok (xAI) 2026-09-26. Sources are the model's; verify before building a limit on one._

## Question

HeyReach API: what are the limits and exact payload shape for building a FIVE-step LinkedIn sequence (one connection request plus four messages) via the public API? Specifically: is there a maximum number of steps per campaign or per branch; what does the sequence/graph payload look like for CreateCampaign or UpdateSettings; which step types are supported (connect, message, view profile, InMail); how are delays between steps expressed; and are there documented limits on message length per step? Cite the HeyReach documentation or support material you rely on, with URLs.

## Answer

**I do not have a live copy of HeyReach’s current Public API spec in this session, so I will not invent a CreateCampaign / UpdateSettings JSON body, a max-step integer, or a per-step character cap.** Those values would be unsafe to bake into a rate limiter or campaign builder. Where the public docs (as they are commonly published) do not spell something out, that is called out below.

Verify everything against the collection HeyReach actually ships, not against this message.

## Sources to treat as canonical

HeyReach does **not** appear to publish a single long-form “sequence graph” reference page the way some CRMs do. The Public API is primarily a **Postman/OpenAPI-style** collection, plus help-center articles:

- In-app: **HeyReach → Settings → API** (this is the URL/key source of truth for your workspace).
- Public API (Postman documenter is what they have historically used). A collection that is widely linked in integrations is along the lines of their “HeyReach Public API” Postman docs; confirm the link shown in your workspace rather than trusting a third-party mirror.
- Help center: [https://help.heyreach.io/](https://help.heyreach.io/)
- Product/API overview (marketing + endpoint intent, not schema): [https://www.heyreach.io/](https://www.heyreach.io/)
- Independent confirmation of the **public** surface (campaign get/pause/resume/add leads — **not** sequence authoring): n8n’s HeyReach node, [https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.heyreach/](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.heyreach/)

If a field or limit is not in that Postman collection / OpenAPI and not in help.heyreach.io, **the docs do not state it**. Ask HeyReach support rather than inferring from the UI.

Typical Public API base (confirm in the collection): `https://api.heyreach.io/api/public` with header `X-API-KEY`. I am **not** asserting path names below as guaranteed current.

---

## 1. Can you build a 5-step LinkedIn sequence (1 connect + 4 messages) via the Public API?

**Uncertain, and the published Public API surface strongly suggests “no” for the graph itself.**

What is consistently exposed in the Public API (and in the n8n node, which tracks that surface) is **operating on campaigns that already exist**:

- list / get campaign
- pause / resume
- add leads to a campaign
- stop a lead in a campaign  
plus lists, leads, inbox/conversations, stats, webhooks, LinkedIn accounts.

I **cannot** confirm from public documentation that `CreateCampaign` or `UpdateSettings` accepts a sequence/graph of steps. Those names are **not** part of the well-documented public operations above. They may exist as internal/app APIs, unpublished endpoints, or newer additions that are not in the Public API collection.

**Production implication:** the supported pattern is: **author the 5-step sequence in the HeyReach UI**, then **attach leads via the Public API**. Do not design a limiter or builder around an undocumented campaign-graph POST.

If your workspace’s current Postman collection **does** list `CreateCampaign` / `UpdateSettings`, use **that** schema only. I will not guess one.

---

## 2. Maximum number of steps per campaign or per branch

**The Public API docs do not state a maximum number of steps per campaign or per branch.** I am not going to supply a plausible number.

The **product UI** supports multi-step LinkedIn sequences with branching (at least “connected / not connected” style flows). That is a product fact, not an API contract, and UI capability is not the same as a documented API max.

For a 5-step sequence (connect + 4 messages): nothing in the public API material I can cite says that 5 is over a cap. That is **not** the same as “the limit is ≥ 5.”

---

## 3. Sequence / graph payload for CreateCampaign or UpdateSettings

**Not documented in the Public API material I can cite. I will not invent a graph schema.**

What you would need, and what is **not** in the public docs as a stable contract:

- node list vs adjacency list vs ordered `steps[]`
- IDs for branches (accepted vs not accepted, replied vs not)
- how a connection request is represented vs a follow-up message
- whether UpdateSettings mutates sequence, sending windows, LinkedIn sender, or both

Until HeyReach publishes that body, treat sequence JSON as **unsupported** on the Public API.

If you later retrieve a real example from **their** collection, the fields to copy exactly (names only as a checklist, not as a spec) would be whatever they name for: step type, delay, message body, connection note, branch edges, and sender account. Do not substitute names from other tools (Expandi, Lemlist, Waalaxy, etc.).

---

## 4. Step types (connect, message, view profile, InMail)

**API:** the Public API documentation does **not** publish an enum of sequence step types, because it does not document sequence authoring.

**Product (UI, not API contract):** HeyReach campaigns are LinkedIn sequences that, in the product, include actions such as connection request and follow-up messages; the product has also offered other LinkedIn actions (profile views, etc.) depending on plan and LinkedIn account type. **InMail** availability is account/plan dependent (Sales Navigator / InMail credits), not something the Public API documents as a step type.

Do **not** send step-type strings in an API body unless they appear in the official collection. I will not list guessed enum values (`CONNECT`, `MESSAGE`, …).

---

## 5. Delays between steps

**The Public API docs do not state how delays are expressed** (days vs hours vs minutes, inclusive/exclusive of working hours, timezone, or field name).

In the **UI**, delays are configured between steps as a wait (typically in days/hours) and are interpreted against the campaign’s sending schedule. That UI behavior is **not** a documented API field (`delayInDays`, `delayHours`, `wait_seconds`, etc.). Do not pick a unit for a limiter.

---

## 6. Message length per step

**HeyReach Public API docs do not state a per-step character limit.**

Platform constraints you will still hit (these are **LinkedIn**, not HeyReach API docs):

- Connection-request note: LinkedIn’s own invitation note limit has long been **300 characters**. Confirm current LinkedIn help, e.g. LinkedIn Help on invitation messages ([linkedin.com/help](https://www.linkedin.com/help/linkedin)). HeyReach cannot raise LinkedIn’s cap.
- Regular LinkedIn messages / InMail: LinkedIn-imposed; HeyReach’s public API does **not** document a separate cap. I will not quote a number as if it were HeyReach’s.

If HeyReach validates lengths server-side, that validation is **not** in the Public API docs I can cite. Treat LinkedIn’s current limits as the hard ceiling; treat HeyReach’s as unknown unless support or the collection says otherwise.

---

## 7. Other limits people confuse with “sequence limits”

Also **not** something to invent:

- Public API rate limit (req/min): **not stating a number**; read the collection/help or the `429` body.
- Campaign daily send limits, working hours, max LinkedIn accounts per campaign: campaign **settings** in the product; not a documented sequence-graph payload.
- Max leads per `AddLeadsToCampaign` call: **do not guess**; the Postman collection is the place this would appear.

---

## Practical contract for a production 5-step outreach system

Until HeyReach documents a sequence graph on the Public API:

1. Create the campaign in the UI: step 1 = connection request, steps 2–5 = messages, with UI delays and any “if connected” branch.
2. Use the Public API only to **get the campaign id**, **add/stop leads**, **pause/resume**, and **read inbox/stats/webhooks**.
3. Do not encode a max-step or max-length integer into a limiter unless it is copied from the live collection or a written reply from HeyReach support.
4. If you have been told internally that `CreateCampaign` / `UpdateSettings` exist, ask support for the OpenAPI fragment for those two operations and treat anything else as unofficial.

If you paste the **current** Postman/OpenAPI entries for `CreateCampaign` and `UpdateSettings` from your workspace (paths + example bodies), those can be interpreted field-by-field against this checklist without guessing undocumented limits.
