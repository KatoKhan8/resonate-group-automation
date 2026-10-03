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

ROOT CAUSE / FILES CHANGED / TESTS / SHA / WHY THIS DOES NOT WEAKEN A GATE
