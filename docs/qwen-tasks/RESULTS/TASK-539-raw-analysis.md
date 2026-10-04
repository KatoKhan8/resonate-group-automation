# TASK-539 Raw Analysis — 28 Task Result Branches

**Analyzed against:** master @ `2bf7b8a571fe11bada4f56fbeee768ab1e78a8`
**Date:** 2026-10-04
**Scope:** Read-only analysis. No merges, cherry-picks, or production changes.

---

## Shared Branch Map

Several branches serve multiple tasks. The code diff is shared; per-task relevance is noted.

| Branch | SHA | Tasks |
|--------|-----|-------|
| qwen-worker-2-r9 | a59e5f9 | TASK-281, TASK-293 |
| qwen-worker-r9 | af48369 | TASK-283, TASK-298 |
| qwen-worker-9-r9 | f1b9c35 | TASK-290, TASK-305, TASK-313 |
| origin/qwen-worker-10-r9 | ab2a6ff | TASK-292, TASK-295 |
| qwen-worker-r9-t391 | d4effa8 | TASK-294, TASK-302, TASK-311 |
| qwen-worker-11-task314 | ddc0bc8 | TASK-296, TASK-314 |
| qwen-worker-4-r9-task280 | cdffd0a | TASK-308, TASK-315 |

---

## Cross-Branch File Overlaps (src/ and tests/)

These files are touched by multiple branches in this batch and cannot be merged naively:

| File | Branches |
|------|----------|
| `src/bisonfactory.py` | TASK-285 (c8a62f4), TASK-296/314 (ddc0bc8) |
| `src/enrich.py` | TASK-285 (c8a62f4), TASK-307 (2ee0940) |
| `tests/base.py` | TASK-292/295 (ab2a6ff), TASK-308/315 (cdffd0a) |

---

## Per-Task Analysis

---

### 1. TASK-281 — The UK/EU re-engagement age comes from the provider, not the cache

- **Branch:** qwen-worker-2-r9 @ `a59e5f98372a5934b3775622c2a98b3479435749`
- **Shared with:** TASK-293 (same branch)
- **Merge base:** `2bf7b8a57` (master HEAD — branch is directly on top of master)
- **Purpose:** Read the re-engagement age from the provider rather than a stale cache.

**Files changed (35):**
- `docs/REENGAGEMENT-UK-EU-PROVIDER-READ-2026-09-25.md` (report)
- `docs/phase2-scenarios/` — CATALOGUE, README, REPORT, 30 scenario YAMLs (S01-S30)
- `docs/qwen-tasks/DONE/TASK-978-thirty-scenario-yaml-files-from-the-catalogue.md`
- `docs/qwen-tasks/REVIEW/TASK-281-*.md`, `docs/qwen-tasks/RUNNING/TASK-281-*.md`
- `scripts/reengagement_provider_read.py` (new script)
- `tests/test_reengagement_age_is_read_not_cached.py` (new test)

**Commits (4):**
```
af4836929 TASK-281 to REVIEW: script, test, and report complete; live run owed
c42f81058 TASK-281: UK/EU re-engagement provider read script, regression test, and report
78ce40763 Claim TASK-281: UK/EU re-engagement provider read
90f45b94d TASK-978: thirty scenario YAML files from the catalogue, all 30 parse clean
```

**Tests:** `tests/test_reengagement_age_is_read_not_cached.py` — new test file.

**Master overlap:** NONE — merge base is master HEAD.

**Cross-branch conflicts:** None with other branches in this batch.

**Disposition: CANDIDATE** — Clean branch on master HEAD, new script + test + report. Live run is owed (noted in commit message). The 30 scenario YAMLs are a bonus artifact (TASK-978).

---

### 2. TASK-283 — S7 renders three bodies and the cadence now wants four

- **Branch:** qwen-worker-r9 @ `af4836929c167bf45568e315f39b16996be34456`
- **Shared with:** TASK-298 (same branch)
- **Merge base:** `2bf7b8a57` (master HEAD)
- **Purpose:** The cadence expects four message bodies but S7 only renders three; investigate and fix the mismatch.

**Files changed (35):** Same branch as TASK-281 — see above. The TASK-283-specific work is the phase2-scenarios directory (30 scenario YAMLs + catalogue/report).

**Commits:** Same 4 commits as TASK-281. The scenario YAMLs are the primary artifact for TASK-283.

**Tests:** No new test files specific to TASK-283's rendering mismatch.

**Master overlap:** NONE.

**Cross-branch conflicts:** None.

**Disposition: CANDIDATE** — The 30 scenario YAMLs and catalogue are a substantial documentation artifact. However, no code fix for the rendering mismatch itself is evident; this is primarily a scenario-mapping exercise. Worth reviewing to confirm the fourth step gap is addressed.

---

### 3. TASK-284 — The MX walk that stopped before it finished

- **Branch:** qwen-worker-12-r59 @ `a520841c33e0b6035685dbf29ed755c1d062b09a`
- **Merge base:** `e4dc021ca` (older than master HEAD)
- **Purpose:** Complete the MX record walk that was terminating early before processing all records.

**Files changed (10):**
- `docs/MX-WALK-2026-09-25.md` (report)
- `docs/qwen-tasks/DONE/TASK-284-*.md`, `docs/qwen-tasks/RUNNING/TASK-245-*.md`
- `scripts/mx_walk_report.py` (new script)
- `src/candidateexport.py` (modified)
- `tests/test_a_dns_failure_never_reads_as_allowed.py` (modified)
- `tests/test_the_candidate_list.py` (modified)
- `tests/test_the_nightly_sourcing_pipeline.py` (modified)
- `tests/test_the_weekly_candidate_export.py` (modified)

**Commits (3):**
```
a520841c3 TASK-245: comprehensive tests for nightly sourcing pipeline, candidate list, and weekly export
e420b6398 TASK-245: claim the nightly sourcing task
25cd568cc TASK-284: the MX walk is complete, fail-closed, and five-outcome
```

**Tests:** 4 test files modified. Commit mentions comprehensive tests for nightly sourcing pipeline.

**Master overlap (7 files!):**
- `docs/MX-WALK-2026-09-25.md`
- `scripts/mx_walk_report.py`
- `src/candidateexport.py`
- `tests/test_a_dns_failure_never_reads_as_allowed.py`
- `tests/test_the_candidate_list.py`
- `tests/test_the_nightly_sourcing_pipeline.py`
- `tests/test_the_weekly_candidate_export.py`

All 7 code/doc files have been modified on master since the merge base. HIGH CONFLICT RISK.

**Cross-branch conflicts:** None with other branches in this batch.

**Disposition: STALE** — Master has modified all 7 of the branch's code/doc files since divergence. The branch would need a rebase and conflict resolution. The work may already be superseded.

---

### 4. TASK-285 — The collision walk batch 3 is sitting behind

- **Branch:** qwen-worker-3-r9-task285 @ `c8a62f4109f47eb5338f1ef334d68f44dcb989ef`
- **Merge base:** `05e9220ba` (significantly older than master HEAD)
- **Purpose:** Complete the third batch of the collision walk that was queued behind other work.

**Files changed (38):**
- `docs/COLLISION-WALK-2026-09-25.md`, `docs/SUITE-TRIAGE-2026-09-27.md`
- Multiple task files across REVIEW/, RUNNING/, TODO/ (TASK-267, 285, 358, 387, 410, 412, 426, 432)
- `scripts/claim_task.py`, `scripts/collision_walk_report.py`, `scripts/stage_s3_llm_tiebreaker.py`
- `src/bisonfactory.py`, `src/enrich.py`, `src/providers/cheapverifier.py`, `src/waterfall.py`
- 10 cheapverifier cassettes (test fixtures)
- 9 test files

**Commits (19):** This is a massive branch covering TASK-285 (collision walk), TASK-267 (LLM tiebreaker), TASK-358 (cheapverifier waterfall), TASK-387 (ledger write-back), TASK-410/412/426/432 (GLM verifications and audits).

**Tests:** 9 test files including cheapverifier waterfall tests, collision tests, LLM tiebreaker tests, staging tests.

**Master overlap (11 files):**
- `docs/COLLISION-WALK-2026-09-25.md`, `docs/SUITE-TRIAGE-2026-09-27.md`
- `scripts/claim_task.py`, `scripts/collision_walk_report.py`
- `src/bisonfactory.py`, `src/enrich.py`
- 5 test files

**Cross-branch conflicts:**
- `src/bisonfactory.py` — also touched by TASK-296/314 (ddc0bc8)
- `src/enrich.py` — also touched by TASK-307 (2ee0940)

**Disposition: REJECT** — This branch is a catch-all for 8+ tasks with 19 commits spanning weeks of work. 11 files overlap with master. The cheapverifier integration (TASK-358) and LLM tiebreaker (TASK-267) are substantial but would need individual cherry-pick evaluation. Cannot be merged as a unit. The collision walk report itself is a finding artifact.

---

### 5. TASK-286 — The suite baseline is a list of names, or it is nothing

- **Branch:** qwen-worker-3-r60 @ `a67999eb71f4f9bf1ca3ebe04c723a10f6ea29e1`
- **Merge base:** `0af11fcba` (older than master HEAD)
- **Purpose:** Create a named list of suite failures as a baseline for tracking regressions.

**Files changed (4):**
- `docs/SUITE-BASELINE-2026-09-25.md` (report)
- `docs/qwen-tasks/DONE/TASK-286-*.md`
- `docs/qwen-tasks/TODO/TASK-286-*.md`
- `docs/state/SUITE-BASELINE-2026-09-25.json` (baseline data)

**Commits (1):**
```
a67999eb7 TASK-286: the suite baseline as a list of names, diffed against 09-23
```

**Tests:** None.

**Master overlap:** NONE — no files overlap with master changes since merge base.

**Cross-branch conflicts:** None.

**Disposition: STALE** — A point-in-time snapshot from 2026-09-25. The baseline JSON and doc are dated artifacts. Master has likely moved past this baseline. The concept is valid but this specific snapshot is over a week old.

---

### 6. TASK-287 — Four issue numbers were taken twice

- **Branch:** qwen-worker-4-r60 @ `8d98cb78410bf840958ef88b0d2d2fe220cd3223`
- **Merge base:** `0af11fcba` (older than master HEAD)
- **Purpose:** Audit and resolve duplicate issue/ID numbers in the problem register.

**Files changed (4):**
- `docs/REGISTER-HYGIENE-2026-09-25.md` (report)
- `docs/qwen-tasks/REVIEW/TASK-287-*.md`
- `scripts/register_lint.py` (new lint script)
- `tests/test_the_register_has_no_duplicate_ids.py` (new test)

**Commits (4):**
```
8d98cb784 TASK-287: final commit SHA in result block
c22dc414c TASK-287: audit complete, move to REVIEW
495432628 TASK-287: register hygiene audit — 44 rows, 4 duplicate IDs, 5 proposed downgrades
fb1c53268 TASK-287: move to RUNNING
```

**Tests:** `tests/test_the_register_has_no_duplicate_ids.py` — new test.

**Master overlap (2 files):**
- `docs/REGISTER-HYGIENE-2026-09-25.md`
- `scripts/register_lint.py`

Both doc/script files have been modified on master since merge base.

**Cross-branch conflicts:** None.

**Disposition: CANDIDATE** — The lint script and test are useful guardrails. Two files overlap with master but the overlap may be compatible (doc report + lint script). Worth a targeted review.

---

### 7. TASK-288 — Second pass: do the account-rule tests actually fail, and for the right reason?

- **Branch:** qwen-worker-6-r59 @ `357c1ffffdd06937be62d599ae5662e0083cfc38`
- **Merge base:** `2bf7b8a57` (master HEAD)
- **Purpose:** Verify that the account-rule tests fail at assertion (logic errors) rather than at import (structural errors).

**Files changed (3):**
- `docs/qwen-tasks/DONE/TASK-288-*.md`
- `docs/qwen-tasks/REVIEW/TASK-275-account-rule-red-tests.md`
- `tests/test_the_account_rule_staggers_rather_than_blocks.py` (modified)

**Commits (4):**
```
357c1ffff Remove accidentally committed .qwen output files
7d1749408 TASK-288: move to DONE
b38175ce1 TASK-288: review complete - all 19 tests fail at IMPORT, not assertion; static analysis confirms logic is correct; verdict ACCEPT WITH ADDITIONS
765f91d7b TASK-288: claim and move to RUNNING; retrieve test file from worktree-agent
```

**Tests:** 1 test file modified. Finding: all 19 tests fail at IMPORT, not assertion — the logic is correct but the tests can't reach it.

**Master overlap:** NONE.

**Cross-branch conflicts:** None.

**Disposition: CANDIDATE** — Investigation task with a clear finding (IMPORT failures, not logic failures). The test file modification and the finding are useful. Clean branch on master HEAD.

---

### 8. TASK-289 — Second pass: the Apify calibration that hit a boundary

- **Branch:** qwen-worker-6-r60 @ `9154d87f2a30f870625dfdb311b34f7f4bba950e`
- **Merge base:** `0af11fcba` (older than master HEAD)
- **Purpose:** Reconcile Apify cost calibration figures that hit a measurement boundary.

**Files changed (3):**
- `docs/APIFY-COST-SECOND-PASS-2026-09-25.md` (report)
- `docs/qwen-tasks/BLOCKED/TASK-276-apify-cost-calibration.md`
- `docs/qwen-tasks/DONE/TASK-289-*.md`

**Commits (3):**
```
9154d87f2 TASK-289: fix commit hash in result block
49ebd276a TASK-289: Apify cost calibration second pass — boundary named, figures reconciled, LinkedIn-only re-priced
79fe89ac1 TASK-289: move to RUNNING, second pass on Apify cost calibration
```

**Tests:** None. This is a pure analysis/investigation task.

**Master overlap (1 file):** `docs/APIFY-COST-SECOND-PASS-2026-09-25.md` — doc file modified on master.

**Cross-branch conflicts:** None.

**Disposition: STALE** — Pure investigation/report from 2026-09-25. No code changes. The cost figures may have shifted. The report doc overlaps with master. Unless the calibration findings are still actionable, this is dated.

---

### 9. TASK-290 — Second pass: the copy lint was wired into a module that refuses to send

- **Branch:** qwen-worker-9-r9 @ `f1b9c357c17f4b557cbdb06f68339c7343ef3e83`
- **Shared with:** TASK-305, TASK-313 (same branch)
- **Merge base:** `fc473844e` (significantly older than master HEAD)
- **Purpose:** The copy lint was connected to a module that cannot send, making the lint ineffective.

**Files changed (62):** This is the largest branch in the batch. It covers TASK-290, TASK-305, TASK-313, plus TASK-384, 392, 399, 400-425 and more. Key files for TASK-290:
- `docs/COPYLINT-SECOND-PASS-2026-09-25.md`
- `docs/qwen-tasks/REVIEW/TASK-277-copylint-wiring-tests.md`
- `docs/qwen-tasks/REVIEW/TASK-290-*.md`
- `tests/test_the_lint_refuses_the_real_push.py`

**Commits (30+):** Massive branch covering many tasks. TASK-290-specific commits:
```
830e65d8d TASK-290: move to REVIEW with completed result block
579cc624b TASK-290: the copylint wiring assertion, the salvage table, and the general no-caller check
```

**Tests:** `tests/test_the_lint_refuses_the_real_push.py` — relevant to TASK-290.

**Master overlap (34 files!):** Extensive overlap including config files, docs, scripts, src/notify.py, src/providers/slack.py, and multiple test files.

**Cross-branch conflicts:** None directly with other branches in this batch on the TASK-290-specific files.

**Disposition: REJECT** — This branch is a 62-file, 30-commit mega-branch covering at least 15 tasks. It cannot be merged as a unit. The TASK-290-specific finding (copylint wired to a no-send module) is valuable as a finding, but the code would need to be extracted and cherry-picked. 34 files overlap with master.

---

### 10. TASK-292 — A push that cannot refuse is not a gate

- **Branch:** origin/qwen-worker-10-r9 @ `ab2a6ff1d46daec0bf00822d1c7cde26ce90c9bf`
- **Shared with:** TASK-295 (same branch)
- **Merge base:** `2bf7b8a57` (master HEAD)
- **Purpose:** Ensure that push operations can actually refuse when preconditions are not met.

**Files changed (28):**
- 7 GLM review docs (TASK-491, 504, 514, 520, 522, 527, 534)
- Multiple task files across DONE/, REVIEW/, RUNNING/, TODO/
- `scripts/task397_seat_cap_check.py` (new)
- `src/generate_campaign.py` (modified)
- `src/secondbrain.py` (modified)
- `tests/base.py` (modified)
- `tests/test_generate.py` (modified)
- `docs/state/TASK397-SEAT-CAP-CHECK.json`

**Commits (28):** Covers TASK-292, TASK-295, TASK-318, TASK-397, TASK-411, TASK-491, 504, 514, 520, 522, 527, 534, 932, 973.

**Tests:** `tests/test_generate.py`, `tests/base.py` modified.

**Master overlap:** NONE — merge base is master HEAD.

**Cross-branch conflicts:**
- `tests/base.py` — also touched by TASK-308/315 (cdffd0a)

**Disposition: CANDIDATE** — Clean branch on master HEAD. However, it's a 28-commit branch covering many tasks. The TASK-292-specific work (push gate) is mixed with GLM verifications and other tasks. The generate_campaign.py and secondbrain.py changes need targeted review.

---

### 11. TASK-293 — Eligible in our store is not eligible at the provider

- **Branch:** qwen-worker-2-r9 @ `a59e5f98372a5934b3775622c2a98b3479435749`
- **Shared with:** TASK-281 (same branch)
- **Merge base:** `2bf7b8a57` (master HEAD)
- **Purpose:** Our store's eligibility check does not match the provider's actual eligibility state.

**Files changed:** Same branch as TASK-281. The TASK-293-specific work is:
- `docs/qwen-tasks/DONE/TASK-935-collision-check-against-provider-truth.md`
- `src/provider_truth_check.py` (new)
- `tests/test_provider_truth_check.py` (new)

**Commits:** The TASK-293-relevant commits are:
```
a59e5f983 TASK-935: move to DONE
912ca1f91 TASK-935: collision check against provider truth, read-only, both estates
```

Note: The branch was actually used for TASK-935 (provider truth check), not TASK-293 directly. The provider truth check module addresses the TASK-293 concern.

**Tests:** `tests/test_provider_truth_check.py` — new test file.

**Master overlap:** NONE.

**Cross-branch conflicts:** None.

**Disposition: CANDIDATE** — New module (`provider_truth_check.py`) with tests that directly addresses the eligibility mismatch concern. Clean branch on master HEAD. The module is read-only (no provider writes), which is correct per the operating rules.

---

### 12. TASK-294 — The researched set and the rendered set are disjoint

- **Branch:** qwen-worker-r9-t391 @ `d4effa8d82c50fc4166fd6e6780f069d728eda00`
- **Shared with:** TASK-302, TASK-311 (same branch)
- **Merge base:** `6d2763289` (significantly older than master HEAD)
- **Purpose:** The set of leads with research packs and the set that gets rendered into messages have no overlap.

**Files changed (39):**
- `COMPLIANCE.md` (modified)
- Multiple docs and task files
- `scripts/qa/__init__.py`, `scripts/qa/check_lead_pack.py` (new QA check)
- `scripts/task463_attribute.py`
- `src/claims.py`, `src/executionguard.py`, `src/generate.py`, `src/ingest.py` (core modules)
- 4 test files

**Commits (24):** Large branch covering TASK-294, 271, 302, 311, 364, 391, 400, 418, 426, 449, 462, 463, 464.

**Tests:** 4 test files including compliance gate, pack fact, ingest LinkedIn, skills wiring.

**Master overlap (27 files!):** Extensive overlap including COMPLIANCE.md, src/claims.py, src/executionguard.py, src/generate.py, and multiple test files.

**Cross-branch conflicts:** None directly with other branches in this batch on the TASK-294-specific files.

**Disposition: REJECT** — 39 files changed, 24 commits, 27 files overlap with master. This branch is a mega-branch covering 13 tasks. The per-lead research-pack QA check (`scripts/qa/check_lead_pack.py`) is the TASK-294 artifact and is valuable as a finding/tool, but the branch cannot be merged wholesale. Individual files would need cherry-picking.

---

### 13. TASK-295 — em4 reads BODY_3, and the step key is not the variable number

- **Branch:** origin/qwen-worker-10-r9 @ `ab2a6ff1d46daec0bf00822d1c7cde26ce90c9bf`
- **Shared with:** TASK-292 (same branch)
- **Merge base:** `2bf7b8a57` (master HEAD)
- **Purpose:** Message template em4 reads BODY_3 when the step key mapping says it should read a different variable.

**Files changed:** Same branch as TASK-292 (28 files). The TASK-295-specific work is embedded in the generate_campaign.py and secondbrain.py changes.

**Tests:** `tests/test_generate.py` — modified.

**Master overlap:** NONE.

**Cross-branch conflicts:**
- `tests/base.py` — also touched by TASK-308/315 (cdffd0a)

**Disposition: CANDIDATE** — Same branch as TASK-292. The step-key/variable-number mismatch is a concrete bug. Clean branch on master HEAD. Needs targeted review of the generate_campaign.py changes.

---

### 14. TASK-296 — Eleven campaigns legitimately hold three steps

- **Branch:** qwen-worker-11-task314 @ `ddc0bc816fed25b327cbe070d0597ba03ae2b67e`
- **Shared with:** TASK-314 (same branch)
- **Merge base:** `a1df8aeaf` (significantly older than master HEAD)
- **Purpose:** Validate that eleven campaigns with exactly three cadence steps is correct, not a bug.

**Files changed (21):**
- `docs/QA-CAMPAIGN-BISON-2026-09-25.md`
- Multiple task files
- `scripts/qa/__init__.py`, `scripts/qa/check_campaign_bison.py` (new QA check)
- `scripts/stage_work_to_host.sh`, `scripts/task413_seat_cap_check.py`, `scripts/task413_seat_cap_probe.py`
- `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`
- `docs/state/SENDER-CAPACITY.json`, `docs/state/TASK-413-SEAT-CAP-CHECK.json`
- 3 test files

**Commits (16):** Covers TASK-296, 314, 364, 398, 410, 413.

**Tests:** 3 test files — `test_every_representation_derives_from_one_plan.py`, `test_no_cadence_step_is_silently_dropped.py`, `test_step_counts_agree_while_the_keys_do_not.py`.

**Master overlap (6 files):**
- `scripts/qa/__init__.py`
- `scripts/stage_work_to_host.sh`
- `src/bisonfactory.py`
- `src/heyreachfactory.py`
- `src/sequenceplan.py`
- `docs/qwen-tasks/TODO/TASK-410-*.md`

**Cross-branch conflicts:**
- `src/bisonfactory.py` — also touched by TASK-285 (c8a62f4)

**Disposition: CANDIDATE** — The QA check script and 58 tests are substantial artifacts. 6 files overlap with master but the core QA logic is new. The three-step validation is a concrete, testable claim. Worth targeted review, especially the sequenceplan.py and test files.

---

### 15. TASK-298 — Absent within the window is not absent

- **Branch:** qwen-worker-r9 @ `af4836929c167bf45568e315f39b16996be34456`
- **Shared with:** TASK-283 (same branch)
- **Merge base:** `2bf7b8a57` (master HEAD)
- **Purpose:** A value absent within the measurement window should not be treated as permanently absent.

**Files changed:** Same branch as TASK-283 (35 files). The TASK-298-specific work is the `docs/APIFY-COST-SECOND-PASS-2026-09-25.md` report and the task file moves.

Wait — looking more carefully at the diff, the TASK-298-specific content on this branch is primarily the Apify cost doc and task file moves. The phase2-scenarios YAMLs belong to TASK-283.

**Commits:** Same 4 commits as TASK-281/283. No TASK-298-specific commit visible.

**Tests:** None specific to TASK-298.

**Master overlap:** NONE.

**Cross-branch conflicts:** None.

**Disposition: STALE** — No code changes specific to TASK-298 are visible on this branch. The task appears to have been addressed through documentation only (the Apify cost report). The "absent within window" concern may have been resolved by other work on master. No diff from master for TASK-298-specific files.

---

### 16. TASK-301 — Re-render 503 from productive.yaml and build the operator's review file

- **Branch:** qwen-worker-7-r59 @ `24df89c75622d515ccec22bce47c2706086d4695`
- **Merge base:** `2bf7b8a57` (master HEAD)
- **Purpose:** Generate the operator review file for campaign 503 from the productive config.

**Files changed (5):**
- `docs/qwen-tasks/REVIEW/TASK-301-*.md`
- `scripts/build_review_html.py` (new)
- `scripts/render_review_503.py` (new)
- `src/packfact.py` (modified)
- `tests/test_review_503_render.py` (new)

**Commits (3):**
```
24df89c75 TASK-301: move to REVIEW with RESULT block
df98c36ed TASK-301: HTML review file generator with personalisation block
78c42f38f TASK-301: pack fact gate, rendering script, and 26 tests
```

**Tests:** `tests/test_review_503_render.py` — 26 tests.

**Master overlap:** NONE.

**Cross-branch conflicts:** None.

**Disposition: CANDIDATE** — Clean branch on master HEAD. New rendering scripts with 26 tests. The packfact.py change is the only modification to an existing module. Focused, well-scoped work.

---

### 17. TASK-302 — Re-render 504 from productive.yaml and build the operator's review file

- **Branch:** qwen-worker-r9-t391 @ `d4effa8d82c50fc4166fd6e6780f069d728eda00`
- **Shared with:** TASK-294, TASK-311 (same branch)
- **Merge base:** `6d2763289` (significantly older)
- **Purpose:** Generate the operator review file for campaign 504.

**Files changed:** Same 39 files as TASK-294. The TASK-302-specific status is BLOCKED — the branch moved TASK-302 to BLOCKED because "Stages 2-3 are Claude's provider write scope."

**Commits:** The TASK-302-specific commits show it was moved to BLOCKED:
```
4918e5307 TASK-302: move to BLOCKED - Stages 2-3 are Claude's provider write scope
```

**Tests:** None specific to TASK-302.

**Master overlap:** Same 27 files as TASK-294.

**Cross-branch conflicts:** Same as TASK-294.

**Disposition: REJECT** — Task was explicitly BLOCKED by the worker because it requires Claude's provider write scope. No code artifact for TASK-302 specifically. The branch is a mega-branch that cannot be merged wholesale.

---

### 18. TASK-303 — Re-render 505 from productive.yaml and build the operator's review file

- **Branch:** qwen-worker-8-r59 @ `53cd306b66d56037f3166d30d3904353eeb24c0b`
- **Merge base:** `2bf7b8a57` (master HEAD)
- **Purpose:** Generate the operator review file for campaign 505.

**Files changed (3):**
- `docs/TASK-303-REPORT.md`
- `docs/qwen-tasks/BLOCKED/TASK-303-*.md`
- `scripts/task303_render_review.py` (new)

**Commits (4):**
```
53cd306b6 TASK-303: move to BLOCKED (no queue access)
785e3f05b TASK-303: result block added, blocked on queue access
826a158dd TASK-303: rendering pipeline built, LinkedIn coverage 0%, blocked on queue access
4fb4b433b TASK-303 claimed: move to RUNNING
```

**Tests:** None.

**Master overlap:** NONE.

**Cross-branch conflicts:** None.

**Disposition: REJECT** — Task was BLOCKED because the worker had no queue access. The rendering script exists but LinkedIn coverage was 0%. No test artifact. The worker explicitly could not complete the task.

---

### 19. TASK-304 — The 491-498 retroactive review files

- **Branch:** origin/qwen-worker-4-task304-review-file @ `1a82ed63b6e4b1f48559bbdd4838a2900399fef4`
- **Merge base:** `c3fbc106f` (older than master HEAD)
- **Purpose:** Build retroactive review files for campaigns 491-498.

**Files changed (6):**
- `docs/qwen-tasks/REVIEW/TASK-304-*.md`
- `docs/qwen-tasks/TODO/TASK-304-*.md`
- `scripts/build_review_file.py` (new)
- `src/reviewfile.py` (new)
- `tests/test_build_review_file.py` (new)
- `tests/test_review_file.py` (new)

**Commits (3):**
```
1a82ed63b TASK-304 to REVIEW: review file generator done, Stage 2 owed
45eef1c40 TASK-304: review file generator for campaigns 491-498
99193b5b7 Move TASK-304 to RUNNING
```

**Tests:** 2 test files — `test_build_review_file.py`, `test_review_file.py`.

**Master overlap:** NONE — no overlapping files with master changes since merge base.

**Cross-branch conflicts:** None.

**Disposition: CANDIDATE** — New module (`reviewfile.py`) with generator script and 2 test files. Clean diff with no master overlap. Stage 2 is noted as owed. Depends on TASK-301 (which is also in this batch).

---

### 20. TASK-305 — Groq as the primary reasoning provider, OpenRouter as fallback

- **Branch:** qwen-worker-9-r9 @ `f1b9c357c17f4b557cbdb06f68339c7343ef3e83`
- **Shared with:** TASK-290, TASK-313 (same branch)
- **Merge base:** `fc473844e` (significantly older)
- **Purpose:** Wire Groq as the reasoning provider with OpenRouter as an explicit fallback.

**Files changed:** Same 62 files as TASK-290/313. TASK-305-specific files:
- `src/providers/groq.py` (new)
- `src/providers/openrouter.py` (new)
- `tests/test_groq_openrouter_adapters.py` (new)
- `config/clients/productive-offers.yaml` (modified)

**Commits:** TASK-305-specific:
```
f1b9c357c TASK-305 to REVIEW: code complete, tests pass, live probe owed
61c1f25d7 TASK-305: Groq adapter with spend ledger, OpenRouter fallback that refuses explicitly
```

**Tests:** `tests/test_groq_openrouter_adapters.py` — new test file.

**Master overlap:** 34 files overlap with master.

**Cross-branch conflicts:** None directly on the Groq/OpenRouter files.

**Disposition: CANDIDATE (with caveat)** — The Groq/OpenRouter adapter code is new and well-scoped. However, it lives on a 62-file mega-branch. The provider files (`src/providers/groq.py`, `src/providers/openrouter.py`) and their tests can be cherry-picked. The spend ledger integration needs verification. Live probe is owed.

---

### 21. TASK-307 — ContactOut: the email → LinkedIn route the adapter does not have

- **Branch:** qwen-worker-9-r59 @ `2ee0940d37f2f6a32d3772ba7ecdea97903c57c9`
- **Merge base:** `2bf7b8a57` (master HEAD)
- **Purpose:** Add the missing ContactOut email-to-LinkedIn URL lookup route.

**Files changed (6):**
- `docs/qwen-tasks/DONE/TASK-307-*.md`
- `docs/qwen-tasks/TODO/TASK-307-*.md`
- `src/enrich.py` (modified)
- `src/providers/__init__.py` (modified)
- `src/providers/contactout.py` (new)
- `tests/test_contactout_linkedin_from_email.py` (new)

**Commits (2):**
```
2ee0940d3 TASK-307: record final commit SHA in task result
bfba918d2 TASK-307: ContactOut email->LinkedIn route wired (GET /people/person)
```

**Tests:** `tests/test_contactout_linkedin_from_email.py` — new test.

**Master overlap (2 files):**
- `src/enrich.py`
- `src/providers/__init__.py`

Both modified on master since merge base.

**Cross-branch conflicts:**
- `src/enrich.py` — also touched by TASK-285 (c8a62f4)

**Disposition: CANDIDATE** — Clean, focused branch with a new provider module and test. Only 2 files overlap with master (enrich.py, providers/__init__.py), and the overlap may be compatible. Small, well-scoped change. Note: merge base is master HEAD, so the overlap check shows no master changes to these files since divergence — the overlap is with changes between the branch's actual origin and master.

Wait — merge base IS master HEAD (`2bf7b8a57`), so there should be NO master changes since divergence. Let me re-check.

Actually, the overlap check showed `src/enrich.py` and `src/providers/__init__.py` as overlapping. This means master has changes to these files that are NOT in the branch's ancestry. Since the merge base is master HEAD, this means the branch was created from master HEAD but master has since received new commits... but master HEAD IS the merge base. This is contradictory.

Let me re-examine: the overlap check compares `git diff --name-only $base..master` with the branch's files. If base = master HEAD, then `git diff --name-only master..master` = empty. So there should be NO overlap.

Looking back at the output for `2ee0940d3`:
```
===SHA:2ee0940d37f2f6a32d3772ba7ecdea97903c57c9 BASE:e4dc021ca04f34b16cc6094add36d1118fba9491===
src/enrich.py
src/providers/__init__.py
```

The merge base is `e4dc021ca`, NOT `2bf7b8a57`. I made an error above. Let me correct: the merge base for 2ee0940 is `e4dc021ca` (older than master HEAD). So master HAS moved forward and modified `src/enrich.py` and `src/providers/__init__.py` since the branch diverged.

**Corrected Disposition: CANDIDATE** — Focused change but 2 files overlap with master. The ContactOut module is new. The enrich.py and __init__.py changes need conflict resolution during merge. Still worth reviewing.

---

### 22. TASK-308 — Claude Sonnet for prospect-facing copy, billed in dollars

- **Branch:** qwen-worker-4-r9-task280 @ `cdffd0a2d3bab2bea4d7a35373876fce93cc97fe`
- **Shared with:** TASK-280, TASK-315 (same branch)
- **Merge base:** `bd2d2432c` (significantly older)
- **Purpose:** Wire Anthropic Claude Sonnet as the provider for prospect-facing copy, with dollar billing.

**Files changed (13):**
- `docs/REVERSE-RECONCILIATION-2026-09-25.md`
- `docs/qwen-tasks/REVIEW/TASK-280-*.md`, `TASK-308-*.md`, `TASK-315-*.md`
- `scripts/reverse_reconcile.py`
- `src/providers/anthropic.py` (new)
- `src/spendledger.py` (modified)
- `tests/base.py` (modified)
- `tests/fixtures/cassettes/anthropic.json` (new)
- `tests/test_a_reply_stops_the_other_channel.py` (new)
- `tests/test_anthropic.py` (new)
- `tests/test_invariants.py` (modified)
- `tests/test_reverse_reconciliation_is_exhaustive.py` (new)

**Commits (10):** Covers TASK-280, 308, 315. TASK-308-specific:
```
30b2d796c TASK-308: REVIEW - 37 tests pass, acceptance passes, result block filled
2478bf357 TASK-308: Anthropic provider for prospect-facing copy, dollar-ledgered
```

**Tests:** `tests/test_anthropic.py` — new. 37 tests reported.

**Master overlap (6 files):**
- `docs/REVERSE-RECONCILIATION-2026-09-25.md`
- `scripts/reverse_reconcile.py`
- `src/spendledger.py`
- `tests/base.py`
- `tests/test_a_reply_stops_the_other_channel.py`
- `tests/test_reverse_reconciliation_is_exhaustive.py`

**Cross-branch conflicts:**
- `tests/base.py` — also touched by TASK-292/295 (ab2a6ff)

**Disposition: CANDIDATE** — New Anthropic provider module with tests. The spendledger.py and tests/base.py overlaps need resolution. 37 tests reported. Depends on TASK-309 (spend ledger unit column) which is NOT in this batch.

---

### 23. TASK-310 — Every APPROVED file feeds work/training/

- **Branch:** qwen-worker-11-r9 @ `c392a8ba4f07208cff6d89ac53c230aa64f4a7d5`
- **Merge base:** `f69793008` (significantly older)
- **Purpose:** Wire the approval system so that every APPROVED file is automatically fed into the training set.

**Files changed (27):**
- `config/clients/productive/offers.yaml`
- Multiple task files and GLM reviews
- `scripts/pool_status.py`
- `src/offers.py`, `src/providers/bison.py`, `src/providers/heyreach.py`, `src/store.py`, `src/reviewapproval.py`, `src/training.py`
- 11 test files

**Commits (12):** Covers TASK-310, 328, 385, 428, 437, 448, 456. TASK-310-specific:
```
f18367e16 TASK-310: result block written, move to REVIEW
6f175797f TASK-310: every APPROVED file feeds work/training/
d8aa141f6 TASK-310: claim and move to RUNNING
```

**Tests:** `tests/test_training.py` — new. Plus 10 other test files modified.

**Master overlap (5 files):**
- `src/offers.py`
- `src/providers/bison.py`
- `src/store.py`
- `tests/test_an_offer_cannot_be_invented.py`
- `tests/test_changing_an_approved_fact_changes_the_output.py`

**Cross-branch conflicts:** None with other branches in this batch.

**Disposition: CANDIDATE** — The training pipeline wiring is a concrete, testable change. 5 files overlap with master but the core training.py module is new. 11 test files demonstrate thorough testing. The src/store.py and src/offers.py overlaps need resolution.

---

### 24. TASK-311 — The ingest drops the LinkedIn column, and the operational signal with it

- **Branch:** qwen-worker-r9-t391 @ `d4effa8d82c50fc4166fd6e6780f069d728eda00`
- **Shared with:** TASK-294, TASK-302 (same branch)
- **Merge base:** `6d2763289` (significantly older)
- **Purpose:** The ingest pipeline drops the LinkedIn column, losing an operational signal.

**Files changed:** Same 39 files as TASK-294/302. TASK-311-specific:
- `src/ingest.py` (modified to carry LinkedIn column)
- `tests/test_the_ingest_carries_linkedin.py` (new)

**Commits:** TASK-311-specific:
```
a6fe73fa4 TASK-311: move to REVIEW with result block
9bb2efbd6 TASK-311: the ingest carries the LinkedIn column onto contacts
```

**Tests:** `tests/test_the_ingest_carries_linkedin.py` — new test.

**Master overlap:** Same 27 files as TASK-294.

**Cross-branch conflicts:** Same as TASK-294.

**Disposition: CANDIDATE (with caveat)** — The LinkedIn column fix is a concrete, focused change. However, it lives on a 39-file mega-branch with 27 master overlaps. The `src/ingest.py` change and its test can be cherry-picked. The fix is simple and valuable.

---

### 25. TASK-312 — Implement stages A to H of the v2 copy engine

- **Branch:** qwen-worker-4-r59 @ `073e81e040a2eee5bd116f5b82113698b894887b`
- **Merge base:** `2bf7b8a57` (master HEAD)
- **Purpose:** Implement the v2 copy engine with stages A through H.

**Files changed (3):**
- `docs/qwen-tasks/DONE/TASK-312-*.md`
- `src/copyengine.py` (new)
- `tests/test_copyengine.py` (new)

**Commits (3):**
```
073e81e04 TASK-312: move to DONE with result block
d6f6572c8 TASK-312: v2 copy engine stages A-H, preview and tests
ff37882a1 TASK-312: claim and move to RUNNING
```

**Tests:** `tests/test_copyengine.py` — new test file.

**Master overlap:** NONE.

**Cross-branch conflicts:** None.

**Disposition: CANDIDATE** — Clean branch on master HEAD. New module with tests. No overlap with master. Focused, well-scoped implementation. The v2 copy engine is a new file with no dependencies on changed existing files.

---

### 26. TASK-313 — Audit the current state against ARCHITECTURE-UPGRADE-SPEC sections 3 to 12

- **Branch:** qwen-worker-9-r9 @ `f1b9c357c17f4b557cbdb06f68339c7343ef3e83`
- **Shared with:** TASK-290, TASK-305 (same branch)
- **Merge base:** `fc473844e` (significantly older)
- **Purpose:** Audit the current codebase state against the architecture upgrade specification.

**Files changed:** Same 62 files as TASK-290/305. TASK-313-specific:
- `docs/qwen-tasks/DONE/TASK-313-*.md`

**Commits:** TASK-313-specific:
```
bb61d9dd7 TASK-313: record final commit SHA in result block
d6d99f19c TASK-313 audit: current state vs ARCHITECTURE-UPGRADE-SPEC sections 3-12
```

**Tests:** None specific to TASK-313 (audit/finding task).

**Master overlap:** 34 files (same as TASK-290/305).

**Cross-branch conflicts:** Same as TASK-290/305.

**Disposition: STALE** — This is an investigation/audit task. The audit result is in the task file's result block. The 62-file mega-branch has 34 master overlaps. The audit findings may be outdated given master's movement. The result block is the artifact; the branch itself adds nothing integrable for this task.

---

### 27. TASK-314 — Find exactly where the HeyReach steps are lost, and pin it

- **Branch:** qwen-worker-11-task314 @ `ddc0bc816fed25b327cbe070d0597ba03ae2b67e`
- **Shared with:** TASK-296 (same branch)
- **Merge base:** `a1df8aeaf` (significantly older)
- **Purpose:** Trace and pin exactly where HeyReach cadence steps are silently dropped.

**Files changed:** Same 21 files as TASK-296. TASK-314-specific:
- `docs/qwen-tasks/DONE/TASK-314-*.md`
- `docs/qwen-tasks/TODO/TASK-314-*.md`
- `tests/test_no_cadence_step_is_silently_dropped.py` (new regression test)

**Commits:** TASK-314-specific:
```
ddc0bc816 TASK-314: move to DONE
038cae462 TASK-314: update commit SHA and remote URL
fbed12f15 TASK-314: regression test for silently dropped cadence steps
```

**Tests:** `tests/test_no_cadence_step_is_silently_dropped.py` — new regression test.

**Master overlap:** Same 6 files as TASK-296.

**Cross-branch conflicts:** Same as TASK-296.

**Disposition: CANDIDATE** — The regression test for silently dropped cadence steps is a concrete, valuable artifact. The finding (where steps are lost) is pinned. 6 files overlap with master. The test file can be cherry-picked even if the full branch needs reconciliation.

---

### 28. TASK-315 — The cross-channel stop, both directions, tested

- **Branch:** qwen-worker-4-r9-task280 @ `cdffd0a2d3bab2bea4d7a35373876fce93cc97fe`
- **Shared with:** TASK-280, TASK-308 (same branch)
- **Merge base:** `bd2d2432c` (significantly older)
- **Purpose:** Implement and test the cross-channel stop rule in both directions (email stop halts LinkedIn, and vice versa).

**Files changed:** Same 13 files as TASK-308/280. TASK-315-specific:
- `docs/qwen-tasks/REVIEW/TASK-315-*.md`
- `tests/test_a_reply_stops_the_other_channel.py` (new — 36 synthetic tests)
- `tests/test_reverse_reconciliation_is_exhaustive.py` (new)

**Commits:** TASK-315-specific:
```
cc4daa819 TASK-315: move to REVIEW with final commit SHA 10932cae
10932cae1 TASK-315: the cross-channel stop, both directions, 36 synthetic tests
```

**Tests:** 2 test files — `test_a_reply_stops_the_other_channel.py` (36 tests), `test_reverse_reconciliation_is_exhaustive.py`.

**Master overlap:** Same 6 files as TASK-308.

**Cross-branch conflicts:**
- `tests/base.py` — also touched by TASK-292/295 (ab2a6ff)

**Disposition: CANDIDATE** — 36 synthetic tests for the cross-channel stop is a substantial test artifact. The bidirectional stop rule is a concrete, testable safety property. 6 files overlap with master. The test files and the cross-channel logic are valuable.

---

## Summary Table

| # | Task | SHA | Files | Tests | Master Overlap | Cross-branch | Disposition |
|---|------|-----|-------|-------|----------------|--------------|-------------|
| 1 | TASK-281 | a59e5f9 | 35 | 1 | NONE | None | **CANDIDATE** |
| 2 | TASK-283 | af48369 | 35 | 0 | NONE | None | **CANDIDATE** |
| 3 | TASK-284 | a520841 | 10 | 4 | 7 files | None | **STALE** |
| 4 | TASK-285 | c8a62f4 | 38 | 9 | 11 files | bisonfactory, enrich | **REJECT** |
| 5 | TASK-286 | a67999e | 4 | 0 | NONE | None | **STALE** |
| 6 | TASK-287 | 8d98cb7 | 4 | 1 | 2 files | None | **CANDIDATE** |
| 7 | TASK-288 | 357c1ff | 3 | 1 | NONE | None | **CANDIDATE** |
| 8 | TASK-289 | 9154d87 | 3 | 0 | 1 file | None | **STALE** |
| 9 | TASK-290 | f1b9c35 | 62 | 1+ | 34 files | None | **REJECT** |
| 10 | TASK-292 | ab2a6ff | 28 | 2 | NONE | tests/base.py | **CANDIDATE** |
| 11 | TASK-293 | a59e5f9 | 3* | 1 | NONE | None | **CANDIDATE** |
| 12 | TASK-294 | d4effa8 | 39 | 4 | 27 files | None | **REJECT** |
| 13 | TASK-295 | ab2a6ff | 28 | 2 | NONE | tests/base.py | **CANDIDATE** |
| 14 | TASK-296 | ddc0bc8 | 21 | 3 | 6 files | bisonfactory | **CANDIDATE** |
| 15 | TASK-298 | af48369 | 3* | 0 | NONE | None | **STALE** |
| 16 | TASK-301 | 24df89c | 5 | 1 | NONE | None | **CANDIDATE** |
| 17 | TASK-302 | d4effa8 | 39† | 0 | 27 files | None | **REJECT** |
| 18 | TASK-303 | 53cd306 | 3 | 0 | NONE | None | **REJECT** |
| 19 | TASK-304 | 1a82ed6 | 6 | 2 | NONE | None | **CANDIDATE** |
| 20 | TASK-305 | f1b9c35 | 4* | 1 | 34 files | None | **CANDIDATE** |
| 21 | TASK-307 | 2ee0940 | 6 | 1 | 2 files | enrich.py | **CANDIDATE** |
| 22 | TASK-308 | cdffd0a | 5* | 1 | 6 files | tests/base.py | **CANDIDATE** |
| 23 | TASK-310 | c392a8b | 27 | 11 | 5 files | None | **CANDIDATE** |
| 24 | TASK-311 | d4effa8 | 2* | 1 | 27 files | None | **CANDIDATE** |
| 25 | TASK-312 | 073e81e | 3 | 1 | NONE | None | **CANDIDATE** |
| 26 | TASK-313 | f1b9c35 | 1* | 0 | 34 files | None | **STALE** |
| 27 | TASK-314 | ddc0bc8 | 3* | 1 | 6 files | bisonfactory | **CANDIDATE** |
| 28 | TASK-315 | cdffd0a | 3* | 2 | 6 files | tests/base.py | **CANDIDATE** |

*Files marked with `*` are the task-specific subset of a shared branch.
†TASK-302 was BLOCKED — no code artifact.

## Disposition Summary

- **CANDIDATE:** 18 tasks (281, 283, 287, 288, 292, 293, 295, 296, 301, 304, 305, 307, 308, 310, 311, 312, 314, 315)
- **STALE:** 5 tasks (284, 286, 289, 298, 313)
- **REJECT:** 5 tasks (285, 290, 294, 302, 303)

## Key Risks for Integration

1. **Mega-branches:** TASK-285 (38 files), TASK-290 (62 files), TASK-294 (39 files) cannot be merged as units. Individual files need cherry-picking.
2. **Cross-branch overlaps:** `src/bisonfactory.py` (TASK-285 + TASK-296/314), `src/enrich.py` (TASK-285 + TASK-307), `tests/base.py` (TASK-292/295 + TASK-308/315) need coordinated merge.
3. **Master drift:** TASK-284, TASK-294/302/311, TASK-296/314 have significant master drift (6-27 overlapping files).
4. **Shared branches:** 7 branches serve multiple tasks. Merging one task's changes may bring unintended changes from co-tenants.
5. **BLOCKED tasks:** TASK-302 and TASK-303 were explicitly BLOCKED by workers and have no completable artifact.
