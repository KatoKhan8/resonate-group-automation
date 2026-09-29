# TASK-539 — Triage report, batch 2 of 8

**Triage only. No integration, no merge, no cherry-pick.**
Operator decision 2026-09-28: Claude decides integration.

---

## TASK-281

    task                TASK-281
    branch              qwen-worker-2-r9
    exact SHA           f03c74fc01a40df45419742e122268d11c8395a1
    purpose             UK/EU re-engagement age must come from the provider, not a cached value
    files changed       src/bisonfactory.py, src/heyreachfactory.py, src/notify.py,
                        src/secondbrain.py, src/sequenceplan.py, config/clients/productive-offers.yaml,
                        scripts/ (bison_watch_loop.py, claim_task.py, pool.sh, pool_watchdog.sh,
                        qa/, reengagement_provider_read.py, refill_queue.py, run_suite.py,
                        stage_work_to_host.sh, task372_*, task397_*),
                        tests/test_reengagement_age_is_read_not_cached.py,
                        tests/test_a_lead_eligible_here_can_be_in_sequence_there.py,
                        tests/test_claim_task.py, tests/test_every_representation_derives_from_one_plan.py,
                        tests/test_no_route_resolves_to_retired_channel.py, tests/test_task387_writeback.py,
                        docs/ (OPERATING-MODE.md, PRODUCTION-HANDOFF, QA-LEAD-STATE, REENGAGEMENT-UK-EU,
                        state/, status/, glm-reviews/, qwen-tasks/REVIEW+RUNNING+TODO)
    tests               test_reengagement_age_is_read_not_cached.py (new), plus 4 existing tests
                        touched; not run against current master
    still relevant?     Branch is 360 commits behind master (merge-base 2026-09-27). Core source files
                        (bisonfactory, heyreachfactory, notify, secondbrain, sequenceplan) all still
                        exist on master. The re-engagement age question is structurally still open.
                        However the branch carries massive unrelated diff (dozens of task files,
                        scripts, state files from other tasks on the same branch).
    conflicts / deps    Shares branch with TASK-293, TASK-318, TASK-372, TASK-397. Touches
                        src/sequenceplan.py (also TASK-296/314), src/notify.py (also TASK-290/305/313),
                        tests/test_claim_task.py (also TASK-285/290).
    disposition         CANDIDATE — core change is relevant, but needs surgical extraction from a
                        branch carrying ~45 other commits of mixed age.

---

## TASK-283

    task                TASK-283
    branch              qwen-worker-2-r9
    exact SHA           f03c74fc01a40df45419742e122268d11c8395a1
    purpose             S7 renders three bodies and the cadence now wants four — verify the render
                        carries every variable the provider sequence asks for
    files changed       No TASK-283-specific files. The task file remains in TODO on both the branch
                        and master with no result block. No commits on the branch mention TASK-283.
    tests               None
    still relevant?     No result was ever produced. The task file exists on master in TODO.
    conflicts / deps    None — no work was done.
    disposition         STALE — no result exists on the branch. Task was never worked.

---

## TASK-284

    task                TASK-284
    branch              qwen-worker-12-r59
    exact SHA           a520841c33e0b6035685dbf29ed755c1d062b09a
    purpose             The MX walk that stopped before it finished — complete the DNS MX-record
                        walk with fail-closed five-outcome semantics
    files changed       scripts/mx_walk_report.py (new), src/candidateexport.py,
                        tests/test_a_dns_failure_never_reads_as_allowed.py (new),
                        tests/test_the_candidate_list.py (new),
                        tests/test_the_nightly_sourcing_pipeline.py (new),
                        tests/test_the_weekly_candidate_export.py (new),
                        docs/MX-WALK-2026-09-25.md, docs/qwen-tasks/DONE/TASK-284-*.md
    tests               4 new test files; not run against current master
    still relevant?     Branch is 421 commits behind master (merge-base 2026-09-26). Source files
                        src/candidateexport.py still exists on master. The MX walk and candidate
                        export pipeline are structurally still present.
    conflicts / deps    No overlap with other pending results in this batch.
    disposition         CANDIDATE — self-contained change, tests and code, still relevant domain.

---

## TASK-285

    task                TASK-285
    branch              qwen-worker-3-r9-task285
    exact SHA           c8a62f4109f47eb5338f1ef334d68f44dcb989ef
    purpose             The collision walk batch 3 — verify no two campaigns stage the same contact,
                        with CheapVerifier wired into the waterfall and an LLM tiebreaker for flagged
    files changed       src/providers/cheapverifier.py (new, GONE from master), src/enrich.py,
                        src/waterfall.py, src/bisonfactory.py,
                        scripts/claim_task.py, scripts/collision_walk_report.py,
                        scripts/stage_s3_llm_tiebreaker.py,
                        tests/cassettes/cheapverifier/ (10 new cassettes),
                        tests/test_cheapverifier_is_part_of_the_waterfall.py (new),
                        tests/test_llm_tiebreaker.py (new),
                        tests/test_a_refused_domain_is_never_clear.py (new),
                        tests/test_claim_task.py, tests/test_claim_task_readiness_is_not_inferred.py,
                        tests/test_staging_a_campaign_twice_builds_one.py (new),
                        tests/test_staging_refuses_colliding_contacts.py (new),
                        tests/test_task387_provider_event_writeback.py (new),
                        docs/COLLISION-WALK-2026-09-25.md, docs/SUITE-TRIAGE-2026-09-27.md
    tests               7+ new test files; not run against current master
    still relevant?     Branch is 335 commits behind master (merge-base 2026-09-27).
                        src/providers/cheapverifier.py does NOT exist on master (never merged).
                        src/enrich.py, src/waterfall.py, src/bisonfactory.py still exist.
                        The collision-walk and staging-refuses logic is structurally relevant,
                        but CheapVerifier as a provider was never integrated.
    conflicts / deps    Shares branch with other tasks. Touches src/bisonfactory.py (also TASK-281,
                        TASK-296), src/enrich.py (also TASK-307), tests/test_claim_task.py
                        (also TASK-281, TASK-290).
    disposition         CANDIDATE — collision-walk and staging guards are relevant; CheapVerifier
                        integration needs separate decision on whether that provider is still wanted.

---

## TASK-286

    task                TASK-286
    branch              qwen-worker-3-r60
    exact SHA           a67999eb71f4f9bf1ca3ebe04c723a10f6ea29e1
    purpose             The suite baseline as a named list of test names, diffed against 09-23
    files changed       docs/SUITE-BASELINE-2026-09-25.md (new),
                        docs/state/SUITE-BASELINE-2026-09-25.json (new),
                        docs/qwen-tasks/DONE/TASK-286-*.md, docs/qwen-tasks/TODO/TASK-286-*.md
    tests               None — documentation/state artifact only
    still relevant?     Branch is 420 commits behind master (merge-base 2026-09-26). The baseline
                        is a point-in-time snapshot from 2026-09-25, now 4 days stale. No source
                        or test code changed.
    conflicts / deps    None.
    disposition         STALE — a dated snapshot with no code changes; master has moved 420 commits
                        past it. The baseline needs regeneration, not integration of this branch.

---

## TASK-287

    task                TASK-287
    branch              qwen-worker-4-r60
    exact SHA           8d98cb78410bf840958ef88b0d2d2fe220cd3223
    purpose             Four issue numbers were taken twice — register hygiene audit finding
                        duplicate IDs in PROBLEM-REGISTER.md
    files changed       scripts/register_lint.py (new, does NOT exist on master),
                        tests/test_the_register_has_no_duplicate_ids.py (new),
                        docs/REGISTER-HYGIENE-2026-09-25.md,
                        docs/qwen-tasks/REVIEW/TASK-287-*.md
    tests               test_the_register_has_no_duplicate_ids.py (new); not run against master
    still relevant?     Branch is 420 commits behind master (merge-base 2026-09-26).
                        scripts/register_lint.py does NOT exist on master (never merged).
                        The register-lint concept is still relevant — duplicate IDs are still
                        possible. The script is self-contained and small (51 lines).
    conflicts / deps    No overlap with other pending results.
    disposition         CANDIDATE — small, self-contained, still-relevant lint script with test.

---

## TASK-288

    task                TASK-288
    branch              qwen-worker-6-r59
    exact SHA           357c1ffffdd06937be62d599ae5662e0083cfc38
    purpose             Second pass: do the account-rule tests actually fail at assertion (not
                        import)? Verdict: all 19 tests fail at IMPORT, static analysis confirms
                        logic is correct, ACCEPT WITH ADDITIONS
    files changed       tests/test_the_account_rule_staggers_rather_than_blocks.py (new),
                        docs/qwen-tasks/DONE/TASK-288-*.md,
                        docs/qwen-tasks/REVIEW/TASK-277-account-rule-red-tests.md
    tests               test_the_account_rule_staggers_rather_than_blocks.py (new); result notes
                        tests fail at import, not assertion — logic correct per static analysis
    still relevant?     Branch is 421 commits behind master (merge-base 2026-09-26). The test file
                        is new and does not exist on master. Account staggering rules are still
                        relevant to the cadence model.
    conflicts / deps    No overlap with other pending results.
    disposition         CANDIDATE — test is relevant, but the result block notes tests fail at
                        import, so the test may need repair before it is useful.

---

## TASK-289

    task                TASK-289
    branch              qwen-worker-6-r60
    exact SHA           9154d87f2a30f870625dfdb311b34f7f4bba950e
    purpose             Second pass on Apify cost calibration — boundary named, figures reconciled,
                        LinkedIn-only re-priced
    files changed       docs/APIFY-COST-SECOND-PASS-2026-09-25.md (new),
                        docs/qwen-tasks/BLOCKED/TASK-276-apify-cost-calibration.md,
                        docs/qwen-tasks/DONE/TASK-289-*.md
    tests               None — documentation only
    still relevant?     Branch is 421 commits behind master (merge-base 2026-09-26). Pure
                        documentation with no code changes. Apify cost figures are point-in-time.
    conflicts / deps    None.
    disposition         STALE — documentation-only result from 4+ days ago with no code changes.
                        Apify pricing may have changed since.

---

## TASK-290

    task                TASK-290
    branch              qwen-worker-9-r9
    exact SHA           f1b9c357c17f4b557cbdb06f68339c7343ef3e83
    purpose             Second pass: the copylint wired into a module that refuses to send — the
                        no-caller check and the salvage table
    files changed       src/notify.py, src/providers/groq.py (new, GONE from master),
                        src/providers/openrouter.py (new, GONE from master),
                        src/providers/slack.py, config/clients/productive-offers.yaml,
                        scripts/claim_task.py, scripts/credential_health.py,
                        scripts/measure_research_freshness.py, scripts/pool.sh,
                        scripts/pool_watchdog.sh, scripts/refill_queue.py,
                        tests/test_the_lint_refuses_the_real_push.py (new),
                        tests/test_a_step_never_renders_an_empty_signature.py (new),
                        tests/test_groq_openrouter_adapters.py (new),
                        tests/test_claim_task.py, tests/test_no_route_resolves_to_retired_channel.py,
                        docs/ (COPYLINT-SECOND-PASS, AUDIT, OPERATING-MODE, PRODUCTION-HANDOFF,
                        state/, status/, glm-reviews/, qwen-tasks/REVIEW+RUNNING+TODO)
    tests               3 new test files; not run against current master
    still relevant?     Branch is 358 commits behind master (merge-base 2026-09-27).
                        src/providers/groq.py and src/providers/openrouter.py do NOT exist on master
                        (never merged). src/notify.py and src/providers/slack.py still exist.
                        The copylint refusal logic in notify.py may still be relevant, but the
                        Groq/OpenRouter provider approach was not taken.
    conflicts / deps    Shares branch with TASK-305 and TASK-313. Touches src/notify.py (also
                        TASK-281), src/providers/slack.py (also TASK-281), tests/test_claim_task.py
                        (also TASK-281, TASK-285).
    disposition         CANDIDATE — the copylint wiring in notify.py is relevant, but the
                        Groq/OpenRouter provider files are dead weight that must be excluded.

---

## TASK-292

    task                TASK-292
    branch              origin/qwen-worker-10-r9
    exact SHA           3f7f8f14280e8f2618c1f1e54ac1f2bfd84d0a0e
    purpose             A push that cannot refuse is not a gate — QA Lane F harness implementing
                        scripts/qa/check_lead_pack.py
    files changed       tests/test_task565_incidents_are_regression_fixtures.py (new, unrelated),
                        docs/ (RACHELE-BLOCKED, glm-reviews/, qwen-tasks/DONE+REVIEW+TODO for
                        TASK-487 through TASK-565)
    tests               test_task565_incidents_are_regression_fixtures.py (new, for TASK-565 not 292)
    still relevant?     Branch is 1 commit behind master (merge-base 2026-09-29). The branch's
                        commits are all about TASK-487 through TASK-565 (later work). TASK-292's
                        task file remains in TODO with no result block. No commits mention TASK-292.
    conflicts / deps    None — no TASK-292 work was done.
    disposition         STALE — no result exists. Branch was reused for later tasks.

---

## TASK-293

    task                TASK-293
    branch              qwen-worker-2-r9
    exact SHA           f03c74fc01a40df45419742e122268d11c8395a1
    purpose             Eligible in our store is not eligible at the provider — per-lead eligibility
                        check via scripts/qa/check_lead_state.py
    files changed       Same branch diff as TASK-281 (shared branch). TASK-293-specific commit:
                        "TASK-293: per-lead eligibility check (scripts/qa/check_lead_state.py)".
                        Key files: scripts/qa/check_lead_state.py (new),
                        tests/test_reengagement_age_is_read_not_cached.py,
                        src/bisonfactory.py, src/heyreachfactory.py, src/notify.py,
                        src/secondbrain.py, src/sequenceplan.py
    tests               scripts/qa/check_lead_state.py (new QA check); not run against master
    still relevant?     Same as TASK-281: branch is 360 behind, source files still exist. The QA
                        check concept is still relevant.
    conflicts / deps    Shares branch with TASK-281 (identical SHA). Same file overlaps.
    disposition         CANDIDATE — same extraction challenge as TASK-281 from a large shared branch.

---

## TASK-294

    task                TASK-294
    branch              qwen-worker-r9-t391
    exact SHA           d4effa8d82c50fc4166fd6e6780f069d728eda00
    purpose             The researched set and the rendered set are disjoint — per-lead research-pack
                        QA check with identity-not-presence semantics
    files changed       src/claims.py, src/executionguard.py, src/generate.py, src/ingest.py,
                        scripts/qa/__init__.py, scripts/qa/check_lead_pack.py (new),
                        scripts/task463_attribute.py (new),
                        tests/test_a_client_supplied_figure_licenses_no_claim_in_either_gate.py (new),
                        tests/test_a_pack_fact_must_belong_to_this_company.py (new),
                        tests/test_compliance_gate.py, tests/test_task391_skills_wired_into_generate.py,
                        tests/test_the_ingest_carries_linkedin.py (new),
                        COMPLIANCE.md, docs/ (INTEGRATION-QUEUE, QA-LEAD-PACK, TASK-463-ATTRIBUTION),
                        docs/state/PROBLEM-REGISTER.md,
                        docs/qwen-tasks/ (REVIEW/TASK-294, REVIEW/TASK-311, REVIEW/TASK-463,
                        RUNNING/TASK-391, BLOCKED/TASK-302, DONE/TASK-364+418+426, TODO/)
    tests               3 new test files plus modifications to test_compliance_gate.py; not run
                        against current master
    still relevant?     Branch is 218 commits behind master (merge-base 2026-09-28). Core source
                        files (claims.py, executionguard.py, generate.py, ingest.py) all still exist.
                        src/ingest.py on master has NO linkedin references, confirming the LinkedIn
                        column finding is still unmerged. Substantially relevant.
    conflicts / deps    Shares branch with TASK-294, TASK-302, TASK-311, TASK-391. Touches
                        src/claims.py (unique in this batch), src/executionguard.py (also TASK-302),
                        src/generate.py (also TASK-310), src/ingest.py (also TASK-311).
    disposition         CANDIDATE — recent merge-base, core source files still relevant, addresses
                        a real gap (pack-fact identity check).

---

## TASK-295

    task                TASK-295
    branch              origin/qwen-worker-10-r9
    exact SHA           3f7f8f14280e8f2618c1f1e54ac1f2bfd84d0a0e
    purpose             em4 reads BODY_3 and the step key is not the variable number — per-lead
                        copy check via scripts/qa/check_lead_copy.py
    files changed       Same as TASK-292 (identical branch and SHA). No TASK-295-specific commits.
                        Task file remains in TODO with no result block.
    tests               None for TASK-295
    still relevant?     No result was produced. Branch was reused for TASK-487+.
    conflicts / deps    None — no work was done.
    disposition         STALE — no result exists. Branch was reused for later tasks.

---

## TASK-296

    task                TASK-296
    branch              qwen-worker-11-task314
    exact SHA           ddc0bc816fed25b327cbe070d0597ba03ae2b67e
    purpose             Eleven campaigns legitimately hold three steps — EmailBison campaign QA
                        check with eight rules, 58 tests
    files changed       src/bisonfactory.py, src/heyreachfactory.py, src/sequenceplan.py,
                        scripts/qa/__init__.py, scripts/qa/check_campaign_bison.py (new),
                        scripts/stage_work_to_host.sh, scripts/task413_seat_cap_check.py (new),
                        scripts/task413_seat_cap_probe.py (new),
                        tests/test_every_representation_derives_from_one_plan.py,
                        tests/test_no_cadence_step_is_silently_dropped.py (new),
                        tests/test_step_counts_agree_while_the_keys_do_not.py (new),
                        docs/QA-CAMPAIGN-BISON-2026-09-25.md, docs/state/SENDER-CAPACITY.json,
                        docs/state/TASK-413-SEAT-CAP-CHECK.json,
                        docs/qwen-tasks/ (DONE/TASK-314, REVIEW/TASK-296+364+398+413, TODO/)
    tests               2 new test files plus modification of existing; not run against master
    still relevant?     Branch is 342 commits behind master (merge-base 2026-09-27). Core source
                        files (bisonfactory, heyreachfactory, sequenceplan) still exist. Campaign
                        QA checks and step-drop guards are structurally relevant.
    conflicts / deps    Shares branch with TASK-314 (identical SHA). Touches src/sequenceplan.py
                        (also TASK-281), src/bisonfactory.py (also TASK-281, TASK-285).
    disposition         CANDIDATE — relevant QA check with tests, still-applicable source files.

---

## TASK-298

    task                TASK-298
    branch              qwen-worker-r9
    exact SHA           53dc50c8ebe158102052206712e18f229bb48a7b
    purpose             Absent within the window is not absent — post-push readback check
                        (scripts/qa/check_readback.py, phase post_push)
    files changed       None. Branch is already merged into master (ancestor). Zero diff.
                        Task file remains in TODO on both branch and master.
    tests               None
    still relevant?     Branch IS master. No work was done.
    conflicts / deps    None.
    disposition         STALE — branch is merged into master, task was never completed, task file
                        still in TODO.

---

## TASK-301

    task                TASK-301
    branch              qwen-worker-7-r59
    exact SHA           24df89c75622d515ccec22bce47c2706086d4695
    purpose             Re-render 503 and build the review file — HTML review file generator with
                        personalisation block, pack fact gate, and 26 tests
    files changed       scripts/build_review_html.py (new, GONE from master),
                        scripts/render_review_503.py (new, GONE from master),
                        src/packfact.py (GONE from master),
                        tests/test_review_503_render.py (new),
                        docs/qwen-tasks/REVIEW/TASK-301-*.md
    tests               test_review_503_render.py (new); not run against master
    still relevant?     Branch is 421 commits behind master (merge-base 2026-09-26). ALL three
                        source files (packfact.py, build_review_html.py, render_review_503.py)
                        do NOT exist on master — they were never merged. The review-file concept
                        may still be wanted, but the implementation is entirely orphaned.
    conflicts / deps    TASK-312 has identical SHA (same branch). No other batch task touches
                        these files.
    disposition         STALE — all source files are gone from master; the branch is 421 commits
                        behind. The approach would need to be rebuilt from scratch.

---

## TASK-302

    task                TASK-302
    branch              qwen-worker-r9-t391
    exact SHA           d4effa8d82c50fc4166fd6e6780f069d728eda00
    purpose             Re-render 504 and build the review file — BLOCKED on queue access and
                        provider write scope
    files changed       Same branch diff as TASK-294 (shared branch). TASK-302 was moved to
                        BLOCKED — no implementation commits. The task file on the branch says
                        "BLOCKED - Stages 2-3 are Claude's provider write scope".
    tests               None
    still relevant?     Task was explicitly BLOCKED, never implemented. The review-file
                        infrastructure (packfact.py etc.) does not exist on master.
    conflicts / deps    Shares branch with TASK-294, TASK-311, TASK-391.
    disposition         REJECT — task was BLOCKED by design, never implemented, and the
                        infrastructure it depends on does not exist on master.

---

## TASK-303

    task                TASK-303
    branch              qwen-worker-8-r59
    exact SHA           53cd306b66d56037f3166d30d3904353eeb24c0b
    purpose             Re-render 505 and build the review file — BLOCKED on queue access
    files changed       scripts/task303_render_review.py (new, GONE from master),
                        docs/TASK-303-REPORT.md,
                        docs/qwen-tasks/BLOCKED/TASK-303-*.md
    tests               None
    still relevant?     Branch is 421 commits behind master (merge-base 2026-09-26). The render
                        script does not exist on master. Task was explicitly BLOCKED.
    conflicts / deps    No overlap with other pending results.
    disposition         REJECT — task was BLOCKED, render script is orphaned, 421 commits behind.

---

## TASK-304

    task                TASK-304
    branch              origin/qwen-worker-4-task304-review-file
    exact SHA           1a82ed63b6e4b1f48559bbdd4838a2900399fef4
    purpose             The 491-498 retroactive review files — review file generator for campaigns
                        491-498, Stage 2 owed
    files changed       scripts/build_review_file.py (new, GONE from master),
                        src/reviewfile.py (new, GONE from master),
                        tests/test_build_review_file.py (new),
                        tests/test_review_file.py (new),
                        docs/qwen-tasks/REVIEW/TASK-304-*.md, docs/qwen-tasks/TODO/TASK-304-*.md
    tests               2 new test files; not run against master
    still relevant?     Branch is 473 commits behind master (merge-base 2026-09-25). Both source
                        files (reviewfile.py, build_review_file.py) do NOT exist on master.
                        The oldest merge-base in this batch.
    conflicts / deps    No overlap with other pending results.
    disposition         STALE — 473 commits behind, all source files gone from master. The
                        review-file concept was not adopted.

---

## TASK-305

    task                TASK-305
    branch              qwen-worker-9-r9
    exact SHA           f1b9c357c17f4b557cbdb06f68339c7343ef3e83
    purpose             Groq as the reasoning provider with OpenRouter fallback — adapter with
                        spend ledger integration and explicit refusal
    files changed       Same branch diff as TASK-290 (shared branch). TASK-305-specific commits:
                        "TASK-305: Groq adapter with spend ledger, OpenRouter fallback that refuses
                        explicitly". Key files: src/providers/groq.py (new, GONE from master),
                        src/providers/openrouter.py (new, GONE from master), src/notify.py,
                        src/providers/slack.py,
                        tests/test_groq_openrouter_adapters.py (new)
    tests               test_groq_openrouter_adapters.py (new); not run against master
    still relevant?     Same branch as TASK-290. groq.py and openrouter.py do NOT exist on master.
                        The Groq/OpenRouter provider approach was not adopted.
    conflicts / deps    Shares branch with TASK-290 and TASK-313 (identical SHA).
    disposition         STALE — provider files are gone from master; the approach was not taken.

---

## TASK-307

    task                TASK-307
    branch              qwen-worker-9-r59
    exact SHA           2ee0940d37f2f6a32d3772ba7ecdea97903c57c9
    purpose             ContactOut LinkedIn URL from email — GET /people/person?email= route
                        wired into enrich
    files changed       src/enrich.py, src/providers/__init__.py, src/providers/contactout.py,
                        tests/test_contactout_linkedin_from_email.py (new),
                        docs/qwen-tasks/DONE/TASK-307-*.md, docs/qwen-tasks/TODO/TASK-307-*.md
    tests               test_contactout_linkedin_from_email.py (new); not run against master
    still relevant?     Branch is 421 commits behind master (merge-base 2026-09-26). Source files
                        (enrich.py, contactout.py) still exist on master. Master's contactout.py
                        already extracts linkedin_url from profile data, but the email->LinkedIn
                        route (GET /people/person?email=) is a NEW capability not on master.
                        Still relevant as a distinct feature.
    conflicts / deps    Touches src/enrich.py (also TASK-285), src/providers/contactout.py
                        (unique in this batch).
    disposition         CANDIDATE — small, focused change adding a new route; still relevant
                        capability not present on master.

---

## TASK-308

    task                TASK-308
    branch              qwen-worker-4-r9-task280
    exact SHA           cdffd0a2d3bab2bea4d7a35373876fce93cc97fe
    purpose             Claude Sonnet for prospect-facing copy — Anthropic provider with dollar
                        ledger integration, 37 tests
    files changed       scripts/reverse_reconcile.py (new), src/providers/anthropic.py (new, GONE
                        from master), src/spendledger.py,
                        tests/base.py, tests/fixtures/cassettes/anthropic.json (new),
                        tests/test_a_reply_stops_the_other_channel.py (new),
                        tests/test_anthropic.py (new),
                        tests/test_invariants.py,
                        tests/test_reverse_reconciliation_is_exhaustive.py (new),
                        docs/REVERSE-RECONCILIATION-2026-09-25.md,
                        docs/qwen-tasks/REVIEW/TASK-280-*.md, REVIEW/TASK-308-*.md, REVIEW/TASK-315-*.md
    tests               3 new test files plus modifications to test_invariants.py and tests/base.py;
                        not run against current master
    still relevant?     Branch is 467 commits behind master (merge-base 2026-09-25).
                        src/providers/anthropic.py does NOT exist on master (never merged).
                        src/spendledger.py still exists but has no reverse reconciliation on master.
                        scripts/reverse_reconcile.py still exists on master.
                        The Anthropic provider approach was not adopted, but the reverse
                        reconciliation and spend ledger changes may have value.
    conflicts / deps    Shares branch with TASK-315 (identical SHA). Touches src/spendledger.py
                        (also TASK-315).
    disposition         CANDIDATE — the Anthropic provider is dead, but the reverse reconciliation
                        concept and spend ledger changes may still be worth extracting.

---

## TASK-310

    task                TASK-310
    branch              qwen-worker-11-r9
    exact SHA           c392a8ba4f07208cff6d89ac53c230aa64f4a7d5
    purpose             Every approved file feeds the training set — approval hash recorded and
                        checked, training set wired to review approvals
    files changed       src/offers.py, src/providers/bison.py, src/providers/heyreach.py,
                        src/reviewapproval.py, src/store.py, src/training.py (GONE from master),
                        scripts/pool_status.py (new),
                        config/clients/productive/offers.yaml (new path),
                        tests/test_an_approval_does_not_survive_a_re_render.py (new),
                        tests/test_an_offer_cannot_be_invented.py (new),
                        tests/test_changing_an_approved_fact_changes_the_output.py (new),
                        tests/test_fixture_hygiene.py, tests/test_pool_status.py (new),
                        tests/test_task400_rework2.py,
                        tests/test_the_cadence_reacts_to_what_the_prospect_did.py,
                        tests/test_the_entrypoint_actually_loads_its_skills.py (new),
                        tests/test_the_entrypoint_is_the_only_generation_path.py (new),
                        tests/test_the_entrypoint_refuses_at_a_client_ceiling.py (new),
                        tests/test_training.py (new),
                        docs/glm-reviews/, docs/qwen-tasks/ (DONE/TASK-330+437+456, REVIEW/,
                        RUNNING/TASK-328+385)
    tests               8+ new test files; not run against current master
    still relevant?     Branch is 177 commits behind master (merge-base 2026-09-28 — most recent
                        in this batch). src/training.py does NOT exist on master. Other source
                        files (offers.py, reviewapproval.py, store.py, bison.py, heyreach.py)
                        still exist. The approval-hash and training-set concepts are structurally
                        relevant.
    conflicts / deps    Touches src/store.py (unique in this batch), src/offers.py (unique),
                        src/reviewapproval.py (unique). No overlap with other batch tasks.
    disposition         CANDIDATE — most recent merge-base, many tests, core approval-to-training
                        pipeline is relevant. src/training.py needs to be re-created or the logic
                        moved elsewhere.

---

## TASK-311

    task                TASK-311
    branch              qwen-worker-r9-t391
    exact SHA           d4effa8d82c50fc4166fd6e6780f069d728eda00
    purpose             The ingest drops the LinkedIn column — fix to carry LinkedIn through from
                        research data into contacts
    files changed       Same branch diff as TASK-294 (shared branch). TASK-311-specific commit:
                        "TASK-311: the ingest carries the LinkedIn column onto contacts".
                        Key files: src/ingest.py, src/claims.py, src/executionguard.py,
                        tests/test_the_ingest_carries_linkedin.py (new)
    tests               test_the_ingest_carries_linkedin.py (new); not run against master
    still relevant?     Branch is 218 commits behind master (merge-base 2026-09-28). src/ingest.py
                        on master has NO linkedin references — the fix is still unmerged and
                        relevant.
    conflicts / deps    Shares branch with TASK-294, TASK-302, TASK-311, TASK-391. Touches
                        src/ingest.py (also TASK-294), src/claims.py (also TASK-294).
    disposition         CANDIDATE — recent merge-base, gap confirmed unmerged on master, small
                        focused fix.

---

## TASK-312

    task                TASK-312
    branch              qwen-worker-4-r59
    exact SHA           24df89c75622d515ccec22bce47c2706086d4695
    purpose             Same branch as TASK-301 — re-render 503 and build the review file
    files changed       Identical to TASK-301 (same SHA, same branch content).
    tests               Identical to TASK-301.
    still relevant?     Identical to TASK-301 — all source files gone from master.
    conflicts / deps    Identical to TASK-301.
    disposition         STALE — identical to TASK-301; all source files gone from master.

---

## TASK-313

    task                TASK-313
    branch              qwen-worker-9-r9
    exact SHA           f1b9c357c17f4b557cbdb06f68339c7343ef3e83
    purpose             Audit the current state against the architecture upgrade spec (sections 3-12)
    files changed       Same branch diff as TASK-290 and TASK-305 (shared branch). TASK-313-specific
                        commit: "TASK-313 audit: current state vs ARCHITECTURE-UPGRADE-SPEC sections
                        3-12". The task file is in DONE/TASK-313-*.md.
    tests               None — audit/documentation task
    still relevant?     Same branch as TASK-290/305. The audit is a point-in-time assessment.
                        Master has moved 358 commits past the merge-base.
    conflicts / deps    Shares branch with TASK-290 and TASK-305.
    disposition         STALE — audit is a point-in-time document; master has moved far past it.
                        A new audit would be needed.

---

## TASK-314

    task                TASK-314
    branch              qwen-worker-11-task314
    exact SHA           ddc0bc816fed25b327cbe070d0597ba03ae2b67e
    purpose             Where the HeyReach steps are lost — regression test for silently dropped
                        cadence steps
    files changed       Same branch diff as TASK-296 (shared branch). TASK-314-specific commits:
                        "TASK-314: regression test for silently dropped cadence steps".
                        Key files: src/heyreachfactory.py, src/sequenceplan.py,
                        src/bisonfactory.py,
                        tests/test_no_cadence_step_is_silently_dropped.py (new),
                        tests/test_step_counts_agree_while_the_keys_do_not.py (new)
    tests               2 new test files; not run against master
    still relevant?     Same branch as TASK-296. Source files (heyreachfactory, sequenceplan,
                        bisonfactory) still exist on master. Step-drop guards are still relevant.
    conflicts / deps    Shares branch with TASK-296 (identical SHA). Touches src/sequenceplan.py
                        (also TASK-281), src/bisonfactory.py (also TASK-281, TASK-285, TASK-296).
    disposition         CANDIDATE — focused regression test for a real bug class, source files
                        still present on master.

---

## TASK-315

    task                TASK-315
    branch              qwen-worker-4-r9-task280
    exact SHA           cdffd0a2d3bab2bea4d7a35373876fce93cc97fe
    purpose             The cross-channel stop in both directions — a reply on one channel stops
                        the other, verified in both directions with 36 synthetic tests
    files changed       Same branch diff as TASK-308 (shared branch). TASK-315-specific commits:
                        "TASK-315: the cross-channel stop, both directions, 36 synthetic tests".
                        Key files: src/spendledger.py, src/providers/anthropic.py (new, GONE),
                        scripts/reverse_reconcile.py (new),
                        tests/test_a_reply_stops_the_other_channel.py (new),
                        tests/test_reverse_reconciliation_is_exhaustive.py (new)
    tests               2+ new test files; not run against master
    still relevant?     Same branch as TASK-308. src/providers/anthropic.py does NOT exist on
                        master. src/spendledger.py still exists but has no reverse reconciliation.
                        The cross-channel stop concept is relevant but the Anthropic-specific
                        implementation is orphaned.
    conflicts / deps    Shares branch with TASK-308 (identical SHA). Touches src/spendledger.py
                        (also TASK-308).
    disposition         CANDIDATE — the cross-channel stop logic is relevant, but needs extraction
                        from a branch that also carries the dead Anthropic provider.

---

## Summary

| #  | Task   | Disposition | Reason                                                    |
|----|--------|-------------|-----------------------------------------------------------|
| 1  | TASK-281 | CANDIDATE | Re-engagement age from provider; relevant but large branch  |
| 2  | TASK-283 | STALE     | No result exists; task was never worked                     |
| 3  | TASK-284 | CANDIDATE | MX walk completion; self-contained with tests               |
| 4  | TASK-285 | CANDIDATE | Collision walk + staging guards; CheapVerifier needs decision|
| 5  | TASK-286 | STALE     | Dated snapshot, no code, 420 commits behind                 |
| 6  | TASK-287 | CANDIDATE | Register lint script; small, self-contained                 |
| 7  | TASK-288 | CANDIDATE | Account rule test; may need import repair                   |
| 8  | TASK-289 | STALE     | Documentation only, no code changes                         |
| 9  | TASK-290 | CANDIDATE | Copylint wiring; Groq/OpenRouter files are dead weight      |
| 10 | TASK-292 | STALE     | No result; branch reused for later tasks                    |
| 11 | TASK-293 | CANDIDATE | Per-lead eligibility QA check; same branch as TASK-281      |
| 12 | TASK-294 | CANDIDATE | Pack-fact identity check; recent merge-base                 |
| 13 | TASK-295 | STALE     | No result; branch reused for later tasks                    |
| 14 | TASK-296 | CANDIDATE | Campaign QA check with 8 rules; relevant                    |
| 15 | TASK-298 | STALE     | Branch merged, task never completed                         |
| 16 | TASK-301 | STALE     | All source files gone from master                           |
| 17 | TASK-302 | REJECT    | Explicitly BLOCKED, never implemented                       |
| 18 | TASK-303 | REJECT    | Explicitly BLOCKED, render script orphaned                  |
| 19 | TASK-304 | STALE     | 473 commits behind, all source files gone                   |
| 20 | TASK-305 | STALE     | Provider files gone from master; approach not adopted       |
| 21 | TASK-307 | CANDIDATE | ContactOut email→LinkedIn route; focused, still relevant    |
| 22 | TASK-308 | CANDIDATE | Reverse reconciliation concept; Anthropic provider is dead  |
| 23 | TASK-310 | CANDIDATE | Approval-to-training pipeline; most recent merge-base       |
| 24 | TASK-311 | CANDIDATE | Ingest LinkedIn column fix; gap confirmed unmerged          |
| 25 | TASK-312 | STALE     | Identical to TASK-301; all source files gone                |
| 26 | TASK-313 | STALE     | Point-in-time audit; master moved far past it               |
| 27 | TASK-314 | CANDIDATE | Regression test for silently dropped steps                  |
| 28 | TASK-315 | CANDIDATE | Cross-channel stop logic; needs extraction from dead provider|

**CANDIDATE: 16** | **STALE: 10** | **REJECT: 2**

---

## Verification notes

- **TASK-298**: `scripts/qa/check_readback.py` EXISTS on master (confirmed at
  HEAD). The work was integrated through a different path (likely cherry-pick).
  The branch `qwen-worker-r9` is an ancestor of master with zero diff. STALE
  confirmed — nothing to integrate from this branch.
- **TASK-294**: `tests/test_a_pack_fact_must_belong_to_this_company.py` exists
  on the branch but NOT on master. `src/claims.py` has significant new logic
  (client-supplied figure restrictions). CANDIDATE confirmed — real, landable
  work that is not yet on master.
- **TASK-312**: The branch `qwen-worker-4-r59` resolves to the same SHA as
  `qwen-worker-7-r59` (TASK-301). No `src/copyengine.py` exists on the branch.
  The branch only contains TASK-301's review-file work. STALE confirmed.
- **Shared branches**: 8 of 28 tasks share branches with other tasks in this
  batch. Integration of any CANDIDATE from a shared branch requires surgical
  cherry-pick of task-specific commits, not whole-branch merge.
