# EmailBison Estate Outcomes - 2026-09-15 (corrected)

TASK-059. Which email produced which reply, across the historical EmailBison estate.

**This is the corrected version.** The original report had four self-contradictions (Section 12 names each one and explains what was wrong). Every number below carries its denominator.

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

### Two populations

| Population | Count | How identified |
|-----------|-------|----------------|
| **Matched** | 934 of 9726 (9.6%) | Reply row carries `scheduled_email_id` linking to the specific sent email |
| **Historical** | 8792 of 9726 (90.4%) | No `scheduled_email_id`. Pre-date API lead creation. No linked sending email. |
| Reply rows with `campaign_id` | 144 of 9726 (1.5%) | 134 matched + 10 historical |

The historical 8792 have reply text (median 253 chars, range 0-5500) but no way to trace back to a campaign, step position, or the sending email's subject/body. They can be classified but cannot carry a rate.

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
| 328 | FIXED - MARKETING AGENCY - eu - ZVONIMIR | active | 8 | 10915 |
| 327 | FIXED - MARKETING AGENCY - USA - ZVONIMI | active | 8 | 10009 |
| 274 | FIXED - PRODUCTIVE - MARKETING AGENCY -  | archived | 35 | 10050 |
| 266 | PRODUCTIVE - MARKETING AGENCY -CANADA -  | archived | 6 | 712 |
| 265 | PRODUCTIVE - MARKETING AGENCY -UK - ZVON | archived | 6 | 1725 |
| 264 | PRODUCTIVE - MARKETING AGENCY - USA - ZV | archived | 6 | 403 |
| 263 | v2 PRODUCTIVE - MARKETING AGENCY - AUSTR | archived | 6 | 329 |
| 262 | PRODUCTIVE - MARKETING AGENCY - AUSTRALI | archived | 6 | 591 |
| 234 | Productive Marketing agencies US  | archived | 17 | 0 |
| 200 | Productive - Marketing agencies - Dusan  | archived | 22 | 0 |

## 2. Reply Rate by Step Position (matched only, n=934)

Of 934 matched replies, 528 (56.5%) resolved to a sequence step order. The remaining 406 had a `sequence_step_id` on the scheduled email that did not map to a known step order (campaign 352 has 44 steps including variants; step-order resolution gaps are expected).

| Step order | Replies | Positive |
|-----------|---------|----------|
| 1 | 157 | 3 |
| 2 | 103 | 4 |
| 3 | 49 | 0 |
| 4 | 83 | 0 |
| 5 | 29 | 1 |
| 6 | 19 | 0 |
| 7 | 65 | 1 |
| 8 | 23 | 0 |
| Unresolved step | 406 | 14 |

*Denominators (total sent per step) require walking the full scheduled-email listing. Campaign 352 alone has 95,459 scheduled emails across 6,364 pages. Reply counts are absolute; rates cannot be computed without the denominator.*

## 3. Classification Breakdown

### A. Matched replies (n=934)

Replies with a linked scheduled email. Classification runs on the reply text extracted from the reply row.

| Classification | Count | Share |
|---------------|-------|-------|
| unknown | 475 | 50.9% |
| negative | 204 | 21.8% |
| unsubscribe | 153 | 16.4% |
| positive | 23 | 2.5% |
| out_of_office | 36 | 3.9% |
| referral | 19 | 2.0% |
| not_relevant | 15 | 1.6% |
| not_now | 7 | 0.7% |
| account_do_not_contact | 2 | 0.2% |

Automated (provider flag): 87 of 934 (9.3%)
Unreadable (extraction yielded empty): 0 of 934 (0.0%)

### B. Historical replies (n=8792)

No linked sending email. Reply text is present and classifiable (median length 253 chars). These rows have no `campaign_id`, no step position, and no sending-email subject or body.

| Classification | Count | Share |
|---------------|-------|-------|
| unknown | 6344 | 72.2% |
| positive | 1547 | 17.6% |
| unsubscribe | 435 | 4.9% |
| not_now | 355 | 4.0% |
| out_of_office | 57 | 0.6% |
| negative | 35 | 0.4% |
| referral | 17 | 0.2% |
| not_relevant | 2 | 0.0% |

Automated (provider flag): 357 of 8792 (4.1%)
Unreadable (extraction yielded empty): 3 of 8792 (0.03%)

**What "unreadable" means here:** the reply text field was present but `extract_prospect_text` yielded an empty string after stripping quoted threads. 3 of 8792 historical rows hit this. This is NOT the same as the 46.5% unreadable rate measured elsewhere, which operated on a different population (scheduled-email bodies, not reply texts).

## 4. Positive Reply Rate

| Population | Positive | Total | Rate | Comparable to TASK-070? |
|-----------|----------|-------|------|------------------------|
| Matched | 23 | 934 | 2.46% | No - denominator is replies fetched, not emails sent |
| Historical | 1547 | 8792 | 17.57% | No - no sending email, no campaign, no denominator |
| Combined | 1570 | 9726 | 16.14% | No - see Section 12 |

### Positive by step (matched, n=23)

| Step | Positive |
|------|----------|
| 1 | 3 |
| 2 | 4 |
| 5 | 1 |
| 7 | 1 |
| Unresolved step | 14 |

### Historical positives: are they real?

Yes, with caveats. The 1547 historical positives have substantial reply text (min 46 chars, p10 180, median 253, p90 323, max 1327). All 1547 were classified via `extract_method: no_quote` (no quoted thread to strip). The classifier matched positive phrases with confidence 0.75. 9 of 1547 were flagged as automated by the provider.

**The caveat:** we cannot compute a reply *rate* for historical rows because we do not know how many emails were sent to produce these 8792 replies. The 17.57% is a classification share, not a reply rate. It answers "of the replies we have, what fraction are positive?" not "of the emails sent, what fraction produced a positive reply?"

## 5. Subject Shape of Sending Email (matched only, n=934)

| Subject shape | Replies to that email |
|--------------|------------------------|
| statement | 551 |
| reply-prefix | 286 |
| question | 97 |

No empty subjects in matched - all 934 have a linked sending email with a subject.

## 6. Body Length Band of Sending Email (matched only, n=934)

| Body length (chars) | Replies to that email |
|--------------------|------------------------|
| 100-299 | 10 |
| 300-599 | 149 |
| 600-999 | 406 |
| 1000+ | 369 |

No sub-100 bodies in matched - all 934 linked sending emails had substantive body text.

## 7. Time to Reply

No time-to-reply data available. The 934 matched scheduled emails all had `status: sent` but lacked `sent_at` timestamps in the cached data.

## 8. Bounce Analysis

Total bounce rows in feed: 4088

| Bounce type | Count |
|------------|-------|
| Bounced | 4088 |

Matched replies whose scheduled email bounced: 0 of 934 (all 934 matched had `se_status: sent`).

## 9. Scheduled Email Status (matched, n=934)

| Status | Count | Share |
|--------|-------|-------|
| sent | 934 | 100.0% |

All matched scheduled emails were in `sent` status. This is expected: a reply can only exist if the email was sent.

## 10. Open Tracking Caveat

**ALL 22 campaigns have `open_tracking: False` or not set.** Open counts are an absent measurement, not an absent open. Any open-based rate is invalid.

## 11. Observations, Hypotheses, and Proven Learnings

### Observations (what the rows say, with n)

- The reply feed contains 22500 rows (1500-page sample): 9726 replies, 4088 bounces, 8686 outgoing.
- Of 9726 reply-type rows, only 934 (9.6%) carry a `scheduled_email_id` linking them to a specific sent email. The remaining 8792 (90.4%) are historical, pre-dating API lead creation.
- Matched replies (n=934): positive rate 2.46% (23/934). Negative 21.8%, unsubscribe 16.4%, unknown 50.9%.
- Historical replies (n=8792): positive classification share 17.57% (1547/8792). Unknown 72.2%. These have real reply text but no campaign attribution.
- Automated replies: 444 total (87 matched + 357 historical), 4.6% of all replies.
- The 8-step sequence reply rate of 8.49% (n=17,690) claimed by the estate CANNOT be re-derived from this data. The bounded sample could not walk the scheduled-email listings (campaign 352 alone has 95,459 emails across 6,364 pages), so denominators per step are unavailable. This is a legitimate finding: absent denominators are a real outcome, not a failure.
- The reply feed's 1500-page cap (22,500 rows) may not cover the full estate history. The feed is cursor-paginated newest-first, so older replies are beyond the cap.

### Hypotheses (what it might mean)

- The higher positive classification share among historical replies (17.57% vs 2.46% matched) may reflect survivorship bias: the historical replies that survived into the API feed may be the more interesting/engaged ones, while matched replies include all recent replies regardless of content.
- Without a denominator (emails sent to produce these replies), neither 2.46% nor 17.57% is a reply *rate*. They are classification shares among fetched replies.

### Proven Learnings (what survives a sample-size objection)

- The denominator (total sent per step) is unavailable without walking millions of scheduled-email pages. Reply counts alone do not yield rates.
- Campaign-level reply rates from TASK-070 (0.3-0.4% for campaigns 327, 328, 331, 335, 352) used `emails_sent` from the campaign API as denominator. That is the correct denominator for a reply rate. This analysis cannot reproduce it because the reply feed does not carry the sending-email population.

## 12. Corrections from the Original Report

The original report (generated at 01:26 on 2026-09-15) had four self-contradictions. This section names each one and explains what was wrong.

### Correction 1: "Matched" counted all 9726 rows

**Original:** "Matched dataset rows (reply + sched) 9726"

**What was wrong:** The report counted all 9726 reply rows as "matched" while simultaneously reporting that only 934 had a `scheduled_email_id`. The 8792 rows without a scheduled email were included in the "matched" total.

**Fix:** Matched is 934 (rows with `scheduled_email_id`). Historical is 8792 (rows without). Reported separately throughout.

### Correction 2: "Unreadable 0.0%" was misleading

**Original:** "Unreadable (extraction yielded empty) 0 of 9726 -> 0.0%" presented as comparable to a previous 46.5% measurement.

**What was wrong:** Two errors compounded. First, the 0.0% was computed across all 9726 rows, mixing matched and historical. Second, the 46.5% figure it was compared against measured something different (scheduled-email body extractability, not reply-text extractability). The reply text for historical rows IS present and extractable - the "empty body" in the original report referred to the *sending email's* body, which is absent by construction for historical rows.

**Fix:** Matched unreadable: 0/934 (0.0%). Historical unreadable: 3/8792 (0.03%). Neither is comparable to the 46.5% figure because they measure different things.

### Correction 3: 1561 of 1570 positives from "no body" rows

**Original:** "positive at step 1-8: 9, positive at '? step': 1561" - implying 1561 positives came from rows with no content.

**What was wrong:** The 1561 (now 1547 after re-classification with current taxonomy) historical positives do NOT have empty reply text. They have substantial reply text (median 253 chars). The "no body" referred to the *sending email's* body, which is absent because these rows have no `scheduled_email_id`. The reply text itself is present and was classified by the rules-based classifier matching positive phrases. The original report conflated "no linked sending email" with "no reply content."

**Fix:** Historical positives (n=1547) have real reply text. They are classified as positive by the same rules-based classifier used for matched rows. The classification is meaningful but the rate (17.57%) is a classification share, not a reply rate, because the denominator (emails sent) is unknown.

### Correction 4: 16.14% positive contradicts 0.3-0.4% from TASK-070

**Original:** "Positive replies: 1570 of 9726 (16.14%)" with no reconciliation against TASK-070's campaign-level measurements of 0.3-0.4%.

**What was wrong:** These measure different things. TASK-070 computed `replies / emails_sent` per campaign using `emails_sent` from the campaign API (a proper denominator). This analysis computed `positive_classifications / all_replies_fetched` - the denominator is replies in the feed, not emails sent. A 16% positive share among replies is not inconsistent with a 0.4% reply rate among sent emails. Example: if 100,000 emails are sent and 400 replies come back (0.4% reply rate), and 16% of those 400 replies are positive (64 positives), the positive rate among *sent emails* is 0.064% - but the positive share among *replies* is 16%.

**Fix:** The 16.14% is retracted as a comparable rate. Matched positive rate: 23/934 = 2.46% (classification share among matched replies). Historical positive share: 1547/8792 = 17.57% (classification share among historical replies). Neither is comparable to TASK-070's campaign-level reply rates because the denominators differ fundamentally.

---

*No unsanitised prospect PII in this report. Email addresses, company names, and reply texts are SHA-256 hashed.*
