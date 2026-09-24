PRIORITY: P1
DEPENDS:

# TASK-276 — what an Apify research pack actually costs, per actor

The pilot reported "36 ledger units for $0.0513" and the slack-agent session
recorded those figures as **placeholders**. A cost model nobody has checked
against a real invoice is a guess with a decimal point.

Apify is on the **Scale** plan: 199 USD prepaid, 128 concurrent runs, 200
datacenter proxies. The operator has removed the 20 USD pilot cap and wants
cost per account reported per source.

## What to measure

For each actor the research pack drives - open roles, company posts, person
posts, site content - measure against the ACCOUNT's own usage figures, not a
self-reported estimate:

1. compute units consumed per run, and per account
2. proxy cost, separated from compute
3. what a run costs when it returns ZERO facts, because that is most of them
   today: open_roles covered 8 of 23 domains, person posts 5 of 8
4. the projected monthly cost at 19,612 accounts, arithmetic shown

`GET /users/me/limits` carries `current.monthlyUsageUsd`. Take it before and
after a bounded run and difference it. **That is the only figure that is not
a self-report.**

## Rules

- BOUND every run. 20-30 accounts maximum. This spends real money.
- Never print a credential value, and never print the account's proxy
  password - a previous session leaked it by filtering what to HIDE instead
  of naming what to SHOW. Print named fields only.
- Datacenter proxies unless an actor is blocked; residential only for that
  actor, and report the cost difference.
- `work/` is gitignored; never commit it.
- Commit on your own branch. Do not merge.

## Result block

    BRANCH:
    COMMIT:
    USD PER ACCOUNT, PER SOURCE:
    COST OF A ZERO-FACT RUN:
    PROJECTED MONTHLY AT 19,612:
    WHERE THE PLACEHOLDER FIGURES WERE WRONG:

---

## STATE RECORDED BY LANE E, 2026-09-24 late

    ATTEMPTED BY     a Qwen worker, 2026-09-24
    STATE            BLOCKED - boundary hit (moved out of TODO/ tonight)
    ON MASTER        NO
    NEXT             TASK-289 - second pass. Name the boundary as a RULE,
                     classify it REAL or SUPPLIABLE, and say which figures
                     survive.

Two cost figures are in circulation and they are not from the same run: this
task's own "36 ledger units for $0.0513" (recorded as a PLACEHOLDER) and the
production session's measured $0.03987/account, $781.94/month at 19,612 -
3.93x over the $199 Scale budget, of which the website crawler is 72%.

Since then the operator has ruled: site content comes from our own free
crawler, and Apify runs LinkedIn only. Any calibration that priced the
website crawler as part of the pack is pricing something we will not buy, so
the re-price is part of the second pass rather than a re-run of this task.
