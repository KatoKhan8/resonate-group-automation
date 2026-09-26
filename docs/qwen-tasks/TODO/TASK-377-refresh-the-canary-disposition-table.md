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
