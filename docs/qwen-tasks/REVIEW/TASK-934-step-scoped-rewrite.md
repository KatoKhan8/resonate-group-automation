PRIORITY: P0
SIZE: M
DEPENDS: 

# TASK-934 — rewrite the FAILING step, keep the clean ones

**Operator decision, Zvonimir, 2026-09-30: APPROVED as a live-path defect
fix, not a feature.**

## The defect

The writer emits a whole set, so `_refuse_partial_regeneration` forbids
rewriting one step and every attempt re-rolls all eleven messages. Measured
2026-09-30 across fourteen candidates and two models: a draft where eight or
nine messages were already gate-clean was thrown away because one step
failed, and the next attempt broke a different one. Joint satisfaction of
about fifteen constraints across eleven messages by repeated whole-set
sampling is the wrong shape, and it is why no contact has ever cleared.

## What to build

Rewrite ONLY the failing step, keeping the gate-clean steps fixed.

## THE GUARDS, AND THEY ARE THE OPERATOR'S OWN WORDS

1. **The rewritten step receives the FULL SEQUENCE CONTEXT** - the other
   steps, the thread, its rung, the offer, the licensed facts. A step
   rewritten blind will repeat a sibling or break the thread.
2. **After EVERY rewrite the WHOLE SEQUENCE is re-gated**, including
   `quality.repetition_across_rungs` and `sequencegate`. **A rewrite that
   makes a sibling fail is REFUSED.** This is the guard that makes the whole
   thing safe: a step is never accepted on its own merits alone.
3. **Bounded retries per step**, then HELD with the exact reason. No
   unbounded loop.
4. **The approval hash is computed over the FINAL FULL SEQUENCE only** -
   never per step, never over an intermediate state.
5. **Storage stays all-or-nothing on the final approved set.** Per channel,
   as `_adapt_plan_to_cadence` now does (f9387d60).

## RULES

- **Do not weaken any gate.** Every check that refuses today must refuse
  after this. The point is to stop discarding clean work, not to lower a bar.
- `_refuse_partial_regeneration` exists for a stated reason - read it and its
  comment before changing anything. If a whole-set rewrite is still the right
  answer for some case, say so rather than removing the guard.
- Do not touch `claims.py`, `copylint.py`, `sequencegate.py`, `evidence.py`,
  `approval.py` or anything under `src/providers/`.
- Mutation check mandatory: break your own fix, prove the intended test goes
  red for the intended reason, restore, verify by sha256, and **clear
  `__pycache__` before re-running** - a cp-based restore leaves stale
  bytecode and the restored file then tests exactly like the mutated one.

## TESTS THAT MUST EXIST

1. one failing step among clean siblings is rewritten and the siblings are
   BYTE-IDENTICAL afterwards;
2. a rewrite that makes a sibling fail is REFUSED and nothing is stored;
3. bounded retries, then HELD with the exact reason;
4. the approval hash covers the final full sequence, not a step;
5. a sequence that never converges stores nothing.

## RETURN

### ROOT CAUSE

The campaign writer (`_process_contact` in `generate_campaign.py`) emits all
eleven messages in one call. When the validate callback (lint, claims,
repetition) refuses one step, the retry loop discards the clean siblings and
re-rolls the whole set. Joint satisfaction of ~15 constraints across 11
messages by repeated whole-set sampling is the wrong shape.

### FILES CHANGED

- `src/generate_campaign.py`: Added `_rewrite_failing_steps`,
  `_identify_failing_steps`, `_rebuild_gate_inputs`, `_step_channel`,
  `MAX_STEP_REWRITES=3`. Modified the retry loop in `_process_contact` to
  call `_rewrite_failing_steps` when copylint passes but validate fails
  (per-step gates), starting from attempt 2.
- `src/copystages.py`: Added `STEP_REWRITE_SYSTEM`, `step_rewrite_user`,
  and imported `LINKEDIN_WRITER_KEYS` from `cadencelibrary`.
- `tests/test_task934_step_scoped_rewrite.py`: 13 tests covering all 5
  required guards plus helpers.

### TESTS

All 13 new tests pass:
- `test_failing_step_rewritten_siblings_unchanged` - siblings BYTE-IDENTICAL
- `test_sibling_breakage_refuses_everything` - refuses + names sibling
- `test_exhausted_rewrites_hold_with_reason` - bounded then HELD
- `test_retries_are_bounded_not_unbounded` - model calls <= MAX_STEP_REWRITES
- `test_hash_changes_when_any_step_changes` - approval hash covers full seq
- `test_hash_is_stable_for_same_sequence` - stability
- `test_never_converging_stores_nothing` - empty sequences on failure
- Plus 6 helper tests (prompt, channel, identify)

Mutation check: removed sibling breakage guard -> test goes red for the
intended reason ("sibling" not found in hold message). Restored, SHA256
verified, __pycache__ cleared, all 13 green.

Pre-existing failures in `test_generate` (3) and
`test_campaign_repetition_integration` (5) are NOT caused by this change
(verified by stashing and running on original code).

### SHA

src/generate_campaign.py: d107dca10eab731fc0e02043a3069c1a686f73aec421cb2af026fb49881540b0
src/copystages.py: 4b11c5575e7d5e5122028811afbf0d126801f848ce71346690377336af73ab82

### WHY THIS DOES NOT WEAKEN A GATE

1. No gate is modified. `lint.check`, `claims.check`, `copylint.check_batch`,
   `sequencegate.check`, and `quality.gate` are all unchanged.
2. `_refuse_partial_regeneration` is NOT touched. It still refuses the old
   path (rewriting one step through the batch writer). The step-scoped
   rewrite is a NEW path that asks for ONE step only.
3. The whole sequence is re-gated after EVERY rewrite, including batch-level
   gates (copylint, sequencegate). A rewrite that passes per-step gates but
   fails batch gates is still refused.
4. A rewrite that makes a sibling fail is REFUSED and nothing is stored.
5. Storage stays all-or-nothing per channel via `_adapt_plan_to_cadence`.
6. The approval hash is computed over the final full plan, never per step.
7. `MAX_STEP_REWRITES=3` is bounded. A step that cannot clear in 3 attempts
   is HELD with the exact reason.

### CALLER CHAIN

- `_rewrite_failing_steps` (generate_campaign.py:275) is called from
  `_process_contact` (generate_campaign.py:1487)
- `step_rewrite_user` (copystages.py:895) is called from
  `_rewrite_failing_steps` (generate_campaign.py:325)
- `STEP_REWRITE_SYSTEM` (copystages.py:892) is used in
  `_rewrite_failing_steps` (generate_campaign.py:341)
