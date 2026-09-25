# emailbison-remove-and-pause

_Asked of Grok (xAI) 2026-09-26. Sources are the model's; verify before building a limit on one._

## Question

EmailBison API: what are the endpoints and exact request shapes for (a) removing a lead from a campaign, (b) pausing a single lead without pausing the campaign, and (c) pausing and resuming a whole campaign? Include the HTTP verb, path, body, and what a success response looks like. Cite the EmailBison documentation with URLs.

## Answer

**I cannot give you production-safe request/response contracts for EmailBison from a public, citable API reference.** I do not have a live fetch of their docs in this session, and I will not invent verbs, paths, bodies, or success JSON. Those would get copied into a rate limiter / client.

## What is actually citable

Public, stable URLs I can point at:

- Product: [https://emailbison.com](https://emailbison.com)
- Marketing/help content lives on that domain and related help surfaces. I am **not** certain that a full public OpenAPI/API-reference site (for example a `docs.emailbison.com` API catalog) currently publishes the exact shapes you asked for. Treat any such hostname as **unverified unless it loads in your workspace**.

What operators typically find in practice (this is **operational knowledge, not a doc citation**):

- API key is created in the EmailBison app (Settings / API).
- Auth is a bearer token on the **workspace/instance base URL**, not a single global `api.emailbison.com` that I can cite as documented.
- Instance URL is account-specific (dedicated/white-label host). The docs do **not**, in anything I can cite, freeze one global base URL for all customers.
- Some EmailBison deployments expose in-app / instance API docs (Laravel-Scribe-style `/docs` is a common pattern in this class of app). **I cannot cite a public page that confirms EmailBison does this, or the path.** Check your own instance.

I am **not** citing third-party n8n/Make/Clay recipes, blog posts, or HAR dumps as EmailBison documentation.

## (a) Remove a lead from a campaign

**Official docs I can cite do not state** the HTTP verb, path, body, or success payload for “remove this lead from this campaign (without necessarily deleting the lead globally).”

Do **not** build against any of these guesses:

- `DELETE /api/campaigns/{campaign_id}/leads/{lead_id}`
- `DELETE /api/leads/{id}`
- `POST /api/campaigns/{id}/leads/remove` with `{ "lead_ids": [...] }`

Those are common REST patterns in other sequencers (Instantly, Smartlead, etc.). **They are not EmailBison documentation.**  
Also distinguish three different product actions the public pages do not specify as API contracts:

1. detach lead from one campaign  
2. delete the lead from the workspace  
3. mark unsubscribed / bounced / replied (stops sending for a different reason)

**Success response:** docs I can cite do not state `200` vs `204`, wrapper (`data` vs bare object), or whether the body is empty.

## (b) Pause a single lead without pausing the campaign

**Official docs I can cite do not state** an endpoint, body, or success response for pausing one lead.

Do **not** ship any of these as fact:

- `POST /api/leads/{id}/pause`
- `PATCH /api/leads/{id}` with `{ "status": "paused" }`
- `PATCH /api/campaigns/{campaign_id}/leads/{lead_id}` with a pivot `status`

I also cannot cite:

- field name (`status` vs `paused` vs `state`)
- enum values (`paused` vs `inactive` vs `stopped`)
- whether pause is per-lead global or per-campaign-membership
- the resume counterpart

If EmailBison’s UI has “pause lead”, that is a product feature, not an API contract.

## (c) Pause and resume a whole campaign

**Official docs I can cite do not state** dedicated pause/resume routes, and they do not state whether pause is a dedicated POST or a `status` update on `PUT/PATCH /campaigns/{id}`.

Do **not** treat these as documented:

- `POST /api/campaigns/{id}/pause` and `POST /api/campaigns/{id}/resume` with empty body  
- `PUT /api/campaigns/{id}` with `{ "status": "paused" }` / `{ "status": "active" }`

**Success response:** not stated in anything I can cite (status code, whether the full campaign resource is returned, field names, `status` enum).

## What to do instead (so you do not freeze a wrong contract)

1. In **your** EmailBison workspace, open the official API docs or OpenAPI/Scribe page attached to **that instance**, and copy verb + path + schema from there. That page is the only source that should feed a production client.
2. If the instance has no schema for (a) or (b), treat those operations as **undocumented** until EmailBison support or the in-app reference adds them. Do not infer them from the UI.
3. For a success fixture, use a real response from that instance (one campaign id, one lead id) and pin the JSON you actually received—not a guessed `{ "data": { "status": "paused" } }`.

If you paste the OpenAPI/Scribe snippet or a redacted HAR for those three calls from **your** instance, I can transcribe the exact verb, path, body, and success shape from that artifact—still labeled as instance-observed, not as a global public doc.
