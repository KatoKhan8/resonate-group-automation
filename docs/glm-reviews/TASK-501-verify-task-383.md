# TASK-501 — Independent Verification of TASK-383 (GLM Checkpoint A)

**Reviewed branch HEAD SHA:** `d0432a8945acc1070bc07d952776ad679e7c755c`
**Branch:** `origin/qwen-worker-5-r9` (has since moved to `0e1331b1`; reviewed at the SHA named in the task file, per protocol)
**Review date:** 2026-09-29
**Reviewer:** Qwen (this session), independent of the original TASK-383 author
**Worktree:** `.qwen/worktrees/glm-501` (detached HEAD at `d0432a89`)
**Method:** Read-only grep/import trace, diff analysis, file existence checks

---

## Summary

TASK-383's review document (`docs/glm-reviews/checkpoint-a-0077c76e.md`, commit `edf9eee2`) is **accurate and well-evidenced**. Every one of its seven control dispositions was independently reproduced. All three new findings (A, B, C) were confirmed. The central defect — a closed wiring loop where five skills feed `generate_campaign.py` which has zero production callers — is real and remains the live blocker.

**Disposition: MERGE the review document. It is a correct, valuable artifact.**

---

## Control-by-Control Verification

### Control 1: One production entrypoint — FAILS ✓ CONFIRMED

**TASK-383 claim:** `generate_campaign.py` has zero production callers; only `generate.py` is reachable.

**Independent verification:**
```
grep -rn "generate_campaign" src/ scripts/
→ (empty, exit code 1)
```
Zero hits. No module in `src/` or `scripts/` imports or references `generate_campaign`. The only references are in four test files. `generate_campaign.py` has no `__main__` block.

**Verdict:** TASK-383 correct. Two entrypoints exist; only `generate.py` is production-reachable.

---

### Control 2: Second Brain has real consumer — FAILS ✓ CONFIRMED

**TASK-383 claim:** `secondbrain.for_task()` is called only from dead code (`copystages.business_context_for`, zero callers) and the disconnected `generate_campaign.py`.

**Independent verification:**
```
grep -rn "for_task" src/
→ src/copystages.py:127  (docstring)
→ src/copystages.py:133  (call inside business_context_for)
→ src/generate_campaign.py:133
→ src/secondbrain.py:8   (docstring)
→ src/secondbrain.py:205 (definition)

grep -rn "business_context_for" src/
→ src/copystages.py:124  (definition ONLY — zero callers)

grep -rn "secondbrain" src/generate.py
→ (empty, exit code 1)
```

**Verdict:** TASK-383 correct. The production entrypoint `generate.py` does not import `secondbrain` at all. The Second Brain has no path to a rendered message in production.

---

### Control 3: Canonical research = one authority — HOLDS ✓ CONFIRMED

**TASK-383 claim:** `rec["research"]` is the one store; `researchpack` has no production caller.

**Independent verification:**
```
grep -rn "researchpack\." src/
→ src/packfacts.py:83           (comment)
→ src/researchpack/pack.py:3-4  (docstring)
→ src/researchpack/__init__.py:7-8 (docstring)
```
All references are docstrings or comments. No production code imports or calls `researchpack`.

**Verdict:** TASK-383 correct.

---

### Control 4: Changed fact → changed artifact — UNVERIFIABLE ✓ AGREED

**TASK-383 claim:** The test proves the property for `generate_campaign` but not for the production chain.

**Independent verification:** The test file `tests/test_changing_an_approved_fact_changes_the_output.py` imports `generate_campaign` directly (line 26). Since `generate_campaign` has no production caller (Control 1), the test proves the property in isolation but not through the live chain.

**Verdict:** TASK-383 correct. This is genuinely unverifiable without runtime + wiring fix.

---

### Control 5: No `work/` dependency — HOLDS ✓ CONFIRMED

**Independent verification:**
```
grep -rn 'open(.*work/' src/
→ (empty)

grep -rn "import work\.|from work\." src/
→ (empty)
```

**Verdict:** TASK-383 correct.

---

### Control 6: No closed wiring loop — FAILS ✓ CONFIRMED

**TASK-383 claim:** All five `skills.load()` calls are in `generate_campaign.py` only, which has no external consumer.

**Independent verification:**
```
grep -rn "skills\.load" src/
→ src/generate_campaign.py:152  (campaign_strategy)
→ src/generate_campaign.py:228  (signal_verification)
→ src/generate_campaign.py:240  (account_research)
→ src/generate_campaign.py:301  (cold_email_writing)
→ src/generate_campaign.py:302  (linkedin_writing)
```
All five calls in `generate_campaign.py` only. And:
```
grep -rn "import skills|from.*skills" src/generate.py
→ (empty)

grep -rn "generate_campaign|skills|secondbrain|campaignstrategy|sequenceplan" src/generate.py
→ (empty)
```
`generate.py` imports NONE of the new modules. The closed loop is confirmed.

**Verdict:** TASK-383 correct. This is the central defect.

---

### Control 7: No cross-account research leakage — HOLDS ✓ CONFIRMED

**TASK-383 claim:** The join is exact identity (record_id + domain), not a text filter.

**Independent verification:** Read `bisonfactory.py:548-559` and `packfacts.py:68-128` at the target SHA:
- `bisonfactory.py:548`: `by_id = {record.get("id"): record for record in recs or []}` — keyed by exact record ID
- `bisonfactory.py:559`: `packfacts.pack_for(by_id.get(lead.get("record_id")))` — exact ID lookup; `None` if no match
- `packfacts.py:68-97`: `identity_of()` applies record_id check, then `same_site()` for exact host/domain match
- `packfacts.py:121`: `pack_for(rec)` reads `rec.get("research")` exclusively

**Verdict:** TASK-383 correct. The identity join is exact.

---

## New Findings Verification

### Finding A: `copystages.business_context_for()` is dead code ✓ CONFIRMED

```
grep -rn "business_context_for" src/
→ src/copystages.py:124  (definition ONLY)
```
Zero callers. Confirmed dead code.

### Finding B: Two parallel architectures ✓ CONFIRMED

`src/generate.py` (2153 lines, record-centric) and `src/generate_campaign.py` (410 lines, account-centric) are independent. Neither imports the other. Confirmed.

### Finding C: `secondbrain_sections` metadata is declarative only ✓ CONFIRMED

```
grep -rn "\.secondbrain_sections" src/
→ (empty)
```
The field is declared on the Skill dataclass (`src/skills/__init__.py:21`) and set in each skill definition, but never read by any code. Confirmed.

---

## Deletion Risk

`git diff master...d0432a89 --diff-filter=D --name-only` shows three deleted files:
- `docs/qwen-tasks/TODO/TASK-334-integrate-the-five-skills-from-their-branch.md`
- `docs/qwen-tasks/TODO/TASK-373-thread-the-client-into-the-spend-gate.md`
- `docs/qwen-tasks/TODO/TASK-375-the-entrypoint-and-its-five-skills-have-no-caller.md`

These are TODO task files that were moved to DONE (their DONE equivalents exist on master). This is normal task lifecycle, not a dangerous deletion. No source code or documentation is deleted.

**Deletion risk: NONE.**

---

## Scope Drift

**SIGNIFICANT.** The branch carries 19 commits and 57 changed files (+3,332 / -414 lines). TASK-383's own contribution is exactly one file: `docs/glm-reviews/checkpoint-a-0077c76e.md` (246 lines, commit `edf9eee2`).

The branch also integrates work from: TASK-334, TASK-367, TASK-373, TASK-374, TASK-375, TASK-376, TASK-377, TASK-387, plus new TODO tasks (379-390), scripts (`pool.sh`, `pool_watchdog.sh`, `bison_watch_loop.py`), and source changes (`campaignstrategy.py`, `generate.py`, `generate_campaign.py`, `llm.py`, `offers.py`, `slackconversation.py`).

This is a multi-task integration branch, not a single-task branch. The review document itself is clean and self-contained. Merging TASK-383's artifact would require cherry-picking commit `edf9eee2` alone, or extracting the single file.

---

## Test Falsifiability Assessment

Three test files on this branch test `generate_campaign.generate()` directly:
- `tests/test_the_entrypoint_actually_loads_its_skills.py` (TASK-375)
- `tests/test_the_entrypoint_refuses_at_a_client_ceiling.py` (TASK-373)
- `tests/test_the_entrypoint_is_the_only_generation_path.py` (TASK-369)

All three import `generate_campaign` and call `generate_campaign.generate()` with a `ScriptedModel`/`_FactAwareModel`/`_RecordingModel`. They prove properties of the disconnected entrypoint, not of the production chain. TASK-383 correctly identified this gap.

**Could these tests pass while the implementation is still wrong?** Yes — they pass today while `generate_campaign.py` has zero production callers. The tests prove the module works in isolation; they do not prove it is connected to production. This is exactly the "existence is not function" defect the repository has been bitten by.

---

## Overall Disposition

| Aspect | Verdict |
|---|---|
| Review document accuracy | **CORRECT** — all 7 controls, 3 findings independently verified |
| Evidence quality | **STRONG** — file:line references, reproducible grep commands |
| Central finding (closed loop) | **CONFIRMED** — remains the live blocker |
| Deletion risk | **NONE** |
| Scope drift | **SIGNIFICANT** — branch carries 18 other commits; review artifact is one clean file |
| Test falsifiability | **CORRECTLY ASSESSED** — tests prove isolation, not production wiring |

**RECOMMENDATION: MERGE**

The review document (`docs/glm-reviews/checkpoint-a-0077c76e.md`) is an accurate, well-evidenced independent review that correctly identifies the central architectural defect. It should be merged. The branch it sits on carries significant additional work that requires separate integration decisions — TASK-383's artifact should be cherry-picked (commit `edf9eee2`) rather than merged as part of the full branch.

The closed wiring loop finding remains the live blocker identified in TASK-137: `generate_campaign.py` must either replace `generate.py` as the production entrypoint, or `generate.py` must be updated to consume skills and Second Brain. Until that wiring decision is made and implemented, the five skills, the Second Brain, and the account-centric architecture are tested but disconnected.
