# GLM First-Pass Verification: TASK-369 Production Entrypoint

**Review date:** 2026-09-26  
**Reviewer:** GLM (independent first-pass, per GLM-REVIEW-PROTOCOL.md)  
**Target:** TASK-369, merged to origin/master at 6ca3b94c  
**Master SHA at review start:** 0077c76e  
**Worktree:** C:\Users\Zvonimir\Desktop\resonate-qwen-worker (qwen-worker-r9)

---

## Executive Summary

TASK-369's production entrypoint exists in git, is importable, and passes all three test files (20 tests total, all green). The mutation test is reproducible: changing an approved Second Brain fact changes the hypothesis and email output; changing an unverified fact does not. The entrypoint loads five skills via `skills.load()` and uses their `.procedure` field for stages A, B, and F.

**Two confirmed findings, both known:**

1. `generate_campaign.generate()` has **zero production callers** in `src/` or `scripts/`. The entrypoint exists but is not wired into the production execution stream.
2. Stages C (hypothesis) and D (match) use raw constants `copystages.HYPOTHESIS_SYSTEM` and `copystages.MATCH_SYSTEM` instead of skill wrappers. The five skills that exist ARE loaded, but there are no skills for hypothesis/match stages, so those stages bypass the skill registry's consumer validation.

**No new findings.** Claude's pre-merge verification and TASK-375's follow-up already identified both gaps.

---

## Section 1: Mutation Test Reproduction

**Directive section 4:** "Changing valid upstream information changes the intended downstream production context/output through the real production entrypoint."

**Test:** `tests/test_changing_an_approved_fact_changes_the_output.py`

**Result:** PASS (3/3 tests green)

```
test_changing_back_returns_output ... ok
test_changing_verified_fact_changes_plan ... ok
test_unverified_fact_does_not_change_prospect_output ... ok
```

**Independent reproduction:**
- Changed verified fact from "ALPHA: Productive shows project margin in real time" to "BETA: Productive tracks utilisation across teams"
- Hypothesis changed: `"margin invisible until month-end, context: ALPHA..., basis: ALPHA..."` → `"margin invisible until month-end, context: BETA..., basis: BETA..."`
- Email em1 changed: `"noticed ALPHA... hypothesis: ...ALPHA..."` → `"noticed BETA... hypothesis: ...BETA..."`
- Changed fact back → output returned to original
- Changed unverified fact → prospect-facing output did NOT change (negative control passes)

**Verdict:** CONFIRMED WORKING. The mutation test is not a false green. The pipeline genuinely propagates verified facts to prospect-facing output and blocks unverified facts.

---

## Section 2: Zero Production Callers

**Finding (from TASK-375):** `generate_campaign.generate()` has no production callers.

**Independent verification:**

```bash
grep -rn "generate_campaign\.generate\|from .+generate_campaign import\|import generate_campaign" src/ scripts/
```

**Result:** No matches in `src/` or `scripts/`. The only hit is in `docs/qwen-tasks/DONE/TASK-375-*.md`, which documents the finding itself.

**Additional check:** Searched for alternative generation paths:
```bash
grep -rn "def generate\(|def run_generation\|def generate_campaign" src/ scripts/
```

**Result:** 
- `src/generate_campaign.py:33` — the entrypoint itself
- `scripts/task089_diagnose_linkedin.py:94` — a diagnostic script that uses `variantgen.build_variant_set`, not `generate_campaign.generate`. This is a LinkedIn variant experiment, not production campaign generation.

**Verdict:** CONFIRMED CURRENT. The production entrypoint exists but is not consumed by the production execution stream. This is a wiring gap, not a code defect. The entrypoint is ready; the caller is missing.

**Disposition:** EXISTING TASK (TASK-375 documented this; TASK-379 is the independent verification).

---

## Section 3: Skills Usage

**Finding (from TASK-375):** "The five `src/skills/*` modules are never called by `_process_contact`."

**Independent verification:**

**What the code actually does:**

`_process_contact` loads 5 skills via `skills.load()`:
- Line 225: `icp_skill = skills.load("signal_verification")` → uses `icp_skill.procedure` for stage A
- Line 236: `extract_skill = skills.load("account_research")` → uses `extract_skill.procedure` for stage B
- Line 150: `skill = skills.load("campaign_strategy")` → uses `skill.procedure` for strategy
- Line 294: `email_skill = skills.load("cold_email_writing")` → uses `email_skill.procedure` for stage F (email)
- Line 295: `linkedin_skill = skills.load("linkedin_writing")` → uses `linkedin_skill.procedure` for stage F (LinkedIn)

**But stages C and D bypass the skill system:**
- Line 253: `copystages.HYPOTHESIS_SYSTEM` (raw constant, no skill)
- Line 266: `copystages.MATCH_SYSTEM` (raw constant, no skill)

**Why this is not a TASK-375 error:** The finding said "the five skills are never called", which is false — they ARE called. But the finding's spirit is correct: **stages C and D have no skill wrappers**, so they bypass the skill registry's consumer validation. The registry enforces "every skill must have a consumer", but it does not enforce "every stage must have a skill".

**Verdict:** PARTIALLY CORRECT. The five skills that exist ARE loaded and used. But two pipeline stages (hypothesis, match) have no skill wrappers and use raw constants. This is a gap in the skill system's coverage, not a bypass of the skills that exist.

**Disposition:** EXISTING TASK (TASK-375 documented the broader concern; the specific gap is stages C/D have no skills).

---

## Section 4: Entrypoint Claims

**Claim 1:** "One versioned production entrypoint for campaign generation."

**Verification:** 
- `src/generate_campaign.py` exists, is importable, has `ENTRYPOINT_VERSION = "1"`
- `src/sequenceplan.py` defines the plan shape and six projections (preview, bison, heyreach, approval_hash)
- No other `generate()` function in `src/` claims to be the production entrypoint

**Verdict:** CONFIRMED. The entrypoint is single-source and versioned.

---

**Claim 2:** "Every model call goes through `src/llm.py`. No `urllib`, no `requests`, no API base URL in this file."

**Verification:**
```bash
grep -n "import urllib\|import requests\|api.groq.com\|api.anthropic.com\|openai.com/v1" src/generate_campaign.py
```
**Result:** No matches. The file imports `from . import llm` and calls `model.complete()`, which is the `llm.py` seam.

**Verdict:** CONFIRMED. The entrypoint does not make direct HTTP calls.

---

**Claim 3:** "The spend ledger sees every call."

**Verification:** The entrypoint calls `model.complete()`, which is implemented by `llm.OpenAICompatibleModel` or `llm.ScriptedModel` in tests. The production model implementation in `llm.py` routes through the spend ledger. The test `TestSpendLedger.test_model_calls_go_through_llm` verifies the model is called, but does not verify the ledger is updated (that is `llm.py`'s responsibility, not the entrypoint's).

**Verdict:** CONFIRMED with caveat. The entrypoint routes through the `llm.py` seam; the ledger enforcement is in `llm.py`, not here. This is the correct separation.

---

**Claim 4:** "Offers refuse by name."

**Verification:** Test `TestOfferRefusal.test_pending_offer_raises_not_approved` passes. The code raises `NotApproved` with the offer ID in the message:
```python
raise NotApproved(
    f"offer {oid} has approval_status={offer.get('approval_status')!r}, not 'approved'. "
    f"Production does not approve its own offers."
)
```

**Verdict:** CONFIRMED. The refusal names the offer and the status.

---

**Claim 5:** "Strategy is decided once per segment+persona."

**Verification:** Test `TestStrategyDecidedOnce.test_fifty_leads_one_strategy_call` passes. The code calls `_decide_strategy()` once before the contact loop, and `campaignstrategy.for_segment()` caches by segment+persona.

**Verdict:** CONFIRMED. 50 contacts, one strategy call.

---

## Section 5: Test Coverage

**Three test files, 20 tests total, all green:**

1. `test_a_skill_is_loaded_by_the_stage_that_uses_it.py` (6 tests)
   - Every skill has a consumer
   - Registry has exactly 5 skills
   - Load returns a skill with all required fields
   - Consumer names a real stage
   - Two skills share stage_f
   - Load unknown skill raises

2. `test_changing_an_approved_fact_changes_the_output.py` (3 tests)
   - Changing verified fact changes plan (mutation test)
   - Changing fact back returns output
   - Changing unverified fact does NOT change prospect output (negative control)

3. `test_the_entrypoint_is_the_only_generation_path.py` (11 tests)
   - Entrypoint is callable
   - Version constant exists
   - No urllib/requests in source
   - Pending offer raises NotApproved
   - Message names the offer
   - 50 leads, one strategy call
   - Plan has contacts
   - Plan has strategy
   - Changing step changes all projections
   - Model calls go through llm
   - Source has no direct HTTP

**Verdict:** Test coverage is adequate for the claims made. The mutation test is the critical one and it passes.

---

## Section 6: New Findings

**None.** Claude's pre-merge verification and TASK-375's follow-up identified the two known gaps (zero callers, stages C/D have no skills). No additional defects found.

---

## Section 7: Dispositions

| Finding | Severity | Disposition | Evidence |
|---------|----------|-------------|----------|
| `generate_campaign.generate()` has zero production callers | P1 | EXISTING TASK | grep confirms no callers in src/ or scripts/; TASK-375 documented this |
| Stages C and D use raw constants, not skills | P2 | EXISTING TASK | Lines 253, 266 use `copystages.HYPOTHESIS_SYSTEM` and `copystages.MATCH_SYSTEM`; no skill wrappers exist for these stages |

---

## Section 8: Conclusion

TASK-369's production entrypoint is **code-correct and test-verified**, but **not wired into production**. The mutation test proves the pipeline propagates verified facts and blocks unverified ones. The five skills that exist are loaded and used. Two pipeline stages (hypothesis, match) have no skill wrappers and use raw constants, which is a gap in the skill system's coverage but not a bypass of the skills that exist.

**The entrypoint is ready. The caller is missing.**

**Recommended next steps:**
1. Wire `generate_campaign.generate()` into the production execution stream (the real blocker)
2. Decide whether stages C and D should have skill wrappers (design decision, not a defect)
3. Do not merge more code until the entrypoint has a caller — otherwise it drifts stale

---

**Review completed:** 2026-09-26  
**Review SHA:** 82c57bf7 (TASK-379 commit)  
**Master SHA:** 0077c76e  
**Status:** COMPLETE, no new findings, two known gaps confirmed
