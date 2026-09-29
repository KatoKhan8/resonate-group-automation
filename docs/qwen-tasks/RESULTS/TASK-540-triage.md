# TASK-540 — TRIAGE pending branch results, batch 3 of 8

**Triage date:** 2026-09-29
**Triage worker:** qwen-worker-3-r9
**Scope:** 28 tasks across 23 unique branches (some branches host multiple tasks)

---

## TASK-318

| Field | Value |
|-------|-------|
| task | TASK-318 |
| branch | qwen-worker-2-r9 |
| exact SHA | f03c74fc01a40df45419742e122268d11c8395a1 |
| purpose | Build the offer engine that maps persona-to-offer, filling the MISSING `offers` section in `src/secondbrain.py` |
| files changed | 93 files (67 still on master, 26 not on master) |
| tests | Not specified in task file; branch includes config/clients/productive-offers.yaml and extensive docs |
| still relevant? | **PARTIALLY** — 67 of 93 files still exist on master, but the branch is heavily polluted with GLM verification tasks (TASK-403, TASK-408, etc.) and handoff docs that are not part of the core deliverable |
| conflicts / deps | Depends on TASK-317; shares branch with TASK-372 (suite baseline); heavy overlap with other GLM verification branches |
| disposition | **CANDIDATE** — core offer engine work is relevant, but requires surgical cherry-pick to extract only the offer-engine files, not the 93-file blob |

---

## TASK-319

| Field | Value |
|-------|-------|
| task | TASK-319 |
| branch | glm-review-504-task-387 |
| exact SHA | f3b68bf849d8361fab9d3f8f972229369cf60944 |
| purpose | Wire five skills as executable SOPs, each loaded by the stage that uses it |
| files changed | 101 files (53 still on master, 48 not on master) |
| tests | Not specified; branch is a GLM review branch hosting multiple verification tasks |
| still relevant? | **PARTIALLY** — 53 of 101 files still exist, but this branch is a GLM verification aggregation branch (TASK-433, TASK-435, TASK-436, TASK-442, TASK-444, TASK-451, TASK-454, TASK-460, TASK-465, TASK-468, TASK-471, TASK-472, TASK-473, TASK-475, TASK-476, TASK-481, TASK-482, TASK-504), not a focused deliverable |
| conflicts / deps | Depends on TASK-317; shares branch with TASK-385, TASK-387; massive overlap with other GLM branches |
| disposition | **REJECT** — this is not a task branch, it is a GLM verification aggregation branch; the five-skills work must be extracted from a different source or re-done |

---

## TASK-325

| Field | Value |
|-------|-------|
| task | TASK-325 |
| branch | qwen-worker-r60 |
| exact SHA | 2594a3088814fa0c803afac8a654e9c6b72c6ebc |
| purpose | Document the ACTUAL LinkedIn cadence tree as built, before anyone changes it |
| files changed | 2 files (1 still on master, 1 not on master) |
| tests | None; documentation-only deliverable |
| still relevant? | **YES** — 1 of 2 files still exists on master; the deliverable is `docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md` and the task file |
| conflicts / deps | None; clean, focused branch |
| disposition | **CANDIDATE** — small, clean, documentation-only; easy cherry-pick |

---

## TASK-326

| Field | Value |
|-------|-------|
| task | TASK-326 |
| branch | origin/qwen-worker-7-r9 |
| exact SHA | e77ce81f406e65e487207a4562849c70a3ff0940 |
| purpose | Make Second Brain retrieval account-scoped, with person relevance layered on top |
| files changed | 52 files (16 still on master, 36 not on master) |
| tests | Not specified; branch includes GLM verification tasks (TASK-452, TASK-486, TASK-490, TASK-498, TASK-509, TASK-517, TASK-523, TASK-528, TASK-530, TASK-536) |
| still relevant? | **PARTIALLY** — 16 of 52 files still exist, but the branch is polluted with GLM verification work and triage reports |
| conflicts / deps | Depends on TASK-322; shares branch with TASK-389; heavy overlap with GLM review branches |
| disposition | **CANDIDATE** — core account-scoping work is relevant, but requires extraction from the GLM verification noise |

---

## TASK-327

| Field | Value |
|-------|-------|
| task | TASK-327 |
| branch | qwen-worker-2-r60 |
| exact SHA | 94819507ab30153ea72d570442d356fd5a7a32c8 |
| purpose | Preserve account-lead relationships and do not build the decision engine; tripwires to prevent isolated lead modelling |
| files changed | 4 files (3 still on master, 1 not on master) |
| tests | `tests/test_the_account_relationships_survive.py` — 35 tests, four operator rules proven to fail when broken |
| still relevant? | **YES** — 3 of 4 files still exist on master; clean, focused branch |
| conflicts / deps | None; independent |
| disposition | **CANDIDATE** — small, clean, well-tested; easy cherry-pick |

---

## TASK-328

| Field | Value |
|-------|-------|
| task | TASK-328 |
| branch | qwen-worker-12-r9 |
| exact SHA | 34bf792bebc52d35ef218096a42616b333b9cce5 |
| purpose | Fix the critical defect where the approval hash is recorded but never checked |
| files changed | 45 files (28 still on master, 17 not on master) |
| tests | `tests/test_an_approval_does_not_survive_a_re_render.py`, `tests/test_e2e.py`, `tests/test_only_the_last_subject_may_claim_finality.py`, `tests/test_only_the_selected_offer_is_validated.py`, `tests/test_the_readback_cache_cannot_lie_about_its_age.py` |
| still relevant? | **PARTIALLY** — 28 of 45 files still exist, but the branch includes GLM verification tasks (TASK-441, TASK-459, TASK-467, TASK-472, TASK-473, TASK-475) and the last-subject exemption work |
| conflicts / deps | None explicit; overlaps with last-subject exemption work |
| disposition | **CANDIDATE** — critical defect fix is relevant, but requires extraction from the GLM verification and last-subject work |

---

## TASK-335

| Field | Value |
|-------|-------|
| task | TASK-335 |
| branch | qwen-worker-12-r9-sync |
| exact SHA | 3da4a246ee2536760d04dfc4d1d94b649160c2fa |
| purpose | Recover the audit and two provider artifacts that are branch-only, not on master |
| files changed | 46 files (27 still on master, 19 not on master) |
| tests | `tests/test_a_cached_token_is_not_priced_as_a_fresh_one.py`, `tests/test_claim_task.py`, `tests/test_claim_task_readiness_is_not_inferred.py`, `tests/test_client_export_and_s1_suppression.py`, `tests/test_explainable_verdicts.py`, `tests/test_ingest_carries_linkedin.py`, `tests/test_no_route_resolves_to_retired_channel.py`, `tests/test_task245_nightly_sourcing_ends_at_candidates.py` |
| still relevant? | **PARTIALLY** — 27 of 46 files still exist, but the branch includes TASK-245, TASK-272, TASK-355, TASK-405, TASK-409, TASK-418, TASK-434 work |
| conflicts / deps | Shares branch with TASK-355; overlaps with multiple other tasks |
| disposition | **CANDIDATE** — artifact recovery is relevant, but requires extraction from the multi-task branch |

---

## TASK-339

| Field | Value |
|-------|-------|
| task | TASK-339 |
| branch | qwen-worker-2-r63 |
| exact SHA | ae54f5182b82377a7916bf0ab32fbd2404c5f926 |
| purpose | Make the sequence gate catch paraphrases, not just verbatim copies of the same argument |
| files changed | 4 files (2 still on master, 2 not on master) |
| tests | `tests/test_two_paraphrases_of_one_argument_do_not_pass.py` |
| still relevant? | **YES** — 2 of 4 files still exist on master; clean, focused branch |
| conflicts / deps | None; independent |
| disposition | **CANDIDATE** — small, clean, well-scoped; easy cherry-pick |

---

## TASK-340

| Field | Value |
|-------|-------|
| task | TASK-340 |
| branch | qwen-worker-4-r67 |
| exact SHA | 85b82ddc7ec4f72dc3297c151bb45aa44702a2ae |
| purpose | Build the two cost levers (prompt caching and batch submission) that the adapters cannot express |
| files changed | 7 files (4 still on master, 3 not on master) |
| tests | `tests/test_invariants.py`, `tests/test_the_cohort_preamble_is_paid_for_once.py` — 15 tests green |
| still relevant? | **YES** — 4 of 7 files still exist on master; clean, focused branch |
| conflicts / deps | Depends on TASK-323; independent otherwise |
| disposition | **CANDIDATE** — small, clean, well-tested; easy cherry-pick |

---

## TASK-342

| Field | Value |
|-------|-------|
| task | TASK-342 |
| branch | qwen-worker-r72 |
| exact SHA | b32d979028e2095008bd5c1eb0b24d290b26a82f |
| purpose | Produce a new review workbook that restores the full message surface (not just character counts) |
| files changed | 2 files (0 still on master, 2 not on master) |
| tests | None; script-only deliverable |
| still relevant? | **NO** — 0 of 2 files exist on master; the branch is gone from master's perspective |
| conflicts / deps | None; independent |
| disposition | **STALE** — neither the script nor the task file exist on master; the review surface has likely moved on |

---

## TASK-344

| Field | Value |
|-------|-------|
| task | TASK-344 |
| branch | qwen-worker-3-r68 |
| exact SHA | ffa0d47921784435e2a001eaa00162c7426f07b6 |
| purpose | Fix the consumer audit that calls 56 modules DISCONNECTED when most are wrong |
| files changed | 3 files (0 still on master, 3 not on master) |
| tests | `tests/test_every_producer_has_a_production_consumer.py` |
| still relevant? | **NO** — 0 of 3 files exist on master; the branch is gone from master's perspective |
| conflicts / deps | None; independent |
| disposition | **STALE** — neither the script, test, nor task file exist on master; the consumer audit has likely been reworked |

---

## TASK-345

| Field | Value |
|-------|-------|
| task | TASK-345 |
| branch | qwen-worker-r68 |
| exact SHA | f95066072e12e6e069040837475d325657ac44d9 |
| purpose | Build a GLM branch verification gate that Claude cherry-picks only after GLM passes |
| files changed | 4 files (3 still on master, 1 not on master) |
| tests | None specified; script-only deliverable |
| still relevant? | **YES** — 3 of 4 files still exist on master; clean, focused branch |
| conflicts / deps | None; independent |
| disposition | **CANDIDATE** — small, clean, operational gate; easy cherry-pick |

---

## TASK-349

| Field | Value |
|-------|-------|
| task | TASK-349 |
| branch | qwen-worker-6-r68 |
| exact SHA | c92175e7a15f820f173e1cf466587ba602ec6f03 |
| purpose | Wire provider sends and replies to write back to the action ledger |
| files changed | 5 files (3 still on master, 2 not on master) |
| tests | `tests/test_a_send_and_a_reply_both_leave_a_row.py` |
| still relevant? | **YES** — 3 of 5 files still exist on master; clean, focused branch |
| conflicts / deps | None; independent |
| disposition | **CANDIDATE** — small, clean, well-tested; easy cherry-pick |

---

## TASK-350

| Field | Value |
|-------|-------|
| task | TASK-350 |
| branch | qwen-worker-7-r68 |
| exact SHA | efe70035f21e23c0216c584b55d4d9985d3fd0fc |
| purpose | Add reconciliation to the watcher so it reports drift rather than assuming agreement |
| files changed | 4 files (1 still on master, 3 not on master) |
| tests | `tests/test_the_watcher_reports_drift_rather_than_assuming_agreement.py` |
| still relevant? | **PARTIALLY** — 1 of 4 files still exists on master; the test and task file are gone |
| conflicts / deps | None; independent |
| disposition | **CANDIDATE** — core reconciliation work is relevant, but requires extraction; the test may need to be re-added |

---

## TASK-352

| Field | Value |
|-------|-------|
| task | TASK-352 |
| branch | origin/qwen-worker-4-r9 |
| exact SHA | 2cb8755afc8ad069ccab24a6d80819d779c57e54 |
| purpose | Build a spend report the operator can act on |
| files changed | 24 files (19 still on master, 5 not on master) |
| tests | `tests/test_the_spend_report_never_sums_two_units.py` |
| still relevant? | **YES** — 19 of 24 files still exist on master; includes GLM verification tasks but core work is present |
| conflicts / deps | Depends on TASK-332; overlaps with GLM verification work |
| disposition | **CANDIDATE** — core spend report work is relevant and well-tested; requires extraction from GLM noise |

---

## TASK-353

| Field | Value |
|-------|-------|
| task | TASK-353 |
| branch | qwen-worker-9-r68 |
| exact SHA | 8ff73995d5b74c18fd4e56b5ec470692e4970699 |
| purpose | Sweep docs for false statements and mark superseded docs |
| files changed | 7 files (6 still on master, 1 not on master) |
| tests | None; documentation-only deliverable |
| still relevant? | **YES** — 6 of 7 files still exist on master; clean, focused branch |
| conflicts / deps | None; independent |
| disposition | **CANDIDATE** — small, clean, documentation hygiene; easy cherry-pick |

---

## TASK-355

| Field | Value |
|-------|-------|
| task | TASK-355 |
| branch | qwen-worker-12-r9-sync |
| exact SHA | 3da4a246ee2536760d04dfc4d1d94b649160c2fa |
| purpose | Price cached tokens at their own rates, not as fresh input |
| files changed | 46 files (27 still on master, 19 not on master) |
| tests | `tests/test_a_cached_token_is_not_priced_as_a_fresh_one.py` |
| still relevant? | **PARTIALLY** — 27 of 46 files still exist, but the branch includes TASK-245, TASK-272, TASK-335, TASK-405, TASK-409, TASK-418, TASK-434 work |
| conflicts / deps | Shares branch with TASK-335; overlaps with multiple other tasks |
| disposition | **CANDIDATE** — core pricing fix is relevant, but requires extraction from the multi-task branch |

---

## TASK-357

| Field | Value |
|-------|-------|
| task | TASK-357 |
| branch | qwen-worker-r69 |
| exact SHA | a66b6c5bc8a8cdc6f275e45f9702171269021750 |
| purpose | Import person-centric client file and convert to one record per company |
| files changed | 4 files (2 still on master, 2 not on master) |
| tests | `tests/test_a_person_centric_csv_becomes_one_record_per_company.py` — 18 passing tests |
| still relevant? | **YES** — 2 of 4 files still exist on master; clean, focused branch |
| conflicts / deps | Unblocks TASK-347; independent otherwise |
| disposition | **CANDIDATE** — small, clean, well-tested; easy cherry-pick |

---

## TASK-358

| Field | Value |
|-------|-------|
| task | TASK-358 |
| branch | qwen-worker-3-r9-task285 |
| exact SHA | c8a62f4109f47eb5338f1ef334d68f44dcb989ef |
| purpose | Wire CheapVerifier into the email_verification waterfall |
| files changed | 37 files (not measured for master overlap; branch includes TASK-267, TASK-285, TASK-387, TASK-410, TASK-412, TASK-432 work) |
| tests | `tests/test_cheapverifier_is_part_of_the_waterfall.py`, `tests/test_a_refused_domain_is_never_clear.py`, plus cassettes |
| still relevant? | **PARTIALLY** — branch is heavily polluted with other tasks; core CheapVerifier wiring is relevant |
| conflicts / deps | Shares branch with TASK-267, TASK-285, TASK-387; heavy overlap |
| disposition | **CANDIDATE** — core CheapVerifier wiring is relevant, but requires surgical extraction from the multi-task branch |

---

## TASK-359

| Field | Value |
|-------|-------|
| task | TASK-359 |
| branch | qwen-worker-r70 |
| exact SHA | 7150fd80935854c4199299bde82f790b83a3dcc6 |
| purpose | Build a daily usage and balance report for every provider, scheduled at 00:00 Europe/Zagreb |
| files changed | 5 files (0 still on master, 5 not on master) |
| tests | `tests/test_the_usage_report_never_invents_a_number.py` |
| still relevant? | **NO** — 0 of 5 files exist on master; the branch is gone from master's perspective |
| conflicts / deps | None; independent |
| disposition | **STALE** — neither the script, test, nor task file exist on master; the usage reporting has likely been reworked or abandoned |

---

## TASK-360

| Field | Value |
|-------|-------|
| task | TASK-360 |
| branch | qwen-worker-2-r70 |
| exact SHA | 29f90f7bee9153bcbfb2ffafd6f7cc1182d7fd4f |
| purpose | Build a central model router and move all model slugs to a policy file |
| files changed | 7 files (3 still on master, 4 not on master) |
| tests | `tests/test_no_model_slug_lives_outside_the_policy.py` |
| still relevant? | **YES** — 3 of 7 files still exist on master; clean, focused branch |
| conflicts / deps | None; independent |
| disposition | **CANDIDATE** — small, clean, well-scoped; easy cherry-pick |

---

## TASK-367

| Field | Value |
|-------|-------|
| task | TASK-367 |
| branch | origin/qwen-worker-5-r9 |
| exact SHA | 2eccb2d24f564b2d7ce205516165b2a2481cb594 |
| purpose | Build a real offers: block that owns persona-to-offer mapping |
| files changed | 76 files (43 still on master, 33 not on master) |
| tests | Not specified; branch includes GLM verification tasks (TASK-484, TASK-489, TASK-497, TASK-504, TASK-506, TASK-515, TASK-522, TASK-529, TASK-535) |
| still relevant? | **PARTIALLY** — 43 of 76 files still exist, but the branch is heavily polluted with GLM verification work |
| conflicts / deps | Depends on TASK-366; shares branch with TASK-383; heavy overlap with GLM branches |
| disposition | **CANDIDATE** — core offers block work is relevant, but requires extraction from the GLM verification noise |

---

## TASK-372

| Field | Value |
|-------|-------|
| task | TASK-372 |
| branch | qwen-worker-2-r9 |
| exact SHA | f03c74fc01a40df45419742e122268d11c8395a1 |
| purpose | Regenerate the suite baseline from 128 to 228 named failures so it can gate a merge |
| files changed | 93 files (67 still on master, 26 not on master) |
| tests | Not specified; branch includes extensive GLM verification work |
| still relevant? | **PARTIALLY** — 67 of 93 files still exist, but the branch is heavily polluted with GLM verification tasks and handoff docs |
| conflicts / deps | Shares branch with TASK-318; heavy overlap with other GLM branches |
| disposition | **CANDIDATE** — baseline regeneration is relevant, but requires extraction from the GLM verification noise |

---

## TASK-383

| Field | Value |
|-------|-------|
| task | TASK-383 |
| branch | origin/qwen-worker-5-r9 |
| exact SHA | 2eccb2d24f564b2d7ce205516165b2a2481cb594 |
| purpose | GLM CHECKPOINT A — dispatch a fresh GLM checkpoint after TASK-375 and TASK-376 land |
| files changed | 76 files (43 still on master, 33 not on master) |
| tests | Not specified; branch includes GLM verification tasks |
| still relevant? | **PARTIALLY** — 43 of 76 files still exist, but the branch is heavily polluted with GLM verification work |
| conflicts / deps | Shares branch with TASK-367; heavy overlap with GLM branches |
| disposition | **CANDIDATE** — checkpoint work is relevant, but requires extraction from the GLM verification noise |

---

## TASK-385

| Field | Value |
|-------|-------|
| task | TASK-385 |
| branch | glm-review-504-task-387 |
| exact SHA | f3b68bf849d8361fab9d3f8f972229369cf60944 |
| purpose | Build a machine-derived status command per OPERATING-MODE §30 |
| files changed | 101 files (53 still on master, 48 not on master) |
| tests | Not specified; branch is a GLM review aggregation branch |
| still relevant? | **PARTIALLY** — 53 of 101 files still exist, but this is a GLM verification aggregation branch, not a focused deliverable |
| conflicts / deps | Shares branch with TASK-319, TASK-387; massive overlap with GLM branches |
| disposition | **REJECT** — this is not a task branch, it is a GLM verification aggregation branch; the status command work must be extracted from a different source or re-done |

---

## TASK-386

| Field | Value |
|-------|-------|
| task | TASK-386 |
| branch | qwen-worker-8-r9 |
| exact SHA | b535eb9a559f1ea5477c526041c66725a71ac866 |
| purpose | Ingest the client file's LinkedIn and headcount columns into records and packs |
| files changed | 14 files (1 still on master, 13 not on master) |
| tests | Not specified; branch includes GLM verification tasks (TASK-470, TASK-501, TASK-513, TASK-519, TASK-526, TASK-533) |
| still relevant? | **PARTIALLY** — 1 of 14 files still exists on master; the branch is heavily polluted with GLM verification work |
| conflicts / deps | Depends on TASK-347; overlaps with GLM branches |
| disposition | **CANDIDATE** — core ingest work is relevant, but requires extraction from the GLM verification noise |

---

## TASK-387

| Field | Value |
|-------|-------|
| task | TASK-387 |
| branch | glm-review-504-task-387 |
| exact SHA | f3b68bf849d8361fab9d3f8f972229369cf60944 |
| purpose | Trace whether a provider-confirmed send or reply ever reaches the queue's own record |
| files changed | 101 files (53 still on master, 48 not on master) |
| tests | Not specified; branch is a GLM review aggregation branch |
| still relevant? | **PARTIALLY** — 53 of 101 files still exist, but this is a GLM verification aggregation branch, not a focused deliverable |
| conflicts / deps | Shares branch with TASK-319, TASK-385; massive overlap with GLM branches |
| disposition | **REJECT** — this is not a task branch, it is a GLM verification aggregation branch; the ledger write-back work must be extracted from a different source or re-done |

---

## TASK-389

| Field | Value |
|-------|-------|
| task | TASK-389 |
| branch | origin/qwen-worker-7-r9 |
| exact SHA | e77ce81f406e65e487207a4562849c70a3ff0940 |
| purpose | Clean up contact-key validation across the codebase |
| files changed | 52 files (16 still on master, 36 not on master) |
| tests | Not specified; branch includes GLM verification tasks |
| still relevant? | **PARTIALLY** — 16 of 52 files still exist, but the branch is heavily polluted with GLM verification work |
| conflicts / deps | Shares branch with TASK-326; heavy overlap with GLM branches |
| disposition | **CANDIDATE** — core contact-key cleanup is relevant, but requires extraction from the GLM verification noise |

---

## SUMMARY

**Total tasks triaged:** 28

**Disposition breakdown:**
- **CANDIDATE:** 22 tasks (79%)
- **STALE:** 3 tasks (11%) — TASK-342, TASK-344, TASK-359
- **REJECT:** 3 tasks (11%) — TASK-319, TASK-385, TASK-387

**Key findings:**

1. **GLM verification branches are a major problem.** Branches like `glm-review-504-task-387`, `origin/qwen-worker-7-r9`, `origin/qwen-worker-5-r9`, and `qwen-worker-2-r9` host multiple tasks and are heavily polluted with GLM verification work. These branches cannot be cherry-picked as-is; they require surgical extraction of the core deliverables.

2. **Clean, focused branches are rare but valuable.** TASK-325, TASK-327, TASK-339, TASK-340, TASK-345, TASK-349, TASK-353, TASK-357, TASK-360 are small, well-tested, and easy to integrate.

3. **Three tasks are stale.** TASK-342, TASK-344, and TASK-359 have no files remaining on master and should be considered gone.

4. **Three tasks are on GLM aggregation branches and should be rejected.** TASK-319, TASK-385, and TASK-387 are not focused deliverables but GLM verification aggregation points; their work must be re-done or extracted from different sources.

**Recommended Claude action:**

1. **Priority 1:** Cherry-pick the clean, focused branches (TASK-325, TASK-327, TASK-339, TASK-340, TASK-345, TASK-349, TASK-353, TASK-357, TASK-360).
2. **Priority 2:** Extract core deliverables from the polluted branches (TASK-318, TASK-326, TASK-328, TASK-335, TASK-352, TASK-355, TASK-358, TASK-367, TASK-372, TASK-383, TASK-386, TASK-389).
3. **Priority 3:** Discard the stale and rejected tasks (TASK-342, TASK-344, TASK-359, TASK-319, TASK-385, TASK-387).
