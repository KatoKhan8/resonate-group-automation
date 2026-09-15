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

## RESULT

**STATUS:** DONE

**COMMIT SHA:** ce3bc84

**TESTS:** Analysis script `scripts/analyze_cohorts.py` reads the snapshot and produces the coverage table and cohort counts. No unit tests were written because this is an analysis task, not a code change. The script is the verification - run it and the numbers match the report.

**FILES CHANGED:**
- `docs/COHORT-INVENTORY-2026-09-15.md` - human-readable cohort inventory
- `docs/state/COHORTS.json` - machine-readable cohort definitions (14 cohorts)
- `scripts/analyze_cohorts.py` - analysis script that produces the numbers

**FINDINGS:**

1. **Coverage verified.** The task brief said specialties at 73%. **Specialties is 0%.** The field does not exist in the contact structure or at record level. All other coverage numbers match: first name/title/company/domain/industry/headcount/persona at 100%, email at 94% (87/92), angle at 88% (81/92), employee_range at 19% (18/92).

2. **Two cohorts of >= 50 leads.**
   - Persona: economic_buyer - 70 leads
   - Industry: Advertising Services - 51 leads

3. **Five cohorts of >= 25 leads.** The two above plus:
   - Angle: founder - 45 leads
   - Persona + Industry: economic_buyer | Advertising Services - 40 leads
   - Angle + Industry: founder | Advertising Services - 27 leads

4. **The estate supports two clear cohorts of 50+, with several more in the 25-45 range.** It does not support dozens of cohorts of 50+. The policy says "where inventory supports it" - and the inventory supports two, maybe three with stretching.

5. **Headcount is contested and was not used as a primary cohort key.** `company_facts.employees` is 100% populated but `employee_range` is only 19%. The task brief warned about conflicts and this inventory respects that warning.

6. **No PII in the report.** All identifiers are hashed or omitted. The report names signals and counts, not companies or people.

**RISKS:**

- The specialties field is absent from the estate, contrary to the task brief's 73% figure. If specialties was expected to be a cohort signal, that signal does not exist and cannot be used.
- The two cohorts of 50+ (economic_buyer and Advertising Services) overlap significantly (40 leads in the intersection). Running them as separate campaigns would double-count those 40 leads. The decision on whether to run them as separate campaigns or as one merged cohort is a product and positioning question, not a data question.
- The cohorts of 25-45 are below the 50-lead target. The policy says they can be "held and accumulated, merged with a genuinely compatible cohort, or run explicitly as a small exploratory cohort with its sample size recorded." The decision on which path to take is not this task's to make.

**RECOMMENDED CLAUDE ACTION:**

1. Review the cohort inventory and decide which cohorts to run first. The two cohorts of 50+ are the obvious starting points.
2. Decide whether economic_buyer (70) and Advertising Services (51) should be separate campaigns or merged, given their 40-lead overlap.
3. For the cohorts of 25-45, decide whether to hold and accumulate, merge with compatible cohorts, or run as small exploratory cohorts.
4. Define the message hypothesis for each cohort. This inventory provides the counts and signals; the messaging is a product and positioning question.
5. Assign senders. The sender estate is measured and zero seats are uncommitted. Adding senders to a cohort requires reassigning seats that are already working.
