# ESTATE BISON CADENCE FINDINGS — 2026-09-14

TASK-070 analysis of the EmailBison estate. Every number carries its row count and statement kind.

## Statement Kinds

    PROVIDER FACT            the API returned this field with this value
    RESONATE RECONSTRUCTION  we derived it from provider data
    ATTRIBUTION HYPOTHESIS   we believe this reply relates to that touch

## Methodology

- **Sent counts** from `emails_sent` on the campaign row (PROVIDER FACT), never `meta.total`.
- **Scheduled emails**: 9,540 sent rows sampled (first 100 pages per campaign, 15 rows/page, offset pagination).
- **Replies**: 3,375 rows from the most recent portion of the cursor-paginated feed (15 rows/page).
- **Reply feed total**: 270,047 rows (PROVIDER FACT from `meta.total`). Our sample is 1.25%.
- **Step resolution**: `sequence_step_id` on scheduled email resolved to parent step `order` via sequence_steps table (RESONATE RECONSTRUCTION).

---

## ESTATE OVERVIEW

| id | name | status | emails_sent | total_leads |
|----|------|--------|-------------|-------------|
| 352 | HeyReach Connection Campaign | active | 92806 | 21215 |
| 327 | FIXED - MARKETING AGENCY - USA - ZVONIMIR APRIL 22 | active | 44976 | 9677 |
| 328 | FIXED -  MARKETING AGENCY - eu - ZVONIMIR APRIL 22 | active | 33695 | 10285 |
| 274 | FIXED - PRODUCTIVE - MARKETING AGENCY - USA - ZVON | archived | 28331 | 9735 |
| 331 | FIXED - MARKETING AGENCY - eu - GERMAN ZVONIMIR AP | completed | 10299 | 643 |
| 335 | FIXED - MARKETING AGENCY ZVONIMIR APRIL 22nd - NOV | completed | 9759 | 547 |
| 334 | FIXED - MARKETING AGENCY - AUSTRALIA- ZVONIMIR APR | completed | 7269 | 326 |
| 329 | FIXED - MARKETING AGENCY - eu - FRENCH ZVONIMIR AP | completed | 4300 | 556 |
| 330 | FIXED - MARKETING AGENCY - eu - DUTCH ZVONIMIR APR | completed | 4028 | 103 |
| 265 | PRODUCTIVE - MARKETING AGENCY -UK - ZVONIMIR APRIL | archived | 1609 | 993 |
| 262 | PRODUCTIVE - MARKETING AGENCY - AUSTRALIA - ZVONIM | archived | 525 | 3 |
| 264 | PRODUCTIVE - MARKETING AGENCY - USA - ZVONIMIR APR | archived | 415 | 311 |
| 266 | PRODUCTIVE - MARKETING AGENCY -CANADA - ZVONIMIR A | archived | 315 | 519 |
| 263 | v2 PRODUCTIVE - MARKETING AGENCY - AUSTRALIA - ZVO | archived | 299 | 297 |
| 451 | RESONATE - PRODUCTIVE CANARY - Hot Soup Group | completed | 1 | 1 |
| 200 | Productive - Marketing agencies - Dusan - Mar 11 2 | archived | 0 | 0 |
| 234 | Productive Marketing agencies US  | archived | 0 | 0 |
| 417 | PRODUCTIVE - SOFTWARE DEVELOPMENT - CONNECTED - JE | draft | 0 | 0 |
| 418 | PRODUCTIVE - SOFTWARE DEVELOPMENT - NOT CONNECTED  | draft | 0 | 0 |
| 423 | MAYBE - Heyreach - Jelena - September 3 | draft | 0 | 0 |
| 424 | INTERESTED - Heyreach - Jelena - September 3 | draft | 0 | 0 |
| 481 | RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - BUY | paused | 0 | 23 |

**PROVIDER FACT.** Total `emails_sent` across estate: 238627.
**PROVIDER FACT.** `open_tracking` is FALSE on every campaign (verified on all 22). No open-rate claim appears.

---

## REPLY FEED CLASSIFICATION (from 3,375-row sample)

| Type | Auto | Count | Interested |
|------|------|-------|-----------|
| Bounced | auto | 1959 | 0 |
| Tracked Reply | human | 843 | 13 |
| Outgoing Email | human | 486 | 3 |
| Tracked Reply | auto | 87 | 0 |

**PROVIDER FACT.** Human replies in sample: 843 (interested: 13).
Automated replies: 2046. Outgoing (our mail): 486.
Feed total: 270,047 rows. Sample: 3,375 (1.25%).

---

## Q1: CAMPAIGN-LEVEL REPLY RATES

Using `emails_sent` (PROVIDER FACT) as denominator. Reply counts from the reply sample. The sample covers the most recent replies only.

| Campaign | emails_sent | Sample replies | Interested | Est. reply% (sample) |
|----------|------------|---------------|-----------|---------------------|
| 352 | 92806 | 409 | 6 | 0.4% |
| 327 | 44976 | 114 | 3 | 0.3% |
| 328 | 33695 | 110 | 1 | 0.3% |
| 274 | 28331 | 70 | 0 | 0.2% |
| 331 | 10299 | 39 | 1 | 0.4% |
| 335 | 9759 | 26 | 1 | 0.3% |
| 334 | 7269 | 33 | 1 | 0.5% |
| 329 | 4300 | 15 | 0 | 0.3% |
| 330 | 4028 | 27 | 0 | 0.7% |
| 265 | 1609 | 0 | 0 | 0.0% |
| 262 | 525 | 0 | 0 | 0.0% |
| 264 | 415 | 0 | 0 | 0.0% |
| 266 | 315 | 0 | 0 | 0.0% |
| 263 | 299 | 0 | 0 | 0.0% |
| 451 | 1 | 0 | 0 | 0.0% |

Total human replies in sample: 843.

**RESONATE RECONSTRUCTION.** The sample covers the most recent ~2 months of the reply feed. Campaigns that finished sending before July 2026 (262-274, 327-335) may have few or no replies in this window. Their reply counts are UNDERCOUNTS.

---

## Q2: STEP-LEVEL SEND DISTRIBUTION

From the 9,540-row scheduled-email sample. Step order resolved from `sequence_step_id` to parent step `order` (RESONATE RECONSTRUCTION).

| Step order | Sample sent | Share of sample |
|-----------|------------|-----------------|
| 1 | 638 | 6.7% |
| 2 | 269 | 2.8% |
| 3 | 869 | 9.1% |
| 4 | 535 | 5.6% |
| 5 | 974 | 10.2% |
| 6 | 1563 | 16.4% |
| 7 | 2118 | 22.2% |
| 8 | 2574 | 27.0% |

Total sample with step resolution: 9540 of 9,540.

---

## Q3: STEP-LEVEL REPLY ATTRIBUTION (ATTRIBUTION HYPOTHESIS)

Human replies from the sample joined to the scheduled-email sample via `scheduled_email_id`. This is an ATTRIBUTION HYPOTHESIS.

| Reply step (ATTR.HYP.) | Replies | Interested | Share |
|------|------|-----------|-------|
| 2 | 3 | 1 | 10.3% |
| 3 | 3 | 0 | 10.3% |
| 4 | 2 | 0 | 6.9% |
| 5 | 2 | 0 | 6.9% |
| 6 | 4 | 0 | 13.8% |
| 7 | 12 | 0 | 41.4% |
| 8 | 3 | 0 | 10.3% |

Total attributed replies: 29 (of 843 human replies = 3.4%).
Unattributed (scheduled email not in our sample): 814.

---

## Q4: CADENCE DELAYS AND DURATION

**PROVIDER FACT.** `wait_in_days` per step position.

| Step position | wait_in_days | Campaigns |
|---------------|-------------|-----------|
| 1 | 2 | 7 |
| 1 | 3 | 7 |
| 1 | 4 | 5 |
| 1 | 5 | 1 |
| 2 | 1 | 1 |
| 2 | 3 | 8 |
| 2 | 4 | 3 |
| 2 | 5 | 7 |
| 3 | 2 | 7 |
| 3 | 3 | 2 |
| 3 | 4 | 3 |
| 3 | 5 | 6 |
| 4 | 1 | 1 |
| 4 | 3 | 6 |
| 4 | 5 | 9 |
| 4 | 7 | 1 |
| 4 | 9 | 1 |
| 5 | 1 | 3 |
| 5 | 3 | 6 |
| 5 | 4 | 2 |
| 5 | 5 | 1 |
| 5 | 7 | 5 |
| 6 | 3 | 13 |
| 6 | 10 | 1 |
| 7 | 1 | 1 |
| 7 | 3 | 7 |
| 7 | 4 | 1 |
| 8 | 1 | 8 |

### Cadence duration per campaign

| Campaign | Parent steps | Total days | Max step |
|----------|-------------|-----------|---------|
| 266 | 6 | 29 | 6 |
| 265 | 6 | 29 | 6 |
| 264 | 6 | 29 | 6 |
| 263 | 6 | 29 | 6 |
| 262 | 6 | 29 | 6 |
| 200 | 7 | 29 | 7 |
| 335 | 8 | 24 | 8 |
| 334 | 8 | 24 | 8 |
| 274 | 8 | 23 | 8 |
| 328 | 8 | 22 | 8 |
| 481 | 5 | 21 | 5 |
| 327 | 8 | 21 | 8 |
| 234 | 5 | 21 | 5 |
| 331 | 8 | 20 | 8 |
| 330 | 8 | 20 | 8 |
| 329 | 8 | 20 | 8 |
| 352 | 5 | 14 | 5 |
| 418 | 4 | 13 | 4 |
| 417 | 2 | 6 | 2 |
| 451 | 1 | 3 | 1 |

---

## Q5: VARIANT-LEVEL DATA (CAMPAIGN 352)

**PROVIDER FACT.** Campaign 352 has 44 sequence steps: 5 parents + 39 variants. Each variant is a first-class step (verdict D, TASK-069).

| Variant id | Parent order | In sample | Replies (ATTR.HYP.) |
|-----------|-------------|-----------|-------|
| 2043 | 1 | 0 | 0 |
| 2044 | 1 | 0 | 0 |
| 2045 | 1 | 0 | 0 |
| 2635 | 1 | 0 | 0 |
| 2636 | 1 | 0 | 0 |
| 2637 | 1 | 0 | 0 |
| 3793 | 1 | 0 | 0 |
| 3794 | 1 | 0 | 0 |
| 3795 | 1 | 0 | 0 |
| 3796 | 1 | 0 | 0 |
| 3797 | 1 | 0 | 0 |
| 3798 | 1 | 0 | 0 |
| 3799 | 1 | 0 | 0 |
| 3816 | 1 | 0 | 0 |
| 3817 | 1 | 0 | 0 |
| 3818 | 1 | 0 | 0 |
| 3819 | 1 | 0 | 0 |
| 3820 | 1 | 0 | 0 |
| 3821 | 1 | 0 | 0 |
| 3822 | 1 | 0 | 0 |
| 4036 | 1 | 45 | 0 |
| 4192 | 1 | 56 | 0 |
| 4193 | 1 | 49 | 0 |
| 4194 | 1 | 53 | 0 |
| 4195 | 1 | 56 | 0 |
| 4196 | 1 | 46 | 0 |
| 4665 | 1 | 0 | 0 |
| 4668 | 1 | 0 | 0 |
| 4670 | 1 | 0 | 0 |
| 2047 | 2 | 0 | 0 |
| 2048 | 2 | 0 | 0 |
| 2049 | 2 | 0 | 0 |
| 2639 | 2 | 0 | 0 |
| 2640 | 2 | 0 | 0 |
| 2641 | 2 | 0 | 0 |
| 3103 | 2 | 0 | 0 |
| 3104 | 2 | 0 | 0 |
| 3105 | 2 | 0 | 0 |
| 3106 | 2 | 0 | 0 |
| 3107 | 2 | 0 | 0 |
| 3800 | 2 | 0 | 0 |
| 3801 | 2 | 0 | 0 |
| 3803 | 2 | 0 | 0 |
| 3823 | 2 | 0 | 0 |
| 3824 | 2 | 0 | 0 |
| 3825 | 2 | 0 | 0 |
| 4038 | 2 | 21 | 0 |
| 4039 | 2 | 17 | 0 |
| 4197 | 2 | 19 | 0 |
| 4198 | 2 | 18 | 0 |
| 4199 | 2 | 11 | 0 |
| 4200 | 2 | 21 | 0 |
| 4201 | 2 | 21 | 0 |
| 4202 | 2 | 16 | 0 |
| 4203 | 2 | 8 | 0 |
| 4204 | 2 | 19 | 1 |
| 4205 | 2 | 24 | 0 |
| 4206 | 2 | 13 | 0 |
| 4207 | 2 | 22 | 1 |
| 2051 | 3 | 0 | 0 |
| 2052 | 3 | 0 | 0 |
| 2053 | 3 | 0 | 0 |
| 2643 | 3 | 0 | 0 |
| 2644 | 3 | 0 | 0 |
| 2645 | 3 | 0 | 0 |
| 3109 | 3 | 0 | 0 |
| 3110 | 3 | 0 | 0 |
| 3111 | 3 | 0 | 0 |
| 3112 | 3 | 0 | 0 |
| 3113 | 3 | 0 | 0 |
| 3804 | 3 | 0 | 0 |
| 3805 | 3 | 0 | 0 |
| 3806 | 3 | 0 | 0 |
| 3807 | 3 | 0 | 0 |
| 3826 | 3 | 0 | 0 |
| 3827 | 3 | 0 | 0 |
| 3828 | 3 | 0 | 0 |
| 3829 | 3 | 0 | 0 |
| 4041 | 3 | 21 | 1 |
| 4042 | 3 | 26 | 0 |
| 4209 | 3 | 21 | 0 |
| 4210 | 3 | 22 | 0 |
| 4211 | 3 | 25 | 0 |
| 4212 | 3 | 22 | 1 |
| 4213 | 3 | 24 | 0 |
| 4214 | 3 | 23 | 0 |
| 4672 | 3 | 0 | 0 |
| 4673 | 3 | 0 | 0 |
| 2055 | 4 | 0 | 0 |
| 2056 | 4 | 0 | 0 |
| 2057 | 4 | 0 | 0 |
| 2647 | 4 | 0 | 0 |
| 2648 | 4 | 0 | 0 |
| 2649 | 4 | 0 | 0 |
| 3115 | 4 | 0 | 0 |
| 3116 | 4 | 0 | 0 |
| 3117 | 4 | 0 | 0 |
| 3118 | 4 | 0 | 0 |
| 4044 | 4 | 26 | 0 |
| 4215 | 4 | 24 | 1 |
| 4216 | 4 | 20 | 0 |
| 4217 | 4 | 22 | 0 |
| 4218 | 4 | 27 | 0 |
| 4219 | 4 | 14 | 0 |
| 4675 | 4 | 0 | 0 |
| 4676 | 4 | 0 | 0 |
| 2059 | 5 | 0 | 0 |
| 2060 | 5 | 0 | 0 |
| 2061 | 5 | 0 | 0 |
| 3120 | 5 | 0 | 0 |
| 3121 | 5 | 0 | 0 |
| 3122 | 5 | 0 | 0 |
| 3123 | 5 | 0 | 0 |
| 3124 | 5 | 0 | 0 |
| 4046 | 5 | 18 | 0 |
| 4047 | 5 | 16 | 0 |
| 4220 | 5 | 23 | 0 |
| 4221 | 5 | 20 | 0 |
| 4222 | 5 | 28 | 0 |
| 4223 | 5 | 24 | 0 |
| 3126 | 6 | 0 | 0 |
| 3127 | 6 | 0 | 0 |
| 3128 | 6 | 0 | 0 |
| 3129 | 6 | 0 | 0 |
| 3132 | 8 | 0 | 0 |
| 3133 | 8 | 0 | 0 |
| 3134 | 8 | 0 | 0 |
| 3135 | 8 | 0 | 0 |

---

## Q6: COPY SHAPE (FROM SAMPLE)

### Subject-line patterns (top 20)

| Subject (truncated) | Count | Pattern |
|---------------------|-------|---------|
| last note from me | 390 | statement |
| leaving the door open | 373 | statement |
| should I be talking to someone else? | 328 | question |
| quick question before I stop reaching out | 300 | statement |
| ich lasse die Tür offen | 247 | statement |
| a different way to look at this | 225 | statement |
| the cost of the current setup | 223 | statement |
| letzte Nachricht von mir | 220 | statement |
| every agency hits this at some point | 208 | statement |
| the 8% margin problem | 203 | statement |
| when you find out too late | 181 | statement |
| sollte ich mit jemand anderem reden? | 159 | question |
| kurze Frage, bevor ich aufhöre | 151 | statement |
| une question rapide avant d'arrêter | 139 | statement |
| je laisse la porte ouverte | 136 | statement |
| dernier message de ma part | 134 | statement |
| laatste berichtje van mij | 124 | statement |
| une façon différente de voir les choses | 121 | statement |
| est-ce que je devrais parler à quelqu'un d'autre ? | 116 | question |
| snelle vraag voor ik stop | 106 | statement |

Question-led subjects: 1703 (17.9%)
Statement-led subjects: 7837 (82.1%)

---

## RE-DERIVATION: THE 8.49% CLAIM

An earlier session recorded "8-step email sequences reply at 8.49% (n=17,690)". Re-deriving from `emails_sent` (PROVIDER FACT) and reply sample.

| Max steps | Campaigns | emails_sent | Sample replies | Reply% (sample) |
|-----------|-----------|-------------|---------------|-----------------|
| 1 | 1 | 1 | 0 | 0.0% |
| 5 | 1 | 92806 | 409 | 0.4% |
| 6 | 5 | 3163 | 0 | 0.0% |
| 8 | 8 | 142657 | 434 | 0.3% |

**The 8.49% figure was NOT reproduced.** The reply sample covers only the most recent ~2 months. Campaigns that finished before July 2026 have their replies outside the sample window. The true reply rate for older campaigns cannot be determined from this sample alone.

To fully re-derive this claim, the complete reply feed (270,047 rows) must be collected and classified. At 15 rows/page and ~1.5s/page, this requires ~18,000 pages and ~7.5 hours of collection time.

---

## CAVEATS AND DISCIPLINE

1. **Sent counts from `emails_sent`, never `meta.total`.** Campaign 274 has 30,411 scheduled rows and ZERO of its first 100 pages carry `sent_at`.
2. **Reply sample is 1.25% of the feed** (3,375 of 270,047). It covers the most recent ~2 months only. Older campaign replies are NOT in the sample.
3. **Classified the reply feed.** Auto-replies and outgoing mail excluded from human counts.
4. **No open-rate claim.** `open_tracking` is False on every campaign.
5. **Every causal statement is an ATTRIBUTION HYPOTHESIS.**
6. **`interested` as positive proxy.** Not a classifier verdict — TASK-067's thread-context classifier has not been run.
7. **Campaign 274 and 263**: 0 sent rows in first 100 pages. Their sends are deeper in the pagination. Step-level data for these campaigns is ABSENT.
8. **Sample size discipline.** n<30 differences are OBSERVATIONS, not PROVEN LEARNINGS.

---

*Generated by `scripts/task070_generate_report.py`. Data in `.qwen/tmp/task070/cadence.db`. Collection script: `scripts/bison_cadence_analysis.py`.*