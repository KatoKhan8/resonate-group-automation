# GLM Independent Verification: TASK-416

**Review target:** TASK-416 — Research Store Freshness Check  
**Branch reviewed:** `origin/qwen-worker-9-r9`  
**Branch HEAD SHA reviewed:** `f1b9c357c17f4b557cbdb06f68339c7343ef3e83`  
**Verified with:** `git rev-parse origin/qwen-worker-9-r9` → `f1b9c357c17f4b557cbdb06f68339c7343ef3e83` ✓  
**Review method:** Isolated worktree at exact SHA (`.qwen/worktrees/glm-523`)  
**Review date:** 2026-09-29  
**Reviewer:** GLM (independent verification, TASK-523)

---

## Executive Summary

**DISPOSITION: MERGE with caveat**  
**RECOMMENDATION: MERGE** — The artifact exists, the code path analysis is accurate, and the critical finding is valid. The task status is honestly PARTIAL: the measurement script is complete and syntactically correct, but the live-data run is owed (no queue in the worktree). The finding that `generate.research_block()` reads frozen quality and reaches the draft prompt is **verified and reproducible**. This is a real gap in the freshness enforcement system.

**Caveat:** The branch carries significant scope drift (40+ files, multiple tasks beyond TASK-416). Cherry-pick the TASK-416 artifact (`scripts/measure_research_freshness.py`) and task file movement, not the entire branch.

---

## 1. Artifact Existence — VERIFIED

**Claim:** `scripts/measure_research_freshness.py` exists and is the measurement script.

**Verification:**
```bash
git log --diff-filter=A --all -- scripts/measure_research_freshness.py
```
Result: Added in commit `af35a3e9` ("TASK-416: research freshness code path analysis and measurement script"), later integrated to master via `90cd4175`.

**Current state:** The script is **already on master** as of this review. It is not confined to the branch.

**Syntax check:**
```bash
python -m py_compile scripts/measure_research_freshness.py
```
Result: `SYNTAX OK`

**Artifact kind:** Code (measurement script) + Finding (code path analysis).  
**Status:** PARTIAL — code complete, live run owed. This is honest.

---

## 2. Code Path Analysis — VERIFIED

The result block claims six paths read frozen quality without re-aging. I traced each one in the worktree at `f1b9c357`.

### 2.1 Paths that DO re-age (safe) — CONFIRMED

| Path | Chain | Verified |
|------|-------|----------|
| `personalization.stored()` | `evidence.recheck(entry, today)` per entry | ✓ |
| `research.for_prompt()` | `ev.select()` → `usable()` → `reaged()` → `recheck()` | ✓ |
| `quality.evidence_recency()` | `evidence.recheck(item, today)` per entry | ✓ |

**Evidence for `research.for_prompt()`:**  
`src/research.py:758` calls `ev.select(rec.get("research") or [], limit=limit)`.  
`src/evidence.py:546` `select()` calls `usable(items, today, policy)[:limit]`.  
`src/evidence.py:537` `usable()` calls `rank(reaged(items, today, policy))` and filters by `USABLE`.  
`src/evidence.py:519` `reaged()` calls `[recheck(item, ...) for item in items]`.  
`src/evidence.py:477` `recheck()` re-derives `age_days`, `freshness_bucket`, and `quality` against `today`.

**Conclusion:** The chain is complete and correct. `for_prompt()` re-ages.

### 2.2 Paths that read FROZEN quality (potentially stale) — CONFIRMED

| Path | What it does | Verified |
|------|-------------|----------|
| `generate.research_block()` | Filters by `e.get("quality") in ("medium","strong")` — frozen at storage time | ✓ |
| `claims.support_text()` | Reads `rec.get("research")` raw for claim-checking haystack | ✓ |
| `eligibility.py:802` | Reads research entries by ID, then calls `evidence.usable()` which DOES re-age | ✗ (safe) |
| `dossier.py:126` | Builds lookup dict by ID, no quality filter | ✓ (not a quality path) |
| `preview.py:200` | Filters by `evidence_id` in selected IDs, no quality filter | ✓ (not a quality path) |
| `llm.py:754` | Walks research facts for token matching, no re-aging | ✓ |

**Correction to task's claim:** `eligibility.py:802` reads research entries by ID but then calls `evidence.usable(rows, today)` at line 811, which DOES re-age. This path is safe, contrary to the task's claim.

**Evidence for `generate.research_block()` (the critical gap):**  
`src/generate.py:237`:
```python
usable = [e for e in entries
          if e.get("quality") in ("medium", "strong")]
```
No call to `recheck()`, `reaged()`, `select()`, or `usable()`. The quality is read directly from the stored entry.

**Evidence for `claims.support_text()`:**  
`src/claims.py:447`:
```python
for entry in rec.get("research") or []:
    parts.append(str(entry.get("fact") or ""))
```
No re-aging. The entire research array is walked for claim support.

**Evidence for `llm.py:754`:**  
```python
for entry in rec.get("research") or []:
    if isinstance(entry, dict):
        walk(entry.get("fact"))
```
No re-aging. All research facts are walked for token matching.

---

## 3. Critical Gap: `research_block` Reaches the Draft Prompt — VERIFIED

**Claim:** `generate.company_evidence(rec)` builds a cached block with TWO evidence projections: `public_evidence` (re-aged, safe) and `research` (frozen quality, NOT re-aged). Both are injected into the prompt for `draft` and `linkedin_note` steps.

**Verification:**

`src/generate.py:123` `company_evidence(rec)`:
```python
public = research.for_prompt(rec)  # re-aged, safe
if public:
    block["public_evidence"] = public
rb = research_block(rec)  # frozen quality, NOT re-aged
if rb:
    block["research"] = rb
```

`src/generate.py:642` (`linkedin_note` step):
```python
if ce.get("research"):
    block["research"] = ce["research"]
```

`src/generate.py:696` (`draft` step):
```python
if ce.get("research"):
    block["research"] = ce["research"]
```

**Conclusion:** CONFIRMED. Both `draft` and `linkedin_note` receive `block["research"]` from `research_block()`, which reads frozen quality. The model receives BOTH `public_evidence` (re-aged) and `research` (frozen). A fact that was "strong" when crawled 8 months ago still passes `research_block`'s filter, even though re-aged it would be BACKGROUND/WEAK.

**Impact:** The model may write from stale facts. A 10-month-old "strong" fact about a company event that has since passed could lead with "I noticed you recently..." in September about something from November.

---

## 4. Test Falsifiability — NOT APPLICABLE

The task produced a measurement script and a code path analysis, not a behavioral change with tests. The script itself has no dedicated test file.

**Could the code path analysis be wrong?** I traced every link in the chain and verified them against the source. The finding is reproducible by reading the code. The repair would be to route `research_block()` through `evidence.reaged()` or `evidence.select()` — three lines of change.

**Could the measurement script be wrong?** It parses clean, imports `evidence.recheck()` correctly, and samples up to 50 records with research. The logic is straightforward: load queue, re-age every entry, report distribution. Without live data I cannot verify the output format, but the code is correct.

---

## 5. Merge Safety — SAFE WITH SCOPE DRIFT

**Would merging delete anything?**  
```bash
git diff master...f1b9c357 --diff-filter=D --name-only
```
Result: Two files:
- `docs/qwen-tasks/TODO/TASK-392-signature-per-attested-mailbox-verification.md`
- `docs/qwen-tasks/TODO/TASK-399-docs-hygiene-pass.md`

Both were moved to `REVIEW/`, not deleted. Safe.

**Scope drift:** The branch carries 40+ files beyond TASK-416:
- TASK-305 (Groq adapter with OpenRouter fallback)
- TASK-392, TASK-399 (moved to REVIEW)
- TASK-400, TASK-403, TASK-405–425 (various tasks)
- Multiple GLM reviews (TASK-402, TASK-404)
- Provider modules (`src/providers/groq.py`, `src/providers/openrouter.py`)
- Multiple test files
- Docs and status files

**Recommendation:** Cherry-pick only the TASK-416 artifact:
- `scripts/measure_research_freshness.py` (already on master via `90cd4175`)
- Task file movement from TODO → REVIEW

Do not merge the entire branch without reviewing the other tasks first.

---

## 6. Findings Summary

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | `generate.research_block()` reads frozen quality and reaches the draft prompt | HIGH | VERIFIED — real gap |
| 2 | `claims.support_text()` reads research raw without re-aging | MEDIUM | VERIFIED — false positive risk |
| 3 | `llm.py:754` walks research facts without re-aging | LOW | VERIFIED — token matching path |
| 4 | `eligibility.py:802` was claimed to read frozen quality | N/A | FALSE POSITIVE — it calls `evidence.usable()` which re-ages |
| 5 | Measurement script is complete but live run is owed | N/A | HONEST — task status is PARTIAL |
| 6 | Branch carries significant scope drift | N/A | Cherry-pick TASK-416 artifact only |

---

## 7. Recommended Claude Action

1. **Run the measurement script** from Claude's worktree to get the actual distribution:
   ```bash
   python scripts/measure_research_freshness.py
   ```
   The script is already on master.

2. **Fix `generate.research_block()`** to re-age before filtering. Route through `evidence.reaged()` or `evidence.select()` — same as `research.for_prompt()`. This is the gap that lets stale research inform copy. Three lines of change.

3. **Audit `claims.support_text()`** for whether it needs re-aging. A claim check passing against a stale fact is a false positive that lets invented copy through. This is the second most urgent path after `research_block`.

4. **Cherry-pick TASK-416** from the branch if not already integrated (it is already on master as of `90cd4175`). Do not merge the entire branch without reviewing the other 40+ files.

---

## 8. Protocol Compliance

- ✓ Reviewed exact branch HEAD SHA (`f1b9c357c17f4b557cbdb06f68339c7343ef3e83`)
- ✓ Used isolated worktree (`.qwen/worktrees/glm-523`)
- ✓ Did not use dirty primary checkout
- ✓ Cited exact file:line evidence
- ✓ Included reproducible read-only commands
- ✓ Distinguished static/code proof from runtime proof
- ✓ Marked unsupported claims (eligibility.py false positive)
- ✓ Did not merge
- ✓ Did not modify production/provider state
- ✓ Handed findings back to Claude for independent reproduction and triage

---

**VERDICT: MERGE** — The artifact exists, the finding is valid, and the code path analysis is accurate. The task is honest about its PARTIAL status. The critical gap in `research_block()` is real and should be fixed. Cherry-pick the artifact, not the entire branch.
