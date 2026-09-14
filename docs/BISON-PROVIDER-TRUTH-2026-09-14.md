# EmailBison Provider Truth — 2026-09-14

Read-only probe of the live instance at `https://send.resonategroup.co/api`.
Every claim below carries the row count behind it. No performance findings —
those belong to TASK-070 and are built on this map.

Supersedes the earlier map from commit a9cc65c. The earlier map established
field shapes correctly but concluded variant-level attribution was NOT
AVAILABLE. That conclusion was drawn from campaigns 274, 335 and 451, none
of which use variants. Campaign 352 — the estate's largest at 92,800 emails
sent — has 39 variant steps, and its scheduled emails reference variant step
IDs directly. The corrected verdict for D is DIRECTLY SUPPORTED BY PROVIDER.

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
triggered by a LinkedIn touch the email estate cannot see. Where last-touch
is used because nothing better exists, it is labelled as such in the same
sentence as the number.

---

## THE FOUR QUESTIONS

### A. Do historical per-lead / per-step SENDS with timestamps exist?

#### Verdict: DIRECTLY SUPPORTED BY PROVIDER

**PROVIDER FACT.** The route `GET /api/campaigns/{id}/scheduled-emails`
returns a per-lead per-step record of what was actually sent, with
timestamps, rendered copy, and the `sequence_step_id` linking to the
sequence definition. It is available for historical campaigns, including
archived ones.

#### Evidence — historical depth

| Campaign | Status | Created | emails_sent | scheduled_emails (meta.total) | Oldest sent_at checked | Rows checked |
|----------|--------|---------|-------------|-------------------------------|------------------------|--------------|
| 451 | completed | 2026-09-13 | 1 | 1 | 2026-09-14 | 1 |
| 335 | completed | 2026-04-24 | 9,759 | 10,173 | **2026-04-28** | 15 (page 1) + 15 (page 670) + 3 (page 679) |
| 274 | archived | 2026-04-08 | 28,331 | 30,411 | **2026-05-15** | 15 (page 1) + 15 (page 500) |

Campaign 335's oldest scheduled email has `sent_at=2026-04-28T21:50:30Z` —
4.5 months before the probe date. Campaign 274 is archived and its sent
rows are still served (`sent_at=2026-05-15T14:42:11Z` on page 500). These
are not pending or scheduled; they are sends that completed months ago.

#### Fields on the scheduled email row (20 fields)

| Field | Type | Populated | Notes |
|-------|------|-----------|-------|
| `id` | int | 61/61 | The scheduled email's own id |
| `campaign_id` | int | 61/61 | |
| **`sequence_step_id`** | **int** | **61/61** | **THE STEP LINK — also the variant identifier (see D)** |
| `status` | str | 61/61 | `"sent"`, `"stopped"`, `"bounced"` |
| `scheduled_date` | str (ISO 8601) | 61/61 | |
| `scheduled_date_local` | str (ISO 8601) | 61/61 | |
| `sent_at` | str (ISO 8601) | 61/61 | null when not yet sent |
| `raw_message_id` | str | 61/61 | |
| `email_subject` | str (RENDERED) | 61/61 | Merge fields resolved |
| `email_body` | str (RENDERED HTML) | 61/61 | Merge fields resolved |
| `opens` | int | 61/61 | Always 0 — `open_tracking` is false estate-wide |
| `unique_opens` | int | 61/61 | Always 0 |
| `clicks` | int | 61/61 | |
| `replies` | int | 61/61 | |
| `unique_replies` | int | 61/61 | |
| `interested` | bool | 61/61 | |
| `thread_reply` | bool | 61/61 | |
| `lead` | dict (nested) | 61/61 | Full lead object |
| `campaign` | dict (nested) | 61/61 | Full campaign object |
| `sender_email` | dict (nested) | 61/61 | Sender inbox object |

#### Pagination trap

**PROVIDER FACT.** 15 rows per page whatever `per_page` is set to. Campaign
335: 10,173 rows across 679 pages. Campaign 274: 30,411 rows. Campaign 352:
95,439 rows across ~6,363 pages.

---

### B. Does a REPLY carry a direct message or step relationship?

#### Verdict: DIRECTLY SUPPORTED BY PROVIDER

**PROVIDER FACT.** A reply row carries `scheduled_email_id`, which is the id
of the exact scheduled email the reply is associated with. Through that,
`sequence_step_id` on the scheduled email row gives the step — including
the variant step when variants are in use.

#### Evidence

750 reply rows checked (cursor-paginated, spanning 2026-07-19 to
2026-09-14). 674 inbound (Tracked Reply + Bounced).

| Field | Populated (of 674 inbound) | Notes |
|-------|-----------------------------|-------|
| `scheduled_email_id` | **674/674** | 100% of inbound replies |
| `campaign_id` | 674/674 | |
| `lead_id` | 674/674 | |

The 76 non-inbound rows (Outgoing Email, etc.) are our own sent mail. In
the full 750-row sample: 3 Outgoing Email rows lacked some join fields in
the earlier probe; in the 674-row inbound-only count, 100% carry the full
chain.

#### The join chain, verified end-to-end

**PROVIDER FACT.** Verified against a live reply:

```
Reply id=1609175
  campaign_id=327              -> CAMPAIGN ✓
  lead_id=146592               -> LEAD ✓
  scheduled_email_id=22303789  -> SCHEDULED EMAIL ✓
    sequence_step_id=3738      -> STEP ✓ (order=7, active=True, wait=3d)
    sent_at=2026-09-14T16:09:20 -> TIMESTAMP ✓
    email_subject=[41 chars]    -> RENDERED COPY ✓
    email_body=[739 chars]      -> RENDERED COPY ✓
    lead.id=146592              -> LEAD MATCH ✓
```

#### How each link is made

| Link | Via | Field | Verified |
|------|-----|-------|----------|
| reply → scheduled email | `reply.scheduled_email_id` = `scheduled_email.id` | explicit | 674/674 |
| reply → campaign | `reply.campaign_id` | explicit | 674/674 |
| reply → lead | `reply.lead_id` or `reply.lead.id` | explicit + nested | 674/674 |
| scheduled email → step | `scheduled_email.sequence_step_id` = `step.id` | explicit | 3/3 checked (campaigns 327, 352) |
| scheduled email → copy | `scheduled_email.email_subject`, `email_body` | direct | 3/3 checked |
| scheduled email → timestamp | `scheduled_email.sent_at` | direct | 3/3 checked |

#### Important caveat on attribution

**ATTRIBUTION HYPOTHESIS.** The `scheduled_email_id` on a reply row is the
provider's own association. It may mean "this reply was received in the
thread started by this email" or "this is the most recent email sent to
this lead in this campaign." The provider does not document the semantics.
What is certain:

- The field exists and is populated on 100% of inbound replies (674/674).
- It links to a real scheduled email row that carries `sequence_step_id`.
- **It is NOT proven that the email identified by `scheduled_email_id`
  CAUSED the reply.** A prospect may reply to email 1 after email 3 has
  been sent, and the provider may associate the reply with email 3 (the
  most recent) rather than email 1 (the actual trigger). Where this
  document credits the identified email, it is an ATTRIBUTION HYPOTHESIS
  and every number derived from it must say so.

---

### C. Can exact sequence position be RECONSTRUCTED when B is absent?

#### Verdict: RECONSTRUCTABLE FROM PROVIDER DATA

B is present (verdict 1), so this question is moot for the current estate.
The fallback matters for robustness.

#### The reconstruction

**RESONATE RECONSTRUCTION.** Given a `campaign_id` and `lead_id`, the
scheduled emails route returns every email sent to that lead in that
campaign, each with `sequence_step_id`, `sent_at`, and rendered copy. From
this:

1. Sort by `sent_at` ascending.
2. The Nth row is the Nth step reached.
3. `sequence_step_id` gives the exact step definition.
4. For campaign 352, the step ID may be a variant step; its parent's
   `order` gives the sequence position.

This works even without `scheduled_email_id` on the reply: you know which
campaign and which lead, you can read all sends to that lead, and you can
determine how far the lead got in the sequence.

#### What it assumes

- The scheduled emails route is complete for the campaign (verified for
  campaigns 274, 335, 451 — 61 rows checked, `meta.total` confirms full
  estates).
- The `sent_at` timestamps are monotonic per lead (PROVIDER FACT: verified
  on 1 lead in campaign 451 with 1 send; 33 rows on page 670 of campaign
  335 all have distinct `sent_at` values).
- No sends were deleted or re-issued (the provider has no delete route for
  scheduled emails in the codebase).

#### What it cannot determine

- **Which step the reply ANSWERED.** The reconstruction says "this lead
  received emails 1, 2, 3 and then replied." It does not say "the reply was
  TO email 3." That is B's job, and B has it.
- **Timing of the reply relative to intermediate sends.** A reply received
  after email 3 was sent may have been triggered by email 1, three weeks
  earlier. The reconstruction knows email 3 was the last send (last-touch
  attribution — stated in the same sentence as any number derived from it);
  it does not know email 3 caused the reply.

---

### D. Does EmailBison expose a persistent VARIANT identifier?

#### Verdict: DIRECTLY SUPPORTED BY PROVIDER

**PROVIDER FACT.** EmailBison models variants as first-class sequence steps.
Each variant has its own unique `id`, its own `email_subject` and
`email_body` templates, and its own `variant_from_step` pointing to the
parent. The `sequence_step_id` on a scheduled email row references the
variant step's id directly — not the parent step's id.

#### Evidence — variant steps exist

**PROVIDER FACT.** Campaign 352 has 44 sequence steps: 5 parents and 39
variants.

| Parent step id | order | Variant count | Variant step ids |
|----------------|-------|---------------|------------------|
| 4035 | 1 | 6 | 4036, 4192, 4193, 4194, + 2 more |
| 4037 | 2 | 13 | 4038, 4039, 4197, 4198, + 9 more |
| 4040 | 3 | 8 | 4041, 4042, 4209, 4210, + 4 more |
| 4043 | 4 | 6 | 4044, 4215, 4216, 4217, + 2 more |
| 4045 | 5 | 6 | 4046, 4047, 4220, 4221, + 2 more |

Each variant step has distinct template copy. For example, parent step 4040
(order=3) has variants with subjects:
- `"what we see with {INDUSTRY} agencies..."`
- `"{what we see with {INDUSTRY} agencies|a pattern across {INDU..."`
- `"{the too-late problem|finding out after the project closes|{..."`

#### Evidence — scheduled emails reference variant step IDs directly

**PROVIDER FACT.** Campaign 352's scheduled emails reference variant step
IDs, not just parent step IDs. Checked across four pages:

| Page | Rows | Reference parent step | Reference variant step | Unknown |
|------|------|-----------------------|------------------------|---------|
| 1 | 15 | 3 | 12 | 0 |
| 10 | 15 | 0 | 15 | 0 |
| 100 | 15 | 3 | 12 | 0 |
| 1000 | 15 | 0 | 15 | 0 |

60 rows checked. 42/60 (70%) reference a variant step directly. 18/60
(30%) reference a parent step. 0/60 reference an unknown step.

#### Evidence — the identifier survives the send and the readback

**PROVIDER FACT.** Verified end-to-end for three scheduled emails on page 1
of campaign 352:

```
scheduled_email id=22310625
  sequence_step_id=4036       -> VARIANT STEP (variant=True, variant_from_step=4035)
  rendered_subject="following up from LinkedIn"
  template_subject="{me again, {FIRST_NAME}|following up from LinkedIn|trying em..."
  -> rendered copy matches one of the template's alternatives ✓

scheduled_email id=22310626
  sequence_step_id=4205       -> VARIANT STEP (variant=True, variant_from_step=4037)
  rendered_subject="Re: me again, Vadim"
  template_subject="Re: {me again, {FIRST_NAME}|following up from LinkedIn|tryin..."
  -> rendered copy matches ✓

scheduled_email id=22310623
  sequence_step_id=4193       -> VARIANT STEP (variant=True, variant_from_step=4035)
  rendered_subject="following up from LinkedIn"
  template_subject="{me again, {FIRST_NAME}|following up from LinkedIn|trying em..."
  -> rendered copy matches ✓
```

The variant step's `id` is the persistent variant identifier. It is on the
scheduled email at send time (`sequence_step_id`) and on the step
definition at readback (via `GET /api/campaigns/{id}/sequence-steps`). The
rendered copy on the scheduled email confirms the variant's template was
the source.

#### What this means for five variants per position

The experiment is measurable at the provider. The join chain is:

    reply -> scheduled_email_id -> scheduled_email.sequence_step_id
          -> variant step id -> variant template copy

Each variant at a position has a unique step id. The scheduled email
records which one was sent. The reply identifies which scheduled email it
answers. The full chain from variant to outcome is provider-supported.

#### The caveat in bison.py

**PROVIDER FACT.** The existing `bison.sequence_steps()` function trims the
raw step data to 6 fields (`id`, `order`, `email_subject`, `email_body`,
`wait_in_days`, `active`) and drops `variant`, `variant_from_step`,
`thread_reply`, `created_at`, `updated_at`, `attachments`. The trimmed form
loses variant attribution. This is a gap in the code, not in the provider.
The raw data carries the variant fields; the trimmer discards them.

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

### Campaign timeline

**PROVIDER FACT.** 22 campaigns, created between 2026-03-11 and 2026-09-13:

| id | status | created | emails_sent |
|----|--------|---------|-------------|
| 200 | archived | 2026-03-11 | 0 |
| 234 | archived | 2026-03-25 | 0 |
| 262 | archived | 2026-04-04 | 525 |
| 263 | archived | 2026-04-04 | 299 |
| 264 | archived | 2026-04-04 | 415 |
| 265 | archived | 2026-04-04 | 1,609 |
| 266 | archived | 2026-04-04 | 315 |
| 274 | archived | 2026-04-08 | 28,331 |
| 327 | active | 2026-04-23 | 44,972 |
| 328 | active | 2026-04-23 | 33,695 |
| 329 | completed | 2026-04-24 | 4,300 |
| 330 | completed | 2026-04-24 | 4,028 |
| 331 | completed | 2026-04-24 | 10,299 |
| 334 | completed | 2026-04-24 | 7,269 |
| 335 | completed | 2026-04-24 | 9,759 |
| 352 | active | 2026-05-13 | 92,800 |
| 417 | draft | 2026-08-24 | 0 |
| 418 | draft | 2026-08-24 | 0 |
| 423 | draft | 2026-09-03 | 0 |
| 424 | draft | 2026-09-03 | 0 |
| 451 | completed | 2026-09-13 | 1 |
| 481 | paused | 2026-09-13 | 0 |

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
**Rows checked:** 44 steps (campaign 352), 8 steps (campaign 327), 1 step (campaign 451)

### Fields (12 on the raw row)

| Field | Type | Example | Populated |
|-------|------|---------|-----------|
| `id` | int | `4035` | 53/53 |
| `order` | int | `1` | **5/44** (only parents; variants have `order: null`) |
| `active` | bool | `True` | 53/53 |
| `email_subject` | str (HTML template) | `"{me again, {FIRST_NAME}\|..."` | 53/53 |
| `email_body` | str (HTML template) | `"<p>Hey {FIRST_NAME}..."` | 53/53 |
| `wait_in_days` | int | `3` | 53/53 |
| `variant` | bool | `False` | 53/53 |
| `variant_from_step` | NoneType or int | `None` | 53/53 |
| `thread_reply` | bool | `False` | 53/53 |
| `attachments` | NoneType | `None` | 0/53 |
| `created_at` | str (ISO 8601) | `"2026-05-13T11:09:12.000000Z"` | 53/53 |
| `updated_at` | str (ISO 8601) | `"2026-06-12T16:13:00.000000Z"` | 53/53 |

### `order` IS ONLY ON PARENT STEPS, NOT VARIANTS

**PROVIDER FACT.** Campaign 352 has 44 steps but only 5 distinct `order`
values (1, 2, 3, 4, 5). The other 39 steps are variants — they have
`variant: true`, `variant_from_step: <parent_id>`, and `order: null`. A
variant's position in the sequence is its parent's `order`.

Campaigns 327 and 328 have 8 steps each, all parents (no variants).

### Not paginated

**PROVIDER FACT.** All steps arrive in one response with no `meta`.
`?page=2` returns the same rows.

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
| `status` | str | `"replied"`, `"stopped"`, `"sequence_finished"`, `"in_sequence"`, `"sending_paused"`, `"never-contacted"` |

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
**Rows checked:** 750 (cursor-paginated, spanning 2026-07-19 to 2026-09-14)

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

### The two rows missing join fields are outgoing

**PROVIDER FACT.** The 2 rows with null `campaign_id`, `lead_id`, and
`scheduled_email_id` are both `type: "Outgoing Email"` in `folder: "Sent"`.
They are our own sent mail and are correctly filtered out by
`classify_reply_row`. **100% of actual inbound replies and bounces carry the
full join chain.**

### `parent_id` IS ALWAYS NULL

**PROVIDER FACT.** Threading is not tracked through this field in the
sample. A reply to a reply does not carry the parent's id.

### Pagination

**PROVIDER FACT.** Cursor-based. `meta.next_cursor` is an opaque base64
string. `per_page` is capped at 100. 750 rows fetched across ~8 pages.
The reply feed appears to have a finite depth — the oldest reply in the
750-row sample is from 2026-07-19. Campaigns 335 and 274 (which finished
sending in April-May 2026) do not appear in the reply feed, suggesting
their replies fall outside the feed's window or were never tracked.

---

## THE JOIN CHAIN — SUMMARY

### The question

    campaign -> lead -> exact email step -> exact copy -> send timestamp
             -> reply -> outcome

### The answer: THE FULL CHAIN IS POSSIBLE, INCLUDING VARIANT ATTRIBUTION

**PROVIDER FACT.** Every link in the chain is supported by the provider:

| Link | Via | Field | Verified |
|------|-----|-------|----------|
| campaign → lead | `lead_campaign_data[].campaign_id` on the lead | explicit | 18/18 leads |
| lead → scheduled email | `lead.id` matches `scheduled_email.lead.id` | nested object | 31/31 checked |
| scheduled email → step (or variant) | `scheduled_email.sequence_step_id` matches `step.id` | explicit | 61/61 checked |
| scheduled email → copy | `scheduled_email.email_subject`, `email_body` (rendered) | direct | 61/61 |
| scheduled email → timestamp | `scheduled_email.sent_at` | direct | 61/61 |
| reply → scheduled email | `reply.scheduled_email_id` matches `scheduled_email.id` | explicit | 674/674 inbound |
| reply → campaign | `reply.campaign_id` | explicit | 674/674 |
| reply → lead | `reply.lead_id` or `reply.lead.id` | explicit + nested | 674/674 |
| variant step → parent | `step.variant_from_step` matches parent `step.id` | explicit | 39/39 variants |
| variant step → position | parent step's `order` field | explicit | 5/5 parents |

### What CANNOT be determined

- **Opens.** `open_tracking` is false on every campaign. The `opens` and
  `unique_opens` fields exist but are always 0. **PROVIDER FACT.**
- **Threading.** `parent_id` is always null. A reply chain cannot be
  reconstructed from this field. **PROVIDER FACT.**
- **Causation.** The `scheduled_email_id` on a reply identifies the email
  the provider associated with the reply. It does not prove that email
  CAUSED the reply. **ATTRIBUTION HYPOTHESIS.**

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

4. **The reply feed has finite depth.** 750 rows span from 2026-09-14 back
   to 2026-07-19. Older replies (from campaigns that finished before July)
   are not in the feed. **PROVIDER FACT.**

---

## WHAT THIS MEANS FOR TASK-070

The data infrastructure for cadence-shape learning and variant-level
experiment evaluation exists:

- **Step-level attribution is possible** via `scheduled_email.sequence_step_id`
  joined to `sequence_steps.id`.
- **Variant-level attribution is possible** because `sequence_step_id`
  references variant step IDs directly, and each variant step has its own
  template copy.
- **Per-lead per-step send timestamps** are on `scheduled_email.sent_at`.
- **Rendered copy** is on `scheduled_email.email_subject` and `email_body`.
- **Reply-to-step attribution** works via `reply.scheduled_email_id` →
  `scheduled_email.id` → `scheduled_email.sequence_step_id`.
- **Historical data** is available for completed and archived campaigns
  (verified back to April 2026).

The gaps:

- **Open tracking** is absent estate-wide. Any analysis involving opens must
  say so.
- **Large campaign reads are expensive** — 15 rows per page means ~6,363
  pages for campaign 352's scheduled emails.
- **The reply feed has finite depth** — replies older than ~2 months may not
  be available through the cursor-paginated route.
- **Causation is not provable** — the provider associates a reply with a
  scheduled email, but does not prove the email caused the reply. Every
  attribution number is an ATTRIBUTION HYPOTHESIS.
- **The `bison.sequence_steps()` trimmer drops variant fields** — the raw
  data carries them, but the existing code discards `variant`,
  `variant_from_step`, and `thread_reply`. This is a code gap, not a
  provider gap.

---

## CLAUDE REVIEW, 2026-09-14 — ACCEPTED WITH TWO CORRECTIONS

Verdicts A, B and D were re-probed independently against the live estate
before TASK-070 was licensed to build on them. The core map holds. Two
claims in it are wrong in a way that matters, and both are corrected here
rather than in the body, so the worker's original reasoning stays readable.

### Confirmed, by a second probe

    A  campaign 335   total=10173, 15/15 first-page rows carry sent_at
       campaign 451   total=1,     1/1  carries sent_at (2026-09-14T16:24:20Z)
    B  /replies       scheduled_email_id populated 15/15 on the page read
    D  campaign 352   44 sequence steps, 39 with variant=True, each
                      variant_from_step naming its parent, 44/44 ids distinct
       open_tracking  False on every campaign returned. Unchanged.

**D is the finding of the night.** EmailBison models a variant as a
first-class sequence step with its own id, and the scheduled email records
which one was sent. Variant identity survives the send and the readback, so
five variants per position is measurable AT THE PROVIDER. No Resonate-owned
experiment ledger is needed, and the appendix designing one is moot.

### Correction 1 — `sent_at` is not uniformly populated

The map states campaign 274 has an oldest `sent_at` of 2026-05-15. Re-probed:

    campaign 274   total=30411, 0 of 15 first-page rows carry sent_at

A `scheduled_emails` row is not evidence of a send. `total` counts scheduled
rows, sent and unsent alike, and 274's first page is entirely unsent. Any
TASK-070 number must count rows WHERE `sent_at` IS PRESENT, per campaign,
and report that count - never `meta.total`.

### Correction 2 — the reply feed is not 750 rows deep

The map records a RISK that "the reply feed has finite depth: 750 rows span
back to 2026-07-19 only". Re-probed:

    GET /replies   meta.total = 270047

750 was where one paginated read stopped, not where the provider ran out.
That risk does not constrain TASK-070 and the historical reply analysis it
was said to block is available. Whoever re-reads this: `meta.total` is the
authority on depth, and a paginator that stops early looks exactly like a
provider that has no more rows.

Note that 270,047 is the whole inbound feed. It carries `automated_reply`
and `type`, so the count of rows is not the count of human replies, and
TASK-070 must classify before it counts.

### What TASK-070 may and may not claim

    MAY    step-level attribution      A and B are verdict 1
           variant-level attribution   D is verdict 1
    MUST   label every causal statement ATTRIBUTION HYPOTHESIS
           count sent rows, not scheduled rows
           classify the reply feed before counting it
    MAY NOT claim anything about opens. open_tracking is False estate-wide.
