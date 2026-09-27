# Register hygiene audit — 2026-09-25

**Auditor:** Qwen worker 4 (qwen-worker-4-r60)
**Scope:** `docs/state/PROBLEM-REGISTER.md` as it stands on master at `0af11fcb`.
**Rule:** audit and propose. The register is NOT edited.

---

## 1. Row count

The task file says 39 rows. The register now has **44 `### ISSUE-` headings**.
Five rows were added after the task was written: ISSUE-041 through ISSUE-045,
all committed 2026-09-24 (`5cd5173d`). Every one of the 44 appears in the
table below.

---

## 2. Full audit table

For each row: id, title (truncated), claimed status, duplicated?, evidence
named?, status supported by evidence?

| # | ID | Title | Claimed | Dup? | Evidence named? | Supported? |
|---|-----|-------|---------|------|-----------------|------------|
| 1 | ISSUE-041 | Cross-channel stop reports success having never called provider | FIXED | No | Commit `5cd5173d`; test `test_a_linkedin_stop_is_not_handed_the_email_campaign.py` (shared with 042) | PARTIAL — no ISSUE-041-specific regression test; the shared test covers 042's `_campaign_of` fix, not 041's `heyreach_lead_id` binding |
| 2 | ISSUE-042 | `_campaign_of` resolved channel-blind | FIXED | No | Commit `5cd5173d`; `test_a_linkedin_stop_is_not_handed_the_email_campaign.py` (5 tests, all green) | YES |
| 3 | ISSUE-043 | `attach_leads` raises on a write that succeeded | OPEN | No | Measurement at provider (lead 205079, campaign 491, t+30s readback) | YES — measurement supports OPEN |
| 4 | ISSUE-044 | New test lead not suppressed until id added by hand | OPEN | No | Measurement: `matches(205079)` False, `matches(address)` True | YES |
| 5 | ISSUE-045 | Nothing can send outside 09:00-17:00 | OPEN | No | Measurement: all 15 EmailBison campaigns 09:00-17:00 Mon-Fri | YES |
| 6 | ISSUE-034 | Research pack named three Apify actors that do not exist | FIXED | **YES** (see §3) | Commit named in text; test `test_researchpack.py` (21 tests, all green) | PARTIAL — the register names `EveryActorIdIsOneApifyKnows` as the regression test class. **That class does not exist.** The file has 21 tests across 7 other classes, all green, but none by the named name |
| 7 | ISSUE-035 | Deliberate stop reads as account-level hold | OPEN | No | Provider measurement of 63 stopped leads | YES |
| 8 | ISSUE-036 | `find_campaigns_by_name` cannot find a campaign just created | OPEN | No | Campaign 500 measurement | YES |
| 9 | ISSUE-037 | Blank-render gate refuses AFTER attach | OPEN | No | Measurement: campaigns 496/497/498 before/after counts | YES |
| 10 | ISSUE-016 (recurred) | `attach_leads` reports REFUSED on succeeded write — RECURRED | OPEN | **YES** (see §3) | Campaign 497/498 measurement | YES — measurement supports OPEN |
| 11 | ISSUE-032 | Bot cannot post/upload in Slack Connect channel | OPEN/FROZEN | No | `slack_complete_file_upload` error, `slack_send_message_draft` success | YES |
| 12 | ISSUE-033 | REFUTED — 481 refused on wrong findings | REFUTED | No | Re-reading the provider; cross-tabulation of sending_paused vs foreign | YES — REFUTED with evidence |
| 13 | ISSUE-031 | QUALIFIED-only ruling enforced at writer not reader | FIXED/RETIRED | No | Commits `d7f3128a`, `a3c02e08`; test `ThisDoesNotUnblockTheExport` | PARTIAL — `ThisDoesNotUnblockTheExport` is a test NAME not a file; no module path given. Commit SHAs verified on master |
| 14 | ISSUE-026 | `emptyrender.scan` called PAUSED contained | FIXED + PRODUCTION_VERIFIED | No | Commit `5257adbe`; 30 tests; provider readback of row 22356723 | YES — provider observation named |
| 15 | ISSUE-027 | External-stop CRITICAL named campaign 487 | FIXED | No | Commit `d6a719c2`; `test_a_campaign_we_did_not_stop_is_critical.py` | YES |
| 16 | ISSUE-028 | Witness 1 unsatisfiable | FIXED + PRODUCTION_VERIFIED | No | Commit `c1d93e94`; `supervisor.record_started` call-site test by `ast` | PARTIAL — test module not named; commit verified. PV claim: "20 of 20 monitors have two witnesses" |
| 17 | ISSUE-029 | Gagged client question reached nobody | FIXED | No | Commit `c62c6309`; "5 tests; removing the alert from the branch fails them" | PARTIAL — test module not named; commit verified |
| 18 | ISSUE-030 | No documented route for removing lead from campaign | OPEN | No | `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md` (50 routes enumerated) | YES |
| 19 | ISSUE-025 | Adopting lead by email carries client's lead | FIXED (code only) | No | Commit `7bb23d6d`; `test_a_blank_email_can_never_be_sent_again.py` (30 tests, green) | YES — explicitly NOT production-verified |
| 20 | ISSUE-012 (ceiling) | Company-search slice ceiling 400 pages | MEASURED | **YES** (see §3) | Direct probe: page 399 OK, 401 HTTP 500 | YES — measurement supports MEASURED |
| 21 | ISSUE-011 (LinkedIn) | LinkedIn ownership allowlist went stale | FIXED (code only) | **YES** (see §3) | `test_ownership_readback_staleness.py` (10 tests, green); readback refreshed live | YES — explicitly NOT production-verified |
| 22 | ISSUE-001 | Reply ingestion discarded reply event | FIXED | No | Commit `0379958d`; 8 tests including reproduction | YES |
| 23 | ISSUE-002 | DNC could not stop HeyReach sequence | FIXED | No | Commit `abfc844a`; 28 new tests | PARTIAL — `test_task235_dnc_cannot_stop_linkedin.py` has 1 RED test (`SUPPORTED` count 16 ≠ 15). The seal the row asserts has drifted |
| 24 | ISSUE-003 | Reconciler settled nothing | FIXED | No | Commit `ac6f7996`; TASK-237 | PARTIAL — no specific regression test named |
| 25 | ISSUE-004 | Dispatcher starved, stranded count wrong | OPEN (partial) | No | `scripts/task173_scan.py` | YES — partially resolved, correctly OPEN |
| 26 | ISSUE-005 | No notification delivered anywhere | OPEN (partial) | No | `scripts/slack_smoke.py` Slack receipt `ts 1789990679.422989` | YES — partially unblocked |
| 27 | ISSUE-006 (reopened) | PII guard was red — REOPENED | REOPENED/GREEN | **YES** (see §3) | 13 files enumerated, all redacted | YES |
| 28 | ISSUE-006 (original) | PII guard was red — original | FIXED | **YES** (see §3) | Commit `cecd4223`; 13/13 green | YES |
| 29 | ISSUE-010 | Zero senders eligible | OPEN/BLOCKED | No | Provider measurements: 2025 headroom, 0 `HUMAN_IDENTITY_ATTESTED` | YES |
| 30 | ISSUE-007 | 489 planned onto full mailbox-day | BLOCKED | No | `docs/489-COULD-GO-THREE-DAYS-EARLIER-2026-09-20.md` | YES |
| 31 | ISSUE-008 | GLM truncated response | NEW | No | `finish_reason='length'`, auth verified 200 in 1840ms | YES |
| 32 | ISSUE-014 | ACTIVATED campaign can never be topped up | OPEN | No | Provider readback per lead; `staging_artifact_evidence(495)` quoted | YES |
| 33 | ISSUE-015 | Planted-cohort-name guard flags ordinary English | OPEN | No | Measurement: 269 name='Will' pairs | YES |
| 34 | ISSUE-016 (original) | `attach_leads` reports REFUSED on succeeded write | OPEN | **YES** (see §3) | Campaign 493 measurement | YES |
| 35 | ISSUE-017 | Re-engagement inventory stores stale lane | FIXED | No | 7 tests; `walk()` now passes campaign status | PARTIAL — no commit SHA named |
| 36 | ISSUE-019 | Candidate pipeline passes ICP REVIEW as IN | OPEN | No | `exportable_candidates()` measurement: 1508 rows, 1394 review | YES |
| 37 | ISSUE-024 | Channel-exclusion list English-only | FIXED/CLOSED | No | `test_a_payroll_channel_is_never_pulled.py` (13 tests, green) | PARTIAL — no commit SHA named |
| 38 | ISSUE-023 | QUALIFIED as wrong as REVIEW | OPEN | No | 114 QUALIFIED measurement | YES |
| 39 | ISSUE-020 | Successive sourcing runs re-walked page one | FIXED | No | "Verified - a fresh run resumed at page 17" | NO — no commit SHA, no test name |
| 40 | ISSUE-022 | Store atomic write loses to concurrent reader on Windows | OPEN | No | `PermissionError` quoted; temp files enumerated | YES |
| 41 | ISSUE-011 (forward book) | Forward book COVERING decays silently | OPEN | **YES** (see §3) | Census measurement: 1470 → 1301 corrected | YES — correctly OPEN |
| 42 | ISSUE-012 (collision) | Collision gate refused batch supply as NOT WALKED | FIXED | **YES** (see §3) | `scripts/s6_collision_walk.py` | PARTIAL — no commit SHA, no test module named |
| 43 | ISSUE-013 | `batch_eligibility` could not finish | FIXED | No | "Loading the ledger once and passing it through" | NO — no commit SHA, no test name |
| 44 | ISSUE-009 | Two model workers invisible to credential health | NEW | No | `ZAI_API_KEY` and `XAI_API_KEY` absent from `config.VARIABLES` | YES — correctly NEW |

**Plus the FIXED tables (F-001 through F-009) and REFUTED table (REFUTED-001 through REFUTED-006).**
These are in their own table format and are not part of the 44 `### ISSUE-` rows, but they are audited below.

### FIXED table audit

| ID | Commit | Exists? | Test named | Test exists? | PV claim | PV supported? |
|----|--------|---------|------------|--------------|----------|---------------|
| F-001 | `28f4766e` | YES | "13 new" | Not individually named | `provider_truth.py` completed live against 4 HeyReach campaigns | YES — named doc/run |
| F-002 | `d321c2ef` | YES | "11 new" | Not individually named | Derived set matches provider exactly | YES |
| F-003 | `c9ddf35d` | YES | "6 new" | Not individually named | "not yet — no production caller exists" | N/A (honest) |
| F-004 | `5ff914d1` | YES | "3 new" | Not individually named | "not yet" | N/A (honest) |
| F-005 | `03d9da3f` | YES | docs | n/a | n/a | n/a |
| F-006 | `98b05550` | YES | "Verified present 2026-09-20" | Not a test, a verification | n/a | n/a |
| F-007 | `55ccb7b6` | YES | Not named | Not named | n/a | n/a |
| F-008 | Not given | n/a | Not named | Not named | "Verified 2026-09-20" | Informal |
| F-009 | `27bcdb67` | YES | Not named | Not named | n/a | n/a |

### REFUTED table audit

All six REFUTED rows (REFUTED-001 through REFUTED-006) are present, named, and
carry evidence for why the claim is wrong. They are correctly kept.

---

## 3. Duplicate ID analysis

Four IDs appear twice each. For each: which row came first, which came later,
and the proposed renumbering.

### ISSUE-006

| Row | Title | Position in file | First? |
|-----|-------|-----------------|--------|
| ISSUE-006 (reopened) | The PII guard was red — REOPENED | Line ~880 | SECOND |
| ISSUE-006 (original) | The PII guard was red — FIXED `cecd4223` | Line ~910 | FIRST (chronologically the original finding) |

**Proposal:** The REOPENED row is the later event and should move. Next free
number above 045 is **ISSUE-046**. The register's own precedent (ISSUE-037,
renumbered from ISSUE-034) says the LATER row moves.

### ISSUE-011

| Row | Title | Position in file | First? |
|-----|-------|-----------------|--------|
| ISSUE-011 (LinkedIn) | LinkedIn ownership allowlist went stale | Line ~720 | FIRST (added 2026-09-23) |
| ISSUE-011 (forward book) | Forward book COVERING decays silently | Line ~1380 | SECOND (found 2026-09-22 but written later in the file) |

**Proposal:** The forward book row was found 2026-09-22 (one day BEFORE the
LinkedIn row was added 2026-09-23), but it sits later in the file. By the
"later row moves" rule applied to file position: the forward book row moves
to **ISSUE-047**.

### ISSUE-012

| Row | Title | Position in file | First? |
|-----|-------|-----------------|--------|
| ISSUE-012 (ceiling) | Company-search slice ceiling 400 pages | Line ~690 | FIRST in file (added 2026-09-23) |
| ISSUE-012 (collision) | Collision gate refused batch supply | Line ~1410 | SECOND in file |

**Proposal:** The collision gate row was fixed earlier (batch 3, 2026-09-22)
but sits later in the file. By file position: the collision gate row moves
to **ISSUE-048**.

### ISSUE-016

| Row | Title | Position in file | First? |
|-----|-------|-----------------|--------|
| ISSUE-016 (recurred) | `attach_leads` REFUSED — RECURRED 2026-09-24 | Line ~430 | SECOND in file (recurred 2026-09-24) |
| ISSUE-016 (original) | `attach_leads` reports REFUSED on succeeded write | Line ~1310 | FIRST in file (first found 2026-09-22) |

**Proposal:** The RECURRED row is an update to the same defect, not a new
finding. It should either (a) be merged into the original row as an
amendment, or (b) be renumbered to **ISSUE-049**. The register already shows
it as a separate `###` heading with "RECURRED" in the title, so option (b)
is less destructive.

---

## 4. FIXED rows — evidence verification

### Rows with full evidence (commit SHA + named regression test, both verified)

| ID | Commit | Test module | Test result |
|----|--------|-------------|-------------|
| ISSUE-001 | `0379958d` ✓ | Named in text (8 tests) | Not run individually |
| ISSUE-002 | `abfc844a` ✓ | `test_task235_dnc_cannot_stop_linkedin.py` | **1 FAILURE** (SUPPORTED count drifted 15→16) |
| ISSUE-025 | `7bb23d6d` ✓ | `test_a_blank_email_can_never_be_sent_again.py` | 30 tests, OK |
| ISSUE-026 | `5257adbe` ✓ | Named (30 tests) | OK |
| ISSUE-027 | `d6a719c2` ✓ | `test_a_campaign_we_did_not_stop_is_critical.py` | Exists, not run individually |
| ISSUE-042 | `5cd5173d` ✓ | `test_a_linkedin_stop_is_not_handed_the_email_campaign.py` | 5 tests, OK |

### Rows with issues

| ID | Issue |
|----|-------|
| ISSUE-034 | Register names `EveryActorIdIsOneApifyKnows` — **that class does not exist** in `test_researchpack.py`. The file has 21 tests across 7 other classes, all green. The fix is real (commit exists, actors are verified) but the named regression test is not what the register says it is. |
| ISSUE-002 | The seal test asserts `len(SUPPORTED) == 15` but it is now 16. The register says "The seal holds: NOT in SUPPORTED or CONDITIONAL, verified after merge (still 14 verbs)." That claim is stale. |
| ISSUE-041 | Shares commit `5cd5173d` with ISSUE-042 but has no ISSUE-041-specific regression test. The fix (binding `heyreach_lead_id`) is in `src/testidentity.py`, and the test covers ISSUE-042's `_campaign_of` fix. |
| ISSUE-020 | **No commit SHA, no test name.** Claims FIXED with only "Verified - a fresh run resumed at page 17." **PROPOSED DOWNGRADE: CONFIRMED.** |
| ISSUE-013 | **No commit SHA, no test name.** Claims FIXED with only a description of the fix. **PROPOSED DOWNGRADE: CONFIRMED.** |
| ISSUE-017 | **No commit SHA.** 7 tests named but no module path. **PROPOSED DOWNGRADE: CONFIRMED** (pending commit identification). |
| ISSUE-024 | **No commit SHA.** Test file exists and passes (13 tests). **PROPOSED DOWNGRADE: CONFIRMED** (pending commit identification). |
| ISSUE-012 (collision) | **No commit SHA, no test name.** `scripts/s6_collision_walk.py` is named. **PROPOSED DOWNGRADE: CONFIRMED.** |
| ISSUE-029 | Commit `c62c6309` ✓. "5 tests" but no module name. Partial. |
| ISSUE-028 | Commit `c1d93e94` ✓. Test by `ast` but module not named. PV claim present. |
| ISSUE-031 | Commits `d7f3128a`, `a3c02e08` ✓. Test name `ThisDoesNotUnblockTheExport` given but no module path. |

---

## 5. PRODUCTION_VERIFIED rows — evidence verification

| ID | PV claim | Evidence | Supported? |
|----|----------|----------|------------|
| ISSUE-026 | "offending row was read back from the provider, stopped, and re-read as `stopped`" | Row 22356723, lead 204724, provider readback | YES — provider observation named |
| ISSUE-028 | "20 of 20 monitors have two witnesses, exit 0, on the live estate" | Live run output | YES — named observation |
| F-001 | "`provider_truth.py` completed live against all four HeyReach campaigns" | Script name + result | YES |
| F-002 | "derived set matches the provider exactly; 487 and 489 headroom answerable again" | Provider comparison | YES |

No PRODUCTION_VERIFIED row is unsupported. No downgrades proposed.

---

## 6. Rows with no named evidence

Every row in the register names some form of evidence — a measurement, a
provider readback, a commit SHA, or a document reference. The weakest rows
are:

| ID | Evidence quality |
|----|-----------------|
| ISSUE-020 | "Verified - a fresh run resumed at page 17" — no commit, no test, no measurement artifact |
| ISSUE-013 | Description of fix only — no commit, no test |
| ISSUE-008 | `finish_reason='length'` observed — adequate for NEW status |

---

## 7. Task/issue cross-reference orphans

### Direction 1: Task file references an ISSUE that has no register row

None found. Every ISSUE-xxx referenced in `docs/qwen-tasks/TODO/` has a
corresponding `### ISSUE-xxx` heading in the register.

### Direction 2: Register row references a TASK-xxx that does not exist

The register references these task IDs inline:
- TASK-235 (ISSUE-002, ISSUE-001) — exists in `DONE/`
- TASK-237 (ISSUE-003) — exists in `DONE/`
- TASK-234 (F-006) — exists in `DONE/`
- TASK-233 (F-007) — exists in `DONE/`
- TASK-232 (ISSUE-004) — exists in `DONE/`
- TASK-212, TASK-224, TASK-227, TASK-229, TASK-230, TASK-231 (ISSUE-004) — all exist in `DONE/`
- TASK-173 (ISSUE-004) — exists in `DONE/`
- TASK-293 (referenced in commit messages for ISSUE-041/042 lane work) — exists in `TODO/`

No orphans in either direction.

---

## 8. Queue hygiene table

`docs/qwen-tasks/TODO/` holds **75 files** on this worktree (qwen-worker-4).
The handoff records TODO depth as 1, which was wrong at the time of writing
and is more wrong now.

### TASK-192 and TASK-262 — cross-worktree claim check

The task says these "sit in `TODO/` on master AND in `RUNNING/` inside three
worker worktrees (qwen-worker, qwen-6, qwen-7, qwen-8 as of 2026-09-23
21:33)."

**Measured 2026-09-26:** Neither TASK-192 nor TASK-262 is in `RUNNING/` in
any of the four checked worktrees. Both are in `TODO/` in ALL of them:

| Worktree | TASK-192 | TASK-262 | mtime (epoch) |
|----------|----------|----------|---------------|
| qwen-worker-4 (this) | TODO | TODO | 1790276901 |
| qwen-worker | TODO | TODO | 1790354124 |
| qwen-6 | TODO | TODO | 1790336997 |
| qwen-7 | TODO | TODO | 1790337002 |
| qwen-8 | TODO | TODO | 1790337007 |

The RUNNING/ copies that existed on 2026-09-23 have been removed (or the
worktrees were reset). Both files are now in TODO/ everywhere, which means
they are dispatchable from any worktree but also that no worker currently
claims them.

### Dispatchable vs claimed-elsewhere vs superseded

All 75 TODO files are dispatchable in principle (none is in RUNNING/ in this
worktree). The cross-worktree check for TASK-192 and TASK-262 shows they are
not claimed elsewhere as of this measurement. No superseded files were
identified — that would require a per-file check against master's integrated
code, which is beyond this audit's scope.

---

## 9. Proposed changes (for approval)

### Renumbering (4 duplicates)

| Current | Proposed | Row |
|---------|----------|-----|
| ISSUE-006 (reopened) | ISSUE-046 | PII guard reopened |
| ISSUE-011 (forward book) | ISSUE-047 | Forward book COVERING decay |
| ISSUE-012 (collision) | ISSUE-048 | Collision gate NOT WALKED |
| ISSUE-016 (recurred) | ISSUE-049 | attach_leads recurred |

### Downgrades (FIXED without adequate evidence)

| ID | Current | Proposed | Reason |
|----|---------|----------|--------|
| ISSUE-020 | FIXED | CONFIRMED | No commit SHA, no test name |
| ISSUE-013 | FIXED | CONFIRMED | No commit SHA, no test name |
| ISSUE-017 | FIXED | CONFIRMED | No commit SHA |
| ISSUE-024 | FIXED | CONFIRMED | No commit SHA (test exists) |
| ISSUE-012 (collision) | FIXED | CONFIRMED | No commit SHA, no test name |

### Corrections

| ID | Issue |
|----|-------|
| ISSUE-034 | Register names `EveryActorIdIsOneApifyKnows` as regression test. That class does not exist. The test file has 21 tests in other classes, all green. The row should name the actual test class or say the named test was renamed. |
| ISSUE-002 | Register says seal holds at 14 verbs. `SUPPORTED` is now 16. The seal test (`test_enabling_it_moved_nothing_else`) is RED. The row's claim is stale. |

---

## 10. The checker and its caller

**Script:** `scripts/register_lint.py`
**Test:** `tests/test_the_register_has_no_duplicate_ids.py`

Run the checker:

    python scripts/register_lint.py

Run the test:

    python -m unittest tests.test_the_register_has_no_duplicate_ids

The script exits non-zero on any duplicate ID, and the test asserts zero
duplicates. Both are wired into the standard discovery path
(`python -m unittest discover`).
