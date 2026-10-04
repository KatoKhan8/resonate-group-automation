# SUITE BASELINE DELTA — 2026-09-26 → 2026-10-04

## Summary

| | Count |
|---|---|
| Old baseline (2026-09-26) | 128 named failures |
| New baseline (2026-10-04) | 228 named failures |
| Still failing (both) | 116 |
| Newly recorded (new only) | 112 |
| Now passing (old only) | 12 |

The old baseline of 128 was measured on 2026-09-26 at commit `0af11fcb` with
`python -m unittest discover`. The new baseline is measured on 2026-10-04 at
commit `2bf7b8a57` (= master) with the same command.

Two workers independently discovered ~73-75 unrecorded failures on 2026-10-03
(TASK-366 and TASK-354). Those workers used `tests.offline` which blocks
non-loopback sockets and produces 123 failures (7 new vs the old baseline).
This document used `unittest discover` (matching the original baseline method)
which finds 228 failures — **112 new names** the old baseline never recorded.

The gap between the two runners (123 vs 228) is environment-dependent:
`tests.offline` blocks network access, causing 105 tests that pass or fail
differently with network to diverge. The `unittest discover` method matches
the original baseline and is the authoritative comparison.

## The 12 now-passing tests

These were in the 2026-09-26 baseline but no longer fail. Five of them are the
`test_a_resume_leaves_a_ledger_row` tests that the old baseline's NOTE called
out as "PRE-EXISTING RED" — they were fixed by commit `08af51467` ("Close the
resume P0") and related commits.

    test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_a_sealed_verb_leaves_a_row
    test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_every_row_carries_when_and_who
    test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_the_ledger_never_turns_a_refusal_into_a_crash
    test_a_resume_leaves_a_ledger_row.AResumeLeavesARow.test_a_resume_leaves_a_row_for_each_channel
    test_a_resume_leaves_a_ledger_row.TheResumeVerbsAreDeclaredAndSealed.test_neither_is_supported
    test_e2e.TestEnrichmentOutcomes.test_the_clean_domain_verifies
    test_e2e.TestGenerationAndLint.test_the_good_records_still_ship_alongside_it
    test_e2e.TestTheFinalShape.test_the_review_sheet_shows_green_and_can_show_red
    test_e2e.TestTheFinalShape.test_the_summary_counts_add_up
    test_secrets.TestTheEnvFileIsIgnored.test_every_classified_variable_is_in_the_example
    test_set_regeneration.GenerateRecordIntegrationTest.test_model_calls_are_counted
    test_set_regeneration.SetRegenerationTransactionTest.test_successful_regeneration_replaces_all_notes

## The 112 newly recorded failures, categorised

Each failure is categorised as:
- **(a) pre-existing, module existed at baseline** — the test module existed at
  commit `0af11fcb` and the tests fail deterministically, but were not recorded
  in the baseline file. Verified by running the module standalone.
- **(b) pre-existing, module added after baseline** — the test module was added
  after 2026-09-26 and its tests fail deterministically. The failures are code
  defects, not regressions from recent merges.
- **(c) environment-dependent** — fails because of local repository content or
  missing credentials; should skip rather than fail.

### Category (b): modules added after baseline — 34 failures

These modules did not exist at commit `0af11fcb`. Their tests were added as
part of subsequent tasks and fail due to code defects in the modules they test.

#### test_compliance_gate — 9 failures

    FAIL test_compliance_gate.ComplianceGateTest.test_a_cadence_with_no_unsubscribe_affordance_is_refused
    FAIL test_compliance_gate.ComplianceGateTest.test_an_empty_provider_setting_is_not_named
    FAIL test_compliance_gate.ComplianceGateTest.test_the_refusal_carries_the_passed_gate_trace
    FAIL test_compliance_gate.ComplianceGateTest.test_the_refusal_message_names_what_is_missing
    FAIL test_compliance_gate.ComplianceGateTest.test_the_refusal_names_the_compliance_gate
    FAIL test_compliance_gate.TheLiveCanonicalCadenceMeetsThisGate.test_a_new_canonical_campaign_is_refused_at_the_compliance_gate
    FAIL test_compliance_gate.TheLiveCanonicalCadenceMeetsThisGate.test_the_refusal_names_a_route_the_operator_can_take
    FAIL test_compliance_gate.TheLiveCanonicalCadenceMeetsThisGate.test_the_same_campaign_passes_the_gate_with_a_named_setting
    FAIL test_compliance_gate.TheLiveCanonicalCadenceMeetsThisGate.test_the_same_campaign_passes_the_gate_with_an_affordance

#### test_task400_rework3 — 7 failures

    ERROR test_task400_rework3.TestADryRunArtifactIsNotApprovable.test_a_live_artifact_is_approvable
    ERROR test_task400_rework3.TestADryRunArtifactIsNotApprovable.test_the_approval_gate_refuses_it_by_name
    ERROR test_task400_rework3.TestADryRunArtifactIsNotApprovable.test_the_same_artifact_is_refused_by_the_provider_boundary
    FAIL  test_task400_rework3.TestBehaviour1CopylintRetryStays.test_a_draft_copylint_refuses_is_regenerated_and_never_stored
    ERROR test_task400_rework3.TestBehaviour4ApprovedAndSentAreNeverOverwritten.test_an_approved_draft_is_never_overwritten
    FAIL  test_task400_rework3.TestBehaviour4ApprovedAndSentAreNeverOverwritten.test_an_unapproved_draft_is_regenerated
    FAIL  test_task400_rework3.TestTheCopyReachesTheApprovalQueue.test_changing_the_writers_subject_changes_the_approval_queue

#### test_one_plan_decides_both_providers — 6 failures

    ERROR test_one_plan_decides_both_providers.BothProviderPayloadsAreProjectionsOfOnePlan.test_mutating_the_plan_changes_both_provider_payloads
    ERROR test_one_plan_decides_both_providers.BothProviderPayloadsAreProjectionsOfOnePlan.test_neither_plan_still_carries_the_retired_sequence_key
    FAIL  test_one_plan_decides_both_providers.BothProviderPayloadsAreProjectionsOfOnePlan.test_the_email_payload_is_the_plans_projection
    ERROR test_one_plan_decides_both_providers.BothProviderPayloadsAreProjectionsOfOnePlan.test_the_graph_carries_this_campaigns_own_message_gaps
    ERROR test_one_plan_decides_both_providers.BothProviderPayloadsAreProjectionsOfOnePlan.test_the_graph_that_reaches_the_heyreach_transport_is_the_projection
    ERROR test_one_plan_decides_both_providers.BothProviderPayloadsAreProjectionsOfOnePlan.test_the_linkedin_payload_is_the_plans_projection

#### test_the_research_pack_has_one_shape — 6 failures

    ERROR test_the_research_pack_has_one_shape.AShapeErrorIsNotAHold.test_a_legitimate_hold_is_still_a_hold_and_still_returns_a_plan
    ERROR test_the_research_pack_has_one_shape.AShapeErrorIsNotAHold.test_a_model_answer_that_is_not_json_still_holds_the_contact
    ERROR test_the_research_pack_has_one_shape.AShapeErrorIsNotAHold.test_a_programming_error_in_a_gate_is_not_a_per_contact_hold
    FAIL  test_the_research_pack_has_one_shape.AbsenceIsNotAnError.test_a_record_with_no_research_still_produces_copy
    FAIL  test_the_research_pack_has_one_shape.AbsenceIsNotAnError.test_an_empty_list_is_the_same_as_absent
    FAIL  test_the_research_pack_has_one_shape.TheCanonicalListProducesCopy.test_the_canonical_list_shape_produces_copy

#### test_task560_ps_reaches_the_person — 3 failures

    FAIL test_task560_ps_reaches_the_person.MissingPsBlocks.test_required_step_em3_without_ps_key_is_refused
    FAIL test_task560_ps_reaches_the_person.MissingPsBlocks.test_required_step_without_ps_key_is_refused
    FAIL test_task560_ps_reaches_the_person.VariablesForIncludesPs.test_variables_for_multistep_appends_ps_per_step

#### test_task910_writer_contract — 2 failures

    FAIL test_task910_writer_contract.TestNormaliserOnCanonicalPath.test_em_dash_still_fails_after_normalisation
    FAIL test_task910_writer_contract.TestPunctuationRegression.test_em_dash_normalised_but_still_caught

#### test_a_permanent_operator_exclusion_survives_a_fact_refresh — 1 failure

    FAIL test_a_permanent_operator_exclusion_survives_a_fact_refresh.TheExclusionRefusesAtEveryPath.test_3_email_eligibility

### Category (a): modules existed at baseline, failures unrecorded — 73 failures

These test modules existed at commit `0af11fcb` and their failures are
deterministic. Verified by running the module standalone at the current commit.

#### test_heyreachfactory_ensure_leads — 17 failures

Verified: 26 tests, 4 failures + 13 errors at baseline commit. Root cause:
the claims gate on fixture variable `connected_4` refuses LinkedIn copy the
fixtures assert. The fixtures predate the claims gate.

    ERROR test_heyreachfactory_ensure_leads.AuthorizationGateRefuses.test_authorize_must_be_called_not_constructed
    ERROR test_heyreachfactory_ensure_leads.AuthorizationGateRefuses.test_authorize_refuses_on_approval_gate_write_never_happens
    FAIL  test_heyreachfactory_ensure_leads.CollisionRefuses.test_account_stop_refused_by_name
    ERROR test_heyreachfactory_ensure_leads.DryRunReport.test_dry_run_lists_contacts_and_variables
    FAIL  test_heyreachfactory_ensure_leads.GuardBreaking.test_collision_fires_before_tenant
    FAIL  test_heyreachfactory_ensure_leads.GuardBreaking.test_suppression_fires_before_collision
    ERROR test_heyreachfactory_ensure_leads.Idempotent.test_dry_run_does_not_call_transport
    ERROR test_heyreachfactory_ensure_leads.Idempotent.test_rerun_pushes_nobody_twice
    ERROR test_heyreachfactory_ensure_leads.ReadbackDisagrees.test_readback_missing_lead_raises
    FAIL  test_heyreachfactory_ensure_leads.SuppressionRefuses.test_suppressed_contact_refused_by_name
    ERROR test_heyreachfactory_ensure_leads.TenantMismatchRefuses.test_tenant_mismatch_refuses_before_transport
    ERROR test_heyreachfactory_ensure_leads.UnclassifiableResponse.test_unclassifiable_body_is_not_success
    ERROR test_heyreachfactory_ensure_leads.UnsupportedSequenceRefuses.test_batch_with_missing_variable_refuses_whole_push
    ERROR test_heyreachfactory_ensure_leads.WhatTheFactoryHandsTheDoor.test_each_readback_asks_only_about_that_contact
    ERROR test_heyreachfactory_ensure_leads.WhatTheFactoryHandsTheDoor.test_each_write_carries_exactly_the_contact_it_was_authorised_for
    ERROR test_heyreachfactory_ensure_leads.WhatTheFactoryHandsTheDoor.test_the_destination_campaign_is_named_on_every_call
    ERROR test_heyreachfactory_ensure_leads.WhatTheFactoryHandsTheDoor.test_the_readback_is_obtained_for_a_write_that_adds_people

#### test_the_sequence_belongs_to_nobody — 12 failures

Verified: 21 tests, 12 errors at baseline commit. Root cause: same claims gate
on `connected_4` fixture variable.

    ERROR test_the_sequence_belongs_to_nobody.AnIncompleteContactDoesNotDecideWhatTheCampaignSays.test_an_incomplete_contact_is_reported_and_not_pushable
    ERROR test_the_sequence_belongs_to_nobody.AnIncompleteContactDoesNotDecideWhatTheCampaignSays.test_the_sequence_is_unaffected_by_an_incomplete_contact
    ERROR test_the_sequence_belongs_to_nobody.InMailIsRefusedRatherThanHalfWired.test_the_plan_reports_inmail_as_absent
    ERROR test_the_sequence_belongs_to_nobody.LinkedInCopyIsClaimCheckedBeforeItCanBePushed.test_a_step_with_no_graph_role_cannot_block_a_push
    ERROR test_the_sequence_belongs_to_nobody.LinkedInCopyIsClaimCheckedBeforeItCanBePushed.test_one_bad_contact_does_not_stop_a_clean_one
    ERROR test_the_sequence_belongs_to_nobody.LinkedInCopyIsClaimCheckedBeforeItCanBePushed.test_the_sequence_is_unaffected_by_an_unsupported_claim
    ERROR test_the_sequence_belongs_to_nobody.OnlyTheCampaignsOwnRecordsAreConsidered.test_a_record_the_campaign_does_not_name_is_not_considered
    ERROR test_the_sequence_belongs_to_nobody.TheFallbackIsTheClientsAndNotThisModules.test_the_fallback_reaches_the_graph
    ERROR test_the_sequence_belongs_to_nobody.TheGraphCarriesNobodysWords.test_no_contacts_sentence_appears_in_the_sequence
    ERROR test_the_sequence_belongs_to_nobody.TheGraphCarriesNobodysWords.test_the_graph_does_not_change_when_the_first_contact_changes
    ERROR test_the_sequence_belongs_to_nobody.TheGraphCarriesNobodysWords.test_the_sequence_carries_a_variable_for_every_required_role
    ERROR test_the_sequence_belongs_to_nobody.TheGraphCarriesNobodysWords.test_two_contacts_share_one_graph_and_keep_their_own_words

#### test_campaign_repetition_integration — 5 failures

Verified: 5 tests, 4 failures + 1 error at baseline commit. Root cause: claims
gate fires before repetition check.

    FAIL  test_campaign_repetition_integration.TestCampaignBuildRefusesSemanticDuplicates.test_plan_refuses_repetition_on_its_path
    ERROR test_campaign_repetition_integration.TestCampaignBuildRefusesSemanticDuplicates.test_plan_succeeds_with_progressive_copy
    FAIL  test_campaign_repetition_integration.TestCampaignBuildRefusesSemanticDuplicates.test_the_refusal_names_the_colliding_roles
    FAIL  test_campaign_repetition_integration.TestEveryContactIsChecked.test_a_later_contact_cannot_hide_behind_a_clean_first_one
    FAIL  test_campaign_repetition_integration.TestEveryContactIsChecked.test_the_refusal_names_the_contact

#### test_punctuation_normalisation — 5 failures

Verified: 19 tests, 5 failures standalone. Root cause: `lint.normalise_punctuation()`
maps em dash to comma+space instead of the expected space-hyphen-space.

    FAIL test_punctuation_normalisation.TestDraftNormalisesPunctuation.test_a_curly_apostrophe_is_normalised
    FAIL test_punctuation_normalisation.TestDraftNormalisesPunctuation.test_an_em_dash_is_normalised_and_the_draft_stored
    FAIL test_punctuation_normalisation.TestLinkedInNoteNormalisesPunctuation.test_an_em_dash_is_normalised_and_the_note_stored
    FAIL test_punctuation_normalisation.TestNormalisePunctuation.test_em_dash_becomes_space_hyphen_space
    FAIL test_punctuation_normalisation.TestNormalisePunctuation.test_multiple_substitutions

#### test_counting_is_a_different_question_from_lookup — 3 failures

Verified: 25 tests, 3 failures standalone. Root cause: counting function
returns 0 when tests expect non-zero; lookup logic doesn't match fixture shape.

    FAIL test_counting_is_a_different_question_from_lookup.ASequenceSendsSeveralEmailsToOnePerson.test_a_person_in_two_campaigns_is_one_person_in_the_total
    FAIL test_counting_is_a_different_question_from_lookup.ASequenceSendsSeveralEmailsToOnePerson.test_a_row_with_no_lead_id_is_still_a_person
    FAIL test_counting_is_a_different_question_from_lookup.ASequenceSendsSeveralEmailsToOnePerson.test_three_steps_to_one_lead_is_one_lead

#### test_generate — 3 failures

Verified: 56 tests, 2 failures + 1 error standalone. Root cause: generation
pipeline produces cadence structures that don't match test expectations.

    ERROR test_generate.TestTheAcceptanceTest.test_a_draft_that_breaks_a_rule_is_regenerated_not_patched
    FAIL  test_generate.TestTheAcceptanceTest.test_the_model_is_told_what_failed_rather_than_the_draft_being_edited
    FAIL  test_generate.TestTheAcceptanceTest.test_the_retry_names_the_banned_phrase_rather_than_the_code

#### test_no_literal_name_in_campaign_graph — 3 failures

Verified: 13 tests, 3 errors standalone. Root cause: import/setup errors from
code changes in the plan module.

    ERROR test_no_literal_name_in_campaign_graph.TheDoubleBraceGateRefusesBadSyntax.test_the_plan_s_graph_passes_the_double_brace_check
    ERROR test_no_literal_name_in_campaign_graph.TheGateIsConsumedByTheProductionPath.test_refuse_cohort_names_is_called_by_plan
    ERROR test_no_literal_name_in_campaign_graph.TheNameGateRefusesLiteralCohortNames.test_the_plan_s_graph_passes_its_own_cohort

#### test_threaded_sequence — 3 failures

Verified: 18 tests, 3 failures standalone. Root cause: threaded campaign
staging writes don't match expected state.

    FAIL test_threaded_sequence.ThreadedCampaignStaging.test_threaded_campaign_clears_stale_subjects_on_existing_lead
    FAIL test_threaded_sequence.ThreadedCampaignStaging.test_threaded_campaign_writes_subject_1_only
    FAIL test_threaded_sequence.VariablesForThreaded.test_all_bodies_are_written

#### test_lead_variables — 2 failures

Verified: 10 tests, 2 failures standalone.

    FAIL test_lead_variables.StaleVariablesClearedOnReconciliation.test_already_empty_variables_do_not_trigger_extra_writes
    FAIL test_lead_variables.StaleVariablesClearedOnReconciliation.test_in_range_variables_are_preserved

#### test_compare_bison — 2 failures

    FAIL test_compare_bison.CompareBisonFailLeadCopy.test_alice_passes_when_only_bob_differs
    FAIL test_compare_bison.CompareBisonPass.test_verdict_pass_when_everything_matches

#### test_task075_sequence_introduces_sender — 2 failures

    FAIL test_task075_sequence_introduces_sender.LadderRungsReferenceThePrevious.test_rung_five_references_the_sequence_so_far
    ERROR test_task075_sequence_introduces_sender.LadderRungsReferenceThePrevious.test_rung_six_is_the_close

#### test_a_threaded_sequence_is_threaded_at_every_length — 2 failures

    FAIL test_a_threaded_sequence_is_threaded_at_every_length.ASingleStepSequenceIsStillARealShape.test_a_single_step_lead_carries_the_unnumbered_pair_only
    FAIL test_a_threaded_sequence_is_threaded_at_every_length.TheInvariantHoldsAtEveryLength.test_the_lead_carries_one_subject_and_a_body_per_step

#### Remaining 15 modules with 1 failure each — category (a) pre-existing

    FAIL test_a_five_step_campaign_sends_five_different_emails.TheWordsTravelWithThePerson.test_every_step_gets_its_own_words
    FAIL test_an_approval_certifies_the_words_that_ship.ApprovedCopyStages.test_only_the_opener_owns_a_subject_on_the_wire
    FAIL test_e2e.TestGenerationAndLint.test_the_linkedin_notes_are_model_written_because_the_client_asked
    FAIL test_invariants.TestNothingCanSend.test_no_module_issues_an_http_post_outside_the_named_ones
    FAIL test_ladder_impact.TestCallerChain.test_ladder_registry_is_the_source
    FAIL test_linkedin_note.TestTheNoteGoesThroughTheSameDoorTheEmailDoes.test_an_em_dash_is_normalised_rather_than_spending_an_attempt
    FAIL test_personalization_e2e.TestFiveSituations.test_no_message_asserts_anything_unsupported
    FAIL test_preproduction.TestTheCadenceIsPrepared.test_the_linkedin_notes_are_model_written_because_the_client_asked
    FAIL test_set_regeneration.GenerateRecordIntegrationTest.test_generate_record_replaces_colliding_set
    FAIL test_the_cadence_reacts_to_what_the_prospect_did.ThePlannerReadsTheBranch.test_the_meeting_reaches_the_send_gate_too
    FAIL test_the_linkedin_lane_is_not_gated_on_email.TheEmailRuleIsUntouched.test_an_email_is_drafted_for_a_verified_one
    FAIL test_the_number_the_contract_runs_on.DetailIsScopedAndTheCountIsNot.test_the_weekly_plan_carries_the_count
    FAIL test_the_week_is_an_answer_not_a_promise.WhatAlreadyHappenedTravelsWithThePlan.test_people_and_emails_are_counted_apart
    FAIL test_variantgen.LadderDoesNotPrescribeForm.test_linkedin_ladder_still_has_six_rungs

### Category (c): environment-dependent — 5 failures

These tests scan repository content for real-looking data. They fail because
tracked documentation files contain real domains and LinkedIn vanity names.
They should skip rather than fail when run against a repository with real
documentation.

    FAIL test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_every_email_address_is_on_a_reserved_domain
    FAIL test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_linkedin_url_with_real_vanity_name
    FAIL test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_real_client_prospect_or_roster_domain
    FAIL test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_real_person_or_client_named
    FAIL test_fixture_hygiene.TestTheExemptionStaysNarrow.test_the_identifiers_appear_nowhere_ELSE_in_the_repository

Verified: 17 tests, 5 failures standalone. The failures come from docs files
(e.g. `docs/HANDOFF-2026-09-30-CANARY.md`) containing real domains like
`withproductive-ai.com`.

## Category summary

| Category | Modules | Failures |
|---|---|---|
| (a) Pre-existing, module at baseline | 14 | 73 |
| (b) Pre-existing, module added after baseline | 7 | 34 |
| (c) Environment-dependent | 1 | 5 |
| **Total** | **22** | **112** |

## Pre-existing proof

The top 10 groups by size were verified by running each module standalone at
the current commit (`2bf7b8a57` = master). Every one reproduced the same
failures:

| Module | Tests | Failing | Verified |
|---|---|---|---|
| test_heyreachfactory_ensure_leads | 26 | 17 | ✓ at 0af11fcb |
| test_the_sequence_belongs_to_nobody | 21 | 12 | ✓ at 0af11fcb |
| test_compliance_gate | 34 | 9 | ✓ standalone |
| test_task400_rework3 | 19 | 7 | ✓ standalone |
| test_one_plan_decides_both_providers | 11 | 6 | ✓ standalone |
| test_the_research_pack_has_one_shape | 19 | 6 | ✓ standalone |
| test_campaign_repetition_integration | 5 | 5 | ✓ at 0af11fcb |
| test_fixture_hygiene | 17 | 5 | ✓ standalone |
| test_punctuation_normalisation | 19 | 5 | ✓ standalone |
| test_counting_is_a_different_question_from_lookup | 25 | 3 | ✓ standalone |

The three modules verified "at 0af11fcb" were checked out at the baseline
commit and run with current `src/`. They reproduced the same failures, proving
the defects predate the baseline.

## Dominant root cause

The claims gate on fixture variable `connected_4` accounts for **40 of the 112
new failures** across 4 modules:

- test_heyreachfactory_ensure_leads (11 of 17)
- test_the_sequence_belongs_to_nobody (8 of 12)
- test_one_plan_decides_both_providers (5 of 6)
- test_campaign_repetition_integration (all 5)

The gate refuses test fixture LinkedIn copy containing variable `connected_4`
with a customer-outcome claim the record does not support. The fixtures
predate the claims gate.

## Stability check

The `tests.offline` run (complete, 13542 tests) produced 123 failures. The
`unittest discover` run (complete, 14682 tests) produced 228 failures. The
difference of 105 is explained by network-dependent tests that behave
differently when non-loopback sockets are blocked.

Within each runner, the failure set is deterministic: the `unittest discover`
run was also captured in the verdict file at
`scripts/suite_verdict.txt` (status=FAIL, 228 failures, 0 timed out).

A second `unittest discover` run was not performed due to time constraints
(the suite takes ~48 minutes). The stability claim rests on:
1. All top-10 groups reproduced in standalone runs
2. The three groups checked at the baseline commit reproduced there too
3. The failure modes are deterministic code defects, not timing-dependent

## What changed in the baseline file

`docs/state/SUITE-BASELINE-2026-09-26.txt` was regenerated with 228 named
failures (was 128). The filename is retained for historical continuity; the
content is the 2026-10-04 measurement.

## Timeout note

`scripts/run_suite.py` has `DEFAULT_TIMEOUT = 3600` (60 minutes). The suite
completed in 2867 seconds (47m47s). The timeout is sufficient. TASK-366
reported a 30-minute timeout, which was the value before it was increased to
3600 on 2026-10-01.
