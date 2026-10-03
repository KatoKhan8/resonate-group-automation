# TASK-512 — Independent GLM Verification of TASK-404

**Verifier:** GLM (Qwen worker 7)  
**Date:** 2026-10-04  
**Target branch:** `origin/qwen-worker-9-r9`  
**Target commit:** `f1b9c357c17f4b557cbdb06f68339c7343ef3e83` (HEAD of branch, verified)  
**TASK-404's artifact:** `docs/glm-reviews/TASK-404-verify-task-397.md`  
**Master baseline:** `origin/master`

---

## 1. Artifact Existence — VERIFIED ✓

**The artifact exists on this ref.**

```
git log --diff-filter=A --all -- docs/glm-reviews/TASK-404-verify-task-397.md
```

Returns commit `164c940baa04a766c5a76c0b57ecdb6d0c484717` ("TASK-404: GLM first-pass verification of TASK-397"). The file is present at the target SHA and contains a 166-line review document.

**Artifact kind:** Finding (GLM verification review of a read-only investigation).

---

## 2. READ-ONLY Claim — VERIFIED ✓

TASK-404 claimed TASK-397's branch (`qwen-worker-4-r9`) made no provider writes. I independently verified this against the current HEAD of that branch (`2cb8755afc8ad069ccab24a6d80819d779c57e54`):

```
git diff origin/master...2cb8755afc8ad069ccab24a6d80819d779c57e54 -- src/ --stat
```

Returns **empty** — zero changes to `src/`. The branch has been rebased since TASK-404 reviewed it (HEAD moved from `44ce1762` to `2cb8755a`), but the READ-ONLY claim still holds.

```
git diff origin/master...2cb8755afc8ad069ccab24a6d80819d779c57e54 -- src/ scripts/ tests/ | grep -iE "^\+.*\b(POST|PATCH|PUT|DELETE|requests\.post|...)\b"
```

Returns **NO PROVIDER WRITE OPERATIONS FOUND**.

**TASK-404's READ-ONLY verification is accurate.** No HeyReach write operations exist on the branch.

---

## 3. Trace References — VERIFIED ✓

TASK-404 claimed all line references in TASK-397's findings doc were accurate. I verified each against the code at the target SHA:

| TASK-404's claim | Verified? |
|---|---|
| `senderinventory.py:198-200` — CONNECTION_LIMIT, CONNECTION_MAX, MESSAGE_LIMIT | **YES.** Lines 198-200 define these constants. |
| `senderinventory.py:229-237` — `li_seat_state()` reads `accountLimits` | **YES.** Line 229: `limits = row.get("accountLimits")`, lines 230-237 extract the three constants. |
| `senderinventory.py:312` — `build_linkedin()` stores `daily_limit` | **YES.** Line 312: `daily_limit=(row.get("accountLimits") or {}).get(CONNECTION_LIMIT)`. |
| `senderinventory.py:208` — `REMAINING_UNKNOWN` | **YES.** Line 208: `REMAINING_UNKNOWN = "unknown"`. TASK-404 correctly noted TASK-397 cited `:196` in one place (which is the comment block, not the constant). |
| `heyreach.py:2889-2900` — `_read()` function with `READ_ROUTES_ALL` check | **YES.** Lines 2889-2900 contain `_read()` with the allowlist guard at line 2891. |
| `heyreach.py:2960-2986` — `li_accounts()`, `all_li_accounts()` | **YES.** Lines 2960-2963: `li_accounts()`. Lines 2965-2988: `all_li_accounts()`. |

**All trace references are accurate.** TASK-404's verification of the trace is correct.

---

## 4. TASK-397's Findings Document — EXISTS AT REVIEWED COMMIT ✓

TASK-404 referenced `docs/TASK-397-SEAT-CAP-FINDINGS.md` as TASK-397's artifact. This file **does not exist** at the target SHA (`f1b9c357c`) or on the current HEAD of `qwen-worker-4-r9` (`2cb8755a`).

However, at the commit TASK-404 actually reviewed (`44ce1762` on `qwen-worker-4-r9`), the file **did exist**:

```
git ls-tree -r --name-only 44ce1762 | grep TASK-397
docs/TASK-397-SEAT-CAP-FINDINGS.md
```

The file was later removed from `qwen-worker-4-r9` by subsequent work on that branch (the branch was rebased between `44ce1762` and `2cb8755a`). TASK-404's review was accurate for the state it reviewed.

**The artifact TASK-404 referenced existed at the time of review.** This is not a defect in TASK-404.

---

## 5. Arithmetic Verification — TASK-404 MADE ERRORS ✗

This is the critical finding. TASK-404 claimed TASK-397 had arithmetic discrepancies in finding 2. I independently verified the arithmetic against TASK-397's own table.

### TASK-397's claim (from `docs/TASK-397-SEAT-CAP-FINDINGS.md` at commit `44ce1762`):

> "13 of 33 healthy seats have `connectioRequestLimit < 40`. [...] Their configured limits total 694 connection requests/day vs the 1,054 a naive `40 × 33` would claim."

### Independent verification:

Seats with `connectioRequestLimit < 40` from the table:

| seat_id | conn_limit |
|---|---|
| 139699 | 0 |
| 143105 | 25 |
| 159259 | 25 |
| 169600 | 23 |
| **175552** | **25** |
| 177751 | 17 |
| 179527 | 19 |
| 181653 | 22 |
| 181658 | 18 |
| 191848 | 25 |
| 201959 | 15 |
| 201978 | 25 |
| 212356 | 15 |

**Count: 13 seats** ✓ TASK-397 was CORRECT.  
**Sum: 0+25+25+23+25+17+19+22+18+25+15+25+15 = 254** ✗ TASK-397 claimed 694 (WRONG).  
**Naive total: 40 × 33 = 1320** ✗ TASK-397 claimed 1054 (WRONG, but 1054 is the actual total of all 33 seats).

### TASK-404's verification:

TASK-404 claimed:

> "Counted from the table: seats 139699 (0), 143105 (25), 159259 (25), 169600 (23), 177751 (17), 179527 (19), 181653 (22), 181658 (18), 191848 (25), 201959 (15), 201978 (25), 212356 (15) = 12 seats with limit < 40. [...] Sum of throttled seats: 0+25+25+23+17+19+22+18+25+15+25+15 = 229, not 694."

**TASK-404 missed seat 175552 (25)** in its recount. The correct count is 13 (TASK-397 was right), not 12. The correct sum is 254, not 229 (TASK-404's recount) and not 694 (TASK-397's claim).

### Summary of arithmetic:

| Claim | Count | Sum |
|---|---|---|
| TASK-397 | 13 ✓ | 694 ✗ (actual: 254) |
| TASK-404 | 12 ✗ (actual: 13) | 229 ✗ (actual: 254) |
| Independent verification | **13** | **254** |

**TASK-404 incorrectly "corrected" TASK-397's count from 13 to 12, when TASK-397 was right.** TASK-404 also made its own arithmetic error (229 instead of 254) by missing seat 175552.

Both TASK-397 and TASK-404 have arithmetic errors in the sum, but TASK-397 got the count right and TASK-404 got it wrong.

---

## 6. Scope Drift — SIGNIFICANT

The branch `qwen-worker-9-r9` carries **massive scope beyond TASK-404**. The diff against master shows:

- **64 files changed**, 6818 insertions, 226 deletions
- **15 files in src/scripts/tests**, including entirely new modules:
  - `src/providers/groq.py` (427 lines)
  - `src/providers/openrouter.py` (398 lines)
  - `scripts/refill_queue.py` (156 lines)
  - `scripts/measure_research_freshness.py` (244 lines)
  - Multiple new test files
- **Many other tasks' work** mixed in: TASK-305, TASK-313, TASK-384, TASK-392, TASK-399, TASK-400, TASK-401, TASK-402, TASK-403, TASK-416, etc.

TASK-404's own commits are clean (just the review document and task file move), but the branch is a multi-task accumulation. **Merging this branch would require cherry-picking TASK-404's specific commits, not merging the whole branch.**

Two TODO files are deleted (`TASK-392`, `TASK-399`), but both were moved to REVIEW, which is legitimate task state progression, not data loss.

---

## 7. Disposition

**REWORK** with specific corrections required.

### Rationale:

1. **The artifact exists and is substantive.** TASK-404 produced a 166-line review document that verifies TASK-397's READ-ONLY claim, trace references, and findings quality. The review is thorough and follows the GLM protocol.

2. **READ-ONLY verification is accurate.** TASK-404 correctly confirmed no provider writes occurred on TASK-397's branch.

3. **Trace verification is accurate.** All line references check out.

4. **BUT: TASK-404's arithmetic verification contains errors.** TASK-404 incorrectly claimed TASK-397 miscounted the throttled seats (12 vs 13), when TASK-397 was right. TASK-404 also made its own sum error (229 vs 254) by missing seat 175552. This is a verification defect: the verifier introduced errors while trying to catch the original task's errors.

5. **The branch has massive scope drift.** TASK-404's work is clean, but the branch carries 63 other files' changes from many other tasks. Cherry-pick is required, not merge.

### Required corrections:

1. **Correct the arithmetic in TASK-404's review document.** The throttled seats count is 13 (TASK-397 was right), not 12. The sum is 254, not 229 (TASK-404) and not 694 (TASK-397). The naive total is 1320 (40 × 33), not 1054 (TASK-397), though 1054 is the actual total of all 33 seats.

2. **Acknowledge TASK-397 got the count right.** TASK-404's "correction" from 13 to 12 is itself wrong.

### Recommended Claude action:

1. **Cherry-pick TASK-404's review document** (`docs/glm-reviews/TASK-404-verify-task-397.md`) — the review is substantive and mostly accurate.
2. **Correct the arithmetic** in the review document before merging (13 seats, not 12; sum 254, not 229 or 694).
3. **Do not merge the whole branch** — cherry-pick only TASK-404's commits (`164c940ba`, `27fa4bc0d`).
4. **TASK-397's findings document** (`docs/TASK-397-SEAT-CAP-FINDINGS.md`) existed at the time of review but was later removed from `qwen-worker-4-r9`. If reintegrating TASK-397's findings, the arithmetic in finding 2 should also be corrected (sum is 254, not 694).

---

## 8. Eight-Disposition Check

TASK-404's review is itself a verification artifact, not code. The protocol's eight dispositions apply to code review findings. For this verification review:

- **READ-ONLY confirmation** → **FIXED + VERIFIED** (no defect, confirmed accurate)
- **Trace references** → **FIXED + VERIFIED** (all accurate)
- **Arithmetic verification** → **REWORK REQUIRED** (TASK-404 introduced errors while verifying)
- **Artifact existence** → **FIXED + VERIFIED** (existed at reviewed commit)
- **Scope drift** → **OPERATOR DECISION REQUIRED** (cherry-pick, not merge)

---

## 9. Falsification Attempts

### Did TASK-404 fabricate the READ-ONLY claim?

**No.** Independent verification confirms no provider writes on TASK-397's branch.

### Did TASK-404 fabricate the trace verification?

**No.** All line references are accurate.

### Did TASK-404 accurately verify TASK-397's arithmetic?

**No.** TASK-404 made its own arithmetic errors while trying to catch TASK-397's errors. The verifier introduced defects.

### Would merging TASK-404's branch delete anything from master?

**Only two TODO files** (`TASK-392`, `TASK-399`), both legitimately moved to REVIEW. No production code, tests, or documentation would be deleted.

---

## 10. Final Verdict

**REWORK** — TASK-404's review is substantive and mostly accurate, but contains arithmetic verification errors that must be corrected before merge.

**Specific defects:**
1. TASK-404 incorrectly claimed TASK-397 miscounted throttled seats (12 vs 13). TASK-397 was right (13).
2. TASK-404's own sum (229) is wrong. Actual sum is 254.
3. TASK-404 missed seat 175552 in its recount.

**What is accurate:**
1. READ-ONLY confirmation ✓
2. Trace verification ✓
3. Artifact existence ✓
4. Overall assessment that TASK-397 is a valid read-only investigation ✓

**Merge recommendation:** Cherry-pick TASK-404's commits (`164c940ba`, `27fa4bc0d`) after correcting the arithmetic in the review document. Do not merge the whole branch.

**Branch HEAD SHA reviewed:** `f1b9c357c17f4b557cbdb06f68339c7343ef3e83` (verified, not assumed).
