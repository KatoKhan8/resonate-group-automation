PRIORITY: P1
DEPENDS:

# TASK-169 - the cheapest order from a verdict to campaign-ready

## WHERE THIS SITS

The operating objective is TIME TO CAMPAIGN-READY ACCOUNT, not finishing the
input file in the order it arrived. Those two goals disagree, and the estate is
where they disagree most:

    316 queued, no facts, no research    <- TASK-163 is finding the free path
    20,944 domains in the estate         <- the intake behind them
    ~471 credits for 150 records         <- TASK-160's enrichment projection
    3.14 credits per record              <- measured, not assumed

Enrichment is the first stage that costs money. Everything before it is free
or nearly so. So the order in which records reach enrichment decides how much
campaign-ready inventory a fixed credit budget buys.

TASK-155 measured the shape of what comes out the far end: 97 LinkedIn-eligible
contacts, 17 email, 39 eligible for both, and persona is the only honest cohort
dimension because signal is 100% null and angle is 79% null.

## THE QUESTION

Given a fixed credit budget, what order maximises campaign-ready accounts?

1. **Yield per credit, measured backwards.** Take the 300 records that went all
   the way through. For each, what did it cost and did it produce a
   campaign-ready contact? Group by whatever the record knew BEFORE enrichment
   ran - ICP score, segment, headcount, persona, geo, whatever the data
   actually carries. Which pre-enrichment signals predict a record that
   survives to CAMPAIGN_READY?
2. **The rejection rate we can see for free.** TASK-152 measured the 250 as
   skewed to micro-agencies, median 5 employees, and projected ~40% ICP
   rejection. A record that cheap gates will reject must never reach a paid
   call. Which free fields, present at intake, predict rejection? Quantify the
   credits that ordering alone saves.
3. **The drop-off between paid and ready.** 91 enriched, 67 verified, 32
   campaign-ready. So roughly two thirds of enrichment spend did not produce a
   campaign-ready contact. Where exactly does it go - verification failure,
   gate rejection, collision, missing company name? Attribute the loss stage by
   stage, with counts.
4. **The recommendation.** A concrete ordering rule, expressed as a predicate
   over fields that exist before enrichment, plus the projected credits per
   campaign-ready account under that rule versus the arrival order we use now.

## THE TRAP

The prize here is spending fewer credits per campaign-ready account. The
cheapest way to appear to win is to pick the records that pass most easily and
call that an improvement, which is ordering, not qualification - and it becomes
gate-weakening the moment a threshold moves. Do not touch a threshold. The
ordering rule may only change WHICH records go first, never WHETHER a record
passes.

Second trap: 91 enriched is a small sample and the 300 came from one purchased
list. A predictor fitted to 91 records will overfit. Report a confidence and
say which findings would not survive a different list.

## WHAT YOU MAY NOT DO

- No paid provider calls. No enrichment run, no Apify, no credit spend. This
  is measurement over records that already went through.
- No provider writes.
- Do not change a gate, a threshold, or an ICP rule. The deliverable is an
  ORDER, not a policy.
- Never commit PII. Hash record identifiers and domains.

## FILES ALLOWED

    docs/ENRICHMENT-ORDER-2026-09-16.md   (new)
    scripts/task169_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The pre-enrichment predictors of survival with their counts, the free-field
rejection predictors and the credits ordering saves, the stage-by-stage
attribution of the two thirds that never became campaign-ready, the ordering
predicate, and the projected credits per campaign-ready account before and
after.
