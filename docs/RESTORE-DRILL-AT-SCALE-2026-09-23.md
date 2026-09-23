# The restore drill, run at scale — 2026-09-23

TASK-265's own drill report (`docs/RESTORE-DRILL-2026-09-22.md`) recorded a
run that restored **zero records** and correctly called itself `ok: false`.
That is an honest artifact and it is not a drill: nothing was proven to come
back, because nothing went in.

This is the drill run against estates that carry records, at 550 (the size
`docs/state/QUEUE-MANIFEST.json` reports for the live queue), 5,000 and
20,000. Run after the five review defects in
`docs/MERGE-REQUEST-INFRA-2026-09-23.md` §1 were fixed, so the verdict below
is one that can now be false.

## The numbers

    records   queue MB   archive MB   backup s   restore s   verdict
        550        7.9          0.1       0.04       0.109   ok
      5,000       71.5          0.6       0.26       0.937   ok
     20,000      286.0          2.3       2.04       9.374   ok

**A 20,000-record estate backs up in 2.0 seconds and restores and verifies in
9.4.** The lock is held for the archive window only — 2.0s at 20,000 records,
which is the number that matters, because that is how long a live loop would
wait behind a nightly backup.

Every arm: `stats_match` true, `manifest_matches` true, temp directory gone,
no findings.

## WHAT THIS IS NOT, STATED BEFORE THE NUMBERS GET QUOTED

**This is a synthetic estate, not the live one.** The live 550 records are in
the production session's worktree on `master`. This session does not read or
lock the live queue, so the drill here proves the mechanism and not the data.
**The production drill is still owed** and it is one command, below.

**The archive sizes are not representative and must not be planned against.**
The synthetic records pad with a repeated character, which `zipfile` deflates
about 125x. Production JSON is not compressible anywhere near that. Treat the
archive column as a floor and re-measure against the real estate before
anyone sizes a destination from it.

**The records are 14,299 bytes mean, against the production mean of 19,819**
(`docs/STORE-SQLITE-DESIGN-2026-09-22.md` §1) — 28% low. The timings are
therefore optimistic by roughly that much, and they have four orders of
magnitude of headroom, so it does not change the conclusion. It is recorded
because a benchmark measured at the wrong record size is already ISSUE-017 in
this register and it is not becoming ISSUE-018.

## The production drill, when the production session wants it

    py -3 scripts/backup_state.py --backup-dir backups
    py -3 scripts/restore_drill.py --archive-dir backups

It takes `store.lock()` for about two seconds, reads `work/`, writes only to
`backups/` and a `mkdtemp`, and deletes the temp directory. It never writes
`work/`, and `tests/test_the_backup_restores_what_it_claimed.py` asserts the
live directory's mtimes are unchanged after a drill. Expected result against
the live estate: 550 records restored, matching the manifest's 550, `ok:
true`.

## The two decisions still owed to the operator

Both were raised by TASK-265's worker and neither is resolved.

**Encryption.** Python's stdlib has none and `zipfile` supports none. The two
viable options are `cryptography` (~3 MB wheel, C extension) and `pyage`
(pure Python). Both are third-party dependencies and this repo's rule is
zero. Until a decision, the archive is **unencrypted and local-only**, which
is why the second decision is not independent of it.

**Off-machine destination.** None is configured, and the worker correctly
refused to invent one. An unencrypted archive shipped off-machine is worse
than no off-machine copy, so these two are decided together or not at all.
`work/` in full includes the action ledger, the spend ledger and client
approval — a stolen archive is a client data breach, not an inconvenience.

`config/.env` is excluded by construction and asserted in two places.

## Reproduce

    py -3 <scratch>/drill_at_scale.py

Detached, no `timeout` wrapper. About 40 seconds for all three arms.
