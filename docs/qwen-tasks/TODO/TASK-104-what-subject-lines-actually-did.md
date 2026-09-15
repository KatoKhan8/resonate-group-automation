PRIORITY: P2
DEPENDS: 

# TASK-104 - subject lines: what the estate actually shows

## WHAT IS KNOWN

    82.1% statement-led, 17.9% question-led   (shape distribution)

That is a distribution of what was SENT, not of what WORKED. Nobody has
related subject shape to outcome with a denominator.

TASK-059's recovered report gives reply counts by subject shape - empty 8792,
statement 551, reply-prefix 286, question 97 - but 8,792 of those are rows
with no subject at all, which are the historical rows with no scheduled email
attached. **Those 8,792 are the same rows that made its other numbers wrong.**
Treat them as unmeasurable, not as "empty subject".

## WHAT TO ESTABLISH

For a deliberately sampled set where the subject IS known and the send IS
confirmed:

1. Reply rate by subject shape - statement, question, reply-prefix (`Re:`).
2. Does a `Re:` prefix correlate with same-thread follow-ups, and can the two
   be told apart? A same-thread follow-up may carry the original subject; if
   so, "reply-prefix" is a proxy for threading rather than an independent
   choice, and treating them as separate shapes double-counts.
3. Subject LENGTH against outcome.
4. Whether any of it survives a sample-size objection.

## WHAT NOT TO DO

- **Do not widen `SUBJECT_VOCABULARY`.** It has been measured and rejected
  twice. A finding that some word correlates with replies is not permission.
- Do not quote an open rate. `open_tracking` is False estate-wide.
- Do not count a row with no subject as a short subject.

## DELIVERABLE

`docs/SUBJECT-ANALYSIS-2026-09-15.md`, with the sample stated, and PROVEN
LEARNINGS empty unless something genuinely survives.

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
