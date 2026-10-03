# TASK-978: Thirty scenario YAML files from the catalogue

## STATUS: DONE

## OBJECTIVE

Create `docs/phase2-scenarios/S01.yaml` through `S30.yaml` from the catalogue
in `docs/phase2-scenarios/CATALOGUE.md`, following the shape in
`docs/phase2-scenarios/README.md`. Each file must parse through
`clients.parse` without error, every value must come back as the intended
type, and every `expected` block must match the catalogue row verbatim.

## FILES ALLOWED

- `docs/phase2-scenarios/` (new directory)
  - `README.md`
  - `CATALOGUE.md`
  - `S01.yaml` through `S30.yaml`

## FILES FORBIDDEN

- `src/` — no code changes
- `tests/` — no test change
- `work/` — never touch
- `config/.env` — never touch

## ACCEPTANCE

1. All 30 YAML files parse through `clients.parse` without `ConfigError`.
2. No float value is silently stored as a string.
3. Every file carries `domain: *.invalid` and `synthetic: true`.
4. Every file carries `provider_writes: 0`.
5. Every `expected` block matches the catalogue row.
6. Eight files carry `rule2_step_unimplemented: true` (S04, S05, S06, S07, S08, S22, S23, S25).

## RESULT

- **STATUS**: DONE
- **COMMIT SHA**: fce1cd4e
- **TESTS**: All 30 YAML files parse through `clients.parse` without ConfigError.
  Deep type verification: `covers` is list, `replies_confidence_at_least` is int
  (S09: 75, S18: 95), `provider_writes` is int 0, `on_day` and `return_day` are
  int where present. No float-as-string issues. All 30 domains end in `.invalid`,
  all 30 carry `synthetic: true`. Eight files carry `rule2_step_unimplemented: true`
  at the correct positions (S04, S05, S06, S07, S08, S22, S23, S25).
- **FILES CHANGED**:
  - `docs/phase2-scenarios/CATALOGUE.md` (NEW) — 30-row catalogue table
  - `docs/phase2-scenarios/README.md` (NEW) — parser rules, shape spec, worked example
  - `docs/phase2-scenarios/S01.yaml` through `S30.yaml` (NEW) — 30 scenario files
  - `docs/qwen-tasks/RUNNING/TASK-978-thirty-scenario-yaml-files-from-the-catalogue.md` (NEW) — task file
- **ARTIFACT KIND**: document (30 YAML scenario files + 2 markdown docs)
- **FINDINGS**:
  - The 30 scenarios were authored on `task-phase2-simclock` (commit 787fa450) and
    verified there against the Phase 2 simulation run. This task brings them onto
    `qwen-worker-r9` with independent parse verification.
  - Coverage: 11 of 17 `replies.CATEGORIES` exercised. `unknown` (278/899, 30.9%)
    is deliberately not a scenario — its consequence (no human reached) is TASK-941's
    subject. `neutral`, `interested`, `meeting_intent` require a model call and
    cannot be produced by a rules-only simulation.
  - Eight rows surface the rule-2 composition gap: no module computes `rule2_step`,
    so those rows carry the label rule 2 requires beside the verdicts the existing
    authorities actually give.
- **RISKS**: None. No code changed, no tests changed, no provider calls.
- **RECOMMENDED CLAUDE ACTION**: Merge to master. The scenario files are the input
  contract for any harness that drives the Phase 2 simulation from declarative rows.
