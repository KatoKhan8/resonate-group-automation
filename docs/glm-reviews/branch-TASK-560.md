# GLM branch verification: TASK-560

Branch: `qwen-worker-r9`
Date: 2026-09-28T17:08:25.627714+00:00
Model: glm-5.3
Duration: 102.957s
Usage: {'prompt_tokens': 10947, 'completion_tokens': 8049, 'total_tokens': 18996, 'reasoning_tokens': 6937, 'cached_tokens': 8512}

## Verdict: FAIL

**6 new test failures not in baseline: ['test_task553_ps_must_reach_the_person.TestBodyWithPs.test_body_with_ps_appends', 'test_task553_ps_must_reach_the_person.TestBodyWithPs.test_empty_body_with_ps_returns_ps', 'test_task553_ps_must_reach_the_person.TestRenderIncludesPs.test_render_body_with_ps_appends', 'test_the_research_pack_has_one_shape.AbsenceIsNotAnError.test_a_record_with_no_research_still_produces_copy', 'test_the_research_pack_has_one_shape.AbsenceIsNotAnError.test_an_empty_list_is_the_same_as_absent']**

## GLM spend

This call: 0 ledger rows, 0 micro-USD

## New test failures

- `test_task553_ps_must_reach_the_person.TestBodyWithPs.test_body_with_ps_appends`
- `test_task553_ps_must_reach_the_person.TestBodyWithPs.test_empty_body_with_ps_returns_ps`
- `test_task553_ps_must_reach_the_person.TestRenderIncludesPs.test_render_body_with_ps_appends`
- `test_the_research_pack_has_one_shape.AbsenceIsNotAnError.test_a_record_with_no_research_still_produces_copy`
- `test_the_research_pack_has_one_shape.AbsenceIsNotAnError.test_an_empty_list_is_the_same_as_absent`
- `test_the_research_pack_has_one_shape.TheCanonicalListProducesCopy.test_the_canonical_list_shape_produces_copy`

## Changed files (199)

- `CLAUDE.md`
- `WEB-READINESS.md`
- `config/model-prices.yaml`
- `docs/BRIEF-30K-POOL-SUPPLY-SAMPLE.md`
- `docs/BRIEF-P0E-CANONICAL-PROJECTION-INTEGRATION.md`
- `docs/COPYLINT-THE-LAST-SUBJECT-IS-EXEMPT-2026-09-28.md`
- `docs/CREDENTIAL-EXPOSURE-2026-09-28.md`
- `docs/FINDING-TASK-427-SELECTION-IS-PERSONA-PLUS-COMPOSITION.md`
- `docs/FINDING-THE-RESEARCH-PACK-HAS-ONE-SHAPE-2026-09-28.md`
- `docs/OPERATING-MODE.md`
- `docs/PRODUCTION-HANDOFF-2026-09-28-EVENING.md`
- `docs/PRODUCTION-HANDOFF-2026-09-28-MIDDAY.md`
- `docs/PRODUCTION-HANDOFF-2026-09-28-NIGHT-MINIMUM-CLAUDE.md`
- `docs/PROVIDER-WRITE-SURFACE-2026-09-28.md`
- `docs/S7-FOUR-STEP-RENDER-VERIFICATION-2026-09-25.md`
- `docs/TASK-425-FINDINGS-2026-09-28.md`
- `docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md`
- `docs/TASK-425-OPERATER-SAZETAK-2026-09-28.md`
- `docs/glm-reviews/TASK-452-verify-task-219.md`
- `docs/glm-reviews/TASK-470-verify-task-219.md`
- `docs/glm-reviews/TASK-474-verify-task-219.md`
- `docs/glm-reviews/TASK-474-verify-task-250.md`
- `docs/glm-reviews/TASK-478-verify-task-219.md`
- `docs/glm-reviews/TASK-484-verify-task-328.md`
- `docs/glm-reviews/TASK-486-verify-task-339.md`
- `docs/glm-reviews/TASK-489-verify-task-344.md`
- `docs/glm-reviews/TASK-490-verify-task-345.md`
- `docs/glm-reviews/TASK-493-verify-task-219.md`
- `docs/glm-reviews/TASK-498-verify-task-359.md`
- `docs/glm-reviews/TASK-499-verify-task-360.md`
- `docs/glm-reviews/TASK-501-verify-task-383.md`
- `docs/glm-reviews/TASK-506-verify-task-390.md`
- `docs/glm-reviews/TASK-507-verify-task-219.md`
- `docs/glm-reviews/TASK-510-verify-task-402.md`
- `docs/glm-reviews/TASK-513-verify-task-405.md`
- `docs/glm-reviews/TASK-514-verify-task-219.md`
- `docs/glm-reviews/TASK-517-verify-task-219.md`
- `docs/glm-reviews/TASK-520-verify-task-412.md`
- `docs/glm-reviews/TASK-521-verify-task-413.md`
- `docs/glm-reviews/TASK-523-verify-task-219.md`
- `docs/glm-reviews/TASK-524-verify-task-219.md`
- `docs/glm-reviews/TASK-526-verify-task-419.md`
- `docs/glm-reviews/TASK-529-verify-task-423.md`
- `docs/glm-reviews/TASK-530-verify-task-424.md`
- `docs/glm-reviews/TASK-532-verify-task-429.md`
- `docs/glm-reviews/TASK-533-verify-task-219.md`
- `docs/glm-reviews/TASK-535-verify-task-433.md`
- `docs/glm-reviews/TASK-537-verify-task-435.md`
- `docs/glm-reviews/review-task425-2d54e274.md`
- `docs/glm-reviews/task-425-branch-review-2d54e274.md`
- `docs/qwen-tasks/DONE/TASK-273-a-conformance-suite-for-two-adapters-that-share-no-interface.md`
- `docs/qwen-tasks/DONE/TASK-298-absent-within-the-window-is-not-absent.md`
- `docs/qwen-tasks/DONE/TASK-452-glm-verify-task-296.md`
- `docs/qwen-tasks/DONE/TASK-470-glm-verify-task-240.md`
- `docs/qwen-tasks/DONE/TASK-478-glm-verify-task-312.md`
- `docs/qwen-tasks/DONE/TASK-484-glm-verify-task-328.md`
- `docs/qwen-tasks/DONE/TASK-498-glm-verify-task-359.md`
- `docs/qwen-tasks/DONE/TASK-499-glm-verify-task-360.md`
- `docs/qwen-tasks/DONE/TASK-501-glm-verify-task-383.md`
- `docs/qwen-tasks/DONE/TASK-504-glm-verify-task-387.md`
- `docs/qwen-tasks/DONE/TASK-506-glm-verify-task-390.md`
- `docs/qwen-tasks/DONE/TASK-514-glm-verify-task-406.md`
- `docs/qwen-tasks/DONE/TASK-520-glm-verify-task-412.md`
- `docs/qwen-tasks/DONE/TASK-521-glm-verify-task-413.md`
- `docs/qwen-tasks/DONE/TASK-523-glm-verify-task-416.md`
- `docs/qwen-tasks/DONE/TASK-526-glm-verify-task-419.md`
- `docs/qwen-tasks/DONE/TASK-529-glm-verify-task-423.md`
- `docs/qwen-tasks/DONE/TASK-533-glm-verify-task-431.md`
- `docs/qwen-tasks/DONE/TASK-535-glm-verify-task-433.md`
- `docs/qwen-tasks/DONE/TASK-537-glm-verify-task-435.md`
- `docs/qwen-tasks/DONE/TASK-539-triage-pending-results-batch-02.md`
- `docs/qwen-tasks/RESULTS/TASK-539-triage.md`
- `docs/qwen-tasks/RESULTS/TASK-540-triage.md`
- `docs/qwen-tasks/REVIEW/TASK-283-s7-renders-three-bodies-and-the-cadence-wants-four.md`
- `docs/qwen-tasks/REVIEW/TASK-395-spend-report-wiring.md`
- `docs/qwen-tasks/REVIEW/TASK-421-suppression-list-audit.md`
- `docs/qwen-tasks/REVIEW/TASK-449-three-order-dependent-failures.md`
- `docs/qwen-tasks/REVIEW/TASK-474-glm-verify-task-250.md`
- `docs/qwen-tasks/REVIEW/TASK-486-glm-verify-task-339.md`
- `docs/qwen-tasks/REVIEW/TASK-489-glm-verify-task-344.md`
- `docs/qwen-tasks/REVIEW/TASK-490-glm-verify-task-345.md`
- `docs/qwen-tasks/REVIEW/TASK-493-glm-verify-task-352.md`
- `docs/qwen-tasks/REVIEW/TASK-510-glm-verify-task-402.md`
- `docs/qwen-tasks/REVIEW/TASK-513-glm-verify-task-405.md`
- `docs/qwen-tasks/REVIEW/TASK-517-glm-verify-task-409.md`
- `docs/qwen-tasks/REVIEW/TASK-524-glm-verify-task-417.md`
- `docs/qwen-tasks/REVIEW/TASK-530-glm-verify-task-424.md`
- `docs/qwen-tasks/REVIEW/TASK-532-glm-verify-task-429.md`
- `docs/qwen-tasks/REVIEW/TASK-537-glm-verify-task-435.md`
- `docs/qwen-tasks/REVIEW/TASK-540-triage-pending-results-batch-03.md`
- `docs/qwen-tasks/REVIEW/TASK-546-glm-verify-task-425-head.md`
- `docs/qwen-tasks/REVIEW/TASK-548-li5-must-block-not-vanish.md`
- `docs/qwen-tasks/REVIEW/TASK-549-the-suite-baseline-is-stale-on-master.md`
- `docs/qwen-tasks/REVIEW/TASK-553-the-ps-must-reach-the-person.md`
- `docs/qwen-tasks/REVIEW/TASK-558-a-possessive-is-still-an-assertion.md`
- `docs/qwen-tasks/REVIEW/TASK-560-the-ps-must-reach-the-person.md`
- `docs/qwen-tasks/REVIEW/TASK-564-the-provider-write-surface.md`
- `docs/qwen-tasks/TODO/TASK-395-spend-report-wiring.md`
- `docs/qwen-tasks/TODO/TASK-421-suppression-list-audit.md`
- `docs/qwen-tasks/TODO/TASK-449-three-order-dependent-failures.md`
- `docs/qwen-tasks/TODO/TASK-470-glm-verify-task-271.md`
- `docs/qwen-tasks/TODO/TASK-471-glm-verify-task-274.md`
- `docs/qwen-tasks/TODO/TASK-472-glm-verify-task-284.md`
- `docs/qwen-tasks/TODO/TASK-473-glm-verify-task-286.md`
- `docs/qwen-tasks/TODO/TASK-474-glm-verify-task-288.md`
- `docs/qwen-tasks/TODO/TASK-475-glm-verify-task-289.md`
- `docs/qwen-tasks/TODO/TASK-476-glm-verify-task-295.md`
- `docs/qwen-tasks/TODO/TASK-477-glm-verify-task-307.md`
- `docs/qwen-tasks/TODO/TASK-479-glm-verify-task-313.md`
- `docs/qwen-tasks/TODO/TASK-480-glm-verify-task-314.md`
- `docs/qwen-tasks/TODO/TASK-481-glm-verify-task-325.md`
- `docs/qwen-tasks/TODO/TASK-482-glm-verify-task-326.md`
- `docs/qwen-tasks/TODO/TASK-483-glm-verify-task-327.md`
- `docs/qwen-tasks/TODO/TASK-485-glm-verify-task-335.md`
- `docs/qwen-tasks/TODO/TASK-487-glm-verify-task-340.md`
- `docs/qwen-tasks/TODO/TASK-488-glm-verify-task-342.md`
- `docs/qwen-tasks/TODO/TASK-491-glm-verify-task-349.md`
- `docs/qwen-tasks/TODO/TASK-492-glm-verify-task-350.md`
- `docs/qwen-tasks/TODO/TASK-494-glm-verify-task-353.md`
- `docs/qwen-tasks/TODO/TASK-495-glm-verify-task-355.md`
- `docs/qwen-tasks/TODO/TASK-496-glm-verify-task-357.md`
- `docs/qwen-tasks/TODO/TASK-497-glm-verify-task-358.md`
- `docs/qwen-tasks/TODO/TASK-500-glm-verify-task-372.md`
- `docs/qwen-tasks/TODO/TASK-502-glm-verify-task-385.md`
- `docs/qwen-tasks/TODO/TASK-503-glm-verify-task-386.md`
- `docs/qwen-tasks/TODO/TASK-505-glm-verify-task-389.md`
- `docs/qwen-tasks/TODO/TASK-507-glm-verify-task-392.md`
- `docs/qwen-tasks/TODO/TASK-508-glm-verify-task-395.md`
- `docs/qwen-tasks/TODO/TASK-509-glm-verify-task-398.md`
- `docs/qwen-tasks/TODO/TASK-511-glm-verify-task-403.md`
- `docs/qwen-tasks/TODO/TASK-512-glm-verify-task-404.md`
- `docs/qwen-tasks/TODO/TASK-515-glm-verify-task-407.md`
- `docs/qwen-tasks/TODO/TASK-516-glm-verify-task-408.md`
- `docs/qwen-tasks/TODO/TASK-518-glm-verify-task-410.md`
- `docs/qwen-tasks/TODO/TASK-519-glm-verify-task-411.md`
- `docs/qwen-tasks/TODO/TASK-522-glm-verify-task-414.md`
- `docs/qwen-tasks/TODO/TASK-525-glm-verify-task-418.md`
- `docs/qwen-tasks/TODO/TASK-527-glm-verify-task-420.md`
- `docs/qwen-tasks/TODO/TASK-528-glm-verify-task-421.md`
- `docs/qwen-tasks/TODO/TASK-531-glm-verify-task-428.md`
- `docs/qwen-tasks/TODO/TASK-534-glm-verify-task-432.md`
- `docs/qwen-tasks/TODO/TASK-536-glm-verify-task-434.md`
- `docs/qwen-tasks/TODO/TASK-538-triage-pending-results-batch-01.md`
- `docs/qwen-tasks/TODO/TASK-541-triage-pending-results-batch-04.md`
- `docs/qwen-tasks/TODO/TASK-542-triage-pending-results-batch-05.md`
- `docs/qwen-tasks/TODO/TASK-543-triage-pending-results-batch-06.md`
- `docs/qwen-tasks/TODO/TASK-544-triage-pending-results-batch-07.md`
- `docs/qwen-tasks/TODO/TASK-545-triage-pending-results-batch-08.md`
- `docs/qwen-tasks/TODO/TASK-547-a-recrawl-must-not-replace-evidence-with-nothing.md`
- `docs/qwen-tasks/TODO/TASK-565-the-incidents-become-regression-fixtures.md`
- `docs/qwen-tasks/TODO/TASK-901-the-figure-gate-matches-a-four-character-prefix.md`
- `docs/qwen-tasks/TODO/TASK-903-a-rung-is-a-question-not-an-assertion.md`
- `docs/qwen-tasks/TODO/TASK-904-every-email-carries-an-opt-out-line.md`
- `docs/qwen-tasks/TODO/TASK-905-the-projection-must-come-from-the-plan.md`
- `docs/qwen-tasks/TODO/TASK-906-the-signature-must-be-composed-into-the-copy.md`
- `docs/state/PROBLEM-REGISTER.md`
- `docs/state/PROVIDER-CAMPAIGNS.json`
- `docs/state/SUITE-BASELINE-2026-09-28-PARTIAL.txt`
- `docs/state/TASK-REGISTRY.json`
- `scripts/glm_verify_branch.py`
- `scripts/task425_artifact.py`
- `scripts/task425_criterion4_completeness.py`
- `scripts/task425_one_account_dry_run.py`
- `scripts/task425_verdict_mutations.py`
- `scripts/verify_s7_render.py`
- `scripts/weekly_report_loop.py`
- `src/approval.py`
- `src/approve.py`
- `src/bisonfactory.py`
- `src/campaignstrategy.py`
- `src/claims.py`
- `src/copylint.py`
- `src/copystages.py`
- `src/generate.py`
- `src/generate_campaign.py`
- `src/lint.py`
- `src/offers.py`
- `src/render.py`
- `src/sequencegate.py`
- `src/sequenceplan.py`
- `src/weeklyreportwatch.py`
- `tests/base.py`
- `tests/task425fixture.py`
- `tests/test_a_dead_cta_link_is_refused.py`
- `tests/test_a_linkedin_message_is_not_a_connection_request.py`
- `tests/test_a_possessive_is_still_an_assertion.py`
- `tests/test_adapter_conformance.py`
- `tests/test_e2e.py`
- `tests/test_glm_verify_branch_reads_attributed_spend.py`
- `tests/test_only_the_last_subject_may_claim_finality.py`
- `tests/test_only_the_selected_offer_is_validated.py`
- `tests/test_task548_payload_must_block.py`
- `tests/test_task553_ps_must_reach_the_person.py`
- `tests/test_task560_ps_reaches_the_person.py`
- `tests/test_the_four_step_render_has_every_variable.py`
- `tests/test_the_offer_ladder_is_enforced_as_step_objectives.py`
- `tests/test_the_readback_cache_cannot_lie_about_its_age.py`
- `tests/test_the_research_pack_has_one_shape.py`
- `tests/test_the_weekly_client_post_is_off_until_reenabled.py`

## Diff stat

```
 CLAUDE.md                                          |   62 +-
 WEB-READINESS.md                                   |   37 +-
 config/model-prices.yaml                           |   22 +
 docs/BRIEF-30K-POOL-SUPPLY-SAMPLE.md               |  112 +
 docs/BRIEF-P0E-CANONICAL-PROJECTION-INTEGRATION.md |  120 +
 ...PYLINT-THE-LAST-SUBJECT-IS-EXEMPT-2026-09-28.md |  286 +
 docs/CREDENTIAL-EXPOSURE-2026-09-28.md             |  375 ++
 ...SK-427-SELECTION-IS-PERSONA-PLUS-COMPOSITION.md |  140 +
 ...G-THE-RESEARCH-PACK-HAS-ONE-SHAPE-2026-09-28.md |  259 +
 docs/OPERATING-MODE.md                             |  475 ++
 docs/PRODUCTION-HANDOFF-2026-09-28-EVENING.md      |  304 +
 docs/PRODUCTION-HANDOFF-2026-09-28-MIDDAY.md       |  252 +
 ...TION-HANDOFF-2026-09-28-NIGHT-MINIMUM-CLAUDE.md |  240 +
 docs/PROVIDER-WRITE-SURFACE-2026-09-28.md          |  315 +
 .../S7-FOUR-STEP-RENDER-VERIFICATION-2026-09-25.md |  158 +
 docs/TASK-425-FINDINGS-2026-09-28.md               |  600 ++
 docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md      | 7092 ++++++++++++++++++++
 docs/TASK-425-OPERATER-SAZETAK-2026-09-28.md       |  142 +
 docs/glm-reviews/TASK-452-verify-task-219.md       |  208 +
 docs/glm-reviews/TASK-470-verify-task-219.md       |  322 +
 docs/glm-reviews/TASK-474-verify-task-219.md       |  163 +
 docs/glm-reviews/TASK-474-verify-task-250.md       |  176 +
 docs/glm-reviews/TASK-478-verify-task-219.md       |  207 +
 docs/glm-reviews/TASK-484-verify-task-328.md       |  114 +
 docs/glm-reviews/TASK-486-verify-task-339.md       |  216 +
 docs/glm-reviews/TASK-489-verify-task-344.md       |  251 +
 docs/glm-reviews/TASK-490-verify-task-345.md       |  271 +
 docs/glm-reviews/TASK-493-verify-task-219.md       |  217 +
 docs/glm-reviews/TASK-498-verify-task-359.md       |  316 +
 docs/glm-reviews/TASK-499-verify-task-360.md       |  191 +
 docs/glm-reviews/TASK-501-verify-task-383.md       |  253 +
 docs/glm-reviews/TASK-506-verify-task-390.md       |  202 +
 docs/glm-reviews/TASK-507-verify-task-219.md       |  185 +
 docs/glm-reviews/TASK-510-verify-task-402.md       |  166 +
 docs/glm-reviews/TASK-513-verify-task-405.md       |  229 +
 docs/glm-reviews/TASK-514-verify-task-219.md       |  207 +
 docs/glm-reviews/TASK-517-verify-task-219.md       |  138 +
 docs/glm-reviews/TASK-520-verify-task-412.md       |  189 +
 docs/glm-reviews/TASK-521-verify-task-413.md       |  216 +
 docs/glm-reviews/TASK-523-verify-task-219.md       |  350 +
 docs/glm-reviews/TASK-524-verify-task-219.md       |  238 +
 docs/glm-reviews/TASK-526-verify-task-419.md       |  177 +
 docs/glm-reviews/TASK-529-verify-task-423.md       |  266 +
 docs/glm-reviews/TASK-530-verify-task-424.md       |  186 +
 docs/glm-reviews/TASK-532-verify-task-429.md       |  212 +
 docs/glm-reviews/TASK-533-verify-task-219.md       |  184 +
 docs/glm-reviews/TASK-535-verify-task-433.md       |  172 +
 docs/glm-reviews/TASK-537-verify-task-435.md       |  279 +
 docs/glm-reviews/review-task425-2d54e274.md        |  222 +
 .../glm-reviews/task-425-branch-review-2d54e274.md |  203 +
 ...ite-for-two-adapters-that-share-no-interface.md |   30 +
 ...K-298-absent-within-the-window-is-not-absent.md |  129 +-
 .../DONE/TASK-452-glm-verify-task-296.md           |  108 +
 .../DONE/TASK-470-glm-verify-task-240.md           |  127 +
 .../DONE/TASK-478-glm-verify-task-312.md           |  130 +
 .../DONE/TASK-484-glm-verify-task-328.md           |   95 +
 .../DONE/TASK-498-glm-verify-task-359.md           |  110 +
 .../DONE/TASK-499-glm-verify-task-360.md           |   74 +
 .../DONE/TASK-501-glm-verify-task-383.md           |  118 +
 .../DONE/TASK-504-glm-verify-task-387.md           |  122 +
 .../DONE/TASK-506-glm-verify-task-390.md           |   85 +
 .../DONE/TASK-514-glm-verify-task-406.md           |  156 +
 .../DONE/TASK-520-glm-verify-task-412.md           |  120 +
 .../DONE/TASK-521-glm-verify-task-413.md           |  146 +
 .../DONE/TASK-523-glm-verify-task-416.md           |  147 +
 .../DONE/TASK-526-glm-verify-task-419.md           |   74 +
 .../DONE/TASK-529-glm-verify-task-423.md           |  113 +
 .../DONE/TASK-533-glm-verify-task-431.md           |  115 +
 .../DONE/TASK-535-glm-verify-task-433.md           |  114 +
 .../DONE/TASK-537-glm-verify-task-435.md           |  108 +
 .../TASK-539-triage-pending-results-batch-02.md    |   84 +
 docs/qwen-tasks/RESULTS/TASK-539-triage.md         |  605 ++
 docs/qwen-tasks/RESULTS/TASK-540-triage.md         |  611 ++
 ...ders-three-bodies-and-the-cadence-wants-four.md |   62 +-
 .../REVIEW/TASK-395-spend-report-wiring.md         |   96 +
 .../REVIEW/TASK-421-suppression-list-audit.md      |  186 +
 .../TASK-449-three-order-dependent-failures.md     |  210 +
 .../TASK-474-glm-verify-task-250.md                |   28 +
 .../REVIEW/TASK-486-glm-verify-task-339.md         |   74 +
 .../REVIEW/TASK-489-glm-verify-task-344.md         |  111 +
 .../REVIEW/TASK-490-glm-verify-task-345.md         |   74 +
 .../REVIEW/TASK-493-glm-verify-task-352.md         |  112 +
 .../REVIEW/TASK-510-glm-verify-task-402.md         |  126 +
 .../REVIEW/TASK-513-glm-verify-task-405.md         |   97 +
 .../REVIEW/TASK-517-glm-verify-task-409.md         |  109 +
 .../REVIEW/TASK-524-glm-verify-task-417.md         |  122 +
 .../REVIEW/TASK-530-glm-verify-task-424.md         |  108 +
 .../REVIEW/TASK-532-glm-verify-task-429.md         |  120 +
 .../REVIEW/TASK-537-glm-verify-task-435.md         |  126 +
 .../TASK-540-triage-pending-results-batch-03.md    |  125 +
 .../REVIEW/TASK-546-glm-verify-task-425-head.md    |  143 +
 .../REVIEW/TASK-548-li5-must-block-not-vanish.md   |  141 +
 ...SK-549-the-suite-baseline-is-stale-on-master.md |  181 +
 .../TASK-553-the-ps-must-reach-the-person.md       |  149 +
 .../TASK-558-a-possessive-is-still-an-assertion.md |  139 +
 .../TASK-560-the-ps-must-reach-the-person.md       |  139 +
 .../REVIEW/TASK-564-the-provider-write-surface.md  |  124 +
 .../TODO/TASK-395-spend-report-wiring.md           |   36 -
 .../TODO/TASK-421-suppression-list-audit.md        |   17 -
 .../TASK-449-three-order-dependent-failures.md     |   97 -
 ...task-240.md => TASK-470-glm-verify-task-271.md} |   12 +-
 .../TODO/TASK-471-glm-verify-task-274.md           |   74 +
 .../TODO/TASK-472-glm-verify-task-284.md           |   74 +
 .../TODO/TASK-473-glm-verify-task-286.md           |   74 +
 .../TODO/TASK-474-glm-verify-task-288.md           |   74 +
 .../TODO/TASK-475-glm-verify-task-289.md           |   74 +
 .../TODO/TASK-476-glm-verify-task-295.md           |   74 +
 .../TODO/TASK-477-glm-verify-task-307.md           |   74 +
 .../TODO/TASK-479-glm-verify-task-313.md           |   74 +
 ...task-296.md => TASK-480-glm-verify-task-314.md} |    8 +-
 .../TODO/TASK-481-glm-verify-task-325.md           |   74 +
 .../TODO/TASK-482-glm-verify-task-326.md           |   74 +
 .../TODO/TASK-483-glm-verify-task-327.md           |   74 +
 .../TODO/TASK-485-glm-verify-task-335.md           |   74 +
 .../TODO/TASK-487-glm-verify-task-340.md           |   74 +
 .../TODO/TASK-488-glm-verify-task-342.md           |   74 +
 .../TODO/TASK-491-glm-verify-task-349.md           |   74 +
 .../TODO/TASK-492-glm-verify-task-350.md           |   74 +
 .../TODO/TASK-494-glm-verify-task-353.md           |   74 +
 .../TODO/TASK-495-glm-verify-task-355.md           |   74 +
 .../TODO/TASK-496-glm-verify-task-357.md           |   74 +
 .../TODO/TASK-497-glm-verify-task-358.md           |   74 +
 .../TODO/TASK-500-glm-verify-task-372.md           |   74 +
 .../TODO/TASK-502-glm-verify-task-385.md           |   74 +
 .../TODO/TASK-503-glm-verify-task-386.md           |   74 +
 .../TODO/TASK-505-glm-verify-task-389.md           |   74 +
 .../TODO/TASK-507-glm-verify-task-392.md           |   74 +
 .../TODO/TASK-508-glm-verify-task-395.md           |   74 +
 .../TODO/TASK-509-glm-verify-task-398.md           |   74 +
 .../TODO/TASK-511-glm-verify-task-403.md           |   74 +
 .../TODO/TASK-512-glm-verify-task-404.md           |   74 +
 .../TODO/TASK-515-glm-verify-task-407.md           |   74 +
 .../TODO/TASK-516-glm-verify-task-408.md           |   74 +
 .../TODO/TASK-518-glm-verify-task-410.md           |   74 +
 .../TODO/TASK-519-glm-verify-task-411.md           |   74 +
 .../TODO/TASK-522-glm-verify-task-414.md           |   74 +
 .../TODO/TASK-525-glm-verify-task-418.md           |   74 +
 .../TODO/TASK-527-glm-verify-task-420.md           |   74 +
 .../TODO/TASK-528-glm-verify-task-421.md           |   74 +
 .../TODO/TASK-531-glm-verify-task-428.md           |   74 +
 .../TODO/TASK-534-glm-verify-task-432.md           |   74 +
 .../TODO/TASK-536-glm-verify-task-434.md           |   74 +
 .../TASK-538-triage-pending-results-batch-01.md    |   84 +
 .../TASK-541-triage-pending-results-batch-04.md    |   84 +
 .../TASK-542-triage-pending-results-batch-05.md    |   84 +
 .../TASK-543-triage-pending-results-batch-06.md    |   84 +
 .../TASK-544-triage-pending-results-batch-07.md    |   84 +
 .../TASK-545-triage-pending-results-batch-08.md    |   82 +
 ...crawl-must-not-replace-evidence-with-nothing.md |   75 +
 ...565-the-incidents-become-regression-fixtures.md |   72 +
 ...-figure-gate-matches-a-four-character-prefix.md |  105 +
 ...SK-903-a-rung-is-a-question-not-an-assertion.md |   85 +
 ...TASK-904-every-email-carries-an-opt-out-line.md |   82 +
 ...K-905-the-projection-must-come-from-the-plan.md |   89 +
 ...the-signature-must-be-composed-into-the-copy.md |   82 +
 docs/state/PROBLEM-REGISTER.md                     |  201 +
 docs/state/PROVIDER-CAMPAIGNS.json                 |  126 +-
 docs/state/SUITE-BASELINE-2026-09-28-PARTIAL.txt   |   90 +
 docs/state/TASK-REGISTRY.json                      | 2638 +++++++-
 scripts/glm_verify_branch.py                       |   10 +-
 scripts/task425_artifact.py                        |  973 +++
 scripts/task425_criterion4_completeness.py         |  122 +
 scripts/task425_one_account_dry_run.py             | 1604 +++++
 scripts/task425_verdict_mutations.py               |  155 +
 scripts/verify_s7_render.py                        |  452 ++
 scripts/weekly_report_loop.py                      |   21 +
 src/approval.py                                    |    9 +-
 src/approve.py                                     |    9 +-
 src/bisonfactory.py                                |  180 +-
 src/campaignstrategy.py                            |   45 +-
 src/claims.py                                      |    8 +
 src/copylint.py                                    |   21 +-
 src/copystages.py                                  |  106 +-
 src/generate.py                                    |   87 +-
 src/generate_campaign.py                           |  294 +-
 src/lint.py                                        |   28 +-
 src/offers.py                                      |   19 +
 src/render.py                                      |   24 +-
 src/sequencegate.py                                |  410 +-
 src/sequenceplan.py                                |   57 +-
 src/weeklyreportwatch.py                           |   49 +
 tests/base.py                                      |   45 +-
 tests/task425fixture.py                            |  390 ++
 tests/test_a_dead_cta_link_is_refused.py           |   21 +-
 ...linkedin_message_is_not_a_connection_request.py |  106 +
 tests/test_a_possessive_is_still_an_assertion.py   |  254 +
 tests/test_adapter_conformance.py                  |  393 ++
 tests/test_e2e.py                                  |    3 +-
 ...est_glm_verify_branch_reads_attributed_spend.py |   90 +
 ...est_only_the_last_subject_may_claim_finality.py |  550 ++
 tests/test_only_the_selected_offer_is_validated.py |  432 ++
 tests/test_task548_payload_must_block.py           |  137 +
 tests/test_task553_ps_must_reach_the_person.py     |  340 +
 tests/test_task560_ps_reaches_the_person.py        |  324 +
 ...test_the_four_step_render_has_every_variable.py |  433 ++
 ..._offer_ladder_is_enforced_as_step_objectives.py |  632 ++
 ..._the_readback_cache_cannot_lie_about_its_age.py |   11 +-
 tests/test_the_research_pack_has_one_shape.py      |  483 ++
 ...he_weekly_client_post_is_off_until_reenabled.py |  124 +
 199 files changed, 40382 insertions(+), 686 deletions(-)

```

## Acceptance output

```
(no acceptance commands extracted from task file)
```

## GLM response

## 1. Production caller

**NO CALLER nameable for TASK-560.** Exactly two files in a 199-file diff answer to TASK-560 by name: `docs/qwen-tasks/REVIEW/TASK-560-the-ps-must-reach-the-person.md` (139 lines) and `tests/test_task560_ps_reaches_the_person.py` (324 lines) — a doc and a test. The `src/` changes (`render.py` +24, `copystages.py` +106, `sequencegate.py` +410, `generate_campaign.py` +294) are shared across the branch's ~40 other tasks and no hunk is attributable to 560 from this diffstat, so I cannot cite a call site. Side flag: TASK-560's title and test are near-duplicates of TASK-553 (`test_task553_ps_must_reach_the_person.py`, 340 lines); cannot tell from the stat whether 560 ships logic or re-asserts 553.

## 2. Can the acceptance check fail

Yes — not vacuous. Concrete failing inputs appear in the branch's own evidence: a row with `body_1=""` → "FAIL 1 row(s) with issues: body_1: EMPTY" (runs 2, 4); a bad `--data` path → "FAIL file not found" (run 3); a surviving template literal in `body_1` → `unrender=1` (run 5).

## 3. Do the numbers reconcile

No, twice:

- **"rendered" contradicts the per-variable table.** Runs 2 and 4 print `1 rows total, 1 rendered, 0 held` while `body_1 present=0, empty=1`. Run 1's OK text defines rendered as "all rendered rows carry every variable non-empty" — under that definition run 2's `rendered=1` is false; if rendered only means "attempted," run 1's OK line is decoration. At the branch's own scale (`docs/BRIEF-30K-POOL-SUPPLY-SAMPLE.md`), a 2% empty rate on 30,000 rows reports "30000 rendered, 0 held" with 600 broken rows — the summary overstates deliverables by 600.
- **The evidence block is truncated mid-table in run 5** (`subject_1  1 0` — the unrender column and the final OK/FAIL line are missing) exactly where `body_1 unrender=1`. The last visible state is a failing state; "completed" cannot be confirmed from the provided output.

## Also checked

- **Scope:** ~195 of 199 files do not answer to TASK-560. Largest offenders: `docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md` (7,092 lines), `scripts/task425_*` (2,854 lines / 4 scripts), `tests/task425fixture.py` (390), `tests/test_the_offer_ladder_is_enforced_as_step_objectives.py` (632), `tests/test_adapter_conformance.py` (393), three PRODUCTION-HANDOFF docs, 60+ TODO/DONE files for tasks 470–906, `docs/state/TASK-REGISTRY.json` (+2,638). A catch-all branch makes per-task review of the `src/` hunks structurally impossible.
- **Registry skew:** `DONE/TASK-470-glm-verify-task-240.md` exists while its TODO was retitled `TASK-470-glm-verify-task-271.md` (diffstat rename); same pattern for 452/296 → 480/314. DONE records verify a different target than the TODO now names.
- **Baseline:** `docs/state/SUITE-BASELINE-2026-09-28-PARTIAL.txt` is committed as state while `REVIEW/TASK-549-the-suite-baseline-is-stale-on-master.md` declares the baseline stale — a partial baseline sits where a canonical one belongs.
- **`docs/CREDENTIAL-EXPOSURE-2026-09-28.md` (375 lines):** content unverifiable from a diffstat; if it quotes live tokens (this repo has a live provider write surface per `docs/PROVIDER-WRITE-SURFACE-2026-09-28.md`), they are permanent in git history. Needs a human read before merge.
- **Scratch files:** none at repo root. Only `*.txt` is the baseline above.
- **Task binding:** "(no acceptance commands extracted from task file)" — nothing ties the shown `verify_s7_render.py` runs to TASK-560; those runs gate the S7 four-step render, not "the PS must reach the person."

VERDICT: NEEDS_CLAUDE - acceptance log truncates before the final verdict with the last visible state failing, TASK-560's code is unattributable inside a 199-file catch-all branch, and CREDENTIAL-EXPOSURE-2026-09-28.md requires a human read for live secrets.
