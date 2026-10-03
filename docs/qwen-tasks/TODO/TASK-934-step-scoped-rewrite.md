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

The writer emits a whole set (11 messages) in one call, and
`_refuse_partial_regeneration` forbids rewriting one step. So every attempt
re-rolls all eleven messages. Joint satisfaction of ~15 constraints across
11 messages by repeated whole-set sampling is the wrong shape, and it is
why no contact has ever cleared.

### FILES CHANGED

- `src/generate_campaign.py` (+278 lines):
  - `MAX_STEP_REWRITES = 3` constant
  - `STEP_REWRITE_SYSTEM` and `STEP_REWRITE_USER` prompt templates
  - `_STEP_KEY_RE` and `_COPYLINT_LOCATOR_RE` regex patterns
  - `_parse_failing_step_keys(failures)` - extracts step keys from both
    validate callback format ("em3: reason") and copylint locator format
    ("buzzword -> em3 ('match')")
  - `_step_scoped_rewrite_phase(...)` - rewrites only failing steps with
    full sequence context, re-gates the whole sequence after each rewrite,
    reverts if a sibling breaks, bounded retries per step
  - Modified retry loop in `_process_contact` to enter step-scoped rewrite
    after the first full-set attempt when specific steps fail
- `tests/test_task934_step_scoped_rewrite.py` (new, 419 lines):
  - 11 tests covering all 5 requirements plus parser tests

### TESTS

11 tests, all passing:
- `test_failing_step_rewritten_siblings_byte_identical` - em3 fails,
  siblings are BYTE-IDENTICAL after rewrite
- `test_rewrite_making_sibling_fail_is_refused` - rewrite that breaks a
  sibling is reverted
- `test_bounded_retries_then_held` - step that never passes stores nothing
- `test_approval_hash_covers_final_full_sequence` - hash covers full sequence
- `test_non_converging_sequence_stores_nothing` - non-converging stores nothing
- 6 parser tests for `_parse_failing_step_keys`

Mutation check: disabled `_step_scoped_rewrite_phase` (early return False),
test 1 went RED for the intended reason ("step-scoped rewrite did not
converge"), restored, SHA verified, __pycache__ cleared, all green.

### SHA

`b090c8d58366d21f7af5dad629fd071703b5ca30706f76459b16e689fce3f17b  src/generate_campaign.py`

### WHY THIS DOES NOT WEAKEN A GATE

1. Every gate that refuses today still refuses after this. The step-scoped
   rewrite runs the SAME gates (copylint, sequencegate, validate callback
   which includes lint.check, claims.check, quality.gate) over the WHOLE
   sequence after every rewrite.
2. A rewrite that makes a sibling fail is REFUSED and reverted. The step
   is never accepted on its own merits alone.
3. The approval hash is computed over the FINAL FULL SEQUENCE by
   `sequenceplan.approval_hash` - unchanged.
4. Storage stays all-or-nothing per channel in `_adapt_plan_to_cadence` -
   unchanged.
5. `_refuse_partial_regeneration` is NOT weakened or removed. It still
   refuses partial regeneration by default. The step-scoped rewrite is a
   new path that operates WITHIN the campaign pipeline's retry loop, not
   a bypass of the refusal.
6. The whole-set retry budget (`MAX_WRITER_ATTEMPTS = 10`) is preserved.
   If the step-scoped rewrite does not converge, the whole-set loop
   continues.
