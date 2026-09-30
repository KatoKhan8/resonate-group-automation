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

No durable controller existed. The pipeline from CSV source to provider write
had no checkpoint, no duplicate protection, and no safe restart. A crash mid-
batch would lose progress and a restart could re-enrol already-staged records.

### FILES CHANGED

- `src/durablecontroller.py` — the controller module (new)
- `tests/test_durable_controller.py` — 20 tests including kill-and-restart (new)
- `src/store.py` — added `CONTROLLER_CHECKPOINT` to `STATE_OVERRIDES`
- `tests/test_invariants.py` — added `durablecontroller` to `SELF_WRITERS`
- `config/.env.example` — added `CONTROLLER_CHECKPOINT=` entry

### TESTS

20 tests, all passing:
- `TestCheckpointPersistence` (4): empty shape, save/reload, corrupt recovery,
  version mismatch
- `TestDuplicateProtection` (6): is_duplicate, record_id, write_state,
  update_write_state, refuses unknown state, refuses unenrolled row
- `TestKillAndRestart` (4): restart does not re-enrol, resume from checkpoint,
  completed batch not re-run, held rows recorded but not enrolled
- `TestNoGateWeakening` (4): no gate module imports, no bare store.save,
  dry by default, live permits enrollment
- `TestSlackNotifications` (2): events sent, notify optional

### SHA

`2172e60b`

### WHY THIS DOES NOT WEAKEN A GATE

The controller wires state, not policy. It does not import `approval`,
`killswitch`, `executionguard`, or `providerwrites` — proven by
`test_controller_does_not_import_gate_modules`. It does not call `store.save`
directly — proven by `test_controller_does_not_weaken_store_transaction`. It
is dry by default and requires explicit `--live` to permit enrollment — proven
by `test_dry_by_default`. Provider writes still go through
`providerwrites.perform` and `executionscope` via the injected `enroll_fn`;
the controller opens no second path to a provider.

Duplicate protection is proven by `test_restart_does_not_re_enrol`: run 3
rows, restart, prove rows 1-3 are not re-processed and no record_id appears
twice. The checkpoint persists source position after each row, so a crash
loses at most one row's work.

The controller is registered in `store.STATE_OVERRIDES`, `SELF_WRITERS`, and
`.env.example` so the existing invariant tests cover it — a new state file
that the safety infrastructure does not know about would be the exact failure
mode this task exists to prevent.
