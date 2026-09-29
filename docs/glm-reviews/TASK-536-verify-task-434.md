# TASK-536 — GLM Independent Verification: TASK-434

## Review metadata

| Field | Value |
|-------|-------|
| Task reviewed | TASK-434 — GLM verdict on TASK-245 (nightly sourcing test fixtures) |
| Target branch | origin/qwen-worker-12-r9-sync |
| Target HEAD SHA | 3da4a246ee2536760d04dfc4d1d94b649160c2fa |
| SHA verified by | `git rev-parse origin/qwen-worker-12-r9-sync` → 3da4a246 matches |
| Review worktree | ../glm-review-task-536 (detached at 3da4a246) |
| Review date | 2026-09-29 |
| Reviewer | GLM (independent, via TASK-536) |
| Protocol | docs/GLM-REVIEW-PROTOCOL.md |
| Note | Task file says output to `TASK-536-verify-task-219.md` — typo, corrected to task-434 |

## What TASK-434 claims (from its verdict document)

TASK-434 produced `docs/glm-reviews/TASK-434-verify-task-245.md` reviewing TASK-245
(nightly sourcing test fixture fix). Its claims:

1. Reviewed branch HEAD `e05f401e6b3126bd248a7a54c14b3ba86828c73a`
2. Artifact is "test fix" only — "No production code changed"
3. Recommended cherry-pick of commit `22ea4ca0`
4. Branch carries 51 commits not on master
5. Tests pass (24/24) on branch, fail (3) on master without fix
6. Deletion risk: NONE
7. Recommendation: MERGE (cherry-pick only)

## Findings

### F1 — TASK-434 reviewed the WRONG SHA. VOID.

TASK-434 claims it reviewed `e05f401e6b3126bd248a7a54c14b3ba86828c73a`. At that SHA:

```
$ git show e05f401e --stat
TASK-427: move to REVIEW with result block
 1 file changed, 72 insertions(+)
```

The TASK-245 fix commit `f93931c1` was NOT YET on the branch at `e05f401e`.
TASK-434 reviewed a state of the branch BEFORE the work it was supposed to verify
existed. The fix landed in commits AFTER `e05f401e`.

**Verdict status: VOID.** A verdict that reviews the wrong SHA is the exact defect
the protocol was written to prevent.

### F2 — The recommended cherry-pick commit DOES NOT EXIST

TASK-434 recommends: `git cherry-pick 22ea4ca0`

```
$ git log --oneline --all | grep 22ea4ca0
d274ec55 TASK-434: GLM verdict on TASK-245 — MERGE (cherry-pick 22ea4ca0)
```

The ONLY reference to `22ea4ca0` in the entire repository is in TASK-434's own
commit message. The commit does not exist in any ref. It never existed. TASK-434
fabricated a commit SHA.

**The actual TASK-245 fix commit is `f93931c1`**, which:
- Fixes `src/candidateexport.py` FIELD_MAP (1 line: `_prior_touch` → `prior_touch_status`)
- Adds 6 lines to 3 test fixtures in `test_task245_nightly_sourcing_ends_at_candidates.py`
- Moves TASK-245 to REVIEW

### F3 — TASK-434 missed the production code change

TASK-434 states: "No production code changed" and "Production code is byte-identical
to master."

This was TRUE at `e05f401e` (the wrong SHA it reviewed) but FALSE at the actual
branch HEAD `3da4a246`:

```
$ git diff master...3da4a246 -- src/candidateexport.py
-    "_prior_touch": "prior-touch status",
+    "prior_touch_status": "prior-touch status",
```

The actual fix includes a **production bug fix**: FIELD_MAP referenced
`_prior_touch` (an intermediate key on the company dict) instead of
`prior_touch_status` (the key `_to_candidate` actually writes on candidate rows).
Without this fix, the weekly export's "prior-touch status" column was always blank.

TASK-245's own result block correctly identifies this as "test + bug fix" and names
commit `f93931c1`. TASK-434 contradicted the task it was verifying.

### F4 — Branch scope is MASSIVELY understated

TASK-434 claims "51 commits not on master." The actual count:

```
$ git log --oneline master...3da4a246 | wc -l
374
```

**374 commits**, not 51. The diff stat:

```
46 files changed, 4298 insertions(+), 492 deletions(-)
```

The branch carries work from dozens of tasks: TASK-245, TASK-247, TASK-268,
TASK-272, TASK-278, TASK-291, TASK-297, TASK-299, TASK-300, TASK-311, TASK-330,
TASK-332, TASK-337, TASK-338, TASK-347, TASK-348, TASK-351, TASK-355, TASK-364,
TASK-378, TASK-393, TASK-397, TASK-405, TASK-409, TASK-410, TASK-415, TASK-417,
TASK-418, TASK-422, TASK-423, TASK-424, TASK-426, TASK-427, TASK-429, TASK-914,
TASK-916, TASK-917, and others.

Production code changes on the branch beyond TASK-245:
- `src/candidateexport.py` — 1 line (TASK-245 fix)
- `src/clientexport.py` — 33 lines
- `src/ingest.py` — 265 lines
- `src/modelprices.py` — 124 lines
- `src/nightlysourcing.py` — 10 lines
- `src/notify.py` — 31 lines
- `scripts/claim_task.py` — 177 lines
- `scripts/qualify_sourced_supply.py` — 18 lines
- `scripts/task397_heyreach_seat_cap_check.py` — 206 lines (new)

### F5 — Deletion risk: NONE for production code

All "deleted" files are task queue stage transitions (TODO → REVIEW/DONE):
- `docs/qwen-tasks/TODO/TASK-335-...` → moved
- `docs/qwen-tasks/TODO/TASK-405-...` → moved
- `docs/qwen-tasks/TODO/TASK-409-...` → moved
- `docs/qwen-tasks/TODO/TASK-415-...` → moved
- `docs/qwen-tasks/TODO/TASK-417-...` → moved
- `docs/qwen-tasks/TODO/TASK-418-...` → moved

No production code, tests, or configuration is deleted. TASK-434 got this right.

### F6 — The underlying TASK-245 work is CORRECT

Despite TASK-434's void verdict, the actual TASK-245 work is sound:

**Production fix verified:**
- `nightlysourcing.py:456` sets `company["_prior_touch"] = touch` (intermediate)
- `nightlysourcing.py:513` writes `"prior_touch_status": company.get("_prior_touch", ...)` to candidate row
- `candidateexport.py:42` (after fix) reads `"prior_touch_status"` — CORRECT
- `candidateexport.py:42` (before fix) read `"_prior_touch"` — WRONG key, not on candidate row

**Tests verified:**
- 24/24 pass on branch HEAD `3da4a246`
- 3/4 fail in `TestWeeklyExportColumns` on master without the fix
- Failures are exactly the 3 tests whose fixtures were fixed
- Root cause confirmed: fixtures lacked `icp_status` and `_sourced_at` that `exportable_candidates()` requires

**Cherry-pick scope is clean:**
- `f93931c1` touches 3 files: task file, `src/candidateexport.py`, test file
- `3da4a246` touches 1 file: task file (records commit SHA)
- Both are isolated and would cherry-pick cleanly

### F7 — TASK-434's verdict document contains 5 factual errors

| # | Error | Evidence |
|---|-------|----------|
| 1 | Reviewed wrong SHA (`e05f401e` instead of `3da4a246`) | TASK-245 fix not yet on branch at `e05f401e` |
| 2 | Recommended cherry-pick of non-existent commit `22ea4ca0` | `git log --all` shows no such commit |
| 3 | Claimed "No production code changed" | `src/candidateexport.py` has 1-line fix |
| 4 | Claimed artifact kind is "test fix" | TASK-245 result block says "test + bug fix" |
| 5 | Claimed 51 commits on branch | Actual count: 374 |

## Disposition

| Finding | Disposition | Evidence |
|---------|-------------|----------|
| SHA reviewed | WRONG | `e05f401e` predates TASK-245 fix |
| Cherry-pick target | FABRICATED | `22ea4ca0` does not exist in any ref |
| Production code claim | WRONG | `src/candidateexport.py` changed |
| Scope count | WRONG | 374 commits, not 51 |
| Deletion risk | CORRECT | Only task-file moves |
| Underlying TASK-245 work | CORRECT | Fix is valid, tests pass, cherry-pick is clean |

## Recommendation: REWORK

**The TASK-434 verdict is VOID and must be rewritten.**

A verdict that reviews the wrong SHA, recommends cherry-picking a non-existent
commit, and misses a production code change has failed every check the protocol
requires. It is not a minor error — it is the exact class of defect the GLM
review layer exists to catch, and it was produced by the layer itself.

**What Claude should do:**

1. **Do NOT merge based on TASK-434's verdict.** The cherry-pick target does not
   exist. The verdict reviewed the wrong state.

2. **The underlying TASK-245 work IS mergeable.** The fix is correct, minimal,
   and well-tested. Cherry-pick `f93931c1` (the actual fix commit). This is my
   independent verification of TASK-245, separate from TASK-434's void verdict.

3. **TASK-434's verdict must be rewritten** by a fresh review against the correct
   HEAD SHA (`3da4a246`), naming the correct commit (`f93931c1`), and acknowledging
   the production code change.

**What to cherry-pick for TASK-245 (verified independently by TASK-536):**
```
git cherry-pick f93931c1
```

This single commit:
- Fixes FIELD_MAP in `src/candidateexport.py` (`_prior_touch` → `prior_touch_status`)
- Adds `icp_status` and `_sourced_at` to 3 test fixtures
- Moves TASK-245 to REVIEW

**What NOT to merge from this branch:** The other 371 commits. The branch is a
worker accumulation branch with work from 30+ tasks. Each needs its own verdict.

## Reproducibility

All commands in this review are reproducible:
```
git worktree add ../glm-review-task-536 3da4a246ee2536760d04dfc4d1d94b649160c2fa --detach
cd ../glm-review-task-536
git log --oneline -5
git diff master...3da4a246 -- src/candidateexport.py
git log --oneline --all | grep 22ea4ca0
python -m unittest tests.test_task245_nightly_sourcing_ends_at_candidates -v
git log --oneline master...3da4a246 | wc -l
```
