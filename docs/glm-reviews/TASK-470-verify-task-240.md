# GLM Independent Verification: TASK-240

**Review target:** TASK-240 — The arity rule moves from the campaign to the action
**Branch:** `origin/qwen-worker-r55`
**Branch HEAD SHA reviewed:** `8f4406e1bb2a4f9ce273b16785011c88da26b4f1`
**SHA verified with:** `git rev-parse origin/qwen-worker-r55` → `8f4406e1bb2a4f9ce273b16785011c88da26b4f1` ✓
**Review date:** 2026-09-28
**Reviewer:** GLM (independent verification)
**Isolated worktree:** Created at exact SHA, reviewed there, cleaned up after

---

## CRITICAL FINDING: Already Integrated

**This work is already on master.** TASK-241 (`90bd119b`) integrated the arity rule change, and master has since moved 920 files and ~195,000 lines ahead. The branch `qwen-worker-r55` is obsolete.

Evidence:
- `git log --oneline master --grep="TASK-241"` shows `90bd119b TASK-241: arity rule moves to action, gate order preserved`
- `git show master:src/executionguard.py | grep "_owner_for"` returns 5 hits (lines 674, 681, 684, 1249, 1260)
- `git show master:tests/test_task240_arity_rule_moves_to_action.py` exists
- `git diff origin/qwen-worker-r55 master -- tests/test_no_write_happens_without_every_gate.py` is empty (identical)
- Master's `executionguard.py` has additional improvements: compliance gate (lines 583-608), try/except wrapper for gate trace (lines 677-684)

**Merging this branch would be a no-op or cause conflicts.** The work is already done.

---

## Verification Results

Despite the branch being obsolete, I verified the artifact at the exact SHA as instructed.

### 1. Does the artifact exist, and does it do what the result block claims?

**YES, verified.**

- `_owner_for` function defined at `src/executionguard.py:1115-1184` ✓
- Replaces `_sender_for` (deprecated at line 1101, no production callers) ✓
- Returns `(human_sender_id, seats)` tuple ✓
- Refuses when: no senders, unowned seat, uninventoried seat, deactivated seat, unhealthy seat, another client's seat, or multiple humans ✓
- All five required protections preserved (unowned, uninventoried, deactivated, unhealthy, another client) ✓

### 2. Existence is not function: is `_owner_for` consumed?

**YES, verified.**

```bash
$ git show origin/qwen-worker-r55:src/executionguard.py | grep -n "_owner_for"
648:    # `_owner_for` replaces `_sender_for`: ...
653:    owner_id, _seats = _owner_for(campaign, channel)
1104:    now uses `_owner_for` below."""
1115:def _owner_for(campaign, channel):
```

Line 653 is inside `authorize()`, the production entry point. The predicate is consumed.

**Contrast with `_sender_for`:**
```bash
$ git grep "_sender_for" origin/qwen-worker-r55 -- src/
origin/qwen-worker-r55:src/executionguard.py:648:    # comment
origin/qwen-worker-r55:src/executionguard.py:1101:def _sender_for(...)
origin/qwen-worker-r55:src/nextaction.py:478:def _sender_for(...)  # DIFFERENT function
origin/qwen-worker-r55:src/senderownership.py:208:    # docstring reference
origin/qwen-worker-r55:src/senders.py:48:    # docstring reference
```

`_sender_for` in `executionguard.py` has ZERO production callers. It is deprecated and kept only for backward compatibility. The docstring references in `senderownership.py` and `senders.py` are informational.

### 3. Falsification: mutation test

**PERFORMED and PASSED.**

I temporarily bypassed `_owner_for` in `authorize()`:
```python
# MUTATION: bypass _owner_for
sender_id = "fake-bypass"
```

Then ran the gate tests from within the worktree (to ensure the mutated code was loaded):
```bash
$ cd <worktree> && python -m unittest discover -s tests -p "test_no_write_happens*"
FAILED (failures=6)
```

**Six tests failed**, including:
- `test_two_senders_are_refused_when_they_are_two_people` — NotAuthorized not raised
- `test_a_seat_with_no_human_owner_is_refused` — NotAuthorized not raised
- `test_another_client_seat_does_not_satisfy_this_client` — NotAuthorized not raised
- `test_a_deactivated_seat_is_refused` — NotAuthorized not raised
- `test_an_unhealthy_seat_is_refused` — NotAuthorized not raised
- `test_a_seat_nobody_inventoried_is_refused` — NotAuthorized not raised

**Conclusion:** The tests are falsifiable. They drive through the real entry point (`authorize()`), and breaking the wiring causes the intended tests to fail for the intended reason. A different guard did not fire first.

### 4. Are the tests falsifiable?

**YES, verified by the mutation test above.**

The tests assert on behavior (NotAuthorized raised at gate "sender"), not on:
- `hasattr` checks
- Source text assertions
- Token presence in files
- Function existence
- JSON shape
- Fake cassettes

The gate tests (`test_no_write_happens_without_every_gate.py`) drive through `authorize()`, the production entry point. The direct tests (`test_task240_arity_rule_moves_to_action.py`) test `_owner_for` in isolation, which is appropriate for unit testing the predicate.

### 5. Would merging delete anything?

**NO, but it would be redundant.**

```bash
$ git diff master...origin/qwen-worker-r55 --stat
 ...y-rule-moves-from-the-campaign-to-the-action.md |  70 +++++++++
 src/executionguard.py                              | 145 +++++++++++-------
 tests/test_no_write_happens_without_every_gate.py  |  63 ++++++--
 tests/test_task240_arity_rule_moves_to_action.py   | 170 +++++++++++++++++++++
 4 files changed, 380 insertions(+), 68 deletions(-)
```

The branch adds 380 lines and removes 68 lines. No file deletions. However:
- `test_no_write_happens_without_every_gate.py` is identical between branch and master (empty diff in the other direction)
- `test_task240_arity_rule_moves_to_action.py` already exists on master
- `executionguard.py` on master has additional improvements

Merging would attempt to re-apply already-integrated changes.

### 6. Scope drift

**NONE.**

```bash
$ git diff master...origin/qwen-worker-r55 --name-only
docs/qwen-tasks/DONE/TASK-240-the-arity-rule-moves-from-the-campaign-to-the-action.md
src/executionguard.py
tests/test_no_write_happens_without_every_gate.py
tests/test_task240_arity_rule_moves_to_action.py
```

Exactly 4 files changed, all within FILES ALLOWED:
- `src/executionguard.py` ✓
- `tests/test_no_write_happens_without_every_gate.py` ✓
- `tests/test_task240_*.py` ✓
- Task file (documentation) ✓

No forbidden files touched:
- `src/providerwrites.py` — unchanged (verified: `git diff master...origin/qwen-worker-r55 -- src/providerwrites.py` is empty)
- `src/providers/*` — unchanged
- `config/` — unchanged
- `src/assignment.py` — unchanged

No junk files, no scratch output, no terminal logs.

---

## Test Results

### TASK-240 direct tests (11 tests)
```
test_another_client_seat_refused ... ok
test_deactivated_seat_refused ... ok
test_no_senders_refused ... ok
test_old_sender_for_no_arity_check ... ok
test_old_sender_for_returns_list ... ok
test_one_seat_one_human_passes ... ok
test_two_seats_same_human_passes ... ok
test_two_seats_two_humans_refused ... ok
test_unhealthy_seat_refused ... ok
test_uninventoried_seat_refused ... ok
test_unowned_seat_refused ... ok

Ran 11 tests in 0.081s
OK
```

### Gate tests (78 tests)
```
Ran 78 tests in 1.549s
OK
```

Including:
- `test_two_senders_are_refused_when_they_are_two_people` ✓ (renamed from `test_two_senders_are_refused_even_when_both_were_approved`)
- `test_two_seats_same_human_pass` ✓ (new sibling)
- `test_a_seat_with_no_human_owner_is_refused` ✓ (inverted from `test_a_seat_with_no_human_owner_still_passes`)
- `test_a_seat_nobody_inventoried_is_refused` ✓ (unaffected)
- `test_a_deactivated_seat_is_refused` ✓ (unaffected)
- `test_an_unhealthy_seat_is_refused` ✓ (unaffected)
- `test_another_client_seat_does_not_satisfy_this_client` ✓ (unaffected)

### Invariant tests (83 tests)
```
FAILED (failures=5)
```

**These failures are PRE-EXISTING and NOT caused by TASK-240.** They relate to modules that exist on master but not on this older branch (Slack modules, candidatelist, etc.). Verified by checking the same tests at the merge base (`586db58a`), which also fail.

Failures:
1. `test_no_test_module_imports_a_provider_exception_by_name`
2. `test_contactouts_post_routes_are_read_only`
3. `test_emailbison_posts_only_to_routes_it_declares`
4. `test_slacks_post_is_gated_on_the_live_switch`
5. `test_the_checklist_has_not_fallen_behind_the_code`

These are about modules/changes that landed on master AFTER the branch's merge base.

---

## Claims Verification

### Result block claims

| Claim | Verified? | Evidence |
|-------|-----------|----------|
| 164 tests pass across 7 modules | PARTIALLY | I verified 11 + 78 = 89 tests pass. Did not run all 7 modules. |
| 11 new direct tests for `_owner_for` | YES | Counted 11 tests in `test_task240_arity_rule_moves_to_action.py` |
| All 78 gate tests green | YES | Ran and verified |
| Two changed tests renamed | YES | `test_two_senders_are_refused_when_they_are_two_people`, `test_a_seat_with_no_human_owner_is_refused` |
| Four unaffected tests at :970-989 still green | YES | Verified all four pass |
| `providerwrites.SUPPORTED` unchanged (14 verbs) | YES | `git diff` is empty |
| Allocator pool: ~20 per human, refused for cross-human | NOT VERIFIED | Did not run allocator measurement |
| EmailBison cannot do per-lead sender binding | NOT VERIFIED | Design doc claim, not re-derived |

### Task specification claims

| Requirement | Met? | Evidence |
|-------------|------|----------|
| Move arity from campaign to action | YES | `_owner_for` checks per-seat ownership, not campaign-level count |
| Refuse unowned seat | YES | Test `test_unowned_seat_refused` passes |
| Refuse uninventoried seat | YES | Test `test_uninventoried_seat_refused` passes |
| Refuse deactivated seat | YES | Test `test_deactivated_seat_refused` passes |
| Refuse unhealthy seat | YES | Test `test_unhealthy_seat_refused` passes |
| Refuse another client's seat | YES | Test `test_another_client_seat_refused` passes |
| Refuse multiple humans | YES | Test `test_two_seats_two_humans_refused` passes |
| Allow multiple seats, same human | YES | Test `test_two_seats_same_human_passes` passes |
| Two existing tests changed | YES | Renamed and inverted as specified |
| Four unaffected tests stay green | YES | Verified |
| No provider writes | YES | No provider modules changed |
| `providerwrites.SUPPORTED` unchanged | YES | Verified |
| Refusal names which clause | YES | Each `raise NotAuthorized` includes specific reason |

---

## Findings

### FINDING 1: Work already integrated (CRITICAL)

**Severity:** CRITICAL (for merge decision)
**Evidence:** `git log --oneline master --grep="TASK-241"` shows integration commit `90bd119b`
**Impact:** Merging this branch is redundant and may cause conflicts
**Disposition:** The branch is obsolete. No merge needed.

### FINDING 2: Master has improvements not on branch

**Severity:** INFORMATIONAL
**Evidence:** `git diff origin/qwen-worker-r55 master -- src/executionguard.py` shows:
- Compliance/unsubscribe gate added (lines 583-608 on master)
- Try/except wrapper for `_owner_for` to attach gate trace (lines 677-684 on master)
- Comment says "TASK-241" instead of "TASK-240"

**Impact:** Master's version is strictly better than the branch's version
**Disposition:** Use master's version, not the branch's.

### FINDING 3: Tests are falsifiable

**Severity:** POSITIVE
**Evidence:** Mutation test (bypass `_owner_for`) causes 6 gate tests to fail
**Impact:** The tests prove the wiring, not just the existence
**Disposition:** The test suite is sound.

### FINDING 4: No scope drift

**Severity:** POSITIVE
**Evidence:** Exactly 4 files changed, all within FILES ALLOWED
**Impact:** Clean, focused change
**Disposition:** No cherry-picking needed (but moot, since already integrated).

---

## Disposition

**CLOSE** — The work is already integrated into master via TASK-241. The branch is obsolete.

**Reason:** Master already has `_owner_for`, the test file, and the changed gate tests. Master also has additional improvements (compliance gate, gate trace wrapper) that the branch lacks. Merging this branch would be redundant and may cause conflicts.

**Evidence:**
- `git log --oneline master --grep="TASK-241"` → `90bd119b TASK-241: arity rule moves to action, gate order preserved`
- `git show master:src/executionguard.py | grep "_owner_for"` → 5 hits
- `git show master:tests/test_task240_arity_rule_moves_to_action.py` → exists
- `git diff origin/qwen-worker-r55 master -- tests/test_no_write_happens_without_every_gate.py` → empty (identical)

**Recommendation:** Do not merge. The branch can be deleted. The work is done and verified on master.

---

## Protocol Compliance

- [x] Reviewed exact HEAD SHA `8f4406e1bb2a4f9ce273b16785011c88da26b4f1`, not branch name
- [x] Used isolated worktree, not dirty primary checkout
- [x] Stamped exact SHA in this document
- [x] Remained read-only (no production/provider state modified)
- [x] Cited exact file:line evidence
- [x] Included reproducible read-only commands
- [x] Distinguished static proof (code review) from runtime proof (test execution)
- [x] Marked unsupported claims UNVERIFIED (allocator measurement, EmailBison limitation)
- [x] Did not merge
- [x] Did not modify production/provider state
- [x] Did not automatically create implementation
- [x] Handed findings back to Claude for independent triage

---

## Commands for Reproduction

```bash
# Verify SHA
git fetch origin qwen-worker-r55
git rev-parse origin/qwen-worker-r55

# Create isolated worktree
git worktree add .qwen/worktrees/task470-review 8f4406e1bb2a4f9ce273b16785011c88da26b4f1 --detach

# Run TASK-240 tests
cd .qwen/worktrees/task470-review
python -m unittest discover -s tests -p "test_task240*" -v

# Run gate tests
python -m unittest discover -s tests -p "test_no_write_happens*" -v

# Verify _owner_for is consumed
git show HEAD:src/executionguard.py | grep -n "_owner_for"

# Verify providerwrites unchanged
git diff master...HEAD -- src/providerwrites.py

# Check if already on master
git log --oneline master --grep="TASK-241"
git show master:src/executionguard.py | grep -n "_owner_for"

# Clean up
cd ../..
git worktree remove .qwen/worktrees/task470-review --force
```

---

**Verdict authored:** 2026-09-28
**Reviewer:** GLM (independent verification, TASK-470)
**Status:** CLOSE — already integrated
