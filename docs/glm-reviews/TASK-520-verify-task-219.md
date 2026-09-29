# GLM Independent Verification: TASK-412 Suppression List Audit

**Reviewer:** GLM (independent, via TASK-520)
**Target task:** TASK-412 — Suppression List Audit
**Target branch:** `origin/qwen-worker-3-r9-task285`
**Branch HEAD SHA reviewed:** `c8a62f4109f47eb5338f1ef334d68f44dcb989ef`
**SHA verified:** `git rev-parse origin/qwen-worker-3-r9-task285` → `c8a62f41` ✓ EXACT MATCH
**Worktree:** `.qwen/worktrees/task520-review` (detached HEAD at target SHA)
**Date:** 2026-09-29

---

## Executive Summary

**DISPOSITION: MERGE with cherry-pick**

TASK-412's audit is accurate, well-structured, and honestly scoped. The six suppression stores are real, the file:line citations are substantially correct (minor discrepancies noted), the chain from `eligibility.decide()` through `must_not_contact()` to all six stores is verified, every prospect-facing write path is confirmed to check suppression before writing, and the owed item (76 re-verification from Claude's worktree) is honestly declared.

However, the branch carries **massive scope drift**: 39 files changed across 8+ tasks (TASK-267, 285, 358, 387, 410, 412, 426, 432), with 7,167 insertions. Only the TASK-412 review file itself is the artifact for this task. The branch should NOT be merged wholesale; the TASK-412 file movement should be cherry-picked.

---

## §1. Does the artifact exist, and does it do what the result block claims?

**YES.** The task file was moved from `docs/qwen-tasks/TODO/TASK-412-suppression-list-audit.md` to `docs/qwen-tasks/REVIEW/TASK-412-suppression-list-audit.md` at commit `49154f6b` with a complete result block.

**Artifact kind:** Finding (read-only audit document). No code changes. This is correct for an audit task.

**Verified on the exact ref:** `git show c8a62f41:docs/qwen-tasks/REVIEW/TASK-412-suppression-list-audit.md` returns the full result block. ✓

---

## §2. Are the six suppression stores real, and are the citations correct?

**YES, with minor line number discrepancies.**

### Store 1: Domain-level global suppression (`suppress.txt`)
- **Claimed:** `ingest.load_suppress()` at `src/ingest.py:109`
- **Actual:** `src/ingest.py:109` ✓ EXACT
- **Claimed:** `eligibility._suppressed()` at `src/eligibility.py:280-293`
- **Actual:** `src/eligibility.py:280` ✓ EXACT
- **Claimed:** `channels._suppressed()` at `src/channels.py:127-133`
- **Actual:** `src/channels.py:127` ✓ EXACT
- **Claimed:** `discovery.known()` at `src/discovery.py:205-206`
- **Actual:** `src/discovery.py:178` (function start), suppression loading at ~204-206 ✓ APPROXIMATE

### Store 2: Agency-wide DNC (`agency-dnc.jsonl`)
- **Claimed:** `agencydnc.lookup()` 
- **Actual:** `src/agencydnc.py:163` ✓
- **Claimed:** checked at `eligibility._suppressed()` → `agencydnc.lookup()` at `src/eligibility.py:295-297`
- **Actual:** `src/eligibility.py:295-297` calls `agencydnc.lookup(contact, index=agency)` ✓ EXACT

### Store 3: Client-level suppression (`clientapproval`)
- **Claimed:** `clientapproval.is_suppressed()` at `src/clientapproval.py:193`
- **Actual:** `src/clientapproval.py:193` ✓ EXACT

### Store 4: Account-level suppression (record `suppression` field)
- **Claimed:** written by `accountpolicy.apply_reply()` at `src/accountpolicy.py:551-553`
- **Actual:** `apply_reply` is at line 604. The actual writer is `_suppress_account()` at ~547, which is called by `apply_reply`. Line numbers are for the helper, not `apply_reply` itself. MINOR MISATTRIBUTION.
- **Claimed:** checked at `eligibility._paused()` at `src/eligibility.py:345`
- **Actual:** `src/eligibility.py:339` (function start), check at line 344. CLOSE.
- **Verified:** `_paused` checks `(rec.get("suppression") or {}).get("unsubscribed")` → `BLOCKED_ACCOUNT_SUPPRESSED` ✓

### Store 5: Contact-level suppression (`unsubscribed`/`suppressed`/`stopped` fields)
- **Claimed:** written by `accountpolicy.apply_reply()` at `src/accountpolicy.py:486-488`
- **Actual:** The actual writer is `_suppress_contact()` at ~481, called by `apply_reply`. Same misattribution pattern as Store 4. MINOR.
- **Claimed:** checked at `eligibility._replied()` at `src/eligibility.py:398-399`
- **Actual:** `src/eligibility.py:393` (function start), check at line 398. CLOSE.
- **Verified:** `_replied` checks `contact.get("unsubscribed") or contact.get("suppressed")` → `BLOCKED_UNSUBSCRIBED` ✓

### Store 6: Bounce events (record `events` array)
- **Claimed:** `adapters.py:130-131` records `EMAIL_BOUNCED`
- **Actual:** `src/adapters.py:131` ✓
- **Claimed:** checked at `channels._bounced()` at `src/channels.py:96-122`
- **Actual:** `src/channels.py:96` ✓ EXACT
- **Claimed:** checked at `eligibility._email_checks()` at line 695-696
- **Actual:** `src/eligibility.py:695` calls `channels._bounced(rec, contact)` ✓ EXACT

**Summary:** All six stores exist. All citations are substantively correct. Line numbers are within 1-5 lines of actual for most, with two minor misattributions (naming `apply_reply` instead of the helper functions it calls). No material errors.

---

## §3. Does `eligibility.decide()` read all six stores?

**YES.** Verified by code reading:

```
src/eligibility.py:605  def decide(...)
src/eligibility.py:651    for reason in (*must_not_contact(rec, contact, ...), ...)
src/eligibility.py:358  def must_not_contact(...)
src/eligibility.py:373    return (_suppressed(...),        # Stores 1+2
src/eligibility.py:374            _client_own_domain(...), # Store 3 variant
src/eligibility.py:375            _record_state(...),      # Store 3/4
src/eligibility.py:376            _replied(...),           # Store 5
src/eligibility.py:377            _paused(...))            # Store 4
src/eligibility.py:664  checks = (_email_checks if channel == EMAIL else ...)
src/eligibility.py:695    if channels._bounced(rec, contact):  # Store 6
```

The chain is complete and consumed. `eligibility.decide` is called by:
- `executionguard.authorize` at `src/executionguard.py:565`
- `executionguard.revalidate` at `src/executionguard.py:1018`
- `funnel.py:242`
- `killswitch.py:218`
- `demo_outreach.py:709`

**Existence is not function: PASSED.** The function has multiple production callers.

---

## §4. Does every prospect-facing write path check suppression BEFORE writing?

**YES.** Verified:

### Path 1: EMAIL_ACTIVATE (facing=True)
- **Claimed:** `executionguard.revalidate(authorization)` at `src/providerwrites.py:2253`
- **Actual:** `src/providerwrites.py:2253` ✓ EXACT
- **Chain:** `revalidate` → `store.get()` (re-read from disk) → `eligibility.decide()` → all six stores ✓

### Path 2: EMAIL_RESUME (facing=False, CONDITIONAL)
- **Claimed:** `_resume_revalidates_suppression()` at `src/providerwrites.py:1415-1473`
- **Actual:** `src/providerwrites.py:1415` (function start), `src/providerwrites.py:1473` (CONDITIONAL registration) ✓ EXACT
- **Chain:** reads every record via `store.get(rid)` → iterates contacts → calls `eligibility.must_not_contact(rec, contact)` → stores 1-5 ✓
- **Test coverage:** `tests/test_a_resume_revalidates_suppression_first.py` with 10 tests, all going through `providerwrites.perform` (real entry point), asserting `WriteRefused` is raised and transport is NOT called. Tests are falsifiable: removing the CONDITIONAL would cause them to fail. ✓

### Path 3: LINKEDIN_ADD_LEAD (facing=True)
- **Claimed:** `executionguard.revalidate(authorization)` at `src/providerwrites.py:2253`
- **Actual:** Same as EMAIL_ACTIVATE ✓

### Path 4: leadstop.sweep
- **Claimed:** `eligibility.must_not_contact(rec, contact)` at `src/leadstop.py:345`
- **Actual:** `src/leadstop.py:345` ✓ EXACT

**Summary:** All write paths check suppression before writing. The chain is real and tested.

---

## §5. Is the 76 re-verification honestly owed?

**YES.** The task correctly states that `work/queue.jsonl` does not exist in this worktree (per QWEN.md, live queue state is in Claude's worktree only). The task explicitly declares this as owed and provides the exact command to run. This is honest and correct.

---

## §6. Are the tests falsifiable?

**YES.** The resume suppression tests at `tests/test_a_resume_revalidates_suppression_first.py`:
- Go through `providerwrites.perform` (the real production entry point), not the function directly
- Assert `WriteRefused` is raised
- Assert the transport was NOT called (`self.assertFalse(transport_called)`)
- Assert the error message contains the count and first five names
- Include a negative control: `test_without_the_guard_a_suppressed_resume_would_pass` verifies the defect existed before the fix

These are not `hasattr` checks or assertions on source text. They test behavior through the production entry point.

---

## §7. Would merging delete anything from master?

**NO.** `git diff master...c8a62f41 --diff-filter=D --name-only -- src/ tests/ scripts/` returns empty. No source, test, or script files would be deleted.

The only deletions are task files moved from TODO to REVIEW (renames), which is expected queue management.

---

## §8. Scope drift

**CRITICAL.** The branch carries work from **8+ tasks**:

| Task | Files | Description |
|------|-------|-------------|
| TASK-267 | `scripts/stage_s3_llm_tiebreaker.py`, `tests/test_llm_tiebreaker.py`, task file | LLM tiebreaker script + 23 tests |
| TASK-285 | `scripts/collision_walk_report.py`, `docs/COLLISION-WALK-2026-09-25.md`, tests, task file | Collision walk batch 3 |
| TASK-358 | `src/providers/cheapverifier.py` (1141 lines), `src/waterfall.py`, `src/enrich.py`, 10 cassettes, 2 test files, task file | CheapVerifier integration |
| TASK-387 | `tests/test_task387_provider_event_writeback.py`, task file | Provider event writeback tests |
| TASK-410 | `docs/glm-reviews/TASK-410-glm-verify-task-400-critical-path.md` | GLM review of TASK-400 |
| **TASK-412** | **`docs/qwen-tasks/REVIEW/TASK-412-suppression-list-audit.md`** | **Suppression list audit (THIS TASK)** |
| TASK-426 | `src/bisonfactory.py` (qualification wiring), task file | Bison staging fix |
| TASK-432 | `docs/glm-reviews/TASK-432-verify-task-226.md`, task file | GLM review of TASK-226 |
| (other) | `scripts/claim_task.py`, `docs/SUITE-TRIAGE-2026-09-27.md` | Infrastructure changes |

**Total:** 39 files changed, 7,167 insertions, 223 deletions.

**TASK-412's artifact is ONE file movement.** The branch should NOT be merged wholesale. The TASK-412 review file can be cherry-picked cleanly.

---

## §9. Findings

### Finding 1: The audit is accurate and complete
The six stores are real, the chain is verified, every write path is confirmed, and the owed item is honestly declared. The result block is a model of what an audit should be.

**Severity:** None (positive finding)
**Disposition:** MERGE

### Finding 2: Minor line number discrepancies
Two citations name `accountpolicy.apply_reply()` at lines 486-488 and 551-553, but those lines are actually the helper functions `_suppress_contact()` and `_suppress_account()` that `apply_reply` calls. The substance is correct; the attribution is slightly off.

**Severity:** Nice to have
**Disposition:** No action needed. The audit is still correct.

### Finding 3: The bounce gap is real
`_resume_revalidates_suppression` calls `must_not_contact` which does NOT include bounce (Store 6). A resume of a campaign holding a bounced email address would not be refused on bounce grounds. The task correctly identifies this as a minor gap.

**Severity:** Suggestion
**Disposition:** The task already recommends considering whether `_resume_revalidates_suppression` should also check `channels._bounced`. Low priority.

### Finding 4: Massive scope drift
The branch carries 7 other tasks' work. Merging the branch wholesale would bring in CheapVerifier (1141 lines), LLM tiebreaker, collision walk, provider writeback tests, bison staging fixes, and two other GLM reviews.

**Severity:** Critical (process)
**Disposition:** Cherry-pick only the TASK-412 file movement. The other tasks have their own branches and should be reviewed and merged independently.

### Finding 5: All functions are consumed
`eligibility.decide` has multiple production callers (`executionguard.authorize`, `executionguard.revalidate`, `funnel`, `killswitch`, `demo_outreach`). This is not a case of "existence is not function."

**Severity:** None (positive finding)
**Disposition:** MERGE

---

## §10. Recommendation

**MERGE with cherry-pick.**

TASK-412's audit is accurate, well-structured, and honestly scoped. The artifact (the review file) can be cherry-picked cleanly from the branch. The branch itself should NOT be merged wholesale due to massive scope drift from 7 other tasks.

**Cherry-pick command:**
```bash
git cherry-pick c8a62f4109f47eb5338f1ef334d68f44dcb989ef --no-commit
# Then reset everything except:
#   docs/qwen-tasks/REVIEW/TASK-412-suppression-list-audit.md (add)
#   docs/qwen-tasks/TODO/TASK-412-suppression-list-audit.md (delete)
```

Or manually move the file:
```bash
git mv docs/qwen-tasks/TODO/TASK-412-suppression-list-audit.md docs/qwen-tasks/REVIEW/TASK-412-suppression-list-audit.md
```

**Owed items (from the task itself):**
1. Fresh read of the 76 suppressed recipients from Claude's worktree
2. Consider whether `_resume_revalidates_suppression` should also check `channels._bounced`

---

## Reproducible verification commands

All commands were run in the isolated worktree `.qwen/worktrees/task520-review` at SHA `c8a62f4109f47eb5338f1ef334d68f44dcb989ef`:

```bash
# Verify the SHA
git rev-parse origin/qwen-worker-3-r9-task285
# → c8a62f4109f47eb5338f1ef334d68f44dcb989ef

# Check the artifact exists
git show c8a62f41:docs/qwen-tasks/REVIEW/TASK-412-suppression-list-audit.md | head -20

# Verify the chain
grep -n "def decide" src/eligibility.py                    # → 605
grep -n "def must_not_contact" src/eligibility.py          # → 358
grep -n "def _suppressed" src/eligibility.py               # → 280
grep -n "def _paused" src/eligibility.py                   # → 339
grep -n "def _replied" src/eligibility.py                  # → 393
grep -n "def _bounced" src/channels.py                     # → 96
grep -n "def revalidate" src/executionguard.py             # → 959
grep -n "executionguard.revalidate" src/providerwrites.py  # → 2253
grep -n "_resume_revalidates_suppression" src/providerwrites.py  # → 1415, 1473

# Verify no deletions
git diff master...c8a62f41 --diff-filter=D --name-only -- src/ tests/ scripts/
# → (empty)

# Check scope drift
git diff master...c8a62f41 --stat
# → 39 files changed, 7167 insertions(+), 223 deletions(-)
```

---

**Verdict completed:** 2026-09-29
**Reviewer:** GLM (independent, via TASK-520)
**Target SHA:** `c8a62f4109f47eb5338f1ef334d68f44dcb989ef` (verified exact match)
**Disposition:** MERGE with cherry-pick
