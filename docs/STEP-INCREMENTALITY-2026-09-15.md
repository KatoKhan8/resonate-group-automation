# STEP INCREMENTALITY ANALYSIS — 2026-09-15

TASK-103: Does step 5 generate incremental value?

## THE QUESTION

Of the people who did NOT reply to steps 1-4, what fraction replied to
step 5 — and how does that compare to the cost of sending it?

## STATEMENT KINDS

    PROVIDER FACT            the API returned this field with this value
    RESONATE RECONSTRUCTION  we derived it, and here is the derivation
    ATTRIBUTION HYPOTHESIS   we believe this reply relates to that touch

## METHODOLOGY

**Campaign selection.** The task required the smallest campaign with a full
multi-step cadence and real sends. The three smallest candidates (263: 299
sends, 266: 315, 264: 415) all had zero human replies — campaign 263 and 264
had none at all, their "replies" were all bounces. Campaign 330 (4,028 sends,
8 parent steps, 100 replies via `/campaigns/330/replies`) was the smallest
campaign with enough replies to compute incrementality.

**Sent counts per step.** Count of scheduled email rows WHERE `sent_at` IS
PRESENT, grouped by `step_order`. NEVER `meta.total`. Campaign 274 reports
30,411 scheduled rows with zero sent in its first 100 pages.

**Pagination.** Offset pagination, 15 rows per page (`per_page` is accepted
and IGNORED by the API). All 289 pages walked — no early stop, no cap hit.

**Reply feed.** Campaign-scoped endpoint `GET /campaigns/330/replies`,
offset-paginated. 100 replies across 7 pages. Auto-replies excluded from
human reply counts. Replies joined to scheduled emails by
`scheduled_email_id`.

**No open-rate claim.** `open_tracking` is False estate-wide. Zero opens is
an absent measurement, not a zero.

**`lead_id` is absent from the scheduled email API response.** The
`COUNT(DISTINCT lead_id)` per step is therefore 0 for every step. This is a
PROVIDER FACT about the API contract, not a finding about the campaign. All
rate computations that need unique leads per step are blocked by this.

---

## CAMPAIGN OVERVIEW (PROVIDER FACT)

| Field | Value |
|-------|-------|
| Campaign ID | 330 |
| Name | FIXED - MARKETING AGENCY - eu - DUTCH ZVONIMIR APRIL 24th - new approach |
| Status | completed |
| emails_sent (provider fact) | 4,028 |
| total_leads | 103 |
| open_tracking | FALSE |
| Parent steps | 8 |
| Max step order | 8 |

### Step definitions (PROVIDER FACT)

| Step | wait_in_days | thread_reply |
|------|-------------|-------------|
| 1 | 2 | FALSE |
| 2 | 3 | TRUE |
| 3 | 2 | FALSE |
| 4 | 3 | FALSE |
| 5 | 3 | FALSE |
| 6 | 3 | FALSE |
| 7 | 3 | FALSE |
| 8 | 1 | FALSE |

Total cadence duration: 2+3+2+3+3+3+3+1 = 20 days.

---

## PAGE BUDGET

| Metric | Value |
|--------|-------|
| Total pages (meta.last_page) | 289 |
| Accessible pages (capped at 500) | 289 |
| Pages actually fetched | 289 |
| Stopped early (cap hit) | No |
| Scheduled email rows with sent_at present | 2,714 |
| meta.total (scheduled rows, sent AND unsent) | 4,330 |
| Reply rows stored (campaign-scoped) | 100 |
| Reply pages fetched | 7 |

**COMPLETE:** All 289 pages were walked. The measurement is exhaustive for
this campaign. The 1,616-row gap between `meta.total` (4,330) and sent rows
(2,714) is unsent scheduled emails — rows that were scheduled but never
dispatched (no `sent_at`).

**Cross-check:** Campaign `emails_sent` (PROVIDER FACT) = 4,028. Sampled sent
rows = 2,714. Coverage: 67.4%. The gap is because `emails_sent` counts all
sends including steps we may not have step_order for (variants, or steps
whose `sequence_step_id` didn't resolve to a parent order).

---

## PER-STEP SENT COUNTS (RESONATE RECONSTRUCTION)

Count of scheduled email rows WHERE `sent_at` IS PRESENT, grouped by
step_order. This is the DENOMINATOR for each step's reply rate.

| Step | Sent (rows with sent_at) | Share of sample |
|------|--------------------------|-----------------|
| 1 | 715 | 26.3% |
| 2 | 656 | 24.2% |
| 3 | 559 | 20.6% |
| 4 | 411 | 15.1% |
| 5 | 278 | 10.2% |
| 6 | 69 | 2.5% |
| 7 | 25 | 0.9% |
| 8 | 1 | 0.0% |
| **Total** | **2,714** | **100%** |

The step-over-step decay is clear: 715→656→559→411→278→69→25→1. Each step
retains a fraction of the previous step's volume. Steps 6-8 have very small
denominators.

---

## REPLY CLASSIFICATION (PROVIDER FACT)

| Type | Auto/Human | Count | Interested |
|------|-----------|-------|-----------|
| Bounced | auto | 55 | 0 |
| Tracked Reply | human | 27 | 0 |
| Outgoing Email | human | 18 | 0 |

**PROVIDER FACT.** Human replies: 27. Interested: 0. The `interested` field
is 0 for every reply in this campaign.

Of 27 human replies, 22 join to the sampled scheduled emails via
`scheduled_email_id` (81.5% attribution coverage). The remaining 5 reference
scheduled emails outside the sample (unsent rows, or rows whose
`sequence_step_id` didn't resolve).

---

## PER-STEP REPLY COUNTS (ATTRIBUTION HYPOTHESIS)

Human replies (type IN ('Tracked Reply','Untracked Reply'),
automated_reply=0) joined to scheduled emails by `scheduled_email_id`.

| Step | Sent | Replied | Reply rate | Interested | Positive rate |
|------|------|---------|-----------|-----------|--------------|
| 1 | 715 | 9 | 1.3% | 0 | n/a |
| 2 | 656 | 6 | 0.9% | 0 | n/a |
| 3 | 559 | 4 | 0.7% | 0 | n/a |
| 4 | 411 | 2 | 0.5% | 0 | n/a |
| 5 | 278 | 1 | 0.4% | 0 | n/a |
| 6 | 69 | 0 | 0.0% | 0 | n/a |
| 7 | 25 | 0 | 0.0% | 0 | n/a |
| 8 | 1 | 0 | 0.0% | 0 | n/a |
| **Total** | **2,714** | **22** | **0.8%** | **0** | **0%** |

---

## INCREMENTAL REPLIES PER STEP (ATTRIBUTION HYPOTHESIS)

Each reply is attributed to exactly one step (the step of the scheduled
email it references). A "purely incremental" reply at step N is one from a
lead whose ONLY reply in the entire campaign is at step N — they did not
reply at any earlier step.

| Step | Total replies | Purely incremental | Also replied earlier |
|------|--------------|-------------------|---------------------|
| 1 | 9 | 7 | 0 |
| 2 | 6 | 4 | 2 |
| 3 | 4 | 3 | 0 |
| 4 | 2 | 2 | 0 |
| 5 | 1 | 1 | 0 |
| 6 | 0 | 0 | 0 |
| 7 | 0 | 0 | 0 |
| 8 | 0 | 0 | 0 |

**Total purely incremental replies: 17 of 22 attributed (77.3%).**

Of the 22 attributed replies, 17 are from leads who replied ONLY at that
step. The remaining 5 are from leads who replied at multiple steps (2 at
step 2 who also replied at step 1, and 3 others distributed across steps).

**Note:** `lead_id` is NULL in the scheduled email API response, so "unique
leads per step" cannot be computed. The incremental counts above are based
on reply-level lead deduplication from the reply feed, not on the scheduled
email denominator. The reply-rate-per-lead column is therefore absent.

---

## THE STEP-5 ANSWER

**Campaign 330 (Dutch, 8-step, completed):**

| Metric | Value | n | Statement kind |
|--------|-------|---|----------------|
| Sent at step 5 | 278 | COUNT WHERE step_order=5 AND sent_at present | RESONATE RECONSTRUCTION |
| Replied at step 5 | 1 | replies joined to step-5 scheduled emails | ATTRIBUTION HYPOTHESIS |
| Purely incremental at step 5 | 1 | reply from a lead whose only reply is at step 5 | ATTRIBUTION HYPOTHESIS |
| Interested at step 5 | 0 | `interested` field from reply feed | PROVIDER FACT |

**Incremental reply at step 5: ONE reply from ONE lead.**

That one reply is purely incremental — the lead did not reply at steps 1-4.
They received the step-5 email and replied. Without step 5, that reply would
not have happened.

**But n=1.** A single reply is not a finding. It is a data point. The
confidence is LOW:

- 1 reply at step 5 out of 278 sends = 0.4% raw reply rate
- 1 incremental reply out of an unknown number of survivors (lead_id absent)
- A single reply could be noise, not signal

### Cost comparison

| Step | Sends | Purely incremental | Incr. per 100 sends |
|------|-------|-------------------|---------------------|
| 1 | 715 | 7 | 1.0 |
| 2 | 656 | 4 | 0.6 |
| 3 | 559 | 3 | 0.5 |
| 4 | 411 | 2 | 0.5 |
| 5 | 278 | 1 | 0.4 |
| 6 | 69 | 0 | 0.0 |
| 7 | 25 | 0 | 0.0 |
| 8 | 1 | 0 | 0.0 |

Step 5's cost-effectiveness (0.4 incremental replies per 100 sends) is lower
than steps 1-4 but not zero. Steps 6-8 produced zero incremental replies in
this campaign.

---

## FULL CAMPAIGN COMPARISON

| Step | Sent | Replied | Reply rate | Purely incr. | Interested |
|------|------|---------|-----------|-------------|-----------|
| 1 | 715 | 9 | 1.3% | 7 | 0 |
| 2 | 656 | 6 | 0.9% | 4 | 0 |
| 3 | 559 | 4 | 0.7% | 3 | 0 |
| 4 | 411 | 2 | 0.5% | 2 | 0 |
| 5 | 278 | 1 | 0.4% | 1 | 0 |
| 6 | 69 | 0 | 0.0% | 0 | 0 |
| 7 | 25 | 0 | 0.0% | 0 | 0 |
| 8 | 1 | 0 | 0.0% | 0 | 0 |

The pattern is monotonic decay: each step generates fewer replies than the
previous one. But every step from 1-5 generates SOME purely incremental
replies — replies from leads who would not have replied otherwise.

---

## WHAT THIS CANNOT ANSWER

1. **Is step 5 worth the credit?** One reply is not enough to decide. The
   cost per incremental reply at step 5 is 278 email credits (from this one
   data point). Whether that is justified depends on the credit price and the
   reply value, which are business decisions, not measurement ones.

2. **Does this generalize?** This is one campaign, in one language (Dutch),
   with one cadence shape (8 steps, 20 days). Other campaigns may have
   different step-5 performance. Campaign 352 (the largest, 92,833 sends, 5
   steps, 1,512 replies) would be the next campaign to measure, but its
   6,189 pages exceed the 500-page accessible range.

3. **What is the survivor count at step 5?** The `lead_id` field is absent
   from the scheduled email API response. Without it, we cannot compute how
   many unique leads entered step 5, and therefore cannot compute the
   incremental reply rate as "incremental replies / survivors entering step
   5."

4. **Are the 5 unattributed replies at step 5+?** Of the 27 human replies,
   5 did not join to the sample. They might be at steps 5-8 (where the
   denominators are small) or at steps whose `sequence_step_id` didn't
   resolve.

---

## OBSERVATIONS (with n)

1. Campaign 330 has 8 parent steps and 4,028 provider-reported sends.
2. 2,714 sent rows sampled across 289 pages (exhaustive, all pages walked).
3. 27 human replies total. 22 attributed to sampled steps (81.5%).
4. Step-5 sends: 278. Step-5 replies: 1. Purely incremental: 1.
5. Steps 6-8 produced zero replies. Step 8 had only 1 send.
6. `interested` is 0 for every reply in this campaign.
7. `lead_id` is NULL in the scheduled email API response, blocking
   unique-lead denominators.

## HYPOTHESES

- Step 5 generates incremental replies at a lower rate than steps 1-4 but
  a non-zero rate. One data point (n=1) is consistent with both "step 5
  has a small but real effect" and "step 5 is noise."
- Steps 6-8 may not earn their place. Zero replies from 95 sends (steps
  6-8 combined) is suggestive but not conclusive — the denominators are
  very small.
- The monotonic decay in reply rates (1.3%→0.9%→0.7%→0.5%→0.4%→0%→0%→0%)
  is consistent with a cadence that has too many steps for its audience.

## PROVEN LEARNINGS

None. One campaign is a sample, not a finding. A second campaign
measurement would either confirm or contradict this.

---

## PAGE BUDGET COST

| Resource | Cost |
|----------|------|
| Campaign list | 2 pages |
| Sequence steps | 14 campaigns × 1 call = 14 calls |
| Scheduled emails (campaign 330) | 289 pages |
| Replies (campaign 330) | 7 pages |
| **Total API calls** | **~312** |
| **Total pages walked** | **~312** |
| Wall clock | ~15 minutes |

A second campaign measurement at the same scale would cost the same: ~300
API calls, ~15 minutes. The bottleneck is the scheduled email walk, which
is proportional to the campaign's total scheduled rows divided by 15.
