PRIORITY: P1
DEPENDS:

# TASK-161 - 36 records are HELD and none records a reason

A hold nobody can explain is a record nobody can unblock. `scripts/funnel.py`
reports 36 HELD and zero of them carry `hold_reason`.

## WHAT TO DO

1. Find where `held` is set - `grep -rn '"held"' src/` - and for each writer,
   say whether a reason was available at that moment and simply not recorded,
   or genuinely unknown.
2. For the 36, reconstruct the reason from what IS on the record: verification
   state, drop history, events, log lines. Say how many are reconstructable
   and how many are not.
3. Classify each into: ACTIONABLE, WAITING, PERMANENT, RETRYABLE,
   HUMAN_REVIEW - with the field that decides.
4. Propose the smallest change that makes every future hold carry a
   machine-readable reason. Name the writer it belongs in.

## DELIVERABLE

`docs/HELD-RECORDS-2026-09-15.md` with the per-record classification, the
reconstructable count, and the proposed writer change.

## RULES

Read-only on `work/`. No provider writes. No model calls. Do not change `src/`
- propose; Claude integrates. Quote the snapshot stamp.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 4df5d18
- **TESTS:** N/A — read-only analysis, no src/ changes
- **FILES CHANGED:**
  - `docs/HELD-RECORDS-2026-09-15.md` (new — the deliverable)
  - `docs/qwen-tasks/RUNNING/TASK-161-every-hold-must-say-why.md` (this file — result block)
- **SNAPSHOT:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`
- **FINDINGS:**
  - 36 held records, 0 carry `hold_reason`. The field does not exist in `src/`.
  - Two writers set `rec["state"] = "held"`: `enrich.outcome()` (line 816/1249) and `generate` exception handler (line 1795). Neither writes `hold_reason`.
  - All 36 are reconstructable from log entries and contact verdicts.
  - Classification: 12 RETRYABLE (generation model errors), 9 WAITING (verification unresolved), 9 ACTIONABLE (un-drop pending re-enrichment), 3 HUMAN_REVIEW (verifier disagreement/lint), 3 PERMANENT (no contacts, should drop).
  - Proposed fix: 2 files, 3 insertion points, 1 new field (`hold_reason`). `funnel._reason()` already checks for it and will work immediately.
- **RISKS:** None — read-only analysis, no src/ changes.
- **RECOMMENDED CLAUDE ACTION:** Integrate the two-line writer changes in `enrich.py` and `generate.py` as proposed in Section 4 of the deliverable. Backfill `hold_reason` on the existing 36 from their log entries.
