# Pre-production suite review of dc43ab6b

Measured 2026-09-28 by an independent review session, in the git-isolated
worktree `.claude/worktrees/agent-a26a9801db649848e`.

    HEAD   dc43ab6bf1ea4a2766dfa643bbae288783260f0e   (detached)
    tree   c130419fd65d7eaff88ceab8437d733004a110a8
    git status --porcelain   EMPTY at launch and at completion

**VERDICT: DO NOT APPLY.** One blocking regression, established below and
reproduced standalone. 19 NEW failing names against the 2026-09-26 baseline,
of which 15 are that one regression.

## The command that produced the result

    # from the worktree root, DEFAULT environment (no QUEUE override)
    # PATH must contain Git Bash, or 5 tests error spuriously - see artifact 2
    python -u scripts/run_suite.py --timeout 7200

Artifacts: `scripts/suite_verdict.txt` (verdict, gitignored),
`scripts/suite_run.log` (full log, gitignored).

    exit_code=1   wall_seconds=2925.0   timed_out=False
    Ran 13627 tests in 2920.496s
    FAILED (failures=95, errors=40, skipped=15, expected failures=18)

`run_suite.py --timeout` defaults to **1800s**, which is shorter than the
suite. The default silently produces `exit_code=124, timed_out=True`. Pass a
real timeout. `scripts/suite_baseline.py` is right that a watchdog reports a
number that is not the suite's.

## Set comparison against docs/state/SUITE-BASELINE-2026-09-26.txt

Compared as SETS, using the repo's own parser
(`scripts/suite_baseline.parse_failures`) so both sides are spelled
identically. Baseline parses to exactly 128 names (FAIL=100, ERROR=28),
matching its own header, with zero unparsed lines.

    baseline distinct   128
    this run distinct   135
    NEW                  19   <-- see attribution below
    FIXED                12
    UNCHANGED           116

### NEW (19)

15 of these are one module, and they are the blocking finding:

    test_the_send_is_recorded_once_and_by_the_provider.NobodyIsGuessedAt.test_a_disagreeing_client_is_refused
    test_the_send_is_recorded_once_and_by_the_provider.NobodyIsGuessedAt.test_a_lead_naming_no_record_we_hold_is_reported_not_applied
    test_the_send_is_recorded_once_and_by_the_provider.NobodyIsGuessedAt.test_the_address_matches_when_the_variables_are_missing
    test_the_send_is_recorded_once_and_by_the_provider.OneMessageIsOneTouch.test_a_hand_written_staging_touch_is_reconciled_not_duplicated
    test_the_send_is_recorded_once_and_by_the_provider.OneMessageIsOneTouch.test_a_second_scheduled_email_on_another_step_is_its_own_touch
    test_the_send_is_recorded_once_and_by_the_provider.OneMessageIsOneTouch.test_polling_a_sent_row_twice_records_one_event
    test_the_send_is_recorded_once_and_by_the_provider.OneMessageIsOneTouch.test_the_reconciled_touch_keeps_the_step_the_staging_recorded
    test_the_send_is_recorded_once_and_by_the_provider.SentIsNotDelivered.test_a_bounce_is_recorded_and_is_not_a_confirmed_touch
    test_the_send_is_recorded_once_and_by_the_provider.SentIsNotDelivered.test_an_event_the_vocabulary_cannot_hold_is_refused_out_loud
    test_the_send_is_recorded_once_and_by_the_provider.SentIsNotDelivered.test_an_unknown_status_produces_no_event
    test_the_send_is_recorded_once_and_by_the_provider.SentIsNotDelivered.test_dry_is_the_default_and_writes_nothing
    test_the_send_is_recorded_once_and_by_the_provider.SentIsNotDelivered.test_every_state_this_module_maps_is_a_state_it_can_explain
    test_the_send_is_recorded_once_and_by_the_provider.SentIsNotDelivered.test_scheduled_is_not_an_action_at_all
    test_the_send_is_recorded_once_and_by_the_provider.SentIsNotDelivered.test_sent_records_push_marked_and_never_email_delivered
    test_the_send_is_recorded_once_and_by_the_provider.SentIsNotDelivered.test_the_touch_is_dated_by_the_provider

The other four:

    test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_every_email_address_is_on_a_reserved_domain
    test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_real_client_prospect_or_roster_domain
    test_an_offer_cannot_be_invented.TestApprovalRefusal.test_approval_status_is_not_defaulted_to_approved
    test_the_cadence_reacts_to_what_the_prospect_did.ThePlannerReadsTheBranch.test_the_meeting_reaches_the_send_gate_too

### FIXED (12)

    test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_a_sealed_verb_leaves_a_row
    test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_every_row_carries_when_and_who
    test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_the_ledger_never_turns_a_refusal_into_a_crash
    test_a_resume_leaves_a_ledger_row.AResumeLeavesARow.test_a_resume_leaves_a_row_for_each_channel
    test_a_resume_leaves_a_ledger_row.TheResumeVerbsAreDeclaredAndSealed.test_neither_is_supported
    test_e2e.TestEnrichmentOutcomes.test_the_clean_domain_verifies
    test_e2e.TestGenerationAndLint.test_the_good_records_still_ship_alongside_it
    test_e2e.TestTheFinalShape.test_the_review_sheet_shows_green_and_can_show_red
    test_e2e.TestTheFinalShape.test_the_summary_counts_add_up
    test_nothing_writes_to_a_provider.NoUndeclaredProviderWrite.test_every_http_write_in_the_repository_is_declared
    test_secrets.TestTheEnvFileIsIgnored.test_every_classified_variable_is_in_the_example
    test_set_regeneration.GenerateRecordIntegrationTest.test_model_calls_are_counted

**The baseline's own header is out of date on one point.** It says
`test_a_resume_leaves_a_ledger_row` is PRE-EXISTING RED and must not be
reported as new. All five of its names are now GREEN and are 5 of the 12
FIXED above. The note should be retired, not carried forward.

## THE BLOCKING FINDING: a hermetic test path now reads a live provider

`confirm_email_touches` performs an unconditional provider read that nothing
mocks:

    confirm_email_touches            src/leadobserve.py:737
      -> email_step_ordinals         src/leadobserve.py:588
      -> bison.sequence_steps(campaign_id)
      -> bison.headers()             src/providers/bison.py:35
      -> key('BISON_KEY')            src/providers/__init__.py:122
      -> src.providers.MissingKey: no BISON_KEY in config/.env

`email_step_ordinals` does **not exist** at the baseline commit `0af11fcb`
(0 occurrences) and exists at `dc43ab6b` (3). The branch added it.

The four classes in `test_the_send_is_recorded_once_and_by_the_provider`
derive from `QueueTest`, not `ProviderTest`, so `tests/base.py` does **not**
patch the transport for them. The module patches `bison.scheduled_emails`
and has zero occurrences of `sequence_steps`, so the new call falls straight
through to the real adapter.

**Why this is worse than the red, and why master cannot see it.** The
failure mode depends only on whether `config/.env` is present:

  - no `config/.env` (this worktree): `MissingKey` -> 15 ERRORs, visible.
  - `config/.env` present (the main checkout has one): no error at all. The
    unit suite makes a **real HTTP GET to EmailBison on every run**,
    silently, from a test that believes it is offline.

So on master this regression is invisible, and the symptom is unattributed
provider traffic rather than a red test. This is the same shape as the
recurring defect CLAUDE.md names: a thing that looks healthy because nothing
downstream is actually being observed.

Reproduced standalone in the clean worktree, so it is not an ordering
artifact.

## The branch's own new test file is GREEN

`tests/test_a_provider_confirmed_send_reaches_the_ledger.py` (new on this
branch, 599 lines):

  - standalone at dc43ab6b: **Ran 39 tests ... OK**, all 39 pass
  - in the full run: **0 failing or erroring entries**

It contributes nothing to the NEW set. Note the irony worth recording: the
branch's new tests for the send ledger all pass, while the pre-existing
module that guards the same contract is the thing it broke.

## MEASUREMENT ARTIFACTS - read before trusting any re-run

These three cost real time and each produced a false NEW set. They are
properties of the harness, not of the branch.

**1. `QUEUE` is the root control, not `WORKSPACES`.** `src/store.py`
resolves every state file except the queue from
`os.path.dirname(queue_path())`, and `WORKSPACES` (`src/workspaces.py:173`)
is a path to a **file** (`workspaces.jsonl`), not a directory. Setting
`QUEUE=<dir>/queue.jsonl` and leaving all 34 `STATE_OVERRIDES` unset moves
the whole set together, which is exactly what `store.use_directory()` does.

Do **not** point `QUEUE` at a populated copy of production `work/` to run
this suite. `tests/base.py:622` isolates per test into a `mkdtemp`, so the
suite is designed for no external state; a populated queue changes the
behaviour of precisely the tests that do not isolate. Measured, same commit,
same module, only the env differing:

    QUEUE unset        test_the_client_scope_under_attack   10 tests, 117s, OK
    QUEUE=<24MB copy>  same module                          >300s standalone,
                                                            >30 min in-suite

The baseline's 2152s total is itself evidence it was measured unpopulated.

**2. Git Bash must be on PATH.** With it absent, 5 tests error with
`FileNotFoundError: [WinError 2]` from `subprocess.run(["bash", ...])` and
`(["grep", ...])` — 4 setUpClass errors in
`test_provision_survives_its_own_firewall` plus
`test_waterfall_order.TestXaiOffByDefault.test_xai_has_no_caller_in_src`.
All five vanish once `C:\Program Files\Git\bin` and
`C:\Program Files\Git\usr\bin` are on PATH. They are not branch defects.

**3. Untracked files contaminate `test_fixture_hygiene`.** It enumerates
with `git ls-files --others --exclude-standard` **deliberately**, so any
untracked, non-ignored file is in scope by design. A second checkout left in
the worktree put 6 spurious names into the NEW set. `git status --porcelain`
must be empty before the run. The suite's own log is safe: `*.log` is
gitignored and `.log` is not in `TEXT_SUFFIXES`.

**4. Long jobs die when launched through background Bash here.** Three runs
were killed at 1-4 minutes at unrelated points with no traceback and no
verdict file. The identical command launched detached via PowerShell
`Start-Process` ran to completion. Two orphaned
`python -m unittest discover` children were also found still running after
their parents were killed, competing for the machine.

## A guard that does not cover what its comment claims

`src/store.py:956` defines `PRODUCTION_WORK = os.path.join(ROOT, "work")`,
and `ROOT` is `dirname(store.py)/..`. In a worktree that resolves to
`<worktree>/work`, nowhere near the real `work/`. So
`refuse_production_write` — the "second barrier" whose comment says it "does
not depend on any test remembering anything" — would **not** stop a run
whose `QUEUE` was pointed at the true production `work/`. It protects
against the default path, not against a bad override.

Related, and confirmed by artifact: a run with `QUEUE` unset created
`<worktree>/work/provider-write-refusals.jsonl` (20KB) with **zero**
`ProductionStateUnderTest` raises, because that writer is outside the
barrier — exactly as the docstring at `src/store.py:980` warns. In the main
checkout that path is the real `work/`, which live Slack loops write every
300s.

## What this review did NOT establish

The 128-name baseline **cannot attribute a NEW name to this branch.**
`dc43ab6b` forks at `4b1fb0c6` and contains none of master's later commits,
while the baseline was taken at `0af11fcb`. Test files: 620 at the baseline
commit, 675 at `dc43ab6b` — 55 added, 0 removed; 12,737 tests vs 13,627. A
NEW name can therefore mean "this branch broke it", "a later master commit
broke it", or "the test did not exist then", and the baseline cannot
separate those.

The run that would separate them was **not performed** (execution mode was
reset before it started): the same clean invocation at the merge base
`4b1fb0c6`, diffed against this run as sets. `A - B` would be this branch's
effect and nothing else. The blocking finding above does not depend on it —
it is established from the code, the traceback and a standalone
reproduction — but these four do, and two are probably NOT this branch's:

  - `test_an_offer_cannot_be_invented...` — offer-ladder work is TASK-425,
    merged on **master** at `439aa169`; `dc43ab6b` does not contain it.
  - the two `test_fixture_hygiene` names — the real-domain hits include
    `tests/test_changing_an_approved_fact_changes_the_output.py` and
    `tests/test_task400_rework2.py`, neither of which is part of this
    branch's diff.
  - `test_the_cadence_reacts_to_what_the_prospect_did...` — unattributed;
    `AssertionError: None != 'blocked:company_paused'`.

No `work/` under the real repository root was written at any point, and no
network write was made.
