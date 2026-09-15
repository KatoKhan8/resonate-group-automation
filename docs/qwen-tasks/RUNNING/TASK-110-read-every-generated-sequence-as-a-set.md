PRIORITY: P3
DEPENDS: TASK-092

# TASK-110 - sequence QA across the whole generated estate

## WHAT THIS IS

TASK-092 counts six specific copy defects. This one asks a different question
of the same material: **does each SEQUENCE work as one conversation?**

A sequence can have six individually clean messages and still be broken - six
messages that each pass lint, and together ask one question six times.

## WHAT TO CHECK, PER SEQUENCE

1. **Progression.** Does each rung do a DIFFERENT job, or do several collapse
   into one discovery question? The ladder specifies six different jobs.
   `ogpartner-dk/jacob-faertz` is the sequence that got it right - six rungs,
   six jobs, product named once at rung 4, easy out at rung 6.
2. **Does it read as one person writing?** Tone drift between steps, a step
   that reintroduces the sender as if for the first time, a step that assumes
   context an earlier step never gave.
3. **Is there an easy out?** A final rung that lets somebody decline without
   awkwardness.
4. **Does a later step acknowledge that earlier steps went unanswered**, or
   does it pretend to be a first contact?
5. **Conceptual duplication** - not the string-level duplicate TASK-092
   counts, but two steps making the same ASK in different words.

## WHAT NOT TO DO

- Do not regenerate. Read what is stored. Regeneration costs 560 steps and 83
  human approvals and is the operator's call.
- Do not fix. This is a measurement; a fix in the same change makes the
  before-number unverifiable.
- Hash identifiers in the report.

## DELIVERABLE

`docs/SEQUENCE-QA-2026-09-15.md`: a per-sequence verdict, the rate of each
defect with its denominator, and the three worst and three best sequences
with identifiers hashed. Name which defects are universal (a prompt problem)
and which are rare (a per-record problem) - that distinction decides the fix.

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
