# GLM Verdict: TASK-485 — Independent verification of TASK-335

**Reviewed branch:** `origin/qwen-worker-12-r9-sync`
**Reviewed HEAD SHA:** `3da4a246ee2536760d04dfc4d1d94b649160c2fa`
**SHA verified with:** `git rev-parse origin/qwen-worker-12-r9-sync` → `3da4a246ee2536760d04dfc4d1d94b649160c2fa` ✓
**Review worktree:** `.qwen/worktrees/task485-review` (detached at target SHA)
**Date:** 2026-09-28
**Reviewer:** Qwen Worker 7 (TASK-485)

---

## Summary

**RECOMMENDATION: REWORK**

TASK-335's result block claims "DONE, artifact verified" with four commits on a `task-335-recovery` branch. The branch being reviewed (`qwen-worker-12-r9-sync` at `3da4a246`) contains **none of the recovered artifacts**. The task file was moved to REVIEW on this branch, but the actual code and document recoveries live on a separate `origin/task-335-recovery` branch that was never merged to master and is not an ancestor of the reviewed ref.

Even on the recovery branch, both code artifacts (`groq.py` adapter and `contactout.linkedin_from_email`) have **zero production callers** — they are DISCONNECTED per the repository's own rule: "Existence is not function."

---

## Finding 1: Artifacts are NOT on the reviewed ref

**Severity: Critical**
**Confidence: High (verified by `git cat-file -e`)**

| Artifact | On `3da4a246`? | On `origin/task-335-recovery`? |
|---|---|---|
| `docs/AUDIT-2026-09-26.md` | **MISSING** | ✓ exists (700 lines) |
| `src/providers/groq.py` | **MISSING** | ✓ exists (427 lines) |
| `src/providers/openrouter.py` | **MISSING** | ✓ exists |
| `tests/test_groq_openrouter_adapters.py` | **MISSING** | ✓ exists |
| `tests/test_contactout_linkedin_from_email.py` | **MISSING** | ✓ exists |
| `contactout.linkedin_from_email` function | **ABSENT** (file exists, function does not) | ✓ present (line 333) |

**Commands run:**
```
git cat-file -e 3da4a246:docs/AUDIT-2026-09-26.md         → fatal: does not exist
git cat-file -e 3da4a246:src/providers/groq.py             → fatal: does not exist
git cat-file -e 3da4a246:src/providers/openrouter.py       → fatal: does not exist
git cat-file -e 3da4a246:tests/test_groq_openrouter_adapters.py → fatal: does not exist
git cat-file -e 3da4a246:tests/test_contactout_linkedin_from_email.py → fatal: does not exist
grep "linkedin_from_email" on 3da4a246:src/providers/contactout.py → no match
```

The result block's own commits (`5215a4de`, `8ea81e8a`, `a8b130c8`, `f025b2a1`) exist on `origin/task-335-recovery`, not on the reviewed branch.

---

## Finding 2: `groq.complete()` has zero production callers

**Severity: Critical**
**Confidence: High (verified by `git grep`)**

On the recovery branch, `src/llm.py` identifies "groq" as a provider name in a classification method (line 274: `if "groq" in base: return "groq"`), but **never imports or calls `groq.complete()`**. No file in `src/` calls `groq.complete()`, imports from `src.providers.groq`, or dispatches to the groq adapter.

```
git grep "groq\.complete\|from.*groq.*import\|import.*groq" origin/task-335-recovery -- src/llm.py
→ (empty, exit 1)
```

The adapter is well-written with spendledger integration (reserve/settle/release), but nothing in the production chain reaches it. Per the standing rule: "Zero production callers means DISCONNECTED, which is a rework and not a merge."

---

## Finding 3: `linkedin_from_email` has zero production callers

**Severity: Critical**
**Confidence: High (verified by `git grep`)**

On the recovery branch, `src/enrich.py` has the cost entry (`"linkedin-url-from-email": 1`) and the route-to-stage mapping (`"linkedin-url-from-email": "people_discovery"`), but **never calls `contactout.linkedin_from_email()`**.

```
git grep "linkedin_from_email" origin/task-335-recovery -- src/enrich.py
→ (empty, exit 1)
```

The function exists, is tested (26/26 pass), and is import-clean — but no production code path invokes it. The result block itself acknowledges this: "the actual caller is a downstream task." That downstream task has not landed.

---

## Finding 4: Recovery branch not merged to master

**Severity: Informational**
**Confidence: High**

```
git merge-base --is-ancestor origin/task-335-recovery origin/master
→ "recovery NOT merged to master"
```

`origin/task-335-recovery` exists only as its own remote branch. It is not an ancestor of master, nor of the reviewed branch.

---

## Finding 5: AUDIT document is real and complete (on recovery branch)

**Severity: Informational (positive)**
**Confidence: High**

The AUDIT document on `origin/task-335-recovery` is 700 lines with 16 section headings matching the result block's claims:

- Executive Summary, Section 3 (Second Brain), Section 4 (Offer Engine), Section 5 (Signal Intelligence), Section 6 (Skills/SOP), Section 7 (Copy), Section 8 (Copy Validation), Section 9 (Learning Engine), Section 10 (Contextual Retargeting), Section 11 (Infrastructure), Section 12 (Performance/Cost), CONFIRMED BUGS, ARCHITECTURAL RECOMMENDATIONS, WHAT SHOULD NOT BE TOUCHED, TEST EVIDENCE SUMMARY, FILES AND FUNCTIONS REFERENCE.

This artifact has real value but is not accessible from master or the reviewed branch.

---

## Finding 6: Tests pass on recovery branch (not on reviewed branch)

**Severity: Informational**
**Confidence: High**

On `origin/task-335-recovery` (detached at `f025b2a1`):
- `tests.test_groq_openrouter_adapters`: **19/19 pass**
- `tests.test_contactout_linkedin_from_email`: **26/26 pass**

These tests cannot run on the reviewed branch (`3da4a246`) because the test files and the modules they test do not exist there.

---

## Finding 7: No deletions of master content

**Severity: Informational (positive)**
**Confidence: High**

```
git diff master...3da4a246 --diff-filter=D --name-only
```

Only task files moved between queues (TODO → REVIEW/DONE). No production source, config, or documentation files would be deleted by merging this branch.

---

## Finding 8: Scope drift — branch carries unrelated work

**Severity: Informational**

The reviewed branch carries work from at least 8 other tasks (TASK-245, TASK-272, TASK-355, TASK-415, TASK-417, TASK-418, TASK-424, TASK-426, TASK-427, TASK-434) plus multiple GLM verdicts. The diff is 46 files / +4298 / -492 lines. TASK-335's contribution to this branch is the task file movement only — no code artifacts.

---

## Finding 9: Function name mismatch confirmed

**Severity: Informational**
**Confidence: High**

The task file's acceptance command checks for `linkedin_url_from_email`, but the actual function is `linkedin_from_email`. The result block correctly identifies this discrepancy (Finding 3 in the result block). The acceptance command as written would fail even on the recovery branch.

---

## Disposition

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | Artifacts not on reviewed ref | **FALSE POSITIVE claim of done** — the artifacts exist on a different branch |
| 2 | groq.py has no production caller | **DISCONNECTED** — rework needed |
| 3 | linkedin_from_email has no production caller | **DISCONNECTED** — rework needed |
| 4 | Recovery branch not merged | **EXISTING STATE** — Claude has not merged it |
| 5 | AUDIT document is real | **VERIFIED on recovery branch** |
| 6 | Tests pass | **VERIFIED on recovery branch** |
| 7 | No deletions | **VERIFIED** |
| 8 | Scope drift | **NOTED** — cherry-pick would be needed |
| 9 | Function name mismatch | **ACKNOWLEDGED in result block** |

---

## Recommendation: REWORK

**Reason:** The task file was moved to REVIEW on `qwen-worker-12-r9-sync`, but the actual recovered artifacts were pushed to a separate `origin/task-335-recovery` branch that was never incorporated into the reviewed ref. Reviewing `3da4a246` for TASK-335 is reviewing an empty claim — the task file says "done" but the work is elsewhere.

Even if the recovery branch were the target, both code artifacts are DISCONNECTED: `groq.complete()` and `contactout.linkedin_from_email()` have zero production callers. The result block acknowledges this for `linkedin_from_email` ("the actual caller is a downstream task") but understates it for groq — `llm.py` classifies the provider name but never dispatches to the adapter.

**What is needed for MERGE:**
1. The recovery branch's artifacts must be on the branch being reviewed (cherry-pick or merge the recovery commits).
2. A production caller for `groq.complete()` must be identified or built — the adapter cannot remain orphaned.
3. A production caller for `contactout.linkedin_from_email()` must be wired — the cost entry and route mapping exist in `enrich.py` but the function is never invoked.
4. The AUDIT document is the highest-value artifact and could be merged independently as a low-risk document-only change.

**What is sound:**
- The AUDIT document is real, complete, and valuable.
- The groq adapter is well-implemented with proper spendledger integration.
- The contactout `linkedin_from_email` function handles errors correctly (404-as-miss, retry, trim).
- Tests are meaningful and pass.
- No master content would be deleted.
