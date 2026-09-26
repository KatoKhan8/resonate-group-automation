PRIORITY: P2
SIZE: XS
DEPENDS:

# TASK-377 — refresh the canary disposition table against current master

**Operator instruction, 2026-09-26 evening: keep a disposition table for the
canary review findings current.** `docs/glm-reviews/TRIAGE-CANARY-b333697-2026-09-26.md`
is that table and it is now stale — every action item it lists except P1-4
has landed since it was written.

## Build

    docs/glm-reviews/TRIAGE-CANARY-b333697-2026-09-26.md   MODIFY

For each row in **THE TABLE**, verify against current `origin/master` (do not
trust this task file's summary — re-check each yourself) and update the
`Action` / `Blocks canary` columns:

    P0-1 / T-3    TASK-331    merged (commit 08af5146, "Close the resume P0")
    P1-1 / T-1    TASK-346    merged (commit 2fdb5568)
    P1-2          TASK-343    merged, retargeted (commit 7291131c) — the
                              provider-payload half now derives its delays
                              from the canonical cadence graph
    P1-3 / T-2    TASK-370    merged (commit 1a8d9a92)
    P1-4          TASK-376    created 2026-09-26 evening — resolves by rule
                              (live path decides), not by operator naming a
                              module. Update this row once TASK-376 lands,
                              not before.

**Verify each merge by effect** — the same discipline the rest of this
project uses: re-run or re-derive the acceptance evidence each task's own
DONE file claims, do not just check the commit exists. A task marked merged
here that regressed later is exactly the failure mode `docs/state/PROBLEM-REGISTER.md`
exists to catch.

Add a new **STATUS LINES** summary at the bottom reflecting the refreshed
table: how many P0/P1 items remain open, and the current master SHA.

## Acceptance

1. Every row's `Action` column reflects actual current master state, verified
   by you, not copied from this task file.
2. The STATUS LINES block is regenerated, not hand-tweaked from the old one.
3. No new finding is invented — this task updates disposition, it does not
   re-run canary review. If refreshing a row surfaces a genuine regression
   (a merged fix that no longer holds), stop and report it by name; that is a
   P0 finding, not a table edit.

## What this task may NOT do

- Do not re-run the canary review from scratch or add new rows for anything
  not already in the table (that is a fresh GLM checkpoint's job, not this
  task's).
- Nothing sent, nothing activated.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** `82ece2d6` (on `qwen-worker-11-r9`, pushed)
- **TESTS:** N/A — document-only task, no code changed. No conflict markers
  in the modified file (verified by grep).
- **FILES CHANGED:** `docs/glm-reviews/TRIAGE-CANARY-b333697-2026-09-26.md`
  (the canary disposition table and STATUS LINES section).
- **ARTIFACT KIND:** document update.

### Verification by effect (not by commit existence)

| Row | Commit | Effect verified |
|---|---|---|
| P0-1/T-3 (TASK-331) | `08af5146` | `orchestrator.py:668` passes `expect_leads=n`; `orchestrator.py:617` docstring corrected to "Suppression is re-checked by the CONDITIONAL entry on EMAIL_RESUME in providerwrites"; `EMAIL_RESUME` has CONDITIONAL in `providerwrites` |
| P1-1/T-1 (TASK-346) | `2fdb5568` | `llm.py` has `spendledger.reserve()` pre-call, `_estimate_cost`, `_settle_spend`; `BudgetExceeded` re-raised at `:357` |
| P1-2 (TASK-343) | `7291131c` | `heyreach.py:1198` `li_message_delays_from_cadence()` derives from `cadencelibrary.PRODUCTIVE_LI_HEAVY_V1`; `heyreachfactory.py:365` `_li_message_delays()` same; `heyreachfactory.py:601` passes `message_delays=_li_message_delays()` to `linkedin_sequence` |
| P1-3/T-2 (TASK-370) | `1a8d9a92` | `test_nothing_writes_to_a_provider.py` has `REQUEST_METHOD` and `REQUEST_DATA` regexes matching `Request`-object form; tests at `:303-325` confirm both shapes |
| P1-4 (TASK-376) | — | Still in `docs/qwen-tasks/TODO/`. Row left as-is per task instruction ("Update this row once TASK-376 lands, not before") |

### Regressions found

None. All four merged fixes hold at code level.

### STATUS LINES summary

- **P0 OPEN:** 0 (was 1)
- **P1 OPEN:** 1 (P1-4, TASK-376, operator decision owed)
- **Current master SHA:** `669318c4`

### FINDINGS

None beyond the table update.

### RISKS

None. This is a document-only change.

### RECOMMENDED CLAUDE ACTION

Accept the table refresh. The sole remaining open canary item is P1-4
(TASK-376), an operator decision on which research store is canonical.
