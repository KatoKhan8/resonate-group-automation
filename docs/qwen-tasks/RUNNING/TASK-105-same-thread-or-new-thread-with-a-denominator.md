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

**STATUS:** REVIEW

**COMMIT SHA:** (pending)

**TESTS:** No code changes to test. This is a measurement and analysis task.
Verification script `scripts/task105_verify_control_group.py` walks all 22
campaigns and their step definitions via the provider API (READS ONLY) and
independently confirms the control-group finding.

**FILES CHANGED:**
- `docs/THREADING-EVIDENCE-2026-09-15.md` (new) — the deliverable
- `scripts/task105_verify_control_group.py` (new) — independent verification
- `scripts/task105_reply_pages.py` (new) — reply feed collection
- `scripts/task105_reply_comparison.py` (new) — reply comparison (initial)
- `scripts/task105_step2_sample.py` (new) — step-2 scheduled email sampling

**FINDINGS:**

1. **The no-control-group claim is PARTIALLY REFUTED.** Five archived
   campaigns (262-266) use `thread_reply=False` at step 2 with 3,163
   combined sends. TASK-080 missed these because it inspected 10 of 22
   campaigns. The control group EXISTS but is too small (3.2K vs 235K
   sends), too old (archived), and too structurally different (6-step
   sequences) for a clean observational comparison.

2. **Position-level analysis:** Positions 2 and 4 both have campaigns with
   thread_reply=True and False with sends > 0. Position 2 has a 62:1
   imbalance (treatment vs control). Position 4 is more balanced but the
   True campaigns (352, 274) differ structurally from the False ones.

3. **The 857/571 body-length numbers are survivorship-biased.** They
   measure emails that GOT REPLIES, not all sent emails. The TASK-080
   methodology is documented and reproducible but the underlying SQLite
   cache was not available in this worktree for independent re-derivation.

4. **The experiment design:** A within-campaign A/B test at step 2 with
   ~7,000 leads per arm would detect a 100% relative improvement
   (doubling the reply rate) at 80% power. This requires ~14,000 total
   step-2 sends.

**OBSERVATIONS (with n):**
- 22 campaigns in the estate (n=22), 20 with accessible step data
- 5 control campaigns at step 2 (n=5): 262-266, all archived, 3,163 sends
- 9 treatment campaigns at step 2 (n=9): 274, 327-335, 352, 235,651 sends
- The control campaigns' reply data is not accessible in the API's reply
  feed window (observed: 0 control replies in 750+ feed rows collected)

**HYPOTHESES:**
- The control campaigns (262-266) were the estate's earliest and may have
  different copy quality, audience, and sender characteristics from the
  treatment group. Even if their reply data were accessible, the confounds
  would prevent a clean comparison.
- The alternating F,T,F,T,F structure remains a design choice, not an
  evidence-backed one.

**PROVEN LEARNINGS:** (empty — nothing survives a sample-size objection
for the control group)

**RISKS:**
- The control group campaigns are archived and their reply data may be
  permanently outside the API's accessible window.
- The experiment design assumes a 0.5% baseline step-2 reply rate. If the
  true baseline is lower, the required sample size increases proportionally.
- The variant system may not support thread_reply divergence on the same
  parent step, requiring the split-campaign design instead.

**RECOMMENDED CLAUDE ACTION:**

1. **Acknowledge the partial refutation.** TASK-080's "no control group"
   claim was based on 10 of 22 campaigns. The control group exists but is
   too weak for observational inference.
2. **Run the experiment.** The design in `docs/THREADING-EVIDENCE-2026-09-15.md`
   specifies a within-campaign A/B test at step 2 with ~7,000 leads per arm.
3. **Do not quote 857/571 without the survivorship caveat.** The numbers
   describe replied-to emails, not all emails.
4. **Update TASK-080's findings** to reflect the control group discovery.
