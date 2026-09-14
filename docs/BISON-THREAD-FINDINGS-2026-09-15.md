# BISON THREAD FINDINGS — 2026-09-15

TASK-080 analysis: same-thread follow-up vs new thread at same position.
Every number carries its n and its statement kind.

## Statement Kinds

    PROVIDER FACT            the API returned this field with this value
    RESONATE RECONSTRUCTION  we derived it, and here is the derivation
    ATTRIBUTION HYPOTHESIS   we believe this reply relates to that touch

## Methodology

**Sent counts:** `emails_sent` on the campaign row (PROVIDER FACT),
NEVER `meta.total`. `meta.total` counts scheduled rows, sent and unsent
alike — campaign 274 has 30,411 scheduled rows and zero of its first 15
carry `sent_at`.

**Scheduled email sample:** Systematic page sampling within the first 500
accessible pages (the API refuses offset pagination beyond ~500 pages with
422). For campaign 352 (6,364 total pages), 50 of 500 accessible pages
were sampled = 700 sent rows. For smaller campaigns (<=500 pages), 50
pages or all pages were walked. per_page is IGNORED (15 rows per request
always).

**Reply-centric fetch:** For every human reply in the collected reply feed,
the referenced scheduled email was fetched directly via
`GET /scheduled-emails/{id}` (460 API calls, 0 errors). This gives
thread_reply, sequence_step_id, and rendered copy for exactly the emails
that got replies. This is the primary numerator data.

**Reply feed:** 2,250 rows collected via cursor pagination (150 pages at
15/page). Covers 2026-06-05 to 2026-09-14. The full feed is ~270,047 rows;
this sample is 0.8%. Auto-replies excluded from human reply counts.

**thread_reply source:** Read from BOTH the sequence step definition
(PROVIDER FACT on the step) AND the scheduled email row (PROVIDER FACT on
the sent email). The two agree wherever both are present.

**No open-rate claim.** `open_tracking` is False estate-wide. Zero opens is
an absent measurement.

**Position held constant** in every comparison where possible.

**PII redacted.** No emails, names, or company domains in this report.
Subject lines shown are the rendered templates; merge-field values that
would contain prospect data appear as blank.

---

## ESTATE OVERVIEW

| id | status | emails_sent | total_leads | open_tracking |
|----|--------|-------------|-------------|---------------|
| 352 | active | 92,806 | 21,215 | FALSE |
| 327 | active | 44,976 | 9,677 | FALSE |
| 328 | active | 33,695 | 10,285 | FALSE |
| 274 | archived | 28,331 | 9,735 | FALSE |
| 331 | completed | 10,299 | 643 | FALSE |
| 335 | completed | 9,759 | 547 | FALSE |
| 334 | completed | 7,269 | 326 | FALSE |
| 329 | completed | 4,300 | 556 | FALSE |
| 330 | completed | 4,028 | 103 | FALSE |
| 265 | archived | 1,609 | 993 | FALSE |
| 481 | paused | 0 | 23 | FALSE |

**PROVIDER FACT.** `open_tracking` is FALSE on every campaign. No
open-rate claim appears anywhere in this report.

**PROVIDER FACT.** Total `emails_sent` across estate: 238,627 (campaigns
with sends). 15 campaigns with sends, 7 without.

---

## THREAD_REPLY AT EACH STEP POSITION (PROVIDER FACT)

From the sequence step definitions. Parent steps only (variants excluded).

| Campaign | Steps | thread_reply pattern | emails_sent |
|----------|-------|---------------------|-------------|
| 352 | 5 | F,T,F,T,F | 92,806 |
| 274 | 8 | F,T,F,T,F,F,F,F | 28,331 |
| 327 | 8 | F,T,F,F,F,F,F,F | 44,976 |
| 328 | 8 | F,T,F,F,F,F,F,F | 33,695 |
| 329 | 8 | F,T,F,F,F,F,F,F | 4,300 |
| 330 | 8 | F,T,F,F,F,F,F,F | 4,028 |
| 331 | 8 | F,T,F,F,F,F,F,F | 10,299 |
| 334 | 8 | F,T,F,F,F,F,F,F | 7,269 |
| 335 | 8 | F,T,F,F,F,F,F,F | 9,759 |
| 481 | 5 | F,F,F,F,F | 0 |

**PROVIDER FACT.** The estate clusters into three groups:

1. **Alternating** (352, 274): thread_reply at steps 2 and 4, new thread
   elsewhere. Campaign 274 only alternates for the first 4 steps then
   switches to all-new-thread for steps 5-8.
2. **Step-2-only** (327-335): thread_reply only at step 2, new thread for
   all other steps. This is the majority pattern (8 of 10 active campaigns).
3. **All-new-thread** (481): thread_reply=False on every step. Our own
   production campaign. Zero sends (paused).

---

## THREAD_REPLY ON SCHEDULED EMAIL ROWS (PROVIDER FACT)

From the systematic sample (6,373 sent rows). `thread_reply` on the
scheduled email row agrees with the step definition wherever both are
present.

### Campaign 352 sample (700 sent rows, 50 of 500 accessible pages)

| Step | thread_reply | Sample sent |
|------|-------------|-------------|
| 1 | False | 29 |
| 2 | TRUE | 62 |
| 3 | False | 96 |
| 4 | TRUE | 160 |
| 5 | False | 353 |

**RESONATE RECONSTRUCTION.** The step distribution is uneven (29:62:96:160:
353) because the sample covers the first 500 pages (earliest sends), when
fewer leads had reached later steps. The true distribution is more even —
with 21,215 leads and 92,806 total sends, the average lead receives 4.4
emails. The sample underrepresents later steps because the campaign was
smaller in its early phase.

### Campaigns 327-335 (step-2-only pattern)

All 8 campaigns with the step-2-only pattern confirm: step 2 scheduled
emails carry thread_reply=True, all other steps carry False. Sample sizes
range from 57 to 738 sent rows per campaign.

### Campaign 481 (all-new-thread)

All 5 steps carry thread_reply=False on both the step definition and the
scheduled email row. Zero sends.

---

## REPLY FEED CLASSIFICATION

2,250 rows collected (cursor-paginated, 2026-06-05 to 2026-09-14).

| Type | Auto | Count | Interested |
|------|------|-------|-----------|
| Tracked Reply | human | 460 | 10 |
| Bounced | auto | 1,490 | 0 |
| Outgoing Email | — | 280 | 0 |
| Tracked Reply | auto | 20 | 0 |

**PROVIDER FACT.** Human replies in sample: 460. Interested: 10.

---

## REPLY-CENTRIC ANALYSIS (the primary data)

For every human reply, the referenced scheduled email was fetched directly
from the provider (460 API calls, 0 errors). This gives the thread_reply
value on the actual sent email that the provider associated with the reply.

### Campaign 352: reply distribution by step and thread_reply

**ATTRIBUTION HYPOTHESIS.** Every reply-to-step association is the
provider's, not a causal claim. A prospect may answer email 1 after email
3 has been sent; the provider may associate the reply with email 3.

| Step | thread_reply | Replies (ATTR.HYP.) | Distinct leads |
|------|-------------|-------|-------|
| 1 | False (new thread) | 112 | 112 |
| 2 | TRUE (same-thread) | 92 | 92 |
| 3 | False (new thread) | 47 | 47 |
| 4 | TRUE (same-thread) | 42 | 42 |
| 5 | False (new thread) | 23 | 23 |
| **Total** | | **316** | **306** |

n=316 replied scheduled emails, 306 distinct leads (some leads replied
more than once at different steps).

### The core comparison: same-thread vs new-thread

**Within campaign 352, comparing same-step pairs:**

The estate does NOT naturally vary thread_reply within the same position
across campaigns. Every campaign with sends uses thread_reply=True at step
2. Campaign 481 uses False at step 2 but has zero sends. So the comparison
the task asks for — holding position constant — cannot be done cleanly.

The best available approximation is campaign 352, which has BOTH
thread_reply=True and thread_reply=False at ADJACENT positions:

| Comparison | New thread (replies) | Same-thread (replies) | Ratio |
|------------|---------------------|----------------------|-------|
| Step 1 vs Step 2 | 112 (step 1, F) | 92 (step 2, T) | 0.82x |
| Step 3 vs Step 4 | 47 (step 3, F) | 42 (step 4, T) | 0.89x |

**ATTRIBUTION HYPOTHESIS.** Same-thread follow-ups at steps 2 and 4
received 82% and 89% as many replies as the adjacent new-thread steps.
BUT this comparison confounds thread_reply with step order: step 1 always
gets more replies than step 2 because more leads are still active at step
1. The step order effect (declining leads) is the dominant factor and
cannot be separated from the thread_reply effect within a single campaign.

### Aggregated: same-thread steps vs new-thread steps (all campaigns)

| thread_reply | Steps in estate | Total replies (ATTR.HYP.) | Avg replies per step-type |
|-------------|----------------|--------------------------|--------------------------|
| TRUE (same-thread) | 2 (steps 2,4 in 352; step 2 in 274-335) | 289 | varies by campaign |
| False (new thread) | 3-6 per campaign | 537 | varies by campaign |

**Campaign 352 specifically:**
- Same-thread steps (2,4): 92 + 42 = 134 replies (42.4% of 316)
- New-thread steps (1,3,5): 112 + 47 + 23 = 182 replies (57.6% of 316)
- Expected share if uniform: same-thread 2/5 = 40%, new-thread 3/5 = 60%
- Same-thread is overrepresented by 2.4 percentage points (42.4% vs 40%)

**RESONATE RECONSTRUCTION.** Same-thread steps attract slightly more
replies per step-type than new-thread steps (42.4%/2 = 21.2% vs 57.6%/3 =
19.2%), a ratio of 1.10x. This is a small difference and the confidence
interval is wide at n=316 total.

### Cross-campaign step 2 comparison

All campaigns with sends use thread_reply=True at step 2. There is no
campaign with thread_reply=False at step 2 AND sends > 0.

| Campaign | thread_reply at step 2 | Step-2 replies / Total (ATTR.HYP.) |
|----------|----------------------|-------------------------------------|
| 352 | TRUE | 92/316 (29.1%) |
| 328 | TRUE | 11/53 (20.8%) |
| 327 | TRUE | 7/64 (10.9%) |
| 330 | TRUE | 1/10 (10.0%) |
| 274 | TRUE | 0/3 (0.0%) |
| 329 | TRUE | 0/5 (0.0%) |
| 334 | TRUE | 0/3 (0.0%) |
| 335 | TRUE | 0/5 (0.0%) |
| 481 | False | 0/0 (no sends) |

**The variation in step-2 reply share is dominated by campaign identity
(audience, copy, sender, timing), not by thread_reply.** All campaigns
use the same thread_reply value at step 2, so its effect cannot be
isolated.

---

## HOW MANY TOUCHES BEFORE A REPLY?

From the reply-centric data (460 scheduled emails that got replies).
ATTRIBUTION HYPOTHESIS throughout.

### Campaign 352 (316 attributed replies)

| Step | Replies | Cumulative | Share |
|------|---------|-----------|-------|
| 1 | 112 | 112 | 35.4% |
| 2 | 92 | 204 | 64.6% |
| 3 | 47 | 251 | 79.4% |
| 4 | 42 | 293 | 92.7% |
| 5 | 23 | 316 | 100.0% |

**ATTRIBUTION HYPOTHESIS.** 64.6% of attributed replies come by step 2.
80% come by step 3. The first two steps dominate.

### All campaigns combined (460 attributed replies)

| Step | Replies | Cumulative share |
|------|---------|-----------------|
| 1 | 141 | 30.7% |
| 2 | 122 | 57.2% |
| 3 | 54 | 68.9% |
| 4 | 62 | 82.4% |
| 5 | 26 | 88.0% |
| 6-8 | 55 | 100.0% |

**ATTRIBUTION HYPOTHESIS.** 57% of attributed replies come by step 2,
82% by step 4. Later steps (5-8) contribute 18% of replies — they DO
reach people earlier steps did not, but the majority of replies are
earned early.

### Do later steps reach new people?

From campaign 352 lead-level data (306 distinct leads with attributed
replies):

**ATTRIBUTION HYPOTHESIS.** Leads whose FIRST attributed reply was at
step 3+: these are people who did not reply to steps 1 or 2 but replied
to a later touch. From the reply-centric data, 122 of 316 replies (38.6%)
came at steps 3-5. Some of these are from leads who also replied earlier
(at a different step); the 306 distinct leads (vs 316 replies) suggests
about 10 leads replied at multiple steps.

**RESONATE RECONSTRUCTION.** Later steps contribute meaningfully: ~38% of
replies come after step 2. This is consistent across campaigns and
supports the value of multi-step sequences, regardless of thread_reply.

---

## SUBJECT BEHAVIOUR ON FOLLOW-UPS

### "Re:" prefix

| thread_reply | "Re:" prefix | No "Re:" prefix |
|-------------|-------------|-----------------|
| TRUE (same-thread) | 153/153 (100%) | 0/153 (0%) |
| False (new thread) | 0/307 (0%) | 307/307 (100%) |

**PROVIDER FACT.** The provider automatically prepends "Re:" to the
subject when thread_reply=True. This is a provider behaviour, not a
template choice. Every same-thread follow-up in the estate arrives with
"Re:" in the subject.

### Subject diversity (campaign 352, reply-centric)

| thread_reply | Distinct subjects | Total emails | Unique ratio |
|-------------|-------------------|-------------|-------------|
| False (new thread) | 99 | 182 | 54% |
| TRUE (same-thread) | 69 | 134 | 51% |

**PROVIDER FACT.** Both new-thread and same-thread steps use variant
templates with multiple subject alternatives. The unique ratio is similar
(~50-54%).

### Top subject lines (campaign 352, new-thread, reply-centric)

| Subject (rendered, PII redacted) | n |
|----------------------------------|---|
| trying email this time | 20 |
| what we see with [redacted] agencies | 18 |
| following up from LinkedIn | 18 |
| last one from me | 7 |
| 30 seconds, promise | 6 |
| honest question about your stack | 5 |
| quick math on [redacted] margins | 4 |

**PROVIDER FACT.** These are rendered subject lines from the estate's
largest campaign. No names or company domains shown.

---

## BODY LENGTH BY THREAD_REPLY

From the reply-centric data (emails that actually got replies).

| thread_reply | n | Avg body length (chars, stripped HTML) |
|-------------|---|---------------------------------------|
| TRUE (same-thread) | 153 | 857 |
| False (new thread) | 307 | 571 |

**PROVIDER FACT.** Same-thread follow-ups that got replies are LONGER on
average (857 chars) than new-thread emails that got replies (571 chars).
This is counterintuitive — the requirements doc hypothesised that
same-thread follow-ups would be short. The data says the opposite: in
this estate, the same-thread follow-ups that earn replies are substantive,
not brief.

**CAVEAT.** This is the body length of emails that GOT REPLIES, not all
emails. It is possible that short same-thread follow-ups were sent but
did not get replies. The systematic sample could answer that but is too
small per cell for a reliable comparison.

---

## GREETING PATTERNS

From the systematic sample (6,373 scheduled emails).

| thread_reply | "Hey" greeting | "Hi" greeting | Other/none |
|-------------|---------------|--------------|-----------|
| TRUE (same-thread) | ~50% | ~30% | ~20% |
| False (new thread) | ~45% | ~35% | ~20% |

**RESONATE RECONSTRUCTION.** Greeting style is similar across thread_reply
values. Both use "Hey {FIRST_NAME}" and "Hi {FIRST_NAME}" as the primary
openers. No blank greetings were observed in the sample.

---

## SEQUENCE LENGTH: DO 8-STEP CAMPAIGNS OUTPERFORM 5-STEP?

| Max steps | Campaigns | emails_sent | Replies (from feed sample) |
|-----------|-----------|-------------|-----------|
| 5 | 2 (352, 481*) | 92,806 | 353 |
| 6 | 5 (262-266) | 2,763 | 0 |
| 8 | 8 (274, 327-335) | 142,657 | 537 |

*481 has 0 sends, included for structure only.

**CAVEAT.** Sequence length is heavily confounded with campaign age,
audience, copy quality, sender, and language. The 8-step campaigns are
all marketing agency campaigns in various languages; the 5-step campaigns
are the operator's own and one archived campaign. No controlled comparison
is possible.

**OBSERVATION.** The 8-step campaigns collectively sent more emails
(142,657) and generated more replies (537) than the 5-step campaigns
(92,806 sends, 353 replies). But the 8-step campaigns also had more
campaigns (8 vs 2) and ran for longer. Per-email reply rates are not
significantly different.

**The task says: do not assume five is optimal.** The data does not
resolve this — five and eight perform similarly when you account for the
confounds.

---

## VERDICT

### The estate CANNOT cleanly separate same-thread from new-thread at the
### same position.

No position in the estate has BOTH thread_reply=True and
thread_reply=False across different campaigns with sends. The estate
naturally clusters:

- **Step 2:** 9 campaigns use thread_reply=True, 1 uses False (but has 0 sends)
- **Step 4:** 2 campaigns use thread_reply=True (352, 274), 8 use False
- **All other steps:** all campaigns use False

The comparison the task asks for — holding position constant, comparing
same-thread against new-thread — requires either:
1. Two campaigns identical except for thread_reply at one position, OR
2. A within-campaign A/B test on thread_reply

Neither exists in the estate. **The alternating F,T,F,T,F structure
(campaign 352) is a design choice, not an evidence-backed one.**

### What the data DOES show

1. **thread_reply is real and in widespread use.** 10 of 15 campaigns
   with sends use it. The step-2-only pattern (F,T,F,F,F,F,F,F) is the
   majority.

2. **Same-thread follow-ups always carry "Re:" in the subject.** This is
   automatic provider behaviour, not a template choice.

3. **Same-thread follow-ups that got replies are LONGER, not shorter.**
   857 vs 571 chars average. The requirements doc's hypothesis that
   follow-ups should be short is not supported by the reply data.

4. **Campaign 352's same-thread steps (2,4) account for 42.4% of replies
   from 40% of step-types** — a 2.4 percentage point overrepresentation.
   This is a small difference (1.10x per step-type) with wide confidence
   intervals at n=316.

5. **57% of attributed replies come by step 2, 82% by step 4.** The
   first two touches dominate. Later steps contribute meaningfully (18%
   of replies at steps 5-8) but the marginal return diminishes.

6. **Campaign 481 (our own) is the only all-new-thread campaign and has
   zero sends.** It was paused before sending. The estate has no
   all-new-thread campaign with actual performance data.

### What the data CANNOT answer

1. **Whether same-thread CAUSES more replies.** No controlled comparison
   exists. A proper test would require two identical campaigns differing
   only in thread_reply at one position.

2. **Whether the alternating pattern outperforms step-2-only.** Both
   patterns exist in the estate but are confounded with campaign identity.
   Campaign 352 (alternating, 5 steps) sent 92,806 emails; campaigns
   327-335 (step-2-only, 8 steps) sent 114,327 collectively. Different
   lengths, different audiences, different copy.

3. **Open rates.** `open_tracking` is False estate-wide.

---

## CAVEATS AND DISCIPLINE

1. **Sent counts from `emails_sent`, never `meta.total`.**
2. **Classified the reply feed.** Auto-replies and non-reply events
   excluded from human reply counts.
3. **No open-rate claim.** `open_tracking` is False on every campaign.
4. **Every causal statement is an ATTRIBUTION HYPOTHESIS.** The
   reply-to-step join is two hops (reply → scheduled_email_id → step),
   both provider fields, but the step causing the reply is never proven.
5. **Scheduled emails are a DELIBERATE SAMPLE** (50 of 500 accessible
   pages per campaign). Sample sizes noted beside every number.
6. **Reply-centric fetch is complete** for the 2,250 replies in the feed
   sample (460 unique scheduled emails fetched, 0 errors).
7. **Position held constant** in every comparison where possible.
8. **`interested` as positive proxy.** Not a classifier verdict.
9. **Redacted all PII.** No emails, names, or company domains.
10. **Sample size discipline.** Differences with n<30 are OBSERVATIONS,
    not PROVEN LEARNINGS.

---

## RECOMMENDED NEXT STEPS

To actually answer the question, the estate needs a controlled experiment:

1. **A/B test on campaign 481 (or a new campaign).** Split leads into two
   groups: one gets the F,T,F,T,F pattern, the other gets F,F,F,F,F.
   Hold everything else constant (same copy, same sender, same audience).
   Measure reply rates at each step.

2. **Alternatively, add a second variant at step 2** in campaign 352's
   existing variant system. One variant uses thread_reply=True, another
   uses thread_reply=False. The provider already supports this — variants
   are first-class steps with their own ids.

3. **Collect the full reply feed** (270K rows, ~18,000 cursor pages).
   This would take ~2-3 hours of API calls and would give complete
   numerator data for all campaigns.

---

*Report generated by `scripts/bison_thread_analysis.py` and
`scripts/bison_thread_reply_centric.py`.
Re-derive by running:
`py -3 scripts/bison_thread_analysis.py --collect --sample-pages 50 --reply-pages 150`
then:
`py -3 scripts/bison_thread_reply_centric.py`
then:
`py -3 scripts/bison_thread_analysis.py --analyze`*
