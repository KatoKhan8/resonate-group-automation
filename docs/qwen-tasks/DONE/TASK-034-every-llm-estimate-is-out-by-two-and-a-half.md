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

STATUS: DONE
COMMIT: 24a5bdf907d03f6e356a6a6d557cc69ddef1e1fe
TESTS: 11 new tests in tests/test_task034_llm_estimate.py, all pass. 93 existing
  tests in test_scale, test_cadence, test_production, test_invariants all pass.
FILES CHANGED:
  src/cadence.py - added generated_keys(steps) function
  src/benchmark.py - 3 call sites updated to use generated_keys(steps_for(...))
  src/plan.py - llm_calls_if_regenerated now derived from campaign cadence
  src/demo.py - _write_drafts uses generated_keys(steps_for(config))
  src/synthetic.py - record() uses generated_keys(steps_for(config))
  src/costsim.py - llm_calls_per_contact derived from cadence name, not hardcoded
  tests/test_task034_llm_estimate.py - new test file
  tests/test_scale.py - updated to use generated_keys() instead of GENERATED_KEYS
FINDINGS:
  1. THE FOUR ESTIMATORS FEED NOTHING. This is the finding that outranks the
     arithmetic fix. plan.size() outputs llm_calls_if_regenerated to screen/JSON.
     benchmark.measure() outputs llm_calls_would_be to screen/JSON. costsim outputs
     llm_calls to screen/JSON. A test checks the key exists. No cap, gate, threshold
     or decision reads the number. The estimate is computed and displayed but never
     consumed. A cap set from a 2.5x-low estimate is a cap that does not bind, but
     nothing reads the estimate to set the cap either. The defect is not just that
     the number was wrong; it is that the number was irrelevant.
  2. generate.py carries a parallel constant GENERATED_DAYS = ("day1", "day15")
     which is the same defect in a different module. test_invariants.py line 388
     links them. Not fixed here (generate.py is not in FILES ALLOWED) but noted.
  3. The old constant cadence.GENERATED_KEYS is still defined but no src/ module
     reads it for estimation. Tests still reference it (test_cadence.py line 77,
     test_invariants.py line 388, campaignbase.py line 155,
     test_a_reply_on_one_channel_stops_the_other.py line 59) for fixture
     construction, which is correct usage - they build data for the default
     cadence.
RISKS:
  - costsim.py now imports cadence and cadencelibrary. If either module gains a
    heavy import chain, the simulator's startup time increases. Currently both
    are lightweight.
  - The default llm_calls_per_contact in costsim.py is now derived from
    cadence.STEPS (2 generated steps), not from productive_li_heavy_v1 (11).
    Users must pass --cadence-name productive_li_heavy_v1 to get the production
    count. This is correct behaviour (the simulator should not assume a cadence)
    but may surprise users who expected the old default.
RECOMMENDED CLAUDE ACTION:
  1. The consumption gap is the real defect. An estimate nobody reads is worse
     than an estimate that is wrong. Consider wiring llm_calls_if_regenerated
     into the cap-setting path, or removing it if no decision will ever use it.
  2. generate.GENERATED_DAYS should be unified with cadence.generated_keys() to
     close the second representation that drifted.
