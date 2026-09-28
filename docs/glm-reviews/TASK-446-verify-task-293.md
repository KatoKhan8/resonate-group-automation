# GLM Verdict: TASK-293 — eligible in our store is not eligible at the provider

**TASK-446. Independent GLM verification.**

## Target

| Field | Value |
|---|---|
| Task | TASK-293 |
| Branch | qwen-worker-2-r9 |
| Branch HEAD SHA | `f03c74fc01a40df45419742e122268d11c8395a1` |
| Verified HEAD matches | YES — `git rev-parse origin/qwen-worker-2-r9` = `f03c74fc` |
| Review worktree | `C:/Users/Zvonimir/Desktop/resonate-qwen-7/.qwen/worktrees/glm-446` (detached at `f03c74fc`) |
| TASK-293 commit | `e733f297` |

## Summary

**REWORK.** Two confirmed bugs in the implementation, one of which is in a rule the task spec explicitly calls out as needing care. The tests do not cover either bug. The live run was not performed (acknowledged in the result block as "owed"). The artifact exists and the structure is sound, but the two code defects must be fixed before merge.

## Findings

### Finding 1 — CRITICAL: `check_approval` freshness check is dead code (NameError)

**File:** `scripts/qa/check_lead_state.py`, lines ~453-476

**Bug:** The `check_approval` function has a `NameError` on the freshness-check path. When `clientapproval.is_approved(domain)` returns `True`, the variable `state_row` is never assigned (it is only assigned inside the `if not approved:` block, which returns early). The subsequent `if state_row:` block then raises `NameError: cannot access local variable 'state_row'`.

**Reproduction:**
```python
from unittest import mock
from scripts.qa import check_lead_state

rec = {'domain': 'example.com', 'changed_at': '2026-09-27T10:00:00+00:00'}
contact = {'key': 'ceo', 'email': 'ceo@example.com'}

with mock.patch.object(check_lead_state.clientapproval, 'is_approved', return_value=True), \
     mock.patch.object(check_lead_state.clientapproval, 'state_of',
                       return_value={'at': '2026-09-01T00:00:00+00:00', 'state': 'approved'}):
    result = check_lead_state.check_approval(rec, contact)
    # → NameError: cannot access local variable 'state_row'
```

**Impact:** The task spec explicitly requires (rule 4): "approval_snapshot_covers must check the snapshot's FRESHNESS, not just its contents." The freshness check NEVER works for approved domains — which is the only case where freshness matters. The runner's generic `except Exception` handler catches the NameError and reports "unverifiable: rule error: ...", so approved-but-stale snapshots silently pass as "unverifiable" rather than failing as they should.

**Test gap:** No test exercises this path. `test_rule7_not_approved_fires` only tests the `not approved` branch. There is no `test_rule7_stale_snapshot_fires`.

**Severity:** Critical. The task spec names this as one of the five rules "that need care." The precedent document `docs/THE-ROSTER-IS-A-SNAPSHOT-NOBODY-REFRESHES-2026-09-17.md` exists because stale snapshots have already caused harm.

### Finding 2 — MEDIUM: `check_timezone` silently defaults missing schedule timezone

**File:** `scripts/qa/check_lead_state.py`, line ~521

**Bug:** When `bison.schedule(campaign_id)` returns a schedule dict with no `timezone` key, the code silently defaults to `"America/New_York"`:
```python
sched_tz = sched.get("timezone") or "America/New_York"
```

**Reproduction:**
```python
fake_sched = {'start': 9, 'end': 17, 'days': [1,2,3,4,5]}  # no timezone
with mock.patch.object(check_lead_state.bison, 'schedule', return_value=fake_sched):
    result = check_lead_state.check_timezone(rec, contact)
    # → verdict uses "America/New_York" silently
```

**Impact:** The task spec explicitly forbids this: "A guessed timezone is worse than a missing one — CLAUDE.md." A missing schedule timezone should yield `unverifiable`, not a fabricated one. The default could cause false failures (campaign actually runs in Europe/Zagreb but is judged against America/New_York hours) or false passes depending on the time of day.

**Test gap:** No test exercises the missing-timezone path. `test_rule8_window_closed_fires` provides a schedule with explicit timezone.

### Finding 3 — INFORMATIONAL: No production consumer (acknowledged)

`scripts/qa/check_lead_state.py` has zero callers in `src/`. The only references are:
- Its own `__main__` CLI entry point
- The QA registry (`scripts/qa/__init__.py`)
- The test file

The result block acknowledges this and recommends "Wire into pre-push refusal in bisonfactory.stage (§5 of contract)." This is a QA tool designed to be run as a pre-push gate, so the absence of a production caller is expected at this stage — but it means the module is not yet integrated into the execution stream. Not a defect in the task delivery, but a dependency for the wiring task.

### Finding 4 — INFORMATIONAL: Scope drift on the branch

The branch `qwen-worker-2-r9` carries 38 commits and changes to 93 files (+10,615 / -315 lines). TASK-293's own commit (`e733f297`) is clean: 5 files, +1,441 / -0. The branch also carries work from TASK-364, TASK-387, TASK-318, TASK-372, TASK-397, TASK-411, TASK-400, TASK-403, TASK-410, TASK-423/424/425, and others.

**Cherry-pick scope for TASK-293 alone:** The four new files (`scripts/qa/__init__.py`, `scripts/qa/check_lead_state.py`, `tests/test_a_lead_eligible_here_can_be_in_sequence_there.py`, `docs/QA-LEAD-STATE-2026-09-25.md`) and the task file move can be cherry-picked cleanly. No dependency on the other branch changes.

### Finding 5 — CONFIRMED: No deletion of master content

The branch deletes one file vs master: `docs/qwen-tasks/TODO/TASK-372-the-suite-baseline-is-73-failures-short.md` — a task file that was moved to REVIEW. No production code, no configuration, no documentation content is deleted.

### Finding 6 — CONFIRMED: Tests are partially falsifiable

The 18 tests drive through the real `run()` entry point, not individual rule functions. Each test constructs an offending record and asserts it appears in the correct rule's offender list. This is the right structure.

However, the tests are not fully falsifiable:
- The approval freshness path (Finding 1) has no test at all
- The timezone default path (Finding 2) has no test
- Breaking the wiring (e.g., removing the call to `check_approval` from `ALL_RULES`) would cause `test_rule7_not_approved_fires` to fail, confirming the test is connected — but only for the "not approved" branch

## What works

- The eight-rule structure is correct and well-organized
- The ISSUE-035 carve-out (own stop is not a reply) is correctly implemented and tested
- The key-presence reporting is implemented
- The arithmetic closure invariant is enforced
- The `unverifiable` verdict is correctly separated from pass/fail
- The ours-vs-theirs tracking for `not_in_a_live_sequence` is implemented
- The QA registry pattern prevents the "module with no caller" defect class
- The CLI interface with `--workspaces`, `--live-reads`, `--json` is correct
- PII safety: `_lead_id_pii_safe` strips email addresses for committed artifacts

## Disposition

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | `check_approval` NameError on freshness path | Critical | REWORK — fix the variable scope, add a test |
| 2 | `check_timezone` silent timezone default | Medium | REWORK — return unverifiable when schedule has no timezone |
| 3 | No production consumer | Informational | Acknowledged; wiring is a separate task |
| 4 | Branch scope drift | Informational | TASK-293's files cherry-pick cleanly |
| 5 | No master content deleted | Confirmed | Clean |
| 6 | Tests partially falsifiable | Informational | Good structure; two gaps match the two bugs |

## Recommendation

**REWORK.** Fix the two bugs (Finding 1 and Finding 2), add tests for both fixed paths, and re-submit. The cherry-pick surface is clean and the overall structure is sound — this is a targeted fix, not a rebuild.

The live run over the real 128 remains owed regardless of this verdict.
