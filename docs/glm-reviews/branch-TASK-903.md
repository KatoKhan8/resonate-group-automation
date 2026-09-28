# GLM branch verification: TASK-903

Branch: `qwen-worker-3-r9`
Date: 2026-09-28T17:19:49.467483+00:00
Model: glm-5.3
Duration: 109.571s
Usage: {'prompt_tokens': 11707, 'completion_tokens': 8319, 'total_tokens': 20026, 'reasoning_tokens': 7432, 'cached_tokens': 0}

## Verdict: FAIL

**9 new test failures not in baseline: ['test_generate.TestOnlyTwoEmailsAreGenerated.test_an_existing_draft_is_not_regenerated', 'test_generate.TestRungFourIsWritten.test_em4_is_stored_when_all_five_pass_lint', 'test_set_regeneration.GenerateRecordIntegrationTest.test_generate_record_replaces_colliding_set', 'test_set_regeneration.PlanIntegrationTest.test_plan_emits_linkedin_set_for_colliding_contact', 'test_set_regeneration.SetRegenerationDetectionTest.test_colliding_notes_trigger_set_regeneration']**

## GLM spend

This call: 0 ledger rows, 0 micro-USD

## New test failures

- `test_generate.TestOnlyTwoEmailsAreGenerated.test_an_existing_draft_is_not_regenerated`
- `test_generate.TestRungFourIsWritten.test_em4_is_stored_when_all_five_pass_lint`
- `test_set_regeneration.GenerateRecordIntegrationTest.test_generate_record_replaces_colliding_set`
- `test_set_regeneration.PlanIntegrationTest.test_plan_emits_linkedin_set_for_colliding_contact`
- `test_set_regeneration.SetRegenerationDetectionTest.test_colliding_notes_trigger_set_regeneration`
- `test_set_regeneration.SetRegenerationDetectionTest.test_intrinsically_failing_notes_excluded_from_passing`
- `test_the_research_pack_has_one_shape.AbsenceIsNotAnError.test_a_record_with_no_research_still_produces_copy`
- `test_the_research_pack_has_one_shape.AbsenceIsNotAnError.test_an_empty_list_is_the_same_as_absent`
- `test_the_research_pack_has_one_shape.TheCanonicalListProducesCopy.test_the_canonical_list_shape_produces_copy`

## Changed files (234)

- `.gitignore`
- `CLAUDE.md`
- `WEB-READINESS.md`
- `config/clients/productive-offers.yaml`
- `config/model-prices.yaml`
- `docs/A-CLEAN-REBASE-IS-NOT-A-COMPATIBLE-ONE.md`
- `docs/BRIEF-30K-POOL-SUPPLY-SAMPLE.md`
- `docs/BRIEF-P0E-CANONICAL-PROJECTION-INTEGRATION.md`
- `docs/COPYLINT-THE-LAST-SUBJECT-IS-EXEMPT-2026-09-28.md`
- `docs/CREDENTIAL-EXPOSURE-2026-09-28.md`
- `docs/FINDING-TASK-427-SELECTION-IS-PERSONA-PLUS-COMPOSITION.md`
- `docs/FINDING-THE-LAST-SUBJECT-IS-NOT-EXEMPT-FROM-FINALITY.md`
- `docs/FINDING-THE-RESEARCH-PACK-HAS-ONE-SHAPE-2026-09-28.md`
- `docs/OPERATING-MODE.md`
- `docs/PRODUCTION-HANDOFF-2026-09-28-EVENING.md`
- `docs/PRODUCTION-HANDOFF-2026-09-28-MIDDAY.md`
- `docs/PRODUCTION-HANDOFF-2026-09-28-NIGHT-MINIMUM-CLAUDE.md`
- `docs/TASK-400-REWORK3-MUTATIONS.md`
- `docs/TASK-425-FINDINGS-2026-09-28.md`
- `docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md`
- `docs/TASK-425-OPERATER-SAZETAK-2026-09-28.md`
- `docs/glm-reviews/TASK-433-verify-task-231.md`
- `docs/glm-reviews/TASK-435-verify-task-246.md`
- `docs/glm-reviews/TASK-436-verify-task-264.md`
- `docs/glm-reviews/TASK-442-verify-task-285.md`
- `docs/glm-reviews/TASK-444-verify-task-290.md`
- `docs/glm-reviews/TASK-451-verify-task-219.md`
- `docs/glm-reviews/TASK-454-verify-task-301.md`
- `docs/glm-reviews/TASK-460-verify-task-311.md`
- `docs/glm-reviews/TASK-465-verify-task-213.md`
- `docs/glm-reviews/TASK-468-verify-task-225.md`
- `docs/glm-reviews/TASK-471-verify-task-243.md`
- `docs/glm-reviews/TASK-472-verify-task-219.md`
- `docs/glm-reviews/TASK-473-verify-task-249.md`
- `docs/glm-reviews/TASK-475-verify-task-262.md`
- `docs/glm-reviews/TASK-476-verify-task-219.md`
- `docs/glm-reviews/TASK-481-verify-task-325.md`
- `docs/glm-reviews/TASK-482-verify-task-326.md`
- `docs/glm-reviews/TASK-487-verify-task-340.md`
- `docs/glm-reviews/TASK-490-verify-task-345.md`
- `docs/glm-reviews/TASK-491-verify-task-349.md`
- `docs/glm-reviews/TASK-494-verify-task-219.md`
- `docs/glm-reviews/TASK-497-verify-task-358.md`
- `docs/glm-reviews/TASK-500-verify-task-219.md`
- `docs/glm-reviews/TASK-503-verify-task-386.md`
- `docs/glm-reviews/TASK-505-verify-task-389.md`
- `docs/glm-reviews/TASK-508-verify-task-219.md`
- `docs/glm-reviews/TASK-509-verify-task-398.md`
- `docs/glm-reviews/TASK-512-verify-task-404.md`
- `docs/glm-reviews/TASK-515-verify-task-407.md`
- `docs/glm-reviews/TASK-519-verify-task-411.md`
- `docs/glm-reviews/TASK-522-verify-task-414.md`
- `docs/glm-reviews/TASK-525-verify-task-418.md`
- `docs/glm-reviews/TASK-527-verify-task-219.md`
- `docs/glm-reviews/TASK-530-verify-task-219.md`
- `docs/glm-reviews/TASK-531-verify-task-428.md`
- `docs/glm-reviews/TASK-534-verify-task-432.md`
- `docs/glm-reviews/TASK-536-verify-task-434.md`
- `docs/qwen-tasks/DONE/TASK-396-training-pair-capture-check.md`
- `docs/qwen-tasks/DONE/TASK-420-docs-hygiene-pass.md`
- `docs/qwen-tasks/DONE/TASK-433-glm-verify-task-231.md`
- `docs/qwen-tasks/DONE/TASK-436-glm-verify-task-264.md`
- `docs/qwen-tasks/DONE/TASK-449-three-order-dependent-failures.md`
- `docs/qwen-tasks/DONE/TASK-454-glm-verify-task-301.md`
- `docs/qwen-tasks/DONE/TASK-460-glm-verify-task-311.md`
- `docs/qwen-tasks/DONE/TASK-465-glm-verify-task-213.md`
- `docs/qwen-tasks/DONE/TASK-472-glm-verify-task-248.md`
- `docs/qwen-tasks/DONE/TASK-475-glm-verify-task-262.md`
- `docs/qwen-tasks/DONE/TASK-481-glm-verify-task-325.md`
- `docs/qwen-tasks/DONE/TASK-487-glm-verify-task-340.md`
- `docs/qwen-tasks/DONE/TASK-494-glm-verify-task-353.md`
- `docs/qwen-tasks/DONE/TASK-497-glm-verify-task-358.md`
- `docs/qwen-tasks/DONE/TASK-500-glm-verify-task-372.md`
- `docs/qwen-tasks/DONE/TASK-505-glm-verify-task-389.md`
- `docs/qwen-tasks/DONE/TASK-508-glm-verify-task-395.md`
- `docs/qwen-tasks/DONE/TASK-509-glm-verify-task-398.md`
- `docs/qwen-tasks/DONE/TASK-512-glm-verify-task-404.md`
- `docs/qwen-tasks/DONE/TASK-515-glm-verify-task-407.md`
- `docs/qwen-tasks/DONE/TASK-519-glm-verify-task-411.md`
- `docs/qwen-tasks/DONE/TASK-522-glm-verify-task-414.md`
- `docs/qwen-tasks/DONE/TASK-525-glm-verify-task-418.md`
- `docs/qwen-tasks/DONE/TASK-541-triage-pending-results-batch-04.md`
- `docs/qwen-tasks/DONE/TASK-544-triage-pending-results-batch-07.md`
- `docs/qwen-tasks/RESULTS/TASK-539-triage.md`
- `docs/qwen-tasks/RESULTS/TASK-541-triage.md`
- `docs/qwen-tasks/RESULTS/TASK-544-triage.md`
- `docs/qwen-tasks/REVIEW/TASK-319-five-skills-as-executable-sops.md`
- `docs/qwen-tasks/REVIEW/TASK-385-machine-derived-status-command.md`
- `docs/qwen-tasks/REVIEW/TASK-387-ledger-write-back-of-provider-sends-and-replies.md`
- `docs/qwen-tasks/REVIEW/TASK-407-glm-verify-task-399.md`
- `docs/qwen-tasks/REVIEW/TASK-408-glm-verify-task-319.md`
- `docs/qwen-tasks/REVIEW/TASK-414-spend-report-wiring-check.md`
- `docs/qwen-tasks/REVIEW/TASK-421-suppression-list-audit.md`
- `docs/qwen-tasks/REVIEW/TASK-435-glm-verify-task-246.md`
- `docs/qwen-tasks/REVIEW/TASK-442-glm-verify-task-285.md`
- `docs/qwen-tasks/REVIEW/TASK-444-glm-verify-task-290.md`
- `docs/qwen-tasks/REVIEW/TASK-451-glm-verify-task-279.md`
- `docs/qwen-tasks/REVIEW/TASK-468-glm-verify-task-225.md`
- `docs/qwen-tasks/REVIEW/TASK-471-glm-verify-task-243.md`
- `docs/qwen-tasks/REVIEW/TASK-473-glm-verify-task-249.md`
- `docs/qwen-tasks/REVIEW/TASK-476-glm-verify-task-266.md`
- `docs/qwen-tasks/REVIEW/TASK-482-glm-verify-task-326.md`
- `docs/qwen-tasks/REVIEW/TASK-491-glm-verify-task-349.md`
- `docs/qwen-tasks/REVIEW/TASK-503-glm-verify-task-386.md`
- `docs/qwen-tasks/REVIEW/TASK-527-glm-verify-task-420.md`
- `docs/qwen-tasks/REVIEW/TASK-531-glm-verify-task-428.md`
- `docs/qwen-tasks/REVIEW/TASK-534-glm-verify-task-432.md`
- `docs/qwen-tasks/REVIEW/TASK-536-glm-verify-task-434.md`
- `docs/qwen-tasks/REVIEW/TASK-539-triage-pending-results-batch-02.md`
- `docs/qwen-tasks/REVIEW/TASK-552-a-rung-is-a-question-not-an-assertion.md`
- `docs/qwen-tasks/REVIEW/TASK-558-a-possessive-is-still-an-assertion.md`
- `docs/qwen-tasks/REVIEW/TASK-559-a-rung-is-a-question-not-an-assertion.md`
- `docs/qwen-tasks/REVIEW/TASK-903-a-rung-is-a-question-not-an-assertion.md`
- `docs/qwen-tasks/TODO/TASK-319-five-skills-as-executable-sops.md`
- `docs/qwen-tasks/TODO/TASK-387-ledger-write-back-of-provider-sends-and-replies.md`
- `docs/qwen-tasks/TODO/TASK-396-training-pair-capture-check.md`
- `docs/qwen-tasks/TODO/TASK-400-generate-py-becomes-the-real-caller.md`
- `docs/qwen-tasks/TODO/TASK-407-glm-verify-task-399.md`
- `docs/qwen-tasks/TODO/TASK-408-glm-verify-task-319.md`
- `docs/qwen-tasks/TODO/TASK-414-spend-report-wiring-check.md`
- `docs/qwen-tasks/TODO/TASK-420-docs-hygiene-pass.md`
- `docs/qwen-tasks/TODO/TASK-421-suppression-list-audit.md`
- `docs/qwen-tasks/TODO/TASK-470-glm-verify-task-271.md`
- `docs/qwen-tasks/TODO/TASK-471-glm-verify-task-274.md`
- `docs/qwen-tasks/TODO/TASK-472-glm-verify-task-284.md`
- `docs/qwen-tasks/TODO/TASK-473-glm-verify-task-286.md`
- `docs/qwen-tasks/TODO/TASK-474-glm-verify-task-288.md`
- `docs/qwen-tasks/TODO/TASK-475-glm-verify-task-289.md`
- `docs/qwen-tasks/TODO/TASK-476-glm-verify-task-295.md`
- `docs/qwen-tasks/TODO/TASK-477-glm-verify-task-307.md`
- `docs/qwen-tasks/TODO/TASK-478-glm-verify-task-312.md`
- `docs/qwen-tasks/TODO/TASK-479-glm-verify-task-313.md`
- `docs/qwen-tasks/TODO/TASK-480-glm-verify-task-314.md`
- `docs/qwen-tasks/TODO/TASK-483-glm-verify-task-327.md`
- `docs/qwen-tasks/TODO/TASK-484-glm-verify-task-328.md`
- `docs/qwen-tasks/TODO/TASK-485-glm-verify-task-335.md`
- `docs/qwen-tasks/TODO/TASK-486-glm-verify-task-339.md`
- `docs/qwen-tasks/TODO/TASK-488-glm-verify-task-342.md`
- `docs/qwen-tasks/TODO/TASK-489-glm-verify-task-344.md`
- `docs/qwen-tasks/TODO/TASK-490-glm-verify-task-345.md`
- `docs/qwen-tasks/TODO/TASK-492-glm-verify-task-350.md`
- `docs/qwen-tasks/TODO/TASK-493-glm-verify-task-352.md`
- `docs/qwen-tasks/TODO/TASK-495-glm-verify-task-355.md`
- `docs/qwen-tasks/TODO/TASK-496-glm-verify-task-357.md`
- `docs/qwen-tasks/TODO/TASK-498-glm-verify-task-359.md`
- `docs/qwen-tasks/TODO/TASK-499-glm-verify-task-360.md`
- `docs/qwen-tasks/TODO/TASK-501-glm-verify-task-383.md`
- `docs/qwen-tasks/TODO/TASK-502-glm-verify-task-385.md`
- `docs/qwen-tasks/TODO/TASK-504-glm-verify-task-387.md`
- `docs/qwen-tasks/TODO/TASK-506-glm-verify-task-390.md`
- `docs/qwen-tasks/TODO/TASK-507-glm-verify-task-392.md`
- `docs/qwen-tasks/TODO/TASK-510-glm-verify-task-402.md`
- `docs/qwen-tasks/TODO/TASK-511-glm-verify-task-403.md`
- `docs/qwen-tasks/TODO/TASK-513-glm-verify-task-405.md`
- `docs/qwen-tasks/TODO/TASK-514-glm-verify-task-406.md`
- `docs/qwen-tasks/TODO/TASK-516-glm-verify-task-408.md`
- `docs/qwen-tasks/TODO/TASK-517-glm-verify-task-409.md`
- `docs/qwen-tasks/TODO/TASK-518-glm-verify-task-410.md`
- `docs/qwen-tasks/TODO/TASK-520-glm-verify-task-412.md`
- `docs/qwen-tasks/TODO/TASK-521-glm-verify-task-413.md`
- `docs/qwen-tasks/TODO/TASK-523-glm-verify-task-416.md`
- `docs/qwen-tasks/TODO/TASK-524-glm-verify-task-417.md`
- `docs/qwen-tasks/TODO/TASK-526-glm-verify-task-419.md`
- `docs/qwen-tasks/TODO/TASK-528-glm-verify-task-421.md`
- `docs/qwen-tasks/TODO/TASK-529-glm-verify-task-423.md`
- `docs/qwen-tasks/TODO/TASK-530-glm-verify-task-424.md`
- `docs/qwen-tasks/TODO/TASK-532-glm-verify-task-429.md`
- `docs/qwen-tasks/TODO/TASK-533-glm-verify-task-431.md`
- `docs/qwen-tasks/TODO/TASK-535-glm-verify-task-433.md`
- `docs/qwen-tasks/TODO/TASK-537-glm-verify-task-435.md`
- `docs/qwen-tasks/TODO/TASK-538-triage-pending-results-batch-01.md`
- `docs/qwen-tasks/TODO/TASK-540-triage-pending-results-batch-03.md`
- `docs/qwen-tasks/TODO/TASK-542-triage-pending-results-batch-05.md`
- `docs/qwen-tasks/TODO/TASK-543-triage-pending-results-batch-06.md`
- `docs/qwen-tasks/TODO/TASK-545-triage-pending-results-batch-08.md`
- `docs/qwen-tasks/TODO/TASK-546-glm-verify-task-425-head.md`
- `docs/qwen-tasks/TODO/TASK-547-a-recrawl-must-not-replace-evidence-with-nothing.md`
- `docs/qwen-tasks/TODO/TASK-548-li5-must-block-not-vanish.md`
- `docs/qwen-tasks/TODO/TASK-549-the-suite-baseline-is-stale-on-master.md`
- `docs/qwen-tasks/TODO/TASK-557-the-figure-gate-matches-a-four-character-prefix.md`
- `docs/qwen-tasks/TODO/TASK-560-the-ps-must-reach-the-person.md`
- `docs/qwen-tasks/TODO/TASK-561-every-email-carries-an-opt-out-line.md`
- `docs/qwen-tasks/TODO/TASK-562-the-projection-must-come-from-the-plan.md`
- `docs/qwen-tasks/TODO/TASK-563-the-signature-must-be-composed-into-the-copy.md`
- `docs/state/PROBLEM-REGISTER.md`
- `docs/state/PROVIDER-CAMPAIGNS.json`
- `docs/state/TASK-REGISTRY.json`
- `scripts/pool_status.py`
- `scripts/task425_artifact.py`
- `scripts/task425_criterion4_completeness.py`
- `scripts/task425_one_account_dry_run.py`
- `scripts/task425_verdict_mutations.py`
- `scripts/weekly_report_loop.py`
- `src/approve.py`
- `src/bisonfactory.py`
- `src/campaignstrategy.py`
- `src/claims.py`
- `src/copylint.py`
- `src/copystages.py`
- `src/generate.py`
- `src/generate_campaign.py`
- `src/heyreachfactory.py`
- `src/lint.py`
- `src/offers.py`
- `src/providers/bison.py`
- `src/providers/heyreach.py`
- `src/run.py`
- `src/sequencegate.py`
- `src/weeklyreportwatch.py`
- `tests/base.py`
- `tests/task425fixture.py`
- `tests/test_a_dead_cta_link_is_refused.py`
- `tests/test_a_linkedin_message_is_not_a_connection_request.py`
- `tests/test_a_possessive_is_still_an_assertion.py`
- `tests/test_a_rung_is_a_question_not_an_assertion.py`
- `tests/test_audit.py`
- `tests/test_changing_an_approved_fact_changes_the_output.py`
- `tests/test_e2e.py`
- `tests/test_generate.py`
- `tests/test_no_model_is_not_a_bad_record.py`
- `tests/test_only_the_last_subject_may_claim_finality.py`
- `tests/test_only_the_selected_offer_is_validated.py`
- `tests/test_pool_status.py`
- `tests/test_preproduction.py`
- `tests/test_qwen_cli_model.py`
- `tests/test_run.py`
- `tests/test_set_regeneration.py`
- `tests/test_task387_writeback_demo.py`
- `tests/test_task400_rework2.py`
- `tests/test_task400_rework3.py`
- `tests/test_the_offer_ladder_is_enforced_as_step_objectives.py`
- `tests/test_the_readback_cache_cannot_lie_about_its_age.py`
- `tests/test_the_research_pack_has_one_shape.py`
- `tests/test_the_weekly_client_post_is_off_until_reenabled.py`

## Diff stat

```
 .gitignore                                         |    1 +
 CLAUDE.md                                          |   62 +-
 WEB-READINESS.md                                   |   37 +-
 config/clients/productive-offers.yaml              |   25 +-
 config/model-prices.yaml                           |   22 +
 docs/A-CLEAN-REBASE-IS-NOT-A-COMPATIBLE-ONE.md     |  167 +
 docs/BRIEF-30K-POOL-SUPPLY-SAMPLE.md               |  112 +
 docs/BRIEF-P0E-CANONICAL-PROJECTION-INTEGRATION.md |  120 +
 ...PYLINT-THE-LAST-SUBJECT-IS-EXEMPT-2026-09-28.md |  286 +
 docs/CREDENTIAL-EXPOSURE-2026-09-28.md             |  375 ++
 ...SK-427-SELECTION-IS-PERSONA-PLUS-COMPOSITION.md |  140 +
 ...THE-LAST-SUBJECT-IS-NOT-EXEMPT-FROM-FINALITY.md |  106 +
 ...G-THE-RESEARCH-PACK-HAS-ONE-SHAPE-2026-09-28.md |  259 +
 docs/OPERATING-MODE.md                             |  412 ++
 docs/PRODUCTION-HANDOFF-2026-09-28-EVENING.md      |  304 +
 docs/PRODUCTION-HANDOFF-2026-09-28-MIDDAY.md       |  252 +
 ...TION-HANDOFF-2026-09-28-NIGHT-MINIMUM-CLAUDE.md |  199 +
 docs/TASK-400-REWORK3-MUTATIONS.md                 |  220 +
 docs/TASK-425-FINDINGS-2026-09-28.md               |  600 ++
 docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md      | 7092 ++++++++++++++++++++
 docs/TASK-425-OPERATER-SAZETAK-2026-09-28.md       |  142 +
 docs/glm-reviews/TASK-433-verify-task-231.md       |  172 +
 docs/glm-reviews/TASK-435-verify-task-246.md       |  281 +
 docs/glm-reviews/TASK-436-verify-task-264.md       |  181 +
 docs/glm-reviews/TASK-442-verify-task-285.md       |  156 +
 docs/glm-reviews/TASK-444-verify-task-290.md       |  201 +
 docs/glm-reviews/TASK-451-verify-task-219.md       |  398 ++
 docs/glm-reviews/TASK-454-verify-task-301.md       |  177 +
 docs/glm-reviews/TASK-460-verify-task-311.md       |  175 +
 docs/glm-reviews/TASK-465-verify-task-213.md       |  257 +
 docs/glm-reviews/TASK-468-verify-task-225.md       |  205 +
 docs/glm-reviews/TASK-471-verify-task-243.md       |  185 +
 docs/glm-reviews/TASK-472-verify-task-219.md       |  192 +
 docs/glm-reviews/TASK-473-verify-task-249.md       |  244 +
 docs/glm-reviews/TASK-475-verify-task-262.md       |  203 +
 docs/glm-reviews/TASK-476-verify-task-219.md       |  150 +
 docs/glm-reviews/TASK-481-verify-task-325.md       |  177 +
 docs/glm-reviews/TASK-482-verify-task-326.md       |  207 +
 docs/glm-reviews/TASK-487-verify-task-340.md       |  153 +
 docs/glm-reviews/TASK-490-verify-task-345.md       |  181 +
 docs/glm-reviews/TASK-491-verify-task-349.md       |  171 +
 docs/glm-reviews/TASK-494-verify-task-219.md       |  149 +
 docs/glm-reviews/TASK-497-verify-task-358.md       |  203 +
 docs/glm-reviews/TASK-500-verify-task-219.md       |  183 +
 docs/glm-reviews/TASK-503-verify-task-386.md       |  112 +
 docs/glm-reviews/TASK-505-verify-task-389.md       |  230 +
 docs/glm-reviews/TASK-508-verify-task-219.md       |  147 +
 docs/glm-reviews/TASK-509-verify-task-398.md       |  124 +
 docs/glm-reviews/TASK-512-verify-task-404.md       |  239 +
 docs/glm-reviews/TASK-515-verify-task-407.md       |  178 +
 docs/glm-reviews/TASK-519-verify-task-411.md       |  148 +
 docs/glm-reviews/TASK-522-verify-task-414.md       |  167 +
 docs/glm-reviews/TASK-525-verify-task-418.md       |  183 +
 docs/glm-reviews/TASK-527-verify-task-219.md       |  136 +
 docs/glm-reviews/TASK-530-verify-task-219.md       |  147 +
 docs/glm-reviews/TASK-531-verify-task-428.md       |  150 +
 docs/glm-reviews/TASK-534-verify-task-432.md       |  249 +
 docs/glm-reviews/TASK-536-verify-task-434.md       |  184 +
 .../DONE/TASK-396-training-pair-capture-check.md   |   79 +
 docs/qwen-tasks/DONE/TASK-420-docs-hygiene-pass.md |   98 +
 .../{TODO => DONE}/TASK-433-glm-verify-task-231.md |   43 +
 .../{TODO => DONE}/TASK-436-glm-verify-task-264.md |   44 +
 .../TASK-449-three-order-dependent-failures.md     |   97 +
 .../DONE/TASK-454-glm-verify-task-301.md           |  112 +
 .../{TODO => DONE}/TASK-460-glm-verify-task-311.md |    0
 .../DONE/TASK-465-glm-verify-task-213.md           |  146 +
 .../DONE/TASK-472-glm-verify-task-248.md           |  112 +
 .../DONE/TASK-475-glm-verify-task-262.md           |  114 +
 .../DONE/TASK-481-glm-verify-task-325.md           |  110 +
 .../DONE/TASK-487-glm-verify-task-340.md           |   96 +
 .../DONE/TASK-494-glm-verify-task-353.md           |  116 +
 .../DONE/TASK-497-glm-verify-task-358.md           |  110 +
 .../DONE/TASK-500-glm-verify-task-372.md           |  137 +
 .../DONE/TASK-505-glm-verify-task-389.md           |  117 +
 .../DONE/TASK-508-glm-verify-task-395.md           |  105 +
 .../DONE/TASK-509-glm-verify-task-398.md           |  114 +
 .../DONE/TASK-512-glm-verify-task-404.md           |  144 +
 .../DONE/TASK-515-glm-verify-task-407.md           |   94 +
 .../DONE/TASK-519-glm-verify-task-411.md           |  115 +
 .../DONE/TASK-522-glm-verify-task-414.md           |  124 +
 .../DONE/TASK-525-glm-verify-task-418.md           |  122 +
 .../TASK-541-triage-pending-results-batch-04.md    |  108 +
 .../TASK-544-triage-pending-results-batch-07.md    |  107 +
 docs/qwen-tasks/RESULTS/TASK-539-triage.md         |  797 +++
 docs/qwen-tasks/RESULTS/TASK-541-triage.md         |  609 ++
 docs/qwen-tasks/RESULTS/TASK-544-triage.md         |  565 ++
 .../TASK-319-five-skills-as-executable-sops.md     |   79 +
 .../TASK-385-machine-derived-status-command.md     |   44 +
 ...ger-write-back-of-provider-sends-and-replies.md |  273 +
 .../REVIEW/TASK-407-glm-verify-task-399.md         |  161 +
 .../REVIEW/TASK-408-glm-verify-task-319.md         |  110 +
 .../REVIEW/TASK-414-spend-report-wiring-check.md   |   74 +
 .../REVIEW/TASK-421-suppression-list-audit.md      |  145 +
 .../TASK-435-glm-verify-task-246.md                |    0
 .../TASK-442-glm-verify-task-285.md                |   36 +
 .../TASK-444-glm-verify-task-290.md                |    0
 .../TASK-451-glm-verify-task-279.md                |    0
 .../TASK-468-glm-verify-task-225.md                |    0
 .../TASK-471-glm-verify-task-243.md                |   29 +
 .../REVIEW/TASK-473-glm-verify-task-249.md         |  106 +
 .../TASK-476-glm-verify-task-266.md                |    0
 .../REVIEW/TASK-482-glm-verify-task-326.md         |  109 +
 .../REVIEW/TASK-491-glm-verify-task-349.md         |  102 +
 .../TASK-503-glm-verify-task-386.md}               |   14 +-
 .../REVIEW/TASK-527-glm-verify-task-420.md         |  109 +
 .../REVIEW/TASK-531-glm-verify-task-428.md         |   95 +
 .../REVIEW/TASK-534-glm-verify-task-432.md         |  103 +
 .../REVIEW/TASK-536-glm-verify-task-434.md         |  101 +
 .../TASK-539-triage-pending-results-batch-02.md    |   84 +
 ...SK-552-a-rung-is-a-question-not-an-assertion.md |  127 +
 .../TASK-558-a-possessive-is-still-an-assertion.md |  132 +
 ...SK-559-a-rung-is-a-question-not-an-assertion.md |  157 +
 ...SK-903-a-rung-is-a-question-not-an-assertion.md |  147 +
 .../TASK-319-five-skills-as-executable-sops.md     |   57 -
 ...ger-write-back-of-provider-sends-and-replies.md |   59 -
 .../TODO/TASK-396-training-pair-capture-check.md   |   30 -
 ...TASK-400-generate-py-becomes-the-real-caller.md |   91 +
 .../TODO/TASK-407-glm-verify-task-399.md           |   29 -
 .../TODO/TASK-408-glm-verify-task-319.md           |   26 -
 .../TODO/TASK-414-spend-report-wiring-check.md     |   14 -
 docs/qwen-tasks/TODO/TASK-420-docs-hygiene-pass.md |   16 -
 .../TODO/TASK-421-suppression-list-audit.md        |   17 -
 .../TODO/TASK-470-glm-verify-task-271.md           |   74 +
 .../TODO/TASK-471-glm-verify-task-274.md           |   74 +
 ...task-248.md => TASK-472-glm-verify-task-284.md} |   12 +-
 ...task-249.md => TASK-473-glm-verify-task-286.md} |   12 +-
 .../TODO/TASK-474-glm-verify-task-288.md           |   74 +
 ...task-262.md => TASK-475-glm-verify-task-289.md} |   12 +-
 .../TODO/TASK-476-glm-verify-task-295.md           |   74 +
 .../TODO/TASK-477-glm-verify-task-307.md           |   74 +
 .../TODO/TASK-478-glm-verify-task-312.md           |   74 +
 .../TODO/TASK-479-glm-verify-task-313.md           |   74 +
 .../TODO/TASK-480-glm-verify-task-314.md           |   74 +
 .../TODO/TASK-483-glm-verify-task-327.md           |   74 +
 .../TODO/TASK-484-glm-verify-task-328.md           |   74 +
 .../TODO/TASK-485-glm-verify-task-335.md           |   74 +
 .../TODO/TASK-486-glm-verify-task-339.md           |   74 +
 ...task-301.md => TASK-488-glm-verify-task-342.md} |   14 +-
 .../TODO/TASK-489-glm-verify-task-344.md           |   74 +
 .../TODO/TASK-490-glm-verify-task-345.md           |   74 +
 .../TODO/TASK-492-glm-verify-task-350.md           |   74 +
 .../TODO/TASK-493-glm-verify-task-352.md           |   74 +
 .../TODO/TASK-495-glm-verify-task-355.md           |   74 +
 .../TODO/TASK-496-glm-verify-task-357.md           |   74 +
 .../TODO/TASK-498-glm-verify-task-359.md           |   74 +
 .../TODO/TASK-499-glm-verify-task-360.md           |   74 +
 .../TODO/TASK-501-glm-verify-task-383.md           |   74 +
 .../TODO/TASK-502-glm-verify-task-385.md           |   74 +
 .../TODO/TASK-504-glm-verify-task-387.md           |   74 +
 .../TODO/TASK-506-glm-verify-task-390.md           |   74 +
 .../TODO/TASK-507-glm-verify-task-392.md           |   74 +
 .../TODO/TASK-510-glm-verify-task-402.md           |   74 +
 .../TODO/TASK-511-glm-verify-task-403.md           |   74 +
 .../TODO/TASK-513-glm-verify-task-405.md           |   74 +
 .../TODO/TASK-514-glm-verify-task-406.md           |   74 +
 .../TODO/TASK-516-glm-verify-task-408.md           |   74 +
 .../TODO/TASK-517-glm-verify-task-409.md           |   74 +
 .../TODO/TASK-518-glm-verify-task-410.md           |   74 +
 .../TODO/TASK-520-glm-verify-task-412.md           |   74 +
 .../TODO/TASK-521-glm-verify-task-413.md           |   74 +
 .../TODO/TASK-523-glm-verify-task-416.md           |   74 +
 .../TODO/TASK-524-glm-verify-task-417.md           |   74 +
 .../TODO/TASK-526-glm-verify-task-419.md           |   74 +
 .../TODO/TASK-528-glm-verify-task-421.md           |   74 +
 .../TODO/TASK-529-glm-verify-task-423.md           |   74 +
 .../TODO/TASK-530-glm-verify-task-424.md           |   74 +
 .../TODO/TASK-532-glm-verify-task-429.md           |   74 +
 .../TODO/TASK-533-glm-verify-task-431.md           |   74 +
 .../TODO/TASK-535-glm-verify-task-433.md           |   74 +
 .../TODO/TASK-537-glm-verify-task-435.md           |   74 +
 .../TASK-538-triage-pending-results-batch-01.md    |   84 +
 .../TASK-540-triage-pending-results-batch-03.md    |   84 +
 .../TASK-542-triage-pending-results-batch-05.md    |   84 +
 .../TASK-543-triage-pending-results-batch-06.md    |   84 +
 .../TASK-545-triage-pending-results-batch-08.md    |   82 +
 .../TODO/TASK-546-glm-verify-task-425-head.md      |   58 +
 ...crawl-must-not-replace-evidence-with-nothing.md |   75 +
 .../TODO/TASK-548-li5-must-block-not-vanish.md     |   60 +
 ...SK-549-the-suite-baseline-is-stale-on-master.md |   76 +
 ...-figure-gate-matches-a-four-character-prefix.md |  105 +
 .../TODO/TASK-560-the-ps-must-reach-the-person.md  |   75 +
 ...TASK-561-every-email-carries-an-opt-out-line.md |   82 +
 ...K-562-the-projection-must-come-from-the-plan.md |   89 +
 ...the-signature-must-be-composed-into-the-copy.md |   82 +
 docs/state/PROBLEM-REGISTER.md                     |  201 +
 docs/state/PROVIDER-CAMPAIGNS.json                 |  126 +-
 docs/state/TASK-REGISTRY.json                      | 2611 ++++++-
 scripts/pool_status.py                             |  422 ++
 scripts/task425_artifact.py                        |  973 +++
 scripts/task425_criterion4_completeness.py         |  122 +
 scripts/task425_one_account_dry_run.py             | 1604 +++++
 scripts/task425_verdict_mutations.py               |  155 +
 scripts/weekly_report_loop.py                      |   21 +
 src/approve.py                                     |   21 +
 src/bisonfactory.py                                |  138 +-
 src/campaignstrategy.py                            |   45 +-
 src/claims.py                                      |   19 +-
 src/copylint.py                                    |   21 +-
 src/copystages.py                                  |  118 +-
 src/generate.py                                    |  791 ++-
 src/generate_campaign.py                           |  662 +-
 src/heyreachfactory.py                             |    4 +
 src/lint.py                                        |   28 +-
 src/offers.py                                      |   19 +
 src/providers/bison.py                             |    5 +
 src/providers/heyreach.py                          |    5 +
 src/run.py                                         |   48 +-
 src/sequencegate.py                                |  410 +-
 src/weeklyreportwatch.py                           |   49 +
 tests/base.py                                      |  330 +-
 tests/task425fixture.py                            |  390 ++
 tests/test_a_dead_cta_link_is_refused.py           |   23 +-
 ...linkedin_message_is_not_a_connection_request.py |  106 +
 tests/test_a_possessive_is_still_an_assertion.py   |  177 +
 .../test_a_rung_is_a_question_not_an_assertion.py  |  412 ++
 tests/test_audit.py                                |   12 +-
 ...changing_an_approved_fact_changes_the_output.py |   91 +-
 tests/test_e2e.py                                  |   59 +-
 tests/test_generate.py                             |  257 +-
 tests/test_no_model_is_not_a_bad_record.py         |   10 +-
 ...est_only_the_last_subject_may_claim_finality.py |  550 ++
 tests/test_only_the_selected_offer_is_validated.py |  432 ++
 tests/test_pool_status.py                          |  160 +
 tests/test_preproduction.py                        |   17 +-
 tests/test_qwen_cli_model.py                       |   16 +-
 tests/test_run.py                                  |   64 +-
 tests/test_set_regeneration.py                     |  127 +-
 tests/test_task387_writeback_demo.py               |  257 +
 tests/test_task400_rework2.py                      |  992 +++
 tests/test_task400_rework3.py                      |  530 ++
 ..._offer_ladder_is_enforced_as_step_objectives.py |  635 ++
 ..._the_readback_cache_cannot_lie_about_its_age.py |   11 +-
 tests/test_the_research_pack_has_one_shape.py      |  483 ++
 ...he_weekly_client_post_is_off_until_reenabled.py |  124 +
 234 files changed, 43385 insertions(+), 1063 deletions(-)

```

## Acceptance output

```
(no acceptance commands extracted from task file)
```

## GLM response

## 1. Production caller

The diff body was not supplied (filenames + counts only), so I cannot cite hunks. What is checkable:

- TASK-903's rule ("a rung is a question not an assertion") lands in the existing lint path (`src/copylint.py` +21, `src/lint.py` +28, `src/sequencegate.py` +410), which the generate pipeline already invokes — the pasted output shows copylint-style refusals, so wiring exists by construction. No new bridge function is evident.
- The branch's largest new code units have **NO CALLER**: `scripts/task425_artifact.py` (973), `scripts/task425_one_account_dry_run.py` (1,604), `scripts/task425_criterion4_completeness.py` (122), `scripts/task425_verdict_mutations.py` (155) — 2,854 lines of standalone scripts; `scripts/pool_status.py` (422) is CLI-only. None is imported by `src/`.

## 2. Can the acceptance check fail?

**No — it is vacuous.** "(no acceptance commands extracted from task file)". There is no command to make fail. Worse, the "test results" block is not a runner transcript: it is interleaved stdout from ~6 script invocations, then unittest lines that cut off mid-identifier (`test_ex`) with **no `Ran N tests / OK` summary**. Exit=0 therefore attests nothing about `tests/test_a_rung_is_a_question_not_an_assertion.py` completing. There is also no TODO/DONE file for TASK-903 in the branch — only `REVIEW/TASK-903-...md`.

## 3. Numbers

- Diffstat "234 files": I count 233 entries in the list (±1). Reconciles.
- "1 record(s), model=none" + exactly 10 gap lines (li1–li5, em1–em5). Reconciles.
- **Does not reconcile:** `LIVE ENRICHMENT (credits spent)` appears **twice**, each followed by `states {}` — live provider credits spent with an empty per-state accounting map. The spend is claimed and recorded nowhere in the output. Cost: nonzero, unknown, and repeatable on every run of this test path since these prints come from it.
- 43,385 insertions vs. TASK-903's actual surface (one 412-line test file, one 147-line REVIEW doc, ~21-line lint delta): **~1.4% of the diff answers to the task.**

## Also

- **Files not answering to TASK-903:** essentially all of them. Named: all four `scripts/task425_*`, `tests/test_task400_rework2.py` (992), `tests/test_task400_rework3.py` (530), `tests/task425fixture.py` (390), `config/model-prices.yaml`, `scripts/pool_status.py`, `scripts/weekly_report_loop.py`, ~100 glm-review/TODO/DONE churn files. The branch's own doc `docs/A-CLEAN-REBASE-IS-NOT-A-COMPATIBLE-ONE.md` (167) concedes the rebase contamination.
- `docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md` is a **7,092-line generated artifact committed into docs/** — scratch output wearing a docs path; ~16% of the entire diff.
- `docs/CREDENTIAL-EXPOSURE-2026-09-28.md` (375 lines): must be grepped for the live secret before merge; if the token is in the file, merging writes it into git history permanently. This is a human check regardless of verdict.
- Root scratch files (*.txt/*.err/*.out): none. Clean.

## Verdict

VERDICT: FAIL - acceptance is vacuous (no commands extracted, test output truncated with no summary, live credits spent unrecorded) and ~98.6% of the 43k-line diff does not answer to TASK-903.
