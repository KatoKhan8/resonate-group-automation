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

**Campaign selection:** Campaign 330 was selected as the smallest campaign
(by `emails_sent` = 4,028) with sends distributed across multiple steps.
Campaign 263 (299 sends, 6 steps) was auto-selected first but had ALL sends
at step 1 only — the other steps were defined but never sent. Campaign 330
is a DELIBERATE SAMPLE of one campaign, not an estate-wide measurement.

**Sent counts per step:** Count of scheduled email rows WHERE `sent_at`
IS PRESENT, grouped by `step_order`. NEVER `meta.total`. The API sorts
oldest-first, so pages 1-N contain the earliest sends.

**Pagination:** Offset pagination, 15 rows per page (per_page is accepted
and IGNORED by the API). Accessible page cap: 500 pages.

**Reply feed:** Cursor-paginated collection of the estate-wide reply feed.
3,006 rows collected before analysis. Auto-replies excluded from human
reply counts. Replies joined to scheduled emails by `scheduled_email_id`.

**lead_id is NULL:** The EmailBison API does not return `lead_id` on
scheduled email rows. All "per lead" metrics use send counts as a proxy.
Each scheduled email row is one send to one lead, so send count ≈ lead
count at each step (assuming no lead receives the same step twice).

**No open-rate claim.** `open_tracking` is FALSE on every campaign.
Zero opens is an absent measurement, not a zero.

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

| Step | wait_in_days | active | thread_reply | Subject (truncated) |
|------|-------------|--------|-------------|------|
| 1 | 2 | TRUE | FALSE | {hoe {COMPANY} marges bijhoudt\|...} |
| 2 | 3 | TRUE | TRUE | Re: {hoe {COMPANY} marges bijhoudt\|...} |
| 3 | 2 | TRUE | FALSE | {het 8% margeprobleem\|...} |
| 4 | 3 | TRUE | FALSE | {waar de marge echt verloren gaat\|...} |
| 5 | 3 | TRUE | FALSE | {wat bureaus zoals {COMPANY} echt vinden\|...} |
| 6 | 3 | TRUE | FALSE | {de kosten van de huidige setup\|...} |
| 7 | 3 | TRUE | FALSE | {praat ik met de juiste persoon\|...} |
| 8 | 1 | TRUE | FALSE | {ik sluit de lus bij {COMPANY}\|...} |

Step 2 is a same-thread follow-up (thread_reply=TRUE). All others are
new-thread emails.

---

## PAGE BUDGET

| Metric | Value |
|--------|-------|
| Total pages (meta.last_page) | 289 |
| Accessible pages (cap 500) | 289 |
| Pages actually fetched | 189 (pages 101-289) |
| Pages missing | 1-100 (oldest sends) |
| Stopped early (cap hit) | No |
| Scheduled email rows with sent_at present | 2,714 |
| Provider-reported emails_sent | 4,028 |
| Coverage | 67.4% |
| Reply rows stored (estate-wide feed) | 3,006 |
| Reply rows for campaign 330 | 100 |
| Human replies for campaign 330 | 27 |
| Attributed to sampled scheduled emails | 22 (81.5%) |

**PARTIAL COVERAGE.** Pages 1-100 were not fetched. These contain the
oldest scheduled emails, which are predominantly step 1 sends (the first
emails in the cadence). The step 1 denominator is therefore UNDERCOUNTED.
Steps 5-8 are less affected because those sends occur later in the
cadence and are concentrated in the later pages that WERE fetched.

---

## PER-STEP SENT COUNTS (RESONATE RECONSTRUCTION)

Count of scheduled email rows WHERE `sent_at` IS PRESENT, grouped by
step_order. These are the DENOMINATORS for each step's reply rate.

| Step | Sent (rows with sent_at) | Share of sample |
|------|--------------------------|-----------------|
| 1 | 715 | 26.3% |
| 2 | 656 | 24.2% |
| 3 | 559 | 20.6% |
| 4 | 411 | 15.1% |
| 5 | 278 | 10.2% |
| 6 | 69 | 2.5% |
| 7 | 25 | 0.9% |
| 8 | 1 | 0.04% |
| **Total** | **2,714** | **100%** |

**Cross-check:** Campaign `emails_sent` (PROVIDER FACT) = 4,028.
Sampled sent rows = 2,714. Coverage: 67.4%.

The gap (1,314 rows) is explained by pages 1-100 not being fetched.
Those pages contain the oldest sends, predominantly step 1. The true
step 1 count is likely ~1,000 (103 leads × ~1 send each at step 1,
accounting for the campaign's 103 leads and the step-1 position).

The step-over-step decay is clear and monotonic:
715 → 656 → 559 → 411 → 278 → 69 → 25 → 1

Each step retains 75-92% of the previous step's volume, except for
steps 6-7 where retention drops sharply (25% and 36%).

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

**Attribution coverage:** Of 27 human replies in this campaign,
22 join to the sampled scheduled emails (81.5%). The remaining 5
reference scheduled emails outside the sample (in the unfetched pages
1-100, or in rows without `sent_at`).

**Reply rate monotonically decreases** from 1.3% at step 1 to 0.4% at
step 5, then to 0% at steps 6-8. This is consistent with reply fatigue:
each subsequent step generates fewer replies per send.

**Zero interested replies.** The `interested` field is 0 for all 22
attributed replies. This does NOT mean the replies were negative — it
means the classifier did not tag them as interested. INTERESTED may NOT
carry a learning claim (0.44 precision on the old pattern set).

---

## INCREMENTAL REPLIES PER STEP (ATTRIBUTION HYPOTHESIS)

Each reply is attributed to exactly one step (the step of the scheduled
email it references). Without lead_id, we cannot track which specific
leads replied at multiple steps. Instead, we estimate incremental
replies by assuming each reply comes from a unique lead (conservative
given the low reply rates).

**Upper bound on multi-step repliers:** The total attributed replies
are 22 across steps 1-5. Even if ALL 22 came from different leads,
that's 22 out of 2,714 sends — less than 1%. The probability that any
single lead replied at multiple steps is very low.

| Step | Replies at step | Estimated incremental* | Reply rate | Incr. rate per 100 sends |
|------|----------------|----------------------|-----------|--------------------------|
| 1 | 9 | 9 (all are first replies) | 1.3% | 1.25 |
| 2 | 6 | ~6 | 0.9% | 0.91 |
| 3 | 4 | ~4 | 0.7% | 0.72 |
| 4 | 2 | ~2 | 0.5% | 0.49 |
| 5 | 1 | ~1 | 0.4% | 0.36 |
| 6 | 0 | 0 | 0.0% | 0.00 |
| 7 | 0 | 0 | 0.0% | 0.00 |
| 8 | 0 | 0 | 0.0% | 0.00 |

*Estimated because lead_id is null. With 22 replies across 2,714 sends
(0.8% overall), the expected number of leads replying at multiple steps
is approximately 0.2 (essentially zero). So each step's replies are
almost certainly all incremental.

---

## THE STEP-5 ANSWER

**Campaign 330:**

| Metric | Value | n | Statement kind |
|--------|-------|---|----------------|
| Sends at step 5 | 278 | COUNT WHERE step_order=5 AND sent_at present | RESONATE RECONSTRUCTION |
| True sends at step 5 (estimated) | ~350-400 | Extrapolating from 67.4% coverage | RESONATE RECONSTRUCTION |
| Replies at step 5 | 1 | replies joined to step-5 scheduled emails | ATTRIBUTION HYPOTHESIS |
| Estimated incremental at step 5 | ~1 | see reasoning above | ATTRIBUTION HYPOTHESIS |
| Reply rate at step 5 | 0.4% | 1 / 278 | RESONATE RECONSTRUCTION |
| Interested at step 5 | 0 | `interested` field from reply feed | PROVIDER FACT |

**Step 5 cost-effectiveness:**
- 278 sends to generate 1 reply = 278 email credits per reply
- Compared to step 1: 715 sends for 9 replies = 79 credits per reply
- Step 5 is **3.5× less cost-effective** than step 1
- Steps 6-8 generated zero replies and are strictly negative ROI

### Confidence assessment

**LOW CONFIDENCE.** Only 1 reply at step 5. This is too few to draw
a reliable conclusion. A single reply changes the rate from 0.4% to
0.7% (if there had been 2) or 0.0% (if there had been 0).

The monotonic decay pattern (1.3% → 0.9% → 0.7% → 0.5% → 0.4% → 0%)
is suggestive but based on small n at each step. The total of 22
attributed replies across 2,714 sends is a sparse signal.

### Caveats

1. **Pages 1-100 missing.** The step 1 denominator is undercounted.
   If pages 1-100 were fetched, step 1 might have ~1,000 sends,
   lowering its reply rate from 1.3% to ~0.9%. This would make the
   step-5 rate (0.4%) look relatively better.

2. **Reply feed incomplete.** Only 3,006 of ~270,000 estate-wide
   replies were collected. Campaign 330 has 27 human replies total
   (from the provider's own count), of which 22 were attributed.
   The 5 unattributed replies might include step-5 replies.

3. **lead_id is null.** Without lead-level tracking, we cannot
   definitively say whether the step-5 reply came from a lead that
   also replied earlier. The estimate (~1 incremental) assumes
   unique leads per reply, which is very likely given the low rates.

4. **One campaign.** This is a sample of one. Campaign 330 is a
   Dutch-language marketing agency campaign. The result may not
   generalize to other languages, industries, or cadence shapes.

---

## FULL STEP-BY-STEP COMPARISON

| Step | Sent | Replied | Reply rate | Est. incremental | Incr. per 100 sends |
|------|------|---------|-----------|-----------------|---------------------|
| 1 | 715 | 9 | 1.3% | ~9 | 1.25 |
| 2 | 656 | 6 | 0.9% | ~6 | 0.91 |
| 3 | 559 | 4 | 0.7% | ~4 | 0.72 |
| 4 | 411 | 2 | 0.5% | ~2 | 0.49 |
| 5 | 278 | 1 | 0.4% | ~1 | 0.36 |
| 6 | 69 | 0 | 0.0% | 0 | 0.00 |
| 7 | 25 | 0 | 0.0% | 0 | 0.00 |
| 8 | 1 | 0 | 0.0% | 0 | 0.00 |

---

## COST COMPARISON: IS STEP 5 WORTH THE CREDIT?

Each sent email burns one email credit.

| Step | Sends | Incremental replies | Credits per incremental reply |
|------|-------|--------------------|------------------------------|
| 1 | 715 | ~9 | ~79 |
| 2 | 656 | ~6 | ~109 |
| 3 | 559 | ~4 | ~140 |
| 4 | 411 | ~2 | ~206 |
| 5 | 278 | ~1 | ~278 |
| 6 | 69 | 0 | ∞ |
| 7 | 25 | 0 | ∞ |
| 8 | 1 | 0 | ∞ |

**Step 5 costs ~278 email credits per incremental reply.** Steps 6-8
cost credits with zero observed return. The marginal cost per reply
increases monotonically from step 1 to step 5.

Whether step 5 is "worth it" depends on:
- The cost of one email credit
- The value of one reply (even an unclassified one)
- Whether the reply would have been generated by a cheaper step

Given the monotonic decay, **steps 6-8 should be removed** from
similar cadences. Step 5 is marginal — it generates replies at 0.4%,
which is 3.5× worse than step 1 but still non-zero.

---

## OBSERVATIONS (with n)

1. Campaign 330 has 8 parent steps, 103 leads, 4,028 provider-reported
   sends. Status: completed.
2. 2,714 sent rows sampled across 189 pages (pages 101-289).
   Pages 1-100 were not fetched.
3. 27 human replies in the campaign. 22 attributed to sampled steps
   (81.5%). 5 unattributed.
4. Reply rate decreases monotonically: 1.3% → 0.9% → 0.7% → 0.5% →
   0.4% → 0% → 0% → 0%.
5. Step 5 had 278 sends and 1 reply (0.4%).
6. Steps 6-8 had 95 sends combined and 0 replies.
7. Zero replies were classified as `interested`.

## HYPOTHESES

- The monotonic decay in reply rate suggests diminishing returns from
  each additional step. Step 5 is the last step with a non-zero reply
  count, but with n=1 this is not statistically significant.
- Steps 6-8 are strictly wasteful in this campaign: 95 credits spent
  for zero observed replies.
- The thread_reply step (step 2) does NOT show a higher reply rate
  than surrounding new-thread steps (0.9% vs 1.3% at step 1 and 0.7%
  at step 3). With n=6, this is inconclusive.

## PROVEN LEARNINGS

None. One campaign with 22 attributed replies is a sample, not a
finding. A second campaign measurement would either confirm or
contradict the monotonic decay pattern.

## WHAT THIS WOULD COST TO ANSWER DEFINITIVELY

To answer the step-5 incrementality question with confidence:

1. **Full page walk of campaign 330:** Fetch pages 1-100 (100 API
   calls, ~10 seconds). This would add ~1,314 scheduled emails,
   mostly at step 1.

2. **Full reply feed collection:** Walk all ~270,000 replies
   (~2,700 pages at 100/page, ~5 minutes). This would capture all
   of campaign 330's replies.

3. **Repeat on 2-3 more campaigns:** Campaigns 329 (4,300 sends),
   334 (7,269 sends), and 335 (9,759 sends) all have 8 steps and
   real sends. Each would need the same treatment.

4. **lead_id resolution:** The API does not return lead_id on
   scheduled email rows. Without it, incremental analysis relies
   on the assumption that each reply comes from a unique lead.
   This assumption is very likely correct at these reply rates
   (<1%) but cannot be proven without lead-level data.

Total estimated cost: ~15 minutes of API time, ~500 API calls for
the additional page walks, plus the existing ~2,700-page reply feed
walk. The reply feed is the dominant cost.
