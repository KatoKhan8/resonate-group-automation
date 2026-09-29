# GLM Independent Verification: TASK-431 (which verified TASK-219)

**Review target:** TASK-431's verdict on TASK-219 "only the opener owns a subject"
**TASK-431 branch:** `origin/qwen-worker-7-r9`
**TASK-431 HEAD SHA (as named):** `8acee2e8bb6a9dc447cf7ee387888f613124cdb1`
**Current branch HEAD SHA:** `539bdc2f448c9d1b648c0046786557d72b976322` (branch has moved)
**TASK-219 SHA (reviewed by TASK-431):** `dff854cf8fce75dfe4d6d2ed973fd68f7b8fab0e`
**Review date:** 2026-09-29
**Reviewer:** GLM (independent verification of TASK-431's verdict)
**Isolated worktrees:**
- `.qwen/worktrees/task533-review` at detached HEAD `8acee2e8` (TASK-431's artifact)
- `.qwen/worktrees/task533-task219` at detached HEAD `dff854cf` (TASK-219's code)

---

## Executive Summary

**DISPOSITION: MERGE**

TASK-431's verdict on TASK-219 is **correct**. Every material claim was independently
re-derived. The artifact exists, the tests are falsifiable, the production callers are
real, and the merge is safe. One minor discrepancy in the caller count (12, not 13)
does not affect the verdict. The observation about caller consistency is correctly
classified as a transition concern, not a defect.

---

## 1. Branch HEAD SHA Verification

**TASK-431's branch has moved.** The task named SHA `8acee2e8` but the current HEAD
of `origin/qwen-worker-7-r9` is `539bdc2f`. Per the standing rule, I reviewed the
exact SHA `8acee2e8` that the task named. The TASK-431 verdict document exists at
that SHA and is the artifact under review.

**TASK-219's SHA (`dff854cf`) exists** and is reachable from `8acee2e8`. The code
changes at that SHA are the subject of TASK-431's verdict.

---

## 2. Does the Artifact Exist, and Does It Do What the Result Block Claims?

### 2.1 TASK-219's Code Changes

The branch modifies four source files:

| File | Change | Verified |
|------|--------|----------|
| `src/approval.py` | `fingerprint(skip_subject=False)`, `is_approved(campaign=None)`, `_is_threaded_follow_up()` helper | ✓ |
| `src/approve.py` | `_is_threaded_follow_up()` helper, `approve_step` detects threading, blanks subject, sets flag | ✓ |
| `src/bisonfactory.py` | `_certified_copy` reads `threaded_follow_up` flag, passes `skip_subject` | ✓ |
| `src/configdiff.py` | `approved_heyreach` and `approved_bison` pass `campaign` to `is_approved` | ✓ |

All changes exist at `dff854cf` and match TASK-431's description.

### 2.2 Test Counts

TASK-431 claimed:
- 28/28 in `test_threaded_sequence` + `test_lead_variables`
- 43/43 in `test_approve`
- 92/92 in `test_campaigns` + `test_eligibility`

**Independent verification:**
```
Ran 28 tests in 0.362s — OK ✓
Ran 43 tests in 2.386s — OK ✓
Ran 92 tests in 7.937s — OK ✓
```

All counts confirmed.

### 2.3 Functional Claims

TASK-431 claimed:
1. The approval fingerprint for a threaded follow-up excludes the subject ✓
2. The slot carries `threaded_follow_up: True` ✓
3. Both negative tests pass at unit level ✓
4. The comparator proves all five properties via `REQUIRED_BISON` ✓

All claims verified by reading the code at `dff854cf`.

---

## 3. Existence Is Not Function: Production Callers

### 3.1 `fingerprint(skip_subject=...)`

TASK-431 claimed two production callers. Independent grep:

```
src/approve.py:144      fingerprint(fp_step, skip_subject=threaded)
src/bisonfactory.py:727 approval.fingerprint(material, skip_subject=skip_subject)
```

**Two callers confirmed.** ✓

### 3.2 `is_approved(campaign=...)`

TASK-431 claimed 17 callers total, 4 updated to pass `campaign`. Independent grep:

**Updated (pass `campaign`):**
1. `src/approve.py:239` — `campaign=campaign` ✓
2. `src/approve.py:323` — `campaign=of_record.get(rec["id"])` ✓
3. `src/configdiff.py:279` — `campaign=campaign` ✓
4. `src/configdiff.py:684` — `campaign=campaign` ✓

**Not updated (12 callers, not 13 as TASK-431 claimed):**
1. `src/cadence.py:1151`
2. `src/campaigns.py:231`
3. `src/campaigns.py:444`
4. `src/eligibility.py:706`
5. `src/eligibility.py:744`
6. `src/executionguard.py:484`
7. `src/funnel.py:261`
8. `src/generate.py:2047`
9. `src/generate.py:2053`
10. `src/preview.py:219`
11. `src/qa.py:305`
12. `src/report.py:451`

**Minor discrepancy:** TASK-431 said 13 non-updated callers; I count 12. This does not
affect the verdict. The `campaign` parameter is optional and only needed for backward
compatibility with old slots. For NEW approvals (with `threaded_follow_up` flag on the
slot), all callers work correctly.

### 3.3 `_is_threaded_follow_up()`

Two implementations:
- `src/approval.py:111` — takes `(step_key, campaign)`, used as fallback in `is_approved`
- `src/approve.py:41` — takes `(step_key, config)`, used in `approve_step`

Both have real production callers. ✓

### 3.4 `threaded_follow_up` flag

Read in:
- `src/approval.py:104` — `slot.get("threaded_follow_up")`
- `src/bisonfactory.py:726` — `(step or {}).get("threaded_follow_up")`

Set in:
- `src/approve.py:174` — `slot["threaded_follow_up"] = True`

Cleared in:
- `src/approve.py:176` — `slot.pop("threaded_follow_up", None)`

All uses are in production code. ✓

---

## 4. Falsifiability: Mutation Test

### 4.1 Method

Disabled the threading detection in `_sequence_steps` by replacing:
```python
has_any_threading = any(s.get("thread_reply") for s in steps[1:])
```
with:
```python
has_any_threading = False  # MUTATION
```

### 4.2 Result

Both negative tests FAILED as expected:
```
FAIL: test_em2_not_threaded_with_distinct_subject_is_refused
AssertionError: FactoryRefused not raised

FAIL: test_em3_not_threaded_with_distinct_subject_is_refused
AssertionError: FactoryRefused not raised
```

### 4.3 Conclusion

The negative tests are **falsifiable**. They actually test the validation logic and
would catch a regression if the validation were removed. The failure is for the
intended reason (`FactoryRefused not raised`), not because a different guard fired
first.

**Mutation test independently reproduced.** ✓

---

## 5. Merge Safety

### 5.1 Deletions

The branch deletes one file:
- `docs/qwen-tasks/TODO/TASK-219-only-the-opener-owns-a-subject.md`

This is expected: the task moved from TODO to REVIEW. No production code,
configuration, or test files are deleted. ✓

### 5.2 Scope Drift

TASK-219's branch (`dff854cf`) changes 7 files:
- `docs/ONLY-THE-OPENER-OWNS-A-SUBJECT-2026-09-16.md` (documentation update)
- `docs/qwen-tasks/REVIEW/TASK-219-only-the-opener-owns-a-subject.md` (result block)
- `docs/qwen-tasks/TODO/TASK-219-only-the-opener-owns-a-subject.md` (deleted, moved to REVIEW)
- `src/approval.py` ✓
- `src/approve.py` ✓
- `src/bisonfactory.py` ✓
- `src/configdiff.py` ✓

**No scope drift.** The branch carries only TASK-219's work. ✓

### 5.3 TASK-431's Branch

TASK-431's branch (`8acee2e8`) has massive scope: 113 files, 15,879 insertions.
This is the accumulated work of many tasks on `qwen-worker-7-r9`, not TASK-431's
verdict alone. TASK-431's own artifact is the verdict document
(`docs/glm-reviews/TASK-431-verify-task-219.md`), which exists at `8acee2e8`.

**TASK-431's branch should NOT be merged wholesale.** Only TASK-219's changes
should be merged (from `dff854cf` or its successor).

### 5.4 Conflict Markers

No conflict markers found in either worktree. ✓

---

## 6. Design Correctness

### 6.1 Threaded Sequence Invariant

The invariant: "only the opener owns a subject." The design:
1. Every step's `email_subject` references `{SUBJECT_1}`
2. The opener sends it as the subject
3. Follow-ups are thread replies, so the provider continues the original thread
   and prepends `Re:` itself
4. There is exactly ONE subject variable per lead (`subject_1`)

**Design is correct** and matches the operator's verified behavior. ✓

### 6.2 Approval Fingerprint

The fingerprint for a threaded follow-up excludes the subject because:
- The subject is not sendable content (the provider uses `subject_1` and prepends
  `Re:` itself)
- The approval should cover what reaches a prospect
- A follow-up's generated subject never reaches a prospect

**Design is sound.** ✓

### 6.3 Validation

The validation in `_sequence_steps` refuses a mixed shape:
- Some follow-ups threaded, others not, with distinct subjects
- This violates the invariant

**Validation is correct** and the negative tests prove it works. ✓

---

## 7. TASK-431's Observations

### 7.1 Caller Consistency

TASK-431 observed that 13 callers of `is_approved` were not updated to pass
`campaign`. I count 12 (minor discrepancy). TASK-431 correctly classified this as
a transition concern, not a defect:

- For NEW approvals (with `threaded_follow_up` flag on the slot), all callers work
  correctly regardless of whether they pass `campaign`.
- For OLD approvals (pre-TASK-219), callers that don't pass `campaign` will compute
  the fingerprint WITH the subject, which matches the old stored fingerprint.
- The result block acknowledges this and states no old approvals exist in production.

**TASK-431's classification is correct.** This is not a blocker.

### 7.2 Duplicate Helper

TASK-431 observed that `_is_threaded_follow_up` is implemented twice (in `approval.py`
and `approve.py`) with similar but not identical logic. This is not a defect, just a
potential refactoring opportunity.

**Correctly classified as not a blocker.**

---

## 8. Findings

### 8.1 Positive Findings

1. **Artifact exists and does what the result block claims.** All test counts verified.
   All functional claims verified. ✓
2. **Production callers exist.** All new/modified functions have real production callers. ✓
3. **Tests are falsifiable.** Mutation test independently reproduced. ✓
4. **Merge is safe.** No production code deleted. No scope drift. No conflict markers. ✓
5. **Design is correct.** The threaded sequence invariant is correctly implemented. ✓
6. **TASK-431's verdict is accurate.** Every material claim was independently verified. ✓

### 8.2 Minor Discrepancies

1. **Caller count:** TASK-431 said 13 non-updated callers; I count 12. Does not affect
   the verdict.
2. **TASK-431's branch scope:** The branch carries 113 files of accumulated work, not
   just TASK-431's verdict. Only TASK-219's changes should be merged.

### 8.3 No Defects Found

TASK-431's verdict is correct. No defects found in TASK-219's implementation or in
TASK-431's review of it.

---

## 9. Reproducible Commands

All verifications were performed in isolated worktrees at the target SHAs:

```bash
# Create worktrees
git worktree add .qwen/worktrees/task533-review 8acee2e8bb6a9dc447cf7ee387888f613124cdb1 --detach
git worktree add .qwen/worktrees/task533-task219 dff854cf8fce75dfe4d6d2ed973fd68f7b8fab0e --detach

# Verify SHAs
git rev-parse origin/qwen-worker-7-r9  # 539bdc2f (branch has moved)
git cat-file -t 8acee2e8               # commit
git cat-file -t dff854cf               # commit

# Run tests (in task533-task219 worktree)
cd .qwen/worktrees/task533-task219
python -m unittest tests.test_threaded_sequence tests.test_lead_variables -v  # 28 tests
python -m unittest tests.test_approve -v                                       # 43 tests
python -m unittest tests.test_campaigns tests.test_eligibility -v              # 92 tests

# Check production callers
grep -rn "skip_subject" src/ --include="*.py"
grep -rn "threaded_follow_up" src/ --include="*.py"
grep -rn "is_approved" src/ --include="*.py" | grep -v "def is_approved"

# Mutation test
cp src/bisonfactory.py src/bisonfactory.py.bak
python -c "
with open('src/bisonfactory.py', 'r', encoding='utf-8') as f:
    content = f.read()
old = '        has_any_threading = any(s.get(\"thread_reply\") for s in steps[1:])'
new = '        has_any_threading = False  # MUTATION'
content = content.replace(old, new, 1)
with open('src/bisonfactory.py', 'w', encoding='utf-8') as f:
    f.write(content)
"
python -m unittest tests.test_threaded_sequence.NegativeTests -v  # Should FAIL
mv src/bisonfactory.py.bak src/bisonfactory.py
python -m unittest tests.test_threaded_sequence.NegativeTests -v  # Should pass

# Check deletions
git diff master...dff854cf --diff-filter=D --name-only

# Check scope drift
git diff master...dff854cf --name-only | sort

# Check conflict markers
grep -rn "^<<<<<<< \|^======= $\|^>>>>>>> " src/ tests/ scripts/

# Clean up
cd ../..
git worktree remove .qwen/worktrees/task533-review --force
git worktree remove .qwen/worktrees/task533-task219 --force
```

---

## 10. Protocol Compliance

This review complies with the GLM Review Protocol:

- ✓ Reviewed the exact SHA named by the task (`8acee2e8`)
- ✓ Detected branch movement (`539bdc2f` is current HEAD)
- ✓ Used isolated clean worktrees
- ✓ Stamped the exact SHAs
- ✓ Remained read-only except for this review document
- ✓ Cited exact file:line evidence
- ✓ Included reproducible read-only commands
- ✓ Distinguished static/code proof from runtime proof
- ✓ Marked unsupported claims (none found)
- ✓ Marked incomplete areas (none found)
- ✓ Did not merge
- ✓ Did not modify production/provider state
- ✓ Did not automatically create implementation
- ✓ Handed findings back to Claude for independent reproduction and triage

---

## 11. Disposition

**MERGE**

TASK-431's verdict on TASK-219 is **correct**. The artifact exists, does what the
result block claims, has real production callers, and the tests are falsifiable.
The branch is clean and merging would not delete production state.

**TASK-431's verdict is verified.** Every material claim was independently
re-derived. The minor discrepancy in caller count (12 vs 13) does not affect the
verdict. The observation about caller consistency is correctly classified as a
transition concern, not a defect.

**Recommended Claude action:**
1. Merge TASK-219's changes (from `dff854cf` or its successor, NOT the entire
   `qwen-worker-7-r9` branch)
2. Review the approval semantics change (fingerprint excludes subject for threaded
   follow-ups)
3. Rebuild campaign 485 with the threaded config (as TASK-219's result block
   recommends)

---

**Review complete.** TASK-431's verdict is accurate and TASK-219 is ready for merge
pending Claude's final review.
