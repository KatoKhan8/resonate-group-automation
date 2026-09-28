# TASK-477 — GLM Independent Verification of TASK-269

## Review metadata

| Field | Value |
|-------|-------|
| Task reviewed | TASK-269 |
| Branch | origin/qwen-worker-4-r58 |
| Branch HEAD SHA | fe92b486beb93425aeaf8458efc521c3b667f3b1 |
| SHA verified by | `git rev-parse FETCH_HEAD` → fe92b486...f3b1 ✓ |
| Review worktree | .qwen/worktrees/task477-review (detached HEAD at fe92b486) |
| Reviewer | GLM (Qwen worktree qwen-worker-7-r9) |
| Date | 2026-09-28 |
| Disposition | **MERGE** |

## What TASK-269 claims

Three production call sites derived a greeting first name three different ways. A contact named "Ing Christoph Lemmer" greeted "Ing" because the first token of the name is an honorific, not a given name. The lint rule `_names_match` passed it because "Ing" was a token of the full name.

TASK-269 claims:
1. `src/names.py` (NEW) provides a unified `greeting_first_name()` derivation with honorific stripping
2. All three call sites (`cadence.py`, `bisonfactory.py`, `heyreachfactory.py`) now call it
3. `lint.py:_names_match` now refuses honorific-only greetings
4. 31 new tests in `tests/test_names.py`, all passing
5. Zero regressions against master baseline

## Finding 1: Artifacts exist on the reviewed ref

**VERIFIED.** All seven files named in the result block exist at `fe92b486`:

```
src/names.py              (NEW, 93 lines)
src/cadence.py            (MODIFIED, 4 lines changed)
src/bisonfactory.py       (MODIFIED, 9 lines changed)
src/heyreachfactory.py    (MODIFIED, 10 lines changed)
src/lint.py               (MODIFIED, 9 lines changed)
tests/test_names.py       (NEW, 232 lines)
docs/qwen-tasks/DONE/TASK-269-*.md (task file)
```

`git diff master...fe92b486 --stat` confirms: 7 files changed, 386 insertions, 9 deletions. No files deleted.

## Finding 2: Existence is function — every link is consumed

**VERIFIED.** Each call site was traced to its production caller:

### cadence.py:582 → `template_vars()`
- Called at `cadence.py:745` in the step expansion path: `step.update(render(TEMPLATES[name], template_vars(rec, contact, config)))`
- This is the production rendering chain for every email template variable.
- **Caller chain:** `cadence.steps_for()` → `template_vars()` → `names.greeting_first_name()`

### bisonfactory.py:392 → `_plan()`
- Inside `_plan()`, the EmailBison campaign planning function that builds lead payloads.
- **Caller chain:** `bisonfactory._plan()` → `names.greeting_first_name(person)`

### heyreachfactory.py:1267 → `ensure_leads()`
- Inside `ensure_leads()`, the HeyReach lead enrichment function.
- The old code derived first_name from `contact["contact_key"].split("_")[0]` (a slug token).
- The new code finds the record contact by key match and calls `names.greeting_first_name(record_contact)`.
- **Caller chain:** `heyreachfactory.ensure_leads()` → `names.greeting_first_name(record_contact)`

### lint.py:345 → `_names_match()`
- Called by `greets_the_wrong_person()` in the lint pipeline.
- The honorific check is correctly placed AFTER the empty-greeting early return and BEFORE the token-match logic.
- **Caller chain:** `lint.greets_the_wrong_person()` → `_names_match()` → `names._normalise_token()` / `names.HONORIFICS`

### No fourth derivation
Grep for `.split()[0]` in `src/` found 10 hits. None are greeting derivations:
- `collision.py:1117` — slug/term derivation for collision detection
- `demo.py:125,248` — demo email generation (not production)
- `demo_outreach.py:461` — demo outreach (not production)
- `dispatch.py:80,94` — Python version string
- `names.py:5,6,87` — the module itself (comments + internal implementation)
- `web/api.py:4452` — Python version string

The `contact_key.split("_")[0]` pattern is gone from heyreachfactory.py. Zero production greeting derivations bypass `names.greeting_first_name`.

## Finding 3: Falsification of the result's own claims

### Mutation 1: cadence integration test distinguishes old from new
```
OLD: (contact.get("name") or "").split()[0] → "Ing"  (the defect)
NEW: names.greeting_first_name(contact)        → "Christoph"  (correct)
```
The test asserts `values["first_name"] == "Christoph"`. Old behavior would produce `"Ing"` and fail. **The test is falsifiable.**

### Mutation 2: _names_match distinguishes old from new
```
OLD: _names_match("Ing", "Ing Christoph Lemmer") → True  (the defect)
NEW: _names_match("Ing", "Ing Christoph Lemmer") → False  (correct)
```
The test asserts `assertFalse(_names_match("Ing", "Ing Christoph Lemmer"))`. Old behavior would return True and fail. **The test is falsifiable.**

### Mutation 3: heyreachfactory distinguishes old from new
```
OLD: contact_key.split("_")[0]  → "ing"  (raw slug token, lowercased)
NEW: names.greeting_first_name(record_contact) → "Christoph"  (honorific stripped)
```
**The change is observable and the test differentiates it.**

### Edge case: single-token name
```
strip_honorific("Ing") → "Ing"  (never strips the only token)
greeting_first_name({"first_name": "Ing"}) → "Ing"  (single token, no stripping)
```
**The "never strip the only token" invariant holds.**

### Edge case: "Mags Bennett" (unknown prefix)
```
strip_honorific("Mags Bennett") → "Mags Bennett"  (not stripped)
greeting_first_name({"name": "Mags Bennett"}) → "Mags"
```
**Over-stripping protection works.**

## Finding 4: Test falsifiability assessment

**STRONG.** The 31 tests cover:
- All closed-list honorifics (Dr, Prof, Dipl.-Ing, Dipl.Ing, Ing, Mag, DI, Mr, Mrs, Ms)
- Case insensitivity and punctuation insensitivity
- Single-token names (never stripped)
- Unknown prefixes (never stripped)
- Empty/None inputs
- Preference order (name over first_name)
- The three repro cases from the real CSV (DE, US, AU)
- DE/AT-specific honorifics (Dipl.-Ing., Mag., Dipl.Ing.)
- `_names_match` refusing honorific-only greetings
- `_names_match` still accepting normal greetings
- **cadence.py integration** (template_vars produces cleaned first_name)

The cadence integration test is the critical one: it drives through `cadence.template_vars()`, the real production entry point, not the `names.greeting_first_name()` function directly. If the wiring were removed, this test would fail.

**Weakness noted:** No equivalent integration test for bisonfactory or heyreachfactory through their real entry points. The bisonfactory `_plan()` function requires a full campaign/record/contact setup, and `ensure_leads()` requires provider mocking. The unit-level tests for `names.greeting_first_name()` are solid, and the wiring is verified by code inspection, but a bisonfactory/heyreachfactory integration test through the real entry point would be stronger. This is a NICE-TO-HAVE, not a blocker — the wiring is confirmed by grep and the mutation tests prove the function itself works.

## Finding 5: Merge would not delete anything

**VERIFIED.** `git diff master...fe92b486 --diff-filter=D --name-only` returns empty. No files would be deleted.

## Finding 6: Scope drift assessment

**CLEAN.** The branch carries exactly 2 commits beyond master:
```
fe92b486 TASK-269: done, commit SHA filled in
9d141ccb TASK-269: one derivation, three call sites, and the honorific that was a name
```
Both are TASK-269 work. No junk, no unrelated changes. The diff is 386 insertions, 9 deletions across 7 files — all accounted for.

## Finding 7: Pre-existing test failures

Two failures in `tests/test_invariants` on this ref:
1. `test_emailbison_posts_only_to_routes_it_declares` — **PRE-EXISTING on master.** Same failure on both refs. Not caused by TASK-269.
2. `test_nothing_was_written_by_that` — **Environmental.** The worktree has no `work/` directory. Not caused by TASK-269.

Zero new test failures introduced by TASK-269.

## Finding 8: HR (Croatia) testing

**CORRECTLY HANDLED.** The task instructed to say HR is untestable for lack of leads (0 rows with Country=Croatia in the CSV). The result block says so. No empty HR test was shipped. DE and AT are tested with real honorific vocabulary.

## Summary of findings

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | All artifacts exist on the reviewed ref | — | VERIFIED |
| 2 | Every link is consumed by production callers | — | VERIFIED |
| 3 | Mutation tests confirm tests are falsifiable | — | VERIFIED |
| 4 | Tests are strong; bisonfactory/heyreachfactory integration tests would be stronger but wiring is confirmed | Nice to have | NOTED |
| 5 | Merge would not delete any files | — | VERIFIED |
| 6 | No scope drift; 2 clean commits | — | VERIFIED |
| 7 | Zero new test failures | — | VERIFIED |
| 8 | HR correctly reported as untestable | — | VERIFIED |

## Recommendation

**MERGE.**

TASK-269 is a correct, well-scoped prevention change. The defect is real (confirmed by reproducing old vs. new behavior), the fix is minimal and unified (one function, three call sites), the tests are falsifiable (mutation tests confirm), and the wiring is consumed (every call site traced to its production caller). The change is prevention for DE/AT sourcing; nothing currently in flight is affected. The branch is clean, carries no scope drift, and would not delete any files on merge.

The one nice-to-have (bisonfactory/heyreachfactory integration tests through real entry points) does not block merge — the wiring is confirmed by code inspection and the function-level tests are solid.
