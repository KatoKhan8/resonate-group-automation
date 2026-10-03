PRIORITY: P0
SIZE: M
DEPENDS: 

# TASK-933 — the MINIMUM durable controller, and nothing more

Operator, 2026-09-30: a durable controller is required before unattended
scaling, it must not consume the production thread, and it is **minimum
requirements only**. Use the existing infrastructure. **No new platform, no
new orchestration framework, no dashboard, no UI.**

## What it must persist, and nothing else

    persistent checkpoint
    source position          (row in productive_ICP_safe_to_send (1).csv)
    batch state              (which batch, which size, running/complete)
    record disposition       (QUALIFIED / HELD + exact reason / NOT_QUALIFIED)
    approval hash
    provider campaign id
    provider write + readback state
    safe restart
    duplicate protection
    Slack operational events

## The rules that decide the design

- **The estate is the checkpoint wherever it can be.** `scripts/canary_candidate_
  walk.py` is resumable today because an account that no longer needs research
  simply is not in the set. Do not invent a second state file for anything the
  queue already answers. Persist only what cannot be derived: source position,
  batch identity, and provider write/readback state.
- **Duplicate protection is the point of the whole thing.** A restart must
  never re-enrol or re-send to somebody already staged. Prove it by killing
  the controller mid-batch and restarting it.
- Writes go through `store.transaction` and provider writes through the
  existing `providerwrites.perform` / `executionscope` door. Do not open a
  second path to a provider.
- Dry by default; `--live` explicit.

## RULES

- Do not weaken any gate, threshold or authority. You are wiring state, not
  policy.
- Do not touch the claim, evidence, approval or provider-write modules.
- Mutation check mandatory, plus a real kill-and-restart test.

## RETURN

ROOT CAUSE / FILES CHANGED / TESTS / SHA / WHY THIS DOES NOT WEAKEN A GATE
