# SUITE TRIAGE — the 106 new failures, 2026-09-27

Operator decision of 2026-09-27: triage first (option B), then fix every genuine
safety regression (option A). **228 is never accepted as a baseline.** This
document is the triage. It changes no production code.

Measured against baseline `0af11fcb` (`docs/state/SUITE-BASELINE-2026-09-26.txt`,
128 named failures) and TASK-372's regeneration at `91a280e2` (228 named
failures, reviewed at `6fc77fb0`).

## THE SET DIFF, INDEPENDENTLY RECOMPUTED

    old distinct   128
    new distinct   228
    entered        106
    gone             6
    arithmetic     128 - 6 + 106 = 228   reconciles exactly

The 6 that now pass are 5 from `test_a_resume_leaves_a_ledger_row` and 1 from
`test_nothing_writes_to_a_provider`.

## CLASSIFICATION, AND A CORRECTION TO TASK-372

    REGRESSION      87     existed at baseline, so it passed then
    NEW_COVERAGE    19     the test did not exist at baseline

**TASK-372 reported 68 regressions and 38 new coverage. That is wrong.** It
counted "19 from three new modules and 19 from new classes". The three new
modules are real and are the 19 NEW_COVERAGE rows below
(`test_an_offer_cannot_be_invented` 10, `test_strategy_is_set_per_segment_not_per_lead`
7, `test_a_dead_cta_link_is_refused` 2). **The other 19 do not exist.** Checked by
AST-parsing each affected module at `0af11fcb` and looking for the test method
inside ITS OWN class: all 87 remaining rows had both class and method present at
baseline. There are no new classes among the entered failures.

So the regression count is 87, not 68. Nineteen tests TASK-372 excused as new
coverage are regressions.

## ROOT CAUSES — 87 REGRESSIONS COLLAPSE INTO THREE

### Cause A — `6fa49014`, 71 regressions across 10 modules

`6fa49014` "TASK-321 PARTIAL: sequencegate is genuinely wired into bisonfactory".
The commit message's own word, PARTIAL, is the whole story.

`src/bisonfactory.py:668`:

    result = sequencegate.check(sequence)

`sequencegate.check` takes five inputs: `sequence, facts, capability,
qualification, batch_capabilities`. The call site passes **one**. And
`sequencegate.check` refuses when `qualification is None`:

    if qualification is None:
        fail("qualified", "lead",
             "no qualification supplied: absence is refused rather than read "
             "as qualified")

That rule is correct and fail-closed. The call site is what is wrong.

**THE CONSEQUENCE, WHICH IS LARGER THAN THE TEST COUNT: `bisonfactory.stage()`
CANNOT SUCCEED FOR ANY INPUT.** Every stage of every campaign with leads and copy
raises `FactoryRefused` on the `qualified` check. The email staging path has been
entirely non-functional since 2026-09-26 15:27. It fails CLOSED, so nothing has
reached a provider and the freeze is over-satisfied on this path — but no campaign
can be staged at all, and the one-account dry run cannot stage anything either.

There is a **second, independent omission** in the same call: `facts` is not
passed, so `claims_supported` checks every claim against an empty fact pack and
refuses any specific claim. Demonstrated below: supplying only the qualification
leaves `test_the_copy_lint_refuses_the_real_send_path` with 3 errors that now name
`claims_supported`. `batch_capabilities` is also missing, which downgrades
`capability_matches` to a warning rather than a check.

Bisect evidence, `test_lead_writes_respect_the_killswitch`:

    35dd8cbd  (parent)    Ran 5 tests  OK
    6fa49014              Ran 5 tests  FAILED (failures=2, errors=3)
    156110f7  (HEAD)      Ran 5 tests  FAILED (failures=2, errors=3)

Same commit confirmed for the largest module,
`test_two_campaigns_do_not_collide_at_the_provider`: 7 errors at `35dd8cbd`,
31 at `6fa49014` — exactly the 24 entered failures. `test_crash_restart_idempotency`
and `test_the_copy_lint_refuses_the_real_send_path` both OK at `35dd8cbd`.

One bisect per module group, not per test: all ten modules stage through
`bisonfactory.stage` and nine of them share the fixture cluster
`test_staging_a_campaign_twice_builds_one` + `test_staging_refuses_colliding_contacts`.

### Cause B — the in-flight notify work, 12 regressions, ALREADY FIXED

`test_notify_pipeline` 4, `test_notify_wiring` 3, `test_web_slack` 3,
`test_notify` 1, `test_status_channel_carries_no_prospect` 1.

These were caused by an `ops_channel()` change that collapsed the ops destination
onto the status channel, and were corrected at `156110f7`. **Verified green at
HEAD: 122 tests across the four notify modules plus the status-channel module, all
OK.** No action needed; they will leave the failing set on the next run.

### Cause C — 4 regressions, individually

- `test_fixture_hygiene` (2). `test_no_real_client_prospect_or_roster_domain`
  fails on `config/clients/productive-offers.yaml: productive.io`, and
  `test_every_email_address_is_on_a_reserved_domain` on a non-reserved domain in
  `tests/test_changing_an_approved_fact_changes_the_output.py`. Absent from the
  09-26 baseline, present in the 09-27 one, so a genuine regression.
  **THIS IS A CONFLICT BETWEEN TWO OPERATOR INSTRUCTIONS, NOT A GUARD TO WEAKEN.**
  The operator approved storing productive.io's public AI page text and the single
  CTA link in that config; the hygiene guard forbids a real client domain in git.
  Both instructions are reasonable and they collide. An operator decision is
  needed: either the guard's allowlist admits the client's own public domain in
  `config/clients/`, or the evidence moves somewhere the guard does not scan. Do
  not resolve this by relaxing the guard silently.
- `test_the_cadence_reacts_to_what_the_prospect_did` (1). `10 != 11` on the
  LinkedIn-heavy sequence length, and separately `None != 'blocked:company_paused'`
  on the send gate. Cause not bisected; needs its own task.
- `test_no_test_leaves_the_environment_changed` (1). A meta-test whose record is
  only populated by a full discovered run, so it is not meaningful in isolation.

## PER-GUARD VERDICTS: BROKEN or UNPROVEN

**NOT ONE OF THE FIVE SAFETY GUARDS IS BROKEN.** All five are UNPROVEN, and the
single reason is Cause A: an always-failing gate refuses before the guard under
test is reached. In every case the system still refuses, and nothing reaches a
provider write.

| guard | failures | verdict | evidence |
|---|---|---|---|
| killswitch | 5 | **UNPROVEN** | Proof RESTORED: 5/5 pass once the gate is reachable. The module's own mutation test passes too — killswitch tripped gives 0 leads, killswitch bypassed gives 2. The guard is load-bearing and functional. |
| crash-restart idempotency | 9 | **UNPROVEN** | Proof RESTORED: 9/9 pass once the gate is reachable. |
| staging collision refusal | 7 | **UNPROVEN** | Same blocker. Hosts the restoration helper; not separately restored. |
| copylint on the real send path | 3 | **UNPROVEN** | Proof PARTIALLY restored. Removing the `qualified` blocker exposes the second omission: 3 errors now name `claims_supported`, because `facts` is not passed either. Cannot be fully restored from the test side. |
| approval is not a fact-check | 2 | **UNPROVEN** | Same blocker. Its `stage()` helper lives in `test_two_campaigns_do_not_collide_at_the_provider`, outside this triage's file scope. |

### The killswitch, stated plainly for the operator

493 is live, so this is the one that matters. **The killswitch works.** With the
sequence gate reachable, a workspace whose `sending.live` is off gets zero leads,
an absent workspace setting also gets zero leads, and bypassing the killswitch
lets two leads through — which is what proves the check is the thing standing in
the way. What was lost on 2026-09-26 was the PROOF, not the protection.

## HOW THE PROOF WAS RESTORED, AND WHY IT IS A STOPGAP

`tests/test_staging_refuses_colliding_contacts.restore_gate_reachability` wraps
`sequencegate.check` at the seam and supplies the one argument production forgets.
It **wraps rather than bypasses**: every other gate check still runs, so nothing
is weakened. Applied in the killswitch and crash-restart modules.

The proof could NOT be restored by constructing better fixture inputs, which is
what the operator's instruction anticipated. The omission is in the production
call site, not in the fixtures, so no input can supply it.

`TheSequenceGateCallSiteIsIncomplete` pins the defect so the wrapper cannot hide
it, with two assertions and neither reads source text:

- the call site is observed at the seam and asserted to pass no `qualification`;
- `sequencegate.check(sequence)` called exactly as production calls it is asserted
  to refuse on `qualified`, for a perfectly good sequence.

Both **fail as soon as the production defect is fixed**, which is the signal to
delete the wrapper and the class together.

## FIX TASKS FOR STEP 2, ORDERED BY SEVERITY

1. **P0 — `_refuse_sequence_gate` must supply the gate's arguments.** Pass
   `qualification`, `facts`, `capability` and `batch_capabilities` from the plan
   and its leads. This one fix unblocks 71 tests, restores five safety proofs and
   makes `bisonfactory.stage()` functional again. Acceptance by effect: a stage
   with a qualified lead and supporting facts SUCCEEDS; a stage with a blocking
   qualification is refused ON the `qualified` check; a claim with no supporting
   fact is refused on `claims_supported`. Then delete
   `restore_gate_reachability` and `TheSequenceGateCallSiteIsIncomplete`.
2. **P0 — confirm the killswitch stops a real write today**, read-only, per the
   operator. This triage shows it refuses in test; the operator asked for
   confirmation on the live path.
3. **P1 — the `test_fixture_hygiene` instruction conflict.** Operator decision, as
   set out under Cause C. Blocks nothing technically; leaving it red normalises a
   red hygiene guard, which is how this repository lost the killswitch proof.
4. **P1 — `test_the_cadence_reacts_to_what_the_prospect_did`**: bisect and fix the
   sequence-length and send-gate failures.
5. **P2 — the 19 NEW_COVERAGE rows** may enter a baseline once the operator
   accepts them as coverage rather than debt. They are not regressions.
6. **P2 — re-run the suite after fix 1** and diff the failing-name SET again. Do
   not adopt any number as a baseline until the stability pass TASK-372 skipped
   has actually run.

## WHAT THIS TRIAGE DID NOT DO

No production code changed. No test weakened, skipped, xfailed or deleted. No
baseline adopted. Provider writes zero; nothing sent, activated, resumed, enrolled
or attached.

## PER-ROW TABLE

One row per entered failure. "commit that turned it red" is the bisected cause for
the module group, not a per-test bisect.

| test | module | verdict | commit that turned it red | safety |
|---|---|---|---|---|
| `GuardFailureTests.test_removing_allowlist_check_lets_dead_link_through` | `test_a_dead_cta_link_is_refused` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `ProductionPathTests.test_allowlisted_url_passes_through_check_batch` | `test_a_dead_cta_link_is_refused` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TheWordsTravelWithThePerson.test_a_contact_missing_one_step_stops_the_whole_run` | `test_a_five_step_campaign_sends_five_different_emails` | REGRESSION | `6fa49014` | no |
| `TheWordsTravelWithThePerson.test_a_multi_step_lead_carries_no_unnumbered_copy` | `test_a_five_step_campaign_sends_five_different_emails` | REGRESSION | `6fa49014` | no |
| `TheWordsTravelWithThePerson.test_a_tenancy_mismatch_is_still_the_first_refusal` | `test_a_five_step_campaign_sends_five_different_emails` | REGRESSION | `6fa49014` | no |
| `TheWordsTravelWithThePerson.test_every_step_gets_its_own_words` | `test_a_five_step_campaign_sends_five_different_emails` | REGRESSION | `6fa49014` | no |
| `TheWordsTravelWithThePerson.test_the_lead_carries_one_subject_and_no_numbered_follow_up_one` | `test_a_five_step_campaign_sends_five_different_emails` | REGRESSION | `6fa49014` | no |
| `TheWordsTravelWithThePerson.test_the_provider_holds_five_steps_with_the_cadence_delays` | `test_a_five_step_campaign_sends_five_different_emails` | REGRESSION | `6fa49014` | no |
| `TheWordsTravelWithThePerson.test_the_provider_holds_one_opener_and_four_thread_replies` | `test_a_five_step_campaign_sends_five_different_emails` | REGRESSION | `6fa49014` | no |
| `TheGateIsActuallyWiredIntoStaging.test_a_clean_record_still_stages` | `test_an_approval_is_not_a_fact_check` | REGRESSION | `6fa49014` | **YES** |
| `TheGateIsActuallyWiredIntoStaging.test_staging_refuses_a_contact_who_was_never_contacted` | `test_an_approval_is_not_a_fact_check` | REGRESSION | `6fa49014` | **YES** |
| `TestApprovalRefusal.test_approval_status_is_not_defaulted_to_approved` | `test_an_offer_cannot_be_invented` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestApprovalRefusal.test_require_approved_false_returns_unapproved` | `test_an_offer_cannot_be_invented` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestApprovalRefusal.test_unapproved_offer_raises_for_campaign_503` | `test_an_offer_cannot_be_invented` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestMissingIsNotEmpty.test_missing_includes_case_studies` | `test_an_offer_cannot_be_invented` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestMissingIsNotEmpty.test_missing_includes_demo_link` | `test_an_offer_cannot_be_invented` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestMissingIsNotEmpty.test_missing_is_not_empty` | `test_an_offer_cannot_be_invented` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestNoInventedCapability.test_every_offer_names_a_confirmed_capability` | `test_an_offer_cannot_be_invented` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestNoInventedCapability.test_six_capabilities_shipped` | `test_an_offer_cannot_be_invented` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestOfferIsDataNotGenerated.test_load_reads_only_from_yaml` | `test_an_offer_cannot_be_invented` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestOfferSchema.test_every_offer_has_all_schema_fields` | `test_an_offer_cannot_be_invented` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `CrashAtSeam.test_crash_after_attach_before_readback` | `test_crash_restart_idempotency` | REGRESSION | `6fa49014` | **YES** |
| `CrashAtSeam.test_crash_after_create_lead_before_remember` | `test_crash_restart_idempotency` | REGRESSION | `6fa49014` | **YES** |
| `CrashAtSeam.test_crash_after_ensure_limits` | `test_crash_restart_idempotency` | REGRESSION | `6fa49014` | **YES** |
| `CrashAtSeam.test_crash_after_ensure_schedule` | `test_crash_restart_idempotency` | REGRESSION | `6fa49014` | **YES** |
| `CrashAtSeam.test_crash_after_ensure_senders` | `test_crash_restart_idempotency` | REGRESSION | `6fa49014` | **YES** |
| `CrashAtSeam.test_crash_after_ensure_sequence` | `test_crash_restart_idempotency` | REGRESSION | `6fa49014` | **YES** |
| `CrashAtSeam.test_crash_after_ensure_stopped` | `test_crash_restart_idempotency` | REGRESSION | `6fa49014` | **YES** |
| `CrashAtSeam.test_crash_after_find_or_create_before_bind` | `test_crash_restart_idempotency` | REGRESSION | `6fa49014` | **YES** |
| `CrashAtSeam.test_crash_between_first_and_second_lead` | `test_crash_restart_idempotency` | REGRESSION | `6fa49014` | **YES** |
| `TestNoRealDataAnywhereInGit.test_every_email_address_is_on_a_reserved_domain` | `test_fixture_hygiene` | REGRESSION | see notes | no |
| `TestNoRealDataAnywhereInGit.test_no_real_client_prospect_or_roster_domain` | `test_fixture_hygiene` | REGRESSION | see notes | no |
| `StaleVariablesClearedOnReconciliation.test_already_empty_variables_do_not_trigger_extra_writes` | `test_lead_variables` | REGRESSION | `6fa49014` | no |
| `StaleVariablesClearedOnReconciliation.test_in_range_variables_are_preserved` | `test_lead_variables` | REGRESSION | `6fa49014` | no |
| `StaleVariablesClearedOnReconciliation.test_report_names_the_cleared_variables` | `test_lead_variables` | REGRESSION | `6fa49014` | no |
| `StaleVariablesClearedOnReconciliation.test_stale_numbered_variables_are_cleared` | `test_lead_variables` | REGRESSION | `6fa49014` | no |
| `KillswitchStopsLeadWrites.test_a_running_campaign_is_caught_fresh_before_attach` | `test_lead_writes_respect_the_killswitch` | REGRESSION | `6fa49014` | **YES** |
| `KillswitchStopsLeadWrites.test_a_tripped_killswitch_stops_lead_creation` | `test_lead_writes_respect_the_killswitch` | REGRESSION | `6fa49014` | **YES** |
| `KillswitchStopsLeadWrites.test_an_absent_workspace_setting_stops_lead_creation` | `test_lead_writes_respect_the_killswitch` | REGRESSION | `6fa49014` | **YES** |
| `KillswitchStopsLeadWrites.test_an_active_campaign_with_leads_already_created_refuses_attach` | `test_lead_writes_respect_the_killswitch` | REGRESSION | `6fa49014` | **YES** |
| `KillswitchStopsLeadWrites.test_the_killswitch_check_is_what_stops_the_leads` | `test_lead_writes_respect_the_killswitch` | REGRESSION | `6fa49014` | **YES** |
| `NoModuleLeavesTheEnvironmentChanged.test_no_module_left_a_variable_set` | `test_no_test_leaves_the_environment_changed` | REGRESSION | see notes | no |
| `TheGlobalChannel.test_operational_events_route_to_it` | `test_notify` | REGRESSION | parent notify work, FIXED at `156110f7` | no |
| `TheAbsentFallbacks.test_an_unmapped_workspace_does_not_borrow_the_operations_channel` | `test_notify_pipeline` | REGRESSION | parent notify work, FIXED at `156110f7` | no |
| `TheAbsentFallbacks.test_the_notification_it_produces_has_no_channel` | `test_notify_pipeline` | REGRESSION | parent notify work, FIXED at `156110f7` | no |
| `TheGlobalOperationsFeed.test_an_approval_request_carries_the_context_to_decide` | `test_notify_pipeline` | REGRESSION | parent notify work, FIXED at `156110f7` | no |
| `TheGlobalOperationsFeed.test_operational_events_never_reach_the_client_channel` | `test_notify_pipeline` | REGRESSION | parent notify work, FIXED at `156110f7` | no |
| `AFailedJobIsAnnounced.test_an_aborted_job_reaches_the_operations_channel` | `test_notify_wiring` | REGRESSION | parent notify work, FIXED at `156110f7` | no |
| `AnApprovalRequestReachesTheOperationsChannel.test_it_is_planned_on_the_same_path_that_builds_the_request` | `test_notify_wiring` | REGRESSION | parent notify work, FIXED at `156110f7` | no |
| `AnUnmatchedReplyIsAnnounced.test_a_reply_for_no_record_reaches_the_operations_channel` | `test_notify_wiring` | REGRESSION | parent notify work, FIXED at `156110f7` | no |
| `StagingTwiceBuildsOne.test_a_foreign_workspace_is_refused` | `test_staging_a_campaign_twice_builds_one` | REGRESSION | `6fa49014` | no |
| `StagingTwiceBuildsOne.test_an_uncapped_campaign_is_refused` | `test_staging_a_campaign_twice_builds_one` | REGRESSION | `6fa49014` | no |
| `StagingTwiceBuildsOne.test_every_lead_can_be_traced_back_to_its_person` | `test_staging_a_campaign_twice_builds_one` | REGRESSION | `6fa49014` | no |
| `StagingTwiceBuildsOne.test_it_is_left_stopped` | `test_staging_a_campaign_twice_builds_one` | REGRESSION | `6fa49014` | no |
| `StagingTwiceBuildsOne.test_re_staging_does_not_stop_a_running_campaign` | `test_staging_a_campaign_twice_builds_one` | REGRESSION | `6fa49014` | no |
| `StagingTwiceBuildsOne.test_the_cap_is_applied_before_anybody_is_attached` | `test_staging_a_campaign_twice_builds_one` | REGRESSION | `6fa49014` | no |
| `StagingTwiceBuildsOne.test_the_provider_id_is_persisted_where_it_can_be_found` | `test_staging_a_campaign_twice_builds_one` | REGRESSION | `6fa49014` | no |
| `StagingTwiceBuildsOne.test_the_second_run_creates_nothing` | `test_staging_a_campaign_twice_builds_one` | REGRESSION | `6fa49014` | no |
| `StagingRefusesCollidingContacts.test_a_clean_contact_still_stages` | `test_staging_refuses_colliding_contacts` | REGRESSION | `6fa49014` | **YES** |
| `StagingRefusesCollidingContacts.test_bounced_is_refused` | `test_staging_refuses_colliding_contacts` | REGRESSION | `6fa49014` | **YES** |
| `StagingRefusesCollidingContacts.test_breaking_the_check_makes_the_intended_test_fail` | `test_staging_refuses_colliding_contacts` | REGRESSION | `6fa49014` | **YES** |
| `StagingRefusesCollidingContacts.test_in_sequence_is_refused_by_name` | `test_staging_refuses_colliding_contacts` | REGRESSION | `6fa49014` | **YES** |
| `StagingRefusesCollidingContacts.test_sequence_finished_may_pass` | `test_staging_refuses_colliding_contacts` | REGRESSION | `6fa49014` | **YES** |
| `StagingRefusesCollidingContacts.test_stopped_is_refused` | `test_staging_refuses_colliding_contacts` | REGRESSION | `6fa49014` | **YES** |
| `StagingRefusesCollidingContacts.test_the_nine_real_cases_as_a_fixture` | `test_staging_refuses_colliding_contacts` | REGRESSION | `6fa49014` | **YES** |
| `TheStatusFeedIsItsOwnDestination.test_ops_events_still_go_to_ops` | `test_status_channel_carries_no_prospect` | REGRESSION | parent notify work, FIXED at `156110f7` | no |
| `TestStrategyIsSegmentInvariant.test_clear_cache_forces_fresh_call` | `test_strategy_is_set_per_segment_not_per_lead` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestStrategyIsSegmentInvariant.test_different_persona_gets_different_strategy` | `test_strategy_is_set_per_segment_not_per_lead` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestStrategyIsSegmentInvariant.test_model_called_once_for_fifty_leads_in_one_segment` | `test_strategy_is_set_per_segment_not_per_lead` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestStrategyIsSegmentInvariant.test_no_model_call_when_cached` | `test_strategy_is_set_per_segment_not_per_lead` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestStrategyIsSegmentInvariant.test_same_segment_same_persona_returns_same_strategy_id` | `test_strategy_is_set_per_segment_not_per_lead` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestStrategyIsSegmentInvariant.test_strategy_carries_required_fields` | `test_strategy_is_set_per_segment_not_per_lead` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `TestStrategyIsSegmentInvariant.test_two_segments_get_two_strategies` | `test_strategy_is_set_per_segment_not_per_lead` | NEW_COVERAGE | n/a, module absent at baseline | no |
| `ThePlannerReadsTheBranch.test_the_meeting_reaches_the_send_gate_too` | `test_the_cadence_reacts_to_what_the_prospect_did` | REGRESSION | see notes | no |
| `TheCopyLintIsOnTheSendPath.test_a_batch_whose_copy_is_clean_is_staged` | `test_the_copy_lint_refuses_the_real_send_path` | REGRESSION | `6fa49014` | **YES** |
| `TheCopyLintIsOnTheSendPath.test_the_lint_is_told_this_plan_s_length_and_not_the_target` | `test_the_copy_lint_refuses_the_real_send_path` | REGRESSION | `6fa49014` | **YES** |
| `TheCopyLintIsOnTheSendPath.test_the_same_fact_on_the_account_s_own_domain_does_support_it` | `test_the_copy_lint_refuses_the_real_send_path` | REGRESSION | `6fa49014` | **YES** |
| `ThreadedCampaignStaging.test_threaded_campaign_clears_stale_subjects_on_existing_lead` | `test_threaded_sequence` | REGRESSION | `6fa49014` | no |
| `ThreadedCampaignStaging.test_threaded_campaign_writes_subject_1_only` | `test_threaded_sequence` | REGRESSION | `6fa49014` | no |
| `ALeadCreatedInARaceIsFoundNotDuplicated.test_a_lead_that_never_appears_still_stops_the_run` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `ALeadCreatedInARaceIsFoundNotDuplicated.test_the_reconciliation_waits_for_the_index` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `APageIsNotAMembership.test_the_factory_reports_the_campaign_size_not_a_page` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `AStaleBindingIsNotABinding.test_a_binding_the_provider_will_not_return_refuses` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `AStaleBindingIsNotABinding.test_a_binding_to_a_campaign_pending_deletion_refuses` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `AWindowThatChangedMustBeWritten.test_an_unchanged_window_writes_nothing` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `AWindowThatChangedMustBeWritten.test_narrowing_the_hours_is_not_already_correct` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `OnePersonCannotBeInTwoLiveSequences.test_a_person_already_in_sequence_refuses_and_says_who_holds_them` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `OnePersonCannotBeInTwoLiveSequences.test_nobody_is_ever_attached_to_a_campaign_that_can_hold_them` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `OnePersonCannotBeInTwoLiveSequences.test_two_stopped_campaigns_may_hold_the_same_person` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheFactoryStillCannotSend.test_a_failed_campaign_is_not_reported_as_running` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheFactoryStillCannotSend.test_a_restage_does_not_rename_the_provider_campaign` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheFactoryStillCannotSend.test_a_staged_campaign_is_left_paused` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheFactoryStillCannotSend.test_staging_never_resumes` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheNameIsIdentityAndTheFingerprintIsMaterial.test_a_regenerated_draft_still_reuses_the_same_campaign` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheSameSpecBuildsOneCampaign.test_a_campaign_created_and_never_recorded_is_recovered` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheSameSpecBuildsOneCampaign.test_a_campaign_pending_deletion_is_not_recovered` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheSameSpecBuildsOneCampaign.test_a_second_run_reuses_the_first_campaign` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheSameSpecBuildsOneCampaign.test_two_campaigns_under_that_name_is_ambiguous_not_a_choice` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheSequenceIsWrittenOnceOrNotAtAll.test_a_changed_sequence_refuses_instead_of_appending` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheSequenceIsWrittenOnceOrNotAtAll.test_a_rebuild_is_refused_until_the_staging_record_is_cleared` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheSequenceIsWrittenOnceOrNotAtAll.test_a_write_that_stored_nothing_is_not_a_success` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheSequenceIsWrittenOnceOrNotAtAll.test_and_then_the_rebuilt_campaign_gets_its_sequence` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `TheSequenceIsWrittenOnceOrNotAtAll.test_staging_twice_leaves_one_step` | `test_two_campaigns_do_not_collide_at_the_provider` | REGRESSION | `6fa49014` | no |
| `AClientIsNotShownTheMachine.test_a_viewers_dashboard_does_not_name_the_operations_channel` | `test_web_slack` | REGRESSION | parent notify work, FIXED at `156110f7` | no |
| `TheAdminSlackConsole.test_it_names_the_global_operations_channel` | `test_web_slack` | REGRESSION | parent notify work, FIXED at `156110f7` | no |
| `TheDemoScenariosAreVisibleAndFictional.test_the_unconfigured_one_is_not_diverted_to_the_ops_channel` | `test_web_slack` | REGRESSION | parent notify work, FIXED at `156110f7` | no |
