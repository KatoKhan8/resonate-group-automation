# QA Harness — 2026-09-25

TASK-292. The harness that answers two questions:
- When a pre-push check fails, does the push actually stop?
- Can the runner tell "every check passed" from "no check ran"?

## What exists

```
scripts/qa/__init__.py     Registry: CHECKS, verdicts, phases, validation, table
scripts/qa/run.py          CLI runner, per-check JSON + TABLE.md artefacts
scripts/qa/refuse_qa.py    Refusal function (patch proposal for bisonfactory)
```

## The registry

Seven checks, all pre-registered:

| check_id          | module               | phase      | blocking |
|-------------------|----------------------|------------|----------|
| lead_state        | check_lead_state     | pre_push   | True     |
| lead_pack         | check_lead_pack      | pre_push   | True     |
| lead_copy         | check_lead_copy      | pre_push   | True     |
| campaign_bison    | check_campaign_bison | pre_push   | True     |
| campaign_heyreach | check_campaign_heyreach | pre_push | True   |
| readback          | check_readback       | post_push  | True     |
| reconcile         | check_reconcile      | ongoing    | True     |

A check module not listed does not run. A listed module that does not exist
reports NOT_IMPLEMENTED in the table — not PASS, and not silence.

## Verdicts and exit codes

| verdict       | exit code | meaning                                      |
|---------------|-----------|----------------------------------------------|
| PASS          | 0         | every subject checked, every rule clear      |
| FAIL          | 1         | at least one subject offends at least one rule |
| UNCONFIRMED   | 2         | could not establish the answer               |
| VACUOUS       | 2         | subject set was empty                        |
| ERROR         | 3         | the check itself broke                       |

## Refusal semantics by phase

- **pre_push**: 0 proceeds. 1, 2, 3 all REFUSE THE PUSH.
- **post_push**: 0 proceeds. 1 raises CRITICAL. 2 is retried. 3 raises CRITICAL.
- **ongoing**: 0 proceeds. 1 is ALWAYS CRITICAL. 2 is CRITICAL if persistent. 3 CRITICAL.

## The five invariants the runner enforces

1. `offenders` and `unverifiable` hold ids, not counts or summaries.
2. `clean + |union(offenders) ∪ union(unverifiable)| == subjects`.
3. `subjects == 0` is VACUOUS, never PASS.
4. Every key in `counts`, `offenders`, `unverifiable` exists in `rules`, and vice versa.
5. `rules` sentences are rendered from this run's parameters.

A result that breaks one is ERROR (3), not whatever the check said.

## The table

One renderer used by both the Slack post and the refusal text. Every registered
check gets a row. No prospect ids in the table; a path to the artefact.

```
QA · batch-2-2026-09-25 · pre_push · REFUSED
campaigns 502, 503 · 256 leads · commit af7c2539 · 2026-09-25T06:01:40Z

check                verdict       subj  clean  offending
lead_state           PASS           128    128  -
lead_pack            FAIL           128    120  8 (8 bad_pack)
lead_copy            VACUOUS          0      0  no copy in this batch
campaign_bison       NOT_IMPLEMENTED     -      -  module not yet on disk
campaign_heyreach    NOT_IMPLEMENTED     -      -  module not yet on disk

REFUSED. Nothing was written to either provider.
offending ids: work/qa/<run-id>/TABLE.md
```

## No bypass

There is no `--skip-qa`, no `--force`, no environment variable that disables a
blocking check. The only escape is `blocking=False` in `CHECKS`, in a commit.

## Patch proposal

`_refuse_qa` is proposed for `src/bisonfactory.py` immediately after
`_refuse_copylint` at line 86, before `bison.bound_workspace()`.

See the TASK-292 result block for the exact patch.
