# Copy Outcome Patterns — 2026-09-15

## What this is

A comparison of the email copy associated with replies that earned a
MEETING_INTENT classification against the copy associated with replies that
earned OBJECTION, UNSUBSCRIBE, or ACCOUNT_DNC. The question is whether
anything in the copy separates them.

## The trap this report avoids

This is survivorship analysis. Copy that got replies is not copy that
*caused* replies; it is copy that was sent to people who were going to
reply. Every finding below is a HYPOTHESIS, not a learning. Nothing in the
OBSERVATIONS section is evidence that changing the copy will change the
outcome. The PROVEN LEARNINGS section is empty for that reason.

## Sampling

| Metric | Value |
|--------|-------|
| Rows fetched | 4,500 |
| Pages walked | 300 |
| Per-page behaviour | EmailBison ignores `per_page`; always 15 rows |
| Pagination | Cursor (`pagination_type=cursor`) |
| Replies classified | 1,256 |
| Outgoing (skipped) | 1,105 |
| Bounces (skipped) | 2,139 |
| Campaigns in sample | 262, 265, 266, 274, 327, 328, 331, 334, 335, 352 |

The sample is the 4,500 most recent rows from the `/replies` endpoint,
cursor-paginated. The estate is larger than this — the feed did not
exhaust in 300 pages — so this is a recency-biased window, not a
cross-section of the full history.

## Classification tally (n=1,256 replies)

| Category | Count | Share |
|----------|-------|-------|
| unknown | 651 | 51.8% |
| negative | 227 | 18.1% |
| unsubscribe | 169 | 13.5% |
| positive | 87 | 6.9% |
| out_of_office | 37 | 2.9% |
| not_relevant | 33 | 2.6% |
| referral | 19 | 1.5% |
| not_now | 17 | 1.4% |
| meeting_intent | 12 | 1.0% |
| account_do_not_contact | 2 | 0.2% |
| objection | 2 | 0.2% |

The classifier is conservative by design. 51.8% unknown is the expected
shape of an outbound reply feed where most responses are ambiguous.

---

## The positive set: MEETING_INTENT (n=12)

**Classifier precision: 1.00, recall: 1.00** (measured on a 263-reply
sample; see `docs/TAXONOMY-PRECISION-2026-09-14.md`).

### The data quality problem

Of the 12 MEETING_INTENT replies, **10 have no campaign_id** and contain
text that reads as test data or spam rather than genuine prospect replies:

- "Reminder: kebab-kebab Customer service workshop this Friday"
- "Can we meet up for a drink sometime soon?"
- "I've attached the PDF of our whitepaper."

These contain meeting-intent phrases ("can we chat soon?", "looking forward
to speaking with you") but are not replies to any tracked campaign. They
predate the API integration or are non-prospect mail.

**The usable positive set is n=2.** Both are from real campaigns:

1. **Campaign 352**: A prospect proposed a specific day and time
   ("available next Wednesday, July 22 between 1:30-3:00PM EST"). 73 words.
2. **Campaign 262**: A prospect accepted a demo offer ("sure, I will take
   a demo. Send me a calendly link"). 47 words.

Nothing generalisable can be built from n=2. The observations below use
the campaign-level copy data (which campaigns the MEETING_INTENT replies
came from) rather than the reply-level data.

### Campaign copy associated with MEETING_INTENT

Campaigns: 262, 352. Sequence steps: 50. Outgoing emails in feed: 270.

| Characteristic | Sequence steps (n=50) | Outgoing emails (n=270) |
|----------------|----------------------|------------------------|
| Word count (mean) | 112 | 324 |
| Word count (median) | 85 | 265 |
| Length: short/medium/long | 8 / 31 / 11 | 0 / 12 / 258 |
| Opening: greeting | 0/50 | 174/270 (64%) |
| Opening: question | 0/50 | 37/270 (14%) |
| CTA present | 24/50 (48%) | 146/270 (54%) |
| Product named | 0/50 | 13/270 (5%) |
| Sender identified | 0/50 | 45/270 (17%) |
| Personalisation (mean depth) | 1.9 | 0.6 |
| Personalisation (any) | 50/50 (100%) | 164/270 (61%) |

The sequence steps are templates with Liquid variables. The outgoing
emails are the rendered versions. The gap between step word count (mean
112) and outgoing word count (mean 324) reflects the rendering expanding
conditional blocks into full text.

---

## The negative set: OBJECTION + UNSUBSCRIBE + ACCOUNT_DNC (n=173)

**OBJECTION precision: 1.00, recall: 0.67.** Unsubscribe and account_dnc
are rule-based with no measured precision/recall (they are pattern matches
on explicit removal language).

### Breakdown

| Category | Count |
|----------|-------|
| unsubscribe | 169 |
| objection | 2 |
| account_do_not_contact | 2 |
| **Total** | **173** |

The negative set is 97.7% unsubscribe. The two objection replies were
both from campaign 352 and cited budget/time constraints. The 169
unsubscribes came from 10 campaigns, with campaigns 327 and 328
contributing the majority.

### One reply that demands attention

Campaign 328 produced this reply:

> "Please for the love of all mighty god stop emailing me. I've received
> well over 50 emails telling me this is the last time you're checking in
> and it never is. I keep hoping it's the end but looks like your email
> sequencer is in some kind of endless fucking loop..."

This is not a copy problem. This is a sequencing problem: the campaign
appears to have continued sending "last note" emails after it should have
stopped. One person counted 50+ such emails. This is recorded as an
observation, not a finding — the reply text is the evidence, and the
campaign's sequence has 8 steps, which is not 50.

### Campaign copy associated with negative replies

Campaigns: 262, 265, 266, 274, 327, 328, 331, 334, 335, 352. Sequence
steps: 165. Outgoing emails in feed: 463.

| Characteristic | Sequence steps (n=165) | Outgoing emails (n=463) |
|----------------|----------------------|------------------------|
| Word count (mean) | 220 | 345 |
| Word count (median) | 254 | 276 |
| Length: short/medium/long | 8 / 34 / 123 | 0 / 14 / 449 |
| Opening: greeting | 0/165 | 305/463 (66%) |
| Opening: question | 0/165 | 45/463 (10%) |
| CTA present | 74/165 (45%) | 269/463 (58%) |
| Product named | 0/165 | 32/463 (7%) |
| Sender identified | 0/165 | 65/463 (14%) |
| Personalisation (mean depth) | 2.0 | 0.6 |
| Personalisation (any) | 165/165 (100%) | 292/463 (63%) |

---

## OBSERVATIONS

### 1. The positive set is too small to compare (n=2 usable)

Of 12 MEETING_INTENT replies, 10 are non-prospect mail with no campaign
association. The two genuine replies came from campaigns 262 and 352.
No statistical comparison is possible at n=2. Every observation below is
noted with this constraint.

### 2. The campaigns that earned MEETING_INTENT had shorter copy

Campaign 352's sequence steps average 67 words (rendered). Campaign 262's
average 255 words. The negative-set campaigns (327, 328, and others)
average 220-280 words per step.

Campaign 352 is the shortest campaign in the sample and is one of only two
that produced a MEETING_INTENT reply. It is also the only campaign whose
copy style is conversational rather than heavily templated.

**But:** campaign 352 also produced unsubscribe replies. Shorter copy did
not prevent negative outcomes; it may have been associated with a different
audience or sending pattern.

### 3. The heavily templated campaigns dominate the unsubscribe count

Campaigns 327 and 328 use complex Liquid templates with conditional blocks,
multiple subject-line variants, and personalisation via `{FIRST_NAME}`,
`{COMPANY}`, `{TITLE}`, and `{LOCATION}`. They average 260-280 words per
step and have 5-8 steps each.

These two campaigns account for the majority of the 169 unsubscribe
replies. The unsubscribe rate is not measurable (the sent count is not
available from the reply feed alone), but the absolute count is
disproportionate.

**But:** campaigns 327 and 328 may have had more leads, a colder audience,
or a more aggressive sending cadence. The copy is one of several variables.

### 4. Sequence step templates are not the rendered email

The sequence step `email_body` contains Liquid template code with
conditional blocks (`{% if title contains "founder" %}`), variable
substitutions (`{FIRST_NAME}`), and spin syntax (`{Hi|Hey|Hi there}`).
The rendered outgoing email is what the prospect actually received, and it
is systematically longer (mean 324-345 words) than the template (mean
112-220 words) because the conditionals expand.

Any analysis of "email length" must specify whether it means the template
or the rendered version. They are different numbers.

### 5. CTA presence does not separate the sets

Both positive and negative campaign copy has CTAs in roughly 45-58% of
emails. There is no visible difference in CTA frequency between the sets.

### 6. Product naming is rare in both sets

Product naming appears in 5-7% of outgoing emails in both sets. Neither
set distinguishes itself by naming or not naming the product.

### 7. Sender identification is low everywhere

17% in the positive set, 14% in the negative set. No separation.

### 8. Personalisation variables are present in all sequence templates

Every sequence step in every campaign uses `{FIRST_NAME}` and `{COMPANY}`
at minimum. The "personalisation depth" metric (mean 1.9-2.0) reflects
template variables, not actual personalisation research. The rendered
outgoing emails show personalisation in 61-63% of cases, suggesting the
variables sometimes resolve to empty.

### 9. The reply text itself differs predictably

| Characteristic | MEETING_INTENT replies (n=12) | Negative replies (n=173) |
|----------------|------------------------------|--------------------------|
| Word count (mean) | 35 | 58 |
| Word count (median) | 36 | 22 |
| Short (<30 words) | 11/12 (92%) | 121/173 (70%) |
| Questions (mean) | 0.8 | 0.4 |

MEETING_INTENT replies are short and sometimes contain questions ("can you
send a calendly link?"). Negative replies are also predominantly short
(70% under 30 words) but are statements, not questions. The difference is
direction (request vs refusal), not length.

**But:** the MEETING_INTENT reply set is contaminated with 10 non-prospect
emails. The 35-word mean may not represent genuine meeting-intent replies.

---

## HYPOTHESES

### H1: Shorter, conversational copy produces fewer unsubscribes than
### heavily templated copy

Campaign 352 (mean 67 words, conversational style) and campaigns 327/328
(mean 260-280 words, heavy Liquid templates) are the extremes in the
sample. Campaign 352 produced both MEETING_INTENT replies and unsubscribe
replies. Campaigns 327/328 produced mostly unsubscribes.

**What would test it:** Run two campaigns with the same audience and
cadence, one using short conversational copy and one using the current
templated style. Measure unsubscribe rate and reply rate.

**Estimated cost:** Two new campaigns, ~200 leads each, 2-4 week run.
Credits burned depend on the lead source; the copy itself is free to
produce. The measurement needs the sent count (from `scheduled_emails` or
the campaign dashboard) to compute rates, which the reply feed alone does
not provide.

### H2: The sequencing problem in campaign 328 is producing avoidable
### unsubscribes

One prospect counted 50+ "last note" emails from a campaign with 8 steps.
If the sequencer is looping or not respecting stop conditions, every
additional email is an unsubscribe risk that the copy cannot fix.

**What would test it:** Audit campaign 328's send log. Count how many
emails each lead received. Check whether the sequence completed or looped.
This is an operational investigation, not a copy experiment.

**Estimated cost:** Read-only audit of `scheduled_emails` for campaign 328.
No credits burned.

### H3: The template expansion is producing emails that are longer than
### the operator intended

The sequence step templates average 112-220 words, but the rendered
outgoing emails average 324-345 words. The Liquid conditionals are
expanding the copy by 2-3x. An operator who writes a 150-word template may
be sending a 400-word email.

**What would test it:** For each campaign, compare the template word count
to the rendered word count. If the gap is consistent, the operator has a
length problem they cannot see in the template editor.

**Estimated cost:** Read-only. Already measurable from the data in this
report.

---

## PROVEN LEARNINGS

Empty. No finding in this report survives the sample-size objection.

The positive set is n=2 usable (10 of 12 MEETING_INTENT replies are
non-prospect mail). The negative set is n=173 but 97.7% is unsubscribe,
not objection, and the unsubscribe decision is driven by sending frequency
and audience fit as much as by copy.

The hypotheses above are experiment candidates, not conclusions.

---

## Which single hypothesis would be most valuable to test

**H2: the sequencing problem.** It is the only one that is both actionable
without a controlled experiment and potentially causing active harm. If
campaign 328 (or any campaign) is sending 50+ emails to people who asked
to stop, that is a reputational risk and a waste of credits. The audit is
read-only, costs no credits, and if it finds a looping sequencer, the fix
is operational rather than creative.

After that, **H1** (short vs templated copy) is the most valuable copy
hypothesis, because it addresses the largest cluster of negative outcomes
(the 169 unsubscribes from campaigns 327/328) and the test is a standard
A/B with existing infrastructure.

---

## What the page budget was

300 pages of 15 rows = 4,500 rows from the `/replies` endpoint. Cursor
pagination. `per_page` is accepted and ignored by EmailBison — the API
always returns 15 rows regardless of the parameter value. The feed did not
exhaust in 300 pages; the estate is larger than this sample.

The sample is recency-biased (most recent 4,500 rows) and may not
represent the full history of the estate. Campaigns that sent earlier are
under-represented if their replies have been pushed out of the cursor
window.

## What was sampled

- 4,500 rows from `GET /api/replies` (cursor pagination, 300 pages)
- 1,256 actual replies classified (the rest were outgoing emails or bounces)
- Sequence steps fetched for 10 campaigns: 262, 265, 266, 274, 327, 328,
  331, 334, 335, 352
- 270 outgoing emails from MEETING_INTENT campaigns analysed
- 463 outgoing emails from negative campaigns analysed

## What this report does not say

- **No open rate.** `open_tracking` is False estate-wide. An absent
  measurement is not a zero.
- **No delivery rate.** The reply feed does not carry a sent count.
  Campaign 274 reports 30,411 scheduled rows and zero of its first 100
  pages are sent. `meta.total` is not a sent count.
- **No reply rate.** Without a sent count, a reply rate would be fabricated.
- **No INTERESTED claims.** INTERESTED has 0.44 precision on the old
  pattern set and the new set is unmeasured. Nothing in this report uses
  INTERESTED as evidence.
- **No 8.49%.** Unreproduced.
