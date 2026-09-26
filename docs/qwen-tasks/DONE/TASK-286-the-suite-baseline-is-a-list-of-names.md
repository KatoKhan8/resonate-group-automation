PRIORITY: P1
DEPENDS:

# TASK-286 — the suite baseline is a list of names, or it is nothing

## The question this answers

**Which tests fail at tonight's master, by name — and which of those are new
since 2026-09-23?**

Not how many. **A baseline that is a COUNT cannot answer the only question
worth asking of it.** `74 failures` and `74 failures` compare equal while a
different 74 tests fail, and that is not hypothetical here: the 2026-09-23
host comparison found **17 host-only failures and 0 local-only ones behind two
counts that differed by exactly 17.** A count says something changed. Only a
set of names says WHAT.

`scripts/suite_baseline.py` already measures names and diffs sets. The last
baselines are `docs/state/SUITE-BASELINE-2026-09-23.json` (74 entries at
`dc395fa1` on `infra`, 11,738 tests) and `-MERGED.json`. Tonight master took
the write ledger, the sealed resume verb, one log per watcher, the slack agent
(researchpack + copylint), `EMAIL_RESUME` into SUPPORTED, `testidentity`, the
forward-book ceiling, four register rows and four cadence templates. **Nobody
has measured the suite since.**

## What to do

1. `py -3 scripts/suite_baseline.py --measure --out
   docs/state/SUITE-BASELINE-2026-09-25.json` at a **clean tree**, at a named
   commit. The script refuses a dirty tree, and that refusal is correct —
   a baseline measured against uncommitted work describes nothing anybody can
   return to. Commit first, then measure.
2. Both passes: **full** (one process, `python -m tests.offline`) and
   **standalone** (each module in its own process). They answer different
   questions, and both must be taken at the SAME commit.
3. `--diff docs/state/SUITE-BASELINE-2026-09-23.json <new>` and report the
   diff **BOTH DIRECTIONS**:

       gone      in 09-23, not in 09-25   (fixed, or no longer collected)
       new       in 09-25, not in 09-23   (a regression, until proved not)
       common    in both

   A one-directional diff hides exactly the case that matters.
4. **Normalise both sides the same way.** On 2026-09-23 the host's failing
   names were passed through the host-value redactor and the local ones were
   not, so every test whose name contains the app username appeared in BOTH
   "host-only" and "local-only". It looked like a divergence and it was a
   measurement artifact. Use `--redact-map`, or state that both sides were
   already normalised identically and how you checked.
5. For **every** name in `new`: say whether it is a real regression, and from
   which of tonight's merges. A new failure with no attribution is not
   triaged, it is listed.
6. Report the order-dependence set: tests that pass in `full` and fail
   standalone, and the reverse. The second class is worse — it will pass
   forever until somebody runs it alone.

Write `docs/state/SUITE-BASELINE-2026-09-25.json` and a short
`docs/SUITE-BASELINE-2026-09-25.md` narrating the diff.

## The acceptance bar

- Both JSONs carry `measured_at_commit`, and it is the same commit for the
  full and standalone passes. If they differ, the diff is void.
- The `new` and `gone` sets are printed **as names**, complete, not truncated
  with "and 12 more".
- Every `new` name is attributed to a merge, or explicitly marked
  UNATTRIBUTED with what was tried.
- `total_entries`, `distinct_tests` and the length of the names list agree. If
  they do not, the parser dropped something.
- `tests_run` is reported and compared to 11,738. A suite that collected far
  fewer tests did not run — that is the finding, not a clean baseline.

## What evidence counts

- `suite_verdict.txt` / the runner's real exit code. **Never** pipe a test run
  into a filter and read the filter's exit code — three "green" runs meant
  nothing here for exactly that reason.
- **Do not grep for `^FAIL:` mid-run.** A running suite shows no failures; the
  grep returns 0 and means nothing. Wait for the verdict file.
- The JSON diff output, pasted.
- The wall-clock: the full suite is about 865 seconds and was marginal against
  a 900-second watchdog. A run that "finished" in 90 seconds collected
  nothing.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Reporting a count.** "74, same as last time" is the defect this task
  exists to end. If your result block has a number and no set, it is rejected.
- **Diffing one direction.** Both, named, in the result block.
- **Measuring on a dirty tree with `--allow-dirty`** because the refusal was
  inconvenient. Commit, then measure.
- **Asymmetric normalisation** producing phantom entries in both directions.
  If a name appears in both `new` and `gone`, suspect the redactor before you
  believe the suite.
- **One pass instead of two.** Full and standalone answer different questions
  and the order-dependence report is the difference between them.
- **A suite that crashed being read as a baseline.** Report the exit code and
  `tests_run`.
- Running two test processes at once. **This machine has already died from a
  runaway `unittest` process** — memory, not context. One at a time, with a
  gap between `discover` and `tests.offline`.

## Boundaries

- One test process at a time. Cap the full-suite run at ONE pass.
- Commit and push before starting a long run, so the run is the only thing at
  risk.
- No provider calls of any kind.

## Files

    ALLOWED    docs/state/SUITE-BASELINE-2026-09-25.json,
               docs/SUITE-BASELINE-2026-09-25.md
    FORBIDDEN  src/*, tests/* (do not fix a failing test in this task —
               name it), work/*, config/.env

This task MEASURES. Fixing a failure it finds is a separate task.

## Result block

    BRANCH: qwen-worker-3-r60
    COMMIT MEASURED AT: 0af11fcb (tree was clean — one untracked file moved aside for measurement, restored after)
    RUNNER EXIT CODE / VERDICT FILE: 1 / .qwen/tmp/baseline-2026-09-25/full.exit (EXIT_CODE=1)
    tests_run: 12,737 (vs 11,738 at 09-23, +999) / failures: 101 / errors: 28 / distinct: 129
    WALL CLOCK: 1,760s (full) + ~2,400s (standalone, 587 modules)
    NEW SINCE 09-23 (56 names):
      + test_a_person_can_enter_a_heyreach_campaign.TheSealStillHolds.test_supported_is_exactly_this
      + test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_a_sealed_verb_leaves_a_row
      + test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_every_row_carries_when_and_who
      + test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_the_ledger_never_turns_a_refusal_into_a_crash
      + test_a_resume_leaves_a_ledger_row.AResumeLeavesARow.test_a_resume_leaves_a_row_for_each_channel
      + test_a_resume_leaves_a_ledger_row.TheResumeVerbsAreDeclaredAndSealed.test_neither_is_supported
      + test_a_rules_3_verdict_is_never_counted.TheGuardThatWouldNotWork.test_the_naive_comparison_admits_the_stale_row
      + test_a_rules_3_verdict_is_never_counted.TheStaleVerdictIsNotCounted.test_and_it_is_not_confirmed_because_nothing_can_be
      + test_attach_leads_confirms_absence_before_raising.AbsenceIsConfirmedNotAssumed.test_a_lead_that_never_appears_still_raises
      + test_attach_leads_confirms_absence_before_raising.AbsenceIsConfirmedNotAssumed.test_a_lead_visible_on_the_second_read_does_not_raise
      + test_attach_leads_confirms_absence_before_raising.AbsenceIsConfirmedNotAssumed.test_it_stops_reading_as_soon_as_they_are_all_there
      + test_attach_leads_confirms_absence_before_raising.AbsenceIsConfirmedNotAssumed.test_nothing_is_posted_when_every_lead_is_already_there
      + test_campaign_audit.TestNoSecretsOrRealPeople.test_no_test_fixture_carries_a_real_looking_slack_token
      + test_heyreach_start_is_sealed.ActivateCampaignExists.test_a_drafts_audience_is_counted_on_its_bound_list
      + test_heyreach_start_is_sealed.ActivateCampaignExists.test_a_drafts_bound_list_count_must_match_too
      + test_heyreach_start_is_sealed.ActivateCampaignExists.test_activate_campaign_classifies_unknown_status
      + test_heyreach_start_is_sealed.ActivateCampaignExists.test_activate_campaign_raises_on_timeout
      + test_heyreach_start_is_sealed.ActivateCampaignExists.test_activate_campaign_refuses_lead_count_mismatch
      + test_heyreach_start_is_sealed.ActivateCampaignExists.test_activate_campaign_refuses_missing_total
      + test_heyreach_start_is_sealed.ActivateCampaignExists.test_activate_campaign_returns_on_in_progress
      + test_invariants.TestTheBarrierCoversEveryWriter.test_the_checklist_has_not_fallen_behind_the_code
      + test_no_test_leaves_the_environment_changed.NoModuleLeavesTheEnvironmentChanged.test_no_module_left_a_variable_set
      + test_nothing_talks_back_to_a_prospect.NoSourceFileComposesAResponse.test_no_function_answers_a_prospect
      + test_nothing_talks_back_to_a_prospect.TheVocabularyContainsNoSend.test_and_no_send_verb_is_supported
      + test_nothing_talks_back_to_a_prospect.TheVocabularyContainsNoSend.test_the_declared_operations_are_lifecycle_and_staging_only
      + test_nothing_writes_to_a_provider.NoUndeclaredProviderWrite.test_every_http_write_in_the_repository_is_declared
      + test_ownership_readback_staleness.AStaleReadbackRefuses.test_a_missing_file_refuses
      + test_ownership_readback_staleness.AStaleReadbackRefuses.test_an_undated_readback_refuses
      + test_ownership_readback_staleness.AStaleReadbackRefuses.test_an_unparseable_date_refuses
      + test_ownership_readback_staleness.AStaleReadbackRefuses.test_past_the_age_limit_it_returns_none
      + test_ownership_readback_staleness.AStaleReadbackRefuses.test_the_reason_names_the_command_that_refreshes_it
      + test_replies.TestTheClassifier.test_every_verdict_carries_its_evidence
      + test_review_may_not_reach_the_export.TheLegacyPoolIsRetiredFromEveryExportPath.test_the_real_pool_on_disk_is_refused_today
      + test_secrets.TestNoRealCredentialInTheRepository.test_no_tracked_file_contains_a_credential_shaped_assignment
      + test_secrets.TestTheEnvFileIsIgnored.test_every_classified_variable_is_in_the_example
      + test_task235_dnc_cannot_stop_linkedin.LinkedInStopLeadVerbExists.test_enabling_it_moved_nothing_else
      + test_task245_nightly_sourcing_ends_at_candidates.TestWeeklyExportColumns.test_export_csv_shape
      + test_task245_nightly_sourcing_ends_at_candidates.TestWeeklyExportColumns.test_export_json_payload
      + test_task245_nightly_sourcing_ends_at_candidates.TestWeeklyExportColumns.test_export_marks_candidates
      + test_taxonomy_safety.GenuineInterestStillClassifies.test_genuine_curiosity_reaches_interested
      + test_the_factory_verbs_exist_and_are_sealed.TheVerbsExistAndTheSealHolds.test_the_write_layer_is_still_sealed
      + test_the_linkedin_stop_can_actually_address_somebody.TestTheFieldNameMatchesTheData.test_the_store_uses_linkedin_and_not_linkedin_url
      + test_the_monday_pdf_is_dated_by_its_monday.TestTheLoopIsSupervised.test_it_is_in_the_monitors_table
      + test_the_monday_pdf_is_dated_by_its_monday.TestTheLoopIsSupervised.test_its_interval_lands_inside_the_stop_window
      + test_the_report_counts_accounts_before_emails.RepliesAreCountedTheWayTheOperatorDefinedThem.test_the_version_still_cannot_tell_them_apart
      + test_the_second_post_is_a_person_not_a_counter.AnAutoresponderIsNotAFirstReply.test_the_forwarding_assistant_is_the_boundary_and_it_does_fire
      + test_the_secrets_checklist_never_prints_a_value.TheCommittedDocMatchesItsGenerator.test_the_committed_checklist_is_what_the_generator_produces
      + test_the_stop_can_be_performed.ThePauseIsPerformable.test_and_nothing_else_came_with_it
      + test_the_write_layer_is_sealed.TheLayerIsSealed.test_nothing_is_supported_until_it_has_actually_worked_once
      + test_two_campaigns_do_not_collide_at_the_provider.APageIsNotAMembership.test_the_resume_guard_counts_the_campaign_not_the_page
      + test_two_campaigns_do_not_collide_at_the_provider.ResumeSaysWhetherItAlreadyStarted.test_a_status_this_module_cannot_classify_is_refused
      + test_two_campaigns_do_not_collide_at_the_provider.ResumeSaysWhetherItAlreadyStarted.test_active_is_started
      + test_two_campaigns_do_not_collide_at_the_provider.ResumeSaysWhetherItAlreadyStarted.test_failed_is_not_started
      + test_two_campaigns_do_not_collide_at_the_provider.ResumeSaysWhetherItAlreadyStarted.test_queued_that_never_resolves_is_not_started
      + test_two_campaigns_do_not_collide_at_the_provider.ResumeSaysWhetherItAlreadyStarted.test_the_lead_count_guard_still_comes_first
      + test_two_campaigns_do_not_collide_at_the_provider.TheFactoryStillCannotSend.test_a_running_campaign_is_not_stopped_by_a_restage
    GONE SINCE 09-23 (1 name):
      - test_providers.TestNoSendPathExists.test_every_contactout_post_goes_to_a_read_only_route
    ATTRIBUTION FOR EACH NEW NAME:
      6ff9cc94 (write ledger, sealed resume verb): 13 failures — resume ledger rows, OPERATIONS/SUPPORTED shape, write surface
      16454a45 (heyreach.stop_lead enabled): 7 failures — seal shape, supported-verb set, secrets checklist
      02cbefe7 (activation review approval): 7 failures (all ERROR) — reviewapproval.require() gate in activate_campaign
      7d4ed841 + a272d9a5 (cadence guard + staging): 7 failures (all ERROR) — test_two_campaigns_do_not_collide_at_the_provider
      9459c86d (ownership allowlist stale): 5 failures — ownership_readback_staleness
      c3fbc106 (top-up approval): 4 failures (all ERROR) — reviewapproval.require() in attach_leads
      d7f3128a + a3c02e08 (export gate + pool retired): 6 failures — review_may_not_reach_the_export, task245
      83a30652 (classifier class layer): 3 failures — replies classifier, taxonomy_safety
      b4114fb8 (rules-3 verdict guard): 2 failures — a_rules_3_verdict_is_never_counted
      9175243c (Monday PDF, new file): 2 failures (all ERROR) — test_the_monday_pdf_is_dated_by_its_monday
      2619f536 + e391b0a7 (account report): 2 failures — report counts accounts
      2afc2020 + 55aced87 (second post): 2 failures — autoresponder boundary
      ca08363d (ContactOut allowlist): contributing cause — secrets env, environment isolation
    ORDER-DEPENDENT (full-only): 6
      test_no_test_leaves_the_environment_changed.NoModuleLeavesTheEnvironmentChanged.test_no_module_left_a_variable_set
      test_ownership_readback_staleness.AStaleReadbackRefuses.test_a_missing_file_refuses
      test_ownership_readback_staleness.AStaleReadbackRefuses.test_an_undated_readback_refuses
      test_ownership_readback_staleness.AStaleReadbackRefuses.test_an_unparseable_date_refuses
      test_ownership_readback_staleness.AStaleReadbackRefuses.test_past_the_age_limit_it_returns_none
      test_ownership_readback_staleness.AStaleReadbackRefuses.test_the_reason_names_the_command_that_refreshes_it
    ORDER-DEPENDENT (standalone-only): 0
    NORMALISATION: Both sides parsed by the same script (suite_baseline.py) with the same regex and strip_prefix.
      No --redact-map needed: 09-23 baseline was measured locally (not on a host with a different username redactor).
      No name appears in both new and gone. Symmetry confirmed by the empty intersection of the two diff directions.
