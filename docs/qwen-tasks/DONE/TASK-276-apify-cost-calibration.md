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

## STAGE: DONE — 2026-09-24, by the production session on master

**Not by a Qwen worker, and taken out of TODO so nobody spends the money a
second time.** Lane 1 was asked for the same measurement by the operator
directly and ran it: `scripts/researchpack_pilot.py`, 24 accounts, cold
cache, from 18:06Z.

The full answer is `docs/RESEARCH-PACK-PILOT-2026-09-24.md`. The short of it,
against this task's four questions:

1. **Per actor, per account, measured from Apify's own run records** - site
   crawl $0.02888, jobs $0.00335, person posts $0.00265, company posts
   $0.00260, slug resolver $0.00238. **$0.03987 per account.**
2. **Proxy cost, separated from compute: there is none.** Every actor ran on
   the automatic DATACENTER pool, nothing was blocked, and no input names a
   proxy group - so no residential cost arises and none is reported.
3. **A run that returns zero facts still costs.** A 0-result harvestapi run
   is $0.00105 (start + the actor's own `no-result` event); a 0-result jobs
   run is $0.0001; a failed crawl is billed for the compute it used - 2 of 24
   crawls failed and were billed.
4. **19,612 accounts x $0.03987 = $781.94/month against a $199 budget -
   3.93x over.** The arithmetic and four alternative shapes are in the doc.
   The binding constraint is the website crawler at 72% of the bill, not
   LinkedIn.

**This task's own premise was right and understated.** The figures were not
merely placeholders: the three LinkedIn actor ids were invented and answer
404, so nothing had ever run. And the `open_roles` coverage this task quotes
as "8 of 23 domains" is itself too high - 50 of the 71 rows behind it were a
different company (ISSUE-036), so the corrected figure is 3 of 24.

`GET /users/me/limits` was not used: `GET /users/me/usage/monthly` carries
`totalUsageCreditsUsdAfterVolumeDiscount`, which is the same not-self-reported
figure, and the per-RUN `usageTotalUsd` attributes it per actor, which the
account total cannot.
