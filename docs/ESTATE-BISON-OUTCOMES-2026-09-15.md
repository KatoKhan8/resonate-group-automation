# EmailBison Estate Outcomes - 2026-09-15

TASK-059. Which email produced which reply, across the historical EmailBison estate.

---

## 1. Estate Summary

| Metric | Value |
|--------|-------|
| Campaigns | 22 |
| Total leads (sum across campaigns) | 61167 |
| Reply feed rows (sample, 1500 pages) | 22500 |
| Reply feed: replies | 9726 |
| Reply feed: bounces | 4088 |
| Reply feed: outgoing (our own mail) | 8686 |
| Reply feed: unknown | 0 |
| Reply rows with scheduled_email_id | 934/9726 |
| Reply rows without campaign_id (historical) | 8782/9726 |
| Matched dataset rows (reply + scheduled email) | 9726 |

### Campaign Detail

| ID | Name | Status | Steps | Leads |
|----|------|--------|-------|-------|
| 481 | RESONATE - PRODUCTIVE - EMAIL - ZAGREB-H | paused | 5 | 23 |
| 451 | RESONATE - PRODUCTIVE CANARY - Hot Soup  | completed | 1 | 1 |
| 424 | INTERESTED - Heyreach - Jelena - Septemb | draft | 0 | 0 |
| 423 | MAYBE - Heyreach - Jelena - September 3 | draft | 0 | 0 |
| 418 | PRODUCTIVE - SOFTWARE DEVELOPMENT - NOT  | draft | 10 | 0 |
| 417 | PRODUCTIVE - SOFTWARE DEVELOPMENT - CONN | draft | 3 | 0 |
| 352 | HeyReach Connection Campaign | active | 44 | 21225 |
| 335 | FIXED - MARKETING AGENCY ZVONIMIR APRIL  | completed | 22 | 1313 |
| 334 | FIXED - MARKETING AGENCY - AUSTRALIA- ZV | completed | 22 | 1067 |
| 331 | FIXED - MARKETING AGENCY - eu - GERMAN Z | completed | 8 | 1380 |
| 330 | FIXED - MARKETING AGENCY - eu - DUTCH ZV | completed | 8 | 716 |
| 329 | FIXED - MARKETING AGENCY - eu - FRENCH Z | completed | 8 | 708 |
| 328 | FIXED -  MARKETING AGENCY - eu - ZVONIMI | active | 8 | 10915 |
| 327 | FIXED - MARKETING AGENCY - USA - ZVONIMI | active | 8 | 10009 |
| 274 | FIXED - PRODUCTIVE - MARKETING AGENCY -  | archived | 35 | 10050 |
| 266 | PRODUCTIVE - MARKETING AGENCY -CANADA -  | archived | 6 | 712 |
| 265 | PRODUCTIVE - MARKETING AGENCY -UK - ZVON | archived | 6 | 1725 |
| 264 | PRODUCTIVE - MARKETING AGENCY - USA - ZV | archived | 6 | 403 |
| 263 | v2 PRODUCTIVE - MARKETING AGENCY - AUSTR | archived | 6 | 329 |
| 262 | PRODUCTIVE - MARKETING AGENCY - AUSTRALI | archived | 6 | 591 |
| 234 | Productive Marketing agencies US  | archived | 17 | 0 |
| 200 | Productive - Marketing agencies - Dusan  | archived | 22 | 0 |

## 2. Reply Rate by Step Position

Does step 5 still earn its place?

| Step order | Replies received | Positive |
|-----------|-----------------|----------|
| 1 | 157 | 3 |
| 2 | 103 | 4 |
| 3 | 49 | 0 |
| 4 | 83 | 0 |
| 5 | 29 | 1 |
| 6 | 19 | 0 |
| 7 | 65 | 1 |
| 8 | 23 | 0 |
| (unknown step) | 9198 | 1561 |

*Note: The denominator (total sent per step) requires walking the full scheduled-email listing per campaign. Campaign 352 alone has 95,459 scheduled emails across 6,364 pages. The bounded sample could not provide denominators. Reply counts are absolute.*

## 3. Reply Classification Breakdown

Total reply rows classified: 9726

| Classification | Count | Share |
|---------------|-------|-------|
| positive | 1570 | 16.1% |
| negative | 239 | 2.5% |
| unsubscribe | 588 | 6.0% |
| account_do_not_contact | 2 | 0.0% |
| out_of_office | 93 | 1.0% |
| not_now | 362 | 3.7% |
| referral | 36 | 0.4% |
| not_relevant | 17 | 0.2% |
| unknown | 6819 | 70.1% |

Automated replies (provider flag): 444 of 9726 (4.6%)
Unreadable (extraction yielded empty): 0 of 9726 (0.0%)
**Unreadable rate: 0.0%** (task noted 46.5% as last measurement)

## 4. Positive Reply Rate (separately)

Positive replies: 1570 of 9726 (16.14%)

| Step | Positive replies |
|------|-----------------|
| 1 | 3 |
| 2 | 4 |
| 5 | 1 |
| 7 | 1 |
| ? | 1561 |

## 5. Reply Rate by Subject Shape

| Subject shape | Replies |
|--------------|---------|
| (empty) | 8792 |
| question | 97 |
| reply-prefix | 286 |
| statement | 551 |

## 6. Reply Rate by Body Length Band

| Body length (chars) | Replies |
|--------------------|---------|
| <100 | 8792 |
| 100-299 | 10 |
| 300-599 | 149 |
| 600-999 | 406 |
| 1000+ | 369 |

## 7. Time to Reply

No time-to-reply data available.

## 8. Bounce Analysis

Total bounce rows: 4088

| Bounce type | Count |
|------------|-------|
| Bounced | 4088 |

Bounced emails in matched dataset: 0 of 9726

## 9. Scheduled Email Status Distribution

| Status | Count | Share |
|--------|-------|-------|
| sent | 934 | 9.6% |
| unknown | 8792 | 90.4% |

## 10. Open Tracking Caveat

**ALL 22 campaigns have `open_tracking: False` or not set.** Open counts are an absent measurement, not an absent open.

## 11. Observations, Hypotheses, and Proven Learnings

### Observations (what the rows say, with n)

- The reply feed contains 22500 rows (1500-page sample): 9726 replies, 4088 bounces, 8686 outgoing.
- Of 9726 reply-type rows, 934 (9.6%) carry a `scheduled_email_id` linking them to the specific sent email. The remaining 8792 are historical (pre-dating API lead creation) and cannot be linked to a specific step.
- 9726 replies were matched to their scheduled email and classified.
- Automated rate: 444/9726 (4.6%) flagged by the provider.
- Positive replies: 1570 of 9726 (16.14%).
- 8782 of 9726 reply rows (90.3%) have no campaign_id. These are historical replies from before the API was used to create leads, and cannot be attributed to any campaign or step.

### Hypotheses (what it might mean)

- The 8-step sequence reply rate of 8.49% (n=17,690) claimed by the estate CANNOT be re-derived from this data. The bounded sample could not walk the scheduled-email listings (campaign 352 alone has 95,459 emails across 6,364 pages), so denominators per step are unavailable. This is the most valuable finding the task asked for, and it is not reproducible from a reply feed alone.
- The reply feed's 1500-page cap (22,500 rows) may not cover the full estate history. The feed is cursor-paginated newest-first, so older replies are beyond the cap.

### Proven Learnings (what survives a sample-size objection)

- None. The analysis is reply-centric with matched scheduled emails, but the denominator (total sent per step) is unavailable without walking millions of scheduled-email pages.

---

*No unsanitised prospect PII in this report. Email addresses, company names, and reply texts are SHA-256 hashed.*
