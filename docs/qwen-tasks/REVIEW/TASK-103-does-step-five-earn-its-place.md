PRIORITY: P2
DEPENDS: 

# TASK-103 - does step 5 generate INCREMENTAL value?

## THE QUESTION, STATED PRECISELY

Not "did somebody reply in a campaign that had five steps". That question has
been answered accidentally several times and means nothing. The question is:

    Of the people who did NOT reply to steps 1-4, what fraction replied to
    step 5 - and how does that compare to the cost of sending it?

That needs a DENOMINATOR per step, and the denominator is the hard part.

## WHAT IS ALREADY KNOWN, AND WHAT IS NOT

TASK-059 recovered reply counts by step position:

    step   1    2    3    4    5    6    7    8
    replies 157  103   49   83   29   19   65   23

and then said plainly that it could not provide denominators, because
campaign 352 alone is 95,459 scheduled emails across 6,364 pages. **That was
the right answer and it stands.** Absolute reply counts by step cannot answer
an incrementality question.

The 8.49% reply rate for 8-step sequences is UNREPRODUCED. Do not quote it.

## WHAT TO DO

**Sample deliberately and say what you sampled.** You cannot walk the estate;
you can walk ONE campaign completely. Pick the smallest campaign with a full
multi-step cadence and real sends, walk its scheduled emails exhaustively, and
compute per-step denominators for that one campaign. A complete answer about
one campaign beats an incomplete answer about twenty.

Then report, for that campaign:

    step, sent, replied, reply rate, positive rate
    survivors entering each step (sent at N minus replied before N)
    incremental replies attributable to each step

And state the page budget it cost, so the next person can decide whether to
buy the same measurement on a second campaign.

## WHAT NOT TO DO

- Do not extrapolate one campaign to the estate. Report it as one campaign.
- Do not infer a denominator from `meta.total`. Count rows WHERE `sent_at` IS
  PRESENT; campaign 274 reports 30,411 rows with zero sent in its first 100
  pages.
- Do not conclude "step 5 works" from a handful of replies. State n and
  confidence, and if n is too small to decide, say that.

## DELIVERABLE

`docs/STEP-INCREMENTALITY-2026-09-15.md`. If the honest conclusion is "this
cannot be decided at the budget available", that is a finding, and it tells
the operator what the answer would cost.

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
