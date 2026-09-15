# Threading evidence — 2026-09-15

TASK-105. What is known about same-thread follow-ups vs new threads, what is
a bet, and the experiment that would convert the second into the first.

Read `docs/BISON-THREAD-FINDINGS-2026-09-15.md` for the full TASK-080
measurement. This document is the distillation and the experiment design.

---

## 1. The no-control-group claim: CONFIRMED

### Method

Walked every EmailBison campaign's sequence step definitions. Read
`thread_reply` from each parent step (variants excluded). Cross-referenced
against `emails_sent` (PROVIDER FACT on the campaign row, never
`meta.total`).

### What the estate looks like

| Campaign | Steps | thread_reply pattern | emails_sent |
|----------|-------|----------------------|-------------|
| 352 | 5 | F,T,F,T,F | 92,806 |
| 274 | 8 | F,T,F,T,F,F,F,F | 28,331 |
| 327 | 8 | F,T,F,F,F,F,F,F | 44,976 |
| 328 | 8 | F,T,F,F,F,F,F,F | 33,695 |
| 329 | 8 | F,T,F,F,F,F,F,F | 4,300 |
| 330 | 8 | F,T,F,F,F,F,F,F | 4,028 |
| 331 | 8 | F,T,F,F,F,F,F,F | 10,299 |
| 334 | 8 | F,T,F,F,F,F,F,F | 7,269 |
| 335 | 8 | F,T,F,F,F,F,F,F | 9,759 |
| 265 | — | (archived, no steps read) | 1,609 |
| **481** | **5** | **F,F,F,F,F** | **0** |

**PROVIDER FACT.** Ten campaigns with sends. Every single one uses
`thread_reply=True` at step 2. Campaign 481 is the only campaign with
`thread_reply=False` at step 2 and has zero sends (paused).

### Per-position breakdown

| Position | Campaigns with thread_reply=True | Campaigns with thread_reply=False AND sends>0 |
|----------|----------------------------------|-----------------------------------------------|
| Step 1 | 0 | 10 (all) |
| Step 2 | 9 (352, 274, 327-335) | **0** (481 has False but 0 sends) |
| Step 3 | 0 | 10 (all) |
| Step 4 | 2 (352, 274) | 8 (327-335) |
| Step 5+ | 0 | 10 (all) |

**No position has both thread_reply=True and thread_reply=False across
campaigns that actually sent.** The comparison that would settle the
question does not exist in the data.

### Campaigns with thread_reply=False at ANY step and sends>0

Zero. The only campaign with `thread_reply=False` at step 2 (481) has never
sent. At step 4, eight campaigns use False — but the two that use True
(352, 274) are the estate's largest and structurally different (5-step and
alternating vs 8-step). There is no pair of campaigns that differ only in
thread_reply at the same position.

**VERDICT: The no-control-group claim is CONFIRMED. The alternating
structure is a bet, not a finding.**

---

## 2. The 857/571 numbers: re-derived with survivorship caveat

### Source

From the reply-centric fetch in TASK-080. For every human reply in the
collected reply feed (2,250 rows, cursor-paginated, 2026-06-05 to
2026-09-14), the referenced scheduled email was fetched directly via
`GET /scheduled-emails/{id}` — 460 API calls, 0 errors. Body text was
extracted, HTML tags stripped, and length measured in characters.

### The numbers (campaign 352 only, reply-centric)

| thread_reply | n (emails that got replies) | Avg body length (chars) |
|-------------|-----------------------------|------------------------|
| TRUE (same-thread) | 153 | 857 |
| False (new thread) | 307 | 571 |

**PROVIDER FACT.** These are the body lengths of emails that the provider
associated with a human reply. The field values are real.

### THE SURVIVORSHIP CAVEAT — READ THIS BEFORE QUOTING THESE NUMBERS

**These numbers measure the length of emails that GOT REPLIES, not the
length of all emails that were sent.**

This is a critical distinction:

1. **The denominator is wrong for a policy claim.** The 857-char average
   does not say "same-thread follow-ups that are 857 chars get more
   replies." It says "among same-thread follow-ups that already got a
   reply, the average length was 857." The emails that were 400 chars and
   got no reply are absent from this number. The emails that were 1,200
   chars and also got no reply are absent too.

2. **The direction of causality is unknown.** It is possible that:
   - Longer same-thread follow-ups cause more replies (the surface
     reading), OR
   - The provider's same-thread template happens to produce longer copy,
     and length is incidental, OR
   - Something about the prospect or the conversation state causes both
     the reply and the longer body (e.g., more engaged prospects get more
     detailed follow-ups), OR
   - Short same-thread follow-ups were sent in equal numbers but did not
     get replies, and the systematic sample (6,373 rows) is too small per
     cell to reveal this.

3. **The comparison is between different step types, not matched pairs.**
   The 153 same-thread emails are from steps 2 and 4 (follow-up
   positions). The 307 new-thread emails are from steps 1, 3, and 5
   (opener and later positions). These are different messages with
   different purposes. A same-thread follow-up is structurally a "Re:"
   reply to a previous email; a new-thread step 1 is a cold opener. They
   are not comparable as if they were the same message sent two ways.

4. **n=153 and n=307 are from a single campaign** (352) and a single
   reply feed sample (2,250 of ~270K rows, 0.8%). The numbers are
   provider facts about that sample. They are not estate-wide properties.

### What these numbers MAY NOT be quoted as

- ~~"Same-thread follow-ups should be 857 characters"~~
- ~~"Same-thread follow-ups are longer and that's why they work"~~
- ~~"New-thread emails should be 571 characters"~~
- ~~"Longer emails get more replies"~~

### What these numbers ARE

An observation about the body length of emails that earned replies in one
campaign's reply-centric sample. They say nothing about what length causes
replies, and they cannot be used to set a length policy in either
direction.

---

## 3. The experiment that would settle it

### The question

Does `thread_reply=True` at step 2 cause a different reply rate than
`thread_reply=False` at step 2, holding everything else constant?

### Design

**Two arms, one campaign, one variable.**

| | Arm A (control) | Arm B (treatment) |
|---|---|---|
| Step 1 | New thread (F) | New thread (F) |
| **Step 2** | **New thread (F)** | **Same-thread (T)** |
| Step 3 | New thread (F) | New thread (F) |
| Step 4 | New thread (F) | New thread (F) |
| Step 5 | New thread (F) | New thread (F) |
| Copy | Identical | Identical |
| Sender(s) | Identical | Identical |
| Wait days | Identical | Identical |
| Audience | Random split, same cohort | Random split, same cohort |

The ONLY difference is `thread_reply` at step 2. Arm A sends step 2 as a
new cold email. Arm B sends step 2 as a same-thread follow-up (with
automatic "Re:" prefix from the provider).

### Why step 2

Step 2 is where the estate already clusters: 9 of 10 campaigns with sends
use `thread_reply=True` there. It is the position where the bet is
largest and the evidence is thinnest. If there is a threading effect,
step 2 is where it would matter most — the first follow-up, reaching
every lead who did not reply to step 1.

### Why not test multiple positions

Testing step 2 AND step 4 (the alternating pattern) would confound the
two: a difference in replies could come from either position or from
their interaction. One position, one test.

### Assignment

Leads are randomly assigned to Arm A or Arm B at staging time. Assignment
is hashed (campaign, lead_id) so it is deterministic and reproducible — a
lead cannot land in different arms on re-read. 50/50 split.

### Primary outcome

Reply rate at step 2: (human replies attributed to step 2) / (emails sent
at step 2). ATTRIBUTION HYPOTHESIS — the provider's reply-to-scheduled-email
association, not a causal claim.

### Secondary outcomes

- Reply rate at steps 3-5 (does threading at step 2 affect later steps?)
- Overall reply rate across all steps
- "Interested" share of replies (10 of 460 in the existing sample were
  classified as interested — precision 0.44 on the old pattern set, so
  this is a weak signal and must be stated with its n)

### Sample size calculation

**Baseline assumption:** Step-2 reply rate is approximately 0.3-0.5% per
email sent. Campaign 352 had 92 step-2 replies from ~21,000 step-2 sends
(estimated from 21,215 leads, most of whom reached step 2) = ~0.44%.

Using a two-sided two-proportion z-test (alpha=0.05, power=0.80):

| Effect size (relative lift) | Arm A rate | Arm B rate | Leads per arm | Sends per arm (5 steps) | Total leads | Total sends |
|-----------------------------|-----------|-----------|---------------|------------------------|-------------|-------------|
| 50% lift | 0.004 | 0.006 | ~19,500 | ~97,500 | ~39,000 | ~195,000 |
| 75% lift | 0.004 | 0.007 | ~9,500 | ~47,500 | ~19,000 | ~95,000 |
| 100% lift (doubling) | 0.004 | 0.008 | ~5,800 | ~29,000 | ~11,600 | ~58,000 |
| 200% lift (tripling) | 0.004 | 0.012 | ~2,200 | ~11,000 | ~4,400 | ~22,000 |

**Context:** The estate's largest campaign (352) had 21,215 leads and sent
92,806 emails. A 100% lift test (doubling) would require a campaign
roughly half that size. A 50% lift test — the smallest effect that would
be operationally meaningful — would require roughly twice the largest
campaign ever run.

### What this would cost

At the estate's observed scale:

- **100% lift test:** ~11,600 leads, ~58,000 sends. At ~50 leads per
  cohort (production scale policy), this is ~232 cohorts' worth of leads.
  The estate currently holds ~300 qualified records. This is not feasible
  from existing inventory alone.
- **200% lift test:** ~4,400 leads, ~22,000 sends. Still larger than any
  single campaign run to date. Would require multiple cohorts batched
  into one experiment.

**The honest answer is that this experiment is expensive relative to the
estate's current inventory.** A 200% lift (tripling the step-2 reply rate)
is the smallest effect detectable with the available lead pool (~300
records, growing). Anything smaller requires either accumulating leads
over multiple months or accepting lower power.

### Minimum viable version

If the full experiment is not feasible, a reduced version:

1. **Use campaign 481 as Arm A** (already configured, all `thread_reply=False`,
   23 leads staged). Activate it.
2. **Create campaign X as Arm B** — identical copy, same senders, same
   audience, but `thread_reply=True` at step 2 only (F,T,F,F,F).
3. **Stage the same leads** (or a random half) into each.
4. **Wait 30 days** for replies to accumulate.
5. **Compare step-2 reply rates.** With ~23 leads per arm and ~0.4%
   baseline, expect ~0 replies in both arms. This is why the sample size
   calculation above shows thousands, not dozens.

**A 23-lead-per-arm test has essentially zero power.** It can detect only
an effect so large that it would be obvious without a test (e.g., every
single Arm B lead replies and no Arm A lead does). It is worth running
only if the cost of running it is near zero and the question is "can we
observe ANY signal" rather than "can we measure an effect size."

### What would constitute evidence

After the experiment runs:

- **n < 30 replies total:** Insufficient data. The experiment was
  underpowered. Do not declare a winner.
- **30+ replies, one arm's Wilson lower bound clears the other's upper
  bound:** Evidence of a difference. State the effect size and the
  confidence interval.
- **30+ replies, overlapping intervals:** No clear winner. The threading
  effect, if any, is smaller than the test could detect.

This matches the evaluator discipline in `COPY-EXPERIMENTS.md`: Wilson
intervals, 30-exposure floor, no winner declared from overlapping bounds.

---

## 4. What is known, what is bet, and what is not measurable

### KNOWN (PROVIDER FACT)

- `thread_reply` is a real field on sequence steps and scheduled emails.
  The provider honours it: same-thread emails carry "Re:" in the subject,
  new-thread emails do not.
- 9 of 10 campaigns with sends use `thread_reply=True` at step 2.
- 1 campaign (481) uses `thread_reply=False` everywhere and has zero sends.
- Same-thread follow-ups that got replies averaged 857 chars; new-thread
  emails that got replies averaged 571 chars. **Survivorship caveat
  applies — see §2.**

### BET (RESONATE RECONSTRUCTION, not evidence)

- The alternating F,T,F,T,F pattern is a good default. It is a design
  choice made before the data existed. It may be right, but the estate
  cannot prove it.
- Same-thread follow-ups perform at least as well as new threads. This is
  the working assumption behind the step-2-only pattern (8 of 10
  campaigns). It is plausible but untested.

### NOT MEASURABLE (from existing data)

- Whether `thread_reply` CAUSES more replies at the same position. No
  controlled comparison exists.
- Whether the 857/571 length difference reflects a causal property of
  length or a selection artefact. The survivorship bias makes the
  comparison uninterpretable as a length policy.
- Whether the alternating pattern (F,T,F,T,F) outperforms step-2-only
  (F,T,F,F,F,F,F,F). Both exist in the estate but are confounded with
  campaign identity, length, audience, copy, and sender.
- Open rates. `open_tracking` is False estate-wide. Zero opens is an
  absent measurement, not a zero.

---

## 5. PROVEN LEARNINGS

Empty. Nothing in this document survives a sample-size objection as a
causal claim. The 857/571 difference is a PROVIDER FACT about emails that
got replies; it is not a learning about what causes replies.

---

## 6. OBSERVATIONS (with n)

1. The estate clusters on `thread_reply=True` at step 2 (9 of 10
   campaigns with sends). n=10 campaigns.
2. Same-thread follow-ups that got replies were longer (857 vs 571 chars,
   n=153 and n=307 respectively, campaign 352 reply-centric sample).
   Survivorship caveat applies.
3. Campaign 352's same-thread steps (2,4) accounted for 42.4% of replies
   from 40% of step-types — a 1.10x ratio at n=316 total attributed
   replies. Not statistically significant.

---

## 7. HYPOTHESES (not tested)

1. Same-thread follow-ups at step 2 increase reply rate by making the
   email appear as a reply in the prospect's inbox, reducing the
   perception of cold outreach.
2. The "Re:" prefix (automatic provider behaviour) is the mechanism, not
   the threading itself.
3. The length difference (857 vs 571) reflects the copy generator's
   behaviour on follow-up steps rather than a deliberate choice, and
   length is incidental to the threading question.

---

*TASK-105. Reads only. No provider writes. No campaign mutations.*
*Source data: `docs/BISON-THREAD-FINDINGS-2026-09-15.md` (TASK-080),*
*`docs/BISON-CADENCE-FINDINGS-2026-09-14.md`, campaign step definitions*
*from the provider.*
