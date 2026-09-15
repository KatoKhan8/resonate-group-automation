# TASK-096 - what cohorts does this estate actually support?

## THE POLICY THIS SERVES

`docs/PRODUCTION-SCALE-POLICY.md`, set by the operator 2026-09-15. A campaign
is a COHORT and never a person. Target ~50 qualified leads per normal cohort
where inventory supports it. Grouping is by evidence-backed signal.

**This task does not create a campaign. It answers whether any cohort of that
size can be honestly assembled from what the estate actually holds.**

## WHY IT MIGHT NOT

The estate is 300 records and **92 contacts on not-dropped records**. If a
cohort needs 50 qualified leads, the whole estate supports at most one or two
cohorts - and that is before any qualification rule is applied. Say so plainly
if that is what you find. An honest "this estate supports one cohort of 60 and
nothing else" is worth far more than five cohorts of twelve dressed up as a
plan.

## FIELD COVERAGE IS ALREADY MEASURED - START FROM IT, VERIFY IT

Over the 92 contacts on not-dropped records:

    first name, title, company, domain, industry, headcount, persona   100%
    email 94%, angle 88%, specialties 73%     SAFE FALLBACK REQUIRED
    employee_range 19%                        EXCLUDE THE RECORD

**Verify these before building on them.** A first pass reported industry and
headcount at 0% and was wrong - it read `sizing`, which is null everywhere,
where the data lives in `company_facts`. That mistake was made three separate
times in one session. A zero and a wrong lookup are indistinguishable from the
outside.

**Headcount is contested and is NOT safe as a cohort key**: 7 conflicts and 64
range/value disagreements across 300 records.

## WHAT TO PRODUCE

1. **A coverage table for every field you might group on**, read through the
   real entry points against `work/queue.jsonl`, with the lookup path named.
   Include fields nobody has checked yet, not just the seven above.

2. **Candidate cohorts.** For each: the signal, the qualification rule, the
   exclusion rule, and THE COUNT. Sort by count. A cohort whose signal is null
   for most of its members is a cohort about nothing - exclude it and say why.

3. **The honest verdict on size.** How many cohorts of >=50 can be assembled?
   Of >=25? If the answer is zero at 50, say what the largest honest cohort is
   and what it would take to reach 50 - more discovery, more enrichment, or a
   merge with a genuinely compatible cohort.

4. **A durable cohort definition file** for the top candidates, carrying the
   fields the policy names: COHORT_ID, SIGNAL, ICP FILTER, QUALIFICATION RULE,
   EXCLUSION RULE, LEAD COUNT, MESSAGE HYPOTHESIS, CAMPAIGN, VARIANTS,
   SENDERS, START DATE, OUTCOMES, CONFIDENCE, LEARNING. Leave CAMPAIGN,
   OUTCOMES and LEARNING empty - they are not yours to fill.

## WHAT NOT TO DO

- **Do not fabricate cohort similarity to reach 50.** Forcing unrelated leads
  together destroys the attribution the cohort exists to produce. The policy
  says this explicitly and it is the main way this task can go wrong.
- Do not create, modify or write to any campaign at either provider. Reads and
  local analysis only.
- Do not count a dropped record. Do not count a contact with no email toward a
  cohort that needs email.
- Do not put a real domain, company name, person's name or address in the
  report. Hash identifiers. `tests/test_fixture_hygiene` guards this and has
  already caught real leaks in this repository, including one committed by
  Claude yesterday.

## DELIVERABLE

`docs/COHORT-INVENTORY-2026-09-15.md` plus `docs/state/COHORTS.json` for the
machine-readable definitions. Every count with the rule that produced it, so
somebody can disagree with the rule rather than with the number.
