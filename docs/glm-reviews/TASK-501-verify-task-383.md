# TASK-501 — Independent GLM Verification of TASK-383

**Target task:** TASK-383 (GLM Checkpoint A)
**Target branch:** `origin/qwen-worker-5-r9`
**Target SHA (per task file):** `d0432a8945acc1070bc07d952776ad679e7c755c`
**Actual HEAD at review time:** `b5caf02c3245e28a9fddcb6985a510d7973bd908` (branch has moved)
**Reviewed SHA:** `d0432a8945acc1070bc07d952776ad679e7c755c` (detached worktree)
**Review date:** 2026-10-03
**Review type:** Independent verification of TASK-383's artifact and claims
**Worktree:** `.qwen/worktrees/task501-review` (detached HEAD at `d0432a894`)

---

## Branch HEAD notice

The branch `origin/qwen-worker-5-r9` has moved from `d0432a894` (as named in the task file) to `b5caf02c3`. Per TASK-501's instructions, the review targets `d0432a8945acc1070bc07d952776ad679e7c755c` because that is the artifact this verdict is about. All evidence below is from that exact SHA.

---

## 1. Does the artifact exist?

**YES.** `docs/glm-reviews/checkpoint-a-0077c76e.md` exists at `d0432a894` (246 lines).

```
git log --diff-filter=A --all -- docs/glm-reviews/checkpoint-a-0077c76e.md
```

Returns two commits: `edf9eee2` (main worktree) and `a07fc86` (review branch). The file was added 2026-09-26 and is present at the target SHA.

**TASK-383 result block claims:** "DONE, artifact verified" with commit `edf9eee2` on review branch `review/glm-checkpoint-a-0077c76e` at `a07fc86`. **Verified: the artifact exists and the commit SHAs match.**

---

## 2. Independent verification of each control

### Control 1: One production entrypoint — FAILS ✓ CONFIRMED

TASK-383 claims two entrypoints exist, only `generate.py` reachable.

**Independent verification:**
- `grep -rn "generate_campaign" src/` → **ZERO hits** in `src/`
- `grep -rn "generate_campaign" scripts/` → **ZERO hits** in `scripts/`
- `grep -rn "generate_campaign" tests/` → 40 hits across 4 test files
- `src/generate.py` does NOT import `generate_campaign`

**Verdict: CONFIRMED FAILS.** `generate_campaign.py` has zero production callers.

### Control 2: Second Brain has real consumer — FAILS ✓ CONFIRMED

TASK-383 claims no file:line reads Second Brain facts in a path reaching a rendered message.

**Independent verification:**
- `secondbrain.for_task()` callers in `src/`:
  - `generate_campaign.py:133` — no production caller (Control 1)
  - `copystages.py:133` — inside `business_context_for(task, client)` at line 124
- `business_context_for` callers in `src/`: **ONE hit** — its own definition at `copystages.py:124`. Zero callers.
- `src/generate.py` does NOT import `secondbrain`

**Verdict: CONFIRMED FAILS.** Second Brain is consumed only by disconnected code.

### Control 3: Canonical research = one authority — HOLDS ✓ CONFIRMED

TASK-383 claims `rec["research"]` is the one store.

**Independent verification:**
- `packfacts.pack_for(rec)` reads `rec.get("research")` exclusively (packfacts.py:121)
- `researchpack.build()` has ZERO callers outside its own docstrings
- No module imports `researchpack` (only self-reference in `researchpack/__init__.py:6`)
- `rec["research"]` is written by `companies.py`, `demo.py`, `synthetic.py`, `benchmark.py`, `web/demodata.py` — all estate-level sources, not alternative research providers

**Verdict: CONFIRMED HOLDS.** One authority, no competing source.

### Control 4: Changed fact → changed artifact — UNVERIFIABLE ✓ AGREED

TASK-383 claims this is unverifiable from a read-only pass.

**Independent verification:**
- `tests/test_changing_an_approved_fact_changes_the_output.py` exists and calls `generate_campaign.generate()` directly
- But `generate_campaign.py` has no production caller (Control 1)
- `src/generate.py` does not use Second Brain facts at all
- A read-only pass cannot execute the mutation test

**Verdict: CONFIRMED UNVERIFIABLE.** The test proves the property for the disconnected path only.

### Control 5: No `work/` dependency in generation — HOLDS ✓ CONFIRMED

TASK-383 claims no critical generation logic depends on gitignored `work/`.

**Independent verification:**
- `grep -rn "open(.*work/" src/` → **ZERO hits**
- 79 matches for `work/` in `src/` are all docstrings/comments or go through `store.py`
- `work/v2_run.py` does not exist (gitignored), referenced only in comments

**Verdict: CONFIRMED HOLDS.** All `work/` access goes through `store.py`.

### Control 6: No closed wiring loop — FAILS ✓ CONFIRMED

TASK-383 claims skills → `generate_campaign.py` → nobody.

**Independent verification:**
- `skills.load()` callers in `src/`: ALL FIVE in `generate_campaign.py` only
  - Line 152: `skills.load("campaign_strategy")`
  - Line 228: `skills.load("signal_verification")`
  - Line 240: `skills.load("account_research")`
  - Line 301: `skills.load("cold_email_writing")`
  - Line 302: `skills.load("linkedin_writing")`
- `generate_campaign.py` has zero production callers (Control 1)

**Note on line numbers:** TASK-383's review document cites lines 150/225/236/294/295. At SHA `d0432a894`, the actual lines are 152/228/240/301/302. The shift is because TASK-387 (which added `skills` import and client/config threading to `generate_campaign.py`) landed after the review was authored against `0077c76e`. The substance is unchanged.

**Verdict: CONFIRMED FAILS.** Closed wiring loop.

### Control 7: No cross-account research leakage — HOLDS ✓ CONFIRMED

TASK-383 claims exact identity join (record_id + domain).

**Independent verification:**
- `bisonfactory.py:548` — `by_id = {record.get("id"): record for record in recs or []}`
- `bisonfactory.py:559` — `packfacts.pack_for(by_id.get(lead.get("record_id")))`
- `packfacts.identity_of()` checks:
  1. `record_id` match (REFUSED if mismatch)
  2. `same_site()` for domain identity (exact host match, not substring)
  3. Falls back to `source_url` host; UNVERIFIABLE if no website stated

**Verdict: CONFIRMED HOLDS.** Identity join, not text filter.

---

## 3. Would merging delete anything?

```
git diff master...d0432a8945acc1070bc07d952776ad679e7c755c --diff-filter=D --name-only
```

Three files deleted, all task files moved between stages:
- `docs/qwen-tasks/TODO/TASK-334-integrate-the-five-skills-from-their-branch.md`
- `docs/qwen-tasks/TODO/TASK-373-thread-the-client-into-the-spend-gate.md`
- `docs/qwen-tasks/TODO/TASK-375-the-entrypoint-and-its-five-skills-have-no-caller.md`

**No source files, test files, config files, or documentation files would be deleted.** The deletions are task lifecycle movements (TODO → DONE/REVIEW), which is expected.

---

## 4. Scope drift

The branch carries work from multiple tasks beyond TASK-383:
- TASK-387 (provider write-back): `src/generate_campaign.py` client/config threading, `tests/test_task387_writeback.py`
- TASK-373 (spend gate): `src/llm.py`, `src/generate.py`, `src/slackconversation.py` client/config threading
- TASK-369/375 (entrypoint + skills): `src/generate_campaign.py` skills integration
- TASK-367 (offers): `src/offers.py` capabilities block, `src/campaignstrategy.py` offer resolution
- Scripts: `scripts/bison_watch_loop.py`, `scripts/pool_watchdog.sh`, `scripts/pool.sh`
- Config: `config/clients/productive-offers.yaml`

**TASK-383's own contribution is the review document only.** The other changes are from other tasks that were on this branch. If only TASK-383 were being merged, the cherry-pick would be clean: one new file (`docs/glm-reviews/checkpoint-a-0077c76e.md`) and the task file movement.

**No junk or pollution detected.** Each changed file traces to a named task.

---

## 5. Test falsifiability assessment

TASK-383 is a review task, not an implementation task. Its artifact is a document, not code. The tests it references (e.g., `test_the_entrypoint_actually_loads_its_skills.py`, `test_changing_an_approved_fact_changes_the_output.py`) were added by OTHER tasks (TASK-369, TASK-375), not by TASK-383 itself.

Those tests are falsifiable:
- They call `generate_campaign.generate()` directly with `ScriptedModel`
- They assert on output structure, skill loading, and fact mutation
- Breaking the wiring (e.g., removing a `skills.load()` call) would cause test failures

However, as TASK-383 itself identified, these tests prove properties of the disconnected `generate_campaign` path, not the production path through `generate.py`.

---

## 6. Disposition summary

| # | Control | TASK-383 claim | Independent verdict |
|---|---|---|---|
| 1 | One production entrypoint | FAILS | **CONFIRMED FAILS** |
| 2 | Second Brain has real consumer | FAILS | **CONFIRMED FAILS** |
| 3 | Canonical research = one authority | HOLDS | **CONFIRMED HOLDS** |
| 4 | Changed fact → changed artifact | UNVERIFIABLE | **CONFIRMED UNVERIFIABLE** |
| 5 | No `work/` dependency | HOLDS | **CONFIRMED HOLDS** |
| 6 | No closed wiring loop | FAILS | **CONFIRMED FAILS** |
| 7 | No cross-account research leakage | HOLDS | **CONFIRMED HOLDS** |

**All seven dispositions are independently confirmed.** The review document's claims are accurate.

---

## 7. New findings from this verification

### Finding 1: Line number drift

TASK-383's review document cites `skills.load()` at lines 150/225/236/294/295 of `generate_campaign.py`. At SHA `d0432a894`, the actual lines are 152/228/240/301/302. The shift is because TASK-387 added lines to `generate_campaign.py` after the review was authored. This is a cosmetic discrepancy, not a substantive error.

### Finding 2: The review was done against a different SHA

TASK-383's review document states `START_MASTER_SHA: 0077c76e8f0ade61600860af5781940ec6feb767`. The branch at `d0432a894` includes subsequent changes (TASK-387). The review's claims remain correct at both SHAs, but the line numbers reflect the earlier state.

### Finding 3: TASK-383's scope was correctly bounded

TASK-383 was a read-only review task. It produced a document and made no code changes. The code changes visible on this branch are from other tasks. TASK-383 stayed within its declared scope.

---

## 8. Recommendation

**MERGE** the TASK-383 artifact (the review document) with the following notes:

1. The review is accurate. All seven controls are correctly assessed.
2. The three FAILS dispositions (Controls 1, 2, 6) identify real architectural defects: the closed wiring loop where `generate_campaign.py` and the five skills are disconnected from production.
3. These defects are not regressions introduced by TASK-383 — they are pre-existing conditions that TASK-383 correctly identified.
4. The review document is a valid GLM Checkpoint A artifact per the protocol.
5. The branch carries work from multiple tasks. TASK-383's own contribution (the review document) is clean and cherry-pickable.

**The review's central finding — that the production entrypoint (`generate.py`) does not consume the Second Brain, skills, or `generate_campaign.py` — is the most important architectural fact this checkpoint establishes.** This is not a defect in TASK-383; it is a defect in the system that TASK-383 correctly documented.

---

## Reproducible commands

```bash
# Verify artifact exists
git show d0432a8945acc1070bc07d952776ad679e7c755c:docs/glm-reviews/checkpoint-a-0077c76e.md | head -5

# Verify Control 1: generate_campaign has no production caller
git grep -n "generate_campaign" d0432a8945acc1070bc07d952776ad679e7c755c -- src/ scripts/
# Expected: zero hits

# Verify Control 6: skills.load has one consumer
git grep -n "skills\.load" d0432a8945acc1070bc07d952776ad679e7c755c -- src/
# Expected: all five hits in generate_campaign.py

# Verify Control 2: business_context_for is dead code
git grep -n "business_context_for" d0432a8945acc1070bc07d952776ad679e7c755c -- src/
# Expected: one hit (definition only)

# Verify no deletions of source files
git diff master...d0432a8945acc1070bc07d952776ad679e7c755c --diff-filter=D --name-only
# Expected: only task files
```

---

**VERDICT: TASK-383's artifact is valid, its claims are accurate, and its findings are confirmed. MERGE the review document.**
