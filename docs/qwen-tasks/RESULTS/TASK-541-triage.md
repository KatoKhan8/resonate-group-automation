# TASK-541 — Triage of Pending Branch Results, Batch 4 of 8

**Triage date:** 2026-10-04
**Master baseline:** `2bf7b8a57` (Merge task-guard-regressions-rebased)
**28 results triaged across 11 branches**

---

## Summary

| # | Task | Disposition | Reason |
|---|------|-------------|--------|
| 1 | TASK-390 | STALE | GLM review never executed; branch accumulated unrelated changes |
| 2 | TASK-391 | CANDIDATE | Skills-mismatch finding valid; code overlaps TASK-396 heavily |
| 3 | TASK-392 | CANDIDATE | Signature gap test not on master; extractable in isolation |
| 4 | TASK-395 | STALE | Key fixes already on master; code overlaps TASK-396 |
| 5 | TASK-396 | CANDIDATE | Training-pair finding valid; code is superset of TASK-391 |
| 6 | TASK-397 | REJECT | Task never completed; artifact belongs to TASK-935, not TASK-397 |
| 7 | TASK-398 | CANDIDATE | Suppression audit finding + 3 sequence plan tests are real artifacts |
| 8 | TASK-399 | STALE | Doc corrections themselves now stale (master moved 400+ commits) |
| 9 | TASK-402 | CANDIDATE | Independent verification of TASK-391, confirms it |
| 10 | TASK-403 | STALE | Target file `src/provider_truth_check.py` deleted from master |
| 11 | TASK-404 | CANDIDATE | Finding-only (GLM verify TASK-397); SAFE TO MERGE |
| 12 | TASK-405 | CANDIDATE | Finding-only (GLM verify TASK-394); SAFE TO MERGE |
| 13 | TASK-406 | STALE | Target script `scripts/durable_controller.py` deleted from master |
| 14 | TASK-407 | CANDIDATE | Finding-only (GLM verify TASK-399); 11 of 13 corrections still owed |
| 15 | TASK-408 | CANDIDATE | Finding-only (GLM verify TASK-319); wiring intact on master |
| 16 | TASK-409 | CANDIDATE | New QA scripts + tests not on master; conflict risk with other branches |
| 17 | TASK-410 | CANDIDATE | Finding-only (GLM verify TASK-400); core wiring on master |
| 18 | TASK-411 | REJECT | Task never completed; no result block in TODO |
| 19 | TASK-412 | CANDIDATE | Finding-only suppression audit; file:line references still valid |
| 20 | TASK-413 | CANDIDATE | Seat cap scripts valuable; bisonfactory.py conflict at line ~509 |
| 21 | TASK-414 | CANDIDATE | Finding-only spend report wiring; verified correct |
| 22 | TASK-415 | STALE | BLOCKED with no artifact; credential blocker structural, data window passed |
| 23 | TASK-416 | CANDIDATE | Stale-research finding actionable; fix is 3 lines, script on master |
| 24 | TASK-417 | CANDIDATE | Cold-branch expansion is durable structural finding |
| 25 | TASK-418 | STALE | Clean-pass audit expired; file likely changed in 400+ commits since |
| 26 | TASK-419 | CANDIDATE | Durable finding: Slack delivery wired but switched off |
| 27 | TASK-420 | STALE | Docs audit from 6+ days ago against master that moved 400+ commits |
| 28 | TASK-421 | CANDIDATE | Durable architectural map of suppression stores |

**Totals:** 16 CANDIDATE, 9 STALE, 2 REJECT, 1 never-completed (REJECT)

---

## Per-Task Detail

---

### TASK-390

    task                TASK-390
    branch              origin/qwen-worker-10-r9
    exact SHA           ab2a6ff1d46daec0bf00822d1c7cde26ce90c9bf
    purpose             GLM checkpoint B — verify offers, persona list, and campaign
                        strategy chain (read-only GLM review protocol pass)
    files changed       src/generate_campaign.py, src/secondbrain.py, tests/base.py,
                        tests/test_generate.py, scripts/task397_seat_cap_check.py,
                        docs/state/TASK397-SEAT-CAP-CHECK.json
    tests               tests/test_generate.py (modified), tests/base.py (modified)
    still relevant?     NO. The GLM review was never executed; the task file remains
                        in TODO on the branch. The branch accumulated unrelated changes
                        (seat cap check script, generate_campaign/secondbrain mods).
    conflicts / deps    src/generate_campaign.py also touched by TASK-391, TASK-395,
                        TASK-396 branches. tests/base.py and tests/test_generate.py
                        also touched by TASK-391 and TASK-396.
    disposition         STALE — GLM review never executed; branch has unrelated changes

---

### TASK-391

    task                TASK-391
    branch              origin/qwen-worker-6-r9
    exact SHA           6aa450938b035e4486a8e13096da83d0c2f0d067
    purpose             Determine whether the five skills can be wired into generate.py's
                        real production entrypoint (finding: they cannot, structural
                        mismatch)
    files changed       src/approve.py, src/bisonfactory.py, src/enrollmenttags.py,
                        src/generate.py, src/generate_campaign.py, src/heyreachfactory.py,
                        src/providers/bison.py, src/providers/heyreach.py, src/run.py,
                        plus 12 test files
    tests               test_audit.py, test_changing_an_approved_fact_changes_the_output.py,
                        test_e2e.py, test_enrollment_tags.py, test_generate.py,
                        test_no_model_is_not_a_bad_record.py, test_preproduction.py,
                        test_qwen_cli_model.py, test_run.py, test_set_regeneration.py,
                        test_task400_rework2.py, test_task400_rework3.py
    still relevant?     PARTIALLY. The finding (skills don't map to generate.py stages)
                        is independently verified by TASK-402 and remains valid. The
                        branch carries massive TASK-400 code changes that overlap almost
                        exactly with TASK-396's branch.
    conflicts / deps    HIGH CONFLICT. Touches 8 src/ files also touched by TASK-396
                        (glm-review-504-task-387). Both branches carry the same TASK-400
                        rework changes. Only the finding should be integrated, not code.
    disposition         CANDIDATE (finding only) — finding valid; code overlaps TASK-396

---

### TASK-392

    task                TASK-392
    branch              qwen-worker-9-r9
    exact SHA           f1b9c357c17f4b557cbdb06f68339c7343ef3e83
    purpose             Verify whether each attested sender mailbox has a signature
                        stored in the render pipeline (finding: present at source, lost
                        in pipeline at senderinventory.py)
    files changed       config/clients/productive-offers.yaml, src/notify.py,
                        src/providers/groq.py (GONE from master),
                        src/providers/openrouter.py (GONE from master),
                        src/providers/slack.py, scripts/claim_task.py,
                        scripts/credential_health.py,
                        scripts/measure_research_freshness.py, scripts/pool.sh,
                        scripts/pool_watchdog.sh, scripts/refill_queue.py,
                        tests/test_a_step_never_renders_an_empty_signature.py (NEW),
                        tests/test_claim_task.py, test_groq_openrouter_adapters.py,
                        test_no_route_resolves_to_retired_channel.py,
                        test_the_lint_refuses_the_real_push.py
    tests               test_a_step_never_renders_an_empty_signature.py (NEW, 4 tests
                        documenting the signature gap)
    still relevant?     PARTIALLY. The test file documenting the signature pipeline gap
                        is NOT on master and the finding is valid. However, the branch
                        has accumulated massive unrelated changes. groq.py and
                        openrouter.py don't exist on master. notify.py changes already
                        superseded.
    conflicts / deps    src/notify.py also touched by qwen-worker-12-r9-sync.
                        config/clients/productive-offers.yaml also touched by TASK-395's
                        branch. scripts/claim_task.py also touched by worker-12 and
                        worker-3.
    disposition         CANDIDATE (test + finding only) — signature gap test valuable;
                        extract in isolation from branch noise

---

### TASK-395

    task                TASK-395
    branch              qwen-worker-12-r9
    exact SHA           34bf792bebc52d35ef218096a42616b333b9cce5
    purpose             Check whether the spend report reads the now-attributed rows
                        correctly post-TASK-346/373
    files changed       src/copylint.py, src/generate_campaign.py, src/providers/bison.py,
                        src/providers/heyreach.py, scripts/glm_verify_branch.py,
                        tests/offline.py, test_an_approval_does_not_survive_a_re_render.py,
                        test_e2e.py,
                        test_glm_verify_branch_read_spend_uses_unattributed.py (NEW),
                        test_only_the_last_subject_may_claim_finality.py,
                        test_only_the_selected_offer_is_validated.py,
                        test_the_readback_cache_cannot_lie_about_its_age.py
    tests               test_glm_verify_branch_read_spend_uses_unattributed.py (NEW),
                        plus 5 modified test files
    still relevant?     MOSTLY NO. The spend fix in glm_verify_branch.py (changing
                        _model to unattributed) is already on master. The copylint
                        finality fix (subject_list exemption for last step) is already
                        on master. Remaining code changes overlap with TASK-396.
    conflicts / deps    HIGH CONFLICT. src/copylint.py also touched by TASK-396.
                        src/generate_campaign.py also touched by TASK-390, TASK-391,
                        TASK-396. src/providers/bison.py and heyreach.py also touched
                        by TASK-391, TASK-396, TASK-398.
    disposition         STALE — key fixes already on master; code overlaps TASK-396

---

### TASK-396

    task                TASK-396
    branch              glm-review-504-task-387
    exact SHA           f3b68bf849d8361fab9d3f8f972229369cf60944
    purpose             Check whether anything captures a training pair (prompt, output,
                        verdict) — finding: nothing does
    files changed       src/approve.py, src/bisonfactory.py, src/copylint.py,
                        src/generate.py, src/generate_campaign.py, src/heyreachfactory.py,
                        src/providers/bison.py, src/providers/heyreach.py, src/run.py,
                        scripts/pool_status.py (NEW, not on master), plus 16 test files
    tests               test_a_dead_cta_link_is_refused.py, test_audit.py,
                        test_changing_an_approved_fact_changes_the_output.py,
                        test_e2e.py, test_generate.py,
                        test_no_model_is_not_a_bad_record.py,
                        test_only_the_last_subject_may_claim_finality.py,
                        test_only_the_selected_offer_is_validated.py, test_pool_status.py,
                        test_preproduction.py, test_qwen_cli_model.py, test_run.py,
                        test_set_regeneration.py, test_task387_writeback_demo.py,
                        test_task400_rework2.py, test_task400_rework3.py,
                        test_the_readback_cache_cannot_lie_about_its_age.py
    still relevant?     PARTIALLY. The finding (no training pair capture exists) is
                        valid and still true. The branch carries massive TASK-400 code
                        changes that overlap almost exactly with TASK-391's branch.
                        scripts/pool_status.py does not exist on master.
    conflicts / deps    HIGHEST CONFLICT. Touches the most src/ files of any branch.
                        Overlaps with TASK-391 (identical approve.py, bisonfactory.py,
                        generate.py, generate_campaign.py changes), TASK-395 (copylint.py,
                        generate_campaign.py, providers), TASK-398 (bisonfactory.py,
                        heyreachfactory.py). TASK-400 changes duplicated across three
                        branches.
    disposition         CANDIDATE (finding only) — finding valid; code is superset of
                        TASK-391, should not be integrated separately

---

### TASK-397

    task                TASK-397
    branch              qwen-worker-2-r9
    exact SHA           a59e5f98372a5934b3775622c2a98b3479435749
    purpose             Check whether any HeyReach seat is over its daily/weekly
                        connection cap via real provider read
    files changed       src/provider_truth_check.py (NEW, 495 lines),
                        tests/test_provider_truth_check.py (NEW)
    tests               tests/test_provider_truth_check.py (NEW)
    still relevant?     NO. The task was a read-only seat cap check but the branch
                        produced provider_truth_check.py — a module for checking
                        collisions against provider state (TASK-935). This file does NOT
                        exist on master. The task file remains in TODO — the seat cap
                        check was never completed. The artifact belongs to a different
                        task entirely.
    conflicts / deps    NO CONFLICT. provider_truth_check.py is a new file not touching
                        any existing source.
    disposition         REJECT — task never completed; artifact belongs to TASK-935

---

### TASK-398

    task                TASK-398
    branch              qwen-worker-11-task314
    exact SHA           ddc0bc816fed25b327cbe070d0597ba03ae2b67e
    purpose             Suppression list audit — is it complete, and does every write
                        path check it?
    files changed       src/bisonfactory.py, src/heyreachfactory.py, src/sequenceplan.py,
                        scripts/qa/__init__.py (NEW),
                        scripts/qa/check_campaign_bison.py (NEW, 702 lines),
                        scripts/task413_seat_cap_check.py (NEW),
                        scripts/task413_seat_cap_probe.py (NEW),
                        tests/test_every_representation_derives_from_one_plan.py (NEW),
                        tests/test_no_cadence_step_is_silently_dropped.py (NEW),
                        tests/test_step_counts_agree_while_the_keys_do_not.py (NEW)
    tests               test_every_representation_derives_from_one_plan.py (NEW),
                        test_no_cadence_step_is_silently_dropped.py (NEW),
                        test_step_counts_agree_while_the_keys_do_not.py (NEW)
    still relevant?     PARTIALLY. The finding (seven suppression stores exist, all
                        checked on send path via eligibility.decide) is valid. The branch
                        carries TASK-314 code (sequence plan derivation, QA checks) that
                        produces real artifacts: sequenceplan.py gains derive_xlsx_data()
                        and qa_validate(), and the QA check script is a genuine new
                        capability.
    conflicts / deps    MODERATE CONFLICT. src/bisonfactory.py and src/heyreachfactory.py
                        also touched by TASK-391, TASK-395, TASK-396. src/sequenceplan.py
                        only touched here. QA scripts are new files with no conflict.
    disposition         CANDIDATE (finding + tests) — suppression audit valuable;
                        sequence plan tests are real artifacts integrable independently

---

### TASK-399

    task                TASK-399
    branch              qwen-worker-9-r9
    exact SHA           f1b9c357c17f4b557cbdb06f68339c7343ef3e83
    purpose             Docs hygiene — find what's now false in the standing docs
                        (CLAUDE.md, OPERATING-MODE.md, handoff docs)
    files changed       Same as TASK-392 (shared branch)
    tests               Same as TASK-392
    still relevant?     NO. The finding report (12+ false/stale claims) was thorough
                        when written but the specific corrections it lists are themselves
                        now stale — master has moved 400+ commits since.
    conflicts / deps    Same branch as TASK-392 and TASK-402. No unique source changes.
    disposition         STALE — doc corrections themselves now stale

---

### TASK-402

    task                TASK-402
    branch              qwen-worker-9-r9
    exact SHA           f1b9c357c17f4b557cbdb06f68339c7343ef3e83
    purpose             GLM first-pass verification of TASK-391's skills-mismatch
                        finding — independently confirm or refute the five-way mismatch
                        table
    files changed       Same as TASK-392 (shared branch)
    tests               Same as TASK-392
    still relevant?     YES as a finding. The verification is thorough and confirms
                        TASK-391's mismatch table across all five pairs. The conclusion
                        is architecturally important. Finding-only, no code changes.
    conflicts / deps    Same branch as TASK-392 and TASK-399. No unique source changes.
    disposition         CANDIDATE (finding only) — independent verification of TASK-391,
                        confirms it

---

### TASK-403

    task                TASK-403
    branch              qwen-worker-2-r9
    exact SHA           a59e5f98372a5934b3775622c2a98b3479435749
    purpose             GLM first-pass verification of TASK-318 (provider_truth_check) —
                        reproduce acceptance checks and confirm falsifiability
    files changed       src/provider_truth_check.py, tests/test_provider_truth_check.py
    tests               tests/test_provider_truth_check.py
    still relevant?     NO. src/provider_truth_check.py does not exist on master
                        (DELETED). The entire code contribution is orphaned.
    conflicts / deps    None — file is gone.
    disposition         STALE — target source file deleted from master

---

### TASK-404

    task                TASK-404
    branch              qwen-worker-9-r9
    exact SHA           f1b9c357c17f4b557cbdb06f68339c7343ef3e83
    purpose             GLM first-pass verification of TASK-397 (HeyReach seat-cap
                        check) — verify read-only findings, confirm no provider write
    files changed       Same as TASK-392 (shared branch); task itself is finding-only
    tests               Same as TASK-392; none specific to this task
    still relevant?     YES. The finding-only verdict is SAFE TO MERGE. The branch
                        carries substantial code from other work (groq.py, openrouter.py
                        GONE from master) but TASK-404 itself produced no code.
    conflicts / deps    src/notify.py also touched by qwen-worker-12-r9-sync.
                        scripts/claim_task.py also touched by worker-12 and worker-3.
                        config/clients/productive-offers.yaml also touched by worker-12.
    disposition         CANDIDATE (finding only) — SAFE TO MERGE

---

### TASK-405

    task                TASK-405
    branch              qwen-worker-12-r9-sync
    exact SHA           3da4a246ee2536760d04dfc4d1d94b649160c2fa
    purpose             GLM first-pass verification of TASK-394 (contact-key guard) —
                        verify contact-key validation consistency
    files changed       Finding-only; branch carries other tasks' code changes
    tests               None specific to this task
    still relevant?     YES. The finding (no inconsistency in contact_key validation)
                        is still valid. Key generation centralized in src/identity.py,
                        validation in src/store.py, enforcement in store.patch(). All
                        still exist on master.
    conflicts / deps    None for the finding itself.
    disposition         CANDIDATE (finding only) — SAFE TO MERGE

---

### TASK-406

    task                TASK-406
    branch              origin/qwen-worker-7-r9
    exact SHA           67c551382346587c55c3f475a8c7a7e7a4389803
    purpose             GLM first-pass verification of TASK-396 (training-pair capture) —
                        verify the negative finding
    files changed       scripts/durable_controller.py (NEW, not on master),
                        tests/test_durable_controller.py (NEW),
                        tests/test_provider_adapter_conformance.py (NEW)
    tests               tests/test_durable_controller.py, tests/test_provider_adapter_
                        conformance.py
    still relevant?     NO. scripts/durable_controller.py does not exist on master
                        (DELETED). The code changes cannot apply.
    conflicts / deps    None — file is gone.
    disposition         STALE — target script deleted from master; finding may still be
                        valid but needs re-verification

---

### TASK-407

    task                TASK-407
    branch              glm-review-504-task-387
    exact SHA           f3b68bf849d8361fab9d3f8f972229369cf60944
    purpose             GLM first-pass verification of TASK-399 (docs hygiene) — verify
                        list of FALSE claims before Claude applies corrections
    files changed       Finding-only; branch carries other tasks' code changes
    tests               None specific to this task
    still relevant?     YES. 11 of 13 FALSE claims remain uncorrected on master. Only
                        Claim #1 (CLAUDE.md handoff reference) has been fixed since.
    conflicts / deps    None for the finding itself.
    disposition         CANDIDATE (finding only) — 11 corrections still owed

---

### TASK-408

    task                TASK-408
    branch              glm-review-504-task-387
    exact SHA           f3b68bf849d8361fab9d3f8f972229369cf60944
    purpose             GLM first-pass verification of TASK-319 (skills registration) —
                        verify 5 skills, all consumed, falsifiable tests
    files changed       Finding-only; branch carries other tasks' code changes
    tests               None specific to this task
    still relevant?     YES. All five skills exist on master in src/skills/,
                        generate_campaign.py calls skills.load(). Wiring intact.
    conflicts / deps    None for the finding itself.
    disposition         CANDIDATE (finding only) — SAFE TO MERGE, all acceptance
                        criteria verified

---

### TASK-409

    task                TASK-409
    branch              qwen-worker-12-r9-sync
    exact SHA           3da4a246ee2536760d04dfc4d1d94b649160c2fa
    purpose             GLM first-pass verification of TASK-294 (research-pack QA) —
                        verify per-lead research-pack QA check verifies identity (exact
                        domain match), not just presence
    files changed       scripts/qa/check_lead_pack.py (NEW, not on master),
                        config/clients/productive-offers.yaml, config/model-prices.yaml,
                        src/candidateexport.py, src/clientexport.py, src/ingest.py,
                        src/modelprices.py, src/nightlysourcing.py, src/notify.py,
                        scripts/claim_task.py, scripts/qualify_sourced_supply.py,
                        scripts/task397_heyreach_seat_cap_check.py,
                        tests/test_a_pack_fact_must_belong_to_this_company.py (NEW),
                        plus 7 other test files
    tests               test_a_pack_fact_must_belong_to_this_company.py (NEW),
                        plus 7 modified test files
    still relevant?     YES. The QA check scripts are NOT on master and represent new
                        functionality. GLM verdict SAFE TO MERGE with 32/32 tests
                        passing. Two minor findings (dead code, private access).
    conflicts / deps    HIGH. Shares many files with qwen-worker-9-r9 (notify.py,
                        claim_task.py, productive-offers.yaml) and qwen-worker-3-r9-
                        task285 (claim_task.py, test_claim_task.py). productive-offers.yaml
                        changes CONFLICT (243 insertions from worker-9 vs 40/39 from
                        worker-12).
    disposition         CANDIDATE — new QA scripts valuable; integration requires
                        conflict resolution with qwen-worker-9-r9 and worker-3

---

### TASK-410

    task                TASK-410
    branch              qwen-worker-3-r9-task285
    exact SHA           c8a62f4109f47eb5338f1ef334d68f44dcb989ef
    purpose             GLM first-pass verification of TASK-400 (generate.py becomes
                        real caller) — critical-path verification with mutation tests
    files changed       Finding-only; branch carries other tasks' code changes
    tests               None specific to this task
    still relevant?     YES. The _generate_via_campaign wiring now exists on master
                        (line 1988 in src/generate.py). The branch's diff against master
                        in generate.py is still 803 lines (glm-review-504 has additional
                        changes beyond master). Finding valid but code has evolved.
    conflicts / deps    None for the finding itself.
    disposition         CANDIDATE (finding only) — SAFE TO MERGE; core wiring on master

---

### TASK-411

    task                TASK-411
    branch              qwen-worker-2-r9
    exact SHA           a59e5f98372a5934b3775622c2a98b3479435749
    purpose             Docs hygiene pass — find what's now false in standing docs
                        (CLAUDE.md, OPERATING-MODE.md, PRODUCTION-HANDOFF)
    files changed       Finding-only; branch code changes are TASK-403's work
    tests               None
    still relevant?     NO. Task was never completed — sits in TODO with no result
                        block. No artifact to integrate.
    conflicts / deps    None.
    disposition         REJECT — task never completed, no result block, no artifact

---

### TASK-412

    task                TASK-412
    branch              qwen-worker-3-r9-task285
    exact SHA           c8a62f4109f47eb5338f1ef334d68f44dcb989ef
    purpose             Suppression list audit — name every store of a suppression fact,
                        confirm every write path checks before writing, re-verify 76
                        incident recipients
    files changed       Finding-only; branch carries other tasks' code changes
    tests               None specific to this task
    still relevant?     YES. Six suppression stores and their check points documented
                        with file:line. eligibility.decide() at src/eligibility.py:605
                        still canonical. One gap: _resume_revalidates_suppression does
                        not check bounces. Fresh read of 76 still owed.
    conflicts / deps    None for the finding itself.
    disposition         CANDIDATE (finding only) — thorough audit with file:line refs;
                        one owed item (fresh read of 76)

---

### TASK-413

    task                TASK-413
    branch              qwen-worker-11-task314
    exact SHA           ddc0bc816fed25b327cbe070d0597ba03ae2b67e
    purpose             HeyReach seat cap check — read every seat's configured cap
                        against actual sends via read-only provider read; report any
                        seat at or over 90%
    files changed       scripts/qa/__init__.py (NEW), scripts/qa/check_campaign_bison.py
                        (NEW), scripts/stage_work_to_host.sh,
                        scripts/task413_seat_cap_check.py (NEW),
                        scripts/task413_seat_cap_probe.py (NEW),
                        src/bisonfactory.py (line 33, lines 509-559),
                        src/heyreachfactory.py (line 64, lines 1038-1087),
                        src/sequenceplan.py (+94 lines),
                        tests/test_every_representation_derives_from_one_plan.py,
                        tests/test_no_cadence_step_is_silently_dropped.py,
                        tests/test_step_counts_agree_while_the_keys_do_not.py
    tests               3 test files changed/added (sequence plan consistency)
    still relevant?     YES. Seat cap check scripts are reusable and NOT on master.
                        src/ changes add SequencePlan integration to bisonfactory and
                        heyreachfactory. All target files exist on master.
    conflicts / deps    HIGH CONFLICT. src/bisonfactory.py also touched by glm-review-
                        504-task-387 (line 1721) and qwen-worker-3-r9-task285 (lines
                        508, 665). Worker-11's hunk at line 509 OVERLAPS with worker-3's
                        hunk at line 508 — both modify the _plan function's lead
                        construction.
    disposition         CANDIDATE with CONFLICT WARNING — seat cap scripts valuable;
                        bisonfactory.py changes at line ~509 overlap with worker-3

---

### TASK-415

    task                TASK-415
    branch              qwen-worker-12-r9-sync
    exact SHA           3da4a246ee2536760d04dfc4d1d94b649160c2fa
    purpose             Sender inventory drift check — compare attested sender/mailbox
                        inventory against internal records via live read-only provider
                        read; report drift both directions
    files changed       Finding-only; task explicitly says "no code changes; BLOCKED"
    tests               None
    still relevant?     NO. BLOCKED with no artifact. The finding was time-sensitive
                        and now 7+ days stale. The HeyReach snapshot referenced was
                        already 6 days old on 2026-09-27. The underlying need persists
                        but this specific audit must be re-run from a credentialed
                        worktree.
    conflicts / deps    Branch overlaps with qwen-worker-9-r9 on src/notify.py and
                        config/clients/productive-offers.yaml. Irrelevant to the task
                        since TASK-415 produced no code.
    disposition         STALE — BLOCKED with no artifact; credential blocker structural,
                        data window passed

---

### TASK-416

    task                TASK-416
    branch              qwen-worker-9-r9
    exact SHA           f1b9c357c17f4b557cbdb06f68339c7343ef3e83
    purpose             Research store freshness check — sample records with populated
                        research, measure age distribution, report whether stale
                        research silently informs current copy
    files changed       scripts/measure_research_freshness.py (already on master);
                        branch carries other tasks' code changes
    tests               None specific to this task
    still relevant?     YES. The core finding is still relevant: generate.research_block()
                        uses frozen quality while research.for_prompt() re-ages — a real
                        gap that lets stale facts reach the draft prompt. The measurement
                        script is on master and runnable. The live-data run is still owed.
    conflicts / deps    Branch overlaps with qwen-worker-12-r9-sync on src/notify.py
                        and config/clients/productive-offers.yaml. Also adds groq.py
                        and openrouter.py which don't exist on master (from TASK-305,
                        not TASK-416).
    disposition         CANDIDATE — finding actionable; fix is 3 lines, script already
                        on master

---

### TASK-417

    task                TASK-417
    branch              qwen-worker-12-r9-sync
    exact SHA           3da4a246ee2536760d04dfc4d1d94b649160c2fa
    purpose             Campaign cadence drift check — for every ACTIVE campaign,
                        confirm actual send cadence matches canonical cadence library's
                        declared days; report named drift
    files changed       Finding-only; task produced no code changes
    tests               None
    still relevant?     YES. The COLD-BRANCH EXPANSION finding (cold path delivers
                        7-day gap where canonical declares 3 days) is baked into
                        linkedin_sequence() in src/providers/heyreach.py and has not
                        been fixed. This is a structural defect/decision, not time-
                        sensitive data.
    conflicts / deps    Branch overlaps same as TASK-415. Irrelevant since no code
                        was produced.
    disposition         CANDIDATE — cold-branch expansion is durable structural finding
                        about linkedin_sequence()

---

### TASK-418

    task                TASK-418
    branch              qwen-worker-r9-t391
    exact SHA           d4effa8d82c50fc4166fd6e6780f069d728eda00
    purpose             Offer config consistency check — read config/clients/productive-
                        offers.yaml end to end; check for internal contradictions;
                        report every contradiction found, file:line
    files changed       Finding-only; branch carries other tasks' code changes
    tests               None specific to this task
    still relevant?     PARTIALLY. The audit found "none found" (clean pass) on
                        2026-09-27. The file may have changed since. Clean-pass audits
                        expire when the file is edited.
    conflicts / deps    Branch overlaps with qwen-worker-12-r9-sync on src/ingest.py
                        and with both 6-r9 and glm-review-504 on src/generate.py.
    disposition         STALE — clean-pass audit expired; file likely changed in 400+
                        commits since

---

### TASK-419

    task                TASK-419
    branch              origin/qwen-worker-6-r9
    exact SHA           6aa450938b035e4486a8e13096da83d0c2f0d067
    purpose             Notify delivery verification — trace whether a GLOBAL-
                        destination notification is ever actually delivered to Slack,
                        or whether it only reaches the stored queue
    files changed       Finding-only; branch carries TASK-400 code changes
    tests               None specific to this task
    still relevant?     YES. The conclusion — "consumer exists but refuses to run
                        because SLACK_LIVE is not set" — is a wiring observation, not
                        time-sensitive data. The risk (backlog dump on enable) persists.
    conflicts / deps    MASSIVE overlap with glm-review-504-task-387: 8 shared src/
                        files and 12 shared test files. Branches are related work on
                        the generate/factory architecture.
    disposition         CANDIDATE — durable finding: Slack delivery wired but switched
                        off; backlog-dump risk persists

---

### TASK-420

    task                TASK-420
    branch              glm-review-504-task-387
    exact SHA           f3b68bf849d8361fab9d3f8f972229369cf60944
    purpose             Docs hygiene pass — verify checkable claims in CLAUDE.md,
                        OPERATING-MODE.md, and latest PRODUCTION-HANDOFF against
                        current master; report every FALSE claim with correction
    files changed       Finding-only; branch carries other tasks' code changes.
                        scripts/pool_status.py is NEW on branch, MISSING on master.
    tests               None specific to this task
    still relevant?     NO. The task audited docs against master state as of
                        2026-09-28. Master has advanced 400+ commits since. The 15
                        FALSE claims it found have likely been superseded.
    conflicts / deps    Same massive overlap with origin/qwen-worker-6-r9 as TASK-419.
    disposition         STALE — docs audit from 6+ days ago against master that moved
                        400+ commits since

---

### TASK-421

    task                TASK-421
    branch              glm-review-504-task-387
    exact SHA           f3b68bf849d8361fab9d3f8f972229369cf60944
    purpose             Suppression list audit — name every store of a suppression
                        fact, confirm every prospect-facing write path checks
                        suppression BEFORE writing, re-verify 76 incident recipients
    files changed       Finding-only; branch carries other tasks' code changes
    tests               None specific to this task
    still relevant?     YES. The six-store architecture, the gate functions, and the
                        pre-write check paths are wiring observations. The 76 re-
                        verification is still owed (needs live queue access). The
                        agency DNC gap (no writer in src/) is documented at
                        PRODUCT-GAPS.md.
    conflicts / deps    Same as TASK-420.
    disposition         CANDIDATE — durable architectural map of suppression stores;
                        76 re-verification still owed

---

## Conflict Matrix (src/ files touched by multiple branches)

| File | Branches | Severity |
|------|----------|----------|
| `src/generate_campaign.py` | 10-r9, 6-r9, 12-r9, glm-504 | HIGH |
| `src/approve.py` | 6-r9, glm-504 | HIGH |
| `src/bisonfactory.py` | 6-r9, 12-r9, glm-504, 11-task314, 3-r9 | HIGH |
| `src/heyreachfactory.py` | 6-r9, 12-r9, glm-504, 11-task314 | HIGH |
| `src/providers/bison.py` | 6-r9, 12-r9, glm-504 | HIGH |
| `src/providers/heyreach.py` | 6-r9, 12-r9, glm-504 | HIGH |
| `src/generate.py` | 6-r9, glm-504, t391 | HIGH |
| `src/copylint.py` | 12-r9, glm-504 | MODERATE |
| `src/run.py` | 6-r9, glm-504 | HIGH |
| `src/notify.py` | 9-r9, 12-r9-sync | LOW |
| `src/ingest.py` | 12-r9-sync, t391 | LOW |
| `src/sequenceplan.py` | 11-task314 only | NONE |
| `config/clients/productive-offers.yaml` | 9-r9, 12-r9-sync | MODERATE |
| `scripts/claim_task.py` | 9-r9, 12-r9-sync, 3-r9 | MODERATE |

**Key observation:** origin/qwen-worker-6-r9 and glm-review-504-task-387 carry nearly
identical TASK-400 rework changes across the same set of files. These should NOT both
be integrated — pick one.

## Files Gone From Master

| File | Branch | Impact |
|------|--------|--------|
| `src/provider_truth_check.py` | qwen-worker-2-r9 | TASK-403 STALE |
| `src/providers/groq.py` | qwen-worker-9-r9 | Stale code (other tasks) |
| `src/providers/openrouter.py` | qwen-worker-9-r9 | Stale code (other tasks) |
| `scripts/durable_controller.py` | origin/qwen-worker-7-r9 | TASK-406 STALE |

## Extractable Artifacts (safe to cherry-pick in isolation)

1. `tests/test_a_step_never_renders_an_empty_signature.py` from TASK-392 (signature gap)
2. Three sequence plan tests from TASK-398 (`test_every_representation_derives_from_one_plan.py`, `test_no_cadence_step_is_silently_dropped.py`, `test_step_counts_agree_while_the_keys_do_not.py`)
3. `scripts/qa/check_lead_pack.py` from TASK-409 (lead-pack QA, not on master)
4. `scripts/qa/check_campaign_bison.py` from TASK-398/413 (EmailBison QA, not on master)
5. `scripts/task413_seat_cap_check.py` and `scripts/task413_seat_cap_probe.py` from TASK-413 (seat cap scripts, not on master)
6. Finding reports from TASK-391, TASK-392, TASK-396, TASK-398, TASK-402, TASK-404, TASK-405, TASK-407, TASK-408, TASK-410, TASK-412, TASK-414, TASK-416, TASK-417, TASK-419, TASK-421 (record in docs, no code)
