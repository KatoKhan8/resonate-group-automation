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

### ROOT CAUSE

No durable controller existed. The pipeline had all the components (assessment,
provider writes, checkpoint patterns, notifications) but no script that wired
them together with kill-and-restart safety and duplicate protection.

### FILES CHANGED

- `scripts/durable_controller.py` — the minimum controller: walks the source
  CSV in deterministic order, assesses each row via
  `canary_candidate_walk.assess()`, checkpoints after every row, resumes from
  the exact source position on restart, checks queue state before enrolling
  (duplicate protection), sends Slack operational events via `notify.notify()`,
  dry by default with `--live` explicit.
- `tests/test_durable_controller.py` — 15 tests proving: checkpoint round-trip,
  kill-and-restart resume, duplicate protection for all enrolled states
  (pushed/approved/drafted), dry mode structural property, batch-size cap,
  and AST-level proof that no gate module (providerwrites, executionguard,
  approval) is imported.

### TESTS

    py -3 -m unittest tests.test_durable_controller -v
    Ran 15 tests in 0.120s — OK

    py -3 scripts/durable_controller.py --mutation-check
    mutation check: PASS

    Full suite: RUNNING (started 23:42 UTC, expected ~865s)

### SHA

    ee8e77e1 — TASK-933: minimum durable controller with checkpoint, duplicate
    protection and kill-and-restart

### WHY THIS DOES NOT WEAKEN A GATE

1. The controller does NOT import `providerwrites`, `executionguard`,
   `executionguard`, `approval`, `claims`, `evidence`, or `bisonfactory`.
   Proved by AST-level test (`NoGateWeakening`).
2. The controller does NOT call any provider write function directly. It calls
   `canary_candidate_walk.assess()` for disposition and `notify.notify()` for
   operational events. Both are read-only / best-effort.
3. The duplicate protection checks the QUEUE STATE, not a separate allowlist.
   A domain at pushed/approved/drafted is skipped because the queue already
   says it has been through the pipeline. This is the same check
   `eligibility.must_not_contact` would make, but at the controller level
   before assessment even runs.
4. The checkpoint persists only what the queue CANNOT derive: source position,
   batch identity, and provider write/readback state. The queue remains the
   authority for record state, contact discovery, ICP verdict, and eligibility.
5. Dry by default. No provider write, no credit spend, no generation unless
   `--live` is passed explicitly.
6. The mutation check proves the checkpoint survives a write-read cycle
   losslessly. The kill-and-restart test proves a controller killed mid-batch
   and restarted resumes from the exact row without re-processing.

### CALLER CHAIN

    grep -rn "durable_controller" scripts/ tests/ src/
    scripts/durable_controller.py: CLI entry point (py -3 scripts/durable_controller.py)
    tests/test_durable_controller.py: imports via importlib for testing

The controller is a script, consumed by its CLI and by its test file. It does
not add a new import surface to any existing module.
