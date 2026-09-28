# TASK-518 — Independent GLM verification of TASK-410's verdict on TASK-400

**Reviewing:** TASK-410's GLM verdict (SAFE TO MERGE) on TASK-400
**TASK-410's artifact:** inline result block in `docs/qwen-tasks/REVIEW/TASK-410-glm-verify-task-400-critical-path.md`
**TASK-410 reviewed:** `origin/qwen-worker-r9` at SHA `3487aeee4f24c5281e8b9f125deb83c643eb2070`
**This verdict verified against:** SHA `3487aeee` (same SHA TASK-410 named) AND branch `origin/qwen-worker-3-r9-task285` at HEAD SHA `c8a62f4109f47eb5338f1ef334d68f44dcb989ef` (the branch carrying TASK-410's verdict)
**Method:** Isolated worktree at `3487aeee`, independent code inspection, full test execution, mutation analysis

---

## Verdict on TASK-410's verdict: SUBSTANTIALLY CORRECT, four findings confirmed

TASK-410's SAFE TO MERGE disposition is **correct on the evidence**. All seven controls were genuinely checked, the SHA was correctly named, and the four non-blocking findings are real. However, TASK-410's review has three methodological weaknesses I independently reproduced, plus one finding it under-reported.

---

## Control-by-control independent verification

### Control 1 — One entrypoint: CONFIRMED PASS

**TASK-410's claim:** `src/generate.py:main()` → `run()` → `_generate_via_campaign()` → `generate_campaign.generate()`. No `isinstance(model, ScriptedModel)`. ConfigError raises.

**My reproduction:**
- `main()` at line 2133 calls `run()` at line 2170. ✓
- `run()` at line 2076 calls `_generate_via_campaign()`. ✓
- `_generate_via_campaign()` at line 2039 calls `generate_campaign.generate()`. ✓
- `grep "isinstance.*ScriptedModel"` on entire `generate.py`: zero hits. ✓
- `ConfigError` at line 2005 raises `CampaignPipelineError` naming the client. ✓

**Chain is unbroken and unambiguous.**

### Control 2 — Second Brain has a real consumer: CONFIRMED PASS

**TASK-410's claim:** `_load_verified_facts()` → `secondbrain.for_task()` → `sb_facts` → `_format_br_context()` → hypothesis prompt.

**My reproduction:**
- `generate_campaign.generate()` line 116: `sb_facts = _load_verified_facts(client_name)`. ✓
- `_load_verified_facts` line 190: `secondbrain.for_task("campaign_strategy", client_name)`. ✓
- Line 135: `second_brain_facts=sb_facts` passed to strategy. ✓
- Line 318: `br_context = _format_br_context(sb_facts)` in `_process_contact`. ✓
- The context flows into the hypothesis prompt via `_format_br_context`. ✓

**This is through the real entrypoint.** The test `test_dry_run_ran_full_pipeline` asserts `len(model.calls) > 3`, proving multiple stages ran including Second Brain.

### Control 3 — Canonical research authority unchanged: CONFIRMED PASS

**My reproduction:**
- `_generate_via_campaign` line 2017: `(rec.get("research") or {}).get("sources")`. ✓
- `generate_campaign.py` receives sources via `account["sources"]` parameter. ✓
- `grep "work/"` on `generate_campaign.py`: only docstring comments (lines 14, 218). ✓
- `grep "work/"` on `generate.py`: zero hits. ✓
- No second research store introduced.

### Control 4 — Changing a fact changes the artifact: CONFIRMED PASS with caveat

**TASK-410's claim:** Code path is correct but test calls `generate_campaign.generate()` directly.

**My reproduction:**
- `test_change_fact_changes_output` changes `account_b["sources"]` to include "FINTECH". ✓
- `_CampaignModel._extract_facts()` returns different facts when prompt contains "fintech". ✓
- Email bodies differ: `em1_a != em1_b`. ✓
- **Caveat confirmed:** The test calls `generate_campaign.generate()` directly, NOT through `_generate_via_campaign()` or `run()`. The code path is correct but the test does not prove the mutation propagates through the bridge from `generate.py`. This is a test coverage gap, not a wiring defect.

### Control 5 — No critical logic depends on gitignored work/: CONFIRMED PASS

**My reproduction:** Identical to TASK-410. `work/` appears only in docstring comments.

### Control 6 — No closed wiring loop: CONFIRMED PARTIAL PASS

**TASK-410's claim:** `linkedin_writing` loaded but `.procedure` never consumed.

**My reproduction:**
- Line 364: `linkedin_skill = skills.load("linkedin_writing")`. ✓
- Line 365: `writer_system = email_skill.procedure`. ✓
- `linkedin_skill` is never referenced again in the function. ✓
- The comment at lines 360-362 says "Both share WRITER_SYSTEM; the entrypoint loads both so neither is disconnected" — but loading without consuming is existence-not-function, exactly as TASK-410 said.

**This is a real dead load.** The skill is imported and assigned but its `.procedure` never enters any prompt.

### Control 7 — No cross-account research leakage: CONFIRMED PASS

**My reproduction:**
- `packfacts.identity_of()` line 78: exact-identity join. ✓
- Lines 97-99: `record_id` exact match with string comparison. ✓
- Line 103: `same_site()` domain match. ✓
- In `generate_campaign.py`, sources come per-account from `account.get("sources")`. ✓
- No cross-account join or shared research store.

---

## Three REWORK 2 defects: ALL CONFIRMED FIXED

1. **ScriptedModel branch:** `grep "isinstance.*ScriptedModel"` on `_generate_via_campaign` returns nothing. ✓
2. **ConfigError raises:** Line 2005-2006 raises `CampaignPipelineError` naming the client. ✓
3. **Provider refusal:** All four boundary points verified independently:
   - `bisonfactory._ensure_leads:1720` → `refuse_dry_run_records` ✓
   - `providers/bison.resume_campaign:1914` → `refuse_dry_run_records` ✓
   - `heyreachfactory.ensure_leads:1333` → `refuse_dry_run_records` ✓
   - `providers/heyreach.activate_campaign:1729` → `refuse_dry_run_records` ✓

---

## Safety gates: ALL CONFIRMED RUNNING

- `copylint.check_batch()` at `generate_campaign.py:423`. ✓
- `sequencegate.check()` at `generate_campaign.py:436`. ✓
- `_check_offers()` → `NotApproved` at `generate_campaign.py:113`. ✓

---

## Test execution: 25/25 GREEN

Ran `python -m unittest tests.test_task400_rework2 -v` in isolated worktree at SHA `3487aeee`. All 25 tests pass in 0.955s.

---

## TASK-410's findings I independently confirmed

### Finding 1: `src/run.py` parallel entrypoint — CONFIRMED

`src/run.py:stage_generate()` (line 274) calls `generate.plan()` and `generate.generate_record()`, bypassing the campaign pipeline entirely. `python -m src.run` is a live CLI entrypoint (line 479: `main()`, line 572: `if __name__ == "__main__"`). Not in TASK-400's scope, but a real parallel path.

### Finding 2: `linkedin_writing` dead load — CONFIRMED

See Control 6 above. Loaded at line 364, never consumed.

### Finding 3: Source inspection tests — CONFIRMED AS WEAKNESS

Mutation test B (`test_mutation_b_scripted_model_branch`) and all four provider refusal tests (Acceptance 4, lines for heyreach/bison ensure_leads/activate/resume) use `inspect.getsource()` to assert strings appear in source code. Per QWEN.md: "Test behaviour, not the text of the source." These tests prove the call exists in the source at test time but would not catch:
- A conditional that skips the call at runtime
- A refactoring that moves the call behind an unreachable branch
- A different module being imported under the same name

The behavioral tests (acceptances 1-3, mutation_a, mutation_c) are strong. The source-inspection tests are a lower bar.

### Finding 4: `test_change_fact_changes_output` bypasses the real entrypoint — CONFIRMED

The test calls `generate_campaign.generate()` directly. It does not drive through `generate.run()` or `_generate_via_campaign()`. The mutation is real but the test does not prove the fact flows through the bridge.

---

## Additional finding TASK-410 under-reported

### Finding 5: Older ConfigError handlers silently swallow the error

TASK-410's correction from Claude specifically asked about `_generate_via_campaign`, and there ConfigError correctly raises. But three OTHER ConfigError handlers in `generate.py` silently swallow the error:

- **Line 273:** `except clients.ConfigError: client = None` — in `steps_for` related code
- **Line 745:** `except clients.ConfigError: return "template"` — in LinkedIn mode code
- **Line 1933:** `except clients.ConfigError: config = None` — in variant generation code

These are NOT in `_generate_via_campaign` and NOT on the TASK-400 campaign pipeline path. They are in older code paths that `src/run.py`'s `stage_generate` still reaches. TASK-410 did not mention these. They are not blocking for TASK-400 but represent the same defect pattern (silent ConfigError swallowing) that the REWORK 2 fixes addressed in the campaign path.

---

## Deletion risk assessment

`git diff master...c8a62f4109f47eb5338f1ef334d68f44dcb989ef --stat --diff-filter=D`:
Three task files deleted (moved between stages):
- `docs/qwen-tasks/REVIEW/TASK-387-provider-write-back...md` (59 lines)
- `docs/qwen-tasks/TODO/TASK-410-glm-verify-task-400...md` (108 lines)
- `docs/qwen-tasks/TODO/TASK-412-suppression-list-audit.md` (17 lines)

These are task lifecycle moves (TODO→REVIEW, REVIEW→DONE), not code deletions. **No production code is deleted.**

---

## Scope drift

The branch `origin/qwen-worker-3-r9-task285` at `c8a62f41` carries work from multiple tasks: TASK-285 (collision walk), TASK-267 (LLM tiebreaker), TASK-358 (CheapVerifier), TASK-432 (GLM verdict), TASK-410 (this verdict), TASK-412 (suppression audit), TASK-387 (provider writeback), and TASK-285's associated code changes (cheapverifier module, collision walk script, tiebreaker script, tests).

TASK-410's own contribution to this branch is ONLY the verdict text in the task file. The code it reviewed (TASK-400) lives on `origin/qwen-worker-r9` at `3487aeee`. **Cherry-picking TASK-410's verdict is trivial — it is a single markdown file.**

---

## Disposition

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | `src/run.py` parallel entrypoint bypasses campaign pipeline | EXISTING TASK — not TASK-400's scope, tracked separately |
| 2 | `linkedin_writing` skill loaded but `.procedure` never consumed | NEW TASK — dead load, existence-not-function |
| 3 | Five tests use `inspect.getsource()` instead of behavioral assertions | ACCEPTED DEFERRED RISK — weaker proof but not wrong; behavioral tests cover the same controls |
| 4 | `test_change_fact_changes_output` does not drive through real entrypoint | ACCEPTED DEFERRED RISK — code path is correct, test coverage gap |
| 5 | Three older ConfigError handlers silently swallow the error | EXISTING TASK — same pattern as REWORK 2 fixed in campaign path; older code paths still vulnerable |

---

## Recommendation: MERGE with cherry-pick

**TASK-410's verdict is correct.** The seven controls pass, the three REWORK 2 defects are genuinely fixed, safety gates are intact, and 25/25 tests pass. The four findings are real but non-blocking.

The verdict should be cherry-picked from `origin/qwen-worker-3-r9-task285` at `c8a62f41` — it is a single markdown file (`docs/qwen-tasks/REVIEW/TASK-410-glm-verify-task-400-critical-path.md`) with no code dependencies.

**TASK-400's code** lives on `origin/qwen-worker-r9` at `3487aeee` and is a separate merge decision.

---

## What I could not verify

- **Runtime proof:** I verified code paths statically and ran the test suite. I did not run `python -m src.generate --live` against a real model or real provider. This is read-only review per the protocol.
- **TASK-400's current state:** TASK-400 has been "BLOCKED TWICE by Claude" per the correction note. The second rework may have produced a `task400-rework3` branch. I reviewed the SHA TASK-410 named (`3487aeee`), which is the artifact TASK-410's verdict is about. If TASK-400 has since been reworked again, that is a separate review.

---

**VERIFIED AGAINST:** SHA `3487aeee4f24c5281e8b9f125deb83c643eb2070` (TASK-400 code as reviewed by TASK-410) and SHA `c8a62f4109f47eb5338f1ef334d68f44dcb989ef` (TASK-410's verdict on `origin/qwen-worker-3-r9-task285`)
**TESTS:** 25/25 green
**RECOMMENDATION:** MERGE (TASK-410 verdict) with cherry-pick
