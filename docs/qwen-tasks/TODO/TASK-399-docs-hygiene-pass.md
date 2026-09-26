PRIORITY: P3
SIZE: S
DEPENDS:

# TASK-399 — docs hygiene: find what's now false in the standing docs

Tonight alone corrected two stale claims found by direct measurement:
CLAUDE.md's "ONE CAMPAIGN IS SENDING, NOT EIGHT" (it was eight, three ours)
and a superseded canary disposition table. Sweep the standing docs for more
of the same class of drift.

## Scope

    CLAUDE.md
    docs/OPERATING-MODE.md
    docs/PRODUCTION-HANDOFF-2026-09-26-EVENING.md
    docs/state/PROBLEM-REGISTER.md (if referenced elsewhere as current)

For each specific, checkable claim (a count, a SHA, a "the only X is Y"
statement, a task's stated status), verify it against current master or a
read-only provider check. Report every claim found FALSE, with the
correction and its evidence — do not fix silently; a status doc changes
based on evidence, and the correction itself is the deliverable here, listed
for Claude to apply, not applied directly by this task (these are
operator-visible standing docs).

## Acceptance

1. A list of every checked claim, PASS or FALSE, with evidence for each.
2. For every FALSE claim: the correct current value, sourced (git SHA,
   provider read, file:line) — not a guess.
3. Do not touch the files yourself; report only. Claude applies the
   corrections.

## What this task may NOT do

- Do not edit any of the scoped files directly - report only.
- Read-only toward providers if a provider check is needed for one claim.
- Nothing sent, nothing activated.
