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
