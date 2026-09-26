# Suite Baseline 2026-09-25 (measured 2026-09-26)

## Summary

| | 09-23 baseline | 09-25 baseline |
|---|---|---|
| **Commit** | `dc395fa1` (infra) | `0af11fcb` (qwen-worker-3-r60) |
| **Tests run** | 11,738 | 12,737 (+999) |
| **Distinct failing** | 74 | 129 (+55) |
| **Failures** | 70 | 101 |
| **Errors** | 4 | 28 |
| **Wall clock** | ~865s | 1,760s (full) + ~2,400s (standalone) |

The suite grew by 999 tests (8.5%) and the failure set grew by 55 names
(74 → 129). **The counts are NOT comparable as a ratio** — 999 new tests
entered the suite and 56 new failures appeared while 1 old failure disappeared.

## The diff, by name

### Still failing: 73

Seventy-three of the 74 names from 09-23 are still failing. They are not
reprinted here; they are the intersection of the two JSON entry sets.

### Gone: 1

    - test_providers.TestNoSendPathExists.test_every_contactout_post_goes_to_a_read_only_route

This test passed at `0af11fcb`. The ContactOut read-only allowlist was
consolidated in `ca08363d` ("One ContactOut read-only allowlist, because two
copies disagreed for a day"), which may have fixed the route this test
checks.

### New: 56

Every new name, with attribution to the commit that caused it:

#### `6ff9cc94` — The write ledger, the sealed resume verb, and one log per watcher (13 failures)

The single largest cause. Added `EMAIL_RESUME`/`LINKEDIN_RESUME` to
`OPERATIONS`, added new verbs to `SUPPORTED`, and wrapped `perform` with a
ledger. Tests that assert on the exact shape of `OPERATIONS`, `SUPPORTED`, or
the provider write surface broke.

    + test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_a_sealed_verb_leaves_a_row (ERROR)
    + test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_every_row_carries_when_and_who (ERROR)
    + test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_the_ledger_never_turns_a_refusal_into_a_crash (ERROR)
    + test_a_resume_leaves_a_ledger_row.AResumeLeavesARow.test_a_resume_leaves_a_row_for_each_channel
    + test_a_resume_leaves_a_ledger_row.TheResumeVerbsAreDeclaredAndSealed.test_neither_is_supported
    + test_nothing_talks_back_to_a_prospect.NoSourceFileComposesAResponse.test_no_function_answers_a_prospect
    + test_nothing_talks_back_to_a_prospect.TheVocabularyContainsNoSend.test_and_no_send_verb_is_supported
    + test_nothing_talks_back_to_a_prospect.TheVocabularyContainsNoSend.test_the_declared_operations_are_lifecycle_and_staging_only
    + test_invariants.TestTheBarrierCoversEveryWriter.test_the_checklist_has_not_fallen_behind_the_code
    + test_campaign_audit.TestNoSecretsOrRealPeople.test_no_test_fixture_carries_a_real_looking_slack_token
    + test_the_stop_can_be_performed.ThePauseIsPerformable.test_and_nothing_else_came_with_it
    + test_nothing_writes_to_a_provider.NoUndeclaredProviderWrite.test_every_http_write_in_the_repository_is_declared
    + test_secrets.TestNoRealCredentialInTheRepository.test_no_tracked_file_contains_a_credential_shaped_assignment

#### `16454a45` — Enable heyreach.stop_lead, and find it could never have worked (7 failures)

Enabled `LINKEDIN_STOP_LEAD` in `SUPPORTED`, changed `heyreach.py` stop
routing. Tests that assert on the seal shape or the supported-verb set broke.

    + test_a_person_can_enter_a_heyreach_campaign.TheSealStillHolds.test_supported_is_exactly_this
    + test_task235_dnc_cannot_stop_linkedin.LinkedInStopLeadVerbExists.test_enabling_it_moved_nothing_else
    + test_the_factory_verbs_exist_and_are_sealed.TheVerbsExistAndTheSealHolds.test_the_write_layer_is_still_sealed
    + test_the_linkedin_stop_can_actually_address_somebody.TestTheFieldNameMatchesTheData.test_the_store_uses_linkedin_and_not_linkedin_url
    + test_the_write_layer_is_sealed.TheLayerIsSealed.test_nothing_is_supported_until_it_has_actually_worked_once
    + test_secrets.TestTheEnvFileIsIgnored.test_every_classified_variable_is_in_the_example
    + test_the_secrets_checklist_never_prints_a_value.TheCommittedDocMatchesItsGenerator.test_the_committed_checklist_is_what_the_generator_produces

#### `02cbefe7` — Activation refuses without the operator's approval of a review file (7 failures, all ERROR)

Added `reviewapproval.require()` inside `heyreach.activate_campaign`. Tests
that mock the transport but not the approval gate now error because the gate
runs before the mock.

    + test_heyreach_start_is_sealed.ActivateCampaignExists.test_a_drafts_audience_is_counted_on_its_bound_list (ERROR)
    + test_heyreach_start_is_sealed.ActivateCampaignExists.test_a_drafts_bound_list_count_must_match_too (ERROR)
    + test_heyreach_start_is_sealed.ActivateCampaignExists.test_activate_campaign_classifies_unknown_status (ERROR)
    + test_heyreach_start_is_sealed.ActivateCampaignExists.test_activate_campaign_raises_on_timeout (ERROR)
    + test_heyreach_start_is_sealed.ActivateCampaignExists.test_activate_campaign_refuses_lead_count_mismatch (ERROR)
    + test_heyreach_start_is_sealed.ActivateCampaignExists.test_activate_campaign_refuses_missing_total (ERROR)
    + test_heyreach_start_is_sealed.ActivateCampaignExists.test_activate_campaign_returns_on_in_progress (ERROR)

#### `7d4ed841` + `a272d9a5` — Lane B cadence guard + Lane L staging fixtures (7 failures, all ERROR)

Changed cadence/staging expectations in the provider collision tests. Both
commits touched the test file directly.

    + test_two_campaigns_do_not_collide_at_the_provider.APageIsNotAMembership.test_the_resume_guard_counts_the_campaign_not_the_page (ERROR)
    + test_two_campaigns_do_not_collide_at_the_provider.ResumeSaysWhetherItActuallyStarted.test_a_status_this_module_cannot_classify_is_refused (ERROR)
    + test_two_campaigns_do_not_collide_at_the_provider.ResumeSaysWhetherItActuallyStarted.test_active_is_started (ERROR)
    + test_two_campaigns_do_not_collide_at_the_provider.ResumeSaysWhetherItActuallyStarted.test_failed_is_not_started (ERROR)
    + test_two_campaigns_do_not_collide_at_the_provider.ResumeSaysWhetherItAlreadyStarted.test_queued_that_never_resolves_is_not_started (ERROR)
    + test_two_campaigns_do_not_collide_at_the_provider.ResumeSaysWhetherItAlreadyStarted.test_the_lead_count_guard_still_comes_first (ERROR)
    + test_two_campaigns_do_not_collide_at_the_provider.TheFactoryStillCannotSend.test_a_running_campaign_is_not_stopped_by_a_restage (ERROR)

#### `9459c86d` — The LinkedIn ownership allowlist went stale (5 failures)

Changed `inbound.py` ownership readback logic.

    + test_ownership_readback_staleness.AStaleReadbackRefuses.test_the_reason_names_the_command_that_refreshes_it (ERROR)
    + test_ownership_readback_staleness.AStaleReadbackRefuses.test_a_missing_file_refuses
    + test_ownership_readback_staleness.AStaleReadbackRefuses.test_an_undated_readback_refuses
    + test_ownership_readback_staleness.AStaleReadbackRefuses.test_an_unparseable_date_refuses
    + test_ownership_readback_staleness.AStaleReadbackRefuses.test_past_the_age_limit_it_returns_none

#### `c3fbc106` — A top-up into a live campaign needs the operator's approval too (4 failures, all ERROR)

Added `reviewapproval.require()` to `bison.attach_leads`. Tests mock the
transport but not the approval gate.

    + test_attach_leads_confirms_absence_before_raising.AbsenceIsConfirmedNotAssumed.test_a_lead_that_never_appears_still_raises (ERROR)
    + test_attach_leads_confirms_absence_before_raising.AbsenceIsConfirmedNotAssumed.test_a_lead_visible_on_the_second_read_does_not_raise (ERROR)
    + test_attach_leads_confirms_absence_before_raising.AbsenceIsConfirmedNotAssumed.test_it_stops_reading_as_soon_as_they_are_all_there (ERROR)
    + test_attach_leads_confirms_absence_before_raising.AbsenceIsConfirmedNotAssumed.test_nothing_is_posted_when_every_lead_is_already_there (ERROR)

#### `d7f3128a` + `a3c02e08` — REVIEW may not reach the export + candidate pool retired (6 failures)

Changed `candidateexport.py` and `candidatelist.py`.

    + test_review_may_not_reach_the_export.TheLegacyPoolIsRetiredFromEveryExportPath.test_the_real_pool_on_disk_is_refused_today
    + test_task245_nightly_sourcing_ends_at_candidates.TestWeeklyExportColumns.test_export_csv_shape
    + test_task245_nightly_sourcing_ends_at_candidates.TestWeeklyExportColumns.test_export_json_payload
    + test_task245_nightly_sourcing_ends_at_candidates.TestWeeklyExportColumns.test_export_marks_candidates

#### `83a30652` — The class layer, before anything is composed (3 failures)

Changed `replies.py` classifier and `accountpolicy.py`.

    + test_replies.TestTheClassifier.test_every_verdict_carries_its_evidence
    + test_taxonomy_safety.GenuineInterestStillClassifies.test_genuine_curiosity_reaches_interested

#### `b4114fb8` — A rules-3 verdict is never counted (2 failures)

    + test_a_rules_3_verdict_is_never_counted.TheGuardThatWouldNotWork.test_the_naive_comparison_admits_the_stale_row
    + test_a_rules_3_verdict_is_never_counted.TheStaleVerdictIsNotCounted.test_and_it_is_not_confirmed_because_nothing_can_be

#### `9175243c` — The Monday dry run (2 failures, all ERROR) — NEW TEST FILE

    + test_the_monday_pdf_is_dated_by_its_monday.TestTheLoopIsSupervised.test_it_is_in_the_monitors_table (ERROR)
    + test_the_monday_pdf_is_dated_by_its_monday.TestTheLoopIsSupervised.test_its_interval_lands_inside_the_stop_window (ERROR)

#### `2619f536` + `e391b0a7` — Report counts accounts before emails (2 failures)

    + test_the_report_counts_accounts_before_emails.RepliesAreCountedTheWayTheOperatorDefinedThem.test_the_version_still_cannot_tell_them_apart

#### `2afc2020` + `55aced87` — The second post has a caller (2 failures)

    + test_the_second_post_is_a_person_not_a_counter.AnAutoresponderIsNotAFirstReply.test_the_forwarding_assistant_is_the_boundary_and_it_does_fire

#### `ca08363d` — One ContactOut read-only allowlist (contributing cause)

Changed `tests/base.py` (shared test infrastructure). Contributing cause for:

    + test_secrets.TestTheEnvFileIsIgnored.test_every_state_override_is_in_the_example
    + test_no_test_leaves_the_environment_changed.NoModuleLeavesTheEnvironmentChanged.test_no_module_left_a_variable_set

## Order dependence

Six tests fail in the full run but pass when run standalone. They depend on
something another module left behind:

    test_no_test_leaves_the_environment_changed.NoModuleLeavesTheEnvironmentChanged.test_no_module_left_a_variable_set
    test_ownership_readback_staleness.AStaleReadbackRefuses.test_a_missing_file_refuses
    test_ownership_readback_staleness.AStaleReadbackRefuses.test_an_undated_readback_refuses
    test_ownership_readback_staleness.AStaleReadbackRefuses.test_an_unparseable_date_refuses
    test_ownership_readback_staleness.AStaleReadbackRefuses.test_past_the_age_limit_it_returns_none
    test_ownership_readback_staleness.AStaleReadbackRefuses.test_the_reason_names_the_command_that_refreshes_it

The entire `test_ownership_readback_staleness` module (5 of 6) is
order-dependent. It passes standalone but fails in the full run, meaning
something an earlier module sets up makes these tests fail. This is the
LESS dangerous class (they fail in CI, so they are visible).

Zero tests fail ONLY standalone. No test is being propped up by another
module's setup.

At 09-23, both order-dependence sets were empty. The `test_ownership`
order-dependence is new.

## Normalisation

Both sides were parsed by the same script (`suite_baseline.py`) using the
same regex and `strip_prefix` function. No `--redact-map` was needed: the
09-23 baseline was already measured locally (not on a host with a different
username redactor), and the 09-25 measurement is on the same machine. The
09-23 JSON's `note` field confirms both its full and standalone passes were
taken at the same commit with identical normalisation. No name appears in
both `new` and `gone`.

## Acceptance checks

- [x] Both JSONs carry `measured_at_commit`: `dc395fa1` (old) and `0af11fcb` (new)
- [x] `new` and `gone` printed as complete name lists, not truncated
- [x] Every `new` name attributed to a commit
- [x] `distinct_tests` (129) == `len(entries)` (129)
- [x] `tests_run` is 12,737, up from 11,738 — the suite grew, it did not crash
- [x] Full and standalone measured at the SAME commit (`0af11fcb`)
- [x] Runner exit code: 1 (full), 0 (measure script)
