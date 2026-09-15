# Subject Line Analysis — 2026-09-15

TASK-104. Read-only analysis of subject line shape vs reply outcome.

## Statement Kinds

    PROVIDER FACT              the API returned this field with this value
    RESONATE RECONSTRUCTION    we derived it from provider data
    CLASSIFICATION             a rule-based label, not a provider field

## What Was Sampled

**Queue snapshot stamp:** 2026-09-14T21:52:15Z  from master 0ac5e60  300 records

### Campaigns

| Campaign | Status | emails_sent | Pages read | Sent rows collected | Total scheduled (reported) |
|----------|--------|-------------|------------|--------------------|---------------------------|
| 352 | HeyReach Connection Campaign | 92,833 | 20 | 52 | 95,487 |
| 327 | FIXED - MARKETING AGENCY - USA | 44,976 | 20 | 275 | 46,476 |
| 328 | FIXED -  MARKETING AGENCY - eu | 33,897 | 25 | 50 | 39,228 |
| 274 | FIXED - PRODUCTIVE - MARKETING | 28,331 | 20 | 60 | 30,411 |
| 331 | FIXED - MARKETING AGENCY - eu  | 10,299 | 10 | 150 | 10,879 |
| 335 | FIXED - MARKETING AGENCY ZVONI | 9,759 | 10 | 150 | 10,173 |
| 334 | FIXED - MARKETING AGENCY - AUS | 7,269 | 10 | 150 | 7,933 |
| 329 | FIXED - MARKETING AGENCY - eu  | 4,300 | 5 | 75 | 4,547 |
| 330 | FIXED - MARKETING AGENCY - eu  | 4,028 | 5 | 75 | 4,330 |
| **TOTAL** | | | | **1,037** | |

**PROVIDER FACT.** `per_page` is IGNORED by this API — 15 rows per request regardless. Offset pagination is refused past ~500 pages. For campaigns with >500 pages, we sampled within the first 50 accessible pages.

**PROVIDER FACT.** Only rows WHERE `sent_at` IS PRESENT are counted as sent. `meta.total` includes unsent scheduled rows.

**PROVIDER FACT.** `open_tracking` is FALSE on every campaign. No open-rate claim appears anywhere in this report.

### Reply Feed

- **Pages walked:** 80
- **Inbound replies collected:** 332
- **Unique scheduled_email_ids with replies:** 309

---

### Subject Examples by Shape (from sample)

**statement:**
- `me again, [first name]`
- `trying email this time`
- `following up from LinkedIn`
- `last note from me`
- `leaving the door open`

**question:**
- `should I be talking to someone else?`
- `what the spreadsheet workaround is actually costing [company]`
- `quick question before I stop reaching out`
- `how does [company] manage project capacity?`

**reply_prefix:**
- `Re: finding out after the project closes`
- `Re: the too-late problem`
- `Re: how [company] tracks margin today`

**Merge-field rendering issues:** 37 of 1037 subjects show signs of unresolved or empty merge fields (e.g., leading spaces, orphaned possessives).

- `Re: how [blank] tracks margin today`
- ` the project [blank] thought was fine`

---

## 1. Reply Rate by Subject Shape

### Classification Rules

- **reply_prefix**: starts with `Re:`, `RE:`, `Fwd:`, `FWD:`, `Fw:`
- **question**: ends with `?` OR starts with a question word (who/what/when/where/why/how/which/shall/should/would/could/can/is/are/do/does/did/will/may/might)
- **statement**: everything else with text
- **empty**: no subject or whitespace only — **excluded from analysis**

### Shape Distribution of SENT Emails (sampled)

| Shape | n (sent) | n (replied, provider counter) | Reply rate (provider) | n (in reply feed) | Reply rate (feed) |
|-------|----------|-------------------------------|----------------------|-------------------|------------------|
| statement | 838 | 2 | 0.24% | 4 | 0.48% |
| question | 142 | 0 | 0.00% | 0 | 0.00% |
| reply_prefix | 57 | 0 | 0.00% | 0 | 0.00% |

**Total sent rows with a subject:** 1,037

### Two Numerators, Stated Separately

**Provider counter** (`replies` field on the scheduled email row): PROVIDER FACT. This is the provider's own count of replies to this email.

**Reply feed** (cross-referenced by `scheduled_email_id`): RESONATE RECONSTRUCTION. The reply feed was cursor-paginated and covers a subset of the estate (332 replies across 80 pages). A sent row not found in the reply feed may have a reply that was not reached by the pagination, not that no reply exists.

---

## 2. Reply-Prefix (`Re:`) and Threading

- **Sent rows with `Re:` prefix:** 57
- **Of those, with `thread_reply=True`:** 57 (100.0%)
- **Of those, with replies > 0 (provider counter):** 0

**OBSERVATION.** `Re:` prefix subjects are a small share of sent emails. Where present, the high `thread_reply` rate suggests these are same-thread follow-ups in a multi-step cadence, not an independent subject choice.

**HYPOTHESIS.** A `Re:` prefix is a proxy for threading rather than an independent subject shape. Treating it as a separate shape double-counts the effect of cadence position. A same-thread follow-up may carry the original subject OR a `Re:` prefix depending on the provider's `thread_reply` setting on the step.

---

## 3. Subject Length vs Outcome

### Length Distribution (all sent rows with a subject)

- **Mean length:** 29.8 chars
- **Median length:** 26 chars
- **Min:** 13, **Max:** 115

### Reply Rate by Length Bucket

| Length (chars) | n (sent) | n (replied, provider) | Reply rate (provider) | n (in reply feed) | Reply rate (feed) |
|----------------|----------|----------------------|----------------------|-------------------|------------------|
| 1-20 | 148 | 0 | 0.00% | 1 | 0.68% |
| 21-30 | 476 | 2 | 0.42% | 0 | 0.00% |
| 31-40 | 253 | 0 | 0.00% | 3 | 1.19% |
| 41-50 | 105 | 0 | 0.00% | 0 | 0.00% |
| 51-60 | 32 | 0 | 0.00% | 0 | 0.00% |
| 61+ | 23 | 0 | 0.00% | 0 | 0.00% |

**Mean length of emails that got replies (provider counter):** 24.5 chars (n=2)
**Mean length of emails that did not:** 29.8 chars (n=1035)

---

## 4. Generated vs Sent Subject Shapes

### What was GENERATED (queue snapshot)

| Shape | n (generated) | Share |
|-------|--------------|-------|
| statement | 138 | 58.0% |
| question | 100 | 42.0% |

### What was SENT (provider sample)

| Shape | n (sent) | Share |
|-------|----------|-------|
| statement | 838 | 80.8% |
| question | 142 | 13.7% |
| reply_prefix | 57 | 5.5% |

---

## OBSERVATIONS

1. **Shape distribution of sent emails** (n=1,037): statement 80.8%, question 13.7%, reply_prefix 5.5%.

2. **Reply rates by shape** (provider counter numerator):
   - statement: 2/838 = 0.24% (n=838)
   - question: 0/142 = 0.00% (n=142)
   - reply_prefix: 0/57 = 0.00% (n=57)

3. **Re: prefix and threading**: 57 sent rows carry a `Re:` prefix. Of those, 57 (100.0%) have `thread_reply=True`. This is consistent with `Re:` being a threading mechanism rather than an independent subject choice.

4. **Subject length**: mean of replied = 24.5 chars (n=2), mean of not replied = 29.8 chars (n=1035).

---

## HYPOTHESES

1. **`Re:` is threading, not a shape.** The high `thread_reply` rate among `Re:` subjects suggests they are follow-ups in an existing thread, not an independent subject strategy. Treating them as a separate shape conflates cadence position with subject choice.

2. **Sample size is the dominant uncertainty.** The sampled sent rows (1,037) are a small fraction of the estate's 236,008 total sends. Reply counts on individual rows are sparse (most are 0), so shape-level reply rates have wide confidence intervals.

3. **Subject length may not be independent of shape.** Longer subjects tend to be statements; shorter ones tend to be questions. Any length-outcome correlation may be a shape-outcome correlation in disguise.

---

## PROVEN LEARNINGS

**Empty.** Nothing in this analysis survives a sample-size objection as a proven learning. The reply rates by shape are observations with wide confidence intervals, not actionable findings. The estate has 1,037 sampled sent rows across 9 campaigns, but the reply counts per shape are too sparse to distinguish signal from noise. A difference with n<30 is an observation, never a learning.

The one structural finding — that `Re:` prefix is a threading mechanism rather than an independent subject choice — is supported by the provider's own `thread_reply` field and is stated as an observation, not a learning, because the sample of `Re:` subjects is small.

---

## Data Quality Notes

- **No open-rate claim.** `open_tracking` is FALSE estate-wide. Zero opens is an absent measurement, not a zero.
- **Two reply numerators.** The provider's `replies` counter on the scheduled email row and the reply feed cross-reference are different measurements. The feed is a sample; the counter is per-row but unverified against individual reply rows.
- **Empty subjects excluded.** Rows with no subject are not counted as short subjects. They are unmeasurable.
- **PII redacted.** No emails, names, or company domains in this report.
