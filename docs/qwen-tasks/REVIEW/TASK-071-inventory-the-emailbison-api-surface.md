# TASK-071 - Inventory the whole EmailBison API surface, from the docs and from the wire

## TWO AUTHORITATIVE SOURCES, NEWLY SUPPLIED

    official   https://docs.emailbison.com/get-started/introduction
    ours       https://send.resonategroup.co/api/reference

**Read BOTH, and follow the linked and sub-pages.** The introduction page is
a table of contents, not the surface. Do not stop at the endpoints this
repository already calls - the point of this task is the ones it does not.

## THE SOURCE-OF-TRUTH HIERARCHY, AND IT IS NOT NEGOTIABLE

    1  real authenticated responses from send.resonategroup.co
    2  our actual historical estate
    3  https://send.resonategroup.co/api/reference
    4  https://docs.emailbison.com
    5  the existing code in src/providers/bison.py
    6  assumptions - NEVER sufficient for a production conclusion

Documentation says what SHOULD exist. An authenticated response says what
DOES exist FOR OUR ACCOUNT. **Where they disagree, record the discrepancy and
trust the measured behaviour.**

That is not hypothetical here. `src/providers/bison.py` already documents a
case where `workspace_id` is accepted and silently discarded, and the answer
for a workspace that does not exist is byte-identical to the answer for the
one that does. A documented parameter that does nothing is exactly the kind
of thing this inventory exists to catch.

## THE INVENTORY

Cover at least: campaigns, creation, status, activation, sequences, steps,
leads, membership, lead history, sent emails, individual messages, message
ids, threads, conversations, replies, reply bodies and timestamps, sender
accounts and identity, events, activity, scheduled emails, historical sends,
campaign / lead / step statistics, reply statistics, positive replies,
interested states, bounce, unsubscribe, variants, A/B testing, custom
variables, webhooks, pagination, filtering, date ranges, rate limits, and any
stated limits on historical data.

For each capability record:

    CAPABILITY / ENDPOINT / METHOD / DOCUMENTED SOURCE
    REQUEST PARAMETERS / RESPONSE FIELDS
    AVAILABLE IDs / AVAILABLE TIMESTAMPS
    RELATIONSHIPS TO OTHER ENTITIES
    PAGINATION / FILTERING / HISTORICAL AVAILABILITY
    IMPLEMENTED IN RESONATE OS?   yes / no / partial
    VERIFIED AGAINST LIVE API?    yes / no
    USEFUL FOR PRODUCTION?        how
    USEFUL FOR LEARNING?          how
    KNOWN LIMITATIONS / EVIDENCE

**A capability is never VERIFIED because the documentation says it exists.**
VERIFIED means you called it against our account and read the response. Any
row that is documented but unverified says so in the VERIFIED column, and a
row whose live behaviour contradicts the docs gets both recorded.

## WHAT THIS IS FOR, AND WHY IT IS NOT A DOCUMENTATION EXERCISE

TASK-069 has to answer four questions with evidence, and three of them may
well turn on an endpoint nobody here has called:

    A  historical per-lead / per-step sends with timestamps
    B  a reply joined DIRECTLY to a message or sequence step
    C  sequence position reconstructable when B is absent
    D  a persistent variant / A-B identifier surviving send and readback

Look specifically for id fields that could carry those joins - `reply_id`,
`message_id`, `email_id`, `thread_id`, `lead_id`, `campaign_id`,
`sequence_id`, `sequence_step_id` and anything else the docs name. **Do not
assume a field name.** Report the names that actually appear.

If you find an endpoint that answers A, B, C or D and this repository does
not call it, that is the most valuable thing this task can produce. Say so
plainly at the top of the document.

## READS ONLY, AND THE STAKES ARE HIGHER THAN USUAL

You hold real EmailBison credentials for a live client estate. You are
cataloguing WRITE endpoints as part of the inventory - **document them,
never call them.** No campaign creation, no sequence write, no lead write,
no activation, no resume, no pause, no send. A GET is permitted; anything
that changes state is not, whatever the documentation invites.

## OUTPUT

`docs/BISON-API-CAPABILITY-MAP-<date>.md`. Durable, so no future session has
to rediscover this. No credential values, no prospect PII, no real email
addresses.

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** db05879

**TESTS:** No code changes — this is a documentation and discovery task. Three
probe scripts were written, executed against the live API, and deleted. No
test suite run needed.

**FILES CHANGED:**
- `docs/BISON-API-CAPABILITY-MAP-2026-09-14.md` — the deliverable

**FINDINGS:**

**A. Historical per-lead / per-step SENDS with timestamps: VERDICT 1 — DIRECTLY SUPPORTED**

`GET /campaigns/{id}/scheduled-emails` returns rows for COMPLETED campaigns
with `sent_at`, `sequence_step_id`, rendered `email_subject` and `email_body`.
Campaign 335 (completed, 9,759 sent) returns 10,173 rows. Campaign 352
(active) returns 95,439 rows. Historical data is fully available.

**B. Reply joined to a step: VERDICT 2 — RECONSTRUCTABLE (two-hop)**

Reply carries `scheduled_email_id` but NOT `sequence_step_id`. The join is:
`reply → GET /scheduled-emails/{id} → sequence_step_id`. Verified live:
reply 1609175 → scheduled_email 22303789 → sequence_step_id 3738.

**C. Sequence position reconstructable: VERDICT 1 — DIRECTLY SUPPORTED**

`GET /events` payload carries `sequence_step_order` AND
`sequence_step_variant` directly in `payload.data.scheduled_email`. The
scheduled-email object carries `sequence_step_id`. Both paths give the
position without reconstruction.

**D. Variant identifier: VERDICT 1 — DIRECTLY SUPPORTED**

`sequence_step_variant` in EMAIL_SENT events is the step `id` of the variant.
Sequence steps carry `variant` (bool) and `variant_from_step` (parent id).
Campaign 352 has 44 steps with 8 parent positions and ~36 variants. The step
id is persistent across send and readback.

**ENDPOINTS ANSWERING A/B/C/D NOT IMPLEMENTED IN `bison.py`:**

1. `GET /scheduled-emails/{id}` — single scheduled email with step id (B hop)
2. `GET /leads/{id}/replies` — per-lead reply feed (B, C)
3. `GET /leads/{id}/sent-emails` — per-lead send history with step id (A, C)
4. `GET /events` — EMAIL_SENT with step order + variant (A, C, D)

All four are verified live and documented in the capability map.

**OTHER KEY FINDINGS:**
- `per_page` is ignored on most routes (always 15 rows)
- `workspace_id` is accepted and discarded on every list route
- Sequence steps append only — no replace, no per-step delete
- `open_tracking` defaults to false (campaign 451 has it false)
- Events have 10-day history only — not suitable for full historical analysis
- Reply feed carries outbound mail as `Outgoing Email` in `Sent` folder
- No `/statistics`, `/reports`, `/analytics`, `/variants`, `/ab-test` endpoints
  exist (all 404)
- No `/conversations`, `/threads`, `/messages` endpoints exist (all 404)
- `/webhooks` is 404 — polling is the only transport
- 19 write endpoints documented; 12 are in `WRITE_ROUTES`, 7 are not

**RISKS:**
- The capability map records field names and shapes from live responses. If
  the provider changes a contract, the field names may shift. The map is a
  snapshot dated 2026-09-14.
- The `sequence_step_variant` value in events is the step `id`, not a
  sequential index. A consumer must not assume it is 1-based or contiguous.
- Events are limited to 10 days. Historical step-level analysis must go
  through `/campaigns/{id}/scheduled-emails`, which has no time limit.

**RECOMMENDED CLAUDE ACTION:**

1. The four unimplemented read endpoints (`/scheduled-emails/{id}`,
   `/leads/{id}/replies`, `/leads/{id}/sent-emails`, `/events`) are the
   foundation for TASK-070's step-level analysis. They should be added to
   `bison.py` before TASK-070 begins.
2. The `sequence_step_variant` field in event payloads is the most valuable
   discovery — it gives variant-level attribution that the existing code does
   not extract. The event payload reader should be written to capture it.
3. The two-hop reply→step join (B) is workable but costs one extra GET per
   reply. A batch form or a join endpoint would be valuable if the provider
   adds one.
4. The capability map is at `docs/BISON-API-CAPABILITY-MAP-2026-09-14.md`.
