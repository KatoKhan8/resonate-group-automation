PRIORITY: P1
DEPENDS:

# TASK-140 - 248 eligible contacts and no principle for grouping them

## WHERE THIS COMES FROM

The first live campaign ships as a canary of three on the CONTROL arm, and the
operator batch progression is 3 -> 10 -> 25 -> 50 -> larger. At 3 the cohort
question does not arise. At 50 it decides whether the experiment can be read
at all: a campaign mixing four signals and three personas produces a reply rate
that means nothing, because nobody can say what it is a reply rate TO.

`PRODUCTION-SCALE-POLICY.md` is the standing contract - a campaign is a COHORT
and never a person, ~50 qualified leads where inventory supports it, grouping
backed by evidence THAT ACTUALLY EXISTS, consolidation over proliferation.
Read it before anything else. This task does not get to invent a different
policy; it applies that one to the estate we really have.

## THE QUESTION

Of the contacts eligible for first touch, what are the LARGEST coherent groups,
and what makes each one coherent?

Coherent means a dimension that would change what a message says or what an
experiment result means:

    signal              persona / role family
    ICP segment         company size or shape
    relationship state  channel
    geography, but only where it changes the words rather than the timezone

## WHAT TO MEASURE

Against `work/queue.snapshot.jsonl` - never the live queue. **Quote
`work/queue.snapshot.STAMP` in the result block.**

1. The distribution of every candidate dimension across eligible contacts:
   how many distinct values, how many contacts in each, how many contacts
   have NO value for it. A dimension where 80% of contacts are null is not a
   grouping dimension, it is a wish.
2. The actual cross-tabs for the two or three densest dimensions. Which
   combinations reach 50? Which reach 25? Which reach 10?
3. **Which dimensions are EVIDENCED and which are inferred.** A signal
   extracted from a crawl of the company's own careers page is evidence. A
   persona inferred from a job title string is a classification, and the
   difference decides whether a message may assert anything about it.
4. The proposal: a small number of named cohorts covering as much of the
   eligible inventory as the evidence honestly supports, each with its size,
   its dimension values, and what is left over. **Say what the leftovers are.**
   A proposal that groups 240 of 248 by widening a definition until everything
   fits has produced one cohort wearing four names.

## THE TRAP TO AVOID

Do not propose cohorts that need copy nobody has written. The CONTROL arm is
the operator's own fallback copy, which is deliberately general - it asserts
nothing about the recipient. A cohort whose whole rationale is a signal only
matters if the copy for it SAYS something about that signal, and that copy
would then have to pass the claims gate against that contact's own evidence.
So for each proposed cohort, state which arm it is for:

    CONTROL     the fallback copy, which says nothing specific - a cohort here
                is for READING the result, not for changing the message
    CHALLENGER  copy that asserts something, which needs per-contact evidence
                and must clear the claims gate

Both are legitimate. Confusing them is how a cohort design becomes a copy
project nobody asked for.

## WHAT YOU MAY NOT DO

- No provider calls.
- No writes to `work/`.
- Do not create campaigns. This task produces a design and the numbers under
  it; Claude builds cohorts.

## FILES ALLOWED

    docs/COHORT-DESIGN-2026-09-15.md   (new)
    scripts/task140_*.py
    the task file itself

## FILES FORBIDDEN

    src/       work/       config/clients/*.yaml

## DELIVERABLE

The distributions, the cross-tabs, the evidenced/inferred split, the named
cohort proposal with sizes and leftovers, and each cohort's arm.

---

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** bd47142

**SNAPSHOT STAMP:** `2026-09-14T21:52:15Z  from master 0ac5e60  300 records`

**TESTS:** Analysis script `scripts/task140_cohort_analysis.py` runs against the snapshot and produces all distributions, cross-tabs, and cohort candidates. No unit tests (this is a measurement task, not a code change).

**FILES CHANGED:**
- `docs/COHORT-DESIGN-2026-09-15.md` (new): full analysis and cohort proposal
- `scripts/task140_cohort_analysis.py` (new): analysis script
- Task file moved TODO -> RUNNING -> DONE

**FINDINGS:**

1. **The eligible population on the snapshot is 92 contacts**, not 248. The 248 comes from the live queue (550 records): 277 contacts with LinkedIn profiles minus 29 with prior EmailBison outreach. The snapshot is 300 records, a subset.

2. **No single dimension produces a cohort of 50.** The largest coherent group is economic_buyer at 72 (78.3% of pool), but that is the default, not a meaningful cohort. The largest vertical is Creative/Branding Agency at 23.

3. **38% of eligible contacts have UNKNOWN vertical** because the website crawl failed (32 of 35 have no research_outcome). These are not a cohort; they are the absence of one. They can be a CONTROL cohort for reading the result ("what happens when we don't know the vertical?"), labelled as such.

4. **66% have region = "Other"** because no location evidence was found. Geography cannot be used as a cohort key until research fills the gap.

5. **Only 22 of 92 contacts (24%) have evidenced pain categories** (resource_planning + delivery_visibility). These are the ONLY contacts where CHALLENGER copy may assert a specific pain. The remaining 70 have no evidenced signal for copy to reference.

6. **The evidenced/inferred split:**
   - EVIDENCED: persona (from title), industry (from LinkedIn), employee_band (from LinkedIn headcount, but contested), region/country/city (from office address where present)
   - INFERRED: vertical (classified from website text), business_model (classified), persona_strategy (rule from employee_band), recommended_angles (system recommendation), icp_tier (composite score)

7. **Proposed cohorts:**
   - CONTROL: 6 cohorts by vertical (Creative/Branding 23, Digital Marketing 14, Performance Marketing 13, UNKNOWN 35, Software Dev + SEO + Consulting 7)
   - CHALLENGER: 1 ready cohort (22 contacts with evidenced resource_planning + delivery_visibility pains)
   - Alternative: 5 size-band cohorts with 100% coverage (1_9: 16, 10_19: 27, 20_49: 22, 50_99: 17, 100+: 10)

8. **The batch progression 3 -> 10 -> 25 -> 50 must fit inside 92 contacts on the snapshot** (or 97 deployable on the live queue after account collision). A ~50-contact cohort is reachable only by combining verticals or by using size bands, neither of which produces a cohort where the copy can say something specific about what the company does.

9. **The CONTROL arm is the honest arm for 70 of 92 contacts.** Only 22 have evidenced pains that copy may assert. The other 70 receive the fallback copy that says nothing specific, which is correct because the evidence does not support anything specific.

10. **The cohort question at 50 is not "which 50 contacts" but "which dimension are we reading the result on."** A campaign of 50 contacts mixing four verticals and two personas produces a reply rate that means nothing unless the cohort is defined BEFORE the send and the result is read against that definition.

**RISKS:**
- The 38% UNKNOWN vertical is a research gap, not a cohort design problem. Fixing it requires website crawls.
- The 66% region=Other is the same: a research gap.
- Headcount is contested on some records (7 conflicts, 64 disagreements across 300 records per PRODUCTION-SCALE-POLICY.md). Size-band cohorts inherit this uncertainty.
- The 22 contacts with evidenced pains are concentrated in Creative/Branding (15) and Digital Marketing (7). Performance Marketing (13 contacts) has no evidenced pains despite having a vertical.

**RECOMMENDED CLAUDE ACTION:**
1. Read `docs/COHORT-DESIGN-2026-09-15.md` for the full analysis and proposal.
2. For the first canary of 3: use CONTROL arm, pick 3 from Creative/Branding Agency economic_buyer (C1) or 10_19 employees (S2).
3. For the batch of 10: use CONTROL, combine C1 + C3 (Creative + Digital Marketing = 37 available).
4. For the batch of 25: use CONTROL, combine C1 + C3 + C4 (Creative + Digital + Performance = 53 available).
5. For the batch of 50: use CONTROL, combine C1 + C3 + C4 + C5 (all known verticals + UNKNOWN = 88 available).
6. For CHALLENGER: wait until CH1 accumulates to 10+ (currently 22, ready). Use the 22 contacts with evidenced pains.
7. Do not merge UNKNOWN verticals into a known vertical cohort. They are not Creative/Branding or Digital Marketing agencies as far as the evidence says.
8. Do not use persona_strategy as a cohort key. It is a restatement of employee_band.
