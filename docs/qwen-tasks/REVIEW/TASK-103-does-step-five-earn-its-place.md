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

**COMMIT SHA:** 07856a8

**TESTS:** N/A — analysis task, no code change to test. Script syntax verified
with `py_compile`.

**FILES CHANGED:**
- `docs/STEP-INCREMENTALITY-2026-09-15.md` — the deliverable
- `scripts/task103_step_incrementality.py` — analysis script

**FINDINGS:**

Campaign 330 (Dutch, 8-step, 4,028 sends, completed) was walked exhaustively:
all 289 pages, 2,714 sent rows with `sent_at` present, 100 replies collected
via campaign-scoped endpoint.

Per-step sent: 715→656→559→411→278→69→25→1. Clear monotonic decay.

Per-step replies (22 attributed of 27 human): 9→6→4→2→1→0→0→0.

Step 5 specifically: 278 sends, 1 reply, 1 purely incremental (the lead did
not reply at steps 1-4). n=1 is LOW confidence — a single data point, not a
finding.

Steps 6-8 combined: 95 sends, 0 replies. Suggestive but denominators are
very small.

`lead_id` is NULL in the scheduled email API response, blocking unique-lead
denominators per step. The survivor count at step 5 cannot be computed from
this API.

Three smaller campaigns (263, 266, 264) had zero human replies — all their
"replies" were bounces. This is itself a finding: the smallest campaigns in
the estate did not generate any human engagement.

**PROVEN LEARNINGS:** Empty. One campaign is a sample, not a finding. The
task rules say to leave this empty when nothing survives a sample-size
objection, and n=1 at step 5 does not survive it.

**RISKS:**
- The `lead_id` gap in the API means we cannot compute the key metric the
  task asked for: "of the people who did NOT reply to steps 1-4, what
  fraction replied to step 5." We can count the numerator (1) but not the
  denominator (survivors entering step 5).
- The 67.4% coverage gap between `emails_sent` (4,028) and sampled sent rows
  (2,714) means some sends are not accounted for.

**RECOMMENDED CLAUDE ACTION:**
1. Read `docs/STEP-INCREMENTALITY-2026-09-15.md` for the full analysis.
2. The honest answer to "does step 5 earn its place?" is: **one campaign
   says yes (1 incremental reply from 278 sends), but n=1 is not enough to
   decide.** A second campaign measurement is needed.
3. The next campaign to measure would be 352 (1,512 replies, 5 steps) but
   its 6,189 pages exceed the 500-page accessible range. A sampled approach
   or a vendor-side filter would be needed.
4. The `lead_id` absence from the scheduled email API is a structural gap.
   Without it, incrementality analysis cannot compute survivor denominators.
