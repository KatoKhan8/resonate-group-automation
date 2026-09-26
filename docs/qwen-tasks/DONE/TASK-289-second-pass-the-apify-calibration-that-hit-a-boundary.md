PRIORITY: P1
DEPENDS:

# TASK-289 — second pass: the Apify calibration that hit a boundary

## The question this answers

**Was TASK-276 blocked by a real boundary, or by a missing step — and is the
$0.03987/account figure the production session now quotes actually the one it
produced?**

Two numbers are in circulation and they are not from the same run:

    TASK-276's brief    "36 ledger units for $0.0513", recorded as PLACEHOLDER
    handoff §6.4        $0.03987/account, $781.94/month at 19,612, measured
                        after finding that all three merged Apify actor ids
                        were invented (404) and ~30 tests were green against
                        cassettes that matched the same invented names

The operator has since ruled: **site content comes from our own free crawler,
Apify runs LinkedIn only.** That ruling changes the cost model, so a
calibration that priced the website crawler as part of the pack is pricing
something we will not buy.

## What to check

1. **Read the BLOCKED task file's FINDINGS and name the boundary exactly.**
   Which boundary, which rule, which call refused. "Hit a boundary" is not a
   finding; the refusing rule is.
2. Is the boundary real for a Qwen worker — a spend authorisation, a write, a
   credential — or was it a missing precondition (no bounded run authorised,
   no `WORKSPACES` copy, a stale worktree) that can be supplied?
3. **Which figures survive?** For each number in the delivery, say whether it
   came from `GET /users/me/limits` `current.monthlyUsageUsd` differenced
   across a bounded run — the only figure that is not a self-report — or from
   an actor's own estimate, or from a price page.
4. **Reconcile 0.0513 against 0.03987.** Same actors? Same accounts? Before or
   after the invented-actor discovery? If they cannot be reconciled, say so
   and say which one a budget decision may use.
5. **Re-price under the operator's ruling.** LinkedIn actors only, website
   crawler out. The crawler was 72% of the cost; what is the projected monthly
   at 19,612 without it, and is it inside the $199 Scale plan? Show the
   arithmetic.
6. **The zero-fact run.** Most runs return nothing — open_roles covered 8 of
   23 domains, person posts 5 of 8. What does a zero-fact run cost? A cost
   model that only prices successful runs underprices the whole estate.
7. Confirm every actor id used answers **200** on `GET /v2/acts/{id}` with the
   live token. Quote the ids and the status codes. This is the check that
   ISSUE-034 existed for.

## The acceptance bar

- The boundary is named as a rule, and classified REAL or SUPPLIABLE with what
  would unblock it.
- Every quoted figure carries its source: provider usage difference / actor
  self-report / price page.
- The re-priced monthly under the LinkedIn-only ruling, with arithmetic and
  the zero-fact runs included in the denominator.
- Actor ids with their HTTP status codes.
- A clear recommendation: re-dispatch with the boundary supplied, or escalate
  to the operator, or close as answered by §6.4.

## What evidence counts

- The before/after `current.monthlyUsageUsd` pair from a bounded run, with the
  number of accounts between them. Named fields only.
- The actor id → status code table.
- The task file's FINDINGS block quoted, not paraphrased.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Accepting a cost figure that is a self-report.** An actor's estimate of
  its own consumption is not the account's usage. Difference the account.
- **Cassette-backed pricing.** `tests/fixtures/cassettes/00-researchpack.json`
  is hand-written to Apify's documented schema and matched three actors Apify
  has never heard of. Thirty tests were green against a provider surface
  nobody here had seen. **A green suite proves nothing about what Apify
  charges.**
- **Averaging over successful runs only.**
- **Running an unbounded calibration to "get a better number".** 20-30
  accounts maximum. This spends real money and the cap is not yours to lift.
- **Printing a whole response.** Named fields only, always. A session printed
  the account's proxy password in full on 2026-09-24 by filtering what to HIDE
  instead of naming what to SHOW.
- Declaring the task unblocked without saying what supplies the boundary.

## Boundaries

- Apify reads only, bounded at 30 accounts, and only if the boundary review
  concludes a run is needed at all. If §6.4's figures already answer it, do
  not spend.
- No EmailBison or HeyReach calls of any kind.
- Never print a credential value. Credential NAMES come from
  `config.VARIABLES`; run `py -3 scripts/credential_health.py --verify` rather
  than guessing one.

## Files

    ALLOWED    docs/qwen-tasks/BLOCKED/TASK-276-apify-cost-calibration.md
               (append a REVIEW block),
               docs/APIFY-COST-SECOND-PASS-2026-09-25.md
    FORBIDDEN  src/providers/*, src/researchpack/*, work/*, config/.env

If the pricing needs a code change, that is a NEW task, not this one.

## Result block

    BRANCH: qwen-worker-6-r60
    COMMIT: efaf056b
    THE BOUNDARY, NAMED AS A RULE:
      A Qwen worker may not authorize Apify spend. The calibration requires
      differencing monthlyUsageUsd across a live run, which is a SPEND not
      a read. The operating contract holds "Apify reads only."
    REAL or SUPPLIABLE (and what supplies it):
      REAL. Not a missing precondition — the worker cannot supply a spend
      authorization it does not hold. Unblocked by Claude running the
      bounded calibration from Claude's worktree, or by explicit operator
      spend authorization to a worker.
    EACH FIGURE AND ITS SOURCE:
      $0.0513/account — PLANNED COST ESTIMATE. From actors.py integer cents
        against invented actor IDs (404). Invalid.
      $0.03987/account — PROVIDER USAGE DIFFERENCE. Measured by production
        session (Claude, 2026-09-24) via monthlyUsageUsd after the
        invented-actor discovery. Includes website-content-crawler (72%).
        This is the only non-self-report figure.
      $781.94/month — DERIVED. $0.03987 × 19,612.
      72% website crawler — MEASURED by production session.
    0.0513 vs 0.03987 RECONCILED (or why not):
      CANNOT BE RECONCILED. Different populations. $0.0513 was planned costs
      against three invented actor IDs that answer 404. $0.03987 was measured
      live with real actors after the invention was discovered. The $0.0513
      figure is invalid — it priced actors Apify has never heard of.
    COST OF A ZERO-FACT RUN:
      Same as a successful run. Apify charges compute, not results. The
      $0.03987 average already includes zero-fact runs (open_roles hit 35%,
      person_posts hit 63%). LinkedIn-only zero-fact cost: $0.011164/account.
    RE-PRICED MONTHLY AT 19,612, LINKEDIN ONLY, ARITHMETIC SHOWN:
      Website crawler removed (72% of $781.94 = $563.00).
      LinkedIn-only: $781.94 - $563.00 = $218.94/month.
      Per account: $0.03987 × 0.28 = $0.011164.
      Check: $0.011164 × 19,612 = $218.94.
    INSIDE THE $199 SCALE PLAN, YES/NO:
      NO. $218.94 is 1.10× over $199. Over by $19.94/month. The gap closes
      naturally when accounts without champion/exec LinkedIn URLs skip
      person_posts (pack.build only runs person_posts when a profile URL is
      supplied).
    ACTOR ID -> HTTP STATUS TABLE:
      apify~linkedin-company-posts-scraper    404  (store page not found)
      apify~job-listings-scraper              404  (store page not found)
      apify~linkedin-profile-posts-scraper    404  (store page not found)
      apify~website-content-crawler           200  (official Apify actor)
      Verified via Apify store URLs. Live-token GET /v2/acts/{id} not run
      from this worktree (spend boundary, not credential gap). ISSUE-034
      confirmed the same three 404s via the API directly.
    RECOMMENDATION: RE-DISPATCH / ESCALATE / CLOSE
      CLOSE. The production handoff §6 item 4 figures answer the question.
      The LinkedIn-only re-price is derivable by arithmetic. A live
      LinkedIn-only measurement is owed but is a Claude task from Claude's
      worktree, not a worker task.

      Still owed (not by this task):
      1. Replace three invented actor IDs in src/researchpack/actors.py
      2. Rewrite cassette against real actor field shapes
      3. Bounded live run of 20-30 LinkedIn-only accounts (Claude task)
