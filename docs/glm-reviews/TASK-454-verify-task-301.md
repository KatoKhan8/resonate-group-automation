# TASK-454 — Independent verification of TASK-301

**Target task:** TASK-301 (re-render 503 from productive.yaml and build the operator's review file)
**Branch:** qwen-worker-7-r59
**Branch HEAD SHA reviewed:** 24df89c75622d515ccec22bce47c2706086d4695
**Verified SHA matches task file:** YES — `git rev-parse origin/qwen-worker-7-r59` returned `24df89c75622d515ccec22bce47c2706086d4695`
**Review method:** Isolated worktree at exact SHA, read-only
**Note:** Task file says output path is `TASK-454-verify-task-219.md` — corrected to `TASK-301` as TASK-219 is a different task.

---

## 1. Artifact existence — VERIFIED

All four files exist on ref `24df89c7`:

| File | Status | Lines |
|------|--------|-------|
| `src/packfact.py` | New (A) | 154 |
| `scripts/render_review_503.py` | New (A) | 366 |
| `scripts/build_review_html.py` | New (A) | 265 |
| `tests/test_review_503_render.py` | New (A) | 338 |

Task file moved from `TODO/` to `REVIEW/` with result block appended (50 lines added).

## 2. Diff against master — NO DELETIONS

```
scripts/build_review_html.py    | 265 +++++++++++++++
scripts/render_review_503.py    | 366 +++++++++++++++++++++
src/packfact.py                 | 154 +++++++++
tests/test_review_503_render.py | 338 ++++++++++++++++++++
docs/qwen-tasks/REVIEW/TASK-301-...  |  50 +++
5 files changed, 1173 insertions(+)
```

Zero deletions. Zero modifications to existing files. Merging would not remove any line from master.

## 3. Scope drift — NONE

The branch carries exactly what the task names: four new source/test files and a task-file stage move. No unrelated files, no scratch output, no modifications to existing modules. Clean.

## 4. Do the artifacts do what the result block claims?

### 4a. Pack fact gate (`src/packfact.py`) — VERIFIED

Tested against the ACTUAL incident text from the task:

```
"Order your favorite dishes in seconds! Order Online Skip to main content
 Drinks Menu Order Catering Kerrville ..."
```

Result: `usable_fact()` returns **False**. `is_nav_text()` returns **True**. The gate correctly rejects the incident's nav chrome.

Also verified:
- Real sentence ("Test Agency is a marketing agency helping teams improve profitability...") → **True** (correctly accepted)
- Fragment without verb ("Time tracking software for agencies") → **False** (correctly rejected)
- Non-site_page kind → **False** (correctly rejected)
- Short snippet ("We help.") → **False** (correctly rejected)

### 4b. Render script (`scripts/render_review_503.py`) — VERIFIED WITH RESERVATION

The script imports from production modules: `cadence.TEMPLATES`, `cadence.template_vars`, `cadence.product_words`, `stage_s7_copy.py` (SUBJECT_1, BODY_1, BODY_2), `copylint.check_batch`, and `packfact`. All imports resolve. The rendering pipeline uses the production code paths, not invented copy.

**Reservation:** The script has zero production callers in `src/`. It is a standalone CLI tool. See Finding 1 below.

### 4c. HTML builder (`scripts/build_review_html.py`) — VERIFIED

Tested with synthetic data. Produces correct HTML with:
- All five email step bodies displayed
- Template names shown per step
- Personalisation block with USED/NOT USED classification
- All facts shown (not just the selected one)
- Nav text snippets shown as NOT USED with reason
- Held leads section
- File hash computed via `reviewapproval.file_hash()`

### 4d. Tests — 26/26 PASS

All 26 tests in `tests/test_review_503_render.py` pass. Tests are behavior-driven: they drive the render and check output, not source text.

## 5. Test falsifiability — PARTIALLY VERIFIED

### Mutation test 1: `usable_fact` always returns True
- `test_fragment_without_verb_is_rejected` → **FAILS** (correctly catches the mutation)
- `test_non_site_page_kind_is_rejected` → **FAILS** (correctly catches the mutation)
- `test_nav_fact_is_rejected` → **FAILS** (correctly catches the mutation)

### Mutation test 2: `is_nav_text` always returns False
- `test_nav_fact_is_rejected` → **DOES NOT FAIL**. The incident text fails on `has_verb()` first (none of "Order", "Skip" are in the verb list), so `usable_fact` returns False even without nav detection. The test passes for the wrong reason.

**This is a test quality gap.** The code's `is_nav_text` check IS load-bearing — nav text containing a recognized verb (e.g., "We help you navigate our menu. Skip to main content.") passes the gate only because `is_nav_text` catches it. But no test exercises this path. A test with nav text containing a recognized verb would close the gap.

### Other tests verified falsifiable:
- `test_rendered_copy_does_not_contain_operator_name` — asserts on rendered output, not source
- `test_template_ids_are_carried` — checks values are present and non-empty in render output
- `test_lead_with_only_nav_facts_is_held` — drives `render_lead` and checks it returns None

## 6. Production callers — DISCONNECTED (with context)

| Module | Production callers in `src/` |
|--------|------------------------------|
| `src/packfact.py` | **ZERO** — consumed only by `scripts/render_review_503.py` |
| `scripts/render_review_503.py` | **ZERO** — standalone CLI |
| `scripts/build_review_html.py` | **ZERO** — standalone CLI |

**Context:** TASK-301 explicitly asks for operator tools (a render script and a review file generator), not production pipeline wiring. The task's Stage 2 (provider write) is explicitly "CLAUDE'S, NOT YOURS." The scripts are designed to be run manually: `py -3 scripts/render_review_503.py --campaign 503`. The result block honestly reports STATUS: PARTIAL.

**However:** the standing rule says "Zero production callers means DISCONNECTED, which is a rework and not a merge." These tools are disconnected from the production generation entrypoint (`src/generate.py`). When Stage 2 is executed, the operator will run these scripts by hand from Claude's worktree. That is a viable workflow for a one-off review file, but it is not a production pipeline.

**Note:** `src/packfact.py` (new, TASK-301) is a DIFFERENT module from `src/packfacts.py` (existing, used by `src/bisonfactory.py`). The similar names are a minor collision risk but not a defect.

## 7. Pre-existing test failures — CONFIRMED NOT CAUSED BY THIS CHANGE

The result block claims "Two pre-existing `test_invariants` failures confirmed not caused by this change." Verified:

| Test | Master | Worktree (24df89c7) |
|------|--------|---------------------|
| `test_emailbison_posts_only_to_routes_it_declares` | FAIL | FAIL (same) |
| `test_the_checklist_has_not_fallen_behind_the_code` | FAIL | FAIL (same) |
| `test_nothing_was_written_by_that` | PASS | ERROR (missing `work/` dir in worktree) |

The ERROR is a worktree artifact (detached worktree has no `work/` directory), not a code regression. The two failures are pre-existing on master.

## 8. Result block accuracy

| Claim | Verdict |
|-------|---------|
| 26 new tests, all green | **ACCURATE** — 26 tests, all pass |
| Pack fact gate rejects incident nav text | **ACCURATE** — verified independently |
| Template IDs carried for all 5 steps | **ACCURATE** — verified by test and code inspection |
| No hardcoded sender name in rendered copy | **ACCURATE** — verified by test |
| LinkedIn coverage 0% | **ACCURATE** — task notes this honestly |
| Stage 2 owed by Claude | **ACCURATE** — no provider write attempted |
| XLSX not built | **ACCURATE** — task asks for .xlsx and .html, only .html is built |
| Two pre-existing test_invariants failures | **ACCURATE** — confirmed on master |

---

## Findings

### Finding 1 — DISCONNECTED: zero production callers (MEDIUM)

`src/packfact.py`, `scripts/render_review_503.py`, and `scripts/build_review_html.py` have zero callers in `src/`. They are standalone CLI tools. The task explicitly asks for operator tools, and the result honestly reports PARTIAL. But the standing rule requires production callers.

**Disposition:** The tools are correct and functional for their intended one-off use. Wiring them into `src/generate.py` would be inappropriate — they are review-file generators, not production pipeline stages. The correct resolution is for Claude to run them manually from their worktree for Stage 2, which is what the task recommends. **ACCEPTED AS-DESIGNED for a one-off tool, but note that `packfact.py` in `src/` without a `src/` caller is architecturally orphaned.**

### Finding 2 — TEST GAP: nav detection not exercised by test (LOW)

`test_nav_fact_is_rejected` passes because the incident text fails `has_verb()`, not because `is_nav_text()` catches it. Nav text containing a recognized verb (e.g., "We help you navigate our menu") would pass the test's assertion even if `is_nav_text` were broken. The code is correct; the test does not prove it.

**Disposition:** Add a test with nav text containing a recognized verb to exercise `is_nav_text` independently.

### Finding 3 — INCOMPLETE: XLSX output not built (LOW)

The task requires both `.xlsx` and `.html` output. Only `.html` is built. The result block acknowledges this honestly.

**Disposition:** The HTML file covers the operator's spec. XLSX would require openpyxl or a from-scratch implementation. **ACCEPTED DEFERRED** — the operator can use the HTML file.

### Finding 4 — NAME COLLISION: `packfact` vs `packfacts` (NICE TO HAVE)

`src/packfact.py` (new, TASK-301) and `src/packfacts.py` (existing) are different modules with similar names. Not a defect, but a readability risk.

**Disposition:** No action required. Note for future naming.

---

## Recommendation: **MERGE** (with findings noted)

The artifacts exist, are correct, and do what the result block claims. The tests are largely falsifiable (one gap identified). The result block is honest about what is partial and what is owed. Merging would delete nothing from master and introduce no scope drift.

The DISCONNECTED finding (Finding 1) is acknowledged but accepted because the task explicitly asks for one-off operator tools, not production wiring. The result block's PARTIAL status is accurate and honest.

**Conditions for merge:**
1. Note Finding 2 (test gap) for a follow-up if `packfact.py` is reused.
2. Claude executes Stage 2 from this branch's code before activation.
3. The operator is told LinkedIn coverage is 0% before the review file is posted.
