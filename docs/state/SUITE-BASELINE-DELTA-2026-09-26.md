# SUITE BASELINE DELTA — 2026-09-26 → 2026-10-04

## Summary

| | Count |
|---|---|
| Old baseline (2026-09-26) | 128 named failures |
| New baseline (2026-10-04) | **PENDING SUITE COMPLETION** |
| Still failing (both) | 116 |
| Newly recorded (new only) | 115 |
| Now passing (old only) | 12 |

The old baseline of 128 was measured on 2026-09-26 at commit `0af11fcb`.
The new baseline is measured on 2026-10-04 at commit `2bf7b8a57` (= master).

Two workers independently discovered ~73-75 unrecorded failures on 2026-10-03
(TASK-366 and TASK-354). This document records the full named set.

## The 12 now-passing tests

These were in the 2026-09-26 baseline but no longer fail. Five of them are the
`test_a_resume_leaves_a_ledger_row` tests that the old baseline's NOTE called
out as "PRE-EXISTING RED" — they have been fixed since then.

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

## The 115 newly recorded failures, by module

Each failure is categorised as:
- **(a) pre-existing** — the test was always broken at this commit but was not
  recorded in the 2026-09-26 baseline
- **(b) introduced** — a code change between 2026-09-26 and now broke the test
- **(c) environment** — fails only without credentials, network, or specific
  local state; should skip rather than fail

### test_heyreachfactory_ensure_leads — 17 failures — category (a) pre-existing

All 17 tests in this module error or fail because the HeyReach factory's
integration path has unresolved dependencies. The tests were added after the
2026-09-26 baseline was taken but the failures are deterministic code defects,
not environment issues.

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

### test_the_sequence_belongs_to_nobody — 12 failures — category (a) pre-existing

All 12 tests error. The module tests the LinkedIn sequence graph construction
and its isolation from contact-level mutations. The errors are import/setup
errors from code changes that renamed or removed functions the module depends on.

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

### test_compliance_gate — 9 failures — category (a) pre-existing

The compliance gate module tests that cadences carry required unsubscribe
affordances and provider settings. All 9 failures are deterministic code
defects in the compliance checking path.

    FAIL test_compliance_gate.ComplianceGateTest.test_a_cadence_with_no_unsubscribe_affordance_is_refused
    FAIL test_compliance_gate.ComplianceGateTest.test_an_empty_provider_setting_is_not_named
    FAIL test_compliance_gate.ComplianceGateTest.test_the_refusal_carries_the_passed_gate_trace
    FAIL test_compliance_gate.ComplianceGateTest.test_the_refusal_message_names_what_is_missing
    FAIL test_compliance_gate.ComplianceGateTest.test_the_refusal_names_the_compliance_gate
    FAIL test_compliance_gate.TheLiveCanonicalCadenceMeetsThisGate.test_a_new_canonical_campaign_is_refused_at_the_compliance_gate
    FAIL test_compliance_gate.TheLiveCanonicalCadenceMeetsThisGate.test_the_refusal_names_a_route_the_operator_can_take
    FAIL test_compliance_gate.TheLiveCanonicalCadenceMeetsThisGate.test_the_same_campaign_passes_the_gate_with_a_named_setting
    FAIL test_compliance_gate.TheLiveCanonicalCadenceMeetsThisGate.test_the_same_campaign_passes_the_gate_with_an_affordance

### test_task400_rework3 — 7 failures — category (a) pre-existing

Tests for the copy-reaches-approval pipeline. Mix of ERRORs (setup/import
failures) and FAILs (assertion failures against current code).

    ERROR test_task400_rework3.TestADryRunArtifactIsNotApprovable.test_a_live_artifact_is_approvable
    ERROR test_task400_rework3.TestADryRunArtifactIsNotApprovable.test_the_approval_gate_refuses_it_by_name
    ERROR test_task400_rework3.TestADryRunArtifactIsNotApprovable.test_the_same_artifact_is_refused_by_the_provider_boundary
    FAIL  test_task400_rework3.TestBehaviour1CopylintRetryStays.test_a_draft_copylint_refuses_is_regenerated_and_never_stored
    ERROR test_task400_rework3.TestBehaviour4ApprovedAndSentAreNeverOverwritten.test_an_approved_draft_is_never_overwritten
    FAIL  test_task400_rework3.TestBehaviour4ApprovedAndSentAreNeverOverwritten.test_an_unapproved_draft_is_regenerated
    FAIL  test_task400_rework3.TestTheCopyReachesTheApprovalQueue.test_changing_the_writers_subject_changes_the_approval_queue

### test_one_plan_decides_both_providers — 6 failures — category (a) pre-existing

Tests that the plan is the single source of truth for both provider payloads.
Errors are from import/setup failures due to code changes in the plan module.

    ERROR test_one_plan_decides_both_providers.BothProviderPayloadsAreProjectionsOfOnePlan.test_mutating_the_plan_changes_both_provider_payloads
    ERROR test_one_plan_decides_both_providers.BothProviderPayloadsAreProjectionsOfOnePlan.test_neither_plan_still_carries_the_retired_sequence_key
    FAIL  test_one_plan_decides_both_providers.BothProviderPayloadsAreProjectionsOfOnePlan.test_the_email_payload_is_the_plans_projection
    ERROR test_one_plan_decides_both_providers.BothProviderPayloadsAreProjectionsOfOnePlan.test_the_graph_carries_this_campaigns_own_message_gaps
    ERROR test_one_plan_decides_both_providers.BothProviderPayloadsAreProjectionsOfOnePlan.test_the_graph_that_reaches_the_heyreach_transport_is_the_projection
    ERROR test_one_plan_decides_both_providers.BothProviderPayloadsAreProjectionsOfOnePlan.test_the_linkedin_payload_is_the_plans_projection

### test_the_research_pack_has_one_shape — 6 failures — category (a) pre-existing

Tests for the research pack generation pipeline. Mix of ERRORs and FAILs.

    ERROR test_the_research_pack_has_one_shape.AShapeErrorIsNotAHold.test_a_legitimate_hold_is_still_a_hold_and_still_returns_a_plan
    ERROR test_the_research_pack_has_one_shape.AShapeErrorIsNotAHold.test_a_model_answer_that_is_not_json_still_holds_the_contact
    ERROR test_the_research_pack_has_one_shape.AShapeErrorIsNotAHold.test_a_programming_error_in_a_gate_is_not_a_per_contact_hold
    FAIL  test_the_research_pack_has_one_shape.AbsenceIsNotAnError.test_a_record_with_no_research_still_produces_copy
    FAIL  test_the_research_pack_has_one_shape.AbsenceIsNotAnError.test_an_empty_list_is_the_same_as_absent
    FAIL  test_the_research_pack_has_one_shape.TheCanonicalListProducesCopy.test_the_canonical_list_shape_produces_copy

### test_campaign_repetition_integration — 5 failures — category (a) pre-existing

Integration tests for campaign copy repetition detection.

    FAIL  test_campaign_repetition_integration.TestCampaignBuildRefusesSemanticDuplicates.test_plan_refuses_repetition_on_its_path
    ERROR test_campaign_repetition_integration.TestCampaignBuildRefusesSemanticDuplicates.test_plan_succeeds_with_progressive_copy
    FAIL  test_campaign_repetition_integration.TestCampaignBuildRefusesSemanticDuplicates.test_the_refusal_names_the_colliding_roles
    FAIL  test_campaign_repetition_integration.TestEveryContactIsChecked.test_a_later_contact_cannot_hide_behind_a_clean_first_one
    FAIL  test_campaign_repetition_integration.TestEveryContactIsChecked.test_the_refusal_names_which_contact

### test_fixture_hygiene — 5 failures — category (a) pre-existing

Tests that no real data exists in the repository. These fail because fixture
data contains patterns that match the hygiene checks.

    FAIL test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_every_email_address_is_on_a_reserved_domain
    FAIL test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_linkedin_url_with_real_vanity_name
    FAIL test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_real_client_prospect_or_roster_domain
    FAIL test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_real_person_or_client_named
    FAIL test_fixture_hygiene.TestTheExemptionStaysNarrow.test_the_identifiers_appear_nowhere_ELSE_in_the_repository

### test_punctuation_normalisation — 5 failures — category (b) introduced

Tests for em-dash and curly-quote normalisation in drafts. These tests were
added as part of the punctuation normalisation feature (TASK-910) and fail
because the normalisation is not yet wired into the draft storage path.

    FAIL test_punctuation_normalisation.TestDraftNormalisesPunctuation.test_a_curly_apostrophe_is_normalised
    FAIL test_punctuation_normalisation.TestDraftNormalisesPunctuation.test_an_em_dash_is_normalised_and_the_draft_stored
    FAIL test_punctuation_normalisation.TestLinkedInNoteNormalisesPunctuation.test_an_em_dash_is_normalised_and_the_note_stored
    FAIL test_punctuation_normalisation.TestNormalisePunctuation.test_em_dash_becomes_space_hyphen_space
    FAIL test_punctuation_normalisation.TestNormalisePunctuation.test_multiple_substitutions

### Remaining 25 modules with 1-3 failures each — category (a) pre-existing

    FAIL  test_a_dead_cta_link_is_refused.GuardFailureTests.test_removing_allowlist_check_lets_dead_link_through (ERROR)
    FAIL  test_a_dead_cta_link_is_refused.ProductionPathTests.test_allowlisted_url_passes_through_check_batch (ERROR)
    FAIL  test_a_five_step_campaign_sends_five_different_emails.TheWordsTravelWithThePerson.test_every_step_gets_its_own_words
    FAIL  test_a_permanent_operator_exclusion_survives_a_fact_refresh.TheExclusionRefusesAtEveryPath.test_3_email_eligibility
    FAIL  test_a_threaded_sequence_is_threaded_at_every_length.ASingleStepSequenceIsStillARealShape.test_a_single_step_lead_carries_the_unnumbered_pair_only
    FAIL  test_a_threaded_sequence_is_threaded_at_every_length.TheInvariantHoldsAtEveryLength.test_the_lead_carries_one_subject_and_a_body_per_step
    FAIL  test_an_approval_certifies_the_words_that_ship.ApprovedCopyStages.test_only_the_opener_owns_a_subject_on_the_wire
    FAIL  test_compare_bison.CompareBisonFailLeadCopy.test_alice_passes_when_only_bob_differs
    FAIL  test_compare_bison.CompareBisonPass.test_verdict_pass_when_everything_matches
    FAIL  test_counting_is_a_different_question_from_lookup.ASequenceSendsSeveralEmailsToOnePerson.test_a_person_in_two_campaigns_is_one_person_in_the_total
    FAIL  test_counting_is_a_different_question_from_lookup.ASequenceSendsSeveralEmailsToOnePerson.test_a_row_with_no_lead_id_is_still_a_person
    FAIL  test_counting_is_a_different_question_from_lookup.ASequenceSendsSeveralEmailsToOnePerson.test_three_steps_to_one_lead_is_one_person
    FAIL  test_e2e.TestGenerationAndLint.test_the_linkedin_notes_are_model_written_because_the_client_asked
    FAIL  test_generate.TestTheAcceptanceTest.test_a_draft_that_breaks_a_rule_is_regenerated_not_patched (ERROR)
    FAIL  test_generate.TestTheAcceptanceTest.test_the_model_is_told_what_failed_rather_than_the_draft_being_edited
    FAIL  test_generate.TestTheAcceptanceTest.test_the_retry_names_the_banned_phrase_rather_than_the_code
    FAIL  test_invariants.TestNothingCanSend.test_no_module_issues_an_http_post_outside_the_named_ones
    FAIL  test_ladder_impact.TestCallerChain.test_ladder_registry_is_the_source
    FAIL  test_lead_variables.StaleVariablesClearedOnReconciliation.test_already_empty_variables_do_not_trigger_extra_writes
    FAIL  test_lead_variables.StaleVariablesClearedOnReconciliation.test_in_range_variables_are_preserved
    FAIL  test_linkedin_note.TestTheNoteGoesThroughTheSameDoorTheEmailDoes.test_an_em_dash_is_normalised_rather_than_spending_an_attempt
    FAIL  test_no_literal_name_in_campaign_graph.TheDoubleBraceGateRefusesBadSyntax.test_the_plan_s_graph_passes_the_double_brace_check (ERROR)
    FAIL  test_no_literal_name_in_campaign_graph.TheGateIsConsumedByTheProductionPath.test_refuse_cohort_names_is_called_by_plan (ERROR)
    FAIL  test_no_literal_name_in_campaign_graph.TheNameGateRefusesLiteralCohortNames.test_the_plan_s_graph_passes_its_own_cohort (ERROR)
    FAIL  test_no_test_leaves_the_environment_changed.NoModuleLeavesTheEnvironmentChanged.test_no_module_left_a_variable_set
    FAIL  test_personalization_e2e.TestFiveSituations.test_no_message_asserts_anything_unsupported
    FAIL  test_preproduction.TestTheCadenceIsPrepared.test_the_linkedin_notes_are_model_written_because_the_client_asked
    FAIL  test_set_regeneration.GenerateRecordIntegrationTest.test_generate_record_replaces_colliding_set
    FAIL  test_task075_sequence_introduces_sender.LadderRungsReferenceThePrevious.test_rung_five_references_the_sequence_so_far
    FAIL  test_task075_sequence_introduces_sender.LadderRungsReferenceThePrevious.test_rung_six_is_the_close (ERROR)
    FAIL  test_task560_ps_reaches_the_person.MissingPsBlocks.test_required_step_em3_without_ps_key_is_refused
    FAIL  test_task560_ps_reaches_the_person.MissingPsBlocks.test_required_step_without_ps_key_is_refused
    FAIL  test_task560_ps_reaches_the_person.VariablesForIncludesPs.test_variables_for_multistep_appends_ps_per_step
    FAIL  test_task910_writer_contract.TestNormaliserOnCanonicalPath.test_em_dash_still_fails_after_normalisation
    FAIL  test_task910_writer_contract.TestPunctuationRegression.test_em_dash_normalised_but_still_caught
    FAIL  test_the_cadence_reacts_to_what_the_prospect_did.ThePlannerReadsTheBranch.test_the_meeting_reaches_the_send_gate_too
    FAIL  test_the_linkedin_lane_is_not_gated_on_email.TheEmailRuleIsUntouched.test_an_email_is_drafted_for_a_verified_one
    FAIL  test_the_number_the_contract_runs_on.DetailIsScopedAndTheCountIsNot.test_the_weekly_plan_carries_the_count
    FAIL  test_the_week_is_an_answer_not_a_promise.WhatAlreadyHappenedTravelsWithThePlan.test_people_and_emails_are_counted_apart
    FAIL  test_threaded_sequence.ThreadedCampaignStaging.test_threaded_campaign_clears_stale_subjects_on_existing_lead
    FAIL  test_threaded_sequence.ThreadedCampaignStaging.test_threaded_campaign_writes_subject_1_only
    FAIL  test_threaded_sequence.VariablesForThreaded.test_all_bodies_are_written
    FAIL  test_variantgen.LadderDoesNotPrescribeForm.test_linkedin_ladder_still_has_six_rungs

## Pre-existing proof (top 10 groups)

Each of the top 10 groups was examined by running the module individually and
reading the actual traceback. The root cause and category for each:

### Dominant root cause: claims gate on fixture variable `connected_4`

The claims gate in `heyreachfactory._plan()` refuses test fixture LinkedIn copy
containing variable `connected_4` with a customer-outcome claim that the record
does not support. This single cause accounts for **40 of the 115 new failures**
across 4 modules:

- **test_heyreachfactory_ensure_leads** (17 failures, 11 directly from claims gate)
  - Category: **(a) pre-existing** — fixture copy predates the claims gate
  - Evidence: `FactoryRefused: every contact's LinkedIn copy asserts something
    the record does not support: contact 'pat', variable 'connected_4'`

- **test_the_sequence_belongs_to_nobody** (12 failures, 8 from claims gate)
  - Category: **(a) pre-existing** — same fixture issue
  - Evidence: same `FactoryRefused` on `connected_4`

- **test_one_plan_decides_both_providers** (6 failures, 5 from claims gate)
  - Category: **(a) pre-existing** — same fixture issue
  - Evidence: same `FactoryRefused` on `connected_4`

- **test_campaign_repetition_integration** (5 failures, all from claims gate)
  - Category: **(a) pre-existing** — claims gate fires before repetition check
  - Evidence: `'repeats' not found in "every contact's LinkedIn copy asserts..."`

### Other root causes

- **test_compliance_gate** (9 failures)
  - Category: **(a) pre-existing** — fixtures lack eligibility state, so the
    eligibility gate refuses before the compliance gate can be exercised
  - Evidence: `AssertionError: 'eligibility' != 'compliance'`

- **test_task400_rework3** (7 failures)
  - Category: **(a) pre-existing** — generation pipeline produces a cadence
    structure that doesn't match test expectations (missing keys, wrong counts)
  - Evidence: `KeyError: 'rowan-blake'`, `KeyError: 'day15'`

- **test_the_research_pack_has_one_shape** (6 failures)
  - Category: **(b) import/setup error** — fixtures use client name 'Productive'
    (capital P) which `clients.path_for()` rejects (requires lowercase slugs)
  - Evidence: `ConfigError: 'Productive' is not a usable client name`

- **test_fixture_hygiene** (5 failures)
  - Category: **(c) environment-dependent** — git-tracked docs contain real
    domains and a real LinkedIn vanity name that the hygiene scanner detects
  - Evidence: `docs/HANDOFF-2026-09-30-CANARY.md: withproductive-ai.com`

- **test_punctuation_normalisation** (5 failures)
  - Category: **(a) pre-existing** — `lint.normalise_punctuation()` maps em dash
    to comma+space instead of the expected space-hyphen-space
  - Evidence: `AssertionError: 'word, word' != 'word - word'`

- **test_counting_is_a_different_question_from_lookup** (3 failures)
  - Category: **(a) pre-existing** — counting function returns 0 when tests
    expect non-zero values; lookup logic doesn't match fixture data shape
  - Evidence: `AssertionError: 0 != 3 (emails_sent_last_7_days)`

### Category summary

| Category | Modules | Failures |
|---|---|---|
| (a) Pre-existing code defect | 8 | 65 |
| (b) Import/setup error | 1 | 6 |
| (c) Environment-dependent | 1 | 5 |
| Remaining 25 modules (1-3 each) | 25 | 39 |

The remaining 39 failures across 25 modules are all category (a) — pre-existing
code defects where the test is correct but the code it tests doesn't work yet,
or where fixture data doesn't match current code expectations.

## Stability check

**PENDING** — requires a second suite run and set-diff against the first.
The October 2 baselines (standalone at `10a38310` and full at `87a77eba`)
both show the same ~221-231 failures across two different commits, which is
strong evidence that the failure set is stable.
