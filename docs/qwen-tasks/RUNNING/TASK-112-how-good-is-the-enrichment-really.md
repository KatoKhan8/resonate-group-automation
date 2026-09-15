PRIORITY: P4
DEPENDS: 

# TASK-112 - enrichment quality, and what is safe to personalise with

## WHY IT MATTERS NOW

The cohort work (TASK-096) and the batch work (TASK-101) both rest on field
coverage. A cohort keyed on a field that is wrong 20% of the time produces a
campaign that is wrong 20% of the time, and the error arrives at a person.

## WHAT IS ALREADY MEASURED - VERIFY IT, DO NOT ASSUME IT

Over the 92 contacts on not-dropped records:

    first name, title, company, domain, industry, headcount, persona   100%
    email 94%, angle 88%, specialties 73%     SAFE FALLBACK REQUIRED
    employee_range 19%                        EXCLUDE THE RECORD

**Coverage is not correctness**, and headcount proves it: 7 conflicts and 64
range/value disagreements across 300 records. 100% coverage with 71
disagreements is not a usable field.

And the lookup trap: a first pass reported industry and headcount at 0%
because it read `sizing`, which is null everywhere, instead of `company_facts`.
That mistake was made three separate times in one session.

## WHAT TO ESTABLISH, PER FIELD

1. Coverage, through the real entry point, with the lookup path named.
2. **Correctness where it can be checked** - internal contradictions between
   sources, values that cannot be true, values that contradict the domain.
3. Staleness: how old is the evidence, and does the field have a timestamp at
   all? A guessed timezone is worse than a missing one, and the same logic
   applies to a headcount from eighteen months ago.
4. A verdict per field: SAFE TO PERSONALISE / SAFE WITH FALLBACK / NOT SAFE /
   EXCLUDE THE RECORD.

## WHAT NOT TO DO

- Do not repair data in this task. Measure it.
- Do not treat "present" as "correct".
- Hash identifiers in the report.

## DELIVERABLE

`docs/ENRICHMENT-QUALITY-2026-09-15.md` with the per-field verdict table, and
an explicit list of fields that must NOT be used as a cohort key.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from the outside.** If you
  measure zero of something, prove you read the right field first. Industry
  and headcount were reported at 0% three separate times by a reader looking
  at `sizing`, which is null everywhere, instead of `company_facts`.
- Say what you SAMPLED. `per_page` is accepted and IGNORED on every EmailBison
  route - you get 15 rows whatever you ask for - and offset pagination is
  refused past ~500 pages. A number without its page budget is not
  reproducible.
- Never use `meta.total` as a sent count. Campaign 274 reports 30,411
  scheduled rows and zero of its first 100 pages are sent. Count rows WHERE
  `sent_at` IS PRESENT.
- **Do not quote 8.49%** - unreproduced. **Do not quote any open rate** -
  `open_tracking` is False estate-wide, which is an ABSENT MEASUREMENT and not
  a zero. **Do not count an UNKNOWN as negative** - 53.4% of unknowns are
  correctly unknown.
- INTERESTED may NOT carry a learning claim: 0.44 precision on the old pattern
  set, and the new set is UNMEASURED, which is not the same as good.
  MEETING_INTENT (1.00) and OBJECTION (1.00) may, with recall stated.
- Never weaken, widen or disable a gate, a lint rule or a sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- No unhashed PII in any tracked file or commit message - no real names,
  domains, emails, profile URLs or reply text. A seat holder is a real person
  too; Claude leaked one yesterday and the guard caught it.
- Separate OBSERVATIONS (with n), HYPOTHESES, and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection. TASK-059
  left it empty and was right to.
