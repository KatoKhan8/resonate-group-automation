#!/usr/bin/env python3
"""2e - back up the estate's state, and PROVE the backup restores.

    py -3 scripts/server/backup.py --backup --into /var/backups/resonate
    py -3 scripts/server/backup.py --restore ARCHIVE --into /tmp/restored
    py -3 scripts/server/backup.py --drill   --into /var/backups/resonate
    py -3 scripts/server/backup.py --ship    ARCHIVE      # REFUSES today

A BACKUP THAT HAS NEVER BEEN RESTORED IS NOT A BACKUP. It is a file with a
date in its name. `--drill` is therefore the command this file exists for:
it takes a backup, restores it into a throwaway directory, and compares the
restored tree against the source BY NAME AND BY HASH. A drill that passes is
the only evidence that any of this works.

WHAT IS BACKED UP. `work/` - the queue, the campaign registry, the
heartbeats, the watch events. CLAUDE.md: "work/queue.jsonl holds record
state and work/campaigns.jsonl holds campaign state. Those two files are the
only state." Everything else in the deployment is reconstructible from git.

WHAT IS NOT, AND WHY IT IS A REFUSAL RATHER THAN AN OMISSION:

  /etc/resonate/secrets.env    NEVER. A backup is a copy that travels, and
                               the whole design of that file is that it does
                               not. It is re-created by hand from
                               docs/SECRETS-MOVE.md, which is what a
                               checklist is for.

TWO OPERATOR VALUES ARE UNFILLED, AND THIS SCRIPT REFUSES RATHER THAN
GUESSING. Per the operator's instruction for 2e and 2f: named, unfilled
inputs that refuse, rather than a guessed destination or an unencrypted
archive leaving the host.

  BACKUP_TARGET      where the archive goes off-host. UNSET. There is no
                     sensible default: a guess is either a host that does
                     not exist, or - worse - one that does and should not
                     receive this.

  BACKUP_ENCRYPTION  how the archive is encrypted before it leaves. UNSET,
                     and the 6b decision is still open. `work/` is 300 real
                     companies and 92 real contacts and "it is not ours to
                     publish" is CLAUDE.md's phrasing. An unencrypted
                     archive on someone else's disk is publishing it slowly.

`--backup`, `--restore` and `--drill` all work TODAY and are exercised by
the tests, because they are local. `--ship` is the only thing blocked, and
it refuses loudly with the names of the two values it needs.
"""
import argparse
import datetime
import hashlib
import io
import os
import shutil
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

#: Named here so the refusal can print them. Read from the environment so an
#: operator filling them changes nothing in git.
BACKUP_TARGET = "BACKUP_TARGET"
BACKUP_ENCRYPTION = "BACKUP_ENCRYPTION"

#: Never in an archive, at any size, under any flag.
NEVER_BACKED_UP = ("secrets.env", ".env")


def state_dir():
    """Where `work/` actually is, asked of the store rather than assumed."""
    from src import store
    return os.path.dirname(store.queue_path())


def _digest(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory(root):
    """{relative path: sha256} for every file under `root`.

    BY NAME AND BY HASH. A restore drill that compared counts would pass
    while a file came back truncated, and the whole point of the drill is to
    be the thing that cannot pass vacuously.
    """
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            out[rel] = _digest(full)
    return out


def compare(before, after):
    """(ok, missing, extra, changed) between two inventories.

    ITS OWN FUNCTION SO IT CAN BE TESTED DIRECTLY, and it is here because a
    mutation found the gap: replacing the whole comparison with
    `len(before) == len(after)` left the drill's test GREEN, since a healthy
    restore has equal counts either way. The test that was supposed to guard
    this asserted on `inventory()` and never reached the comparison the drill
    actually uses. A guard aimed next to the thing it guards is not a guard.
    """
    missing = sorted(set(before) - set(after))
    extra = sorted(set(after) - set(before))
    changed = sorted(k for k in set(before) & set(after)
                     if before[k] != after[k])
    return (not (missing or extra or changed)), missing, extra, changed


def _excluded(rel):
    base = os.path.basename(rel)
    return base in NEVER_BACKED_UP


def backup(source, into, now=None):
    """Write a .tar.gz of `source` into `into`. Returns the archive path."""
    if not os.path.isdir(source):
        raise SystemExit("REFUSING: %s does not exist. There is no state to "
                         "back up, and an empty archive is worse than none - "
                         "it restores cleanly over a live estate." % source)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    os.makedirs(into, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(into, "resonate-state-%s.tar.gz" % stamp)

    kept = 0
    with tarfile.open(path, "w:gz") as tar:
        for rel in sorted(inventory(source)):
            if _excluded(rel):
                sys.stderr.write("excluded (never backed up): %s\n" % rel)
                continue
            tar.add(os.path.join(source, rel), arcname=rel)
            kept += 1
    if not kept:
        os.unlink(path)
        raise SystemExit("REFUSING: nothing was added to the archive. An "
                         "empty backup is a restore that silently empties "
                         "the estate.")
    sys.stderr.write("wrote %s (%d files)\n" % (path, kept))
    return path


def restore(archive, into, force=False):
    """Extract `archive` into `into`, which must be empty unless --force.

    IT WILL NOT RESTORE OVER A LIVE ESTATE BY DEFAULT. A restore is the one
    operation that can destroy the thing it is meant to protect, and the
    command to do it is short and typed in a hurry at exactly the wrong
    moment.
    """
    if os.path.exists(into) and os.listdir(into) and not force:
        raise SystemExit(
            "REFUSING: %s is not empty. A restore over live state is how a "
            "backup destroys the estate it was taken to protect. Restore "
            "into a fresh directory and compare, or pass --force if you have "
            "decided." % into)
    os.makedirs(into, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            # A tar member naming `../` escapes the destination. The archives
            # this script writes never contain one; the archives it READS are
            # whatever was handed to it.
            name = member.name.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                raise SystemExit(
                    "REFUSING: archive member %r escapes the destination."
                    % member.name)
            if _excluded(name):
                raise SystemExit(
                    "REFUSING: archive contains %r, which is never backed up "
                    "and must never be restored from one." % member.name)
        tar.extractall(into)
    sys.stderr.write("restored into %s\n" % into)
    return into


def drill(source, into):
    """Back up, restore into a throwaway directory, compare by name and hash.

    Returns (ok, report). This is the only thing in this file that is
    evidence rather than intention.
    """
    archive = backup(source, into)
    scratch = tempfile.mkdtemp(prefix="resonate-restore-drill-")
    try:
        restore(archive, scratch)
        before = {k: v for k, v in inventory(source).items()
                  if not _excluded(k)}
        after = inventory(scratch)
        ok, missing, extra, changed = compare(before, after)
        report = [
            "DRILL %s" % ("PASSED" if ok else "FAILED"),
            "  archive     %s" % archive,
            "  files       %d" % len(before),
            "  missing     %d %s" % (len(missing), missing[:5] or ""),
            "  unexpected  %d %s" % (len(extra), extra[:5] or ""),
            "  CHANGED     %d %s" % (len(changed), changed[:5] or ""),
        ]
        if ok:
            report.append("  every file came back, byte for byte.")
        return ok, "\n".join(report)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def ship(archive):
    """Send the archive off-host. REFUSES: two operator values are unfilled."""
    target = os.environ.get(BACKUP_TARGET, "").strip()
    encryption = os.environ.get(BACKUP_ENCRYPTION, "").strip()
    problems = []
    if not target:
        problems.append(
            "  %s is unset. There is no sensible default: a guessed\n"
            "  destination is either a host that does not exist or, worse, one\n"
            "  that does and should not receive this." % BACKUP_TARGET)
    if not encryption:
        problems.append(
            "  %s is unset, and the 6b encryption decision is still\n"
            "  open. work/ is 300 real companies and 92 real contacts and it\n"
            "  is not ours to publish. An unencrypted archive on somebody\n"
            "  else's disk is publishing it slowly." % BACKUP_ENCRYPTION)
    if problems:
        sys.stderr.write(
            "REFUSING to ship %s off-host.\n\n%s\n\n"
            "Both are named, unfilled operator inputs. Fill them in\n"
            "%s and re-run. Nothing was sent.\n"
            % (os.path.basename(archive), "\n\n".join(problems),
               "/etc/resonate/secrets.env"))
        return 2
    # Deliberately not implemented past the refusal: the transport depends on
    # what BACKUP_TARGET turns out to be, and writing an scp call against a
    # guessed shape is how the guess becomes the design.
    sys.stderr.write(
        "%s and %s are set, but the transport is not built: it depends on\n"
        "what the target turns out to be. Nothing was sent.\n"
        % (BACKUP_TARGET, BACKUP_ENCRYPTION))
    return 3


def main():
    ap = argparse.ArgumentParser(description="Back up the estate, and prove it restores")
    ap.add_argument("--backup", action="store_true")
    ap.add_argument("--restore", metavar="ARCHIVE")
    ap.add_argument("--drill", action="store_true")
    ap.add_argument("--ship", metavar="ARCHIVE")
    ap.add_argument("--into", help="destination directory")
    ap.add_argument("--state-dir", help="what to back up (default: work/)")
    ap.add_argument("--force", action="store_true",
                    help="restore into a non-empty directory")
    args = ap.parse_args()

    source = args.state_dir or state_dir()

    if args.ship:
        return ship(args.ship)
    if args.drill:
        if not args.into:
            ap.error("--drill needs --into")
        ok, report = drill(source, args.into)
        print(report)
        return 0 if ok else 1
    if args.restore:
        if not args.into:
            ap.error("--restore needs --into")
        restore(args.restore, args.into, force=args.force)
        return 0
    if args.backup:
        if not args.into:
            ap.error("--backup needs --into")
        backup(source, args.into)
        return 0
    ap.error("one of --backup, --restore, --drill or --ship")


if __name__ == "__main__":
    sys.exit(main())
