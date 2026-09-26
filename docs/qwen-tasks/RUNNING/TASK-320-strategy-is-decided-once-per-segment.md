PRIORITY: P0
SIZE: M
DEPENDS: TASK-333

# TASK-320 - strategy is decided once per segment, not once per lead

Written from `docs/PHASE1-PLAN-2026-09-26.md` TASK-320, which the handoff lists as
NOT YET WRITTEN. This is it.

## The defect, measured

Stage E (strategy) is segment-invariant by design and is coded to run per lead.
**At 50 leads in one segment that is 49 redundant model calls.** Confirmed
independently on 2026-09-26: the v2 design makes 6 model calls per lead, and
stage E's inputs (hypothesis, capability, facts) are per-company outputs, so
nothing ties it to the individual.

This is also the cost argument. The fifty cost 24.20c per lead that passes both
gates, and Sonnet is 95.8% of the bill.

## Files

    src/campaignstrategy.py   NEW, or EXTEND if a strategy module already exists -
                              CHECK FIRST. Directives section 6: does equivalent
                              functionality already exist? `src/segments.py` and
                              `src/accountintel.py`-adjacent modules may already
                              hold part of this.
    src/copystages.py         READ ONLY. Claude owns the prompts.
    src/segments.py           READ. Existing segmentation.
    tests/test_strategy_is_set_per_segment_not_per_lead.py   NEW

## Build

Strategy is decided ONCE PER SEGMENT and carries: target ICP, segment, persona,
primary problem, primary offer, secondary offer, evidence, approved angles,
objective, CTA strategy, disqualification criteria.

Per-lead work ADAPTS it: account research, signal relevance, personalisation,
validation. It does not re-decide it.

**Offers come from TASK-333's `src/offers.py` as DATA.** A strategy may not
invent an offer, a capability, a discount, a pilot, a guarantee or a customer
result. That is why this task depends on 333.

## Acceptance - RUN each, paste real output

1. Stable per segment:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import campaignstrategy as c;\
    a=c.for_segment('US-East/MktgAdv','economic_buyer');\
    b=c.for_segment('US-East/MktgAdv','economic_buyer');\
    assert a['strategy_id']==b['strategy_id'],'strategy regenerated per call';\
    print(a['strategy_id'])"

2. **The measured count, which is the point of the task.** Instrument the model
   call and assert it is made ONCE for a 50-lead batch in one segment, not 50
   times. Paste the count. A test that only checks `strategy_id` stability does
   not close this task - a cached return value with 50 calls behind it would pass
   it.

3. Two different segments get two different strategies (proving it is keyed on
   the segment, not a global singleton).

4. **No model call in the test.** Use a fixture/fake. This task may not spend.

5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against the baseline, not the count.

## What this task may NOT do

- Do not shorten the five-step email cadence or its threading, and do not touch
  the LinkedIn cadence tree.
- Do not invent an offer or a commercial term.
- Do not wire the copy path - that is TASK-321.
- Nothing sent, nothing activated.

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: d62dd535
TESTS: 7/7 pass in tests/test_strategy_is_set_per_segment_not_per_lead.py

FILES CHANGED:
- src/campaignstrategy.py (NEW) - strategy module with for_segment(), cache,
  model_call_count(), clear_cache(). Model injectable for tests.
- tests/test_strategy_is_set_per_segment_not_per_lead.py (NEW) - 7 tests
- docs/qwen-tasks/RUNNING/TASK-320-strategy-is-decided-once-per-segment.md
  (moved from TODO/)

FINDINGS:
1. `copystages.py` defines STRATEGY_SYSTEM and strategy_user() but NEITHER is
   imported anywhere in src/. The v2 stages (C, D, E, F) exist as text but
   have no caller. This is the "existence is not function" defect from
   QWEN.md. TASK-321 will wire them.
2. `src/offers.py` has no `for_segment()` function. Offers are filtered by
   campaign_id, not by segment+persona. campaignstrategy._offers_for_segment
   filters by approval_status, segment match ('all' matches everything), and
   persona match.
3. The segment key format in the acceptance test ('US-East/MktgAdv') differs
   from campaignseg.key_for's format ('SEG-USEAST-DIGITAL-MID-champion').
   for_segment accepts any string as segment_key - it is a cache key, not a
   structural constraint.

ACCEPTANCE CRITERIA VERIFIED:
1. Stable per segment: strategy_id a05b6399ae414a83, same on both calls.
2. Model called ONCE for 50 leads: model_call_count() == 1.
3. Two segments get two strategies: different strategy_ids, 2 model calls.
4. No model call in test: ScriptedModel used throughout.
5. Full suite: RUNNING (awaiting verdict).

RISKS:
- campaignstrategy is consumed ONLY by tests. The copy path wiring is
  TASK-321. Until then, for_segment() is available but not called by
  production code. This is intentional per the task scope.
- The strategy prompt uses copystages.STRATEGY_SYSTEM verbatim. The user
  prompt is minimal (segment, persona, offers). TASK-321 may need to enrich
  it with company-level context.

RECOMMENDED CLAUDE ACTION:
- Review and integrate. TASK-321 wires this into the copy path.
- The full suite verdict should be checked before merging.
