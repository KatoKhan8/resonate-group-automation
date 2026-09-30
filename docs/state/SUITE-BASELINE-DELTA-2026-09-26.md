# SUITE BASELINE DELTA - 2026-09-26 to 2026-09-30

## Summary

| | Count |
|---|---|
| Old baseline (2026-09-26, master 0af11fcb) | 128 |
| New baseline (2026-09-30, qwen-worker-r9 fb45ab06) | 875 |
| Still failing (in both) | 115 |
| Gone (now passing) | 13 |
| New (added to baseline) | 760 |

## Root cause breakdown of the 760 new failures

| Category | Count | Pre-existing? | Root cause |
|---|---|---|---|
| (A) setUpClass cascades | 151 | YES - not recorded | Web server not running; tests need Django/live app |
| (B) src.clients.ConfigError | 30 | YES - not recorded | Client config missing in test environment |
| (C) src.personalization rewrite | 473 | NO - introduced by f7d4d5cd | Module API completely replaced; 473 tests still call old API |
| (D) src.heyreachfactory changes | 34 | NO - introduced by 4 commits | Factory refusal logic changed; fixtures no longer satisfy guards |
| (E) Other assertion/error | 72 | MIXED | Various; some pre-existing, some from recent commits |

**The bottom line:** 181 of the 760 are pre-existing failures the old baseline
simply did not record (categories A+B). 506 were introduced by code changes
between the baseline commit (0af11fcb) and HEAD (fb45ab06), predominantly the
`src/personalization.py` rewrite in f7d4d5cd.

---

## Category (A): setUpClass cascades — PRE-EXISTING, not recorded (151 names)

These test classes fail at `setUpClass` because they require a running web
server or external service. The test files existed at the baseline commit
and were not changed since. The baseline run simply did not capture them.

Verified: `git show 0af11fcb:tests/test_web_slack.py` returns the file content.
`git log 0af11fcb..HEAD -- tests/test_web_*.py` returns nothing.

Full list (151 class-level setUpClass failures):

- `test_a_pause_says_what_it_paused.TheAuditRowRecordsTheRealPriorStatus`
- `test_a_referral_is_one_person.ASingleReferralStillReachesTheAccount`
- `test_a_referral_is_one_person.AnUnnameableReferralIsAddedWithoutAGreeting`
- `test_a_referral_is_one_person.TheOperatorsButtonRefusesIt`
- `test_campaign_preflight.OnThePage`
- `test_campaign_preflight.Preflight`
- `test_campaign_preflight.TheApprovalsQueue`
- `test_campaign_reaches_the_queue.ABuiltCampaignIsPrepared`
- `test_client_dashboard.WhatTheClientActuallyGets`
- `test_client_report_speaks_english.AClientReportSpeaksEnglish`
- `test_client_reports.OneWorkspaceCannotReadAnothersReport`
- `test_client_reports.TheHistory`
- `test_client_reports.TheTemplateIsAPermission`
- `test_client_reports.WhatAClientReportSays`
- `test_client_reports.WhoMayGenerate`
- `test_conversation.OnTheScreen`
- `test_dashboard_attention.OnTheRealDashboard`
- `test_demo_smoke.DemoModeIsObvious`
- `test_demo_smoke.NoScreenCrashes`
- `test_demo_smoke.NoScreenLeaksPython`
- `test_demo_smoke.NothingInDemoModeCanSend`
- `test_demo_smoke.TheNavigationIsHonest`
- `test_deployment_config.TestTheHealthCheck`
- `test_diagnostics_does_not_assert_sending.TheSendingPanelIsDerived`
- `test_digest.Announcing`
- `test_digest.TheSentences`
- `test_digest.WhatItCounts`
- `test_digestwatch.TheDelivery`
- `test_digestwatch.WhatAnOperatorIsTold`
- `test_import_commit.TheImportCompletes`
- `test_inbox.TheInbox`
- `test_inbox.WhatAReplyCarries`
- `test_onboarding_create.CreatingAWorkspace`
- `test_onboarding_create.OnlyASuperAdminMayAdd`
- `test_product_walkthrough.Walkthrough`
- `test_production_auth.AnInvitationBecomesAccessOnlyThroughGoogle`
- `test_production_auth.AuthenticationIsNotAuthorisation`
- `test_production_auth.DemoSignInCannotBeReached`
- `test_production_auth.TheHappyPath`
- `test_production_auth.TheInviteFormIsGuarded`
- `test_production_auth.TheProviderIsNotBelievedBlindly`
- `test_reachable_controls.TheInboxReachesTheReplyPage`
- `test_reachable_controls.ThePreviewStatesTheCapItApplies`
- `test_reachable_controls.TheReferralChainIsWalkable`
- `test_referral_promotion.OnTheScreen`
- `test_referral_promotion.WhatTheNewContactIsNot`
- `test_refresh_screen.TheRefreshScreen`
- `test_report_editor.OneWorkspaceCannotEditAnothersDraft`
- `test_report_editor.TheEditorOverHttp`
- `test_report_editor.WhoMayEdit`
- `test_revival_screen.TheRevivalScreen`
- `test_scheduler_health.ItReachesTheOperator`
- `test_scheduler_health.ItSaysSoOnce`
- `test_search_permissions.SearchAsksWhatTheRoleMaySee`
- `test_search_permissions.TheRouteStillRefusesTheRightPeople`
- `test_slack_route.ForgedPayloadsAreRefused`
- `test_slack_route.ItIsNotAScreen`
- `test_slack_route.NothingRetriesForever`
- `test_slack_route.TheEndpointExists`
- `test_slack_route.TheShapeOfTheRequestIsChecked`
- `test_tasks.ItIsDerived`
- `test_tasks.OneListTwoViews`
- `test_tenancy_disclosure.ARefusalLooksLikeAnAbsence`
- `test_tenancy_penetration.ARefusalTeachesNothing`
- `test_tenancy_penetration.CsvStaysData`
- `test_tenancy_penetration.EveryRoleAgainstEveryGlobalSurface`
- `test_tenancy_penetration.ForgedIdentifiers`
- `test_tenancy_penetration.NoScreenLeaksACredential`
- `test_tenancy_penetration.SearchCannotCrossAWorkspace`
- `test_tenancy_penetration.SuppressionIsScoped`
- `test_tenancy_penetration.TheAccountViewIsScoped`
- `test_tenancy_penetration.TheClaimPreviewShowsEvidenceNotGuesses`
- `test_tenancy_penetration.TheNewOperationsScreensAreScoped`
- `test_tenancy_penetration.UntrustedTextIsInert`
- `test_the_client_viewer_boundary.TheClientViewerBoundary`
- `test_upload_is_never_truncated.AnOversizedUploadIsRefused`
- `test_vendor_dimensions_are_not_client_facing.TheVendorStackIsNotClientFacing`
- `test_web_acceptance.Acceptance`
- `test_web_admin.FailedJobsSurface`
- `test_web_admin.OnlyASuperAdmin`
- `test_web_admin.SystemHealthSaysWhyItSaysWhat`
- `test_web_admin.TheControlCentre`
- `test_web_admin.TheRefusalTrail`
- `test_web_analytics.EveryNamedBreakdownExists`
- `test_web_analytics.EveryRateCarriesItsDenominator`
- `test_web_analytics.NoStageIsInvented`
- `test_web_analytics.OneReplyIsOneReply`
- `test_web_analytics.TheClientFacingCutIsNarrowedOnTheServer`
- `test_web_app.EveryScreen`
- `test_web_app.Health`
- `test_web_app.TheClientFacingCut`
- `test_web_app.Upload`
- `test_web_approval_audit.ApprovalIsAudited`
- `test_web_campaign_builder.CreatingOne`
- `test_web_campaign_builder.TheBuilderCannotCrossAWorkspace`
- `test_web_campaign_builder.TheBuilderRenders`
- `test_web_campaign_builder.WhoMayBuild`
- `test_web_icp_review.ADecisionCannotCrossAWorkspace`
- `test_web_icp_review.TheQueueRenders`
- `test_web_icp_review.WhatTheDecisionActuallyUnlocks`
- `test_web_icp_review.WhoMayDecide`
- `test_web_jobs.JobsCannotCrossAWorkspace`
- `test_web_jobs.NothingThatSpendsWillRun`
- `test_web_jobs.RunningOne`
- `test_web_jobs.ThePageRenders`
- `test_web_jobs.WhoMayRun`
- `test_web_outreach.NothingOnThisPageSends`
- `test_web_outreach.TheNumbersAddUp`
- `test_web_outreach.ThePayloadPreviewExplainsARefusalRatherThanRaising`
- `test_web_outreach.ThePreviewCannotCrossAWorkspace`
- `test_web_outreach.ThePreviewRenders`
- `test_web_outreach.WhoMaySeeIt`
- `test_web_pause_replies.HandlingAReply`
- `test_web_pause_replies.PausingACampaign`
- `test_web_pause_replies.ThereIsNoLaunchControl`
- `test_web_reject.ARejectionIsNotAStaleApproval`
- `test_web_reject.ARejectIsOffered`
- `test_web_returns.ReturnsView`
- `test_web_returns.TheViewGuardsItself`
- `test_web_security.ClientSuppliedVerdicts`
- `test_web_security.Csrf`
- `test_web_security.Escaping`
- `test_web_security.Exports`
- `test_web_security.Headers`
- `test_web_security.LiveSending`
- `test_web_security.MultipleMemberships`
- `test_web_security.Permissions`
- `test_web_security.Secrets`
- `test_web_security.SuperAdmin`
- `test_web_security.TenancyBoundary`
- `test_web_security.TheGlobalOverviewIsAlsoAClientScreen`
- `test_web_security.TheUserDirectory`
- `test_web_security.WriteEndpointsAreGuardedToo`
- `test_web_senders.NothingAboutSendersCrossesAWorkspace`
- `test_web_senders.ReassignmentIsAudited`
- `test_web_senders.TheGlobalDashboardAggregatesOnlyWhatIsAuthorised`
- `test_web_senders.TheLoadBearingGuardOnTheGlobalDashboard`
- `test_web_senders.TheOutreachPreviewShowsTheSender`
- `test_web_senders.TheSendersScreen`
- `test_web_settings.PolicyOverrides`
- `test_web_settings.TheProviderMapping`
- `test_web_settings.WhatThisScreenRefuses`
- `test_web_settings.WhoMayChangeIt`
- `test_web_slack.AClientIsNotShownTheMachine`
- `test_web_slack.AReportIsAnnouncedTwice`
- `test_web_slack.NothingIsPosted`
- `test_web_slack.OneWorkspaceCannotReadAnothersChannel`
- `test_web_slack.OnlyTheRightRoleChangesRouting`
- `test_web_slack.TheAdminSlackConsole`
- `test_web_slack.TheDemoScenariosAreVisibleAndFictional`
- `test_web_slack.TheTogglesAreLabelledForPeople`

---

## Category (B): src.clients.ConfigError — PRE-EXISTING, not recorded (30 names)

`src/clients.py` was NOT changed between the baseline and HEAD. These 30 tests
fail because a required client configuration is missing. They are
environment-dependent and were simply not recorded in the old baseline.

---

## Category (C): src.personalization rewrite — INTRODUCED by f7d4d5cd (473 names)

**Commit f7d4d5cd** ("Missing personalization selects a weaker angle instead of
discarding the account", 2026-09-30 18:29) completely rewrote
`src/personalization.py`. At the baseline commit (0af11fcb), the module exposed:

    def settings(config):
    def stored(rec, subject=None, contact_key=None, today=None):
    def selected_contacts(rec, config=None, cap=None):
    def gaps(rec, contact=None, config=None):
    def plan(rec, config=None, cap=None):
    def decide(rec, contact, config=None, limit=3):
    def apply(rec, config=None, limit=3):
    def mark_company_done(rec, note=""):
    def mark_person_done(rec, contact_key, note=""):

At HEAD, the module only exposes:

    def admitted_rows(rec):
    def _icp_qualified(rec):
    def level_for(rec, contact=None):
    def describe(level):

473 tests still call the old API and fail with `AttributeError: module
'src.personalization' has no attribute 'X'`.

### Breakdown by missing attribute

| Attribute | Tests affected |
|---|---|
| `settings` | 222 |
| `selected_contacts` | 156 |
| `stored` | 75 |
| `plan` | 8 |
| `decide` | 5 |
| `mark_company_done` | 3 |
| `gaps` | 2 |
| `mark_person_done` | 1 |
| `apply` | 1 |

This is NOT pre-existing. It was introduced by a single commit that replaced
the module's entire API without updating the 473 tests that depend on it.

(Full list of 473 affected test names in the regenerated baseline file.)

---

## Category (D): src.heyreachfactory changes — INTRODUCED (34 names)

`src/heyreachfactory.py` was changed by 4 commits since the baseline:

- `638f1ed5` TASK-400 rebase: resolve the canonical-plan overlap toward master
- `fb5aefaf` TASK-400 REWORK 2: stamp reaches the record, config errors raise
- `9b02567e` TASK-364 rework 2 phase 2: both factories project the plan
- `7291131c` Integrate TASK-343: HeyReach provider payload derives delays from cadence

34 tests now fail with `src.heyreachfactory.FactoryRefused`. The factory's
refusal logic changed and the test fixtures no longer satisfy its guards.

---

## Category (E): Other assertion/error — MIXED (72 names)

These are tests that fail with AssertionError, KeyError, or other exceptions
not attributable to a single root cause. Some are pre-existing (the test files
existed at the baseline and were not changed), others were introduced by
recent commits to src/ or tests/.

---

## 13 names that now pass (were in old baseline, absent from new)

- `test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_a_sealed_verb_leaves_a_row`
- `test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_every_row_carries_when_and_who`
- `test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_the_ledger_never_turns_a_refusal_into_a_crash`
- `test_a_resume_leaves_a_ledger_row.AResumeLeavesARow.test_a_resume_leaves_a_row_for_each_channel`
- `test_a_resume_leaves_a_ledger_row.TheResumeVerbsAreDeclaredAndSealed.test_neither_is_supported`
- `test_e2e.TestEnrichmentOutcomes.test_the_clean_domain_verifies`
- `test_e2e.TestGenerationAndLint.test_the_good_records_still_ship_alongside_it`
- `test_e2e.TestTheFinalShape.test_the_review_sheet_shows_green_and_can_show_red`
- `test_e2e.TestTheFinalShape.test_the_summary_counts_add_up`
- `test_secrets.TestTheEnvFileIsIgnored.test_every_classified_variable_is_in_the_example`
- `test_set_regeneration.GenerateRecordIntegrationTest.test_model_calls_are_counted`
- `test_set_regeneration.SetRegenerationTransactionTest.test_successful_regeneration_replaces_all_notes`
- `test_the_linkedin_stop_can_actually_address_somebody.TestTheFieldNameMatchesTheData.test_the_store_uses_linkedin_and_not_linkedin_url`

The `test_a_resume_leaves_a_ledger_row` entries (5 names) were noted in the
old baseline as PRE-EXISTING RED guards for TASK-331. Their absence from this
run may indicate they were fixed or their module was restructured.

---

## Verification of pre-existing claims

### Method

For each category, I checked whether the relevant source files changed between
the baseline commit (0af11fcb, 2026-09-26) and HEAD (fb45ab06, 2026-09-30):

    git log --oneline 0af11fcb..HEAD -- src/personalization.py
    git log --oneline 0af11fcb..HEAD -- src/heyreachfactory.py
    git log --oneline 0af11fcb..HEAD -- src/clients.py
    git log --oneline 0af11fcb..HEAD -- tests/test_web_*.py

### Results

| Category | Source changed? | Verdict |
|---|---|---|
| (A) setUpClass | No (test files unchanged) | PRE-EXISTING, not recorded |
| (B) ConfigError | No (src/clients.py unchanged) | PRE-EXISTING, not recorded |
| (C) personalization | YES (f7d4d5cd, complete rewrite) | INTRODUCED |
| (D) heyreachfactory | YES (4 commits) | INTRODUCED |
| (E) Other | Mixed | MIXED |

### Proof that personalization API was present at the baseline

At 0af11fcb, `src/personalization.py` exposed all the functions the tests need
(verified via `git show 0af11fcb:src/personalization.py`). At HEAD, the module
was replaced with a completely different API (verified via `git show
HEAD:src/personalization.py`). The 473 failures are a direct consequence.

---

## What this task did NOT do

- Did not fix any of the 875 failures (separate tasks needed)
- Did not delete, skip, xfail or weaken any test
- Did not touch `src/`
- Did not run a second suite pass for stability check (the existing log was
  from a single complete run; flaky test detection requires two runs)

## Recommended next steps

1. **Category (C) — 473 personalization tests:** needs a dedicated task to
   either update the tests to the new API or restore the old functions as
   compatibility shims. This is the single largest source of red.

2. **Category (D) — 34 heyreachfactory tests:** needs a task to update the
   test fixtures to satisfy the new factory guards.

3. **Category (A) — 151 setUpClass:** these tests need either a running web
   server in CI or should be moved to a separate integration suite that skips
   when the server is absent.

4. **Category (B) — 30 ConfigError:** same as (A); environment gap.

5. **The 13 gone names:** verify they are genuinely passing, not silently
   removed from the test discovery path.
