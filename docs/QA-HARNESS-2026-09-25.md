# QA Harness — TASK-292

**Date:** 2026-09-30
**Status:** Implemented, tests green

## What was built

The QA harness: the registry, the runner, the result validator, the table
renderer, and the tests that prove the gate stops the real send path.

### Files

- `scripts/qa/__init__.py` — the registry (`CHECKS` as an ordered tuple),
  verdict/exit-code vocabulary, phase mapping, result validator (five
  invariants), check-module discovery.
- `scripts/qa/run.py` — the runner (`--phase <phase>`), table renderer,
  CLI entry point. Writes per-check JSON and `TABLE.md` under
  `work/qa/<run-id>/`.
- `tests/test_the_qa_gate_stops_the_real_send_path.py` — 20 tests.
- `tests/test_a_qa_result_that_does_not_add_up_is_an_error.py` — 14 tests.

### The registry

Seven checks, in the order the contract names them:

| check_id            | module                              | phase      | blocking |
|---------------------|-------------------------------------|------------|----------|
| lead_state          | scripts.qa.check_lead_state         | pre_push   | True     |
| lead_pack           | scripts.qa.check_lead_pack          | pre_push   | True     |
| lead_copy           | scripts.qa.check_lead_copy          | pre_push   | True     |
| campaign_bison      | scripts.qa.check_campaign_bison     | pre_push   | True     |
| campaign_heyreach   | scripts.qa.check_campaign_heyreach  | pre_push   | True     |
| readback            | scripts.qa.check_readback           | post_push  | True     |
| reconcile           | scripts.qa.check_reconcile          | ongoing    | True     |

Four modules are not yet implemented (TASK-293 through TASK-296). They
report `NOT_IMPLEMENTED` in the table, not PASS and not silence.

### The verdict and exit-code vocabulary

| verdict       | exit code | meaning                                      |
|---------------|-----------|----------------------------------------------|
| PASS          | 0         | every subject checked, every rule clear      |
| FAIL          | 1         | at least one subject offends at least one rule|
| UNCONFIRMED   | 2         | the check ran and could not establish the answer|
| VACUOUS       | 2         | subjects == 0; never PASS                    |
| ERROR         | 3         | the check itself broke                       |

One table in `__init__.py`; two copies is how pre-push and post-push come
to disagree about what 2 means.

### The five invariants the runner enforces

1. `offenders` and `unverifiable` hold ids, never counts or summaries.
2. The arithmetic closes: `clean + |union(offenders) ∪ union(unverifiable)| == subjects`.
3. `subjects == 0` is VACUOUS, never PASS, and carries a stated reason.
4. Every key in `counts`, `offenders` and `unverifiable` exists in `rules`,
   and every key in `rules` exists in `counts`.
5. `rules` sentences are non-empty strings rendered from this run's parameters.

A result that breaks any invariant is downgraded to ERROR.

### The table

Every registered check gets a row. Checks for other phases get a row marked
`-` with the phase named. No prospect ids in the table; a path to the
artefact.

### No bypass

There is no `--skip-qa`, no `--force`, no environment variable that disables
a blocking check. The only escape is `blocking=False` in `CHECKS`, in a
commit.

## _refuse_qa patch proposal

`src/bisonfactory.py` is FORBIDDEN (Lane D's territory). The patch below
goes immediately after `_refuse_copylint(plan, recs, report)` at line 122,
before `bison.bound_workspace()`:

```python
def _refuse_qa(plan, recs, report):
    """Run the pre-push QA suite and refuse if any blocking check fails.

    The refusal carries the runner's own rendered table, not a sentence
    written here, so a rule that did not exist when this function was
    written still names itself in the refusal.
    """
    from scripts.qa import run as qa_run
    from scripts.qa import PASS, NOT_IMPLEMENTED

    campaigns = [plan.get("campaign_id")]
    batch = plan.get("batch")

    results, table_text, worst = qa_run.run_phase(
        "pre_push",
        batch=batch,
        campaigns=campaigns,
        workspaces=None,
        live_reads=False,
    )
    report["qa"] = {
        "results": results,
        "table": table_text,
        "worst": worst,
    }
    if worst == PASS:
        return
    raise FactoryRefused(
        "the pre-push QA suite refuses this push:\\n"
        + table_text,
        report=report)
```

Call site in `bisonfactory.stage`, after `_refuse_copylint`:

```python
    _refuse_copylint(plan, recs, report)
    _refuse_qa(plan, recs, report)          # <- the pre-push suite
    workspace = bison.bound_workspace()      # first provider call
```

Same for `heyreachfactory.stage` at its equivalent seam.

## Lane D status

Lane D has landed on this branch: `_refuse_copylint` is present at
`src/bisonfactory.py:627`. The patch proposal above is ready to apply.
