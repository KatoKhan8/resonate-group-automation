# TASK-520 — GLM Independent Verification: TASK-412

**VERDICT: REWORK**

**Recommendation:** REWORK — the audit is mostly accurate but has one owed item and minor inaccuracies. The branch carries significant scope drift from 8+ other tasks. Cherry-pick only TASK-412's task file movement.

---

## Review Metadata

- **Task reviewed:** TASK-412 (suppression-list-audit)
- **Branch reviewed:** `origin/qwen-worker-3-r9-task285`
- **Branch HEAD SHA reviewed:** `c8a62f4109f47eb5338f1ef334d68f44dcb989ef`
- **SHA verified:** YES — `git rev-parse c8a62f4109f47eb5338f1ef334d68f44dcb989ef` returns the SHA
- **Commit message at SHA:** `TASK-285: move to REVIEW with complete result block`
- **START_MASTER_SHA:** `2bf7b8a571fe11bada4f56fbebeee768ab1e78a8` (current origin/master)
- **Merge base:** `05e9220baa74adb26f27c61364c2836b378d66ea`
- **Review worktree:** `.qwen/worktrees/glm-task520` (detached at exact SHA)
- **Review date:** 2026-10-04
- **Reviewer:** GLM (independent verification)

---

## §1. Does the artifact exist on this ref?

**YES.** The artifact is the RESULT BLOCK in `docs/qwen-tasks/REVIEW/TASK-412-suppression-list-audit.md` on the branch at SHA `c8a62f4109f47eb5338f1ef334d68f44dcb989ef`.

**Verification:**
```bash
git show c8a62f4109f47eb5338f1ef334d68f44dcb989ef:docs/qwen-tasks/REVIEW/TASK-412-suppression-list-audit.md
```
Returns 192 lines containing the complete audit with four sections:
- §1. Every store of a suppression fact (six stores named)
- §2. Every prospect-facing write path checks suppression BEFORE writing
- §3. The 09-23 incident's 76 suppressed recipients
- §4. Findings (six findings, including one gap)

**Artifact kind:** Finding (read-only audit document). No code changes.

---

## §2. Does the artifact do what the result block claims?

**MOSTLY YES, with one owed item and minor inaccuracies.**

### Claim 1: Six stores of suppression facts exist and are deliberately separated

**VERIFIED.** The audit correctly identifies six stores:

1. **Store 1: Domain-level global suppression (`suppress.txt`)**
   - Loader: `ingest.load_suppress()` at `src/ingest.py:109` ✓
   - Checked at: `eligibility._suppressed()` at `src/eligibility.py:293` ✓ (audit says "hygiene.check → hygiene.py:337" which is INACCURATE — it's checked in eligibility, not hygiene)
   - Also checked at: `channels._suppressed()` at `src/channels.py:130` ✓
   - Also checked at: `discovery.known()` at `src/discovery.py:205` ✓

2. **Store 2: Agency-wide DNC (`agency-dnc.jsonl`)**
   - Module: `src/agencydnc.py` exists ✓
   - Lookup: `agencydnc.lookup()` at `src/agencydnc.py:163` ✓
   - Checked at: `eligibility._suppressed()` at `src/eligibility.py:299-301` ✓
   - Checked at: `hygiene.check()` at `src/hygiene.py:377` ✓

3. **Store 3: Client-level suppression (`clientapproval`)**
   - Function: `clientapproval.is_suppressed()` at `src/clientapproval.py:193` ✓
   - Checked at: `hygiene.check()` at `src/hygiene.py:365-371` ✓

4. **Store 4: Account-level suppression (record `suppression` field)**
   - Written by: `accountpolicy.apply_reply()` at `src/accountpolicy.py:553-554` ✓ (audit says 551-553, actual is 553-554 — close enough)
   - Checked at: `eligibility._paused()` at `src/eligibility.py:345` ✓

5. **Store 5: Contact-level suppression (`unsubscribed`/`suppressed`/`stopped` fields)**
   - Written by: `accountpolicy.apply_reply()` at `src/accountpolicy.py:487-488` ✓ (audit says 486-488, actual is 487-488 — close enough)
   - Checked at: `eligibility._replied()` at `src/eligibility.py:399` ✓ (audit says 398-399, actual is 399)

6. **Store 6: Bounce events (record `events` array)**
   - Recorded by: `adapters.py:131` — `event_type = events.EMAIL_BOUNCED` ✓
   - Checked at: `channels._bounced()` at `src/channels.py:96` ✓
   - Checked at: `eligibility._email_checks()` at `src/eligibility.py:695` ✓ (audit says 695-696, actual is 695)

**Minor inaccuracy:** The audit says store 1 is checked at "Ingest: `hygiene.check()` → `src/hygiene.py:337`" but `hygiene.check` does NOT check `suppress.txt`. It's checked in `eligibility._suppressed` at line 293, `channels._suppressed` at line 130, and `discovery.known` at line 205. The functional claim (it IS checked before writes) is correct, but the specific location cited is wrong.

### Claim 2: `eligibility.decide()` reads all six stores in one call

**VERIFIED.** `eligibility.decide()` at line 605 (now line 716 on current master) calls:
- Lines 649-651: `must_not_contact(rec, contact, config=config, suppressed=suppressed)` which calls:
  - `_suppressed` (stores 1+2)
  - `_client_own_domain` (store 3)
  - `_record_state` (stores 3/4)
  - `_replied` (store 5)
  - `_paused` (store 4)
- Line 668: `_email_checks` (store 6, for email channel only)

The claim that "eligibility.decide reads ALL six stores in one call" is CORRECT.

### Claim 3: Every prospect-facing write path checks suppression BEFORE writing

**VERIFIED.** The audit identifies five write paths:

1. **EMAIL_ACTIVATE (`facing=True`)**
   - Pre-write check: `executionguard.revalidate(authorization)` at `src/providerwrites.py:2253` ✓
   - `revalidate` at `src/executionguard.py:959` re-reads from disk (line 1013: `rec = store.get(authorization.rec_id)`) and calls `eligibility.decide` (line 1024) ✓
   - Coverage: ALL six stores via `eligibility.decide` ✓

2. **EMAIL_RESUME (`facing=False`, CONDITIONAL)**
   - Pre-write check: `_resume_revalidates_suppression()` at `src/providerwrites.py:1415-1473` ✓
   - Registered as `CONDITIONAL[EMAIL_RESUME]` at line 1473 ✓
   - Reads every record from disk (line 1452: `rec = store.get(rid)`) ✓
   - Calls `eligibility.must_not_contact(rec, contact)` at line 1455 ✓
   - Coverage: Stores 1+2+3+4+5 via `must_not_contact` ✓
   - **Does NOT check bounces (store 6)** — `must_not_contact` does not include `_email_checks` ✓

3. **EMAIL_SEND (provider-driven)**
   - Gated at staging time by `eligibility.decide()` ✓
   - Coverage: ALL six stores ✓

4. **LINKEDIN_ADD_LEAD (`facing=True`)**
   - Pre-write check: `executionguard.revalidate(authorization)` at `src/providerwrites.py:2253` ✓
   - Coverage: ALL six stores via `eligibility.decide` ✓

5. **leadstop.sweep**
   - Calls `eligibility.must_not_contact(rec, contact)` at `src/leadstop.py:345` ✓
   - Coverage: Stores 1+2+3+4+5 ✓

**All write paths ARE gated. The audit's table is accurate.**

### Claim 4: The 76 re-verification is OWED

**CONFIRMED.** The audit explicitly states in §3:

> **Fresh read: OWED**
> **I cannot do a fresh read from this worktree.** `work/queue.jsonl` does not exist here — per QWEN.md, live queue state is in Claude's worktree only.

The audit correctly identifies that the 76 re-verification cannot be done from this worktree and is owed from Claude's worktree. This is an honest acknowledgment of a limitation, not a defect in the audit itself.

### Claim 5: Bounce gap in `_resume_revalidates_suppression`

**VERIFIED.** The audit's finding §4.4 states:

> `must_not_contact` does not include bounce (store 6). Bounce is checked in `eligibility._email_checks` at line 695, which runs only when the channel is known to be email. This is correct — a bounce says nothing about LinkedIn — but means `_resume_revalidates_suppression` (which calls `must_not_contact` only) does not catch bounced addresses.

**Verification:** `must_not_contact` at line 358-377 returns a tuple of five checks: `_suppressed`, `_client_own_domain`, `_record_state`, `_replied`, `_paused`. It does NOT call `_email_checks`. The bounce gap is REAL.

The audit correctly identifies this as a "minor gap" — a bounced address will bounce again at the provider, and the scope is per-address not per-company.

---

## §3. Existence is not function — is the artifact consumed?

**N/A.** TASK-412 is a read-only audit with no code changes. The artifact is a finding document, not a module or function. There is no production caller to trace.

The audit's value is in its documentation of the suppression architecture and its identification of the bounce gap. That value is realized when Claude reads it and decides whether to close the gap.

---

## §4. Are the tests falsifiable?

**N/A.** TASK-412 made no code changes and added no tests. The audit references existing tests:

- `tests/test_a_resume_revalidates_suppression_first.py` — added by TASK-331, not TASK-412
- This test verifies the CONDITIONAL guard on EMAIL_RESUME

The audit itself is a code reading, not a test. Its claims are verifiable by reading the code, which I have done.

---

## §5. Would merging this branch DELETE anything from master?

**YES, but only task files being moved between queue stages.**

The branch deletes three files from `docs/qwen-tasks/TODO/`:
1. `TASK-387-ledger-write-back-of-provider-sends-and-replies.md` — moved to `RUNNING/` on the branch
2. `TASK-410-glm-verify-task-400-critical-path.md` — moved to `REVIEW/` on the branch
3. `TASK-412-suppression-list-audit.md` — moved to `REVIEW/` on the branch

These are task file stage moves, not deletions of work. The files exist in their new locations on the branch. This is the normal workflow.

**No source code, tests, or documentation files are deleted.**

---

## §6. Scope drift — does the branch carry junk beside the work?

**SIGNIFICANT SCOPE DRIFT.** The branch `qwen-worker-3-r9-task285` carries work from 8+ tasks:

- TASK-285 (collision walk) — 330 lines in `scripts/collision_walk_report.py`, 242 lines in `docs/COLLISION-WALK-2026-09-25.md`
- TASK-358 (CheapVerifier) — 1141 lines in `src/providers/cheapverifier.py`, 95 lines in tests, 1575 lines in cassettes
- TASK-267 (LLM tiebreaker) — 385 lines in `scripts/stage_s3_llm_tiebreaker.py`, 436 lines in tests
- TASK-387 (provider event writeback) — 216 lines in tests
- TASK-432 (GLM verdict) — 210 lines in `docs/glm-reviews/`
- TASK-410 (GLM verdict) — 108 lines in `docs/glm-reviews/`
- TASK-426 (bison staging) — 84 lines changed
- TASK-412 (this audit) — 192 lines in task file only

**Total diff:** 39 files changed, 7167 insertions, 223 deletions.

**TASK-412's contribution:** 2 files changed (task file moved from TODO to REVIEW), 192 insertions, 17 deletions.

**Cherry-pick required:** To merge only TASK-412's work, cherry-pick commits `5bbf11101..58dcd9fb6` (the four TASK-412 commits). This will move the task file from TODO to REVIEW without bringing in the other tasks' work.

---

## §7. Falsification attempts

### Attempt 1: Can I find a write path that bypasses suppression?

**NO.** I traced every `facing=True` operation in `providerwrites.py`:
- EMAIL_ACTIVATE → `executionguard.revalidate` → `eligibility.decide` → all six stores
- LINKEDIN_ADD_LEAD → `executionguard.revalidate` → `eligibility.decide` → all six stores
- EMAIL_RESUME → `CONDITIONAL[_resume_revalidates_suppression]` → `must_not_contact` → five stores (bounce gap confirmed)

Every path is gated. The audit's claim is correct.

### Attempt 2: Can I show that `must_not_contact` actually includes bounce?

**NO.** I read `must_not_contact` at line 358-377. It returns a tuple of five checks, none of which is `_email_checks`. The bounce gap is real.

### Attempt 3: Can I show that the six stores can disagree?

**NO.** The audit correctly explains that the stores are separated by scope (domain / person / account / address / workspace) and none supersedes another. `eligibility.decide` reads all six in one call, so they cannot disagree at the decision point. A domain on `suppress.txt` and a contact with `unsubscribed=True` are different facts about different scopes, and both must be clear for a step to go out.

### Attempt 4: Can I find a production caller that does NOT use `eligibility.decide`?

**NO.** Every write path I traced goes through `eligibility.decide` or `must_not_contact`. The audit's claim that `eligibility.decide` is "the single authority" is correct.

---

## §8. Line number accuracy

The audit's line numbers are MOSTLY ACCURATE but not exact:

| Audit claim | Actual on branch | Actual on current master | Status |
|---|---|---|---|
| `eligibility.decide` at line 605 | 605 ✓ | 716 (shifted) | Accurate at time of audit |
| `eligibility._suppressed` at line 280 | 280 ✓ | 342 (shifted) | Accurate at time of audit |
| `eligibility._paused` at line 345 | 345 (check within function) | 407 (shifted) | Accurate |
| `eligibility._replied` at line 398-399 | 399 ✓ | 459 (shifted) | Accurate |
| `eligibility._email_checks` at line 695-696 | 695 ✓ | 806 (shifted) | Accurate |
| `must_not_contact` at line 358 | 358 ✓ | 420 (shifted) | Accurate at time of audit |
| `executionguard.revalidate` at line 959 | 959 ✓ | 959 ✓ | Accurate |
| `providerwrites.py:2253` revalidate call | 2253 ✓ | 2253 ✓ | Accurate |
| `_resume_revalidates_suppression` at line 1415 | 1415 ✓ | 1415 ✓ | Accurate |
| `CONDITIONAL[EMAIL_RESUME]` at line 1473 | 1473 ✓ | 1473 ✓ | Accurate |
| `accountpolicy.apply_reply` at line 551-553 | 553-554 | 553-554 ✓ | Close enough |
| `accountpolicy.apply_reply` at line 486-488 | 487-488 | 487-488 ✓ | Close enough |
| `channels._suppressed` at line 127-133 | 127 ✓ | 127 ✓ | Accurate |
| `channels._bounced` at line 96-122 | 96 ✓ | 96 ✓ | Accurate |
| `channels._unsubscribed` at line 91-92 | 90-92 | 90-92 ✓ | Accurate |
| `ingest.load_suppress` at line 109 | 109 ✓ | 109 ✓ | Accurate |
| `discovery.known` at line 205-206 | 205 ✓ | 205 ✓ | Accurate |
| `leadstop.py:345` must_not_contact | 345 ✓ | 345 ✓ | Accurate |
| `adapters.py:130-131` EMAIL_BOUNCED | 131 ✓ | 131 ✓ | Accurate |
| `hygiene.check` at line 337 checks store 1 | **INACCURATE** — hygiene.check does NOT check suppress.txt | N/A | **Wrong** |

**One inaccuracy:** The audit says store 1 (`suppress.txt`) is checked at "Ingest: `hygiene.check()` → `src/hygiene.py:337`" but `hygiene.check` does NOT check `suppress.txt`. It's checked in `eligibility._suppressed` at line 293, `channels._suppressed` at line 130, and `discovery.known` at line 205. The functional claim (it IS checked before writes) is correct, but the specific location cited is wrong.

---

## §9. Findings

### Finding 1: Audit is mostly accurate

**Severity:** Low  
**Confidence:** High  
**Evidence:** All six stores verified, all write paths verified, bounce gap confirmed, line numbers mostly accurate.  
**Disposition:** The audit achieves its objective: it names every store, confirms every write path, and honestly reports the owed item.

### Finding 2: One owed item — the 76 re-verification

**Severity:** Low  
**Confidence:** High  
**Evidence:** The audit explicitly states the 76 re-verification is owed from Claude's worktree. This is an honest acknowledgment, not a defect.  
**Disposition:** The owed item is a READ-ONLY operation that Claude can perform. It does not block the audit's value.

### Finding 3: One inaccuracy — store 1 location

**Severity:** Low  
**Confidence:** High  
**Evidence:** The audit says store 1 is checked at `hygiene.check` line 337, but it's actually checked at `eligibility._suppressed` line 293, `channels._suppressed` line 130, and `discovery.known` line 205.  
**Disposition:** Minor inaccuracy. The functional claim is correct; the specific citation is wrong. Does not undermine the audit's conclusions.

### Finding 4: Significant scope drift on the branch

**Severity:** Medium  
**Confidence:** High  
**Evidence:** The branch carries work from 8+ tasks (7167 insertions across 39 files). TASK-412's contribution is 2 files, 192 insertions.  
**Disposition:** Cherry-pick only TASK-412's commits (`5bbf11101..58dcd9fb6`) to avoid merging unrelated work.

### Finding 5: Bounce gap is real and correctly identified

**Severity:** Low  
**Confidence:** High  
**Evidence:** `must_not_contact` does not include `_email_checks`. `_resume_revalidates_suppression` calls `must_not_contact` only. A resume of a campaign holding a bounced email address would not be refused on bounce grounds.  
**Disposition:** The audit correctly identifies this as a "minor gap" and recommends Claude consider whether to close it. Low priority — the provider will re-bounce.

---

## §10. Recommendation

**REWORK** — with a narrow scope:

1. **Cherry-pick TASK-412's commits only:** `5bbf11101..58dcd9fb6` (four commits, 2 files changed). Do NOT merge the entire branch.

2. **Correct the inaccuracy:** Update the audit to say store 1 is checked at `eligibility._suppressed` line 293, `channels._suppressed` line 130, and `discovery.known` line 205 — NOT at `hygiene.check` line 337.

3. **Perform the owed item:** Claude should run the fresh read of the 76 from `work/queue.jsonl` in Claude's worktree to confirm they are still suppressed. This is a READ-ONLY operation.

4. **Decide on the bounce gap:** Claude should decide whether `_resume_revalidates_suppression` should also check `channels._bounced` for email-channel contacts. Low priority.

**The audit achieves its objective.** It names every store, confirms every write path, and honestly reports its limitations. The inaccuracy is minor and the owed item is acknowledged. The scope drift is the main concern — the branch must not be merged wholesale.

---

## §11. Reproducible commands

All verification was performed in an isolated worktree at the exact SHA:

```bash
# Create worktree
git worktree add .qwen/worktrees/glm-task520 c8a62f4109f47eb5338f1ef334d68f44dcb989ef --detach

# Verify SHA
git rev-parse c8a62f4109f47eb5338f1ef334d68f44dcb989ef

# Read the audit
git show c8a62f4109f47eb5338f1ef334d68f44dcb989ef:docs/qwen-tasks/REVIEW/TASK-412-suppression-list-audit.md

# Check function locations
cd .qwen/worktrees/glm-task520
grep -n "def decide\|def _suppressed\|def must_not_contact" src/eligibility.py
grep -n "def revalidate" src/executionguard.py
grep -n "revalidate" src/providerwrites.py

# Check what must_not_contact calls
sed -n '358,377p' src/eligibility.py

# Check what decide calls
sed -n '605,675p' src/eligibility.py

# Check diff stat
git diff master...c8a62f4109f47eb5338f1ef334d68f44dcb989ef --stat

# Check TASK-412's specific commits
git log --oneline 5bbf11101^..58dcd9fb6

# Check what TASK-412 changed
git diff 5bbf11101^..58dcd9fb6 --stat
```

---

## §12. Disposition summary

| Finding | Severity | Disposition |
|---|---|---|
| Audit mostly accurate | Low | VERIFIED |
| 76 re-verification owed | Low | OWED (acknowledged) |
| Store 1 location inaccurate | Low | CORRECT (minor) |
| Scope drift | Medium | CHERRY-PICK required |
| Bounce gap real | Low | VERIFIED (minor) |

**Overall: REWORK** — cherry-pick TASK-412's commits, correct the inaccuracy, perform the owed item, decide on the bounce gap.

---

**VERDICT: REWORK**

**Branch HEAD SHA reviewed:** `c8a62f4109f47eb5338f1ef334d68f44dcb989ef`

**Recommendation:** Cherry-pick commits `5bbf11101..58dcd9fb6` only. Correct the store 1 location inaccuracy. Perform the 76 re-verification from Claude's worktree. Decide on the bounce gap.
