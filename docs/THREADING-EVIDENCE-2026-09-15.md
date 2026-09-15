# THREADING EVIDENCE — 2026-09-15

TASK-105: same-thread vs new-thread, and the missing control.

What is known, what is bet, and the experiment that would convert the
second into the first.

---

## Statement Kinds

    PROVIDER FACT            the API returned this field with this value
    RESONATE RECONSTRUCTION  we derived it, and here is the derivation
    ATTRIBUTION HYPOTHESIS   we believe this reply relates to that touch

---

## 1. THE CONTROL-GROUP QUESTION: CONFIRMED OR REFUTED?

### TASK-080's claim

TASK-080 reported: "Every campaign with sends uses `thread_reply=True` at
step 2. Campaign 481 is the only one with False there and it has zero
sends." This was based on 10 campaigns with step data.

### TASK-105 independent verification

**The claim is PARTIALLY REFUTED.** The estate has 22 campaigns. Walking
all 22 via `GET /campaigns` and `GET /campaigns/{id}/sequence-steps`:

    22 campaigns total
    20 have sequence step data accessible
     2 (423, 424) return no step data

**Campaigns with `thread_reply=False` at ANY step: 20**
**Campaigns with `thread_reply=False` at step 2 AND sends > 0: 5**

The five control campaigns are:

| Campaign | Steps | thread_reply pattern | emails_sent | Status   |
|----------|-------|---------------------|-------------|----------|
| 262      | 6     | F,F,F,F,F,F         | 525         | archived |
| 263      | 6     | F,F,F,F,F,F         | 299         | archived |
| 264      | 6     | F,F,F,F,F,F         | 415         | archived |
| 265      | 6     | F,F,F,F,F,F         | 1,609       | archived |
| 266      | 6     | F,F,F,F,F,F         | 315         | archived |

**PROVIDER FACT.** These five campaigns use `thread_reply=False` on every
step, including step 2. Combined sends: 3,163. All are archived. They are
the estate's earliest campaigns (predecessors to the 327-335 series).

### Why TASK-080 missed them

TASK-080's step-level table listed 10 campaigns (274, 327-335, 352, 481).
The five archived 6-step campaigns (262-266) were omitted from that table.
They appear in the sequence-length section as a group ("5 (262-266),
2,763 sends") but their thread_reply pattern was not individually
reported. The conclusion "every campaign with sends uses thread_reply=True
at step 2" was drawn from the 10 campaigns that were step-inspected, not
from all 22.

### The control group exists, but it is weak

A control group exists at step 2:

| Group       | Campaigns       | thread_reply at step 2 | Total sends |
|-------------|-----------------|------------------------|-------------|
| CONTROL     | 262-266         | False                  | 3,163       |
| TREATMENT   | 274,327-335,352 | True                   | 235,651     |

**But the comparison is heavily confounded:**

1. **Different structure.** Control campaigns have 6 steps; treatment
   campaigns have 5 or 8. The step-2 position in a 6-step sequence is
   not the same as step 2 in an 8-step sequence — the surrounding
   context differs.
2. **Different era.** Control campaigns are archived (likely Q1-Q2 2026).
   Treatment campaigns are active or recently completed. Copy, audience,
   sender, and language all differ.
3. **Different scale.** 3,163 control sends vs 235,651 treatment sends —
   a 75:1 imbalance.
4. **Different language/audience.** The 262-266 campaigns were the
   original "productive marketing agency" series in various geos
   (Australia, UK, USA, Canada). The treatment campaigns include the
   operator's own (352) and fixed marketing agency campaigns in multiple
   languages.

**The control group EXISTS but no clean comparison is possible from
observational data alone.** The confounds are structural, not incidental.

### Position-level analysis

At each step position, does any position have BOTH thread_reply=True and
thread_reply=False across campaigns with sends?

| Position | True (with sends) | False (with sends) | Control? |
|----------|-------------------|--------------------|----------|
| 1        | 0                 | 15                 | No       |
| 2        | 9                 | 5                  | YES      |
| 3        | 0                 | 14                 | No       |
| 4        | 2                 | 12                 | YES      |
| 5        | 0                 | 14                 | No       |
| 6        | 0                 | 13                 | No       |
| 7        | 0                 | 8                  | No       |
| 8        | 0                 | 8                  | No       |

**PROVIDER FACT.** Positions 2 and 4 have both True and False campaigns
with sends. But:
- Position 2: 9 True (195K+ sends) vs 5 False (3.1K sends) — 62:1 imbalance
- Position 4: 2 True (352 + 274 = 121K sends) vs 12 False (118K sends) —
  more balanced, but the 2 True campaigns (352, 274) are the alternating
  pattern campaigns, and the 12 False include both 6-step and 8-step
  campaigns

**No position has a clean, balanced control.** Position 4 is the closest
to balanced in volume, but the True campaigns (352, 274) differ
structurally from the False ones.

---

## 2. THE 857/571 NUMBERS: RE-DERIVED WITH CAVEAT

### Source

These numbers come from TASK-080's reply-centric fetch
(`scripts/bison_thread_reply_centric.py`). For every human reply in the
collected reply feed (2,250 rows, cursor-paginated), the referenced
scheduled email was fetched via `GET /scheduled-emails/{id}` (460 API
calls, 0 errors). Body text was extracted by stripping HTML tags and
collapsing whitespace.

### The numbers

| thread_reply       | n   | Avg body length (chars, stripped HTML) |
|--------------------|-----|----------------------------------------|
| TRUE (same-thread) | 153 | 857                                    |
| False (new thread) | 307 | 571                                    |

**PROVIDER FACT.** The body lengths are measured on the actual rendered
emails the provider associated with replies. The HTML stripping and
character counting methodology is reproducible from the script.

### The survivorship caveat — READ THIS BEFORE QUOTING

**These are body lengths of emails that GOT REPLIES, not all sent emails.**

The 153 same-thread emails and 307 new-thread emails are the ones that
a human replied to. We do NOT know the average body length of all
same-thread emails sent (including those that got no reply). It is
possible that:

- Short same-thread follow-ups were sent but did not get replies
- The average body length of ALL same-thread emails is 400 chars, and
  the 857 reflects only the long ones that earned replies
- Length causes replies, or length is a consequence of what the model
  writes when continuing a thread, or length is irrelevant and the
  difference is an artifact of which emails happen to get replies

**The 857/571 comparison is survivorship-biased.** It tells us what the
replied-to emails looked like, not what all emails looked like, and not
whether length causes replies. Quoting these numbers without the caveat
is quoting a selection effect as a finding.

### What the code says about follow-up length

`src/cadencelibrary.py` lines 262-270: the `FOLLOWUP_ADDENDUM` instructs
the model to "add one thought" and "not repeat what the earlier email
said." A prior instruction to "be short" was deliberately removed after
TASK-080 measured these numbers — the follow-ups that earned replies
were longer, not shorter, so the instruction was contradicted by the
data. The current addendum carries no length instruction in either
direction.

---

## 3. WHAT IS KNOWN (PROVIDER FACT)

1. **22 campaigns in the estate.** 20 have accessible step data. 15 have
   sends > 0. Total sends: ~238,800.

2. **Three thread_reply patterns in use:**
   - Alternating F,T,F,T,F (campaigns 352, 274) — 121K sends
   - Step-2-only F,T,F,F,F,F,F,F (campaigns 327-335) — 114K sends
   - All-new-thread F,F,F,F,F,F (campaigns 262-266) — 3.2K sends
   - All-new-thread F,F,F,F,F (campaign 481) — 0 sends (paused)

3. **A control group exists at step 2** (campaigns 262-266, 3,163 sends,
   all archived). It is too small and too confounded for a clean
   comparison.

4. **Same-thread follow-ups always carry "Re:" in the subject.** This is
   automatic provider behaviour, not a template choice.

5. **`open_tracking` is False estate-wide.** No open-rate claim is
   possible. Zero opens is an absent measurement, not a zero.

6. **57% of attributed replies come by step 2, 82% by step 4.**
   (TASK-080, n=460 attributed replies, ATTRIBUTION HYPOTHESIS)

---

## 4. WHAT IS BET (HYPOTHESIS, NOT EVIDENCE)

1. **The alternating F,T,F,T,F structure is a design choice.** No
   controlled comparison proves it outperforms step-2-only or
   all-new-thread. The 1.10x per-step-type ratio from campaign 352
   (42.4% of replies from 40% of step-types) is not statistically
   significant at n=316.

2. **Same-thread follow-ups may or may not cause more replies.** The
   observational data points slightly in favour (1.10x) but the
   confounds are structural. The control group exists but is too weak
   to settle the question.

3. **The 857 vs 571 character difference is survivorship-biased.** It
   describes replied-to emails, not all emails. It does not prove that
   length causes replies or that same-thread follow-ups should be long.

---

## 5. EXPERIMENT DESIGN

### The question

Does `thread_reply=True` at step 2 cause a different reply rate than
`thread_reply=False` at step 2, holding everything else constant?

### Design: within-campaign A/B at step 2

**Arms:**
- Arm A (treatment): step 2 with `thread_reply=True` (same-thread follow-up)
- Arm B (control): step 2 with `thread_reply=False` (new thread)

**Everything else held constant:** same copy template, same sender, same
audience pool, same timing, same campaign.

**Implementation:** The estate already has a variant system. Each parent
step can have variant steps with different copy. The experiment adds a
**thread_reply variant** at step 2: two variants of the same parent step,
identical except for `thread_reply`. Leads are randomly assigned to one
variant or the other.

If the variant system does not support thread_reply divergence on the
same parent step (it currently carries thread_reply per step, not per
variant), the alternative is:

**Split-campaign design:** Create two identical campaigns on the same
audience pool. Campaign X uses the F,T,F,F,F pattern; campaign Y uses
F,F,F,F,F. Everything else — copy, sender, timing, audience — is
identical. The only difference is thread_reply at step 2.

### Sample size

**Effect size to detect:** The observational data suggests a 1.10x ratio
(same-thread slightly better). A practical effect size to power for is
a 20% relative improvement in step-2 reply rate (e.g., from 0.5% to
0.6% absolute).

**Baseline reply rate:** Step-2 reply rates in the estate range from
0% to 29.1% of total campaign replies (TASK-080). The absolute step-2
reply rate (replies / step-2 sends) is not directly measured but can be
estimated: campaign 352 has 92,833 total sends across 5 steps (~18.5K
per step if uniform) and 316 attributed replies, of which 92 are at
step 2. If step 2 has ~18.5K sends and 92 replies, the step-2 reply
rate is ~0.5%.

**Power calculation (two-proportion z-test):**
- p1 (control) = 0.005 (0.5% reply rate)
- p2 (treatment) = 0.006 (0.6%, a 20% relative improvement)
- alpha = 0.05, power = 0.80
- n per arm ≈ 267,000 sends

**This is impractically large.** At 0.5% baseline, detecting a 20%
relative improvement requires ~267K sends per arm. The entire estate
has ~238K sends.

**Alternative: detect a larger effect.**
- p1 = 0.005, p2 = 0.010 (100% relative improvement, doubling)
- n per arm ≈ 6,600 sends

**A 100% relative improvement (doubling the reply rate) would require
~6,600 sends per arm, or ~13,200 total step-2 sends.** At ~4,000 leads
per campaign (the size of campaign 352's current lead pool), this is
achievable in a single campaign run.

### What cohort

Campaign 481 (paused, 0 sends, 23 leads) is too small. The experiment
should run on:

1. **A new campaign** with ~7,000+ leads from the same ICP pool used by
   campaign 352 (same geo, same company size, same industry).
2. **5-step cadence** (matching the production target).
3. **Leads split 50/50** at random into arm A (thread_reply=True at
   step 2) and arm B (thread_reply=False at step 2).
4. **All other steps identical** — same copy, same sender, same timing.

### Cost in sends

- 7,000 leads × 5 steps = 35,000 total sends (if all leads complete)
- Step-2 sends: ~7,000 per arm = ~14,000 total step-2 sends
- At the estate's cost per send, this is a measurable but not trivial
  investment
- Attrition will reduce actual step-2 sends (not all leads reach step 2)

### What to measure

1. **Primary:** Step-2 reply rate (replies / step-2 sends) per arm
2. **Secondary:** Total reply rate across all steps per arm
3. **Tertiary:** Reply quality (interested/positive classification)
4. **Exploratory:** Whether the thread_reply effect differs by lead
   characteristics (geo, company size, industry)

### Duration

At campaign 352's send rate (~92K sends over ~3 months = ~1K/day), a
7,000-lead campaign would take ~7 days to send step 1 and ~3-4 weeks to
complete all 5 steps. Reply collection should continue for 2 weeks after
the last step-2 send to capture delayed replies.

### What would settle it

- If arm A (same-thread) replies at ≥0.8% vs arm B (new-thread) at
  ≤0.4%: same-thread wins at step 2. Adopt F,T,F,F,F estate-wide.
- If arm A and arm B reply at the same rate (±0.1%): thread_reply does
  not matter at step 2. Simplify to all-new-thread.
- If arm B (new-thread) replies higher: same-thread HURTS at step 2.
  Switch to all-new-thread immediately.

---

## 6. RECOMMENDED NEXT STEPS

1. **Do not quote the 857/571 numbers without the survivorship caveat.**
   They describe replied-to emails, not all emails.

2. **Do not present the alternating structure as evidence-backed.** It
   is a design choice. The 1.10x ratio is not significant.

3. **Run the experiment.** The control group exists but is too weak for
   observational inference. A within-campaign A/B test at step 2 with
   ~7,000 leads per arm would settle the question for ~14,000 step-2
   sends.

4. **The step-2-only pattern (F,T,F,F,F,F,F,F) is the majority** (8 of
   10 active campaigns). If the experiment shows thread_reply does not
   matter, the estate can simplify to all-new-thread without losing
   performance.

---

## METHODOLOGY

**Campaign enumeration:** `GET /campaigns` (offset pagination, all pages).
22 campaigns returned.

**Step data:** `GET /campaigns/{id}/sequence-steps` for each campaign.
20 of 22 returned step data. Parent steps only (variants excluded) for
the thread_reply pattern analysis.

**Reply feed:** `GET /replies` with `pagination_type=cursor`,
`per_page=100`. (In progress — see scripts/task105_reply_pages.py.)

**Sent counts:** `emails_sent` on the campaign row (PROVIDER FACT).
NEVER `meta.total`.

**Verification script:** `scripts/task105_verify_control_group.py`
independently walks all campaigns and their step definitions.

---

## CAVEATS

1. **Sent counts from `emails_sent`, never `meta.total`.** Campaign 274
   has 30,411 scheduled rows and a fraction are sent.
2. **`per_page` is ignored** — 15 rows per request on every route.
3. **No open-rate claim.** `open_tracking` is False estate-wide.
4. **The control group (262-266) is archived.** Their reply data may be
   outside the API's accessible reply feed window.
5. **All causal statements are ATTRIBUTION HYPOTHESES** unless labelled
   PROVIDER FACT.
6. **No PII in this report.** No emails, names, or company domains.
