# TASK-034 - Every LLM cost estimate for this client is out by 2.5x

Carried as OPEN P1 since the context-reset checkpoint and untouched since.

## THE DEFECT

Four cost estimators multiply by `cadence.GENERATED_KEYS`, which still reads
TWO generated emails. `productive_li_heavy_v1` generates FIVE emails and SIX
LinkedIn notes.

So every model-cost estimate for this client is low by about 2.5x on the email
half alone, and the LinkedIn half is not counted at all. The checkpoint records
the direction that matters: **the estimate is wrong in the direction that
makes a run look affordable.**

`PRODUCT-GAPS.md` already carries it. This closes it.

## WHY IT IS NOT COSMETIC

`enrich.spend()` and the waterfall ledger are what make credit spend auditable,
and a cap that was set from a 2.5x-low estimate is a cap that does not bind.
The handoff also records the real shape of a cohort: "a record now plans one
persona angle, five email drafts AND six LinkedIn notes - about twelve calls
rather than six", and that number should come from the cadence rather than
from a constant somebody has to remember to update.

## SCOPE

1. Find all four estimators. `grep -rn "GENERATED_KEYS" src/` and read every
   hit; name them in the result block.
2. Make the count come from the CADENCE the campaign actually runs, not from a
   module constant. The cadence already knows which steps are `generated` -
   `cadencelibrary` marks them - so the number is derivable and a second
   representation of it is what drifted here.
3. A cadence with no generated steps must estimate zero rather than a default.
4. Check whether anything CONSUMES the estimate before you finish. An estimate
   nobody reads is the defect this repository keeps finding; if the four
   estimators feed nothing, say so in FINDINGS and that becomes the finding.

## FILES ALLOWED

`src/costs.py`, `src/costsim.py`, `src/cadence.py`, `src/cadencelibrary.py`,
and whichever other estimator the grep turns up; `tests/`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/enrich.py` - `spend()` and the ledger are the audit and are not part of
this. `src/providerwrites.py`, `src/executionguard.py`, `work/**`.

## TESTS REQUIRED

- the estimate for `productive_li_heavy_v1` counts five emails and six notes;
- the estimate for a two-step cadence counts two;
- a cadence with no generated steps estimates zero;
- the number is read from the cadence, proved by changing the cadence in the
  test and watching the estimate move - not by asserting a constant.
