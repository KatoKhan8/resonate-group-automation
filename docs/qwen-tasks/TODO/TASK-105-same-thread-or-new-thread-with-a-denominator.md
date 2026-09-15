PRIORITY: P2
DEPENDS: 

# TASK-105 - same-thread vs new-thread, and the missing control

## THE STATE OF THIS QUESTION

TASK-080 measured it and the result was turned into a standing design: later
steps are same-thread follow-ups rather than a new subject every time.

**But the estate has NO CONTROL GROUP.** Every campaign with sends uses
`thread_reply=True` at step 2. Campaign 481 is the only one with False there
and it has zero sends. So the comparison that would settle it does not exist
in the data, and the alternating structure is recorded as a BET.

The one number that exists: same-thread follow-ups that got replies average
857 characters against 571 for new threads. That is survivorship - measured
only on emails that GOT replies - so it says nothing about whether length or
threading causes replies.

## WHAT TO DO

1. **Confirm or refute the no-control-group claim.** Walk the campaign
   configurations across the estate and report how many campaigns use
   `thread_reply=False` at any step, and how many of those have sends. If a
   control group exists after all, that is the most valuable finding available
   and the rest of this task becomes a real comparison.
2. If there is genuinely no control, **design the experiment that would settle
   it**: what two arms, what sample size for what effect size, on what cohort,
   and what it would cost in sends. Do not run it.
3. Re-derive the 857/571 numbers and state their survivorship caveat
   explicitly alongside them, so they cannot be quoted bare.

## WHAT NOT TO DO

- Do not reintroduce a length instruction to the follow-up addendum in either
  direction. A test pins that it asserts no length, and that test is correct.
- Do not present the bet as evidence.

## DELIVERABLE

`docs/THREADING-EVIDENCE-2026-09-15.md`: what is known, what is bet, and the
experiment design that would convert the second into the first.

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
