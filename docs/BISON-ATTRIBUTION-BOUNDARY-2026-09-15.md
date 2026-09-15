---
title: "EmailBison Attribution Boundary — what the provider can prove about a reply"
task: "TASK-141"
date: "2026-09-15"
builds_on:
  - "docs/BISON-API-CAPABILITY-MAP-2026-09-14.md"
  - "docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md"
---

# EmailBison Attribution Boundary — 2026-09-15

**TASK-141 deliverable.** Every line in the data model classified as FACT,
RECONSTRUCTION, or HYPOTHESIS, with the route and field behind each line.

**Workspace:** PRODUCTIVE (id 10).
**Probed:** 2026-09-15, read-only. No write route was called.
**Scripts:** `scripts/task141_attribution_probe.py`, `scripts/task141_variant_edge.py`.

This document does not restate the route inventory in
`BISON-API-CAPABILITY-MAP-2026-09-14.md` or the evidence map in
`BISON-API-ROUTE-EVIDENCE-2026-09-15.md`. It draws three lines through the
data those routes return and says what each side of each line is.

---

## The three categories

| Category | Meaning | Confidence |
|---|---|---|
| **FACT** | The provider returned this value on a response. It is what EmailBison stated. | Provider-stated |
| **RECONSTRUCTION** | We joined two or more provider rows to infer this. Every field in the join came from the provider, but the connection is ours. | Derived from provider data |
| **HYPOTHESIS** | We believe this but the provider does not state it and no join of provider rows produces it. | Our guess |

---

## 1. THE HIERARCHY: campaign → sequence → step → lead → variant → send → reply → outcome

### 1.1 CAMPAIGN

**FACT.** A reply carries `campaign_id` directly on the reply row.

| Route | Field | Example |
|---|---|---|
| `GET /replies` | `campaign_id` | `352` |
| `GET /campaigns` | `id`, `name`, `status` | `352`, `HeyReach Connection Campaign`, `active` |

The campaign's `open_tracking` is `false` estate-wide (campaign 451, all
others). Any open count or open rate derived from this field is noise. The
provider states `open_tracking: false`; we state "opens are not measured."

**No reconstruction needed.** The reply names its campaign.

---

### 1.2 SEQUENCE

**FACT.** A campaign carries `sequence_id` on the campaign row.

| Route | Field | Example |
|---|---|---|
| `GET /campaigns/{id}` | `sequence_id` | `int` |

**RECONSTRUCTION.** The sequence is the set of steps belonging to a
campaign, obtained by `GET /campaigns/{id}/sequence-steps`. The sequence
has no independent route — it is the step listing.

**No hypothesis.** The sequence is fully determined by the campaign.

---

### 1.3 STEP

**RECONSTRUCTION.** A reply does NOT carry `sequence_step_id`. The join is
two hops:

    reply.scheduled_email_id
        → GET /scheduled-emails/{id}
            → sequence_step_id

This was verified live on five replies:

| Reply | `scheduled_email_id` | → `sequence_step_id` | Route chain |
|---|---|---|---|
| 1609203 | 22310389 | 4035 | reply → sched email → step |
| 1609202 | 22314331 | 3741 | reply → sched email → step |
| 1609200 | 22310733 | 4036 | reply → sched email → step |
| 1609192 | 22313165 | 3745 | reply → sched email → step |
| 1609187 | 22313879 | 3745 | reply → sched email → step |

**The field that decides:** `scheduled_email_id` on the reply row. When
present and non-null, the step is reachable. When null (untracked reply),
the step is unreachable by provider data.

**The step's `order` field** is available on the sequence-steps listing
(`GET /campaigns/{id}/sequence-steps`, field `order`). It is also available
on events (`payload.data.scheduled_email.sequence_step_order`), but events
have a 10-day history.

**HYPOTHESIS.** "This step caused the reply." The provider states that this
email was sent to this lead at this step. It does not state that the email
caused the reply. Temporal succession is ours to claim.

---

### 1.4 LEAD

**FACT.** A reply carries `lead_id` directly, and a nested `lead` dict with
`id`, `uuid`, `first_name`, `last_name`, `email`, `company`, `status`,
`custom_variables`.

| Route | Field | Example |
|---|---|---|
| `GET /replies` | `lead_id` | `203727` |
| `GET /replies` | `lead.email` | (address present) |
| `GET /replies` | `lead.custom_variables` | `[{name, value}]` |

**No reconstruction needed.** The reply names its lead.

---

### 1.5 VARIANT

This is the level where the boundary matters most. The finding is that
variant identity IS available from provider data, but through a mechanism
that requires understanding the step model.

#### The step model

A sequence step is either a **parent** (`variant: false`) or a **variant**
(`variant: true`, `variant_from_step: <parent_id>`). Verified on campaign
352 (44 steps, 39 variants) and campaign 328 (8 steps, 0 variants).

Campaign 352 structure (verified live):

```
step 4035: order=1, parent,    variant_from_step=None
step 4036: order=None, VARIANT, variant_from_step=4035
step 4192: order=None, VARIANT, variant_from_step=4035
step 4193: order=None, VARIANT, variant_from_step=4035
step 4194: order=None, VARIANT, variant_from_step=4035
step 4195: order=None, VARIANT, variant_from_step=4035
step 4196: order=None, VARIANT, variant_from_step=4035
step 4037: order=2, parent,    variant_from_step=None
...
```

#### How variant identity travels

**FACT.** When EmailBison sends a variant, the scheduled email's
`sequence_step_id` is the VARIANT step's id, not the parent's. Verified
live:

| Scheduled email | `sequence_step_id` | Step `variant`? | Variant of |
|---|---|---|---|
| 22310733 | 4036 | **True** | step 4035 |
| 22310389 | 4035 | **False** (parent) | — |

Both sends are in campaign 352. Both are to step 4035's family. But one
points to the parent and the other to variant step 4036. The provider
distinguishes them.

**RECONSTRUCTION.** To resolve whether a scheduled email was a variant:

1. `GET /scheduled-emails/{id}` → `sequence_step_id`
2. `GET /campaigns/{id}/sequence-steps` → find step with that id
3. If `variant: true` → the step id IS the variant identifier
4. If `variant: false` → no variant was used; the parent copy was sent

This join is fully determined by provider data. No guessing.

**FACT (events).** The events endpoint carries `sequence_step_variant`, a
1-based positional index among sibling variants. Verified live:

| Event | `sequence_step_id` | `sequence_step_variant` | Step |
|---|---|---|---|
| 232720 | 4042 | 2 | variant of 4040, 2nd sibling |
| 232718 | 4195 | 5 | variant of 4035, 5th sibling |
| 232716 | 4193 | 3 | variant of 4035, 3rd sibling |
| 232709 | 4035 | None | parent step, no variant |

This is the ONLY route that carries `sequence_step_variant` and
`sequence_step_order`. Neither field appears on the scheduled-email or
reply objects. **Events have a 10-day history** and are unsuitable for
full historical analysis.

**The two variant identifiers:**

| Identifier | Source | Persistent? | Scope |
|---|---|---|---|
| Step `id` (e.g. 4036) | sequence-steps + scheduled-email join | Yes | All time |
| `sequence_step_variant` (e.g. 2) | events only | No (10 days) | Recent |

The step id is the durable variant identifier. The event index is a
compact alias that expires.

**HYPOTHESIS.** None at this level. The provider states which step was
sent, and the step listing states whether that step is a variant. The join
is deterministic.

**What is NOT available:** a variant-level summary route. There is no
`GET /campaigns/{id}/variants`, no `GET /campaigns/{id}/ab-test`, no
analytics endpoint. All four return 404 (verified live). Variant analysis
must be assembled from the step listing and the scheduled-email listing.

---

### 1.6 SEND

**FACT.** A scheduled email row carries:

| Field | Route | Example |
|---|---|---|
| `id` | `/scheduled-emails/{id}` | `22310389` |
| `sequence_step_id` | `/scheduled-emails/{id}` | `4035` |
| `status` | `/scheduled-emails/{id}` | `sent` |
| `sent_at` | `/scheduled-emails/{id}` | `2026-09-15T01:04:50.000000Z` |
| `scheduled_date` | `/scheduled-emails/{id}` | `2026-09-15T01:04:00.000000Z` |
| `email_subject` | `/scheduled-emails/{id}` | rendered, merge fields resolved |
| `email_body` | `/scheduled-emails/{id}` | rendered, merge fields resolved |
| `raw_message_id` | `/scheduled-emails/{id}` | message-id header |
| `replies` | `/scheduled-emails/{id}` | `1` |

**The listing form** (`GET /campaigns/{id}/scheduled-emails`) carries the
same fields plus a nested `lead` dict. **The individual form** (`GET
/scheduled-emails/{id}`) does NOT carry `lead`. This asymmetry is verified
and is a provider behaviour, not a bug in our code.

**RECONSTRUCTION.** The send's step position is the step's `order` field,
reachable via the sequence-steps listing. The send's variant identity is
the step's `variant` flag, reachable via the same listing.

---

### 1.7 REPLY

**FACT.** A reply row carries 31 fields. The attribution-relevant ones:

| Field | Meaning | Example |
|---|---|---|
| `id` | reply id | `1609203` |
| `type` | `Tracked Reply` / `Untracked Reply` / `Outgoing Email` / `Bounced` | `Tracked Reply` |
| `folder` | `Inbox` / `Sent` / `Bounced` | `Inbox` |
| `campaign_id` | which campaign | `352` |
| `lead_id` | who replied | `203727` |
| `scheduled_email_id` | the join to step | `22310389` |
| `date_received` | when | `2026-09-15T15:17:30.000000Z` |
| `interested` | provider interest flag | `false` |
| `automated_reply` | auto-reply detected | `false` |
| `tracked_reply` | linked to a scheduled email | `true` |
| `subject` | reply subject | |
| `text_body` | reply text | |

**Fields NOT present on a reply:** `sequence_step_id`, `step_id`,
`variant_id`, `message_id` (the provider uses `raw_message_id` instead).

**Two reply types matter for attribution:**

- `Tracked Reply` (`scheduled_email_id` non-null): joinable to a step.
- `Untracked Reply` (`scheduled_email_id` null): NOT joinable to any step.
  The provider could not associate this reply with a sent email.

**⚠️ HAZARD:** The reply feed carries outbound mail as type `Outgoing
Email` in folder `Sent`. This is not a reply and must be filtered.

---

### 1.8 OUTCOME

**FACT.** The provider states:

- `interested` (bool) on the reply row
- `type` (string) on the reply row
- `automated_reply` (bool) on the reply row
- `replies` (int) on the scheduled email row
- `unique_replies` (int) on the scheduled email row

**RECONSTRUCTION.** Classifying a reply as "positive" or "negative"
requires reading the reply text. The provider's `interested` flag is one
signal but is not the same as "positive reply." A reply that is not marked
interested may still be positive.

**HYPOTHESIS.** "An unknown reply is negative." The provider does not
state this. An untracked reply (`scheduled_email_id: null`) is one the
provider could not associate with a send. Counting it as negative
attributes a cause to an unattributable event. Counting it as positive
would be equally wrong. The honest answer is: it is unattributable.

**HYPOTHESIS.** "`interested: false` means the reply was negative." The
provider's `interested` flag is an operator classification, not a sentiment
analysis. A reply can be substantive and not marked interested.

---

## 2. THE BOUNDARY TABLE

| Level | FACT | RECONSTRUCTION | HYPOTHESIS |
|---|---|---|---|
| **Campaign** | `campaign_id` on reply | — | — |
| **Sequence** | `sequence_id` on campaign | steps via `/sequence-steps` | — |
| **Step** | — | `reply → scheduled_email → sequence_step_id` (two-hop) | "this step caused the reply" |
| **Lead** | `lead_id` on reply | — | — |
| **Variant** | step `id` + `variant` flag on sequence-steps | step id → variant check (deterministic join) | — |
| **Variant (events)** | `sequence_step_variant` on EMAIL_SENT event | — | — (but 10-day window) |
| **Send** | `sent_at`, `status`, `sequence_step_id` on scheduled email | step order from sequence-steps listing | — |
| **Reply** | `type`, `scheduled_email_id`, `date_received` | tracked vs untracked classification | — |
| **Outcome** | `interested`, `automated_reply` | positive/negative requires text read | untracked = negative; interested=false = negative |

---

## 3. THE CONSEQUENCE: STRONGEST DEFENSIBLE ANALYSIS

Given the boundaries above, the strongest defensible analysis of reply
outcomes is:

### What CAN be said at step level

**Step-level attribution is reconstructable from provider data.** Every
tracked reply can be joined to a specific step by:

    reply.scheduled_email_id → GET /scheduled-emails/{id} → sequence_step_id

This is a deterministic two-hop join. Every field comes from the provider.
The connection (reply was a response to the email sent at this step) is a
reconstruction — the provider does not state causation — but every field
in the join is a provider fact.

**What this permits:** reply rates per step, reply timing per step
(`date_received` minus `sent_at`), and step-level funnel analysis.

### What CAN be said at variant level

**Variant-level attribution is available when the scheduled email's step
is a variant step.** The step id on the scheduled email resolves to a step
in the sequence-steps listing. If that step has `variant: true`, the
variant is identified. If `variant: false`, no variant was used.

**What this permits:** variant-level reply rates, but ONLY for campaigns
that use variant steps AND where the variant step id is recorded on the
scheduled email. Both conditions are met in campaign 352 (verified live).

**What this does NOT permit:** variant-level comparison across campaigns
that do not use the same step structure. A variant in campaign 352 is not
comparable to a variant in campaign 335 because they are different steps
in different sequences.

### What CANNOT be said

1. **Variant-level attribution for untracked replies.** An untracked reply
   has `scheduled_email_id: null`. There is no join path. The step is
   unknown, the variant is unknown, and the reply is unattributable.

2. **Variant-level attribution beyond the step id.** The events endpoint
   carries `sequence_step_variant` (a compact index) but only for 10 days.
   The step id is durable but is a large integer with no inherent ordering.
   To say "variant A beat variant B" you need a stable mapping from step
   id to variant label, which lives in the sequence-steps listing and must
   be preserved externally.

3. **Causal claims.** "This email caused this reply" is a hypothesis. The
   provider states that the email was sent and the reply was received. The
   causal link is ours to claim and ours to defend.

4. **Open rates.** `open_tracking` is `false` estate-wide. Any open count
   is noise. The provider states this.

5. **Sentiment from flags.** `interested: false` is not "negative."
   `automated_reply: true` is not "uninteresting." These are provider
   classifications, not outcome measurements.

### What a variant experiment would need to become readable

The current data model CAN read variant-level outcomes. But to make a
variant experiment defensible, the following must also be true:

1. **Each variant arm must be a separate step in EmailBison.** This is
   already the case in campaign 352 — variants are separate steps with
   their own ids. The scheduled email records which variant step was sent.

2. **The variant-to-step mapping must be preserved.** The sequence-steps
   listing gives the mapping today, but if steps are deleted or renumbered,
   the mapping is lost. Resonate OS must store the mapping at the time of
   send, not reconstruct it later.

3. **Sufficient volume per variant.** The evaluator in `COPY-EXPERIMENTS.md`
   requires 30 exposures per variant and 8 outcomes total. Below that, the
   answer is `insufficient_data` whatever the rates look like.

4. **One campaign per experiment arm is NOT required.** The provider
   carries variant identity within a single campaign. Separate campaigns
   are not needed for variant-level attribution — but they ARE needed if
   the experiment hypothesis is about the campaign itself (subject line,
   sending window, sender identity) rather than the message copy.

5. **A subject marker or custom variable is NOT required for variant
   attribution.** The step id is sufficient. But a custom variable on the
   lead (e.g. `variant_arm=A`) would provide an independent check on the
   step-id attribution and would survive step deletion.

---

## 4. THE UNTRACKED REPLY PROBLEM

An untracked reply (`type: "Untracked Reply"`, `scheduled_email_id: null`)
is a reply the provider could not associate with any sent email. This
happens when:

- The reply came to an inbox that was not the sending inbox
- The reply's subject line did not match any sent thread
- The reply was forwarded from another address

**The provider states:** this reply exists, it was received, it belongs to
this campaign and this lead.

**The provider does not state:** which email produced this reply.

**The honest classification:** untracked replies are UNATTRIBUTABLE. They
are not positive, not negative, and not neutral. They are evidence that a
reply happened, with no step or variant assignment.

Counting untracked replies in a step-level or variant-level analysis
introduces noise. Excluding them loses signal. The defensible position is
to report them separately and state that they are unattributable.

---

## 5. SUMMARY OF ROUTES AND FIELDS

### Routes that carry attribution data

| Route | Attribution role | Key fields |
|---|---|---|
| `GET /replies` | Reply feed | `campaign_id`, `lead_id`, `scheduled_email_id`, `type`, `interested`, `date_received` |
| `GET /scheduled-emails/{id}` | The second hop | `sequence_step_id`, `sent_at`, `status`, `email_subject` |
| `GET /campaigns/{id}/scheduled-emails` | Bulk send history | Same as above + nested `lead` |
| `GET /campaigns/{id}/sequence-steps` | Step → variant resolution | `id`, `order`, `variant`, `variant_from_step` |
| `GET /events` | Rich event data (10 days) | `sequence_step_order`, `sequence_step_variant` |
| `GET /leads/{id}/sent-emails` | Per-lead send history | Same as scheduled-emails |
| `GET /leads/{id}/replies` | Per-lead reply feed | Same as replies |

### Routes that do NOT carry attribution data

| Route | Why it does not help |
|---|---|
| `GET /campaigns/{id}` | Campaign-level aggregates only; no per-step breakdown |
| `GET /campaigns/{id}/leads` | Membership only; no reply or step data |
| `GET /campaigns/{id}/statistics` | 404 — does not exist |
| `GET /campaigns/{id}/variants` | 404 — does not exist |
| `GET /campaigns/{id}/ab-test` | 404 — does not exist |

---

## 6. WHAT TASK-059 NEEDS TO KNOW

TASK-059 asks which email produced which reply. Based on this boundary:

1. **For tracked replies:** the email is identifiable. The join is
   `reply → scheduled_email_id → scheduled email → sequence_step_id → step`.
   Every field is a provider fact. The causal claim ("this email PRODUCED
   this reply") is a reconstruction, but a well-founded one — the reply
   is thread-linked to the sent email.

2. **For untracked replies:** the email is NOT identifiable. The step is
   unknown. Any assignment of an untracked reply to a step is a hypothesis.

3. **For variant-level analysis:** the variant is identifiable when the
   scheduled email's step is a variant step. The variant is NOT
   identifiable when the step is a parent step (no variant was used) or
   when the reply is untracked.

4. **The strongest defensible claim:** "This tracked reply was a response
   to the email sent at step X (variant Y) on [date]." Not "this email
   caused this reply." The first is a reconstruction from provider data.
   The second is a hypothesis.

---

*Probed 2026-09-15 against workspace PRODUCTIVE (id 10). Read-only. No
write route was called. Scripts: `scripts/task141_attribution_probe.py`,
`scripts/task141_variant_edge.py`.*
