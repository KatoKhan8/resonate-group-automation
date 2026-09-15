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

## RESULT

**STATUS:** DONE

**COMMIT SHA:** acb0510

**TESTS:** No tests required - this is a read-only analysis task. The
analysis script (`scripts/copy_outcome_analysis.py`) was run against the
live EmailBison API and produced `docs/COPY-OUTCOME-PATTERNS-2026-09-15.md`.

**FILES CHANGED:**
- `docs/COPY-OUTCOME-PATTERNS-2026-09-15.md` — the deliverable report
- `scripts/copy_outcome_analysis.py` — the analysis script (reusable)

**FINDINGS:**

1. **The positive set is too small for comparison.** Of 12 MEETING_INTENT
   replies, 10 have null campaign_id and contain test/spam text. The usable
   positive set is n=2 (campaigns 262 and 352). No statistical comparison
   is possible.

2. **The negative set is n=173, of which 169 are unsubscribes.** Only 2 are
   OBJECTION (both from campaign 352, citing budget/time). The dominant
   negative signal is removal requests, not objections.

3. **Campaigns 327 and 328 dominate the unsubscribes.** These use heavy
   Liquid templates (~260-280 words per step, 5-8 steps each). One prospect
   counted 50+ "last note" emails from an 8-step campaign, suggesting a
   sequencing loop.

4. **Campaign 352 is the shortest and most conversational** (~67 words per
   step). It produced both MEETING_INTENT replies and unsubscribes. Shorter
   copy did not prevent negative outcomes.

5. **Template expansion makes rendered emails 2-3x longer than templates.**
   Sequence step templates average 112-220 words; rendered outgoing emails
   average 324-345 words.

6. **CTA presence, product naming, and sender identification do not separate
   the sets.** Both positive and negative campaigns have CTAs in 45-58% of
   emails, product naming in 5-7%, and sender identification in 14-17%.

7. **PROVEN LEARNINGS is empty.** No finding survives the sample-size
   objection. Three hypotheses are offered for testing:
   - H1: Shorter conversational copy produces fewer unsubscribes
   - H2: The sequencing problem in campaign 328 is producing avoidable harm
   - H3: Template expansion makes emails longer than the operator intended

**RISKS:**
- The sample is recency-biased (most recent 4,500 rows from cursor
  pagination). Older campaigns may be under-represented.
- The MEETING_INTENT classifier has 1.00 precision but the sample of 12
   includes 10 non-prospect emails, suggesting the classifier is catching
   meeting-intent phrases in spam/test mail that the production system
   would never see.
- No sent count is available from the reply feed alone, so unsubscribe
  *rates* cannot be computed. The absolute counts are reported.

**RECOMMENDED CLAUDE ACTION:**
1. **Audit campaign 328's send log** to determine if the sequencer is
   looping. This is read-only, costs no credits, and if a loop is found,
   the fix is operational rather than creative.
2. **Design an A/B test** comparing short conversational copy (campaign 352
   style) against heavy templated copy (campaign 327/328 style) with the
   same audience and cadence. Measure unsubscribe rate and reply rate.
3. **Consider whether the MEETING_INTENT classifier needs a campaign_id
   guard** to filter out non-prospect mail from the analysis set.
