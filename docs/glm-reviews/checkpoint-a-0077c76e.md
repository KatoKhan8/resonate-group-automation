# GLM CHECKPOINT A — Production Generation Entrypoint + Canonical Research Store

**START_MASTER_SHA:** `0077c76e8f0ade61600860af5781940ec6feb767`
**Review date:** 2026-09-26
**Review type:** Read-only falsification pass over seven negative controls
**Worktree:** `C:\Users\Zvonimir\Desktop\glm-checkpoint-a` (detached HEAD at origin/master)
**Driven by:** Qwen (this session), following `docs/GLM-REVIEW-PROTOCOL.md`

---

## Summary

Two of seven negative controls **fail**, four **hold**, and one is **unverifiable** from a read-only pass. The central finding is that `src/generate_campaign.py` — the module TASK-369 built and TASK-375 wired the five skills into — is a **closed wiring loop** with zero production consumer. The real production entrypoint is `src/generate.py`, which does not call `generate_campaign.py`, does not use the Second Brain, and does not load skills. The five skills, the Second Brain retrieval, and the strategy cache are all connected to each other through `generate_campaign.py` but disconnected from the production chain that actually sends.

---

## Negative Control Results

### Control 1: One version-controlled production entrypoint exists

**DISPOSITION: FAILS**

Two version-controlled entrypoints exist. Only one is reachable from a real invocation:

| Module | Version-controlled | Production caller | Reachable via `python -m` |
|---|---|---|---|
| `src/generate.py` | Yes | `if __name__ == "__main__"` at line 2151 | Yes: `python -m src.generate --live` |
| `src/generate_campaign.py` | Yes | **NONE** | No `__main__` block, no script calls it |

**Evidence:**
- `grep -rn "generate_campaign" src/` returns ZERO hits. No module in `src/` imports it.
- `grep -rn "generate_campaign" scripts/` returns ZERO hits.
- The only references to `generate_campaign` outside its own definition are in `tests/` (four test files).
- `src/generate.py` does NOT import or call `generate_campaign`.

**Conclusion:** "One entrypoint" is **aspirational, not currently true**. The real production path is `src/generate.py`, a record-centric architecture that predates `generate_campaign.py`. The newer module exists, is tested, but is not wired into production.

---

### Control 2: The Second Brain has a real consumer

**DISPOSITION: FAILS**

No file:line reads Second Brain facts in a path that reaches a rendered message through the production chain.

**Trace of every `secondbrain.for_task()` call in `src/`:**

1. `src/copystages.py:133` — inside `business_context_for(task, client)`. But `business_context_for` has **ZERO callers** in `src/`. It is defined but never called. Dead code.
2. `src/generate_campaign.py:131` — inside `_load_verified_facts(client_name)`. But `generate_campaign` has no production caller (Control 1).
3. Skills declare `secondbrain_sections` as metadata (e.g., `src/skills/campaign_strategy.py:23`) but this is a dataclass field — the skills never call `secondbrain.for_task()` themselves.

**The production entrypoint `src/generate.py`:**
- Does NOT import `secondbrain`
- Does NOT import `copystages`
- Does NOT call `business_context_for`
- Has no Second Brain retrieval of any kind

**Conclusion:** The Second Brain is consumed only by the disconnected `generate_campaign.py` and by `copystages.business_context_for()` which is itself dead code. No Second Brain fact reaches a rendered message through the production chain.

---

### Control 3: Canonical research has exactly one authority

**DISPOSITION: HOLDS**

`rec["research"]` is the one canonical store for account research. No alternative research source reaches a rendered message.

**Evidence:**
- `src/packfacts.py:121` — `pack_for(rec)` reads `rec.get("research")` exclusively
- `src/generate.py:115,232` — reads `rec.get("research")` directly and via `research.for_prompt(rec)`
- `src/researchpack/` has **ZERO production callers** outside its own package docstrings. `grep -rn "researchpack\." src/` returns only self-references in `researchpack/__init__.py` and `researchpack/pack.py` docstrings, plus one comment in `packfacts.py:83`.
- No module imports `researchpack` (`grep -rn "from .researchpack|import researchpack" src/` returns only the self-reference in `researchpack/__init__.py:6`).

**Conclusion:** TASK-376's claim holds. `rec["research"]` is the one authority. `researchpack` is demoted — it exists as a package but has no production caller that lets its output reach a rendered message.

---

### Control 4: Changing an approved fact changes the resulting artifact

**DISPOSITION: UNVERIFIABLE from read-only pass**

A test file exists (`tests/test_changing_an_approved_fact_changes_the_output.py`) that exercises this through `generate_campaign.generate()`. However:

1. The test calls `generate_campaign.generate()` directly with a `ScriptedModel` — not through the production entrypoint `src/generate.py`.
2. `generate_campaign.py` has no production caller (Control 1), so proving the chain works inside `generate_campaign` does not prove it works in production.
3. `src/generate.py` does not use Second Brain facts at all, so the analogous test through the real entrypoint cannot be constructed without first wiring the Second Brain into `generate.py`.
4. A read-only pass cannot execute the mutation test. The task explicitly requires end-to-end reproduction ("change a Second Brain fact, regenerate, show the artifact differs"), which requires running code.

**Conclusion:** The test proves the property for the disconnected `generate_campaign` path. Whether it holds for the production chain is unverifiable without (a) running the code and (b) first connecting `generate_campaign` to production. **Static proof: the property holds in isolation. Runtime proof through production: not yet possible.**

---

### Control 5: No critical generation logic depends on gitignored `work/`

**DISPOSITION: HOLDS**

**Evidence:**
- `grep -rn "open(.*work/" src/` returns ZERO hits. No module opens a `work/` file directly.
- `grep -rn "import work\.|from work\." src/` returns ZERO hits.
- All `work/` access goes through `src/store.py` (the sanctioned path per AGENTS.md).
- `src/generate_campaign.py:158` explicitly states: "Sources come from the account dict, not from hardcoded work/ paths."
- `work/v2_run.py` does not exist in the worktree (gitignored). It is referenced only in comments in `generate_campaign.py:14,276`.
- The 79 matches for `work/` in `src/` are all either (a) docstring/comment references, (b) going through `store.py`, or (c) the `store.py` module itself.

**Conclusion:** No current in-scope generation module has a direct dependency on gitignored `work/` paths. The `work/v2_run.py` reference is historical — it was the scratch prototype `generate_campaign.py` was built from, and it is not imported.

---

### Control 6: No closed wiring loop with zero external consumer

**DISPOSITION: FAILS**

This is the central defect. The five skills are wired into `generate_campaign.py`, but `generate_campaign.py` has no external consumer.

**Trace of `skills.load()` callers in `src/`:**

| Call site | Module |
|---|---|
| `generate_campaign.py:150` | `skills.load("campaign_strategy")` |
| `generate_campaign.py:225` | `skills.load("signal_verification")` |
| `generate_campaign.py:236` | `skills.load("account_research")` |
| `generate_campaign.py:294` | `skills.load("cold_email_writing")` |
| `generate_campaign.py:295` | `skills.load("linkedin_writing")` |

**These are the ONLY five `skills.load()` calls in the entire `src/` tree.** Every skill consumer is inside `generate_campaign.py`. And `generate_campaign.py` has no production caller (Control 1).

**The loop:**
```
skills.load() → generate_campaign.generate() → [NOBODY]
```

`src/generate.py` — the real production entrypoint — does not import `generate_campaign`, does not import `skills`, and does not call any skill.

**Conclusion:** This IS a closed wiring loop. Five skills, one consumer (`generate_campaign.py`), zero external consumers of that consumer. TASK-375's work is internally correct — the skills are loaded and used — but the module that uses them is itself disconnected from production.

---

### Control 7: No cross-account research leakage in the reviewed path

**DISPOSITION: HOLDS**

The join from lead to research pack is exact identity, not a text filter.

**Trace of the `bisonfactory` → `packfacts` path:**

1. `src/bisonfactory.py:548` — `_copylint_batch()` builds `by_id = {record.get("id"): record for record in recs or []}` — keyed by exact record ID.
2. `src/bisonfactory.py:559` — looks up `packfacts.pack_for(by_id.get(lead.get("record_id")))` — exact record ID match. If the lead's `record_id` doesn't match any record, `by_id.get()` returns `None`, and `pack_for(None)` returns an empty pack.
3. `src/packfacts.py:110-128` — `pack_for(rec)` iterates `rec.get("research")` and applies `identity_of()` to each row.
4. `src/packfacts.py:68-97` — `identity_of(row, domain, record_id)` applies three checks:
   - If `record_id` is stamped on the row and doesn't match → REFUSED
   - If the row states a website → `same_site()` checks exact host/domain match (not substring)
   - If no website → falls back to `source_url` host, admits only if same site, otherwise UNVERIFIABLE (not admitted)

**The `generate_campaign` path:**
- `src/generate_campaign.py:157-163` — `_prepare_sources(account)` takes sources from `account.get("sources")`, which is passed in by the caller. No cross-account lookup.

**Conclusion:** The join is exact identity (record_id + domain match). A fact from account A cannot reach account B's pack unless it passes both the record_id check and the domain identity check. The 50-of-71 defect (documented in `packfacts.py:83`) was specifically fixed by replacing text filter (`companyName`) with identity match (`companyWebsite`).

---

## Disposition Summary

| # | Control | Disposition | Evidence type |
|---|---|---|---|
| 1 | One production entrypoint | **FAILS** | Static: grep, import trace |
| 2 | Second Brain has real consumer | **FAILS** | Static: grep, caller trace |
| 3 | Canonical research = one authority | **HOLDS** | Static: grep, import trace |
| 4 | Changed fact → changed artifact | **UNVERIFIABLE** | Needs runtime + wiring fix |
| 5 | No `work/` dependency in generation | **HOLDS** | Static: grep, file absence |
| 6 | No closed wiring loop | **FAILS** | Static: grep, caller trace |
| 7 | No cross-account research leakage | **HOLDS** | Static: code trace, identity checks |

---

## New Findings

### Finding A: `copystages.business_context_for()` is dead code

- **File:** `src/copystages.py:124`
- **Evidence:** `grep -rn "business_context_for" src/` returns ONE hit — its own definition. No caller anywhere in `src/`.
- **Impact:** This function was the intended bridge between the Second Brain and the production copy stages. It is disconnected.

### Finding B: Two parallel generation architectures with no migration path

- `src/generate.py` (2153 lines) — the record-centric production entrypoint. Uses `rec["research"]`, `research.for_prompt()`, its own `research_block()`, `claims`, `lint`. Does NOT use Second Brain, skills, `sequenceplan`, or `generate_campaign`.
- `src/generate_campaign.py` (410 lines) — the account-centric entrypoint. Uses Second Brain, skills, `sequenceplan`, `campaignstrategy`, `copylint`, `sequencegate`. Does NOT use `store.py`, `rec["research"]`, or `research.for_prompt()`.
- These are two independent architectures. Neither calls the other. The production system runs on `generate.py`; the tested, skill-aware path is `generate_campaign.py`.

### Finding C: Skill metadata (`secondbrain_sections`) is declarative only

- The five skill modules declare `secondbrain_sections` as a dataclass field (e.g., `src/skills/campaign_strategy.py:23`).
- No code reads this field to actually fetch Second Brain sections. The skills' `procedure` text is used as a system prompt, but the Second Brain data is not injected through the skill mechanism.
- The Second Brain loading in `generate_campaign._load_verified_facts()` is hardcoded to `"campaign_strategy"` and does not vary by skill.

---

## What is NOT reviewed

- Runtime behavior (model calls, provider writes, spend ledger enforcement) — read-only pass.
- The `researchpack` package's internal correctness — only its (lack of) production wiring.
- Whether `generate.py`'s own prompts produce correct output — only whether `generate_campaign.py` is connected.
- Spend ceiling enforcement (Checkpoint E in the protocol).
- Provider safety, approval, suppression (Checkpoint E).

---

## Reproducible read-only commands

```bash
# Control 1: prove generate_campaign has no production caller
grep -rn "generate_campaign" src/ scripts/
# Expected: only test files reference it

# Control 2: prove Second Brain has no production consumer
grep -rn "for_task" src/
grep -rn "business_context_for" src/
# Expected: only generate_campaign (disconnected) and copystages (dead code)

# Control 3: prove researchpack has no production caller
grep -rn "researchpack\." src/
grep -rn "from .researchpack\|import researchpack" src/
# Expected: only self-references in docstrings

# Control 5: prove no direct work/ access
grep -rn 'open(.*work/' src/
grep -rn "import work\.\|from work\." src/
# Expected: zero hits

# Control 6: prove skills.load has one consumer
grep -rn "skills\.load" src/
# Expected: all five hits in generate_campaign.py only

# Control 7: trace the identity join
# Read bisonfactory.py:548-559 and packfacts.py:68-128
```

---

## END_MASTER_SHA check

Re-fetch and verify no master movement during review:

```bash
git log -1 --format="%H" origin/master
# Must still be 0077c76e8f0ade61600860af5781940ec6feb767
```
