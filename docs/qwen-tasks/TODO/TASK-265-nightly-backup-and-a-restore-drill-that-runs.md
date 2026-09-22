PRIORITY: P1
DEPENDS:

# TASK-265 — nightly encrypted backup, and a restore drill that actually runs

**A backup nobody has restored is a belief, not a backup.** The drill is the
deliverable; the backup is the easy half.

`docs/SERVER-MIGRATION-PLAN.md` §5 is the design. This implements it on the
CURRENT Windows machine, so it is useful before the migration rather than
after, and it is written to move to Linux unchanged.

## What is backed up

`work/` in full. That is 30 state files, and the set is
`store.STATE_OVERRIDES` plus the queue - do not enumerate them by hand, ask
the module. It includes `queue.jsonl`, `campaigns.jsonl`, the action ledger,
the spend ledger, client approval, and - newly - `queue.db`, `queue.db-wal`
and `queue.db-shm` from the SQLite store.

**`config/.env` is NOT backed up.** Secrets are restored by hand from the
password manager, deliberately. A backup carrying the credentials turns one
stolen archive into full provider access.

## Build

    scripts/backup_state.py     nightly: archive, encrypt, ship, prune
    scripts/restore_drill.py    restore into a temp dir and PROVE it

### backup_state.py

1. Take `store.lock()` for the archive window so the snapshot is consistent.
   Release it immediately after; do not hold it across the upload.
2. `tar` + `zstd` (or `zipfile` - stdlib, zero deps, and this repo's rule is
   zero third-party deps).
3. Encrypt. **If that needs a third-party library, STOP and write the finding**
   rather than adding a dependency: name the options and their cost. An
   unencrypted archive shipped off-machine is worse than no off-machine copy.
4. Ship to the off-machine target. **The target is not chosen yet** - if no
   credential or path exists, write the archive locally, record the gap as a
   FINDING, and do not invent a destination.
5. Retention 14 days, pruned by age, oldest first.

### restore_drill.py — the part that matters

Restores into a TEMP DIRECTORY and never near `work/`:

1. Restore the newest archive to a `mkdtemp`.
2. `store.use_directory(<tmp>)` and read it.
3. **Diff record counts against the live store** - total, and per state and
   per lane via `store.stats()`. The operator asked for record counts
   specifically.
4. Also compare against `docs/state/QUEUE-MANIFEST.json`, which is in git
   precisely so a restore can be checked against something that is NOT in the
   backup.
5. Report timing: archive size, restore seconds, record count, verdict.
6. **Delete the temp directory.** Two directories holding the same live estate
   is the single-writer gate broken by operator error.

**Run the drill once and record the timing in `docs/`.** A drill that leaves
no artifact did not happen.

## Falsifiable requirements

1. The backup contains every file `store.STATE_OVERRIDES` names, plus the
   queue and the SQLite store. Assert by asking the module, not by a list.
2. `config/.env` is NOT in the archive. Assert it.
3. The drill restores into a temp dir and the live `work/` is untouched -
   assert the live directory's mtimes are unchanged after a drill.
4. A drill against a DELIBERATELY CORRUPTED archive FAILS loudly. Truncate
   one and prove the drill refuses rather than reporting a smaller count as
   success.
5. Retention prunes at 14 days and keeps the newest. Drive it with faked
   mtimes rather than waiting.
6. Neither script writes `work/` under test.
7. Both use `sys.executable` and no `timeout`.

## Do not

- Do not back up or transmit `config/.env`.
- Do not add a third-party dependency without writing the finding first.
- Do not invent an off-machine destination or a credential for one.
- Do not restore over `work/`. Ever. The drill is read-only with respect to
  live state.
- Do not touch `src/providers/*`, `scripts/*_watch_loop.py` or `work/`.
