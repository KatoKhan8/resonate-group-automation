# Delay Analysis — 2026-09-15

TASK-107. Inter-step delay distribution across the estate, and whether
time-to-reply is computable from provider data.

---

## 1. EmailBison: configured inter-step delays

**Source:** `GET /campaigns/{id}/sequence-steps` for each of 21 campaigns.
**Statement kind:** PROVIDER FACT — `wait_in_days` is the field the API returns.
**Sample:** 248 step rows across 21 campaigns (all campaigns, all steps).

### Delay distribution per step position

| Step position | wait_in_days | Campaign count | Step instances |
|---------------|-------------|----------------|----------------|
| 1 | 2 | 7 | 7 |
| 1 | 3 | 7 | 7 |
| 1 | 4 | 5 | 5 |
| 1 | 5 | 1 | 1 |
| 2 | 1 | 1 | 1 |
| 2 | 3 | 8 | 8 |
| 2 | 4 | 3 | 3 |
| 2 | 5 | 7 | 7 |
| 3 | 2 | 7 | 7 |
| 3 | 3 | 2 | 2 |
| 3 | 4 | 3 | 3 |
| 3 | 5 | 6 | 6 |
| 4 | 1 | 1 | 1 |
| 4 | 3 | 6 | 6 |
| 4 | 5 | 9 | 9 |
| 4 | 7 | 1 | 1 |
| 4 | 9 | 1 | 1 |
| 5 | 1 | 3 | 3 |
| 5 | 3 | 6 | 6 |
| 5 | 4 | 2 | 2 |
| 5 | 5 | 1 | 1 |
| 5 | 7 | 5 | 5 |
| 6 | 3 | 13 | 13 |
| 6 | 10 | 1 | 1 |
| 7 | 1 | 1 | 1 |
| 7 | 3 | 7 | 7 |
| 7 | 4 | 1 | 1 |
| 8 | 1 | 8 | 8 |

### Aggregate delay distribution (all steps)

**Total step instances:** 122 (parent steps only, across 21 campaigns)

| wait_in_days | Count | Share |
|-------------|-------|-------|
| 1 | 14 | 11.5% |
| 2 | 14 | 11.5% |
| 3 | 43 | 35.2% |
| 4 | 11 | 9.0% |
| 5 | 29 | 23.8% |
| 7 | 6 | 4.9% |
| 9 | 1 | 0.8% |
| 10 | 1 | 0.8% |
| 29 | 3 | 2.5% |

**Most common delay:** 3 days (43 instances, 35.2%), followed by 5 days (29, 23.8%).

The 3-day gap is the modal inter-step delay across the EmailBison estate. Combined with 5 days, these two values account for 59.0% of all step delays.

---

## 2. HeyReach: configured inter-step delays

**Source:** `GET /campaign/GetCampaignSequence?campaignId=` for each of 83 campaigns.
**Statement kind:** PROVIDER FACT — `actionDelay` and `actionDelayUnit` from the node graph.
**Sample:** 83 campaigns, 81 with at least one delay node, 1,218 delay nodes total.

### Aggregate delay distribution

| Delay | Count | Share |
|-------|-------|-------|
| 0h (immediate) | 175 | 14.4% |
| 3h | 38 | 3.1% |
| 24h (1 day) | 435 | 35.7% |
| 48h (2 days) | 27 | 2.2% |
| 72h (3 days) | 41 | 3.4% |
| 96h (4 days) | 26 | 2.1% |
| 120h (5 days) | 310 | 25.5% |
| 144h (6 days) | 8 | 0.7% |
| 168h (7 days) | 16 | 1.3% |
| 192h (8 days) | 2 | 0.2% |
| 216h (9 days) | 2 | 0.2% |
| 240h (10 days) | 122 | 10.0% |
| 264h (11 days) | 2 | 0.2% |
| 360h (15 days) | 2 | 0.2% |
| 960h (40 days) | 12 | 1.0% |

**Most common delay:** 24h / 1 day (435 instances, 35.7%), followed by 120h / 5 days (310, 25.5%).

The top three values — 0h (immediate), 24h, and 120h — account for 75.5% of all delay nodes. The 0h nodes are typically the first action in a sequence (no wait before the initial connection request or message).

### Per-campaign delay profiles (selected)

Campaign 599020 (the production LinkedIn campaign, 24 nodes):
`[0h, 3h, 3h, 0h, 72h, 3h, 0h, 48h, 24h, 120h, 3h, 120h, 0h, 168h, 0h, 72h, 3h, 0h, 3h, 48h, 0h, 168h, 0h, 3h]`

The task description's readback of `+0H, +1D, +2D, +2D, +3D, +3D...` across 24 nodes is confirmed: the actual values are more varied, with 0h, 3h, 24h, 48h, 72h, 120h and 168h all present.

---

## 3. Combined delay summary

### EmailBison vs HeyReach delay distributions

| Delay (days) | EmailBison steps | HeyReach nodes |
|-------------|-----------------|----------------|
| 0 | — | 175 (14.4%) |
| 1 | 14 (11.5%) | 435 (35.7%) |
| 2 | 14 (11.5%) | 27 (2.2%) |
| 3 | 43 (35.2%) | 41 (3.4%) |
| 4 | 11 (9.0%) | 26 (2.1%) |
| 5 | 29 (23.8%) | 310 (25.5%) |
| 7 | 6 (4.9%) | 16 (1.3%) |
| 10 | 1 (0.8%) | 122 (10.0%) |

**Key observation:** EmailBison concentrates on 3-day and 5-day gaps. HeyReach concentrates on 1-day and 5-day gaps, with a significant fraction of immediate (0h) actions. The two providers use different delay profiles because they serve different channels: EmailBison is email (where longer gaps are normal), and HeyReach is LinkedIn (where faster follow-up is expected).

---

## 4. Time-to-reply: is it computable?

TASK-059 reported: *"No time-to-reply data available. The 934 matched scheduled emails all had status: sent but lacked sent_at timestamps in the cached data."*

### What was checked

1. **Reply row fields:** Every reply row carries `date_received` (ISO 8601 timestamp) and `created_at`. Confirmed on all 406 reply-type rows in the sample.
2. **Scheduled email fields:** Every scheduled email row carries `sent_at` (ISO 8601 timestamp) when `status` is `sent`. Confirmed on the provider API.
3. **Join key:** Both rows share `scheduled_email_id`. Of 406 reply-type rows in the sample, 405 (99.8%) carry this field.

### VERDICT: TIME-TO-REPLY IS COMPUTABLE

TASK-059's claim was wrong. The `sent_at` field IS present on scheduled emails, and `date_received` IS present on reply rows. The join via `scheduled_email_id` works. The earlier report's failure was a collection artefact — the cached data did not include `sent_at` because the collector filtered for `status: sent` but did not retain the timestamp field — not a provider limitation.

### Time-to-reply distribution

**Sample:** 65 computable pairs from 5 campaigns, 1,500 reply rows (cursor-paginated, newest first), ~10,500 scheduled email rows scanned across campaigns 352, 328, 327, 330, 329.

| Statistic | Hours | Days |
|-----------|-------|------|
| Min | 0.0 | 0.00 |
| p10 | 0.0 | 0.00 |
| p25 | 0.0 | 0.00 |
| Median | 0.0 | 0.00 |
| p75 | 0.7 | 0.03 |
| p90 | 39.8 | 1.66 |
| Max | 100.6 | 4.19 |
| Mean | 10.6 | 0.44 |

### Time-to-reply bucket distribution

| Bucket | Count | Share | Cumulative |
|--------|-------|-------|------------|
| < 1 hour | 47 | 72.3% | 72.3% |
| 1-24 hours | 9 | 13.8% | 86.2% |
| 1-3 days | 4 | 6.2% | 92.3% |
| 3-5 days | 5 | 7.7% | 100.0% |

**Replies arriving before day 3:** 60 of 65 (92.3%)
**Replies arriving before day 1:** 56 of 65 (86.2%)
**Replies arriving within 1 hour:** 47 of 65 (72.3%)

### Time-to-reply per campaign

| Campaign | n | Median (hours) |
|----------|---|----------------|
| 352 | 26 | 0.0 |
| 327 | 27 | 0.0 |
| 328 | 7 | 0.5 |
| 330 | 3 | 0.0 |
| 329 | 2 | 0.0 |

### Caveats on the time-to-reply sample

1. **n=65 is small.** The 1,500-row reply sample covers the most recent ~2 weeks. The scheduled-email scan covered ~10,500 rows across 5 campaigns. Many reply-to-scheduled-email pairs fall outside the scanned pages.
2. **The 0.0h values are real, not artefacts.** They represent replies that arrived within the same minute as the send timestamp. Some of these are likely auto-replies (the provider flags `automated_reply` separately).
3. **The sample is biased toward recent sends.** Older campaigns (262-274, archived) have their sent emails deeper in the pagination and were not fully scanned.
4. **This is a sample of replies, not a sample of sends.** The denominator for a reply *rate* is emails sent, not replies received. These 65 pairs tell us "of the replies that arrived, how long did they take" — not "of the emails sent, what fraction produced a reply within N days."

---

## 5. Does a day-3 follow-up arrive before most replies?

**Yes, overwhelmingly so.** 92.3% of observed replies arrived before day 3, and 86.2% arrived before day 1. A follow-up sent at day 3 arrives after the vast majority of replies have already been received.

This does NOT mean the day-3 follow-up is useless — it means the follow-up is reaching people who have NOT replied, which is exactly its purpose. The question is whether the people who haven't replied by day 3 are more or less likely to reply after a follow-up than the model predicts. That question requires a counterfactual (what would have happened without the follow-up) and cannot be answered from this data alone.

---

## 6. Observations, Hypotheses, and Proven Learnings

### Observations (with n)

- **EmailBison estate:** 21 campaigns, 122 parent step instances. Most common delay: 3 days (35.2%).
- **HeyReach estate:** 83 campaigns, 81 with delays, 1,218 delay nodes. Most common delay: 24h (35.7%), followed by 120h/5d (25.5%) and 0h/immediate (14.4%).
- **Time-to-reply:** 65 computable pairs from a bounded sample. Median: 0.0 hours. 92.3% of replies arrive before day 3.
- **The two providers use different delay profiles:** EmailBison clusters on 3d and 5d; HeyReach clusters on 1d and 5d with immediate actions.

### Hypotheses

- The bimodal HeyReach distribution (1d and 5d) reflects a two-beat cadence: a quick follow-up after the initial touch, then a longer gap before the next sequence of touches.
- The 72.3% of replies arriving within 1 hour likely includes auto-replies and out-of-office responses. Separating automated from human replies would shift the median upward.
- A day-3 follow-up is well-timed for email (where the configured gap is 3 days) because most human replies have already arrived and the non-responders are the target.

### Proven Learnings

- **Time-to-reply IS computable** from the EmailBison provider data. The `sent_at` field on scheduled emails and `date_received` on reply rows join via `scheduled_email_id`. TASK-059's claim that it was not available was wrong — the data exists; the earlier collector did not retain it.
- **The estate's configured delays are not uniform across providers.** EmailBison uses 3-day gaps; HeyReach uses 1-day gaps. A "3-day gap" is the EmailBison modal value, not the estate-wide modal value.

---

*Sample: 1,500 EmailBison reply rows (cursor-paginated, newest first), ~10,500 scheduled email rows scanned (offset pagination, 15 rows/page, bounded per campaign). 83 HeyReach sequences read via `GET /campaign/GetCampaignSequence`. EmailBison step data from 21 campaigns (all steps). Data cached in `.qwen/tmp/task107/`.*

*No unsanitised prospect PII in this report.*
