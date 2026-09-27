# GLM branch verification: TASK-400

Branch: `task400-rework3`
Date: 2026-09-27T22:07:56.542280+00:00
Model: glm-5.3
Duration: 89.445s
Usage: {'prompt_tokens': 3064, 'completion_tokens': 7272, 'total_tokens': 10336, 'reasoning_tokens': 6489, 'cached_tokens': 0}

## Verdict: FAIL

**17 new test failures not in baseline: ['test_a_catch_all_cleared_by_one_provider_is_now_held (tests.test_e2e.TestEnrichmentOutcomes.test_a_catch_all_cleared_by_one_provider_is_now_held)', 'test_a_deliverable_failure_never_becomes_evidence_of_validity (tests.test_e2e.TestTheProviderWaterfall.test_a_deliverable_failure_never_becomes_evidence_of_validity)', 'test_after_approval_the_payloads_appear (tests.test_preproduction.TestApprovalIsRequired.test_after_approval_the_payloads_appear)', 'test_deliverable_never_called_while_its_contract_is_unconfirmed (tests.test_e2e.TestTheProviderWaterfall.test_deliverable_never_called_while_its_contract_is_unconfirmed)', 'test_each_contact_has_the_full_seven_step_timeline (tests.test_preproduction.TestTheCadenceIsPrepared.test_each_contact_has_the_full_seven_step_timeline)']**

## GLM spend

This call: 0 ledger rows, 0 micro-USD

## New test failures

- `test_a_catch_all_cleared_by_one_provider_is_now_held (tests.test_e2e.TestEnrichmentOutcomes.test_a_catch_all_cleared_by_one_provider_is_now_held)`
- `test_a_deliverable_failure_never_becomes_evidence_of_validity (tests.test_e2e.TestTheProviderWaterfall.test_a_deliverable_failure_never_becomes_evidence_of_validity)`
- `test_after_approval_the_payloads_appear (tests.test_preproduction.TestApprovalIsRequired.test_after_approval_the_payloads_appear)`
- `test_deliverable_never_called_while_its_contract_is_unconfirmed (tests.test_e2e.TestTheProviderWaterfall.test_deliverable_never_called_while_its_contract_is_unconfirmed)`
- `test_each_contact_has_the_full_seven_step_timeline (tests.test_preproduction.TestTheCadenceIsPrepared.test_each_contact_has_the_full_seven_step_timeline)`
- `test_editing_after_approval_pulls_it_back_out_of_the_payload (tests.test_preproduction.TestApprovalIsRequired.test_editing_after_approval_pulls_it_back_out_of_the_payload)`
- `test_one_provider_failing_does_not_stop_the_batch (tests.test_e2e.TestTheProviderWaterfall.test_one_provider_failing_does_not_stop_the_batch)`
- `test_successful_regeneration_replaces_all_notes (tests.test_set_regeneration.SetRegenerationTransactionTest.test_successful_regeneration_replaces_all_notes)`
- `test_the_approval_is_attributed_to_a_person (tests.test_preproduction.TestApprovalIsRequired.test_the_approval_is_attributed_to_a_person)`
- `test_the_catch_all_cleared_through_reoon_before_being_used (tests.test_preproduction.TestTheControlledScope.test_the_catch_all_cleared_through_reoon_before_being_used)`
- `test_the_catch_all_that_cleared_needed_reoon (tests.test_e2e.TestTheProviderWaterfall.test_the_catch_all_that_cleared_needed_reoon)`
- `test_the_catch_all_that_does_not_clear_is_held_and_not_sendable (tests.test_e2e.TestEnrichmentOutcomes.test_the_catch_all_that_does_not_clear_is_held_and_not_sendable)`
- `test_the_funnel_adds_up (tests.test_preproduction.TestTheWholeRunIsAccountedFor.test_the_funnel_adds_up)`
- `test_the_invalid_address_ends_dropped_with_a_reason (tests.test_e2e.TestEnrichmentOutcomes.test_the_invalid_address_ends_dropped_with_a_reason)`
- `test_the_payloads_are_the_documented_shapes (tests.test_e2e.TestPushPreparationAndIdempotency.test_the_payloads_are_the_documented_shapes)`
- `test_the_report_can_break_verification_down_by_verifier (tests.test_e2e.TestTheProviderWaterfall.test_the_report_can_break_verification_down_by_verifier)`
- `test_the_state_of_every_record (tests.test_e2e.TestTheFinalShape.test_the_state_of_every_record)`

## Changed files (23)

- `docs/TASK-400-REWORK3-MUTATIONS.md`
- `docs/qwen-tasks/TODO/TASK-400-generate-py-becomes-the-real-caller.md`
- `src/approve.py`
- `src/bisonfactory.py`
- `src/generate.py`
- `src/generate_campaign.py`
- `src/heyreachfactory.py`
- `src/providers/bison.py`
- `src/providers/heyreach.py`
- `src/run.py`
- `src/sequenceplan.py`
- `tests/base.py`
- `tests/test_audit.py`
- `tests/test_changing_an_approved_fact_changes_the_output.py`
- `tests/test_e2e.py`
- `tests/test_generate.py`
- `tests/test_no_model_is_not_a_bad_record.py`
- `tests/test_preproduction.py`
- `tests/test_qwen_cli_model.py`
- `tests/test_run.py`
- `tests/test_set_regeneration.py`
- `tests/test_task400_rework2.py`
- `tests/test_task400_rework3.py`

## Diff stat

```
 docs/TASK-400-REWORK3-MUTATIONS.md                 | 220 +++++
 ...TASK-400-generate-py-becomes-the-real-caller.md |  91 ++
 src/approve.py                                     |  21 +
 src/bisonfactory.py                                |  78 +-
 src/generate.py                                    | 721 ++++++++++++++-
 src/generate_campaign.py                           | 380 ++++++--
 src/heyreachfactory.py                             |  72 +-
 src/providers/bison.py                             |   5 +
 src/providers/heyreach.py                          |   5 +
 src/run.py                                         |  48 +-
 src/sequenceplan.py                                |  30 +-
 tests/base.py                                      | 287 +++++-
 tests/test_audit.py                                |  12 +-
 ...changing_an_approved_fact_changes_the_output.py |  56 +-
 tests/test_e2e.py                                  |  56 +-
 tests/test_generate.py                             | 257 ++++--
 tests/test_no_model_is_not_a_bad_record.py         |  10 +-
 tests/test_preproduction.py                        |  17 +-
 tests/test_qwen_cli_model.py                       |  16 +-
 tests/test_run.py                                  |  64 +-
 tests/test_set_regeneration.py                     | 127 ++-
 tests/test_task400_rework2.py                      | 992 +++++++++++++++++++++
 tests/test_task400_rework3.py                      | 530 +++++++++++
 23 files changed, 3808 insertions(+), 287 deletions(-)

```

## Acceptance output

```
(no acceptance commands extracted from task file)
```

## GLM response

**Material limit, stated once:** I was given a diffstat and test stdout, not hunks. Line-number citation is therefore impossible except where the output itself prints one. Everything below is constrained to what the evidence actually shows.

## 1. Production caller — NO CALLER (not demonstrable)

Every execution of the new code in evidence is a unittest under `.qwen\worktrees\verify-94140-tests\tests\`. The CLI-shaped stdout ("DRY RUN", "add --spend…", "--live is refused", "DRY RUN, no model called: 1 record(s)") is emitted from test bodies, not from any operator invocation. The task doc title (`TASK-400-generate-py-becomes-the-real-caller.md`) asserts that `src/generate.py` (+721) becomes the caller — but nothing shown calls *generate.py* outside `tests/`. I cannot construct the call edge from this material, so I say NO CALLER rather than guess that `run.py` (+48) wires it.

## 2. Acceptance check — VACUOUS

The header states it directly: "(no acceptance commands extracted from task file)". A check that does not run cannot fail on any input; I cannot name one. The only gate is 12 test files (+2,424 lines, incl. `tests/test_task400_rework3.py` +530) authored on this same branch — self-certification of a 3,808-insertion change.

Secondary, concrete: both "LIVE ENRICHMENT (credits spent)" blocks ran against `states {}` — the live path was exercised on **0 records**, so the "credits spent" smoke bought zero coverage of per-record live enrichment.

## 3. Numbers — they reconcile

- Per-file bars: 311 (docs) + 1,360 (src) + 2,424 (tests) = **4,095 = 3,808 insertions + 287 deletions**. ✓
- "1 record(s), model=none" ↔ rec-1 Ada Tester with exactly 10 gap lines (li1–li5, em1–em5). ✓
- One unreconciled print, no measurable cost: "no model ships with this repo: pass one to run(model=...)" prints immediately above "model=spy" — the advisory fires even when a model *was* passed. Cosmetic log contradiction.
- "0 record(s), model=spy" is consistent only because the adjacent state was empty (`states {}`). Not a defect on this evidence.

## Also-check

- **File not answering to the task:** `tests/test_task400_rework2.py` (+992) is *prior*-rework output landing first on the rework3 branch. If rework2 was previously accepted, it was accepted without these tests existing anywhere.
- **Scratch files:** changed set is all `.md`/`.py`; no `*.txt`/`*.err`/`*.out`. Untracked files aren't visible in this material — NO FINDING.
- **Concrete defect (test-side):** `tests/test_e2e.py:194` — `io.open(self.mx_cache, "w").write(...)` never closes the handle; ResourceWarning ×4 in this run. On Windows, the open handle on `%TEMP%\rga-e2e-run-*\mx-cache.json` can fail a later reopen/unlink. Confined to the suite.

VERDICT: FAIL - Completion is self-certified: zero acceptance commands exist to fail, the live-enrichment smoke covered 0 records, and no non-test caller of the +721-line generate.py rework is in evidence.
