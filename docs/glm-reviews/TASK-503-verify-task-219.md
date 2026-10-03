# GLM Verdict: TASK-503 — Independent verification of TASK-386

**Reviewed branch:** `origin/qwen-worker-8-r9`
**Reviewed HEAD SHA:** `afa48d18ab6df1e3478cd7abf1c30a59287ddd59`
**Branch HEAD at time of fetch:** `eb3b3e1d76bd24ea893697a7d283da47e45469fa` (has moved; reviewed SHA as instructed)
**Worktree:** `.qwen/worktrees/task503-review` (detached at `afa48d18a`)
**Master at time of review:** `2bf7b8a57`
**Date:** 2026-10-03

---

## 1. Does the artifact exist on this ref?

**YES, with caveats.**

TASK-386's core artifact is two files:

| File | Status at `afa48d18a` |
|------|----------------------|
| `src/packfacts.py` | Modified: +42 lines adding `_add_company_facts()` and `_add_linkedin_facts()`, wired into `pack_for()` at lines 139-140 |
| `tests/test_packfacts_includes_record_facts.py` | New file: 226 lines, 17 tests across 4 classes |

Both exist at the reviewed SHA. Verified with `git ls-tree` and `read_file`.

**However:** master has since evolved `src/packfacts.py` significantly (TASK-348, CLIENT_SUPPLIED operator decision). Master's current `packfacts.py` does NOT contain `_add_company_facts` or `_add_linkedin_facts`. It has a different approach: `client_supplied_facts()` reads `company_facts` keys including `headcount` but places them in `unused[CLIENT_SUPPLIED]`, deliberately NOT in `pack["facts"]` (the claim licence).

## 2. Does it do what the result block claims?

**YES, within its own frame.**

The result block claims:
- Headcount from `company_facts.headcount` is included in the pack when state is `agreed`/`single_source` and value is a positive int. **Verified.**
- LinkedIn URLs from contacts and `company_facts.linkedin` are included when present. **Verified.**
- Conflict, unestablished, band-only, and zero headcounts are excluded. **Verified.**
- Missing evidence is never positive evidence. **Verified.**

I independently reproduced all five claims with direct function calls in the worktree:

```
PASS: headcount:45 in pack with wiring intact
PASS: conflicted headcount correctly excluded
PASS: band-only headcount correctly excluded
PASS: invented headcount 200 correctly flagged by copylint
PASS: real headcount 45 correctly traces
```

## 3. Existence is not function — is every link consumed?

**YES.** The production chain is complete:

```
src/bisonfactory.py:559  →  packfacts.pack_for(rec)
src/packfacts.py:139-140  →  _add_company_facts / _add_linkedin_facts
src/packfacts.py:141  →  returns {"facts": admitted}
src/bisonfactory.py:573  →  copylint.check_batch(leads, packs, ...)
src/bisonfactory.py:87  →  _refuse_copylint(plan, recs, report)
```

`pack_for` is called by `bisonfactory._copylint_batch` which feeds `copylint.check_batch`. The pack's facts are what `copylint.untraceable` checks claims against. The chain is real and consumed.

## 4. Are the tests falsifiable?

**YES, with one reservation.**

The tests assert on `pack_for`'s output (what the pack contains), not on source text. They drive the real entry point and check the resulting pack object. The `WiringCheck` class explicitly tests that removing the calls causes facts to disappear.

The `EndToEndTrace` class goes further: it feeds the pack into `copylint.untraceable` and verifies that a real headcount (45) traces while an invented one (200) does not. This is the right test.

**Reservation:** The tests construct records by hand with `company_facts.headcount` in the resolved shape. They do not test the path from enrichment (`headcount.resolve`) to the pack. This is acceptable for a unit test of `pack_for`, but the end-to-end path from enrichment through to the pack is not exercised by these tests alone.

## 5. Would merging DELETE anything?

**No production code would be deleted.** The three files deleted by the branch are task files moving through their lifecycle (TODO → REVIEW/DONE):
- `docs/qwen-tasks/TODO/TASK-334-...` (superseded, closed)
- `docs/qwen-tasks/TODO/TASK-373-...` (integrated)
- `docs/qwen-tasks/TODO/TASK-375-...` (integrated)

These are normal task lifecycle moves, not production deletions.

## 6. Scope drift

**SIGNIFICANT.** The branch carries 20 commits from multiple tasks:

| Task | Status on master |
|------|-----------------|
| TASK-373 (spend gate threading) | Already integrated (`af108baf0`, `4c8496150`, `77221f9f3`) |
| TASK-374 (write-audit scanner) | Already integrated (`a8b21a2e4`) |
| TASK-375 (skill loading) | Already integrated (`bcdfccf44`) |
| TASK-376 (researchpack demotion) | Already integrated (`149a3730c`) |
| TASK-377 (canary disposition) | Already integrated (`c20ebbd8b`) |
| TASK-379 (GLM verify TASK-369) | GLM review dispatch, not code |
| TASK-382 (GLM verify TASK-367) | GLM review dispatch, not code |
| pool.sh / pool_watchdog.sh | Infrastructure, already on master via other paths |
| **TASK-386** | **The only unique code contribution** |

TASK-386's cherry-pick scope is 3 commits (`0b95e5070`, `eb66a0025`, `55d94e1ea`, `afa48d18a`) touching 2 production files.

## 7. Merge conflicts

**22 files are changed in both master and the branch.** These are mostly TASK-373's `client`/`config` kwarg threading through `model.complete()` signatures, which was already integrated into master via different commits. The branch's versions of these changes will conflict with master's already-integrated versions.

`src/packfacts.py` is the critical conflict: master has rewritten it with the CLIENT_SUPPLIED framework while the branch adds `_add_company_facts`/`_add_linkedin_facts`. These are architecturally different approaches to the same area.

---

## Findings

### F1: The artifact is real and well-tested [VERIFIED]
- 17/17 tests pass
- Production chain is complete: `pack_for` → `bisonfactory._copylint_batch` → `copylint.check_batch`
- Falsification confirms tests catch both positive and negative cases
- Headcount gating logic is correct (state + value checks)

### F2: Master has superseded the approach [CONFLICT]
- Master's TASK-348 + CLIENT_SUPPLIED operator decision (2026-09-27) deliberately keeps `company_facts` out of `pack["facts"]`
- The operator decision states: "A prospect-facing claim still needs a public source or a stored page, never the CSV alone"
- TASK-386's `_add_company_facts` puts resolved headcount directly into the claim licence
- These are not the same thing: TASK-386's headcount comes from enrichment (`headcount.resolve`), not the raw CSV, so it has stronger provenance than CLIENT_SUPPLIED
- But master's architecture does not distinguish enrichment-derived from CSV-derived company_facts at the packfacts level

### F3: The LinkedIn URL path is not in conflict [COMPATIBLE]
- Master does not handle LinkedIn URLs at all in the current packfacts
- TASK-386's `_add_linkedin_facts` (contact LinkedIn profiles) and the `company_facts.linkedin` part of `_add_company_facts` add new capability master lacks
- This part could be cherry-picked without conflicting with the CLIENT_SUPPLIED framework

### F4: The branch cannot be merged as-is [BLOCKER]
- 22 files changed in both, mostly duplicate integrations of TASK-373/375
- `src/packfacts.py` has architectural divergence
- A merge would require conflict resolution across the entire TASK-373 surface

### F5: TASK-386's finding about ingest is still valid [OPEN]
- The result block correctly identifies that `ingest.py` (CLI path) drops LinkedIn URLs
- The `Url` column normalises to `url` which is not in `columns.py`'s alias table
- This finding was not addressed by master's subsequent changes

---

## Disposition

| Finding | Severity | Disposition |
|---------|----------|-------------|
| F1: Artifact real and tested | — | VERIFIED |
| F2: Master superseded approach | P1 | OPERATOR DECISION REQUIRED |
| F3: LinkedIn path compatible | — | CHERRY-PICKABLE |
| F4: Branch cannot merge as-is | P1 | REWORK |
| F5: Ingest finding still open | P2 | EXISTING TASK (TASK-347 follow-up) |

---

## Recommendation: **REWORK**

**Reason:** The artifact is real, the tests are good, and the production chain is complete. But master has moved past this branch with a different architectural decision (CLIENT_SUPPLIED). The branch cannot be merged without conflict resolution, and the conflict is not mechanical — it is a design question about whether resolved enrichment data should enter the claim licence.

**What should be cherry-picked:**
1. `_add_linkedin_facts()` and the LinkedIn part of `_add_company_facts()` — master has no LinkedIn handling, these are additive
2. The test file `tests/test_packfacts_includes_record_facts.py` — after adapting to master's current packfacts API

**What needs an operator decision:**
- Should a resolved headcount (state=`agreed`, value=45, from enrichment) enter `pack["facts"]` as a claim licence?
- TASK-386 says yes (it is verified data). Master's CLIENT_SUPPLIED framework says no (only identity-admitted research with a public source is a claim licence).
- The operator (Zvonimir) decided on 2026-09-27 that client-CSV facts are not a claim licence. The question is whether enrichment-derived headcount is in the same category.

**What should NOT be merged:**
- The branch's TASK-373/375/376/377 changes — already on master via different commits
- The branch's `model.complete()` signature changes — already on master
- The pool.sh/pool_watchdog.sh changes — already on master
