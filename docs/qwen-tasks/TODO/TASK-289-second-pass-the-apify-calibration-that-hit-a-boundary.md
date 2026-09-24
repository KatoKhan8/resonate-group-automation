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

    BRANCH:
    COMMIT:
    THE BOUNDARY, NAMED AS A RULE:
    REAL or SUPPLIABLE (and what supplies it):
    EACH FIGURE AND ITS SOURCE:
    0.0513 vs 0.03987 RECONCILED (or why not):
    COST OF A ZERO-FACT RUN:
    RE-PRICED MONTHLY AT 19,612, LINKEDIN ONLY, ARITHMETIC SHOWN:
    INSIDE THE $199 SCALE PLAN, YES/NO:
    ACTOR ID -> HTTP STATUS TABLE:
    RECOMMENDATION: RE-DISPATCH / ESCALATE / CLOSE
