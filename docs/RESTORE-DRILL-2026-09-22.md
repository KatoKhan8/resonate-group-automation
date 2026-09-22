# Restore Drill Report — 2026-09-22

TASK-265. A backup nobody has restored is a belief, not a backup.

## What was run

1. `py -3 scripts/backup_state.py --backup-dir backups`
2. `py -3 scripts/restore_drill.py --archive-dir backups`

## Backup result

| Field | Value |
|---|---|
| Archive | `backups/resonate-state-20260922-184710.zip` |
| Files archived | 7 |
| Archive size | 2,176,070 bytes (~2.1 MB) |
| Elapsed | 0.21 seconds |
| Encrypted | No (see findings below) |

## Drill result

| Field | Value |
|---|---|
| Archive size | 2,176,070 bytes |
| Restore time | 0.067 seconds |
| Live records | 0 |
| Restored records | 0 |
| Stats match | Yes (0 = 0) |
| Manifest match | No (manifest says 550, this worktree has 0) |
| Temp dir cleaned | Yes |
| Overall verdict | `ok: false` — expected on this worktree |

## Why the verdict is false and that is correct

This worktree (`qwen-worker-6`) does not hold the live production queue.
The live estate (550 records, 6 stages) is in Claude's worktree on
`master`. The manifest in git — `docs/state/QUEUE-MANIFEST.json` — was
generated from that live estate and correctly reports 550 records. The
drill compared the restored 0 against the manifest's 550 and refused to
call it a match. That is the drill working as designed.

On Claude's worktree, where `work/queue.jsonl` carries the 550 records,
the same drill would report `ok: true`.

## Findings

### Encryption: zero-dep rule blocks it

Python's stdlib has no encryption. `zipfile` supports no encryption at
all. The two viable options:

| Library | Size | Notes |
|---|---|---|
| `cryptography` | ~3 MB wheel | Industry standard, C extension |
| `pyage` | Pure Python | age encryption format, small |

Both are third-party deps. The repo's rule is zero third-party deps.
**Decision owed from Claude:** accept one dep for encryption, or accept
unencrypted local-only archives until the server migration provides a
different mechanism.

### Off-machine destination: none configured

No S3 bucket, no Storage Box, no credential exists. The archive is
written locally. **Decision owed from Claude:** provision a destination
before the server migration.

### This worktree has no production state

The drill is structurally sound but cannot verify production data from
here. The drill must be re-run from Claude's worktree against the live
`work/` to get a meaningful `ok: true`.

## Falsifiable requirements status

| # | Requirement | Status |
|---|---|---|
| 1 | Archive contains every STATE_OVERRIDES file + queue + SQLite | Proven by test |
| 2 | config/.env is NOT in the archive | Proven by test |
| 3 | Drill restores into temp dir, live untouched | Proven by test |
| 4 | Corrupted archive FAILS loudly | Proven by test |
| 5 | Retention prunes at 14 days, keeps newest | Proven by test |
| 6 | Neither script writes work/ under test | Proven by test |
| 7 | Both use sys.executable, no timeout | Yes |
