# QA Harness — TASK-292, 2026-09-25

## What was built

The QA harness: registry, runner, result validator, table renderer, and the
wiring into `bisonfactory.stage` that refuses a push before any provider call.

## Files

    scripts/qa/__init__.py     Registry: CHECKS, PHASES, verdicts, exit codes
    scripts/qa/run.py          Runner, validator, table renderer, CLI
    tests/test_the_qa_gate_stops_the_real_send_path.py
    tests/test_a_qa_result_that_does_not_add_up_is_an_error.py

## The registry

`scripts/qa/__init__.py::CHECKS` is an ordered tuple of
`(check_id, module_name, phase, blocking)`. Seven checks are registered,
conforming to `docs/QA-LANE-F-CONTRACT-2026-09-25.md` §1:

    lead_state        pre_push    TASK-293
    lead_pack         pre_push    TASK-294
    lead_copy         pre_push    TASK-295
    campaign_bison    pre_push    TASK-296
    campaign_heyreach pre_push    TASK-297
    readback          post_push   TASK-298
    reconcile         ongoing     TASK-299

A check module that does not yet exist reports `NOT_IMPLEMENTED` in the table.
NOT_IMPLEMENTED is advisory — it does not block the push until the check
module lands. This allows the checks to be built incrementally without
blocking production pushes.

## The verdict vocabulary

    PASS          0   every subject checked, every rule clear
    FAIL          1   at least one subject offends at least one rule
    UNCONFIRMED   2   the check ran and could not establish the answer
    VACUOUS       2   subjects == 0; never PASS; carries a stated reason
    ERROR         3   the check itself broke — bad arithmetic, import error

One table in `__init__.py`; both phases read it.

## The five invariants

The runner asserts these on every result and downgrades a broken one to ERROR:

1. `offenders` and `unverifiable` hold ids, never counts or "..."
2. `clean + |union(offenders) ∪ union(unverifiable)| == subjects`
3. `subjects == 0` is VACUOUS, never PASS
4. `rules`, `counts`, `offenders` keys agree in both directions
5. `rules` sentences are non-empty strings rendered from run parameters

## The push refusal

`_refuse_qa(plan, recs, report)` is wired into `bisonfactory.stage` at line 87,
immediately after `_refuse_copylint` and BEFORE `bison.bound_workspace()` —
the first provider call of any kind.

The refusal text is the RUNNER'S OWN rendered table, not a sentence written at
the raise site. A rule that did not exist when the function was written still
names itself in the refusal.

NOT_IMPLEMENTED checks are advisory and do not cause a refusal. The moment a
check EXISTS and returns a failing verdict (FAIL, UNCONFIRMED, VACUOUS, ERROR),
the gate fires.

## The table

One renderer used by both the Slack post and the refusal text. Every registered
check gets a row. No prospect ids in the table; a path to the artefact.

## No bypass

There is no `--skip-qa`, no `--force`, no environment variable that disables a
blocking check. The only escape is `blocking=False` in `CHECKS`, in a commit.
