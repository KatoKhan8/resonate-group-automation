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
    """Every state file that must be in the archive.

    Asks ``store.STATE_OVERRIDES`` what to back up rather than listing files
    by hand, then adds the queue and the SQLite store files.  Only files that
    actually exist on disk are returned - a fresh install has no spend ledger
    yet and that must not fail the backup.
    """
    if directory is None:
        directory = os.path.dirname(store.queue_path())
    directory = os.path.abspath(directory)

    expected_basenames = set()
    for var in store.STATE_OVERRIDES:
        expected_basenames.add(_default_basename(var))
    expected_basenames.add("queue.jsonl")
    expected_basenames.add("queue.db")
    expected_basenames.add("queue.db-wal")
    expected_basenames.add("queue.db-shm")

    found = []
    if os.path.isdir(directory):
        for fn in sorted(os.listdir(directory)):
            fp = os.path.join(directory, fn)
            if os.path.isfile(fp) and not fn.endswith(".lock"):
                found.append(fp)

    return found


def _default_basename(env_var):
    """The filename a STATE_OVERRIDES entry resolves to when unset."""
    _OVERRIDE_DEFAULTS = {
        "QUEUE_DB": "queue.db",
        "CAMPAIGNS": "campaigns.jsonl",
        "JOBS": "jobs.jsonl",
        "WORKSPACES": "workspaces.jsonl",
        "AUDIT": "audit.jsonl",
        "SENDERS": "senders.jsonl",
        "NOTIFICATIONS": "notifications.jsonl",
        "REPORTS": "reports.jsonl",
        "REPORT_DRAFTS": "report-drafts.jsonl",
        "MX_CACHE": "mx-cache.json",
        "OBSERVABILITY": "observability.jsonl",
        "CHECKPOINTS": "checkpoints.json",
        "REPLY_WATCH_STATUS": "replywatch.json",
        "TAG_OUTBOX": "tag-outbox.jsonl",
        "AGENCY_DNC": "agency-dnc.jsonl",
        "SIGNALS": "signals.jsonl",
        "GTM": "gtm.jsonl",
        "DISCOVERY": "discovery.jsonl",
        "CLIENT_REVIEW": "clientreview.jsonl",
        "CRAWL_CACHE": "crawl-cache.json",
        "KNOWLEDGE_PACK": "knowledge-pack.json",
        "SLACK_THREADS": "slack-threads.jsonl",
        "SLACK_REQUESTS": "slack-requests.jsonl",
        "SLACK_FOLLOWUPS": "slack-followups.jsonl",
        "ACTION_LEDGER": "action-ledger.jsonl",
        "SPEND_LEDGER": "spend-ledger.jsonl",
        "LEAD_OBSERVATIONS": "lead-observations.jsonl",
        "WATCH_EVENTS": "watch-events",
        "WATCH_HEARTBEAT": "heartbeat",
        "CLIENT_APPROVAL": "client-approval.jsonl",
        "CANDIDATES": "candidates.jsonl",
    }
    return _OVERRIDE_DEFAULTS.get(env_var, env_var.lower().replace("_", "-"))


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
    for fp in archives:
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

    with store.lock():
        files = collect_state_files(work_dir)

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
        "encryption_finding": (
            "Python stdlib has no encryption. Options: cryptography "
            "(pip install cryptography, ~3MB wheel), pyage (pip install "
            "pyage, pure-Python age). Zero-third-party-dep rule blocks "
            "both. Archive is local-only until a decision is made."),
        "off_machine_destination": None,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
