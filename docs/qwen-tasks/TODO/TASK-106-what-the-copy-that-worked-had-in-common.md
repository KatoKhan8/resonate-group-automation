PRIORITY: P2
DEPENDS: 

# TASK-106 - what the copy that EARNED replies had in common

## THE TASK

Across the historical EmailBison estate, take the emails that earned a
POSITIVE reply and the emails that earned a NEGATIVE or unsubscribe, and
establish what separates them - if anything does.

## THE TRAP THIS TASK IS BUILT AROUND

**This is survivorship analysis and it will lie to you if you let it.** Copy
that got replies is not copy that causes replies; it is copy that was sent to
people who were going to reply. A finding here is a HYPOTHESIS, and the
PROVEN LEARNINGS section should almost certainly be empty.

Report it anyway - a well-stated hypothesis with n is exactly what an
experiment gets designed from. But do not promote it.

## AND THE CLASSIFIER CAVEAT THAT DECIDES WHAT YOU MAY USE

    MEETING_INTENT   precision 1.00, recall 1.00   USABLE
    OBJECTION        precision 1.00, recall 0.67   USABLE, state recall
    INTERESTED       precision 0.44 on the OLD set, NEW SET UNMEASURED

**Build the positive set from MEETING_INTENT, not from INTERESTED.** More than
half of INTERESTED was wrong, because in outbound sales "interesting" is a
politeness marker and not an interest signal - "Sounds interesting, but..."
was a refusal 29 times out of 52. A positive set built on INTERESTED is
roughly half noise and every conclusion drawn from it inherits that.

## WHAT TO COMPARE

Length, opening type, question vs statement, CTA type, whether the product is
named and at which step, personalisation depth, and whether the sender is
identified. Say what you sampled and what the page budget was.

## DELIVERABLE

`docs/COPY-OUTCOME-PATTERNS-2026-09-15.md`. OBSERVATIONS with n, HYPOTHESES,
and PROVEN LEARNINGS almost certainly empty. Plus: which single hypothesis
would be the most valuable to test, and what testing it would cost.

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
