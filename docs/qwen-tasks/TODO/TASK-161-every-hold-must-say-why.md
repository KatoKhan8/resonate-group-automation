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
