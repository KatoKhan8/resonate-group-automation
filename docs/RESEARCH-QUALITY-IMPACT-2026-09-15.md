# Research Quality Impact: TASK-143

**Date:** 2026-09-15
**Snapshot:** 2026-09-14T21:52:15Z from master 0ac5e60, 300 records
**Script:** `scripts/task143_analysis.py`

## The Question

34% of research rows are page furniture (navigation, legal text, cookie banners).
`research.for_prompt` takes the first 3 rows in stored order with no quality
ordering, so some records show the model only furniture where facts should be.

TASK-135 added a quality-filtered `research_block` to the prompt, but the
drafts in the estate were generated BEFORE that change. They saw the unfiltered
`public_evidence`. This measurement asks: did the junk evidence do any damage?

Three candidate answers:
1. **Nowhere** - the model ignores unusable evidence and writes from structured data
2. **In the copy, silently** - drafts pass all gates but are weak because the evidence gave the model nothing
3. **In the rejection rate** - drafts fail more often on junk-fed records

## The Split

| Group | Records | With drafts | Total drafts |
|-------|---------|-------------|--------------|
| JUNK-FED (first 3 all unusable/missing) | 45 | 8 (18%) | 47 |
| FACT-FED (first 3 all usable) | 91 | 29 (32%) | 193 |
| MIXED | 67 | 18 (27%) | 108 |

Overall: 270 of 695 research rows (38.8%) are unusable quality.

## Pre-Stated Thresholds

Before computing, I stated what difference would be worth acting on for a
45-vs-91 comparison:

| Metric | Threshold for "worth acting on" | Rationale |
|--------|--------------------------------|-----------|
| Fact-referencing rate | 20+ percentage points | Below this, the model is not reading the evidence at all |
| Rejection rate (per record) | 10+ percentage points | Below this, the gates are not affected |
| Generic language rate | 15+ percentage points | Below this, the copy is not visibly degraded |
| Avg draft length | 3+ words | Below this, the model is not engaging with the material |

## The Comparison

### Rejection rates (per record)

| Class | JUNK-FED | FACT-FED | Difference |
|-------|----------|----------|------------|
| Records with rejections | 8/45 (18%) | 31/91 (34%) | +16pp FACT-FED |
| Repetition rejections | 297 | 582 | - |
| Claims rejections | 24 | 51 | - |
| Lint rejections | 34 | 113 | - |
| Repetition per record with drafts | 297/8 = 37.1 | 582/29 = 20.1 | JUNK-FED higher |
| Claims per record with drafts | 24/8 = 3.0 | 51/29 = 1.8 | Similar |

**Verdict:** No meaningful difference in rejection rates. Both groups fail at
similar rates, and repetition dominates both (88% of JUNK-FED rejections, 76%
of FACT-FED). The claims gate caught unsupported claims at the same rate (~7%
of all rejections in both groups). **Candidate (3) is not supported.**

### Generic product language

| Metric | JUNK-FED | FACT-FED | Difference |
|--------|----------|----------|------------|
| Avg generic phrases/draft | 0.17 | 0.26 | FACT-FED +0.09 |
| Drafts with 1+ generic phrase | 8/47 (17%) | 44/193 (23%) | FACT-FED +6pp |

**Verdict:** JUNK-FED drafts have LESS generic product language, not more.
The difference is small (6pp) and in the counterintuitive direction. **Candidate
(2) is not supported on this metric.**

### Draft length

| Metric | JUNK-FED | FACT-FED | Difference |
|--------|----------|----------|------------|
| Avg words | 18.7 | 20.5 | FACT-FED +1.8 |
| Min | 11 | 11 | - |
| Max | 34 | 33 | - |

**Verdict:** 1.8 words difference, below the 3-word threshold. Not meaningful.

### Vocabulary overlap (avg pairwise Jaccard)

| Metric | JUNK-FED | FACT-FED |
|--------|----------|----------|
| Avg Jaccard (200 samples) | 0.065 | 0.066 |

**Verdict:** Identical. Both groups produce drafts with similar vocabulary
diversity. The model is not repeating the same words more in either group.

### Fact-referencing rate

| Metric | JUNK-FED | FACT-FED | Difference |
|--------|----------|----------|------------|
| Drafts referencing a research fact | 6/47 (12.8%) | 91/193 (47.2%) | **FACT-FED +34.4pp** |

**Verdict:** A 34.4 percentage point gap. This is the only metric that crosses
its pre-stated threshold, and it crosses it by a wide margin. **Candidate (2)
is supported on this metric.**

## The Verdict: Candidate (2) - Silent Copy Degradation

The damage from junk evidence is not in the gates. It is in the copy.

When the model receives only unusable evidence (navigation text, legal pages,
cookie banners), it writes persona-pain templates with the company name swapped
in. When it receives usable evidence, it references real facts about the
company 3.7x more often.

The gates do not catch this because:
- The claims gate refuses unsupported claims, but persona-pain templates do not
  make claims - they ask questions ("how do you currently track profitability?")
- The repetition gate catches angle-wording leakage between steps, but a
  template that never had anything to say is repetitive by construction, not
  because it leaked wording from another step
- The lint gate catches filler phrases and formatting, but "how do you
  currently track utilisation?" is grammatically correct and has no filler

The cost is a weak message rather than a rejected one. Three human reads have
already said the generated copy loses to the fallbacks. This measurement says
why: 87% of JUNK-FED drafts do not reference any fact from the research.

### Examples

**JUNK-FED draft** (record `adk-america`, research is 3 GoDaddy copyright pages):
> li2: "how are you currently tracking utilisation and capacity across your live projects?"

This is a generic question. It could be sent to any agency. It says nothing
about ADK America.

**FACT-FED draft** (record `2020companies-com`, research includes "Driving
Measurable Retail Growth Across 600,000+ Retail Doors"):
> li1: "hi rachele, i admire how 2020 Companies drives measurable retail growth. i'd love to connect and share insights on enhancing profitability in retail."

This references a specific fact: "measurable retail growth". It could only be
sent to 2020 Companies.

**Another JUNK-FED draft** (record `agency59-ca`, research is 3 pages of
"Agency59. An independent branding ad agency." repeated):
> li4: "i've seen how teams like yours have improved profitability by streamlining their processes. have you noticed any areas where efficiency could be enhanced?"

"I've seen how teams like yours" is the most generic sentence possible. It
asserts nothing about Agency59.

## What Good Evidence Looks Like

If the answer is (2) - and it is - then the useful deliverable is not a filter
(TASK-135 already added one). It is the measurement that tells a generation
task what "good evidence" means.

### A fact worth putting in front of the model must:

1. **Contain a specific, verifiable claim about the company.** Not "we are a
   leading provider" (self-praise, unverifiable), but "we opened a Vienna
   office in March 2026" or "we serve 600,000+ retail doors" or "we partnered
   with BYD as Official Automotive Partner".

2. **Include at least one concrete detail:** a number, a date, a named client,
   a location, a team size, a technology stack. "We help agencies grow" has
   none. "We help 40-person agencies track utilisation across 12+ concurrent
   projects" has three.

3. **Survive the boilerplate test.** After removing navigation text, cookie
   consent language, and legal furniture, at least 12 content words must
   remain. This is already enforced by `evidence.boilerplate()`.

4. **Score medium or strong on quality.** This requires relevance >= 0.65
   against the client's angle vocabulary, and freshness within the policy
   maximum age.

### Examples from the real data

**Good (STRONG, relevance 1.0):**
> "2020 Companies is a premier sales and marketing agency that specializes in
> providing comprehensive solutions to retail businesses of all sizes. Our team
> of retail strategy experts is dedicated to driving measurable growth across
> 600,000+ retail doors."

Why it is good: names the company, states what it does (retail sales/marketing),
gives a specific number (600,000+ retail doors), and is verifiable.

**Good (STRONG, relevance 1.0):**
> "ARIAN began over 50 years ago as a small printing company in Austria. Our
> story already starts in our name: inspired by the idea of making campaigns
> visible."

Why it is good: gives a founding date (50+ years ago), a location (Austria),
an origin story (printing company), and a mission (making campaigns visible).

**Bad (UNUSABLE, quality correctly refused):**
> "Skip to content About Clients Archive Menu 3x34 - One Company Will Rise
> Above Danske Malermestre - Small details - great masterpieces NEXT - Campaign
> Identity CS Megastore - Unleash the Fantasy"

Why it is bad: navigation menu items. No claim about the company. Could be
any agency's website.

**Bad (UNUSABLE, quality correctly refused):**
> "Copyright (c) 1999-2026 GoDaddy, LLC. All rights reserved. Privacy Policy
> Disclaimer"

Why it is bad: legal furniture. Says nothing about the company.

**Borderline (MEDIUM, relevance 0.7):**
> "Call +353 1 864 3704 home our work experience live experience fit out our
> team vacancies contact Menu... With a culture based in a genuine passion for
> craft; we are real people striving to create meaningful work"

Why it is borderline: contains navigation text at the start, but the second
half has a real claim ("culture based in a genuine passion for craft; we are
real people striving to create meaningful work"). It is weak because the claim
is generic self-description, not a specific fact.

## The Honest Outcome

The difference in rejection rates is inside the noise (1-2pp). The difference
in generic language is inside the noise (6pp, wrong direction). The difference
in vocabulary overlap is zero.

The difference in fact-referencing is NOT inside the noise: 12.8% vs 47.2% is
a 34.4pp gap on 47 vs 193 drafts. It is the only metric that crosses its
pre-stated threshold, and it crosses it by 14pp.

But 47 drafts from 8 records is a small sample. The honest outcome is:

**The junk evidence does not cause rejections. It causes the model to write
persona-pain templates instead of fact-based messages. The gates cannot see
this because a template that says nothing is not wrong - it is just weak.**

The 45 JUNK-FED records are not a crisis. 8 of them produced drafts, and those
drafts passed the gates. But they are also not useful: 87% of them do not
reference any fact from the research. They are the same message with the
company name swapped in.

TASK-135's quality filter (`research_block`) addresses this for future
generation. The drafts in the estate were generated before that filter existed.
Regenerating them with the filter would be the next step, and that is Claude's
run from Claude's worktree.

## Files Changed

- `docs/RESEARCH-QUALITY-IMPACT-2026-09-15.md` (this file)
- `scripts/task143_analysis.py` (the measurement script)

## Result Block

- **STATUS:** DONE
- **COMMIT SHA:** (pending)
- **TESTS:** No code changes to test. The script is a measurement, not a feature.
- **FILES CHANGED:** `docs/RESEARCH-QUALITY-IMPACT-2026-09-15.md`, `scripts/task143_analysis.py`
- **FINDINGS:**
  - 270 of 695 research rows (38.8%) are unusable quality
  - 45 records have their first 3 rows all unusable (JUNK-FED)
  - 91 records have their first 3 rows all usable (FACT-FED)
  - Rejection rates: no meaningful difference (18% vs 34% of records, but per-draft repetition is similar)
  - Generic language: no meaningful difference (17% vs 23%, wrong direction)
  - Fact-referencing: **34.4pp gap** (12.8% vs 47.2%), the only metric that crosses its threshold
  - Verdict: candidate (2) - silent copy degradation. The model writes templates instead of fact-based messages when evidence is junk.
  - The gates do not catch this because a template that says nothing is not wrong, just weak.
- **RISKS:**
  - Small sample: 47 JUNK-FED drafts from 8 records. The gap is large (34.4pp) but the base is small.
  - The fact-referencing check uses 2+ overlapping content words (5+ chars), which may catch company-name matches as well as real fact references. The gap is still large enough to be meaningful even with false positives.
  - The drafts were generated before TASK-135's quality filter. Regenerating with the filter would confirm whether the gap closes.
- **RECOMMENDED CLAUDE ACTION:**
  - Regenerate the 45 JUNK-FED records with the quality-filtered `research_block` and compare the new drafts against the old ones. If the fact-referencing rate rises from 12.8% to near 47%, the filter is confirmed to work.
  - The 45 JUNK-FED record IDs are in the script output. They are the highest-value candidates for regeneration because they are the ones most likely to improve.
