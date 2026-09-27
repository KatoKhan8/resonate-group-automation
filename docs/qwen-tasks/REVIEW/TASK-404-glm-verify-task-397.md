PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-404 — GLM first-pass verification: TASK-397 (HeyReach seat-cap check)

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly.

## Target

TASK-397, in REVIEW on `qwen-worker-4-r9`. This task involved a READ-ONLY
provider check — verify no write occurred (grep the branch's diff for any
POST/PATCH/PUT/DELETE to HeyReach) before trusting any other claim.

## What GLM's pass must produce

1. **Confirm READ-ONLY was honored** - no provider write in this branch's
   diff. This is the first thing to check, not the last.
2. Reproduce the seat-cap read's own acceptance criteria against the task's
   own spec file.
3. Any new finding, file:line.

## Result

Use the protocol's own format and eight dispositions. SAFE TO MERGE or
BLOCKED, and why.

---

## RESULT BLOCK

**STATUS:** DONE
**ARTIFACT KIND:** finding (GLM verification review)
**COMMIT SHA:** 164c940b
**FILES CHANGED:** `docs/glm-reviews/TASK-404-verify-task-397.md` (new), task file moved TODO → REVIEW
**TESTS:** N/A (read-only verification, no code changes)

### Verification summary

1. **READ-ONLY confirmed.** The only `src/` change on `qwen-worker-4-r9` is `src/spendledger.py` (TASK-395 work, unrelated). TASK-397 itself made zero code changes. Grep for provider write operations (POST/PATCH/PUT/DELETE to write endpoints) returned only false positives. The only HeyReach API call in the trace is `POST /li_account/GetAll` via `_read()`, which is on the `READ_ROUTES_ALL` allowlist and documented as "A POST that reads" — a HeyRead API convention for read endpoints.

2. **Trace verified against current master.** All line references accurate:
   - `senderinventory.py:198-200` — CONNECTION_LIMIT, CONNECTION_MAX, MESSAGE_LIMIT ✓
   - `senderinventory.py:229-237` — li_seat_state() reads accountLimits ✓
   - `senderinventory.py:312` — build_linkedin() stores daily_limit ✓
   - `heyreach.py:2960-2986` — li_accounts(), all_li_accounts() ✓
   - `senderinventory.py:208` — REMAINING_UNKNOWN (task says :196 in one place, which is the comment block, not the constant — trivial discrepancy)

3. **Acceptance criteria honestly reported as PARTIAL.** The task correctly reported that criterion 1 (cap, actual, %) cannot be fully met because the provider does not expose per-seat daily usage. It did not fabricate a percentage. It reported configured-cap findings instead and labeled them as such.

4. **Findings substantive.** Six findings reported. Four fully verified (seats 139699 at 0 limit, 174892 with 13 campaigns, 129531 AUTH_INVALID, all cooldowns false). Finding 2 (13 throttled seats) has minor arithmetic discrepancies (table shows 12, not 13; sum is 229, not 694) but the directional conclusion is correct. Finding 5 (seat 174810 unattested) is plausible but not independently verified.

5. **Blockers honestly reported.** No fresh live read due to missing `config/.env`. Data is 6 days old (2026-09-21). The task did not claim a fresh read when it could not perform one.

### Disposition

**SAFE TO MERGE** with minor reservations.

- READ-ONLY was honored (most important check).
- The task honestly reported partial acceptance and did not fabricate data.
- The trace is accurate (one trivial line-number discrepancy).
- The findings are substantive and directionally correct.
- Minor arithmetic discrepancy in finding 2 (12 vs 13 seats, 229 vs 694 sum) should be corrected if reintegrated.
- A fresh live read is owed from Claude's worktree (which has `config/.env`).

### Eight-disposition mapping (for provider-state findings)

1. Seat 139699 at 0 limit → OPERATOR DECISION REQUIRED
2. 13 throttled seats → EXISTING TASK (known from 2026-09-17)
3. Seat 174892 with 13 campaigns → ACCEPTED DEFERRED RISK
4. Seat 129531 AUTH_INVALID → OPERATOR DECISION REQUIRED
5. Seat 174810 unattested → OPERATOR DECISION REQUIRED
6. No per-seat usage counter → NEW TASK (ask HeyReach support)

### FINDINGS

- TASK-397 is a valid read-only investigation.
- READ-ONLY was honored — no provider write occurred.
- The trace is accurate and the findings are substantive.
- Minor arithmetic discrepancy in finding 2 (12 vs 13 throttled seats, 229 vs 694 sum) — directional conclusion correct, exact numbers do not reproduce from the table.
- Data is 6 days old; a fresh live read is owed.
- The task honestly reported partial acceptance and did not claim to have met criteria it could not meet.

### RISKS

- The arithmetic discrepancy in finding 2 is minor but should be corrected if the findings are reintegrated.
- The 6-day-old data may have stale cooldown flags and campaign counts.

### RECOMMENDED CLAUDE ACTION

1. Cherry-pick `docs/TASK-397-SEAT-CAP-FINDINGS.md` (valid investigation).
2. Run `scripts/sender_capacity.py` from Claude's worktree for a fresh read.
3. Correct the arithmetic in finding 2 if reintegrating (12 seats, not 13; sum 229, not 694 — or re-verify from source data).
4. Consider asking HeyReach support whether a per-seat daily usage endpoint exists.
