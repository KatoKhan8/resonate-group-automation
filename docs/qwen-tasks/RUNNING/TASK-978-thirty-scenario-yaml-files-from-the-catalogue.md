# TASK-978: Thirty scenario YAML files from the catalogue

## STATUS: RUNNING

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
