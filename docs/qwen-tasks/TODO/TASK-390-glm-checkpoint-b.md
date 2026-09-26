PRIORITY: P0
SIZE: M
DEPENDS: TASK-367

# TASK-390 — GLM CHECKPOINT B (offers, persona list, campaign strategy)

**Operator instruction, 2026-09-26/27 overnight standing order.** Dispatched
now; `DEPENDS: TASK-367` means the dispatcher will not hand this out until
TASK-367 (the real offers block, cta_link corrected per its REWORK note) is
merged to master. **Do not dispatch by hand before then.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly — isolated
worktree, read-only, Qwen driving the adapter, falsification over
confirmation, the eight dispositions. This task file only names the target
and the negative controls.

## Target

The three pieces the operator named as one checkpoint, because they are one
chain: `capability_by_persona` (TASK-366, ordered list, angle order) →
`offers:` block (TASK-367, persona-to-offer, once merged) → campaign
strategy (TASK-320, decided once per segment+persona, cached).

## Negative controls — GLM must try to falsify each, not confirm it

1. **The offer's `cta_link` is the sole standing allowlisted URL**
   (`https://productive.io/get-started/`), for BOTH offers, verified by
   reading the merged config directly - not by reading TASK-367's own
   result block and trusting it.
2. **Neither offer's `approval_status` is `approved`.** Grep the whole repo,
   not just the offers file, for anywhere it could have been flipped.
3. **`capability_by_persona`'s order changes only the angle, never which
   offer a persona gets.** Reorder the list in a fixture, confirm the offer
   assignment is unchanged, confirm the angle order is.
4. **Campaign strategy is decided ONCE per segment+persona** — reproduce the
   cache-hit test yourself (N leads, one model call), do not accept the
   worker's own count.
5. **No capability was deleted** in getting from six records to two offers -
   confirm all six still exist under `capabilities:`, `billing` included,
   correctly absent from both offers.
6. **An offer never restates a value proposition** - grep for
   `value_proposition` text appearing verbatim inside an `offers:` record;
   it must only exist under `capabilities:`.
7. **`NotApproved` still raises at the offer layer**, by name, naming the
   offer - reproduce it, not read the test.

## What GLM's pass must produce

Per the protocol's eight dispositions, for each control above plus anything
new found with file:line. State plainly whether the chain is safe to build
copy generation against, or what specifically still blocks it.

## What this task may NOT do

- No provider write, no campaign action, nothing sent or activated.
- Do not approve an offer or recommend approving one - that is the
  operator's decision, not a finding this checkpoint may substitute for.
