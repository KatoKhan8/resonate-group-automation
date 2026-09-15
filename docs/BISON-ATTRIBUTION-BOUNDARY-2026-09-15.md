---
title: "EmailBison Attribution Boundary — what the provider can prove"
task: "TASK-141"
date: "2026-09-15"
supersedes: "docs/BISON-API-CAPABILITY-MAP-2026-09-14.md (section D: variant identity)"
---

# EmailBison Attribution Boundary — 2026-09-15

**TASK-141 deliverable.** The three lines in the data model: what the provider
states as fact, what we can reconstruct by joining provider rows, and what we
would be guessing. Every line has a route and a field behind it.

**Workspace:** PRODUCTIVE (id 10)
**Base URL:** `https://send.resonategroup.co/api`
**Probed:** 2026-09-15, read-only, no write route called.

---

## CORRECTION TO PRIOR DOCUMENTATION

`BISON-API-CAPABILITY-MAP-2026-09-14.md` section D stated:

> `sequence_step_variant` is an integer (e.g. 3, 4, 5, 7) ... The
> `sequence_step_variant` value in events is the step `id` of the variant
> that was sent, NOT a sequential index.

**That is wrong.** Live verification on 2026-09-15 shows `sequence_step_variant`
is a **sequential index within a parent step** (1=A, 2=B, 3=C...), not a step
id. Step ids are in the 4000s; variant index values observed are 2, 3, 5.
Cross-referenced three events against the step listing: the computed index
(sorted by step id within parent) matches the event value exactly.

| Event step_id | Event sequence_step_variant | Computed index | Parent step |
|---|---|---|---|
| 4042 | 2 | 2 | 4040 |
| 4195 | 5 | 5 | 4035 |
| 4193 | 3 | 3 | 4035 |

This correction matters because an index is not a persistent identifier. Step
ids are. The step id is the variant's identity; the index is its position in
creation order and may change if variants are added or reordered.

---

## LEVEL 1: PROVIDER FACT

What the provider states directly, on a single route, with no join required.

### 1.1 A reply belongs to a campaign

| Route | Field | Example |
|---|---|---|
| `GET /replies` | `campaign_id` | 352 |

**Confidence:** Direct. The field is on the reply row. No join.

### 1.2 A reply belongs to a lead

| Route | Field | Example |
|---|---|---|
| `GET /replies` | `lead_id` | 203757 |
| `GET /replies` | `lead.email` | (present, nested) |

**Confidence:** Direct. The field is on the reply row.

### 1.3 A reply is tracked or untracked

| Route | Field | Example |
|---|---|---|
| `GET /replies` | `type` | `Tracked Reply` / `Untracked Reply` |
| `GET /replies` | `tracked_reply` | true / false |

**Confidence:** Direct. `type` is a string enum; `tracked_reply` is a bool.
Both present on every reply row.

### 1.4 A reply points to a scheduled email (when tracked)

| Route | Field | Example |
|---|---|---|
| `GET /replies` | `scheduled_email_id` | 22310733 |

**Confidence:** Direct when present. `null` on untracked replies. This is
the join key to Level 2.

### 1.5 A scheduled email belongs to a sequence step

| Route | Field | Example |
|---|---|---|
| `GET /scheduled-emails/{id}` | `sequence_step_id` | 4036 |
| `GET /campaigns/{id}/scheduled-emails` | `sequence_step_id` | 4036 |

**Confidence:** Direct. Present on every scheduled email row. This is the
step identifier.

### 1.6 A sequence step is or is not a variant

| Route | Field | Example |
|---|---|---|
| `GET /campaigns/{id}/sequence-steps` | `variant` | true / false |
| `GET /campaigns/{id}/sequence-steps` | `variant_from_step` | 4035 (parent step id) |
| `GET /campaigns/{id}/sequence-steps` | `order` | null for variants, int for parents |

**Confidence:** Direct. These fields are on the step row.

### 1.7 An event carries step position and variant index

| Route | Field | Example |
|---|---|---|
| `GET /events` | `payload.data.scheduled_email.sequence_step_id` | 4042 |
| `GET /events` | `payload.data.scheduled_email.sequence_step_order` | 3 |
| `GET /events` | `payload.data.scheduled_email.sequence_step_variant` | 2 |

**Confidence:** Direct within the event payload. But the event log has a
**10-day retention window** — this is not available for historical analysis.

**Correction:** `sequence_step_variant` is a sequential index (1=A, 2=B, 3=C)
within a parent step, NOT a step id. It is not a persistent identifier.

### 1.8 A scheduled email was sent at a specific time

| Route | Field | Example |
|---|---|---|
| `GET /scheduled-emails/{id}` | `sent_at` | `2026-09-15T13:11:03.000000Z` |

**Confidence:** Direct. Present on sent rows. `null` on unsent rows.

### 1.9 A reply was received at a specific time

| Route | Field | Example |
|---|---|---|
| `GET /replies` | `date_received` | `2026-09-15T13:50:17.000000Z` |

**Confidence:** Direct.

---

## LEVEL 2: RECONSTRUCTION

What we can join from provider data by following keys across routes.

### 2.1 A reply can be joined to a specific sequence step

**Chain:**
```
reply.scheduled_email_id
  → GET /scheduled-emails/{scheduled_email_id}
  → response.sequence_step_id
```

**Verified live:**
- Reply 1609200 → `scheduled_email_id: 22310733`
- GET `/scheduled-emails/22310733` → `sequence_step_id: 4036`
- GET `/campaigns/352/sequence-steps` → step 4036: `variant: true, variant_from_step: 4035`

**Confidence:** High. Two-hop join on integer keys the provider returns. No
inference, no timestamp matching. The step id is a persistent identifier
that appears on both the scheduled email and the step listing.

**Cost:** One additional GET per reply (the scheduled email lookup). The step
listing is fetched once per campaign and cached.

**Alternative path (events only):**
```
EMAIL_SENT event → payload.data.scheduled_email.sequence_step_id
```
This avoids the extra GET but is limited to 10-day history.

### 2.2 A reply can be joined to a specific variant arm

**Chain:**
```
reply.scheduled_email_id
  → GET /scheduled-emails/{scheduled_email_id}
  → response.sequence_step_id     ← this IS the variant step id
  → GET /campaigns/{id}/sequence-steps
  → step.variant == true, step.variant_from_step == parent_id
```

**Verified live:**
- Reply 1609200 → scheduled_email 22310733 → step 4036
- Step 4036: `variant: true`, `variant_from_step: 4035`, `order: null`
- Step 4036 is variant index 1 of parent 4035 (sorted by step id)

**Confidence:** High. The `sequence_step_id` on the scheduled email IS the
variant step's own id when a variant was sent. There is no separate "variant
id" field — the step id is the variant identifier.

**What this means:** Variant-level attribution is RECONSTRUCTABLE from
provider data. It is not a guess. The chain is:

    reply → scheduled_email → step → (variant? true, parent: 4035)

### 2.3 A reply can be joined to a sequence position (step order)

**Chain:**
```
reply.scheduled_email_id
  → GET /scheduled-emails/{id}
  → response.sequence_step_id
  → GET /campaigns/{id}/sequence-steps
  → step.order (null for variants, int for parents)
```

**Confidence:** High for parent steps. Variants have `order: null` because
they share the parent's position. The position is the parent step's `order`.

### 2.4 A reply can be joined to the rendered email that produced it

**Chain:**
```
reply.scheduled_email_id
  → GET /scheduled-emails/{id}
  → response.email_subject (rendered, merge fields resolved)
  → response.email_body (rendered, merge fields resolved)
```

**Confidence:** High. The scheduled email carries the exact rendered content
that was sent. This is the email the reply is responding to.

**Caveat:** This is the email the provider *links* the reply to. Whether it
is actually the email that *caused* the reply is Level 3.

---

## LEVEL 3: HYPOTHESIS

What we would be guessing if we stopped here.

### 3.1 "The email that produced the reply"

The provider links a reply to a scheduled email via `scheduled_email_id`.
This is the email the reply is *threaded to* — it is the most recent email
in the thread the prospect is replying to.

**What this IS:** The last email sent to this lead before the reply, in this
campaign, that the provider could match.

**What this is NOT necessarily:** The email whose *content* caused the reply.
A prospect might reply to step 3 because of something in step 1. The
provider cannot know this. The threading relationship is a fact; the causal
attribution is a hypothesis.

**Confidence:** The threading link is a FACT (Level 1). The causal claim
"step N produced this reply" is a HYPOTHESIS — a plausible and often correct
one, but not provable from provider data alone.

### 3.2 "Variant A outperformed variant B"

Given that variant-level attribution is reconstructable (Level 2.2), we can
count:

- How many replies came from variant arm A (step 4036)
- How many came from variant arm B (step 4192)
- How many leads were sent variant A vs variant B (from scheduled emails)

**What this IS:** A comparison of reply rates across variant arms, where the
arm is identified by the step the provider actually sent.

**What this is NOT:** A controlled experiment. Variants are not randomly
assigned by the provider in a way that guarantees equal exposure. The
provider sends variants according to its own logic (likely round-robin or
weighted), and we do not observe the assignment mechanism.

**Confidence:** The counts are FACTS. The comparison is RECONSTRUCTABLE. The
claim that one variant *caused* more replies is a HYPOTHESIS — confounded by
lead quality, send time, sender, and the assignment mechanism.

### 3.3 "This reply is positive/negative/neutral"

The provider carries `interested` (bool) on both replies and scheduled
emails. But:

- `interested` is set by the operator (or automation), not by the provider
- It may not be set at all
- It is a binary flag, not a sentiment

**Classifying reply sentiment from text** requires NLP or human review. The
provider does not do this. Any sentiment label is a HYPOTHESIS unless a
human set it.

### 3.4 "The reply rate for step N is X%"

This requires knowing the denominator: how many leads reached step N. The
provider gives us:

- `GET /campaigns/{id}/scheduled-emails` filtered by `sequence_step_id` = N
  → count of scheduled emails for step N
- Of those, how many have `status: sent` → count of sends
- Of those, how many have a matching reply → count of replies

**What this IS:** The reply rate for emails sent at step N.

**What this is NOT:** The reply rate for *leads at step N*, because some
leads may have been stopped, bounced, or replied before reaching step N. The
denominator is sends, not leads.

**Confidence:** The counts are FACTS. The rate is RECONSTRUCTABLE. The
interpretation ("step N has a X% reply rate") is valid only if the
denominator is clearly stated as "emails sent at step N."

---

## THE STRONGEST DEFENSIBLE ANALYSIS

Given the boundaries above, here is what can be stated with confidence:

### What is defensible

1. **Step-level reply attribution is reconstructable.** For every tracked
   reply, we can identify the exact sequence step that sent the email the
   reply is threaded to. The chain is two hops on integer keys the provider
   returns. No timestamp matching, no inference.

2. **Variant-level reply attribution is reconstructable.** The step id on
   the scheduled email IS the variant step id when a variant was sent. We
   can identify which variant arm produced the email that each reply is
   threaded to.

3. **Per-step and per-variant reply counts are facts.** Given (1) and (2),
   we can count replies per step and per variant arm. These counts are
   provider facts.

4. **Per-step and per-variant reply rates are reconstructable.** Given the
   denominator (emails sent at each step/arm), the rate is a fact.

### What is not defensible

1. **Causal attribution.** "Step N caused this reply" is a hypothesis. The
   provider tells us which email the reply is threaded to, not which email
   caused the reply.

2. **Variant comparison as experiment.** "Variant A outperformed variant B"
   is a hypothesis unless the assignment mechanism is known and controlled.
   The provider sends variants; it does not randomize them in a way we can
   verify.

3. **Sentiment classification.** Reply sentiment is not in the provider
   data. Any sentiment label is a hypothesis unless set by a human.

4. **Open rates.** `open_tracking` is false estate-wide. Any number derived
   from open tracking is noise.

### What a variant experiment would need to become readable

Given that variant-level attribution is reconstructable, the gap is not
measurement but experimental design. To make a variant comparison
defensible:

1. **One campaign per arm.** If variant A and variant B are in separate
   campaigns, the campaign_id on the reply identifies the arm directly. No
   step join needed. This is the simplest design.

2. **A subject marker.** If variants have distinguishable subjects (e.g.,
   a marker in the subject line), the rendered `email_subject` on the
   scheduled email identifies the arm. This works even if the step join
   fails.

3. **A custom variable per arm.** EmailBison supports custom variables on
   leads. If variant A leads have `arm=A` and variant B leads have
   `arm=B`, the lead's `custom_variables` identify the arm. This survives
   even if the reply is untracked.

4. **Known assignment mechanism.** If the provider assigns variants
   round-robin, and we can verify this from the scheduled emails, then the
   assignment is effectively random and the comparison is defensible. We
   would need to check: for each lead, which variant was sent, and is the
   assignment independent of lead quality?

Without one of these, a variant comparison is a description of what
happened, not an experiment that proves causation.

---

## THE HIERARCHY IN ONE TABLE

| Question | Level | Route | Field | Confidence |
|---|---|---|---|---|
| Which campaign did this reply come from? | FACT | `/replies` | `campaign_id` | Direct |
| Which lead sent this reply? | FACT | `/replies` | `lead_id` | Direct |
| Is this reply tracked? | FACT | `/replies` | `type`, `tracked_reply` | Direct |
| Which scheduled email is this reply threaded to? | FACT | `/replies` | `scheduled_email_id` | Direct (null if untracked) |
| Which sequence step sent that email? | RECONSTRUCTION | `/scheduled-emails/{id}` | `sequence_step_id` | Two-hop join |
| Is that step a variant? | RECONSTRUCTION | `/campaigns/{id}/sequence-steps` | `variant`, `variant_from_step` | One-hop join from step |
| Which variant arm (A, B, C...) is this? | RECONSTRUCTION | `/campaigns/{id}/sequence-steps` | step id sorted within parent | Index by sort order |
| What was the step order (position)? | RECONSTRUCTION | `/campaigns/{id}/sequence-steps` | `order` (parent step) | One-hop join |
| What email content was sent? | RECONSTRUCTION | `/scheduled-emails/{id}` | `email_subject`, `email_body` | Direct on scheduled email |
| Did this step cause this reply? | HYPOTHESIS | — | — | Causal claim |
| Does variant A outperform variant B? | HYPOTHESIS | — | — | Requires controlled design |
| Is this reply positive/negative? | HYPOTHESIS | — | — | Requires NLP or human review |

---

## CONSEQUENCE FOR TASK-059

TASK-059 asks which email produced which reply. The honest answer, given
this boundary:

- **What TASK-059 can prove:** For each tracked reply, the scheduled email
  it is threaded to, the sequence step that sent it, and whether that step
  is a variant arm. This is reconstructable from provider data with two
  hops and no inference.

- **What TASK-059 cannot prove:** That the email it identified *caused* the
  reply. The threading link is the best available evidence, and it is
  strong, but it is not a causal proof.

- **What TASK-059 should state:** "Reply R is threaded to the email sent at
  step N on date D." Not "Step N produced reply R." The first is a fact;
  the second is a hypothesis.

If TASK-059 states the threading link and labels it as such, its answer is
checkable. If it states causal attribution, its answer is plausible but not
provable.

---

## ROUTES AND FIELDS — COMPLETE REFERENCE

### Reply fields (GET /replies, 31 fields)

```
id, uuid, type, folder, campaign_id, lead_id, scheduled_email_id,
sender_email_id, parent_id, subject, text_body, html_body, raw_body,
headers, date_received, created_at, updated_at, from_email_address,
from_name, primary_to_email_address, to, cc, bcc, automated_reply,
tracked_reply, interested, read, lead (nested dict), raw_message_id,
attachments
```

**Attribution-relevant:** `campaign_id`, `lead_id`, `scheduled_email_id`,
`type`, `tracked_reply`, `date_received`.

### Scheduled email fields (GET /scheduled-emails/{id}, 19 fields)

```
id, campaign_id, campaign (nested), sender_email (nested),
sequence_step_id, status, sent_at, scheduled_date, scheduled_date_local,
email_subject, email_body, opens, replies, unique_opens, unique_replies,
clicks, interested, thread_reply, raw_message_id
```

**Attribution-relevant:** `sequence_step_id`, `sent_at`, `status`,
`email_subject`, `email_body`.

**Note:** The individual form (`GET /scheduled-emails/{id}`) does NOT carry
a `lead` nested object. The listing form (`GET /campaigns/{id}/scheduled-emails`)
does. This is a real asymmetry.

### Sequence step fields (GET /campaigns/{id}/sequence-steps, 12 fields)

```
id, order, email_subject, email_body, wait_in_days, active, variant,
variant_from_step, thread_reply, attachments, created_at, updated_at
```

**Attribution-relevant:** `id`, `order`, `variant`, `variant_from_step`.

### Event payload fields (GET /events, scheduled_email sub-object)

```
id, lead_id, sequence_step_id, sequence_step_order,
sequence_step_variant, email_subject, email_body, status, sent_at,
scheduled_date_local, scheduled_date_est, local_timezone, opens,
replies, unique_opens, unique_replies, interested, raw_message_id
```

**Attribution-relevant:** `sequence_step_id`, `sequence_step_order`,
`sequence_step_variant`.

**Limitation:** 10-day retention. Not suitable for full historical analysis.

**Correction:** `sequence_step_variant` is a sequential index (1, 2, 3...)
within a parent step, NOT a step id.

---

## VERIFICATION SCRIPTS

- `scripts/task141_verify_attribution.py` — end-to-end chain verification
- `scripts/task141_variant_index.py` — variant index vs step id cross-check

Both are read-only. No write route called.
