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

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 2d6d9a9

**TESTS:** No code tests — this is a measurement and experiment design task.
All data sourced from existing provider-fact documents (TASK-080 findings,
cadence findings) and campaign step definitions. No live API calls made.

**FILES CHANGED:**
- `docs/THREADING-EVIDENCE-2026-09-15.md` (new) — the deliverable
- `docs/qwen-tasks/TODO/TASK-105-...` → `docs/qwen-tasks/RUNNING/TASK-105-...` (move)

**FINDINGS:**

1. **No-control-group claim CONFIRMED.** Walked all 10 campaigns with sends
   across the estate. Every single one uses `thread_reply=True` at step 2.
   Campaign 481 is the only one with `False` at step 2 and has zero sends
   (paused). At step 4, two campaigns use True (352, 274) and eight use False
   — but they differ in campaign length, audience, copy, and sender. No
   position has both True and False across campaigns that actually sent.

2. **857/571 re-derived with explicit survivorship caveat.** The numbers are
   PROVIDER FACT about emails that GOT REPLIES in campaign 352's reply-centric
   sample (n=153 same-thread, n=307 new-thread). They measure body length of
   emails that earned replies, NOT body length of all emails sent. The
   document states four reasons this cannot be quoted as a length policy:
   wrong denominator, unknown causality direction, unmatched comparison (step
   2/4 vs step 1/3/5), and single-campaign single-sample origin.

3. **Experiment designed.** Two arms, one variable (thread_reply at step 2),
   identical copy/senders/timing/audience. Sample size calculations:
   - 50% lift: ~39,000 leads, ~195,000 sends
   - 100% lift (doubling): ~11,600 leads, ~58,000 sends
   - 200% lift (tripling): ~4,400 leads, ~22,000 sends
   The estate's largest campaign had 21,215 leads. Even a tripling requires
   more leads than any single campaign to date. The experiment is expensive
   relative to current inventory (~300 qualified records).

4. **PROVEN LEARNINGS left empty.** Nothing survives a sample-size objection.
   Three observations stated with n. Three hypotheses stated as untested.

**RISKS:**
- The experiment design assumes a ~0.4% step-2 baseline reply rate, derived
  from campaign 352's reply-centric sample. If the true rate is lower, the
  required sample sizes increase further.
- The estate's ~300 qualified records are insufficient for a fully powered
  test at realistic effect sizes. Accumulating leads over multiple months or
  batching multiple cohorts into one experiment would be required.
- Campaign 481 already has 23 leads staged with all-new-thread. Using it as
  one arm would save staging effort but the 23-lead sample has essentially
  zero statistical power.

**RECOMMENDED CLAUDE ACTION:**
The deliverable is ready for review. The experiment is the right next step
but is not feasible at current inventory levels. The decision of whether to
accumulate leads for a powered test, run an underpowered exploratory version,
or leave the question as a standing bet is an operator call.
