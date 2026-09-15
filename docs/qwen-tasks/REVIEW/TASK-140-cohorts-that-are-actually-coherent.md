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

## RESULT

**STATUS:** DONE

**COMMIT:** 2cd4c8c

**SNAPSHOT:** `work/queue.snapshot.jsonl` from `2026-09-14T21:52:15Z`, master `0ac5e60`, 300 records.

**TESTS:** Four analysis scripts produced consistent results (scripts/task140_*.py). No unit tests applicable - this is a measurement task.

**FILES CHANGED:**
- `docs/COHORT-DESIGN-2026-09-15.md` (new) - the deliverable
- `scripts/task140_cohort_analysis.py` (new) - dimension distributions and cross-tabs
- `scripts/task140_deep_analysis.py` (new) - ICP flags, role families, evidenced vs inferred
- `scripts/task140_icp_eligibility.py` (new) - ICP gate analysis, clean vs flagged split
- `scripts/task140_evidence_audit.py` (new) - research quality, pipeline status, approval status

**FINDINGS:**

1. **56 eligible contacts, 1 client, 1 vertical, no signal.** All for "productive" in advertising/marketing/design services. Signal and context fields are 100% null across the entire non-dropped estate.

2. **ICP gate dominates: 24 clean, 32 flagged.** 27 flagged for under client minimum headcount (<20 employees), 12 for geo outside client markets, 7 for both. These are not cohorts; they are a backlog needing client decision or data correction.

3. **No evidenced signal exists.** Angle is inferred from title (only 9 of 56 have angle mentioned in research). Persona is classified from title. 13 of 54 records have "strong" quality research. 13 contacts had persona_angle held because "evidence not traceable to the record."

4. **Three CONTROL-arm cohorts cover the 24 ICP-clean contacts:**
   - C1: ICP-clean, founder-angle (11 contacts) - largest cell
   - C2: ICP-clean, operations-angle (7 contacts) - second largest
   - C3: ICP-clean, other (6 contacts) - residual
   - Total: 24 contacts, 100% of ICP-clean eligible

5. **No CHALLENGER cohort is defensible.** A challenger needs per-contact evidence that clears the claims gate. That evidence does not exist. Angle is inferred, not evidenced. Signal is null. Research is thin.

6. **The 32 ICP-flagged contacts are a backlog, not a cohort.** They need: client decision to lower headcount minimum, client decision to expand geo markets, headcount data correction, or new evidence.

7. **The design changes when:** signal is recorded, research deepens, or ICP flags are resolved. At 24 clean contacts the canary is three; at 50+ cohort splits become readable.

**RISKS:**
- The 24 clean contacts are 43% of eligible. The 32 flagged are excluded honestly, but they are still "eligible" in the email-verification sense. If the ICP flags are resolved, the cohort design needs revisiting.
- Angle is inferred from title. If the title classification is wrong, the cohort split is wrong. The evidence check (9 of 56) is the honest number.
- Headcount_signal is contested (7 conflicts, 64 disagreements across 300 records per PRODUCTION-SCALE-POLICY.md). The size buckets in this analysis use that field.

**RECOMMENDED CLAUDE ACTION:**
- Read `docs/COHORT-DESIGN-2026-09-15.md` for the full analysis, cross-tabs, and proposal.
- The 24 ICP-clean contacts are available for the CONTROL arm canary of three.
- The 32 ICP-flagged contacts need a client decision before they enter any cohort.
- No CHALLENGER arm is defensible until signal is recorded and research deepens.
