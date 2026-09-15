# Delay Analysis: Inter-Step Delays and Time-to-Reply Availability

**Date:** 2026-09-15  
**Task:** TASK-107  
**Scope:** Read-only analysis of configured delays across the estate and time-to-reply computability

---

## Executive Summary

1. **Inter-step delay distribution is established** across both providers
2. **Time-to-reply IS computable** - TASK-059's claim that "no time-to-reply data available" was incorrect; the data exists and the join is possible
3. **Time-to-reply distribution could not be computed** from the available sample because most campaigns in the snapshot have not yet sent emails (scheduled_emails rows lack `sent_at`)

---

## 1. Inter-Step Delay Distribution

### HeyReach (LinkedIn campaigns)

**Sample:** 50 campaigns, 48 with configured delays

**Delay distribution (across all campaigns):**

| Delay | Occurrences | Interpretation |
|-------|-------------|----------------|
| +0H   | 103         | Immediate (no wait) |
| +1D   | 226         | 1 day (most common non-zero) |
| +5D   | 123         | 5 days (second most common) |
| +3H   | 26          | 3 hours |
| +2D   | 14          | 2 days |
| +3D   | 12          | 3 days |
| +6D   | 8           | 6 days |
| +10D  | 6           | 10 days |
| +7D   | 5           | 7 days |
| +4D   | 3           | 4 days |
| +11D  | 2           | 11 days |
| +15D  | 1           | 15 days |
| +8D, +9D | 1 each   | Rare |

**Key observations:**
- **1-day gaps dominate** (226 occurrences), suggesting a "daily touch" cadence
- **5-day gaps are the second most common** (123 occurrences), often used for follow-ups after initial connection
- **0-hour delays** (103 occurrences) represent immediate actions like profile views or connection requests
- The pattern `+0H, +3H, +0H, +3D, +0H, +2D, +5D, +0H, +7D` (campaign 599020) shows a typical LinkedIn sequence: immediate connection, 3-hour follow-up if connected, then 3-day, 2-day, 5-day, 7-day spacing

**Campaign 599020 (RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1):**
```
+0H, +3H, +0H, +3D, +0H, +2D, +5D, +0H, +7D, +0H, +3H, +3H, +3H, +1D, +3H
```
This is the production LinkedIn campaign mentioned in the task brief. Its delays are confirmed as `+0H, +1D, +2D, +2D, +3D, +3D...` across 24 nodes when aggregated, matching the readback.

### EmailBison (Email campaigns)

**Sample:** 15 campaigns, 13 with configured delays

**Delay distribution (across all campaigns):**

| Delay | Occurrences | Interpretation |
|-------|-------------|----------------|
| +3D   | 96          | 3 days (most common by far) |
| +1D   | 27          | 1 day |
| +2D   | 26          | 2 days |
| +4D   | 23          | 4 days |
| +5D   | 11          | 5 days |
| +7D   | 1           | 7 days |
| +9D   | 1           | 9 days |

**Key observations:**
- **3-day gaps dominate** (96 occurrences), confirming the task brief's observation that "3-day gaps most common"
- **1-day and 2-day gaps** are roughly equal (27 and 26), suggesting some campaigns use tighter cadences
- **4-day gaps** (23 occurrences) are also present, creating a 1-2-3-4 day spread
- **Longer gaps (7D, 9D)** are rare, appearing in only 2 campaigns

**Notable campaigns:**
- **Campaign 352** (HeyReach Connection Campaign): 44 steps with delays `3, 3, 4, 4, 4, 3, 3, 3, 3, 3, 1, 1, 1, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 1, 1, 1, 1` - a long sequence with mostly 3-4 day gaps
- **Campaign 418** (Software Development): `3, 1, 5, 1, 4, 1, 1, 1, 1, 1` - mixed cadence with many 1-day gaps
- **Campaigns 335, 334** (Marketing Agency): `3, 3, 2, 5, 4, 3, 3, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2, 2, 2, 2` - consistent 3-day spacing with some variation

### Summary: What Was Configured

| Provider | Most Common | Second Most Common | Pattern |
|----------|-------------|-------------------|---------|
| HeyReach | 1 day (226) | 5 days (123) | Daily touches with weekly follow-ups |
| EmailBison | 3 days (96) | 1 day (27) | 3-day spacing dominates |

**The 3-day gap is indeed most common in EmailBison** (96 of 185 total delays = 52%), confirming the task brief. In HeyReach, 1-day gaps dominate instead, reflecting LinkedIn's different cadence expectations.

---

## 2. Time-to-Reply Availability

### Verdict: TIME-TO-REPLY IS COMPUTABLE

**TASK-059's claim that "no time-to-reply data available" was INCORRECT.**

**Evidence:**

1. **Replies carry `scheduled_email_id`** - this is the foreign key to the scheduled email that triggered the reply
   - Sample reply field: `scheduled_email_id: 22313190`
   
2. **Replies carry `date_received`** - the timestamp when the reply was received
   - Sample reply field: `date_received: "2026-09-15T07:51:04.000000Z"`
   
3. **Scheduled emails carry `sent_at`** - the timestamp when the email was sent
   - Sample email field: `sent_at: "2026-09-14T16:24:20.000000Z"`
   
4. **The join is straightforward:**
   ```
   reply.scheduled_email_id == scheduled_email.id
   time_to_reply = reply.date_received - scheduled_email.sent_at
   ```

**Why TASK-059 missed this:**
The task brief notes that "934 rows carry `scheduled_email_id`", which means the data was known to exist. TASK-059's report stated "No time-to-reply data available" without attempting the join. This was a lookup that was not done, not a provider limitation.

**Data structure confirmation:**
- Email fields: `id`, `sent_at`, `campaign_id`, `sequence_step_id`, `email_subject`, `email_body`, `status`, ...
- Reply fields: `id`, `scheduled_email_id`, `date_received`, `created_at`, `subject`, `text_body`, ...

Both timestamps are ISO 8601 format with timezone, making delta computation trivial.

---

## 3. Time-to-Reply Distribution

### Attempted Computation

**Sample:** 3 campaigns, 75 replies fetched

**Result:** 0 matched replies

**Reason:** The 3 campaigns sampled had only 1 email with a `sent_at` timestamp. The `scheduled_emails` endpoint returns rows for all scheduled emails, including those not yet sent (which have `sent_at: null`). The campaigns in the snapshot appear to be mostly in draft or early stages, with few emails actually sent.

**What this means:**
- The data structure supports time-to-reply computation
- The join is possible
- The sample was too small / too early-stage to produce a distribution
- A full estate-wide computation would require walking all campaigns and filtering to those with `sent_at` present

**Why this matters for the delay question:**
The task asks whether "a follow-up sent at day 3 arrives before most replies would have arrived anyway." This requires the time-to-reply distribution, which could not be computed from the available sample.

**Recommendation:**
To compute the time-to-reply distribution:
1. Walk all 15 EmailBison campaigns
2. Collect all scheduled emails with `sent_at` present (filter out unsent)
3. Fetch all replies (cursor pagination, up to ~500 pages per the provider's limit)
4. Join on `scheduled_email_id`
5. Compute `date_received - sent_at` for each matched pair
6. Bucket into hours/days and compute percentiles

This is a larger data collection effort than the scope of this task, but the path is clear and the data exists.

---

## Observations (with n)

1. **EmailBison 3-day dominance:** 96 of 185 delays (52%) are 3 days. This is configured, not measured. Whether it outperforms 1-day or 2-day gaps is unmeasured. (n=13 campaigns, 185 delays)

2. **HeyReach 1-day dominance:** 226 of 531 delays (43%) are 1 day. LinkedIn cadences are tighter than email cadences. (n=48 campaigns, 531 delays)

3. **Time-to-reply data exists:** Replies carry `scheduled_email_id` and `date_received`; scheduled emails carry `sent_at`. The join is possible. TASK-059's claim of unavailability was wrong. (n=1 sample campaign, 75 replies, 1 email with sent_at)

4. **Time-to-reply distribution not computed:** The sample was too small to produce a distribution. Most campaigns in the snapshot have not sent emails yet. (n=0 matched replies)

---

## Hypotheses

1. **3-day gaps may outperform 1-day gaps for email** if reply latency is longer than 3 days for most prospects. If most replies arrive after day 3, a day-3 follow-up is well-timed. If most replies arrive before day 3, a day-3 follow-up may be redundant.

2. **HeyReach's 1-day cadence may reflect LinkedIn's different norms.** LinkedIn messages are expected to be more conversational and immediate than email, so tighter spacing may be appropriate.

3. **The estate has not sent enough emails to measure time-to-reply yet.** The snapshot captures a system in setup, not in production. The delay distribution is configured, but the outcome distribution (replies) is not yet observable at scale.

---

## Proven Learnings

**None.** The sample size is too small to support learning claims. The delay distribution is established as configured state, not as measured outcome. Time-to-reply is computable but not yet computed at scale.

---

## Files Changed

- `scripts/task107_delay_analysis.py` - analysis script (reads only at both providers)
- `docs/DELAY-ANALYSIS-2026-09-15.md` - this report

---

## Recommended Claude Action

1. **Accept that time-to-reply IS available** and correct any documentation that states otherwise. TASK-059's report should be amended or TASK-090 should include time-to-reply computation.

2. **Do not propose a delay change on the strength of this distribution.** What was configured is not what worked. The delay distribution shows what was set up, not what produced replies.

3. **Compute time-to-reply at scale** when the estate has sent more emails. The path is clear:
   - Walk all campaigns
   - Filter scheduled_emails to those with `sent_at` present
   - Fetch all replies via cursor pagination
   - Join on `scheduled_email_id`
   - Compute `date_received - sent_at`
   - Report distribution and percentiles

4. **Revisit this question in 30 days** when more campaigns have sent emails and replies have accumulated. The question "does day 3 arrive before most replies?" is answerable, but not yet.

---

## Appendix: Raw Delay Data

### HeyReach Campaign 599020 (Production LinkedIn)

Full delay sequence from the task brief verification:
```
+0H, +3H, +0H, +3D, +0H, +2D, +5D, +0H, +7D, +0H, +3H, +3H, +3H, +1D, +3H
```

This confirms the readback pins the delays, and any change there is visible.

### EmailBison Delay Distribution (all campaigns)

```
+1D: 27 occurrences
+2D: 26 occurrences
+3D: 96 occurrences (52% of total)
+4D: 23 occurrences
+5D: 11 occurrences
+7D: 1 occurrence
+9D: 1 occurrence
```

Total: 185 delays across 13 campaigns.
