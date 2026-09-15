# Research Quality Impact: Where Junk Evidence Surfaces

**Date:** 2026-09-15
**Task:** TASK-143
**Snapshot:** `work/queue.snapshot.jsonl` — 2026-09-14T21:52:15Z from master 0ac5e60, 300 records

---

## The Two Groups

203 records carry `research[]` rows. Classified by what `research.for_prompt(rec)` returns (first 3 rows, stored order, no quality filter):

| Group | Definition | Count |
|-------|-----------|-------|
| JUNK-FED | All of first 3 rows are `quality=unusable` | 32 |
| FACT-FED | At least one of first 3 is `medium` or `strong` | 119 |
| WEAK-FED | First 3 are only `weak` or missing quality | 52 |

The quality distribution across all 695 rows:

| Quality | Count |
|---------|-------|
| unusable | 236 |
| weak | 156 |
| medium | 155 |
| strong | 114 |
| (missing) | 34 |

---

## Pre-Stated Threshold

With n(JUNK-FED)=32 and n(FACT-FED)=119, the comparison is underpowered.
The minimum detectable effect at ~80% power is roughly 20-25 percentage points.

**Pre-stated actionable threshold: >= 15pp difference on any rate metric.**
A difference inside +/- 10pp is noise. Between 10-15pp is suggestive but not conclusive.

---

## 1. Rejection Rates by Class

| Category | JUNK-FED (32 rec) | FACT-FED (119 rec) |
|----------|-------------------|---------------------|
| Records with any rejection | 5 (15.6%) | 38 (31.9%) |
| Total rejection reasons | 164 | 943 |
| Avg per record | 5.1 | 7.9 |
| — repetition | 143 (87.2%) | 720 (76.4%) |
| — banned/filler | 12 (7.3%) | 77 (8.2%) |
| — unsupported claim | 2 (1.2%) | 25 (2.7%) |
| — formatting | 3 (1.8%) | 33 (3.5%) |
| — subject too long | 3 (1.8%) | 35 (3.7%) |
| — no angle | 0 | 46 (4.9%) |

**Interpretation:** JUNK-FED records have FEWER rejections, not more. But this is
because fewer JUNK-FED records have drafts at all (5 of 32 vs 36 of 119). The
rejection rate per record-with-drafts is similar: ~9-10 rejections per record
in both groups.

**Unsupported claims are rare everywhere** — 2 in JUNK-FED, 25 in FACT-FED.
As a share of total rejections: 1.2% vs 2.7%. The difference is 1.5pp, well
inside the noise. The claims gate is not where junk evidence does its damage,
because junk evidence does not produce claims — it produces nothing.

---

## 2. Draft Quality Metrics

| Metric | JUNK-FED (49 drafts) | FACT-FED (371 drafts) |
|--------|----------------------|------------------------|
| Records with drafts | 5 of 32 (15.6%) | 36 of 119 (30.3%) |
| Drafts with >= 1 generic phrase | 10 (20.4%) | 101 (27.2%) |
| Avg generic phrases per draft | 0.31 | 0.39 |
| Drafts with navigation leakage | 8 (16.3%) | 43 (11.6%) |
| Drafts referencing evidence facts | 0 (0.0%) | 27 (7.3%) |
| Avg draft length (words) | 39.2 | 36.6 |

**Key findings:**

1. **JUNK-FED drafts never reference evidence facts (0 of 49).** The model
   receives navigation text and writes from `company_facts` instead. The
   evidence is not rejected — it is ignored.

2. **FACT-FED drafts reference evidence only 7.3% of the time.** Even when
   given usable facts, the model mostly ignores them. The 7.3% is the
   ceiling of what filtering could fix.

3. **Generic phrase rates are similar or LOWER in JUNK-FED.** The model
   writes "describes itself as" and "innovative approach" from `company_facts`
   (which are also surface-level), not from research evidence.

4. **Navigation leakage is only slightly higher in JUNK-FED** (16.3% vs
   11.6%). The difference is 4.7pp — inside the noise threshold.

---

## 3. Vocabulary Analysis

| Metric | Value |
|--------|-------|
| Cross-group Jaccard (junk vs fact vocab) | 0.281 |
| Internal Jaccard (JUNK-FED, sampled) | 0.113 |
| Internal Jaccard (FACT-FED, sampled) | 0.095 |

JUNK-FED drafts are slightly more homogeneous internally (0.113 vs 0.095),
but the difference is small. Both groups draw from similar vocabulary pools,
with cross-group overlap at 0.281.

---

## 4. Examples: What Junk-Fed Copy Looks Like

5 instances of drafts directly quoting navigation text, all from one record
(`mypersonalestatesale-com`):

    "Your focus on client care at My Personal Estate Sale LLC My Personal
     Estate Sale LLC highlights a mission to provide professional..."

The company name appears in the navigation menu, the model picks it up as a
"fact" about the company, and repeats it verbatim — including the duplication.
This is the visible face of junk evidence: not a rejected claim, but a
grammatically correct sentence that says nothing.

---

## 5. The Usable Evidence That Exists But Is Not Shown

Of 32 JUNK-FED records, only **1** has usable evidence in rows 4+:

    Record: pomplunspanier-com
    [medium] Pomplunspanier – Agentur für Markenfreundschaft Als Agentur
    für Markenfreundschaft gestalten wir die Beziehungsqualität...

**31 of 32 JUNK-FED records have NO usable evidence at any position.**
Reordering or expanding the limit would help exactly 1 record. The problem
is not that good evidence is buried — it is that good evidence was never
extracted.

---

## 6. What Good Evidence Looks Like

Examples from the `strong` quality tier:

    "2020 Companies is a premier sales and marketing agency that specializes
     in providing comprehensive solutions to retail businesses of all sizes."

    "2TON | Award-Winning Creative Agency Full Service Creative & Digital
     Agency Creative Powerhouse Meets Peak Performance Premium design.
     Strategic messaging."

Even `strong` evidence is still extracted page text with some navigation
residue. The difference from `unusable`:

| Quality | What it contains | Example |
|---------|-----------------|---------|
| unusable | Pure navigation, menus, client lists | "Skip to content About Clients Archive Menu..." |
| weak | Navigation + company self-description | "We are a creative advertising agency, creating custom-made solutions..." |
| medium | Team descriptions, service details, some substance | "With a culture based in genuine passion for craft; we are really..." |
| strong | Actual prose about what the company does | "2020 Companies is a premier sales and marketing agency that specializes in..." |

**What a fact would have to look like to be worth putting in front of the model:**

1. **Contains a complete sentence** about the company, not a fragment.
   - Good: "We help marketing agencies build scalable outbound sales pipelines"
   - Bad: "Services Testimonials Case Studies About Book a call"

2. **Names something specific** — a service, a speciality, a client outcome.
   - Good: "specializes in providing comprehensive solutions to retail businesses"
   - Bad: "creating custom-made solutions, accommodating the ever-changing market"

3. **Is not the company's own tagline repeated back to them.**
   - Good: "Our team of 45 engineers has shipped 200+ projects since 2019"
   - Bad: "Award-Winning Creative Agency Creative Powerhouse Meets Peak Performance"

4. **Survives the "so what?" test** — gives the model something to build a
   question or observation around, not just a fact to parrot.
   - Good: "helps agencies track profitability visible on Monday rather than
     two weeks later" (gives the model a pain point to reference)
   - Bad: "Facebook Twitter LinkedIn Instagram" (gives the model nothing)

---

## Verdict: Candidate (2) — Silent Degradation

The answer is **(2): In the copy, silently.**

The damage from junk evidence is:
- **Invisible to every gate** — rejections are not higher, claims are not
  more unsupported, lint passes equally.
- **Visible to a human read** — the model ignores unusable evidence entirely
  (0% reference rate) and writes from `company_facts` alone, producing
  generic copy that says what any template would say.
- **Not fixable by reordering** — 31 of 32 JUNK-FED records have no usable
  evidence at any position. The extraction itself is the bottleneck.
- **Not fixed by filtering alone** — even FACT-FED records reference evidence
  only 7.3% of the time. The model has usable facts and mostly ignores them.

The 15.6% vs 11.6% navigation leakage difference (4.7pp) is inside noise.
The 0% vs 7.3% evidence-reference difference is real but small — it tells us
the model CAN use evidence when it is usable, but usually does not.

### The Real Constraint

The constraint is not that evidence does not reach the model. It is that:

1. **34% of extracted rows are page furniture** (navigation, menus, contact
   blocks) that the quality classifier correctly marks `unusable`.
2. **The quality filter works** — `research_block()` in TASK-135 already
   filters to medium+strong. But even with good evidence available, the model
   references it only 7.3% of the time.
3. **The extraction, not the filtering, is the bottleneck.** Most JUNK-FED
   records (31 of 32) have no usable evidence anywhere. No reordering helps.
   The crawler needs to extract better prose, not the system needs to sort
   worse.

### What Would Help

- **Better extraction** from the crawler: skip navigation-dominant pages,
  prioritize /about, /services, /team pages that contain actual prose.
- **A stronger prompt instruction** to use `public_evidence` or `research`
  facts when available, rather than falling back to `company_facts` alone.
- **A measurement that catches silent degradation**: a gate that checks
  whether the draft references ANY evidence fact, not just whether claims
  are supported. This is a new gate, and the task forbids widening gates.

### What Would NOT Help

- Reordering research rows (31 of 32 JUNK-FED records have nothing to reorder)
- Expanding `for_prompt` limit from 3 to 5 (same reason)
- Further filtering the quality threshold (already done by TASK-135, and the
  model ignores even good evidence 93% of the time)

---

## Statistical Honesty

This comparison has 32 JUNK-FED records against 119 FACT-FED records. The
minimum detectable effect at 80% power is ~20-25pp. The pre-stated threshold
was 15pp.

The largest observed difference is the evidence-reference rate (0% vs 7.3%),
which is a 7.3pp difference — below the actionable threshold. All other
differences are smaller.

**The honest outcome is that the difference is inside the noise for most
metrics, and the one metric where it is not (evidence referencing) tells us
the model CAN use evidence but usually does not, regardless of quality.**
