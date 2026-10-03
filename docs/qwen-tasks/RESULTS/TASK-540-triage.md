# TASK-540 — Triage pending branch results, batch 3 of 8

**Triage date:** 2026-10-04
**Triage by:** Qwen (qwen-worker-3-r9)
**Scope:** 28 tasks, read-only. No integration, no merge, no cherry-pick.

---

## TASK-318

    task                TASK-318
    branch              qwen-worker-2-r9
    exact SHA           84268e53233e37441d9b58414eb432d163537e9f (origin/qwen-worker-2-r9)
    purpose             Build the Offer Engine — fill the gaps in the offers section of
                        src/secondbrain.py.
    files changed       63 files: src/providerwrites.py, docs/PROVIDER-WRITE-SURFACE-2026-10-03.md,
                        docs/phase2-scenarios/S01-S30.yaml (30 files), 14 tests, various task files.
    tests               No RESULT block in the TASK-318 task file (still in TODO on branch).
                        Tests on branch relate to provider writes and phase2 scenarios, not offers.
    still relevant?     src/providerwrites.py EXISTS on master and HAS DIFF.
                        src/provider_truth_check.py is GONE from master.
                        No offer-engine code (src/secondbrain.py offers, src/offers.py) in the diff.
    conflicts / deps    Shares branch with TASK-372 (same SHA). Branch has work from TASK-972
                        (provider write surface) and phase2 scenarios, not TASK-318.
    disposition         REJECT — no RESULT block for TASK-318. Task file still in TODO on branch.
                        The branch's 63 files are from other tasks (provider writes, phase2 scenarios).
                        No offer-engine artifact exists on this branch.

---

## TASK-319

    task                TASK-319
    branch              glm-review-504-task-387
    exact SHA           515c638e14423a203e56f3ed3525af8569f72c07 (origin/glm-review-504-task-387)
    purpose             Turn five skills into executable SOPs — register prompts as data objects
                        with consumers, refuse to register a skill with no consumer.
    files changed       102 files: src/skills/ (loader + 5 skill modules), src/approve.py,
                        src/bisonfactory.py, src/copylint.py, src/generate.py, src/generate_campaign.py,
                        src/heyreachfactory.py, src/providers/bison.py, src/providers/heyreach.py,
                        src/run.py, 20+ GLM review docs, 30+ task files, 15+ tests.
    tests               tests/test_a_skill_is_loaded_by_the_stage_that_uses_it.py — 6/6 pass.
                        RESULT block present: STATUS DONE.
    still relevant?     Most src files EXIST on master and HAVE DIFFS. scripts/pool_status.py GONE.
                        The skills layer (src/skills/) is NOT in the diff against master — meaning
                        it was either already merged or never existed on master. The 102-file diff
                        is dominated by GLM reviews and task file moves from other tasks.
    conflicts / deps    Shares branch with TASK-385 and TASK-387 (same SHA). Overlaps with
                        TASK-328 (bison, heyreach, copylint, generate_campaign), TASK-358
                        (bisonfactory), TASK-386 (generate_campaign, bisonfactory).
    disposition         CANDIDATE — has a clear RESULT with passing tests. The skills layer is
                        additive (no prompt rewritten). But the branch is massive (102 files) and
                        carries work from many other tasks. Integration must cherry-pick only the
                        skills layer, not the whole branch.

---

## TASK-325

    task                TASK-325
    branch              qwen-worker-r60
    exact SHA           2594a3088814fa0c803afac8a654e9c6b72c6ebc (origin/qwen-worker-r60)
    purpose             Document the actual LinkedIn cadence tree — what is built, not what is
                        assumed.
    files changed       2 files: docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md (NEW),
                        task file move TODO→DONE.
    tests               Read-only task — no tests, no code changed.
    still relevant?     docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md EXISTS on master.
                        Diff against master is empty for this file — meaning master already has it
                        or an identical version.
    conflicts / deps    None. Docs-only, no source changes.
    disposition         STALE — the doc file exists on master and the diff is empty. Master already
                        has this deliverable.

---

## TASK-326

    task                TASK-326
    branch              qwen-worker-7-r9
    exact SHA           f3148ac50327f307fbebca0b261db612236d40a6 (origin/qwen-worker-7-r9)
    purpose             Second Brain retrieval is account-scoped — company research done once per
                        account, person relevance layers on top.
    files changed       35+ files: GLM review docs, task file moves, src/batchcontroller.py (GONE),
                        src/generate_campaign.py, src/store.py, scripts/, tests.
    tests               No RESULT block for TASK-326 on the branch. Task file still in TODO.
    still relevant?     src/batchcontroller.py is GONE from master. src/generate_campaign.py and
                        src/store.py EXIST and HAVE DIFFS, but the diffs are from other tasks on
                        this branch (TASK-484, TASK-491, etc.), not TASK-326.
    conflicts / deps    Shares branch with TASK-389 (same SHA). Branch carries GLM verification
                        work from 8+ other tasks.
    disposition         REJECT — no RESULT block for TASK-326. Task file still in TODO on branch.
                        The branch's changes are from other tasks.

---

## TASK-327

    task                TASK-327
    branch              qwen-worker-2-r60
    exact SHA           94819507ab30153ea72d570442d356fd5a7a32c8 (origin/qwen-worker-2-r60)
    purpose             A lead is never modelled as an isolated campaign unit — prove the account
                        model's edges are traversable with tests.
    files changed       4 files: tests/test_the_account_relationships_survive.py (NEW, 35 tests),
                        docs/state/ACCOUNT-MODEL-INVARIANTS.md (NEW), task file moves.
    tests               35 new tests, all green. 135 existing account tests unaffected.
                        RESULT block present: STATUS DONE.
    still relevant?     docs/state/ACCOUNT-MODEL-INVARIANTS.md EXISTS on master.
                        Test file is new and self-contained.
    conflicts / deps    None. Clean, isolated test + doc addition.
    disposition         CANDIDATE — clean, small, tests pass, clear RESULT. No overlaps with other
                        branches.

---

## TASK-328

    task                TASK-328
    branch              qwen-worker-12-r9
    exact SHA           34bf792bebc52d35ef218096a42616b333b9cce5 (origin/qwen-worker-12-r9)
    purpose             The approval hash is recorded and never checked — thread review_hash
                        through provider call sites so the gate can fire.
    files changed       40+ files: src/copylint.py, src/generate_campaign.py, src/providers/bison.py,
                        src/providers/heyreach.py, tests/test_an_approval_does_not_survive_a_re_render.py
                        (NEW, 14 tests), GLM review docs, task file moves.
    tests               14 new tests, all green. 33 total approval tests green.
                        RESULT block present: STATUS REVIEW.
    still relevant?     All four src files EXIST on master and HAVE DIFFS.
    conflicts / deps    Overlaps with TASK-319 (bison, heyreach, copylint, generate_campaign),
                        TASK-326 (generate_campaign), TASK-386 (generate_campaign, bisonfactory).
                        Four branches touch src/generate_campaign.py.
    disposition         CANDIDATE — has clear RESULT, tests pass, finding is valuable (default is
                        permissive, operator decision needed on making hash mandatory). But overlaps
                        with TASK-319 on provider files and generate_campaign.py. Integration order
                        matters.

---

## TASK-335

    task                TASK-335
    branch              qwen-worker-12-r9-sync
    exact SHA           3da4a246ee2536760d04dfc4d1d94b649160c2fa (origin/qwen-worker-12-r9-sync)
    purpose             Recover the audit and two provider artifacts from branches — cherry-pick
                        lost work (AUDIT-2026-09-26.md, groq.py, openrouter.py, contactout linkedin).
    files changed       45+ files: src/candidateexport.py, src/clientexport.py, src/ingest.py,
                        src/modelprices.py, src/nightlysourcing.py, src/notify.py, config files,
                        GLM reviews, task files, tests.
    tests               Recovery cherry-picks verified: 19/19 groq/openrouter tests, 26/26 contactout
                        tests. No new failures. RESULT block present: STATUS DONE.
    still relevant?     All six src files EXIST on master and HAVE DIFFS.
    conflicts / deps    Shares branch with TASK-355 (same SHA). Overlaps with TASK-357 on
                        src/ingest.py. Branch carries work from both tasks plus other recoveries.
    disposition         CANDIDATE — recovery task, tests pass, artifacts were lost and are now
                        recovered. But shares branch with TASK-355 and overlaps with TASK-357 on
                        ingest.py. Integration must separate the recovery cherry-picks from
                        TASK-355's pricing changes.

---

## TASK-339

    task                TASK-339
    branch              qwen-worker-2-r63
    exact SHA           ae54f5182b82377a7916bf0ab32fbd2404c5f926 (origin/qwen-worker-2-r63)
    purpose             The gate against five phrasings cannot catch a paraphrase — add semantic
                        paraphrase detection to sequencegate.
    files changed       4 files: src/sequencegate.py (semantic overlap + concept groups),
                        tests/test_two_paraphrases_of_one_argument_do_not_pass.py (NEW, 21 tests),
                        task file moves.
    tests               21 new tests pass. 19 existing sequence gate tests pass.
                        RESULT block present: STATUS DONE (pending full suite verdict).
    still relevant?     src/sequencegate.py EXISTS on master and HAS DIFF.
    conflicts / deps    None. Focused change to one module.
    disposition         CANDIDATE — clean, focused, tests pass, no overlaps. The semantic detection
                        is additive to the existing lexical check.

---

## TASK-340

    task                TASK-340
    branch              qwen-worker-4-r67
    exact SHA           85b82ddc7ec4f72dc3297c151bb45aa44702a2ae (origin/qwen-worker-4-r67)
    purpose             The two cost levers are unbuilt and the adapters cannot express them —
                        build Anthropic adapter with prompt caching and batch submission.
    files changed       5 files: src/llm.py (cache=False param + complete_batch),
                        src/providers/anthropic.py (NEW, adapter), src/providers/glm.py (cache param),
                        tests/test_the_cohort_preamble_is_paid_for_once.py (NEW, 15 tests),
                        tests/test_invariants.py (POST allowlist update).
    tests               15 new tests pass. 2 pre-existing invariants failures unrelated.
                        RESULT block present: STATUS REVIEW.
    still relevant?     src/llm.py EXISTS, src/providers/glm.py EXISTS — both HAVE DIFFS.
                        src/providers/anthropic.py is GONE from master.
    conflicts / deps    Overlaps with TASK-360 on src/llm.py and src/providers/glm.py.
                        anthropic.py being gone means the adapter was removed from master after
                        this branch diverged.
    disposition         CANDIDATE with concern — has RESULT and tests, but src/providers/anthropic.py
                        is GONE from master (needs rebase or explanation of why it was removed).
                        Overlaps with TASK-360 on llm.py and glm.py; integration order matters.

---

## TASK-342

    task                TASK-342
    branch              qwen-worker-r72
    exact SHA           b32d979028e2095008bd5c1eb0b24d290b26a82f (origin/qwen-worker-r72)
    purpose             The review spreadsheet lost the messages — rebuild the projection from
                        fifty-data.json into xlsx + html with full message bodies.
    files changed       2 files: scripts/export_review_342.py (NEW), task file.
                        (work/ outputs are gitignored and not in the diff.)
    tests               7 acceptance criteria pass. RESULT block present: STATUS DONE.
    still relevant?     scripts/export_review_342.py is GONE from master.
    conflicts / deps    None. Script was standalone.
    disposition         STALE — the script is gone from master. The work/ outputs are gitignored.
                        No landable artifact remains.

---

## TASK-344

    task                TASK-344
    branch              qwen-worker-3-r68
    exact SHA           ffa0d47921784435e2a001eaa00162c7426f07b6 (origin/qwen-worker-3-r68)
    purpose             The consumer audit calls 56 modules disconnected — build an audit script
                        that traces every producer to its production consumer.
    files changed       3 files: scripts/consumer_audit.py (NEW),
                        tests/test_every_producer_has_a_production_consumer.py (NEW, 9 tests),
                        task file.
    tests               9/9 pass. 2 pre-existing invariants failures unrelated.
                        RESULT block present: STATUS REVIEW.
    still relevant?     scripts/consumer_audit.py is GONE from master.
    conflicts / deps    None. Script was standalone.
    disposition         STALE — the script is gone from master. No landable artifact remains.

---

## TASK-345

    task                TASK-345
    branch              qwen-worker-r68
    exact SHA           f95066072e12e6e069040837475d325657ac44d9 (origin/qwen-worker-r68)
    purpose             GLM verifies a finished branch before Claude picks it — build the
                        glm_verify_branch.py script that dry-runs a branch's claims.
    files changed       3 files: scripts/glm_verify_branch.py (NEW, 570 lines),
                        docs/glm-reviews/branch-TASK-323.md (NEW),
                        docs/glm-reviews/branch-TASK-324.md (NEW).
    tests               Dry-run verified against two branches. Live run completed.
                        RESULT block present: STATUS DONE.
    still relevant?     scripts/glm_verify_branch.py EXISTS on master.
    conflicts / deps    None. Tooling script, additive.
    disposition         CANDIDATE — tooling script exists on master, RESULT is clear, caught real
                        defects on two branches. Low risk.

---

## TASK-349

    task                TASK-349
    branch              qwen-worker-6-r68
    exact SHA           c92175e7a15f820f173e1cf466587ba602ec6f03 (origin/qwen-worker-6-r68)
    purpose             Provider sends and replies never reach the ledger — wire inbound event
                        handling to write PROVIDER_SENT and PROVIDER_REPLIED rows.
    files changed       3 files: src/actionledger.py (new states + record_provider_event),
                        src/inbound.py (write-back after events.apply),
                        tests/test_a_send_and_a_reply_both_leave_a_row.py (NEW, 10 tests).
    tests               10/10 pass. 275 inbound/actionledger/reply tests pass, zero regressions.
                        Guard test verified: removing the call makes 6 tests fail.
                        RESULT block present: STATUS REVIEW.
    still relevant?     Both src files EXIST on master and HAVE DIFFS.
    conflicts / deps    None. Focused change, no overlaps with other branches.
    disposition         CANDIDATE — focused code change, tests pass, guard verified, no overlaps.
                        Directly addresses TASK-137's ledger gap.

---

## TASK-350

    task                TASK-350
    branch              qwen-worker-7-r68
    exact SHA           efe70035f21e23c0216c584b55d4d9985d3fd0fc (origin/qwen-worker-7-r68)
    purpose             The watcher does not reconcile — add reconciliation to replywatch.py so
                        drift between local and provider state is reported, not silently assumed.
    files changed       2 files: src/replywatch.py (~350 lines: reconcile_campaigns, drift_summary,
                        --reconcile CLI flag),
                        tests/test_the_watcher_reports_drift_rather_than_assuming_agreement.py
                        (NEW, 15 tests).
    tests               15/15 pass. 26 existing replywatch tests pass.
                        RESULT block present: STATUS DONE.
    still relevant?     src/replywatch.py EXISTS on master and HAS DIFF.
    conflicts / deps    None. Focused change, no overlaps.
    disposition         CANDIDATE — focused, tests pass, no overlaps. Adds real operational value
                        (drift detection between local and provider state).

---

## TASK-352

    task                TASK-352
    branch              qwen-worker-4-r9
    exact SHA           2cb8755afc8ad069ccab24a6d80819d779c57e54 (origin/qwen-worker-4-r9)
    purpose             A spend report that does not add up three units — build a report with
                        labelled cost-per-lead denominators and mixed-unit tripwires.
    files changed       2 files: scripts/spend_report.py (NEW, 335 lines),
                        tests/test_the_spend_report_never_sums_two_units.py (NEW, 7 tests).
                        Plus 22 other task/doc files on the branch.
    tests               7/7 pass. 22 spend ledger tests pass.
                        RESULT block present: STATUS DONE.
    still relevant?     scripts/spend_report.py is GONE from master.
    conflicts / deps    None. Script was standalone.
    disposition         STALE — the script is gone from master. No landable artifact remains.

---

## TASK-353

    task                TASK-353
    branch              qwen-worker-9-r68
    exact SHA           8ff73995d5b74c18fd4e56b5ec470692e4970699 (origin/qwen-worker-9-r68)
    purpose             The docs still say things that are not true — sweep docs for superseded
                        claims and mark them.
    files changed       6 files: docs/DOC-TRUTH-SWEEP-2026-09-26.md (NEW, the sweep report),
                        docs/CLAUDE-HANDOFF.md (SUPERSEDED marker),
                        docs/CONTEXT-RESET-2026-09-14.md (SUPERSEDED marker),
                        docs/CONTEXT-RESET-2026-09-14-B.md (SUPERSEDED marker),
                        docs/CONTEXT-RESET-2026-09-14-C.md (SUPERSEDED marker),
                        docs/CONTEXT-RESET-2026-09-15-D.md (SUPERSEDED marker).
    tests               No tests — docs-only sweep. Verification commands recorded in sweep doc.
                        RESULT block present: STATUS REVIEW.
    still relevant?     All 6 files EXIST on master and HAVE DIFFS.
    conflicts / deps    None. Docs-only, no source changes.
    disposition         CANDIDATE — docs-only, targeted corrections, all files exist on master.
                        Low risk, high value (prevents future workers from reading stale docs).

---

## TASK-355

    task                TASK-355
    branch              qwen-worker-12-r9-sync
    exact SHA           3da4a246ee2536760d04dfc4d1d94b649160c2fa (origin/qwen-worker-12-r9-sync)
    purpose             Cached tokens are priced as if they were fresh — add cache creation and
                        cache read rates to model-prices.yaml and cost calculation.
    files changed       Same branch as TASK-335. TASK-355's own changes:
                        config/model-prices.yaml (cache rates added),
                        src/modelprices.py (cache_rates_for, cost_details),
                        tests/test_a_cached_token_is_not_priced_as_a_fresh_one.py (NEW, 7 tests).
    tests               7/7 pass. All 7 acceptances verified.
                        RESULT block present: STATUS DONE.
    still relevant?     config/model-prices.yaml EXISTS on master. src/modelprices.py EXISTS.
    conflicts / deps    Shares branch with TASK-335 (same SHA). The branch diff carries both
                        tasks' changes plus other recoveries.
    disposition         CANDIDATE — clean, focused, tests pass. But shares branch with TASK-335;
                        integration must separate the pricing changes from the recovery cherry-picks.

---

## TASK-357

    task                TASK-357
    branch              qwen-worker-r69
    exact SHA           a66b6c5bc8a8cdc6f275e45f9702171269021750 (origin/qwen-worker-r69)
    purpose             The client file is person-centric and the queue is not — add a
                        person-centric ingestion mode that groups rows by company.
    files changed       2 files: src/ingest.py (run_person_centric, --person-centric CLI flag),
                        tests/test_a_person_centric_csv_becomes_one_record_per_company.py
                        (NEW, 18 tests).
    tests               18/18 pass. 18 existing ingest tests pass (no regression).
                        RESULT block present: STATUS REVIEW.
    still relevant?     src/ingest.py EXISTS on master and HAS DIFF.
    conflicts / deps    Overlaps with TASK-335 on src/ingest.py (both modify the same file).
    disposition         CANDIDATE — focused, tests pass. But overlaps with TASK-335 on ingest.py;
                        integration must reconcile the two changes to that file.

---

## TASK-358

    task                TASK-358
    branch              qwen-worker-3-r9-task285
    exact SHA           c8a62f4109f47eb5338f1ef334d68f44dcb989ef (origin/qwen-worker-3-r9-task285)
    purpose             CheapVerifier exists on a branch and not in the waterfall — wire the
                        CheapVerifier adapter into the enrichment waterfall with cost tracking.
    files changed       src/bisonfactory.py, src/enrich.py (COSTS + CALL_STAGE),
                        src/providers/cheapverifier.py (cherry-picked), src/waterfall.py (entry added),
                        tests/test_cheapverifier_is_part_of_the_waterfall.py (NEW, 12 tests),
                        10 VCR cassettes, plus other task files.
    tests               12 new tests pass. 59 total waterfall tests pass.
                        RESULT block present: STATUS DONE.
    still relevant?     src/bisonfactory.py EXISTS, src/enrich.py EXISTS, src/waterfall.py EXISTS —
                        all HAVE DIFFS. src/providers/cheapverifier.py is GONE from master.
    conflicts / deps    Overlaps with TASK-319 on src/bisonfactory.py. cheapverifier.py being gone
                        from master means the adapter was removed after this branch diverged.
    disposition         CANDIDATE with concern — has RESULT and tests, but cheapverifier.py is GONE
                        from master (needs rebase or explanation). Overlaps with TASK-319 on
                        bisonfactory.py.

---

## TASK-359

    task                TASK-359
    branch              qwen-worker-r70
    exact SHA           7150fd80935854c4199299bde82f790b83a3dcc6 (origin/qwen-worker-r70)
    purpose             A daily usage and balance report for every provider — build a script that
                        reads provider balances and writes a daily usage markdown.
    files changed       scripts/usage_report.py (NEW), scripts/register_usage_job.ps1 (NEW),
                        tests/test_the_usage_report_never_invents_a_number.py (NEW, 22 tests),
                        docs/usage/2026-09-26.md (NEW).
    tests               22/22 pass. RESULT block present: STATUS DONE.
    still relevant?     scripts/usage_report.py is GONE from master.
    conflicts / deps    None. Script was standalone.
    disposition         STALE — the main script is gone from master. The scheduled task registration
                        and usage docs are also gone. No landable artifact remains.

---

## TASK-360

    task                TASK-360
    branch              qwen-worker-2-r70
    exact SHA           29f90f7bee9153bcbfb2ffafd6f7cc1182d7fd4f (origin/qwen-worker-2-r70)
    purpose             A central model router and no model slug anywhere else — build
                        src/modelrouter.py with config/model_policy.yaml as the single source of
                        model slugs.
    files changed       config/model_policy.yaml (NEW), src/modelrouter.py (NEW),
                        src/llm.py (modified), src/providers/glm.py (modified),
                        src/providers/xai.py (modified),
                        tests/test_no_model_slug_lives_outside_the_policy.py (NEW, 3 tests).
    tests               3/3 pass. Full suite: 137 failures, 9 new (fixture hygiene), 0 fixed.
                        RESULT block present: STATUS REVIEW.
    still relevant?     config/model_policy.yaml is GONE from master. src/modelrouter.py is GONE.
                        src/llm.py EXISTS, src/providers/glm.py EXISTS, src/providers/xai.py EXISTS.
    conflicts / deps    Overlaps with TASK-340 on src/llm.py and src/providers/glm.py.
                        Two key files (modelrouter.py, model_policy.yaml) are GONE from master.
    disposition         STALE — the central artifacts (modelrouter.py, model_policy.yaml) are gone
                        from master. The approach was apparently abandoned or superseded. The
                        remaining changes to llm.py/glm.py/xai.py may conflict with TASK-340.

---

## TASK-367

    task                TASK-367
    branch              qwen-worker-5-r9
    exact SHA           26b988889ebb8f966c00451058fbb4c5d8af315d (origin/qwen-worker-5-r9)
    purpose             A real offers block that owns persona-to-offer — build the offers: block
                        that maps persona to offer with capability angles.
    files changed       27 files: src/claims.py, src/copystages.py, GLM review docs (10 files),
                        task files, tests/task903_a_rung_is_a_question_not_an_assertion.py.
    tests               No RESULT block for TASK-367 on the branch. Task file still in TODO.
    still relevant?     src/claims.py EXISTS and HAS DIFF. src/copystages.py EXISTS and HAS DIFF.
                        But the diffs are not attributable to TASK-367 specifically.
    conflicts / deps    Shares branch with TASK-383 (same SHA). Branch carries GLM verification
                        work and TASK-903 test work.
    disposition         REJECT — no RESULT block for TASK-367. Task file still in TODO on branch.
                        The branch has code changes but no attribution to TASK-367's offer engine
                        work.

---

## TASK-372

    task                TASK-372
    branch              qwen-worker-2-r9
    exact SHA           84268e53233e37441d9b58414eb432d163537e9f (origin/qwen-worker-2-r9)
    purpose             The suite baseline is 73 failures short — measure and document the gap
                        between the named baseline and actual failures.
    files changed       Same 63 files as TASK-318 (same branch, same SHA).
    tests               No RESULT block for TASK-372 on the branch. Task file still in TODO.
    still relevant?     Same as TASK-318. The branch's changes are from other tasks.
    conflicts / deps    Shares branch with TASK-318 (same SHA).
    disposition         REJECT — no RESULT block for TASK-372. Task file still in TODO on branch.
                        The branch has work from other tasks (provider writes, phase2 scenarios).

---

## TASK-383

    task                TASK-383
    branch              qwen-worker-5-r9
    exact SHA           26b988889ebb8f966c00451058fbb4c5d8af315d (origin/qwen-worker-5-r9)
    purpose             GLM CHECKPOINT A — dispatch a fresh GLM checkpoint per the review protocol.
    files changed       Same 27 files as TASK-367 (same branch, same SHA).
    tests               No RESULT block for TASK-383 on the branch. Task file still in TODO.
    still relevant?     Same as TASK-367.
    conflicts / deps    Shares branch with TASK-367 (same SHA).
    disposition         REJECT — no RESULT block for TASK-383. Task file still in TODO on branch.

---

## TASK-385

    task                TASK-385
    branch              glm-review-504-task-387
    exact SHA           515c638e14423a203e56f3ed3525af8569f72c07 (origin/glm-review-504-task-387)
    purpose             Machine-derived status command — build pool_status.py that reports worker
                        pool state (idle reasons, ready tasks, worker details).
    files changed       Same 102 files as TASK-319 (same branch, same SHA).
                        TASK-385's own: scripts/pool_status.py (NEW), tests/test_pool_status.py
                        (NEW, 16 tests).
    tests               16/16 pass. 47 total claim_task tests pass.
                        RESULT block present: STATUS DONE.
    still relevant?     scripts/pool_status.py is GONE from master.
    conflicts / deps    Shares branch with TASK-319 and TASK-387 (same SHA).
    disposition         STALE — the main script (pool_status.py) is gone from master. No landable
                        artifact remains.

---

## TASK-386

    task                TASK-386
    branch              qwen-worker-8-r9
    exact SHA           ad031f130ef3493ba76410ae20307ad7026b0dbc (origin/qwen-worker-8-r9)
    purpose             Ingest the client file's LinkedIn and headcount columns into records and
                        packs.
    files changed       30 files: src/bisonfactory.py, src/campaignstrategy.py,
                        src/generate_campaign.py, src/offers.py, GLM review docs (12 files),
                        task files, tests.
    tests               No RESULT block for TASK-386 on the branch. Task file still in TODO.
    still relevant?     All four src files EXIST on master and HAVE DIFFS. But the diffs are not
                        attributable to TASK-386 specifically (LinkedIn/headcount ingestion).
    conflicts / deps    Overlaps with TASK-319 (bisonfactory, generate_campaign), TASK-328
                        (generate_campaign), TASK-326 (generate_campaign).
    disposition         REJECT — no RESULT block for TASK-386. Task file still in TODO on branch.
                        The branch has src changes but no attribution to LinkedIn/headcount ingestion.

---

## TASK-387

    task                TASK-387
    branch              glm-review-504-task-387
    exact SHA           515c638e14423a203e56f3ed3525af8569f72c07 (origin/glm-review-504-task-387)
    purpose             Ledger write-back of provider sends and replies — investigate whether
                        provider events reach the record event log.
    files changed       Same 102 files as TASK-319 (same branch, same SHA).
                        TASK-387's own: tests/test_task387_writeback_demo.py (NEW, 3 demo tests).
    tests               3 demo tests pass. RESULT block present: STATUS DONE.
    still relevant?     The demo tests prove existing code paths (leadobserve.confirm_email_touches,
                        events.apply) already write to the record. No new production code was added.
    conflicts / deps    Shares branch with TASK-319 and TASK-385 (same SHA).
    disposition         CANDIDATE — the finding is valuable (provider events DO reach the ledger via
                        existing code paths, closing the question). But the branch has 102 files of
                        unrelated changes. Integration would extract only the finding + demo tests,
                        not the branch's other work.

---

## TASK-389

    task                TASK-389
    branch              qwen-worker-7-r9
    exact SHA           f3148ac50327f307fbebca0b261db612236d40a6 (origin/qwen-worker-7-r9)
    purpose             Contact-key guard clean-up — trace whether contact_key validation is
                        consistent across modules.
    files changed       Same 35+ files as TASK-326 (same branch, same SHA).
    tests               No RESULT block for TASK-389 on the branch. Task file still in TODO.
    still relevant?     Same as TASK-326.
    conflicts / deps    Shares branch with TASK-326 (same SHA).
    disposition         REJECT — no RESULT block for TASK-389. Task file still in TODO on branch.

---

## Summary

| Disposition | Count | Tasks |
|-------------|-------|-------|
| CANDIDATE   | 13    | 319, 327, 328, 335, 339, 345, 349, 350, 353, 355, 357, 358, 387 |
| STALE       | 7     | 325, 342, 344, 352, 359, 360, 385 |
| REJECT      | 8     | 318, 326, 367, 372, 383, 386, 389 + 340* |

*TASK-340 is CANDIDATE with concern (anthropic.py gone, overlaps with TASK-360).

### Conflict clusters for integration planning

1. **src/generate_campaign.py** — touched by TASK-326 (REJECT), TASK-328, TASK-386 (REJECT),
   TASK-319. Only TASK-328 and TASK-319 are CANDIDATEs; integrate in known order.
2. **src/llm.py + src/providers/glm.py** — touched by TASK-340 and TASK-360 (STALE).
   Only TASK-340 is CANDIDATE; no conflict.
3. **src/bisonfactory.py** — touched by TASK-358 and TASK-319. Both CANDIDATE.
4. **src/ingest.py** — touched by TASK-335 and TASK-357. Both CANDIDATE.
5. **Shared branches** — TASK-335+TASK-355 (same SHA), TASK-319+TASK-385(STALE)+TASK-387
   (same SHA). Extract only the relevant files per task.

### REJECT reasons

All 7 REJECTs share the same defect: the task file is still in TODO on the branch with no RESULT
block. The branch has accumulated work from other tasks, but the named task was not completed or
its result was not recorded.
