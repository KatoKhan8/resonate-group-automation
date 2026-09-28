# TASK-442 — GLM Independent Verification of TASK-285

**Reviewed branch:** `origin/qwen-worker-4-r9`
**Reviewed HEAD SHA:** `e05f401e6b3126bd248a7a54c14b3ba86828c73a`
**Branch has since moved to:** `2cb8755afc8ad069ccab24a6d80819d779c57e54`
**Review worktree:** `.qwen/worktrees/glm-442` (detached at target SHA)
**Date:** 2026-09-28

---

## Summary

**REWORK.** The three TASK-285 artifacts exist and are internally correct, but the test suite does not prove the wiring it claims to prove, and the branch carries severe scope drift that makes it unmergeable as-is. The walk was run, the report is thorough, and the classifier is correct — but the tests pin the report tool, not the eligibility gate, and a mutation that breaks `collision_cleared()` in `batch_eligibility.py` would go undetected.

---

## Findings

### Finding 1: Artifacts exist — PASS

All three allowed files are new on this branch and present at the target SHA:

- `docs/COLLISION-WALK-2026-09-25.md` — 262 lines, comprehensive walk report
- `tests/test_a_refused_domain_is_never_clear.py` — 192 lines, 15 tests, all pass
- `scripts/collision_walk_report.py` — 216 lines, report generation script

Verified with `git diff master...e05f401e -- <path>`: all three show as new files.

### Finding 2: Wiring — UNVERIFIED, tests do not prove it

**The wiring is pre-existing on master.** Both the walk writer (`scripts/s6_collision_walk.py`) and the consumer (`scripts/batch_eligibility.py`) exist on master with zero diff against this branch. The `collision_cleared()` function at `scripts/batch_eligibility.py:118` already reads `s6-collision-walk.json` on master.

**The tests do not test the wiring.** The test suite imports only:
```python
from scripts.collision_walk_report import classify
```

It does NOT import `collision_cleared` from `batch_eligibility`. Two tests (`test_refused_survives_policy_check`, `test_collision_cleared_logic_excludes_refused`) re-implement the `collision_cleared()` filtering logic inline rather than calling the real function.

**Mutation test — FAILED:** If I delete lines 118-126 of `scripts/batch_eligibility.py` (the walk-file read), all 15 tests still pass, because no test calls `collision_cleared()`. The wiring is untested.

This is the "test the text, not the behavior" defect the repository has been bitten by repeatedly (TASK-029, TASK-028, TASK-019 on 2026-09-14). The classifier is correct, but the connection between the walk output and the eligibility gate is not pinned by any test.

**The result block claims the wiring proof was done** ("Deleting the read at batch_eligibility.py:118 changes the cleared set"), but this was a manual check, not a test. It is not reproducible from the test suite.

**`batch_eligibility.py` is a standalone script** — it is not imported by anything in `src/`. No shell script or YAML file references it. Whether it is called by the generation pipeline is not visible in the code at this SHA.

### Finding 3: Scope drift — SEVERE

The branch diff against master:
- **69 files changed**, 14,648 insertions, 3,115 deletions
- **7 `src/` files changed**: `enrollmenttags.py` (+183), `generate_campaign.py` (+80), `notify.py` (+31), `push.py` (+11), `secondbrain.py` (+85), `spendledger.py` (+19), `workspaces.py` (+25)
- **25 task files** moved between TODO/REVIEW/DONE/BLOCKED
- **Multiple other tasks' work**: TASK-245, TASK-264, TASK-279, TASK-298, TASK-326, TASK-408, TASK-410, TASK-414, TASK-422, TASK-423, TASK-425, TASK-426, TASK-427, TASK-428, TASK-429

TASK-285's allowed files are exactly 3. The branch carries work for 15+ other tasks. **This branch cannot be merged as-is.** Only the 3 TASK-285 files could be cherry-picked.

### Finding 4: Deletion check — PASS

`git diff master...e05f401e --diff-filter=D --name-only` returns only 5 task files in `docs/qwen-tasks/TODO/` (moved to REVIEW/DONE/BLOCKED). No production code deleted. Safe.

### Finding 5: Report quality — PASS

The walk report (`docs/COLLISION-WALK-2026-09-25.md`) is thorough and well-structured:
- Four verdicts, counted, summing to the input set (577 + 2493 + 10 + 0 = 3080)
- Three COLLIDES rows with campaign IDs, dates, and ownership evidence
- One REFUSED row with the response shape that triggered it (1961 rows, BROAD_MATCH=200)
- Eligibility counts with walk output present/absent (800 walk-cleared + 868 legacy = 1668 union; 939 verified contacts on walk-cleared domains)
- Staleness field on every clearance
- Resume proof (3080/3080 walked, 0 todo on re-run)

The report claims the walk was run on 2026-09-22 against live provider state. I cannot independently re-run it (no access to production `work/` state or provider credentials), but the report is internally consistent and the numbers add up.

### Finding 6: Test quality — PARTIAL

The 15 tests are correct for what they test (the `classify()` function), but they do not test what the task requires (the wiring between walk output and eligibility gate).

**What the tests prove:**
- `classify()` correctly maps policy/verdict pairs to the four buckets
- REFUSED (policy=None) never enters the cleared set
- Staleness detection works (date comparison)
- The four buckets partition the input set

**What the tests do NOT prove:**
- `batch_eligibility.collision_cleared()` actually reads the walk file
- Deleting the walk-file read changes eligibility
- The walk output flows into production eligibility decisions

The task explicitly says: "A green `test_collision` suite as the proof" is not accepted. "The wiring and the provider's real response shape are." The suite is green, but the wiring is not tested.

---

## Disposition

**REWORK.**

**Reasons:**

1. **Tests are not falsifiable through the real entry point.** The test suite pins `classify()` from the report tool, not `collision_cleared()` from the eligibility gate. A mutation that breaks the wiring goes undetected. The task requires proving that "deleting the line that reads the walk output" changes eligibility — that proof must be in a test, not a manual check documented in a report.

2. **Scope drift is severe.** The branch carries 69 files of changes across 15+ tasks. Only 3 files belong to TASK-285. The branch cannot be merged; only cherry-pick is viable.

3. **Wiring is claimed but not pinned.** The result block claims the wiring proof was done manually, but the test suite does not reproduce it. The repository has been burned three times by "the test is green but the wiring is absent" (TASK-029, TASK-028, TASK-019). This is the same defect.

**What is correct and can be cherry-picked:**

- `docs/COLLISION-WALK-2026-09-25.md` — the walk report is thorough and well-documented
- `scripts/collision_walk_report.py` — the report script is correct
- The `classify()` function is correct and the 10 tests that pin it are valid

**What needs rework:**

- The test suite must import and test `batch_eligibility.collision_cleared()` directly, not re-implement its logic inline. A test that writes a fake walk state to a temp directory, calls `collision_cleared()`, and asserts the cleared set includes/excludes the right domains would pin the wiring.
- A mutation test that deletes the walk-file read in `batch_eligibility.py:118-126` and asserts the cleared set changes would prove the wiring is load-bearing.
- The branch needs to be split: TASK-285's 3 files cherry-picked to a clean branch, leaving the other 15+ tasks' work on separate branches.

---

## Reproducible commands

```bash
# Check out the target SHA
git worktree add .qwen/worktrees/glm-442 e05f401e6b3126bd248a7a54c14b3ba86828c73a --detach

# Run the tests
cd .qwen/worktrees/glm-442
python -m unittest tests.test_a_refused_domain_is_never_clear -v

# Check what the tests import
grep "^import\|^from" tests/test_a_refused_domain_is_never_clear.py
# → from scripts.collision_walk_report import classify
# → NOT from scripts.batch_eligibility import collision_cleared

# Check if batch_eligibility is imported by src/
grep -rn "batch_eligibility\|collision_cleared" src/
# → (no matches)

# Check the diff scope
git diff master...e05f401e --stat
# → 69 files changed, 14648 insertions(+), 3115 deletions(-)

# Check what's new vs pre-existing
git diff master...e05f401e -- scripts/batch_eligibility.py
# → (empty — pre-existing on master)

git diff master...e05f401e -- scripts/s6_collision_walk.py
# → (empty — pre-existing on master)
```

---

## Recommendation

**Cherry-pick the 3 TASK-285 files to a clean branch, rework the tests to pin the wiring, and leave the other 15+ tasks' work on separate branches.**

The walk was run, the report is good, and the classifier is correct. The defect is in the test suite: it tests the report tool, not the eligibility gate. That is fixable without re-running the walk.
