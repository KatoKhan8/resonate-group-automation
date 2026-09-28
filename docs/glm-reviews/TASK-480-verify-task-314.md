# TASK-480 — Independent verification of TASK-314

## Review metadata

| Field | Value |
|-------|-------|
| Target task | TASK-314 |
| Target branch | `origin/qwen-worker-11-task314` |
| Branch HEAD SHA | `ddc0bc816fed25b327cbe070d0597ba03ae2b67e` |
| SHA verified by | `git rev-parse origin/qwen-worker-11-task314` → matches |
| Review worktree | `.qwen/worktrees/task480-review` (detached at exact SHA) |
| Review date | 2026-09-28 |
| Reviewer | Qwen (independent GLM verdict) |

## TASK-314 claims

1. Found the bug where HeyReach LinkedIn steps were silently dropped: `cadence.expand_step` checked `stored.get("body")` instead of `stored.get("note")` for LinkedIn steps.
2. The fix is "already in place" at `src/cadence.py` lines 912-913.
3. Created a regression test `tests/test_no_cadence_step_is_silently_dropped.py` with 3 tests.
4. The test fails when the bug is reintroduced.

## Findings

### Finding 1: The fix is on master, not from TASK-314

**Severity**: Informational
**Confidence**: High

`git diff master...ddc0bc81 -- src/cadence.py` returns **empty**. The fix at lines 909-910:

```python
written = stored.get("body") if spec.get("channel") == "email" \
    else stored.get("note")
```

is identical on master and the branch. TASK-314 did not introduce the fix; it was already present. The result block's line numbers (912-913) are also slightly off — the fix is at lines 909-910 on both refs.

**TASK-314's actual deliverable is the regression test alone.**

### Finding 2: The regression test exists and passes

**Severity**: None (positive finding)
**Confidence**: High

```
$ python -m unittest tests.test_no_cadence_step_is_silently_dropped -v
test_a_step_with_no_copy_is_refused_not_dropped ... ok
test_all_configured_linkedin_steps_surface_when_approved ... ok
test_breaking_the_fix_causes_the_test_to_fail ... ok

Ran 3 tests in 0.076s
OK
```

### Finding 3: The test is falsifiable — independently verified

**Severity**: None (positive finding)
**Confidence**: High

I independently reverted the fix (lines 909-910 → `written = stored.get("body")`) and ran the primary test:

```
FAIL: test_all_configured_linkedin_steps_surface_when_approved
AssertionError: 1 != 5 : Expected 5 LinkedIn steps with content in the timeline,
but found 1. Missing: {'li5', 'li4', 'li2', 'li3'}.
```

The test correctly catches the exact bug through the real production entry point (`cadence.build()`), fails for the intended reason (LinkedIn steps return None because `body` is empty when copy is in `note`), and no different guard fires first.

After restoring the fix, all 3 tests pass again.

### Finding 4: The test goes through the real production entry point

**Severity**: None (positive finding)
**Confidence**: High

- The test calls `cadence.build(rec, self.config)` — the same function called by `approve.py`, `campaigns.py`, `preview.py`, `push.py`, `coherence.py`, `eligibility.py`, `plan.py`, `qa.py`, `report.py`, `web/api.py`, and others (38 call sites in `src/`).
- `cadence.build()` internally calls `expand_step()` for each step — the function where the bug lived.
- The test asserts on the output of `cadence.build()`, not on `expand_step()` directly.
- No `hasattr`, no source text assertions, no JSON shape checks, no fake cassettes.
- Uses real fixture data from `tests/fixtures/phase7.jsonl`.

### Finding 5: The mutation test (test 3) is valid but redundant

**Severity**: Informational
**Confidence**: High

The third test patches `cadence.expand_step` to simulate the old bug and asserts the count assertion would fail. This is a valid meta-test, but I independently verified the same thing by actually reverting the fix in the source code (Finding 3). The meta-test is not wrong — it just duplicates evidence I produced more directly.

### Finding 6: Significant scope drift on the branch

**Severity**: Rework
**Confidence**: High

The branch carries work from at least 6 tasks, not just TASK-314:

| Task | Files |
|------|-------|
| TASK-314 | `tests/test_no_cadence_step_is_silently_dropped.py`, task file movement |
| TASK-296 | `scripts/qa/check_campaign_bison.py`, `src/bisonfactory.py`, `src/heyreachfactory.py`, `tests/test_every_representation_derives_from_one_plan.py`, `docs/QA-CAMPAIGN-BISON-2026-09-25.md` |
| TASK-364 | `src/sequenceplan.py`, `tests/test_step_counts_agree_while_the_keys_do_not.py` |
| TASK-398 | `docs/qwen-tasks/REVIEW/TASK-398-suppression-list-audit.md` |
| TASK-413 | `scripts/task413_seat_cap_check.py`, `scripts/task413_seat_cap_probe.py`, `docs/state/TASK-413-SEAT-CAP-CHECK.json` |
| TASK-410 | `docs/qwen-tasks/TODO/TASK-410-glm-verify-task-400-critical-path.md` |
| Infrastructure | `scripts/stage_work_to_host.sh`, `docs/state/SENDER-CAPACITY.json` |

**Cherry-pick scope for TASK-314 alone:**
- `tests/test_no_cadence_step_is_silently_dropped.py` (new file)
- `docs/qwen-tasks/DONE/TASK-314-where-the-heyreach-steps-are-lost.md` (task file moved from TODO)

Merging the entire branch would bring in all the other tasks' work, which may or may not be ready.

### Finding 7: Merging would not delete production code

**Severity**: None (positive finding)
**Confidence**: High

`git diff master...ddc0bc81 --diff-filter=D --name-only` shows only task file movements:
- `docs/qwen-tasks/TODO/TASK-314-where-the-heyreach-steps-are-lost.md`
- `docs/qwen-tasks/TODO/TASK-398-suppression-list-audit.md`
- `docs/qwen-tasks/TODO/TASK-413-heyreach-seat-cap-check.md`

These are task files being moved from TODO to REVIEW/DONE — expected and correct. No production code, tests, or configuration is deleted.

### Finding 8: No weak assertion patterns

**Severity**: None (positive finding)
**Confidence**: High

`grep` for `hasattr`, `assertTrue.*in`, `assertIn.*source`, `open.*\.py` returns empty. All assertions are behavioral:
- `assertEqual` on count of LinkedIn steps with content
- `assertEqual` on step key sets
- `assertIn` checking a step appears in the timeline
- `assertRaises(AssertionError)` wrapping a count assertion (meta-test)

## Disposition

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | Fix already on master, not from TASK-314 | Informational — the task file says "already in place" |
| 2 | Regression test exists and passes | Verified |
| 3 | Test is falsifiable | Independently verified by reverting the fix |
| 4 | Test uses real production entry point | Verified — `cadence.build()` has 38 callers in `src/` |
| 5 | Mutation test is valid but redundant | Informational |
| 6 | Significant scope drift | Rework — cherry-pick only TASK-314 files |
| 7 | No deletion risk | Verified |
| 8 | No weak assertions | Verified |

## Recommendation

**MERGE** — with cherry-pick, not whole-branch merge.

TASK-314's deliverable (the regression test) is genuine, falsifiable, and load-bearing. It tests through the real production entry point, asserts on behavior not structure, and catches the exact bug it claims to catch. The fix was already on master, so the test is a regression guard, not a fix — but that is what the task file claims and it delivers.

**Cherry-pick only:**
- `tests/test_no_cadence_step_is_silently_dropped.py`
- `docs/qwen-tasks/DONE/TASK-314-where-the-heyreach-steps-are-lost.md`

The other 18 files on the branch belong to other tasks and should be merged through their own review processes.

## Reproducible commands

```bash
# Verify the branch HEAD SHA
git fetch origin qwen-worker-11-task314
git rev-parse origin/qwen-worker-11-task314
# Expected: ddc0bc816fed25b327cbe070d0597ba03ae2b67e

# Create isolated worktree
git worktree add .qwen/worktrees/task480-review ddc0bc816fed25b327cbe070d0597ba03ae2b67e --detach

# Run the regression test
cd .qwen/worktrees/task480-review
python -m unittest tests.test_no_cadence_step_is_silently_dropped -v

# Verify the fix is identical on master
git diff master...ddc0bc81 -- src/cadence.py
# Expected: empty

# Independently falsify: revert the fix and run the test
# (See Finding 3 for the exact reversion and expected failure)
```
