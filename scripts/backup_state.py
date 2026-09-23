#!/usr/bin/env python3
"""Nightly backup of work/ state.

Archives every file store.STATE_OVERRIDES names, plus the queue and the
SQLite store.  config/.env is NEVER included: a backup carrying credentials
turns one stolen archive into full provider access.

Encryption needs a third-party library (cryptography, pyage).  This repo's
rule is zero third-party deps, so the archive is written unencrypted locally.
The off-machine destination is not yet configured - see FINDINGS in TASK-265.

Usage:
    py -3 scripts/backup_state.py [--backup-dir DIR] [--retention DAYS]
"""
import argparse
import datetime
import json
import os
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import store


def collect_state_files(directory=None):
    """Every state file that must be in the archive, plus what is NOT there.

    Returns ``(files, findings)``.

    Two sources, because one is not enough:

    1. Everything on disk in the work directory. That covers every
       ``STATE_OVERRIDES`` entry left UNSET, which is the normal case - they
       all default beside ``queue_path()``.
    2. Every ``STATE_OVERRIDES`` entry that IS set in the environment and
       resolves OUTSIDE the work directory. Those are invisible to a
       directory listing, and an archive that quietly omits them is a backup
       that reports success while missing the spend ledger.

    The set is asked of ``store.STATE_OVERRIDES`` rather than written down
    here. The first version of this script carried a 30-name table of
    defaults; ``SUPERVISOR_LOCKS`` and ``SUPERVISOR_STATE`` landed with
    TASK-263 the same evening and the table was already two entries stale
    before it was ever run. A list that has to be maintained is a list that
    will be wrong.
    """
    if directory is None:
        directory = os.path.dirname(store.queue_path())
    directory = os.path.abspath(directory)

    findings = []
    found = []
    seen = set()

    if os.path.isdir(directory):
        for fn in sorted(os.listdir(directory)):
            fp = os.path.join(directory, fn)
            if os.path.isfile(fp) and not fn.endswith(".lock"):
                found.append(fp)
                seen.add(os.path.normcase(fp))
    else:
        findings.append("work directory does not exist: " + directory)

    for var in store.STATE_OVERRIDES:
        raw = os.environ.get(var)
        if not raw:
            continue
        fp = os.path.abspath(raw)
        if _is_within(fp, directory):
            continue
        if not os.path.isfile(fp):
            findings.append(
                var + " points outside the work directory at " + fp
                + ", and no file is there")
            continue
        if os.path.normcase(fp) in seen:
            continue
        found.append(fp)
        seen.add(os.path.normcase(fp))
        findings.append(
            var + " resolves outside the work directory to " + fp
            + "; archived, but it will not restore beside the rest")

    queue = os.path.abspath(store.queue_path())
    if os.path.normcase(queue) not in seen:
        findings.append("the queue is not in the archive: " + queue)

    return found, findings


def _is_within(path, directory):
    """True when *path* sits inside *directory*."""
    path = os.path.normcase(os.path.abspath(path))
    directory = os.path.normcase(os.path.abspath(directory))
    try:
        return os.path.commonpath([path, directory]) == directory
    except ValueError:          # different drives on Windows
        return False


def create_archive(file_list, work_dir, backup_dir):
    """Zip the state files into a timestamped archive.

    Asserts config/.env is absent.  Returns the archive path.
    """
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive = os.path.join(backup_dir, f"resonate-state-{ts}.zip")

    work_dir = os.path.abspath(work_dir)

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in file_list:
            fp = os.path.abspath(fp)
            if ".env" in os.path.basename(fp):
                raise ValueError(
                    f"refusing to archive credential file: {fp}")
            arcname = os.path.relpath(fp, work_dir)
            zf.write(fp, arcname)

    with zipfile.ZipFile(archive, "r") as zf:
        for name in zf.namelist():
            if name.endswith(".env") or "/.env" in name:
                raise ValueError(
                    f"config/.env found in archive as {name}")

    return archive


def prune_old_archives(backup_dir, retention_days=14):
    """Remove archives older than *retention_days*, oldest first.

    **The newest archive is never pruned, whatever its age.** If backups stop
    for a month, the run that notices must not begin by deleting the only
    copy that exists - "retention 14 days" is a rule about how much history
    to keep, not permission to reach zero.

    Returns the list of removed paths.
    """
    if not os.path.isdir(backup_dir):
        return []
    cutoff = time.time() - retention_days * 86400
    archives = []
    for fn in os.listdir(backup_dir):
        if not fn.endswith(".zip"):
            continue
        fp = os.path.join(backup_dir, fn)
        if os.path.isfile(fp):
            archives.append(fp)
    archives.sort(key=lambda p: os.path.getmtime(p))

    removed = []
    for fp in archives[:-1]:            # never the newest
        if os.path.getmtime(fp) < cutoff:
            os.remove(fp)
            removed.append(fp)
    return removed


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Backup work/ state to a local zip archive.")
    p.add_argument("--backup-dir",
                   default=os.path.join(ROOT, "backups"),
                   help="Where to write archives (default: ./backups/)")
    p.add_argument("--retention", type=int, default=14,
                   help="Days to keep archives (default: 14)")
    p.add_argument("--work-dir",
                   default=None,
                   help="Override the work directory (default: from store)")
    args = p.parse_args(argv)

    work_dir = args.work_dir or os.path.dirname(store.queue_path())
    work_dir = os.path.abspath(work_dir)

    t0 = time.monotonic()

    # The lock covers the LISTING AND THE ZIP. Holding it only across the
    # listdir leaves the archive itself racing a checkpoint, and a torn
    # archive is the one failure a backup may not have. It is released before
    # the prune and before any future upload, which is what the brief asked:
    # do not hold it across the ship.
    with store.lock():
        files, findings = collect_state_files(work_dir)
        archive = create_archive(files, work_dir, args.backup_dir)

    prune_old_archives(args.backup_dir, args.retention)
    elapsed = time.monotonic() - t0
    size = os.path.getsize(archive)

    result = {
        "archive": archive,
        "files": len(files),
        "size_bytes": size,
        "elapsed_seconds": round(elapsed, 2),
        "encrypted": False,
        "findings": findings,
        "encryption_finding": (
            "Python stdlib has no encryption. Options: cryptography "
            "(pip install cryptography, ~3MB wheel), pyage (pip install "
            "pyage, pure-Python age). Zero-third-party-dep rule blocks "
            "both. Archive is local-only until a decision is made."),
        "off_machine_destination": None,
    }
    print(json.dumps(result, indent=2))
    # A finding is not a warning to read later. An archive missing the queue,
    # or missing a ledger that lives outside work/, is a failed backup and the
    # exit code has to say so or nightly cron will report success forever.
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
