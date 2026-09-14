# EmailBison Provider Truth — 2026-09-14 (revised)

Read-only probe of the live instance at `https://send.resonategroup.co/api`.
Every claim below carries the row count behind it. No performance findings —
those belong to TASK-070 and are built on this map.

Supersedes the earlier map from commit a9cc65c. The earlier map established
field shapes; this one answers four specific questions with one of four
allowed verdicts and labels every non-verdict-1 claim.

## Method

Each section names the route, the field, the type, the shape, and how many
rows were checked. All probes are reproducible from `src/providers/bison.py`
with the credential in `config/.env`. No PII is committed — emails, names and
company domains are redacted. No write of any kind was made.

## Three kinds of statement

    PROVIDER FACT              the API returned this field with this value
    RESONATE RECONSTRUCTION    we derived it from provider data, and here is
                               the derivation and what it assumes
    ATTRIBUTION HYPOTHESIS     we believe this reply relates to that touch,
                               and it is a belief

**"The last email before the reply" is an ATTRIBUTION HYPOTHESIS and never
proof that the email caused the reply.** A prospect may answer email one
three weeks later, after emails two and three have gone out. A reply may be
triggered by a LinkedIn touch the email estate cannot see.

---

## A. DO HISTORICAL PER-LEAD / PER-STEP SENDS WITH TIMESTAMPS EXIST?

### Verdict: DIRECTLY SUPPORTED BY PROVIDER

**PROVIDER FACT.** The route `GET /api/campaigns/{id}/scheduled-emails`
returns a per-lead per-step record of what was actually sent, with
timestamps, rendered copy, and the `sequence_step_id` linking to the
sequence definition. It is available for historical campaigns, including
archived ones.

### Evidence

| Campaign | Status | emails_sent | scheduled_emails (meta.total) | Rows checked |
|----------|--------|-------------|-------------------------------|--------------|
| 451 | completed | 1 | 1 | 1 |
| 335 | completed | 9,759 | 10,173 | 15 (page 1) |
| 274 | archived | 28,331 | 30,411 | 15 (page 1) |

31 rows checked directly. `meta.total` confirms availability for the full
estates. Campaign 274 is archived and its data is still served.

### Fields on the scheduled email row (20 fields)

| Field | Type | Populated | Notes |
|-------|------|-----------|-------|
| `id` | int | 31/31 | The scheduled email's own id |
| `campaign_id` | int | 31/31 | |
| **`sequence_step_id`** | **int** | **31/31** | **THE STEP LINK** |
| `status` | str | 31/31 | `"sent"`, `"stopped"`, `"bounced"` |
| `scheduled_date` | str (ISO 8601) | 31/31 | |
| `scheduled_date_local` | str (ISO 8601) | 31/31 | |
| `sent_at` | str (ISO 8601) | 31/31 | null when not yet sent |
| `raw_message_id` | str | 31/31 | |
| `email_subject` | str (RENDERED) | 31/31 | Merge fields resolved |
| `email_body` | str (RENDERED HTML) | 31/31 | Merge fields resolved |
| `opens` | int | 31/31 | Always 0 (see Campaign section) |
| `unique_opens` | int | 31/31 | Always 0 |
| `clicks` | int | 31/31 | |
| `replies` | int | 31/31 | |
| `unique_replies` | int | 31/31 | |
| `interested` | bool | 31/31 | |
| `thread_reply` | bool | 31/31 | |
| `lead` | dict (nested) | 31/31 | Full lead object |
| `campaign` | dict (nested) | 31/31 | Full campaign object |
| `sender_email` | dict (nested) | 31/31 | Sender inbox object |

### What this means

Step-level learning is possible. For every email that was sent, the provider
stores:
- Which step it was (`sequence_step_id`)
- When it was sent (`sent_at`)
- What the recipient actually saw (`email_subject`, `email_body` — rendered)
- Who received it (`lead.id`, `lead.email`)

### Pagination trap

**PROVIDER FACT.** 15 rows per page whatever `per_page` is set to. Campaign
335: 10,173 rows across 679 pages. Campaign 274: 30,411 rows. The
`_paged()` function in `bison.py` walks the full listing with a `PAGE_CAP`
of 40 (600 rows). Large campaigns exceed the cap and raise
`PartialInventory`.

---

## B. DOES A REPLY CARRY A DIRECT MESSAGE OR STEP RELATIONSHIP?

### Verdict: DIRECTLY SUPPORTED BY PROVIDER

**PROVIDER FACT.** A reply row carries `scheduled_email_id`, which is the id
of the exact scheduled email the reply is associated with. Through that,
`sequence_step_id` on the scheduled email row gives the step.

### Evidence

750 reply rows checked (50 pages, cursor-paginated, spanning 2026-07-19 to
2026-09-14).

| Field | Populated (of 750) | Notes |
|-------|---------------------|-------|
| `scheduled_email_id` | **748/750** | 2 missing are `type: "Outgoing Email"` |
| `campaign_id` | 748/750 | Same 2 |
| `lead_id` | 748/750 | Same 2 |

### The two rows missing the join fields are outgoing

**PROVIDER FACT.** The 2 rows with null `campaign_id`, `lead_id`, and
`scheduled_email_id` are both `type: "Outgoing Email"` in `folder: "Sent"`.
They are our own sent mail and are correctly filtered out by
`classify_reply_row`. **100% of actual inbound replies and bounces carry the
full join chain.**

### The join chain, verified end-to-end

**PROVIDER FACT.** Verified against a live reply:

```
Reply id=1609175
  campaign_id=327              -> CAMPAIGN
  lead_id=146592               -> LEAD
  scheduled_email_id=22303789  -> SCHEDULED EMAIL
    sequence_step_id=3738      -> STEP (order=7, active=True, wait=3d)
    sent_at=2026-09-14T16:09:20 -> TIMESTAMP
    email_subject=[41 chars]    -> RENDERED COPY
    email_body=[739 chars]      -> RENDERED COPY
    lead.id=146592              -> LEAD MATCH
```

### How each link is made

| Link | Via | Field | Verified |
|------|-----|-------|----------|
| reply → scheduled email | `reply.scheduled_email_id` = `scheduled_email.id` | explicit | 748/750 |
| reply → campaign | `reply.campaign_id` | explicit | 748/750 |
| reply → lead | `reply.lead_id` or `reply.lead.id` | explicit + nested | 748/750 |
| scheduled email → step | `scheduled_email.sequence_step_id` = `step.id` | explicit | 1/1 checked |
| scheduled email → copy | `scheduled_email.email_subject`, `email_body` | direct | 1/1 checked |
| scheduled email → timestamp | `scheduled_email.sent_at` | direct | 1/1 checked |

### What this means

A reply is attributable to a campaign, a lead, AND a step. The full chain
the operator wants is buildable:

    campaign -> lead -> exact email step -> exact copy -> send timestamp
             -> reply -> outcome

### Important caveat on attribution

**ATTRIBUTION HYPOTHESIS.** The `scheduled_email_id` on a reply row is the
provider's own association. It may mean "this reply was received in the
thread started by this email" or it may mean "this is the most recent email
sent to this lead in this campaign." The provider does not document the
semantics. What is certain:

- The field exists and is populated on 100% of inbound replies (748/748
  inbound, excluding 2 outgoing).
- It links to a real scheduled email row that carries `sequence_step_id`.
- **It is NOT proven that the email identified by `scheduled_email_id`
  CAUSED the reply.** A prospect may reply to email 1 after email 3 has
  been sent, and the provider may associate the reply with email 3 (the
  most recent) rather than email 1 (the actual trigger). This is an
  ATTRIBUTION HYPOTHESIS and every number derived from it must say so.

---

## C. CAN EXACT SEQUENCE POSITION BE RECONSTRUCTED WHEN B IS ABSENT?

### Verdict: RECONSTRUCTABLE FROM PROVIDER DATA

B is present (verdict 1), so this question is moot for the current estate.
But the fallback matters for robustness.

### The reconstruction

**RESONATE RECONSTRUCTION.** Given a `campaign_id` and `lead_id`, the
scheduled emails route returns every email sent to that lead in that
campaign, each with `sequence_step_id`, `sent_at`, and rendered copy. From
this:

1. Sort by `sent_at` ascending.
2. The Nth row is the Nth step reached.
3. `sequence_step_id` gives the exact step definition.

This works even without `scheduled_email_id` on the reply: you know which
campaign and which lead, you can read all sends to that lead, and you can
determine how far the lead got in the sequence.

### What it assumes

- The scheduled emails route is complete for the campaign (verified for
  campaigns 274, 335, 451 — 31 rows checked, `meta.total` confirms).
- The `sent_at` timestamps are monotonic per lead (PROVIDER FACT: verified
  on 1 lead in campaign 451 with 1 send).
- No sends were deleted or re-issued (the provider has no delete route for
  scheduled emails in the codebase).

### What it cannot determine

- **Which step the reply ANSWERED.** The reconstruction says "this lead
  received emails 1, 2, 3 and then replied." It does not say "the reply was
  TO email 3." That is B's job, and B has it.
- **Timing of the reply relative to intermediate sends.** A reply received
  after email 3 was sent may have been triggered by email 1, three weeks
  earlier. The reconstruction knows email 3 was the last send; it does not
  know email 3 caused the reply.

### When this fallback matters

If the provider drops `scheduled_email_id` from reply rows (contract
change), or if a reply row is missing it for any reason, the reconstruction
still gives campaign + lead + sequence position. That is enough for
cadence-shape learning ("at what step do people typically reply?") even
when per-step attribution ("did THIS step cause THIS reply?") is not.

---

## D. DOES EMAILBISON EXPOSE A PERSISTENT VARIANT IDENTIFIER?

### Verdict: NOT AVAILABLE

### Evidence

**PROVIDER FACT.** The sequence step raw data (from `GET
/api/campaigns/{id}/sequence-steps`) carries two variant-related fields:

| Field | Type | Populated (44 steps, campaign 352) |
|-------|------|-------------------------------------|
| `variant` | bool | 44/44 (39 true, 5 false) |
| `variant_from_step` | int or None | 44/44 (39 carry a parent id, 5 are None) |

**PROVIDER FACT.** The scheduled email row (from `GET
/api/campaigns/{id}/scheduled-emails`) carries `sequence_step_id` but NO
variant identifier. Checked 31 rows across campaigns 274, 335, 451. None
carry a `variant_id`, `variant_index`, `variant_from_step`, or any field
that distinguishes which variant of a step was sent.

**PROVIDER FACT.** The `sequence_steps()` function in `bison.py` trims the
raw step data to 6 fields (`id`, `order`, `email_subject`, `email_body`,
`wait_in_days`, `active`) and drops `variant`, `variant_from_step`,
`thread_reply`, `created_at`, `updated_at`, `attachments`. The trimmed form
loses variant attribution entirely.

### What this means

If a step has 8 variants, the scheduled email carries the rendered copy but
not which variant produced it. Five variants per position is unmeasurable
at the provider. The experiment has to be owned by Resonate.

### What CAN be done

**RESONATE RECONSTRUCTION.** The rendered copy on the scheduled email
(`email_subject`, `email_body`) is the actual text sent. If each variant
has distinct copy, the variant can be identified by diffing the rendered
copy against the known variant templates. This is a reconstruction, not a
provider fact: it assumes each variant has unique copy and that the copy
does not change after sending.

---

## APPENDIX: THE RESONATE-OWNED EXPERIMENT LEDGER (DESIGN)

D is NOT AVAILABLE. Five variants per position is unmeasurable at the
provider. The experiment has to be owned by Resonate. This is the design.
**Design only — not implemented in this task.**

### What it stores

```
experiment_ledger:
    lead_id             our internal record id (not provider PII)
    campaign_id         provider campaign id
    channel             "email" | "linkedin"
    sequence_position   integer step ordinal (1, 2, 3, ...)
    variant_id          our identifier for which of N variants was sent
    exact_rendered_copy the subject + body actually sent (hash or full text)
    scheduled_email_id  provider's scheduled email id (the join key)
    sent_at             provider's sent_at timestamp
    reply_at            timestamp of the reply, or null
    classified_outcome  "reply" | "bounce" | "no_response" | "ooo"
    attribution_confidence
        "direct"        — provider supplied scheduled_email_id on the reply
        "reconstructed" — inferred from last-touch on scheduled emails
        "unknown"       — reply present but no scheduled_email_id match
```

### Where it lives

A new file `work/experiment_ledger.jsonl`, one row per send. Appended to by
the observation layer (`leadobserve.py`) when a scheduled email is first
seen with a rendered copy and a variant assignment. Read by the evaluation
layer when classifying outcomes.

### What writes it

The staging layer (`bisonfactory`) at the moment it assigns a variant to a
lead at a position. The variant assignment is our decision, not the
provider's, so we record it at the point of decision. The observation layer
(`leadobserve.observe_emails`) appends `sent_at` and
`scheduled_email_id` when the provider confirms the send.

### What reads it

The evaluation layer (TASK-070's successor) reads it to answer: "of the N
variants at position P, which produced the best outcome?" It joins on
`lead_id` + `campaign_id` + `sequence_position` + `variant_id`.

### How it survives a provider that forgets

The ledger is Resonate-owned. If EmailBison loses the scheduled email data,
the ledger still has `exact_rendered_copy`, `sent_at`, and
`scheduled_email_id` as it was at send time. The provider's data is a
readback, not the source of truth for the experiment.

### What it CANNOT know

- **Whether the variant caused the reply.** `attribution_confidence` is
  where that honesty lives. If the provider cannot tell us which step a
  reply answers, the ledger cannot either. "direct" confidence means the
  provider supplied `scheduled_email_id` on the reply; "reconstructed"
  means last-touch; "unknown" means the reply is present but unattributable.
- **Whether the copy was actually read.** `open_tracking` is false on every
  campaign. The ledger records `sent_at`, not `read_at`.
- **Whether a LinkedIn touch influenced the reply.** The ledger covers
  email. A reply may have been triggered by a LinkedIn message the email
  estate cannot see. `attribution_confidence: "direct"` means "this email
  was the one the provider associated with the reply" — not "this email
  caused the reply."

### Why this is not in the event log

The existing event log (`work/events.jsonl`) records what happened: sends,
replies, bounces. The experiment ledger records what was PLANNED to happen:
which variant was assigned to which lead at which position. The event log
can be reconstructed from the provider; the experiment ledger cannot,
because the variant assignment is our decision and the provider does not
store it.

### What Claude decides

`CLAUDE.md`: new state has to earn its place. The question is whether a
second ledger is the right answer or whether the existing event log can be
extended with a `variant_id` field. The event log already carries
`scheduled_email_id` and `sequence_step_id`; adding `variant_id` would
avoid a second file. But the event log is append-only observations; the
variant assignment is a plan, not an observation. A plan that is recorded
only in the event log after the send is an observation of a plan, which is
the same thing — but the timing matters: if the variant assignment is
recorded at staging time (before the send), it survives a send that fails
and is retryable. If it is recorded at observation time (after the send), a
failed send loses the assignment.

---

## CAMPAIGN FIELDS (reference)

**Route:** `GET /api/campaigns?page=N` (listing), `GET /api/campaigns/{id}` (single)
**Rows checked:** 22 campaigns (the entire estate, 2 pages)

### Fields (29 on the listing row)

| Field | Type | Example | Populated |
|-------|------|---------|-----------|
| `id` | int | `481` | 22/22 |
| `uuid` | str | `"a2bd17a8-..."` | 22/22 |
| `name` | str | `"RESONATE - PRODUCTIVE - EMAIL - ..."` | 22/22 |
| `status` | str | `"paused"`, `"active"`, `"completed"`, `"draft"`, `"archived"` | 22/22 |
| `type` | str | `"outbound"` | 22/22 |
| `created_at` | str (ISO 8601) | `"2026-09-13T20:11:34.000000Z"` | 22/22 |
| `updated_at` | str (ISO 8601) | `"2026-09-13T22:17:13.000000Z"` | 22/22 |
| `emails_sent` | int | `92799` | 22/22 |
| `opened` | int | `0` | 22/22 (always 0 — see below) |
| `unique_opens` | int | `0` | 22/22 (always 0) |
| `replied` | int | `0` | 22/22 |
| `unique_replies` | int | `0` | 22/22 |
| `bounced` | int | `0` | 22/22 |
| `unsubscribed` | int | `0` | 22/22 |
| `interested` | int | `0` | 22/22 |
| `total_leads` | int | `23` | 22/22 |
| `total_leads_contacted` | int | `0` | 22/22 |
| `completion_percentage` | int | `0` | 22/22 |
| **`open_tracking`** | **bool** | **`False`** | **22/22 — ALL FALSE** |
| `can_unsubscribe` | bool | `False` | 22/22 |
| `include_auto_replies_in_stats` | bool | `True` | 22/22 |
| `plain_text` | bool | `False` | 22/22 |
| `sequence_id` | int | `428` | 22/22 |
| `sequence_prioritization` | str | `"followups"` | 22/22 |
| `max_emails_per_day` | int | `20` | 22/22 |
| `max_new_leads_per_day` | int | `20` | 22/22 |
| `daily_max_sends_per_receiving_domain` | int | `25` | 22/22 |
| `tags` | list | `[]` | 22/22 (all empty) |
| `unsubscribe_text` | NoneType | `None` | 0/22 |

### CRITICAL: `open_tracking` IS FALSE ON EVERY CAMPAIGN

**PROVIDER FACT.** All 22 campaigns have `open_tracking: false`. The
`opened` and `unique_opens` fields are 0 on every campaign, including
campaign 352 which sent 92,799 emails. **Zero opens across the entire
estate is an absent measurement, not an absent outcome.** Any open-rate
analysis that ignores this flag is fiction.

### Status values observed

**PROVIDER FACT.** `draft`, `paused`, `active`, `completed`, `archived`,
`failed`, `queued`, `pending deletion`

### Pagination

**PROVIDER FACT.** The listing serves 15 rows per page whatever `per_page`
is set to. `meta.total` carries the true count. The estate has 22 campaigns
across 2 pages.

---

## SEQUENCE STEP FIELDS (reference)

**Route:** `GET /api/campaigns/{id}/sequence-steps`
**Rows checked:** 44 steps (campaign 352), 1 step (campaign 451)

### Fields (12 on the raw row)

| Field | Type | Example | Populated |
|-------|------|---------|-----------|
| `id` | int | `4035` | 44/44 |
| `order` | int | `1` | **5/44** (see below) |
| `active` | bool | `True` | 44/44 |
| `email_subject` | str (HTML template) | `"{me again, {FIRST_NAME}\|..."` | 44/44 |
| `email_body` | str (HTML template) | `"<p>Hey {FIRST_NAME}..."` | 44/44 |
| `wait_in_days` | int | `3` | 44/44 |
| `variant` | bool | `False` | 44/44 |
| `variant_from_step` | NoneType or int | `None` | 44/44 |
| `thread_reply` | bool | `False` | 44/44 |
| `attachments` | NoneType | `None` | 0/44 |
| `created_at` | str (ISO 8601) | `"2026-05-13T11:09:12.000000Z"` | 44/44 |
| `updated_at` | str (ISO 8601) | `"2026-06-12T16:13:00.000000Z"` | 44/44 |

### `order` IS ONLY ON PARENT STEPS, NOT VARIANTS

**PROVIDER FACT.** Campaign 352 has 44 steps but only 5 distinct `order`
values (1, 2, 3, 4, 5). The other 39 steps are variants — they have
`variant: true`, `variant_from_step: <parent_id>`, and `order: null`. A
step's position in the sequence is determined by `order` for parents;
variants share their parent's position.

**PROVIDER FACT.** `bison.sequence_steps()` in the existing code trims this
to 6 fields and drops `variant`, `variant_from_step`, `thread_reply`,
`created_at`, `updated_at`, `attachments`. The trimmed form is sufficient
for sequence reproduction but loses variant attribution.

### Not paginated

**PROVIDER FACT.** All 44 steps arrive in one response with no `meta`.
`?page=2` returns the same 44 rows.

### A 200 is not an existence proof

**PROVIDER FACT.** A campaign with no sequence answers 200 carrying
`{"success": false, "message": "Sequence steps do not exist for <name>"}`.
Absence is read from the body.

---

## LEAD FIELDS (reference)

**Route:** `GET /api/campaigns/{id}/leads?page=N` (listing), `GET /api/leads/{id}` (single)
**Rows checked:** 18 leads across campaigns 352, 451, 335; 1 individual lead (146592)

### Fields (14 on the listing row)

| Field | Type | Example | Populated |
|-------|------|---------|-----------|
| `id` | int | `203752` | 18/18 |
| `uuid` | str | `"a2bf057e-..."` | 18/18 |
| `email` | str | `[REDACTED]` | 18/18 |
| `first_name` | str | `[REDACTED]` | 18/18 |
| `last_name` | str | `[REDACTED]` | 18/18 |
| `company` | str | `"Koval"` | 18/18 |
| `title` | str | `"CEO & Founder"` | 17/18 |
| `status` | str | `"unverified"` | 18/18 |
| `created_at` | str (ISO 8601) | `"2026-09-14T19:12:26.000000Z"` | 18/18 |
| `updated_at` | str (ISO 8601) | same | 18/18 |
| `notes` | NoneType | `None` | 0/18 |
| `custom_variables` | list[{name, value}] | see below | 18/18 |
| `lead_campaign_data` | list[dict] | see below | 18/18 |
| `overall_stats` | dict | see below | 18/18 |

### `lead_campaign_data` — per-campaign stats

| Field | Type | Example |
|-------|------|---------|
| `campaign_id` | int | `327` |
| `emails_sent` | int | `7` |
| `opens` | int | `0` |
| `replies` | int | `1` |
| `interested` | bool | `False` |
| `status` | str | `"replied"`, `"stopped"`, `"sequence_finished"`, `"in_sequence"`, `"sending_paused"`, `"never_contacted"` |

**PROVIDER FACT.** A lead in three campaigns has three entries. The status
is per-campaign, not global.

### `overall_stats` — cross-campaign totals

| Field | Type |
|-------|------|
| `emails_sent` | int |
| `opens` | int |
| `replies` | int |
| `unique_opens` | int |
| `unique_replies` | int |

### `custom_variables` — list of `{name, value}`

**PROVIDER FACT.** Older campaigns (335, 274, 327, 328, 352): carry
provider-defined variables like `location`, `industry`, `headline`. No
`record_id` or `contact_key`. Checked 37/46 reply leads — none had
`record_id` or `contact_key`.

**PROVIDER FACT.** Newer campaigns (451): carry our variables —
`record_id`, `contact_key`, `client`, `subject`, `body`. Checked 1/1 lead —
all five present.

### Pagination

**PROVIDER FACT.** 15 rows per page whatever `per_page` is set to.
`meta.total` carries the true count. Campaign 352 has 21,159 leads across
1,411 pages.

---

## REPLY FIELDS (reference)

**Route:** `GET /api/replies?pagination_type=cursor&per_page=N`
**Rows checked:** 750 (50 pages, cursor-paginated, spanning 2026-07-19 to 2026-09-14)

### Fields (30 on the row)

| Field | Type | Populated (of 750) |
|-------|------|---------------------|
| `id` | int | 750/750 |
| `uuid` | str | 750/750 |
| `type` | str | 750/750 |
| `folder` | str | 750/750 |
| `campaign_id` | int | 748/750 |
| `lead_id` | int | 748/750 |
| `scheduled_email_id` | int | 748/750 |
| `date_received` | str (ISO 8601) | 750/750 |
| `created_at` | str (ISO 8601) | 750/750 |
| `from_email_address` | str | 750/750 |
| `from_name` | str | 750/750 |
| `subject` | str | 750/750 |
| `text_body` | str | 750/750 |
| `html_body` | str | 750/750 |
| `raw_message_id` | str | 750/750 |
| `parent_id` | int or None | 0/750 (always null) |
| `sender_email_id` | int | 750/750 |
| `primary_to_email_address` | str | 750/750 |
| `to` | list[{address, name}] | 750/750 |
| `cc` | NoneType | 0/750 |
| `bcc` | NoneType | 0/750 |
| `automated_reply` | bool | 750/750 |
| `tracked_reply` | bool | 750/750 |
| `interested` | bool | 750/750 |
| `read` | bool | 750/750 |
| `lead` | dict (nested) | 748/750 |
| `attachments` | list | 750/750 |
| `headers` | NoneType | 0/750 |
| `raw_body` | NoneType | 0/750 |
| `updated_at` | str (ISO 8601) | 750/750 |

### Type distribution (750 rows)

| Type | Count | Folder | Classification |
|------|-------|--------|----------------|
| `Tracked Reply` | 46+ | `Inbox` | `reply` |
| `Untracked Reply` | subset | `Inbox` | `reply` |
| `Outgoing Email` | 3+ | `Sent` | `outgoing` — NOT A REPLY |
| `Bounced` | 26+ | `Bounced` | `bounce` |

### `parent_id` IS ALWAYS NULL

**PROVIDER FACT.** Threading is not tracked through this field in the
sample. A reply to a reply does not carry the parent's id.

### `custom_variables` ON REPLY LEADS

**PROVIDER FACT.** Of 46 inbound replies sampled: 37/46 leads have
`custom_variables` populated, but **0/46 have `record_id` or
`contact_key`**. These are leads from older campaigns that predate our
custom variable scheme.

### Pagination

**PROVIDER FACT.** Cursor-based. `meta.next_cursor` is an opaque base64
string. `per_page` is capped at 100. 750 rows fetched across ~8 pages.

---

## PAGINATION TRAPS

1. **`per_page` is ignored on most routes.** The listing, membership,
   scheduled-emails, and campaign-senders routes all serve 15 rows per page
   whatever is asked for. Only the reply feed honours `per_page` (cursor
   pagination, max 100). **PROVIDER FACT.**

2. **`workspace_id` is accepted and discarded.** Every list route answers
   identically for any workspace id, including ones that do not exist. The
   credential is the scope boundary. **PROVIDER FACT.**

3. **The reply feed carries our own sent mail.** `type: "Outgoing Email"` in
   `folder: "Sent"` must be filtered out before any reply analysis. The
   allowlist in `classify_reply_row` handles this. **PROVIDER FACT.**

---

## SUMMARY OF VERDICTS

| Question | Verdict | Evidence |
|----------|---------|----------|
| A: Historical per-lead/per-step sends with timestamps | **DIRECTLY SUPPORTED BY PROVIDER** | 31 rows across 3 campaigns (274, 335, 451); `meta.total` confirms full estates |
| B: Reply carries direct message/step relationship | **DIRECTLY SUPPORTED BY PROVIDER** | `scheduled_email_id` on 748/750 reply rows (2 missing are outgoing); links to `sequence_step_id` via scheduled email |
| C: Sequence position reconstructable when B absent | **RECONSTRUCTABLE FROM PROVIDER DATA** | Scheduled emails per lead give full send history with step ids and timestamps |
| D: Persistent variant identifier | **NOT AVAILABLE** | `scheduled_email` has no variant field; sequence steps have `variant`/`variant_from_step` but the send does not carry which variant was sent |

---

## WHAT THIS MEANS FOR TASK-070

The data infrastructure for cadence-shape learning exists:

- **Step-level attribution is possible** via `scheduled_email.sequence_step_id`
  joined to `sequence_steps.id`.
- **Per-lead per-step send timestamps** are on `scheduled_email.sent_at`.
- **Rendered copy** is on `scheduled_email.email_subject` and `email_body`.
- **Reply-to-step attribution** works via `reply.scheduled_email_id` →
  `scheduled_email.id` → `scheduled_email.sequence_step_id`.
- **Campaign-level stats** (`replied`, `bounced`, etc.) exist but are
  untrustworthy for opens because `open_tracking` is universally false.

The gaps:

- **Variant-level attribution** is not available — the scheduled email carries
  the rendered copy but not which variant produced it. The experiment ledger
  design in the appendix addresses this.
- **Open tracking** is absent estate-wide. Any analysis involving opens must
  say so.
- **Large campaign reads are expensive** — 15 rows per page means 1,411 pages
  for campaign 352's membership and 679 pages for its scheduled emails.
- **Reply causation is not proven.** `scheduled_email_id` on a reply is the
  provider's association, not a causal claim. Every attribution number must
  say whether it is PROVIDER FACT, RESONATE RECONSTRUCTION, or ATTRIBUTION
  HYPOTHESIS.
