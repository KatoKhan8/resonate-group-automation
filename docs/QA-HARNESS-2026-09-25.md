# QA Harness — TASK-292

**Implemented 2026-10-03.** The harness that answers: "When a pre-push check
fails, does the push actually stop — on the real send path, without a flag
anybody can pass to get past it?"

## What exists

    scripts/qa/__init__.py    the registry, verdict vocabulary, result validator
    scripts/qa/run.py         the runner, table renderer, and _refuse_qa
    scripts/qa/check_*.py     one module per check group (TASK-293..299)

## The registry

`CHECKS` is an ordered tuple of `(check_id, module_name, phase, blocking)`.
Seven check ids from the contract:

    lead_state        TASK-293  pre_push    subject: lead
    lead_pack         TASK-294  pre_push    subject: lead
    lead_copy         TASK-295  pre_push    subject: lead
    campaign_bison    TASK-296  pre_push    subject: campaign
    campaign_heyreach TASK-297  pre_push    subject: campaign
    readback          TASK-298  post_push   subject: campaign
    reconcile         TASK-299  ongoing     subject: lead

A module not listed does not run. A listed module that does not yet exist
reports `NOT_IMPLEMENTED` in the table — not PASS, and not silence.

## The verdict and exit-code vocabulary

    verdict        exit   meaning
    PASS           0      every subject checked, every rule clear
    FAIL           1      at least one subject offends at least one rule
    UNCONFIRMED    2      the check ran and could not establish the answer
    VACUOUS        2      subjects == 0; never PASS, carries a stated reason
    ERROR          3      the check itself broke

ONE table in `__init__.py`. The runner, the refusal and the Slack post all
read these.

## The result validator

The runner asserts five invariants on every result:

1. `offenders` and `unverifiable` hold ids, not counts or summaries
2. `clean + |union(offenders) ∪ union(unverifiable)| == subjects`
3. `subjects == 0` is VACUOUS, never PASS, with a stated reason
4. `rules`, `counts`, `offenders` keys agree in both directions
5. `rules` sentences are non-empty strings

A result that breaks one is downgraded to ERROR.

## The refusal wiring

`_refuse_qa(plan, recs, report)` is called from both `bisonfactory.stage`
and `heyreachfactory.stage`, immediately after `_refuse_copylint` and before
the first provider call. It raises `FactoryRefused` carrying the runner's
own rendered table plus the offending ids.

Lane D had landed before this task started (`_refuse_copylint` at line 122
of `bisonfactory.py`), so the wiring was edited directly rather than
delivered as a patch proposal.

## The table

One renderer used by both the Slack post and the refusal text. Every
registered check gets a row. No prospect ids in the table; a path to the
artefact. The refusal text appends the ids after the table.

## Tests

    tests/test_the_qa_gate_stops_the_real_send_path.py
    tests/test_a_qa_result_that_does_not_add_up_is_an_error.py

25 tests, all passing.
