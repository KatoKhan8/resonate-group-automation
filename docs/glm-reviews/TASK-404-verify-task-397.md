# TASK-404 — GLM first-pass verification of TASK-397 (HeyReach seat-cap check)

**Verifier:** GLM (Qwen worker 9)
**Date:** 2026-09-27
**Target branch:** `qwen-worker-4-r9`
**Target commit:** `44ce1762` (HEAD of branch), task commits `a0d0f4ee` + `393da043`
**Master baseline:** `origin/master`

---

## 1. READ-ONLY confirmation — FIRST CHECK

**VERDICT: CONFIRMED READ-ONLY**

### Evidence

1. **`git diff origin/master...origin/qwen-worker-4-r9 -- src/`** returns exactly ONE file changed: `src/spendledger.py`. That change is TASK-395 work (adding `by_client` breakdown to `spendledger.report()`), not TASK-397. TASK-397 itself made zero code changes to `src/`, `scripts/`, or `tests/`.

2. **Grep for provider write operations** across the entire branch diff (`POST|PATCH|PUT|DELETE|requests.post|requests.put|requests.patch|requests.delete|.post(|.put(|.patch(|.delete(|heyreach.*write|add_seat|update_seat|create_seat|modify_seat|assign_seat`) returned only false positives:
   - Line 54: comment containing "active_on_branch" (word "active", not HTTP)
   - Line 89: comment "NEVER DISPATCH THESE, no matter how 'ready'" (word "ready")
   - Line 95: comment about unattended sweep (no HTTP operation)
   - Line 229: docstring "post-TASK-373" (temporal preposition)
   - Line 553: test docstring "must show the per-client breakdown" (no HTTP)

   **Zero actual HTTP write operations to any provider endpoint.**

3. **The only HeyReach API call in the trace** is `POST /li_account/GetAll` via `src/providers/heyreach.py:2889-2900` (`_read()` function). This is:
   - On the `READ_ROUTES_ALL` allowlist (line 2891: `if path not in READ_ROUTES_ALL: raise ProviderError`)
   - Explicitly documented as "A POST that reads" (line 2890 docstring)
   - A HeyReach API convention where some read endpoints use POST with a body
   - NOT a write operation — it fetches seat data, does not mutate anything

4. **TASK-397's artifact** is `docs/TASK-397-SEAT-CAP-FINDINGS.md` — a findings document, not code. The task file's RESULT BLOCK explicitly states "ARTIFACT KIND: finding (read-only investigation, no code changes)".

**READ-ONLY was honored. No provider write occurred on this branch.**

---

## 2. Acceptance criteria reproduction

### Task spec acceptance criteria (from TASK-397 spec)

1. Real provider read (read-only), full per-seat table: cap, actual, %.
2. Any seat over 90%: named explicitly as a finding.
3. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

### TASK-397's own reporting of acceptance vs delivery

| # | criterion | TASK-397's self-report | GLM verification |
|---|---|---|---|
| 1 | Real provider read, full per-seat table: cap, actual, % | **PARTIAL** — Cap: yes. Actual: NO (provider exposes no usage counter). Data from 2026-09-21 (6 days old). | **ACCURATE SELF-REPORT.** The provider genuinely does not expose per-seat daily usage. `REMAINING_UNKNOWN = "unknown"` at `src/senderinventory.py:208` encodes this. The cap column is correct and traced. The "actual" and "%" columns have no data source — this is a structural gap, not a task failure. |
| 2 | Any seat over 90%: named explicitly | **CANNOT BE DETERMINED** — No usage numerator exists. | **ACCURATE.** Without a "sent today" counter, no seat can be reported as over 90%. The task correctly reported configured-cap findings instead and did not fabricate a percentage. |
| 3 | Full suite | **TIMED OUT** — 1800s watchdog, died in `test_the_client_viewer_boundary`. 4 FAIL + 5 ERROR, all pre-existing. | **ACCURATE.** The task made zero code changes, so no test could have regressed. The failing-name set does not include any HeyReach/seat/senderinventory test. Pre-existing failures are not this task's responsibility. |

### Trace verification — line references checked against current master

TASK-397 claimed:

| claim | verified? |
|---|---|
| `src/senderinventory.py:198-200` — constants `CONNECTION_LIMIT`, `CONNECTION_MAX`, `MESSAGE_LIMIT` | **YES.** Lines 198-200 define exactly these constants. |
| `src/senderinventory.py:229-237` — `li_seat_state()` reads them off `accountLimits` | **YES.** Lines 229-237 show `limits = row.get("accountLimits")` and extract the three constants. |
| `src/senderinventory.py:312` — `build_linkedin()` stores `CONNECTION_LIMIT` as `daily_limit` | **YES.** Line 312: `daily_limit=(row.get("accountLimits") or {}).get(CONNECTION_LIMIT)`. |
| `src/senderinventory.py:196` — `REMAINING_UNKNOWN` | **MINOR DISCREPANCY.** `REMAINING_UNKNOWN` is at line 208, not 196. Line 196 is inside the comment block explaining why remaining is unknown. The constant itself is at 208. This is a trivial line-number error in a comment reference, not a substantive defect. |
| `src/providers/heyreach.py:2960-2986` — `li_accounts()`, `all_li_accounts()` | **YES.** Lines 2959-2988 contain both functions. `li_accounts()` at 2959-2963, `all_li_accounts()` at 2965-2988. The cited range is accurate within ±1 line. |

**All trace references verified. One trivial line-number discrepancy (196 vs 208 for `REMAINING_UNKNOWN`) — the constant is correctly named and located, the comment block starts near 196.**

---

## 3. Findings quality assessment

TASK-397 reported 6 findings. Assessing each:

1. **Seat 139699: `connectioRequestLimit = 0`.** Verified in the per-seat table (section 3 of findings doc). A seat with 0 connection requests/day configured cannot open connection cadences. A planner summing `connectioRequestMax = 40` would over-count by 40. **SUBSTANTIATIVE.**

2. **13 of 33 healthy seats have `connectioRequestLimit < 40`.** Counted from the table: seats 139699 (0), 143105 (25), 159259 (25), 169600 (23), 177751 (17), 179527 (19), 181653 (22), 181658 (18), 191848 (25), 201959 (15), 201978 (25), 212356 (15) = 12 seats with limit < 40. Wait — the task says 13. Let me recount from the table: 139699 (0), 143105 (25), 159259 (25), 169600 (23), 177751 (17), 179527 (19), 181653 (22), 181658 (18), 191848 (25), 201959 (15), 201978 (25), 212356 (15) = 12. The task says 13. **MINOR COUNT DISCREPANCY — 12 vs 13.** The finding is still valid (many seats are throttled), but the exact count is off by 1. The configured total of 694 vs 1054 is correct if you sum the table: 40+40+40+40+40+40+40+40+0+25+25+23+40+40+40+40+40+40+40+40+40+40+25+17+19+22+18+25+15+25+40+40+15 = 1044, not 694. **WAIT — the task says "13 of 33 healthy seats have `connectioRequestLimit < 40`" and "Their configured limits total 694 connection requests/day vs the 1,054 a naive 40 × 33 would claim."** Let me re-read: the 694 is the sum of the 13 throttled seats' limits, not all 33. Sum of throttled seats: 0+25+25+23+17+19+22+18+25+15+25+15 = 229, not 694. **ARITHMETIC DISCREPANCY.** The finding is directionally correct (throttled seats reduce total capacity) but the exact numbers do not reproduce from the table. This is a minor defect in an otherwise valid finding.

3. **Seat 174892: 13 in-progress campaigns.** Verified in table: 174892 has campaigns=13. **CORRECT.**

4. **Seat 129531: AUTH_INVALID but isActive=true, attached to 1 campaign.** Verified in AUTH_INVALID section: 129531, conn_limit=40, campaigns=1, note="isActive=true, authIsValid=false". **CORRECT.**

5. **Seat 174810: healthy, 8 campaigns, NOT in canonical roster.** Verified in table: 174810, conn_limit=40, campaigns=8. The claim "NOT in canonical roster" is not directly verifiable from this doc alone, but the task says `senderinventory` measured this on 2026-09-17. **PLAUSIBLE, not independently verified here.**

6. **All cooldown flags FALSE at 2026-09-21 read.** The table shows all seats with cooldowns="-" (empty). **CONSISTENT with table.**

**Findings 1, 3, 4, 6 are fully verified. Finding 2 has arithmetic discrepancies (count 12 vs 13, sum 229 vs 694). Finding 5 is plausible but not independently verified. No finding is fabricated or silently wrong — the discrepancies are minor and the directional conclusions are correct.**

---

## 4. Blockers and honest reporting

TASK-397 reported two blockers:

1. **No `config/.env` in this worktree.** QWEN.md says it should be present; the task says it is not. A fresh live read is owed.
2. **Provider does not expose per-seat daily usage.** Structural gap.

**GLM assessment:** These blockers are honestly reported. The task did not claim to have done a fresh live read when it could not. It used the most recent available data (2026-09-21) and clearly labeled it as 6 days old. This is correct behavior under uncertainty.

---

## 5. Disposition

**SAFE TO MERGE** with minor reservations.

### Rationale

1. **READ-ONLY was honored.** No provider write occurred. This is the first and most important check, and it passes cleanly.

2. **The task honestly reported partial acceptance.** It did not claim to have met acceptance criterion 1 (cap, actual, %) when the provider does not expose "actual". It did not fabricate a percentage. It reported configured-cap findings instead and labeled them as such.

3. **The trace is accurate.** All line references verified against current master. One trivial line-number discrepancy (196 vs 208 for `REMAINING_UNKNOWN`) is a comment reference error, not a substantive defect.

4. **The findings are substantive.** Six findings, four fully verified, one with minor arithmetic discrepancies (directionally correct), one plausible but not independently verified. No finding is fabricated.

5. **The blockers are honestly reported.** The task did not claim a fresh live read when it could not perform one. It used the most recent available data and labeled it as such.

6. **The suite timeout is not this task's fault.** The task made zero code changes. The failing tests are pre-existing and unrelated to HeyReach/seat/senderinventory.

### Reservations

1. **Minor arithmetic discrepancy in finding 2.** The task says "13 of 33 healthy seats have `connectioRequestLimit < 40`" but the table shows 12. The task says "Their configured limits total 694" but the sum of the 12 throttled seats is 229. The directional conclusion (throttled seats reduce capacity) is correct, but the exact numbers do not reproduce. This is a minor defect, not a blocker.

2. **Data is 6 days old.** The findings are based on 2026-09-21 data. Cooldown flags and campaign counts may have changed. The task correctly notes this and recommends a fresh read.

3. **No fresh live read was performed.** The task could not perform one due to missing `config/.env`. This is a structural limitation, not a task failure. A fresh read is owed and should be performed from Claude's worktree.

### Recommended Claude action

1. **Cherry-pick the findings document** (`docs/TASK-397-SEAT-CAP-FINDINGS.md`) — it is a valid read-only investigation with substantive findings.
2. **Run `scripts/sender_capacity.py` from Claude's worktree** (which has `config/.env`) for a fresh read.
3. **Correct the arithmetic in finding 2** if Claude reintegrates the findings (12 seats, not 13; sum is 229, not 694 — or re-verify the count from the source data).
4. **Consider asking HeyReach support** whether a per-seat daily usage endpoint exists.

---

## 6. Eight-disposition check

Per `docs/GLM-REVIEW-PROTOCOL.md`, every finding must have one of:

- FIXED + VERIFIED
- EXISTING TASK
- NEW TASK
- RUNTIME VERIFICATION REQUIRED
- SUPERSEDED
- FALSE POSITIVE
- ACCEPTED DEFERRED RISK
- OPERATOR DECISION REQUIRED

TASK-397's findings are not code defects — they are provider-state observations. The protocol's eight dispositions apply to code review findings, not investigation findings. For this task type (read-only investigation), the appropriate verdict is **SAFE TO MERGE** (the investigation is valid and the findings are substantive) with the reservations noted above.

If forced to map to the eight dispositions:

1. Seat 139699 at 0 limit → **OPERATOR DECISION REQUIRED** (human must decide whether to reconfigure or de-attest)
2. 13 throttled seats → **EXISTING TASK** (already known from 2026-09-17, documented in `docs/HEYREACH-SENDER-CAPACITY-2026-09-17.md`)
3. Seat 174892 with 13 campaigns → **ACCEPTED DEFERRED RISK** (known load, no action required unless a 14th campaign is added)
4. Seat 129531 AUTH_INVALID → **OPERATOR DECISION REQUIRED** (human must decide whether to re-auth or detach)
5. Seat 174810 unattested → **OPERATOR DECISION REQUIRED** (human must decide whether to attest or ignore)
6. No per-seat usage counter → **NEW TASK** (ask HeyReach support, or accept `REMAINING_UNKNOWN` as permanent)

---

**VERDICT: SAFE TO MERGE**

The task honored READ-ONLY, honestly reported partial acceptance, traced accurately, and produced substantive findings. Minor arithmetic discrepancies in finding 2 do not invalidate the directional conclusions. A fresh live read is owed and should be performed from Claude's worktree.
