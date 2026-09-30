# QA Harness — TASK-292, 2026-09-25

## What this is

The QA harness is the runner, registry, result validator and table renderer
for the standing QA suite (Lane F). It answers two questions:

1. **When a pre-push check fails, does the push actually stop?**
2. **Can the runner tell "every check passed" apart from "no check ran"?**

## Components

### `scripts/qa/__init__.py` — the registry

- `CHECKS`: ordered tuple of `(check_id, module, phase, blocking)` for all
  seven check groups from the contract.
- `VERDICTS`: `PASS/FAIL/UNCONFIRMED/VACUOUS/ERROR` → `0/1/2/2/3`.
- `validate_result()`: asserts the five invariants of contract §4 on every
  result. A result that breaks one is downgraded to ERROR.

### `scripts/qa/run.py` — the runner and table renderer

- `run_phase(phase, ...)`: runs every blocking check for the phase, writes
  per-check JSON and TABLE.md, returns the worst verdict.
- `render_table(results, ...)`: ONE renderer used by both the Slack post and
  the refusal text. Every registered check gets a row. No prospect ids.

### `scripts/qa/refuse.py` — the refusal function

- `_refuse_qa(plan, recs, report)`: runs the pre-push suite and raises
  `_QARefused` carrying the runner's own rendered table. Delivered as a
  patch proposal for `bisonfactory.py` and `heyreachfactory.py`.

### `scripts/qa/check_*.py` — one module per check group

Seven check groups (TASK-293 through TASK-299). A module not listed in
`CHECKS` does not run. A listed module that does not yet exist reports
`NOT_IMPLEMENTED` in the table.

## The five invariants (contract §4)

1. `offenders` and `unverifiable` hold ids, never counts or summaries.
2. `clean + |union(offenders) ∪ union(unverifiable)| == subjects`.
3. `subjects == 0` is VACUOUS, never PASS, with a stated reason.
4. Every key in `counts`, `offenders`, `unverifiable` exists in `rules`.
5. Rule sentences are rendered from this run's parameters.

## Refusal semantics by phase

| Phase     | PASS    | FAIL     | UNCONFIRMED | VACUOUS  | ERROR    |
|-----------|---------|----------|-------------|----------|----------|
| pre_push  | proceed | REFUSE   | REFUSE      | REFUSE   | REFUSE   |
| post_push | proceed | CRITICAL | RETRY       | CRITICAL | CRITICAL |
| ongoing   | proceed | CRITICAL | CRITICAL*   | CRITICAL | CRITICAL |

*CRITICAL if persistent across two consecutive cycles.

## The patch proposal

`_refuse_qa` goes inside `bisonfactory.stage` and `heyreachfactory.stage`,
immediately after `_refuse_copylint` and before the first provider call:

```python
_refuse_copylint(plan, recs, report)
_refuse_qa(plan, recs, report)          # <- the pre-push suite
workspace = bison.bound_workspace()      # first provider call
```

The refusal carries the runner's own rendered table, not a sentence written
at the raise site.

## No bypass

There is no `--skip-qa`, no `--force`, no environment variable that disables
a blocking check. The only escape is `blocking=False` in `CHECKS`, in a
commit.
