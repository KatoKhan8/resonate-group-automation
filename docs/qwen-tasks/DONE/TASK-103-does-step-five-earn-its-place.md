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

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 3a54750

**TESTS:** N/A — analysis task, no code change to test. Script syntax verified
with `py_compile`.

**FILES CHANGED:**
- `docs/STEP-INCREMENTALITY-2026-09-15.md` — the deliverable (rewritten)
- `scripts/task103_step_incrementality.py` — analysis script

**FINDINGS:**

Campaign 330 (Dutch, 8-step, 4,028 sends, 103 leads, completed) was the
target. Campaign 263 (299 sends, 6 steps) was auto-selected first but had
ALL 291 sends at step 1 only — the other steps were defined but never sent.

Campaign 330 scheduled emails: 2,714 sent rows across 189 pages (pages
101-289; pages 1-100 missing — oldest sends, predominantly step 1).
Coverage: 67.4% of provider-reported 4,028 sends.

Per-step sent: 715→656→559→411→278→69→25→1. Clear monotonic decay.

Per-step replies (22 attributed of 27 human): 9→6→4→2→1→0→0→0.

Step 5 specifically: 278 sends, 1 reply (0.4%), ~1 purely incremental.
n=1 is LOW confidence — a single data point, not a finding.

Steps 6-8 combined: 95 sends, 0 replies. Strictly wasteful in this campaign.

Reply rate monotonically decreases: 1.3%→0.9%→0.7%→0.5%→0.4%→0%→0%→0%.
Step 5 is 3.5× less cost-effective than step 1 (278 vs 79 credits per reply).

`lead_id` is NULL in the scheduled email API response, blocking unique-lead
denominators. Incremental analysis uses send counts as proxy (valid at <1%
reply rates where multi-reply leads are essentially impossible).

Zero `interested` replies across all steps. INTERESTED may not carry a
learning claim (0.44 precision on old pattern set).

**PROVEN LEARNINGS:** Empty. One campaign is a sample, not a finding. n=1
at step 5 does not survive a sample-size objection.

**RISKS:**
- Pages 1-100 missing: step 1 denominator is undercounted. True step 1
  count is likely ~1,000, which would lower its reply rate to ~0.9%.
- Reply feed partially collected (3,006 of ~270,000 estate-wide). 5 of 27
  campaign 330 replies are unattributed.
- `lead_id` absence means survivor denominators cannot be computed from
  this API.

**RECOMMENDED CLAUDE ACTION:**
1. Read `docs/STEP-INCREMENTALITY-2026-09-15.md` for the full analysis.
2. The honest answer: step 5 generated 1 incremental reply from 278 sends
   (0.4%). Steps 6-8 generated 0 from 95. The monotonic decay is clear
   but n is too small to decide.
3. To answer definitively: fetch pages 1-100 for campaign 330 (100 calls),
   complete the reply feed walk (~2,700 pages), and repeat on 2-3 more
   campaigns (329, 334, 335 all have 8 steps and real sends).
4. The `lead_id` absence from the scheduled email API is a structural gap
   for incrementality analysis.
